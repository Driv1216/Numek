"""Independent-review counterexamples and invariant regressions for CG5."""
from dataclasses import replace
from itertools import product
from pathlib import Path
from types import SimpleNamespace
import copy
import csv
import json

import pytest

from confidenceguard.contracts import DecisionSpec, EvaluationConfig, EvaluationError, digest
from confidenceguard.policy_contracts import (
    FrozenPolicy, FrozenPolicyFamily, PolicyApplicationSpec, PolicyAssessmentSpec,
    PolicyClaim, PolicyConstraint, PolicyFamilySpec, PolicyLimits, PolicyMetricSpec,
    PolicyParameter, PolicySearchSpec, PolicySpec,
)
from confidenceguard.policy_runtime import Budget, Interpreter
from confidenceguard.policy_metrics import metric_result
from confidenceguard.policy_optimization import all_metrics, bind, domains, evaluate_candidate, milp_family, search
from confidenceguard.policies import optimize_policies, replay_policy, export_frozen_policy
from confidenceguard.policy_assessment import freeze_policy_family, inspect_policy_assessment, assess_policies
from .helpers import evidence, study, threshold
from .test_solver_resources import problem

CFG = EvaluationConfig(free_disk_bytes=1)


@pytest.mark.parametrize('regression', [False, True])
def test_R01_cross_cell_subpolicy_is_not_a_separable_milp(tmp_path, regression):
    s, f, p = problem(tmp_path, regression)
    linked = {'kind': 'accept', 'when': {'kind': 'compare', 'value': {'kind': 'constant', 'value': 1},
              'op': 'eq', 'constant': 1}, 'accepted': 'low', 'rejected': 'low'}
    f = replace(f, parameters=(replace(f.parameters[0], values=(linked,)), f.parameters[1]))
    s = replace(s, objectives=(PolicyMetricSpec('primary', 'mae' if regression else 'correct_issue_rate'),), families=(f,), candidates=(), baselines=())
    # The same composition remains legal for exact replay/enumeration.
    bound = bind(f.template, {v.id: v.values[0] for v in f.parameters})
    assert isinstance(bound, PolicySpec)
    with pytest.raises(EvaluationError, match='independent|separable|parameter'):
        milp_family(f, domains(f, p), s, p)


def test_R01_objective_disagreement_cannot_transfer_certificate(tmp_path, monkeypatch):
    from confidenceguard import policy_optimization as module
    s, f, p = problem(tmp_path, True)
    s = replace(s, objectives=(PolicyMetricSpec('primary', 'mae'),), families=(f,), baselines=())
    original = module.evaluate_candidate
    def disagree(*args, **kwargs):
        row, values = original(*args, **kwargs)
        row['metrics']['primary']['value'] += 10
        return row, values
    monkeypatch.setattr(module, 'evaluate_candidate', disagree)
    _, runs = milp_family(f, domains(f, p), s, p)
    assert runs[0]['certificate_transferred'] is False
    assert runs[0]['authoritative_re_evaluation'] == 'objective_mismatch'


def test_R05_weighted_optimum_survives_detail_retention(tmp_path):
    s, _, p = problem(tmp_path)
    def gate(cut):
        q = threshold(p.task, cut); nodes = q.to_dict()['nodes']
        nodes['no']['action'] = {'kind': 'abstain'}
        return replace(q, nodes=nodes)
    s = replace(s, candidates=(gate(.8), gate(.2)), families=(), baselines=(),
                objectives=(PolicyMetricSpec('cover', 'issued_coverage', weight=1),
                            PolicyMetricSpec('correct', 'correct_issue_rate', 'maximize', weight=100)),
                search=PolicySearchSpec(mode='weighted'))
    full = search(s, p)[3]
    limited = replace(s, limits=replace(s.limits, metric_records=len(all_metrics(s))*5))
    p = replace(p, limits=limited.limits, budget=Budget(limited.limits, CFG))
    records, _, _, actual, retention = search(limited, p)
    assert retention['omitted_candidate_detail'] == 1
    assert actual['policy_digest'] == full['policy_digest']
    assert actual['empirical_optimum'] == full['empirical_optimum']


def test_R05_tolerance_nomination_is_independent_of_display_pool(tmp_path):
    s,_,p=problem(tmp_path)
    gated=threshold(p.task,.8);nodes=gated.to_dict()['nodes'];nodes['no']['action']={'kind':'abstain'}
    gated=replace(gated,nodes=nodes)
    simple=PolicySpec(p.task,'model',{'root':{'kind':'action','action':{'kind':'argmax'}}},'root',{'kind':'abstain'},{'kind':'unavailable'})
    s=replace(s,candidates=(gated,simple),families=(),baselines=(),
              objectives=(PolicyMetricSpec('cover','issued_coverage'),),
              search=PolicySearchSpec(absolute_tolerance=1.,relative_tolerance=0))
    full=search(s,p)[3]
    limits=replace(s.limits,metric_records=len(all_metrics(s))*5)
    limited=replace(s,limits=limits);p=replace(p,limits=limits,budget=Budget(limits,CFG))
    records,policies,_,nomination,retention=search(limited,p)
    assert nomination['policy_digest']==full['policy_digest']==simple.policy_digest
    assert nomination['empirical_optimum']==full['empirical_optimum']==[.2]
    assert nomination['within_selection_tolerance'] is True
    assert nomination['policy_digest'] in policies and len(records)==5


def test_R02_decision_rule_identity_and_frozen_reapplication(tmp_path):
    inp = evidence(tmp_path); task = inp.evaluation.task
    policy = PolicySpec(task, 'model', {'root': {'kind': 'action', 'action': {'kind': 'supplied'}}},
                        'root', {'kind': 'abstain'}, {'kind': 'unavailable'})
    def application(cut, definition=policy):
        run = replace(inp.evaluation.runs[0], decision=DecisionSpec(rule='probability_threshold', threshold=cut))
        return PolicyApplicationSpec(replace(inp, evaluation=replace(inp.evaluation, runs=(run,))), definition, role='S')
    first = replay_policy(application(.5), CFG)
    packet = FrozenPolicy.from_dict(export_frozen_policy(first, next(iter(first.private['policies']))).to_dict())
    with pytest.raises(EvaluationError) as error:
        replay_policy(application(.9, PolicySpec.from_dict(packet.data['policy'])), CFG)
    assert error.value.code == 'incompatible_policy_input'
    second = replay_policy(application(.9), CFG)
    assert set(first.private['policies']) != set(second.private['policies'])
    assert first.private['action_ledger'] != second.private['action_ledger']


def protocol(result, claims=None):
    key = result.data['policy']['nomination']['policy_digest']
    return PolicyAssessmentSpec(tuple(claims or [PolicyClaim('accuracy', key, PolicyMetricSpec('accuracy', 'issued_accuracy', 'maximize'), 'ge', .5)]),
        sampling='independent_rows', upstream_independence='declared_independent', external_exposure='declared_unexposed',
        declaration_author='Synthetic review fixture', declaration_reason='Disjoint synthetic opportunities')


def test_R03_frozen_population_rules_cannot_be_replaced(tmp_path):
    s = study(tmp_path); selected = optimize_policies(s, CFG)
    family = FrozenPolicyFamily.from_dict(freeze_policy_family(selected, assessment=protocol(selected)).to_dict())
    alternatives = [replace(s.input.roles, column='group'), replace(s.input.roles, values={'S':'C','E':'E'}),
                    replace(s.input.roles, seed=1), replace(s.input.roles, unit='entity')]
    for roles in alternatives:
        with pytest.raises(EvaluationError) as error:
            inspect_policy_assessment(family, CFG, assessment_input=replace(s.input, roles=roles))
        assert error.value.code == 'policy_assessment_semantics'


def test_R04_optional_matching_claim_cannot_cover_required_constraint(tmp_path):
    s = study(tmp_path); metric = s.objectives[0]
    s = replace(s, constraints=(PolicyConstraint('floor', metric, 'ge', .9),))
    result = optimize_policies(s, CFG); key = result.data['policy']['nomination']['policy_digest']
    claims = [PolicyClaim('optional_floor', key, metric, 'ge', .9, required=False),
              PolicyClaim('coverage', key, PolicyMetricSpec('cover', 'issued_coverage'), 'ge', .5)]
    family = freeze_policy_family(result, assessment=protocol(result, claims))
    assert family.data['provenance']['required_constraints_covered'][key] is False
    assessed = assess_policies(family, CFG)
    assert assessed.data['policy']['policy_support'][key] == 'not_established'
    # A producer cannot repair coverage by changing only its self-reported flag.
    bad = family.to_dict(); bad['provenance']['required_constraints_covered'][key] = True
    bad['assessment_family_digest'] = digest({k:v for k,v in bad.items() if k not in {'assessment_family_digest','content_digest'}})
    bad['content_digest'] = digest({k:v for k,v in bad.items() if k != 'content_digest'})
    with pytest.raises(EvaluationError): FrozenPolicyFamily.from_dict(bad)


@pytest.mark.parametrize('regression', [False, True])
def test_R06_utility_envelopes_bound_utility_in_the_correct_order(regression):
    from confidenceguard.contracts import TaskDefinition
    task = TaskDefinition('regression', 'Quantity', units='items') if regression else TaskDefinition('binary_classification', 'Event', ('no','yes'), 'yes')
    action = {'kind':'numeric','value':0} if regression else {'kind':'label','label':'yes'}
    p = PolicySpec(task, 'model', {'root':{'kind':'action','action':action}}, 'root', {'kind':'abstain'}, {'kind':'unavailable'})
    events = [{'event_key':str(i),'inputs':{}} for i in range(2)]
    truth = [{'outcome_valid':True,'y':'no','y_num':10.}, {'outcome_valid':False}]
    actions = Interpreter(p).apply(events)[0]
    table = {'kind':'numeric_loss','loss':'absolute'} if regression else {'yes':{'no':10,'yes':0}}
    st = SimpleNamespace(evaluation_costs={'c':table}, charges={})
    values = []
    for basis in ('partial_lower','partial_upper'):
        spec = PolicyMetricSpec('utility','utility',basis=basis,cost='c',bounds=(-10,0))
        values.append(metric_result(spec,events,truth,actions,p,st,Budget(PolicyLimits(),CFG))['value'])
    assert values == [-10., -5.]


@pytest.mark.parametrize('operation', ['optimize','replay'])
def test_R09_source_change_after_reservation_aborts_without_result(tmp_path, monkeypatch, operation):
    from confidenceguard import policies
    s = study(tmp_path); original = policies._reserve; path = Path(s.input.evaluation.sources[0].path)
    def mutate(*args, **kwargs):
        reservation = original(*args, **kwargs)
        path.write_text(path.read_text().replace('0,0.05,no,S', '0,0.05,yes,S'))
        return reservation
    monkeypatch.setattr(policies, '_reserve', mutate)
    with pytest.raises(EvaluationError) as error:
        if operation == 'optimize': optimize_policies(s, CFG)
        else: replay_policy(PolicyApplicationSpec(s.input,threshold(s.input.evaluation.task),role='S'),CFG)
    assert error.value.code == 'stale_confirmation'


@pytest.mark.parametrize('regression', [False, True])
def test_milp_tie_refinement_matches_exhaustive_complexity_and_digest(tmp_path, regression):
    s, f, p = problem(tmp_path, regression)
    # Coverage ties every fully issuing option, despite distinct behavior.
    leafs = tuple(v for v in f.parameters[0].values if v['action']['kind'] != 'abstain')
    f = replace(f, parameters=tuple(replace(q, values=leafs) for q in f.parameters))
    s = replace(s, objectives=(PolicyMetricSpec('cover','issued_coverage','maximize'),), families=(f,), candidates=(), baselines=())
    d = domains(f,p); rows = []
    for values in product(*d.values()):
        policy = bind(f.template,dict(zip(d,values)))
        row,_ = evaluate_candidate(policy,s,p); rows.append(row)
    oracle = min(rows,key=lambda r:(r['complexity'],r['policy_digest']))
    actual,runs = milp_family(f,d,s,p)
    assert actual[0].policy_digest == oracle['policy_digest']
    assert runs[-1]['tie_refinement']['complete'] is True
    from confidenceguard.policy_optimization import milp_standing
    assert milp_standing(runs,actual)['search_coverage'] == 'complete'


def test_milp_incomplete_ties_and_hybrid_outer_limits_are_qualified(tmp_path):
    from confidenceguard.policy_optimization import hybrid_family, milp_standing
    s,f,p = problem(tmp_path)
    s = replace(s, objectives=(PolicyMetricSpec('cover','issued_coverage','maximize'),), families=(f,), candidates=(), baselines=())
    limits=replace(p.limits,solver_calls=1); p=replace(p,limits=limits,budget=Budget(limits,CFG))
    candidate,runs=milp_family(f,domains(f,p),s,p)
    standing=milp_standing(runs,candidate)
    assert candidate and standing['solution_standing']=='solver_optimal_objectives_tie_incomplete'
    assert standing['search_coverage']=='incomplete'
    s,f,p=problem(tmp_path/'hybrid')
    root=f.template['nodes']['root']; alternate=copy.deepcopy(root);alternate['rules'][0]['when']['constant']=.4
    template=copy.deepcopy(f.template);template['nodes']['root']={'parameter':'routing'}
    f=replace(f,kind='composition',backend='hybrid',template=template,
              parameters=(PolicyParameter('routing','node',(root,alternate)),*f.parameters),routing_parameters=('routing',))
    s=replace(s,families=(f,),candidates=(),baselines=(),objectives=(PolicyMetricSpec('cover','issued_coverage','maximize'),))
    limits=replace(p.limits,solver_calls=1);p=replace(p,limits=limits,budget=Budget(limits,CFG))
    found,branches,complete=hybrid_family(f,domains(f,p),s,p)
    assert found and not complete and len(branches)==1


@pytest.mark.parametrize('regression', [False, True])
def test_hybrid_outer_routes_and_inner_leaf_solve_match_full_enumeration(tmp_path, regression):
    from confidenceguard.policy_optimization import hybrid_family, choose, family_guidance
    s,f,p=problem(tmp_path,regression)
    root=f.template['nodes']['root']; alternate=copy.deepcopy(root);alternate['rules'][0]['when']['constant']=.3
    template=copy.deepcopy(f.template);template['nodes']['root']={'parameter':'routing'}
    f=replace(f,kind='composition',backend='hybrid',template=template,
              parameters=(PolicyParameter('routing','node',(root,alternate)),*f.parameters),routing_parameters=('routing',))
    s=replace(s,families=(f,),candidates=(),baselines=(),objectives=(PolicyMetricSpec('primary','mae' if regression else 'correct_issue_rate', 'minimize' if regression else 'maximize'),))
    d=domains(f,p); expected=[]
    for values in product(*d.values()): expected.append(evaluate_candidate(bind(f.template,dict(zip(d,values))),s,p)[0])
    found,branches,complete=hybrid_family(f,d,s,p)
    assert complete and len(branches)==2
    assert choose([row for _,row in found],s)['policy_digest']==choose(expected,s)['policy_digest']
    fresh=replace(p,budget=Budget(p.limits,CFG))
    guidance=family_guidance(s,fresh)[0]
    assert guidance['status']=='admitted' and guidance['outer_preflight_complete']
    assert not fresh.budget.counts['solver_calls']


def history_application(tmp_path):
    from confidenceguard import ReliabilityWorkspace, WorkspaceConfig
    from confidenceguard.method_contracts import RoleSpec
    from confidenceguard.policy_contracts import PolicyInputSpec
    inp=evidence(tmp_path);ev=inp.evaluation.to_dict();path=Path(ev['sources'][0]['path'])
    with path.open() as f: records=list(csv.DictReader(f))
    for i,row in enumerate(records): row.update(when='2026-01-01T00:00:00Z' if i<40 else '2026-02-01T00:00:00Z',available='2026-02-03T00:00:00Z')
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=records[0]);w.writeheader();w.writerows(records)
    ev['runs'][0]['prediction_at']={'column':'when'};ev['outcomes']['available_at']={'column':'available'}
    ws=ReliabilityWorkspace.initialize(tmp_path/'workspace',WorkspaceConfig(saving=True,free_disk_bytes=1))
    ws.ingest({'namespace':inp.roles.namespace,'outcome_definition_version':'v1','evaluation':ev,'bindings':[{'run':'model','features':{'group':'categorical'}}]})
    variant=ws.models()[0]['id']
    selection={'namespace':inp.roles.namespace,'variants':[variant],'as_of':'2026-03-01T00:00:00Z',
        'cohorts':[{'id':'groups','column':'group','categories':['a','b']}],
        'windows':[{'id':'jan','start':'2026-01-01T00:00:00Z','end':'2026-02-01T00:00:00Z'},
                   {'id':'feb','start':'2026-02-01T00:00:00Z','end':'2026-03-01T00:00:00Z'}]}
    retained=PolicyInputSpec(RoleSpec(inp.roles.namespace,proportions={'E':1}),history={'workspace_path':str(ws.path),'selection':selection})
    a=PolicyMetricSpec('a','issued_accuracy','maximize',scope='cohort_0/category_0')
    b=replace(a,id='b',scope='cohort_0/category_1')
    app=PolicyApplicationSpec(retained,replace(threshold(inp.evaluation.task,.7),run=variant),metrics=(a,),
        constraints=(PolicyConstraint('a_floor',a,'ge',.95),PolicyConstraint('b_floor',b,'ge',.95),PolicyConstraint('b_support',b,'ge',.1,minimum_support=100)))
    return ws,app


def test_R07_historical_scopes_constraints_and_immutable_restatement(tmp_path):
    from confidenceguard.policy_history import analyze_policy_history
    ws,app=history_application(tmp_path)
    result=analyze_policy_history(app,CFG)
    timeline=result.data['policy']['timeline']
    assert len(timeline)==2
    assert all(row['evidence']['value']==1. and row['evidence']['denominator']==20 for row in timeline)
    assert all(row['evidence']['population_definition']['restriction']=='cohort_0/category_0' for row in timeline)
    ledger=result.data['policy']['constraint_ledger']
    assert len(ledger)==6
    for row in ledger:
        assert row['state']=={'a_floor':'feasible','b_floor':'violated','b_support':'undefined'}[row['constraint_id']]
        assert row['support']==20
    ws.save_assessment(result)
    reopened=ws.open(result.data['analysis_id'])
    assert reopened.data['policy']['constraint_ledger']==ledger
    restated=ws.restate_policy_history(result.data['analysis_id'],as_of='2026-04-01T00:00:00Z',reason='Outcome-only restatement',config=CFG)
    assert restated.data['policy']['constraint_ledger']==ledger
    assert set(restated.private['policies'])==set(result.private['policies'])


def test_R09_historical_execution_uses_reserved_fingerprint(tmp_path,monkeypatch):
    from contextlib import contextmanager
    from confidenceguard import policy_history
    ws,app=history_application(tmp_path);original=policy_history.prepared_policy_history
    @contextmanager
    def changed(*args,**kwargs):
        with original(*args,**kwargs) as p:
            if kwargs.get('phase')=='history':
                # Identity uses the same preparation phase; alter only the
                # second, analytical opening, without bypassing supervision.
                p.fingerprint='changed-'+p.fingerprint
            yield p
    # Parent identity executes in a separate spawned interpreter; this local
    # context exercises the actual analytical worker's invariant directly.
    monkeypatch.setattr(policy_history,'prepared_policy_history',changed)
    from confidenceguard.policies import _application_study,arguments
    spec,config,roots=arguments(app,CFG,cls=PolicyApplicationSpec)
    with pytest.raises(EvaluationError) as error:
        policy_history._policy_history_worker(spec,_application_study(spec),config,roots,{},'reserved-snapshot')
    assert error.value.code=='stale_confirmation'


def test_R08_claim_projection_is_interpretable_and_private_claims_withhold_jointly(tmp_path):
    from confidenceguard.artifacts import render_report
    s=study(tmp_path);selected=optimize_policies(s,CFG);key=selected.data['policy']['nomination']['policy_digest']
    metric=s.objectives[0]
    claims=[PolicyClaim('private claim name',key,metric,'ge',.5),
            PolicyClaim('protected cohort claim',key,replace(metric,id='protected',scope='cohort_0/private cohort'),'ge',.5)]
    family=freeze_policy_family(selected,assessment=protocol(selected,claims))
    assessed=assess_policies(family,CFG);public=assessed.to_dict()
    assert public['policy']['joint_withholding'] is False
    assert public['policy']['withheld_assessments']==1
    claim=public['policy']['assessments'][0]
    assert claim['metric']=='issued_accuracy' and claim['operator']=='ge' and claim['bound']==.5 and claim['support']==40
    assert claim['basis']=='observed_outcome' and claim['policy_digest'].startswith('policy_')
    assert all('evidence_basis' in row for row in public['measurements'])
    for data in (public,assessed.to_private_dict()):
        html=render_report(data)
        assert 'issued_accuracy' in html and 'observed_outcome' in html and '40 eligible' in html and 'ge 0.5' in html
    raw=json.dumps(public)+render_report(public)
    assert 'private claim name' not in raw and 'private cohort' not in raw and str(tmp_path) not in raw
    assert key not in raw
    shared=type(assessed).from_dict(public)
    with pytest.raises(EvaluationError): shared.to_dict(audience='local')


def test_capability_preflight_refuses_actual_incompatible_encodings(tmp_path):
    from confidenceguard.policy_optimization import family_guidance
    s,f,p=problem(tmp_path)
    s=replace(s,families=(f,),objectives=(PolicyMetricSpec('precision','precision',target='yes'),),baselines=())
    guidance=family_guidance(s,p)[0]
    assert guidance['status']=='refused' and guidance['reason']=='policy_backend_incompatible'
    assert not p.budget.counts['solver_calls']


@pytest.mark.parametrize('kind',['multiclass_classification','regression'])
def test_R02_other_task_input_semantics_change_identity(tmp_path,kind):
    from confidenceguard.contracts import EvaluationSpec, TaskDefinition, SourceSpec, PredictionRunSpec, ModelIdentity, ProbabilitySpec, OutcomeSnapshotSpec
    from confidenceguard.policy_contracts import PolicyInputSpec
    from confidenceguard.method_contracts import RoleSpec
    path=tmp_path/'data.csv'
    path.write_text('id,p_a,p_b,p_c,x,z,y,role\n1,.5,.5,0,1,9,1,S\n')
    task=TaskDefinition(kind,'Outcome',units='items') if kind=='regression' else TaskDefinition(kind,'Outcome',('a','b','c'))
    run=PredictionRunSpec('r','data',ModelIdentity('same','v1'),key_columns=('id',),prediction='x') if kind=='regression' else PredictionRunSpec('r','data',ModelIdentity('same','v1'),key_columns=('id',),probabilities=ProbabilitySpec(columns={'a':'p_a','b':'p_b','c':'p_c'}),decision=DecisionSpec(rule='probability_argmax'))
    ev=EvaluationSpec(task,(SourceSpec('data',str(path)),),(run,),OutcomeSnapshotSpec('data','y',('id',)))
    inp=PolicyInputSpec(RoleSpec('other-task',column='role'),evaluation=ev)
    policy=PolicySpec(task,'r',{'root':{'kind':'action','action':{'kind':'supplied'}}},'root',{'kind':'abstain'},{'kind':'unavailable'})
    first=replay_policy(PolicyApplicationSpec(inp,policy,role='S'),CFG)
    changed=replace(run,prediction='z') if kind=='regression' else replace(run,decision=replace(run.decision,tie_policy='class_order'))
    other=replace(inp,evaluation=replace(ev,runs=(changed,)))
    second=replay_policy(PolicyApplicationSpec(other,policy,role='S'),CFG)
    assert set(first.private['policies'])!=set(second.private['policies'])
    assert first.private['action_ledger']!=second.private['action_ledger']
    original=PolicySpec.from_dict(next(iter(first.private['policies'].values())))
    with pytest.raises(EvaluationError): replay_policy(PolicyApplicationSpec(other,original,role='S'),CFG)


@pytest.mark.parametrize('dependency',['matrix','keys'])
def test_R09_external_representation_snapshot_is_reserved(tmp_path,monkeypatch,dependency):
    import numpy as np
    from confidenceguard import policies
    from confidenceguard.feature_contracts import DiscoveryRepresentationSpec
    from confidenceguard.contracts import SourceSpec
    s=study(tmp_path)
    matrix=tmp_path/'vectors.npy';keys=tmp_path/'keys.csv'
    np.save(matrix,np.arange(80,dtype=float).reshape(80,1));keys.write_text('id\n'+'\n'.join(str(i) for i in range(80))+'\n')
    rep=DiscoveryRepresentationSpec('frozen',matrix_path=str(matrix),keys_source=SourceSpec('keys',str(keys)),key_columns=('id',),dimensions=1,availability='at_decision')
    s=replace(s,input=replace(s.input,region_representations=(rep,)))
    reserve=policies._reserve
    def mutate(*args,**kwargs):
        receipt=reserve(*args,**kwargs)
        if dependency=='matrix': np.save(matrix,np.ones((80,1)))
        else: keys.write_text('id\n'+'\n'.join(str(i+100) for i in range(80))+'\n')
        return receipt
    monkeypatch.setattr(policies,'_reserve',mutate)
    with pytest.raises(EvaluationError) as error: optimize_policies(s,CFG)
    assert error.value.code=='stale_confirmation'


def test_frozen_import_cannot_strip_input_identity(tmp_path):
    result=optimize_policies(study(tmp_path),CFG)
    packet=export_frozen_policy(result,result.data['policy']['nomination']['policy_digest']).to_dict()
    packet['policy']['input_identity']={}
    packet['policy_digest']=PolicySpec.from_dict(packet['policy']).policy_digest
    packet['content_digest']=digest({k:v for k,v in packet.items() if k!='content_digest'})
    with pytest.raises(EvaluationError) as error: FrozenPolicy.from_dict(packet)
    assert error.value.code=='policy_input_contract'


def test_public_inspection_guidance_is_S_only_and_solver_free(tmp_path,monkeypatch):
    from confidenceguard.policies import inspect_policy_study
    s=study(tmp_path);inspection=inspect_policy_study(s,CFG)
    assert inspection['backend_admission'][0]['backend']=='sweep'
    assert inspection['backend_admission'][0]['status']=='admitted'
    assert inspection['assessment_values_disclosed'] is False
    path=Path(s.input.evaluation.sources[0].path)
    with path.open() as f: rows=list(csv.DictReader(f))
    for r in rows:
        if r['role']=='E':r.update(p='.999',y='no')
    with path.open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=rows[0]);writer.writeheader();writer.writerows(rows)
    after=inspect_policy_study(s,CFG)
    assert after['backend_admission']==inspection['backend_admission']
