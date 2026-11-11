from dataclasses import replace
from itertools import product
from types import SimpleNamespace
import math
import pytest
from confidenceguard import (EvaluationConfig,PolicyMetricSpec,PolicyConstraint,PolicyLimits,PolicyFamilySpec,PolicyParameter,PolicySearchSpec,PolicySpec,TaskDefinition)
from confidenceguard.contracts import EvaluationError
from confidenceguard.policy_runtime import Budget,Interpreter
from confidenceguard.policy_problem import DevelopmentProblem
from confidenceguard.policy_optimization import milp_family,domains,evaluate_candidate,bind,search
from confidenceguard.policy_solver import solve
from .helpers import study


def problem(tmp_path,regression=False):
    s=study(tmp_path);task=TaskDefinition('regression','Quantity',units='items') if regression else s.input.evaluation.task
    if regression:
        evaluation=replace(s.input.evaluation,task=task,runs=(replace(s.input.evaluation.runs[0],probabilities=None,prediction='point'),))
        s=replace(s,input=replace(s.input,evaluation=evaluation),families=(),candidates=(PolicySpec(task,'model',{'root':{'kind':'action','action':{'kind':'numeric','value':0}}},'root',{'kind':'abstain'},{'kind':'unavailable'}),),baselines=())
    root={'kind':'rules','rules':[{'when':{'kind':'compare','value':{'kind':'point' if regression else 'probability',**({} if regression else {'target':'yes'})},'op':'ge','constant':.6},'then':'high'}],'otherwise':'low'}
    actions=[{'kind':'numeric','value':v} for v in (0.,1.,2.)] if regression else [{'kind':'label','label':'no'},{'kind':'label','label':'yes'},{'kind':'abstain'}]
    options=[{'kind':'action','action':a} for a in actions]
    template={'task':task.to_dict(),'run':'model','nodes':{'root':root,'high':{'parameter':'high'},'low':{'parameter':'low'}},'root':'root','fallback':{'kind':'abstain'},'unavailable':{'kind':'unavailable'}}
    family=PolicyFamilySpec('cells',template,(PolicyParameter('high','node',options),PolicyParameter('low','node',options)),kind='fixed_cells',backend='milp')
    events=[];records=[]
    for i in range(20):
        score=(i%10+.5)/10
        events.append({'event_key':str(i),'inputs':{'model':{'probs':[1-score,score],'prob_valid':True,'point':score,'_classes':['no','yes']}}})
        records.append({'outcome_valid':True,'y':'yes' if i%10>=6 else 'no','y_num':float(i%3)})
    budget=Budget(PolicyLimits(),EvaluationConfig());p=DevelopmentProblem(task,'model',budget.limits,budget,SimpleNamespace(batches=()),{'model':(events,records)},{'model':{}})
    return s,family,p

@pytest.mark.parametrize('name',['correct_issue_rate','issued_coverage','empirical_cost','balanced_accuracy'])
def test_registered_milp_matches_exhaustive_with_ratio_constraint(tmp_path,name):
    s,f,p=problem(tmp_path);cost={'c':{'no':{'no':0,'yes':3},'yes':{'no':2,'yes':0},'abstained':{'no':1,'yes':1}}}
    objective=PolicyMetricSpec('primary',name,'maximize' if name!='empirical_cost' else 'minimize',cost='c' if name=='empirical_cost' else None)
    precision=PolicyMetricSpec('precision','precision',target='yes')
    s=replace(s,objectives=(objective,),constraints=(PolicyConstraint('precision',precision,'ge',.8,minimum_support=1),),evaluation_costs=cost,baselines=(),families=(f,))
    domain=domains(f,p);solved,runs=milp_family(f,domain,s,p);assert solved and runs[0]['authoritative_re_evaluation']=='feasible'
    values=[]
    for a,b in product(*domain.values()):
        row,_=evaluate_candidate(bind(f.template,{'high':a,'low':b}),s,p)
        if row['observed_feasibility']=='feasible': values.append(row['metrics']['primary']['value'])
    assert solved[1]['metrics']['primary']['value']==pytest.approx((max if objective.direction=='maximize' else min)(values))

@pytest.mark.parametrize('name',['mae','mse','rmse','absolute_bias','pinball'])
def test_regression_fixed_numeric_actions_and_epigraph(tmp_path,name):
    s,f,p=problem(tmp_path,True);s=replace(s,objectives=(PolicyMetricSpec('loss',name),),baselines=(),families=(f,))
    domain=domains(f,p);solved,_=milp_family(f,domain,s,p)
    oracle=[evaluate_candidate(bind(f.template,{'high':a,'low':b}),s,p)[0]['metrics']['loss']['value'] for a,b in product(*domain.values())]
    assert solved[1]['metrics']['loss']['value']==pytest.approx(min(oracle))

@pytest.mark.parametrize('metric',['precision','macro_f1_fixed','median_absolute_error','r2'])
def test_variable_ratio_or_nonlinear_objective_refuses(tmp_path,metric):
    s,f,p=problem(tmp_path,metric in {'median_absolute_error','r2'})
    s=replace(s,objectives=(PolicyMetricSpec('bad',metric),),baselines=(),families=(f,))
    with pytest.raises(EvaluationError): milp_family(f,domains(f,p),s,p)


def test_scaling_profile_and_aggregate_solver_limits():
    budget=Budget(PolicyLimits(),EvaluationConfig())
    with pytest.raises(EvaluationError) as exc: solve([1,1e-20],[{0:1,1:1}],[1],[1],[0,0],[1,1],[1,1],budget)
    assert exc.value.code=='policy_solver_scaling'
    budget.counts['solver_nodes']=budget.limits.solver_nodes
    result=solve([1],[{0:1}],[1],[1],[0],[1],[1],budget)
    assert result['state']=='limit' and result['candidate'] is None
    with pytest.raises(EvaluationError): Budget(PolicyLimits(action_cells=1),EvaluationConfig()).charge('action_cells',2)


def test_bounded_beam_and_epsilon_frontier_do_not_claim_completeness(tmp_path):
    s,f,p=problem(tmp_path);s=replace(s,families=(replace(f,backend='bounded'),),baselines=())
    _,_,runs,nominee,_=search(s,p);assert nominee and runs[0]['search_coverage']=='incomplete'
    s,f,p=problem(tmp_path/'second');s=replace(s,families=(f,),baselines=(),objectives=(PolicyMetricSpec('correct','correct_issue_rate','maximize'),PolicyMetricSpec('cover','issued_coverage','maximize')),search=PolicySearchSpec(mode='pareto'))
    _,_,runs,nominee,_=search(s,p);assert nominee and runs[0]['solution_standing']=='sampled_epsilon_tradeoff_set'


def test_worst_window_epigraph_matches_exhaustive(tmp_path):
    s,f,p=problem(tmp_path,True)
    from confidenceguard.policy_contracts import PolicyInputSpec
    from confidenceguard.method_contracts import RoleSpec
    selection={'namespace':'fixture','windows':[{'id':'a','start':'2026-01-01T00:00:00Z','end':'2026-02-01T00:00:00Z'},{'id':'b','start':'2026-02-01T00:00:00Z','end':'2026-03-01T00:00:00Z'}]}
    inp=PolicyInputSpec(RoleSpec('fixture',proportions={'S':1}),history={'workspace_path':str(tmp_path),'selection':selection})
    for i,record in enumerate(p.frames['model'][1]):record['_windows']=['a' if i<10 else 'b']
    s=replace(s,input=inp,objectives=(PolicyMetricSpec('worst','mae',scope='worst_windows'),),families=(f,),baselines=(),candidates=())
    domain=domains(f,p);solved,_=milp_family(f,domain,s,p)
    oracle=[evaluate_candidate(bind(f.template,{'high':a,'low':b}),s,p)[0]['metrics']['worst']['value'] for a,b in product(*domain.values())]
    assert solved[1]['metrics']['worst']['value']==pytest.approx(min(oracle))


def test_solver_warning_and_integral_decode(monkeypatch):
    import warnings
    import scipy.optimize
    from confidenceguard import policy_solver
    monkeypatch.setattr(policy_solver,'availability',lambda:{'available':True,'profile':'synthetic'})
    def invoke(c,**kwargs):
        assert kwargs['options']['parallel'] is False
        assert kwargs['options']['threads']==1
        warnings.warn("Unrecognized options detected: {"+', '.join(repr(k) for k in sorted(policy_solver.FORWARDED))+"}. These will be passed to HiGHS verbatim.",RuntimeWarning)
        return SimpleNamespace(status=0,x=[.5],fun=0,mip_node_count=0,mip_gap=0,mip_dual_bound=0)
    monkeypatch.setattr(scipy.optimize,'milp',invoke)
    result=solve([1],[{0:1}],[0],[1],[0],[1],[1],Budget(PolicyLimits(),EvaluationConfig()))
    assert result['candidate'] is None
    def unexpected(c,**kwargs):
        warnings.warn('Invalid value for parallel',RuntimeWarning)
        return SimpleNamespace(status=0,x=[1],fun=1,mip_node_count=0)
    monkeypatch.setattr(scipy.optimize,'milp',unexpected)
    with pytest.raises(EvaluationError) as error:solve([1],[{0:1}],[0],[1],[0],[1],[1],Budget(PolicyLimits(),EvaluationConfig()))
    assert error.value.code=='policy_solver_warning'
    monkeypatch.setattr(policy_solver,'availability',lambda:{'available':False})
    with pytest.raises(EvaluationError) as error:solve([1],[],[],[],[0],[1],[1],Budget(PolicyLimits(),EvaluationConfig()))
    assert error.value.code=='policy_solver_dependency'
