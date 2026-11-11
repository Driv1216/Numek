"""Summarize locked panels without turning missing/failed trials into successes."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.stats import binomtest

ROOT = Path(__file__).with_name('results')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def monte_carlo(k, n):
    interval = binomtest(k, n).proportion_ci(method='exact')
    return [float(interval.low), float(interval.high)]


def approximate():
    from qualify_approximate import SCENARIOS
    rows = []
    for scenario in SCENARIOS:
        directory = ROOT / f'approx-{scenario.replace("normal_mean", "normal")}-v1'
        path = directory / 'summary.json'
        summary = json.loads(path.read_text())
        seeds = {int(p.stem) for p in directory.glob('*.json') if p.stem.isdigit()}
        if seeds != set(range(50000, 51000)) or not summary['panel_complete']:
            raise RuntimeError(f'{scenario}: do not assess an incomplete diagnostic panel.')
        rows.append({'scenario': scenario, 'summary_sha256': sha(path),
                     'summary': str(path.relative_to(ROOT.parent)), **{k: summary[k] for k in (
                         'completed_trials', 'available', 'noncoverage', 'false_confirmation',
                         'refusals', 'coverage_bounds_with_refusals', 'conditional_noncoverage_MC95',
                         'excess_noncoverage_diagnostic_p')}})
    order = sorted(range(len(rows)), key=lambda i: rows[i]['excess_noncoverage_diagnostic_p'])
    adjusted = 0.
    for rank, index in enumerate(order):
        row = rows[index]
        adjusted = max(adjusted, min(1., (len(rows)-rank)*row['excess_noncoverage_diagnostic_p']))
        row.update(Holm_adjusted_p=adjusted, excess_noncoverage_rejected=adjusted < .05,
                   false_confirmation_MC95=monte_carlo(row['false_confirmation'], row['available']))
    reference = ROOT / 'BCa-SciPy-reference-v1.json'
    parity = json.loads(reference.read_text())
    if not parity['all_available_cases_match']:
        raise RuntimeError('Resolve the independent numerical-reference disagreement before method attribution.')
    return {'schema_version': 'numek.cg4_approximate_panel_summary/1.0',
            'diagnostic_family': 'Seven predeclared two-sided noncoverage diagnostics; Holm at .05.',
            'rows': rows, 'independent_reference': {'path': reference.name, 'sha256': sha(reference),
                'available_cases': len(parity['rows']), 'all_match': True},
            'method_qualification_failures': [r['scenario'] for r in rows if r['excess_noncoverage_rejected']],
            'interpretation': 'The small-support heavy-lognormal and unequal-cluster profiles failed qualification. '
                'Matching SciPy checks numerical composition, not statistical coverage. Non-rejection in other '
                'panels is limited empirical evidence, not universal validity. Refusals are not covered intervals. '
                'These results do not qualify arbitrary distributions, smaller support, multiplicity-adjusted '
                'extreme tails, or adaptively selected hypotheses. Required operating-envelope resolution remains open.'}


def curved():
    rows = []
    for seed in range(1000, 1040):
        directory = ROOT / ('recovery-curved-v1' if seed < 1003 else 'recovery-curved-v2')
        path = directory / f'recovery_qualification-curved_region-{seed}.json'
        row = json.loads(path.read_text())
        if row['status'] != 'completed' or row['seed'] != seed:
            raise RuntimeError('Every locked trial must be completed under its recorded profile.')
        measured = row['recovery']['H']['primary_selected_union']
        rows.append({'seed': seed, 'path': str(path.relative_to(ROOT.parent)), 'sha256': sha(path),
                     'source_sha256': row['profile']['source_sha256'],
                     'recovery': {role: row['recovery'][role]['primary_selected_union'] for role in ('D', 'S', 'H')},
                     'success': measured['precision'] >= .7 and measured['recall'] >= .7})
    successes = sum(r['success'] for r in rows)
    reuse = ROOT / 'reuse-provenance-v1' / 'reuse.json'
    return {'schema_version': 'numek.cg4_recovery_anchor_summary/1.0', 'archetype': 'curved_region',
            'expected_seeds': [1000, 1039], 'trials': rows, 'successes': successes,
            'success_fraction_MC95': monte_carlo(successes, len(rows)), 'required_successes': 32,
            'anchor_criterion_met': successes >= 32, 'median_H_precision': float(np.median([
                r['recovery']['H']['precision'] for r in rows])), 'median_H_recall': float(np.median([
                r['recovery']['H']['recall'] for r in rows])),
            'reuse_audit': {'path': str(reuse.relative_to(ROOT.parent)), 'sha256': sha(reuse)},
            'scope': 'This strong-signal curved-region anchor only; not landmark superiority, all geometric '
                'families, all objectives, generalization to arbitrary geometry, or a resource capacity claim. '
                'Interrupted/source-invalidated trials are retained separately and are not counted.'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('panel', choices=('approximate', 'curved'))
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    result = approximate() if args.panel == 'approximate' else curved()
    result.update(generated_at=datetime.now(timezone.utc).isoformat(), harness_sha256=sha(Path(__file__)))
    with Path(args.out).open('x') as stream:
        json.dump(result, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({k: v for k, v in result.items() if k not in {'trials', 'rows'}}))


if __name__ == '__main__':
    main()
