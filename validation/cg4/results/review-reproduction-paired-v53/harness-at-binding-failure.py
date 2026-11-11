"""Small synthetic product/lifecycle reproduction, not method qualification.

The deliberately exposed fixture may demonstrate discovery and refusal, never a
fresh independent confirmation. All outputs use a new caller-specified directory.
"""
import argparse
from collections import Counter
import csv
import copy
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sqlite3
import sys
import tarfile

import numpy as np


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', required=True)
    parser.add_argument('--require-wheel', action='store_true')
    parser.add_argument('--objective',choices=('error_rate','paired_precision'),default='error_rate')
    args = parser.parse_args()
    import confidenceguard
    import datatrust
    from confidenceguard import (ConfirmationSpec, InvestigationSpec,
                                 ReliabilityWorkspace, WorkspaceConfig)
    origins = {name: str(Path(module.__file__).resolve())
               for name, module in [('confidenceguard', confidenceguard), ('datatrust', datatrust)]}
    if args.require_wheel and any('site-packages' not in Path(path).parts for path in origins.values()):
        raise RuntimeError('Reproduction requires wheel imports, without source/editable overrides.')
    out = Path(args.out).absolute()
    if out.exists():
        raise RuntimeError('Preserve earlier evidence; use a new reproduction directory.')
    out.mkdir(parents=True, mode=0o700)
    inputs = out / 'inputs'; inputs.mkdir()
    source = inputs / 'predictions.csv'
    rows = []
    for i in range(720):
        x = (i // 3) % 2; z = (i // 6) % 2; y = (i // 12) % 2
        prediction = (1 if x else y) if args.objective=='paired_precision' else y ^ (x != z)
        rows.append([str(i), str(i), str(y), str(int(prediction)), '.8' if prediction else '.2',
                     str(x), str(z), ('D', 'S', 'H')[i % 3],
                     '2026-01-01T00:00:00Z', '2026-01-02T00:00:00Z',str(y)])
    with source.open('x', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['id', 'entity', 'y', 'decision', 'p', 'x', 'z', 'role', 'when', 'available','reference'])
        writer.writerows(rows)
    vectors = np.array([[float(row[5]), float(row[6])] * 4 for row in rows], dtype='<f4')
    matrix = inputs / 'coordinates.npy'; np.save(matrix, vectors, allow_pickle=False)
    packet = {
        'name': 'Previously exposed synthetic CG4 review reproduction',
        'evaluation': {
            'task': {'kind': 'binary_classification', 'classes': ['0', '1'], 'positive_class': '1',
                     'outcome_definition': 'Deterministic synthetic review fixture'},
            'sources': [{'id': 'data', 'path': str(source)}],
            'runs': [{'id': 'model', 'source': 'data', 'model': {'id': 'synthetic-review', 'version': 'v1'},
                      'key_columns': ['id'], 'entity_columns': ['entity'], 'prediction': 'decision',
                      'probabilities': {'positive_column': 'p'}, 'prediction_at': {'column': 'when'}}],
            'outcomes': {'source': 'data', 'column': 'y', 'key_columns': ['id'],
                         'available_at': {'column': 'available'}},
            'as_of': '2026-02-01T00:00:00Z'},
        'roles': {'namespace': 'cg4-exposed-review-fixture-v1', 'unit': 'entity', 'column': 'role'},
        'features': [{'id': 'context', 'availability': 'at_decision',
                      'fields': [{'id': 'x', 'column': 'x', 'kind': 'categorical'},
                                 {'id': 'z', 'column': 'z', 'kind': 'categorical'}]}],
        'representations': [{'id': 'geometry', 'kind': 'supplied', 'matrix_path': str(matrix),
                             'keys_source': {'id': 'keys', 'path': str(source)}, 'key_columns': ['id'],
                             'dimensions': 8, 'producer': 'NUMEK deterministic synthetic context',
                             'availability': 'at_decision'}],
        'objectives': [{'id': 'error', 'metric': 'error_rate', 'run': 'model', 'practical_threshold': .1}],
        'strategies': ['structured', 'catboost', 'geometric'],
        'limits': {'max_nodes': 10000, 'max_depth': 3, 'candidates_per_strategy': 8,
                   'shortlist': 3, 'stability_replicates': 1, 'landmarks': 16, 'neighbors': 4}}
    if args.objective=='paired_precision':
        reference=copy.deepcopy(packet['evaluation']['runs'][0])
        reference.update(id='reference',prediction='reference',model={'id':'synthetic-review-reference','version':'v1'})
        reference.pop('probabilities')
        packet['evaluation']['runs'].append(reference)
        packet['objectives']=[{'id':'precision','metric':'precision','run':'model','comparator':'paired',
                               'reference_run':'reference','direction':'lower','practical_threshold':.1}]
        packet['roles']['namespace']+='-paired-precision'
    spec=InvestigationSpec.from_dict(packet)
    (inputs / 'spec.json').write_text(json.dumps(spec.to_dict(), indent=2, sort_keys=True) + '\n')
    # Workspaces remain disposable local state; the separately verified archive
    # and exported synthetic evidence are the portable delivery inputs.
    runtime = out / 'runtime.nosync'; runtime.mkdir(mode=0o700)
    ws = ReliabilityWorkspace.initialize(runtime / 'workspace', WorkspaceConfig(saving=True))
    ws.evidence_tracking(True)
    ws.prepare_representations({
        'schema_version': 'confidenceguard.prediction_batch_spec/2.0',
        'evaluation': spec.evaluation.to_dict(), 'namespace': spec.roles.namespace,
        'outcome_definition_version': 'v1', 'bindings': [{'run': 'model'}],
        'feature_views': [view.to_dict() for view in spec.features],
        'discovery_representations': [rep.to_dict() for rep in spec.representations]},
        request_id='review-synthetic-ingest')
    discovered = ws.investigate(spec, request_id='review-synthetic-discovery')
    if not discovered.data['investigation']['shortlist']:
        raise RuntimeError('Synthetic fixture did not produce an investigation shortlist.')
    selected=set(discovered.data['investigation']['shortlist'])
    selected_evidence=[candidate['S'] for candidate in discovered.data['investigation']['candidates'] if candidate['id'] in selected]
    if args.objective=='paired_precision' and not any(abs(row['effect']-.5)<1e-12 and
            row['conditional_members']==120 and row['conditional_nonmembers']==60 for row in selected_evidence):
        raise RuntimeError('Installed paired precision lost the distinct positive denominators.')
    frozen = ws.freeze_hypotheses(discovered, confirmation=ConfirmationSpec(
        upstream_independence='declared_independent', external_exposure='known_exposed',
        declaration_author='NUMEK synthetic review reproduction',
        declaration_reason='Deterministic, previously exposed fixture; demonstrate refusal and lifecycle, not independent confirmation.'),
        request_id='review-synthetic-freeze')
    assessed = ws.confirm_investigation(frozen, request_id='review-synthetic-refusal')
    assessments = assessed.data['investigation']['assessments']
    if not assessments or any(a['state'] != 'statistically_inadmissible' or a['H_outcomes_disclosed'] for a in assessments):
        raise RuntimeError('Known exposure must refuse before H metric assessment.')
    reports = {}
    for name, result, audience in [('discovery', discovered, 'local'), ('assessment', assessed, 'shareable')]:
        directory = out / name; directory.mkdir()
        artifacts = result.generate_artifacts(directory / 'report.pdf', format='pdf',
                                              json_path=directory / 'report.json', audience=audience)
        reports[name] = {'audience': audience, 'html': str(Path(artifacts.html_path).relative_to(out)),
                         'pdf': str(Path(artifacts.pdf_path).relative_to(out)),
                         'json': str(Path(artifacts.json_path).relative_to(out))}
    backup = runtime / 'backup'
    manifest = ws.backup(backup)
    restored = ReliabilityWorkspace.restore(backup, runtime / 'restored-workspace')
    for result in (discovered, assessed):
        if restored.open(result.data['analysis_id']).to_private_dict() != result.to_private_dict():
            raise RuntimeError('Restored assessment changed immutable evidence.')
    if restored.open_hypotheses(frozen.data['content_digest']).to_dict() != frozen.to_dict():
        raise RuntimeError('Restored frozen family changed.')
    for relative in manifest['files']:
        if relative.startswith('objects/') and sha(backup / relative) != sha(restored.path / relative):
            raise RuntimeError('Restored immutable object changed.')
    with sqlite3.connect('file:' + str((backup / 'catalog.sqlite3').resolve()) + '?mode=ro', uri=True) as db:
        codecs = dict(db.execute("SELECT encoding,count(*) FROM objects WHERE state='active' GROUP BY encoding"))
    if not {'utf8_jsonl_v1', 'typed_feature_rows_v1', 'dense_vectors_npy_v1'} <= set(codecs):
        raise RuntimeError('Synthetic backup did not exercise all durable codecs.')
    archive = out / 'synthetic-backup.tar.gz'
    with tarfile.open(archive, 'x:gz') as tar:
        for path in sorted(backup.rglob('*')):
            if path.is_symlink() or not (path.is_file() or path.is_dir()):
                raise RuntimeError('Unsafe synthetic backup member.')
            tar.add(path, arcname='synthetic-backup/' + str(path.relative_to(backup)), recursive=False)
    archive.chmod(0o600)
    record = {'schema_version': 'numek.cg4_review_reproduction/1.0', 'customer_evidence': False,
              'python': sys.version, 'import_origins': origins, 'script_sha256': sha(__file__),
              'installed_distribution': importlib.metadata.version('datatrust'),
              'objective':args.objective,
              'selected_S_evidence':[{'effect':row['effect'],'conditional_members':row['conditional_members'],
                                      'conditional_nonmembers':row['conditional_nonmembers']} for row in selected_evidence],
              'shortlist': discovered.data['investigation']['shortlist'],
              'finding_states': dict(Counter(a['state'] for a in assessments)),
              'H_metrics_disclosed': any(a['H_outcomes_disclosed'] for a in assessments),
              'family_content_digest': frozen.data['content_digest'], 'backup_codecs': codecs,
              'backup_manifest_digest': manifest['content_digest'], 'archive_sha256': sha(archive),
              'immutable_assessments_and_hypotheses_restored': True,
              'restored_exposure': restored.evidence_tracking(), 'reports': reports,
              'scope': 'Small actual product and mixed-codec backup/restore replay from the installed wheel when required. No recovery, fresh statistical confirmation, method qualification or final ZIP/acceptance claim. PDF visual inspection is separate.'}
    with (out / 'verification.json').open('x') as stream:
        json.dump(record, stream, indent=2, sort_keys=True); stream.write('\n')
    print(json.dumps(record, sort_keys=True))


if __name__ == '__main__':
    main()
