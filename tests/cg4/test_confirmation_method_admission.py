"""Unsupported, predeclared inference routes must refuse before H metrics."""
from dataclasses import replace
import csv

import pytest

from confidenceguard import ConfirmationSpec, freeze_hypotheses, investigate
from confidenceguard.confirmation import confirm_investigation, inspect_confirmation
from confidenceguard.investigation import arguments, prepared
from confidenceguard.investigation_objectives import bind
from confidenceguard.investigation_contracts import InvestigationSpec
from .helpers import binary


@pytest.mark.parametrize(('metric', 'sampling', 'reason'), [
    ('error_rate', 'independent_entities', 'finite_row_methods_do_not_correct_entity_dependence'),
    ('roc_auc', 'independent_rows', 'ranking_finite_method_not_registered'),
    ('log_loss', 'independent_rows', 'finite_inference_requires_registered_bounded_contributions'),
])
def test_unregistered_finite_route_refuses_before_H(tmp_path, metric, sampling, reason):
    spec = binary(tmp_path)
    spec = replace(spec, objectives=(replace(spec.objectives[0], metric=metric, direction='auto', units=None),))
    result = investigate(spec)
    protocol = ConfirmationSpec(sampling=sampling, upstream_independence='declared_independent',
        external_exposure='declared_unexposed', declaration_author='synthetic fixture',
        declaration_reason='Isolated independent synthetic entities for method-admission checks.')
    frozen = freeze_hypotheses(result, [result.data['investigation']['shortlist'][0]], confirmation=protocol)
    preview = inspect_confirmation(frozen)
    assert not preview['H_outcomes_disclosed']
    assert reason in preview['membership'][0]['admissibility_reasons']
    assessment = confirm_investigation(frozen).data['investigation']['assessments'][0]
    assert assessment['state'] == 'statistically_inadmissible'
    assert reason in assessment['reason']
    assert assessment['H_outcomes_disclosed'] is False
    assert not {'member_metric', 'comparator_metric', 'effect', 'interval'} & assessment.keys()


def test_nonadditive_regression_refuses_even_with_declared_point_loss_bounds(tmp_path):
    packet = binary(tmp_path).to_dict()
    packet['evaluation']['task'] = {'kind': 'regression', 'outcome_definition': 'Synthetic numeric target'}
    packet['evaluation']['runs'][0].pop('probabilities')
    packet['objectives'] = [{'id': 'quantile_failure', 'metric': 'p90_absolute_error', 'run': 'model',
        'practical_threshold': .1, 'bounds': [0., 1.]}]
    result = investigate(InvestigationSpec.from_dict(packet))
    protocol = ConfirmationSpec(upstream_independence='declared_independent',
        external_exposure='declared_unexposed', declaration_author='synthetic fixture',
        declaration_reason='Isolated independent synthetic numeric rows.')
    frozen = freeze_hypotheses(result, [result.data['investigation']['shortlist'][0]], confirmation=protocol)
    preview = inspect_confirmation(frozen)
    assert preview['membership'][0]['admissibility_reasons'] == ['native_nonadditive_interval_not_registered']
    row = confirm_investigation(frozen).data['investigation']['assessments'][0]
    assert row['state'] == 'statistically_inadmissible' and not row['H_outcomes_disclosed']
    assert 'effect' not in row


@pytest.mark.parametrize(('metric', 'bounds'), [('f1', ()), ('log_loss', (0., 5.))])
def test_registered_composition_and_declared_bounded_mean_remain_admitted(tmp_path, metric, bounds):
    spec = binary(tmp_path)
    spec = replace(spec, objectives=(replace(spec.objectives[0], metric=metric,
        direction='auto', units=None, bounds=bounds),))
    result = investigate(spec)
    protocol = ConfirmationSpec(upstream_independence='declared_independent',
        external_exposure='declared_unexposed', declaration_author='synthetic fixture',
        declaration_reason='Independent synthetic rows; probability construction bounds log loss below five nats.')
    frozen = freeze_hypotheses(result, [result.data['investigation']['shortlist'][0]], confirmation=protocol)
    preview = inspect_confirmation(frozen)
    assert not preview['admissibility_reasons'] and not preview['membership'][0]['admissibility_reasons']
    row = confirm_investigation(frozen).data['investigation']['assessments'][0]
    assert row['H_outcomes_disclosed'] and row['strength'] == 'finite_sample'
    assert row['inference']['method'] == ('confusion_cell_exact_composition' if metric == 'f1' else 'hoeffding_component_bonferroni')


def uncertainty_fixture(tmp_path):
    packet = binary(tmp_path).to_dict()
    packet['evaluation']['task'] = {'kind': 'regression', 'outcome_definition': 'Synthetic numeric target'}
    run = packet['evaluation']['runs'][0]
    run.pop('probabilities')
    run['intervals'] = [{'id': 'band', 'lower': 'decision', 'upper': 'decision',
        'meaning': 'prediction', 'coverage': .9, 'central': True}]
    packet['objectives'] = [{'id': 'coverage', 'metric': 'interval_coverage@0.9', 'run': 'model',
        'direction': 'lower', 'practical_threshold': .1}]
    return packet


def test_uncertainty_loss_materialization_keeps_H_sealed(tmp_path):
    spec = InvestigationSpec.from_dict(uncertainty_fixture(tmp_path))
    s, c, roots = arguments(spec, None, None)
    with prepared(s, c, roots) as p:
        objective = bind(s.objectives[0], p.store)
        rows = p.store.con.execute(f'SELECT r.cg4_role, count(*) FROM {objective.loss_table} x '
            f'JOIN {objective.table} r USING(event_key) WHERE x.metric=? GROUP BY r.cg4_role',
            [objective.spec.metric]).fetchall()
        assert dict(rows) == {'D': 240, 'S': 240}
        _, eligible, values = objective.training('D')
        assert eligible.sum() == 240 and set(values[eligible]) == {0., 1.}


def test_future_H_only_uncertainty_inspection_does_not_need_D_S_outcomes(tmp_path):
    packet = uncertainty_fixture(tmp_path)
    spec = InvestigationSpec.from_dict(packet)
    result = investigate(spec)
    protocol = ConfirmationSpec(upstream_independence='declared_independent',
        external_exposure='declared_unexposed', declaration_author='synthetic fixture',
        declaration_reason='Independent held-out entities; H-only file preserves original model/output semantics.')
    frozen = freeze_hypotheses(result, [result.data['investigation']['shortlist'][0]], confirmation=protocol)
    with (tmp_path/'predictions.csv').open() as stream:
        records = [row for row in csv.DictReader(stream) if row['role'] == 'H']
    future = tmp_path/'H-only.csv'
    with future.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=records[0]); writer.writeheader(); writer.writerows(records)
    packet['evaluation']['sources'][0]['path'] = str(future)
    future_spec = InvestigationSpec.from_dict(packet)
    preview = inspect_confirmation(frozen, confirmation_input=future_spec)
    assert not preview['H_outcomes_disclosed'] and not preview['admissibility_reasons']
    assert not preview['membership'][0]['admissibility_reasons']
    row = confirm_investigation(frozen, confirmation_input=future_spec).data['investigation']['assessments'][0]
    assert row['strength'] == 'finite_sample' and row['H_outcomes_disclosed']
    assert row['inference']['method'] == 'clopper_pearson_component_bonferroni'
