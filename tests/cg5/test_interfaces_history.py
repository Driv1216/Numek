import copy,json,time,csv
from dataclasses import replace
from click.testing import CliRunner
from datatrust.web import create_app
from confidenceguard.cli import main
from confidenceguard import schema,ReliabilityWorkspace,WorkspaceConfig
from confidenceguard.policies import optimize_policies
from confidenceguard.policy_contracts import PolicyInputSpec,PolicyApplicationSpec,PolicyMetricSpec,PolicySpec
from confidenceguard.policy_history import analyze_policy_history
from confidenceguard.method_contracts import RoleSpec
from .helpers import study,threshold,evidence
BASE='/api/confidenceguard/v1'
CFG={'free_disk_bytes':1}
def wait(client,jid):
    for _ in range(600):
        job=client.get(BASE+'/jobs/'+jid).json['data']
        if job['state'] not in {'pending','running','cancelling'}: return job
        time.sleep(.05)
    raise AssertionError('Policy job timeout')

def test_contracts_cli_reports_and_privacy(tmp_path):
    defs=schema.schemas();s=study(tmp_path)
    import subprocess
    subprocess.run(['python3','-c',"import jsonschema,json,sys; v=json.load(sys.stdin);jsonschema.Draft202012Validator.check_schema(v['schema']);jsonschema.validate(v['spec'],v['schema'])"],input=json.dumps({'spec':s.to_dict(),'schema':{**defs,'$ref':'#/$defs/PolicyStudySpec'}}),text=True,check=True)
    assert 'policy_assess' in schema.capabilities()['job_kinds']
    assert '/policy-families' in schema.openapi()['paths']
    assert CliRunner().invoke(main,['policy','--help']).exit_code==0
    result=optimize_policies(s,CFG)
    public=result.generate_artifacts(tmp_path/'public.html',json_path=tmp_path/'public.json')
    assert public.private_manifest_path is None
    raw=(tmp_path/'public.html').read_text()+(tmp_path/'public.json').read_text()
    assert str(tmp_path) not in raw and 'decision_costs' not in raw and 'nodes' not in raw
    local=result.generate_artifacts(tmp_path/'private.html',audience='local')
    assert local.private_manifest_path
    refs=result.private['locators']
    if refs: assert result.resolve_evidence(next(iter(refs)),allowed_roots=[tmp_path])['status']=='resolved'

def test_owned_api_select_freeze_assess(tmp_path):
    spec=study(tmp_path).to_dict();app=create_app(tmp_path/'host',data_roots=(tmp_path,));app.testing=True;client=app.test_client()
    try:
        headers={'X-CSRF-Token':client.get(BASE+'/session').json['data']['csrf_token']}
        source=client.post(BASE+'/sources',headers=headers,json={'root_id':'root_0','relative_path':'predictions.csv'}).json['data']
        spec['input']['evaluation']['sources']=[{'id':'data','handle':source['handle']}]
        assert client.post(BASE+'/policy-studies',json={'spec':spec}).status_code==403
        response=client.post(BASE+'/policy-studies',headers=headers,json={'spec':spec,'config':CFG});assert response.status_code==201,response.json
        draft=response.json['data']
        def run(kind,**more):
            request={'kind':kind,'client_request_id':kind,'policy_study_id':draft['id'],'revision':1,**more}
            posted=client.post(BASE+'/jobs',headers=headers,json=request);assert posted.status_code==202,posted.json
            result=wait(client,posted.json['data']['id']);assert result['state']=='succeeded',result
            return result['output']
        inspection=run('policy_inspect');selected=run('policy_optimize',fingerprint=inspection['fingerprint']);rid=selected['result_id']
        panel=client.get(BASE+f'/results/{rid}/policy/summary').json['data']['policy'];key=panel['nomination']['policy_digest']
        protocol={'claims':[{'id':'accuracy','policy_digest':key,'metric':{'id':'accuracy','metric':'issued_accuracy','direction':'maximize'},'operator':'ge','bound':.5}],
                  'sampling':'independent_rows','upstream_independence':'declared_independent','external_exposure':'declared_unexposed','declaration_author':'fixture','declaration_reason':'Untouched synthetic E'}
        frozen=client.post(BASE+'/policy-families',headers=headers,json={'result_id':rid,'assessment':protocol});assert frozen.status_code==201,frozen.json
        handle=frozen.json['data']['handle'];admission=run('policy_assessment_inspect',family_handle=handle)
        assessed=run('policy_assess',family_handle=handle,assessment_fingerprint=admission['fingerprint'])
        assert client.get(BASE+f"/results/{assessed['result_id']}/policy/assessments").json['data']['items'][0]['state']=='supported'
        assert app.test_client().get(BASE+f'/policy-studies/{draft["id"]}').status_code==404
    finally: app.extensions['confidenceguard_store'].cleanup()

def test_history_persistence_restatement(tmp_path):
    inp=evidence(tmp_path);evaluation=inp.evaluation.to_dict();path=tmp_path/'predictions.csv'
    with path.open() as f: records=list(csv.DictReader(f))
    for i,row in enumerate(records): row.update(when='2026-01-01T00:00:00Z' if i<40 else '2026-02-01T00:00:00Z',available='2026-02-03T00:00:00Z')
    with path.open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)
    evaluation['runs'][0]['prediction_at']={'column':'when'};evaluation['outcomes']['available_at']={'column':'available'}
    ws=ReliabilityWorkspace.initialize(tmp_path/'ws',WorkspaceConfig(saving=True,free_disk_bytes=1))
    ws.ingest({'namespace':inp.roles.namespace,'outcome_definition_version':'v1','evaluation':evaluation,'bindings':[{'run':'model'}]})
    variant=ws.models()[0]['id'];selection={'namespace':inp.roles.namespace,'variants':[variant],'as_of':'2026-03-01T00:00:00Z','windows':[{'id':'jan','start':'2026-01-01T00:00:00Z','end':'2026-02-01T00:00:00Z'},{'id':'feb','start':'2026-02-01T00:00:00Z','end':'2026-03-01T00:00:00Z'}]}
    retained=PolicyInputSpec(RoleSpec(inp.roles.namespace,proportions={'E':1}),history={'workspace_path':str(ws.path),'selection':selection})
    app=PolicyApplicationSpec(retained,replace(threshold(inp.evaluation.task,.6),run=variant),metrics=(PolicyMetricSpec('accuracy','issued_accuracy','maximize'),))
    result=analyze_policy_history(app,CFG);assert len(result.data['policy']['timeline'])==2
    ws.save_assessment(result);assert ws.open(result.data['analysis_id']).to_private_dict()==result.to_private_dict()
    restated=ws.restate_policy_history(result.data['analysis_id'],as_of='2026-04-01T00:00:00Z',reason='Later outcome authority',config=CFG)
    assert next(iter(result.private['policies']))==next(iter(restated.private['policies']))


def test_policy_family_packet_backup_and_dependency_deletion(tmp_path):
    from confidenceguard.policy_assessment import freeze_policy_family
    from .test_assessment import protocol
    ws=ReliabilityWorkspace.initialize(tmp_path/'workspace',WorkspaceConfig(saving=True,free_disk_bytes=1))
    selected=ws.optimize_policies(study(tmp_path),CFG,request_id='select')
    frozen=ws.freeze_policy_family(selected,assessment=protocol(selected))
    assert ws.open_policy_family(frozen.data['content_digest']).to_dict()==frozen.to_dict()
    assessed=ws.assess_policies(frozen,CFG,request_id='assess');before=assessed.to_private_dict()
    ws.backup(tmp_path/'backup');restored=ReliabilityWorkspace.restore(tmp_path/'backup',tmp_path/'restored')
    assert restored.open(assessed.data['analysis_id']).to_private_dict()==before
    family_fact=next(restored.catalog.iter_facts('policy_family'))
    plan=restored.deletion_preview(object_ids=[family_fact['object_id']])
    assert assessed.data['analysis_id'] in plan['potentially_impacted_assessments']
    restored.delete(plan)
    import pytest
    with pytest.raises(Exception): restored.open(assessed.data['analysis_id'])
