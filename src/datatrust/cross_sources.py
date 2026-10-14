"""M9 narrow disk projections and frozen local source identities."""
from dataclasses import asdict
from pathlib import Path
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
import shutil
import time
import unicodedataplus as unicode

from datatrust.image_assets import capture, secure_open
from datatrust.text_normalization import frames, get, MISSING
from datatrust.text_contracts import TextSourceSpec, TextWorkLimits
from datatrust.cross_private_base import digest
from datatrust.scalable import fail


def value(record,sel):
    v=get(record,sel)
    return None if v is MISSING else v


def key(record,selectors,representation='typed'):
    values=[]
    for sel in selectors:
        v=value(record,sel)
        if v is None or v=='' or isinstance(v,(list,dict)) or any(0xd800<=ord(c)<=0xdfff for c in str(v)): return None
        if representation=='numeric':
            try:
                if isinstance(v,bool): return None
                d=Decimal(str(v))
                if not d.is_finite(): return None
                if abs(d.adjusted())>4096: return None
                canonical=format(d,'f');canonical=canonical.rstrip('0').rstrip('.') if '.' in canonical else canonical
                values.append(['numeric','0' if d==0 else canonical])
            except InvalidOperation: return None
        elif representation in {'lexical','nfc'}:
            if not isinstance(v,str): return None
            values.append(['str',unicode.normalize('NFC',v) if representation=='nfc' else v])
        else: values.append([type(v).__name__,str(v) if isinstance(v,Decimal) else v])
    return json.dumps(values,ensure_ascii=True,allow_nan=False,separators=(',',':'))


def record_id(sid,ordinal): return digest([sid,ordinal])


class NativeDate(str): pass
class NativeTimestamp(str): pass


def encode_record(record):
    decimals=[];native=[]
    def visit(v,path):
        if isinstance(v,Decimal): decimals.append((path,str(v)));return str(v)
        if isinstance(v,(NativeDate,NativeTimestamp)): native.append((path,type(v).__name__));return str(v)
        if isinstance(v,dict): return {k:visit(x,[*path,k]) for k,x in v.items()}
        if isinstance(v,list): return [visit(x,[*path,i]) for i,x in enumerate(v)]
        return v
    result=visit(record,[])
    return json.dumps({'record':result,'decimals':decimals,'native':native},ensure_ascii=True,allow_nan=False)


def decode_record(payload):
    envelope=json.loads(payload);record=envelope['record']
    for path,v in envelope['decimals']:
        parent=record
        for part in path[:-1]: parent=parent[part]
        parent[path[-1]]=Decimal(v)
    for path,kind in envelope.get('native',[]):
        parent=record
        for part in path[:-1]: parent=parent[part]
        parent[path[-1]]=(NativeDate if kind=='NativeDate' else NativeTimestamp)(parent[path[-1]])
    return record


class Store:
    def __init__(self,work,spec,config):
        self.work=work;self.con=work.con;self.spec=spec;self.config=config
        self.files={};self.unavailable=set();self.sources={x.id:x for x in spec.inputs};self.snapshots={};self.locators={};self.private_targets={}
        self.populations={};self.asset_cache={};self.asset_units={};self.read_bytes=0;self.hash_seconds=0;self.pages=0;self.characters=0;self.documents=0;self.total_bytes=0;self.total_rows=0;self.discovery_visits=0
        self.image_pixels=0;self.image_bytes=0;self.image_admission={};self.kind_assets=set()
        self.asset_facts={};self.image_admission_totals={}
        self.roots=spec.allowed_roots or tuple(dict.fromkeys(str(Path(x.path).absolute().parent) for x in spec.inputs))
        self.con.execute('CREATE TABLE records(rid VARCHAR PRIMARY KEY,sid VARCHAR,ordinal BIGINT,lid VARCHAR,split VARCHAR,payload VARCHAR,loc VARCHAR,asset VARCHAR,state VARCHAR)')
        self.con.execute('CREATE TABLE units(asset VARCHAR,settings VARCHAR,ordinal BIGINT,payload VARCHAR)')
        self.con.execute('CREATE TABLE bindings(rel VARCHAR,side VARCHAR,rid VARCHAR,k VARCHAR,rawk VARCHAR)')
        self.con.execute('CREATE TABLE edges(rel VARCHAR,l VARCHAR,r VARCHAR)')
        self.con.execute('CREATE TABLE outcomes(rule VARCHAR,rid VARCHAR,status VARCHAR,payload VARCHAR)')
        self.con.execute('CREATE TABLE contexts(rel VARCHAR,l VARCHAR,r VARCHAR,payload VARCHAR,excluded BOOLEAN,unresolved BOOLEAN)')

    def snapshot(self,path,*,limit=None,retain=True):
        path=str(Path(path).absolute());info,_,seconds=capture(path,self.roots,check=lambda:self.work.check('source hashing'))
        if info['bytes']>(limit or self.config.execution.max_source_bytes): fail('Source byte admission exceeded.','source_limit')
        self.total_bytes+=info['bytes']
        if self.total_bytes>self.config.execution.max_combined_source_bytes: fail('Combined source admission exceeded.','source_limit')
        old=self.files.get(path)
        if old and (old['sha256']!=info['sha256'] or old['signature'][:4]!=info['signature'][:4]): fail('Source changed between declared roles.','source_changed')
        self.files[path]=info;self.read_bytes+=info['bytes'];self.hash_seconds+=seconds
        if not retain:
            self.snapshots[path]=path
            return Path(path)
        self.work.check('immutable metadata capture',info['bytes']*2)
        snap=self.work.root/f'source-{len(self.snapshots)}'
        with secure_open(path,self.roots) as (f,_),snap.open('wb') as out: shutil.copyfileobj(f,out,1024**2)
        os.chmod(snap,0o600)
        with snap.open('rb') as handle:
            snapshot_hash=hashlib.sha256()
            for chunk in iter(lambda:handle.read(1024**2),b''): snapshot_hash.update(chunk)
            if snapshot_hash.hexdigest()!=info['sha256']: fail('Source snapshot changed.','source_changed')
        capture(path,self.roots,expected=info)
        self.snapshots[path]=str(snap);return snap

    def reference(self,loc):
        ref='evidence_'+digest(loc)[:24]
        if ref not in self.locators:
            self.locators[ref]=loc
            if len(json.dumps(self.locators,ensure_ascii=True).encode())>self.config.limits.private_bytes: fail('Private locator budget exceeded.','private_result_limit')
        return ref

    def record(self,rid):
        row=self.con.execute('SELECT sid,ordinal,payload,loc,asset,state FROM records WHERE rid=?',[rid]).fetchone()
        if not row: raise ValueError('Unknown record.')
        return {'rid':rid,'sid':row[0],'ordinal':row[1],'record':decode_record(row[2]),'loc':json.loads(row[3]),'asset':row[4],'state':row[5]}

    def insert(self,table,rows):
        if not rows: return
        import pandas as pd
        columns=[x[0] for x in self.con.execute('DESCRIBE '+table).fetchall()]
        frame=pd.DataFrame(rows,columns=columns)
        self.con.register('_cross_batch',frame)
        try: self.con.execute('INSERT INTO '+table+' SELECT * FROM _cross_batch')
        finally: self.con.unregister('_cross_batch')

    def witness(self,rid,selector=None,unit=None):
        r=self.record(rid);loc={'source_id':r['sid'],'source':self.sources[r['sid']].path,'record':r['loc'],'selector':selector,'asset':r['asset']}
        if unit:
            loc['unit']={k:v for k,v in unit.items() if k!='value'}
            loc['unit']['value_digest']=digest(str(unit['value']))
            loc['unit_digest']=digest(loc['unit'])
        else: loc['content_digest']=digest(value(r['record'],selector) if selector else r['record'])
        return self.reference(loc)

    def ingest(self,item):
        started=time.monotonic();snap=self.snapshot(item.path,limit=self.config.limits.document_bytes if item.format in {'pdf','docx'} else None,retain=item.format not in {'pdf','docx','txt'})
        selectors={item.id_selector,item.text_selector,item.path_selector,item.split_selector,item.layout_selector,'role','layout','unit','currency'}
        for rel in self.spec.relationships:
            if item.id in {rel.left_source,rel.right_source}:
                selectors.update(rel.left_keys if item.id==rel.left_source else rel.right_keys)
                selectors.update(pair[0 if item.id==rel.left_source else 1] for pair in rel.context.values())
                clocks=(rel.cutoff,) if item.id==rel.left_source else (rel.availability,rel.valid_from,rel.valid_to)
                for c in clocks:
                    if c: selectors.update((c.column,c.timezone_column,c.fold_column))
            if item.id==rel.association_source: selectors.update((*rel.association_left_keys,*rel.association_right_keys,rel.association_left,rel.association_right))
        for rule in self.spec.rules:
            rel=next(r for r in self.spec.relationships if r.id==rule.relationship)
            if rel.left_source==item.id:
                selectors.add(rule.field)
                if rule.claim_template:
                    import string
                    selectors.update(f for _,f,_,_ in string.Formatter().parse(rule.claim_template) if f)
                m=next((m for m in self.spec.mappings if m.id==rule.mapping),None)
                if m: selectors.update([m.row_selector,*m.context_columns.values(),*m.substitutions.values()])
            if rel.right_source==item.id: selectors.add(rule.right_field)
        for s in self.spec.separation:
            if item.id==s.left_source: selectors.update(s.left_keys)
            if item.id==s.right_source: selectors.update(s.right_keys)
        roots={x[1:].split('/')[0].replace('~1','/').replace('~0','~') if x.startswith('/') else x for x in selectors if x}
        count=invalid=0
        if item.format in {'pdf','docx','txt'}:
            metadata=dict(item.metadata);metadata.setdefault(item.id_selector,item.id);metadata.setdefault('layout',item.layout or 'default')
            iterator=[({'ordinal':1},metadata,None)]
        elif item.format=='parquet':
            from datatrust.temporal_normalization import parquet_preflight
            from datatrust.temporal_contracts import TemporalWorkLimits
            reader,meta=parquet_preflight(snap,TemporalWorkLimits())
            if meta['columns']>self.config.execution.max_columns: fail('Parquet column limit exceeded.','column_limit')
            if meta['rows']>self.config.execution.max_rows: fail('Parquet row limit exceeded.','record_limit')
            def rows():
                ordinal=0
                try:
                    for batch in reader.iter_batches(batch_size=1024,use_threads=False):
                        self.work.check('Parquet decode')
                        if batch.nbytes>64*1024**2: fail('Accepted Parquet batch exceeds ceiling.','record_limit')
                        for record in batch.to_pylist():
                            ordinal+=1
                            # Preserve explicit scalar decimal/date lexemes; native clocks still require declarations.
                            from datetime import datetime,date
                            record={k:NativeTimestamp(v.isoformat()) if isinstance(v,datetime) else NativeDate(v.isoformat()) if isinstance(v,date) else v for k,v in record.items()}
                            yield {'ordinal':ordinal},record,None
                finally: reader.close()
            iterator=rows()
        else:
            iterator=frames(snap,TextSourceSpec(str(snap),item.format,item.encoding,item.delimiter),self.config.execution,TextWorkLimits())
        batch=[];batch_bytes=0;lexical=snap.open('rb') if item.format=='jsonl' else None
        for loc,record,reason in iterator:
            if 'header' in loc:
                if set(item.json_columns)-set(loc['header']): raise ValueError('JSON columns are absent from CSV header.')
                continue
            if record is None and reason is None: continue
            count+=1;self.total_rows+=1
            if count>self.config.execution.max_rows or self.total_rows>self.config.execution.max_combined_rows: fail('Record limit exceeded.','record_limit')
            record=record or {};rid=record_id(item.id,loc['ordinal']);asset=None;state='invalid' if reason else 'valid'
            if lexical is not None and not reason:
                lexical.seek(loc['byte_start']);record=json.loads(lexical.read(loc['byte_length']).decode(item.encoding),parse_float=Decimal)
            if item.format=='csv':
                from datatrust.text_normalization import strict_json
                for col in item.json_columns:
                    try:
                        strict_json(record[col]);record[col]=json.loads(record[col],parse_float=Decimal)
                    except (ValueError,TypeError): record[col]=None;state='invalid'
            invalid+=state=='invalid'
            record={k:v for k,v in record.items() if k in roots}
            if item.kind in {'document','image'} or item.format=='txt' or item.kind=='text' and item.asset_root:
                v=item.path if item.format in {'pdf','docx','txt'} else value(record,item.path_selector)
                if not isinstance(v,str) or not v: state='unavailable'
                else:
                    root=Path(item.asset_root or Path(item.path).absolute().parent)
                    asset=str((root/v).absolute())
            payload=encode_record(record)
            if len(payload.encode())>self.config.execution.max_record_bytes: fail('Mapped record exceeds byte ceiling.','record_limit')
            batch.append((rid,item.id,loc['ordinal'],key(record,(item.id_selector,)),str(value(record,item.split_selector) or item.role) if item.split_selector else item.role,payload,json.dumps(loc),asset,state))
            batch_bytes+=len(payload.encode())+len(json.dumps(loc))+256
            if len(batch)>=256 or batch_bytes>=self.config.execution.batch_bytes: self.insert('records',batch);batch.clear();batch_bytes=0;self.work.check('record ingestion')
        if batch: self.insert('records',batch)
        if lexical: lexical.close()
        self.populations[item.id]={'records':count,'invalid_records':invalid,'ingestion_seconds':time.monotonic()-started}
        self.populations[item.id]['missing_logical_ids']=self.con.execute('SELECT count(*) FROM records WHERE sid=? AND lid IS NULL',[item.id]).fetchone()[0]
        self.populations[item.id]['duplicate_logical_ids']=self.con.execute('SELECT count(*) FROM (SELECT lid FROM records WHERE sid=? AND lid IS NOT NULL GROUP BY lid HAVING count(*)>1)',[item.id]).fetchone()[0]

    def admit_image(self,sid,path,info):
        admission=self.image_admission.setdefault(sid,{})
        if path in admission: return
        admission[path]=info['bytes'];self.image_bytes+=info['bytes']
        self.image_admission_totals[sid]=self.image_admission_totals.get(sid,0)+info['bytes']
        if self.image_bytes>self.config.limits.image_media_bytes or self.image_admission_totals[sid]>self.config.limits.image_media_per_input_bytes: fail('Image media admission exceeded.','image_media_limit')

    def load_assets(self):
        cursor=self.con.cursor();cursor.execute("SELECT rid,sid,asset FROM records WHERE asset IS NOT NULL ORDER BY sid,ordinal")
        while rows:=cursor.fetchmany(128):
            for rid,sid,path in rows:
                item=self.sources[sid]
                if item.kind=='image' and path in self.files and path not in self.image_admission.get(sid,{}):
                    self.admit_image(sid,path,self.files[path])
                if (item.kind,path) in self.kind_assets: continue
                self.kind_assets.add((item.kind,path))
                try:
                    cap=self.config.limits.document_bytes if item.kind=='document' else 128*1024**2
                    info,raw,secs=capture(path,self.roots,max_bytes=cap,check=lambda:self.work.check('asset capture'))
                except AnalysisError as exc:
                    if exc.code!='source_unavailable': raise
                    self.unavailable.add(path);self.asset_facts[item.kind,path]=self.asset_cache[path]={'state':'unavailable'};continue
                old=self.files.get(path)
                if old and (old['sha256']!=info['sha256'] or old['signature'][:4]!=info['signature'][:4]): fail('Source changed between ingestion and media capture.','source_changed')
                self.files[path]=info;self.read_bytes+=info['bytes'];self.hash_seconds+=secs
                if raw is None: fail('Referenced asset exceeds capture admission.','asset_limit')
                if item.kind=='image':
                    self.admit_image(sid,path,info)
                elif path not in self.snapshots:
                    self.total_bytes+=info['bytes']
                    if self.total_bytes>self.config.execution.max_combined_source_bytes: fail('Combined source/assets exceed byte admission.','source_limit')
                if item.kind=='image':
                    from datatrust.image_assets import decode
                    from datatrust.image_contracts import ImageWorkLimits
                    facts,_=decode(raw,ImageWorkLimits());self.image_pixels+=facts.get('pixels',0)
                    if self.image_pixels>self.config.limits.image_pixels or len({p for k,p in self.kind_assets if k=='image'})>self.config.limits.image_assets: fail('Image population/pixel work limit exceeded.','image_work_limit')
                    self.asset_facts[item.kind,path]=self.asset_cache[path]=facts|{'state':facts['decode']};continue
                if item.kind=='document':
                    from datatrust.cross_documents import extract,versions
                    versions();self.documents+=1
                    if self.documents>self.config.limits.documents: fail('Document count limit exceeded.','document_limit')
                    strategies={m.strategy for m in self.spec.mappings} or {'lines'}
                    for strategy in strategies:
                        parts=tuple(dict.fromkeys(p for m in self.spec.mappings for p in m.parts)) or ('word/document.xml',)
                        settings=digest([strategy,parts,versions()]);units=[];coverage=None;chars=0
                        fmt=item.format if item.format in {'pdf','docx'} else Path(path).suffix.lower().lstrip('.')
                        if fmt not in {'pdf','docx'}:
                            self.asset_facts[item.kind,path]=self.asset_cache[path]={'state':'unsupported_format'};break
                        for ordinal,u in enumerate(extract(raw,fmt,self.config.limits,strategy=strategy,parts=parts,check=lambda:self.work.check('document extraction'))):
                            if u['kind']=='coverage': coverage=u;continue
                            chars+=len(u.get('text',''))+sum(len(c or '') for row in u.get('rows',[]) for c in row)
                            if self.characters+chars>self.config.limits.characters: fail('Combined extracted character limit exceeded.','character_limit')
                            units.append((path,settings,ordinal,json.dumps(u,ensure_ascii=True)))
                            if len(units)>=32: self.con.executemany('INSERT INTO units VALUES (?,?,?,?)',units);units.clear();self.work.check('document unit storage')
                        if units: self.con.executemany('INSERT INTO units VALUES (?,?,?,?)',units)
                        coverage=coverage or {'state':'unsupported','processed':0}
                        if coverage['state'] in {'unreadable_or_unsupported','unsupported_encrypted'}: self.con.execute('DELETE FROM units WHERE asset=? AND settings=?',[path,settings])
                        self.characters+=chars;self.pages+=coverage.get('total',0) if strategy==sorted(strategies)[0] else 0
                        if self.pages>self.config.limits.pages: fail('Combined page limit exceeded.','page_limit')
                        self.asset_units[(item.kind,path,strategy)]={'settings':settings,'coverage':coverage,'parts':parts,'format':fmt}
                    self.asset_facts[item.kind,path]=self.asset_cache[path]={'state':'extracted' if (item.kind,path,'lines') in self.asset_units or (item.kind,path,'text') in self.asset_units else 'unsupported_format'}
                else:
                    if Path(path).suffix.lower()!='.txt': self.asset_facts[item.kind,path]=self.asset_cache[path]={'state':'wrong_text_media'};continue
                    try: text=raw.decode(item.encoding)
                    except UnicodeError: self.asset_facts[item.kind,path]=self.asset_cache[path]={'state':'invalid_encoding'};continue
                    self.characters+=len(text)
                    if self.characters>self.config.limits.characters: fail('Text character limit exceeded.','character_limit')
                    u={'kind':'text','text':text,'span':[0,len(text)],'complete':True,'representation':'decoded_txt_v1'}
                    self.con.execute('INSERT INTO units VALUES (?,?,?,?)',[path,'txt',0,json.dumps(u)])
                    self.asset_units[(item.kind,path,'lines')]={'settings':'txt','coverage':{'state':'processed'},'format':'txt'};self.asset_facts[item.kind,path]=self.asset_cache[path]={'state':'extracted'}
        cursor.close()

    def units(self,r,mapping):
        if not r['asset']:
            text=value(r['record'],self.sources[r['sid']].text_selector)
            return iter([{'kind':'text','text':text,'complete':True,'representation':'mapped_text_v1'}]) if isinstance(text,str) else iter([])
        kind=self.sources[r['sid']].kind
        info=self.asset_units.get((kind,r['asset'],mapping.strategy)) or self.asset_units.get((kind,r['asset'],'lines'))
        if not info: return iter([])
        cur=self.con.cursor();cur.execute('SELECT payload FROM units WHERE asset=? AND settings=? ORDER BY ordinal',[r['asset'],info['settings']])
        def stream():
            try:
                while rows:=cur.fetchmany(32):
                    for row in rows: yield json.loads(row[0])
            finally: cur.close()
        return stream()


from datatrust.contracts import AnalysisError
