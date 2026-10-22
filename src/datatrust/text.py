"""M6 supervised orchestration; completed evidence never depends on surviving scratch."""
from dataclasses import asdict
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import time
import uuid

from datatrust.text_contracts import TextAuditSpec,TextAnalysisConfig,TextAuditResult
from datatrust.text_normalization import Store,ingest,verify
from datatrust.text_diagnostics import Evidence,required
from datatrust.scalable import Workspace,fail
from datatrust.worker import run_supervised
from datatrust.contracts import AnalysisError


def preflight(spec,config):
    if not isinstance(spec,TextAuditSpec) or not isinstance(config,TextAnalysisConfig):raise ValueError('audit_text requires TextAuditSpec and TextAnalysisConfig.')
    import unicodedataplus as u
    import regex
    if u.unidata_version!='16.0.0' or regex.__version__!='2.5.148':raise ValueError('Install the pinned M6 Unicode dependencies.')
    if len(spec.inputs)>config.execution.max_columns:raise ValueError('Source declarations exceed hard limit.')
    from datatrust.text_models import preflight as models
    return models(config.models)


def _execute(spec,config,*,progress=None):
    started=time.monotonic();work=None
    try:
        model_provenance,protected=preflight(spec,config)
        adapter=[SimpleNamespace(id=x.id,dataset=SimpleNamespace(path=x.source.path),config=None) for x in spec.inputs]
        size=sum(Path(x.source.path).stat().st_size for x in spec.inputs)
        phase={'estimated_peak_workspace_bytes':max(256*1024**2,8*size),'kind':'text_streaming_snapshot_relations_and_bounded_search'}
        work=Workspace(config.execution,adapter,progress,phase_plan=phase)
        if progress:progress({'stage':'text ingestion','owned_workspace':str(work.root)})
        audit_id=uuid.uuid4().hex;e=Evidence(work,spec,config,audit_id);store=Store(work,spec,config,e);store.counts={};total=0;phases={}
        for item in spec.inputs:
            tick=time.monotonic();store.counts[item.id]=ingest(store,item);total+=store.counts[item.id]['records']
            if total>config.execution.max_combined_rows:fail('Combined record population exceeds limit.','record_limit')
            phases[e.sources[item.id]+':ingestion']=time.monotonic()-tick
        from datatrust.text_diagnostics import associated_annotations
        tick=time.monotonic();work.check('text required diagnostics');associated_annotations(store);required(e,store);phases['required']=time.monotonic()-tick
        tick=time.monotonic()
        from datatrust.text_search import investigate
        work.check('text bounded investigations');investigate(e,store);phases['bounded_lexical']=time.monotonic()-tick
        tick=time.monotonic()
        from datatrust.text_models import investigate as model_investigation
        work.check('text optional models');model_investigation(e,store,model_provenance);phases['models']=time.monotonic()-tick
        for info in store.sources.values():verify(info)
        for info in store.asset_cache.values():verify(info)
        clean_assets={p:{k:v for k,v in info.items() if k!='snapshot'} for p,info in store.asset_cache.items()}
        protected+=list(clean_assets)+[x.source.path for x in spec.inputs]+[x['path'] for x in store.sources.values()]
        private={'schema':'text_private_manifest_v1','audit_id':audit_id,'spec':{'inputs':{x.id:asdict(x) for x in spec.inputs},'evaluation':asdict(spec.evaluation)},'config':asdict(config),'sources':store.sources,'assets':clean_assets,'locators':e.locators,'definitions':e.definitions,'protected_paths':list(dict.fromkeys(protected)),'models':model_provenance}
        raw=json.dumps(private,ensure_ascii=True,allow_nan=False).encode()
        if len(raw)>config.limits.private_bytes:fail('Private locator return payload exceeds budget.','private_result_limit')
        from datatrust.text_private import digest
        profile={'audit_id':audit_id,'private_manifest_sha256':digest(private),'source_count':len(spec.inputs),'source_populations':{e.sources[k]:v for k,v in store.counts.items()},'normalized_items':store.items,'asset_references':store.asset_count,'source_bytes':size,'asset_bytes':store.asset_bytes,'score':None,'summary':f'{len(e.findings)} evidence-qualified findings; required checks completed over applicable records. Bounded investigations disclose their examined scope.'}
        execution={'status':'completed','backend':'duckdb_local','engine_version':__import__('duckdb').__version__,'effective_limits':asdict(config.execution),'text_limits':asdict(config.limits),'phase_seconds':phases,'duration_seconds':time.monotonic()-started,'peak_workspace_bytes':work.peak,'estimated_peak_workspace_bytes':work.estimate,'provenance':{e.sources[k]:{'sha256':v['sha256'],'bytes':v['bytes']} for k,v in store.sources.items()},'warnings':['Budgets are engineering caps, not capacity promises or OS quotas.','RSS monitoring can overshoot between samples.','Bounded or approximate searches cannot establish global absence.']}
        execution['effective_limits'].pop('scratch_directory',None)
        # Publication is one transaction for the whole text audit. Native faults
        # can invalidate both a DuckDB connection and collector state; publishing
        # required-only evidence would imply trustworthy recovery we cannot prove.
        execution['publication_policy']='whole_audit_atomic_fail_closed'
        from datatrust.text_presentation import executive_summary
        executive=executive_summary({'profile':profile,'checks':e.checks,'evidence':e.records,'findings':e.findings,'coverage':{'families':e.coverage}})
        profile.update(summary=executive['summary'],executive_action_count=len(executive['actions']),technical_finding_count=len(e.findings))
        result=TextAuditResult(profile,e.checks,e.records,e.findings,{'required_population':'All framed records and valid applicable mapped items; invalidity remains accounted.','families':e.coverage,'retained_details_are_bounded':True},execution,datetime.now(timezone.utc).isoformat(),private)
        from datatrust.guidance import attach_guidance
        attach_guidance(result)
        if len(result.json_text().encode())>config.execution.result_bytes:fail('Public text result exceeds budget.','result_limit')
        work.check('completed text evidence publication',config.execution.result_bytes+len(raw))
        return result
    except AnalysisError:
        raise
    except Exception as exc:
        # Native/parser failures must not leak SQL literals, records or paths through supervision.
        raise AnalysisError('Text execution failed; no completed evidence was published.',code='text_execution_failed',stage='text execution') from exc
    finally:
        if work:work.close()


def audit_text(spec,config=None,*,progress=None,cancel=None):
    config=config or TextAnalysisConfig();preflight(spec,config)
    return run_supervised(_execute,(spec,config),config.execution,progress=progress,cancel=cancel)
