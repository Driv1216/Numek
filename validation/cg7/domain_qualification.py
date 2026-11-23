"""CG7 Q-DC: null qualification of the domain-classifier exploratory permutation test (locked protocol; run once).

    python validation/cg7/domain_qualification.py
    python validation/cg7/domain_qualification.py --rerun --reason "<implementation bug>"
"""
import argparse
import hashlib
import json
import platform
import sys
import time
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from confidenceguard.operations.intelligence import domain  # noqa: E402

PROTOCOL = Path(__file__).with_name('domain_protocol.json')
KINDS = {'region': 'categorical', 'channel': 'categorical', 'income': 'numeric', 'tenure': 'numeric'}


def arm(rng, n, prefix):
    rows = []
    for i in range(n):
        features = {'region': rng.choice(['north', 'south', 'east', 'west'], p=[.4, .3, .2, .1]),
                    'channel': rng.choice(['web', 'branch', 'phone']),
                    'income': f'{rng.lognormal(10, 0.5):.2f}',
                    'tenure': None if rng.random() < 0.1 else f'{rng.integers(0, 240)}'}
        rows.append((hashlib.sha256(f'{prefix}-{i}'.encode()).digest(), features))
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--rerun', action='store_true')
    parser.add_argument('--reason')
    args = parser.parse_args()
    raw = PROTOCOL.read_bytes()
    protocol = json.loads(raw)
    digest = hashlib.sha256(raw).hexdigest()
    out_path = ROOT / protocol['results']
    existing = json.loads(out_path.read_text()) if out_path.exists() else None
    if existing and existing['protocol_sha256'] != digest:
        raise SystemExit('The protocol changed after the locked run; refusing.')
    if existing and not (args.rerun and args.reason):
        raise SystemExit('The locked run already exists; only --rerun --reason <implementation bug> is allowed.')
    panel = protocol['panel']
    rng = np.random.default_rng(panel['seed'])
    secret = hashlib.sha256(b'q-dc split secret').digest()
    started = time.perf_counter()
    p_values, refused = [], 0
    for run in range(panel['runs']):
        result = domain.core(arm(rng, panel['entities_per_arm'], f'r{run}'), arm(rng, panel['entities_per_arm'], f'c{run}'), KINDS,
                             secret, permutations=panel['permutations'], importance=False, seed=run)
        test = result.get('exploratory_test') or {}
        if test.get('state') != 'completed':
            refused += 1
            continue
        p_values.append(test['p_value'])
    rejections = sum(1 for p in p_values if p <= panel['level'])
    binomial_p = float(stats.binom.sf(rejections - 1, len(p_values), panel['level'])) if p_values else None
    outcome = {'runs': panel['runs'], 'completed_tests': len(p_values), 'refused_tests': refused, 'rejections': rejections,
               'rejection_rate': rejections / len(p_values) if p_values else None, 'binomial_p': binomial_p,
               'pass': bool(p_values) and refused == 0 and binomial_p >= 0.001, 'seconds': round(time.perf_counter() - started, 1),
               'p_value_deciles': [float(np.quantile(p_values, q)) for q in np.linspace(0.1, 0.9, 9)] if p_values else None}
    results = existing or {'protocol': str(PROTOCOL.relative_to(ROOT)), 'protocol_sha256': digest, 'reruns': [],
                           'environment': {'python': platform.python_version(), 'numpy': np.__version__,
                                           'sklearn': __import__('sklearn').__version__, 'machine': platform.machine()}}
    if existing:
        results['reruns'].append({'reason': args.reason, 'original': existing.get('outcome'), 'at': time.strftime('%Y-%m-%dT%H:%M:%S')})
    results['outcome'] = outcome
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=1, sort_keys=True))
    print('pass' if outcome['pass'] else 'FAIL', json.dumps({k: v for k, v in outcome.items() if k != 'p_value_deciles'}))


if __name__ == '__main__':
    main()
