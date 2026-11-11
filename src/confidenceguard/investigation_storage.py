"""Bounded canonical-JSON parts for large sealed CG4 records, using existing JSONL.

This is not a general codec or serialization framework. Only assessments and
frozen hypothesis sets use it. Every part has a logical hash, normal catalog
integrity/dependencies and the same atomic visibility boundary as its header.
"""
import base64
import hashlib
from .contracts import EvaluationError,digest,strict_json
from .history_storage import serialized

MAX_PACKET_BYTES=256*1024**2


def write_packet(writer,kind,identity,payload):
    if kind not in {'assessment','hypothesis_set','policy_family','robustness_protocol'}:raise EvaluationError('Unsupported sealed packet.','packet_kind')
    raw=serialized(payload)
    if len(raw)+2048<=writer.config.max_record_bytes:return writer.add(kind,identity,payload)
    if len(raw)>MAX_PACKET_BYTES:raise EvaluationError('Sealed CG4 packet exceeds its 256 MiB admission.','packet_limit')
    step=min(1024**2,max(1,(writer.config.max_record_bytes-4096)*3//4))
    if writer.config.max_record_bytes<8192 or (len(raw)+step-1)//step>4096:raise EvaluationError('Recording limits cannot admit bounded CG4 parts.','packet_limit')
    packet_id=digest([kind,identity]);parts=[];objects=set(payload.get('depends_on_objects',()))
    for index,start in enumerate(range(0,len(raw),step)):
        block=raw[start:start+step]
        key=writer.add('cg4_packet_part',[packet_id,index],{'packet_id':packet_id,'index':index,
            'data':base64.b64encode(block).decode('ascii'),'depends_on_objects':payload.get('depends_on_objects',[])})
        parts.append({'key':key,'index':index,'bytes':len(block),'sha256':hashlib.sha256(block).hexdigest()});objects.add(writer.object_id)
        writer.check('sealed CG4 packet parts',len(block))
    header={'cg4_packet':{'schema_version':'confidenceguard.cg4_packet/1.0','packet_id':packet_id,'bytes':len(raw),
        'sha256':hashlib.sha256(raw).hexdigest(),'parts':parts},'depends_on_objects':sorted(objects)}
    if kind=='assessment':header['result']={k:payload['result'][k] for k in ('analysis_id','schema_version','methodology_id','name','generated_at')}
    return writer.add(kind,identity,header)


def read_packet(catalog,fact):
    payload=fact['payload'];header=payload.get('cg4_packet')
    if header is None:return payload
    if fact['kind'] not in {'assessment','hypothesis_set','policy_family','robustness_protocol'} or not isinstance(header,dict) or set(header)!={'schema_version','packet_id','bytes','sha256','parts'} or header['schema_version']!='confidenceguard.cg4_packet/1.0':raise EvaluationError('Invalid sealed packet header.','packet_changed')
    if header['packet_id']!=digest([fact['kind'],fact['identity']]) or type(header['bytes']) is not int or not 0<header['bytes']<=MAX_PACKET_BYTES:raise EvaluationError('Invalid sealed CG4 packet identity/size.','packet_changed')
    parts=header['parts']
    if not isinstance(parts,list) or not 1<=len(parts)<=4096 or any(not isinstance(p,dict) or set(p)!={'key','index','bytes','sha256'} or p['index']!=i or type(p['bytes']) is not int or not 0<p['bytes']<=1024**2 or p['key']!=digest([header['packet_id'],i]) for i,p in enumerate(parts)):raise EvaluationError('Invalid sealed CG4 packet part declarations.','packet_changed')
    if sum(p['bytes'] for p in parts)!=header['bytes']:raise EvaluationError('Sealed CG4 packet byte count differs.','packet_changed')
    found={f['key']:f for f in catalog.iter_facts('cg4_packet_part',keys=[p['key'] for p in parts],max_records=len(parts))};raw=bytearray()
    for part in parts:
        value=found.get(part['key'],{}).get('payload',{})
        if value.get('packet_id')!=header['packet_id'] or value.get('index')!=part['index']:raise EvaluationError('Required sealed CG4 packet part is absent.','packet_unavailable')
        encoded=value.get('data')
        if not isinstance(encoded,str) or len(encoded)>((part['bytes']+2)//3)*4:raise EvaluationError('Invalid sealed CG4 packet part.','packet_changed')
        try:block=base64.b64decode(encoded,validate=True)
        except ValueError as exc:raise EvaluationError('Invalid sealed CG4 part encoding.','packet_changed') from exc
        if len(block)!=part['bytes'] or hashlib.sha256(block).hexdigest()!=part['sha256']:raise EvaluationError('Sealed CG4 packet part differs.','packet_changed')
        raw.extend(block)
    if hashlib.sha256(raw).hexdigest()!=header['sha256']:raise EvaluationError('Sealed CG4 packet digest differs.','packet_changed')
    result=strict_json(bytes(raw))
    if not isinstance(result,dict):raise EvaluationError('Invalid sealed CG4 packet root.','packet_changed')
    return result
