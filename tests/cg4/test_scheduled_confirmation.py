from dataclasses import replace
from decimal import Decimal
import pytest
from confidenceguard import ConfirmationSpec,ConfirmationLook,EvaluationError,freeze_hypotheses
from .test_history import retained


def protocol():
    return ConfirmationSpec(study_id='scheduled-synthetic-study',batch_alpha=.025,
        restatement_schedule=(ConfirmationLook('april','2026-04-01T00:00:00Z',.025),),
        upstream_independence='declared_independent',external_exposure='declared_unexposed',declaration_author='fixture',
        declaration_reason='Independent synthetic entities, locally protected study, no external study branches or earlier exposure.')


def test_scheduled_look_is_frozen_before_H_and_spends_its_own_allocation(tmp_path):
    ws,spec=retained(tmp_path);ws.evidence_tracking(True)
    discovery=ws.investigate(spec);frozen=ws.freeze_hypotheses(discovery,confirmation=protocol())
    first=ws.confirm_investigation(frozen);assert any(a.get('H_outcomes_disclosed') for a in first.data['investigation']['assessments'])
    inspection=ws.inspect_restatement_confirmation(first.data['analysis_id'],'april')
    assert inspection['confirmation_look']['id']=='april' and not inspection['H_outcomes_disclosed']
    assert not inspection['admissibility_reasons']
    second=ws.restate_confirmation(first.data['analysis_id'],'april',request_id='scheduled-april')
    assert second.data['investigation']['family_digest']==first.data['investigation']['family_digest']
    assert second.data['investigation']['predeclared_restatement']['fresh_independent_evidence'] is False
    uses=[f['payload'] for f in ws.catalog.iter_facts('evidence_use') if f['payload']['kind']=='confirmation']
    assert len(uses)==2 and sum(Decimal(str(u['alpha'])) for u in uses)==Decimal('.05')
    assert second.private['memberships']==first.private['memberships']
    assert ws.restate_confirmation(first.data['analysis_id'],'april',request_id='scheduled-april').to_private_dict()==second.to_private_dict()
    with pytest.raises(EvaluationError) as caught:ws.restate_confirmation(first.data['analysis_id'],'unplanned')
    assert caught.value.code=='unplanned_confirmation_look'
    updates=tmp_path/'late-correction.csv'
    updates.write_text('id,y,revision,order,available,status\n'+''.join(f'{i},{1-(i//12)%2},late,1,2026-03-01T00:00:00Z,final\n' for i in range(720)))
    ws.update_outcomes({'source':{'id':'outcomes','path':str(updates)},'namespace':spec.roles.namespace,'outcome_definition_version':'v1','event_columns':['id'],'column':'y','revision_column':'revision','order_column':'order','available_at':{'column':'available'},'status_column':'status'})
    with pytest.raises(EvaluationError) as caught:ws.restate_confirmation(first.data['analysis_id'],'april')
    assert caught.value.code=='scheduled_look_already_assessed'
    ws.evidence_tracking(False);ws.evidence_tracking(True)
    with pytest.raises(EvaluationError) as caught:ws.inspect_restatement_confirmation(first.data['analysis_id'],'april')
    assert caught.value.code=='scheduled_restatement_provenance'


def test_schedule_allocations_cannot_be_added_after_discovery_or_overspent():
    with pytest.raises(EvaluationError,match='exceed'):replace(protocol(),batch_alpha=.05)
    with pytest.raises(EvaluationError,match='study identity'):replace(protocol(),study_id=None)
