import pytest
from confidenceguard import EvaluationError,ReliabilityWorkspace,WorkspaceConfig
from confidenceguard.contracts import digest
from confidenceguard.evidence_use import EvidenceUseLedger,record_session,session_overlap


def workspace(path):
    result=ReliabilityWorkspace.initialize(path,WorkspaceConfig(saving=True,free_disk_bytes=1))
    result.evidence_tracking(True)
    return result


def use_object(ws,receipt):
    with ws.catalog.db.connect() as conn:
        return conn.execute('SELECT membership_object FROM evidence_uses WHERE catalog_id=%s AND id=%s',
                            (ws.catalog.catalog_id,receipt['evidence_use_id'])).fetchone()['membership_object'].hex


def platform_exposure_is_durable_governance(ws,ledger,receipt,events):
    """Platform contract replacing v2 deletable exposure: uses are durable governance rows.

    Nothing is held in process memory, every recorded member stays exposed, and a
    targeted deletion of a use's record is refused (only a purge retires it, and
    exposure history survives that).
    """
    assert not any(session_overlap([e],[]) for e in events)
    for event in events:assert ledger.overlap([event],[])==['previously_exposed_confirmation_population']
    with pytest.raises(EvaluationError) as caught:ws.deletion_preview(object_ids=[use_object(ws,receipt)])
    assert caught.value.code=='governance_record'


def test_deleted_exposure_releases_only_its_owned_session_identifiers(tmp_path):
    first=workspace(tmp_path/'first');second=workspace(tmp_path/'second')
    ledger=EvidenceUseLedger(first)
    erased=digest([str(tmp_path),'erase']);kept=digest([str(tmp_path),'keep']);shared=digest([str(tmp_path),'shared'])
    def record(target,event,request):
        return target.record('outcome_disclosure',events=[event],units=[],population_digest=digest('same-population'),request_id=request)
    removed=record(ledger,erased,'removed');record(ledger,kept,'retained');other=record(EvidenceUseLedger(second),shared,'other')
    removed_shared=record(ledger,shared,'shared')
    platform_exposure_is_durable_governance(first,ledger,removed,[erased,kept,shared])
    assert record(ledger,erased,'removed')==removed                  # idempotent receipt
    second.delete(second.deletion_preview(purge=True))               # another workspace's purge
    assert ledger.overlap([shared],[])==['previously_exposed_confirmation_population']
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
    # The use itself cannot be deleted; a purge that dies after its tombstones still
    # releases this workspace's process-local values, finishes on reopen, and keeps
    # the durable exposure history.
    platform_exposure_is_durable_governance(ws,ledger,receipt,[event])
    with pytest.raises(RuntimeError,match='synthetic crash'):ws.delete(ws.deletion_preview(purge=True))
    from confidenceguard.evidence_use import _SESSION_USES
    assert not any(v.get('owner')==ws.instance_id for v in _SESSION_USES)
    assert session_overlap([standalone],[])                          # an unowned observation is kept
    with pytest.raises(EvaluationError) as caught:ReliabilityWorkspace(ws.path)
    assert caught.value.code=='workspace_retired'
    with ws.catalog.db.connect() as conn:
        exposed=conn.execute("SELECT outcome_exposed FROM exposure_registry WHERE catalog_id=%s AND member_kind='event' AND hash=%s",
                             (ws.catalog.catalog_id,bytes.fromhex(event))).fetchone()
    assert exposed and exposed['outcome_exposed']                     # exposure history survives the purge


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
