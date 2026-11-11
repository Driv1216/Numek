"""Protect the new validation panel's estimands and diagnostic denominators."""
import json
import math
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'validation/cg4'))
from qualify_studentized import aggregate, sample, support, summary, SCENARIOS


def test_known_truths_and_complete_cluster_event_weighting():
    for scenario in SCENARIOS:
        values, units, truth, ceiling = sample(7, scenario)
        assert values.shape == (len(units), 4)
        expected = math.exp(1.5**2/2) if scenario == 'lognormal_ceiling' else 1. if scenario == 'exponential_ceiling' else 0.
        assert truth == expected
        assert (ceiling == 0.) == scenario.endswith('_ceiling')
        combined = aggregate(values, units)
        assert combined.shape == (200, 4)
        np.testing.assert_allclose(combined.sum(axis=0), values.sum(axis=0), rtol=1e-14, atol=1e-12)
        for unit in (0, 99, 100, 199):
            np.testing.assert_allclose(combined[unit], values[units == unit].sum(axis=0), rtol=1e-14)
        assert all(a['independent_units'] >= 100 for a in support(combined, ceiling))
    paired, _, _, _ = sample(7, 'paired_common_heavy')
    assert np.all(paired[:, (1, 3)] == 1)
    assert np.corrcoef(paired[:, 0], paired[:, 2])[0, 1] > .9


def test_diagnostics_count_refusals_and_both_directions_and_serialize():
    rows = []
    for scenario in SCENARIOS:
        for seed in range(1000):
            # One refusal, two lower errors, three upper errors, no other errors.
            measured = {'status': 'unavailable', 'reason': 'test_refusal'} if seed == 0 else {
                'status': 'available', 'lower': 1. if seed <= 2 else -1.,
                'upper': -0.5 if 3 <= seed <= 5 else 2.}
            rows.append({'scenario': scenario, 'seed': seed, 'truth': 0., 'result': measured})
    result = summary(rows, 'qualification'); json.dumps(result, allow_nan=False)
    assert result['panel_complete'] and result['screening_criteria_met']
    assert len(result['diagnostics']) == 30
    for row in result['rows']:
        assert row['available'] == 999 and row['noncoverage'] == 5
        assert row['lower_above_truth'] == 2 and row['upper_below_truth'] == 3
        assert row['coverage_bounds_with_refusals'] == [.994, .995]
        assert row['unconditional_wrong_positive_claim_rate'] == .002
    incomplete = summary(rows[:10], 'development'); json.dumps(incomplete, allow_nan=False)
    assert not incomplete['panel_complete'] and not incomplete['screening_criteria_met']
    assert all(d['Holm_rejected'] is None for d in incomplete['diagnostics'])
