"""Validation-only fixed-n score inversion with a known variance upper bound.

Not registered in the product. The bound is an external population assumption,
never an observed variance/extremum or a fitted diagnostic target. No sequential,
adaptive-reuse, monitoring or unknown-variance guarantee is provided.
"""
import math
import numpy as np

METHOD='fixed_n_catoni_variance_bound_candidate_v1'


def influence(values):
    values=np.asarray(values,dtype=float);magnitude=np.abs(values);output=np.empty_like(values)
    small=magnitude<=1;v=magnitude[small]
    output[small]=np.log1p(v+.5*v*v)
    v=magnitude[~small];inverse=1/v
    output[~small]=2*np.log(v)+np.log(.5+inverse+inverse*inverse)
    return np.copysign(output,values)


def mean_interval(values,*,variance_bound,alpha=.05,max_iterations=256,relative_tolerance=1e-12,
                  work_budget=100_000_000,check=lambda *args:None):
    """Invert both fixed-time exponential inequalities at their frozen allocation.

    With fixed lambda and population Var(X)<=v, E exp(+-sum psi(lambda*(X-mu)))
    <= exp(n*lambda**2*v/2). Markov + two tails gives the confidence set below.
    The numerical translation does not change lambda or infer a variance bound.
    """
    raw=np.asarray(values);n=raw.size
    base={'method':METHOD,'status':'unavailable','units':n,'allocated_alpha':alpha,
          'declared_variance_upper_bound':variance_bound,'product_enabled':False,
          'assumptions':'IID complete sampling units with a population variance bounded by the supplied, justified a priori value. No variance-bound estimation is performed.'}
    if raw.ndim!=1 or raw.dtype.kind not in 'biuf' or not n or not np.isfinite(raw).all():return {**base,'reason':'invalid_original_contributions'}
    if type(variance_bound) not in {int,float} or not math.isfinite(variance_bound) or variance_bound<=0:return {**base,'reason':'positive_known_variance_bound_required'}
    if type(alpha) not in {int,float} or not math.isfinite(alpha) or not 0<alpha<1 or 1-alpha==1:return {**base,'reason':'unresolved_error_allocation'}
    if type(max_iterations) is not int or max_iterations<1 or not 0<relative_tolerance<1:raise ValueError('Invalid frozen numerical profile.')
    estimated_work=n*(2*max_iterations+128)
    if estimated_work>work_budget:return {**base,'reason':'numerical_work_admission','estimated_work':estimated_work}
    raw=raw.astype(float,copy=False);center=float(np.partition(raw,(n-1)//2)[(n-1)//2]);scale=math.sqrt(variance_bound)
    with np.errstate(over='ignore',invalid='ignore',divide='ignore'):
        normalized=(raw-center)/scale
        if not np.isfinite(normalized).all():normalized=raw/scale-center/scale
    if not np.isfinite(normalized).all():return {**base,'reason':'normalization_numeric_range'}
    log_tail=math.log(2/alpha);lam=math.sqrt(2*log_tail/n)
    threshold=n*lam*lam*(variance_bound/scale/scale)/2+log_tail;calls=0
    # This conservative floating-point allowance is engineering qualification,
    # not a claim of formally verified interval arithmetic.
    def score(point):
        nonlocal calls
        calls+=1
        if calls*n>work_budget:raise ArithmeticError('score_work_budget')
        if calls%8==1:check('fixed-time variance-bound score inversion')
        with np.errstate(over='ignore',invalid='ignore'):
            terms=influence(lam*(normalized-point))
        if not np.isfinite(terms).all():raise ArithmeticError('score_numeric_range')
        guard=64*np.finfo(float).eps*n*(1+float(np.max(np.abs(terms))))
        return float(np.sum(terms)),guard
    # Wide fixed brackets avoid a data-dependent choice of lambda. They use
    # sample coordinates only to find numerical roots of the same fixed score.
    left=min(float(normalized.min()),0.)-1;right=max(float(normalized.max()),0.)+1
    try:
        for _ in range(64):
            lo,lg=score(left);hi,hg=score(right)
            if lo-lg>=threshold and hi+hg<=-threshold:break
            if lo-lg<threshold:left=2*left-1
            if hi+hg>-threshold:right=2*right+1
            if not math.isfinite(left) or not math.isfinite(right):raise ArithmeticError('root_bracket_numeric_range')
        else:raise ArithmeticError('root_bracket_budget')
        def root(target,lower):
            a,b=left,right
            for _ in range(max_iterations):
                middle=a/2+b/2
                if middle==a or middle==b or b-a<=relative_tolerance*(1+abs(middle)):return a if lower else b
                value,guard=score(middle)
                # Widen the confidence set for possible score rounding error.
                value=value-guard if lower else value+guard
                if value>=target:a=middle
                else:b=middle
            raise ArithmeticError('root_resolution_budget')
        lower=root(threshold,True);upper=root(-threshold,False)
        with np.errstate(over='ignore',invalid='ignore'):
            lower=float(np.nextafter(center+scale*lower,-np.inf));upper=float(np.nextafter(center+scale*upper,np.inf))
        if not math.isfinite(lower) or not math.isfinite(upper) or lower>upper:raise ArithmeticError('interval_numeric_range')
    except ArithmeticError as error:return {**base,'reason':str(error),'score_evaluations':calls,'estimated_work':estimated_work}
    return {**base,'status':'available','lower':lower,'upper':upper,'score_evaluations':calls,
            'lambda_in_declared_standard_deviation_units':lam,'score_threshold':threshold,
            'numerical_profile':{'max_iterations_per_root':max_iterations,'relative_tolerance':relative_tolerance,
                                 'guard':'64 * binary64 epsilon * n * (1 + largest absolute score term)',
                                 'outward_endpoint_rounding':True},
            'scope':'Experimental fixed-time scalar mean interval under the declared true variance bound. Finite-sample mathematics is conditional on assumptions; numerical implementation and ratio composition still require qualification.'}


def contrast_interval(contributions,*,variance_bounds,family_size=1,alpha=.05,ceiling=None,
                      transform='identity',nonnegative_numerator=False,work_budget=100_000_000,check=lambda *args:None):
    """Validation-only Bonferroni boxes for the frozen event-weighted ratio means.

    Four unit-level columns have the same meaning as the bootstrap candidate:
    comparator numerator/denominator then member numerator/denominator. Whole
    entities must already be aggregated. Bounds concern these unit contributions,
    including their zeroes, not the conditional variance of individual losses.
    """
    values=np.asarray(contributions)
    base={'method':METHOD+'_ratio_composition','status':'unavailable','product_enabled':False,
          'family_size':family_size,'study_alpha':alpha,'transform':transform,
          'declared_variance_bounds':variance_bounds}
    if type(family_size) is not int or not 1<=family_size<=32 or not 0<alpha<1:raise ValueError('Invalid frozen error family.')
    if values.ndim!=2 or values.shape[1]!=4 or values.dtype.kind not in 'biuf' or not np.isfinite(values).all():return {**base,'reason':'invalid_original_contributions'}
    if (values[:,(1,3)]<0).any() or any(np.any((values[:,d]==0)&(values[:,a]!=0)) for a,d in ((0,1),(2,3))):return {**base,'reason':'invalid_unit_denominator_contributions'}
    if transform not in {'identity','lower','absolute','sqrt'}:raise ValueError('Unregistered fixed transform.')
    if transform=='sqrt' and (not nonnegative_numerator or (values[:,(0,2)]<0).any()):return {**base,'reason':'known_nonnegative_numerator_required'}
    if ceiling is not None and (type(ceiling) not in {int,float} or not math.isfinite(ceiling)):raise ValueError('Finite fixed comparator required.')
    columns=(2,3) if ceiling is not None else (0,1,2,3)
    if type(variance_bounds) not in {tuple,list} or len(variance_bounds)!=len(columns):return {**base,'reason':'all_required_variance_bounds_must_be_declared'}
    allocation=alpha/family_size/len(columns);components={}
    for column,bound in zip(columns,variance_bounds):
        components[column]=mean_interval(values[:,column],variance_bound=bound,alpha=allocation,
            work_budget=work_budget//len(columns),check=check)
    base.update(elementary_intervals=len(columns),component_alpha=allocation,
                components={str(k):v for k,v in components.items()})
    if any(c['status']!='available' for c in components.values()):return {**base,'reason':'component_interval_unavailable'}
    def ratio(numerator,denominator):
        a=components[numerator];b=components[denominator]
        if b['lower']<=0:raise ArithmeticError('population_denominator_not_separated_from_zero')
        values=[a[key]/b[other] for key in ('lower','upper') for other in ('lower','upper')]
        lo,hi=min(values),max(values)
        if not math.isfinite(lo) or not math.isfinite(hi):raise ArithmeticError('ratio_numeric_range')
        if transform=='sqrt':return math.sqrt(max(0,lo)),math.sqrt(max(0,hi))
        if transform=='lower':return -hi,-lo
        if transform=='absolute':return (0. if lo<=0<=hi else min(abs(lo),abs(hi))),max(abs(lo),abs(hi))
        return lo,hi
    try:
        member=ratio(2,3)
        if ceiling is None:comparison=ratio(0,1)
        else:
            value=-ceiling if transform=='lower' else abs(ceiling) if transform=='absolute' else ceiling
            comparison=(value,value)
        lower=member[0]-comparison[1];upper=member[1]-comparison[0]
        if not math.isfinite(lower) or not math.isfinite(upper):raise ArithmeticError('contrast_numeric_range')
    except ArithmeticError as error:return {**base,'reason':str(error)}
    return {**base,'status':'available','lower':lower,'upper':upper,
        'scope':'Experimental fixed-hypothesis confidence composition under justified true unit-contribution variance bounds and IID complete units. Sampling weights/metric semantics are supplied by the authoritative reducer; this prototype does not redefine them.'}
