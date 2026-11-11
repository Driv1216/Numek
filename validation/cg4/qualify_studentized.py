"""Separate locked bootstrap-t candidate panels; no product-method activation.

Coverage, directional error and availability are assessed separately. In particular,
a favorable symmetric contrast cannot qualify a mean ceiling or asymmetric arms.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import inspect
import json
from pathlib import Path
import time

import numpy as np
from scipy.stats import binomtest
from threadpoolctl import threadpool_limits

from studentized_candidate import estimates, studentized, METHOD

SCENARIOS = ('normal_contrast', 'exponential_contrast', 'lognormal_contrast',
             'heavy_member_light_comparator', 'light_member_heavy_comparator',
             'unequal_complete_clusters', 'paired_common_heavy',
             'normal_ceiling', 'exponential_ceiling', 'lognormal_ceiling')
PROTOCOL = {
    'schema_version': 'numek.cg4_studentized_candidate_panel/1.0', 'method': METHOD,
    'scenarios': list(SCENARIOS), 'development_seed_range': [0, 9],
    'qualification_seed_range': [220000, 220999], 'independent_units': 200,
    'replicates': 20000, 'confidence': .95, 'family_size': 1,
    'elementary_intervals': 1, 'minimum_conditional_units': 30,
    'variance': 'Analytic ratio influence covariance, n/(n-1); no inner bootstrap.',
    'sampling': 'Independent rows or complete independent entities; event-weighted ratios.',
    'diagnostics': 'One-sided exact binomial excess-error diagnostics at .05 total and .025 per endpoint, conditional on available intervals; Holm across all 30 diagnostics only after every locked panel completes. Also show unconditional wrong claims and refusal bounds.',
    'availability': 'Bonferroni simultaneous two-sided exact Monte Carlo lower bounds must exceed .90 across the 10 scenarios.',
    'acceptance': 'All 1000 seeds in each scenario, no Holm-rejected excess-error diagnostic, and all availability bounds above .90. Non-rejection is not a coverage theorem; a failure remains negative evidence. Power, extreme family tails and full-pipeline qualification are separate required gates.',
    'rationale': '1000 trials resolve several-percentage-point coverage errors. This cannot establish exact 95% coverage, rare-event safety or arbitrary heavy-tail performance.',
    'status': 'Experimental validation-only candidate. The existing joint/component BCa failures remain retained; no automatic substitute or product fallback.'}


def sample(seed, scenario):
    """Known superpopulation truths; raw moments, never observed H extrema."""
    rng = np.random.Generator(np.random.PCG64(seed)); n = 200
    units = np.arange(n); member = units < 100; ceiling = None; truth = 0.
    heavy_mean = float(np.exp(1.5**2/2))
    if scenario == 'unequal_complete_clusters':
        sizes = np.minimum(50, rng.geometric(.2, n)); units = np.repeat(units, sizes)
        # Cluster size is independent of the mean-zero shared and event effects.
        value = np.repeat(rng.normal(size=n), sizes) + rng.normal(0, .2, len(units))
        member = units < 100
    elif scenario == 'paired_common_heavy':
        common = rng.lognormal(0, 1.5, n)
        reference = common + rng.normal(size=n); current = common + rng.normal(size=n)
        return np.column_stack((reference, np.ones(n), current, np.ones(n))), units, truth, ceiling
    elif scenario in {'heavy_member_light_comparator', 'light_member_heavy_comparator'}:
        heavy = rng.lognormal(0, 1.5, n) - heavy_mean; light = rng.normal(size=n)
        value = np.where(member, heavy, light) if scenario.startswith('heavy_member') else np.where(member, light, heavy)
    elif scenario.startswith('normal_'):
        value = rng.normal(size=n)
    elif scenario.startswith('exponential_'):
        value = rng.exponential(size=n); truth = 1. if scenario.endswith('_ceiling') else 0.
    elif scenario.startswith('lognormal_'):
        value = rng.lognormal(0, 1.5, n); truth = heavy_mean if scenario.endswith('_ceiling') else 0.
    else:
        raise ValueError('Undeclared scenario.')
    if scenario.endswith('_ceiling'):
        member = np.ones(len(units), bool); ceiling = 0.
    comparator = ~member
    values = np.column_stack((np.where(comparator, value, 0), comparator.astype(float),
                              np.where(member, value, 0), member.astype(float)))
    return values, units, truth, ceiling


def aggregate(values, units):
    """One row per complete independent unit; preserve event-weighted estimands."""
    _, inverse = np.unique(units, return_inverse=True)
    return np.column_stack([np.bincount(inverse, weights=values[:, c]) for c in range(4)])


def support(values, ceiling):
    result = []
    for column in ((3,) if ceiling is not None else (3, 1)):
        weights = values[:, column]; positive = weights[weights > 0]
        result.append({'independent_units': len(positive),
                       'effective_units': float(positive.sum()**2/(positive@positive)) if len(positive) else 0.})
    return result


def summary(rows, panel):
    result = []; diagnostics = []; complete = panel == 'qualification' and len(rows) == 1000*len(SCENARIOS)
    for scenario in SCENARIOS:
        selected = [r for r in rows if r['scenario'] == scenario]; n = len(selected)
        if not n: continue
        available = [r for r in selected if r['result']['status'] == 'available']; k = len(available)
        lower = sum(r['result']['lower'] > r['truth'] for r in available)
        upper = sum(r['result']['upper'] < r['truth'] for r in available)
        ci = lambda count, total, confidence=.95: [float(v) for v in binomtest(count, total).proportion_ci(confidence_level=confidence, method='exact')] if total else None
        availability = ci(k, n, 1-.05/len(SCENARIOS))
        result.append({'scenario': scenario, 'trials': n, 'available': k,
            'lower_above_truth': lower, 'upper_below_truth': upper, 'noncoverage': lower+upper,
            'noncoverage_MC95_conditional': ci(lower+upper, k),
            'availability_simultaneous_MC_interval': availability,
            'coverage_bounds_with_refusals': [(k-lower-upper)/n, (n-lower-upper)/n],
            'unconditional_wrong_positive_claim_rate': lower/n,
            'refusals': dict(Counter(r['result'].get('reason') for r in selected if r['result']['status'] != 'available')),
            'availability_criterion_met': bool(complete and availability[0] > .90)})
        for name, count, alpha in (('total', lower+upper, .05), ('lower_above_truth', lower, .025), ('upper_below_truth', upper, .025)):
            diagnostics.append({'scenario': scenario, 'diagnostic': name, 'count': count,
                'available_denominator': k, 'nominal_error': alpha,
                'p': float(binomtest(count, k, alpha, alternative='greater').pvalue) if k else None,
                'Holm_rejected': None})
    if complete:
        ordered = sorted([d for d in diagnostics if d['p'] is not None], key=lambda d: d['p']); stopped = False
        for i, d in enumerate(ordered):
            reject = not stopped and d['p'] <= .05/(len(ordered)-i)
            d['Holm_rejected'] = bool(reject); stopped |= not reject
    return {'rows': result, 'diagnostics': diagnostics, 'panel_complete': complete,
            'screening_criteria_met': bool(complete and all(r['availability_criterion_met'] for r in result) and not any(d['Holm_rejected'] for d in diagnostics)),
            'interpretation': 'Experimental candidate screening only. Conditional diagnostics can conceal refusal selection; refusal counts, unconditional errors and bounds remain visible. Does not activate a product method or establish finite-sample coverage.'}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--panel', choices=('development', 'qualification'), required=True)
    parser.add_argument('--out', required=True); args = parser.parse_args()
    directory = Path(args.out); directory.mkdir(parents=True, exist_ok=True)
    functions = (estimates, studentized, sample, aggregate, support, summary)
    profile = {'protocol': PROTOCOL, 'panel': args.panel,
        'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'function_sha256': {f.__name__: hashlib.sha256(inspect.getsource(f).encode()).hexdigest() for f in functions},
        'runtime': {name: importlib.metadata.version(name) for name in ('numpy', 'scipy', 'threadpoolctl')}}
    identity = hashlib.sha256(json.dumps(profile, sort_keys=True).encode()).hexdigest(); path = directory/'profile.json'
    if path.exists() and json.loads(path.read_text()) != profile: raise RuntimeError('Preserve prior source/protocol and choose another output directory.')
    if not path.exists(): path.write_text(json.dumps(profile, indent=2, sort_keys=True)+'\n')
    start, stop = PROTOCOL[args.panel+'_seed_range']; rows = []
    with threadpool_limits(limits=1):
        for scenario in SCENARIOS:
            for seed in range(start, stop+1):
                path = directory/f'{scenario}-{seed}.json'
                if path.exists():
                    row = json.loads(path.read_text())
                    if row['scenario'] != scenario or row['seed'] != seed or row['profile_digest'] != identity: raise RuntimeError('Existing trial identity differs.')
                else:
                    begun = time.monotonic(); values, units, truth, ceiling = sample(seed, scenario)
                    aggregated = aggregate(values, units); arms = support(aggregated, ceiling)
                    if any(a['independent_units'] < 30 or a['effective_units'] < 30 for a in arms):
                        measured = {'status': 'unavailable', 'reason': 'insufficient_conditional_independent_support'}
                    else:
                        measured = studentized(aggregated, replicates=20000, seed=seed+900000, ceiling=ceiling)
                    row = {'scenario': scenario, 'seed': seed, 'truth': truth, 'ceiling': ceiling,
                        'result': measured, 'support': arms, 'profile_digest': identity,
                        'input_sha256': hashlib.sha256(values.tobytes()+units.tobytes()).hexdigest(),
                        'unit_matrix_sha256': hashlib.sha256(aggregated.tobytes()).hexdigest(),
                        'seconds': time.monotonic()-begun, 'generated_at': datetime.now(timezone.utc).isoformat()}
                    pending = path.with_suffix('.pending'); pending.write_text(json.dumps(row, indent=2, sort_keys=True, allow_nan=False)+'\n'); pending.rename(path)
                    print(json.dumps({'scenario': scenario, 'seed': seed, 'status': measured['status'], 'seconds': row['seconds']}), flush=True)
                rows.append(row)
    final = {'profile': profile, **summary(rows, args.panel)}; path = directory/'summary.json'
    if path.exists() and json.loads(path.read_text()) != final: raise RuntimeError('Completed summary differs.')
    if not path.exists(): path.write_text(json.dumps(final, indent=2, sort_keys=True, allow_nan=False)+'\n')


if __name__ == '__main__':
    main()
