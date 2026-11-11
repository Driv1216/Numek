"""Benchmark input admission: generated numeric evidence must be usable."""
import csv
import importlib.util
import json
from pathlib import Path

import numpy as np

from confidenceguard.features import normalize, value


def test_synthetic_recovery_generator_uses_finite_lexical_float_coordinates(tmp_path,monkeypatch):
    path = Path(__file__).resolve().parents[2]/'validation/cg4/qualify_pipeline.py'
    monkeypatch.syspath_prepend(str(path.parent))
    module_spec = importlib.util.spec_from_file_location('_cg4_qualification_generator', path)
    module = importlib.util.module_from_spec(module_spec); module_spec.loader.exec_module(module)
    specification, _, _ = module.generate(tmp_path, 5, 100, 'categorical_numeric_conjunction')
    with (tmp_path/'predictions.csv').open() as stream: rows = list(csv.DictReader(stream))
    vectors = np.load(tmp_path/'vectors.npy', allow_pickle=False)
    fields = {field.id: field for field in specification.features[0].fields}
    for index, row in enumerate(rows):
        for column, coordinate in (('x', 0), ('y', 1)):
            cell = normalize(row[column], fields[column])
            assert cell['state'] == 'observed'
            assert np.float32(value(cell)) == vectors[index, coordinate]
            assert 'np.' not in row[column]


def test_historical_panel_keeps_whole_entities_and_dated_label_availability(tmp_path,monkeypatch):
    directory=Path(__file__).resolve().parents[2]/'validation/cg4'
    monkeypatch.syspath_prepend(str(directory))
    import qualify_history
    batch,view,truth=qualify_history.generate(tmp_path,17,120)
    with (tmp_path/'predictions.csv').open() as stream:rows=list(csv.DictReader(stream))
    assert len(rows)==240 and len({row['entity'] for row in rows})==120
    for row in rows:
        assert truth[row['id']]==(row['a']=='1' and float(row['x'])>.5)
        assert row['when']<row['available'] and 'np.' not in row['x']
    assert all((rows[i]['entity'],rows[i]['x'],rows[i]['a'])==(rows[i+120]['entity'],rows[i+120]['x'],rows[i+120]['a']) for i in range(120))
    assert batch['evaluation']['runs'][0]['entity_columns']==['entity']
    assert batch['evaluation']['outcomes']['available_at']=={'column':'available'}


def test_component_power_injection_preserves_denominators_and_cluster_estimand(monkeypatch):
    directory=Path(__file__).resolve().parents[2]/'validation/cg4'
    monkeypatch.syspath_prepend(str(directory))
    import qualify_component_power as power
    from qualify_approximate import sample
    for scenario in power.SCENARIOS:
        original,_,_,units,_=sample(17,scenario)
        values,objective,spec,actual_units=power.power_sample(17,scenario)
        np.testing.assert_array_equal(actual_units,units)
        np.testing.assert_array_equal(values[:,:2],original[:,:2])
        np.testing.assert_array_equal(values[:,3],original[:,3])
        assert np.isfinite(values).all() and values.shape==original.shape
        assert abs((values[:,2].sum()-original[:,2].sum())/values[:,3].sum()-1.)<1e-12
        assert objective.practical_threshold==.15
        arms=power.support(values,actual_units)
        assert all(a['independent_units']==100 and a['effective_units']>=30 for a in arms)
        assert sum(a['events'] for a in arms)==len(values)
        assert spec.sampling==('independent_entities' if 'clusters' in scenario else 'independent_rows')
    # Refused intervals stay in the denominator, never count as power success.
    fake=[{'scenario':'normal_mean','result':{'status':'unavailable','reason':'fixture'}} for _ in range(1000)]
    report=power.summary(fake,'qualification')['rows'][0]
    assert report['trials']==1000 and report['confirmations']==0 and not report['criterion_met']
    json.dumps(report,allow_nan=False)
    positive=[{'scenario':'normal_mean','result':{'status':'available','lower':.8,'upper':1.2}} for _ in range(1000)]
    report=power.summary(positive,'qualification')['rows'][0]
    assert report['criterion_met'] and report['confirmations']==1000
    json.dumps(report,allow_nan=False)
