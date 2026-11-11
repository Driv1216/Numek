from dataclasses import replace
import pytest

from confidenceguard.contracts import TaskDefinition, EvaluationError
from confidenceguard.policy_contracts import PolicySpec, PolicyLimits
from confidenceguard.policy_runtime import Interpreter, evaluate_predicate


TASK=TaskDefinition('binary_classification','Observed event',('no','yes'),'yes')


def policy(nodes=None,**kwargs):
    return PolicySpec(TASK,'model',nodes or {'root':{'kind':'action','action':{'kind':'argmax'}}},
                      'root',{'kind':'abstain'},{'kind':'defer','queue':'review'},**kwargs)


def event(p=.7):
    return {'event_key':'["1"]','inputs':{'model':{'probs':[1-p,p],'prob_valid':True,
            '_classes':['no','yes'],'state':'issued'}},'features':{}}


def compare(kind='probability',**value):
    return {'kind':'compare','value':{'kind':kind,**value},'op':'ge','constant':.5}


def test_ordered_unknown_does_not_fall_through_and_kleene_short_circuits():
    unknown=compare('field',target='missing.x')
    true=compare(target='yes')
    nodes={'root':{'kind':'rules','rules':[{'when':unknown,'then':'yes'},{'when':true,'then':'no'}]},
           'yes':{'kind':'action','action':{'kind':'label','label':'yes'}},
           'no':{'kind':'action','action':{'kind':'label','label':'no'}}}
    out,trace=Interpreter(policy(nodes)).apply([event()])
    assert out[0]['state']=='deferred' and out[0]['input_unavailable']
    assert trace['unknown_routes']=={'root':1}
    assert evaluate_predicate({'kind':'any','items':[unknown,true]},event(),'model') is True
    assert evaluate_predicate({'kind':'all','items':[unknown,{'kind':'not','item':true}]},event(),'model') is False


def test_inclusive_threshold_native_ties_and_task_actions():
    p=policy({'root':{'kind':'action','action':{'kind':'threshold','source':{'kind':'probability','target':'yes'},'threshold':.5}}})
    outputs,_=Interpreter(p).apply([event(.5),event(.499)])
    assert [o['value'] for o in outputs]==['yes','no']
    tied,_=Interpreter(policy()).apply([event(.5)])
    assert tied[0]['state']=='abstained'
    regression=TaskDefinition('regression','Quantity',units='items')
    q=PolicySpec(regression,'r',{'root':{'kind':'action','action':{'kind':'numeric','source':{'kind':'sample_median'}}}},
                 'root',{'kind':'abstain'},{'kind':'unavailable'})
    result,_=Interpreter(q).apply([{'event_key':'1','inputs':{'r':{'_samples':[1.,4.,9.]}}}])
    assert result[0]['value']==4


def test_decision_cost_identity_and_expected_cost_not_argmax():
    p=policy({'root':{'kind':'action','action':{'kind':'expected_cost','costs':'economics',
              'actions':[{'kind':'label','label':'no'},{'kind':'label','label':'yes'}]}}},
              decision_costs={'economics':{'no':{'no':0,'yes':1},'yes':{'no':10,'yes':0}}})
    out,_=Interpreter(p).apply([event(.7)])
    assert out[0]['value']=='no'
    updated=replace(p,decision_costs={'economics':{'no':{'no':0,'yes':10},'yes':{'no':1,'yes':0}}})
    assert updated.policy_digest!=p.policy_digest
    assert Interpreter(updated).apply([event(.7)])[0][0]['value']=='yes'


def test_graph_cycles_unknown_fields_and_shape_refuse():
    with pytest.raises(EvaluationError):
        policy({'root':{'kind':'accept','when':compare(target='yes'),'accepted':'root','rejected':'root'}})
    with pytest.raises(EvaluationError):
        policy({'root':{'kind':'action','action':{'kind':'label','label':'yes','python':'evil'}}})
    with pytest.raises(EvaluationError):
        policy({'root':{'kind':'action','action':{'kind':'numeric','value':1}}})


def test_reused_subgraph_longest_path_still_respects_depth_limit():
    nodes={'root':{'kind':'rules','rules':[{'when':compare(target='yes'),'then':'s0'}],'otherwise':'p0'},'leaf':{'kind':'action','action':{'kind':'abstain'}}}
    for i in range(5):nodes['s'+str(i)]={'kind':'accept','when':compare(target='yes'),'accepted':'s'+str(i+1) if i<4 else 'leaf','rejected':'leaf'}
    for i in range(4):nodes['p'+str(i)]={'kind':'accept','when':compare(target='yes'),'accepted':'p'+str(i+1) if i<3 else 's0','rejected':'leaf'}
    with pytest.raises(EvaluationError):policy(nodes)


def test_capacity_keeps_whole_ties_and_refuses_incomplete_batch():
    from confidenceguard.contracts import digest
    items=[event(.9),event(.8),event(.8),event(.1)]
    for i,e in enumerate(items):
        e['event_key']=str(i)
        e['features']['batch.id']={'kind':'categorical','state':'observed','canonical':'day1'}
    p=policy({'root':{'kind':'capacity','batch':'day','ranking':{'kind':'probability','target':'yes'},
                      'budget':2,'admitted':'yes','overflow':'no'},
              'yes':{'kind':'action','action':{'kind':'label','label':'yes'}},
              'no':{'kind':'action','action':{'kind':'abstain'}}})
    batches=[{'id':'day','field':'batch.id','closed_at':'2026-11-03T00:00:00Z',
              'members':{'day1':{'count':4,'digest':digest(sorted(e['event_key'] for e in items))}}}]
    out,trace=Interpreter(p).apply(items,batches=batches)
    assert [o['state'] for o in out]==['issued','abstained','abstained','abstained']
    assert trace['capacity'][0]['used_resource']==1
    partial,_=Interpreter(p).apply(items[:3],batches=batches)
    assert all(o['input_unavailable'] for o in partial)


def test_capacity_decimal_resource_boundary_is_not_a_business_relaxation():
    from confidenceguard.contracts import digest
    items=[event(.8),event(.8)]
    for i,item in enumerate(items):
        item['event_key']=str(i);item['features']={'batch.id':{'kind':'categorical','state':'observed','canonical':'day'},'batch.resource':{'kind':'decimal','state':'observed','canonical':('.1','.2')[i]}}
    p=policy({'root':{'kind':'capacity','batch':'day','ranking':{'kind':'probability','target':'yes'},'resource':{'kind':'field','target':'batch.resource'},'budget':.3,'admitted':'yes','overflow':'no'},'yes':{'kind':'action','action':{'kind':'label','label':'yes'}},'no':{'kind':'action','action':{'kind':'abstain'}}})
    declaration={'id':'day','field':'batch.id','closed_at':'2026-01-01T00:00:00Z','members':{'day':{'count':2,'digest':digest(['0','1'])}}}
    actions,trace=Interpreter(p).apply(items,batches=[declaration])
    assert all(a['state']=='issued' for a in actions) and trace['capacity'][0]['used_resource']==.3
    assert trace['capacity'][0]['used_resource_canonical']=='0.3'
