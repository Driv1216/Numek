"""M9 required core, bounded model isolation and final integrity publication."""
from collections import Counter
from dataclasses import asdict, replace
from datetime import datetime,timezone
import json
from pathlib import Path
import time
import uuid

from datatrust.cross_contracts import *
from datatrust.cross_sources import Store,value
from datatrust.cross_diagnostics import required,separation,stream
from datatrust.cross_private_base import digest
from datatrust.contracts import AnalysisError
from datatrust.scalable import Workspace,fail
from datatrust.worker import run_supervised
from datatrust.image_assets import capture,secure_open


def preflight(spec,config):
    if not isinstance(spec,CrossRepresentationAuditSpec) or not isinstance(config,CrossRepresentationAnalysisConfig): raise ValueError('M9 requires its typed specification and configuration.')
    if len(spec.inputs)>config.limits.inputs or sum(len(getattr(spec,n)) for n in ('relationships','rules','mappings','separation'))>config.limits.declarations: raise ValueError('M9 declaration admission exceeded.')
    if any(x.kind=='document' for x in spec.inputs):
        from datatrust.cross_documents import versions
        versions()
    from datatrust.cross_models import preflight as model_preflight
    return model_preflight(config.models)


def _core(spec,config,model_provenance=None,owned_snapshots=(),*,progress=None,preview=False):
    start=time.monotonic();work=None
    try:
        size=sum(Path(x.path).stat().st_size for x in spec.inputs)
        work=Workspace(config.execution,[],progress,owned_snapshots=owned_snapshots,phase_plan={'estimated_peak_workspace_bytes':max(512*1024**2,4*size),'kind':'cross_source_projected_relations_and_document_units'})
        if progress: progress({'owned_workspace':str(work.root),'stage':'M9 input projections'})
        store=Store(work,spec,config)
        for item in spec.inputs: store.ingest(item)
        store.load_assets();structural=required(store);separated=separation(store)
        audit_id=uuid.uuid4().hex;records=[];checks=[];findings=[];families={};targets={};model_inputs=[]
        def add(family,population,counts,refs=(),scope='population',status='completed'):
            eid='measurement_'+str(len(records)+1);tid='finding_'+str(len(findings)+1)
            rec={'id':eid,'family':family,'population':population,'data':counts,'references':list(refs),'scope':scope}
            records.append(rec);checks.append({'id':eid,'family':family,'execution':status,'applicability':'applicable','scope':scope,'evidence_refs':[eid]})
            issue=any(counts.get(k,0) for k in ('violated','conflicting_evidence','inconclusive','required_gap','inverse_gap','cardinality_violations','normalization_collisions','invalid_association_rows','invalid_keys_total','investigation_candidates'))
            if issue:
                finding={'id':tid,'family':family,'title':{'relationships':'Review associations and identities','identities':'Review missing or repeated logical identities','context':'Review entity, version and timing context','reconciliation':'Review discrepancies and unresolved evidence','separation':'Review declared cross-source separation'}.get(family,'Review evidence'),'priority':'High' if counts.get('violated') or counts.get('conflicting_evidence') else 'Moderate','evidence_refs':[eid],'references':list(refs),'population':population,'counts':counts}
                findings.append(finding);targets[tid]={'kind':'aggregate_finding','evidence_refs':[eid,*refs],'population':population,'counts':counts,'inspection_scope':'Aggregate disposition does not establish individual record inspection.'}
            return eid
        def retain_examples(population,examples):
            details=[]
            for i,example in enumerate(examples[:config.limits.details]):
                target='item_'+digest([audit_id,population,i,example])[:20]
                detail={**example,'target_id':target};details.append(detail)
                targets[target]={'kind':'source_investigation','evidence_refs':example['evidence_refs'],'population':population,'detail':detail}
                store.private_targets[target]={'reason':example['reason']}
            return details,[r for d in details for r in d['evidence_refs']]
        for i,item in enumerate(spec.inputs):
            population=store.populations[item.id];examples=[];public_source='source_'+str(i+1)
            for reason,where in [('missing_logical_identity','lid IS NULL'),('invalid_source_record',"state='invalid'")]:
                for rid, in store.con.execute('SELECT rid FROM records WHERE sid=? AND '+where+' ORDER BY ordinal LIMIT ?',[item.id,config.limits.witnesses]).fetchall():
                    examples.append({'reason':reason,'evidence_refs':[store.witness(rid,item.id_selector)]})
            for lid, in store.con.execute('SELECT lid FROM records WHERE sid=? AND lid IS NOT NULL GROUP BY lid HAVING count(*)>1 ORDER BY lid LIMIT ?',[item.id,config.limits.witnesses]).fetchall():
                refs=[store.witness(rid,item.id_selector) for rid, in store.con.execute('SELECT rid FROM records WHERE sid=? AND lid=? ORDER BY ordinal LIMIT 2',[item.id,lid]).fetchall()]
                examples.append({'reason':'duplicate_logical_identity','evidence_refs':refs})
            details,refs=retain_examples(public_source,examples)
            add('identities',public_source,{'records':population['records'],'invalid_records':population['invalid_records'],'invalid_keys_total':population['missing_logical_ids'],'cardinality_violations':population['duplicate_logical_ids'],'details':details,'retained_examples':len(details)},refs)
        for i,v in enumerate(structural):
            counts={k:v[k] for k in ('associations','required_gap','inverse_gap','cardinality_violations','normalization_collisions','invalid_association_rows','duplicate_association_rows')};counts['invalid_keys_total']=sum(v['invalid_keys'].values());counts['unmatched']=v['unmatched'];counts['duplicate_keys']=v['duplicate_keys']
            population='relationship_'+str(i+1);details,refs=retain_examples(population,v['examples'])
            add('relationships',population,{**counts,'details':details,'retained_examples':len(details)},refs)
        for i,v in enumerate(store.context_evidence):
            rel=next(r for r in spec.relationships if r.id==v['relationship']);refs=[]
            pairs=list(rel.context.values())
            if rel.cutoff: pairs.append((rel.cutoff.column,rel.availability.column))
            for left,right in store.con.execute('SELECT l,r FROM contexts WHERE rel=? AND (excluded OR unresolved) ORDER BY l,r LIMIT ?',[rel.id,config.limits.witnesses]).fetchall():
                for a,b in pairs[:config.limits.witnesses]: refs.extend((store.witness(left,a),store.witness(right,b)))
            add('context','context_'+str(i+1),{k:x for k,x in v.items() if k!='relationship'},refs)
        model_budget={'nli':0,'image_text':0}
        # Round-robin rules when selecting optional work so one large rule cannot monopolize it.
        semantic_cursors=[]
        for ri,rule in enumerate(spec.rules):
            public_rule='rule_'+str(ri+1)
            counts=dict(store.con.execute('SELECT status,count(*) FROM outcomes WHERE rule=? GROUP BY status',[rule.id]).fetchall())
            counts['records']=sum(counts.values());details=[];reasons=Counter();incomplete=0;contexts=Counter();candidate_count=0
            for rid,payload in stream(store.con,"SELECT rid,payload FROM outcomes WHERE rule=? ORDER BY CASE status WHEN 'violated' THEN 0 WHEN 'conflicting_evidence' THEN 0 WHEN 'inconclusive' THEN 1 WHEN 'unassessed' THEN 2 ELSE 3 END,hash(rid,?),rid",(rule.id,config.seed)):
                o=json.loads(payload);incomplete+=not o['complete'];reasons.update(o['reasons']);candidate_count+=len(o['candidates'])
                for c in o['contexts']: contexts.update(c['excluded']+c['unknown'])
                if len(details)<config.limits.details:
                    refs=[store.witness(rid,rule.field)]
                    for c in o['candidates'][:config.limits.witnesses]: refs.append(store.witness(c['right'],unit=c['unit']))
                    target='item_'+digest([audit_id,rule.id,rid])[:20]
                    detail={'target_id':target,'status':o['status'],'complete':o['complete'],'reasons':o['reasons'],'evidence_refs':refs,'candidate_count':len(o['candidates']),'conflicting_values':o.get('conflict',False)}
                    details.append(detail);targets[target]={'kind':'record_investigation','evidence_refs':refs,'population':public_rule,'detail':detail}
                    store.private_targets[target]={'rule':rule.id,'record_id':rid,'status':o['status'],'complete':o['complete'],'contexts':o['contexts']}
            families[public_rule]={'records':counts['records'],'candidate_occurrences':candidate_count,'incomplete_records':incomplete,'reasons':dict(reasons),'context_exclusions_or_unknown':dict(contexts),'retained':len(details),'detail_omissions':counts['records']-len(details),'method':rule.method}
            add('reconciliation',public_rule,{**counts,'incomplete_records':incomplete,'details':details,'method':rule.method},[r for d in details[:config.limits.witnesses] for r in d['evidence_refs']])
            if rule.method in {'nli','image_text'} and (config.models.nli_directory if rule.method=='nli' else config.models.image_text_directory):
                semantic_cursors.append((ri,rule,iter(stream(store.con,'SELECT rid,payload FROM outcomes WHERE rule=? ORDER BY hash(rid,?)',(rule.id,config.seed)))))
        selection_started=time.monotonic()
        while semantic_cursors:
            next_round=[]
            for ri,rule,cur in semantic_cursors:
                kind='nli' if rule.method=='nli' else 'image_text';limit=config.limits.claims if kind=='nli' else config.limits.image_pairs
                if model_budget[kind]>=limit: continue
                try: rid,payload=next(cur)
                except StopIteration: continue
                o=json.loads(payload);left=store.record(rid);rel=next(x for x in spec.relationships if x.id==rule.relationship)
                claim=o['expected']
                if rule.claim_template:
                    import string
                    fields=[f for _,f,_,_ in string.Formatter().parse(rule.claim_template) if f]
                    if any(not f.isidentifier() for f in fields): raise ValueError('Claim templates accept simple mapped selectors only.')
                    supplied={f:value(left['record'],f) for f in fields}
                    claim=rule.claim_template.format(**supplied) if all(v is not None for v in supplied.values()) else None
                docs=[]
                for c in o['candidates']:
                    right=store.record(c['right']);src=store.sources[right['sid']]
                    docs.append({'text':c['unit']['value'],'reference':store.witness(c['right'],unit=c['unit']),'language':src.language,'asset':right['asset'],'source_identity':store.files.get(right['asset']),'format':Path(right['asset']).suffix.lower().lstrip('.') if right['asset'] else src.format,'alternative':False})
                if rule.alternative_relationship:
                    from datatrust.cross_diagnostics import context
                    alternatives=next(x for x in spec.relationships if x.id==rule.alternative_relationship)
                    for right_id, in stream(store.con,'SELECT r FROM edges WHERE rel=? AND l=? ORDER BY r',(alternatives.id,rid)):
                        if len(docs)>=config.limits.candidates: o['complete']=False;break
                        right=store.record(right_id);src=store.sources[right['sid']]
                        if not context(alternatives,left['record'],right['record'])['eligible']: continue
                        docs.append({'text':None,'reference':store.witness(right_id,src.path_selector),'language':src.language,'asset':right['asset'],'source_identity':store.files.get(right['asset']),'format':'image','alternative':True})
                target='item_'+digest([audit_id,rule.id,rid])[:20]
                claim_ref=store.witness(rid,rule.field)
                if rule.claim_template and claim is not None:
                    claim_ref=store.reference({'source_id':left['sid'],'source':store.sources[left['sid']].path,'record':left['loc'],'selector':rule.field,'asset':None,'generated_claim':rule.claim_template,'content_digest':digest(claim)})
                model_inputs.append({'kind':kind,'rule':'rule_'+str(ri+1),'target_id':target,'claim':claim,'language':rule.claim_language or store.sources[rel.left_source].language,'evidence':docs,'complete':o['complete'],'layout':mapping.layout if (mapping:=next((m for m in spec.mappings if m.id==rule.mapping),None)) else store.sources[rel.right_source].layout,'mapping_kind':mapping.kind if mapping else 'field','claim_reference':claim_ref})
                model_budget[kind]+=1;next_round.append((ri,rule,cur))
            semantic_cursors=next_round
        selection_seconds=time.monotonic()-selection_started
        for i,v in enumerate(separated):
            population='separation_'+str(i+1);details,refs=retain_examples(population,v['examples'])
            add('separation',population,{k:x for k,x in v.items() if k not in {'requirement','examples'}}|{'details':details,'violated':v['left_affected_records'] if v['status']=='violated' else 0,'inconclusive':int(v['status']=='inconclusive')},refs)
        files=dict(store.files)
        for p in (model_provenance or {}).values():
            for info in p.get('files',{}).values(): files[info['path']]=info
            if p.get('manifest'): files[p['manifest']['path']]=p['manifest']
        private={'schema':'cross_private_manifest_v1','audit_id':audit_id,'spec':spec.to_dict(),'config':config.to_dict(),'files':files,'unavailable':sorted(store.unavailable),'locators':store.locators,'targets':store.private_targets,'document_settings':[{ 'kind':k,'asset':a,'strategy':s,**v} for (k,a,s),v in store.asset_units.items()],'image_assets':[{'path':p,'facts':v} for (k,p),v in store.asset_facts.items() if k=='image'],'models':model_provenance or {},'model_inputs':model_inputs}
        profile={'audit_id':audit_id,'dataset_name':spec.dataset_name,'purpose':spec.purpose,'source_count':len(spec.inputs),'records':store.total_rows,'documents':store.documents,'pages':store.pages,'review_targets':targets,'score':None,'summary':f'This review identified {len(findings):,} topics for investigation across the supplied sources.'}
        execution={'status':'completed','backend':'duckdb_local','effective_limits':asdict(config.execution),'cross_limits':asdict(config.limits),'peak_workspace_bytes':work.peak,'estimated_peak_workspace_bytes':work.estimate,'duration_seconds':time.monotonic()-start,'capture_read_bytes':store.read_bytes,'initial_hash_seconds':store.hash_seconds,'publication_policy':'required_core_atomic_optional_models_isolated','source_populations':{'source_'+str(i+1):store.populations[x.id] for i,x in enumerate(spec.inputs)},'persistent_corpus_copy':False,'tabular_snapshots_temporary':True,'warnings':['Budgets are provisional safeguards, not capacity promises.','Sampled RSS may overshoot.','Per-file integrity is not an atomic filesystem snapshot.']}
        execution['effective_limits'].pop('scratch_directory',None)
        from datatrust.cross_documents import versions
        if store.documents: execution['parsers']=versions()
        from datatrust.temporal_normalization import timezone_provenance
        execution['timezone_provenance']=timezone_provenance()
        execution['image_work']={'decoded_pixels':store.image_pixels,'admitted_media_bytes':store.image_bytes}
        execution['model_selection_seconds']=selection_seconds
        coverage={'families':families,'document_extraction':[v['coverage'] for v in store.asset_units.values()],'discovery_visits':store.discovery_visits,'required_population':'All framed records and declared associations within admitted hard limits. Bounded discovery does not establish absence.','model_selected':model_budget}
        coverage['asset_states']={kind:dict(Counter(v['state'] for (k,p),v in store.asset_facts.items() if k==kind)) for kind in ('document','text','image')}
        selected_rules=Counter(item['rule'] for item in model_inputs)
        coverage['model_selection']={key:{'population':v['records'],'selected':selected_rules[key],'not_selected':v['records']-selected_rules[key],'requested':bool(config.models.nli_directory if v['method']=='nli' else config.models.image_text_directory)} for key,v in families.items() if v['method'] in {'nli','image_text'}}
        result=CrossRepresentationAuditResult(profile,checks,records,findings,coverage,execution,datetime.now(timezone.utc).isoformat(),private)
        if len(json.dumps(private,ensure_ascii=True).encode())>config.limits.private_bytes: fail('Private payload limit exceeded.','private_result_limit')
        work.check('frozen M9 core',config.execution.result_bytes)
        return result
    except AnalysisError: raise
    except Exception as exc:
        raise AnalysisError('M9 execution failed; no completed evidence published.',code='cross_execution_failed',stage='cross required core') from exc
    finally:
        if work: work.close()


def finalize(result,spec,config,*,progress=None):
    start=time.monotonic()
    roots=spec.allowed_roots or tuple(str(Path(x.path).absolute().parent) for x in spec.inputs)
    model_roots=tuple(str(Path(p).absolute()) for p in (config.models.nli_directory,config.models.retrieval_directory,config.models.image_text_directory) if p)
    total=0
    for info in result.private['files'].values():
        current,_,_=capture(info['path'],roots+model_roots,expected=info);total+=current['bytes']
    for path in result.private['unavailable']:
        try:
            with secure_open(path,roots): fail('Previously unavailable evidence appeared.','source_availability_changed')
        except AnalysisError as exc:
            if exc.code!='source_unavailable': raise
    result.private.pop('model_inputs',None)
    result.profile['private_manifest_sha256']=digest(result.private)
    result.execution.update(final_verification_seconds=time.monotonic()-start,final_verification_bytes=total)
    return result


def audit_cross_representation(spec,config=None,*,progress=None,cancel=None,owned_snapshots=()):
    import copy
    spec=copy.deepcopy(spec);config=copy.deepcopy(config or CrossRepresentationAnalysisConfig());started=time.monotonic();provenance=preflight(spec,config)
    def remaining():
        left=config.execution.max_seconds-(time.monotonic()-started)
        if cancel is not None and cancel.is_set(): fail('Audit cancelled.','cancelled')
        if left<=0: fail('M9 global deadline exceeded.','deadline')
        return left
    core_config=replace(config,execution=replace(config.execution,max_seconds=remaining()))
    result=run_supervised(_core,(spec,core_config,provenance,owned_snapshots),core_config.execution,progress=progress,cancel=cancel,owned_snapshots=owned_snapshots)
    core_execution=dict(result.execution)
    if result.private['model_inputs']:
        from datatrust.cross_models import execute,merge
        reserve=max(30,1.5*result.execution['initial_hash_seconds'])+30
        allocation=max(0,min(max(0,config.limits.model_seconds-result.execution['model_selection_seconds']),remaining()-reserve))
        if allocation:
            opts=replace(config.execution,max_seconds=allocation)
            try:
                stage=run_supervised(execute,(result.private['model_inputs'],provenance,config,allocation),opts,progress=progress,cancel=cancel)
                merge(result,stage)
            except AnalysisError as exc:
                if exc.code in {'source_changed','out_of_root','cancelled','source_unavailable'}: raise
                remaining()
                if exc.code=='deadline': result.coverage['models']={'status':'bounded','reason':'optional_allocation','committed':0}
                else:
                    result.execution['status']='partial';result.coverage['models']={'status':'failed','reason':'isolated_model_failure','committed':0}
        else: result.coverage['models']={'status':'bounded','reason':'final_verification_reservation','examined':0}
    opts=replace(config.execution,max_seconds=remaining())
    result=run_supervised(finalize,(result,spec,config),opts,progress=progress,cancel=cancel)
    stages=[core_execution,result.execution.get('model_execution',{}),dict(result.execution)]
    result.execution['phase_resources']={name:{k:e.get(k) for k in ('peak_worker_rss_bytes','peak_workspace_bytes','peak_spill_bytes','whole_job_seconds')} for name,e in zip(('core','models','final_verification'),stages)}
    for key in ('peak_worker_rss_bytes','peak_workspace_bytes','peak_spill_bytes'): result.execution[key]=max(e.get(key,0) for e in stages)
    result.execution['whole_job_seconds']=time.monotonic()-started
    from datatrust.cross_presentation import summary
    result.profile['summary']=summary(result)
    from datatrust.guidance import attach_guidance
    attach_guidance(result)
    for _ in range(2): result.execution['serialized_bytes']=len(result.json_text().encode())
    if len(result.json_text().encode())>config.execution.result_bytes: fail('Final M9 result budget exceeded.','result_limit')
    return result
