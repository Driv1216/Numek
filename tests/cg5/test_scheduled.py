from dataclasses import replace
from decimal import Decimal
import pytest
from confidenceguard import (PolicyInputSpec,PolicySpec,PolicyStudySpec,PolicyMetricSpec,PolicyAssessmentSpec,PolicyClaim,ConfirmationLook,EvaluationError)
from confidenceguard.method_contracts import RoleSpec
from tests.cg4.test_history import retained
CFG={'free_disk_bytes':1}

def test_policy_scheduled_look_preserves_family_and_spends_frozen_allocation(tmp_path):
    ws,old=retained(tmp_path);ws.evidence_tracking(True)
    inp=PolicyInputSpec(RoleSpec(old.roles.namespace,proportions={'S':.5,'E':.5},unit='entity'),history=old.history)
    variant=old.objectives[0].run;task=old.history and old.objectives
    from confidenceguard.history_storage import Catalog
    meta=ws.models()[0]
    from confidenceguard.contracts import TaskDefinition
    task=TaskDefinition('binary_classification','fixture',('0','1'),'1')
    policy=PolicySpec(task,variant,{'root':{'kind':'action','action':{'kind':'supplied'}}},'root',{'kind':'abstain'},{'kind':'unavailable'})
    metric=PolicyMetricSpec('accuracy','issued_accuracy','maximize')
    selected=ws.optimize_policies(PolicyStudySpec(inp,(metric,),candidates=(policy,)),CFG,request_id='selection')
    key=selected.data['policy']['nomination']['policy_digest']
    protocol=PolicyAssessmentSpec((PolicyClaim('requirement',key,metric,'ge',.1),),sampling='independent_rows',study_id='cg5-scheduled-study',batch_alpha='0.025',
       restatement_schedule=(ConfirmationLook('april','2026-04-01T00:00:00Z',.025),),upstream_independence='declared_independent',external_exposure='declared_unexposed',declaration_author='fixture',declaration_reason='Synthetic isolated event population')
    frozen=ws.freeze_policy_family(selected,assessment=protocol)
    first=ws.assess_policies(frozen,CFG,request_id='initial')
    assert first.data['policy']['assessments'][0]['state']=='supported'
    inspection=ws.inspect_policy_restatement(first.data['analysis_id'],'april',CFG)
    assert not inspection['assessment_values_disclosed'] and not inspection['admissibility_reasons']
    from datatrust.web import create_app
    from .test_interfaces_history import wait,BASE
    app=create_app(tmp_path/'host',data_roots=(tmp_path,),confidenceguard_workspace=ws.path,confidenceguard_launch_token='synthetic-look')
    app.testing=True;client=app.test_client()
    try:
        client.get('/confidenceguard?launch=synthetic-look')
        headers={'X-CSRF-Token':client.get(BASE+'/session').json['data']['csrf_token']}
        aid=first.data['analysis_id'];opened=client.post(BASE+'/workspace/policies/'+aid+'/open',headers=headers,json={});assert opened.status_code==200
        def submit(kind,**options):
            response=client.post(BASE+'/jobs',headers=headers,json={'kind':kind,'client_request_id':kind,'result_id':aid,'look_id':'april',**options});assert response.status_code==202,response.json
            completed=wait(client,response.json['data']['id']);assert completed['state']=='succeeded',completed
            return completed['output']
        admission=submit('policy_inspect_look');assert admission['fingerprint']==inspection['fingerprint']
        output=submit('policy_assess_look',assessment_fingerprint=admission['fingerprint'])
        second=ws.open(output['result_id'])
    finally:app.extensions['confidenceguard_store'].cleanup()
    assert second.data['policy']['assessment_family_digest']==frozen.family_digest
    assert second.data['policy']['predeclared_restatement']['fresh_independent_evidence'] is False
    uses=[f['payload'] for f in ws.catalog.iter_facts('evidence_use') if f['payload']['kind']=='confirmation']
    assert len(uses)==2 and sum(Decimal(str(u['alpha'])) for u in uses)==Decimal('.05')
    with pytest.raises(EvaluationError):ws.inspect_policy_restatement(first.data['analysis_id'],'not-planned',CFG)
    ws.evidence_tracking(False);ws.evidence_tracking(True)
    with pytest.raises(EvaluationError):ws.inspect_policy_restatement(first.data['analysis_id'],'april',CFG)
