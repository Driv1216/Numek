"""ConfidenceGuard CG3 on the platform: parity, governance before access, identity preservation.

The full CG3 suite is also run with ``NUMEK_PLATFORM_DSN`` set (see the CG7
status record). This test keeps a representative workflow in the default suite.
"""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _cg3_helpers():
    spec = importlib.util.spec_from_file_location('cg3_history_helpers', ROOT / 'cg3' / 'test_history.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def cg3(platform, monkeypatch):
    monkeypatch.setenv('NUMEK_PLATFORM_DSN', platform.db.dsn)
    return _cg3_helpers()


def test_cg3_history_workflow_runs_on_the_platform(platform, cg3, tmp_path):
    from confidenceguard import EvaluationError
    from confidenceguard.platform_catalog import PlatformCatalog
    tmp_path = tmp_path.resolve()
    ws = cg3.workspace(tmp_path)
    assert isinstance(ws.catalog, PlatformCatalog) and not (ws.path / 'catalog.sqlite3').exists()
    receipt = ws.ingest(cg3.batch(tmp_path))
    assert receipt['catalog_sequence'] == 1 and receipt['new_facts'] > 0
    again = ws.ingest(cg3.batch(tmp_path))      # identical bytes: only the per-operation capture metadata is new (as in v2)
    assert again['new_facts'] == 1 and again['duplicate_occurrences'] == receipt['new_facts'] - 1
    status = ws.status()
    assert status['storage'] == 'numek_platform' and status['facts']['prediction'] == 12

    request = cg3.longitudinal(ws)
    first = ws.analyze(request, request_id='analysis-1')
    retry = ws.analyze(request, request_id='analysis-1')
    assert retry.to_private_dict() == first.to_private_dict()       # idempotent receipt
    with pytest.raises(EvaluationError, match='different content'):
        ws.analyze(cg3.longitudinal(ws, name='changed'), request_id='analysis-1')
    reopened = ws.open(first.data['analysis_id'])
    assert reopened.to_private_dict() == first.to_private_dict()

    # Governance before access: the analysis reserved the namespace's outcomes
    # and its saved assessment consumed that reservation.
    with platform.db.connect() as conn:
        uses = conn.execute("SELECT purpose, state, metadata->>'purpose' AS label FROM evidence_uses WHERE catalog_id = %s",
                            (ws.catalog.catalog_id,)).fetchall()
    assert {(u['label'], u['state']) for u in uses} >= {('historical_analysis', 'consumed')}

    # Outcome facts are not readable without a reservation.
    with pytest.raises(EvaluationError) as caught:
        list(ws.catalog.iter_facts('outcome'))
    assert caught.value.code == 'reservation_required'

    # v2 identities preserved: object ids are 32-hex, sequences are contiguous.
    fact = next(ws.catalog.iter_facts('prediction'))
    assert len(fact['object_id']) == 32 and fact['recorded_sequence'] == 1


def test_cg3_outcome_only_restatement_keeps_the_prediction_snapshot(platform, cg3, tmp_path):
    tmp_path = tmp_path.resolve()
    ws = cg3.workspace(tmp_path)
    ws.ingest(cg3.batch(tmp_path))
    analysis = ws.analyze(cg3.longitudinal(ws))
    extra = cg3.batch(tmp_path, 'more', count=14)
    path = Path(extra['evaluation']['sources'][0]['path'])
    rows = path.read_text().splitlines()
    path.write_text('\n'.join([rows[0]] + [','.join([str(100 + int(r.split(',')[0]))] + r.split(',')[1:]) for r in rows[1:]]) + '\n')
    ws.ingest(extra)
    restated = ws.restate(analysis.data['analysis_id'], as_of='2026-03-03T00:00:00Z', reason='Outcome-only snapshot')
    assert [r['selected_predictions'] for r in restated.data['history']['window_coverage']] == [6, 6]
    current = ws.analyze(cg3.longitudinal(ws))
    assert [r['selected_predictions'] for r in current.data['history']['window_coverage']] == [13, 13]


def test_cg3_deletion_on_the_platform(platform, cg3, tmp_path):
    from confidenceguard import EvaluationError, ReliabilityWorkspace
    tmp_path = tmp_path.resolve()
    ws = cg3.workspace(tmp_path)
    ws.ingest(cg3.batch(tmp_path))
    analysis = ws.analyze(cg3.longitudinal(ws))
    fact = next(ws.catalog.iter_facts('prediction'))
    preview = ws.deletion_preview(object_ids=[fact['object_id']])
    assert analysis.data['analysis_id'] in preview['potentially_impacted_assessments']
    assert fact['object_id'] in preview['object_ids'] and preview['affected_batches']
    before = ws.status()['catalog_sequence']
    assert ws.delete(preview)['deleted_objects'] == len(preview['object_ids'])
    assert ws.status()['catalog_sequence'] == before + 1                 # v2: deletion advances K by one
    assert ws.evidence_tracking()['continuity'] == 'incomplete'
    with pytest.raises(EvaluationError) as caught:                     # deleted evidence never shrinks silently
        ws.analyze(cg3.longitudinal(ws))
    assert caught.value.code == 'historical_evidence_unavailable'
    with pytest.raises(EvaluationError) as caught:                     # and cannot be resurrected
        ws.ingest(cg3.batch(tmp_path))
    assert caught.value.code == 'historical_evidence_unavailable'
    with pytest.raises(EvaluationError) as caught:
        ws.delete(preview)
    assert caught.value.code == 'stale_deletion'
    purge = ws.deletion_preview(purge=True)
    assert ws.delete(purge)['workspace_retired'] is True
    with pytest.raises(EvaluationError) as caught:
        ReliabilityWorkspace(ws.path)
    assert caught.value.code == 'workspace_retired'


def test_cg3_local_workspace_backup_and_restore(tmp_path, monkeypatch, cluster):
    """A workspace with its own P-LOCAL cluster backs up and restores into a new instance."""
    from confidenceguard import ReliabilityWorkspace, WorkspaceConfig
    from numek_platform.local import LocalCluster
    monkeypatch.delenv('NUMEK_PLATFORM_DSN', raising=False)
    helpers = _cg3_helpers()
    tmp_path = tmp_path.resolve()
    ws = ReliabilityWorkspace.initialize(tmp_path / 'workspace', WorkspaceConfig(saving=True, free_disk_bytes=1), platform=True)
    restored = None
    try:
        ws.ingest(helpers.batch(tmp_path))
        analysis = ws.analyze(helpers.longitudinal(ws))
        ws.backup(tmp_path / 'backup')
        restored = ReliabilityWorkspace.restore(tmp_path / 'backup', tmp_path / 'restored')
        assert restored.instance_id != ws.instance_id
        assert restored.open(analysis.data['analysis_id']).to_private_dict() == analysis.to_private_dict()
        assert restored.status()['catalog_sequence'] == ws.status()['catalog_sequence']
        assert restored.evidence_tracking()['continuity'] == 'restore_unreconciled'
        again = restored.analyze(helpers.longitudinal(restored))
        assert again.data['history']['window_coverage'] == analysis.data['history']['window_coverage']
    finally:
        for root in (tmp_path / 'workspace', tmp_path / 'restored'):
            if (root / 'platform').exists():
                LocalCluster(root / 'platform').stop()


def test_shared_installation_workspace_refuses_workspace_backup_without_side_effects(platform, cg3, tmp_path):
    """Replacement contract for v2 workspace backups on a shared installation (S3d)."""
    from confidenceguard import EvaluationError, ReliabilityWorkspace
    tmp_path = tmp_path.resolve()
    ws = cg3.workspace(tmp_path)
    ws.ingest(cg3.batch(tmp_path))
    before = ws.status()
    with pytest.raises(EvaluationError) as caught:
        ws.backup(tmp_path / 'backup')
    assert caught.value.code == 'backup_scope'
    assert not (tmp_path / 'backup').exists()                       # nothing partial is left behind
    assert ws.status() == before                                     # and the workspace is unchanged
    with pytest.raises(EvaluationError) as caught:                  # and nothing restorable exists
        ReliabilityWorkspace.restore(tmp_path / 'backup', tmp_path / 'restored')
    assert caught.value.code == 'backup_changed'
