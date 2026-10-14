"""Original-coordinate text primitives, strict framing and bounded disk ingestion."""
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil

from datatrust.contracts import AnalysisError
from datatrust.ingestion import source_signature, source_digest
from datatrust.scalable import fail

MISSING = object()


def strict_json(value):
    def pairs(items):
        result={}
        for k,v in items:
            if k in result: raise ValueError('duplicate_key')
            result[k]=v
        return result
    def constant(value): raise ValueError('nonfinite_json')
    def finite_float(value):
        import math
        result=float(value)
        if not math.isfinite(result):raise ValueError('nonfinite_json')
        return result
    return json.loads(value,object_pairs_hook=pairs,parse_constant=constant,parse_float=finite_float)


def get(value, path):
    if not path: return MISSING
    parts=path[1:].split('/') if path.startswith('/') else [path]
    for part in parts:
        part=part.replace('~1','/').replace('~0','~')
        if isinstance(value,dict): value=value.get(part,MISSING)
        elif isinstance(value,list) and part.isdigit() and (part=='0' or not part.startswith('0')) and int(part)<len(value): value=value[int(part)]
        else: return MISSING
    return value


def pointer(path):
    return path if path.startswith('/') else '/'+path.replace('~','~0').replace('/','~1')


def lexical(value):
    # JSON numeric/boolean identities are not silently promoted to lexical strings.
    return value if isinstance(value,str) and value!='' and not any(0xd800<=ord(c)<=0xdfff for c in value) else None


def state(value):
    if value is MISSING:return 'absent'
    if value is None:return 'null'
    if not isinstance(value,str) or any(0xd800<=ord(c)<=0xdfff for c in value):return 'invalid'
    if value=='':return 'empty'
    if value.isspace():return 'whitespace'
    return 'present'


def graphemes(text):
    import regex
    return regex.findall(r'\X',text)


def views(text,names):
    import unicodedataplus as u
    result={'raw':text}
    if 'nfc' in names:result['nfc']=u.normalize('NFC',text)
    if 'casefold' in names:result['casefold']=u.normalize('NFC',text).casefold()
    if 'whitespace' in names:result['whitespace']=' '.join(text.split())
    return result


def span_bounds(text,start,end,unit='codepoint',tokens=None):
    if any(isinstance(x,bool) or not isinstance(x,int) for x in (start,end)) or start<0 or end<start: raise ValueError('invalid_offset')
    if unit=='token':
        if tokens is None or end>len(tokens):raise ValueError('invalid_token_offset')
        if start==end:
            if start==len(tokens):return len(text),len(text)
            return tokens[start]['start'],tokens[start]['start']
        return tokens[start]['start'],tokens[end-1]['end']
    if unit=='codepoint':
        if end>len(text):raise ValueError('offset_out_of_bounds')
        return start,end
    offsets={0:0};n=0
    for i,c in enumerate(text):
        n+=len(c.encode('utf-8')) if unit=='utf8' else len(c.encode('utf-16-le'))//2
        offsets[n]=i+1
    if start not in offsets or end not in offsets:raise ValueError('offset_splits_character')
    return offsets[start],offsets[end]


def validate_tree(value,limits):
    pending=[(value,0)];count=0
    while pending:
        item,depth=pending.pop();count+=1
        if depth>limits.max_depth or count>limits.max_nested_items:
            fail('Nested input exceeds declared hard limits.','text_expansion_limit','ingestion')
        if isinstance(item,dict):pending.extend((x,depth+1) for x in item.values())
        elif isinstance(item,list):pending.extend((x,depth+1) for x in item)


def capture(path):
    path=Path(path)
    if not path.is_file():fail('A required source is unavailable.','source_unavailable','ingestion')
    sig=source_signature(path);digest=source_digest(path)
    if sig!=source_signature(path):fail('Source changed while hashing.','source_changed','ingestion')
    return {'path':str(path.resolve()),'signature':sig,'sha256':digest,'bytes':sig[2]}


def verify(info):
    try:
        if tuple(info['signature'])!=source_signature(info['path']) or source_digest(info['path'])!=info['sha256']:
            fail('Source changed after confirmation or ingestion.','source_changed','integrity')
    except OSError as exc:raise AnalysisError('Source unavailable after confirmation.',code='source_changed',stage='integrity') from exc


def frames(path,source,options,limits):
    """Yield location, record, invalidity. Separators have record=None, reason=None."""
    if source.format=='jsonl':
        with Path(path).open('rb') as handle:
            ordinal=0;offset=0
            while True:
                raw=handle.readline(options.max_record_bytes+1)
                if not raw:break
                ordinal+=1
                if len(raw)>options.max_record_bytes:fail('JSONL physical line exceeds record limit.','record_limit','ingestion')
                loc={'ordinal':ordinal,'byte_start':offset,'byte_length':len(raw),'record_sha256':hashlib.sha256(raw).hexdigest()};offset+=len(raw)
                if ordinal==1 and source.encoding=='utf-8-sig':raw=raw.removeprefix(b'\xef\xbb\xbf')
                if not raw.strip():yield loc,None,None;continue
                try:
                    record=strict_json(raw.decode('utf-8'))
                    if not isinstance(record,dict):raise ValueError('non_object_root')
                except (UnicodeError,ValueError,RecursionError) as exc:
                    if isinstance(exc,RecursionError):fail('JSON nesting exceeds parser capacity.','text_expansion_limit','ingestion')
                    yield loc,None,'invalid_jsonl_record';continue
                validate_tree(record,limits)
                yield loc,record,None
    else:
        with Path(path).open(encoding=source.encoding,newline='') as handle:
            size=0;first_line=1
            def lines():
                nonlocal size
                while True:
                    value=handle.readline(options.max_record_bytes+1)
                    if not value:break
                    size+=len(value.encode(source.encoding))
                    if size>options.max_record_bytes:fail('CSV logical record exceeds record limit.','record_limit','ingestion')
                    yield value
            headers=None;ordinal=0
            csv.field_size_limit(options.max_record_bytes)
            try:
                reader=csv.reader(lines(),delimiter=source.delimiter,quotechar=source.quotechar,strict=True)
                for row in reader:
                    loc={'ordinal':ordinal+1,'line_start':first_line,'line_end':reader.line_num};first_line=reader.line_num+1;size=0
                    if not row:yield loc,None,None;continue
                    if headers is None:
                        headers=row
                        if len(headers)>options.max_columns:fail('CSV header exceeds column limit.','column_limit','ingestion')
                        if not all(headers) or len(set(headers))!=len(headers):raise ValueError('CSV headers must be nonempty and unique.')
                        if set(source.json_columns)-set(headers):raise ValueError('JSON-valued CSV column is undeclared in header.')
                        yield {'header':headers},None,None;continue
                    ordinal+=1;loc['ordinal']=ordinal
                    if len(row)!=len(headers):fail('CSV record width differs from its header.','csv_structure','ingestion')
                    record=dict(zip(headers,row));invalid=[]
                    for name in source.json_columns:
                        try:record[name]=strict_json(record[name])
                        except RecursionError:fail('JSON cell exceeds parser nesting capacity.','text_expansion_limit','ingestion')
                        except ValueError:
                            invalid.append(name);record[name]={'__datatrust_invalid_json_cell__':True,'raw':record[name]}
                    validate_tree(record,limits)
                    yield loc,record,{'invalid_json_cells':invalid} if invalid else None
                if headers is None:raise ValueError('CSV requires a header.')
            except (csv.Error,UnicodeError) as exc:
                raise AnalysisError('CSV decoding or framing is invalid.',code='csv_structure',stage='ingestion') from exc


SCHEMA={
 'records':'rid VARCHAR,sid VARCHAR,ordinal BIGINT,lid VARCHAR,split VARCHAR,payload VARCHAR,loc VARCHAR,valid BOOLEAN',
 'content':'uid VARCHAR,rid VARCHAR,sid VARCHAR,field VARCHAR,kind VARCHAR,role VARCHAR,split VARCHAR,state VARCHAR,text VARCHAR,chars BIGINT,graphemes BIGINT,bytes BIGINT,scripts VARCHAR,controls BIGINT',
 'representations':'uid VARCHAR,representation VARCHAR,digest VARCHAR,text VARCHAR',
 'invalid':'ref VARCHAR,rid VARCHAR,sid VARCHAR,reason VARCHAR',
 'annotations':'aid VARCHAR,rid VARCHAR,uid VARCHAR,kind VARCHAR,state VARCHAR,expected VARCHAR,status VARCHAR,labels VARCHAR,metadata_state VARCHAR',
 'messages':'mid VARCHAR,rid VARCHAR,sid VARCHAR,conv VARCHAR,position BIGINT,role VARCHAR,state VARCHAR,payload VARCHAR',
 'assets':'aid VARCHAR,rid VARCHAR,sid VARCHAR,kind VARCHAR,state VARCHAR',
 'links':'rid VARCHAR,sid VARCHAR,kind VARCHAR,target_sid VARCHAR,target_key VARCHAR,query_sid VARCHAR,query_key VARCHAR,start_value VARCHAR,end_value VARCHAR,grade VARCHAR',
 'intervals':'rid VARCHAR,parent_uid VARCHAR,start_pos BIGINT,end_pos BIGINT',
 'annotation_items':'aid VARCHAR,ordinal BIGINT,state VARCHAR,start_pos BIGINT,end_pos BIGINT',
 'tokens':'aid VARCHAR,ordinal BIGINT,start_pos BIGINT,end_pos BIGINT,valid BOOLEAN',
 'locators':'ref VARCHAR,payload VARCHAR',
 'pending_annotations':'sid VARCHAR,rid VARCHAR,loc VARCHAR,payload VARCHAR',
}


class Store:
    def __init__(self,work,spec,config,collector):
        self.work=work;self.con=work.con;self.spec=spec;self.config=config;self.e=collector
        self.buffers={t:[] for t in SCHEMA};self.buffer_bytes=0;self.items=0;self.asset_count=0;self.asset_bytes=0
        self.asset_cache={};self.sources={};self.tokens=0;self.annotations=0
        for table,schema in SCHEMA.items():self.con.execute(f'CREATE TABLE {table}({schema})')
    def add(self,table,row):
        self.items+=1
        if self.items>self.config.limits.max_items:fail('Normalized item population exceeds hard limit.','text_item_limit')
        self.buffers[table].append(row);self.buffer_bytes+=sum(len(v.encode('utf8')) if isinstance(v,str) else 8 for v in row)
        if self.buffer_bytes>=min(self.config.execution.batch_bytes,16*1024**2):self.flush()
    def flush(self):
        import pandas as pd
        for table,rows in self.buffers.items():
            if rows:
                columns=[v.strip().split()[0] for v in SCHEMA[table].split(',')]
                frame=pd.DataFrame(rows,columns=columns)
                self.con.register('_text_batch',frame)
                self.con.execute(f'INSERT INTO {table} SELECT * FROM _text_batch')
                self.con.unregister('_text_batch');rows.clear()
        self.buffer_bytes=0;self.work.check('text ingestion batch')
    def invalid(self,rid,sid,loc,reason):
        ref=self.e.ref({**loc,'source_id':sid,'reason':reason})
        self.add('locators',(ref,json.dumps({**loc,'source_id':sid,'reason':reason})))
        self.add('invalid',(ref,rid,sid,reason))
        return ref
    def content(self,item,rid,loc,field,value,selector_path=None):
        import unicodedataplus as u
        selected=selector_path or field.selector
        uid=hashlib.sha256((rid+'\0'+field.name+'\0'+selected).encode()).hexdigest()
        self.add('locators',(uid,json.dumps({k:v for k,v in loc.items() if k!='_record'}|{'source_id':item.id,'selector':selected,'content_sha256':hashlib.sha256(value.encode()).hexdigest() if isinstance(value,str) and state(value)!='invalid' else None,'asset_selector':field.asset.selector if field.asset else None,'asset_encoding':field.asset.encoding if field.asset else None})))
        st=state(value);text=value if st not in {'absent','null','invalid'} else None
        if text is not None and len(text.encode('utf8'))>self.config.execution.max_record_bytes:fail('Decoded text exceeds record limit.','record_limit')
        scripts={};controls=0;ng=0
        if text is not None:
            ng=len(graphemes(text))
            from collections import Counter
            for c,n in Counter(text).items():
                script=u.script(c);scripts[script]=scripts.get(script,0)+n
                controls+=n*(u.category(c) in {'Cc','Cf'} and c not in '\t\n\r')
            for name,v in views(text,self.config.representations).items():
                self.add('representations',(uid,name,hashlib.sha256(v.encode()).hexdigest(),v))
        split=lexical(get(loc.get('_record',{}),item.split_selector)) or item.role
        self.add('content',(uid,rid,item.id,field.name,field.kind,item.role,split,st,text,len(text) if text is not None else None,ng if text is not None else None,len(text.encode()) if text is not None else None,json.dumps(scripts),controls))
        if st=='invalid' or field.required and st in {'absent','null','empty','whitespace'}:
            self.invalid(rid,item.id,{k:v for k,v in loc.items() if k!='_record'}|{'selector':selected},'invalid_content' if st=='invalid' else 'required_content_missing')
        return uid,text,st
    def asset(self,item,rid,loc,asset):
        self.asset_count+=1
        if self.asset_count>self.config.limits.max_assets:fail('Asset reference count exceeds hard limit.','asset_limit')
        value=get(loc['_record'],asset.selector);st=state(value);info=None;text=None
        if st=='present':
            path=(Path(item.source.path).parent/value).resolve()
            roots=self.spec.allowed_roots or (str(Path(item.source.path).resolve().parent),)
            readable=True
            if any(path.is_relative_to(Path(r)) for r in roots) and path.is_file():
                try:
                    with path.open('rb') as handle:handle.read(1)
                except OSError:readable=False
            if not any(path.is_relative_to(Path(r)) for r in roots):st='out_of_root'
            elif not path.is_file() or not readable:st='unavailable'
            elif asset.kind=='text' and path.suffix.lower()!='.txt':st='wrong_media'
            else:
                if str(path) not in self.asset_cache:
                    info=capture(path)
                    if info['bytes']>self.config.execution.max_source_bytes or asset.kind=='text' and info['bytes']>self.config.execution.max_record_bytes:fail('Referenced asset exceeds its hard byte limit.','asset_limit')
                    self.asset_bytes+=info['bytes']
                    if self.asset_bytes+sum(x['bytes'] for x in self.sources.values())>self.config.execution.max_combined_source_bytes:fail('Combined source and asset bytes exceed limit.','asset_limit')
                    self.work.check('asset snapshot',info['bytes']*2)
                    snapshot=self.work.root/f'asset-{len(self.asset_cache)}'
                    shutil.copyfile(path,snapshot);os.chmod(snapshot,0o600);verify(info)
                    if source_digest(snapshot)!=info['sha256']:fail('Asset snapshot integrity failed.','source_changed')
                    info['snapshot']=str(snapshot);self.asset_cache[str(path)]=info
                info=self.asset_cache[str(path)]
                expected=get(loc['_record'],asset.checksum_selector)
                if expected is not MISSING and expected!=info['sha256']:st='checksum_mismatch'
                if asset.kind=='text':
                    try:text=Path(info['snapshot']).read_bytes().decode(asset.encoding);st=state(text) if st=='present' else st
                    except UnicodeError:st='invalid_encoding'
                else:
                    with Path(info['snapshot']).open('rb') as handle:magic=handle.read(16)
                    if not (magic.startswith(b'\x89PNG\r\n\x1a\n') or magic.startswith(b'\xff\xd8\xff')) or path.suffix.lower() not in {'.png','.jpg','.jpeg'}:st='wrong_media'
        ref=self.e.ref({k:v for k,v in loc.items() if k!='_record'}|{'source_id':item.id,'selector':asset.selector,'asset':{k:v for k,v in info.items() if k!='snapshot'} if info else None,'encoding':asset.encoding})
        self.add('assets',(ref,rid,item.id,asset.kind,st))
        self.add('locators',(ref,json.dumps({k:v for k,v in loc.items() if k!='_record'}|{'source_id':item.id,'selector':asset.selector,'asset':{k:v for k,v in info.items() if k!='snapshot'} if info else None,'encoding':asset.encoding})))
        if st not in {'present','empty','whitespace'}:self.add('invalid',(ref,rid,item.id,'invalid_asset_'+st))
        return text if st in {'present','empty','whitespace'} else MISSING


def ingest(store,item):
    source=capture(item.source.path);store.sources[item.id]=source
    if store.asset_bytes+sum(x['bytes'] for x in store.sources.values())>store.config.execution.max_combined_source_bytes:fail('Combined source and asset bytes exceed limit.','asset_limit')
    store.work.check('source snapshot',source['bytes']*3)
    snapshot=store.work.root/f'source-{len(store.sources)}';shutil.copyfile(source['path'],snapshot);os.chmod(snapshot,0o600);verify(source)
    if source_digest(snapshot)!=source['sha256']:fail('Source snapshot integrity failed.','source_changed')
    counts={'records':0,'valid_records':0,'invalid_records':0,'separators':0}
    headers=None
    for loc,record,reason in frames(snapshot,item.source,store.config.execution,store.config.limits):
        if 'header' in loc:
            headers=loc['header'];declared=[f.selector for f in item.fields]+[x for x in (item.id_selector,item.split_selector) if x]+[a.selector for a in item.annotations]
            if any((x[1:].split('/')[0] if x.startswith('/') else x).replace('~1','/').replace('~0','~') not in headers for x in declared):raise ValueError('Declared CSV field is absent from header.')
            continue
        if record is None and reason is None:counts['separators']+=1;continue
        counts['records']+=1
        if counts['records']>store.config.execution.max_rows:fail('Per-source record count exceeds limit.','record_limit')
        rid=hashlib.sha256((source['sha256']+'\0'+item.id+'\0'+str(loc['ordinal'])).encode()).hexdigest()
        counts['valid_records' if record is not None else 'invalid_records']+=1
        lid=lexical(get(record,item.id_selector)) if record else None;split=lexical(get(record,item.split_selector)) if record else None
        store.add('records',(rid,item.id,loc['ordinal'],lid,split or item.role,json.dumps(record,ensure_ascii=True) if record is not None else None,json.dumps(loc),record is not None))
        store.add('locators',(rid,json.dumps(loc|{'source_id':item.id,**({'reason':reason} if record is None else {})})))
        if record is None:store.invalid(rid,item.id,loc,reason);continue
        if item.id_selector and lid is None:store.invalid(rid,item.id,loc|{'selector':item.id_selector},'invalid_or_missing_identity')
        if reason:
            for cell in reason['invalid_json_cells']:store.invalid(rid,item.id,loc|{'selector':cell},'invalid_json_cell')
        loc=loc|{'_record':record};units={}
        for f in item.fields:
            value=store.asset(item,rid,loc,f.asset) if f.asset else get(record,f.selector)
            units[f.name]=store.content(item,rid,loc,f,value)
        for name in item.task.output_fields:
            if item.task.required_outputs and units[name][2] in {'absent','null','empty','whitespace'}:store.invalid(rid,item.id,{k:v for k,v in loc.items() if k!='_record'}|{'selector':next(f.selector for f in item.fields if f.name==name)},'required_output_missing')
        from datatrust.text_diagnostics import ingest_annotations,ingest_conversation
        ingest_annotations(store,item,rid,loc,record,units)
        if any(a.content_source for a in item.annotations):store.add('pending_annotations',(item.id,rid,json.dumps({k:v for k,v in loc.items() if k!='_record'}),json.dumps(record,ensure_ascii=True)))
        if item.conversation:ingest_conversation(store,item,rid,loc,record)
        for asset in item.assets:store.asset(item,rid,loc,asset)
        r=item.retrieval
        if r and r.kind in {'chunk','judgment','reference'}:
            def serialized(x):return None if x is MISSING else json.dumps(x,ensure_ascii=True,allow_nan=False)
            store.add('links',(rid,item.id,r.kind,r.parent_source or r.target_source,lexical(get(record,r.parent_selector or r.target_selector)),r.query_source,lexical(get(record,r.query_selector)),serialized(get(record,r.start_selector)),serialized(get(record,r.end_selector)),serialized(get(record,r.grade_selector))))
    store.flush()
    return counts
