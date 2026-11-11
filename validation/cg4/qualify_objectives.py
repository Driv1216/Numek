"""Locked objective-specific recovery, separate from generic error discovery.

These engineered supplied predictions define a joint synthetic population, not a
product predictor-execution API. Development seeds cannot count as qualification.
"""
import argparse
import csv
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import traceback

import numpy as np
from scipy.special import expit

import qualify_pipeline as pipeline
import parallel_qualification as parallel

PANELS = {
    'false_negative': {'metric': 'false_negative_rate', 'delta': .15, 'contrast': '.40 versus .10 among actual positives'},
    'false_positive': {'metric': 'false_positive_rate', 'delta': .15, 'contrast': '.40 versus .10 among actual negatives'},
    'precision': {'metric': 'precision', 'direction': 'lower', 'delta': .15, 'contrast': '.60 versus .90 among predicted positives'},
    'probability_quality': {'metric': 'brier', 'delta': .12, 'contrast': 'Brier .33 versus .09; high-confidence error mechanism'},
    'calibration_residual': {'metric': 'calibration_residual', 'delta': .15, 'contrast': 'Signed target residual +.30 versus zero at supplied p=.5'},
    'calibration_bins': {'metric': 'reliability_diagram', 'delta': .15, 'contrast': 'Frozen equal-width bin residual magnitude .30 versus zero'},
    'regression_bias': {'metric': 'bias', 'delta': .45, 'units': 'metres', 'bounds': [-1., 2.], 'contrast': 'Signed mean bias .90 versus zero with bounded independent noise'},
    'regression_tail': {'metric': 'material_error_rate', 'delta': .25, 'units': 'fraction', 'contrast': 'Absolute error >1 metre: .60 versus .01'},
    'ranking_auc': {'metric': 'roc_auc', 'direction': 'lower', 'delta': .35, 'contrast': 'Reversed versus correctly ordered noisy score distributions'},
    'ranking_ap': {'metric': 'average_precision', 'direction': 'lower', 'delta': .20, 'contrast': 'Reversed versus correctly ordered noisy scores at balanced label prevalence'},
    'uncertainty_coverage': {'metric': 'interval_miscoverage', 'delta': .25, 'contrast': 'Prediction-interval miscoverage .60 versus .10'},
    'uncertainty_efficiency': {'metric': 'interval_width', 'delta': 1., 'units': 'metres', 'bounds': [1., 5.], 'contrast': 'Issued interval widths 4 versus 2 metres, with unchanged perfect coverage'},
    'paired_degradation': {'metric': 'error_rate', 'delta': .15, 'contrast': 'Common-population candidate minus reference error .30 versus zero'},
    'paired_precision': {'metric': 'precision', 'direction': 'lower', 'delta': .15,
        'contrast': 'Common issued base; reference precision .90, candidate .60 in the region and .90 outside; distinct positive denominators'},
    'regression_r2': {'metric': 'r2', 'direction': 'lower', 'delta': .75, 'units': 'dimensionless',
        'contrast': 'Equal independent Uniform(-5,5) target distributions; regional residual variance 16 versus background 1/12. Population R2 contrast 1.91.',
        'scope': 'Negative-squared-residual proposal under equal target variance. Does not qualify arbitrary subgroup target variance or native R2 confidence intervals.'},
}
PROTOCOL = {'schema_version': 'numek.cg4_objective_recovery_protocol/1.2', 'panels': PANELS,
    'selection_policy':'severity_material_excess_support_frontier_v2',
    'qualification_seed_range': [310000, 310039], 'development_seed_range': [0, 39], 'units': 40000,
    'panel_specific_seed_ranges': {'paired_precision': [380000, 380039], 'regression_r2': [480000, 480039]},
    'region': 'categorical a=1 AND continuous x>.5; expected prevalence .125',
    'primary': 'Positive-native-effect S-selected union evaluated on independent H; unavailable counts stay in planned recall.',
    'criterion': {'H_precision': .7, 'H_recall': .7, 'minimum_successes_of_40': 32},
    'assessments': 'Authoritative frozen-region H effects measured separately from recovery; intervals remain finite or explicitly approximate and subject to qualification/refusal.',
    'strategy_claims': 'Unified runs do not qualify every strategy. Separate --strategies ablations retain the same profile and separate evidence.',
    'not_covered': ['Historical-deterioration workspace panel', 'Natural-data recovery', 'Every registered metric from one representative objective']}


def generate(directory, seed, n, panel):
    from confidenceguard import InvestigationSpec
    spec, region, _ = pipeline.generate(directory, seed, n, 'categorical_numeric_conjunction')
    path = directory/'predictions.csv'
    with path.open() as stream: rows = list(csv.DictReader(stream))
    rng = np.random.default_rng(seed+900000); target = rng.integers(0, 2, n); error = rng.random(n) < np.where(region, .4, .1)
    decision = target ^ error; probability = np.where(decision, .9, .1); point = decision.astype(float)
    definition = PANELS[panel]; regression = panel.startswith('regression_') or panel == 'uncertainty_efficiency'
    if panel in {'false_negative', 'false_positive'}:
        conditional = target == (1 if panel == 'false_negative' else 0)
        error = rng.random(n) < np.where(region & conditional, .4, .1); decision = target ^ error
        probability = np.where(decision, .9, .1)
    elif panel == 'precision':
        decision = rng.integers(0, 2, n); error = rng.random(n) < np.where(region & (decision == 1), .4, .1)
        target = decision ^ error; probability = np.where(decision, .9, .1)
    elif panel == 'paired_precision':
        # Shared uniforms couple the predictors without intersecting their
        # positive sets. With balanced Y, .9 TPR/.1 FPR gives precision .9;
        # raising regional FPR to .6 gives .9/(.9+.6)=.6. Outside is identical.
        shared=rng.random(n)
        reference=(shared<np.where(target==1,.9,.1)).astype(int)
        decision=(shared<np.where(target==1,.9,np.where(region,.6,.1))).astype(int)
        probability=np.where(decision,.9,.1)
    elif panel.startswith('calibration_'):
        probability = np.full(n, .5); target = (rng.random(n) < np.where(region, .8, .5)).astype(int); decision = np.ones(n, int)
    elif panel.startswith('ranking_'):
        raw = (2*target-1)*np.where(region, -1., 1.) + rng.normal(0, .7, n)
        probability = expit(raw); decision = (probability >= .5).astype(int)
    if regression or panel == 'uncertainty_coverage':
        target = rng.uniform(-5, 5, n); noise = rng.uniform(-.5, .5, n)
        if panel == 'regression_bias': point = target + noise + .9*region
        elif panel == 'regression_r2': point = target + np.where(region, rng.normal(0., 4., n), noise)
        elif panel == 'regression_tail':
            bad = rng.random(n) < np.where(region, .6, .01); point = target+noise+2*bad
        elif panel == 'uncertainty_coverage':
            bad = rng.random(n) < np.where(region, .6, .1); point = target+noise+2*bad
        else: point = target+noise
    if panel!='paired_precision':reference = target ^ (rng.random(n) < .1) if panel == 'paired_degradation' else np.zeros(n)
    for i, row in enumerate(rows):
        row.update(outcome=str(float(target[i])) if regression or panel == 'uncertainty_coverage' else str(int(target[i])),
                   prediction=str(float(point[i])) if regression or panel == 'uncertainty_coverage' else str(int(decision[i])),
                   probability=repr(float(probability[i])), reference=str(int(reference[i])),
                   lower=repr(float(point[i]-(2 if panel == 'uncertainty_efficiency' and region[i] else 1))),
                   upper=repr(float(point[i]+(2 if panel == 'uncertainty_efficiency' and region[i] else 1))))
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0]); writer.writeheader(); writer.writerows(rows)
    packet = spec.to_dict(); objective = {'id': 'failure', 'run': 'candidate', 'metric': definition['metric'],
        'practical_threshold': definition['delta'], 'direction': definition.get('direction', 'higher'), 'units': definition.get('units', 'fraction')}
    if definition.get('bounds'): objective['bounds'] = definition['bounds']
    if panel.startswith('calibration_'): objective['target'] = '1'
    if regression or panel == 'uncertainty_coverage':
        packet['evaluation']['task'] = {'kind': 'regression', 'outcome_definition': 'Synthetic bounded continuous target', 'units': 'metres', 'material_error': 1.}
        packet['evaluation']['runs'][0].pop('probabilities', None)
        if panel.startswith('uncertainty_'):
            packet['evaluation']['runs'][0]['intervals'] = [{'id': 'issued_interval', 'lower': 'lower', 'upper': 'upper', 'meaning': 'prediction', 'coverage': .9}]
            objective['interval'] = 'issued_interval'
    if panel in {'paired_degradation','paired_precision'}:
        reference_run = {**packet['evaluation']['runs'][0], 'id': 'reference', 'prediction': 'reference', 'model': {'id': 'synthetic-reference', 'version': 'v1'}}
        reference_run.pop('probabilities', None); packet['evaluation']['runs'].append(reference_run)
        objective.update(comparator='paired', reference_run='reference')
    packet.update(objectives=[objective], name='Synthetic '+panel)
    packet['roles']['namespace'] = f'cg4-objective-{panel}-{seed}-{n}'
    return InvestigationSpec.from_dict(packet), region


def trial(panel, seed, development, strategies, full_profile=False):
    from confidenceguard import investigate, freeze_hypotheses, confirm_investigation, ConfirmationSpec
    from confidenceguard.investigation import arguments, prepared
    from confidenceguard.investigation_membership import apply
    from confidenceguard.investigation_objectives import bind
    with tempfile.TemporaryDirectory(prefix='numek-cg4-objective-', dir='/private/tmp') as temporary:
        root = Path(temporary); spec, oracle = generate(root, seed, 6000 if development and not full_profile else 40000, panel)
        if strategies: spec = replace(spec, strategies=tuple(strategies.split(',')))
        if development and not full_profile: spec = replace(spec, limits=replace(spec.limits, max_nodes=10000, candidates_per_strategy=32, stability_replicates=1))
        result = investigate(spec); selected = result.data['investigation']['shortlist']; assessments = []
        if selected:
            method = 'percentile' if panel.startswith('ranking_') else 'finite'
            protocol = ConfirmationSpec(method=method, upstream_independence='declared_independent', external_exposure='declared_unexposed',
                declaration_author='NUMEK independent synthetic generator', declaration_reason='IID joint observations, isolated process, no predictor fitting or earlier H access.')
            family = freeze_hypotheses(result, confirmation=protocol); assessed = confirm_investigation(family)
            assessments = assessed.data['investigation']['assessments']
        s, c, roots = arguments(spec, None, None); evidence = {}
        with prepared(s, c, roots) as p:
            objective = bind(spec.objectives[0], p.store)
            for role in ('D', 'S', 'H'):
                indices, features, reps = p.role_data(role); union = np.zeros(len(indices), bool); available = np.ones(len(indices), bool); effects = []
                cache = {'_models': result.private['models'], '_directory': str(p.work.root), '_population_size': len(indices), '_max_distance_ops': spec.limits.max_distance_operations}
                for candidate in result.data['investigation']['candidates']:
                    if candidate['id'] not in selected: continue
                    artifact = result.private['artifacts'][candidate['membership_artifact']]
                    mask = apply(artifact, features, reps, cache=cache, check=p.work.check)
                    union |= mask['member']; available &= mask['available']
                    measured = p.evaluate(objective, role, indices, mask, artifact)
                    effects.append({'candidate_id': candidate['id'], 'strategy': candidate['strategy'], 'native_evidence': measured,
                        'frozen_explanation_fidelity':pipeline.diagnostics.explanation_fidelity(candidate,artifact,mask,features,reps,cache,p.work.check)})
                truth = oracle[np.array([int(json.loads(p.keys[i])[0]) for i in indices])]
                oracle_mask = {'member': truth, 'available': np.ones(len(indices), bool), 'reason': ['']*len(indices)}
                oracle_effect = p.evaluate(objective, role, indices, oracle_mask, {'artifact_digest': 'benchmark_oracle_diagnostic_only'})
                evidence[role] = {'primary_selected_union': pipeline.recovery(truth, union, available | union),
                                  'selected_native_effects': effects, 'oracle_native_effect': oracle_effect}
        h = evidence['H']['primary_selected_union']
        return {'seed': seed, 'objective_panel': panel, 'input_sha256': pipeline.sha(root/'predictions.csv'), 'oracle_prevalence': float(oracle.mean()),
                'objective': spec.objectives[0].to_dict(), 'limits': spec.limits.to_dict(), 'strategies': list(spec.strategies),
                'recovery': evidence, 'assessments': assessments, 'execution': result.execution, 'strategy_execution': result.data['investigation']['strategies'],
                'investigation_diagnostics':pipeline.diagnostics.snapshot(result),
                'anchor_success': h['precision'] >= .7 and h['recall'] >= .7, 'status': 'completed'}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('objective', choices=PANELS)
    parser.add_argument('--panel', choices=('development', 'qualification'), required=True); parser.add_argument('--out', required=True)
    parser.add_argument('--offset', type=int, default=0); parser.add_argument('--count', type=int, default=40); parser.add_argument('--strategies')
    parser.add_argument('--full-profile', action='store_true')
    parser.add_argument('--worker', action='store_true'); parser.add_argument('--seed', type=int)
    parser.add_argument('--workers',type=int,choices=range(1,5),default=1)
    args = parser.parse_args()
    profile = {'protocol': PROTOCOL, 'harness_sha256': pipeline.sha(Path(__file__)), 'source_sha256': pipeline.identity(),
               'base_harness_sha256': pipeline.sha(Path(pipeline.__file__)),'parallel_seed_runner_sha256':pipeline.sha(parallel.__file__),'diagnostics_harness_sha256':pipeline.sha(pipeline.diagnostics.__file__),
               'packages': pipeline.runtime_versions(), 'panel': args.panel, 'strategies': args.strategies, 'full_profile': args.full_profile}
    if args.worker:
        started = time.monotonic()
        try: record = trial(args.objective, args.seed, args.panel == 'development', args.strategies, args.full_profile)
        except Exception as exc: record = {'status': 'execution_failure', 'seed': args.seed, 'error_code': getattr(exc, 'code', None), 'traceback': traceback.format_exc()}
        if pipeline.identity() != profile['source_sha256'] or pipeline.sha(Path(__file__)) != profile['harness_sha256'] or pipeline.sha(pipeline.diagnostics.__file__)!=profile['diagnostics_harness_sha256'] or pipeline.sha(parallel.__file__)!=profile['parallel_seed_runner_sha256']:
            record.update(status_before_invalidation=record['status'], status='invalidated_source_change')
        record.update(profile=profile, seconds=time.monotonic()-started, generated_at=datetime.now(timezone.utc).isoformat())
        with Path(args.out).open('x') as stream:stream.write(json.dumps(record, sort_keys=True, indent=2, allow_nan=False)+'\n')
        return
    if args.offset < 0 or args.count < 1 or args.offset+args.count > 40: parser.error('Outside the locked 40-seed panel.')
    output = Path(args.out); output.mkdir(parents=True, exist_ok=True)
    seed_range=PROTOCOL.get('panel_specific_seed_ranges',{}).get(args.objective,PROTOCOL['qualification_seed_range'])
    start = 0 if args.panel == 'development' else seed_range[0]
    import zipfile
    archive = output/('objective-source-'+hashlib.sha256(json.dumps(profile, sort_keys=True).encode()).hexdigest()+'.zip')
    if not archive.exists():
        with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as z:
            for name, expected in profile['source_sha256'].items():
                raw = (pipeline.ROOT/name).read_bytes()
                if hashlib.sha256(raw).hexdigest() != expected: raise RuntimeError('Source changed during snapshot.')
                z.writestr(name, raw)
            z.writestr('qualify_objectives.py', Path(__file__).read_bytes())
            z.writestr('qualify_pipeline.py', Path(pipeline.__file__).read_bytes())
            raw=Path(pipeline.diagnostics.__file__).read_bytes()
            if hashlib.sha256(raw).hexdigest()!=profile['diagnostics_harness_sha256']:raise RuntimeError('Diagnostics source changed during capture.')
            z.writestr('qualification_diagnostics.py',raw)
            z.writestr('parallel_qualification.py',Path(parallel.__file__).read_bytes())
            z.writestr('objective-profile.json', json.dumps(profile, sort_keys=True, indent=2))
    def run_seed(seed):
        if pipeline.identity() != profile['source_sha256']: raise RuntimeError('Campaign runtime changed; preserve prior evidence.')
        path = output/f'{args.objective}-{seed}.json'
        if path.exists():
            previous=json.loads(path.read_text())
            if previous.get('profile')!=profile or previous.get('status')!='completed' or previous.get('seed')!=seed or previous.get('objective_panel')!=args.objective:
                raise RuntimeError('Failed or mismatched saved trial; preserve it and resolve before resuming.')
            return
        pending=path.with_suffix('.pending')
        if pending.exists():raise RuntimeError('Preserve incomplete pending evidence before resuming.')
        command = [sys.executable, '-B', str(Path(__file__).resolve()), args.objective, '--panel', args.panel, '--worker', '--seed', str(seed), '--out', str(pending)]
        if args.strategies: command += ['--strategies', args.strategies]
        if args.full_profile: command += ['--full-profile']
        subprocess.run(command, check=True); pending.rename(path); row = json.loads(path.read_text())
        parallel.emit({'objective': args.objective, 'seed': seed, 'status': row['status'], 'anchor_success': row.get('anchor_success'), 'seconds': row['seconds']})
        if row['status'] != 'completed' or row.get('profile')!=profile: raise RuntimeError('Execution failure preserved; diagnose before continuing.')
    parallel.run_fixed_seeds(range(start+args.offset,start+args.offset+args.count),args.workers,run_seed)


if __name__ == '__main__':
    main()
