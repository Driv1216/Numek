"""Development counterexample, not a recovery or confirmation campaign."""
import csv
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT/'validation/cg4'))
import qualify_objectives as benchmarks
import qualify_pipeline as pipeline
from confidenceguard.investigation import arguments, prepared
from confidenceguard.investigation_objectives import bind


def main():
    out = ROOT/'validation/cg4/results/r2-variance-counterexample-v105'
    out.mkdir(exist_ok=False)
    spec, _ = benchmarks.generate(out, 8, 2000, 'regression_r2')
    path = out/'predictions.csv'
    with path.open() as stream:
        rows = list(csv.DictReader(stream))
    for i, row in enumerate(rows):
        hot = row['a'] == '1'
        y = (-1 if i % 2 else 1) * (.1 if hot else 10.)
        row.update(outcome=str(y), prediction=str(y+(1. if hot else 2.)))
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0]); writer.writeheader(); writer.writerows(rows)
    s, c, roots = arguments(spec, None, None)
    with prepared(s, c, roots) as evidence:
        objective = bind(spec.objectives[0], evidence.store)
        keys, eligible, proxy = objective.training('D')
        records = [evidence.run_records['candidate'][key] for key in keys]
        hot = np.array([rows[int(json.loads(key)[0])]['a'] == '1' for key in keys])
        arms = []
        for label, mask in [('small_variance_region', hot & eligible), ('background', ~hot & eligible)]:
            y = np.array([r['y_num'] for r in records])[mask]
            residual = np.array([r['point']-r['y_num'] for r in records])[mask]
            arms.append({'arm': label, 'D_support': int(mask.sum()), 'target_variance': float(np.var(y)),
                'squared_error_mean': float(np.mean(residual**2)), 'proposal_adverse_mean': float(-proxy[mask].mean()),
                'independent_R2': float(1-np.mean(residual**2)/np.var(y))})
        indices, _, _ = evidence.role_data('D')
        members = np.array([rows[int(json.loads(evidence.keys[i])[0])]['a'] == '1' for i in indices])
        native = evidence.evaluate(objective, 'D', indices,
            {'member': members, 'available': np.ones(len(indices), bool), 'reason': ['']*len(indices)},
            {'artifact_digest': 'benchmark_counterexample_only'})
    assert np.isclose(native['member_metric']['value'], arms[0]['independent_R2'])
    assert np.isclose(native['comparator_metric']['value'], arms[1]['independent_R2'])
    assert arms[0]['independent_R2'] < -90 and arms[1]['independent_R2'] > .95
    assert arms[0]['proposal_adverse_mean'] < arms[1]['proposal_adverse_mean']
    result = {'schema_version': 'numek.cg4_r2_proxy_counterexample/1.0', 'seed': 8, 'units': 2000,
        'source_sha256': pipeline.identity(), 'generator_sha256': pipeline.sha(benchmarks.__file__),
        'script_sha256': pipeline.sha(__file__), 'inputs': {p.name: pipeline.sha(p) for p in (out/'predictions.csv', out/'vectors.npy')},
        'objective': spec.objectives[0].to_dict(), 'arms': arms, 'authoritative_D_evidence': native,
        'interpretation': 'Native R2 is correct. Squared residual alone orders these groups opposite to native adverse R2 because target variances differ.',
        'scope': 'A deterministic D-only diagnostic counterexample. No discovery learner was fitted here; this is not a measured algorithm recovery failure or a newly independent confirmation. It does not prove that every proposal strategy must miss this region. The equal-variance R2 recovery anchor remains unrun.'}
    (out/'summary.json').write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False)+'\n')
    print(json.dumps({'arms': arms, 'native_adverse_R2_effect': native['effect'], 'scope': result['scope']}))


if __name__ == '__main__':
    main()
