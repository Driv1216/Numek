"""M7 supervised core, isolated optional model stage, and final integrity publication."""
from dataclasses import asdict
from datetime import datetime,timezone
import importlib.metadata
import json
import time
import uuid

from datatrust.contracts import AnalysisError
from datatrust.image_contracts import ImageAuditSpec,ImageAnalysisConfig,ImageAuditResult
from datatrust.image_sources import Store,source_plan,roots_for
from datatrust.scalable import Workspace
from datatrust.worker import run_supervised
from datatrust.image_assets import verify_files,membership,error


def preflight(spec,config):
    if not isinstance(spec,ImageAuditSpec) or not isinstance(config,ImageAnalysisConfig): raise ValueError('audit_images requires ImageAuditSpec and ImageAnalysisConfig.')
    if len(spec.inputs)>config.execution.max_columns: raise ValueError('Image source count exceeds its hard limit.')
    for package,version in {'Pillow':'12.3.0','ijson':'3.4.0.post0','PyYAML':'6.0.3','pycocotools':'2.0.10'}.items():
        try:
            if importlib.metadata.version(package)!=version: raise ValueError('Install the pinned images extra.')
        except importlib.metadata.PackageNotFoundError as exc: raise ValueError('Install the pinned images extra.') from exc
    from datatrust.image_models import preflight as models
    model=models(config.models)
    source_plan(spec,config)
    return model


def execute_core(spec,config,model_provenance=None,*,progress=None):
    work=None; started=time.monotonic()
    try:
        plan=source_plan(spec,config)
        work=Workspace(config.execution,[],progress,phase_plan={'estimated_peak_workspace_bytes':plan.estimated_peak_workspace_bytes,'kind':'image_metadata_relations_and_bounded_buffers'},image_source_plan=plan)
        if progress: progress({'stage':'image inventory','owned_workspace':str(work.root)})
        audit_id=uuid.uuid4().hex; store=Store(work,spec,config,audit_id)
        from datatrust.image_sources import ingest
        from datatrust.image_diagnostics import Evidence,required
        from datatrust.image_search import investigate
        for item in spec.inputs: ingest(store,item)
        e=Evidence(store); required(e,store); investigate(e,store)
        from datatrust.image_models import selection
        for oid, in work.con.execute('SELECT oid FROM occurrences ORDER BY hash(oid,?) LIMIT ?',[config.seed,config.limits.details]).fetchall(): store.witness(oid)
        for loc in list(store.locators.values()): store.witness(loc['occurrence_id'])
        selected=selection(store,e) if config.models.directory else []
        files={p:{k:v for k,v in info.items() if k!='snapshot'} for p,info in store.files.items()}
        if model_provenance:
            files.update({v['path']:v for v in model_provenance['files'].values()})
            files[model_provenance['manifest']['path']]=model_provenance['manifest']
        # Retain only published witnesses and selected model locators, not source pixels.
        private={'schema':'image_private_manifest_v1','audit_id':audit_id,'files':files,'memberships':store.memberships,'unavailable':sorted(store.unavailable),'roots':list(store.roots),
                 'spec':spec.to_dict(),'locators':store.locators,'definitions':e.definitions,'model':model_provenance,'model_selection':selected,'model_populations':getattr(store,'model_populations',[])}
        profile={'audit_id':audit_id,'occurrences':store.count,'source_count':len(spec.inputs),'image_locations':work.con.execute('SELECT count(*) FROM assets').fetchone()[0],
                 'dataset_name':spec.dataset_name,'purpose':spec.purpose,'summary':f'{len(e.findings)} evidence-qualified findings across {store.count} image occurrences.'}
        execution={'status':'completed','backend':'duckdb_local','effective_limits':asdict(config.execution),'image_limits':asdict(config.limits),'image_source_limits':asdict(config.source_limits),
                   'duration_seconds':time.monotonic()-started,'peak_workspace_bytes':work.peak,'estimated_peak_workspace_bytes':work.estimate,'capture_read_bytes':store.read_bytes,
                   'initial_hash_seconds':store.hash_seconds,'corpus_copied':False,'publication_policy':'required_core_atomic_optional_model_isolated','warnings':['Sampled resource controls can overshoot.','Capacity and calibrated recall are measured claims for recorded workloads only.']}
        execution['effective_limits'].pop('scratch_directory',None)
        result=ImageAuditResult(profile,e.checks,e.records,e.findings,{'families':e.coverage,'required_population':'complete inventoried and applicable supplied populations within hard limits','retained_examples_are_bounded':True},execution,datetime.now(timezone.utc).isoformat(),private)
        if len(json.dumps(private,allow_nan=False).encode())>config.limits.private_bytes: error('private_result_limit')
        if len(result.json_text().encode())>config.execution.result_bytes: error('result_limit')
        work.check('frozen core publication',len(result.json_text().encode())+len(json.dumps(private).encode()))
        return result
    except AnalysisError: raise
    except Exception as exc: raise AnalysisError('Image core failed; no completed evidence was published.',code='image_core_failed',stage='image core') from exc
    finally:
        if work: work.close()


def finalize(result,spec,config,*,progress=None):
    started=time.monotonic()
    def check():
        if time.monotonic()-started>config.execution.max_seconds: error('deadline')
    from datatrust.image_assets import secure_open
    for path in result.private.get('unavailable',()):
        try:
            with secure_open(path,roots_for(spec)): error('source_availability_changed')
        except AnalysisError as exc:
            if exc.code!='source_unavailable': raise
    model=result.private.get('model') or {}
    model_paths={v['path'] for v in model.get('files',{}).values()}
    if model.get('manifest'): model_paths.add(model['manifest']['path'])
    source_files={p:v for p,v in result.private['files'].items() if p not in model_paths}
    bytes_read=verify_files(source_files,roots_for(spec),check=check)
    if model_paths:
        model_root=str(__import__('pathlib').Path(model['manifest']['path']).parent)
        bytes_read+=verify_files({p:result.private['files'][p] for p in model_paths},(model_root,),check=check)
    for directory,sealed in result.private['memberships'].items():
        if membership(directory,roots_for(spec),check=check)!=sealed: error('directory_membership_changed')
    from datatrust.image_private import digest
    result.private.pop('model_selection',None); result.private.pop('model_populations',None)
    result.profile['private_manifest_sha256']=digest(result.private)
    result.execution.update(final_verification_bytes=bytes_read,final_verification_seconds=time.monotonic()-started)
    if len(json.dumps(result.private,allow_nan=False).encode())>config.limits.private_bytes: error('private_result_limit')
    return result


def audit_images(spec,config=None,*,progress=None,cancel=None):
    from dataclasses import replace
    config=config or ImageAnalysisConfig(); start=time.monotonic(); model=preflight(spec,config); preflight_seconds=time.monotonic()-start
    def remaining():
        left=config.execution.max_seconds-(time.monotonic()-start)
        if left<=0: error('deadline')
        if cancel is not None and cancel.is_set(): error('cancelled')
        return left
    def stage_config(seconds): return replace(config,execution=replace(config.execution,max_seconds=seconds))
    result=run_supervised(execute_core,(spec,stage_config(remaining()),model),replace(config.execution,max_seconds=remaining()),progress=progress,cancel=cancel)
    result.execution['preflight_seconds']=preflight_seconds
    core_execution=dict(result.execution)
    if model:
        reserve=max(30,1.5*(result.execution['initial_hash_seconds']+preflight_seconds))+30
        allocation=max(0,min(config.models.max_seconds,remaining()-reserve))
        if allocation<=0:
            result.checks.append({'id':'image_embeddings','family':'embeddings','applicability':'applicable','execution':'completed','scope':'bounded','violations':0})
            result.coverage['families']['embeddings']={'selected':len(result.private['model_selection']),'examined':0,'stop_reason':'whole_audit_verification_reservation','reference_pool_complete':False}
        else:
            from datatrust.image_models import execute_model
            # A separate process protects committed core evidence from native model failure.
            opts=replace(config.execution,max_seconds=min(remaining()-reserve+15,allocation+15))
            try:
                stage=run_supervised(execute_model,(result.private['model_selection'],model,spec,stage_config(opts.max_seconds),allocation,result.profile['audit_id'],result.private.get('model_populations',())),opts,progress=progress,cancel=cancel)
                result.evidence.extend(stage.evidence); result.checks.extend(stage.checks); result.findings.extend(stage.findings)
                result.coverage['families'].update(stage.coverage['families']); result.private['locators'].update(stage.private.get('locators',{}))
                result.execution['model_execution']=stage.execution
            except AnalysisError as exc:
                if exc.code in {'source_changed','cancelled','out_of_root','unsafe_path','directory_membership_changed'}: raise
                remaining()
                result.execution['status']='partial'
                result.checks.append({'id':'image_embeddings','family':'embeddings','applicability':'applicable','execution':'failed','scope':'bounded','reason':'isolated_model_failure'})
                result.coverage['families']['embeddings']={'examined_evidence_committed':0,'selected':len(result.private['model_selection']),'reason':'isolated_model_failure','model_evidence_discarded':True}
                result.execution['model_failure']={'code':exc.code,'completed_model_result_published':False}
    # The last supervised pass checks source bytes and membership; no corpus copies survive.
    final=run_supervised(finalize,(result,spec,stage_config(remaining())),replace(config.execution,max_seconds=remaining()),progress=progress,cancel=cancel)
    final.execution['core_execution']=core_execution
    final.execution['whole_job_seconds']=time.monotonic()-start
    final.execution['peak_worker_rss_bytes']=max(core_execution.get('peak_worker_rss_bytes',0),final.execution.get('peak_worker_rss_bytes',0),final.execution.get('model_execution',{}).get('peak_worker_rss_bytes',0))
    remaining()
    final.profile['summary']=f'{len(final.findings)} evidence-qualified findings across {final.profile["occurrences"]} image occurrences; {final.execution["status"]} execution.'
    if len(final.json_text().encode())>config.execution.result_bytes: error('result_limit')
    return final
