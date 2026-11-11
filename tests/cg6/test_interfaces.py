import json
import time
from click.testing import CliRunner
from datatrust.web import create_app
from confidenceguard.cli import main
from .helpers import execution,CFG

BASE='/api/confidenceguard/v1'


def wait(client,jid):
    until=time.monotonic()+120
    while time.monotonic()<until:
        j=client.get(BASE+'/jobs/'+jid).json['data']
        if j['state'] not in {'pending','running','cancelling'}:return j
        time.sleep(.05)
    raise AssertionError('CG6 fixed job exceeded test deadline')


def test_owned_execution_auxiliary_and_bridge_api(tmp_path):
    s=execution(tmp_path,regression=True).to_dict();app=create_app(tmp_path/'host',data_roots=(tmp_path,));app.testing=True;client=app.test_client()
    try:
        headers={'X-CSRF-Token':client.get(BASE+'/session').json['data']['csrf_token']}
        source=client.post(BASE+'/sources',headers=headers,json={'root_id':'root_0','relative_path':'inputs.csv'}).json['data']
        s['sources']=[{'id':'input','handle':source['handle']}]
        def draft(workflow,spec):
            response=client.post(BASE+'/execution/drafts',headers=headers,json={'workflow':workflow,'spec':spec,'config':CFG})
            assert response.status_code==201,response.json
            return response.json['data']
        d=draft('execution',s)
        assert app.test_client().get(BASE+'/execution/drafts/'+d['id']).status_code==404
        assert client.post(BASE+'/execution/drafts',json={'workflow':'execution','spec':s}).status_code==403
        def run(d,kind,fingerprint=None):
            payload={'kind':kind,'client_request_id':kind+'-'+d['id'],'draft_id':d['id'],'revision':1}
            if fingerprint:payload['fingerprint']=fingerprint
            response=client.post(BASE+'/jobs',headers=headers,json=payload);assert response.status_code==202,response.json
            r=wait(client,response.json['data']['id']);assert r['state']=='succeeded',r
            return r['output']
        inspected=run(d,'cg6_inspect');executed=run(d,'cg6_execute',inspected['fingerprint']);rid=executed['result_id']
        page=client.get(BASE+f'/results/{rid}/execution/outputs?cursor=50&limit=5').json['data']
        assert page['total']==60 and len(page['items'])==5 and page['next_cursor']=='55'
        restatement=draft('restatement',{'result_id':rid,'spec':{'sources':[{'id':'later','handle':source['handle']}],
            'outcomes':{'source':'later','column':'y','key_columns':['id']},'reason':'Owned outcome restatement'}})
        inspected=run(restatement,'cg6_inspect');revised=run(restatement,'cg6_restate',inspected['fingerprint'])
        summary=client.get(BASE+f"/results/{revised['result_id']}/execution/summary").json['data']
        assert summary['cg6']['execution_repeated'] is False
        bridged=client.post(BASE+f'/results/{rid}/execution/bridge',headers=headers,json={})
        assert bridged.status_code==201,bridged.json
        assert 'handle' in bridged.json['data']['spec']['evaluation']['sources'][0]
        aux=draft('auxiliary',{'execution':s,'kind':'scale','base_predictor':'model','inputs':[{'id':'z','column':'z','kind':'float','role':'model_input'}],'candidates':[{'id':'constant','family':'constant'}]})
        inspected=run(aux,'cg6_inspect');fitted=run(aux,'cg6_auxiliary_fit',inspected['fingerprint'])
        handle=fitted['auxiliary_handles'][0]
        applied=draft('auxiliary',{'execution':s,'artifact_handle':handle,'role':'E'})
        inspected=run(applied,'cg6_inspect');result=run(applied,'cg6_auxiliary_apply',inspected['fingerprint'])
        summary=client.get(BASE+f"/results/{result['result_id']}/execution/summary").json['data']
        assert summary['cg6']['stage']=='auxiliary_application'
        page=client.get(BASE+f"/results/{result['result_id']}/execution/outputs").json['data']
        assert page['items'] and all('z' in r['input_record'] for r in page['items'])
    finally:app.extensions['confidenceguard_store'].cleanup()


def test_cli_groups_and_data_only_execution(tmp_path):
    s=execution(tmp_path).to_dict();path=tmp_path/'request.json';path.write_text(json.dumps(s));config=tmp_path/'config.json';config.write_text(json.dumps(CFG))
    cli=CliRunner()
    for group in ('predictor','auxiliary','robustness'):assert cli.invoke(main,[group,'--help']).exit_code==0
    result=cli.invoke(main,['predictor','execute','--spec',str(path),'--config',str(config),'--audience','local'])
    assert result.exit_code==0,result.output
    assert json.loads(result.output)['cg6']['stage']=='execution'
