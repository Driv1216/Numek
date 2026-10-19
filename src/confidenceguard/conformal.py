"""Exact split conformal scores and inversions, with no hidden set enlargement."""
from decimal import Decimal, ROUND_CEILING
from fractions import Fraction
import math
import numpy as np
from .contracts import EvaluationError
from .calibration import MethodUnavailable

VERSIONS={'lac':'lac_inclusive_v1','aps':'aps_cumulative_deterministic_v1',
          'raps':'raps_cumulative_deterministic_v1','split':'absolute_split_v1',
          'normalized':'positive_scale_split_v1','cqr':'signed_cqr_v1'}


def value_state(value=None,*,state=None,reason=None):
    if value is not None and math.isnan(value):
        if state not in (None,'undefined'):
            raise EvaluationError('NaN requires an undefined numeric state.','invalid_value_state')
        state='undefined';reason=reason or 'not_a_number'
    if state is None:
        state='undefined' if value is None else 'finite' if math.isfinite(value) else 'positive_infinity' if value>0 else 'negative_infinity'
    out={'value':float(value) if state=='finite' else None,'value_state':state}
    if reason: out['reason']=reason
    return out


def read_value(value,*,allowed=('finite','positive_infinity','negative_infinity','undefined')):
    if not isinstance(value,dict) or set(value)-{'value','value_state','reason'} or value.get('value_state') not in allowed or 'value' not in value:
        raise EvaluationError('Invalid safe numeric value.','invalid_value_state')
    state=value['value_state']; v=value['value']
    if state=='finite':
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v): raise EvaluationError('Finite state requires a finite number.','invalid_value_state')
        return float(v)
    if v is not None: raise EvaluationError('Extended numeric states require null values.','invalid_value_state')
    return math.inf if state=='positive_infinity' else -math.inf if state=='negative_infinity' else None


def rank(n,coverage):
    from .method_contracts import level
    if isinstance(n,bool) or not isinstance(n,int) or not 1<=n<2**63: raise MethodUnavailable('Conformal support must be a positive bounded record count.','empty_conformal_population')
    fraction=Fraction(Decimal(level(coverage)))
    return ((n+1)*fraction.numerator+fraction.denominator-1)//fraction.denominator


def thresholds(con,table,levels,check):
    n=con.execute(f'SELECT count(*) FROM {table}').fetchone()[0]
    if not n: raise MethodUnavailable('No common conformal calibration scores.','empty_conformal_population')
    bad=con.execute(f'SELECT count(*) FROM {table} WHERE score IS NULL OR NOT isfinite(score)').fetchone()[0]
    if bad: raise MethodUnavailable('Nonrepresentable scores cannot become unbounded thresholds.','numerical_conformal_score')
    output=[]
    for coverage in levels:
        check('exact conformal order statistic'); k=rank(n,coverage)
        q=math.inf if k==n+1 else con.execute(f'SELECT score FROM {table} ORDER BY score LIMIT 1 OFFSET ?',[k-1]).fetchone()[0]
        output.append({'coverage':coverage,'n':n,'rank':k,'threshold':value_state(q)})
    return output


def class_scores(p,kind,penalty=0.,k_reg=0):
    p=np.asarray(p,dtype=float)
    if kind=='lac': return 1-p
    # Stable sort gives declared class order for ties, independently of labels.
    order=np.argsort(-p,axis=1,kind='stable')
    sorted_p=np.take_along_axis(p,order,axis=1)
    cumulative=np.cumsum(sorted_p,axis=1)
    if kind=='raps': cumulative=cumulative+penalty*np.maximum(np.arange(1,p.shape[1]+1)-k_reg,0)
    return np.take_along_axis(cumulative,np.argsort(order,axis=1),axis=1)


def score(spec,*,p=None,y=None,point=None,scale=None,lower=None,upper=None):
    with np.errstate(over='ignore',invalid='ignore',divide='ignore'):
        if spec.kind in {'lac','aps','raps'}:
            scores=class_scores(p,spec.kind,spec.penalty,spec.k_reg)
            result=scores[np.arange(len(y)),y]
        elif spec.kind=='split': result=np.abs(np.asarray(y)-point)
        elif spec.kind=='normalized': result=np.abs(np.asarray(y)-point)/scale
        else: result=np.maximum(lower-np.asarray(y),np.asarray(y)-upper)
    if not np.all(np.isfinite(result)): raise MethodUnavailable('Unrepresentable conformity score.','numerical_conformal_score')
    return result


def construct(spec,fitted,*,p=None,point=None,scale=None,lower=None,upper=None):
    q=read_value(fitted['threshold'],allowed=('finite','positive_infinity'))
    if spec.kind in {'lac','aps','raps'}:
        selected=class_scores(np.asarray(p)[None,:],spec.kind,spec.penalty,spec.k_reg)[0]<=q
        indices=np.flatnonzero(selected).tolist()
        return {'state':'full' if len(indices)==len(p) else 'empty' if not indices else 'finite','members':indices,'size':len(indices)}
    if math.isinf(q):
        return {'state':'unbounded','lower':value_state(-math.inf),'upper':value_state(math.inf),'width':value_state(math.inf)}
    if spec.kind=='cqr': lo,hi=lower-q,upper+q
    else:
        delta=q*(scale if spec.kind=='normalized' else 1.)
        lo,hi=point-delta,point+delta
    if not math.isfinite(lo) or not math.isfinite(hi): raise MethodUnavailable('Interval arithmetic overflow.','numerical_transformation')
    if lo>hi:
        return {'state':'empty','lower':None,'upper':None,'width':value_state(0.),'reason':'signed_cqr_inversion_empty'}
    width=hi-lo
    if not math.isfinite(width): raise MethodUnavailable('Width overflow is not an unbounded conformal threshold.','numerical_transformation')
    return {'state':'finite','lower':value_state(lo),'upper':value_state(hi),'width':value_state(width)}


def validate_output(output,classes=None):
    if not isinstance(output,dict): raise EvaluationError('Invalid uncertainty output.')
    state=output.get('state')
    if classes is not None:
        members=output.get('members')
        if state=='unavailable':
            if members is not None: raise EvaluationError('Unavailable sets cannot contain labels.')
            return
        if state not in {'finite','empty','full'} or not isinstance(members,list) or members!=sorted(set(members)) or any(isinstance(v,bool) or not isinstance(v,int) or not 0<=v<classes for v in members) or output.get('size')!=len(members): raise EvaluationError('Invalid prediction set.')
        if (state=='empty')!=(len(members)==0) or (state=='full')!=(len(members)==classes): raise EvaluationError('Prediction-set state differs from membership.')
    elif state=='finite':
        lo=read_value(output.get('lower'),allowed=('finite',)); hi=read_value(output.get('upper'),allowed=('finite',)); w=read_value(output.get('width'),allowed=('finite',))
        if lo>hi or not math.isclose(hi-lo,w,rel_tol=1e-12,abs_tol=1e-12): raise EvaluationError('Invalid finite interval.')
    elif state=='unbounded':
        read_value(output.get('lower'),allowed=('negative_infinity',)); read_value(output.get('upper'),allowed=('positive_infinity',)); read_value(output.get('width'),allowed=('positive_infinity',))
    elif state=='empty':
        if output.get('lower') is not None or output.get('upper') is not None or read_value(output.get('width'),allowed=('finite',))!=0: raise EvaluationError('Invalid empty interval.')
    elif state=='unavailable':
        if output.get('width') is not None: raise EvaluationError('Unavailable intervals do not have zero width.')
    else: raise EvaluationError('Invalid interval state.')
