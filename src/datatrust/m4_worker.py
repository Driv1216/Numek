"""One spawned local worker. Parent monitoring can terminate native operations."""
from dataclasses import asdict, replace
from datetime import datetime, timezone
import json
import multiprocessing
import os
from pathlib import Path
import shutil
import time
import traceback

import psutil

from datatrust.contracts import AnalysisConfig, AnalysisError, AnalysisResult
from datatrust.m4_contracts import (AdvancedTabularOptions, ComparisonConfig, ComparisonResult, DatasetInput, ExecutionOptions)
from datatrust.scalable import Workspace, ingest, inventory, owned_inventory, available, METHOD, PARSING_POLICY, fail
from datatrust.m4_diagnostics import Evidence, analyze_input
from datatrust.ingestion import verify_source


def _classification_score(work,r,profile):
    if r.task.kind!='classification' or r.parsing['base_task_policy']!='classification_legacy_2026_08_13':return {'status':'not_applicable','values':None}
    from datatrust.scoring import score_profile
    from datatrust.profiler import _leakage_candidates
    t=r.task.target_names[0];c=r.col(t)
    n,small,large=work.con.execute(f'SELECT count(*),min(n),max(n) FROM (SELECT count(*) n FROM {r.table} WHERE {c} IS NOT NULL GROUP BY {c})').fetchone()
    labeled=r.rows-next(x['missing_count'] for x in profile['columns'] if x['name']==t)
    if not labeled:return {'status':'unavailable','reason':'no_observed_labels','values':None}
    balance={'class_count':n,'largest_class_percentage':round(large/labeled*100,2),'minority_class_percentage':round(small/labeled*100,2)}
    p=dict(profile,class_balance=balance,target_missing_count=r.rows-labeled,strong_leakage_candidates=[x['column'] for x in _leakage_candidates(r.features,t) if x['classification']=='strong'],severe_missing_columns=[x['name'] for x in profile['columns'] if x['role']=='feature' and x['missing_rate']>=50])
    # Existing formulas consume the same rounded percentages over this parsed interpretation.
    p['missing_rate']=round(p['missing_rate'],2);p['duplicate_rate']=round(p['duplicate_rate'],2)
    p['columns']=[dict(x,missing_rate=round(x['missing_rate'],2),outlier_rate=round(x['outlier_rate'],2)) for x in p['columns']]
    profile.update(class_balance=balance,target_missing_count=r.rows-labeled,strong_leakage_candidates=p['strong_leakage_candidates'])
    return {'status':'available','methodology_id':'classification_legacy_2026_08_13','scope':r.id,'values':score_profile(p),'interpretation':'Existing scoring formulas over the scalable parsed interpretation; M4 diagnostics do not change the score.'}


def _executive_narrative(findings,coverage,evidence,status,mode):
    """Summarize committed findings and scope without new analysis or scoring."""
    checks_by_ref={record.id:record.check_id for record in evidence}
    def family(finding,suffix):
        return any(checks_by_ref.get(ref,'').endswith('.'+suffix) for ref in finding['evidence_refs'])
    separation=[f for f in findings if f['evidence_type']=='declared_violation' and family(f,'split_integrity')]
    populations=[f for f in findings if family(f,'populations')]
    requirements=[f for f in findings if f['evidence_type']=='declared_violation' and f not in separation]
    other=[f for f in findings if f not in separation and f not in populations and f not in requirements]
    diagnostics=coverage['diagnostics']
    failed=sum(d.get('status')=='failed' for d in diagnostics.values())
    bounded=sum(bool(d.get('planned_bounds') or d.get('unsearched_scope')) for d in diagnostics.values())
    blocked=sum(bool(d.get('status')=='blocked' or d.get('distribution_blocks')) for d in diagnostics.values())
    sentences=[];scope_limits=[]
    if status=='partial':
        sentences.append(f'Analysis is partial: {failed} diagnostic'+(' failed.' if failed==1 else 's failed.'))
        scope_limits.append('Conclusions cover committed evidence only; failed diagnostics remain unanswered.')
    if separation:
        pairs=len({f['scope'] for f in separation})
        sentences.append(f'Declared split separation is violated in {pairs} source pair'+('.' if pairs==1 else 's.'))
    if requirements:
        count=len(requirements)
        sentences.append(f'{count} declared-requirement finding'+(' warrants review.' if count==1 else 's warrant review.'))
    if populations:
        count=len(populations)
        sentences.append(f'{count} population comparison'+(' shows' if count==1 else 's show')+' distribution or missing/non-finite changes meeting the configured effect and support thresholds.')
    if other:
        count=len(other);leading=other[0]['title'].rstrip('. ')
        sentences.append(f'{count} '+('additional ' if separation or requirements or populations else '')+'review finding'+(' remains' if count==1 else 's remain')+f'; leading concern: {leading}.')
    if not findings:
        subject='comparison' if mode else 'dataset'
        sentences.append(f'No qualifying issues were found within completed {subject} coverage.')
    if bounded:
        sentences.append('Search limits left some analytical scope unsearched; completed bounded checks retain their evidence.')
        scope_limits.append('Planned search bounds are completed execution, not exhaustive analysis; consult coverage for unsearched scope.')
    if blocked:
        sentences.append('Some selected methods were blocked; conclusions exclude those definitions.')
        scope_limits.append('Blocked methods and excluded alignments remain visible in coverage; available marginal evidence can still be reported.')
    if any(d.get('role_change_qualifications') for d in diagnostics.values()):
        scope_limits.append('Role-changed fields compare supplied marginal values, with the existing sampling/method gates for optional tests; equivalent feature use, target meaning or annotation selection is not established.')
    return {'summary':' '.join(sentences),'limitations':scope_limits+['Parsed equality does not establish byte-identical records or proven leakage.','Effects and support describe supplied populations; conditional evidence is descriptive.','Search bounds and detail omissions remain visible in coverage.']}


def execute(inputs,options,advanced,spec=None,comparison_config=None,owned_snapshots=(),progress=None):
    work=None
    try:
        work=Workspace(options,inputs,progress,owned_snapshots)
        if progress:progress({'stage':'workspace ownership','owned_workspace':str(work.root)})
        relations=[]
        for item in inputs:
            keys=[]
            if spec:
                mapping=spec.column_mappings.get(item.id,{})
                reverse={v:k for k,v in mapping.items()}
                keys=[reverse.get(k,k) for key in spec.identity_keys+spec.group_keys for k in key]
            r=ingest(work,item,tuple(dict.fromkeys(keys)));relations.append(r)
            if sum(r.rows for r in relations)>options.max_combined_rows:fail('Combined row count exceeds job limit; every input role is counted.')
        e=Evidence(work,advanced);profiles={};annotations={}
        if spec:
            from datatrust.comparison import alignment
            for r in relations: r.alignment = alignment(spec,r)
            declared = {c for constraint in advanced.constraints for c in constraint.columns} | {s.column for s in advanced.segments} | {c for pair in advanced.requested_pairs+advanced.spearman_pairs for c in pair}
            known = {c for r in relations for c in r.alignment}
            if set(comparison_config.continuous_columns)-known:
                raise ValueError('Unknown aligned continuous columns: '+', '.join(sorted(set(comparison_config.continuous_columns)-known)))
            unknown = declared-known-{c for constraint in advanced.constraints if constraint.rule in {'required','forbidden'} for c in constraint.columns}
            if unknown: raise ValueError('Unknown aligned diagnostic columns: '+', '.join(sorted(unknown)))
        reference=next((r for r in relations if r.role=='reference'),None)
        for r in relations:
            if spec:
                names=r.alignment
                e.limits=replace(advanced,constraints=tuple(replace(c,columns=tuple(names.get(n,n) for n in c.columns)) for c in advanced.constraints),segments=tuple(replace(s,column=names[s.column]) for s in advanced.segments if s.column in names),requested_pairs=tuple(tuple(names[c] for c in pair) for pair in advanced.requested_pairs if set(pair)<=set(names)),spearman_pairs=tuple(tuple(names[c] for c in pair) for pair in advanced.spearman_pairs if set(pair)<=set(names)),feature_availability={names.get(c,c):v for c,v in advanced.feature_availability.items()})
            profiles[r.id],annotations[r.id]=analyze_input(e,r,advanced=True,reference=reference)
            profiles[r.id]['declarations']['advanced']=asdict(e.limits)
        e.limits=advanced
        summary={}
        if spec:
            from datatrust.comparison import compare_relations
            summary=compare_relations(e,spec,relations,profiles,annotations,comparison_config)
        for item,r in zip(inputs,relations):verify_source(item.dataset.path,r.source,'final source verification')
        work.check('completed evidence publication',options.result_bytes)
        provenance={r.id:{'sha256':r.source['sha256'],'source_bytes':r.source['bytes'],'rows':r.rows,'columns':len(r.names),'parsing_fingerprint':r.parsing['fingerprint']} for r in relations}
        coverage={'task_support':{r.id:r.task.kind for r in relations},'diagnostics':e.coverage,'measurements':e.measurements,'bounds':asdict(advanced),'advanced_job_work_units':e.work_units,'meaning':'Accepted task-family support does not mean exhaustive analytical searches. Planned limits complete bounded scope; omitted detail and unsearched scope remain explicit.'}
        execution={'status':'partial' if any(c.execution.value=='failed' for c in e.checks) else 'completed','backend':'duckdb_local','engine_version':__import__('duckdb').__version__,'parsing_policy':PARSING_POLICY,'method_version':METHOD,'effective_limits':asdict(options),'duration_seconds':time.monotonic()-work.started,'peak_workspace_bytes':work.peak,'estimated_peak_workspace_bytes':work.estimate,'planning_estimate_is_upper_bound':False,'ledger':work.phases,'provenance':provenance,'warnings':['Resource monitoring can overshoot between samples; memory and disk settings are not OS quotas.','Capacity and performance targets are measured engineering objectives, not guarantees.']}
        now=datetime.now(timezone.utc).isoformat()
        findings=sorted(e.findings,key=lambda f:({'High':0,'Moderate':1}.get(f['priority'],2),f['id']))
        narrative=_executive_narrative(findings,coverage,e.records,execution['status'],spec.mode if spec else None)
        if spec:
            result=ComparisonResult(tuple(inputs),spec,{'sources':profiles,'comparison':summary},{r.id:r.parsing for r in relations},[],e.checks,e.records,findings,narrative,{'dataset_name':spec.dataset_name,'purpose':spec.purpose,'presentation':asdict(comparison_config.presentation)},coverage,{'status':'not_applicable','values':None,'reason':'Comparisons have no composite score or risk band.'},execution,now,METHOD)
        else:
            r=relations[0]
            result=AnalysisResult(inputs[0].dataset,r.task,profiles[r.id],r.parsing,[],e.checks,e.records,findings,narrative,{'dataset_name':inputs[0].dataset.dataset_name,'purpose':inputs[0].dataset.purpose,'source_filename':r.source['filename'],'presentation':asdict(r.config.presentation)},coverage,_classification_score(work,r,profiles[r.id]),execution,now,METHOD,'1.3')
        size=len(result.json_text().encode('utf-8'))
        if size>options.result_bytes:fail(f'Serialized retained result {size} bytes exceeds {options.result_bytes}; reduce diagnostic/detail bounds.', 'result_limit')
        result.execution['serialized_bytes']=size
        return result
    finally:
        if work:work.close()


def run_worker(inputs,options,advanced,spec=None,comparison_config=None,*,progress=None,cancel=None,owned_snapshots=()):
    from datatrust.worker import run_supervised
    return run_supervised(execute,(inputs,options,advanced,spec,comparison_config,owned_snapshots),options,
        progress=progress,cancel=cancel,owned_snapshots=owned_snapshots)


def analyze_scalable(dataset,task,config,**kwargs):
    options=config.execution or ExecutionOptions()
    if config.limits and config.limits.max_seconds is not None:options=replace(options,max_seconds=min(options.max_seconds,config.limits.max_seconds))
    item=DatasetInput('dataset','dataset',dataset,task,replace(config,execution=None,advanced=None))
    return run_worker((item,),options,config.advanced or AdvancedTabularOptions(missingness=False,dependencies=False),**kwargs)


def compare(spec,config=None,**kwargs):
    from datatrust.m4_contracts import ComparisonSpec
    if not isinstance(spec,ComparisonSpec):raise ValueError('compare requires ComparisonSpec.')
    config=config or ComparisonConfig()
    if not isinstance(config,ComparisonConfig):raise ValueError('config must be ComparisonConfig.')
    from datatrust.contracts import AnnotationOptions
    inputs = tuple(replace(item,config=replace(item.config or AnalysisConfig(), annotations=(item.config.annotations if item.config and item.config.annotations is not None else AnnotationOptions()))) for item in spec.inputs)
    effective = replace(spec, inputs=inputs)
    return run_worker(inputs,config.execution,config.advanced,effective,config,**kwargs)
