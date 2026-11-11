"""R2 benchmark semantics and the residual proxy's variance limitation."""
import csv
import json
from pathlib import Path

import numpy as np
import pytest

from confidenceguard.investigation import arguments, prepared
from confidenceguard.investigation_objectives import bind


def test_r2_anchor_is_regression_with_fresh_seeds_and_native_units(tmp_path, monkeypatch):
    directory = Path(__file__).resolve().parents[2]/'validation/cg4'
    monkeypatch.syspath_prepend(str(directory))
    import qualify_objectives as benchmarks
    spec, truth = benchmarks.generate(tmp_path, 7, 2000, 'regression_r2')
    assert spec.evaluation.task.kind == 'regression'
    assert spec.objectives[0].metric == 'r2'
    assert spec.objectives[0].units == 'dimensionless'
    assert benchmarks.PROTOCOL['panel_specific_seed_ranges']['regression_r2'] == [480000, 480039]
    assert not spec.objectives[0].bounds
    with (tmp_path/'predictions.csv').open() as stream:
        rows = list(csv.DictReader(stream))
    y = np.array([float(row['outcome']) for row in rows])
    point = np.array([float(row['prediction']) for row in rows])
    # A distinct objective generator must not accidentally retain binary outputs.
    assert np.unique(y).size == len(y) and np.var(point[truth]-y[truth]) > 10
    s, c, roots = arguments(spec, None, None)
    with prepared(s, c, roots) as evidence:
        objective = bind(spec.objectives[0], evidence.store)
        native = objective.evaluate("cg4_role='D'", 'r2_anchor_reference')
        keys, eligible, target = objective.training('D')
        records = [evidence.run_records['candidate'][key] for key in keys]
        actual = np.array([r['y_num'] for r in records])[eligible]
        residual = np.array([r['point']-r['y_num'] for r in records])[eligible]
        assert native['value'] == pytest.approx(1-np.mean(residual**2)/np.var(actual))
        np.testing.assert_allclose(target[eligible], -(residual**2))


def test_lower_squared_error_alone_does_not_order_subgroup_r2(tmp_path, monkeypatch):
    """An analytical counterexample; no universal recovery claim from the anchor."""
    directory = Path(__file__).resolve().parents[2]/'validation/cg4'
    monkeypatch.syspath_prepend(str(directory))
    import qualify_objectives as benchmarks
    spec, _ = benchmarks.generate(tmp_path, 8, 2000, 'regression_r2')
    path = tmp_path/'predictions.csv'
    with path.open() as stream:
        rows = list(csv.DictReader(stream))
    for i, row in enumerate(rows):
        # Both groups have symmetric target supports. The low-error group has much
        # smaller outcome variance, so its native R2 is far worse.
        hot = row['a'] == '1'
        y = (-1 if i % 2 else 1) * (.1 if hot else 10.)
        row['outcome'] = str(y)
        row['prediction'] = str(y + (1. if hot else 2.))
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0]); writer.writeheader(); writer.writerows(rows)
    s, c, roots = arguments(spec, None, None)
    with prepared(s, c, roots) as evidence:
        objective = bind(spec.objectives[0], evidence.store)
        keys, eligible, proxy = objective.training('D')
        records = [evidence.run_records['candidate'][key] for key in keys]
        ids = np.array([int(json.loads(key)[0]) for key in keys])
        hot = np.array([rows[i]['a'] == '1' for i in ids])
        metrics = []
        for mask in (hot & eligible, ~hot & eligible):
            y = np.array([r['y_num'] for r in records])[mask]
            e = np.array([r['point']-r['y_num'] for r in records])[mask]
            metrics.append(1-np.mean(e**2)/np.var(y))
        assert metrics[0] < -90 and metrics[1] > .95
        # The registered proxy instead ranks the background squared error higher.
        assert -proxy[~hot & eligible].mean() > -proxy[hot & eligible].mean()
