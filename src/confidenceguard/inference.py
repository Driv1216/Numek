"""Paired fixed-artifact bootstrap with explicit statistical/computational admission."""
import math
from decimal import Decimal,ROUND_CEILING
import numpy as np
from .contracts import EvaluationError


def preflight(spec,records,units,family_size,*,ranked=False,available_bytes=2*1024**3,remaining_seconds=None):
    m=max(1,family_size) if spec.adjustment=='bonferroni' else 1
    tail_decimal=(Decimal(1)-Decimal(str(spec.confidence)))/(2*m)
    tail=float(tail_decimal)
    minimum=int((Decimal(spec.minimum_tail)/tail_decimal).to_integral_value(rounding=ROUND_CEILING))
    # One contribution scan and bootstrap weight reduction per metric/unit; ranking
    # additionally scans all event scores. No quadratic jackknife is admitted.
    work=spec.replicates*(records*4 if ranked else units*4)+records*4+units*4+(math.ceil(2*records*math.log2(max(2,records))) if ranked else 0)
    memory=records*(64 if ranked else 32)+units*32+spec.replicates*8
    reasons=[]
    if spec.mode=='descriptive':reasons.append('descriptive_requested')
    if units<3:reasons.append('insufficient_independent_units')
    if spec.replicates<minimum:reasons.append('insufficient_tail_resolution')
    if work>spec.work_units:reasons.append('inference_work_limit')
    if memory>available_bytes:reasons.append('inference_memory_admission')
    if remaining_seconds is not None and remaining_seconds<=0:reasons.append('deadline_admission')
    return {'status':'admitted' if not reasons else 'not_admitted','reasons':reasons,
            'work_accounting_version':'paired_bootstrap_reductions_v1','records':records,'independent_units':units,
            'family_size':family_size,'effective_family_size':m,'adjustment':spec.adjustment,'confidence':spec.confidence,
            'nominal_tail_probability':tail,'minimum_tail_observations':spec.minimum_tail,
            'requested_replicates':spec.replicates,'minimum_nominal_replicates':minimum,
            'estimated_work_units':work,'estimated_memory_bytes':memory,'estimated_memory_is_upper_bound':False,
            'remaining_seconds_at_admission':remaining_seconds,
            'conditioning':'Frozen fitted methods; excludes training, fitting and selection variability.',
            'resolution_rule':'Engineering Monte Carlo resolution rule, not a confidence-interval accuracy theorem.'}


def ratio_stat(totals,root=False):
    if totals[1]<=0 or totals[3]<=0:return math.nan
    a,b=totals[0]/totals[1],totals[2]/totals[3]
    if root:
        if a<0 or b<0:return math.nan
        a,b=math.sqrt(a),math.sqrt(b)
    return b-a


def rank_stat(y,left,right,metric):
    """Pre-group tied scores once; replicate weights preserve whole tied groups."""
    def plan(scores):
        _,groups=np.unique(scores,return_inverse=True)
        return groups,int(groups.max())+1
    plans=[plan(left),plan(right)]
    def side(weights,p):
        groups,k=p
        positive=np.bincount(groups,weights=weights*y,minlength=k)
        counts=np.bincount(groups,weights=weights,minlength=k)
        total=positive.sum(); negative=counts.sum()-total
        if total<=0 or negative<=0:return math.nan
        if metric=='roc_auc':
            neg=counts-positive; before=np.cumsum(neg)-neg
            return float(np.sum(positive*(before+.5*neg))/total/negative)
        positive=positive[::-1]; counts=counts[::-1]
        cp=np.cumsum(positive); cn=np.cumsum(counts)
        return float(np.sum(np.divide(positive*cp,cn,out=np.zeros_like(cp),where=cn>0))/total)
    def statistic(weights):return side(weights,plans[1])-side(weights,plans[0])
    return statistic


def bootstrap(contributions,spec,*,family_size,check,clusters=None,ranked=None,available_bytes=2*1024**3,remaining_seconds=None):
    """Smooth input columns are left numerator/denominator, right numerator/denominator.

    Clusters are explicit integer unit indices. For smooth statistics callers may
    supply preaggregated cluster contributions, avoiding an event-sized replicate.
    Ranked input is (y,left_score,right_score); events remain together by cluster.
    """
    values=np.asarray(contributions,dtype=float); n=len(values)
    if clusters is None: unit_index=None; units=n
    else:
        clusters=np.asarray(clusters)
        if len(clusters)!=n:raise EvaluationError('Cluster assignments differ from the paired base.')
        _,unit_index=np.unique(clusters,return_inverse=True);units=int(unit_index.max())+1 if n else 0
    admission=preflight(spec,n,units,family_size,ranked=bool(ranked),available_bytes=available_bytes,remaining_seconds=remaining_seconds)
    if admission['status']!='admitted':
        if spec.inference_required:raise EvaluationError('Required inference could not be admitted.','inference_not_admitted')
        return {**admission,'execution':'not_run'}
    if not np.all(np.isfinite(values)):
        return {**admission,'status':'unavailable','execution':'not_run','reason':'nonfinite_statistic_input'}
    if ranked:
        y,left,right=values.T; statistic=rank_stat(y,left,right,ranked)
        estimate=statistic(np.ones(n)); method='paired_percentile'
        unit_values=None
    else:
        if values.ndim!=2 or values.shape[1]!=4:raise EvaluationError('Invalid paired contributions.')
        if unit_index is not None:
            unit_values=np.zeros((units,4))
            for col in range(4):unit_values[:,col]=np.bincount(unit_index,weights=values[:,col],minlength=units)
        else:unit_values=values
        totals=unit_values.sum(axis=0)
        statistic=lambda weights: ratio_stat(weights@unit_values)
        estimate=ratio_stat(totals); method='paired_bca'
    return _replicates(spec,admission,units,n,unit_index,statistic,estimate,unit_values,method,check)


def smooth_bootstrap(contributions,spec,*,family_size,check,root=False,available_bytes=2*1024**3,remaining_seconds=None):
    values=np.asarray(contributions,dtype=float);n=len(values)
    admission=preflight(spec,n,n,family_size,available_bytes=available_bytes,remaining_seconds=remaining_seconds)
    if admission['status']!='admitted':
        if spec.inference_required:raise EvaluationError('Required inference could not be admitted.','inference_not_admitted')
        return {**admission,'execution':'not_run'}
    if values.ndim!=2 or values.shape[1]!=4 or not np.all(np.isfinite(values)):
        return {**admission,'status':'unavailable','execution':'not_run','reason':'nonfinite_statistic_input'}
    statistic=lambda weights:ratio_stat(weights@values,root)
    return _replicates(spec,admission,n,n,None,statistic,ratio_stat(values.sum(axis=0),root),values,'paired_bca',check,root=root)


def _replicates(spec,admission,units,n,unit_index,statistic,estimate,unit_values,method,check,root=False):
    if not math.isfinite(estimate):return {**admission,'status':'unavailable','execution':'not_run','reason':'undefined_original_statistic'}
    rng=np.random.Generator(np.random.PCG64(spec.seed)); draws=np.empty(spec.replicates)
    probabilities=np.full(units,1/units)
    invalid=0
    for i in range(spec.replicates):
        if i%16==0:check('paired bootstrap replicate batch')
        weights=rng.multinomial(units,probabilities)
        if unit_index is not None and method=='paired_percentile':weights=weights[unit_index]
        draws[i]=statistic(weights)
        invalid+=int(not math.isfinite(draws[i]))
    base={**admission,'execution':'completed','completed_replicates':spec.replicates,'invalid_replicates':invalid,
          'rng':'numpy.PCG64','seed':spec.seed,'method':method,'estimate':estimate,
          'quantile_convention':'numpy_linear','tail_resolution_validated':False}
    if invalid:return {**base,'status':'unavailable','reason':'undefined_bootstrap_replicates'}
    if np.all(draws==draws[0]):return {**base,'status':'unavailable','reason':'degenerate_bootstrap_distribution'}
    tail=admission['nominal_tail_probability']; lower=tail;upper=1-tail
    if method=='paired_bca':
        try:
            from scipy.special import ndtr,ndtri
        except ImportError:
            return {**base,'status':'unavailable','reason':'statistics_unavailable'}
        check('exact sufficient-statistic jackknife')
        totals=unit_values.sum(axis=0)
        jack=np.array([ratio_stat(totals-v,root) for v in unit_values])
        if not np.all(np.isfinite(jack)):return {**base,'status':'unavailable','reason':'undefined_jackknife'}
        deviations=jack.mean()-jack;scale=np.max(np.abs(deviations))
        if not scale:return {**base,'status':'unavailable','reason':'degenerate_jackknife'}
        d=deviations/scale; denominator=6*float(np.sum(d*d))**1.5
        acceleration=float(np.sum(d*d*d))/denominator
        fraction=(np.count_nonzero(draws<estimate)+.5*np.count_nonzero(draws==estimate))/len(draws)
        if not 0<fraction<1:return {**base,'status':'unavailable','reason':'undefined_bias_correction'}
        z0=float(ndtri(fraction)); zs=ndtri([lower,upper]); den=1-acceleration*(z0+zs)
        if np.any(den<=0):return {**base,'status':'unavailable','reason':'invalid_bca_tail_transform'}
        lower,upper=map(float,ndtr(z0+(z0+zs)/den))
        base.update(acceleration=acceleration,bias_correction=z0)
    base.update(adjusted_lower_probability=lower,adjusted_upper_probability=upper)
    if not 0<lower<upper<1 or spec.replicates*lower<spec.minimum_tail-1e-10 or spec.replicates*(1-upper)<spec.minimum_tail-1e-10:
        p=min(lower,1-upper)
        return {**base,'status':'unavailable','reason':'insufficient_tail_resolution',
                'recommended_replicates':math.ceil(spec.minimum_tail/p) if p>0 else None,
                'recommendation_is_guarantee':False}
    lo,hi=map(float,np.quantile(draws,[lower,upper],method='linear'))
    return {**base,'status':'available','lower':lo,'upper':hi,'level':spec.confidence,
            'tail_resolution_validated':True,'scope':'conditional_on_frozen_artifacts',
            'cluster_warning':spec.mode=='independent_clusters' and units<30,
            'small_cluster_warning_is_heuristic':True}
