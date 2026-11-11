"""Fixed finite-entity qualification; no predictor or general job execution API."""
import argparse
from datetime import datetime, timezone
import hashlib
import inspect
import json
from pathlib import Path
import sys
import time

import numpy as np
import psutil
from scipy.special import betaincinv
from scipy.stats import binomtest
from threadpoolctl import threadpool_limits

from confidenceguard.confirmation import finite_interval, _entity_arm_refusal
from confidenceguard.investigation_contracts import FailureObjectiveSpec
import qualify_pipeline as pipeline

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = {
    'schema_version': 'numek.cg4_finite_entity_arm_qualification/1.0',
    'sampling': 'independent_entity_arms', 'alpha': .05, 'elementary_intervals': 2,
    'families': [1, 10, 32], 'rng': 'NumPy PCG64 default_rng([seed, scenario_index])',
    'development_seeds': [0, 39],
    'scenarios': {
        'paired_binary': {'index': 0, 'start': 410000, 'trials': 10000, 'entities': 512,
            'kind': 'binary', 'prevalence': .5, 'observed': [1., 1.], 'truth': 0., 'delta': 0.},
        'rare_observed_binary': {'index': 1, 'start': 420000, 'trials': 10000, 'entities': 512,
            'kind': 'binary', 'prevalence': .125, 'observed': [.6, .8], 'truth': 0., 'delta': 0.},
        'bounded_mean': {'index': 2, 'start': 430000, 'trials': 10000, 'entities': 512,
            'kind': 'bounded', 'prevalence': .5, 'observed': [.8, .9], 'truth': 0., 'delta': 0., 'bounds': [0., 1.]},
        'partial_null_power': {'index': 3, 'start': 460000, 'trials': 2000, 'entities': 10000,
            'kind': 'binary', 'prevalence': .125, 'observed': [1., 1.], 'delta': .15,
            'truth': 'current risk .40 in x<.125 and .10 elsewhere; reference risk .10', 'families': [32]},
    },
    'gates': '32 fixed intervals [j/64, j/64+prevalence) on independent Uniform(0,1) entity context.',
    'within_entity': 'One potential current and reference observation per entity. Binary errors use U<risk and U>.9; bounded values use U and 1-U. Dependence inside entities is intentional.',
    'observation': 'Separate predeclared label-observation indicators independent of context/outcomes. Observed-label estimands; no selection correction is inferred.',
    'allocation': 'Original full family m; each of two marginal intervals gets .05/(2*m). No family shrinking or claim of simultaneous control across separate studies.',
    'acceptance': 'One-sided exact binomial excess-error diagnostics at .05, Holm across every positive-panel family noncoverage and practical-null false-confirmation diagnostic. No diagnostic may reject. In the power panel, the one-sided 95% lower bound for gate-zero confirmation probability must be >=.80; all trials/refusals remain in the denominator. Numerical/native references must agree.',
    'negative_controls': '200 independent seeds each for an unmodelled global shock and naive duplicated-row inference, deliberately bypassing required assumptions/structural admission. Retain failures; do not treat them as product-admitted designs.',
    'scope': 'Mathematics supplies finite guarantees under the declared IID complete-entity design, not simulation non-rejection. This does not qualify general complete-entity bootstrap, unbounded means, temporal dependence, discovery recovery or external provenance.',
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def cp(count, success, alpha):
    valid = count > 0
    lo = np.full(count.shape, np.nan); hi = lo.copy()
    lo[valid] = 0.; hi[valid] = 1.
    interior = valid & (success > 0)
    lo[interior] = betaincinv(success[interior], count[interior]-success[interior]+1, alpha/2)
    interior = valid & (success < count)
    hi[interior] = betaincinv(success[interior]+1, count[interior]-success[interior], 1-alpha/2)
    return lo, hi


def intervals(counts, m, kind):
    a, x, b, y = (counts[:, :m, j] for j in range(4))
    allocated = .05/(2*m)
    if kind == 'binary':
        al, au = cp(a, x, allocated); bl, bu = cp(b, y, allocated)
    else:
        with np.errstate(divide='ignore', invalid='ignore'):
            am = x/a; bm = y/b
            ae = np.sqrt(np.log(2/allocated)/(2*a)); be = np.sqrt(np.log(2/allocated)/(2*b))
        al, au = np.maximum(0., am-ae), np.minimum(1., am+ae)
        bl, bu = np.maximum(0., bm-be), np.minimum(1., bm+be)
    return al-bu, au-bl


def diagnostic(errors, trials):
    interval = binomtest(errors, trials).proportion_ci(method='exact')
    return {'events': errors, 'trials': trials, 'rate': errors/trials,
        'MC95': [float(interval.low), float(interval.high)],
        'excess_p': float(binomtest(errors, trials, .05, alternative='greater').pvalue)}


def panel(name, spec, out):
    n, trials = spec['entities'], spec['trials']
    counts = np.empty((trials, 32, 4), dtype='<f8')
    input_hashes = []; references = 0; maximum_error = 0.; sampled_peak = 0
    objective = FailureObjectiveSpec('reference', 'error_rate' if spec['kind']=='binary' else 'mae', 'model',
        comparator='reference_period', reference_period='reference', current_period='current',
        direction='higher', practical_threshold=spec['delta'])
    started = time.monotonic()
    for start in range(0, trials, 16 if n>512 else 64):
        stop = min(start+(16 if n>512 else 64), trials)
        context = []; uniform = []; observation_a = []; observation_b = []
        for seed in range(spec['start']+start, spec['start']+stop):
            rng = np.random.default_rng([seed, spec['index']])
            z = rng.random(n); u = rng.random(n)
            oa = rng.random(n)<spec['observed'][0]; ob = rng.random(n)<spec['observed'][1]
            input_hashes.append(hashlib.sha256(z.tobytes()+u.tobytes()+oa.tobytes()+ob.tobytes()).hexdigest())
            context.append(z); uniform.append(u); observation_a.append(oa); observation_b.append(ob)
        z = np.array(context); u = np.array(uniform)
        oa = np.array(observation_a); ob = np.array(observation_b)
        offsets = np.arange(32)/64
        gate = (z[:, :, None]>=offsets)&(z[:, :, None]<offsets+spec['prevalence'])
        if spec['kind']=='binary':
            risk = np.where(z<.125, .4, .1) if name=='partial_null_power' else .1
            value_a = (u<risk).astype(float); value_b = (u>.9).astype(float)
        else:
            value_a = u; value_b = 1-u
        arm_a = gate&oa[:, :, None]; arm_b = gate&ob[:, :, None]
        counts[start:stop, :, 0] = arm_a.sum(axis=1)
        counts[start:stop, :, 1] = (arm_a*value_a[:, :, None]).sum(axis=1)
        counts[start:stop, :, 2] = arm_b.sum(axis=1)
        counts[start:stop, :, 3] = (arm_b*value_b[:, :, None]).sum(axis=1)
        if start==0:
            for m in spec.get('families', PROTOCOL['families']):
                lower, upper = intervals(counts[:stop], m, spec['kind'])
                for i in range(min(8, stop)):
                    for j in sorted({0, m-1}):
                        native = finite_interval(objective, value_a[i][arm_a[i, :, j]], value_b[i][arm_b[i, :, j]],
                            .05/m, binary=spec['kind']=='binary', bounds=() if spec['kind']=='binary' else (0., 1.))
                        if counts[i, j, 0] and counts[i, j, 2]:
                            assert native['status']=='available'
                            error = max(abs(native['lower']-lower[i, j]), abs(native['upper']-upper[i, j]))
                            assert error<=5e-11, error
                            maximum_error = max(maximum_error, error)
                        else:
                            assert native['status']=='unavailable'
                        references += 1
        sampled_peak = max(sampled_peak, psutil.Process().memory_info().rss)
        if stop==trials or start//1000 != stop//1000:
            print(json.dumps({'scenario': name, 'completed': stop, 'planned': trials}), flush=True)
    np.save(out/(name+'-counts.npy'), counts, allow_pickle=False)
    with (out/(name+'-inputs.json')).open('x') as stream:
        json.dump({'seeds': [spec['start'], spec['start']+trials-1], 'sha256': input_hashes}, stream)
    truth = .3*np.maximum(.125-np.arange(32)/64, 0)/.125 if name=='partial_null_power' else np.zeros(32)
    families = []
    for m in spec.get('families', PROTOCOL['families']):
        lower, upper = intervals(counts, m, spec['kind'])
        available = (counts[:, :m, 0]>0)&(counts[:, :m, 2]>0)
        assert np.isfinite(lower[available]).all() and np.isfinite(upper[available]).all()
        assert (lower[available]<=upper[available]).all()
        noncoverage = np.any(available&((lower>truth[:m])|(upper<truth[:m])), axis=1)
        false = np.any(available&(lower>spec['delta'])&(truth[:m]<=spec['delta']), axis=1)
        families.append({'m': m, 'family_noncoverage': diagnostic(int(noncoverage.sum()), trials),
            'false_confirmation_family': diagnostic(int(false.sum()), trials),
            'families_with_unavailable_claims': int((~available.all(axis=1)).sum())})
    power = None
    if name=='partial_null_power':
        successes = int((lower[:, 0]>spec['delta']).sum())
        lower_bound = float(betaincinv(successes, trials-successes+1, .05)) if successes else 0.
        power = {'successes': successes, 'trials': trials, 'lower_bound': float(lower_bound), 'required': .8,
            'bound_confidence': .95, 'bound_tail': 'lower_only',
            'criterion_met': bool(lower_bound>=.8), 'refusals_in_denominator': True,
            'truth': float(truth[0]), 'delta': spec['delta']}
    return {'scenario': name, 'families': families, 'power': power, 'native_reference_cases': references,
        'maximum_reference_difference': float(maximum_error), 'seconds': time.monotonic()-started,
        'sampled_peak_RSS_bytes': sampled_peak, 'resource_scope': 'Concurrent host; sampled RSS, not a controlled efficiency comparison.'}


def negative_controls(out):
    records = []
    for scenario in ('common_shock', 'duplicated_rows'):
        counts = np.empty((200, 32, 4))
        for i, seed in enumerate(range(450000, 450200)):
            rng = np.random.default_rng([seed, scenario=='duplicated_rows'])
            if scenario=='common_shock':
                counts[i, :, :] = [512, 512*int(rng.random()<.5), 512, 0]
            else:
                success = int((rng.random(64)<.5).sum())
                counts[i, :, :] = [512, 8*success, 512, 8*(64-success)]
        lower, upper = intervals(counts, 1, 'binary')
        truth = .5 if scenario=='common_shock' else 0.
        records.append({'scenario': scenario, 'trials': 200, 'truth': truth, 'delta': truth,
            'false_confirmation': diagnostic(int((lower[:, 0]>truth).sum()), 200),
            'noncoverage': diagnostic(int(((lower[:, 0]>truth)|(upper[:, 0]<truth)).sum()), 200),
            'scope': 'Intentionally bypasses required IID/structural admission; not a product-admitted finding or a qualifying population.'})
        np.save(out/(scenario+'-negative-counts.npy'), counts, allow_pickle=False)
    return records


def verify_source(manifest):
    if hashlib.sha256(json.dumps(manifest['files'], sort_keys=True).encode()).hexdigest()!=manifest['source_identity']:
        raise RuntimeError('Invalid source identity.')
    for relative, expected in manifest['files'].items():
        path = ROOT/relative
        if path.is_symlink() or not path.resolve().is_relative_to(ROOT) or sha(path)!=expected:
            raise RuntimeError('Source capsule changed.')


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--out', required=True); args = parser.parse_args()
    manifest = json.loads((ROOT/'source-manifest.json').read_text())
    if not Path(inspect.getfile(finite_interval)).resolve().is_relative_to(ROOT):
        raise RuntimeError('Use the immutable source capsule and its src PYTHONPATH.')
    verify_source(manifest)
    out = Path(args.out).resolve(); out.mkdir(parents=True, exist_ok=False)
    profile = {'protocol': PROTOCOL, 'source_identity': manifest['source_identity'], 'packages': pipeline.runtime_versions(),
        'functions_sha256': {f.__name__: hashlib.sha256(inspect.getsource(f).encode()).hexdigest()
            for f in (cp, intervals, panel, negative_controls, finite_interval, _entity_arm_refusal)},
        'harness_sha256': sha(__file__), 'python': sys.version}
    with (out/'profile.json').open('x') as stream: json.dump(profile, stream, indent=2, sort_keys=True)
    with threadpool_limits(limits=2):
        positive = [panel(name, spec, out) for name, spec in PROTOCOL['scenarios'].items()]
        negative = negative_controls(out)
    verify_source(manifest)
    diagnostics = []
    for case in positive:
        for family in case['families']:
            for kind in ('family_noncoverage', 'false_confirmation_family'):
                row = family[kind]; diagnostics.append((case['scenario'], family['m'], kind, row))
    adjusted = 0.
    for rank, (scenario, m, kind, row) in enumerate(sorted(diagnostics, key=lambda item: item[3]['excess_p'])):
        adjusted = max(adjusted, min(1., (len(diagnostics)-rank)*row['excess_p']))
        row['Holm_adjusted_p'] = adjusted; row['diagnostic_rejects'] = bool(adjusted<.05)
    passed = not any(row['diagnostic_rejects'] for *_, row in diagnostics) and all(
        case['power'] is None or case['power']['criterion_met'] for case in positive)
    result = {'profile': profile, 'positive': positive, 'negative': negative,
        'qualification_diagnostics_pass': passed, 'scope': PROTOCOL['scope'],
        'generated_at': datetime.now(timezone.utc).isoformat()}
    with (out/'summary.json').open('x') as stream: json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
    print(json.dumps({'qualification_diagnostics_pass': passed, 'native_reference_cases': sum(c['native_reference_cases'] for c in positive),
        'scope': PROTOCOL['scope']}), flush=True)
    if not passed: raise SystemExit('Retain the failed panel and investigate; do not weaken criteria.')


if __name__=='__main__':
    main()
