"""CG7 S5a: SM1 e-CUSUM with resets, SM2 normal-mixture confidence sequence, finite bounds, planner.

Focused arithmetic checks. The statistical qualification (exact enumeration, null simulations, planner
validity) is the locked protocol ``validation/cg7/sequential_protocol.json``, run once.
"""
import math

import numpy as np
import pytest
from scipy import integrate

from confidenceguard.operations.monitoring import eprocess as ep


def _brute_force(x, m0, alpha):
    """Definition: C_t = max over run starts s (after the last alarm) of prod_{i=s..t} factor_i; alarms reset."""
    lam = ep.grid(m0)
    alarms, last_reset = [], 0
    for t in range(1, len(x) + 1):
        best = np.zeros(ep.GRID_SIZE)
        for s in range(last_reset + 1, t + 1):
            best = np.maximum(best, np.prod(1 + np.outer(x[s - 1:t] - m0, lam), axis=0))
        if best.mean() >= 1 / alpha:
            alarms.append(t)
            last_reset = t
    return alarms


@pytest.mark.parametrize('m0', [0.05, 0.3, 0.6])
def test_sm1_recursion_equals_definition_with_resets(m0):
    rng = np.random.default_rng(7)
    for trial in range(6):
        x = rng.binomial(1, min(0.95, 2.5 * m0), 60).astype(float) if trial % 2 else rng.uniform(0, 1, 60)
        alpha = 0.02
        detector = ep.EDetector(m0, alpha)
        found = [a['unit'] for a in detector.update(x)]
        assert found == _brute_force(x, m0, alpha)


def test_sm1_cusum_never_exceeds_shiryaev_roberts():
    rng = np.random.default_rng(3)
    m0, x = 0.2, rng.uniform(0, 0.5, 400)
    lam = ep.grid(m0)
    detector = ep.EDetector(m0, 1e-300)                     # no alarms: compare the raw recursions
    sr = np.zeros(ep.GRID_SIZE)
    for value in x:
        detector.update([value])
        sr = (sr + 1) * (1 + lam * (value - m0))
        assert np.all(np.exp(detector.log_c) <= sr * (1 + 1e-12))


def test_sm1_checkpoint_is_exact_and_chunking_invariant():
    rng = np.random.default_rng(11)
    x = np.concatenate([rng.binomial(1, 0.05, 3000), rng.binomial(1, 0.15, 3000)]).astype(float)
    whole = ep.EDetector(0.06, 1e-4)
    alarms_whole = whole.update(x)
    pieces, alarms = ep.EDetector(0.06, 1e-4), []
    for chunk in np.array_split(x, 17):
        restored = ep.EDetector.from_state(pieces.state())
        alarms += restored.update(chunk)
        pieces = restored
    assert alarms == alarms_whole and alarms_whole
    assert pieces.state() == whole.state()


def test_sm1_detects_a_shift_and_reports_a_descriptive_onset():
    rng = np.random.default_rng(1)
    detector = ep.EDetector(0.063, 2e-8)
    assert detector.update(rng.binomial(1, 0.063, 20000)) == []
    alarm = detector.update(rng.binomial(1, 0.08, 40000))[0]
    assert 20000 < alarm['unit'] < 60000 and alarm['onset'] > 15000
    assert alarm['log_statistic'] >= -math.log(2e-8)
    assert detector.log_statistic() < alarm['log_statistic']      # reset after the alarm


def test_sm1_refusals():
    with pytest.raises(ValueError):
        ep.EDetector(1.0, 0.01)
    with pytest.raises(ValueError):
        ep.EDetector(0.0, 0.01)
    with pytest.raises(ValueError):
        ep.EDetector(0.2, 1.0)
    detector = ep.EDetector(0.2, 0.01)
    for bad in ([1.2], [-0.1], [float('nan')]):
        with pytest.raises(ValueError):
            detector.update(bad)
    assert detector.units == 0
    with pytest.raises(ValueError):
        ep.EDetector.from_state({'kernel': 'other'})


def test_sm1_log_space_is_stable_far_beyond_float_range():
    """A sustained extreme shift: the log statistic stays finite and alarms keep resetting."""
    detector = ep.EDetector(0.001, 1e-12)
    alarms = detector.update(np.ones(5000))
    assert alarms and all(math.isfinite(a['log_statistic']) for a in alarms)
    detector = ep.EDetector(0.5, 1e-300)
    detector.update(np.zeros(200000))                       # long null run toward 0: never -inf, never NaN
    assert all(math.isfinite(v) for v in detector.log_c)


def _mixture(s, n, rho):
    """Independent implementation: integrate exp(l*s - l^2 n / 8) against N(0, 1/rho)."""
    def integrand(lam):
        return math.exp(lam * s - lam * lam * n / 8) * math.sqrt(rho / (2 * math.pi)) * math.exp(-rho * lam * lam / 2)
    value, _ = integrate.quad(integrand, -np.inf, np.inf, limit=400)
    return value


@pytest.mark.parametrize('n,rho,alpha', [(30, 25.0, 0.05), (400, 100.0, 0.05), (2000, 500.0, 0.01), (50, 1.0, 0.1)])
def test_sm2_boundary_inverts_the_normal_mixture(n, rho, alpha):
    width = ep.recovery_upper(0.0, n, rho, alpha) * n           # S at which the mixture equals 1/alpha
    assert _mixture(width, n, rho) == pytest.approx(1 / alpha, rel=1e-6)
    assert _mixture(width * 0.99, n, rho) < 1 / alpha


def test_sm2_claims_only_with_support_and_checkpoints():
    test = ep.RecoveryTest.planned(theta=0.9, alpha=0.05, planned_support=30)
    assert test.rho == 7.5
    assert test.update(np.zeros(29)) is None and test.upper() < 0.9    # bound already below: support blocks
    assert test.update([0.0]) == 30
    restored = ep.RecoveryTest.from_state(test.state())
    assert restored.claimed_at == 30 and restored.upper() == test.upper()
    tight = ep.RecoveryTest.planned(theta=0.2, alpha=0.05, planned_support=400)
    claimed = tight.update(np.zeros(400))
    first = next(n for n in range(30, 401) if ep.recovery_upper(0.0, n, 100.0, 0.05) < 0.2)
    assert claimed == first
    rng = np.random.default_rng(2)
    worse = ep.RecoveryTest.planned(theta=0.1, alpha=0.05, planned_support=400)
    assert worse.update(rng.binomial(1, 0.12, 4000)) is None
    with pytest.raises(ValueError):
        ep.RecoveryTest(theta=0.1, alpha=0.05, rho=0)


def test_finite_bounds():
    assert ep.clopper_pearson(0, 200, 0.05, 'upper') == pytest.approx(1 - 0.05 ** (1 / 200))
    assert ep.clopper_pearson(200, 200, 0.05, 'lower') == pytest.approx(0.05 ** (1 / 200))
    assert ep.clopper_pearson(0, 200, 0.05, 'lower') == 0.0 and ep.clopper_pearson(5, 5, 0.05, 'upper') == 1.0
    lo, hi = ep.clopper_pearson(30, 300, 0.05, 'lower'), ep.clopper_pearson(30, 300, 0.05, 'upper')
    assert lo < 0.1 < hi
    assert ep.hoeffding(0.5, 200, 0.05, 'upper') == pytest.approx(0.5 + math.sqrt(math.log(20) / 400))
    assert ep.hoeffding(0.5, 200, 0.05, 'lower', 0, 2) == pytest.approx(0.5 - 2 * math.sqrt(math.log(20) / 400))


def test_planner():
    plan = ep.plan_detection(0.063, 0.08, 2e-8, units_per_day=20000, max_useful_delay_days=7)
    assert plan['power'] == 'adequate' and plan['expected_delay_days'] < 1
    assert plan['growth_rate'] <= plan['kl_bernoulli']           # the grid cannot beat the KL rate
    slow = ep.plan_detection(0.0075, 0.01, 2e-8, units_per_day=500, max_useful_delay_days=30)
    assert slow['power'] == 'insufficient_power'
    assert ep.plan_detection(0.1, 0.1, 0.01)['expected_delay_units'] == math.inf
    # Bernoulli is the worst case for a bounded statistic with the same mean.
    lam = ep.grid(0.1)[3]
    rng = np.random.default_rng(0)
    beta = rng.beta(2, 8, 400000)                                   # mean 0.2
    assert np.mean(np.log1p(lam * (beta - 0.1))) >= ep.growth_rate(0.1, 0.2, lam) - 1e-3
