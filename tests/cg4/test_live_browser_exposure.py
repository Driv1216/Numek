from dataclasses import replace
import json
import pytest
from datatrust.web import create_app
from confidenceguard import ReliabilityWorkspace,WorkspaceConfig,EvaluationConfig,investigate,freeze_hypotheses,inspect_confirmation
from confidenceguard.evidence_use import EvidenceUseLedger,source_aliases,source_scope_aliases
from confidenceguard.method_contracts import ReliabilitySpec,RoleSpec
from .helpers import binary
from .test_confirmation import declared
from .test_interfaces import wait,BASE
from tests.backend_support import evidence_uses


def attached(tmp_path,spec):
    ws=ReliabilityWorkspace.initialize(tmp_path/'workspace',WorkspaceConfig(saving=False,free_disk_bytes=1));ws.evidence_tracking(True)
    app=create_app(tmp_path/'host',data_roots=(tmp_path,),confidenceguard_workspace=ws.path,confidenceguard_launch_token='synthetic-launch')
    app.testing=True;client=app.test_client()
    client.get('/confidenceguard?launch=synthetic-launch')
    headers={'X-CSRF-Token':client.get(BASE+'/session').json['data']['csrf_token']}
    response=client.post(BASE+'/sources',headers=headers,json={'root_id':'root_0','relative_path':'predictions.csv'})
    assert response.status_code==201
    value=spec.to_dict();value['evaluation']['sources']=[{'id':'data','handle':response.json['data']['handle']}]
    return ws,app,client,headers,value


def test_live_CG4_tracks_without_retaining_results_and_detach_revokes_jobs(tmp_path):
    spec=binary(tmp_path);ws,app,client,headers,value=attached(tmp_path,spec)
    try:
        draft=client.post(BASE+'/investigations',headers=headers,json={'spec':value}).json['data']
        assert draft['workspace_instance']==ws.instance_id
        def job(kind,**fields):
            payload={'kind':kind,'client_request_id':kind,'investigation_id':draft['id'],'revision':1,'retain':False,**fields}
            response=client.post(BASE+'/jobs',headers=headers,json=payload);assert response.status_code==202,response.json
            done=wait(client,response.json['data']['id']);assert done['state']=='succeeded',done
            return done['output'],response.json['data']['id'],payload
        inspected,_,_=job('investigation_inspect')
        discovery,_,_=job('investigation_discover',fingerprint=inspected['fingerprint'])
        assert [u['kind'] for u in evidence_uses(ws)]==['discovery_selection']
        assert ws.assessments()==[] and discovery['retained'] is False
        response=client.post(BASE+'/hypothesis-sets',headers=headers,json={'result_id':discovery['result_id'],'confirmation':declared().to_dict()})
        assert response.status_code==201,response.json
        frozen=response.json['data']
        preview,_,_=job('confirmation_inspect',hypothesis_handle=frozen['handle'])
        assert preview['independence']['ledger_enabled'] is True
        assert not preview['admissibility_reasons']
        assessed,jid,payload=job('investigation_confirm',hypothesis_handle=frozen['handle'],confirmation_fingerprint=preview['fingerprint'])
        assert sorted(u['kind'] for u in evidence_uses(ws))==['confirmation','discovery_selection']
        assert ws.assessments()==[] and assessed['retained'] is False
        assert client.post(BASE+'/workspace/detach',headers=headers,json={}).status_code==200
        assert client.get(BASE+'/jobs/'+jid).status_code==403
        assert client.post(BASE+'/jobs',headers=headers,json=payload).status_code==403
        assert client.get(BASE+'/results/'+assessed['result_id']).status_code==403
    finally:app.extensions['confidenceguard_store'].cleanup()


def test_live_CG1_records_outcome_use_before_analysis_failure_without_feature_retention(tmp_path,monkeypatch):
    spec=binary(tmp_path);ws,app,client,headers,value=attached(tmp_path,spec)
    try:
        evaluation=client.post(BASE+'/evaluations',headers=headers,json={'spec':value['evaluation']}).json['data']
        payload={'kind':'inspect','evaluation_id':evaluation['id'],'revision':1,'client_request_id':'inspect'}
        inspected=client.post(BASE+'/jobs',headers=headers,json=payload);assert inspected.status_code==202
        done=wait(client,inspected.json['data']['id']);assert done['state']=='succeeded',done
        fingerprint=done['output']['fingerprint']
        from confidenceguard import EvaluationError
        def interrupted(*args,**kwargs):raise EvaluationError('Deliberate interruption after reservation.','fixture_interruption')
        monkeypatch.setattr('confidenceguard.transport.evaluate',interrupted)
        payload={'kind':'evaluate','evaluation_id':evaluation['id'],'revision':1,'client_request_id':'evaluate','fingerprint':fingerprint}
        submitted=client.post(BASE+'/jobs',headers=headers,json=payload);assert submitted.status_code==202
        jid=submitted.json['data']['id'];failed=wait(client,jid)
        assert failed['state']=='failed' and failed['error']['code']=='fixture_interruption'
        uses=evidence_uses(ws)
        assert len(uses)==1 and uses[0]['kind']=='outcome_disclosure'
        assert uses[0]['metadata']['purpose']=='live_browser_outcome_assessment'
        assert ws.assessments()==[]
        client.post(BASE+'/workspace/detach',headers=headers,json={})
        assert client.get(BASE+'/jobs/'+jid).status_code==403
        assert client.post(BASE+'/jobs',headers=headers,json=payload).status_code==403
    finally:app.extensions['confidenceguard_store'].cleanup()


def test_unkeyed_CG1_use_is_observable_to_later_keyed_CG4_without_contaminating_separate_keyed_roles(tmp_path):
    spec=binary(tmp_path);ws=ReliabilityWorkspace.initialize(tmp_path/'workspace',WorkspaceConfig(saving=False,free_disk_bytes=1));ws.evidence_tracking(True)
    config=EvaluationConfig();roots=(str(tmp_path),)
    unkeyed=replace(spec.evaluation,runs=(replace(spec.evaluation.runs[0],key_columns=()),),outcomes=replace(spec.evaluation.outcomes,key_columns=()))
    ws._reserve_live_exposure(unkeyed,config,roots,operation='evaluate',request_id='unkeyed')
    result=investigate(spec);family=freeze_hypotheses(result,confirmation=declared())
    preview=inspect_confirmation(family,workspace=ws)
    assert 'previously_exposed_confirmation_population' in preview['admissibility_reasons']


def test_keyed_CG2_fit_records_F_S_C_but_does_not_mark_unseen_E_from_shared_files(tmp_path):
    spec=binary(tmp_path);ws=ReliabilityWorkspace.initialize(tmp_path/'workspace',WorkspaceConfig(saving=False,free_disk_bytes=1));ws.evidence_tracking(True)
    reliability=ReliabilitySpec(spec.evaluation,RoleSpec(namespace='upstream',column='role',values={'D':'F','S':'C','H':'E'}))
    ws._reserve_live_exposure(reliability,EvaluationConfig(),(str(tmp_path),),operation='fit',request_id='fit')
    from confidenceguard import compat
    info=compat.capture(tmp_path/'predictions.csv',(str(tmp_path),))[0]
    d_event,d_unit=source_aliases(info,json.dumps(['0'],separators=(',',':')))
    h_event,h_unit=source_aliases(info,json.dumps(['2'],separators=(',',':')))
    ledger=EvidenceUseLedger(ws)
    assert ledger.overlap(d_event,d_unit)==['previously_exposed_confirmation_population']
    assert ledger.overlap(set(h_event)|source_scope_aliases(info),h_unit)==[]


def test_implicit_inline_outcomes_are_tracked_before_later_CG4_confirmation(tmp_path):
    spec=binary(tmp_path)
    inline=replace(spec.evaluation,outcomes=None,runs=(replace(spec.evaluation.runs[0],inline_outcome='y'),))
    ws=ReliabilityWorkspace.initialize(tmp_path/'workspace',WorkspaceConfig(saving=False,free_disk_bytes=1));ws.evidence_tracking(True)
    ws._reserve_live_exposure(inline,EvaluationConfig(),(str(tmp_path),),operation='evaluate',request_id='inline-outcome-use')
    uses=evidence_uses(ws)
    assert len(uses)==1 and uses[0]['kind']=='outcome_disclosure'
    result=investigate(replace(spec,evaluation=inline));family=freeze_hypotheses(result,confirmation=declared())
    assert 'previously_exposed_confirmation_population' in inspect_confirmation(family,workspace=ws)['admissibility_reasons']
