"""Versioned probability maps. Objectives stream frozen fit batches; no model execution."""
import math
import hashlib
from pathlib import Path
import numpy as np
from .contracts import EvaluationError


class MethodUnavailable(EvaluationError):
    """An expected method/data incompatibility, distinct from an unexpected fault."""


VERSIONS = {'identity':'identity_v1', 'platt':'platt_monotone_smoothed_v1',
            'isotonic':'isotonic_pava_linear_v1', 'beta':'beta_monotone_identity_l2_v1',
            'temperature':'temperature_finite_v1', 'dirichlet':'dirichlet_identity_l2_v1'}


def scipy_special():
    try:
        from scipy.special import expit, logsumexp
        return expit, logsumexp
    except ImportError as exc:
        raise MethodUnavailable('This method requires the statistics extra.','statistics_unavailable') from exc


def sigmoid_log_probabilities(z):
    z=np.asarray(z,dtype=float)
    if not np.all(np.isfinite(z)):raise MethodUnavailable('Overflow cannot manufacture endpoint probabilities.','numerical_transformation')
    return np.stack((-np.logaddexp(0,z),-np.logaddexp(0,-z)),axis=-1)


def log_softmax(z):
    z=np.asarray(z,dtype=float)
    top=np.max(z,axis=-1,keepdims=True)
    with np.errstate(over='ignore',invalid='ignore',under='ignore'):
        shifted=z-top
        result=shifted-np.log(np.sum(np.exp(shifted),axis=-1,keepdims=True))
    if np.any(np.isfinite(z)&~np.isfinite(result)):
        raise MethodUnavailable('Finite logits produced an unrepresentable log probability.','numerical_transformation')
    if np.any(np.isnan(result)) or np.any(result==np.inf):
        raise MethodUnavailable('Unrepresentable log probability transformation.','numerical_transformation')
    return result


def _scalar(x,spec,positive):
    if spec.input=='score': return x[:,0]
    p=x[:,positive]
    if spec.input=='probability_logit':
        p=np.clip(p,spec.epsilon,1-spec.epsilon)
        return np.log(p)-np.log1p(-p)
    return p


def fit_calibrator(spec,task,batches,*,directory,check,connection=None,parameter_elements=1000000):
    """batches() yields (input matrix, integer class indices), never evaluation labels."""
    n=0; counts=np.zeros(len(task.classes),dtype=np.int64); endpoint_count=0
    pos=task.classes.index(task.positive_class) if task.positive_class else 1
    scalar_max=0.
    for x,y in batches():
        check('calibrator fit population scan'); n+=len(y); counts+=np.bincount(y,minlength=len(counts))
        if spec.kind=='dirichlet':endpoint_count+=int(np.count_nonzero((x<spec.epsilon)|(x>1-spec.epsilon)))
        elif spec.kind=='beta' or spec.input=='probability_logit':
            p=x[:,pos];endpoint_count+=int(np.count_nonzero((p<spec.epsilon)|(p>1-spec.epsilon)))
        if spec.kind in {'platt','isotonic'}:
            scalar_max=max(scalar_max,float(np.max(np.abs(_scalar(x,spec,pos)))))
    if not n: raise MethodUnavailable('No common fit population.','empty_fit_population')
    if spec.kind in {'platt','isotonic','beta'} and (len(counts)!=2 or np.any(counts==0)):
        raise MethodUnavailable('Binary calibration requires both classes.','insufficient_class_support')
    if spec.kind=='dirichlet' and np.any(counts==0):
        raise MethodUnavailable('Every declared class needs fit support.','insufficient_class_support')
    metadata={'fit_records':n,'class_counts':counts.tolist(),'log_preprocessing_cells':endpoint_count,
              'algorithm_version':VERSIONS[spec.kind], 'objective':'fit_mean_log_loss'}
    if spec.kind=='identity': return {},metadata
    if spec.kind=='isotonic':
        # External sorting and grouped PAVA are supplied by the caller's disk relation.
        return fit_isotonic(spec,batches,pos,directory,check,connection,parameter_elements),{**metadata,'objective':'fit_squared_error','interpolation':'linear','outside':'constant_endpoint'}
    try:
        from scipy.optimize import minimize
    except ImportError as exc:
        raise MethodUnavailable('Install the statistics extra for optimization.','statistics_unavailable') from exc
    mean=0.; sd=1.; scalar_scale=scalar_max or 1.
    if spec.kind=='platt':
        total=0.; squares=0.
        for x,y in batches():
            v=_scalar(x,spec,pos)/scalar_scale
            total+=float(np.sum(v)); squares+=float(np.sum(v*v))
        mean=total/n; sd=math.sqrt(max(0.,squares/n-mean*mean)) or 1.
    k=len(counts); projection=np.eye(k)-np.ones((k,k))/k
    ridge=spec.regularization if spec.regularization is not None else 1e-6
    if spec.kind=='platt': initial=np.array([1.,0.]); bounds=[(0,None),(None,None)]
    elif spec.kind=='beta': initial=np.array([1.,1.,0.]); bounds=[(0,None),(0,None),(None,None)]
    elif spec.kind=='temperature': initial=np.zeros(1); bounds=None
    else: initial=np.r_[projection.ravel(),np.zeros(k)]; bounds=None

    def objective(theta):
        check('calibrator objective pass')
        value=0.; gradient=np.zeros_like(theta)
        for x,y in batches():
            check('calibrator objective batch')
            if spec.kind in {'platt','beta'}:
                binary=(y==pos).astype(float)
                if spec.kind=='platt':
                    design=np.c_[(_scalar(x,spec,pos)/scalar_scale-mean)/sd,np.ones(len(y))]
                    # Published Platt target smoothing, not clipping evaluated predictions.
                    binary=np.where(binary==1,(counts[pos]+1)/(counts[pos]+2),1/(n-counts[pos]+2))
                else:
                    p=np.clip(x[:,pos],spec.epsilon,1-spec.epsilon)
                    design=np.c_[np.log(p),-np.log1p(-p),np.ones(len(y))]
                z=design@theta
                lp=sigmoid_log_probabilities(z)
                value+=float(np.sum(-(1-binary)*lp[:,0]-binary*lp[:,1]))/n
                gradient+=design.T@(np.exp(lp[:,1])-binary)/n
            else:
                if spec.kind=='temperature':
                    if not math.isfinite(float(theta[0])) or abs(theta[0])>700: return math.inf,np.zeros_like(theta)
                    inverse=math.exp(-float(theta[0]))
                    if spec.input=='logits': z=x
                    else:
                        with np.errstate(divide='ignore'): z=np.log(x)
                    if np.any(np.isneginf(z[np.arange(len(y)),y])):
                        raise MethodUnavailable('True-zero input makes every temperature log-loss infinite.','no_finite_objective')
                    with np.errstate(over='ignore',invalid='ignore'): scaled=z*inverse
                    if np.any(np.isnan(scaled)) or np.any(scaled==np.inf): return math.inf,np.zeros_like(theta)
                    lp=log_softmax(scaled)
                    value-=float(np.sum(lp[np.arange(len(y)),y]))/n
                    safe=np.where(np.isfinite(scaled),scaled,0.)
                    gradient[0]+=float(np.sum(safe[np.arange(len(y)),y]-np.sum(np.exp(lp)*safe,axis=1)))/n
                else:
                    design=np.log(np.clip(x,spec.epsilon,1-spec.epsilon))
                    w=theta[:k*k].reshape(k,k); b=theta[k*k:]
                    # Remove softmax's common-row gauge before applying the identity penalty.
                    w=projection@w; b=projection@b
                    lp=log_softmax(design@w.T+b)
                    value-=float(np.sum(lp[np.arange(len(y)),y]))/n
                    err=np.exp(lp); err[np.arange(len(y)),y]-=1
                    gradient[:k*k]+=(projection@(err.T@design/n)).ravel()
                    gradient[k*k:]+=projection@np.sum(err,axis=0)/n
        if spec.kind=='beta':
            delta=theta-np.array([1.,1.,0.]); value+=ridge*float(delta@delta); gradient+=2*ridge*delta
        elif spec.kind=='dirichlet':
            delta=projection@theta[:k*k].reshape(k,k)-projection; b=projection@theta[k*k:]
            # Gauge components are also pinned; predictions do not depend on them.
            gauge=(np.eye(k)-projection)@theta[:k*k].reshape(k,k)
            bg=(np.eye(k)-projection)@theta[k*k:]
            value+=ridge*float(np.sum(delta*delta)+b@b+np.sum(gauge*gauge)+bg@bg)
            gradient[:k*k]+=(2*ridge*(projection@delta+gauge)).ravel()
            gradient[k*k:]+=2*ridge*(b+bg)
        if not math.isfinite(value) or not np.all(np.isfinite(gradient)):
            raise MethodUnavailable('Nonfinite calibration objective.','numerical_fit')
        return value,gradient

    result=minimize(objective,initial,jac=True,bounds=bounds,method='L-BFGS-B',
                    options={'maxiter':spec.max_iterations,'ftol':spec.tolerance,'gtol':spec.tolerance})
    if not result.success or not np.all(np.isfinite(result.x)) or not math.isfinite(float(result.fun)):
        raise MethodUnavailable('No converged finite calibrator was obtained.','fit_nonconvergence')
    theta=result.x
    if spec.kind=='temperature':
        temperature=math.exp(float(theta[0]))
        if not math.isfinite(temperature) or temperature<=0: raise MethodUnavailable('No finite positive temperature.','numerical_fit')
        params={'temperature':temperature}
    elif spec.kind=='dirichlet': params={'weights':(projection@theta[:k*k].reshape(k,k)).tolist(),'intercepts':(projection@theta[k*k:]).tolist()}
    elif spec.kind=='platt': params={'coefficients':theta.tolist(),'scalar_scale':scalar_scale,'mean':mean,'sd':sd}
    else: params={'coefficients':theta.tolist(),'regularization':ridge}
    return params,{**metadata,'optimizer':'scipy_lbfgsb','iterations':int(result.nit),'objective_value':float(result.fun),'converged':True,'regularization':ridge if spec.kind in {'beta','dirichlet'} else None}


def fit_isotonic(spec,batches,pos,directory,check,connection=None,parameter_elements=1000000):
    """Disk-backed sorting and stack. Memory is independent of unique score count."""
    import duckdb
    token=hashlib.sha256(spec.id.encode()).hexdigest()[:24]
    db=connection or duckdb.connect(str(Path(directory)/('isotonic-'+token+'.duckdb')))
    try:
        if connection is None:db.execute('SET memory_limit=\'32MB\''); db.execute('SET threads=1')
        db.execute('CREATE TABLE observations(x DOUBLE,y INTEGER)')
        for x,y in batches():
            check('isotonic observation storage')
            values=_scalar(x,spec,pos)
            db.executemany('INSERT INTO observations VALUES (?,?)',zip(values.tolist(),(y==pos).astype(int).tolist()))
        db.execute('CREATE TABLE grouped AS SELECT x,sum(y)::DOUBLE sy,count(*)::DOUBLE n FROM observations GROUP BY x ORDER BY x')
        n=db.execute('SELECT count(*) FROM grouped').fetchone()[0]
        check('isotonic stack reservation',n*32)
        stack=np.memmap(Path(directory)/('pava-'+token),mode='w+',dtype='float64',shape=(n,4))
        top=0
        cursor=db.cursor(); cursor.execute('SELECT x,sy,n FROM grouped ORDER BY x')
        while True:
            chunk=cursor.fetchmany(1024)
            if not chunk: break
            check('isotonic PAVA stack')
            for x,sy,count in chunk:
                stack[top]=[x,x,sy,count]; top+=1
                while top>1 and stack[top-2,2]/stack[top-2,3]>stack[top-1,2]/stack[top-1,3]:
                    stack[top-2,1]=stack[top-1,1]; stack[top-2,2:]+=stack[top-1,2:]; top-=1
        knots=[]; values=[]
        knot_count=sum(1 if stack[i,0]==stack[i,1] else 2 for i in range(top))
        if knot_count*2>parameter_elements:raise MethodUnavailable('Exact isotonic knots exceed fitted parameter admission.','method_parameter_limit')
        # Each constant block needs both endpoints to preserve linear interpolation.
        for i in range(top):
            lo,hi,sy,count=stack[i]; knots.append(float(lo)); values.append(float(sy/count))
            if hi!=lo: knots.append(float(hi)); values.append(float(sy/count))
        del stack
        return {'knots':knots,'values':values}
    finally:
        if connection is None:db.close()
        else:
            db.execute('DROP TABLE IF EXISTS observations');db.execute('DROP TABLE IF EXISTS grouped')


def transform(spec,params,x,classes,positive_class):
    """Return probabilities AND log probabilities; preserve genuine vs numerical zeros."""
    x=np.asarray(x,dtype=float)
    pos=classes.index(positive_class) if positive_class else 1
    if spec.kind=='identity':
        with np.errstate(divide='ignore'): lp=np.log(x)
        return x.copy(),lp
    if spec.kind in {'platt','isotonic','beta'}:
        if spec.kind=='isotonic':
            p=np.interp(_scalar(x,spec,pos),params['knots'],params['values'])
            with np.errstate(divide='ignore'): binary=np.c_[np.log1p(-p),np.log(p)]
        else:
            if spec.kind=='platt':
                a,b=params['coefficients']
                with np.errstate(over='ignore',invalid='ignore'):z=a*(_scalar(x,spec,pos)/params['scalar_scale']-params['mean'])/params['sd']+b
            else:
                p=np.clip(x[:,pos],spec.epsilon,1-spec.epsilon); a,b,c=params['coefficients']; z=a*np.log(p)-b*np.log1p(-p)+c
            binary=sigmoid_log_probabilities(z)
        lp=binary if pos==1 else binary[:,::-1]
    elif spec.kind=='temperature':
        if spec.input=='logits': z=x
        else:
            with np.errstate(divide='ignore'): z=np.log(x)
        with np.errstate(over='ignore',invalid='ignore'): lp=log_softmax(z/params['temperature'])
    else:
        z=np.log(np.clip(x,spec.epsilon,1-spec.epsilon))
        lp=log_softmax(z@np.asarray(params['weights']).T+np.asarray(params['intercepts']))
    if np.any(np.isnan(lp)) or np.any(lp==np.inf): raise MethodUnavailable('Invalid transformed probabilities.','numerical_transformation')
    with np.errstate(under='ignore'): p=np.exp(lp)
    return p,lp
