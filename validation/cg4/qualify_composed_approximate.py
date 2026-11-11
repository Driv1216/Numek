"""Candidate component-BCa contrast, separate from the failed joint profile.

This is qualification tooling, not an enabled product method. It composes two
separately allocated BCa mean/ratio intervals by interval subtraction. Its
coverage still depends on the component approximations; no theorem is inferred
from a small development panel. The prior joint-BCa failures remain unchanged.
"""
import argparse
from collections import Counter
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import inspect
import json
from pathlib import Path
import time

import numpy as np
from scipy.stats import binomtest
from threadpoolctl import threadpool_limits

from confidenceguard.confirmation import approximate_interval
from confidenceguard.inference import _replicates, preflight
from qualify_approximate import sample

SCENARIOS = ('normal_mean', 'skew_exponential', 'heavy_lognormal', 'imbalanced_arms', 'unequal_complete_clusters')


def composed(values, objective, spec, units):
    intervals = []; n = len(values)
    declaration = replace(objective, direction='higher', comparator='ceiling', ceiling=0.)
    allocated = replace(spec, batch_alpha=spec.batch_alpha/2)
    for numerator, denominator in ((2, 3), (0, 1)):
        matrix = np.column_stack((np.zeros(n), np.ones(n), values[:, numerator], values[:, denominator]))
        measured = approximate_interval(matrix, declaration, allocated, family_size=1, units=units,
            work_budget=2_000_000_000, check=lambda *args: None)
        intervals.append(measured)
    if any(i['status'] != 'available' for i in intervals):
        return {'status': 'unavailable', 'reason': 'component_interval_unavailable', 'components': intervals}
    a, b = intervals
    return {'status': 'available', 'lower': a['lower']-b['upper'], 'upper': a['upper']-b['lower'],
            'components': intervals, 'method': 'component_BCa_contrast_candidate_v1',
            'elementary_intervals': 2, 'strength': 'approximate'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--panel', choices=('development', 'qualification'), required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    directory = Path(args.out); directory.mkdir(parents=True, exist_ok=True)
    seeds = range(40) if args.panel == 'development' else range(60000, 61000)
    profile = {'schema_version': 'numek.cg4_component_BCa_candidate/1.0', 'panel': args.panel,
        'method': 'component_BCa_contrast_candidate_v1', 'scenarios': list(SCENARIOS), 'seed_range': [seeds.start, seeds.stop-1],
        'units': 200, 'B': 20000, 'family_size': 1, 'components': 2, 'confidence': .95,
        'functions_sha256': {f.__name__: hashlib.sha256(inspect.getsource(f).encode()).hexdigest()
            for f in (composed, approximate_interval, _replicates, preflight, sample)},
        'acceptance': 'For the complete qualification panel, predeclared one-sided exact binomial excess-noncoverage '
            'diagnostics at .05, Holm across all five scenarios. Retain MC intervals, all refusals and availability. '
            'A nonsignificant diagnostic is limited empirical evidence, not proof or arbitrary-distribution support.',
        'product_status': 'Not enabled. Independent method identity and numerical/multiplicity admission would be '
            'required before product integration. No outcome-triggered switch from joint BCa is permitted.'}
    path = directory/'profile.json'
    if path.exists() and json.loads(path.read_text()) != profile:
        raise RuntimeError('Preserve the old candidate profile; use a new output directory.')
    if not path.exists(): path.write_text(json.dumps(profile, sort_keys=True, indent=2)+'\n')
    rows = []
    with threadpool_limits(limits=2):
        for scenario in SCENARIOS:
            for seed in seeds:
                destination = directory/f'{scenario}-{seed}.json'
                if destination.exists(): row = json.loads(destination.read_text())
                else:
                    started = time.monotonic(); values, objective, spec, units, _ = sample(seed, scenario)
                    result = composed(values, objective, spec, units)
                    row = {'scenario': scenario, 'seed': seed, 'result': result, 'seconds': time.monotonic()-started,
                           'input_sha256': hashlib.sha256(values.tobytes()+units.tobytes()).hexdigest()}
                    with destination.open('x') as stream: json.dump(row, stream, sort_keys=True, indent=2); stream.write('\n')
                    print(json.dumps({k: row[k] for k in ('scenario', 'seed', 'seconds')}), flush=True)
                rows.append(row)
    summaries = []
    for scenario in SCENARIOS:
        selected = [r for r in rows if r['scenario'] == scenario]
        available = [r['result'] for r in selected if r['result']['status'] == 'available']
        failed = sum(not r['lower'] <= 0 <= r['upper'] for r in available)
        ci = binomtest(failed, len(available)).proportion_ci(method='exact') if available else None
        summaries.append({'scenario': scenario, 'trials': len(selected), 'available': len(available), 'noncoverage': failed,
            'false_confirmation': sum(r['lower'] > 0 for r in available),
            'refusals': dict(Counter(r['result'].get('reason') for r in selected if r['result']['status'] != 'available')),
            'noncoverage_MC95': [ci.low, ci.high] if ci else None,
            'excess_p': binomtest(failed, len(available), .05, alternative='greater').pvalue if available else 1.})
    adjusted = 0.
    for rank, row in enumerate(sorted(summaries, key=lambda r: r['excess_p'])):
        adjusted = max(adjusted, min(1., (len(summaries)-rank)*row['excess_p']))
        row['Holm_adjusted_p'] = adjusted
        row['qualification_diagnostic_rejects'] = args.panel == 'qualification' and adjusted < .05
    summary = {'profile': profile, 'rows': summaries, 'generated_at': datetime.now(timezone.utc).isoformat(),
               'development_is_qualification': False}
    with (directory/'summary.json').open('x') as stream: json.dump(summary, stream, sort_keys=True, indent=2); stream.write('\n')


if __name__ == '__main__':
    main()
