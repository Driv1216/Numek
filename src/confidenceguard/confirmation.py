"""Frozen-family confirmation: explicit assumptions, allocation and refusal."""
from dataclasses import dataclass
from decimal import Decimal,ROUND_CEILING
import math
from types import SimpleNamespace
import numpy as np
from .contracts import EvaluationError
from .investigation_contracts import ConfirmationSpec


@dataclass(frozen=True)
class _NumericalExtension:
    origin_analysis_digest: str
    replicates: int


def _protocol(frozen,scheduled=None,numerical_extension=None):
    from dataclasses import replace
    protocol=ConfirmationSpec.from_dict(frozen.data['confirmation_spec'])
    if scheduled:protocol=replace(protocol,batch_alpha=scheduled['look']['alpha'],restatement_schedule=())
    if numerical_extension is not None:
        if not isinstance(numerical_extension,_NumericalExtension):raise EvaluationError('Protected numerical extension required.','numerical_retry_origin')
        protocol=replace(protocol,replicates=numerical_extension.replicates,max_replicates=max(protocol.max_replicates,numerical_extension.replicates),replicate_policy='fixed')
    return protocol


@dataclass(frozen=True)
class ConfirmationFeasibility:
    data: dict
    def to_dict(self):return dict(self.data)


def elementary_count(objective,method,bins=10):
    sides=1 if objective.comparator=='ceiling' else 2
    if method!='finite':return sides if objective.direction=='absolute' else 1
    return sides*(4 if objective.metric=='f1' else bins if objective.metric=='reliability_diagram' else 1)


def _method_refusal(objective,protocol):
    """Registration depends on frozen semantics, never observed H outcomes.

    Binding an adapter constructs its metric/eligibility expressions. It does
    not evaluate H. Keep support, observed bound violations and numerical
    degeneracy in assessment, where they genuinely require reserved H access.
    """
    proxy=objective.proxy.removeprefix('paired_metric_specific_proposal_difference:')
    if proxy=='point_loss_proxy_for_nonadditive_metric':return 'native_nonadditive_interval_not_registered'
    if protocol.method=='percentile' and objective.spec.metric not in {'roc_auc','average_precision'}:
        return 'percentile_confirmation_registered_for_ranking_only'
    if protocol.method=='percentile':
        # Retained one-family synthetic ranking panels do not qualify general
        # product populations or multiplicity-adjusted operating points.
        return 'general_ranking_percentile_confirmation_not_qualified'
    if protocol.method=='finite':
        if protocol.sampling not in {'independent_rows','independent_entity_arms'}:return 'finite_row_methods_do_not_correct_entity_dependence'
        if objective.spec.metric in {'f1','reliability_diagram'}:return None
        if objective.reducer=='ranking':return 'ranking_finite_method_not_registered'
        if not objective.binary and not objective.bounded:return 'finite_inference_requires_registered_bounded_contributions'
    return None


def _entity_arm_refusal(records,membership,objective,check=lambda *args:None):
    """Check potential observations, without reading any H outcome fields.

    The selected design asserts IID complete entities. This check verifies the
    admitted extract's arm structure only; it cannot establish that assertion.
    """
    seen=[set(),set()]
    for i,record in enumerate(records):
        if i%512==0:check('frozen entity arm structure')
        if not membership['available'][i]:continue
        entity=record.get('entity_key')
        if entity is None:return 'entity_keys_required'
        member=bool(membership['member'][i]);comparator=objective.comparator
        if comparator=='reference_period':
            arms=(member and record.get('cg4_period')==objective.current_period,
                  member and record.get('cg4_period')==objective.reference_period)
        elif comparator=='ceiling':arms=(member,False)
        elif comparator=='paired':arms=(member,member)
        elif comparator=='overall':arms=(member,True)
        else:arms=(member,not member)
        for arm,included in enumerate(arms):
            if not included:continue
            if entity in seen[arm]:return 'multiple_potential_observations_per_entity_in_an_arm'
            seen[arm].add(entity)
    return None


def feasibility(spec,family_size,component_counts,*,units,records,work_budget,available_bytes,remaining_seconds=None,ranked=False):
    if isinstance(spec,dict):spec=ConfirmationSpec.from_dict(spec)
    if not 1<=family_size<=32 or len(component_counts)!=family_size or any(not isinstance(c,int) or c<1 for c in component_counts):raise EvaluationError('Invalid frozen confirmation family.')
    alpha=Decimal(str(spec.batch_alpha));tail=alpha/(Decimal(2)*family_size*max(component_counts))
    minimum=int((Decimal(spec.minimum_tail)/tail).to_integral_value(rounding=ROUND_CEILING))
    effective=(spec.replicates if spec.replicate_policy=='fixed' else max(spec.replicates,minimum)) if spec.method!='finite' else 0
    reasons=[]
    if spec.method!='finite' and effective>spec.max_replicates:reasons.append('replication_budget_below_nominal_requirement')
    if spec.method!='finite' and effective<minimum:reasons.append('insufficient_nominal_tail_resolution')
    if spec.method!='finite' and units<spec.minimum_units:reasons.append('insufficient_independent_units')
    # Absolute-effect intervals call the numerical kernel separately for each
    # allocated component. Match its ranking-setup and reduction accounting,
    # rather than admitting one joint call and refusing a later component at H.
    # Components run sequentially, so their transient memory is not summed.
    calls=sum(component_counts) if spec.method!='finite' else 0
    setup=math.ceil(2*records*math.log2(max(2,records))) if ranked else 0
    work=calls*(effective*(records if ranked else units)*4+records*4+units*4+setup) if spec.method!='finite' else records*sum(component_counts)
    memory=records*(64 if ranked else 32)+units*32+effective*8 if spec.method!='finite' else records*24
    if work>work_budget:reasons.append('inference_work_limit')
    if memory>available_bytes:reasons.append('inference_memory_admission')
    if remaining_seconds is not None and remaining_seconds<=0:reasons.append('deadline_admission')
    return ConfirmationFeasibility({'status':'not_admitted' if reasons else 'nominally_admitted','reasons':reasons,
       'family_size':family_size,'elementary_intervals':list(component_counts),'confidence':spec.confidence,
       'study_alpha':spec.study_alpha,'batch_alpha':spec.batch_alpha,'hypothesis_alpha':float(alpha/family_size),
       'minimum_nominal_tail_probability':float(tail),'minimum_nominal_replicates':minimum,
       'requested_replicates':spec.replicates,'effective_replicates':effective,'maximum_replicates':spec.max_replicates,
       'replicate_policy':spec.replicate_policy,'minimum_tail_observations':spec.minimum_tail,
       'independent_units':units,'records':records,'estimated_work_units':work,'estimated_memory_bytes':memory,
       'bootstrap_kernel_calls':calls,'work_accounting_version':'component_bootstrap_reductions_v2' if calls else 'finite_component_scans_v1',
       'estimated_memory_is_upper_bound':False,
       'BCa_adjusted_tail_feasibility':'requires_reserved_H_computation' if spec.method=='bca' else 'not_applicable',
       'guarantee':'Numerical admission is not a bootstrap coverage theorem.'})


def orient(interval,objective):
    lo,hi=interval
    if objective.direction=='lower':return -hi,-lo
    if objective.direction=='nominal_shortfall':return objective.nominal-hi,objective.nominal-lo
    if objective.direction=='absolute':return (0. if lo<=0<=hi else min(abs(lo),abs(hi))),max(abs(lo),abs(hi))
    return lo,hi


def classify(interval,delta):
    lo,hi=interval
    return 'confirmed' if lo>delta else 'unreproduced' if hi<=delta else 'inconclusive'


def binomial_interval(values,alpha):
    from scipy.stats import binomtest
    n=len(values)
    if not n:return None
    if not np.isin(values,[0.,1.]).all():raise EvaluationError('Bernoulli inference received non-Bernoulli contributions.','inference_contribution')
    if not 0<alpha<1 or 1-alpha==1:raise EvaluationError('Interval allocation is below numerical resolution.','inference_tail_resolution')
    interval=binomtest(int(np.sum(values)),n).proportion_ci(confidence_level=1-alpha,method='exact')
    return float(interval.low),float(interval.high)


def bounded_interval(values,bounds,alpha):
    if not len(values):return None
    if not np.isfinite(values).all() or np.min(values)<bounds[0] or np.max(values)>bounds[1]:raise EvaluationError('Declared contribution bounds were violated.','contribution_bounds_violated')
    radius=(bounds[1]-bounds[0])*math.sqrt(math.log(2/alpha)/(2*len(values)));mean=float(np.mean(values))
    return max(bounds[0],mean-radius),min(bounds[1],mean+radius)


def _transform_mean(value,metric):
    return math.sqrt(max(0,value)) if metric=='rmse' else value


def finite_interval(objective,left,right,alpha,*,binary,bounds):
    """Component Bonferroni does not assume the groups are independent."""
    sides=1 if objective.comparator=='ceiling' else 2;allocation=alpha/sides
    if binary:interval=binomial_interval(left,allocation)
    elif bounds:interval=bounded_interval(left,bounds,allocation)
    else:return {'status':'inadmissible','reason':'finite_inference_requires_registered_bounded_contributions'}
    if interval is None:return {'status':'unavailable','reason':'empty_conditional_member_population'}
    interval=tuple(_transform_mean(x,objective.metric) for x in interval);a=orient(interval,objective)
    if sides==1:b=orient((objective.ceiling,objective.ceiling),objective)
    else:
        comparison=binomial_interval(right,allocation) if binary else bounded_interval(right,bounds,allocation)
        if comparison is None:return {'status':'unavailable','reason':'empty_conditional_comparator_population'}
        comparison=tuple(_transform_mean(x,objective.metric) for x in comparison);b=orient(comparison,objective)
    return {'status':'available','lower':a[0]-b[1],'upper':a[1]-b[0],
            'method':'clopper_pearson_component_bonferroni' if binary else 'hoeffding_component_bonferroni',
            'strength':'finite_sample','allocated_alpha':alpha,'elementary_intervals':sides}


def f1_interval(confusions,objective,alpha):
    sides=len(confusions);intervals=[]
    for cells in confusions:
        n=sum(cells)
        if not n:return {'status':'unavailable','reason':'empty_confusion_population'}
        bounds=[]
        from scipy.stats import binomtest
        for cell in cells:
            interval=binomtest(int(cell),int(n)).proportion_ci(confidence_level=1-alpha/(4*sides),method='exact');bounds.append((interval.low,interval.high))
        tp,fp,fn,_=bounds
        lower=2*tp[0]/(2*tp[0]+fp[1]+fn[1]) if 2*tp[0]+fp[1]+fn[1] else 0.
        upper=2*tp[1]/(2*tp[1]+fp[0]+fn[0]) if 2*tp[1]+fp[0]+fn[0] else 1.
        intervals.append(orient((float(lower),float(upper)),objective))
    a=intervals[0];b=intervals[1] if sides==2 else orient((objective.ceiling,objective.ceiling),objective)
    return {'status':'available','lower':a[0]-b[1],'upper':a[1]-b[0],'method':'confusion_cell_exact_composition',
            'strength':'finite_sample','elementary_intervals':4*sides,'allocated_alpha':alpha}


def calibration_interval(residuals,bin_ids,member,control,objective,alpha,bins):
    sides=1 if objective.comparator=='ceiling' else 2;intervals=[]
    for group in (member,control)[:sides]:
        if not np.any(group):return {'status':'unavailable','reason':'empty_calibration_population'}
        lo=hi=0.
        for i in range(bins):
            values=np.where(bin_ids[group]==i,residuals[group],0.)
            component=bounded_interval(values,(-1.,1.),alpha/(bins*sides))
            a,b=component;lo+=0 if a<=0<=b else min(abs(a),abs(b));hi+=max(abs(a),abs(b))
        intervals.append(orient((lo,min(1.,hi)),objective))
    a=intervals[0];b=intervals[1] if sides==2 else orient((objective.ceiling,objective.ceiling),objective)
    return {'status':'available','lower':a[0]-b[1],'upper':a[1]-b[0],'method':'fixed_bin_residual_hoeffding_composition',
            'strength':'finite_sample','elementary_intervals':bins*sides,'allocated_alpha':alpha}


def approximate_interval(contributions,objective,spec,*,family_size,units,work_budget,check,ranked=None):
    from .inference import preflight,_replicates,rank_stat
    values=np.asarray(contributions,dtype=float);n=len(values)
    if objective.direction=='absolute':
        if ranked:return {'status':'inadmissible','reason':'absolute_ranking_transform_not_registered'}
        from dataclasses import replace
        sides=1 if objective.comparator=='ceiling' else 2;components=[]
        component_objective=replace(objective,direction='higher',comparator='ceiling',ceiling=0.)
        allocated=replace(spec,batch_alpha=spec.batch_alpha/sides)
        for numerator,denominator in ((2,3),(0,1))[:sides]:
            matrix=np.column_stack((np.zeros(n),np.ones(n),values[:,numerator],values[:,denominator]))
            component=approximate_interval(matrix,component_objective,allocated,family_size=family_size,units=units,work_budget=work_budget//sides,check=check)
            components.append(component)
        if any(c['status']!='available' for c in components):return {'status':'unavailable','reason':'absolute_effect_component_interval_unavailable','components':components}
        a=orient((components[0]['lower'],components[0]['upper']),objective)
        b=orient((components[1]['lower'],components[1]['upper']),objective) if sides==2 else orient((objective.ceiling,objective.ceiling),objective)
        return {'status':'available','lower':a[0]-b[1],'upper':a[1]-b[0],'method':'component_bootstrap_then_absolute_interval_composition',
                'strength':'approximate','components':components,'elementary_intervals':sides,'allocated_alpha':spec.batch_alpha/family_size}
    _,index=np.unique(np.asarray(units),return_inverse=True);count=int(index.max())+1 if n else 0
    if count<spec.minimum_units:return {'status':'unavailable','reason':'insufficient_independent_units'}
    if ranked and spec.method!='percentile':return {'status':'inadmissible','reason':'ranking_requires_predeclared_percentile_method'}
    helper=SimpleNamespace(adjustment='bonferroni',confidence=1-spec.batch_alpha,minimum_tail=spec.minimum_tail,
           replicates=spec.replicates,work_units=work_budget,mode='independent_clusters' if spec.sampling=='independent_entities' else 'independent_rows',
           inference_required=False,seed=spec.seed)
    admission=preflight(helper,n,count,family_size,ranked=bool(ranked))
    if admission['status']!='admitted':return {**admission,'status':'unavailable','reason':','.join(admission['reasons'])}
    if ranked:
        y,scores,left_mask,right_mask=ranked[:4]
        evaluator=rank_stat(y,scores,scores,objective.metric).left_value
        comparator_evaluator=rank_stat(y,ranked[4],ranked[4],objective.metric).left_value if len(ranked)>4 else evaluator
        def statistic(weights):
            event=weights[index];a=evaluator(event*left_mask);b=comparator_evaluator(event*right_mask) if objective.comparator!='ceiling' else objective.ceiling
            if not math.isfinite(a) or not math.isfinite(b):return math.nan
            aa=orient((a,a),objective)[0];bb=orient((b,b),objective)[0];return aa-bb
        estimate=statistic(np.ones(count));unit_values=None;method='paired_percentile'
    else:
        if values.shape!=(n,4) or not np.isfinite(values).all():return {'status':'unavailable','reason':'invalid_contributions'}
        unit_values=np.zeros((count,4))
        for j in range(4):unit_values[:,j]=np.bincount(index,weights=values[:,j],minlength=count)
        def totals_statistic(totals):
            if totals[1]<=0 or totals[3]<=0:return math.nan
            a=_transform_mean(totals[2]/totals[3],objective.metric);b=_transform_mean(totals[0]/totals[1],objective.metric)
            return orient((a,a),objective)[0]-orient((b,b),objective)[0]
        statistic=lambda weights:totals_statistic(weights@unit_values)
        estimate=statistic(np.ones(count));method='paired_bca' if spec.method=='bca' else 'paired_percentile'
    if not math.isfinite(estimate):return {'status':'unavailable','reason':'undefined_original_statistic'}
    result=_replicates(helper,admission,count,n,None,statistic,estimate,unit_values,method,check,
                       totals_statistic=totals_statistic if not ranked else None)
    result['strength']='approximate';result['scope']='Frozen hypotheses; declared independent rows/entities; no temporal correction or missing-label correction'
    return result


def _input(frozen,confirmation_input=None):
    from .investigation_contracts import InvestigationSpec,FrozenHypothesisSet,observation_policy
    if isinstance(frozen,FrozenHypothesisSet):frozen=FrozenHypothesisSet.from_dict(frozen.to_dict())
    elif isinstance(frozen,dict):frozen=FrozenHypothesisSet.from_dict(frozen)
    if not isinstance(frozen,FrozenHypothesisSet):raise EvaluationError('FrozenHypothesisSet required.')
    original=InvestigationSpec.from_dict(frozen.data['investigation_spec'])
    spec=original if confirmation_input is None else confirmation_input if isinstance(confirmation_input,InvestigationSpec) else InvestigationSpec.from_dict(confirmation_input)
    if spec.roles.namespace!=original.roles.namespace or spec.roles.unit!=original.roles.unit:raise EvaluationError('Confirmation cannot rename the event/entity namespace.','confirmation_identity')
    if [o.to_dict() for o in spec.objectives]!=[o.to_dict() for o in original.objectives]:raise EvaluationError('Confirmation input cannot revise the frozen objective declarations.','confirmation_identity')
    if (spec.evaluation is None)!=(original.evaluation is None):raise EvaluationError('Confirmation cannot switch supplied and retained evidence contracts.','confirmation_identity')
    if spec.feature_time_view!=original.feature_time_view:raise EvaluationError('Confirmation cannot change the frozen feature-time interpretation.','confirmation_observation_policy')
    if observation_policy(spec)!=observation_policy(original):raise EvaluationError('Confirmation cannot change frozen outcome status, clock, maturity, authority or context semantics. Rebind only the declared future sources/snapshots.','confirmation_observation_policy')
    if spec.evaluation is not None and original.evaluation is not None:
        if spec.evaluation.task.to_dict()!=original.evaluation.task.to_dict():raise EvaluationError('Confirmation task changed.','confirmation_identity')
        before={r.id:r.model.to_dict() for r in original.evaluation.runs};after={r.id:r.model.to_dict() for r in spec.evaluation.runs}
        if before!=after:raise EvaluationError('Confirmation predictor identities changed.','confirmation_identity')
        semantics=lambda r:{k:v for k,v in r.to_dict().items() if k!='source'}
        if {r.id:semantics(r) for r in original.evaluation.runs}!={r.id:semantics(r) for r in spec.evaluation.runs}:raise EvaluationError('Confirmation output/decision semantics changed.','confirmation_identity')
    semantic=lambda view:{k:v for k,v in view.to_dict().items() if k not in {'source','revision','predecessor','reason'}}
    if {v.id:semantic(v) for v in spec.features}!={v.id:semantic(v) for v in original.features}:raise EvaluationError('Confirmation feature semantics changed.','confirmation_identity')
    rep=lambda r:{k:v for k,v in r.to_dict().items() if k not in {'matrix_path','keys_source','key_columns','model_directory'}}
    if {r.id:rep(r) for r in spec.representations}!={r.id:rep(r) for r in original.representations}:raise EvaluationError('Confirmation representation identity changed.','confirmation_identity')
    return frozen,spec


def _configuration(frozen,config):
    from .contracts import EvaluationConfig
    original=EvaluationConfig.from_dict(frozen.data['evaluation_config'])
    candidate=original if config is None else config if isinstance(config,EvaluationConfig) else EvaluationConfig.from_dict({**original.to_dict(),**config})
    for attr in ('calibration_bins','high_confidence','probability_tolerance','sampling'):
        if getattr(original,attr)!=getattr(candidate,attr):raise EvaluationError('Confirmation cannot change frozen analytical settings.','confirmation_metric_identity')
    return candidate


def _inspect_confirmation(frozen,spec,config,roots,require_original=False,scheduled=None,numerical_extension=None,*,progress=None):
    from .investigation import prepared
    from .investigation_membership import apply
    from .investigation_contracts import FailureObjectiveSpec
    from .contracts import digest
    from .result import Inspection
    protocol=_protocol(frozen,scheduled,numerical_extension)
    with prepared(spec,config,roots,progress) as p:
        if require_original and {k:(v.get('sha256'),v.get('bytes')) for k,v in p.files.items()}!={k:(v.get('sha256'),v.get('bytes')) for k,v in frozen.data['files'].items()}:
            raise EvaluationError('The original frozen input changed. Supply an explicit confirmation population or immutable restatement input.','frozen_input_changed')
        indices,features,representations=p.role_data('H');records=[p.records[i] for i in indices]
        entities=[r.get('entity_key') for r in records]
        units=len(set(entities)) if protocol.sampling in {'independent_entities','independent_entity_arms'} and None not in entities else len(records)
        events=[digest([spec.roles.namespace,p.keys[i]]) for i in indices]
        from .evidence_use import population_identifiers,local_identity_scope
        exposure_events,unit_ids=population_identifiers(p,indices)
        identity_scope=local_identity_scope(p,indices)
        reasons=[]
        if any(r.get('cg_role') in {'F','S','C'} for r in records):reasons.append('observable_CG2_F_S_C_overlap')
        if any(r.get('history_fact') in getattr(p.store,'cg4_known_exposed_facts',set()) for r in records):reasons.append('previously_assessed_historical_evidence')
        from .membership import key_digest
        for sidecar in getattr(p.store,'cg4_sidecars',[]):
            if sidecar['namespace']!=spec.roles.namespace:continue
            prior_events={r[0] for r in sidecar['rows']};prior_entities={r[1] for r in sidecar['rows'] if r[1] is not None}
            for record in records:
                original_key=getattr(p.store,'cg4_original_keys',{}).get(record['event_key'])
                original_entity=getattr(p.store,'cg4_original_entities',{}).get(record['event_key'])
                if (original_key is not None and key_digest(spec.roles.namespace,original_key) in prior_events) or key_digest(spec.roles.namespace,record.get('entity_key')) in prior_entities or original_entity is not None and key_digest(spec.roles.namespace,original_entity) in prior_entities:
                    reasons.append('observable_upstream_method_membership_overlap');break
        if set(exposure_events)&set(frozen.data['D_S_events']) or set(unit_ids)&set(frozen.data['D_S_units']):reasons.append('observable_D_S_H_overlap')
        if protocol.sampling=='independent_rows' and any(e is not None for e in entities) and len(set(entities))<len(entities):reasons.append('repeated_entities_in_independent_row_design')
        if protocol.sampling in {'independent_entities','independent_entity_arms'} and None in entities:reasons.append('entity_keys_required')
        if protocol.sampling=='independent_entity_arms' and spec.roles.unit!='entity':reasons.append('entity_arm_confirmation_requires_entity_role_assignment')
        if protocol.sampling in {'descriptive','unsupported_temporal'} or protocol.known_common_shocks:reasons.append('unsupported_confirmation_dependence')
        if protocol.upstream_independence!='declared_independent':reasons.append('upstream_independence_unknown' if protocol.upstream_independence=='unknown' else 'known_upstream_overlap')
        if protocol.external_exposure!='declared_unexposed':reasons.append('external_exposure_unknown' if protocol.external_exposure=='unknown' else 'known_external_exposure')
        # The numerical kernel is retained for reproducibility and qualification.
        # Its joint contrast failed locked coverage panels; a generic choice of
        # BCa cannot assert that the unseen population avoids those failures.
        if protocol.method=='bca':reasons.append('joint_BCa_confirmation_qualification_unresolved')
        cache={'_models':frozen.data['models'],'_directory':str(p.work.root),'_max_distance_ops':spec.limits.max_distance_operations,'_population_size':len(indices),'_membership_memory_bytes':config.max_rss_bytes//3,'_threads':config.threads}
        membership=[];components=[]
        for h in frozen.data['hypotheses']:
            artifact=frozen.data['artifacts'][h['membership_artifact']]
            fields=set(artifact['features']);representation=next((r for r in spec.representations if r.id==artifact.get('representation')),None)
            if representation and representation.field:fields.add(representation.field)
            if fields&p.known_outcome_features:raise EvaluationError('Known outcome-bound membership cannot disclose H membership counts.','outcome_derived_membership')
            mask=apply(artifact,features,representations,cache=cache,check=p.work.check)
            count=int(mask['available'].sum());coverage=count/len(indices) if len(indices) else 0.
            affected=[]
            from .features import FEATURE_TIME_POLICY
            if any(v.information_cutoff and any(v.id+'.'+f.id in fields for f in v.fields) for v in spec.features) and h.get('feature_time_policy')!=FEATURE_TIME_POLICY:
                affected.append('legacy_information_cutoff_interpretation_unqualified')
            if scheduled:
                expected=scheduled['memberships'].get(h['membership_artifact'],{}).get('H')
                actual={'member_bits':np.packbits(mask['member'],bitorder='little').tobytes().hex(),'available_bits':np.packbits(mask['available'],bitorder='little').tobytes().hex(),'records':len(indices)}
                if expected!=actual or scheduled['event_hashes']!=events:affected.append('scheduled_restatement_population_or_membership_changed')
            if h['membership_scope']=='full_population' and count!=len(indices):affected.append('incomplete_full_population_membership')
            if coverage<h['minimum_membership_coverage']:affected.append('membership_coverage_below_frozen_requirement')
            objective=FailureObjectiveSpec.from_dict(h['objective']);components.append(elementary_count(objective,protocol.method,config.calibration_bins))
            if protocol.sampling=='independent_entity_arms':
                structural_refusal=_entity_arm_refusal(records,mask,objective,p.work.check)
                if structural_refusal:affected.append(structural_refusal)
            from .investigation_objectives import legacy_paired_precision
            if legacy_paired_precision(objective,artifact):affected.append('legacy_paired_precision_population_unqualified')
            from .investigation_objectives import bind,uncertainty_contribution_contract
            contribution_contract=uncertainty_contribution_contract(objective,p.store.spec.task)
            registration=(SimpleNamespace(spec=objective,proxy='exact_additive_loss',reducer='uncertainty',**contribution_contract)
                          if contribution_contract is not None else bind(objective,p.store))
            refusal=_method_refusal(registration,protocol)
            if refusal:affected.append(refusal)
            membership.append({'hypothesis_id':h['id'],'planned':len(indices),'available':count,'members':int(mask['member'].sum()),'nonmembers':int((mask['available']&~mask['member']).sum()),'unavailable':len(indices)-count,'admissibility_reasons':affected})
        feasibility_data=feasibility(protocol,len(components),components,units=units,records=len(indices),work_budget=spec.limits.inference_work_units,
                                     available_bytes=config.max_rss_bytes//2,remaining_seconds=config.max_seconds,
                                     ranked=any(h['objective']['metric'] in {'roc_auc','average_precision'} for h in frozen.data['hypotheses'])).to_dict()
        import hashlib
        vector_snapshots={}
        for rid,rep in representations.items():
            sha=hashlib.sha256(rep['vectors'].dtype.str.encode())
            for start in range(0,len(rep['vectors']),128):sha.update(np.ascontiguousarray(rep['vectors'][start:start+128]).view(np.uint8))
            provenance=rep.get('provenance',{});declaration=next(r for r in spec.representations if r.id==rid)
            vector_snapshots[rid]=digest({'vectors':sha.hexdigest(),'available':rep['available'].tolist(),
                'producer_contract':{k:v for k,v in declaration.to_dict().items() if k not in {'matrix_path','keys_source','model_directory','available_at','content_available_at'}},
                'producer_runtime':{k:provenance.get(k) for k in ('producer','model','revision','runtime','profile')}})
        snapshot=hashlib.sha256()
        for record in records:snapshot.update(digest({k:v for k,v in record.items() if k not in {'ordinal','cg4_member','cg4_available'}}).encode())
        population=digest({'events':exposure_events,'units':sorted(set(unit_ids)),'H_snapshot':snapshot.hexdigest(),
                           'features':digest(features),'representations':vector_snapshots,'family':frozen.evidence_family_digest})
        if scheduled:reasons=[r for r in reasons if r!='previously_assessed_historical_evidence']
        fingerprint=digest({'family':frozen.data['content_digest'],'input':p.fingerprint,'feasibility':feasibility_data,'membership':membership,'scheduled_look':scheduled['look'] if scheduled else None})
        p.verify()
        return Inspection({'schema_version':'confidenceguard.confirmation_inspection/1.0','fingerprint':fingerprint,'input_fingerprint':p.fingerprint,
            'family_digest':frozen.family_digest,'feasibility':feasibility_data,'membership':membership,'admissibility_reasons':sorted(set(reasons)),
            'independence':{'local_separation':'failed' if any(reason in reasons for reason in ('observable_D_S_H_overlap','observable_CG2_F_S_C_overlap','observable_upstream_method_membership_overlap')) else 'partially_checked' if identity_scope=='canonical_history_keys_original_aliases_incomplete' else 'system_checked',
                            'local_identity_scope':identity_scope,
                            'upstream':protocol.upstream_independence,'external_exposure':protocol.external_exposure,'exposure_continuity':'unknown',
                            'sampling_design':protocol.sampling},
            'H_outcomes_disclosed':False,'confirmation_look':scheduled['look'] if scheduled else None,'_effective_spec':p.spec.to_dict(),
            '_protected_population':{'events':exposure_events,'units':sorted(set(unit_ids)),'population_digest':population,
                'query_events':sorted(set(exposure_events)|set(population_identifiers(p,indices,source_scope=True)[0]))}},
            {'status':'completed','peak_workspace_bytes':p.work.peak})


def inspect_confirmation(frozen,config=None,*,confirmation_input=None,allowed_roots=None,workspace=None,progress=None,cancel=None,_protected=False,_deadline=None,_scheduled=None,_numerical_extension=None):
    from .investigation import arguments,historical_workspace
    from . import compat
    from .evidence_use import EvidenceUseLedger,session_overlap,session_replay_history_incomplete
    frozen,spec=_input(frozen,confirmation_input);spec,config,roots=arguments(spec,_configuration(frozen,config),allowed_roots)
    result=compat.supervise(_inspect_confirmation,(frozen,spec,config,roots,confirmation_input is None,_scheduled,_numerical_extension),config,progress=progress,cancel=cancel,deadline=_deadline).to_dict()
    from .investigation_contracts import InvestigationSpec
    workspace=historical_workspace(InvestigationSpec.from_dict(result['_effective_spec']),workspace)
    population=result['_protected_population'];reasons=result['admissibility_reasons']
    query_events=population.get('query_events',population['events'])
    if not _scheduled and session_overlap(query_events,population['units'],frozen.evidence_family_digest,population['population_digest']):reasons.append('known_session_exposure')
    if not _scheduled and session_replay_history_incomplete():reasons.append('session_replay_exposure_history_incomplete')
    if workspace is not None:
        ledger=EvidenceUseLedger(workspace);state=ledger.status();result['independence']['exposure_continuity']=state['continuity']
        observed=ledger.overlap(query_events,population['units'],family_digest=frozen.evidence_family_digest,population_digest=population['population_digest'])
        gaps=[r for r in observed if r in {'exposure_history_unavailable','exposure_history_incomplete'}]
        protocol=ConfirmationSpec.from_dict(frozen.data['confirmation_spec'])
        gap=state['continuity'] in {'incomplete','restore_unreconciled'} or bool(gaps)
        current=bool(protocol.exposure_history_token and protocol.exposure_history_token==state.get('continuity_token'))
        if gap and not current:reasons.append('exposure_history_gap_requires_current_declaration')
        if gap and current:result['independence']['history_gap_basis']='current_scoped_declaration_not_system_verified_history'
        if gaps and current and protocol.external_exposure=='declared_unexposed':
            result['independence']['ledger_gaps_declaration_qualified']=gaps;observed=[r for r in observed if r not in gaps]
        reasons.extend(observed)
        result['independence']['ledger_enabled']=state['enabled']
    elif ConfirmationSpec.from_dict(frozen.data['confirmation_spec']).exposure_history_token is not None:reasons.append('history_declaration_workspace_required')
    if _scheduled:
        reasons[:]=[r for r in reasons if r not in {'previously_exposed_confirmation_population','exposure_history_unavailable','exposure_history_incomplete'}]
        result['independence'].update(evidence_use='predeclared_restatement_not_fresh_independent_evidence',original_reservation_id=_scheduled['initial_use_id'],
            external_exposure_declaration_scope='before_initial_H_access',schedule_predeclared_and_locally_verified=True)
    result['admissibility_reasons']=sorted(set(reasons))
    from .contracts import digest
    result['fingerprint']=digest({'analytical_inspection':result['fingerprint'],'admissibility_reasons':result['admissibility_reasons'],'independence':result['independence']})
    if not _protected:
        result.pop('_protected_population');result.pop('_effective_spec')
    return result


def _assess(frozen,spec,config,roots,inspection,reservation,scheduled=None,numerical_extension=None,*,progress=None):
    from datetime import datetime,timezone
    import copy,time,uuid
    from dataclasses import replace
    from .investigation import prepared
    from .investigation_membership import apply
    from .investigation_objectives import bind
    from .investigation_contracts import FailureObjectiveSpec,CONFIRMATION_RESULT,INVESTIGATION_METHOD
    from .investigation_result import InvestigationResult
    from .contracts import digest
    started=time.monotonic();protocol=_protocol(frozen,scheduled,numerical_extension)
    protocol=replace(protocol,replicates=inspection['feasibility']['effective_replicates']) if protocol.method!='finite' and inspection['feasibility']['effective_replicates']<=protocol.max_replicates else protocol
    with prepared(spec,config,roots,progress) as p:
        if p.fingerprint!=inspection['input_fingerprint']:raise EvaluationError('Confirmation input changed after inspection/reservation.','stale_confirmation')
        p.store.cg4_confirmation=True
        indices,features,reps=p.role_data('H');n=len(indices);cache={'_models':frozen.data['models'],'_directory':str(p.work.root),'_max_distance_ops':spec.limits.max_distance_operations,'_population_size':n,'_membership_memory_bytes':config.max_rss_bytes//3,'_threads':config.threads}
        records=[p.records[i] for i in indices];unit_labels=[r.get('entity_key') if protocol.sampling in {'independent_entities','independent_entity_arms'} else r['event_key'] for r in records]
        assessments=[];memberships={};family_size=len(frozen.data['hypotheses'])
        for h in frozen.data['hypotheses']:
            objective_spec=FailureObjectiveSpec.from_dict(h['objective']);artifact=frozen.data['artifacts'][h['membership_artifact']]
            mask=apply(artifact,features,reps,cache=cache,check=p.work.check)
            memberships[h['membership_artifact']]={'H':{'member_bits':np.packbits(mask['member'],bitorder='little').tobytes().hex(),'available_bits':np.packbits(mask['available'],bitorder='little').tobytes().hex(),'records':n}}
            support={'planned':n,'available':int(mask['available'].sum()),'members':int(mask['member'].sum()),'nonmembers':int((mask['available']&~mask['member']).sum()),'unavailable':n-int(mask['available'].sum())}
            base={'hypothesis_id':h['id'],'candidate_id':h['candidate_id'],'membership_scope':h['membership_scope'],'practical_threshold':objective_spec.practical_threshold,
                  'objective':objective_spec.to_dict(),'support':support,'independence_qualification':inspection['independence'],'strength':'descriptive'}
            affected=next(row['admissibility_reasons'] for row in inspection['membership'] if row['hypothesis_id']==h['id'])
            if inspection['admissibility_reasons'] or affected:
                assessments.append({**base,'state':'statistically_inadmissible','reason':','.join(inspection['admissibility_reasons']+affected),'H_outcomes_disclosed':False});continue
            if inspection['feasibility']['status']=='not_admitted':
                assessments.append({**base,'state':'inconclusive','reason':','.join(inspection['feasibility']['reasons']),'H_outcomes_disclosed':False});continue
            objective=bind(objective_spec,p.store);measurement=p.evaluate(objective,'H',indices,mask,artifact)
            base.update(effect=measurement['effect'],effect_state=measurement['effect_state'],sensitive_counts=measurement['sensitive_counts'],H_outcomes_disclosed=True,
                        member_metric=measurement['member_metric'],comparator_metric=measurement['comparator_metric'],
                        membership_unavailable_reasons=measurement['membership_unavailable_reasons'],outcome_observation_states=measurement['outcome_observation_states'])
            if 'outcome_status_states' in measurement:base['outcome_status_states']=measurement['outcome_status_states']
            # Contributions are read only after the parent has reserved H access.
            query=p.store.con.execute(f'SELECT event_key,({objective.eligible_sql}),({objective.loss_sql}) FROM {objective.table} WHERE cg4_role=\'H\' ORDER BY event_key').fetchall()
            mapped={r[0]:(bool(r[1]),float(r[2]) if r[2] is not None else math.nan) for r in query}
            eligible=np.array([mapped[p.keys[i]][0] for i in indices]);loss=np.array([mapped[p.keys[i]][1] for i in indices])
            member=mask['member']&eligible;control=mask['available']&eligible&(~mask['member'] if objective_spec.comparator!='overall' else True)
            control_loss=loss;reference_records=None
            if objective.reference:
                ref=objective.reference
                cursor=p.store.con.execute(f'SELECT * FROM {ref.table} WHERE cg4_role=\'H\'');columns=[c[0] for c in cursor.description]
                reference_records={row['event_key']:row for row in (dict(zip(columns,r)) for r in cursor.fetchall())}
                other=p.store.con.execute(f'SELECT event_key,({ref.eligible_sql}),({ref.loss_sql}) FROM {ref.table} WHERE cg4_role=\'H\'').fetchall()
                other={row[0]:(bool(row[1]),float(row[2]) if row[2] is not None else math.nan) for row in other}
                own_base=dict(p.store.con.execute(f'SELECT event_key,({objective.pair_eligible_sql}) FROM {objective.table} WHERE cg4_role=\'H\'').fetchall())
                other_base=dict(p.store.con.execute(f'SELECT event_key,({ref.pair_eligible_sql}) FROM {ref.table} WHERE cg4_role=\'H\'').fetchall())
                common=np.array([bool(own_base.get(p.keys[i],False)) and bool(other_base.get(p.keys[i],False)) for i in indices])
                control_loss=np.array([other.get(p.keys[i],(False,math.nan))[1] for i in indices])
                member=mask['member']&common&eligible
                control=mask['member']&common&np.array([other.get(p.keys[i],(False,math.nan))[0] for i in indices])
            elif objective_spec.comparator=='reference_period':
                periods=[r['cg4_period'] for r in records]
                member&=np.array([v==objective_spec.current_period for v in periods])
                control=mask['member']&eligible&np.array([v==objective_spec.reference_period for v in periods])
            support.update(conditional_members=int(member.sum()),conditional_nonmembers=int(control.sum()))
            alpha=protocol.batch_alpha/family_size
            try:
                if measurement['effect_state']=='undefined':inference={'status':'unavailable','reason':'undefined_original_statistic'}
                elif objective.proxy.removeprefix('paired_metric_specific_proposal_difference:')=='point_loss_proxy_for_nonadditive_metric':
                    inference={'status':'inadmissible','reason':'native_nonadditive_interval_not_registered'}
                elif protocol.outcome_scope=='complete_population' and not all(r['outcome_valid'] for r in records):
                    inference={'status':'inadmissible','reason':'incomplete_outcomes_for_full_population_claim'}
                elif protocol.method=='finite' and protocol.sampling not in {'independent_rows','independent_entity_arms'}:
                    inference={'status':'inadmissible','reason':'finite_row_methods_do_not_correct_entity_dependence'}
                elif objective_spec.metric=='f1' and protocol.method=='finite':
                    c=objective_spec.target or p.store.spec.task.positive_class;confusions=[]
                    for arm,group in enumerate((member,control)[:1 if objective_spec.comparator=='ceiling' else 2]):
                        selected_records=[reference_records.get(p.keys[i],{}) for i in indices] if arm==1 and reference_records is not None else records
                        selected=[r for r,g in zip(selected_records,group) if g and r['outcome_valid'] and r['decision'] is not None and r['state'] in {'issued','hypothetical'}]
                        confusions.append([sum(r['y']==c and r['decision']==c for r in selected),sum(r['y']!=c and r['decision']==c for r in selected),sum(r['y']==c and r['decision']!=c for r in selected),sum(r['y']!=c and r['decision']!=c for r in selected)])
                    inference=f1_interval(confusions,objective_spec,alpha)
                elif objective_spec.metric=='reliability_diagram' and protocol.method=='finite':
                    target=objective_spec.target or p.store.spec.task.positive_class;j=p.store.spec.task.classes.index(target)
                    probabilities=np.array([r['probs'][j] if r['probs'] else np.nan for r in records]);bin_ids=np.minimum(config.calibration_bins-1,np.floor(np.nan_to_num(probabilities)*config.calibration_bins)).astype(int)
                    if reference_records is None:inference=calibration_interval(loss,bin_ids,member,control,objective_spec,alpha,config.calibration_bins)
                    else:
                        components=[];component_spec=replace(objective_spec,comparator='ceiling',ceiling=0.,direction='higher')
                        other_probabilities=np.array([(reference_records.get(p.keys[i],{}).get('probs') or [math.nan]*len(p.store.spec.task.classes))[j] for i in indices])
                        other_bins=np.minimum(config.calibration_bins-1,np.floor(np.nan_to_num(other_probabilities)*config.calibration_bins)).astype(int)
                        for residual,bins,group in ((loss,bin_ids,member),(control_loss,other_bins,control)):
                            component=calibration_interval(residual,bins,group,group,component_spec,alpha/2,config.calibration_bins);components.append(component)
                        if any(c['status']!='available' for c in components):inference={'status':'unavailable','reason':'undefined_calibration_component'}
                        else:
                            a,b=[orient((c['lower'],c['upper']),objective_spec) for c in components]
                            inference={'status':'available','lower':a[0]-b[1],'upper':a[1]-b[0],'strength':'finite_sample','method':'paired_fixed_bin_residual_hoeffding_composition','elementary_intervals':2*config.calibration_bins}
                elif protocol.method=='finite' and objective.reducer=='ranking':inference={'status':'inadmissible','reason':'ranking_finite_method_not_registered'}
                elif protocol.method=='finite':inference=finite_interval(objective_spec,loss[member],control_loss[control],alpha,binary=objective.binary,bounds=objective.bounded)
                elif objective.proxy.removeprefix('paired_metric_specific_proposal_difference:') not in {'exact_additive_loss','finite_clipped_log_loss_for_proposals','fixed_D_discordance','D_precision_staircase_and_discordance_proxy'}:
                    inference={'status':'inadmissible','reason':'approximate_method_not_registered_for_nonsmooth_metric'}
                else:
                    group_units=[];_,unit_index=np.unique(unit_labels,return_inverse=True)
                    for group in (member,control)[:1 if objective_spec.comparator=='ceiling' else 2]:
                        counts=np.bincount(unit_index,weights=group.astype(float))
                        counts=counts[counts>0];effective=counts.sum()**2/np.sum(counts**2) if len(counts) else 0
                        group_units.append({'independent_units':len(counts),'effective_units':effective})
                    support['independent_units']=min((v['independent_units'] for v in group_units),default=0)
                    support['effective_units']=min((v['effective_units'] for v in group_units),default=0)
                    if any(v['independent_units']<protocol.minimum_units or v['effective_units']<protocol.minimum_units for v in group_units):inference={'status':'unavailable','reason':'insufficient_conditional_independent_support'}
                    else:
                        finite=np.isfinite(loss)
                        if (not finite[member].all() or not np.isfinite(control_loss[control]).all()) and objective.reducer!='ranking':inference={'status':'unavailable','reason':'nonfinite_original_contributions'}
                        else:
                            left=np.where(control,control_loss,0.);left_den=control.astype(float)
                            if objective_spec.comparator=='ceiling':left=np.full(n,objective_spec.ceiling**2 if objective_spec.metric=='rmse' else objective_spec.ceiling);left_den=np.ones(n)
                            right=np.where(member,loss,0.);values=np.column_stack((left,left_den,right,member.astype(float)))
                            ranked=None
                            if objective.reducer=='ranking':
                                y=np.array([r['y']==p.store.spec.task.positive_class for r in records]);scores=np.array([r['rank_score'] if r['rank_score'] is not None else 0 for r in records]);scores*= -1 if objective.run.score and objective.run.score.direction=='lower' else 1
                                ranked=(y,scores,member,control)
                                if reference_records is not None:
                                    reference_scores=np.array([reference_records.get(p.keys[i],{}).get('rank_score') or 0. for i in indices]);reference_scores*= -1 if objective.reference.run.score and objective.reference.run.score.direction=='lower' else 1
                                    ranked=(*ranked,reference_scores)
                                class_support=[]
                                for arm,group in enumerate((member,control)[:1 if objective_spec.comparator=='ceiling' else 2]):
                                    for label in (False,True):
                                        counts=np.bincount(unit_index,weights=(group&(y==label)).astype(float));counts=counts[counts>0]
                                        effective=counts.sum()**2/np.sum(counts**2) if len(counts) else 0.
                                        class_support.append({'arm':arm,'class':'positive' if label else 'negative','independent_units':len(counts),'effective_units':float(effective)})
                                support['ranking_class_support']=class_support
                            if ranked and any(v['independent_units']<protocol.minimum_units or v['effective_units']<protocol.minimum_units for v in class_support):
                                inference={'status':'unavailable','reason':'insufficient_ranking_class_support'}
                            else:inference=approximate_interval(values,objective_spec,protocol,family_size=family_size,units=unit_labels,work_budget=spec.limits.inference_work_units//family_size,check=p.work.check,ranked=ranked)
            except EvaluationError as exc:inference={'status':'inadmissible','reason':exc.code}
            if protocol.sampling=='independent_entity_arms':
                inference.update(sampling_design=protocol.sampling,
                    assumptions='IID complete entities; at most one potential observation per entity in each frozen comparison arm. Within-entity dependence across arms is allowed. Structural checks cover admitted records; population independence and complete extraction are declarations.')
            if inference.get('status')=='available' and (not all(math.isfinite(float(inference[k])) for k in ('lower','upper')) or inference['lower']>inference['upper']):
                inference={'status':'unavailable','reason':'invalid_or_nonfinite_interval_endpoints'}
            if inference.get('status')=='available':
                interval=(float(inference['lower']),float(inference['upper']));state=classify(interval,objective_spec.practical_threshold)
                base.update(interval={'lower':interval[0],'upper':interval[1],'confidence':protocol.confidence,'adjustment':'bonferroni','family_size':family_size},strength=inference.get('strength','approximate'))
            else:state='statistically_inadmissible' if inference.get('status')=='inadmissible' else 'inconclusive'
            assessments.append({**base,'state':state,'reason':inference.get('reason'),'inference':inference});p.work.check('independent frozen hypothesis assessment')
        data={'schema_version':CONFIRMATION_RESULT,'methodology_id':INVESTIGATION_METHOD,'analysis_id':uuid.uuid4().hex,'name':spec.name+(' — predeclared outcome restatement' if scheduled else ' — independent assessment'),
              'generated_at':datetime.now(timezone.utc).isoformat(),'task':p.store.spec.task.to_dict(),'runs':[],
              'outcomes':{'scope':protocol.outcome_scope,'no_selective_label_correction':True},'comparison':None,'measurements':[],'checks':[],
              'findings':[{'code':'independent_confirmation_scope','priority':'Review','message':'Inference is conditional on frozen hypotheses, declared upstream independence and the recorded observation/membership population.'}],
              'coverage':{'planned_H':n,'populations':[]},'investigation':{'stage':'confirmation','family_digest':frozen.family_digest,'origin_analysis_id':frozen.data['origin_analysis_id'],
                  'candidates':[],'strategies':[],'overlap':[],'assessments':assessments,'history':[],'notes':[],'feasibility':inspection['feasibility'],
                  'independence':inspection['independence'],'reservation':reservation,'workspace_wide_guarantee':False,
                  'predeclared_restatement':{'look':scheduled['look'],'origin_analysis_id':scheduled['origin_analysis_id'],'origin_analysis_digest':scheduled['origin_analysis_digest'],
                    'study_error_allocation':protocol.study_alpha,'look_error_allocation':protocol.batch_alpha,'fresh_independent_evidence':False} if scheduled else None}}
        private={'schema':'confidenceguard.investigation_private/1.0','analysis_id':data['analysis_id'],'config':config.to_dict(),'files':p.files,'spec':spec.evaluation.to_dict() if spec.evaluation else {},
                 'investigation_spec':spec.to_dict(),'artifacts':frozen.data['artifacts'],'models':frozen.data['models'],'locators':{},'frozen_hypotheses':frozen.to_dict(),
                 'confirmation_population':inspection['_protected_population'],'history_binding':p.history}
        private['memberships']=memberships;private['population_event_hashes']={'H':[digest([spec.roles.namespace,p.keys[i]]) for i in indices]}
        if p.history:private['workspace_path']=p.history['workspace_path']
        p.verify();return InvestigationResult(data,private,{'status':'completed','peak_workspace_bytes':p.work.peak,'duration_seconds':time.monotonic()-started}).seal()


def confirm_investigation(frozen,config=None,*,confirmation_input=None,allowed_roots=None,workspace=None,expected_fingerprint=None,request_id=None,progress=None,cancel=None,_required_population=None,_scheduled=None,_numerical_extension=None):
    from .investigation import arguments
    from . import compat
    from .evidence_use import EvidenceUseLedger,record_session
    frozen,spec=_input(frozen,confirmation_input);spec,config,roots=arguments(spec,_configuration(frozen,config),allowed_roots)
    import time
    started=time.monotonic();deadline=started+config.max_seconds
    inspection=inspect_confirmation(frozen,config,confirmation_input=confirmation_input,allowed_roots=roots,workspace=workspace,progress=progress,cancel=cancel,_protected=True,_deadline=deadline,_scheduled=_scheduled,_numerical_extension=_numerical_extension)
    if expected_fingerprint and inspection['fingerprint']!=expected_fingerprint:raise EvaluationError('Confirmation inspection is stale.','stale_confirmation')
    population=inspection['_protected_population'];reservation={'kind':'external_declaration_and_session_checks','cross_session_history_verified':False}
    from .investigation_contracts import InvestigationSpec
    spec=InvestigationSpec.from_dict(inspection['_effective_spec'])
    from .investigation import historical_workspace
    workspace=historical_workspace(spec,workspace)
    continuity=EvidenceUseLedger(workspace).status() if workspace is not None else None
    tracking=bool(continuity and continuity['enabled'])
    if _required_population is not None and population['population_digest']!=_required_population:raise EvaluationError('Numerical recomputation requires the identical reserved population and evidence snapshot.','numerical_retry_population_changed')
    admissible=(not inspection['admissibility_reasons'] and inspection['feasibility']['status']!='not_admitted' and
                any(not row['admissibility_reasons'] for row in inspection['membership']))
    if admissible:
        if _numerical_extension is not None:
            # One immutable budget per origin, reserved before H access. A crash
            # can resume the same attempt; an old parent cannot fork Monte Carlo
            # budgets after one child produces an inconvenient result.
            if tracking:
                EvidenceUseLedger(workspace).record('numerical_recomputation',events=population['events'],units=population['units'],
                    population_digest=population['population_digest'],family_digest=frozen.evidence_family_digest,
                    request_id='numerical:'+_numerical_extension.origin_analysis_digest,cancel=cancel,deadline=deadline,session_max_bytes=config.max_rss_bytes//8,
                    metadata={'origin_analysis_digest':_numerical_extension.origin_analysis_digest,'replicates':_numerical_extension.replicates,
                        'continuity_token':continuity.get('continuity_token'),'branch_id':continuity['branch_id']})
            else:record_session('numerical_recomputation',population['events'],population['units'],family=frozen.evidence_family_digest,
                population=population['population_digest'],max_bytes=config.max_rss_bytes//8,
                numerical_origin=_numerical_extension.origin_analysis_digest,numerical_replicates=_numerical_extension.replicates,workspace=workspace)
        if tracking:
            protocol=_protocol(frozen,_scheduled,_numerical_extension)
            reservation=EvidenceUseLedger(workspace).record('confirmation',events=population['events'],units=population['units'],
                population_digest=population['population_digest'],family_digest=frozen.evidence_family_digest,request_id=request_id,
                query_events=population.get('query_events'),
                study_id=protocol.study_id,alpha=protocol.batch_alpha,total_alpha=protocol.study_alpha,cancel=cancel,deadline=deadline,session_max_bytes=config.max_rss_bytes//8,
                metadata={'external_exposure':protocol.external_exposure,'declaration_author':protocol.declaration_author,'declaration_reason':protocol.declaration_reason,
                    'exposure_history_token':protocol.exposure_history_token,
                    'look_id':_scheduled['look']['id'] if _scheduled else None,'predeclared_look':_scheduled['look'] if _scheduled else None,
                    'initial_use_id':_scheduled['initial_use_id'] if _scheduled else None,
                    'restatement_schedule':[s.to_dict() for s in ConfirmationSpec.from_dict(frozen.data['confirmation_spec']).restatement_schedule]})
        else:record_session('confirmation',population['events'],population['units'],family=frozen.evidence_family_digest,population=population['population_digest'],max_bytes=config.max_rss_bytes//8,workspace=workspace)
    result=compat.supervise(_assess,(frozen,spec,config,roots,inspection,reservation,_scheduled,_numerical_extension),config,progress=progress,cancel=cancel,deadline=deadline)
    result.execution['end_to_end_seconds']=time.monotonic()-started
    result.execution['requested_operation_deadline_seconds']=config.max_seconds
    if workspace is not None:
        result.private['numerical_continuity']=reservation.get('continuity_context',continuity)
        result.private['evidence_workspace_path']=str(EvidenceUseLedger(workspace).catalog.root)
    return result.seal()


def retry_confirmation(prior,*,replicates,config=None,confirmation_input=None,workspace=None,allowed_roots=None,progress=None,cancel=None,request_id=None):
    """Linked numerical recomputation, never another independent experiment."""
    import copy
    from .contracts import digest,positive
    from .investigation_contracts import FrozenHypothesisSet
    from .investigation_result import InvestigationResult
    if not isinstance(prior,InvestigationResult) or prior.data['investigation']['stage']!='confirmation':raise EvaluationError('A protected prior confirmation assessment is required.','numerical_retry_origin')
    InvestigationResult.from_dict(prior.to_private_dict(),private=prior.private)
    positive(replicates,'replicates')
    allowed={'insufficient_tail_resolution','insufficient_nominal_tail_resolution','replication_budget_below_nominal_requirement',
             'inference_work_limit','inference_memory_admission','deadline_admission'}
    affected={a['hypothesis_id'] for a in prior.data['investigation']['assessments']
              if a['state']=='inconclusive' and set((a.get('reason') or '').split(','))<=allowed and a.get('reason')}
    if not affected:raise EvaluationError('Only recorded numerical insufficiency permits this retry. Statistical, support and independence failures require their own resolution.','numerical_retry_not_eligible')
    packet=copy.deepcopy(prior.private['frozen_hypotheses']);protocol=packet['confirmation_spec']
    if protocol['method']=='finite' or replicates<=prior.data['investigation']['feasibility']['effective_replicates']:raise EvaluationError('A numerical retry must increase the replication budget for the identical approximate estimator.','numerical_retry_budget')
    frozen=FrozenHypothesisSet(packet)
    origin_workspace=prior.private.get('evidence_workspace_path') or prior.private.get('workspace_path')
    if workspace is None and origin_workspace:
        from pathlib import Path
        from . import compat
        root=Path(origin_workspace).absolute()
        with compat.secure_open(root/'catalog.sqlite3',allowed_roots if allowed_roots is not None else (root,)):pass
        from .workspace import ReliabilityWorkspace
        workspace=ReliabilityWorkspace(root)
    if workspace is None and prior.private.get('numerical_continuity',{}).get('enabled'):
        raise EvaluationError('Attach the protected original workspace; omitting it cannot bypass durable retry history.','numerical_retry_provenance')
    if workspace is not None:
        from pathlib import Path
        from .evidence_use import EvidenceUseLedger
        if isinstance(workspace,(str,Path)):
            from .workspace import ReliabilityWorkspace
            workspace=ReliabilityWorkspace(workspace)
        if origin_workspace and Path(origin_workspace).resolve()!=workspace.path.resolve():raise EvaluationError('Numerical retries cannot switch the evidence workspace.','numerical_retry_provenance')
        stored=workspace.open(prior.data['analysis_id'])
        if stored.binding!=prior.binding:raise EvaluationError('The retained numerical origin differs.','numerical_retry_origin')
        ledger=EvidenceUseLedger(workspace);state=ledger.status();origin=prior.private.get('numerical_continuity',{})
        population=prior.private['confirmation_population']
        gaps=ledger.overlap(population['events'],population['units'],family_digest=frozen.evidence_family_digest,population_digest=population['population_digest'])
        if (not state['enabled'] or not origin.get('enabled') or state['branch_id']!=origin.get('branch_id') or
            state['continuity']!=origin.get('continuity') or state['continuity'] in {'incomplete','restore_unreconciled'} or
            state.get('continuity_token')!=origin.get('continuity_token') or
            any(r in {'exposure_history_incomplete','exposure_history_unavailable'} for r in gaps)):
            raise EvaluationError('Numerical-attempt continuity since the protected origin cannot be verified. Restored, deleted or missing history cannot reset retry budgets.','numerical_retry_provenance')
    scheduled=None
    if prior.data['investigation'].get('predeclared_restatement'):
        look_id=prior.data['investigation']['predeclared_restatement']['look']['id']
        _,_,scheduled,workspace=_scheduled_context(prior,look_id,workspace)
        if confirmation_input is None:confirmation_input=prior.private['investigation_spec']
    result=confirm_investigation(frozen,config or prior.private['config'],confirmation_input=confirmation_input,
        workspace=workspace,allowed_roots=allowed_roots,progress=progress,cancel=cancel,request_id=request_id,
        _required_population=prior.private['confirmation_population']['population_digest'],_scheduled=scheduled,
        _numerical_extension=_NumericalExtension(prior.binding['analysis_digest'],replicates))
    unchanged={a['hypothesis_id']:a for a in prior.data['investigation']['assessments'] if a['hypothesis_id'] not in affected}
    result.data['investigation']['assessments']=[copy.deepcopy(unchanged.get(a['hypothesis_id'],a)) for a in result.data['investigation']['assessments']]
    result.data['investigation']['numerical_recomputation']={'origin_analysis_id':prior.data['analysis_id'],'origin_analysis_digest':prior.binding['analysis_digest'],
        'affected_hypotheses':sorted(affected),'unchanged_hypotheses_reused':sorted(unchanged),'same_frozen_family':True,'same_population_and_snapshot':True,
        'draw_prefix':{'generator':'numpy.PCG64','seed':protocol['seed'],'previous_replicates':prior.data['investigation']['feasibility']['effective_replicates'],'new_replicates':replicates},
        'fresh_independent_evidence':False}
    return result.seal()


def _scheduled_context(prior,look_id,workspace):
    """Require local proof that this exact family/schedule preceded initial H."""
    from .investigation_result import InvestigationResult
    from .investigation_contracts import FrozenHypothesisSet
    from .evidence_use import EvidenceUseLedger
    from .history_contracts import instant,now
    from .investigation_replay import restatement_spec
    from dataclasses import replace
    if workspace is None or not isinstance(prior,InvestigationResult) or prior.data['investigation']['stage']!='confirmation':raise EvaluationError('Scheduled inference requires a retained protected confirmation and its workspace.','scheduled_restatement_provenance')
    if isinstance(workspace,(str,__import__('pathlib').Path)):
        from .workspace import ReliabilityWorkspace
        workspace=ReliabilityWorkspace(workspace)
    stored=workspace.open(prior.data['analysis_id'])
    if stored.binding!=prior.binding:raise EvaluationError('The retained original assessment differs.','scheduled_restatement_provenance')
    frozen=FrozenHypothesisSet.from_dict(prior.private['frozen_hypotheses']);protocol=ConfirmationSpec.from_dict(frozen.data['confirmation_spec'])
    look=next((entry for entry in protocol.restatement_schedule if entry.id==look_id),None)
    if look is None:raise EvaluationError('This look was not in the family frozen before initial H.','unplanned_confirmation_look')
    if instant(look.as_of)>instant(now()):raise EvaluationError('The predeclared outcome cutoff has not arrived.','scheduled_look_not_due')
    ledger=EvidenceUseLedger(workspace);state=ledger.status()
    if not state['enabled'] or state['continuity']=='incomplete':raise EvaluationError('Scheduled reuse requires uninterrupted protected tracking after the original reservation.','scheduled_restatement_provenance')
    origin=prior
    if not any(a.get('H_outcomes_disclosed') for a in prior.data['investigation']['assessments']) and prior.data['investigation'].get('predeclared_restatement'):
        origin=workspace.open(prior.data['investigation']['predeclared_restatement']['origin_analysis_id'])
    if not any(a.get('H_outcomes_disclosed') for a in origin.data['investigation']['assessments']):raise EvaluationError('The prior assessment did not establish an admitted original H use.','scheduled_restatement_provenance')
    uses=[f['payload'] for f in workspace.catalog.iter_facts('evidence_use')]
    initial=next((u for u in uses if u['kind']=='confirmation' and u.get('family_digest')==frozen.evidence_family_digest and u.get('metadata',{}).get('look_id') is None),None)
    schedule=[s.to_dict() for s in protocol.restatement_schedule]
    if initial is None or initial['branch_id']!=state['branch_id'] or initial.get('metadata',{}).get('restatement_schedule')!=schedule:raise EvaluationError('Original schedule/branch continuity cannot be verified; restored or incomplete histories cannot reset look allocations.','scheduled_restatement_provenance')
    context={'look':look.to_dict(),'initial_use_id':initial['id'],'memberships':prior.private['memberships'],
        'event_hashes':prior.private['population_event_hashes']['H'],'origin_analysis_id':prior.data['analysis_id'],'origin_analysis_digest':prior.binding['analysis_digest']}
    spec=restatement_spec(prior,look.as_of,'Predeclared inferential outcome restatement')
    spec=replace(spec,history={**spec.history,'workspace_path':str(workspace.path)})
    return frozen,spec,context,workspace


def inspect_restatement_confirmation(prior,look_id,config=None,*,workspace,allowed_roots=None,progress=None,cancel=None):
    frozen,spec,context,workspace=_scheduled_context(prior,look_id,workspace)
    return inspect_confirmation(frozen,config or prior.private['config'],confirmation_input=spec,workspace=workspace,
        allowed_roots=allowed_roots,progress=progress,cancel=cancel,_scheduled=context)


def restate_confirmation(prior,look_id,config=None,*,workspace,allowed_roots=None,progress=None,cancel=None,request_id=None,expected_fingerprint=None):
    frozen,spec,context,workspace=_scheduled_context(prior,look_id,workspace)
    return confirm_investigation(frozen,config or prior.private['config'],confirmation_input=spec,workspace=workspace,
        allowed_roots=allowed_roots,progress=progress,cancel=cancel,request_id=request_id,expected_fingerprint=expected_fingerprint,_scheduled=context)
