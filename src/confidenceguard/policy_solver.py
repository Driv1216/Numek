"""Narrow, version-bound SciPy/HiGHS multiple-choice MILP adapter."""
import math
import time
import warnings

from .contracts import EvaluationError

PROFILE='scipy_1.18.1_highs_1.12.0_single_thread_v1'
SETTINGS={'threads':1,'parallel':False,'random_seed':0,'presolve':True,
          'mip_rel_gap':0.,'mip_abs_gap':0.,'mip_feasibility_tolerance':1e-9,
          'primal_feasibility_tolerance':1e-9,'dual_feasibility_tolerance':1e-9,
          'small_matrix_value':1e-12,'disp':False}
FORWARDED=set(SETTINGS)-{'presolve','mip_rel_gap','disp'}


def availability():
    try:
        import scipy
        from scipy.optimize._highspy import _core
        highs=_core._Highs().version()
        import sys,numpy
        return {'available':scipy.__version__=='1.18.1' and highs=='1.12.0',
                'scipy':scipy.__version__,'highs':highs,'profile':PROFILE,'numpy':numpy.__version__,'python':sys.version.split()[0]}
    except (ImportError,AttributeError,OSError):
        return {'available':False,'reason':'registered_scipy_highs_profile_unavailable','profile':PROFILE}


def solve(c,rows,lower,upper,variable_lower,variable_upper,integrality,budget,*,inspect_only=False):
    profile=availability()
    if not profile['available'] and not inspect_only: raise EvaluationError('Registered optional SciPy/HiGHS profile is unavailable.','policy_solver_dependency')
    n=len(c); r=len(rows); nnz=sum(len(row) for row in rows)
    for key,count in [('solver_variables',n),('solver_rows',r),('solver_nonzeros',nnz)]:
        if count>getattr(budget.limits,key): raise EvaluationError('MILP declaration exceeds admission.','policy_'+key+'_limit')
        if not inspect_only:
            budget.counts[key]=max(budget.counts[key],count)
            budget.counts[key+'_total']+=count
    budget.materialize((nnz*24+(n+r)*64)*4)
    scales=[]; ii=[]; jj=[]; vv=[]; lo=[]; hi=[]
    for index,(row,a,b) in enumerate(zip(rows,lower,upper)):
        values=[abs(v) for v in row.values() if v]
        scale=max(values+[abs(v) for v in (a,b) if math.isfinite(v)]+[1.])
        factor=2.**(-math.floor(math.log2(scale)))
        if any(not math.isfinite(v*factor) or v and not 1e-9<=abs(v*factor)<=1e9 for v in row.values()):
            raise EvaluationError('MILP row cannot preserve meaningful coefficients within the admitted numeric range.','policy_solver_scaling')
        for j,value in sorted(row.items()):
            if value: ii.append(index); jj.append(j); vv.append(value*factor)
        lo.append(a*factor); hi.append(b*factor); scales.append(factor)
    objective_scale=max([abs(v) for v in c]+[1.]); factor=2.**(-math.floor(math.log2(objective_scale)))
    if any(v and not 1e-9<=abs(v*factor)<=1e9 for v in c): raise EvaluationError('MILP objective scale is not admitted.','policy_solver_scaling')
    if inspect_only:
        return {'profile':profile,'matrix_sizes':{'variables':n,'rows':r,'nonzeros':nnz},'row_scaling':scales,'objective_scaling':factor}
    import numpy as np
    from scipy.optimize import milp,Bounds,LinearConstraint
    from scipy.sparse import csc_array
    remaining=budget.limits.solver_seconds-budget.counts['solver_seconds']
    nodes=budget.limits.solver_nodes-budget.counts['solver_nodes']
    if remaining<=0 or nodes<=0: return {'state':'limit','candidate':None,'profile':profile,'reason':'aggregate_solver_limit'}
    budget.charge('solver_calls')
    remaining=min(remaining,max(.001,budget.config.max_seconds-(time.monotonic()-budget.started)))
    options={**SETTINGS,'time_limit':remaining,'node_limit':nodes}
    matrix=csc_array((np.asarray(vv,float),(np.asarray(ii,np.int32),np.asarray(jj,np.int32))),shape=(r,n))
    started=time.monotonic()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        result=milp(np.asarray(c,float)*factor,integrality=np.asarray(integrality,np.int32),
                    bounds=Bounds(variable_lower,variable_upper),constraints=LinearConstraint(matrix,lo,hi),options=options)
    elapsed=time.monotonic()-started
    budget.counts['solver_seconds']+=elapsed
    budget.counts['solver_nodes']+=int(getattr(result,'mip_node_count',0) or 0)
    for warning in caught:
        message=str(warning.message)
        expected=(issubclass(warning.category,RuntimeWarning) and message.startswith('Unrecognized options detected:') and
                  message.endswith('These will be passed to HiGHS verbatim.') and set(_warning_keys(message))==FORWARDED)
        if not expected: raise EvaluationError('Solver emitted an unexpected option/numerical warning.','policy_solver_warning')
    state={0:'solver_optimal_encoded_model',1:'limit',2:'solver_infeasible_encoded_model',3:'solver_unbounded_encoded_model'}.get(result.status,'solver_failure')
    values=getattr(result,'x',None)
    candidate=None
    if values is not None:
        candidate=[]
        for i,v in enumerate(values):
            if not math.isfinite(float(v)): candidate=None; break
            if integrality[i] and abs(v-round(v))>1e-9: candidate=None; break
            candidate.append(int(round(v)) if integrality[i] else float(v))
    def objective(value): return float(value)/factor if value is not None and math.isfinite(float(value)) else None
    return {'state':state,'candidate':candidate,'encoded_objective':objective(getattr(result,'fun',None)),
            'encoded_dual_bound':objective(getattr(result,'mip_dual_bound',None)),
            'mip_gap':float(result.mip_gap) if getattr(result,'mip_gap',None) is not None and math.isfinite(result.mip_gap) else None,
            'nodes':int(getattr(result,'mip_node_count',0) or 0),'seconds':elapsed,'profile':profile,
            'settings':options,'matrix_sizes':{'variables':n,'rows':r,'nonzeros':nnz},'row_scaling':scales,'objective_scaling':factor,
            'certificate_scope':'Encoded finite model within recorded floating-point tolerances; authoritative policy replay must agree.'}


def _warning_keys(message):
    # Parse only the known warning's quoted option names, never evaluate Python.
    import re
    return re.findall(r"'([^']+)'",message)
