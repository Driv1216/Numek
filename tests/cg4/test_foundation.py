import json
from decimal import Decimal
import numpy as np
import pytest
from confidenceguard import EvaluationError, ReliabilityWorkspace, WorkspaceConfig
from confidenceguard.contracts import digest
from confidenceguard.feature_contracts import FeatureField
from confidenceguard.features import normalize,value,apply_availability
from confidenceguard.feature_storage import validate_matrix,read_features
from confidenceguard.history_storage import EvidenceWriter


def envelope(i,cell,**payload):
    identity=['features','v1',str(i)]
    row={'kind':'feature','key':digest(identity),'identity':identity,'revision':'initial','predecessor':None,
         'available_ns':'100','authority':'fixture','reason':None,'payload':{'values':{'x':cell},**payload}}
    return {**row,'fact_digest':digest(row)}


def test_lossless_typed_cells_and_distinct_states():
    integer=normalize('9007199254740993',FeatureField('x','x','integer'))
    assert value(integer)==9007199254740993
    lexical='123456789012345678901234567890.12345678901234567890'
    assert value(normalize(lexical,FeatureField('x','x','decimal')))==Decimal(lexical)
    assert len({normalize(s,FeatureField('x','x'))['canonical'] for s in ('1','1.0','01',' 1')})==4
    assert normalize('NaN',FeatureField('x','x','float'))['state']=='invalid'
    assert normalize('',FeatureField('x','x','integer'))['state']=='missing'
    dated=normalize('1',FeatureField('x','x','integer'),available_ns=20,availability_state='valid')
    assert apply_availability(dated,view='available_at_decision',cutoff_ns=10)['state']=='unavailable'
    assert apply_availability(dated,view='retrospective',as_of_ns=30)['state']=='observed'


@pytest.mark.workspace_backup
def test_mixed_codec_commit_reconstruct_backup_and_delete(tmp_path):
    ws=ReliabilityWorkspace.initialize(tmp_path/'workspace',WorkspaceConfig(saving=True,free_disk_bytes=1))
    assert ws.catalog.catalog_version==2
    with ws.catalog.operation():
        operation,_=ws.catalog.begin('typed','same')
        writer=EvidenceWriter(ws.path/'staging'/operation,ws.catalog.config,operation)
        vectors=np.array([[1.,2.],[3.,4.]],dtype='<f4');locations=writer.add_vectors(vectors)
        rows=[envelope(i,normalize(str(i),FeatureField('x','x','integer')),vector_digest=loc['vector_digest']) for i,loc in enumerate(locations)]
        writer.add_features(rows,('x',));writer.finish({'capture_stages':['typed']})
        receipt=ws.catalog.commit_capture(operation)
    retained=list(ws.catalog.iter_facts('feature'))
    assert len(retained)==2 and [value(r['payload']['values']['x']) for r in retained]==[0,1]
    assert {r['fact_digest'] for r in retained}=={r['fact_digest'] for r in rows}
    from tests.backend_support import stored_evidence
    before=stored_evidence(ws)
    ws.backup(tmp_path/'backup')
    restored=ReliabilityWorkspace.restore(tmp_path/'backup',tmp_path/'restored')
    assert restored.instance_id!=ws.instance_id
    assert restored.status()['exposure_continuity']=='restore_unreconciled'
    assert stored_evidence(restored)==before
    assert len(list(restored.catalog.iter_facts('feature')))==2
    ws.delete(ws.deletion_preview(object_ids=[retained[0]['object_id']]))
    assert stored_evidence(ws)=={}
    assert ws.status()['exposure_continuity']=='incomplete'
    with pytest.raises(EvaluationError):list(ws.catalog.iter_facts('feature'))


def test_nonobject_matrix_admission(tmp_path):
    path=tmp_path/'matrix.npy';np.save(path,np.ones((4,3),dtype=np.float64))
    assert validate_matrix(path)['dimensions']==3
    with pytest.raises(EvaluationError):validate_matrix(path,max_dimensions=2)
    np.save(path,np.array([['a']],dtype=object))
    with pytest.raises(EvaluationError):validate_matrix(path)
    np.save(path,np.ones((4,3),dtype=np.float64));path.write_bytes(path.read_bytes()+b'extra')
    with pytest.raises(EvaluationError):validate_matrix(path)
