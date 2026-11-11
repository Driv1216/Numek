"""Pre-H budgets must cover the numerical calls actually planned."""
from dataclasses import replace
from types import SimpleNamespace

import pytest

from confidenceguard.confirmation import feasibility
from confidenceguard.inference import preflight
from confidenceguard.investigation_contracts import ConfirmationSpec
from .helpers import binary


def kernel_work(protocol, *, records, units, family, ranked=False, components=1):
    helper = SimpleNamespace(adjustment='bonferroni', confidence=1-protocol.batch_alpha/components,
        minimum_tail=protocol.minimum_tail, replicates=protocol.replicates, work_units=10**15,
        mode='independent_rows')
    return preflight(helper, records, units, family, ranked=ranked)['estimated_work_units']


def test_ranking_inspection_includes_the_registered_kernel_setup_cost():
    protocol = ConfirmationSpec(method='percentile', replicate_policy='fixed')
    records, units, family = 8000, 8000, 10
    expected = family*kernel_work(protocol, records=records, units=units, family=family, ranked=True)
    result = feasibility(protocol, family, [1]*family, units=units, records=records,
        work_budget=expected-1, available_bytes=10**9, ranked=True).to_dict()
    assert result['estimated_work_units'] == expected
    assert result['status'] == 'not_admitted' and 'inference_work_limit' in result['reasons']


@pytest.mark.parametrize('counts', [[2], [1, 2, 1]])
def test_absolute_component_calls_are_not_counted_as_one_joint_call(counts):
    protocol = ConfirmationSpec(method='bca', replicate_policy='fixed')
    records, units, family = 400, 200, len(counts)
    expected = sum(c*kernel_work(protocol, records=records, units=units,
        family=family, components=c) for c in counts)
    result = feasibility(protocol, family, counts, units=units, records=records,
        work_budget=expected-1, available_bytes=10**9).to_dict()
    assert result['estimated_work_units'] == expected
    assert result['status'] == 'not_admitted' and 'inference_work_limit' in result['reasons']


def test_single_smooth_call_and_finite_component_accounting_are_preserved():
    protocol = ConfirmationSpec(method='bca', replicate_policy='fixed')
    expected = 3*kernel_work(protocol, records=400, units=200, family=3)
    result = feasibility(protocol, 3, [1]*3, units=200, records=400,
        work_budget=expected, available_bytes=10**9).to_dict()
    assert result['estimated_work_units'] == expected
    finite = feasibility(replace(protocol, method='finite'), 3, [1, 2, 4], units=200,
        records=400, work_budget=2800, available_bytes=10**9).to_dict()
    assert finite['estimated_work_units'] == 2800 and finite['effective_replicates'] == 0


def test_finite_budget_refuses_through_public_inspection_before_H_metrics(tmp_path):
    from confidenceguard import investigate, freeze_hypotheses, inspect_confirmation, confirm_investigation
    spec = binary(tmp_path)
    # Registered finite procedures retain a public numerical-capacity path;
    # general ranking approximations now refuse independently of capacity.
    old_work = 240*2-1
    spec = replace(spec, limits=replace(spec.limits, inference_work_units=old_work))
    result = investigate(spec)
    protocol = ConfirmationSpec(method='finite', upstream_independence='declared_independent',
        external_exposure='declared_unexposed', declaration_author='Synthetic budget fixture',
        declaration_reason='Independent synthetic rows, predeclared numerical budget, isolated process.')
    frozen = freeze_hypotheses(result, [result.data['investigation']['shortlist'][0]], confirmation=protocol)
    inspection = inspect_confirmation(frozen)
    assert not inspection['admissibility_reasons']
    assert inspection['feasibility']['status'] == 'not_admitted'
    assert inspection['feasibility']['estimated_work_units'] > old_work
    row = confirm_investigation(frozen).data['investigation']['assessments'][0]
    assert row['state'] == 'inconclusive' and not row['H_outcomes_disclosed']
    assert 'effect' not in row and 'member_metric' not in row and 'interval' not in row
