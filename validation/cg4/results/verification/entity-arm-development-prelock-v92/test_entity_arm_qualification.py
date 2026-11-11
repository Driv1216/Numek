"""Numerical and denominator checks for the fixed new-design qualification."""
import importlib
import json
from pathlib import Path

import numpy as np
import pytest
from scipy.stats import binomtest


@pytest.fixture
def harness(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2]/'validation/cg4'))
    return importlib.import_module('qualify_entity_arms')


def test_vector_components_match_public_exact_intervals_and_keep_empty_arms(harness):
    counts = np.tile([20., 2., 17., 7.], (2, 32, 1))
    counts[1, 0] = [0, 0, 17, 7]
    for m in (1, 10, 32):
        lo, hi = harness.intervals(counts, m, 'binary')
        a = binomtest(2, 20).proportion_ci(confidence_level=1-.05/(2*m), method='exact')
        b = binomtest(7, 17).proportion_ci(confidence_level=1-.05/(2*m), method='exact')
        assert lo[0, 0] == pytest.approx(a.low-b.high, abs=5e-11)
        assert hi[0, 0] == pytest.approx(a.high-b.low, abs=5e-11)
        assert np.isnan(lo[1, 0]) and np.isnan(hi[1, 0])
    zero, one = harness.cp(np.array([1, 1]), np.array([0, 1]), .025)
    assert zero[0] == 0 and one[1] == 1


def test_fixed_protocol_keeps_all_families_and_separate_power_denominator(harness):
    protocol = harness.PROTOCOL
    assert protocol['families'] == [1, 10, 32]
    ranges = [set(range(p['start'], p['start']+p['trials'])) for p in protocol['scenarios'].values()]
    assert sum(len(s) for s in ranges) == len(set.union(*ranges)) == 32000
    assert protocol['scenarios']['partial_null_power']['families'] == [32]
    assert protocol['scenarios']['rare_observed_binary']['observed'] == [.6, .8]


def test_small_development_shape_and_power_summary_are_serializable(harness, tmp_path):
    spec = {**harness.PROTOCOL['scenarios']['partial_null_power'], 'entities': 16, 'trials': 2}
    result = harness.panel('partial_null_power', spec, tmp_path)
    assert result['power']['trials'] == 2 and result['power']['refusals_in_denominator']
    assert type(result['power']['criterion_met']) is bool
    assert result['families'][0]['family_noncoverage']['trials'] == 2
    json.dumps(result, allow_nan=False)
    array = np.load(tmp_path/'partial_null_power-counts.npy', allow_pickle=False)
    assert array.shape == (2, 32, 4) and not array.dtype.hasobject
