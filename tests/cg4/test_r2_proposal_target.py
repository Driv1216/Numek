"""R2's residual proxy must respect the native metric's adverse direction."""
from dataclasses import replace

import numpy as np
import pytest

from confidenceguard import InvestigationSpec, investigate
from confidenceguard.discovery_rules import heads
from confidenceguard.investigation import arguments, prepared
from confidenceguard.investigation_objectives import bind
from .helpers import binary


def regression_fixture(tmp_path):
    packet = binary(tmp_path).to_dict()
    packet['evaluation']['task'] = {'kind': 'regression', 'outcome_definition': 'Synthetic numeric target'}
    packet['evaluation']['runs'][0].pop('probabilities')
    packet['objectives'] = [{'id': 'r2_failure', 'metric': 'r2', 'run': 'model', 'practical_threshold': .1}]
    return InvestigationSpec.from_dict(packet)


def test_r2_proxy_direction_and_authoritative_reducer(tmp_path):
    spec = regression_fixture(tmp_path)
    s, c, roots = arguments(spec, None, None)
    with prepared(s, c, roots) as p:
        objective = bind(s.objectives[0], p.store)
        keys, eligible, target = objective.training('D')
        records = [p.run_records['model'][key] for key in keys]
        squared_error = np.array([(row['point'] - row['y_num']) ** 2 for row in records])
        assert np.array_equal(target[eligible], -squared_error[eligible])
        assert np.array_equal(heads(objective, target)[0][1][eligible], squared_error[eligible])
        assert objective.identity['diagnostic_target_policy'] == 'negative_squared_residual_for_r2_v2'
        assert objective.identity['learning_target'] == '-(pow(point-y_num,2))'
        native = objective.evaluate("cg4_role='D'", 'r2_native_reference')
        truth = np.array([row['y_num'] for row in records])[eligible]
        assert native['value'] == pytest.approx(1 - np.mean(squared_error[eligible]) / np.var(truth))
        opposite = bind(replace(s.objectives[0], direction='higher'), p.store)
        _, allowed, transformed = opposite.training('D')
        assert np.array_equal(heads(opposite, transformed)[0][1][allowed], -squared_error[allowed])


def test_default_lower_r2_discovers_worse_native_regions(tmp_path):
    result = investigate(regression_fixture(tmp_path))
    selected = set(result.data['investigation']['shortlist'])
    assert selected
    for candidate in result.data['investigation']['candidates']:
        if candidate['id'] in selected:
            assert candidate['S']['effect'] == pytest.approx(4.)
            assert candidate['S']['member_metric']['value'] == pytest.approx(-3.)
            assert candidate['S']['comparator_metric']['value'] == pytest.approx(1.)
