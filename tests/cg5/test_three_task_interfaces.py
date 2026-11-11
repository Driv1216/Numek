import json
from dataclasses import replace
import pytest
from click.testing import CliRunner
from datatrust.web import create_app
from confidenceguard import optimize_policies
from confidenceguard.cli import main
from validation.cg5.measure import fixture
from .test_interfaces_history import wait,BASE,CFG

@pytest.mark.parametrize('kind',['binary_classification','multiclass_classification','regression'])
def test_Python_CLI_API_selection_and_registered_assessment_agree(tmp_path,kind):
    spec=fixture(tmp_path/'data',kind,1200);python=optimize_policies(spec,CFG)
    key=python.data['policy']['nomination']['policy_digest'];expected=next(r['metrics'] for r in python.data['policy']['candidates'] if r['policy_digest']==key)
    spec_path=tmp_path/'study.json';config_path=tmp_path/'config.json';spec_path.write_text(json.dumps(spec.to_dict()));config_path.write_text(json.dumps(CFG))
    command=CliRunner().invoke(main,['policy','optimize','--spec',str(spec_path),'--config',str(config_path),'--audience','local'])
    assert command.exit_code==0,command.output
    cli=json.loads(command.output);assert cli['policy']['nomination']['policy_digest']==key
    assert next(r['metrics'] for r in cli['policy']['candidates'] if r['policy_digest']==key)==expected
    app=create_app(tmp_path/'host',data_roots=(tmp_path,));app.testing=True;client=app.test_client()
    try:
        headers={'X-CSRF-Token':client.get(BASE+'/session').json['data']['csrf_token']}
        source=client.post(BASE+'/sources',headers=headers,json={'root_id':'root_0','relative_path':'data/predictions.csv'}).json['data']
        value=spec.to_dict();value['input']['evaluation']['sources']=[{'id':'data','handle':source['handle']}]
        posted=client.post(BASE+'/policy-studies',headers=headers,json={'spec':value,'config':CFG});assert posted.status_code==201,posted.json
        draft=posted.json['data']
        def run(kind,**extra):
            posted=client.post(BASE+'/jobs',headers=headers,json={'kind':kind,'client_request_id':kind,'policy_study_id':draft['id'],'revision':1,**extra});assert posted.status_code==202,posted.json
            job=wait(client,posted.json['data']['id']);assert job['state']=='succeeded',job
            return job['output']
        inspection=run('policy_inspect');selected=run('policy_optimize',fingerprint=inspection['fingerprint']);rid=selected['result_id']
        rows=client.get(BASE+f'/results/{rid}/policy/candidates').json['data']['items'];assert next(r['metrics'] for r in rows if r['policy_digest']==key)==expected
        claims=[{'id':c.id,'policy_digest':key,'metric':c.metric.to_dict(),'operator':c.operator,'bound':c.bound,'minimum_support':c.minimum_support} for c in spec.constraints]
        objective=spec.objectives[0]
        claims.append({'id':'primary','policy_digest':key,'metric':objective.to_dict(),'operator':'le' if objective.direction=='minimize' else 'ge','bound':2 if kind=='regression' else .4})
        protocol={'claims':claims,'sampling':'independent_rows','upstream_independence':'declared_independent','external_exposure':'declared_unexposed','declaration_author':'fixture','declaration_reason':'Independent synthetic test evidence; E untouched before freezing.'}
        family=client.post(BASE+'/policy-families',headers=headers,json={'result_id':rid,'assessment':protocol});assert family.status_code==201,family.json
        handle=family.json['data']['handle'];admission=run('policy_assessment_inspect',family_handle=handle)
        assessed=run('policy_assess',family_handle=handle,assessment_fingerprint=admission['fingerprint'])
        claims=client.get(BASE+f"/results/{assessed['result_id']}/policy/assessments").json['data']['items']
        assert all(c['state']=='supported' for c in claims),claims
    finally:app.extensions['confidenceguard_store'].cleanup()
