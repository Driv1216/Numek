"""CG7 M.2 statistical qualification of SM1/SM2 (locked protocol ``sequential_protocol.json``; run once).

    python validation/cg7/sequential_qualification.py            # every panel, once
    python validation/cg7/sequential_qualification.py --rerun Q-E2 --reason "<implementation bug>"

The results file records the protocol digest; a changed protocol or an existing result refuses a plain run.
A rerun (implementation bug only, per the stopping rule) keeps the original panel outcome next to the rerun.
"""
import argparse
import hashlib
import json
import math
import platform
import sys
import time
from pathlib import Path

import numpy as np
from scipy import integrate, stats

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from confidenceguard.operations.monitoring import eprocess as ep  # noqa: E402

PROTOCOL = Path(__file__).with_name('sequential_protocol.json')


# Vectorized SM1 (same arithmetic as EDetector, across trials) -----------------------------------------------
def sm1_batch(x, m0, alpha, *, stop_when_all_alarmed=False):
    """x: (trials, n). Returns (alarm counts, first alarm unit or 0)."""
    trials, n = x.shape
    lam = ep.grid(m0)
    threshold, log_k = -math.log(alpha), math.log(ep.GRID_SIZE)
    log_c = np.full((trials, ep.GRID_SIZE), -np.inf)
    counts = np.zeros(trials, dtype=np.int64)
    first = np.zeros(trials, dtype=np.int64)
    for t in range(n):
        log_c = np.maximum(log_c, 0.0) + np.log1p(np.outer(x[:, t] - m0, lam))
        top = log_c.max(axis=1)
        stat = top + np.log(np.exp(log_c - top[:, None]).sum(axis=1)) - log_k
        hit = stat >= threshold
        if hit.any():
            counts[hit] += 1
            first[hit & (first == 0)] = t + 1
            log_c[hit] = -np.inf
            if stop_when_all_alarmed and (first > 0).all():
                break
    return counts, first


def check_sm1_equivalence(x, m0, alpha, counts, first, k=20):
    for i in range(min(k, len(x))):
        alarms = ep.EDetector(m0, alpha).update(x[i])
        if len(alarms) != counts[i] or (alarms[0]['unit'] if alarms else 0) != first[i]:
            raise SystemExit(f'implementation mismatch: vectorized SM1 differs from EDetector on trial {i}')


def binomial_upper_p(k, n, p):
    return float(stats.binom.sf(k - 1, n, p))


# Q-E1 ------------------------------------------------------------------------------------------------------
def q_e1a(spec):
    rows, n = [], spec['n']
    for m0 in spec['m0']:
        for alpha in spec['alpha']:
            lam = ep.grid(m0)
            threshold, log_k = -math.log(alpha), math.log(ep.GRID_SIZE)
            log_c = np.full((1, ep.GRID_SIZE), -np.inf)
            logp = np.zeros(1)
            count = np.zeros(1)
            ever = np.zeros(1, dtype=bool)
            worst = 0.0
            per_t = []
            for t in range(1, n + 1):
                log_c = np.concatenate([log_c, log_c])
                logp = np.concatenate([logp + math.log1p(-m0), logp + math.log(m0)])
                count, ever = np.concatenate([count, count]), np.concatenate([ever, ever])
                xs = np.concatenate([np.zeros(len(log_c) // 2), np.ones(len(log_c) // 2)])
                log_c = np.maximum(log_c, 0.0) + np.log1p(np.outer(xs - m0, lam))
                top = log_c.max(axis=1)
                stat = top + np.log(np.exp(log_c - top[:, None]).sum(axis=1)) - log_k
                hit = stat >= threshold
                count += hit
                ever |= hit
                log_c[hit] = -np.inf
                p = np.exp(logp)
                expected, prob_any = float(p @ count), float(p[ever].sum())
                worst = max(worst, expected / (t * alpha), prob_any / (t * alpha))
                per_t.append({'t': t, 'expected_alarms': expected, 'p_any_alarm': prob_any, 'bound': t * alpha})
            ok = all(r['expected_alarms'] <= r['bound'] + 1e-12 and r['p_any_alarm'] <= r['bound'] + 1e-12 for r in per_t)
            rows.append({'m0': m0, 'alpha': alpha, 'paths': 2 ** n, 'at_n': per_t[-1], 'max_ratio_to_bound': worst, 'pass': ok})
    return {'cases': rows, 'pass': all(r['pass'] for r in rows)}


def _brute(x, m0, alpha):
    lam = ep.grid(m0)
    alarms, last, sr, cusum_le_sr = [], 0, np.zeros(ep.GRID_SIZE), True
    for t in range(1, len(x) + 1):
        best = np.zeros(ep.GRID_SIZE)
        for s in range(last + 1, t + 1):
            best = np.maximum(best, np.prod(1 + np.outer(x[s - 1:t] - m0, lam), axis=0))
        sr = (sr + 1) * (1 + lam * (x[t - 1] - m0))
        cusum_le_sr &= bool(np.all(best <= sr * (1 + 1e-12)))
        if best.mean() >= 1 / alpha:
            alarms.append(t)
            last = t
            sr = np.zeros(ep.GRID_SIZE)
    return alarms, cusum_le_sr


def q_e1b(spec):
    rng = np.random.default_rng(spec['seed'])
    mismatches, sr_ok, alarms_seen = 0, True, 0
    for i in range(spec['paths']):
        m0 = float(rng.choice([0.03, 0.1, 0.3, 0.6]))
        alpha = float(rng.choice([0.005, 0.02, 0.1]))
        x = (rng.binomial(1, min(0.97, rng.uniform(0.5, 3) * m0), spec['length']).astype(float) if i % 2
             else rng.uniform(0, min(1, 3 * m0), spec['length']))
        expected, le = _brute(x, m0, alpha)
        found = [a['unit'] for a in ep.EDetector(m0, alpha).update(x)]
        mismatches += found != expected
        sr_ok &= le
        alarms_seen += len(expected)
    return {'paths': spec['paths'], 'alarms_compared': alarms_seen, 'mismatches': int(mismatches),
            'cusum_le_shiryaev_roberts': bool(sr_ok), 'pass': mismatches == 0 and bool(sr_ok)}


def q_e1c(spec):
    """Chunked Lindley form: log C_t = S_t - min(-max(L_0, 0), min_{1<=s<t} S_s) within a segment."""
    rng = np.random.default_rng(spec['seed'])
    m0, alpha, total = spec['m0'], spec['alpha'], spec['units']
    lam = ep.grid(m0)
    threshold, log_k = -math.log(alpha), math.log(ep.GRID_SIZE)
    chunk, check_at = 500_000, 200_000
    carry = np.full(ep.GRID_SIZE, -np.inf)
    alarms, done, finite, stat_at_check, prefix_x = [], 0, True, None, None
    while done < total:
        x = rng.binomial(1, m0, min(chunk, total - done)).astype(float)
        if prefix_x is None:
            prefix_x = x[:check_at].copy()
        g = np.log1p(np.outer(x - m0, lam))
        start = 0
        while start < len(x):
            s = np.cumsum(g[start:], axis=0)
            base = -np.maximum(carry, 0.0)
            prior = np.vstack([base[None, :], np.minimum(base[None, :], np.minimum.accumulate(s[:-1], axis=0))])
            log_c = s - prior
            top = log_c.max(axis=1)
            stat = top + np.log(np.exp(log_c - top[:, None]).sum(axis=1)) - log_k
            hits = np.flatnonzero(stat >= threshold)
            end = int(hits[0]) if hits.size else len(stat) - 1
            offset = done + start                                  # global unit of stat[0] is offset + 1
            if stat_at_check is None and offset < check_at <= offset + end + 1:
                stat_at_check = float(stat[check_at - offset - 1])
            if hits.size:
                alarms.append({'unit': offset + end + 1, 'log_statistic': float(stat[end])})
                carry = np.full(ep.GRID_SIZE, -np.inf)
                start += end + 1
                if start >= len(x) and stat_at_check is None and offset + end + 1 == check_at:
                    stat_at_check = float(stat[end])
                continue
            carry = log_c[-1]
            break
        finite &= bool(np.all(np.isfinite(carry) | np.isneginf(carry)))
        done += len(x)
    detector = ep.EDetector(m0, alpha)
    det_alarms = [a['unit'] for a in detector.update(prefix_x)]
    lindley_alarms = [a['unit'] for a in alarms if a['unit'] <= check_at]
    prefix_ok = det_alarms == lindley_alarms
    if not det_alarms or det_alarms[-1] != check_at:
        prefix_ok &= stat_at_check is not None and abs(detector.log_statistic() - stat_at_check) < 1e-9
    return {'units': total, 'alarms': len(alarms), 'alarm_units': [a['unit'] for a in alarms][:50],
            'alpha_times_units': alpha * total, 'state_finite': finite, 'prefix_equal_to_edetector': bool(prefix_ok),
            'final_state': [None if math.isinf(v) else float(v) for v in carry], 'pass': finite and bool(prefix_ok)}


def q_e1d(spec):
    rows = []
    alpha, horizon, support = spec['alpha'], spec['horizon'], spec['min_support']
    rho = horizon / 4
    for theta in spec['theta']:
        dist = np.zeros(horizon + 1)
        dist[0] = 1.0
        claimed = 0.0
        for n in range(1, horizon + 1):
            new = dist * (1 - theta)
            new[1:] += dist[:-1] * theta
            dist = new
            if n >= support:
                sums = np.arange(horizon + 1)
                upper = sums / n + math.sqrt(2 * (n / 4 + rho) * math.log(math.sqrt((n / 4 + rho) / rho) / alpha)) / n
                claim = (upper < theta) & (sums <= n)
                claimed += float(dist[claim].sum())
                dist[claim] = 0.0
        rows.append({'theta': theta, 'exact_false_claim_probability': claimed, 'alpha': alpha, 'pass': claimed <= alpha})
    integration = []
    for n, r, a in spec['integration_points']:
        width = ep.recovery_upper(0.0, n, r, a) * n
        f = (lambda lam, n=n, r=r, width=width: math.exp(lam * width - lam * lam * n / 8 - r * lam * lam / 2) * math.sqrt(r / (2 * math.pi)))
        value, _ = integrate.quad(f, -np.inf, np.inf, limit=400)
        integration.append({'n': n, 'rho': r, 'alpha': a, 'mixture_at_boundary': value, 'target': 1 / a,
                            'pass': abs(value * a - 1) < 1e-6})
    return {'exact': rows, 'closed_form': integration,
            'pass': all(r['pass'] for r in rows) and all(r['pass'] for r in integration)}


# Generators ------------------------------------------------------------------------------------------------
def generate(kind, spec, trials, n, rng):
    if kind == 'bernoulli':
        return rng.binomial(1, spec['m0'], (trials, n)).astype(float)
    if kind == 'bernoulli_true':
        return rng.binomial(1, spec['true_mean'], (trials, n)).astype(float)
    if kind == 'beta':
        return rng.beta(spec['a'], spec['b'], (trials, n))
    if kind == 'markov':
        lo, hi = spec['means'][1], spec['means'][0]
        state = np.zeros((trials, n), dtype=bool)
        cur = rng.random(trials) < 0.5
        switches = rng.random((trials, n)) < spec['switch']
        for t in range(n):
            cur = np.where(switches[:, t], ~cur, cur)
            state[:, t] = cur
        return rng.binomial(1, np.where(state, hi, lo)).astype(float)
    if kind == 'entity_first':
        risk = rng.beta(*spec['risk_beta'], (trials, n))        # first event of each entity: independent units
        return rng.binomial(1, risk).astype(float)
    if kind == 'entity_bursts':
        bursts = n // spec['burst'] + 1
        risk = np.repeat(rng.beta(*spec['risk_beta'], (trials, bursts)), spec['burst'], axis=1)[:, :n]
        return rng.binomial(1, risk).astype(float)
    if kind == 'blocks':
        blocks = n // spec['block'] + 1
        shift = np.where(rng.random((trials, blocks)) < 0.5, spec['shift'], -spec['shift'])
        mean = spec['m0'] + np.repeat(shift, spec['block'], axis=1)[:, :n]
        return rng.binomial(1, mean).astype(float)
    raise ValueError(kind)


def _sm1_panel(spec, verdict):
    rng = np.random.default_rng(spec['seed'])
    trials, n = spec['trials'], spec['n']
    alpha = spec['n_alpha'] / n
    out = {}
    for name, gen in spec['generators'].items():
        started = time.perf_counter()
        x = generate(gen['kind'], gen, trials, n, rng)
        counts, first = sm1_batch(x, gen['m0'], alpha)
        check_sm1_equivalence(x, gen['m0'], alpha, counts, first)
        any_alarm = int((counts > 0).sum())
        mean = float(counts.mean())
        lower = mean - stats.norm.ppf(0.999) * float(counts.std(ddof=1)) / math.sqrt(trials) if counts.any() else 0.0
        row = {'trials': trials, 'n': n, 'alpha': alpha, 'n_alpha': spec['n_alpha'], 'first_alarm_trials': any_alarm,
               'first_alarm_rate': any_alarm / trials, 'mean_alarms': mean, 'mean_alarms_lower_0999': float(lower),
               'binomial_p': binomial_upper_p(any_alarm, trials, spec['n_alpha']),
               'seconds': round(time.perf_counter() - started, 1)}
        if verdict:
            row['pass'] = bool(row['binomial_p'] >= 0.001 and lower <= spec['n_alpha'])
        out[name] = row
    return out


def q_e2(spec):
    panels = _sm1_panel(spec, True)
    return {'panels': panels, 'pass': all(p['pass'] for p in panels.values())}


def q_e4(spec):
    return {'panels': _sm1_panel(spec, False), 'pass': None, 'note': 'documented limits; no acceptance'}


def q_e3(spec):
    rng = np.random.default_rng(spec['seed'])
    trials, horizon, alpha = spec['trials'], spec['horizon'], spec['alpha']
    rho = horizon / 4
    n = np.arange(1, horizon + 1)
    width = np.sqrt(2 * (n / 4 + rho) * np.log(np.sqrt((n / 4 + rho) / rho) / alpha)) / n
    out = {}
    for name, gen in spec['generators'].items():
        theta = gen['theta']
        if gen['kind'] == 'constant':
            mu = np.full(horizon, theta)
        elif gen['kind'] == 'alternating':
            mu = np.where(n % 2 == 1, theta + gen['d'], theta - gen['d'])
        else:                                                      # drifting: running average >= theta to the horizon
            mu = theta + gen['d'] * (1 - 2 * (n - 1) / (horizon - 1))
        running = np.cumsum(mu) / n
        assert np.all(running >= theta - 1e-12)
        x = rng.binomial(1, np.broadcast_to(mu, (trials, horizon))).astype(float)
        upper = np.cumsum(x, axis=1) / n + width
        claim = (upper < theta) & (n >= ep.MIN_RECOVERY_SUPPORT)
        claimed = claim.any(axis=1)
        for i in range(20):                                        # equivalence with RecoveryTest
            test = ep.RecoveryTest(theta, alpha, rho)
            got = test.update(x[i])
            want = int(np.argmax(claim[i]) + 1) if claimed[i] else None
            if got != want:
                raise SystemExit(f'implementation mismatch: vectorized SM2 differs from RecoveryTest ({name}, trial {i})')
        k = int(claimed.sum())
        p = binomial_upper_p(k, trials, alpha)
        out[name] = {'trials': trials, 'false_claims': k, 'rate': k / trials, 'alpha': alpha, 'binomial_p': p, 'pass': p >= 0.001}
    return {'panels': out, 'pass': all(r['pass'] for r in out.values())}


def q_e5(spec):
    rng = np.random.default_rng(spec['seed'])
    out = {}
    for name, sc in spec['scenarios'].items():
        alpha = spec['target_false_alarms_per_30_days'] / (30 * sc['units_per_day'])
        plan = ep.plan_detection(sc['m0'], sc['m1'], alpha, units_per_day=sc['units_per_day'])
        cap = int(math.ceil(10 * plan['expected_delay_units']))
        trials = spec['trials']
        first = np.zeros(trials, dtype=np.int64)
        lam = ep.grid(sc['m0'])
        threshold, log_k = -math.log(alpha), math.log(ep.GRID_SIZE)
        log_c = np.full((trials, ep.GRID_SIZE), -np.inf)
        block = 20000
        t = 0
        while t < cap and (first == 0).any():
            x = rng.binomial(1, sc['m1'], (trials, min(block, cap - t))).astype(float)
            for j in range(x.shape[1]):
                log_c = np.maximum(log_c, 0.0) + np.log1p(np.outer(x[:, j] - sc['m0'], lam))
                top = log_c.max(axis=1)
                stat = top + np.log(np.exp(log_c - top[:, None]).sum(axis=1)) - log_k
                hit = (stat >= threshold) & (first == 0)
                first[hit] = t + j + 1
                if (first > 0).all():
                    break
            t += x.shape[1]
        delays = np.where(first == 0, cap, first)
        median = float(np.median(delays))
        ratio = median / plan['expected_delay_units']
        out[name] = {'m0': sc['m0'], 'm1': sc['m1'], 'alpha': alpha, 'predicted_delay_units': plan['expected_delay_units'],
                     'predicted_delay_days': plan['expected_delay_days'], 'observed_median_units': median,
                     'observed_quartiles': [float(np.quantile(delays, 0.25)), float(np.quantile(delays, 0.75))],
                     'capped_trials': int((first == 0).sum()), 'ratio': ratio, 'pass': 0.5 <= ratio <= 1.5}
    return {'scenarios': out, 'pass': all(r['pass'] for r in out.values())}


def _plain(value):
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(type(value).__name__)


PANELS = {'Q-E1a': q_e1a, 'Q-E1b': q_e1b, 'Q-E1c': q_e1c, 'Q-E1d': q_e1d, 'Q-E2': q_e2, 'Q-E3': q_e3,
          'Q-E4': q_e4, 'Q-E5': q_e5}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--rerun')
    parser.add_argument('--reason')
    parser.add_argument('--resume', action='store_true', help='run panels that have no recorded outcome yet (first runs)')
    args = parser.parse_args()
    raw = PROTOCOL.read_bytes()
    protocol = json.loads(raw)
    digest = hashlib.sha256(raw).hexdigest()
    out_path = ROOT / protocol['results']
    existing = json.loads(out_path.read_text()) if out_path.exists() else None
    if existing and existing['protocol_sha256'] != digest:
        raise SystemExit('The protocol changed after the locked run; refusing.')
    if existing and not (args.rerun or args.resume):
        raise SystemExit('The locked run already exists; only --rerun <panel> --reason <implementation bug> is allowed.')
    if args.rerun and (not existing or not args.reason or args.rerun not in PANELS):
        raise SystemExit('A rerun needs an existing run, a known panel and a reason.')
    results = existing or {'protocol': str(PROTOCOL.relative_to(ROOT)), 'protocol_sha256': digest, 'panels': {}, 'reruns': [],
                           'environment': {'python': platform.python_version(), 'numpy': np.__version__,
                                           'scipy': __import__('scipy').__version__, 'machine': platform.machine(),
                                           'system': platform.system()}}
    todo = [args.rerun] if args.rerun else [p for p in PANELS if p not in results['panels']]
    for name in todo:
        started = time.perf_counter()
        outcome = PANELS[name](protocol['panels'][name])
        outcome['seconds'] = round(time.perf_counter() - started, 1)
        if args.rerun:
            results['reruns'].append({'panel': name, 'reason': args.reason, 'original': results['panels'].get(name),
                                      'at': time.strftime('%Y-%m-%dT%H:%M:%S')})
        results['panels'][name] = outcome
        print(name, 'pass' if outcome['pass'] else ('recorded' if outcome['pass'] is None else 'FAIL'), outcome['seconds'], 's', flush=True)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(results, indent=1, sort_keys=True, default=_plain))
    verdicts = [p['pass'] for p in results['panels'].values() if p['pass'] is not None]
    results['all_pass'] = all(verdicts)
    out_path.write_text(json.dumps(results, indent=1, sort_keys=True, default=_plain))
    print('all pass' if results['all_pass'] else 'FAILURES RECORDED')


if __name__ == '__main__':
    main()
