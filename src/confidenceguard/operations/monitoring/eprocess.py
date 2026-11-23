"""Sequential kernels for CG7 monitoring (plan G.3/G.4 as corrected by Addendum R2.4 and R2.5).

Proofs: ``docs/CG7_SEQUENTIAL_METHODS.md``. Qualification: ``validation/cg7/sequential_protocol.json``.

**SM1: bounded-mean e-CUSUM change detector with resets (R2.4).** Units ``X_i`` in [0, 1] (a
bounded statistic rescaled by its declared true bounds). For a null level ``m0`` in (0, 1) and a
fixed geometric grid ``lambda_k = (0.5 / m0) * 2**-k`` (k = 0..11, weights 1/12), each component is
the CUSUM e-detector ``C_t = max(C_{t-1}, 1) * (1 + lambda_k (X_t - m0))`` with ``C_0 = 0``; the
detector alarms when ``D_t = mean_k C_t^(k) >= 1/alpha`` and then resets every component to 0.
Under H0 (``E[X_i | past] <= m0`` for every i), for any horizon U that is a stopping time,
``E[N_U] <= alpha * E[U]`` (number of false alarms). Computed in log space.

**SM2: anytime-valid recovery test (R2.5).** The one-sided Hoeffding normal-mixture confidence
sequence for the running average of conditional means: with probability >= 1 - alpha, for every n,

    mean_mu_n <= mean_X_n + sqrt(2 (n/4 + rho) * log(sqrt((n/4 + rho) / rho) / alpha)) / n.

A recovery claim (R2: ``theta`` = declared acceptable risk; R3: ``theta = L_ref + Delta``) is made
when the upper sequence falls below ``theta`` with at least ``min_support`` units; it is valid under
any data-dependent checking schedule.

**Finite bounds** for references (Clopper-Pearson, Hoeffding) and the **detection planner**
(expected delay from the grid's worst-case growth rate, which for a given mean is attained by the
Bernoulli distribution, so it is conservative for any statistic in [0, 1]).
"""
import math
from dataclasses import dataclass, field

import numpy as np

GRID_SIZE = 12
MIN_RECOVERY_SUPPORT = 30


def _unit(values):
    x = np.asarray(values, dtype=float).reshape(-1)
    if not np.isfinite(x).all() or (x < 0).any() or (x > 1).any():
        raise ValueError('SM1/SM2 units must lie in [0, 1] (rescale by the declared true bounds).')
    return x


def grid(m0):
    if not 0 < m0 < 1:
        raise ValueError('The null level m0 must lie in (0, 1).')
    return (0.5 / m0) * 2.0 ** -np.arange(GRID_SIZE)


# SM1 -------------------------------------------------------------------------------------------------------
@dataclass
class EDetector:
    """SM1 e-CUSUM with resets. ``state()`` / ``from_state`` give an exact checkpoint."""
    m0: float
    alpha: float
    log_c: list = field(default=None)          # log C^(k); -inf encodes C = 0
    start: list = field(default=None)          # unit index where each component's current run began
    units: int = 0
    alarms: int = 0

    def __post_init__(self):
        if not 0 < self.alpha < 1:
            raise ValueError('alpha must lie in (0, 1).')
        self.lam = grid(self.m0)
        self.threshold = -math.log(self.alpha)
        if self.log_c is None:
            self.log_c = [-math.inf] * GRID_SIZE
            self.start = [0] * GRID_SIZE

    def update(self, values):
        """Process units in order. Returns alarms: [{unit, log_statistic, onset}] (``unit`` is 1-based)."""
        x = _unit(values)
        log_c = np.asarray(self.log_c, dtype=float)
        start = np.asarray(self.start, dtype=np.int64)
        out = []
        log_k = math.log(GRID_SIZE)
        for value in x:
            self.units += 1
            factor = np.log1p(self.lam * (value - self.m0))
            restart = log_c <= 0                            # max(C, 1) = 1: a new run starts at this unit
            start = np.where(restart, self.units, start)
            log_c = np.maximum(log_c, 0.0) + factor
            top = float(np.max(log_c))
            stat = top + math.log(np.exp(log_c - top).sum()) - log_k     # log mean_k C^(k)
            if stat >= self.threshold:
                self.alarms += 1
                out.append({'unit': self.units, 'log_statistic': stat,
                            'onset': int(start[int(np.argmax(log_c))])})   # descriptive onset (argmax start)
                log_c = np.full(GRID_SIZE, -math.inf)
                start = np.zeros(GRID_SIZE, dtype=np.int64)
        self.log_c, self.start = log_c.tolist(), start.tolist()
        return out

    def log_statistic(self):
        log_c = np.asarray(self.log_c, dtype=float)
        if np.isneginf(log_c).all():
            return -math.inf
        top = float(np.max(log_c))
        return top + math.log(np.exp(log_c - top).sum()) - math.log(GRID_SIZE)

    def state(self):
        return {'kernel': 'sm1_ecusum_resets_v1', 'm0': self.m0, 'alpha': self.alpha, 'units': self.units, 'alarms': self.alarms,
                'log_c': [None if math.isinf(v) else v for v in self.log_c], 'start': list(self.start)}

    @classmethod
    def from_state(cls, state):
        if state.get('kernel') != 'sm1_ecusum_resets_v1':
            raise ValueError('Unknown detector state.')
        return cls(state['m0'], state['alpha'], log_c=[-math.inf if v is None else v for v in state['log_c']],
                   start=list(state['start']), units=state['units'], alarms=state['alarms'])


def expected_false_alarms(alpha, units):
    """R2.4: E[N] <= alpha * E[U]; evaluated at an observed or planned volume (an estimate of the right-hand
    side, not a realized-period guarantee)."""
    return alpha * units


# SM2 -------------------------------------------------------------------------------------------------------
def recovery_upper(mean_x, n, rho, alpha):
    """Upper normal-mixture confidence sequence for the running average of conditional means."""
    if n <= 0:
        return math.inf
    v = n / 4 + rho
    return mean_x + math.sqrt(2 * v * math.log(math.sqrt(v / rho) / alpha)) / n


@dataclass
class RecoveryTest:
    """SM2: claims mean conditional risk since the verification start is below ``theta`` (R2/R3)."""
    theta: float
    alpha: float
    rho: float
    units: int = 0
    total: float = 0.0
    claimed_at: int | None = None
    min_support: int = MIN_RECOVERY_SUPPORT

    def __post_init__(self):
        if not 0 < self.alpha < 1 or self.rho <= 0 or not 0 <= self.theta <= 1:
            raise ValueError('Invalid recovery test.')

    @classmethod
    def planned(cls, theta, alpha, planned_support):
        """rho fixed before verification starts (R2.5 default: planned support / 4)."""
        return cls(theta, alpha, max(planned_support, 1) / 4)

    def update(self, values):
        for value in _unit(values):
            self.units += 1
            self.total += float(value)
            if self.claimed_at is None and self.units >= self.min_support and self.upper() < self.theta:
                self.claimed_at = self.units
        return self.claimed_at

    def upper(self):
        return recovery_upper(self.total / self.units, self.units, self.rho, self.alpha) if self.units else math.inf

    def state(self):
        return {'kernel': 'sm2_normal_mixture_cs_v1', 'theta': self.theta, 'alpha': self.alpha, 'rho': self.rho,
                'units': self.units, 'total': self.total, 'claimed_at': self.claimed_at, 'min_support': self.min_support}

    @classmethod
    def from_state(cls, state):
        if state.get('kernel') != 'sm2_normal_mixture_cs_v1':
            raise ValueError('Unknown recovery state.')
        return cls(state['theta'], state['alpha'], state['rho'], state['units'], state['total'], state['claimed_at'],
                   state['min_support'])


# Finite bounds ---------------------------------------------------------------------------------------------
def clopper_pearson(successes, n, alpha, side):
    """One-sided exact binomial bound at level 1 - alpha."""
    from scipy.stats import beta
    if n <= 0:
        return 1.0 if side == 'upper' else 0.0
    if side == 'upper':
        return 1.0 if successes >= n else float(beta.ppf(1 - alpha, successes + 1, n - successes))
    return 0.0 if successes <= 0 else float(beta.ppf(alpha, successes, n - successes + 1))


def hoeffding(mean, n, alpha, side, low=0.0, high=1.0):
    """One-sided Hoeffding bound for a mean of independent values in [low, high]."""
    if n <= 0:
        return high if side == 'upper' else low
    width = (high - low) * math.sqrt(math.log(1 / alpha) / (2 * n))
    return min(high, mean + width) if side == 'upper' else max(low, mean - width)


# Detection planner ---------------------------------------------------------------------------------------
def growth_rate(m0, m1, lam):
    """Expected log factor under a mean-m1 alternative. For a fixed mean the Bernoulli law minimizes it
    (log is concave), so this is a conservative rate for any statistic in [0, 1]."""
    return m1 * math.log1p(lam * (1 - m0)) + (1 - m1) * math.log1p(-lam * m0)


def plan_detection(m0, m1, alpha, *, units_per_day=None, max_useful_delay_days=None):
    """Planned expected detection delay of SM1 for a sustained shift from <= m0 to m1 (planner shown at inspection)."""
    rates = [growth_rate(m0, m1, lam) for lam in grid(m0)]
    best = max(rates)
    if m1 <= m0 or best <= 0:
        delay = math.inf
    else:
        delay = (math.log(1 / alpha) + math.log(GRID_SIZE)) / best
    out = {'m0': m0, 'm1': m1, 'alpha': alpha, 'expected_delay_units': delay, 'growth_rate': best,
           'kl_bernoulli': _kl(m1, m0) if 0 < m1 < 1 else None}
    if units_per_day:
        out['expected_delay_days'] = delay / units_per_day
        out['expected_false_alarms_per_30_days'] = expected_false_alarms(alpha, 30 * units_per_day)
    if max_useful_delay_days is not None and units_per_day:
        out['power'] = 'adequate' if out['expected_delay_days'] <= max_useful_delay_days else 'insufficient_power'
    return out


def _kl(p, q):
    return p * math.log(p / q) + (1 - p) * math.log((1 - p) / (1 - q))
