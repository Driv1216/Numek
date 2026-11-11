"""Finite root and bounded-cluster inference; no bootstrap promotion."""
import math
from collections import Counter,defaultdict
import numpy as np

from ..contracts import EvaluationError
from ..confirmation import binomial_interval,bounded_interval


def cluster_ratio(numerators,denominators,*,max_size,bounds,alpha):
    """IID complete clusters, event weighting E(sum X)/E(count).

    For n_u<=M, A_u/M lies in [min(0,a),max(0,b)] and D_u/M
    in [0,1]. Simultaneous Hoeffding components bound the ratio without
    treating events or generated variants as independent observations.
    """
    if type(max_size) is not int or max_size<1 or not 0<alpha<1 or len(bounds)!=2 or not np.isfinite(bounds).all() or bounds[0]>bounds[1]:raise EvaluationError('Invalid finite cluster protocol.','cluster_protocol')
    a=np.asarray(numerators,float);d=np.asarray(denominators,float)
    if len(a)!=len(d) or not len(a) or not np.isfinite(a).all() or not np.isfinite(d).all() or np.any(d<0) or np.any(d>max_size) or np.any(d!=np.floor(d)):raise EvaluationError('True cluster size bound violated.','cluster_size_bound')
    lo,hi=bounds
    if np.any(a<d*lo) or np.any(a>d*hi):raise EvaluationError('Cluster contribution bounds violated.','contribution_bounds_violated')
    ni=bounded_interval(a/max_size,(min(0,lo),max(0,hi)),alpha/2)
    di=bounded_interval(d/max_size,(0.,1.),alpha/2)
    if di[0]<=0:return {'state':'insufficient_support','reason':'denominator_not_bounded_away_from_zero','components':{'numerator':ni,'denominator':di}}
    endpoints=[x/y for x in ni for y in di]
    return {'state':'available','lower':max(lo,min(endpoints)),'upper':min(hi,max(endpoints)),
            'estimate':float(a.sum()/d.sum()),'method':'bounded_cluster_ratio_hoeffding_v1','independent_units':len(a),
            'components':{'numerator':ni,'denominator':di},'max_cluster_size':max_size,
            'estimand':'event_weighted_ratio_of_cluster_expectations'}


def assess(values,entities,claim,protocol,family_size,*,potential_entities=None):
    values=np.asarray(values,float);alpha=(1-protocol.confidence)/family_size
    base={'id':claim.id,'predictor':claim.predictor,'scenario':claim.scenario,'metric':claim.metric,'operator':claim.operator,
          'threshold':claim.threshold,'family_size':family_size,'allocated_alpha':alpha,'support':len(values),'state':'refused'}
    if len(values)<claim.minimum_support:return {**base,'state':'insufficient_support','reason':'claim_support_floor'}
    indicator=claim.metric in {'flip_rate','output_failure_rate','metamorphic_violation','attack_success'}
    scenario=next(s for s in protocol.study.scenarios if s.id==claim.scenario)
    # Root averages of several indicators are bounded means, not Bernoulli
    # trials. Select the kernel from the frozen design, never observed values.
    bernoulli=indicator and scenario.replicates==1
    bounds=claim.bounds or ((0.,1.) if indicator or claim.metric=='probability_max_change' else (-1.,1.) if claim.metric in {'confidence_delta','confidently_wrong_transition'} or claim.metric.startswith(('coverage_delta@','uncertainty_availability_delta@')) else None)
    if bounds is None:return {**base,'reason':'true_contribution_bounds_required'}
    if not np.isfinite(values).all() or np.any(values<bounds[0]) or np.any(values>bounds[1]):return {**base,'reason':'contribution_bounds_violated'}
    if protocol.sampling=='independent_roots':
        potential=potential_entities if potential_entities is not None else entities
        if len(set(potential))!=len(potential):return {**base,'reason':'repeated_entities_before_label_filter'}
        interval=binomial_interval(values,alpha) if bernoulli else bounded_interval(values,bounds,alpha)
        out={'lower':interval[0],'upper':interval[1],'estimate':float(values.mean()),'method':'clopper_pearson' if bernoulli else 'paired_bounded_mean_hoeffding'}
    else:
        if protocol.max_cluster_size is None:return {**base,'reason':'true_maximum_cluster_size_required'}
        if potential_entities is not None and any(n>protocol.max_cluster_size for n in Counter(potential_entities).values()):return {**base,'reason':'cluster_size_bound_before_label_filter'}
        totals=defaultdict(float);counts=Counter(entities)
        for v,u in zip(values,entities):totals[u]+=v
        units=sorted(counts);numerators=[totals[k] for k in units];denominators=[counts[k] for k in units]
        try:out=cluster_ratio(numerators,denominators,max_size=protocol.max_cluster_size,bounds=bounds,alpha=alpha)
        except EvaluationError as exc:return {**base,'reason':exc.code}
        if out['state']!='available':return {**base,**out}
    lo,hi=out['lower'],out['upper'];threshold=claim.threshold
    state='supported' if hi<=threshold else 'contradicted' if lo>threshold else 'inconclusive'
    if claim.operator=='ge':state='supported' if lo>=threshold else 'contradicted' if hi<threshold else 'inconclusive'
    return {**base,**out,'state':state,'bounds':list(bounds),'evidence_level':'qualified_statistical_inference'}
