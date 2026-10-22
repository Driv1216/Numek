from dataclasses import replace
import math
import numpy as np
import pytest
from confidenceguard import LongitudinalInferenceSpec, EvaluationError
from confidenceguard.history_inference import historical_bootstrap


def records(offset=0, n=120, entities=False, bins=False):
    rng = np.random.default_rng(8+offset)
    return [(str(offset+i), 'entity-'+str(i//3) if entities else 'entity-'+str(offset+i),
             'target-'+str(offset+i), i*100 if bins else i, float(rng.normal()+offset/1000), 1., None) for i in range(n)]


def run(left, right, spec, **kwargs):
    return historical_bootstrap(left, right, spec, metric='bias', family_size=kwargs.pop('family_size', 1),
        check=lambda *a: None, available_bytes=128*1024**2, left_window=(0, len(left)*100), right_window=(0, len(right)*100), **kwargs)


def test_independent_periods_refuse_overlap_and_preserve_size():
    left, right = records(), records(1000)
    spec = LongitudinalInferenceSpec(mode='independent_periods', metrics=('bias',), independent_units=True,
                                    independent_periods=True, finite_moments=True)
    result = run(left, right, spec)
    assert result['status'] == 'available' and result['estimate'] > .5
    assert result['lower'] < result['estimate'] < result['upper']
    assert result['support'][0]['participating_units'] == len(left)
    assert run(left, left, spec)['reason'] == 'shared_opportunities_or_outcome_targets'
    assert run(left, right, replace(spec, known_serial_dependence=True))['reason'] == 'uncorrected_serial_dependence'
    assert run(left, right, spec, family_size=10)['reason'] == 'insufficient_tail_resolution'


def test_entity_cluster_union_and_event_weighting():
    left, right = records(0, 120, entities=True), records(1000, 180, entities=True)
    spec = LongitudinalInferenceSpec(mode='entity_clusters', metrics=('bias',), independent_units=True, finite_moments=True)
    result = run(left, right, spec)
    assert result['status'] == 'available'
    assert result['estimate'] == pytest.approx(np.mean([r[4] for r in right])-np.mean([r[4] for r in left]))
    assert result['support'][0]['participating_units'] == 40
    broken = list(right); broken[0] = (*broken[0][:2], left[0][2], *broken[0][3:])
    broken[0] = (broken[0][0], 'different-entity', *broken[0][2:])
    assert run(left, broken, spec)['reason'] == 'outcome_dependence_crosses_entities'


def test_moving_block_admission_and_replication():
    left = records(0, 300, bins=True); right = records(1000, 300, bins=True)
    spec = LongitudinalInferenceSpec(mode='moving_blocks', metrics=('bias',), stationary=True, independent_periods=True,
                                    finite_moments=True, complete_bins=True, bin_ns='100', block_length=5)
    result = run(left, right, spec)
    assert result['status'] == 'available' and result['block_length'] == 5
    assert result == run(left, right, spec)
    assert run(left, right, replace(spec, block_length=20))['reason'] == 'insufficient_block_equivalents'
    assert run(left, right, replace(spec, known_nonstationarity=True))['reason'] == 'nonstationary_regime'
    assert run(left, right, replace(spec, block_length=1))['reason'] == 'block_length_one_is_not_dependence_correction'


def test_degenerate_nonfinite_and_required_refusal():
    left, right = records(), records(1000)
    left = [(*r[:4], 0., 1., None) for r in left]; right = [(*r[:4], 1., 1., None) for r in right]
    spec = LongitudinalInferenceSpec(mode='independent_periods', metrics=('bias',), independent_units=True,
                                    independent_periods=True, finite_moments=True)
    assert run(left, right, spec)['reason'] == 'degenerate_bootstrap_distribution'
    right[0] = (*right[0][:4], math.inf, 1., None)
    assert run(left, right, spec)['reason'] == 'nonfinite_statistic'
    with pytest.raises(EvaluationError): run(left[:1], right, replace(spec, inference_required=True))


def test_block_sensitivity_retains_primary_and_refuses_long_alternative():
    spec=LongitudinalInferenceSpec(mode='moving_blocks',metrics=('bias',),stationary=True,independent_periods=True,
        finite_moments=True,complete_bins=True,bin_ns='100',block_length=5,sensitivity_lengths=(10,20))
    result=run(records(0,300,bins=True),records(1000,300,bins=True),spec)
    assert result['status']=='available' and result['block_length']==5
    assert result['sensitivity'][0]['status']=='available'
    assert result['sensitivity'][1]['reason']=='insufficient_block_equivalents'
    assert all(v['exploratory'] for v in result['sensitivity'])
