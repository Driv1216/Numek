from contextlib import closing
import pytest
from confidenceguard import ReliabilityWorkspace,WorkspaceConfig
from confidenceguard.contracts import digest
from confidenceguard.evidence_use import EvidenceUseLedger,record_session,session_overlap


def workspace(path):
    result=ReliabilityWorkspace.initialize(path,WorkspaceConfig(saving=True,free_disk_bytes=1))
    result.evidence_tracking(True)
    return result


def use_object(ws,receipt):
    with closing(ws.catalog._connect()) as db:
        return db.execute('SELECT object_id FROM evidence_uses WHERE id=?',(receipt['evidence_use_id'],)).fetchone()[0]


def test_deleted_exposure_releases_only_its_owned_session_identifiers(tmp_path):
    first=workspace(tmp_path/'first');second=workspace(tmp_path/'second')
    ledger=EvidenceUseLedger(first)
    erased=digest([str(tmp_path),'erase']);kept=digest([str(tmp_path),'keep']);shared=digest([str(tmp_path),'shared'])
    def record(target,event,request):
        return target.record('outcome_disclosure',events=[event],units=[],population_digest=digest('same-population'),request_id=request)
    removed=record(ledger,erased,'removed');record(ledger,kept,'retained');other=record(EvidenceUseLedger(second),shared,'other')
    removed_shared=record(ledger,shared,'shared')
    assert session_overlap([erased],[]) and session_overlap([kept],[])
    first.delete(first.deletion_preview(object_ids=[use_object(first,removed),use_object(first,removed_shared)]))
    assert not session_overlap([erased],[])
    assert session_overlap([kept],[]) and session_overlap([shared],[])
    # Idempotent old receipts remain historical records, never a way to retain
    # deleted membership again. Missing history still forbids freshness claims.
    assert record(ledger,erased,'removed')==removed
    assert not session_overlap([erased],[])
    assert ledger.status()['continuity']=='incomplete'
    assert set(ledger.overlap([erased],[])) & {'exposure_history_incomplete','exposure_history_unavailable'}
    second.delete(second.deletion_preview(purge=True))
    assert not session_overlap([shared],[])
    assert session_overlap([kept],[])
    assert other['evidence_use_id']!=removed_shared['evidence_use_id']


def test_tombstone_failure_and_recovery_do_not_retain_deleted_session_values(tmp_path,monkeypatch):
    ws=workspace(tmp_path/'workspace');ledger=EvidenceUseLedger(ws)
    event=digest([str(tmp_path),'event']);standalone=digest([str(tmp_path),'standalone'])
    receipt=ledger.record('outcome_disclosure',events=[event],units=[],population_digest=digest(event))
    record_session('discovery_selection',[standalone],[],workspace=ws)
    record_session('outcome_disclosure',[standalone],[])  # separate unowned observation
    def fault(boundary):
        if boundary=='deletion_tombstoned':raise RuntimeError('synthetic crash after tombstone')
    monkeypatch.setattr(ws.catalog,'_fault',fault)
    with pytest.raises(RuntimeError,match='synthetic crash'):
        ws.delete(ws.deletion_preview(object_ids=[use_object(ws,receipt)]))
    assert not session_overlap([event],[])
    from confidenceguard.evidence_use import _SESSION_USES
    assert not any(v.get('owner')==ws.instance_id and standalone in v['events'] for v in _SESSION_USES)
    assert session_overlap([standalone],[])
    ws.catalog.recover()
    assert not session_overlap([event],[])
    assert ledger.status()['continuity']=='incomplete'


def test_purge_releases_untracked_workspace_memory_but_preserves_other_owners(tmp_path):
    ws=workspace(tmp_path/'workspace');ws.evidence_tracking(False)
    other=workspace(tmp_path/'other')
    event=digest([str(tmp_path),'untracked'])
    record_session('discovery_selection',[event],[],workspace=ws)
    record_session('discovery_selection',[event],[],workspace=other)
    ws.delete(ws.deletion_preview(purge=True))
    assert session_overlap([event],[])
    other.delete(other.deletion_preview(purge=True))
    assert not session_overlap([event],[])
