import uuid
import pytest
from confidenceguard import ReliabilityWorkspace,WorkspaceConfig,EvaluationError
from confidenceguard.history_storage import EvidenceWriter
from confidenceguard.investigation_storage import write_packet,read_packet
from confidenceguard.contracts import digest
from .test_history import retained
from .helpers import binary


def test_deleting_historical_features_transitively_deletes_private_CG4_copies(tmp_path):
    ws,spec=retained(tmp_path);result=ws.investigate(spec);frozen=ws.freeze_hypotheses(result)
    annotated=ws.annotate_investigation(result.data['analysis_id'],'Protected note referencing the retained region.')
    source=next(ws.catalog.iter_facts('feature'))['object_id']
    preview=ws.deletion_preview(object_ids=[source])
    derived=(ws.catalog.object_ids_for_key('assessment',digest([result.data['analysis_id']]))|ws.catalog.object_ids_for_key('assessment',digest([annotated.data['analysis_id']]))
             |{f['object_id'] for f in ws.catalog.iter_facts('hypothesis_set',require_complete=False)})
    assert len(derived)>=3
    assert derived<=set(preview['object_ids'])
    ws.delete(preview)
    for aid in (result.data['analysis_id'],annotated.data['analysis_id']):
        with pytest.raises(EvaluationError):ws.open(aid)
    with pytest.raises(EvaluationError):ws.open_hypotheses(frozen.data['content_digest'])


def test_standalone_byte_identical_retained_source_has_deletion_dependency(tmp_path):
    ws,history=retained(tmp_path)
    # Reuse the retained file directly through the standalone product API.
    from dataclasses import replace
    separate=tmp_path/'separate';separate.mkdir();base=binary(separate)
    evaluation=base.evaluation.to_dict();evaluation['sources'][0]['path']=str(tmp_path/'predictions.csv')
    spec=replace(base,evaluation=type(base.evaluation).from_dict(evaluation))
    result=ws.investigate(spec)
    source=next(ws.catalog.iter_facts('feature'))['object_id']
    preview=ws.deletion_preview(object_ids=[source])
    (oid,)=ws.catalog.object_ids_for_key('assessment',digest([result.data['analysis_id']]))
    assert oid in preview['object_ids']
    ws.delete(preview)
    with pytest.raises(EvaluationError):ws.open(result.data['analysis_id'])


def test_capture_metadata_used_for_origin_checks_is_a_retained_dependency(tmp_path):
    ws,spec=retained(tmp_path)
    metadata=next(ws.catalog.iter_facts('capture_metadata'))['payload']
    with ws.catalog.operation():
        operation,_=ws.catalog.begin('metadata-only-origin',digest(metadata))
        writer=EvidenceWriter(ws.path/'staging'/operation,ws.catalog.config,operation)
        writer.finish(metadata);ws.catalog.commit_capture(operation)
    origin=next(f for f in ws.catalog.iter_facts('capture_metadata') if f['identity']==[operation])
    result=ws.investigate(spec)
    assert origin['object_id'] in result.private['history_binding']['source_objects']
    (assessment_object,)=ws.catalog.object_ids_for_key('assessment',digest([result.data['analysis_id']]))
    preview=ws.deletion_preview(object_ids=[origin['object_id']])
    assert assessment_object in preview['object_ids']


@pytest.mark.workspace_backup
def test_large_sealed_packet_roundtrip_backup_and_complete_deletion(tmp_path):
    ws=ReliabilityWorkspace.initialize(tmp_path/'workspace',WorkspaceConfig(saving=True,free_disk_bytes=1,max_record_bytes=8192))
    aid=uuid.uuid4().hex;payload={'result':{'analysis_id':aid,'schema_version':'confidenceguard.investigation_result/1.0','methodology_id':'failure_investigation_v1','name':'Synthetic packet','generated_at':'2026-01-01T00:00:00Z'},'manifest':{'large_protected_value':'X'*60000}}
    with ws.catalog.operation():
        operation,_=ws.catalog.begin('large-packet',digest(payload));writer=EvidenceWriter(ws.path/'staging'/operation,ws.catalog.config,operation)
        write_packet(writer,'assessment',[aid],payload);writer.finish({'assessment_id':aid});ws.catalog.commit_capture(operation)
    fact=next(ws.catalog.iter_facts('assessment'));assert fact['payload']['cg4_packet']['bytes']>8192
    assert read_packet(ws.catalog,fact)==payload
    ws.backup(tmp_path/'backup');restored=ReliabilityWorkspace.restore(tmp_path/'backup',tmp_path/'restored')
    assert read_packet(restored.catalog,next(restored.catalog.iter_facts('assessment')))==payload
    parts={f['object_id'] for f in ws.catalog.iter_facts('cg4_packet_part')};preview=ws.deletion_preview(assessment_ids=[aid])
    assert parts<=set(preview['object_ids'])
    ws.delete(preview)
    from tests.backend_support import object_retained
    assert not any(object_retained(ws,oid) for oid in parts)
    with pytest.raises(EvaluationError):read_packet(ws.catalog,fact)
