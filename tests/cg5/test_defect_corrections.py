"""D1–D5: population-semantic inference and globally valid optimizer evidence."""
from dataclasses import replace
from itertools import product
from pathlib import Path
from types import SimpleNamespace
import copy
import csv
import math

import pytest

from confidenceguard.contracts import EvaluationConfig, EvaluationError, TaskDefinition, DisclosureSpec
from confidenceguard.policy_contracts import (
    PolicySpec, PolicyMetricSpec, PolicyClaim, PolicyAssessmentSpec, PolicyFamilySpec,
    PolicyParameter, PolicySearchSpec,
)
from confidenceguard.policy_runtime import Budget
from confidenceguard.policy_optimization import (
    bind, domains, evaluate_candidate, choose, milp_family, milp_standing, search, all_metrics,
)
from confidenceguard.policies import optimize_policies
from confidenceguard.policy_assessment import freeze_policy_family, assess_policies, _interval
from confidenceguard.policy_result import PolicyResult
from confidenceguard.artifacts import render_report
from .helpers import study, threshold
from .test_solver_resources import problem

CFG = EvaluationConfig(free_disk_bytes=1)


def regression_study(path, *, outcome='0', units='items'):
    s = study(path)
    source = Path(s.input.evaluation.sources[0].path)
    with source.open() as stream:
        rows = list(csv.DictReader(stream))
    for row in rows:
        row.update(p='0', y=outcome)
    with source.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0]); writer.writeheader(); writer.writerows(rows)
    task = TaskDefinition('regression', 'Quantity', units=units, material_error=.5)
    ev = replace(s.input.evaluation, task=task,
                 runs=(replace(s.input.evaluation.runs[0], probabilities=None, prediction='p'),))
    policy = PolicySpec(task, 'model', {'root': {'kind': 'action', 'action': {'kind': 'numeric', 'value': 0}}},
                        'root', {'kind': 'abstain'}, {'kind': 'unavailable'})
    return replace(s, input=replace(s.input, evaluation=ev), families=(), baselines=(), candidates=(policy,),
                   objectives=(PolicyMetricSpec('mae', 'mae', units=units),))


def protocol(key, metrics, bound=.1):
    return PolicyAssessmentSpec(tuple(PolicyClaim(m.id, key, m, 'le', bound) for m in metrics),
        sampling='independent_rows', upstream_independence='declared_independent',
        external_exposure='declared_unexposed', declaration_author='D1–D5 fixture',
        declaration_reason='Independent synthetic rows, disjoint frozen S and E')


def test_D1_original_false_support_is_replaced_by_true_bounded_loss_interval(tmp_path):
    selected = optimize_policies(regression_study(tmp_path), CFG)
    key = selected.data['policy']['nomination']['policy_digest']
    metric = PolicyMetricSpec('risk', 'selective_risk', loss='absolute', bounds=(0, 10), units='items')
    result = assess_policies(freeze_policy_family(selected, assessment=protocol(key, [metric])), CFG)
    row = result.data['policy']['assessments'][0]
    expected_upper = 10 * math.sqrt(math.log(2 / .05) / (2 * 40))
    assert row['state'] == 'inconclusive' and row['upper'] == pytest.approx(expected_upper)
    assert row['lower'] == 0 and row['support'] == 40
    assert row['method'] == 'bounded_mean_hoeffding'
    assert result.data['policy']['policy_support'][key] == 'not_established'
    # The original binomial upper bound .0881 excluded the true mean .5 on an
    # IID event of probability .95**40 > alpha. The new bound includes it.
    assert .95**40 > .05 and row['upper'] > .5
    public = result.to_dict()
    assert public['policy']['assessments'][0]['upper'] == row['upper']
    reopened = PolicyResult.from_dict(result.to_private_dict(), private=result.private)
    assert reopened.data['policy']['assessment_digest'] == result.data['policy']['assessment_digest']


@pytest.mark.parametrize('loss', ['absolute', 'squared', 'signed', 'pinball', 'material'])
def test_D1_interval_dispatch_uses_registered_loss_semantics(loss):
    task = TaskDefinition('regression', 'Quantity', units='items', material_error=.5)
    policy = SimpleNamespace(task=task)
    metric = PolicyMetricSpec('risk', 'selective_risk', loss=loss, bounds=(-10, 10) if loss == 'signed' else (0, 10))
    stat = {'value_state': 'finite', 'statistic_kind': 'mean', '_contributions': [0.] * 40}
    interval, error = _interval(stat, metric, SimpleNamespace(), policy, .05)
    assert error is None
    if loss == 'material':
        assert interval[1] == pytest.approx(1 - (.05 / 2)**(1 / 40))
    else:
        assert interval[1] == pytest.approx((20 if loss == 'signed' else 10) * math.sqrt(math.log(40) / 80))
    bad = {**stat, '_contributions': [11.]}
    assert _interval(bad, metric, SimpleNamespace(), policy, .05)[1] == 'contribution_bounds_violated'


def nomination_fixture(path, backend='milp', *, other_family=False, mode='lexicographic'):
    s, f, p = problem(path)
    abstain = {'kind': 'action', 'action': {'kind': 'abstain'}}
    predicate = {'kind': 'compare', 'value': {'kind': 'constant', 'value': 1}, 'op': 'eq', 'constant': 1}
    via = {'kind': 'accept', 'when': predicate, 'accepted': 'end', 'rejected': 'end'}
    template = copy.deepcopy(f.template)
    template['nodes']['end'] = {'kind': 'action', 'action': {'kind': 'label', 'label': 'no'}}
    f = replace(f, template=template, parameters=(replace(f.parameters[0], values=(abstain,)),
                                                 replace(f.parameters[1], values=(abstain, via))))
    if backend == 'hybrid':
        root = template['nodes']['root']; alternate = copy.deepcopy(root)
        alternate['rules'][0]['when']['constant'] = .5
        template = copy.deepcopy(template); template['nodes']['root'] = {'parameter': 'route'}
        f = replace(f, template=template, kind='composition', backend='hybrid', routing_parameters=('route',),
                    parameters=(PolicyParameter('route', 'node', (root, alternate)), *f.parameters))
    q = threshold(p.task, .6); nodes = q.to_dict()['nodes']
    nodes['extra'] = {'kind': 'accept', 'when': predicate, 'accepted': 'root', 'rejected': 'root'}
    nodes['extra2'] = {**nodes['extra'], 'accepted': 'extra', 'rejected': 'extra'}
    q = replace(q, nodes=nodes, root='extra2')
    families = [f]
    if other_family:
        exact = copy.deepcopy(q.to_dict()); exact['nodes']['root']['when']['constant'] = {'parameter': 'cut'}
        families.append(PolicyFamilySpec('other', exact, (PolicyParameter('cut', 'finite', (.6,)),), backend='enumerate'))
    return replace(s, candidates=() if other_family else (q,), families=tuple(families), baselines=(),
                   objectives=(PolicyMetricSpec('correct', 'correct_issue_rate', 'maximize'),),
                   search=PolicySearchSpec(mode=mode, absolute_tolerance=.65, relative_tolerance=0)), p


@pytest.mark.parametrize('backend', ['milp', 'hybrid'])
@pytest.mark.parametrize('other_family', [False, True])
def test_D2_original_global_nomination_matches_exhaustive_public_service(tmp_path, backend, other_family):
    s, _ = nomination_fixture(tmp_path, backend, other_family=other_family)
    expected = optimize_policies(replace(s, families=tuple(replace(f, backend='enumerate') for f in s.families)), CFG)
    actual = optimize_policies(s, CFG)
    assert actual.data['policy']['nomination']['policy_digest'] == expected.data['policy']['nomination']['policy_digest']
    nominee = actual.data['policy']['nomination']
    assert nominee['nominated_objective'] == [-.6] and nominee['empirical_optimum'] == [-1.]
    assert all(r['search_coverage'] == 'complete' for r in actual.data['policy']['searches'])
    # Force a one-candidate detail pool. Global nomination must still survive.
    limited = replace(s, limits=replace(s.limits, metric_records=len(all_metrics(s)) * 5))
    retained = optimize_policies(limited, CFG)
    assert retained.data['policy']['nomination']['policy_digest'] == nominee['policy_digest']


@pytest.mark.parametrize('relative', [0, .5, 1.5])
@pytest.mark.parametrize('mode', ['lexicographic', 'weighted'])
def test_D2_later_priorities_and_large_relative_tolerances_match_exhaustive(tmp_path, relative, mode):
    s, f, p = problem(tmp_path)
    # Distinct outer references can make a later objective eligible globally
    # even when it lies outside its own family's local later-objective tie band.
    candidates = (threshold(p.task, .2), threshold(p.task, .6), threshold(p.task, .9))
    s = replace(s, families=(f,), candidates=candidates, baselines=(),
                objectives=(PolicyMetricSpec('correct', 'correct_issue_rate', 'maximize'),
                            PolicyMetricSpec('abstain', 'abstention_rate', 'maximize', weight=2)),
                search=PolicySearchSpec(mode=mode, absolute_tolerance=.4, relative_tolerance=relative))
    expected = optimize_policies(replace(s, families=(replace(f, backend='enumerate'),)), CFG)
    actual = optimize_policies(s, CFG)
    assert actual.data['policy']['nomination']['policy_digest'] == expected.data['policy']['nomination']['policy_digest']
    assert actual.data['policy']['nomination']['empirical_optimum'] == expected.data['policy']['nomination']['empirical_optimum']


def test_D2_global_later_priority_can_be_outside_the_local_later_tie_band(tmp_path):
    s, f, _ = problem(tmp_path)
    no = {'kind': 'action', 'action': {'kind': 'label', 'label': 'no'}}
    abstain = {'kind': 'action', 'action': {'kind': 'abstain'}}
    f = replace(f, parameters=(replace(f.parameters[0], values=(abstain, no)),
                                replace(f.parameters[1], values=(no,))))
    external = threshold(s.input.evaluation.task, .6)
    nodes = external.to_dict()['nodes']
    nodes['extra'] = {'kind': 'accept', 'when': {'kind': 'compare', 'value': {'kind': 'constant', 'value': 1},
        'op': 'eq', 'constant': 1}, 'accepted': 'root', 'rejected': 'root'}
    external = replace(external, nodes=nodes, root='extra')
    s = replace(s, families=(f,), candidates=(external,), baselines=(),
        objectives=(PolicyMetricSpec('correct', 'correct_issue_rate', 'maximize'),
                    PolicyMetricSpec('charge', 'operational_charge', 'minimize')),
        charges={'no': 10, 'yes': 10, 'abstained': 0, 'unavailable': 0},
        search=PolicySearchSpec(absolute_tolerance=.65, relative_tolerance=0))
    oracle = optimize_policies(replace(s, families=(replace(f, backend='enumerate'),)), CFG)
    actual = optimize_policies(s, CFG)
    assert actual.data['policy']['nomination']['policy_digest'] == oracle.data['policy']['nomination']['policy_digest']
    assert actual.data['policy']['nomination']['nominated_objective'] == [-.6, 10.]


def test_D2_nomination_resource_limit_never_inherits_complete_standing(tmp_path):
    s, f, p = problem(tmp_path)
    s = replace(s, families=(f,), objectives=(PolicyMetricSpec('correct', 'correct_issue_rate', 'maximize'),))
    def no_room(*args):
        raise EvaluationError('Synthetic nomination memory admission', 'policy_selection_state_limit')
    actual, runs = milp_family(f, domains(f, p), s, p, on_candidate=no_room, global_nomination=True)
    standing = milp_standing(runs, actual)
    assert standing['search_coverage'] == 'incomplete'
    assert standing['solution_standing'] == 'solver_optimal_objectives_tie_incomplete'
    limited, _ = nomination_fixture(tmp_path / 'limited')
    result = optimize_policies(replace(limited, limits=replace(limited.limits, solver_calls=1)), CFG)
    assert result.data['policy']['searches'][0]['search_coverage'] == 'incomplete'
    assert result.data['policy']['nomination']['tie_coverage'] == 'incomplete_best_found'


def test_D2_direct_hybrid_candidates_retain_shared_memory_accounting(tmp_path):
    from confidenceguard.policy_optimization import hybrid_family
    s, p = nomination_fixture(tmp_path, 'hybrid')
    f = s.families[0]; d = domains(f, p)
    first, _, complete = hybrid_family(f, d, s, p)
    assert first and complete
    reserved = p.budget.allocations['hybrid_candidates']
    second, _, complete = hybrid_family(f, d, s, p)
    assert second and complete and p.budget.allocations['hybrid_candidates'] > reserved


def weighted_rmse_fixture(path, *, weight=1, direction='minimize'):
    s, f, p = problem(path, True)
    for record in p.frames['model'][1]: record['y_num'] *= 3
    template = copy.deepcopy(f.template)
    template['nodes']['end1'] = {'kind': 'action', 'action': {'kind': 'numeric', 'value': 3.}}
    via = {'kind': 'accept', 'when': {'kind': 'compare', 'value': {'kind': 'constant', 'value': 1}, 'op': 'eq', 'constant': 1}, 'accepted': 'end1', 'rejected': 'end1'}
    options = ({'kind': 'action', 'action': {'kind': 'numeric', 'value': 0.}}, via,
               {'kind': 'action', 'action': {'kind': 'numeric', 'value': 6.}})
    f = replace(f, template=template, parameters=tuple(replace(q, values=options) for q in f.parameters))
    return replace(s, objectives=(PolicyMetricSpec('loss', 'rmse', direction, weight=weight),),
                   families=(f,), candidates=(), baselines=(),
                   search=PolicySearchSpec(mode='weighted', absolute_tolerance=.9, relative_tolerance=0)), f, p


@pytest.mark.parametrize('weight', [0, .5, 1, 3])
@pytest.mark.parametrize('direction', ['minimize', 'maximize'])
def test_D3_weighted_rmse_tie_band_matches_exhaustive(weight, direction, tmp_path):
    s, f, p = weighted_rmse_fixture(tmp_path, weight=weight, direction=direction)
    d = domains(f, p)
    rows = [evaluate_candidate(bind(f.template, dict(zip(d, values))), s, p)[0] for values in product(*d.values())]
    expected = choose(rows, s)
    actual, runs = milp_family(f, d, s, replace(p, budget=Budget(p.limits, CFG)))
    assert actual[0].policy_digest == expected['policy_digest']
    assert milp_standing(runs, actual)['search_coverage'] == 'complete'
    if weight == 1 and direction == 'minimize':
        assert actual[1]['metrics']['loss']['value'] == pytest.approx(3.2171415884290826)


def test_D3_mixed_rmse_sum_refuses_and_limited_ties_are_incomplete(tmp_path):
    s, f, p = weighted_rmse_fixture(tmp_path)
    mixed = replace(s, objectives=(*s.objectives, PolicyMetricSpec('bias', 'bias')))
    with pytest.raises(EvaluationError) as error:
        milp_family(f, domains(f, p), mixed, p)
    assert error.value.code == 'policy_backend_incompatible'
    limits = replace(p.limits, solver_calls=1)
    p = replace(p, limits=limits, budget=Budget(limits, CFG))
    actual, runs = milp_family(f, domains(f, p), s, p)
    assert actual and milp_standing(runs, actual)['solution_standing'] == 'solver_optimal_objectives_tie_incomplete'


def test_D3_weighted_rmse_public_service_and_unrepresentable_band(tmp_path):
    from confidenceguard.policy_optimization import encoded_tie_bounds
    s = regression_study(tmp_path)
    source = Path(s.input.evaluation.sources[0].path)
    with source.open() as stream: rows = list(csv.DictReader(stream))
    for i, row in enumerate(rows): row['y'] = str((i % 3) * 3)
    with source.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0]); writer.writeheader(); writer.writerows(rows)
    fixture, f, _ = weighted_rmse_fixture(tmp_path / 'fixture', weight=3)
    template = copy.deepcopy(f.template); template['task'] = s.input.evaluation.task.to_dict()
    f = replace(f, template=template)
    s = replace(s, candidates=(), families=(f,), objectives=fixture.objectives, search=fixture.search)
    oracle = optimize_policies(replace(s, families=(replace(f, backend='enumerate'),)), CFG)
    actual = optimize_policies(s, CFG)
    assert actual.data['policy']['nomination']['policy_digest'] == oracle.data['policy']['nomination']['policy_digest']
    assert actual.data['policy']['searches'][0]['search_coverage'] == 'complete'
    with pytest.raises(EvaluationError) as error:
        encoded_tie_bounds(s.objectives[0], 0, 1e300, 1e-300)
    assert error.value.code == 'policy_solver_scaling'


def test_D4_complete_hybrid_optimization_is_not_a_complete_frontier(tmp_path):
    s, f, _ = problem(tmp_path)
    root = f.template['nodes']['root']; alternate = copy.deepcopy(root)
    alternate['rules'][0]['when']['constant'] = .4
    template = copy.deepcopy(f.template); template['nodes']['root'] = {'parameter': 'route'}
    f = replace(f, template=template, kind='composition', backend='hybrid', routing_parameters=('route',),
                parameters=(PolicyParameter('route', 'node', (root, alternate)), *f.parameters))
    s = replace(s, families=(f,), candidates=(), baselines=(),
                objectives=(PolicyMetricSpec('correct', 'correct_issue_rate', 'maximize'),
                            PolicyMetricSpec('abstain', 'abstention_rate', 'maximize')))
    actual = optimize_policies(s, CFG)
    assert actual.data['policy']['searches'][0]['search_coverage'] == 'complete'
    assert actual.data['policy']['frontier']['standing'] == 'sampled_tradeoff_set'
    oracle = optimize_policies(replace(s, families=(replace(f, backend='enumerate'),)), CFG)
    assert oracle.data['policy']['frontier']['standing'] == 'complete_empirical_frontier'
    assert 'sampled_tradeoff_set' in render_report(actual.to_private_dict())
    public = actual.to_dict(disclosure=DisclosureSpec(minimum_component=1, minimum_denominator=1))['policy']['searches'][0]
    assert public['solution_standing'] == 'complete_outer_routing_with_encoded_inner_optima'


def regression_claims():
    return [PolicyMetricSpec('low', 'pinball', level=.1, bounds=(0, 10), units='items'),
            PolicyMetricSpec('high', 'pinball', level=.9, bounds=(0, 10), units='items'),
            PolicyMetricSpec('square', 'selective_risk', loss='squared', bounds=(0, 10), units='squared_items'),
            PolicyMetricSpec('material', 'material_error_rate')]


def test_D5_public_regression_semantics_and_joint_private_unit_withholding(tmp_path):
    s = regression_study(tmp_path, outcome='1')
    selected = optimize_policies(s, CFG); key = selected.data['policy']['nomination']['policy_digest']
    result = assess_policies(freeze_policy_family(selected, assessment=protocol(key, regression_claims(), 2)), CFG)
    public = result.to_dict(); rows = public['policy']['assessments']
    assert [r.get('level') for r in rows[:2]] == [.1, .9]
    assert rows[2]['loss'] == 'squared' and rows[2]['units'] == 'squared_items'
    assert rows[3]['material_error'] == .5 and rows[3]['outcome_units'] == 'items'
    for audience in (public, result.to_private_dict()):
        html = render_report(audience)
        assert 'Pinball level: 0.1' in html and 'Pinball level: 0.9' in html
        assert 'Loss: squared' in html and 'Material error threshold: 0.5' in html
    legacy = result.to_private_dict()
    for row in legacy['policy']['assessments']:
        for field in ('units', 'outcome_units', 'loss', 'level', 'material_error'): row.pop(field, None)
    legacy_html = render_report(legacy)
    assert 'Pinball level: 0.1' in legacy_html and 'Loss: squared' in legacy_html
    assert 'Material error threshold: 0.5' in legacy_html
    shared = PolicyResult.from_dict(public)
    assert shared.to_dict() == public
    with pytest.raises(EvaluationError): shared.to_dict(audience='local')
    # Uncontrolled unit text must not leak, nor leave its dependent conclusion.
    private = regression_study(tmp_path / 'private', units='Private unit name')
    selected = optimize_policies(private, CFG); key = selected.data['policy']['nomination']['policy_digest']
    metrics = [PolicyMetricSpec('risk', 'selective_risk', bounds=(0, 10), units='Private unit name')]
    protected = assess_policies(freeze_policy_family(selected, assessment=protocol(key, metrics)), CFG)
    hidden = protected.to_dict()
    assert hidden['policy']['assessments'] == [] and hidden['policy']['withheld_assessments'] == 1
    assert 'Private unit name' not in str(hidden) and 'Private unit name' not in render_report(hidden)
    approved = protected.to_dict(disclosure=DisclosureSpec(display_labels={'units:Private unit name': 'approved unit'}))
    assert approved['policy']['assessments'][0]['units'] == 'approved unit'


def test_D1_D5_owned_api_assessment_preserves_bounded_inference_and_semantics(tmp_path):
    from datatrust.web import create_app
    from .test_interfaces_history import BASE, wait
    spec = regression_study(tmp_path).to_dict()
    app = create_app(tmp_path / 'host', data_roots=(tmp_path,)); app.testing = True; client = app.test_client()
    try:
        headers = {'X-CSRF-Token': client.get(BASE + '/session').json['data']['csrf_token']}
        source = client.post(BASE + '/sources', headers=headers, json={'root_id': 'root_0', 'relative_path': 'predictions.csv'}).json['data']
        spec['input']['evaluation']['sources'] = [{'id': 'data', 'handle': source['handle']}]
        draft = client.post(BASE + '/policy-studies', headers=headers, json={'spec': spec, 'config': CFG.to_dict()}).json['data']
        def run(kind, **extra):
            posted = client.post(BASE + '/jobs', headers=headers, json={'kind': kind, 'client_request_id': kind,
                'policy_study_id': draft['id'], 'revision': 1, **extra})
            assert posted.status_code == 202, posted.json
            job = wait(client, posted.json['data']['id']); assert job['state'] == 'succeeded', job
            return job['output']
        inspected = run('policy_inspect')
        selected = run('policy_optimize', fingerprint=inspected['fingerprint']); rid = selected['result_id']
        key = client.get(BASE + f'/results/{rid}/policy/summary').json['data']['policy']['nomination']['policy_digest']
        metrics = regression_claims()
        plan = protocol(key, metrics).to_dict()
        frozen = client.post(BASE + '/policy-families', headers=headers, json={'result_id': rid, 'assessment': plan})
        assert frozen.status_code == 201, frozen.json
        handle = frozen.json['data']['handle']
        inspected = run('policy_assessment_inspect', family_handle=handle)
        assessed = run('policy_assess', family_handle=handle, assessment_fingerprint=inspected['fingerprint']); aid = assessed['result_id']
        public = client.get(BASE + f'/results/{aid}/policy/assessments?audience=shareable').json['data']['items']
        assert public[0]['level'] == .1 and public[1]['level'] == .9
        assert public[2]['loss'] == 'squared' and public[2]['state'] == 'inconclusive'
        assert public[2]['upper'] > .5 and public[3]['material_error'] == .5
        assert app.test_client().get(BASE + f'/results/{aid}/policy/assessments').status_code == 404
    finally:
        app.extensions['confidenceguard_store'].cleanup()
