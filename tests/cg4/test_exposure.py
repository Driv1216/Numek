import csv
from contextlib import closing
from dataclasses import replace
import json
import numpy as np
import pytest
from confidenceguard import ReliabilityWorkspace,WorkspaceConfig,EvaluationError
from confidenceguard.contracts import digest
from confidenceguard.evidence_use import EvidenceUseLedger
from confidenceguard.representations import subset
from .helpers import binary
from .test_history import retained


def test_historical_identity_scope_does_not_treat_absent_aliases_as_verified():
    from types import SimpleNamespace
    from confidenceguard.evidence_use import local_identity_scope
    p=SimpleNamespace(history={'selection':'synthetic'},records=[{'event_key':'a'},{'event_key':'b'}],
        store=SimpleNamespace(cg4_source_identities={'a':[({'path':'original'},'a',None)]}))
    assert local_identity_scope(p,[0,1])=='canonical_history_keys_original_aliases_incomplete'
    assert local_identity_scope(p,[0])=='canonical_history_keys_and_retained_original_aliases'
    p.store.cg4_source_identities['b']=[]
    assert local_identity_scope(p,[1])=='canonical_history_keys_original_aliases_incomplete'
    p.history=None
    assert local_identity_scope(p,[0,1])=='live_source_keys_and_available_local_aliases'


def test_representation_subset_preserves_unavailable_reasons_and_duplicates():
    original={'vectors':np.arange(12,dtype=float).reshape(4,3),'available':np.array([True,False,True,False]),
              'reason':['','missing','','outside'],'coverage':[{'i':i} for i in range(4)]}
    selected=subset(original,np.array([3,0,3]))
    assert selected['reason']==['outside','','outside']
    assert selected['coverage']==[{'i':3},{'i':0},{'i':3}]
    assert selected['available'].tolist()==[False,True,False]


def test_evaluation_exposure_is_durable_even_if_analysis_fails(tmp_path,monkeypatch):
    spec=binary(tmp_path)
    ws=ReliabilityWorkspace.initialize(tmp_path/'workspace',WorkspaceConfig(saving=True,free_disk_bytes=1))
    ws.evidence_tracking(True)
    batch={'evaluation':spec.evaluation.to_dict(),'namespace':spec.roles.namespace,'outcome_definition_version':'v1',
           'bindings':[{'run':'model'}],'operation':'evaluate'}
    def fail(*args,**kwargs):raise EvaluationError('Deliberate interruption after reservation.','fixture_interruption')
    monkeypatch.setattr('confidenceguard.engine.evaluate',fail)
    with pytest.raises(EvaluationError,match='Deliberate'):ws.ingest(batch,request_id='evaluation')
    assert list(ws.catalog.iter_facts('evidence_use'))[0]['payload']['kind']=='outcome_disclosure'
    event=digest([spec.roles.namespace,json.dumps(['0'],separators=(',',':'))])
    assert EvidenceUseLedger(ws).overlap([event],[])==['previously_exposed_confirmation_population']
    assert ws.evidence_tracking()['continuity']=='unknown'


def test_vector_bytes_bind_capture_retry_identity(tmp_path):
    spec=binary(tmp_path);path=tmp_path/'vectors.npy'
    np.save(path,np.ones((720,2),dtype='<f4'))
    ws=ReliabilityWorkspace.initialize(tmp_path/'workspace',WorkspaceConfig(saving=True,free_disk_bytes=1))
    batch={'evaluation':spec.evaluation.to_dict(),'namespace':spec.roles.namespace,'outcome_definition_version':'v1','bindings':[{'run':'model'}],
           'schema_version':'confidenceguard.prediction_batch_spec/2.0','discovery_representations':[{'id':'vec','matrix_path':str(path),
            'keys_source':spec.evaluation.sources[0].to_dict(),'key_columns':['id'],'dimensions':2,'availability':'at_decision'}]}
    first=ws.ingest(batch,request_id='vectors');assert ws.ingest(batch,request_id='vectors')==first
    np.save(path,np.zeros((720,2),dtype='<f4'))
    with pytest.raises(EvaluationError) as caught:ws.ingest(batch,request_id='vectors')
    assert caught.value.code=='idempotency_conflict'


def test_historical_preview_is_recorded_as_exposure(tmp_path):
    ws,spec=retained(tmp_path);ws.evidence_tracking(True)
    selection=spec.history['selection'];ws.inspect(selection)
    uses=list(ws.catalog.iter_facts('evidence_use'))
    assert uses[-1]['payload']['metadata']['purpose']=='historical_population_preview'
    assert uses[-1]['payload']['event_count']>=720


def test_ledger_checks_all_membership_chunks_even_after_index_loss(tmp_path):
    ws=ReliabilityWorkspace.initialize(tmp_path/'workspace',WorkspaceConfig(saving=True,free_disk_bytes=1));ws.evidence_tracking(True)
    ledger=EvidenceUseLedger(ws);events=[digest(['event',i]) for i in range(1100)];units=[digest(['unit',i]) for i in range(17)]
    ledger.record('outcome_disclosure',events=events,units=units,population_digest=digest('population'))
    assert ledger.overlap([events[0]],[])==['previously_exposed_confirmation_population']
    assert ledger.overlap([digest('unrelated')],[])==[]
    missing=list(ws.catalog.iter_facts('exposure_members',_logical_order=True))[1]
    # Simulate partial index loss, rather than a physical checksum failure.
    with closing(ws.catalog._connect()) as db:
        fid=db.execute('SELECT id FROM facts WHERE kind=? AND key=?',('exposure_members',missing['key'])).fetchone()[0]
        db.execute('DELETE FROM occurrences WHERE fact_id=?',(fid,));db.execute('DELETE FROM facts WHERE id=?',(fid,));db.commit()
    assert 'exposure_history_incomplete' in ledger.overlap([digest('unrelated')],[])


def test_source_instance_aliases_survive_namespace_rename_and_outcome_revision(tmp_path):
    from confidenceguard import investigate,freeze_hypotheses,ConfirmationSpec,inspect_confirmation
    from confidenceguard.investigation import _discovery_population,arguments
    spec=binary(tmp_path);ws=ReliabilityWorkspace.initialize(tmp_path/'workspace',WorkspaceConfig(saving=True,free_disk_bytes=1));ws.evidence_tracking(True)
    result=ws.investigate(spec);protocol=ConfirmationSpec(upstream_independence='declared_independent',external_exposure='declared_unexposed',declaration_author='fixture',declaration_reason='Synthetic independent units, isolated source.')
    frozen=freeze_hypotheses(result,confirmation=protocol);initial=inspect_confirmation(frozen,workspace=ws,_protected=True)
    EvidenceUseLedger(ws).record('outcome_disclosure',**initial['_protected_population'])
    renamed=replace(spec,roles=replace(spec.roles,namespace=spec.roles.namespace+'-renamed'))
    path=tmp_path/'predictions.csv';moved=tmp_path/'renamed.csv';path.rename(moved)
    evaluation=replace(renamed.evaluation,sources=(replace(renamed.evaluation.sources[0],path=str(moved)),))
    renamed=replace(renamed,evaluation=evaluation)
    with moved.open() as stream:values=list(csv.DictReader(stream))
    for row in values:
        if row['role']=='H':row['y']=str(1-int(row['y']))
    with moved.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=values[0]);writer.writeheader();writer.writerows(values)
    second=ws.investigate(renamed);family=freeze_hypotheses(second,confirmation=protocol)
    inspected=inspect_confirmation(family,workspace=ws)
    assert 'previously_exposed_confirmation_population' in inspected['admissibility_reasons']


def test_repartitioning_cannot_reclassify_observed_source_rows_as_H(tmp_path):
    from confidenceguard import investigate,freeze_hypotheses,ConfirmationSpec,inspect_confirmation
    spec=binary(tmp_path);result=investigate(spec)
    frozen=freeze_hypotheses(result,confirmation=ConfirmationSpec(upstream_independence='declared_independent',external_exposure='declared_unexposed',declaration_author='fixture',declaration_reason='Synthetic independent rows.'))
    # Repartitioning an explicit future input is permitted to be inspected, but
    # it cannot turn the source's original D rows into independent evidence.
    values=spec.to_dict();values['roles']['values']={'D':'H','S':'S','H':'D'}
    from confidenceguard import InvestigationSpec
    altered=InvestigationSpec.from_dict(values)
    inspected=inspect_confirmation(frozen,confirmation_input=altered)
    assert 'observable_D_S_H_overlap' in inspected['admissibility_reasons']
