"""Streaming standard-format adapters and a bounded DuckDB occurrence catalog."""
from dataclasses import dataclass
import csv
import hashlib
import json
import os
from pathlib import Path
import time
from types import SimpleNamespace

from datatrust.image_assets import capture, secure_open, membership, walk, authorized, error, EXTENSIONS
from datatrust.text_normalization import strict_json, get, MISSING


@dataclass(frozen=True)
class ValidatedImageSourcePlan:
    metadata_sizes: list
    estimated_peak_workspace_bytes: int


def roots_for(spec):
    if spec.allowed_roots: return tuple(spec.allowed_roots)
    return tuple(dict.fromkeys(str(Path(x.source.asset_root or (x.source.path if x.source.format=='directory' else Path(x.source.path).parent)).absolute()) for x in spec.inputs))


def source_plan(spec,config):
    roots=roots_for(spec); sizes=[]
    for item in spec.inputs:
        if item.source.format=='directory':
            authorized(item.source.path,roots); sizes.append(0)
        else:
            with secure_open(item.source.path,roots) as (handle,_): sizes.append(os.fstat(handle.fileno()).st_size)
    if any(n>config.execution.max_source_bytes for n in sizes) or sum(sizes)>config.execution.max_combined_source_bytes: error('metadata_byte_limit')
    estimate=max(256*1024**2,sum(sizes)*2+min(config.limits.annotations,1000000)*256+config.limits.assets*128)
    return ValidatedImageSourcePlan(sizes,estimate)


def typed_key(value):
    if isinstance(value,bool) or value is None or not isinstance(value,(str,int)) or value=='': return None
    return json.dumps([type(value).__name__,value],ensure_ascii=True,separators=(',',':'))


def safe_yaml(raw):
    import yaml
    for event in yaml.parse(raw):
        if isinstance(event,yaml.AliasEvent) or getattr(event,'anchor',None): raise ValueError('YAML aliases and anchors are unsupported.')
    class Loader(yaml.SafeLoader): pass
    def mapping(loader,node,deep=False):
        result={}
        for k,v in node.value:
            key=loader.construct_object(k,deep=deep)
            if key in result: raise ValueError('Duplicate YAML key.')
            result[key]=loader.construct_object(v,deep=deep)
        return result
    Loader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,mapping)
    value=yaml.load(raw,Loader=Loader)
    if not isinstance(value,dict) or set(value)-{'path','train','val','test','names','nc'}: raise ValueError('Unsupported YOLO configuration fields.')
    return value


def validate_json_stream(path,config):
    import ijson
    stack=[]; root_keys=set()
    with Path(path).open('rb') as handle:
        for _,event,value in ijson.parse(handle,use_float=True):
            if event in {'start_map','start_array'}:
                stack.append(set() if event=='start_map' else None)
                if len(stack)>32: error('json_nesting_limit')
            elif event=='map_key':
                if len(stack)==1: root_keys.add(value)
                if value in stack[-1]: error('duplicate_json_key')
                stack[-1].add(value)
            elif event in {'end_map','end_array'}: stack.pop()
            elif event=='number':
                import math
                if not math.isfinite(value): error('nonfinite_json')
    if stack: error('unframeable_json')
    if not {'images','categories','annotations'}<=root_keys: error('invalid_coco_structure')


class Store:
    def __init__(self,work,spec,config,audit_id):
        self.work=work; self.con=work.con; self.spec=spec; self.config=config; self.roots=roots_for(spec); self.audit_id=audit_id
        self.files={}; self.memberships={}; self.media={}; self.metadata={}; self.read_bytes=0; self.hash_seconds=0; self.count=0; self.ann_count=0
        self.segment_budget=[0]; self.annotation_visits=0; self.vertices=0; self.runs=0; self.media_bytes={}; self.metadata_bytes={}; self.decoded_pixels=0; self.media_count=0; self.seen_media=set(); self.unavailable=set()
        self.sources={x.id:f'source_{i+1}' for i,x in enumerate(spec.inputs)}; self.locators={}; self.categories={}; self.category_definitions={}; self.physical={}
        self.con.execute('CREATE TABLE assets(path VARCHAR PRIMARY KEY, payload VARCHAR)')
        self.con.execute('CREATE TABLE occurrences(oid BIGINT, sid VARCHAR, split VARCHAR, logical VARCHAR, groups VARCHAR, path VARCHAR, payload VARCHAR)')
        self.con.execute('CREATE TABLE group_values(oid BIGINT, sid VARCHAR, namespace VARCHAR, selector VARCHAR, value VARCHAR)')
        self.con.execute('CREATE TABLE group_vectors(oid BIGINT, sid VARCHAR, namespace VARCHAR, key_set VARCHAR, value VARCHAR, complete BOOLEAN)')
        self.con.execute('CREATE TABLE annotations(oid BIGINT, sid VARCHAR, external_id VARCHAR, payload VARCHAR)')
        self.con.execute('CREATE TABLE coco_annotations(sid VARCHAR, image_key VARCHAR, annotation_key VARCHAR, payload VARCHAR)')
        self.con.execute('CREATE TABLE associated(sid VARCHAR, logical VARCHAR, payload VARCHAR)')
    def check(self):
        # Byte/hash loops check the deadline without rescanning the filesystem each MiB.
        if time.monotonic()-self.work.started>self.config.execution.max_seconds: error('deadline')
    def metadata_file(self,path,sid):
        key=str(Path(path).absolute())
        if key not in self.files:
            info,raw,seconds=capture(path,self.roots,max_bytes=self.config.execution.max_source_bytes,check=self.check)
            if raw is None: error('metadata_byte_limit')
            self.files[key]=info; self.hash_seconds+=seconds; self.read_bytes+=info['bytes']
            self.work.check('metadata capture',info['bytes'])
            snapshot=self.work.root/f'metadata-{len(self.files)}'; snapshot.write_bytes(raw); snapshot.chmod(0o600)
            info['snapshot']=str(snapshot)
        info=self.files[key]
        paths=self.metadata.setdefault(sid,set())
        if key not in paths: self.metadata_bytes[sid]=self.metadata_bytes.get(sid,0)+info['bytes']; paths.add(key)
        total=sum(self.metadata_bytes.values())
        if total>self.config.execution.max_combined_source_bytes: error('metadata_byte_limit')
        return Path(info['snapshot'])
    def media_file(self,path,sid,kind='image'):
        key=str(Path(path).absolute())
        paths=self.media.setdefault(sid,set())
        new=key not in paths
        if key not in self.seen_media:
            self.seen_media.add(key)
            if len(self.seen_media)>self.config.limits.assets: error('asset_count_limit')
        if key in self.unavailable: error('source_unavailable')
        if key not in self.files:
            try:
                with secure_open(path,self.roots) as (handle,_): admitted_size=os.fstat(handle.fileno()).st_size
            except Exception as exc:
                if getattr(exc,'code',None)=='source_unavailable': self.unavailable.add(key)
                raise
            if new and (self.media_bytes.get(sid,0)+admitted_size>self.config.source_limits.media_per_input_bytes or sum(self.media_bytes.values())+admitted_size>self.config.source_limits.combined_media_bytes): error('media_byte_limit')
            info,raw,seconds=capture(path,self.roots,max_bytes=self.config.source_limits.asset_capture_bytes,check=self.check)
            self.files[key]=info; self.hash_seconds+=seconds; self.read_bytes+=info['bytes']
            from datatrust.image_assets import decode
            if kind=='image':
                physical=tuple(info['signature'][:2])
                if physical in self.physical:
                    facts=self.physical[physical]
                else:
                    facts,_=decode(raw,self.config.limits); self.physical[physical]=facts
                    self.decoded_pixels+=facts.get('pixels',0)
                    if self.decoded_pixels>self.config.limits.decoded_pixels: error('decoded_pixel_work_limit')
                facts=dict(facts)
                extensions={'JPEG':{'.jpg','.jpeg','.jfif'},'PNG':{'.png'},'BMP':{'.bmp'},'WEBP':{'.webp'},'TIFF':{'.tif','.tiff'}}
                facts['extension_mismatch']=facts.get('format') in extensions and Path(key).suffix.lower() not in extensions[facts['format']]
                facts['sha256']=info['sha256']; facts['bytes']=info['bytes']
                self.con.execute('INSERT INTO assets VALUES (?,?)',[key,json.dumps(facts,allow_nan=False)])
            else: facts=None
        else:
            raw=None
            if kind=='image' and not self.con.execute('SELECT 1 FROM assets WHERE path=?',[key]).fetchone():
                _,raw,_=capture(path,self.roots,max_bytes=self.config.source_limits.asset_capture_bytes,expected=self.files[key],check=self.check)
                from datatrust.image_assets import decode
                facts,_=decode(raw,self.config.limits); facts.update(sha256=self.files[key]['sha256'],bytes=self.files[key]['bytes'])
                self.con.execute('INSERT INTO assets VALUES (?,?)',[key,json.dumps(facts,allow_nan=False)])
        if new: self.media_bytes[sid]=self.media_bytes.get(sid,0)+self.files[key]['bytes']; paths.add(key)
        size=self.media_bytes.get(sid,0)
        if size>self.config.source_limits.media_per_input_bytes or sum(self.media_bytes.values())>self.config.source_limits.combined_media_bytes: error('media_byte_limit')
        return self.files[key],raw
    def media_locations(self): return set().union(*self.media.values()) if self.media else set()
    def occurrence(self,item,record,location,*,annotations=None,asset_root=None):
        self.count+=1
        if self.count>self.config.limits.occurrences: error('occurrence_limit')
        m=item.mapping; value=get(record,m.path); path=None; reasons=[]
        root=Path(asset_root or item.source.asset_root or (item.source.path if item.source.format=='directory' else Path(item.source.path).parent))
        if not isinstance(value,str) or not value or '://' in value: reasons.append('invalid_asset_reference')
        else:
            candidate=root/value
            try:
                authorized(candidate,self.roots)
                self.media_file(candidate,item.id)
                path=str(candidate.absolute())
            except Exception as exc:
                if getattr(exc,'code',None) in {'source_unavailable','unsafe_or_unavailable_source','out_of_root','unsafe_path','not_regular_file'}: reasons.append(getattr(exc,'code'))
                else: raise
        logical=typed_key(get(record,m.logical_id)) if m.logical_id else None
        split=get(record,m.split) if m.split else item.role
        if not isinstance(split,str) or not split: reasons.append('invalid_split'); split='unknown'
        groups=[typed_key(get(record,k)) for k in m.groups]
        namespace=json.dumps(['namespace',item.namespace] if item.namespace is not None else ['source',item.id])
        bindings=sorted(zip(m.groups,groups))
        if bindings:
            self.con.executemany('INSERT INTO group_values VALUES (?,?,?,?,?)',[(self.count,item.id,namespace,k,v) for k,v in bindings])
            self.con.execute('INSERT INTO group_vectors VALUES (?,?,?,?,?,?)',[self.count,item.id,namespace,json.dumps([k for k,v in bindings]),json.dumps(bindings),all(v is not None for k,v in bindings)])
        payload={'location':location,'asset_path':path,'reasons':reasons,'labels':get(record,m.labels),'objects':get(record,m.objects),'mask':get(record,m.mask),
                 'status':get(record,m.status) if m.status else None,'checksum':get(record,m.checksum) if m.checksum else None,
                 'declared_width':get(record,m.width),'declared_height':get(record,m.height)}
        # Missing values are tagged, never silently interpreted as explicit null/empty.
        for key in ('labels','objects','mask','declared_width','declared_height','checksum'):
            if payload[key] is MISSING: payload[key]={'__absent__':True}
        if annotations is not None: payload['objects']=annotations
        self.con.execute('INSERT INTO occurrences VALUES (?,?,?,?,?,?,?)',[self.count,item.id,split,logical,json.dumps(groups),path,json.dumps(payload,allow_nan=False)])
        if self.count%128==0: self.work.check('image inventory and decode')
        return self.count
    def witness(self,oid):
        ref='image_'+hashlib.sha256(f'{self.audit_id}:{oid}'.encode()).hexdigest()[:24]
        if ref not in self.locators:
            row=self.con.execute('SELECT sid,path,payload,groups,split,logical FROM occurrences WHERE oid=?',[oid]).fetchone()
            if row:
                sid,path,payload,groups,split,logical=row; value=json.loads(payload)
                self.locators[ref]={'source_id':sid,'occurrence_id':oid,'path':path,'location':value['location'],'annotation':value,'groups':json.loads(groups),'split':split,'logical_key':logical}
                normalized=self.con.execute('SELECT payload FROM normalized WHERE oid=?',[oid]).fetchone() if self.con.execute("SELECT 1 FROM information_schema.tables WHERE table_name='normalized'").fetchone() else None
                if normalized: self.locators[ref]['normalized']=json.loads(normalized[0])
        if ref in self.locators and 'normalized' not in self.locators[ref] and self.con.execute("SELECT 1 FROM information_schema.tables WHERE table_name='normalized'").fetchone():
            row=self.con.execute('SELECT payload FROM normalized WHERE oid=?',[oid]).fetchone()
            if row: self.locators[ref]['normalized']=json.loads(row[0])
        return ref


def manifest_rows(store,source,sid):
    snapshot=store.metadata_file(source.path,sid)
    if source.format=='jsonl':
        with snapshot.open('rb') as f:
            ordinal=0; offset=0
            while raw:=f.readline(store.config.execution.max_record_bytes+1):
                ordinal+=1
                if len(raw)>store.config.execution.max_record_bytes: error('record_limit')
                loc={'ordinal':ordinal,'byte_start':offset,'byte_length':len(raw)}; offset+=len(raw)
                if not raw.strip(): continue
                try:
                    record=strict_json(raw.decode(source.encoding))
                    if not isinstance(record,dict): raise ValueError('non-object')
                except (ValueError,UnicodeError): yield {},loc|{'invalid_record':True}; continue
                from datatrust.text_normalization import validate_tree
                from datatrust.text_contracts import TextWorkLimits
                validate_tree(record,TextWorkLimits(max_nested_items=100000))
                yield record,loc
    else:
        csv.field_size_limit(store.config.execution.max_record_bytes)
        with snapshot.open(encoding=source.encoding,newline='') as f:
            record_bytes=[0]
            def lines():
                while True:
                    line=f.readline(store.config.execution.max_record_bytes+1)
                    if not line: break
                    record_bytes[0]+=len(line.encode('utf8'))
                    if record_bytes[0]>store.config.execution.max_record_bytes: error('record_limit')
                    yield line
            reader=csv.DictReader(lines(),strict=True)
            if not reader.fieldnames or len(set(reader.fieldnames))!=len(reader.fieldnames) or any(not x for x in reader.fieldnames): error('csv_header')
            if set(source.json_columns)-set(reader.fieldnames): error('undeclared_json_column')
            record_bytes[0]=0
            for i,row in enumerate(reader,1):
                record_bytes[0]=0
                if None in row or any(v is None for v in row.values()): error('csv_structure')
                if sum(len(v.encode('utf8')) for v in row.values())>store.config.execution.max_record_bytes: error('record_limit')
                for col in source.json_columns:
                    try: row[col]=strict_json(row[col])
                    except ValueError: row[col]={'__invalid_json__':True}
                yield row,{'ordinal':i,'line_end':reader.line_num}


def ingest(store,item):
    source=item.source
    if source.format=='directory':
        root,rel=authorized(source.path,store.roots); directory=root/rel; store.memberships[str(directory)]=membership(directory,store.roots,check=store.check)
        for path in walk(directory,store.roots,check=store.check):
            if path.suffix.lower() not in EXTENSIONS: continue
            relative=path.relative_to(directory)
            record={'path':str(relative)}
            if source.layout=='class_subdirectories':
                record['labels']=relative.parts[0] if len(relative.parts)>1 else {'__absent__':True}
            store.occurrence(item,record,{'relative_path':str(relative)},asset_root=directory)
    elif source.format in {'csv','jsonl'}:
        for record,loc in manifest_rows(store,source,item.id): store.occurrence(item,record,loc)
    elif source.format=='coco':
        import ijson
        snapshot=store.metadata_file(source.path,item.id); validate_json_stream(snapshot,store.config)
        cats=[]
        with snapshot.open('rb') as f:
            for cat in ijson.items(f,'categories.item',use_float=True):
                cats.append(cat)
                if len(cats)>store.config.execution.max_columns: error('category_limit')
        if len(cats)>store.config.execution.max_columns: error('category_limit')
        store.categories[item.id]=[c.get('id') for c in cats]
        store.category_definitions[item.id]=[{'id':c.get('id'),'name':c.get('name'),'supercategory':c.get('supercategory')} for c in cats]
        if any(typed_key(c.get('id')) is None for c in cats) or len({typed_key(c['id']) for c in cats})!=len(cats): error('duplicate_or_invalid_category_id')
        with snapshot.open('rb') as f:
            for i,image in enumerate(ijson.items(f,'images.item',use_float=True),1):
                if not isinstance(image,dict) or typed_key(image.get('id')) is None: error('invalid_coco_image_id')
                record=dict(image); record.update(path=image.get('file_name'),width=image.get('width'),height=image.get('height'),id=image.get('id'))
                from dataclasses import replace
                mapped=replace(item,mapping=replace(item.mapping,path='path',logical_id=item.mapping.logical_id or 'id',width=item.mapping.width or 'width',height=item.mapping.height or 'height'))
                store.occurrence(mapped,record,{'collection':'images','ordinal':i})
        with snapshot.open('rb') as f:
            for ann in ijson.items(f,'annotations.item',use_float=True):
                if not isinstance(ann,dict): error('invalid_coco_annotation')
                store.ann_count+=1
                if store.ann_count>store.config.limits.annotations: error('annotation_limit')
                raw=json.dumps(ann,allow_nan=False)
                if len(raw.encode())>store.config.execution.max_record_bytes: error('annotation_record_limit')
                store.con.execute('INSERT INTO coco_annotations VALUES (?,?,?,?)',[item.id,typed_key(ann.get('image_id')),typed_key(ann.get('id')),raw])
    else:
        from dataclasses import replace
        snapshot=store.metadata_file(source.path,item.id)
        if snapshot.stat().st_size>store.config.execution.max_record_bytes: error('yolo_yaml_limit')
        declaration=safe_yaml(snapshot.read_text())
        names=declaration.get('names')
        if isinstance(names,list): names=dict(enumerate(names))
        if not isinstance(names,dict) or set(names)!=set(range(len(names))) or any(not isinstance(v,str) for v in names.values()): error('invalid_yolo_categories')
        if declaration.get('nc',len(names))!=len(names): error('invalid_yolo_categories')
        store.categories[item.id]=list(names)
        store.category_definitions[item.id]=[{'id':i,'name':names[i]} for i in sorted(names)]
        root=Path(source.asset_root or Path(source.path).parent/declaration.get('path',''))
        for split,role in [('train','train'),('val','validation'),('test','test')]:
            entries=declaration.get(split,[]); entries=[entries] if isinstance(entries,str) else entries
            if not isinstance(entries,list) or any(not isinstance(x,str) for x in entries): error('invalid_yolo_split')
            for entry in entries:
                target=root/entry; authorized(target,store.roots)
                if target.suffix=='.txt':
                    listing=store.metadata_file(target,item.id)
                    paths=(root/x.strip() for x in listing.read_text().splitlines() if x.strip())
                else:
                    store.memberships[str(target.absolute())]=membership(target,store.roots,check=store.check)
                    paths=(p for p in walk(target,store.roots,check=store.check) if p.suffix.lower() in EXTENSIONS)
                for image in paths:
                    parts=list(image.parts)
                    if 'images' not in parts: error('yolo_label_layout')
                    pos=len(parts)-1-parts[::-1].index('images'); parts[pos]='labels'
                    label=Path(*parts).with_suffix('.txt'); objects=[]; absent=False
                    try:
                        label_snapshot=store.metadata_file(label,item.id)
                        for line in label_snapshot.open(encoding='utf8'):
                            if not line.strip(): continue
                            tokens=line.split()
                            try:
                                if len(tokens)!=5 or not tokens[0].isdigit(): raise ValueError()
                                import math
                                values=[float(v) for v in tokens[1:]]
                                if not all(math.isfinite(v) for v in values): raise ValueError()
                                objects.append({'category':int(tokens[0]),'bbox':values,'format':'normalized_cxcywh'})
                                if len(objects)*128>store.config.execution.max_record_bytes: error('annotation_collection_limit')
                            except ValueError: objects.append({'invalid_row':True})
                    except Exception as exc:
                        if getattr(exc,'code',None)=='source_unavailable': absent=not item.annotations.missing_yolo_labels_are_negative
                        else: raise
                    mapped=replace(item,role=role,mapping=replace(item.mapping,path='path'),annotations=replace(item.annotations,box_format='normalized_cxcywh'))
                    store.occurrence(mapped,{'path':str(image.absolute()),'objects':{'__absent__':True} if absent else objects}, {'image':str(image.relative_to(root))},asset_root=root)
    if item.annotations.associated_source:
        for record,loc in manifest_rows(store,item.annotations.associated_source,item.id):
            logical=typed_key(get(record,item.annotations.associated_key))
            store.con.execute('INSERT INTO associated VALUES (?,?,?)',[item.id,logical,json.dumps(record,allow_nan=False)])
    pixels=store.con.execute("SELECT coalesce(sum(json_extract(payload,'$.pixels')::BIGINT),0) FROM assets").fetchone()[0]
    if pixels>store.config.limits.decoded_pixels: error('decoded_pixel_work_limit')
