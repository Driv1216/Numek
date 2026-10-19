"""Protected exact membership sidecars; hashes are identifiers, not anonymization."""
import hashlib
import json
from .contracts import EvaluationError,digest
from .fitted import model_identity,shape_check
from .sources import rows

SCHEMA='confidenceguard.membership_sidecar/1.0'

def assessment_membership_passed(method_id,fitted,imported_ids,checks):
    """Current fits use checked roles; imports and upstream imports need passed checks."""
    seen=set()
    while method_id is not None:
        if method_id in seen or method_id not in fitted:return False
        seen.add(method_id)
        check=checks.get(method_id)
        if check is None:
            if method_id in imported_ids:return False
        elif check.get('status')!='passed':return False
        method_id=fitted[method_id]['definition'].get('parent')
    return True

def key_digest(namespace,value):
    return hashlib.sha256(json.dumps([namespace,value],ensure_ascii=True,separators=(',',':')).encode()).hexdigest() if value is not None else None

def validate(value,limits):
    shape_check(value,limits)
    fields={'schema_version','namespace','root_run','model_digest','method_digests','rows','content_digest'}
    if not isinstance(value,dict) or set(value)!=fields or value['schema_version']!=SCHEMA:raise EvaluationError('Invalid membership sidecar.')
    if not all(isinstance(value[k],str) and value[k] for k in ('namespace','root_run','model_digest')):raise EvaluationError('Invalid membership binding.')
    def hexkey(v):return isinstance(v,str) and len(v)==64 and all(c in '0123456789abcdef' for c in v)
    if not isinstance(value['method_digests'],list) or not value['method_digests'] or any(not hexkey(v) for v in value['method_digests']):raise EvaluationError('Invalid membership method identities.')
    if not isinstance(value['rows'],list):raise EvaluationError('Invalid membership rows.')
    for row in value['rows']:
        if not isinstance(row,list) or len(row)!=3 or not hexkey(row[0]) or row[1] is not None and not hexkey(row[1]) or row[2] not in {'F','S','C'}:raise EvaluationError('Invalid protected membership row.')
    if len({v[0] for v in value['rows']})!=len(value['rows']):raise EvaluationError('Ambiguous membership identities.')
    if digest({k:v for k,v in value.items() if k!='content_digest'})!=value['content_digest']:raise EvaluationError('Membership sidecar digest differs.')
    return value

def preserve(store,fitted):
    """One shared sidecar per root, bounded by the protected-result admission."""
    if not store.extension.separation.preserve_membership:return []
    result=[];estimated=0;namespace=store.extension.roles.namespace
    for run in store.extension.evaluation.runs:
        methods=[v['artifact_digest'] for v in fitted.values() if v['definition']['run']==run.id and v['id'] not in {m['id'] for m in store.extension.fitted_methods}]
        if not methods:continue
        table=store.run_tables[run.id]
        query=f"SELECT event_key,entity_key,cg_role FROM {table} WHERE cg_role IN ('F','S','C') AND input_identity_valid ORDER BY event_key"
        count=store.con.execute(f'SELECT count(*) FROM ({query}) q').fetchone()[0]
        estimated+=count*160
        if estimated>store.config.private_bytes//2:raise EvaluationError('Protected membership exceeds result admission; increase private_bytes or explicitly disable membership preservation.','membership_limit')
        entries=[]
        for event,entity,role in rows(store.con,query,batch=512):
            entries.append([key_digest(namespace,event),key_digest(namespace,entity),role])
            if len(entries)%512==0:store.work.check('protected membership sidecar')
        value={'schema_version':SCHEMA,'namespace':namespace,'root_run':run.id,'model_digest':digest(model_identity(run.model)),'method_digests':sorted(methods),'rows':entries}
        value['content_digest']=digest(value);result.append(value)
    return result

def inspect_imports(store,fitted):
    """An unavailable sidecar never becomes a passed observable separation check."""
    sidecars=[validate(v,store.extension.limits) for v in store.extension.membership_sidecars]
    known={v['artifact_digest']:v for v in fitted.values()}
    for sidecar in sidecars:
        if not set(sidecar['method_digests'])&known.keys():raise EvaluationError('Membership sidecar binds no supplied method.','incompatible_membership')
        for md in sidecar['method_digests']:
            method=known.get(md)
            if method is not None and (sidecar['root_run']!=method['definition']['run'] or sidecar['model_digest']!=digest(model_identity(method['model']))):raise EvaluationError('Membership sidecar does not bind an imported method.','incompatible_membership')
    states={}
    for method in store.extension.fitted_methods:
        md=method['artifact_digest'];run=method['definition']['run'];table=store.run_tables[run]
        compatible=[v for v in sidecars if md in v['method_digests'] and v['namespace']==store.extension.roles.namespace]
        if not compatible:states[method['id']]={'status':'unavailable','reason':'matching_prior_membership_not_supplied'};continue
        store.con.execute('CREATE TEMP TABLE prior_membership(event_hash VARCHAR,entity_hash VARCHAR)')
        for sidecar in compatible:
            for start in range(0,len(sidecar['rows']),512):
                store.con.executemany('INSERT INTO prior_membership VALUES (?,?)',[v[:2] for v in sidecar['rows'][start:start+512]])
                store.work.check('prior membership check')
        store.con.execute('CREATE TEMP TABLE current_membership(event_hash VARCHAR,entity_hash VARCHAR)')
        pending=[]
        for event,entity in rows(store.con,f"SELECT event_key,entity_key FROM {table} WHERE cg_role='E' AND input_identity_valid",batch=512):
            pending.append((key_digest(store.extension.roles.namespace,event),key_digest(store.extension.roles.namespace,entity)))
            if len(pending)>=512:store.con.executemany('INSERT INTO current_membership VALUES (?,?)',pending);pending=[];store.work.check('current membership check')
        if pending:store.con.executemany('INSERT INTO current_membership VALUES (?,?)',pending)
        event_overlap,entity_overlap=store.con.execute('SELECT count(*) FILTER(WHERE event_hash IN (SELECT event_hash FROM prior_membership)),count(*) FILTER(WHERE entity_hash IN (SELECT entity_hash FROM prior_membership)) FROM current_membership').fetchone()
        store.con.execute('DROP TABLE current_membership')
        store.con.execute('DROP TABLE prior_membership')
        states[method['id']]={'status':'contradicted' if event_overlap or entity_overlap else 'passed','event_overlaps':event_overlap,'entity_overlaps':entity_overlap}
    for method in fitted.values():
        parent=method['definition'].get('parent');upstream=states.get(parent)
        if not upstream:continue
        current=states.get(method['id'])
        if upstream['status']=='contradicted' and (not current or current['status']!='contradicted') or upstream['status']=='unavailable' and (not current or current['status']=='passed'):
            states[method['id']]={'status':upstream['status'],'reason':'upstream_prior_membership','upstream_method':parent,'upstream_check':upstream}
    return states
