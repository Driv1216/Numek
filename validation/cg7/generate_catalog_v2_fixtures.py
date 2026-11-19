"""Generate frozen catalog v2 fixture workspaces for the v2 -> platform migration tests (CG7 S3c).

Run once with the last runtime that still has the catalog v2 writer (CG7 S3, before the writer's
retirement), from the repository root, without ``NUMEK_PLATFORM_DSN``:

    validation/cg7/py313.nosync/bin/python validation/cg7/generate_catalog_v2_fixtures.py

It writes ``tests/fixtures/catalog_v2/{cg3,cg3_deletion,multi}.tar.gz`` and ``manifest.json``
(runtime identity, archive digests, analysis ids and the frozen CG4 spec the tests reuse). The
archives are immutable test inputs; later runtimes can only read and migrate them.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'tests' / 'fixtures' / 'catalog_v2'


def _shift(path, offset):
    rows = path.read_text().splitlines()
    path.write_text('\n'.join([rows[0]] + [','.join([str(offset + int(r.split(',')[0]))] + r.split(',')[1:])
                                           for r in rows[1:]]) + '\n')


def cg3(base):
    import importlib.util
    spec = importlib.util.spec_from_file_location('cg3_helpers', ROOT / 'tests' / 'cg3' / 'test_history.py')
    helpers = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helpers)
    return helpers


def build_cg3(base):
    h = cg3(base)
    ws = h.workspace(base)
    ws.ingest(h.batch(base))
    first = ws.analyze(h.longitudinal(ws), request_id='first')
    extra = h.batch(base, 'more', count=14)
    _shift(Path(extra['evaluation']['sources'][0]['path']), 100)
    ws.ingest(extra)
    restated = ws.restate(first.data['analysis_id'], as_of='2026-03-03T00:00:00Z', reason='Outcome-only snapshot')
    ws.evidence_tracking(True)
    tracked = ws.analyze(h.longitudinal(ws, name='tracked'), request_id='tracked')
    doomed = ws.analyze(h.longitudinal(ws, name='doomed'))
    ws.delete(ws.deletion_preview(assessment_ids=[doomed.data['analysis_id']]))
    return ws, {'first': first.data['analysis_id'], 'restated': restated.data['analysis_id'],
                'tracked': tracked.data['analysis_id'], 'doomed': doomed.data['analysis_id']}, {}


def build_cg3_deletion(base):
    h = cg3(base)
    ws = h.workspace(base)
    ws.ingest(h.batch(base))
    analysis = ws.analyze(h.longitudinal(ws))
    extra = h.batch(base, 'more', count=14)
    _shift(Path(extra['evaluation']['sources'][0]['path']), 100)
    receipt = ws.ingest(extra)
    reading = ws.analyze(h.longitudinal(ws, name='reads-the-deleted-batch'))
    fact = next(f for f in ws.catalog.iter_facts('prediction') if f['recorded_sequence'] == receipt['catalog_sequence'])
    ws.delete(ws.deletion_preview(object_ids=[fact['object_id']]))
    return ws, {'analysis': analysis.data['analysis_id'], 'reading': reading.data['analysis_id']}, {}


def build_multi(base):
    sys.path.insert(0, str(ROOT))
    from confidenceguard import (ConfirmationLook, ConfirmationSpec, PolicyInputSpec, PolicyMetricSpec, PolicySpec,
                                 PolicyStudySpec, execute_predictor, inspect_investigation)
    from confidenceguard.contracts import TaskDefinition
    from confidenceguard.investigation_contracts import InvestigationSpec
    from confidenceguard.method_contracts import RoleSpec
    from tests.cg4.test_history import retained
    from tests.cg5.test_assessment import protocol as policy_protocol
    from tests.cg6.helpers import CFG as CFG6, execution
    ws, spec = retained(base)
    ws.evidence_tracking(True)
    frozen_spec = InvestigationSpec.from_dict(inspect_investigation(spec)['effective_spec'])
    discovery = ws.investigate(frozen_spec)
    family = ws.freeze_hypotheses(discovery, confirmation=ConfirmationSpec(
        study_id='migration-study', batch_alpha=.025, restatement_schedule=(ConfirmationLook('april', '2026-04-01T00:00:00Z', .025),),
        upstream_independence='declared_independent', external_exposure='declared_unexposed', declaration_author='fixture',
        declaration_reason='Independent synthetic entities, locally protected study.'))
    confirmed = ws.confirm_investigation(family, request_id='confirm')
    inp = PolicyInputSpec(RoleSpec(spec.roles.namespace, proportions={'S': .5, 'E': .5}, unit='entity'), history=spec.history)
    task = TaskDefinition('binary_classification', 'fixture', ('0', '1'), '1')
    policy = PolicySpec(task, spec.objectives[0].run, {'root': {'kind': 'action', 'action': {'kind': 'supplied'}}}, 'root',
                        {'kind': 'abstain'}, {'kind': 'unavailable'})
    selected = ws.optimize_policies(PolicyStudySpec(inp, (PolicyMetricSpec('accuracy', 'issued_accuracy', 'maximize'),),
                                                    candidates=(policy,)), {'free_disk_bytes': 1}, request_id='select')
    assessed = ws.assess_policies(ws.freeze_policy_family(selected, assessment=policy_protocol(selected)),
                                  {'free_disk_bytes': 1}, request_id='assess')
    (base / 'cg6').mkdir()
    executed = execute_predictor(execution(base / 'cg6', n=24), CFG6, workspace=ws)
    ids = {'discovery': discovery.data['analysis_id'], 'confirmed': confirmed.data['analysis_id'],
           'selected': selected.data['analysis_id'], 'assessed': assessed.data['analysis_id'],
           'executed': executed.data['analysis_id']}
    return ws, ids, {'frozen_spec': frozen_spec.to_dict()}


def main():
    if os.environ.get('NUMEK_PLATFORM_DSN'):
        raise SystemExit('Unset NUMEK_PLATFORM_DSN: fixtures are catalog v2 workspaces.')
    sys.path.insert(0, str(ROOT))
    OUT.mkdir(parents=True, exist_ok=True)
    commit = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    dirty = bool(subprocess.run(['git', 'status', '--porcelain', '--', 'src'], cwd=ROOT, capture_output=True, text=True).stdout.strip())
    manifest = {'schema_version': 'numek.catalog_v2_fixtures/1.0', 'generated_by': {
        'runtime_commit': commit, 'source_tree_modified': dirty, 'python': sys.version.split()[0],
        'note': 'Generated by the last runtime with the catalog v2 writer (CG7 S3, before writer retirement).'},
        'fixtures': {}}
    for name, build in (('cg3', build_cg3), ('cg3_deletion', build_cg3_deletion), ('multi', build_multi)):
        work = Path(tempfile.mkdtemp(prefix='nmk-v2fx-')).resolve()
        try:
            ws, ids, extra = build(work)
            assert (ws.path / 'catalog.sqlite3').exists() and not (ws.path / 'platform.json').exists()
            status = ws.status()
            archive = OUT / f'{name}.tar.gz'
            with tarfile.open(archive, 'w:gz') as tar:
                tar.add(ws.path, arcname='workspace')
            manifest['fixtures'][name] = {'archive': archive.name, 'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
                                          'bytes': archive.stat().st_size, 'original_root': str(ws.path),
                                          'catalog_sequence': status['catalog_sequence'], 'facts': status['facts'],
                                          'analysis_ids': ids, **extra}
        finally:
            shutil.rmtree(work, ignore_errors=True)
    (OUT / 'manifest.json').write_text(json.dumps(manifest, indent=1, sort_keys=True) + '\n')
    print(json.dumps({k: v['bytes'] for k, v in manifest['fixtures'].items()}))


if __name__ == '__main__':
    main()
