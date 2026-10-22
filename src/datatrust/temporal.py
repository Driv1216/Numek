"""M5 orchestration: required full-population stages, atomic optional evidence."""
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import time
from datatrust.contracts import AnalysisError
from datatrust.ingestion import verify_source
from datatrust.scalable import Workspace,fail
from datatrust.temporal_contracts import TemporalAuditSpec,TemporalAnalysisConfig,TemporalAuditResult
from datatrust.temporal_normalization import (source_plan,ingest_temporal,canonical_cells,all_clocks,
    normalize_clock,timezone_provenance,zone)
from datatrust.temporal_diagnostics import Evidence,structural,continuity
from datatrust.temporal_availability import availability,histories,maturity
from datatrust.temporal_evaluation import evaluation
from datatrust.temporal_behavior import behavior


def preflight(spec,config):
    if not isinstance(spec,TemporalAuditSpec):raise ValueError('audit_temporal requires TemporalAuditSpec.')
    if not isinstance(config,TemporalAnalysisConfig):raise ValueError('config must be TemporalAnalysisConfig.')
    if len(spec.evaluation.folds)>config.limits.max_folds:raise ValueError('Fold declaration exceeds configured hard limit.')
    for item in spec.inputs:
        for clock in all_clocks(spec,item):
            if clock.timezone:zone(clock.timezone)
        if item.temporal and item.temporal.schedule.timezone:zone(item.temporal.schedule.timezone)
    known_measurements={m.name for item in spec.inputs if item.temporal for m in item.temporal.measurements}
    if set(config.behavior.requested_measurements)-known_measurements:raise ValueError('Requested behavior measurements are undeclared.')
    for pair in config.behavior.multivariate_pairs:
        if not any(x.temporal and set(pair)<={m.name for m in x.temporal.measurements} for x in spec.inputs):raise ValueError('Multivariate pair must bind measurements present in the same source.')
    for fold in spec.evaluation.folds:
        for sid in (fold.train_source_id,fold.evaluation_source_id):
            source=next(x for x in spec.inputs if x.id==sid)
            if any((fold.purge_ns,fold.horizon_ns,fold.lookback_ns)) and (fold.origin or source.temporal.clock).kind!='instant':raise ValueError('Nanosecond fold requirements require instant origin clocks.')
        if fold.label_start and fold.label_start.kind!=fold.label_end.kind:raise ValueError('Label interval clocks must have compatible semantics.')
        if fold.horizon_ns and fold.label_end.kind!='instant':raise ValueError('Nanosecond horizons require instant label clocks.')
    for series in config.behavior.requested_series:
        source=next((x for x in spec.inputs if x.id==series.source_id and x.temporal),None)
        if not source or series.measurement not in {m.name for m in source.temporal.measurements} or len(series.entity)!=len(source.temporal.entity_columns):raise ValueError('Requested series references incompatible source/measurement/entity keys.')
    if len(config.behavior.requested_series)>config.limits.detailed_series:raise ValueError('Requested series exceed the configured detail-search scope; raise its explicit limit.')
    for season in config.behavior.seasonality:
        source=next((x for x in spec.inputs if x.id==season.source_id and x.temporal),None)
        if not source or season.measurement not in {m.name for m in source.temporal.measurements}:raise ValueError('Seasonality references an undeclared analytical measurement.')
        if season.timezone:zone(season.timezone)
    return {'declarations':spec.to_dict(),'configuration':config.to_dict(),'timezone_data':timezone_provenance(),'availability_unknown':{x.id:[m.name for m in x.temporal.measurements if not any(a.source_id==x.id and m.name in a.features for a in spec.availability) and not any(h.source_id==x.id and m.name in h.features for h in spec.histories)] for x in spec.inputs if x.temporal},'budgets_are_provisional':True}


def annotations(e,r):
    if not r.task.target_names:return
    # Reuse the accepted M3 state reducer, translating its evidence rather than altering its policies.
    from datatrust.m4_diagnostics import annotation_relations
    class Adapter:
        work=e.work
        def add(self,scope,family,value,**kwargs):return e.add(family,scope,value,population='supplied target cells and declared annotation expectations')
        def finding(self,ident,title,priority,**kwargs):e.finding(ident,title,kind=kwargs.get('meaning','investigation_candidate'),detail='Annotation evidence is independent of outcome maturation.')
    r.annotations=annotation_relations(Adapter(),r)


def execute(spec,config,owned_snapshots=(),progress=None):
    effective=preflight(spec,config);work=None;started=time.monotonic();timings={}
    try:
        phase=source_plan(spec.inputs,config.limits,config.execution)
        work=Workspace(config.execution,spec.inputs,progress,owned_snapshots,phase_plan=phase)
        if progress:progress({'stage':'workspace ownership','owned_workspace':str(work.root)})
        # Physical ordinals are explicit; disabling implicit order retention reduces native pressure.
        work.con.execute('SET preserve_insertion_order=false')
        e=Evidence(work,config);relations={};profiles={};totalrows=0;totalcells=0;totalseries=0
        for item in spec.inputs:
            tick=time.monotonic();r=ingest_temporal(work,spec,item,config.limits);relations[item.id]=r;totalrows+=r.rows
            if totalrows>config.execution.max_combined_rows:fail('Combined rows exceed the declared job limit.')
            timings[item.id+':ingestion']=time.monotonic()-tick
            profiles[item.id]={'role':item.role,'rows':r.rows,'columns':list(r.names),'source':{k:v for k,v in r.source.items() if k!='signature'},'base_task':asdict(item.task),'auxiliary':item.temporal is None}
            # Explicit base-task references must resolve even though M5 does not run every base diagnostic.
            for c in item.task.target_names+item.task.metadata_columns+item.task.group_columns+(item.task.feature_columns or ()):r.col(c)
            if item.temporal:
                tick=time.monotonic();canonical_cells(work,r,item,config);totalcells+=r.cell_count
                if totalcells>config.limits.max_cells:fail('Combined normalized cell count exceeds hard limit.','temporal_cell_limit')
                totalseries+=r.series
                if totalseries>config.limits.max_series:fail('Combined temporal series exceeds hard limit.','temporal_series_limit')
                timings[item.id+':normalization']=time.monotonic()-tick
                addition=min(config.execution.workspace_bytes, r.cell_count*160+r.series*256)
                work.check(item.id+': cardinality-based sort/join reservation',addition)
                profiles[item.id].update(normalized_cells=r.cell_count,distinct_series=r.series,temporal=asdict(item.temporal))
        tick=time.monotonic()
        totalseries=0
        for r in relations.values():
            if hasattr(r,'cells'):
                structural(e,r);continuity(e,r,relations);annotations(e,r)
                series=f'SELECT entity,measurement FROM {r.cells} WHERE entity_ok UNION SELECT entity,measurement FROM {r.active}'
                if hasattr(r,'expected'):series+=f' UNION SELECT entity,measurement FROM {r.expected}'
                totalseries+=work.con.execute(f'SELECT count(*) FROM ({series})').fetchone()[0]
                if totalseries>config.limits.max_series:fail('Combined observed/expected temporal series exceeds hard limit.','temporal_series_limit')
        timings['required_diagnostics']=time.monotonic()-tick
        tick=time.monotonic();availability(e,spec,relations);histories(e,spec,relations);maturity(e,spec,relations);evaluation(e,spec,relations);timings['availability_history_evaluation']=time.monotonic()-tick
        tick=time.monotonic()
        pairs=[(x.source_id,x.measurement) for x in config.behavior.requested_series]+[(x.source_id,x.measurement) for x in config.behavior.seasonality]
        pairs += [(r.id,name) for pair in config.behavior.multivariate_pairs for r in relations.values() if hasattr(r,'cells') and set(pair)<={m.name for m in r.temporal.measurements} for name in pair]
        pairs += [(r.id,m.name) for name in config.behavior.requested_measurements for r in relations.values() if hasattr(r,'cells') for m in r.temporal.measurements if m.name==name]
        requested=list(dict.fromkeys(pairs))
        if len(requested)>config.limits.behavior_measurements:raise ValueError('Requested investigation scope exceeds the explicit behavior measurement limit.')
        pairs += [(r.id,m.name) for r in relations.values() if hasattr(r,'cells') for m in r.temporal.measurements]
        selected=list(dict.fromkeys(pairs))[:config.limits.behavior_measurements]
        for r in relations.values():
            if hasattr(r,'cells'):
                declared={m.name:m for m in r.temporal.measurements}
                r.behavior_measurements=[declared[name] for sid,name in selected if sid==r.id]
                r.requested_behavior_names={name for sid,name in requested if sid==r.id}
        # Spend bounded work on explicitly requested scope across every source before defaults.
        for phase in (('requested','remaining') if requested else ('complete',)):
            e.behavior_phase=phase
            for r in relations.values():
                if hasattr(r,'cells'):
                    with e.optional('behavior',r.id,relation=r):behavior(e,r)
        timings['behavior']=time.monotonic()-tick
        for item in spec.inputs:verify_source(item.source.path,relations[item.id].source,'final source verification')
        work.check('completed temporal evidence publication',config.execution.result_bytes)
        for item in spec.inputs:
            r=relations[item.id]
            r.parsing['temporal_fingerprint']=hashlib.sha256(json.dumps({'temporal':asdict(item.temporal) if item.temporal else None,'clocks':[asdict(c) for c in all_clocks(spec,item)],'parsing':r.parsing['fingerprint'],'timezone_data':timezone_provenance(),'methodology':'temporal_reliability_v1'},sort_keys=True).encode()).hexdigest()
        provenance={r.id:{'sha256':r.source['sha256'],'source_bytes':r.source['bytes'],'rows':r.rows,'parsing_fingerprint':r.parsing['fingerprint'],'normalization_fingerprint':r.parsing.get('temporal_fingerprint')} for r in relations.values()}
        for record in e.records:
            if record['clock'] is None:record['clock']={item.id:[asdict(c) for c in all_clocks(spec,item)] for item in spec.inputs if item.id in record['source_ids']}
            record['source_references']=[{'source_id':sid,**provenance[sid],'columns':list(relations[sid].names)} for sid in record['source_ids'] if sid in provenance]
            for witness in record['witnesses']:
                if '_row' in witness:witness['ordinal']=witness['_row']
        status='partial' if any(c['execution']=='failed' for c in e.checks) else 'completed'
        unsearched=[]
        for record in e.records:
            scope={k:v for k,v in record['data'].items() if k.startswith('unsearched') and v not in (None,0,[], '')}
            if scope or record['check_id']=='behavior_scope':
                for key in ('selected_measurements','selected_series','selection','selection_bias'):
                    if key in record['data']:scope[key]=record['data'][key]
                unsearched.append({'family':record['check_id'],'source_ids':record['source_ids'],'measurement':record['measurement'],'scope':scope})
        coverage={'computed_aggregate_scope':'Every eligible declared record in required stages; no silent sampling.','checks':e.coverage,'unsearched_analytical_scope':unsearched,'internal_detail_retention_omissions':e.omissions,'presentation_omissions':'Determined independently when rendering. JSON preserves every retained evidence record.','limits':asdict(config.limits),'work_observation_visits':e.visits,'behavior_comparisons':e.comparisons,'representation_equivalence':{'conditions':['Same observations, explicit missing cells and multiplicities','Same measurement identities, meanings, units and representations','Same entity identity, exact clock precision and schedule/lifecycle semantics','Same feature availability, revision semantics, analytical selections and bounds'],'excluded':['physical source row references','file-order evidence'],'absent_long_row_equals_null_wide_cell':'Only under an explicit dense-layout expectation; otherwise absence and supplied missing values differ.'}}
        execution={'status':status,'backend':'duckdb_local','engine_version':__import__('duckdb').__version__,'effective_limits':asdict(config.execution),'temporal_limits':asdict(config.limits),'duration_seconds':time.monotonic()-started,'phase_seconds':timings,'phase_plan':phase,'peak_workspace_bytes':work.peak,'estimated_peak_workspace_bytes':work.estimate,'planning_estimate_is_upper_bound':False,'ledger':work.phases,'provenance':provenance,'timezone_data':timezone_provenance(),'warnings':['Workload budgets are provisional engineering controls, not capacity guarantees or OS quotas.','Decoded-batch/application retention bounds do not bound native Parquet decoder peaks.','Sampled RSS supervision can overshoot between samples.']}
        e.findings.sort(key=lambda x:(x['priority']!='High',x['id']))
        summary=f'{len(e.findings)} evidence-qualified finding(s) across {len(profiles)} supplied source(s). '
        summary+= 'Optional failures leave this result partial; review unanswered scope.' if status=='partial' else 'Required stages completed over eligible records; behavioral search scope is disclosed separately.'
        result=TemporalAuditResult(spec,{'sources':profiles},effective,{r.id:r.parsing for r in relations.values()},e.checks,e.records,e.findings,{'summary':summary,'actions':e.findings[:config.presentation.executive_actions],'limitations':['No composite score or universal readiness verdict.','Investigation defaults are not validated defect criteria.','Supplied evidence does not prove what a production pipeline consumed.']},coverage,execution,{'dataset_name':spec.dataset_name or 'Temporal reliability audit','purpose':spec.purpose,'presentation':asdict(config.presentation)},datetime.now(timezone.utc).isoformat())
        from datatrust.guidance import attach_guidance
        attach_guidance(result)
        if len(result.json_text().encode())>config.execution.result_bytes:fail('Retained temporal result exceeds configured JSON budget.','result_limit')
        return result
    finally:
        if work:work.close()


def audit_temporal(spec,config=None,*,progress=None,cancel=None,owned_snapshots=()):
    from datatrust.worker import run_supervised
    config=config or TemporalAnalysisConfig();preflight(spec,config)
    return run_supervised(execute,(spec,config,owned_snapshots),config.execution,progress=progress,cancel=cancel,owned_snapshots=owned_snapshots)
