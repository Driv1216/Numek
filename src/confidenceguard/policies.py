"""Public CG5 orchestration through existing supervision and immutable evidence."""
from dataclasses import replace
from datetime import datetime,timezone
import copy
import json
from pathlib import Path
import time
import uuid

from . import compat
from .contracts import EvaluationConfig,EvaluationError,digest
from .result import Inspection
from .policy_contracts import (METHOD,RESULT,PolicyStudySpec,PolicyInputSpec,PolicyApplicationSpec,
                               PolicyMetricSpec,PolicyLimits,PolicySpec,FrozenPolicy, bounded_json)
from .policy_result import PolicyResult,LIMITATIONS
from .policy_store import prepared_policy
from .policy_optimization import search,frontier,evaluate_candidate,choose,all_metrics
from .policy_metrics import metric_result,public_stat,native_measurements
from .policy_runtime import Interpreter


def action_record(event,action):
    return {'event_key':event['event_key'],**action,
            'upstream_output_states':{run:v.get('state','missing') for run,v in event['inputs'].items()},
            'feature_states':{key:v['state'] for key,v in event.get('features',{}).items()},'region_states':event.get('regions',{})}


def arguments(spec,config=None,allowed_roots=None,cls=PolicyStudySpec):
    if isinstance(spec,dict):
        bounded_json(spec,maximum=128*1024**2)
        spec=cls.from_dict(spec)
    if not isinstance(spec,cls): raise EvaluationError('Typed policy specification required.','policy_contract')
    spec=copy.deepcopy(spec)
    config=EvaluationConfig.from_dict(config) if isinstance(config,dict) else copy.deepcopy(config or EvaluationConfig())
    if not isinstance(config,EvaluationConfig): raise EvaluationError('Typed evaluation configuration required.')
    inp=spec.input
    if inp.evaluation:
        evaluation=replace(inp.evaluation,sources=tuple(replace(s,path=str(Path(s.path).absolute())) for s in inp.evaluation.sources))
        inp=replace(inp,evaluation=evaluation)
        default=[str(Path(s.path).parent) for s in evaluation.sources]
    else:
        inp=replace(inp,history={**inp.history,'workspace_path':str(Path(inp.history['workspace_path']).absolute())})
        if inp.history['selection'].get('catalog_sequence') is None:
            from .history_storage import Catalog
            selection={**inp.history['selection'],'catalog_sequence':Catalog(inp.history['workspace_path']).status()['catalog_sequence']}
            inp=replace(inp,history={**inp.history,'selection':selection})
        default=[inp.history['workspace_path']]
    spec=replace(spec,input=inp)
    if allowed_roots is not None and not allowed_roots: raise EvaluationError('Explicit authorized roots cannot be empty.','roots_required')
    roots=tuple(str(Path(p).absolute()) for p in (allowed_roots if allowed_roots is not None else default))
    return spec,config,roots


def workspace_for(inp,workspace=None):
    if inp.history:
        from .workspace import ReliabilityWorkspace
        declared=Path(inp.history['workspace_path']).resolve()
        if workspace is None: workspace=ReliabilityWorkspace(declared)
        if Path(workspace.path).resolve()!=declared: raise EvaluationError('Use the evidence source workspace.','workspace_identity')
    return workspace


def _identity_worker(inp,config,limits,roots,role,phase,*,progress=None):
    with prepared_policy(inp,config,limits,roots,progress,phase=phase) as p:
        population=p.identifiers(p.anchor,role)
        population['population_digest']=digest({'planned_keys':population['population_digest'],'input_fingerprint':p.fingerprint,'role':role})
        checks={'upstream_membership':getattr(p.store,'policy_prior_membership',{}),
                'known_outcome_features':sorted(p.known_outcome_features),
                'history_known_exposed':bool(p.history and set(p.history.get('known_exposed_events',[]))) if role=='E' else False}
        if p.history and role=='E':
            table=p.store.run_tables[p.anchor]
            keys={r[0] for r in p.con.execute(f"SELECT event_key FROM {table} WHERE cg_role='E'").fetchall()}
            checks['history_known_exposed']=bool(keys.intersection(p.history.get('known_exposed_events',[])))
        p.verify()
        return Inspection({'fingerprint':p.fingerprint,'population':population,'checks':checks,
                           'task':p.task.to_dict(),'anchor_run':p.anchor,
                           'history_binding':p.history,'files':p.files},
                          {'status':'completed','peak_workspace_bytes':p.work.peak})


def _reserve(kind,population,inp,workspace,config,*,family=None,request_id=None,protocol=None,metadata=None,cancel=None,deadline=None):
    from .evidence_use import EvidenceUseLedger,record_session
    metadata={'purpose':'policy_'+kind,**(metadata or {})}
    if workspace is not None and EvidenceUseLedger(workspace).status()['enabled']:
        return EvidenceUseLedger(workspace).record(kind,events=population['events'],units=population['units'],
            population_digest=population['population_digest'],family_digest=family,request_id=request_id,
            study_id=protocol.study_id if protocol else None,alpha=float(protocol.batch_alpha) if protocol else None,
            total_alpha=float(protocol.study_alpha) if protocol else None,metadata=metadata,cancel=cancel,deadline=deadline,
            query_events=population.get('query_events',population['events']),
            session_max_bytes=config.max_rss_bytes//8)
    record_session(kind,population['events'],population['units'],family=family,population=population['population_digest'],
                   workspace=workspace,max_bytes=config.max_rss_bytes//8,metadata=metadata)
    return {'kind':'session_and_external_declarations','cross_session_history_verified':False}


def _finish(result,config):
    result.seal()
    if len(result.json_text().encode())>config.private_bytes: raise EvaluationError('Protected policy result exceeds its byte budget.','private_result_limit')
    if len(json.dumps(result.to_dict()).encode())>config.result_bytes: raise EvaluationError('Portable policy result exceeds its byte budget.','result_limit')
    return result


def make_result(study,config,pstore,panel,policies,*,measurements=(),populations=(),locators=None,private_extra=None):
    aid=uuid.uuid4().hex; role='S' if pstore.phase=='selection' else 'E'
    runs=[]; measured=list(measurements); ledger=list(populations)
    primary=(panel.get('nomination') or {}).get('policy_digest')
    visible=[primary] if primary else list(policies)[:pstore.limits.assessment_policies]
    panel['behavior']={key:policies[key] for key in visible}
    panel['evaluation_economics']={'costs':study.evaluation_costs,'known_charges':study.charges,
                                   'metric_definitions':[m.to_dict() for m in all_metrics(study).values()]}
    panel['baselines']=[{'policy_digest':r['policy_digest'],'comparison_role':r.get('comparison_role','declared_incumbent_or_baseline')} for r in panel.get('candidates',[]) if r.get('baseline')]
    for policy_digest,definition in policies.items():
        policy=PolicySpec.from_dict(definition); rid='policy_'+policy_digest[:16]
        runs.append({'id':rid,'display_name':rid,'version_alias':'Frozen policy','model':pstore.runs[policy.run].model.to_dict(),
                     'role':'selection' if role=='S' else 'evaluation','decision_provenance':{'origin':'simulated','rule':'typed_policy','policy_digest':policy_digest},
                     'representations':{'hard_prediction':policy.task.kind!='regression','probabilities':False,'scores':False,'intervals':0}})
    for candidate in panel.get('candidates',[]):
        rid='policy_'+candidate['policy_digest'][:16]
        for key,stat in candidate['metrics'].items():
            population={'id':'pop_'+digest([pstore.fingerprint,candidate['policy_digest'],stat.get('definition_digest',key),role,stat['denominator']])[:32],
                        'run':rid,'scope':key,'denominator':stat['denominator'],'denominator_kind':'evaluation_support' if stat.get('statistic_kind')=='class_summary' else 'eligible_records',
                        'lineage':{'input_fingerprint':pstore.fingerprint,'policy_digest':candidate['policy_digest'],'role':role,'metric_definition':stat.get('definition_digest')},
                        'definition':'Registered policy metric eligibility; planned opportunities are never silently dropped.'}
            ledger.append(population)
            measured.append({'id':'policy_m'+str(len(measured)+1),'run':rid,'scope':key,'family':'policy','metric':stat['metric'],
                             'population_id':population['id'],'denominator':stat['denominator'],'denominator_kind':population['denominator_kind'],
                             'value':stat['value'],'value_state':stat['value_state'],'basis':'simulated','evidence_basis':stat['basis'],
                             'units':stat['units'],'interpretation':'descriptive','applicability':'applicable' if stat['value_state']!='undefined' else 'blocked',
                             'execution':'completed','reason':stat.get('reason'),'sensitive_counts':stat.get('sensitive_counts',[]),'data':stat,'evidence_refs':[]})
    data={'schema_version':RESULT,'methodology_id':METHOD,'analysis_id':aid,'generated_at':datetime.now(timezone.utc).isoformat(),
          'name':study.name,'task':pstore.task.to_dict(),'runs':runs,'outcomes':{**pstore.store.outcome_facts,'scope':'observed_labels'},
          'comparison':None,'measurements':measured,'checks':[],'findings':[],
          'coverage':{'population_provenance_version':'cg5_population_v1','populations':ledger,'limitations':LIMITATIONS,
                      'accounting':pstore.budget.to_dict(),'input_fingerprint':pstore.fingerprint},'policy':panel}
    private={'schema':'confidenceguard.policy_private/1.0','analysis_id':aid,'study':study.to_dict(),'config':config.to_dict(),
             'spec':pstore.input.evaluation.to_dict() if pstore.input.evaluation else None,
             'files':pstore.files,'policies':policies,'locators':locators or {},'history_binding':pstore.history,
             'workspace_path':pstore.history['workspace_path'] if pstore.history else None,**(private_extra or {})}
    execution={'status':'completed','backend':'duckdb_local','peak_workspace_bytes':pstore.work.peak,'accounting':pstore.budget.to_dict(),
               'publication_policy':'whole_evaluation_atomic','resource_qualification':'Sampled supervision and explicit algorithm counters; no hard capacity guarantee.'}
    return PolicyResult(data,private,execution)


def _inspect_worker(study,config,roots,*,progress=None):
    from .policy_solver import availability
    from .policy_metrics import registered
    with prepared_policy(study.input,config,study.limits,roots,progress) as p:
        for m in all_metrics(study).values(): registered(m,p.task)
        for policy in (*study.candidates,*study.baselines):p.bind_policy(policy)
        from .policy_problem import admit
        from .policy_optimization import family_guidance
        guidance=family_guidance(study,admit(p,study))
        data={'schema_version':'confidenceguard.policy_inspection/1.0','fingerprint':p.fingerprint,
              'task':p.task.to_dict(),'planned_development':p.count(p.anchor,'S'),
              'supported_action_inputs':{run:{'probabilities':r.probabilities is not None,'class_scores':bool(r.score and r.score.columns),
                  'native_score':bool(r.score and r.score.meaning=='event_ranking'),'supplied_action':bool(r.prediction or r.decision.column),
                  'explicit_selector':bool(r.selection or r.score and r.score.meaning=='selection'),
                  'distribution':p.store.representations[run].to_dict() if run in getattr(p.store,'representations',{}) else None} for run,r in p.runs.items()},
              'assessment_values_disclosed':False,'effective_spec':study.to_dict(),'effective_config':config.to_dict(),
              'solver':availability(),'backend_admission':guidance,'effective_policy_limits':study.limits.to_dict(),
              'admission_scope':'S-only domains and encoding preflight; no solver execution or E-dependent summaries.',
              'limitations':LIMITATIONS}
        p.verify(); return Inspection(data,{'status':'completed','peak_workspace_bytes':p.work.peak})


def inspect_policy_study(spec,config=None,*,allowed_roots=None,progress=None,cancel=None):
    spec,config,roots=arguments(spec,config,allowed_roots)
    return compat.supervise(_inspect_worker,(spec,config,roots),config,progress=progress,cancel=cancel).to_dict()


def _optimize_worker(study,config,roots,expected,development,reservation,*,progress=None):
    with prepared_policy(study.input,config,study.limits,roots,progress) as p:
        if expected and p.fingerprint!=expected: raise EvaluationError('Policy input/configuration changed.','stale_confirmation')
        study=replace(study,candidates=tuple(p.bind_policy(v) for v in study.candidates),baselines=tuple(p.bind_policy(v) for v in study.baselines))
        if progress: progress({'stage':'policy_selection'})
        from .policy_problem import admit
        problem=admit(p,study)
        try: records,policies,searches,nomination,retention=search(study,problem)
        finally: p.budget.policy_store=p
        # Selection metrics are recomputed from the executable nominee. A prefix
        # accumulator or solver never overrides authoritative replay feasibility.
        audited=set()
        while nomination and nomination['policy_digest'] not in audited:
            definition=PolicySpec.from_dict(policies[nomination['policy_digest']])
            audited.add(definition.policy_digest)
            verified,_=evaluate_candidate(definition,study,p,count=False)
            original=next(r for r in records if r['policy_digest']==definition.policy_digest)
            original.update(metrics=verified['metrics'],constraints=verified['constraints'],observed_feasibility=verified['observed_feasibility'])
            nomination=choose(records,study)
        if nomination: nomination['tie_coverage']=retention['selection_tie_coverage']
        tradeoffs=frontier(records,study,p.budget)
        complete=all(s['search_coverage']=='complete' for s in searches)
        tradeoffs['standing']='complete_empirical_frontier' if complete and not retention['omitted_candidate_detail'] and tradeoffs['dominance_complete_for_retained_pool'] and not any(s['backend'] in {'milp','hybrid'} for s in searches) else 'sampled_tradeoff_set'
        selection_digest=digest({'study_design_digest':study.study_design_digest,'input_fingerprint':p.fingerprint,
                                 'records':records,'searches':searches,'nomination':nomination})
        panel={'stage':'selection','study_design_digest':study.study_design_digest,'selection_record_digest':selection_digest,
               'candidates':records,'searches':searches,'nomination':nomination,'frontier':tradeoffs,'retention':retention,
               'assessment_state':'not_assessed','reservation':reservation,
               'conclusion':'Observed-data policy selection only; independently supported feasibility and improvement require separate assessment.'}
        native=([],[],{}); profile={}; action_examples=[]
        if nomination:
            policy=PolicySpec.from_dict(policies[nomination['policy_digest']]); events,truth=p.materialize(policy.run,'S')
            actions,_=Interpreter(policy,p.budget).apply(events,batches=p.input.batches)
            from collections import Counter
            profile[policy.policy_digest]={'planned':len(events),'observed_outcomes':sum(bool(r.get('outcome_valid')) for r in truth),
                'action_counts':dict(Counter(a['state'] for a in actions)),
                'issued_observed_outcomes':sum(a['state']=='issued' and bool(r.get('outcome_valid')) for a,r in zip(actions,truth)),
                'cohorts':{cohort.id:dict(Counter(r.get('g'+str(i)) for r in truth)) for i,cohort in enumerate(p.store.spec.cohorts)}}
            native=native_measurements(p,policy,'S',actions)
            action_examples=[action_record(e,a) for e,a in zip(events[:config.max_details],actions[:config.max_details])]
        result=make_result(study,config,p,panel,policies,measurements=native[0],populations=native[1],locators=native[2],private_extra={'development_events':development['events'],
                           'development_units':development['units'],'selection_record_digest':selection_digest,
                           'development_population':development,'development_profile':profile,'nominee_action_examples':action_examples,
                           'nominee_action_examples_omitted':max(0,development['planned']-len(action_examples)) if nomination else 0,
                           'known_outcome_features':sorted(p.known_outcome_features)})
        p.verify(); return result


def optimize_policies(spec,config=None,*,allowed_roots=None,expected_fingerprint=None,workspace=None,request_id=None,progress=None,cancel=None,_deadline=None):
    spec,config,roots=arguments(spec,config,allowed_roots); workspace=workspace_for(spec.input,workspace)
    deadline=_deadline or time.monotonic()+config.max_seconds
    identity=compat.supervise(_identity_worker,(spec.input,config,spec.limits,roots,'S','selection'),config,progress=progress,cancel=cancel,deadline=deadline).to_dict()
    if expected_fingerprint and identity['fingerprint']!=expected_fingerprint: raise EvaluationError('Policy inspection is stale.','stale_confirmation')
    reservation=_reserve('discovery_selection',identity['population'],spec.input,workspace,config,request_id=request_id,cancel=cancel,deadline=deadline)
    worker=replace(config,result_bytes=config.private_bytes+config.result_bytes)
    result=compat.supervise(_optimize_worker,(spec,config,roots,identity['fingerprint'],identity['population'],reservation),worker,progress=progress,cancel=cancel,deadline=deadline)
    if cancel is not None and cancel.is_set(): raise EvaluationError('Cancelled before policy commit.','cancelled')
    return _finish(result,config)


def _application_study(spec):
    metrics=spec.metrics or (PolicyMetricSpec('issued_coverage','issued_coverage',direction='maximize',basis='operational'),)
    return PolicyStudySpec(spec.input,metrics,candidates=(spec.policy,),constraints=spec.constraints,evaluation_costs=spec.evaluation_costs,charges=spec.charges,limits=spec.limits,name=spec.name)


def _replay_worker(application,study,config,roots,expected,reservation,*,progress=None):
    with prepared_policy(application.input,config,application.limits,roots,progress,phase='replay') as p:
        if expected and p.fingerprint!=expected: raise EvaluationError('Policy replay inspection changed.','stale_confirmation')
        application=replace(application,policy=p.bind_policy(application.policy)); study=replace(study,candidates=(application.policy,))
        p.project((application.policy,))
        events,records=p.materialize(application.policy.run,application.role)
        outputs,trace=Interpreter(application.policy,p.budget).apply(events,batches=application.input.batches)
        values={m.id:public_stat(metric_result(m,events,records,outputs,application.policy,study,p.budget)) for m in all_metrics(study).values()}
        from .policy_metrics import constraint_state
        constraints=[constraint_state(c,values[c.metric.id]) for c in study.constraints]
        state='not_requested' if not constraints else 'undefined' if any(c['state']=='undefined' for c in constraints) or any(not c['complete'] for c in trace['capacity']) else 'feasible' if all(c['state']=='feasible' for c in constraints) else 'violated'
        row={'policy_digest':application.policy.policy_digest,'metrics':values,'constraints':constraints,'observed_feasibility':state,'baseline':False,'trace':trace}
        panel={'stage':'replay','candidates':[row],'reservation':reservation,'assessment_state':'applied_unvalidated',
               'application_state':'capacity_unavailable' if any(not c['complete'] for c in trace['capacity']) else 'completed',
               'application_digest':digest([application.policy.policy_digest,p.fingerprint,application.role]),
               'action_counts':dict(__import__('collections').Counter(a['state'] for a in outputs))}
        native=native_measurements(p,application.policy,application.role,outputs)
        result=make_result(study,config,p,panel,{application.policy.policy_digest:application.policy.to_dict()},measurements=native[0],populations=native[1],locators=native[2])
        result.private['action_ledger']=[action_record(e,a) for e,a in zip(events,outputs)]
        p.verify(); return result


def replay_policy(spec,config=None,*,allowed_roots=None,expected_fingerprint=None,workspace=None,request_id=None,progress=None,cancel=None,_deadline=None):
    spec,config,roots=arguments(spec,config,allowed_roots,PolicyApplicationSpec); study=_application_study(spec)
    workspace=workspace_for(spec.input,workspace); deadline=_deadline or time.monotonic()+config.max_seconds
    identity=compat.supervise(_identity_worker,(spec.input,config,spec.limits,roots,spec.role,'replay'),config,progress=progress,cancel=cancel,deadline=deadline).to_dict()
    if expected_fingerprint and identity['fingerprint']!=expected_fingerprint: raise EvaluationError('Policy replay inspection is stale.','stale_confirmation')
    reservation=_reserve('outcome_disclosure',identity['population'],spec.input,workspace,config,request_id=request_id,cancel=cancel,deadline=deadline,
                         metadata={'purpose':'policy_replay','identity_policy':'canonical_and_original_source_aliases_v1','local_identity_scope':identity['population']['identity_scope']})
    result=compat.supervise(_replay_worker,(spec,study,config,roots,identity['fingerprint'],reservation),replace(config,result_bytes=config.private_bytes+config.result_bytes),progress=progress,cancel=cancel,deadline=deadline)
    return _finish(result,config)


def export_frozen_policy(result,policy_digest):
    PolicyResult.from_dict(result.to_private_dict(),private=result.private)
    if policy_digest not in result.private['policies']: raise EvaluationError('Policy is not retained.','policy_unavailable')
    packet={'schema_version':'confidenceguard.frozen_policy/1.0','policy':result.private['policies'][policy_digest],
            'policy_digest':policy_digest,'provenance':{'selection_record_digest':result.private.get('selection_record_digest'),
                'development_events':result.private.get('development_events',[]),'development_units':result.private.get('development_units',[]),
                'membership_available':bool(result.private.get('development_population'))}}
    packet['content_digest']=digest(packet); return FrozenPolicy(packet)
