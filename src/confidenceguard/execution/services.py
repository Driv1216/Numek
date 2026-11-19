"""CG6 supervised application boundary shared by every interface."""
from dataclasses import replace
from datetime import datetime,timezone
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import time
import uuid

import numpy as np

from .. import compat
from ..contracts import EvaluationConfig,EvaluationError,digest,strict_json
from ..result import Inspection
from .contracts import ExecutionSpec,DeviceSpec,METHOD,RESULT,design_fingerprint
from .store import PreparedExecution
from .adapters import Adapter,normalize_outputs,host_bindings
from .result import ExecutionResult,LIMITATIONS
from . import devices
from ..execution_context import ctx


def arguments(spec,config,allowed_roots):
    if isinstance(spec,dict):spec=ExecutionSpec.from_dict(spec)
    if not isinstance(spec,ExecutionSpec):raise EvaluationError('ExecutionSpec required.')
    config=EvaluationConfig.from_dict(config) if isinstance(config,dict) else config or EvaluationConfig()
    spec=copy.deepcopy(spec);config=copy.deepcopy(config)
    registrations=host_bindings();predictors=[]
    for p in spec.predictors:
        if p.adapter=='custom' or p.architecture.get('kind')=='host':
            registration=registrations.get(p.registration)
            if registration is None:raise EvaluationError('Host registration is unavailable.','host_registration')
            prior=p.provenance.get('host_code_digest')
            if prior and prior!=registration['code_digest']:raise EvaluationError('Host code identity differs.','host_registration')
            p=replace(p,provenance={**p.provenance,'host_code_digest':registration['code_digest']})
        predictors.append(p)
    spec=replace(spec,predictors=tuple(predictors))
    paths=[s.path for s in spec.sources]+[f.path for p in spec.predictors for f in p.files]
    paths.extend(f['path'] for a in spec.auxiliaries for p in a['predictors'] for f in p['files'])
    paths.extend(v for p in spec.predictors for k,v in p.preprocessing.items() if k in {'tensor_file','keys_source'} and isinstance(v,str))
    if allowed_roots is not None and not allowed_roots:raise EvaluationError('Authorized roots cannot be empty.','roots_required')
    roots=tuple(str(Path(r).absolute()) for r in (allowed_roots if allowed_roots is not None else {str(Path(p).absolute().parent) for p in paths}))
    return spec,config,roots


def qualification_state():
    return {'cpu':'not_established_by_this_result','mps':'not_established_by_this_result',
            'cuda':'not_run_hardware_unavailable' if not devices.capabilities()['availability']['cuda'] else 'runtime_qualification_not_established',
            'cuda_pending_is_nonblocking':True,'scientific_qualification':'separate_from_device_execution'}


def make_result(prepared,stage,panel,*,started,evidence=None,staging=None,private_extra=None):
    spec=prepared.spec;config=prepared.config;aid=uuid.uuid4().hex
    if evidence is None:
        measurements=[];populations=[];locators={}
    else:
        measurements=evidence.measurements;populations=list(evidence.populations.values());locators={}
    retained=[];output_artifact=None
    media_inventory={}
    if prepared.views:
        asset_paths={}
        media={**getattr(prepared,'generated_assets',{})} if spec.evidence_retention=='materialized_inputs' else {}
        for old,path in (prepared.assets.items() if spec.evidence_retention=='materialized_inputs' else []):
            if old not in media:
                with open(path,'rb') as source:sha=hashlib.file_digest(source,'sha256').hexdigest()
                media[old]={'path':path,'sha256':sha,'bytes':Path(path).stat().st_size}
        for old,info in media.items():
            destination=Path(staging)/('media-'+info['sha256']+'.png')
            if not destination.exists():shutil.copyfile(info['path'],destination);os.chmod(destination,0o600)
            asset_paths[old]=str(destination)
            media_inventory[str(destination)]={**info,'path':str(destination)}
        target=Path(staging)/'predictions.jsonl';h=hashlib.sha256();size=0;total=0
        with target.open('xb') as stream:
            for row in prepared.output_rows():
                if spec.evidence_retention=='outputs_and_recipes':
                    row['input_record']={}
                    if row.get('variant'):row['variant']['input_record']={}
                for record in (row.get('input_record',{}),row.get('variant',{}).get('input_record',{})):
                    for k,v in record.items():
                        if isinstance(v,str) and v in asset_paths:record[k]=asset_paths[v]
                raw=(json.dumps(row,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode();stream.write(raw);h.update(raw);size+=len(raw);total+=1
                if size>config.workspace_bytes:raise EvaluationError('Prediction artifact exceeds disk admission.','execution_output_limit')
                if total<=spec.limits.retained_rows:retained.append(row)
                if len(locators)<config.max_details:
                    identity=digest([row['predictor'],row['scenario'],row['event_key']]);locators['cg6_'+identity[:24]]={'key':identity}
                if total%512==0:prepared.work.check('protected output staging',size)
            stream.flush();os.fsync(stream.fileno())
        os.chmod(target,0o600)
        output_artifact={'path':str(target),'sha256':h.hexdigest(),'bytes':size,'records':total}
    runs=[{'id':v['id'],'display_name':v['id'],'model':v['run'].model.to_dict(),'role':'experiment','scope':v['scope']} for v in prepared.views]
    if not runs:runs=[{'id':p.id,'display_name':p.id,'model':{'artifact_sha256':p.predictor_digest},'role':'registered'} for p in spec.predictors]
    panel={'stage':stage,'evidence_level':'verified_experimental_behavior','qualification':qualification_state(),**panel}
    panel['retention']={'inputs':spec.evidence_retention,'models':{p.id:p.retention for p in spec.predictors},
        'exact_input_reopening':spec.evidence_retention=='materialized_inputs','reopening_executes_models':False}
    data={'schema_version':RESULT,'methodology_id':METHOD,'analysis_id':aid,'generated_at':datetime.now(timezone.utc).isoformat(),
          'name':spec.name,'task':spec.task.to_dict(),'runs':runs,'outcomes':{**prepared.store.outcome_facts,'scope':'observed_labels' if spec.outcomes else 'unlabeled'},
          'comparison':None,'measurements':measurements,'checks':getattr(evidence,'checks',[]) if evidence else [],'findings':panel.pop('findings',[]),
          'coverage':{'population_provenance_version':'1.1','populations':populations,'planned_roots':prepared.count,
                      'output_cells':prepared.cell_count,'retained_output_rows':len(retained),'complete_output_records':output_artifact['records'] if output_artifact else 0,
                      'limitations':LIMITATIONS},'cg6':panel}
    private={'schema':'confidenceguard.execution_private/1.0','analysis_id':aid,'execution_spec':spec.to_dict(),'config':config.to_dict(),
             'files':prepared.files,'locators':locators,'output_artifact':output_artifact,'output_rows':retained,'input_fingerprint':prepared.fingerprint,
             'predictors':{p.id:p.to_dict() for p in spec.predictors},'view_predictors':{v['predictor'].id:v['predictor'].to_dict() for v in prepared.views},**(private_extra or {})}
    private['variant_assets']=media_inventory
    if spec.auxiliaries:private['auxiliary_artifacts']=list(spec.auxiliaries)
    private['fitted_methods']=list(spec.fitted_methods);private['membership_sidecars']=list(spec.membership_sidecars)
    if hasattr(prepared,'method_membership'):panel['frozen_method_membership']=prepared.method_membership
    private['view_specs']=[{'id':v['id'],'scope':v['scope'],'predictor':v['predictor'].id,'run':v['run'].to_dict(),
                            'representation':prepared.store.representations[v['id']].to_dict() if v['id'] in prepared.store.representations else None} for v in prepared.views]
    if hasattr(prepared,'requested_spec'):private['requested_execution_spec']=prepared.requested_spec.to_dict()
    execution={'status':'completed','backend':'supervised_local','duration_seconds':time.monotonic()-started,
               'peak_workspace_bytes':prepared.work.peak,'whole_evaluation_atomic':True,'resource_limits_are_hard_quotas':False}
    return ExecutionResult(data,private,execution)


def measurement(result,run,metric,value,n,*,scope='overall',family='robustness_operational',data=None,reason=None,counts=()):
    pid='pop_'+digest([result.private['input_fingerprint'],run,scope,metric,n,data or {}])[:32]
    population={'id':pid,'run':run,'scope':scope,'definition':metric,'lineage':{'execution_fingerprint':result.private['input_fingerprint']},'denominator':n,'denominator_kind':'eligible_records'}
    result.data['coverage']['populations'].append(population)
    state='finite' if value is not None and np.isfinite(value) else 'undefined' if value is None or np.isnan(value) else 'positive_infinity' if value>0 else 'negative_infinity'
    m={'id':'cg6_m'+str(len(result.data['measurements'])+1),'run':run,'scope':scope,'family':family,'metric':metric,
       'value':float(value) if state=='finite' else None,'value_state':state,'denominator':n,'denominator_kind':'eligible_records',
       'population_id':pid,'data':data or {},'reason':reason,'basis':'measured','interpretation':'descriptive',
       'applicability':'applicable' if reason is None else 'blocked','execution':'completed','sensitive_counts':list(counts),'evidence_refs':[]}
    result.data['measurements'].append(m);return m


def predict_batch(adapter,events,prepared):
    pure=adapter.spec.adapter in {'sklearn','constant'} or adapter.spec.adapter=='torch' and adapter.spec.architecture.get('kind','mlp')!='host'
    enabled=pure and getattr(prepared,'cache_enabled',True) and prepared.spec.limits.cache_bytes>0
    if not enabled:return _predict_batch(adapter,events,prepared)
    from collections import OrderedDict
    if not hasattr(prepared,'prediction_cache'):prepared.prediction_cache=OrderedDict();prepared.prediction_cache_bytes=0
    profile=[adapter.spec.predictor_digest,adapter.realization['kind'],adapter.realization.get('index',0),getattr(adapter,'device_spec',prepared.spec.device).precision]
    keys=[digest([profile,e['record'],e['event_key'] if adapter.spec.preprocessing.get('kind')=='tensor' else None,e.get('unavailable_fields',[])]) for e in events]
    cached={i:prepared.prediction_cache[k][0] for i,k in enumerate(keys) if k in prepared.prediction_cache}
    missing=[i for i,k in enumerate(keys) if k not in prepared.prediction_cache]
    fresh=_predict_batch(adapter,[events[i] for i in missing],prepared) if missing else []
    outputs={i:o for i,o in zip(missing,fresh)};result=[]
    for i,k in enumerate(keys):
        if i in outputs:out=outputs[i]
        else:
            out=cached[i]
            if k in prepared.prediction_cache:prepared.prediction_cache.move_to_end(k)
            adapter.realization['cache_hits']=adapter.realization.get('cache_hits',0)+1
        result.append(copy.deepcopy(out))
        if k not in prepared.prediction_cache and out['execution']=='completed':
            size=len(json.dumps(out))+len(k)+256
            if size<=prepared.spec.limits.cache_bytes:
                while prepared.prediction_cache and prepared.prediction_cache_bytes+size>prepared.spec.limits.cache_bytes:
                    _,(_,old_size)=prepared.prediction_cache.popitem(last=False);prepared.prediction_cache_bytes-=old_size
                prepared.prediction_cache[k]=(copy.deepcopy(out),size);prepared.prediction_cache_bytes+=size
    return result


def _predict_batch(adapter,events,prepared):
    fields={f.column for f in adapter.spec.inputs}
    coupled=adapter.spec.adapter=='custom' and not adapter.realization['host_registration']['batch_independent']
    if any(fields&set(e.get('unavailable_fields',())) for e in events):
        if coupled:return [{'channels':{},'channel_failures':{},'execution':'complete_batch_unavailable','failure_code':'batch_input_after_information_cutoff','issuance':'failed','decision':None} for e in events]
        return [({'channels':{},'channel_failures':{},'execution':'feature_unavailable','failure_code':'input_after_information_cutoff','issuance':'failed','decision':None} if fields&set(e.get('unavailable_fields',())) else predict_batch(adapter,[e],prepared)[0]) for e in events]
    if hasattr(adapter,'predict_normalized'):return adapter.predict_normalized(events)
    records=[{**e['record'],'_cg6_event_key':e['event_key']} for e in events]
    try:
        raw=adapter.predict(records)
        return normalize_outputs(raw,adapter.spec,len(events),prepared.config.probability_tolerance)
    except Exception as exc:
        oom=isinstance(exc,MemoryError) or 'out of memory' in str(exc).lower()
        if oom:raise
        code=getattr(exc,'code',None)
        rejected=code=='predictor_input_rejected' or adapter.spec.adapter=='sklearn' and isinstance(exc,ValueError)
        if not rejected:raise
        if len(events)>1 and not coupled:return [predict_batch(adapter,[e],prepared)[0] for e in events]
        if coupled:return [{'channels':{},'channel_failures':{},'execution':'input_rejected','failure_code':'complete_batch_input_rejected','issuance':'failed','decision':None} for e in events]
        return [{'channels':{},'channel_failures':{},'execution':'input_rejected','failure_code':'predictor_input_rejected','issuance':'failed','decision':None}]


def apply_events(prepared,adapter,events,scope,*,sink=None):
    view=prepared.start_view(adapter.spec,scope);pending=[];size=0
    batch=prepared.spec.limits.modality_batch_rows if adapter.spec.preprocessing.get('kind') in {'text','image'} else prepared.spec.limits.batch_rows
    if adapter.spec.preprocessing.get('kind')=='image' and not adapter.spec.preprocessing.get('image_size'):batch=1
    coupled=adapter.spec.adapter=='custom' and not adapter.realization['host_registration']['batch_independent']
    def flush(items,attempt=0):
        nonlocal batch
        if any(not e.get('variant',{}).get('applicable',True) for e in items):
            if coupled:
                prepared.append(view,items,[{'channels':{},'channel_failures':{},'execution':'complete_batch_unavailable','failure_code':'batch_transformation_inapplicable','issuance':'failed','decision':None} for e in items]);return
            for e in items:
                if e.get('variant',{}).get('applicable',True):flush([e],attempt)
                else:prepared.append(view,[e],[{'channels':{},'channel_failures':{},'execution':'transformation_inapplicable','failure_code':'transformation_invalid_or_infeasible'}])
            return
        try:outputs=predict_batch(adapter,items,prepared)
        except Exception as exc:
            if not coupled and (isinstance(exc,MemoryError) or 'out of memory' in str(exc).lower()) and len(items)>1 and len(adapter.realization['retries'])<prepared.spec.limits.max_inference_retries:
                adapter.realization['retries'].append({'rows':len(items),'attempt':attempt+1,'reason':'recognized_oom'})
                mid=len(items)//2;batch=min(batch,mid);flush(items[:mid],attempt+1);flush(items[mid:],attempt+1);return
            raise
        prepared.append(view,items,outputs)
        if sink:sink(items,outputs)
    if coupled:
        complete={}
        for event in prepared.events():
            key=tuple(event['record'].get(c) for c in prepared.spec.batch_columns) if prepared.spec.batch_columns else ('application',)
            group=complete.setdefault(key,{'count':0,'roles':set()});group['count']+=1;group['roles'].add(event['role'])
        groups={};used=0
        for event in events:
            key=tuple(event['record'].get(c) for c in prepared.spec.batch_columns) if prepared.spec.batch_columns else ('application',)
            if any(v is None or v=='' for v in key):raise EvaluationError('Batch-coupled input ownership is incomplete.','execution_batch')
            group=groups.setdefault(key,[]);group.append(event);used+=len(json.dumps(event))+256
            if len(group)>batch or used>prepared.config.max_rss_bytes//3:raise EvaluationError('A complete coupled batch exceeds admission.','execution_batch')
        from .batch_admission import tensor_bytes
        for key,group in groups.items():
            if len(group)!=complete[key]['count']:raise EvaluationError('Batch-coupled execution requires complete original batches.','execution_batch_incomplete')
            if len(complete[key]['roles'])>1:raise EvaluationError('A coupled operational batch cannot cross information roles.','execution_batch_role')
            if sum(tensor_bytes(adapter,e,prepared) for e in group)>prepared.spec.limits.batch_tensor_bytes:raise EvaluationError('A complete coupled batch exceeds tensor admission.','batch_tensor_limit')
            flush(group)
        prepared.finish_view(view)
        from .frozen import apply_frozen
        apply_frozen(prepared,view);return view
    tensor_size=0
    from .batch_admission import tensor_bytes
    for event in events:
        estimate=tensor_bytes(adapter,event,prepared)
        if estimate>prepared.spec.limits.batch_tensor_bytes:raise EvaluationError('One event exceeds tensor allocation admission.','batch_tensor_limit')
        if pending and tensor_size+estimate>prepared.spec.limits.batch_tensor_bytes:flush(pending);pending=[];size=0;tensor_size=0
        pending.append(event);size+=sum(len(str(v)) for v in event['record'].values())
        tensor_size+=estimate
        if len(pending)>=batch or size>=prepared.config.batch_bytes:
            flush(pending);pending=[];size=0;tensor_size=0
    if pending:flush(pending)
    prepared.finish_view(view)
    from .frozen import apply_frozen
    apply_frozen(prepared,view);return view


def _worker(spec,config,roots,operation,expected,staging,registrations,options,*,progress=None):
    try:
        return _worker_once(spec,config,roots,operation,expected,staging,registrations,options,progress=progress)
    except Exception as exc:
        cause=exc;reason=None
        while cause is not None:
            code=getattr(cause,'code',None)
            if code in {'device_unavailable','device_precision','device_memory_limit'}:reason=code
            if isinstance(cause,MemoryError) or 'out of memory' in str(cause).lower():reason='recognized_oom'
            if 'not implemented for' in str(cause).lower() and any(k in str(cause).lower() for k in ('mps','cuda')):reason='unsupported_device_operation'
            cause=cause.__cause__
        if not spec.device.allow_cpu_fallback or spec.device.kind=='cpu' or reason is None or operation=='inspect':
            if reason=='recognized_oom':raise EvaluationError('Memory allocation failed within the requested execution profile.','device_oom') from exc
            raise
        # Discard all partial outputs/checkpoints before one whole-operation
        # restart. Training repeats F/S selection from its initial state.
        for path in Path(staging).iterdir():
            if path.is_dir():shutil.rmtree(path)
            else:path.unlink()
        result=_worker_once(spec,config,roots,operation,expected,staging,registrations,options,progress=progress,fallback=reason)
        result.data['cg6']['fallback']={'requested':spec.device.to_dict(),'actual':'cpu','reason':reason,'restart':'entire_operation_from_initial_state'}
        return result


def _worker_once(spec,config,roots,operation,expected,staging,registrations,options,*,progress=None,fallback=None):
    started=time.monotonic();prepared=PreparedExecution(spec,config,roots,progress)
    prepared.fingerprint=design_fingerprint(prepared.fingerprint,options)
    prepared.cache_enabled=operation!='qualify'
    adapters=[]
    try:
        if expected and prepared.fingerprint!=expected:raise EvaluationError('Confirmed CG6 inputs changed.','stale_confirmation')
        if fallback:
            prepared.requested_spec=spec
            spec=replace(spec,device=replace(spec.device,kind='cpu',index=0,allow_cpu_fallback=False))
            prepared.spec=spec
        if operation=='inspect':
            prepared.verify()
            return Inspection({'schema_version':'confidenceguard.execution_inspection/1.0','fingerprint':prepared.fingerprint,
                'planned_roots':prepared.count,'predictors':[{'id':p.id,'digest':p.predictor_digest,'device':devices.resolve(spec.device,p.adapter)} for p in spec.predictors],
                'capabilities':devices.capabilities(),'effective_spec':spec.to_dict()}, {'status':'completed','peak_workspace_bytes':prepared.work.peak})
        if operation.startswith('auxiliary_'):
            from ..auxiliary.services import run_worker
            return run_worker(prepared,operation,staging,registrations,options,started)
        if operation in {'robustness','robustness_assess','policy_stress'}:
            from ..robustness.services import run_worker
            return run_worker(prepared,operation,staging,registrations,options,started)
        realizations={}
        for p in spec.predictors:
            if progress:progress({'stage':'predictor_loading','completed':len(adapters),'total':len(spec.predictors)})
            try:adapter=Adapter(p,spec.device,config,spec.limits,prepared.work,roots,registrations)
            except EvaluationError as exc:
                if not spec.device.allow_cpu_fallback or spec.device.kind=='cpu' or exc.code not in {'device_unavailable','device_precision'}:raise
                adapter=Adapter(p,replace(spec.device,kind='cpu',index=0),config,spec.limits,prepared.work,roots,registrations)
                adapter.realization.update(requested=spec.device.to_dict(),fallback_reason=exc.code)
            adapters.append(adapter);prepared.attach(adapter)
            if operation!='register':
                apply_events(prepared,adapter,prepared.events(),'original')
            realizations[p.id]=None
        if spec.auxiliaries:
            from ..auxiliary.composite import attach_auxiliaries
            composites=attach_auxiliaries(prepared,{a.spec.id:a for a in adapters},registrations)
            for pid,adapter in composites.items():
                if pid in realizations:continue
                adapters.append(adapter)
                if operation!='register':apply_events(prepared,adapter,prepared.events(),'original')
                realizations[pid]=None
        if spec.ensembles:
            from .ensembles import attach_ensembles
            collections={a.spec.id:a for a in adapters};attach_ensembles(prepared,collections)
            for group in spec.ensembles:
                adapter=collections[group['id']];adapters.append(adapter)
                if operation!='register':apply_events(prepared,adapter,prepared.events(),'original')
                realizations[adapter.spec.id]=None
        evidence=prepared.metrics() if prepared.views else None
        result=make_result(prepared,'registration' if operation=='register' else 'qualification' if operation=='qualify' else 'execution',
            {'devices':realizations,'predictor_digests':{p.id:p.predictor_digest for p in spec.predictors}},started=started,evidence=evidence,staging=staging)
        if operation=='qualify':
            parity=qualify(prepared,adapters,options)
            result.data['cg6']['parity']=parity
        for adapter in adapters:realizations[adapter.spec.id]=adapter.finish()
        if operation=='qualify':
            qualified={}
            for adapter in adapters:
                counts=parity['runtime_evidence'][adapter.spec.id];kind=adapter.realization['kind']
                observed=counts['usable_outputs']>0 and counts['forward_batches']>0
                if kind=='cuda' and adapter.spec.adapter=='onnx':observed &= realizations[adapter.spec.id].get('cuda_nodes_observed',False)
                state='failed_for_recorded_corpus' if parity['batch_parity']=='failed' or parity['reference_parity']=='failed' else 'execution_and_batch_parity_verified_reference_unestablished' if observed and parity['reference_parity']=='not_supplied' else 'verified_for_recorded_model_runtime_and_reference_corpus' if observed else 'runtime_verification_not_established'
                qualified[adapter.spec.id]=state
                if observed:result.data['cg6']['qualification'][kind]=state
            result.data['cg6']['model_qualification']=qualified
        prepared.verify();return result
    except EvaluationError:raise
    except Exception as exc:
        raise EvaluationError('Predictor operation failed; no completed evidence was published.','predictor_execution_failed','execution') from exc
    finally:prepared.close()


def qualify(prepared,adapters,options):
    atol=options.get('atol',1e-6);rtol=options.get('rtol',1e-5)
    from .contracts import finite
    finite(atol,minimum=0);finite(rtol,minimum=0)
    reference=options.get('reference')
    expected={} if reference is None else {(r['predictor'],r['event_key']):r for r in reference}
    details=[];passed=True;external=reference is not None;runtime_evidence={}
    for adapter in adapters:
        batch_rows={r['event_key']:r for r in prepared.output_rows(adapter.spec.id)}
        runtime_evidence[adapter.spec.id]={'usable_outputs':sum(r['execution']=='completed' and bool(r['channels']) and not r['channel_failures'] for r in batch_rows.values()),'forward_batches':adapter.realization.get('batches',0)}
        coupled=adapter.spec.adapter=='custom' and not adapter.realization['host_registration']['batch_independent']
        runtime_evidence[adapter.spec.id]['batch_test']='complete_declared_batch_replay' if coupled else 'singleton_vs_batch_invariance'
        groups={}
        if coupled:
            for event in prepared.events():
                key=tuple(event['record'].get(c) for c in prepared.spec.batch_columns) if prepared.spec.batch_columns else ('application',)
                groups.setdefault(key,[]).append(event)
        replay=groups.values() if coupled else ([e] for e in prepared.events())
        for group in replay:
            actuals=predict_batch(adapter,group,prepared)
            for event,actual in zip(group,actuals):
                prior=batch_rows[event['event_key']]
                compare_row(prepared,adapter,event,actual,prior,expected,external,details,atol,rtol)
        passed &= not any(d['kind']=='batch_parity_failed' and d['predictor']==adapter.spec.id for d in details)
    return {'batch_parity':'passed' if passed else 'failed','reference_parity':'not_supplied' if not external else 'failed' if any(d['kind']=='reference_parity_failed' for d in details) else 'passed',
            'atol':atol,'rtol':rtol,'details':details,'runtime_evidence':runtime_evidence,'qualification_scope':'recorded model/runtime/corpus only; no scientific improvement or universal device claim'}


def compare_row(prepared,adapter,event,actual,prior,expected,external,details,atol,rtol):
    def compare(a,b):
        if a.get('execution')!=b.get('execution') or a.get('decision')!=b.get('decision') or a.get('issuance')!=b.get('issuance') or a.get('channel_failures')!=b.get('channel_failures') or set(a.get('channels',{}))!=set(b.get('channels',{})):return False
        for k,v in a['channels'].items():
            if k in {'prediction','issuance'}:
                if v!=b['channels'][k]:return False
            elif not np.allclose(v,b['channels'][k],atol=atol,rtol=rtol):return False
        return True
    ok=compare(prior,actual)
    ref=expected.get((adapter.spec.id,event['event_key']))
    refok=compare(prior,ref) if ref else False
    if external and not refok:details.append({'predictor':adapter.spec.id,'event_key':event['event_key'],'kind':'reference_parity_failed'})
    if not ok:details.append({'predictor':adapter.spec.id,'event_key':event['event_key'],'kind':'batch_parity_failed'})

def service(spec,config=None,*,operation='execute',allowed_roots=None,expected_fingerprint=None,progress=None,cancel=None,workspace=None,tracking_workspace=None,request_id=None,options=None,_artifact_root=None):
    options=copy.deepcopy(options or {})
    if options.get('artifact') and operation in {'inspect','auxiliary_apply','auxiliary_assess'}:
        # Direct application must enter the same admission path as an attached
        # auxiliary, before identity preparation, inspection or reservation.
        from ..auxiliary.contracts import AuxiliaryArtifact
        artifact=AuxiliaryArtifact.from_dict(options['artifact']).to_dict()
        spec=ExecutionSpec.from_dict(spec) if isinstance(spec,dict) else spec
        attached=list(spec.auxiliaries)
        prior=next((i for i,a in enumerate(attached) if a['id']==artifact['id']),None)
        if prior is None:attached.append(artifact)
        elif attached[prior]['artifact_digest']!=artifact['artifact_digest']:
            raise EvaluationError('Direct auxiliary differs from its attached identity.','auxiliary_changed')
        else:attached[prior]=artifact
        spec=replace(spec,auxiliaries=tuple(attached))
    spec,config,roots=arguments(spec,config,allowed_roots)
    if operation=='robustness_assess':
        from ..robustness.contracts import RobustnessAssessmentSpec
        RobustnessAssessmentSpec(options['protocol'],spec)
    request_digest=digest({'operation':operation,'spec':spec.to_dict(),'config':config.to_dict(),'options':options or {},'expected_fingerprint':expected_fingerprint})
    if workspace is not None and request_id is not None:
        from ..workspace import ReliabilityWorkspace
        ws=ReliabilityWorkspace(workspace) if isinstance(workspace,(str,Path)) else workspace
        with ws.catalog.operation():previous=ws.catalog.receipt(request_id,request_digest)
        if previous:return ws.open(previous['assessment_id'])
    if allowed_roots is None and (options or {}).get('artifact'):
        roots=tuple(sorted(set(roots)|{str(Path(f['path']).absolute().parent) for p in options['artifact'].get('predictors',[]) for f in p.get('files',[])}))
    staging=compat.protected_directory(tempfile.mkdtemp(prefix='numek-cg6-',dir=_artifact_root or config.scratch_directory))
    deadline=time.monotonic()+config.max_seconds
    try:
        budget=replace(config,result_bytes=config.private_bytes+config.result_bytes)
        if operation not in {'inspect','register'}:
            from .exposure import identity_worker,reserve
            roles={'F','S'} if operation=='auxiliary_fit' else {'E'} if operation in {'auxiliary_assess','robustness_assess'} else None
            if operation=='robustness' and options.get('robustness',{}).get('role'):roles={options['robustness']['role']}
            identity=ctx.run(identity_worker,(spec,config,roots,roles,options),budget,progress=progress,cancel=cancel,deadline=deadline).data
            if expected_fingerprint and identity['fingerprint']!=expected_fingerprint:raise EvaluationError('Confirmed inputs changed.','stale_confirmation')
            expected_fingerprint=identity['fingerprint']
            reservation,checks=reserve(identity,operation,options,tracking_workspace or workspace,request_id,config)
            options.update(reservation=reservation,exposure_checks=checks)
        result=ctx.run(_worker,(spec,config,roots,operation,expected_fingerprint,str(staging),host_bindings(),options),budget,progress=progress,cancel=cancel,deadline=deadline)
        if operation=='inspect':
            shutil.rmtree(staging);return result.to_dict()
        if cancel is not None and cancel.is_set():raise EvaluationError('Cancelled before CG6 publication.','cancelled')
        if options.get('reservation'):
            result.private['evidence_use_reservation']=options['reservation']
            result.data['cg6']['exposure_checks']=options['exposure_checks']
            result.private['execution_membership']={'events':identity['canonical_events'],'units':identity['canonical_units']}
        result.seal()
        if len(result.json_text().encode())>config.private_bytes:raise EvaluationError('Protected CG6 result exceeds admission.','private_result_limit')
        if len(json.dumps(result.to_dict()).encode())>config.result_bytes:raise EvaluationError('Public CG6 result exceeds admission.','result_limit')
        if workspace is not None:
            from .storage import save_result
            save_result(workspace,result,request_id=request_id,cancel=cancel,request_digest=request_digest)
        return result
    except BaseException:
        shutil.rmtree(staging,ignore_errors=True);raise


def inspect_predictor(spec,config=None,**kwargs):return service(spec,config,operation='inspect',**kwargs)
def register_predictor(spec,config=None,**kwargs):return service(spec,config,operation='register',**kwargs)
def execute_predictor(spec,config=None,**kwargs):return service(spec,config,operation='execute',**kwargs)
def qualify_predictor(spec,config=None,*,reference=None,atol=1e-6,rtol=1e-5,**kwargs):
    return service(spec,config,operation='qualify',options={'reference':reference,'atol':atol,'rtol':rtol},**kwargs)
