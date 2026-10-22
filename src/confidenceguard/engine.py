"""Prediction evaluation orchestration. No HTTP, templates or model execution."""
import copy
from dataclasses import replace
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import time
import uuid
from .contracts import *
from . import compat
from .sources import Store, rows
from .result import EvaluationResult, Inspection
from .analytics import Evidence,evaluate_scope,policies,compare,literal,distributions


def preflight(spec,config):
    if not isinstance(spec,EvaluationSpec) or not isinstance(config,EvaluationConfig):raise EvaluationError('Typed evaluation specification/configuration required.')
    if len(spec.cohorts)>config.max_cohorts or len(spec.task.classes)>config.max_classes:raise EvaluationError('Declaration admission exceeded; adjust explicit limits.','declaration_limit')
    groups=sum((len(c.categories)+2) if c.categories else len(c.edges)+3 for c in spec.cohorts)
    if groups>config.max_groups:raise EvaluationError('Requested cohort groups exceed max_groups, including residual/missing states.','group_limit')
    if len(spec.policies)>config.max_policies or any(len(p.thresholds)>config.max_thresholds for p in spec.policies):raise EvaluationError('Policy admission exceeded.','policy_limit')
    if config.curve_points<4:raise EvaluationError('At least four retained curve points are required.')
    for p in spec.policies:
        needed=len(p.thresholds)+2 if p.thresholds else 103 if p.kind in {'probability_threshold','confidence_abstention'} else 0
        if needed>config.curve_points:raise EvaluationError('Requested cutoffs and endpoint states exceed curve_points.','curve_limit')
    if spec.context and set(spec.context.assertions)-{r.id for r in spec.runs}:raise EvaluationError('Unknown context assertion run.')


def open_store(spec,config,roots,progress=None,extension=None,capture=None):
    """Shared CG1/CG2 snapshot admission and normalization boundary."""
    work=None
    try:
        preflight(spec,config)
        sizes=[Path(s.path).stat().st_size for s in spec.sources]
        if any(v>config.max_source_bytes for v in sizes) or sum(sizes)>config.max_combined_source_bytes:raise EvaluationError('Source-byte admission exceeded.','source_limit')
        decoded=0
        for source,size in zip(spec.sources,sizes):
            with compat.secure_open(source.path,roots):pass
            if source.format=='parquet':
                reader,meta=compat.parquet(source.path)
                try:decoded+=meta['uncompressed_chunk_bytes']*3
                finally:reader.close()
            else:decoded+=size*6
        estimate=max(512*1024**2,sum(sizes)+decoded+config.private_bytes+256*1024**2)
        work=compat.workspace(config,estimate,progress)
        if progress:progress({'owned_workspace':str(work.root),'stage':'prediction_source_ingestion'})
        if extension is None:
            store=Store(work,spec,config,roots)
        else:
            from .method_sources import MethodStore
            store=MethodStore(work,spec,config,roots,extension)
        if capture is not None:
            from .history_capture import Capture
            store.history_capture=Capture(capture,store)
            store.history_capture.extend_projection(store)
        store.ingest()
        if capture is not None:store.history_capture.raw(store)
        cells=sum(store.counts[r.source]*(len(spec.task.classes) if r.probabilities or r.score and r.score.columns else 0) for r in spec.runs)
        if cells>config.probability_cells:raise EvaluationError('Probability/score cell admission exceeded.','probability_cell_limit')
        store.prepare()
        return work,store,cells
    except BaseException:
        if work:work.close()
        raise


def _execute(spec,config,roots,inspection,expected,capture=None,*,progress=None):
    started=time.monotonic();work=None
    try:
        work,store,cells=open_store(spec,config,roots,progress,capture=capture)
        if capture is not None and not inspection:store.history_capture.outputs(store)
        fingerprint=digest({'sources':{sid:{'sha256':v['sha256'],'bytes':v['bytes']} for sid,v in store.sources.items()},'spec':spec.to_dict(),'config':config.to_dict(),'outcome_snapshot':store.outcome_facts.get('snapshot_digest'),'context_snapshot':store.context_facts['snapshot_digest'],'methodology':METHOD})
        if expected and expected!=fingerprint:raise EvaluationError('Confirmed inputs or configuration changed.','stale_confirmation')
        if inspection:
            data={'schema_version':'confidenceguard.inspection/1.0','fingerprint':fingerprint,'sources':[{'id':s.id,'columns':store.headers[s.id],'records':store.counts[s.id],'bytes':store.sources[s.id]['bytes']} for s in spec.sources],'effective_spec':spec.to_dict(),'effective_config':config.to_dict(),'outcomes':store.outcome_facts,'runs':store.run_facts,'methodology_id':METHOD}
            store.verify()
            return Inspection(data,{'status':'completed','peak_workspace_bytes':work.peak,'duration_seconds':time.monotonic()-started})
        if progress:progress({'stage':'prediction_metrics'})
        e=Evidence(store)
        for run in spec.runs:
            table=store.run_tables[run.id];distributions(e,run,table);evaluate_scope(e,run,table,'true','overall')
            for method,present in [('probability_quality',bool(run.probabilities)),('supplied_intervals',bool(run.intervals)),('fixed_policy_replay',any(p.run==run.id for p in spec.policies))]:
                e.checks.append({'id':method+':'+run.id,'applicability':'applicable' if present else 'not_applicable','execution':'completed' if present else 'not_run','reason':None if present else 'representation_or_policy_not_declared'})
            for i,c in enumerate(spec.cohorts):
                if store.run_facts[run.id]['context_conflicts'].get(c.column):
                    e.checks.append({'id':f'cohort_{i}:{run.id}','applicability':'blocked','execution':'not_run','reason':'conflicting_canonical_context_assertion'});continue
                groups=store.con.execute(f'SELECT g{i},count(*) FROM {table} GROUP BY 1 ORDER BY 1').fetchall()
                for g,count in groups:
                    if g=='unresolved':
                        e.checks.append({'id':f'cohort_{i}:{run.id}:unresolved','applicability':'blocked','execution':'not_run','reason':'no_unique_context','count':count});continue
                    evaluate_scope(e,run,table,f'g{i}={literal(g)}',f'cohort_{i}/{g}')
                inventory=store.con.execute(f'SELECT count(DISTINCT json_extract_string(payload,?)) FROM context_unique',[ '$.'+json.dumps(c.column)]).fetchone()[0]
                e.checks.append({'id':f'cohort_{i}:{run.id}:inventory','applicability':'applicable','execution':'completed','data':{'observed_context_values':inventory,'groups':[{'group':g,'records':count} for g,count in groups],'residual_is_not_absence':True,'overlapping_declarations_not_summed':True}})
            policies(e,run,table)
        comparison=compare(e)
        findings=[]
        for run in spec.runs:
            f=store.run_facts[run.id]
            for field in ('duplicate_keys','missing_keys','invalid_probabilities','inline_conflicts','decision_rule_mismatches','unresolved_issuance'):
                if f[field]:findings.append({'code':field,'run':run.id,'priority':'Review','message':'Review the declared input interpretation and affected evidence.','count':f[field]})
            if run.role in {'train','calibration','selection'}:findings.append({'code':'not_held_out','run':run.id,'priority':'Review','message':'This run is not declared independent final evaluation; generalization is not established.'})
        if not e.inference and config.sampling.mode!='descriptive':findings.append({'code':'inference_blocked','priority':'Review','message':'Known repeated entities block independent-row intervals.'})
        if comparison and comparison['blocked_reasons']:findings.append({'code':'paired_comparison_blocked','priority':'Review','message':'Paired performance is unavailable under the current outcome, identity or timing declarations.','reasons':comparison['blocked_reasons']})
        if any(m['metric']=='log_loss' and m['value_state']=='positive_infinity' for m in e.measurements):findings.append({'code':'zero_probability_observed_outcome','priority':'Review','message':'An observed reference outcome received zero supplied probability.'})
        analysis_id=uuid.uuid4().hex
        runs=[{'id':r.id,'display_name':r.model.display_name or f'Model {i+1}','version_alias':f'Version {i+1}','model':r.model.to_dict(),'role':r.role,'decision_provenance':r.decision.to_dict(),'representations':{'hard_prediction':bool(r.prediction or r.decision.column),'probabilities':bool(r.probabilities),'scores':bool(r.score),'intervals':len(r.intervals)},'facts':store.run_facts[r.id]} for i,r in enumerate(spec.runs)]
        for declaration,run in zip(spec.runs,runs):
            run['decision_provenance'].update(origin='supplied' if declaration.prediction or declaration.decision.column else 'derived' if declaration.decision.rule!='none' else 'none',source_fields=[c for c in (declaration.decision.column or declaration.prediction,declaration.decision.state_column) if c],behavior='recorded candidate output' if declaration.prediction or declaration.decision.column else 'hypothetical rule' if declaration.decision.rule!='none' else 'no decision established')
        e.validate_populations()
        coverage={'population_provenance_version':'1.1','sources':store.counts,'run_populations':{},'populations':list(e.populations.values()),'outcome_snapshot':store.outcome_facts,'context_snapshot':store.context_facts,'retention_limits':{'witnesses_per_group':config.witnesses,'retained_witnesses':len(e.locators),'maximum_investigation_details':config.max_details,'curve_points':config.curve_points},'analytical_scope':'All eligible admitted records; no silent sampling. Retained curve points and witnesses are bounded.','sampling':{'requested':config.sampling.mode,'inference_enabled':e.inference},'limits':{'max_cohorts':config.max_cohorts,'max_groups':config.max_groups,'probability_cells':config.probability_cells,'observed_probability_cells':cells},'limitations':['Supplied outcomes are reference evidence, not independently verified truth.','Observed labels need not represent unobserved cases.','No universal score or production approval.','Unknown provenance does not establish out-of-sample evaluation.']}
        for r in spec.runs:
            t=store.run_tables[r.id]
            coverage['run_populations'][r.id]={'outcome_states':dict(store.con.execute(f'SELECT coalesce(outcome_reason,\'eligible\'),count(*) FROM {t} GROUP BY 1').fetchall()),'issuance_states':dict(store.con.execute(f'SELECT state,count(*) FROM {t} GROUP BY 1').fetchall())}
        coverage['cohort_definitions']=[c.to_dict() for c in spec.cohorts]
        private={'schema':'confidenceguard.private_manifest/1.0','analysis_id':analysis_id,'spec':spec.to_dict(),'config':config.to_dict(),'files':store.sources,'locators':e.locators,'methodology':METHOD}
        execution={'status':'completed','backend':'duckdb_local','engine_version':__import__('duckdb').__version__,'effective_limits':config.to_dict(),'peak_workspace_bytes':work.peak,'estimated_peak_workspace_bytes':work.estimate,'planning_estimate_is_upper_bound':False,'duration_seconds':time.monotonic()-started,'publication_policy':'whole_evaluation_atomic','resource_qualification':'Sampled RSS and storage controls can overshoot; admission settings are not capacity guarantees.'}
        execution['effective_limits'].pop('scratch_directory',None)
        data={'schema_version':RESULT_SCHEMA,'methodology_id':METHOD,'analysis_id':analysis_id,'generated_at':datetime.now(timezone.utc).isoformat(),'name':spec.name,'task':spec.task.to_dict(),'runs':runs,'outcomes':store.outcome_facts,'comparison':comparison,'measurements':e.measurements,'checks':e.checks,'findings':findings,'coverage':coverage}
        result=EvaluationResult(data,private,execution)
        store.verify();work.check('completed evidence publication',config.private_bytes)
        if len(result.json_text().encode())>config.private_bytes:raise EvaluationError('Protected result exceeds its configured budget.','private_result_limit')
        return result
    except EvaluationError:raise
    except Exception as exc:
        from datatrust.contracts import AnalysisError
        if isinstance(exc,AnalysisError):raise EvaluationError('Evaluation stopped; review source/limits.',exc.code,exc.stage) from exc
        raise EvaluationError('Evaluation failed; no completed evidence was published.','evaluation_failed','evaluation') from exc
    finally:
        if work:work.close()


def _arguments(spec,config,allowed_roots):
    if isinstance(spec,dict):spec=EvaluationSpec.from_dict(spec)
    if isinstance(config,dict):config=EvaluationConfig.from_dict(config)
    spec=copy.deepcopy(spec);config=copy.deepcopy(config or EvaluationConfig());preflight(spec,config)
    spec=replace(spec,sources=tuple(replace(s,path=os.path.abspath(s.path)) for s in spec.sources))
    if allowed_roots is not None and not allowed_roots:raise EvaluationError('Authorized roots must not be empty.','roots_required')
    roots=tuple(str(Path(p).absolute()) for p in (allowed_roots if allowed_roots is not None else tuple(str(Path(s.path).absolute().parent) for s in spec.sources)))
    return spec,config,roots


def evaluate(spec,config=None,*,progress=None,cancel=None,allowed_roots=None,expected_fingerprint=None,_capture=None):
    from .method_contracts import ReliabilitySpec, parse_spec
    if isinstance(spec,dict):spec=parse_spec(spec)
    if isinstance(spec,ReliabilitySpec):
        from .methods import evaluate_methods
        return evaluate_methods(spec,config,progress=progress,cancel=cancel,allowed_roots=allowed_roots,expected_fingerprint=expected_fingerprint,_capture=_capture)
    spec,config,roots=_arguments(spec,config,allowed_roots)
    # The legacy worker protocol must budget the full protected return value.
    worker_config=replace(config,result_bytes=config.private_bytes+config.result_bytes)
    result=compat.supervise(_execute,(spec,config,roots,False,expected_fingerprint,_capture),worker_config,progress=progress,cancel=cancel)
    if cancel is not None and cancel.is_set():raise EvaluationError('Evaluation cancelled before commit.','cancelled')
    result.seal()
    if len(result.json_text().encode())>config.private_bytes:raise EvaluationError('Final protected result exceeds budget.','private_result_limit')
    if len(json.dumps(result.to_dict()).encode())>config.result_bytes:raise EvaluationError('Shareable result exceeds budget.','result_limit')
    return result


def inspect(spec,config=None,*,progress=None,cancel=None,allowed_roots=None):
    from .method_contracts import ReliabilitySpec, parse_spec
    if isinstance(spec,dict):spec=parse_spec(spec)
    if isinstance(spec,ReliabilitySpec):
        from .methods import inspect_methods
        return inspect_methods(spec,config,progress=progress,cancel=cancel,allowed_roots=allowed_roots)
    spec,config,roots=_arguments(spec,config,allowed_roots)
    result=compat.supervise(_execute,(spec,config,roots,True,None),config,progress=progress,cancel=cancel)
    return result.to_dict()


class ConfidenceGuard:
    evaluate=staticmethod(evaluate)
    inspect=staticmethod(inspect)
