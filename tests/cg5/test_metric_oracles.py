from dataclasses import replace
from types import SimpleNamespace
import math
import pytest
from confidenceguard import TaskDefinition,EvaluationConfig,PolicySpec,PolicyLimits,PolicyMetricSpec
from confidenceguard.policy_runtime import Interpreter,Budget
from confidenceguard.policy_metrics import metric_result
from confidenceguard.policy_assessment import _interval

def fixtures(task,values,ys):
    policy=PolicySpec(task,'r',{'root':{'kind':'action','action':{'kind':'supplied'}}},'root',{'kind':'abstain'},{'kind':'unavailable'})
    events=[{'event_key':str(i),'inputs':{'r':{'state':'issued','point':v if task.kind=='regression' else None,'decision':v if task.kind!='regression' else None}}} for i,v in enumerate(values)]
    records=[{'outcome_valid':y is not None,'y_num':y if task.kind=='regression' else None,'y':y if task.kind!='regression' else None} for y in ys]
    return policy,events,records

def measure(metric,p,e,r,actions,study):
    return metric_result(metric,e,r,actions,p,study,Budget(PolicyLimits(),EvaluationConfig()),retain_components=True)

def test_regression_actions_losses_and_bounds():
    task=TaskDefinition('regression','Demand',units='items',material_error=2)
    p,e,r=fixtures(task,[2.,5.,9.],[1.,7.,8.]);out=Interpreter(p).apply(e)[0];s=SimpleNamespace(evaluation_costs={},charges={})
    for metric,expected in [('mae',4/3),('mse',2),('rmse',math.sqrt(2)),('bias',0),('absolute_bias',0),('pinball',2/3)]:
        spec=PolicyMetricSpec(metric,metric,bounds=(-10,10) if metric in {'bias','absolute_bias'} else (0,100))
        stat=measure(spec,p,e,r,out,s);assert stat['value']==pytest.approx(expected)
        assert _interval(stat,spec,s,p,.05)[0] is not None
    broken=PolicyMetricSpec('broken','mse',bounds=(0,1))
    assert _interval(measure(broken,p,e,r,out,s),broken,s,p,.05)[1]=='contribution_bounds_violated'

def test_multiclass_opportunity_denominators_and_absent_class():
    task=TaskDefinition('multiclass_classification','Class',('a','b','c'))
    p,e,r=fixtures(task,['a','a','b','c'],['a','b','b','b']);out=Interpreter(p).apply(e)[0];out[2]={'state':'abstained','value':None}
    s=SimpleNamespace(evaluation_costs={},charges={})
    precision=measure(PolicyMetricSpec('precision','precision',target='a'),p,e,r,out,s)
    recall=measure(PolicyMetricSpec('recall','opportunity_recall',target='b'),p,e,r,out,s)
    assert precision['value']==.5 and precision['denominator']==2
    assert recall['value']==0 and recall['denominator']==3
    assert measure(PolicyMetricSpec('macro','balanced_accuracy'),p,e,r,out,s)['value_state']=='undefined'

def test_missing_label_envelopes_selective_ratio_and_unpriced_actions():
    task=TaskDefinition('binary_classification','Event',('no','yes'),'yes')
    p,e,r=fixtures(task,['yes','yes','no','yes'],['yes',None,'yes',None]);out=Interpreter(p).apply(e)[0]
    costs={'cost':{'yes':{'yes':'0','no':'2'},'no':{'yes':'5','no':'0'}}};s=SimpleNamespace(evaluation_costs=costs,charges={})
    low=measure(PolicyMetricSpec('lo','partial_lower',cost='cost'),p,e,r,out,s)
    high=measure(PolicyMetricSpec('hi','partial_upper',cost='cost'),p,e,r,out,s)
    assert low['value']==1.25 and high['value']==2.25 and low['denominator']==4
    out[2]={'state':'abstained','value':None}
    assert measure(PolicyMetricSpec('cost','empirical_cost',cost='cost'),p,e,r,out,s)['value_state']=='undefined'
    spec=PolicyMetricSpec('sel','selective_partial_upper',cost='cost',bounds=(0,5))
    stat=measure(spec,p,e,r,out,s);assert stat['value']==pytest.approx(4/3) and stat['denominator']==3
    interval,error=_interval(stat,spec,s,p,.05);assert interval is None and error=='acceptance_denominator_not_bounded_away_from_zero' or interval[1]>=stat['value']

def test_capacity_ranks_only_routed_events():
    from confidenceguard.contracts import digest
    task=TaskDefinition('binary_classification','Event',('no','yes'),'yes')
    p,e,r=fixtures(task,['no']*3,['no']*3)
    for i,event in enumerate(e):
        event['features']={'batch.id':{'kind':'categorical','state':'observed','canonical':'b'}}
        event['inputs']['r'].update(probs=[i/10,1-i/10],prob_valid=True,_classes=['no','yes'])
    nodes={'root':{'kind':'accept','when':{'kind':'compare','value':{'kind':'probability','target':'yes'},'op':'lt','constant':1},'accepted':'guard','rejected':'skip'},'guard':{'kind':'capacity','batch':'batch','ranking':{'kind':'probability','target':'yes'},'budget':1,'admitted':'yes','overflow':'skip'},'skip':{'kind':'action','action':{'kind':'abstain'}},'yes':{'kind':'action','action':{'kind':'label','label':'yes'}}}
    p=replace(p,nodes=nodes)
    batch={'id':'batch','field':'batch.id','closed_at':'2026-01-01T00:00:00Z','members':{'b':{'count':3,'digest':digest(sorted(x['event_key'] for x in e))}}}
    actions,trace=Interpreter(p).apply(e,batches=[batch])
    assert [a['state'] for a in actions]==['abstained','issued','abstained'] and trace['capacity'][0]['routed']==2
