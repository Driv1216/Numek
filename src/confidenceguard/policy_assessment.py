"""Development-only planning, frozen families and independently reserved finite claims."""
from dataclasses import replace
from decimal import Decimal,ROUND_CEILING
import copy
import math
import time
from types import SimpleNamespace

from . import compat
from .contracts import EvaluationError,EvaluationConfig,digest
from .result import Inspection
from .policy_contracts import (PolicyStudySpec,PolicyInputSpec,PolicySpec,PolicyClaim,PolicyMetricSpec,
                               PolicyAssessmentSpec,FrozenPolicyFamily,required_constraint_coverage,required_constraint_claims)
from .policy_result import PolicyResult
from .policy_store import prepared_policy
from .policy_runtime import Interpreter
from .policy_metrics import metric_result,public_stat,RATES,F1,FORMAL_UNSUPPORTED,bernoulli_contribution,claim_parameters
from .policies import arguments,workspace_for,_identity_worker,_reserve,_finish,make_result


def freeze_policy_family(result,policy_digests=None,*,assessment=None,assessment_preview=None):
    PolicyResult.from_dict(result.to_private_dict(),private=result.private)
    if result.data['policy']['stage']!='selection': raise EvaluationError('Freeze policies from a completed development selection.','policy_freeze_stage')
    nominee=result.data['policy'].get('nomination')
    selected=list(policy_digests or ([nominee['policy_digest']] if nominee else []))
    study=PolicyStudySpec.from_dict(result.private['study'])
    if not selected or len(set(selected))!=len(selected) or set(selected)-result.private['policies'].keys(): raise EvaluationError('Select distinct retained policies.','policy_unavailable')
    if assessment is None:
        claims=[PolicyClaim('constraint:'+policy+':'+c.id,policy,c.metric,c.operator,c.bound,minimum_support=c.minimum_support) for policy in selected for c in study.constraints]
        if not claims: raise EvaluationError('Declare meaningful claim bounds/material thresholds before freezing.','policy_claims_required')
        protocol=PolicyAssessmentSpec(tuple(claims))
    else: protocol=PolicyAssessmentSpec.from_dict(assessment) if isinstance(assessment,dict) else assessment
    if not isinstance(protocol,PolicyAssessmentSpec): raise EvaluationError('Typed policy assessment required.')
    if assessment_preview is not None:
        if not isinstance(assessment_preview,dict) or assessment_preview.get('selection_record_digest')!=result.private['selection_record_digest'] or assessment_preview.get('protocol_digest')!=digest(protocol.to_dict()) or assessment_preview.get('preview_digest')!=digest({k:v for k,v in assessment_preview.items() if k!='preview_digest'}) or assessment_preview.get('assessment_values_accessed') is not False or assessment_preview.get('alpha_spent') is not False:
            raise EvaluationError('Assessment preview differs from the selected development record and protocol.','policy_preview_binding')
    needed=set(selected)|{c.comparator for c in protocol.claims if c.comparator}
    if needed-result.private['policies'].keys(): raise EvaluationError('Claim comparator is not retained.','policy_unavailable')
    if any(c.policy_digest not in selected for c in protocol.claims): raise EvaluationError('Claims reference a non-nominated policy.')
    covered=required_constraint_coverage(study,protocol,selected)
    imported=[packet['provenance'] for packet in study.imported_policies if packet['policy_digest'] in needed]
    packet={'schema_version':'confidenceguard.frozen_policy_family/1.0',
            'policies':[result.private['policies'][p] for p in sorted(needed)],'protocol':protocol.to_dict(),'study':study.to_dict(),
            'selection_record_digest':result.private['selection_record_digest'],
            'development_events':sorted(set(result.private['development_events']).union(*(set(p.get('development_events',[])) for p in imported))),
            'development_units':sorted(set(result.private['development_units']).union(*(set(p.get('development_units',[])) for p in imported))),
            'provenance':{'origin_analysis_id':result.data['analysis_id'],'origin_analysis_digest':result.binding['analysis_digest'],
                          'required_constraints_covered':covered,'nominated':selected,
                          'imported_membership_available':all(p.get('membership_available') is True for p in imported),
                          'assessment_plan_preview':copy.deepcopy(assessment_preview),
                          'development_population':result.private.get('development_population'),
                          'history_binding':result.private.get('history_binding')}}
    packet['assessment_family_digest']=digest(packet); packet['content_digest']=digest(packet)
    return FrozenPolicyFamily(packet)


def claim_alpha(protocol,claim):
    return float(Decimal(str(protocol.batch_alpha))*(Decimal(str(claim.weight)) if claim.weight is not None else Decimal(1)/len(protocol.claims)))


def component_count(metric,classes,study=None):
    if metric.scope=='worst_windows':
        windows=(study.input.history or {}).get('selection',{}).get('windows',[]) if study else []
        return max(1,len(windows))*component_count(replace(metric,scope='overall'),classes)
    if metric.metric.startswith('selective_partial_'): return 2
    if metric.metric in F1: return 4
    if metric.metric in {'balanced_accuracy','macro_f1_fixed'}: return len(classes)*(1 if metric.metric=='balanced_accuracy' else 4)
    return 1


def metric_bounds(metric,study,policy):
    if metric.bounds: return tuple(metric.bounds)
    if metric.metric in RATES|F1|{'balanced_accuracy','macro_f1_fixed','interval_coverage','roc_auc','average_precision'}: return (0.,1.)
    if metric.metric=='brier': return (0.,1. if policy.task.kind=='binary_classification' else 2.)
    table=study.evaluation_costs.get(metric.cost) if metric.cost else None
    if table and table.get('kind')!='numeric_loss':
        numbers=[float(v) for row in table.values() for v in row.values()]
        lo,hi=min(numbers),max(numbers)
        if metric.metric=='utility': lo,hi=-hi,-lo
        if metric.basis=='model_implied' or metric.metric=='model_implied_cost':
            # Accepted supplied probabilities may sum within CG1's tolerance.
            # A conservative expansion does not silently renormalize them.
            radius=max(abs(lo),abs(hi))*1e-3
            lo-=radius; hi+=radius
        if lo==hi: hi=math.nextafter(hi,math.inf); lo=math.nextafter(lo,-math.inf)
        return (lo,hi)
    if metric.metric in {'operational_charge','resource_mean'} or metric.basis=='operational':
        actions=[n['action'] for n in policy.nodes.values() if n['kind']=='action']+[policy.fallback,policy.unavailable]
        resources=[float(a.get('resource',1.)) for a in actions if a['kind']=='defer']+[0.]
        upper=max(resources) if metric.metric=='resource_mean' else max([float(v) for v in study.charges.values()]+[0.])*(1+max(resources))
        return (0.,upper) if upper>0 else (0.,math.nextafter(0.,math.inf))
    return None


def method_refusal(metric,protocol,study,policy):
    if protocol.sampling=='descriptive': return 'descriptive_only'
    if protocol.sampling not in {'independent_rows','independent_entity_arms'}: return 'sampling_design_not_registered'
    if protocol.known_common_shocks: return 'known_common_shocks'
    if metric.metric in FORMAL_UNSUPPORTED: return 'native_nonadditive_or_total_interval_not_registered'
    if any(n['kind']=='capacity' for n in policy.nodes.values()): return 'batch_coupling_has_no_iid_event_risk_claim'
    if metric_bounds(metric,study,policy) is None: return 'finite_inference_requires_true_predeclared_bounds'
    if bernoulli_contribution(metric,policy.task) or metric.metric in F1|{'balanced_accuracy','macro_f1_fixed'}:
        import importlib.util
        if importlib.util.find_spec('scipy') is None: return 'statistics_dependency_unavailable'
    return None


def _protocol_input_signature(inp):
    evaluation=inp.evaluation
    population={'roles':inp.roles.to_dict(),'batches':copy.deepcopy(inp.batches),
                'run_bindings':copy.deepcopy(inp.run_bindings),'as_of':inp.as_of}
    if evaluation:
        outcome=evaluation.effective_outcomes
        binding={k:v for k,v in outcome.to_dict().items() if k not in {'source','snapshot_name'}} if outcome else None
        return {'kind':'supplied','population':population,'task':evaluation.task.to_dict(),'observation':binding,
                'outcome_as_of':evaluation.as_of,
                'event_bindings':{r.id:{'key_columns':r.key_columns,'entity_columns':r.entity_columns} for r in evaluation.runs},
                'cohorts':[c.to_dict() for c in evaluation.cohorts],
                'context':evaluation.context.to_dict() if evaluation.context else None,
                'feature_time_view':inp.feature_time_view,'features':[v.to_dict() for v in inp.features],
                'methods':[v['artifact_digest'] for v in inp.fitted_methods],
                'regions':[r['artifact']['artifact_digest'] for r in inp.regions]}
    selection=copy.deepcopy(inp.history['selection'])
    selection['prediction_catalog_sequence']=selection.get('prediction_catalog_sequence') or selection.get('catalog_sequence')
    selection['prediction_as_of']=selection.get('prediction_as_of') or selection.get('as_of')
    for key in ('catalog_sequence','as_of','config','name','outcome_only'): selection.pop(key,None)
    return {'kind':'retained','population':population,'selection':selection,'features':[v.to_dict() for v in inp.features],
            'feature_time_view':inp.feature_time_view}


def _input(frozen,assessment_input):
    frozen=FrozenPolicyFamily.from_dict(frozen) if isinstance(frozen,dict) else frozen
    if not isinstance(frozen,FrozenPolicyFamily): raise EvaluationError('Frozen policy family required.')
    study=PolicyStudySpec.from_dict(frozen.data['study'])
    if assessment_input is not None:
        inp=PolicyInputSpec.from_dict(assessment_input) if isinstance(assessment_input,dict) else assessment_input
        if _protocol_input_signature(inp)!=_protocol_input_signature(study.input): raise EvaluationError('Assessment changed frozen observation/input semantics.','policy_assessment_semantics')
        study=replace(study,input=inp)
    return frozen,study,PolicyAssessmentSpec.from_dict(frozen.data['protocol'])


def preview_policy_assessment(result,assessment,*,planned_e_size,requested_half_width=None):
    """Pure completed-S evidence operation: no input/source/E accessor exists."""
    PolicyResult.from_dict(result.to_private_dict(),private=result.private)
    if type(planned_e_size) is not int or planned_e_size<1: raise EvaluationError('Declare a positive planned E size.')
    if requested_half_width is not None and (isinstance(requested_half_width,bool) or not isinstance(requested_half_width,(int,float)) or not math.isfinite(requested_half_width) or requested_half_width<=0): raise EvaluationError('Precision half-width must be positive and finite.')
    protocol=PolicyAssessmentSpec.from_dict(assessment) if isinstance(assessment,dict) else assessment
    if not isinstance(protocol,PolicyAssessmentSpec): raise EvaluationError('Assessment protocol required.')
    study=PolicyStudySpec.from_dict(result.private['study']); candidates={c['policy_digest']:c for c in result.data['policy'].get('candidates',[])}
    previews=[]
    for claim in protocol.claims:
        candidate=candidates.get(claim.policy_digest)
        if candidate is None: raise EvaluationError('Preview policies must be retained development candidates.')
        # JSON consumers may round-trip 1.0 as 1. Compare validated metric
        # semantics against the frozen S design, without replay or E access.
        definitions={m.id:m for m in (*study.objectives,*(c.metric for c in study.constraints))}
        matching=next((v for key,v in candidate['metrics'].items() if v.get('definition_digest')==digest(claim.metric.to_dict()) or definitions.get(key)==claim.metric),None)
        policy=PolicySpec.from_dict(result.private['policies'][claim.policy_digest]); count=component_count(claim.metric,policy.task.classes,study)*(2 if claim.comparator else 1)
        alpha=claim_alpha(protocol,claim); bounds=metric_bounds(claim.metric,study,policy)
        planned=result.private['development_population']['planned']
        n=max(0,int(planned_e_size*matching['denominator']/planned)) if matching and planned else None
        entry={'claim_id':claim.id,'components':count,'allocated_alpha':alpha,'scenario_conditional_support':n,
               'development_support':matching['denominator'] if matching else None,
               'development_profile':result.private.get('development_profile',{}).get(claim.policy_digest),
               'status':'scenario_only' if matching else 'development_metric_not_retained',
               'method_refusal':method_refusal(claim.metric,protocol,study,policy)}
        if n and bounds:
            radius=(bounds[1]-bounds[0])*math.sqrt(math.log(2*count/alpha)/(2*n))
            entry.update(hoeffding_component_half_width=radius)
            if requested_half_width is not None: entry.update(requested_half_width=requested_half_width,required_conditional_sample_size=math.ceil((bounds[1]-bounds[0])**2*math.log(2*count/alpha)/(2*requested_half_width**2)))
            if claim.metric.metric in RATES and matching['value_state']=='finite':
                successes=min(n,max(0,round(matching['value']*n)))
                try:
                    from scipy.stats import binomtest
                    interval=binomtest(successes,n).proportion_ci(confidence_level=1-alpha/count,method='exact')
                    entry['illustrative_CP_interval']={'lower':float(interval.low),'upper':float(interval.high),'scenario_successes':successes}
                except ImportError: entry['illustrative_CP_unavailable']='optional_statistics_dependency_unavailable'
        previews.append(entry)
    data={'schema_version':'confidenceguard.assessment_plan_preview/1.0','selection_record_digest':result.private['selection_record_digest'],
          'protocol_digest':digest(protocol.to_dict()),'planned_e_size':planned_e_size,'claim_count':len(protocol.claims),
          'component_count':sum(p['components'] for p in previews),'claims':previews,'assessment_values_accessed':False,
          'alpha_spent':False,'limitations':['Development-selected rates can be optimistic; scenarios are not passing probabilities or guarantees.',
                                          'Future mix, label maturity, dependence and shift can invalidate projected support.',
                                          'Omitted required constraints cannot support independent feasibility.']}
    data['preview_digest']=digest(data); return data


def inspect_policy_assessment(frozen,config=None,*,assessment_input=None,allowed_roots=None,workspace=None,progress=None,cancel=None,_protected=False,_deadline=None,_scheduled=None):
    frozen,study,protocol=_input(frozen,assessment_input); study,config,roots=arguments(study,config,allowed_roots)
    workspace=workspace_for(study.input,workspace)
    identity=compat.supervise(_identity_worker,(study.input,config,study.limits,roots,'E','identity'),config,progress=progress,cancel=cancel,deadline=_deadline).to_dict()
    population=identity['population']; reasons=[]
    if frozen.data['provenance'].get('imported_membership_available') is False: reasons.append('imported_policy_development_membership_unavailable')
    if set(population['events']).intersection(frozen.data['development_events']) or set(population['units']).intersection(frozen.data['development_units']): reasons.append('observable_development_assessment_overlap')
    if protocol.upstream_independence!='declared_independent': reasons.append('upstream_independence_not_established')
    if protocol.external_exposure!='declared_unexposed': reasons.append('external_exposure_not_established')
    if study.input.feature_time_view!='available_at_decision': reasons.append('retrospective_policy_inputs')
    if identity['checks']['known_outcome_features']: reasons.append('known_outcome_derived_policy_context')
    if identity['checks']['history_known_exposed']: reasons.append('retained_assessment_outcomes_previously_exposed')
    if any(v.get('status')!='passed' for v in identity['checks']['upstream_membership'].values()): reasons.append('upstream_membership_unavailable_or_contradicted')
    for region in study.input.regions:
        provenance=region['provenance']
        from .features import FEATURE_TIME_POLICY
        if provenance['feature_time_policy']!=FEATURE_TIME_POLICY: reasons.append('region_information_cutoff_semantics_unqualified')
        if region['artifact']['features'] and not region.get('feature_contracts') or region['artifact'].get('representation') and not region.get('representation_contract'): reasons.append('region_input_contract_provenance_unavailable')
        if provenance['independence']!='declared_independent': reasons.append('region_development_provenance_unavailable')
        if set(population['events']).intersection(provenance['development_events']) or set(population['units']).intersection(provenance['development_units']): reasons.append('region_development_assessment_overlap')
    from .evidence_use import session_overlap,EvidenceUseLedger,session_replay_history_incomplete
    if not _scheduled and session_replay_history_incomplete(): reasons.append('session_replay_exposure_history_incomplete')
    # CG5 does not grant the investigation ledger's same-family recomputation
    # exception: outcome restatements require a frozen scheduled look.
    if session_overlap(population.get('query_events',population['events']),population['units']): reasons.append('assessment_population_previously_exposed')
    continuity=EvidenceUseLedger(workspace).status() if workspace else None
    if continuity and continuity['enabled']:
        overlap=EvidenceUseLedger(workspace).overlap(population.get('query_events',population['events']),population['units'])
        if protocol.exposure_history_token==continuity.get('continuity_token') and protocol.external_exposure=='declared_unexposed':
            overlap=[r for r in overlap if r not in {'exposure_history_unavailable','exposure_history_incomplete'}]
        reasons.extend(overlap)
    policies={p.policy_digest:p for p in (PolicySpec.from_dict(v) for v in frozen.data['policies'])}
    claims=[]; components=0
    for claim in protocol.claims:
        policy=policies[claim.policy_digest]
        count=component_count(claim.metric,policy.task.classes,study)*(2 if claim.comparator else 1); components+=count
        claims.append({'id':claim.id,'method_refusal':method_refusal(claim.metric,protocol,study,policy),
                       'components':count,'allocated_alpha':claim_alpha(protocol,claim)})
    if components>study.limits.assessment_components: reasons.append('assessment_component_limit')
    if _scheduled:
        if digest({'events':population['events'],'units':population['units']})!=_scheduled['membership_digest']:
            raise EvaluationError('Scheduled look changed its planned population.','scheduled_restatement_provenance')
        reasons=[r for r in reasons if r not in {'assessment_population_previously_exposed','previously_exposed_confirmation_population'}]
        claims=[{**c,'allocated_alpha':c['allocated_alpha']*float(_scheduled['look']['alpha'])/float(protocol.batch_alpha)} for c in claims]
    data={'schema_version':'confidenceguard.policy_assessment_inspection/1.0','assessment_family_digest':frozen.family_digest,
          'fingerprint':digest([frozen.family_digest,identity['fingerprint'],population['population_digest']]),
          'assessment_values_disclosed':False,'resource_admission':'within_declared_source_and_role_limits','claims':claims,
          'family_size':len(protocol.claims),'elementary_components':components,'admissibility_reasons':sorted(set(reasons)),
          'continuity':continuity,'local_identity_scope':population['identity_scope']}
    if _protected: data.update(_population=population,_input_fingerprint=identity['fingerprint'])
    return data


def _interval(stat,metric,study,policy,alpha):
    import numpy as np
    from .confirmation import binomial_interval,bounded_interval,f1_interval
    values=stat.get('_contributions',[])
    if stat['value_state']!='finite': return None,'contribution_bounds_violated' if stat['value_state'] in {'positive_infinity','negative_infinity'} and metric_bounds(metric,study,policy) else stat.get('reason') or 'undefined_statistic'
    if stat['statistic_kind']=='worst_window':
        intervals=[]
        for window,child in zip(stat['windows'],stat['children']):
            interval,reason=_interval(child,replace(metric,scope='window:'+window),study,policy,alpha/len(stat['children']))
            if interval is None: return None,reason
            intervals.append(interval)
        aggregate=max if metric.direction=='minimize' else min
        return (aggregate(i[0] for i in intervals),aggregate(i[1] for i in intervals)),None
    if stat['statistic_kind']=='class_summary':
        children=stat['children']; weights=stat['weights']; intervals=[]
        for child in children:
            interval,reason=_interval(child,replace(metric,metric=child['metric']),study,policy,alpha/len(children))
            if interval is None: return None,reason
            intervals.append(interval)
        return (sum(w*i[0] for w,i in zip(weights,intervals))/sum(weights),sum(w*i[1] for w,i in zip(weights,intervals))/sum(weights)),None
    if stat['statistic_kind']=='f1':
        objective=SimpleNamespace(direction='higher',comparator='ceiling',ceiling=0.)
        result=f1_interval([stat['cells']],objective,alpha)
        return (result['lower'],result['upper']),None
    bounds=metric_bounds(metric,study,policy)
    if not bounds: return None,'finite_inference_requires_true_bounds'
    if not values: return None,'zero_denominator'
    array=np.asarray(values,float)
    checked_bounds=(min(0.,bounds[0]),max(0.,bounds[1])) if stat['statistic_kind']=='envelope_ratio' else bounds
    if not np.isfinite(array).all() or min(values)<checked_bounds[0] or max(values)>checked_bounds[1]: return None,'contribution_bounds_violated'
    if stat['statistic_kind']=='envelope_ratio':
        # Contributions include zero for rejected opportunities; both population
        # components are bounded simultaneously before taking their ratio.
        numerator=bounded_interval(array,(min(0.,bounds[0]),max(0.,bounds[1])),alpha/2)
        denominator=binomial_interval(np.asarray(stat['_acceptance']),alpha/2)
        if denominator[0]<=0: return None,'acceptance_denominator_not_bounded_away_from_zero'
        endpoints=[a/b for a in numerator for b in denominator]
        return (min(endpoints),max(endpoints)),None
    raw=binomial_interval(array,alpha) if bernoulli_contribution(metric,policy.task) else bounded_interval(array,bounds,alpha)
    if stat['statistic_kind']=='sqrt_mean': return tuple(math.sqrt(max(0.,v)) for v in raw),None
    if stat['statistic_kind']=='absolute_mean': return (0. if raw[0]<=0<=raw[1] else min(abs(v) for v in raw),max(abs(v) for v in raw)),None
    return raw,None


def _entity_refusal(events,records,metric,outputs,protocol):
    from .policy_metrics import scoped
    seen=set(); repeated=False
    for event,record in zip(events,records):
        if not scoped(metric,event,record): continue
        entity=event.get('entity_key')
        if entity is not None:
            repeated |= entity in seen; seen.add(entity)
        elif protocol.sampling=='independent_entity_arms': return 'entity_keys_required'
    if repeated: return 'multiple_potential_observations_per_entity_in_claim_arm'
    return None


def _assess_worker(frozen,study,protocol,config,roots,inspection,reservation,*,progress=None):
    from .platform_catalog import study_authority
    with study_authority(reservation),prepared_policy(study.input,config,study.limits,roots,progress,phase='assessment') as p:
        if p.fingerprint!=inspection['_input_fingerprint']: raise EvaluationError('Assessment snapshot changed after reservation.','stale_confirmation')
        definitions={q.policy_digest:q for q in (PolicySpec.from_dict(v) for v in frozen.data['policies'])}
        for definition in definitions.values(): p.bind_policy(definition)
        p.project(tuple(definitions.values()))
        rows=[]; candidates=[]; outputs={}; data={}; refusal=inspection['admissibility_reasons']
        allowed=(not refusal or protocol.sampling=='descriptive') and reservation.get('state')!='not_reserved_no_admitted_claims'
        if allowed:
            for key,policy in definitions.items():
                events,records=p.materialize(policy.run,'E')
                p.budget.reserve('assessment_actions:'+key,len(events)*512)
                actions,trace=Interpreter(policy,p.budget).apply(events,batches=p.input.batches)
                data[key]=(events,records); outputs[key]=actions
        metric_records={key:{} for key in definitions}
        claim_inspections={c['id']:c for c in inspection['claims']}
        for claim in protocol.claims:
            policy=definitions[claim.policy_digest]; alpha=claim_alpha(protocol,claim)
            row={'id':claim.id,'policy_digest':claim.policy_digest,'metric':claim.metric.metric,'operator':claim.operator,
                 'bound':claim.bound,'basis':claim.metric.basis,'scope':claim.metric.scope,'state':'unsupported',
                 'comparator':claim.comparator,'direction':claim.metric.direction,'metric_definition':claim.metric.to_dict(),
                 'minimum_support':claim.minimum_support,
                 'family_size':len(protocol.claims),'allocated_alpha':alpha,'required':claim.required}
            row.update(claim_parameters(claim.metric,policy.task))
            reason=claim_inspections[claim.id]['method_refusal']
            if refusal and protocol.sampling!='descriptive': reason=refusal[0]
            if reason and reason!='descriptive_only':
                row.update(reason=reason,failure_class='insufficient_provenance_or_independence' if refusal else 'unsupported_method_or_design'); rows.append(row); continue
            events,records=data[claim.policy_digest]; actions=outputs[claim.policy_digest]
            stat=metric_result(claim.metric,events,records,actions,policy,study,p.budget,retain_components=True)
            metric_records[claim.policy_digest][claim.metric.id]=public_stat(stat)
            row.update(estimate=stat['value'],estimate_state=stat['value_state'],support=stat['denominator'],support_counts=stat.get('sensitive_counts',[]))
            if protocol.sampling=='descriptive': row.update(state='descriptive_only',reason='independent_support_not_requested'); rows.append(row); continue
            reason=_entity_refusal(events,records,claim.metric,actions,protocol)
            if stat['denominator']<claim.minimum_support: reason='insufficient_support'
            if reason: row.update(state='insufficient_support',reason=reason,failure_class='insufficient_support'); rows.append(row); continue
            interval,error=_interval(stat,claim.metric,study,policy,alpha/(2 if claim.comparator else 1))
            method='registered_finite_component_composition'
            if not claim.comparator and stat['statistic_kind'] in {'mean','sqrt_mean','absolute_mean'}:
                method='bernoulli_clopper_pearson' if bernoulli_contribution(claim.metric,policy.task) else {
                    'mean':'bounded_mean_hoeffding','sqrt_mean':'bounded_squared_mean_hoeffding_sqrt',
                    'absolute_mean':'bounded_signed_mean_hoeffding_absolute'}[stat['statistic_kind']]
            if interval and claim.comparator:
                comparator=definitions[claim.comparator]; other_events,other_records=data[claim.comparator]
                other=metric_result(claim.metric,other_events,other_records,outputs[claim.comparator],comparator,study,p.budget,retain_components=True)
                row['comparator_support']=other['denominator']
                metric_records[claim.comparator][claim.metric.id]=public_stat(other)
                comparison,error=_interval(other,claim.metric,study,comparator,alpha/2)
                structural=_entity_refusal(other_events,other_records,claim.metric,outputs[claim.comparator],protocol)
                if other['denominator']<claim.minimum_support or structural:
                    row.update(state='insufficient_support',reason=structural or 'insufficient_comparator_support'); rows.append(row); continue
                if comparison is None:
                    row.update(state='bound_violation' if error=='contribution_bounds_violated' else 'unsupported',reason=error,failure_class='bound_violation' if error=='contribution_bounds_violated' else 'unsupported_method_or_design'); rows.append(row); continue
                fixed_base=claim.metric.metric in {'issued_coverage','abstention_rate','deferral_rate','unavailable_rate','input_unavailable_rate','label_availability','correct_issue_rate','opportunity_recall','false_negative_rate','specificity','false_positive_rate','empirical_cost','utility','partial_lower','partial_upper','operational_charge','resource_mean'}
                if fixed_base and stat.get('_identities')==other.get('_identities') and stat['statistic_kind']=='mean' and other['statistic_kind']=='mean' and len(stat.get('_contributions',[]))==len(other.get('_contributions',[])):
                    import numpy as np
                    from .confirmation import bounded_interval
                    a,b=metric_bounds(claim.metric,study,policy),metric_bounds(claim.metric,study,comparator)
                    sign=1 if claim.metric.direction=='maximize' else -1
                    differences=np.asarray([(v-w)*sign for v,w in zip(stat['_contributions'],other['_contributions'])])
                    bounds=(a[0]-b[1],a[1]-b[0]) if sign==1 else (b[0]-a[1],b[1]-a[0])
                    interval=bounded_interval(differences,bounds,alpha); method='paired_bounded_difference_hoeffding'
                else:
                    if comparison:
                        interval=(interval[0]-comparison[1],interval[1]-comparison[0]) if claim.metric.direction=='maximize' else (comparison[0]-interval[1],comparison[1]-interval[0])
                    else: interval=None
                if stat['value_state']=='finite' and other['value_state']=='finite':
                    row['estimate']=(stat['value']-other['value'])*(1 if claim.metric.direction=='maximize' else -1)
            if interval is None:
                category='bound_violation' if error=='contribution_bounds_violated' else 'unavailable_required_output' if error=='unavailable_required_contribution' else 'insufficient_support' if error in {'undefined_class_summary','unavailable_window','zero_denominator','zero_formula_denominator','acceptance_denominator_not_bounded_away_from_zero'} else 'unsupported_method_or_design'
                row.update(state=category if category!='unsupported_method_or_design' else 'unsupported',failure_class=category,reason=error or 'interval_unavailable')
            else:
                lo,hi=interval
                state=('supported' if hi<=claim.bound else 'contradicted' if lo>claim.bound else 'inconclusive') if claim.operator=='le' else ('supported' if lo>claim.bound else 'contradicted' if hi<=claim.bound else 'inconclusive') if claim.operator=='improvement' else ('supported' if lo>=claim.bound else 'contradicted' if hi<claim.bound else 'inconclusive')
                row.update(state=state,lower=lo,upper=hi,method=method,strength='finite_sample_under_declared_assumptions',reason=None)
            rows.append(row)
        for key,metrics in metric_records.items():
            if metrics: candidates.append({'policy_digest':key,'metrics':metrics,'constraints':[],'baseline':False,'observed_feasibility':'assessment_evidence'})
        supported={}
        for key in frozen.data['provenance']['nominated']:
            required=[r for r in rows if r['policy_digest']==key and r['required']]
            by_id={r['id']:r for r in rows}
            covered=all(any(by_id[c.id]['state']=='supported' for c in required_constraint_claims(requirement,protocol,key)) for requirement in study.constraints)
            covered=covered and required_constraint_coverage(study,protocol,[key])[key]
            supported[key]='independently_supported_for_declared_claims' if covered and required and all(r['state']=='supported' for r in required) else 'not_established'
        panel={'stage':'assessment','assessment_family_digest':frozen.family_digest,'assessments':rows,'candidates':candidates,
               'assessment_plan_preview':frozen.data['provenance'].get('assessment_plan_preview'),
               'assessment_digest':digest({'family':frozen.family_digest,'E':p.fingerprint,'reservation':reservation,'claims':rows}),
               'policy_support':supported,'reservation':reservation,'inspection':{k:v for k,v in inspection.items() if not k.startswith('_')},
               'freshness_scope':'Observable event/entity non-overlap and declared external provenance; no global fork coordination.'}
        result=make_result(study,config,p,panel,{k:v.to_dict() for k,v in definitions.items()},private_extra={'frozen_family':frozen.to_dict(),
                  'assessment_population':inspection['_population'],'origin_analysis_id':frozen.data['provenance']['origin_analysis_id']})
        p.verify(); return result


def assess_policies(frozen,config=None,*,assessment_input=None,allowed_roots=None,expected_fingerprint=None,workspace=None,request_id=None,progress=None,cancel=None,_deadline=None,_scheduled=None):
    frozen,study,protocol=_input(frozen,assessment_input); study,config,roots=arguments(study,config,allowed_roots)
    workspace=workspace_for(study.input,workspace); deadline=_deadline or time.monotonic()+config.max_seconds
    inspection=inspect_policy_assessment(frozen,config,assessment_input=study.input,allowed_roots=roots,workspace=workspace,progress=progress,cancel=cancel,_protected=True,_deadline=deadline,_scheduled=_scheduled)
    if _scheduled: protocol=replace(protocol,batch_alpha=str(_scheduled['look']['alpha']),restatement_schedule=())
    if expected_fingerprint and inspection['fingerprint']!=expected_fingerprint: raise EvaluationError('Assessment inspection is stale.','stale_confirmation')
    reservation={'state':'not_reserved_no_admitted_claims'}
    admitted=not inspection['admissibility_reasons'] and any(not c['method_refusal'] for c in inspection['claims'])
    if admitted or protocol.sampling=='descriptive':
        reservation=_reserve('confirmation' if admitted else 'outcome_disclosure',inspection['_population'],study.input,workspace,config,
            family=frozen.family_digest,request_id=request_id,protocol=protocol if admitted else None,cancel=cancel,deadline=deadline,
            metadata={'purpose':'policy_assessment','external_exposure':protocol.external_exposure,
                      'declaration_author':protocol.declaration_author,'declaration_reason':protocol.declaration_reason,
                      'exposure_history_token':protocol.exposure_history_token,
                      'restatement_schedule':[s.to_dict() for s in protocol.restatement_schedule],
                      **({'initial_use_id':_scheduled['initial_use_id'],'look_id':_scheduled['look']['id'],'predeclared_look':_scheduled['look']} if _scheduled else {})})
    result=compat.supervise(_assess_worker,(frozen,study,protocol,config,roots,inspection,reservation),
                            replace(config,result_bytes=config.private_bytes+config.result_bytes),progress=progress,cancel=cancel,deadline=deadline)
    if cancel is not None and cancel.is_set(): raise EvaluationError('Assessment cancelled before commit.','cancelled')
    if _scheduled: result.data['policy']['predeclared_restatement']={**_scheduled,'fresh_independent_evidence':False}
    return _finish(result,config)


def _scheduled_context(prior,look_id,workspace):
    from .evidence_use import EvidenceUseLedger
    from .history_contracts import instant,now
    from .history_storage import Catalog
    if workspace is None or not isinstance(prior,PolicyResult) or prior.data['policy']['stage']!='assessment' or not prior.private.get('history_binding'):
        raise EvaluationError('Scheduled policy looks require a retained historical assessment and its workspace.','scheduled_restatement_provenance')
    if workspace.open(prior.data['analysis_id']).binding!=prior.binding: raise EvaluationError('Retained assessment differs.','scheduled_restatement_provenance')
    frozen=FrozenPolicyFamily.from_dict(prior.private['frozen_family']); protocol=PolicyAssessmentSpec.from_dict(frozen.data['protocol'])
    look=next((s for s in protocol.restatement_schedule if s.id==look_id),None)
    if look is None: raise EvaluationError('Look was not frozen before E.','unplanned_confirmation_look')
    if instant(look.as_of)>instant(now()): raise EvaluationError('Look is not due.','scheduled_look_not_due')
    state=EvidenceUseLedger(workspace).status()
    uses=EvidenceUseLedger(workspace).records()
    initial=next((u for u in uses if u['kind']=='confirmation' and u.get('family_digest')==frozen.family_digest and u.get('metadata',{}).get('look_id') is None),None)
    if not state['enabled'] or state['continuity'] in {'incomplete','restore_unreconciled'} or initial is None or initial['branch_id']!=state['branch_id'] or initial['metadata'].get('restatement_schedule')!=[s.to_dict() for s in protocol.restatement_schedule]:
        raise EvaluationError('Original schedule and uninterrupted reservation continuity are required.','scheduled_restatement_provenance')
    study=PolicyStudySpec.from_dict(prior.private['study']); history=copy.deepcopy(study.input.history); selection=history['selection']; binding=prior.private['history_binding']
    selection.update(prediction_catalog_sequence=selection.get('prediction_catalog_sequence') or binding['catalog_sequence'],prediction_as_of=selection.get('prediction_as_of') or selection.get('as_of'),catalog_sequence=Catalog(workspace.path).status()['catalog_sequence'],as_of=look.as_of,outcome_only=True)
    inp=replace(study.input,history=history)
    context={'look':look.to_dict(),'initial_use_id':initial['id'],'membership_digest':initial['membership_digest'],'origin_analysis_id':prior.data['analysis_id']}
    return frozen,inp,context


def inspect_policy_restatement(prior,look_id,config=None,*,workspace,**kwargs):
    frozen,inp,context=_scheduled_context(prior,look_id,workspace)
    return inspect_policy_assessment(frozen,config or prior.private['config'],assessment_input=inp,workspace=workspace,_scheduled=context,**kwargs)


def restate_policy_assessment(prior,look_id,config=None,*,workspace,**kwargs):
    frozen,inp,context=_scheduled_context(prior,look_id,workspace)
    return assess_policies(frozen,config or prior.private['config'],assessment_input=inp,workspace=workspace,_scheduled=context,**kwargs)
