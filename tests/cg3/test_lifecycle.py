import copy
import threading
import pytest
from confidenceguard import EvaluationError, ReliabilityWorkspace
from confidenceguard.history_storage import file_lock
from .test_history import workspace,batch,longitudinal


def test_analysis_receipt_and_outcome_only_prediction_freeze(tmp_path):
    ws=workspace(tmp_path);spec=batch(tmp_path);ws.ingest(spec)
    request=longitudinal(ws)
    a=ws.analyze(request,request_id='same-analysis')
    extra=batch(tmp_path,'more',count=14)
    # A second batch adds genuinely new opportunities to the same variant.
    from .test_semantics import rewrite
    from pathlib import Path
    rewrite(Path(extra['evaluation']['sources'][0]['path']),lambda rows:[r.update(id=str(100+int(r['id']))) for r in rows])
    ws.ingest(extra)
    retry=ws.analyze(request,request_id='same-analysis')
    assert retry.to_private_dict()==a.to_private_dict()
    with pytest.raises(EvaluationError,match='different content'):
        ws.analyze(longitudinal(ws,name='changed'),request_id='same-analysis')
    restated=ws.restate(a.data['analysis_id'],as_of='2026-03-03T00:00:00Z',reason='Outcome-only snapshot')
    assert [r['selected_predictions'] for r in restated.data['history']['window_coverage']]==[6,6]
    assert [r['selected_predictions'] for r in ws.analyze(longitudinal(ws)).data['history']['window_coverage']]==[13,13]


def test_deleted_evidence_cannot_silently_shrink_or_resurrect(tmp_path):
    ws=workspace(tmp_path);spec=batch(tmp_path);receipt=ws.ingest(spec)
    a=ws.analyze(longitudinal(ws));fact=next(ws.catalog.iter_facts('prediction'))
    preview=ws.deletion_preview(object_ids=[fact['object_id']]);assert a.data['analysis_id'] in preview['potentially_impacted_assessments']
    ws.delete(preview)
    assert ws.open(a.data['analysis_id']).to_private_dict()==a.to_private_dict()
    with pytest.raises(EvaluationError) as e:ws.analyze(longitudinal(ws))
    assert e.value.code=='historical_evidence_unavailable'
    with pytest.raises(EvaluationError) as e:ws.ingest(spec)
    assert e.value.code=='historical_evidence_unavailable'


def test_operation_and_download_locks_are_bounded(tmp_path):
    ws=workspace(tmp_path);ws.ingest(batch(tmp_path));errors=[]
    def mutate():
        try:ws.set_saving(False)
        except EvaluationError as exc:errors.append(exc.code)
    with file_lock(ws.catalog.operation_path):
        worker=threading.Thread(target=mutate);worker.start();worker.join(5)
    assert not worker.is_alive() and errors==['workspace_busy']
    fact=next(ws.catalog.iter_facts('prediction'));plan=ws.deletion_preview(object_ids=[fact['object_id']])
    with file_lock(ws.catalog.objects_lock,False):
        with pytest.raises(EvaluationError) as e:ws.delete(plan)
        assert e.value.code=='workspace_busy'


def test_inspection_effective_populations_and_backup_refusal(tmp_path):
    ws=workspace(tmp_path);ws.ingest(batch(tmp_path));before=ws.status()['catalog_sequence']
    preview=ws.inspect(longitudinal(ws))
    assert [c['selected_predictions'] for c in preview['population_preview']['window_coverage']]==[6,6]
    assert ws.status()['catalog_sequence']==before
    backup=tmp_path/'backup';ws.backup(backup)
    (backup/'backup.json').write_text('{}')
    with pytest.raises(EvaluationError):ReliabilityWorkspace.restore(backup,tmp_path/'restored')


def test_interrupted_full_purge_completes_on_reopen(tmp_path,monkeypatch):
    ws=workspace(tmp_path);ws.ingest(batch(tmp_path));plan=ws.deletion_preview(purge=True)
    def crash(boundary):
        if boundary=='deletion_tombstoned':raise RuntimeError('process died')
    monkeypatch.setattr(ws.catalog,'_fault',crash)
    with pytest.raises(RuntimeError):ws.delete(plan)
    with pytest.raises(EvaluationError) as e:ReliabilityWorkspace(ws.path)
    assert e.value.code=='workspace_retired'
    assert not (ws.path/'catalog.sqlite3').exists()
    assert not list((ws.path/'objects').iterdir())


@pytest.mark.parametrize('boundary,committed',[('before_catalog_commit',False),('catalog_committed',True)])
def test_crash_commit_visibility_and_lost_response_receipt(tmp_path,monkeypatch,boundary,committed):
    ws=workspace(tmp_path);spec=batch(tmp_path)
    def crash(name):
        if name==boundary:raise RuntimeError('injected process exit boundary')
    monkeypatch.setattr(ws.catalog,'_fault',crash)
    with pytest.raises(RuntimeError):ws.ingest(spec,request_id='lost-response')
    assert bool(ws.status()['facts'])==committed
    monkeypatch.setattr(ws.catalog,'_fault',lambda _:None);ws.recover()
    receipt=ws.ingest(spec,request_id='lost-response')
    assert ws.status()['facts']['prediction']==12
    assert receipt['catalog_sequence']==1


def test_cancel_and_quota_never_publish_partial_history(tmp_path):
    import threading
    from confidenceguard import WorkspaceConfig
    ws=workspace(tmp_path);spec=batch(tmp_path);cancel=threading.Event();cancel.set()
    with pytest.raises(EvaluationError):ws.ingest(spec,cancel=cancel)
    assert ws.status()['facts']=={};ws.recover()
    tiny=ReliabilityWorkspace.initialize(tmp_path/'tiny',WorkspaceConfig(saving=True,max_bytes=1024,free_disk_bytes=1))
    with pytest.raises(EvaluationError) as e:tiny.ingest(spec)
    assert e.value.code=='history_quota'


def test_assessment_deletion_preserves_catalog_listing_and_dependency_guard(tmp_path):
    from confidenceguard.contracts import digest
    ws=workspace(tmp_path);ws.ingest(batch(tmp_path));a=ws.analyze(longitudinal(ws));b=ws.analyze(longitudinal(ws))
    ws.delete(ws.deletion_preview(assessment_ids=[a.data['analysis_id']]))
    assert [v['id'] for v in ws.assessments()]==[b.data['analysis_id']]
    fact=next(ws.catalog.iter_facts('prediction'));plan=ws.deletion_preview(object_ids=[fact['object_id']])
    plan['object_ids']=[fact['object_id']];plan.pop('confirmation');plan['confirmation']=digest(plan)
    with pytest.raises(EvaluationError):ws.delete(plan)


def test_outcome_only_restatement_freezes_prediction_availability_cutoff(tmp_path):
    import csv
    from pathlib import Path
    ws=workspace(tmp_path);source=batch(tmp_path);path=Path(source['evaluation']['sources'][0]['path'])
    with path.open() as stream:rows=list(csv.DictReader(stream));fields=list(rows[0])+['ready']
    for i,row in enumerate(rows):row['ready']='2026-01-01T00:00:00Z' if i<6 else '2026-04-01T00:00:00Z'
    with path.open('w') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)
    source['bindings'][0]['available_at']={'column':'ready'};ws.ingest(source)
    old=ws.analyze(longitudinal(ws));new=ws.restate(old.data['analysis_id'],as_of='2026-05-01T00:00:00Z',reason='Label update cutoff')
    assert [v['selected_predictions'] for v in old.data['history']['window_coverage']]==[6,0]
    assert [v['selected_predictions'] for v in new.data['history']['window_coverage']]==[6,0]
    independent=ws.analyze(longitudinal(ws,as_of='2026-05-01T00:00:00Z'))
    assert [v['selected_predictions'] for v in independent.data['history']['window_coverage']]==[6,6]
