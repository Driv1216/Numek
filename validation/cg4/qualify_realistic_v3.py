"""Realistic-data journeys; predictor preparation is benchmark-only.

Training T is disjoint from D/S/H. Public data have incomplete entity/exposure
provenance, so these journeys cannot establish formally independent claims.
Keep data, images, texts, derived vectors and private results out of review ZIPs.
"""
import argparse
from collections import Counter
from dataclasses import replace
from datetime import datetime, timezone
import csv
import hashlib
import io
import importlib.metadata
import inspect
import json
import os
from pathlib import Path
import shutil
import tarfile
import tempfile
import time
import zipfile

import numpy as np
from threadpoolctl import threadpool_limits

from qualify_pipeline import identity, runtime_versions, recovery

ROOT = Path(__file__).resolve().parents[2]
CACHE = Path(__file__).with_name('datasets.nosync')
PROFILE = {'seed': 20261024, 'bank_train': 6000, 'bank_evaluate': 4000,
           'wine_train': 3500, 'wine_evaluate': 2997,
           'ag_news_train': 2000, 'ag_news_evaluate': 2000,
           'cifar10_train': 600, 'cifar10_evaluate': 1200,
           'max_nodes': 100000, 'candidates_per_strategy': 64, 'stability_replicates': 3,
           'injected_classification_rates': [.1, .4], 'injected_regression_bias': 2.,
           'purpose': 'Predeclared realistic workflow/availability/effect measurements, not strong-signal anchor qualification.'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def acquire(dataset):
    directory = CACHE / dataset
    manifest = json.loads((directory / 'acquisition.json').read_text())
    for entry in manifest['files']:
        if sha(directory / entry['filename']) != entry['sha256']:
            raise RuntimeError('Dataset bytes differ from their immutable acquisition manifest.')
    return directory, manifest


def load_tabular(dataset):
    directory, manifest = acquire(dataset)
    archive = zipfile.ZipFile(directory / manifest['files'][0]['filename'])
    if dataset == 'bank':
        nested = zipfile.ZipFile(io.BytesIO(archive.read('bank.zip')))
        rows = list(csv.DictReader(io.StringIO(nested.read('bank-full.csv').decode()), delimiter=';'))
        # Call duration is acquired after contact; it is deliberately excluded
        # from this hypothetical available-at-decision benchmark view.
        names = [name for name in rows[0] if name not in {'y', 'duration'}]
        categorical = {'job', 'marital', 'education', 'default', 'housing', 'loan', 'contact', 'month', 'poutcome'}
        y = np.array([int(row['y'] == 'yes') for row in rows]); task = 'binary_classification'
    else:
        rows = []
        for name, kind in (('winequality-red.csv', 'red'), ('winequality-white.csv', 'white')):
            part = list(csv.DictReader(io.StringIO(archive.read(name).decode()), delimiter=';'))
            for row in part: row['wine_kind'] = kind
            rows.extend(part)
        names = [name for name in rows[0] if name != 'quality']
        categorical = {'wine_kind'}; y = np.array([float(row['quality']) for row in rows]); task = 'regression'
    return rows, names, categorical, y, task, manifest


def load_content(dataset, directory):
    source, manifest = acquire(dataset)
    count = PROFILE[dataset + '_train'] + PROFILE[dataset + '_evaluate']
    if dataset == 'ag_news':
        import pyarrow.parquet as pq
        # Fixed publisher training split; local T/D/S/H allocations are distinct.
        path = source / 'train-00000-of-00001.parquet'
        table = pq.read_table(path, columns=['text', 'label']).slice(0, count)
        return table['text'].to_pylist(), np.array(table['label'].to_pylist()), manifest
    from PIL import Image
    with tarfile.open(source / 'cifar-10-binary.tar.gz', 'r:gz') as archive:
        member = archive.getmember('cifar-10-batches-bin/data_batch_1.bin')
        if not member.isfile() or member.size != 10000 * 3073:
            raise RuntimeError('Unexpected CIFAR binary member; no extraction is permitted.')
        with archive.extractfile(member) as stream:
            raw = stream.read(count * 3073)
    pixels = np.frombuffer(raw, dtype='uint8').reshape(count, 3073)
    images = pixels[:, 1:].reshape(count, 3, 32, 32).transpose(0, 2, 3, 1)
    paths = []
    for i, image in enumerate(images):
        path = directory / f'image-{i}.png'; Image.fromarray(image).save(path); paths.append(str(path))
    return paths, pixels[:, 0].astype(int), manifest


def encode_worker(dataset, contents, directory, *, progress=None):
    from confidenceguard import compat, EvaluationConfig, InvestigationLimits, DiscoveryRepresentationSpec, FeatureField
    from confidenceguard.features import normalize
    from confidenceguard.representations import encode
    from confidenceguard.result import Inspection
    image = dataset == 'cifar10'; config = EvaluationConfig(); work = compat.workspace(config, 1024**3, progress)
    try:
        field = FeatureField('content', 'content', 'asset' if image else 'text')
        cells = {'context.content': [normalize(text, field) for text in contents]}
        model = ROOT / ('validation/m7/models/dinov2-base' if image else 'validation/m6/models/multilingual-e5-small')
        declaration = DiscoveryRepresentationSpec('frozen_publisher', kind='dinov2_image' if image else 'e5_text',
            field='context.content', model_directory=str(model), max_windows_per_event=4)
        rep, _ = encode(declaration, [str(i) for i in range(len(contents))], cells, work, config, InvestigationLimits(),
                        (str(ROOT), directory), directory)
        # Return a bounded NPY reference, not millions of JSON float literals.
        # This file is inside the parent's isolated benchmark staging directory.
        destination = Path(directory)/'encoder-vectors.npy'
        with destination.open('xb') as stream: np.save(stream, rep['vectors'], allow_pickle=False)
        return Inspection({'matrix_path': str(destination), 'matrix_file_sha256': sha(destination),
            'available': rep['available'].tolist(), 'matrix_bytes': destination.stat().st_size,
            'reasons': dict(Counter(rep['reason'])), 'partial_coverage': sum(not c['complete'] for c in rep['coverage']),
            'publisher_profile': {k: rep['provenance'][k] for k in ('model', 'revision', 'profile', 'runtime', 'pooling', 'prefix')},
            'matrix_sha256': hashlib.sha256(rep['vectors'].tobytes()).hexdigest()}, {'status': 'completed', 'peak_workspace_bytes': work.peak})
    finally:
        work.close()


def predictor(rows, names, categorical, y, train, test, task, matrix):
    if matrix is not None:
        from scipy.linalg import solve
        from scipy.special import softmax
        x = matrix.astype(float); center = x[train].mean(0); x = x-center
        classes = sorted(set(y)); target = np.eye(len(classes))[y[train]]; baseline = target.mean(0)
        weights = solve(x[train].T @ x[train] + np.eye(x.shape[1]), x[train].T @ (target-baseline), assume_a='pos')
        probabilities = softmax(x[test] @ weights + baseline, axis=1)
        return probabilities.argmax(1), probabilities, {'method': 'T-only ridge one-hot regression plus fixed softmax', 'L2': 1.}
    from catboost import CatBoostClassifier, CatBoostRegressor
    data = [[row[name] if name in categorical else float(row[name]) for name in names] for row in rows]
    model = (CatBoostRegressor if task == 'regression' else CatBoostClassifier)(iterations=256, depth=6,
        learning_rate=.05, l2_leaf_reg=3, random_seed=PROFILE['seed'], thread_count=2, allow_writing_files=False, verbose=False)
    model.fit([data[i] for i in train], y[train], cat_features=[i for i, name in enumerate(names) if name in categorical])
    x = [data[i] for i in test]; predicted = np.asarray(model.predict(x)).reshape(-1)
    return predicted, None if task == 'regression' else model.predict_proba(x), {'method': 'T-only CPU CatBoost', 'trees': 256, 'depth': 6}


def frozen_vectors(dataset, contents, temporary):
    """Reuse label-independent benchmark vectors under exact producer identity."""
    from confidenceguard import compat, EvaluationConfig
    from confidenceguard.representations import encode, verified_encoder
    from confidenceguard.features import normalize
    from confidenceguard.feature_storage import validate_matrix
    producer = {f.__name__: hashlib.sha256(inspect.getsource(f).encode()).hexdigest()
                for f in (encode_worker, encode, verified_encoder, normalize)}
    producer.update({p: sha(ROOT/'src/datatrust'/p) for p in ('text_models.py', 'text_normalization.py', 'legacy_casefold.json')})
    runtime = {name: importlib.metadata.version(name) for name in ('numpy', 'torch', 'transformers', 'tokenizers', 'safetensors', 'Pillow')}
    inputs = hashlib.sha256()
    for content in contents:
        raw = Path(content).read_bytes() if dataset == 'cifar10' else content.encode('utf-8')
        inputs.update(len(raw).to_bytes(8, 'little')); inputs.update(raw)
    binding = {'dataset': dataset, 'input_content_sha256': inputs.hexdigest(), 'rows': len(contents),
               'producer_functions': producer, 'runtime': runtime, 'windows_per_event': 4}
    key = hashlib.sha256(json.dumps(binding, sort_keys=True).encode()).hexdigest()
    directory = CACHE/'frozen-vectors.nosync'/dataset; directory.mkdir(parents=True, exist_ok=True)
    target = directory/(key+'.npy'); manifest = directory/(key+'.json')
    if manifest.exists():
        prior = json.loads(manifest.read_text())
        if prior['binding'] != binding or sha(target) != prior['matrix_file_sha256']:
            raise RuntimeError('Frozen benchmark vector evidence changed; no silent regeneration.')
        validate_matrix(target, max_rows=len(contents), max_dimensions=768)
        return np.load(target, allow_pickle=False), {**prior['encoder'], 'benchmark_cache_reused': True}
    encoded = compat.supervise(encode_worker, (dataset, contents, temporary), EvaluationConfig())
    stage = Path(encoded.data['matrix_path'])
    if stage.parent != Path(temporary) or sha(stage) != encoded.data['matrix_file_sha256']:
        raise RuntimeError('Benchmark matrix staging identity changed.')
    validate_matrix(stage, max_rows=len(contents), max_dimensions=768)
    encoder = {k: v for k, v in encoded.data.items() if k != 'matrix_path'}
    encoder.update(execution=encoded.execution, benchmark_cache_reused=False)
    with stage.open('rb') as source, target.open('xb') as destination:
        shutil.copyfileobj(source, destination); destination.flush(); os.fsync(destination.fileno())
    record = {'binding': binding, 'matrix_file_sha256': sha(target), 'encoder': encoder,
              'redistribution': 'Protected benchmark cache only. Exclude matrix and source content from review ZIP.'}
    with manifest.open('x') as destination:
        json.dump(record, destination, sort_keys=True, indent=2); destination.write('\n'); destination.flush(); os.fsync(destination.fileno())
    return np.load(target, allow_pickle=False), encoder


def journey(dataset, kind, root, y, prediction, probabilities, rows, fields, matrix, oracle):
    from confidenceguard import InvestigationSpec, InvestigationLimits, investigate, freeze_hypotheses, ConfirmationSpec, confirm_investigation
    from confidenceguard.investigation import arguments, prepared
    from confidenceguard.investigation_membership import apply
    from confidenceguard.investigation_objectives import bind
    is_regression = dataset == 'wine'; path = root / (kind + '.csv'); class_count = len(set(y))
    with path.open('w', newline='') as stream:
        writer = csv.writer(stream); writer.writerow(['id', 'entity', 'target', 'point', *[f'p{i}' for i in range(class_count) if not is_regression], *fields])
        for i in range(len(y)):
            writer.writerow([i, i, y[i], prediction[i], *([] if is_regression else probabilities[i]), *[rows[i][f] for f in fields]])
    task = {'kind': 'regression' if is_regression else 'binary_classification' if class_count == 2 else 'multiclass_classification',
            'outcome_definition': f'{dataset}: publisher label, benchmark {kind} supplied predictions'}
    if is_regression: task.update(units='quality score', material_error=1.)
    else:
        task['classes'] = [str(i) for i in range(class_count)]
        if class_count == 2: task['positive_class'] = '1'
    run = {'id': 'candidate', 'source': 'data', 'model': {'id': f'benchmark-{dataset}-{kind}', 'version': 'v1'},
           'key_columns': ['id'], 'entity_columns': ['entity'], 'prediction': 'point'}
    if not is_regression: run['probabilities'] = {'columns': {str(i): f'p{i}' for i in range(class_count)}}
    objective = {'id': 'objective', 'run': 'candidate', 'metric': 'bias' if is_regression else 'error_rate',
                 'direction': 'absolute' if is_regression else 'higher', 'units': 'quality score' if is_regression else 'fraction',
                 'practical_threshold': .5 if is_regression else .15}
    features = [{'id': 'context', 'availability': 'at_decision', 'fields': list(fields.values())}] if fields else []
    reps = []
    if matrix is not None:
        vectors = root / 'vectors.npy'
        if not vectors.exists(): np.save(vectors, matrix)
        reps = [{'id': 'publisher', 'matrix_path': str(vectors), 'keys_source': {'id': 'keys', 'path': str(path)},
                 'key_columns': ['id'], 'availability': 'at_decision', 'dimensions': matrix.shape[1]}]
    spec = InvestigationSpec.from_dict({'name': f'{dataset} {kind} benchmark', 'evaluation': {'task': task,
        'sources': [{'id': 'data', 'path': str(path)}], 'runs': [run], 'outcomes': {'source': 'data', 'column': 'target', 'key_columns': ['id']}},
        'roles': {'namespace': f'cg4-realistic-{dataset}-{kind}-v1', 'unit': 'entity'}, 'objectives': [objective],
        'features': features, 'representations': reps,
        'limits': replace(InvestigationLimits(), max_nodes=PROFILE['max_nodes'], candidates_per_strategy=64, stability_replicates=3).to_dict()})
    result = investigate(spec); chosen = result.data['investigation']['shortlist']
    assessment = None
    if chosen:
        # Unknown original entity dependence/exposure never becomes verified IID
        # because a benchmark randomly splits rows or fits its own T predictor.
        family = freeze_hypotheses(result, confirmation=ConfirmationSpec(method='bca' if is_regression else 'finite'))
        assessment = confirm_investigation(family)
        if any(a['state'] == 'confirmed' for a in assessment.data['investigation']['assessments']):
            raise AssertionError('Incomplete realistic-data provenance must refuse formal confirmation.')
    measurements = {}
    s, c, roots = arguments(spec, None, None)
    with prepared(s, c, roots) as p:
        objective = bind(spec.objectives[0], p.store)
        for role in ('D', 'S', 'H'):
            indices, f, representations = p.role_data(role); mask = np.zeros(len(indices), bool); available = np.ones(len(indices), bool)
            native = []
            cache = {'_models': result.private['models'], '_directory': str(p.work.root), '_population_size': len(indices),
                     '_max_distance_ops': spec.limits.max_distance_operations}
            for candidate in result.data['investigation']['candidates']:
                if candidate['id'] not in chosen: continue
                artifact = result.private['artifacts'][candidate['membership_artifact']]
                applied = apply(artifact, f, representations, cache=cache, check=p.work.check)
                mask |= applied['member']; available &= applied['available']
                measured = p.evaluate(objective, role, indices, applied, artifact)
                native.append({'strategy': candidate['strategy'], **{k: measured[k] for k in (
                    'effect', 'effect_state', 'conditional_members', 'conditional_nonmembers', 'planned', 'available', 'unavailable')},
                    'member_metric': measured['member_metric']['value'],
                    'comparator_metric': measured['comparator_metric']['value'] if measured['comparator_metric'] else None,
                    'interpretation': 'Frozen gate; held-out descriptive effect. Original population independence remains unknown.'})
            available |= mask
            truth = oracle[np.array([int(json.loads(p.keys[i])[0]) for i in indices])]
            measurements[role] = recovery(truth, mask, available) if kind == 'injected' else {
                'planned': len(indices), 'members': int(mask.sum()), 'unavailable': int((~available).sum())}
            measurements[role]['selected_native_effects'] = native
    return {'kind': kind, 'prediction_source_sha256': sha(path), 'limits': spec.limits.to_dict(),
            'candidates': len(result.data['investigation']['candidates']), 'selected': len(chosen), 'population_measurements': measurements,
            'S_selected_effects': [{'strategy': row['strategy'], 'metric': row['objective']['metric'], 'S': {
                k: row['S'][k] for k in ('effect', 'effect_state', 'conditional_members', 'conditional_nonmembers', 'unavailable') if k in row['S']}}
                for row in result.data['investigation']['candidates'] if row['id'] in chosen],
            'assessments': [{k: a[k] for k in ('state', 'effect', 'effect_state', 'reason', 'support', 'strength') if k in a}
                for a in assessment.data['investigation']['assessments']] if assessment else [],
            'strategy_execution': result.data['investigation']['strategies'], 'execution': result.execution}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('dataset', choices=('bank', 'wine', 'ag_news', 'cifar10'))
    parser.add_argument('--out', required=True); args = parser.parse_args(); started = time.monotonic(); sources = identity(); harness = sha(Path(__file__))
    rng = np.random.default_rng(PROFILE['seed']); nt = PROFILE[args.dataset+'_train']; ne = PROFILE[args.dataset+'_evaluate']
    with tempfile.TemporaryDirectory(prefix='numek-cg4-realistic-', dir='/private/tmp') as temporary, threadpool_limits(limits=2):
        directory = Path(temporary); encoder = None
        if args.dataset in {'bank', 'wine'}:
            rows, names, categorical, y, task, manifest = load_tabular(args.dataset); matrix = None
        else:
            contents, y, manifest = load_content(args.dataset, directory)
            matrix, encoder = frozen_vectors(args.dataset, contents, temporary)
            if not all(encoder['available']): raise RuntimeError('Preserve incomplete encoding instead of substituting zero vectors.')
            rows = [{} for _ in y]; names = []; categorical = set(); task = 'multiclass_classification'
        order = rng.permutation(len(rows)); train = order[:nt]; test = order[nt:nt+ne]
        if len(test) != ne: raise RuntimeError('The locked dataset profile exceeds the acquired population.')
        predicted, probabilities, predictor_profile = predictor(rows, names, categorical, y, train, test, task, matrix)
        if args.dataset == 'bank': oracle = np.array([row['job'] == 'blue-collar' for row in rows])[test]
        elif args.dataset == 'wine': oracle = np.array([float(row['alcohol']) > 11.5 for row in rows])[test]
        else: oracle = matrix[test, 0] > np.quantile(matrix[train, 0], .85)
        fields = {f'f{i}': {'id': f'f{i}', 'column': f'f{i}', 'kind': 'categorical' if name in categorical else 'float'} for i, name in enumerate(names)}
        values = [{f'f{j}': rows[i][name] for j, name in enumerate(names)} for i in test]
        natural = journey(args.dataset, 'natural', directory, y[test], predicted, probabilities, values, fields, matrix[test] if matrix is not None else None, oracle)
        if task == 'regression': injected = y[test]+rng.normal(0, .25, ne)+2*oracle; injected_probabilities = None
        else:
            error = rng.random(ne) < np.where(oracle, .4, .1); classes = len(set(y)); injected = (y[test]+error*rng.integers(1, classes, ne)) % classes
            injected_probabilities = np.full((ne, classes), .1/(classes-1)); injected_probabilities[np.arange(ne), injected] = .9
        controlled = journey(args.dataset, 'injected', directory, y[test], injected, injected_probabilities, values, fields, matrix[test] if matrix is not None else None, oracle)
        record = {'schema_version': 'numek.cg4_realistic_benchmark/1.0', 'dataset': args.dataset, 'profile': PROFILE,
            'acquisition': manifest, 'T_count': nt, 'evaluation_count': ne,
            'T_index_sha256': hashlib.sha256(train.tobytes()).hexdigest(), 'evaluation_index_sha256': hashlib.sha256(test.tobytes()).hexdigest(),
            'T_DSH_overlap': bool(set(train) & set(test)), 'predictor': predictor_profile, 'encoder': encoder,
            'oracle_prevalence': float(oracle.mean()), 'journeys': [natural, controlled], 'seconds': time.monotonic()-started,
            'source_sha256': sources, 'harness_sha256': harness, 'packages': runtime_versions(),
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'scope': 'Realistic and separately injected diagnostic workflows. Original entity dependence, upstream exposure '
                'and actual decision-time content availability are not established. No formal independent confirmation, '
                'causal claim, natural oracle-recovery claim, or universal encoder qualification. No dataset contents are exported.'}
        if identity() != sources or sha(Path(__file__)) != harness: record['status'] = 'invalidated_source_change'
        else: record['status'] = 'completed'
        with Path(args.out).open('x') as stream: json.dump(record, stream, sort_keys=True, indent=2, allow_nan=False); stream.write('\n')
        print(json.dumps({'dataset': args.dataset, 'status': record['status'], 'seconds': record['seconds']}))


if __name__ == '__main__':
    main()
