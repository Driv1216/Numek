from dataclasses import replace
import csv
import math
import pytest

from confidenceguard.contracts import EvaluationConfig,EvaluationError
from confidenceguard.policies import inspect_policy_study,optimize_policies,replay_policy
from confidenceguard.policy_contracts import PolicyApplicationSpec,PolicyMetricSpec,PolicySpec,PolicyFamilySpec,PolicyParameter,PolicyConstraint
from .helpers import study,evidence,threshold


CONFIG=EvaluationConfig(free_disk_bytes=1)


def test_supervised_exact_sweep_and_exhaustive_reference(tmp_path):
    spec=study(tmp_path)
    preview=inspect_policy_study(spec,CONFIG)
    assert preview['assessment_values_disclosed'] is False
    result=optimize_policies(spec,CONFIG,expected_fingerprint=preview['fingerprint'])
    panel=result.data['policy']; nominee=panel['nomination']['policy_digest']
    row=next(r for r in panel['candidates'] if r['policy_digest']==nominee)
    assert row['metrics']['accuracy']['value']==1.
    assert panel['searches'][0]['solution_standing']=='exact_grouped_empirical_search'
    assert panel['searches'][0]['search_coverage']=='complete'
    # Independent explicit event/action oracle, including equal-score groups.
    with open(spec.input.evaluation.sources[0].path) as stream: rows=[r for r in csv.DictReader(stream) if r['role']=='S']
    for candidate in panel['candidates']:
        policy=PolicySpec.from_dict(result.private['policies'][candidate['policy_digest']])
        if policy.nodes['root']['kind']!='accept': continue
        cut=policy.nodes['root']['when']['constant']
        predicted=[('yes' if (cut['cut']=='all' if isinstance(cut,dict) else float(r['p'])>=cut) else 'no') for r in rows]
        assert candidate['metrics']['accuracy']['value']==pytest.approx(sum(a==r['y'] for a,r in zip(predicted,rows))/len(rows))
    result2=type(result).from_dict(result.to_private_dict(),private=result.private)
    assert result2.to_dict()==result.to_dict()


def test_assessment_labels_and_inputs_cannot_change_selection(tmp_path):
    spec=study(tmp_path); before=optimize_policies(spec,CONFIG)
    path=spec.input.evaluation.sources[0].path
    with open(path) as stream: rows=list(csv.DictReader(stream))
    for row in rows:
        if row['role']=='E': row.update(y='no',p='.999')
    with open(path,'w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=rows[0]); writer.writeheader(); writer.writerows(rows)
    after=optimize_policies(spec,CONFIG)
    assert before.data['policy']['nomination']['policy_digest']==after.data['policy']['nomination']['policy_digest']
    assert before.data['coverage']['input_fingerprint']!=after.data['coverage']['input_fingerprint']


def test_costs_and_full_opportunity_denominators(tmp_path):
    inp=evidence(tmp_path); policy=threshold(inp.evaluation.task,.8)
    # Reject low confidence by abstaining, keeping all labeled events in cost/coverage.
    nodes=policy.to_dict()['nodes']; nodes['no']['action']={'kind':'abstain'}
    policy=replace(policy,nodes=nodes)
    metrics=(PolicyMetricSpec('cover','issued_coverage',basis='operational'),PolicyMetricSpec('risk','selective_risk'),
             PolicyMetricSpec('recall','opportunity_recall'),PolicyMetricSpec('cost','empirical_cost',cost='cost'))
    app=PolicyApplicationSpec(inp,policy,role='S',metrics=metrics,evaluation_costs={'cost':{'yes':{'yes':0,'no':10},'abstained':{'yes':2,'no':1}}})
    result=replay_policy(app,CONFIG); row=result.data['policy']['candidates'][0]['metrics']
    assert row['cover']['denominator']==40 and row['cover']['value']==.2
    assert row['risk']['denominator']==8 and row['risk']['value']==0
    assert row['recall']['denominator']==16 and row['recall']['value']==.5
    assert row['cost']['denominator']==40 and row['cost']['value']==1
    assert len(result.private['action_ledger'])==40


def test_evaluation_costs_do_not_change_actions(tmp_path):
    inp=evidence(tmp_path); p=threshold(inp.evaluation.task)
    app=PolicyApplicationSpec(inp,p,role='S',metrics=(PolicyMetricSpec('cost','empirical_cost',cost='c'),),evaluation_costs={'c':{'no':{'no':0,'yes':1},'yes':{'no':1,'yes':0}}})
    first=replay_policy(app,CONFIG)
    second=replay_policy(replace(app,evaluation_costs={'c':{'no':{'no':0,'yes':100},'yes':{'no':100,'yes':0}}}),CONFIG)
    assert first.private['action_ledger']==second.private['action_ledger']
    assert first.data['policy']['candidates'][0]['metrics']['cost']['value']!=second.data['policy']['candidates'][0]['metrics']['cost']['value']


def test_fixed_cell_milp_matches_complete_finite_oracle(tmp_path):
    spec=study(tmp_path)
    template=threshold(spec.input.evaluation.task).to_dict()
    # Fixed probability routing; each cell chooses a constant label.
    template['nodes']={'root':{'kind':'rules','rules':[{'when':{'kind':'compare','value':{'kind':'probability','target':'yes'},'op':'ge','constant':.6},'then':'high'}],'otherwise':'low'},
                       'high':{'parameter':'high'},'low':{'parameter':'low'}}
    options=({'kind':'action','action':{'kind':'label','label':'no'}},{'kind':'action','action':{'kind':'label','label':'yes'}})
    family=PolicyFamilySpec('cells',template,(PolicyParameter('high','node',options),PolicyParameter('low','node',options)),kind='fixed_cells',backend='milp')
    model=replace(spec,families=(family,),baselines=())
    result=optimize_policies(model,CONFIG)
    assert result.data['policy']['nomination'] is not None
    row=next(r for r in result.data['policy']['candidates'] if r['policy_digest']==result.data['policy']['nomination']['policy_digest'])
    assert row['metrics']['accuracy']['value']==1
    solvers=result.data['policy']['searches'][0]['solver_runs']
    assert solvers[0]['state']=='solver_optimal_encoded_model'
    assert solvers[0]['settings']['parallel'] is False and solvers[0]['settings']['threads']==1
    precision=PolicyMetricSpec('precision','precision',target='yes')
    invalid=replace(model,objectives=(precision,))
    with pytest.raises(EvaluationError) as exc: optimize_policies(invalid,CONFIG)
    assert exc.value.code=='policy_backend_incompatible'


def test_two_cut_complete_ordered_pairs_match_an_independent_band_oracle(tmp_path):
    from confidenceguard.policy_contracts import PolicyStudySpec
    inp=evidence(tmp_path);task=inp.evaluation.task;value={'kind':'probability','target':'yes'}
    template={'task':task.to_dict(),'run':'model','root':'root','fallback':{'kind':'abstain'},'unavailable':{'kind':'unavailable'},'nodes':{
      'root':{'kind':'rules','rules':[{'when':{'kind':'compare','value':value,'op':'lt','constant':{'parameter':'lower'}},'then':'no'},
       {'when':{'kind':'compare','value':value,'op':'ge','constant':{'parameter':'upper'}},'then':'yes'}],'otherwise':'reject'},
      'no':{'kind':'action','action':{'kind':'label','label':'no'}},'yes':{'kind':'action','action':{'kind':'label','label':'yes'}},'reject':{'kind':'action','action':{'kind':'abstain'}}}}
    family=PolicyFamilySpec('band',template,(PolicyParameter('lower',values=(.25,.65)),PolicyParameter('upper',values=(.25,.65,.85))),kind='two_cut',backend='enumerate')
    result=optimize_policies(PolicyStudySpec(inp,(PolicyMetricSpec('correct','correct_issue_rate','maximize'),),families=(family,)),CONFIG)
    with open(inp.evaluation.sources[0].path) as f: data=[r for r in csv.DictReader(f) if r['role']=='S']
    actual=[r for r in result.data['policy']['candidates'] if not r['baseline']]
    assert len(actual)==5
    for row in actual:
        lower,upper=row['parameters']['lower'],row['parameters']['upper']
        actions=['no' if float(r['p'])<lower else 'yes' if float(r['p'])>=upper else None for r in data]
        assert row['metrics']['correct']['value']==sum(a==r['y'] for a,r in zip(actions,data))/len(data)


def test_secondary_input_identity_binds_its_model_without_changing_CG1(tmp_path):
    from confidenceguard.contracts import ModelIdentity
    inp=evidence(tmp_path);first=inp.evaluation.runs[0];second=replace(first,id='second',model=ModelIdentity('alternate','v1'))
    inp=replace(inp,evaluation=replace(inp.evaluation,runs=(first,second)))
    policy=threshold(inp.evaluation.task);nodes=policy.to_dict()['nodes'];nodes['root']['when']['value']['run']='second';policy=replace(policy,nodes=nodes)
    a=replay_policy(PolicyApplicationSpec(inp,policy,role='S'),CONFIG)
    inp2=replace(inp,evaluation=replace(inp.evaluation,runs=(first,replace(second,model=ModelIdentity('alternate','v2')))))
    b=replay_policy(PolicyApplicationSpec(inp2,policy,role='S'),CONFIG)
    assert next(iter(a.private['policies']))!=next(iter(b.private['policies']))
