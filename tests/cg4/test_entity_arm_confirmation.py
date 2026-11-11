"""Explicit one-observation-per-arm design; no generic entity-bootstrap claim."""
import csv
from dataclasses import replace
import math

import numpy as np
import pytest
from scipy.stats import binomtest

from confidenceguard import ConfirmationSpec, InvestigationSpec, freeze_hypotheses, investigate
from confidenceguard.confirmation import _entity_arm_refusal, confirm_investigation, inspect_confirmation
from confidenceguard.contracts import EvaluationError
from .helpers import binary


def protocol():
    return ConfirmationSpec(sampling='independent_entity_arms',
        upstream_independence='declared_independent', external_exposure='declared_unexposed',
        declaration_author='synthetic design',
        declaration_reason='Complete independent entity records; at most one potential observation in each frozen comparison arm.')


def paired_events(tmp_path, *, per_entity=2, hide_repeated_labels=False, comparator='complement'):
    spec = binary(tmp_path)
    path = tmp_path/'predictions.csv'
    with path.open() as stream:
        records = list(csv.DictReader(stream))
    seen = set()
    for i, row in enumerate(records):
        row['entity'] = row['role']+'-'+str(i//(3*per_entity))
        if row['role'] == 'H' and hide_repeated_labels and row['entity'] in seen:
            row['y'] = ''
        seen.add(row['entity'])
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=records[0]); writer.writeheader(); writer.writerows(records)
    return replace(spec, objectives=(replace(spec.objectives[0], comparator=comparator),))


def broad_failure(result):
    # S-only choice, independently of H and of any oracle entity mapping.
    return max((c for c in result.data['investigation']['candidates'] if c['S']['effect'] is not None),
        key=lambda c: (c['S']['effect'], c['S']['conditional_members']))


def test_dependent_observations_across_arms_use_native_finite_components(tmp_path):
    result = investigate(paired_events(tmp_path))
    candidate = broad_failure(result)
    assert candidate['S']['conditional_members'] == 120
    frozen = freeze_hypotheses(result, [candidate['id']], confirmation=protocol())
    inspection = inspect_confirmation(frozen)
    assert not inspection['admissibility_reasons']
    assert not inspection['membership'][0]['admissibility_reasons']
    assert inspection['feasibility']['independent_units'] == 120
    row = confirm_investigation(frozen).data['investigation']['assessments'][0]
    assert row['state'] == 'confirmed' and row['strength'] == 'finite_sample'
    assert row['support']['conditional_members'] == row['support']['conditional_nonmembers'] == 120
    a = binomtest(120, 120).proportion_ci(confidence_level=.975, method='exact')
    b = binomtest(0, 120).proportion_ci(confidence_level=.975, method='exact')
    assert row['interval']['lower'] == pytest.approx(a.low-b.high)
    assert row['interval']['upper'] == pytest.approx(a.high-b.low)
    assert row['independence_qualification']['sampling_design'] == 'independent_entity_arms'
    assert row['inference']['sampling_design'] == 'independent_entity_arms'
    old = freeze_hypotheses(result, [candidate['id']], confirmation=replace(protocol(), sampling='independent_entities'))
    refused = confirm_investigation(old).data['investigation']['assessments'][0]
    assert refused['state'] == 'statistically_inadmissible' and not refused['H_outcomes_disclosed']


@pytest.mark.parametrize(('per_entity', 'hide_labels', 'comparator'), [
    (3, False, 'complement'), (3, True, 'complement'), (2, False, 'overall'),
])
def test_repeated_potential_records_refuse_before_label_filtering(tmp_path, per_entity, hide_labels, comparator):
    result = investigate(paired_events(tmp_path, per_entity=per_entity,
        hide_repeated_labels=hide_labels, comparator=comparator))
    frozen = freeze_hypotheses(result, [broad_failure(result)['id']], confirmation=protocol())
    reason = 'multiple_potential_observations_per_entity_in_an_arm'
    preview = inspect_confirmation(frozen)
    assert reason in preview['membership'][0]['admissibility_reasons']
    row = confirm_investigation(frozen).data['investigation']['assessments'][0]
    assert row['state'] == 'statistically_inadmissible' and not row['H_outcomes_disclosed']
    assert 'effect' not in row


def test_arm_design_cannot_select_bootstrap_or_omit_entity_role_assignment(tmp_path):
    with pytest.raises(EvaluationError, match='finite'):
        replace(protocol(), method='percentile')
    result = investigate(paired_events(tmp_path))
    frozen = freeze_hypotheses(result, [broad_failure(result)['id']], confirmation=protocol())
    assert frozen.data['confirmation_spec']['sampling'] == 'independent_entity_arms'
    rows = paired_events(tmp_path)
    rows = replace(rows, roles=replace(rows.roles, unit='independent_rows'))
    result = investigate(rows)
    frozen = freeze_hypotheses(result, [broad_failure(result)['id']], confirmation=protocol())
    preview = inspect_confirmation(frozen)
    assert 'entity_arm_confirmation_requires_entity_role_assignment' in preview['admissibility_reasons']


def test_structural_check_uses_comparator_and_periods_without_outcomes(tmp_path):
    objective = paired_events(tmp_path).objectives[0]
    records = [{'entity_key': 'a', 'cg4_period': p} for p in ['now', 'before', 'outside']]
    mask = {'member': np.array([True, False, False]), 'available': np.ones(3, bool)}
    assert _entity_arm_refusal(records, mask, replace(objective, comparator='paired', reference_run='other')) is None
    assert _entity_arm_refusal(records, mask, replace(objective, comparator='ceiling', ceiling=.1)) is None
    assert _entity_arm_refusal(records, mask, objective) == 'multiple_potential_observations_per_entity_in_an_arm'
    mask['member'][:] = True
    dated = replace(objective, comparator='reference_period', current_period='now', reference_period='before')
    assert _entity_arm_refusal(records, mask, dated) is None
    records[2]['cg4_period'] = 'now'
    assert _entity_arm_refusal(records, mask, dated) == 'multiple_potential_observations_per_entity_in_an_arm'
    mask['available'][2] = False
    assert _entity_arm_refusal(records, mask, dated) is None


def test_inadmissible_region_remains_in_the_confirmation_family(tmp_path):
    result = investigate(paired_events(tmp_path))
    broad = broad_failure(result)
    narrow = next(c for c in result.data['investigation']['candidates']
        if c['S']['effect'] is not None and c['S']['effect'] > 0 and c['S']['conditional_members'] == 60)
    assert narrow['S']['effect'] == pytest.approx(2/3)
    frozen = freeze_hypotheses(result, [broad['id'], narrow['id']], confirmation=protocol())
    assessed = confirm_investigation(frozen).data['investigation']['assessments']
    by_candidate = {r['candidate_id']: r for r in assessed}
    assert len(assessed) == 2
    assert by_candidate[narrow['id']]['state'] == 'statistically_inadmissible'
    assert not by_candidate[narrow['id']]['H_outcomes_disclosed']
    row = by_candidate[broad['id']]
    assert row['interval']['family_size'] == 2
    a = binomtest(120, 120).proportion_ci(confidence_level=.9875, method='exact')
    b = binomtest(0, 120).proportion_ci(confidence_level=.9875, method='exact')
    assert row['interval']['lower'] == pytest.approx(a.low-b.high)


def test_bounded_mean_preserves_event_weighted_native_metric(tmp_path):
    packet = paired_events(tmp_path).to_dict()
    packet['evaluation']['task'] = {'kind': 'regression', 'outcome_definition': 'Synthetic numeric target'}
    packet['evaluation']['runs'][0].pop('probabilities')
    packet['objectives'] = [{'id': 'mae', 'metric': 'mae', 'run': 'model',
        'bounds': [0., 1.], 'practical_threshold': .1}]
    result = investigate(InvestigationSpec.from_dict(packet))
    frozen = freeze_hypotheses(result, [broad_failure(result)['id']], confirmation=protocol())
    row = confirm_investigation(frozen).data['investigation']['assessments'][0]
    assert row['state'] == 'confirmed' and row['effect'] == 1
    epsilon = math.sqrt(math.log(80)/240)
    assert row['interval']['lower'] == pytest.approx(1-2*epsilon)
    assert row['inference']['method'] == 'hoeffding_component_bonferroni'


def test_retained_one_event_per_period_can_confirm_with_entity_separation(tmp_path):
    from confidenceguard import ReliabilityWorkspace, WorkspaceConfig
    source = tmp_path/'periods.csv'
    records = []
    for entity in range(600):
        hot = (entity//2)%2 == 1
        y = entity%2
        for period, when in [('reference', '2026-01-01T00:00:00Z'), ('current', '2026-02-01T00:00:00Z')]:
            error = period == 'current' or not hot
            records.append({'id': f'{period}-{entity}', 'entity': str(entity), 'y': str(y),
                'decision': str(y^int(error)), 'hot': str(hot).lower(), 'when': when,
                'available': '2026-03-01T00:00:00Z'})
    with source.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=records[0]); writer.writeheader(); writer.writerows(records)
    namespace = 'entity-arm-history-'+tmp_path.name
    evaluation = {'task': {'kind': 'binary_classification', 'outcome_definition': 'Synthetic paired periods',
        'classes': ['0', '1'], 'positive_class': '1'}, 'sources': [{'id': 'data', 'path': str(source)}],
        'runs': [{'id': 'model', 'source': 'data', 'model': {'id': 'fixed', 'version': '1'},
            'key_columns': ['id'], 'entity_columns': ['entity'], 'prediction': 'decision', 'prediction_at': {'column': 'when'}}],
        'outcomes': {'source': 'data', 'column': 'y', 'key_columns': ['id'], 'available_at': {'column': 'available'}}}
    view = {'id': 'context', 'availability': 'at_decision',
        'fields': [{'id': 'hot', 'column': 'hot', 'kind': 'boolean'}]}
    workspace = ReliabilityWorkspace.initialize(tmp_path/'workspace', WorkspaceConfig(saving=True, free_disk_bytes=1))
    workspace.evidence_tracking(True)
    workspace.ingest({'schema_version': 'confidenceguard.prediction_batch_spec/2.0', 'namespace': namespace,
        'evaluation': evaluation, 'outcome_definition_version': 'v1', 'bindings': [{'run': 'model'}], 'feature_views': [view]})
    variant = workspace.models()[0]['id']
    spec = InvestigationSpec.from_dict({'history': {'workspace_path': str(workspace.path), 'selection': {
        'namespace': namespace, 'variants': [variant], 'as_of': '2026-04-01T00:00:00Z', 'windows': [
            {'id': 'reference', 'start': '2026-01-01T00:00:00Z', 'end': '2026-02-01T00:00:00Z'},
            {'id': 'current', 'start': '2026-02-01T00:00:00Z', 'end': '2026-03-01T00:00:00Z'}]}},
        'roles': {'namespace': namespace, 'unit': 'entity'}, 'features': [view], 'strategies': ['structured'],
        'objectives': [{'id': 'deterioration', 'metric': 'error_rate', 'run': variant,
            'comparator': 'reference_period', 'reference_period': 'reference', 'current_period': 'current',
            'practical_threshold': .15}],
        'limits': {'max_depth': 1, 'max_nodes': 1000, 'candidates_per_strategy': 16, 'stability_replicates': 1}})
    discovered = workspace.investigate(spec)
    frozen = freeze_hypotheses(discovered, [broad_failure(discovered)['id']], confirmation=protocol())
    original = frozen.to_dict()
    preview = inspect_confirmation(frozen, workspace=workspace)
    assert not preview['H_outcomes_disclosed'] and not preview['admissibility_reasons']
    assessed = workspace.confirm_investigation(frozen)
    row = assessed.data['investigation']['assessments'][0]
    assert row['state'] == 'confirmed' and row['effect'] == 1 and row['strength'] == 'finite_sample'
    assert row['support']['members'] == 2*row['support']['conditional_members']
    assert row['support']['conditional_members'] == row['support']['conditional_nonmembers']
    assert frozen.to_dict() == original
    public = assessed.to_dict()['investigation']['assessments'][0]
    assert public['independence_qualification']['sampling_design'] == 'independent_entity_arms'
