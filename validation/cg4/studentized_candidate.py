"""Experimental bootstrap-t for smooth loss means/ratios; not a product method.

Uses unit-level sufficient statistics and analytic influence variance, with
whole-unit resampling. See DiCiccio & Efron (1996), section 5, and boot::boot.ci.
Neither source establishes finite-sample coverage for arbitrary loss laws. Every
replicate must be defined; unstable pivots cause refusal, never replicate removal.
"""
from decimal import Decimal,ROUND_CEILING
import math
import numpy as np

METHOD='studentized_delta_candidate_v1'


def estimates(totals,moments,n,offsets,*,ceiling=None,root=False,sign=1.):
    totals=np.atleast_2d(totals);moments=np.asarray(moments).reshape(-1,4,4)
    gradient=np.zeros_like(totals);valid=np.ones(len(totals),bool);parts=[]
    with np.errstate(divide='ignore',invalid='ignore',over='ignore'):
        for numerator,denominator,offset,coefficient in ((0,1,offsets[0],-1.),(2,3,offsets[1],1.)):
            if numerator==0 and ceiling is not None:
                parts.append(np.full(len(totals),ceiling));continue
            count=totals[:,denominator];ratio=totals[:,numerator]/count;raw=offset+ratio
            valid&=count>0
            if root:
                valid&=raw>0;value=np.sqrt(raw);derivative=.5/value
            else:value=raw;derivative=np.ones(len(raw))
            parts.append(value)
            gradient[:,numerator]=sign*coefficient*derivative/count
            gradient[:,denominator]=-sign*coefficient*derivative*totals[:,numerator]/count**2
        theta=sign*(parts[1]-parts[0])
        # Ratio gradients are homogeneous of degree zero: g.T @ totals = 0.
        # Centering the numerator columns beforehand avoids cancellation between
        # huge common offsets in this equivalent covariance calculation.
        variance=n/(n-1)*np.einsum('bi,bij,bj->b',gradient,moments,gradient)
        scale=n/(n-1)*np.einsum('bi,bij,bj->b',np.abs(gradient),np.abs(moments),np.abs(gradient))
        se=np.sqrt(variance)
        valid&=np.isfinite(theta)&np.isfinite(se)&(variance>16*np.finfo(float).eps*scale)&(se>0)
    return theta,se,valid


def studentized(values,*,replicates=20000,alpha=.05,seed=0,ceiling=None,root=False,sign=1.,
                minimum_tail=20,work_budget=2_000_000_000,memory_bytes=512*1024**2,batch_size=256,check=lambda *args:None):
    """Columns: comparator numerator/denominator, member numerator/denominator.

    Inputs are already aggregated per independent entity when clustering applies.
    This preserves event-weighted ratio estimands rather than averaging entities.
    Absolute transformations require separately allocated interval composition and
    are deliberately outside this prototype's admission.
    """
    values=np.asarray(values);n=len(values) if values.ndim else 0
    base={'method':METHOD,'strength':'experimental_approximate','replicates':replicates,'alpha':alpha,
          'sampling_units':n,'seed':seed,'rng':'numpy.PCG64','quantile_convention':'numpy_linear'}
    if values.ndim!=2 or values.shape[1]!=4 or values.dtype.kind not in 'biuf' or n<3 or not np.isfinite(values).all():return {**base,'status':'unavailable','reason':'invalid_original_contributions'}
    values=values.astype(float,copy=False)
    if type(replicates) is not int or replicates<1 or type(batch_size) is not int or batch_size<1 or not 0<alpha<1:raise ValueError('Invalid fixed prototype budget.')
    tail=Decimal(str(alpha))/2;minimum=int((Decimal(minimum_tail)/tail).to_integral_value(rounding=ROUND_CEILING))
    if replicates<minimum:return {**base,'status':'unavailable','reason':'insufficient_nominal_tail_resolution','minimum_replicates':minimum}
    work=replicates*(n*24+128);memory=n*24*8+replicates*8;batch_memory=max(512,n*8*4)
    if work>work_budget or memory+batch_memory>memory_bytes:return {**base,'status':'unavailable','reason':'prototype_resource_admission','estimated_work':work,'estimated_bytes':memory}
    block=max(1,min(batch_size,(memory_bytes-memory)//batch_memory))
    centered=values.copy();offsets=[]
    for numerator,denominator in ((0,1),(2,3)):
        total=values[:,denominator].sum()
        if total<=0 and not (numerator==0 and ceiling is not None):return {**base,'status':'unavailable','reason':'undefined_original_statistic'}
        offset=float(values[:,numerator].sum()/total) if total>0 else 0.
        offsets.append(offset);centered[:,numerator]-=offset*centered[:,denominator]
    with np.errstate(over='ignore',invalid='ignore'):
        products=np.einsum('ni,nj->nij',centered,centered).reshape(n,16)
    if not np.isfinite(products).all():return {**base,'status':'unavailable','reason':'nonfinite_variance_contributions'}
    theta,se,valid=estimates(centered.sum(axis=0),products.sum(axis=0),n,offsets,ceiling=ceiling,root=root,sign=sign)
    if not valid[0]:return {**base,'status':'unavailable','reason':'undefined_original_standard_error'}
    theta=float(theta[0]);se=float(se[0]);pivots=np.empty(replicates);rng=np.random.Generator(np.random.PCG64(seed));invalid=0
    for start in range(0,replicates,block):
        check('studentized prototype replicate batch')
        size=min(block,replicates-start);weights=rng.multinomial(n,np.full(n,1/n),size=size)
        t,s,ok=estimates(weights@centered,weights@products,n,offsets,ceiling=ceiling,root=root,sign=sign)
        with np.errstate(divide='ignore',invalid='ignore',over='ignore'):pivot=(t-theta)/s
        ok&=np.isfinite(pivot);invalid+=int((~ok).sum());pivots[start:start+size]=pivot
    base.update(estimate=theta,standard_error=se,completed_replicates=replicates,invalid_replicates=invalid,
        estimated_work=work,variance_estimator='unit_influence_covariance_with_n_over_n_minus_one',batch_size=block,
        variance_resolution_factor=float(16*np.finfo(float).eps))
    if invalid:return {**base,'status':'unavailable','reason':'undefined_studentized_replicates'}
    if np.all(pivots==pivots[0]):return {**base,'status':'unavailable','reason':'degenerate_studentized_distribution'}
    qlo,qhi=map(float,np.quantile(pivots,[float(tail),1-float(tail)],method='linear'))
    lower=theta-qhi*se;upper=theta-qlo*se
    if not math.isfinite(lower) or not math.isfinite(upper) or lower>upper:return {**base,'status':'unavailable','reason':'nonfinite_studentized_interval'}
    return {**base,'status':'available','lower':lower,'upper':upper,'tail_resolution_validated':True,
        'scope':'Experimental frozen mean/ratio contrast; independent complete units; asymptotic regularity assumptions, no temporal or selective-label correction.'}
