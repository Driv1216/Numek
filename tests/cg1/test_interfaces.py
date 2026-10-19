from dataclasses import replace
import io
import json
from pathlib import Path
import time
import pytest
from confidenceguard import *
from confidenceguard.cli import main
from datatrust.web import create_app
from click.testing import CliRunner
from .test_analysis import spec,core,measurement

BASE='/api/confidenceguard/v1'


def terminal(client,job):
    end=time.monotonic()+30
    while job['state'] in {'pending','running','cancelling'} and time.monotonic()<end:
        time.sleep(.02);job=client.get(BASE+'/jobs/'+job['id']).json['data']
    assert job['state'] not in {'pending','running','cancelling'},job
    return job


def test_artifacts_canonical_private_resolution_and_failure(tmp_path):
    s=spec(tmp_path,'id,y,p\n'+''.join(f'{i},{i%2},{1-i%2}\n' for i in range(30)),prediction='p')
    r=core(s);before=r.to_private_dict()
    a=r.generate_artifacts(tmp_path/'report.html',json_path=tmp_path/'report.json')
    assert Path(a.html_path).is_file() and Path(a.private_manifest_path).stat().st_mode&0o077==0
    assert r.to_private_dict()==before
    assert 'projection_digest' in json.loads(Path(a.json_path).read_text())
    ref=next(iter(r.private['locators']))
    assert r.resolve_evidence(ref,allowed_roots=(tmp_path,))['status']=='resolved'
    assert 'excerpt' not in r.resolve_evidence(ref,allowed_roots=(tmp_path,))
    assert 'excerpt' in r.resolve_evidence(ref,allowed_roots=(tmp_path,),reveal_values=True)
    def broken(*a):raise RuntimeError('renderer unavailable')
    with pytest.raises(RuntimeError) as error:r.generate_artifacts(tmp_path/'failure.pdf',format='pdf',json_path=tmp_path/'failure.json',pdf_converter=broken)
    assert Path(error.value.artifacts.html_path).is_file() and Path(error.value.artifacts.json_path).is_file()
    Path(s.sources[0].path).write_text('id,y,p\n0,1,1\n')
    with pytest.raises(Exception):r.resolve_evidence(ref,allowed_roots=(tmp_path,))


def test_json_browser_story_and_security(tmp_path):
    s=spec(tmp_path,'id,y,p,g\n'+''.join(f'{i},{i%2},{1-i%2},A\n' for i in range(30)),prediction='p')
    app=create_app(tmp_path/'app',data_roots=(tmp_path,));app.testing=True;client=app.test_client()
    try:
        csrf=client.get(BASE+'/session').json['data']['csrf_token'];headers={'X-CSRF-Token':csrf}
        assert client.post(BASE+'/sources',json={}).status_code==403
        assert client.get(BASE+'/capabilities',headers={'Origin':'http://evil.example'}).status_code==403
        assert client.get(BASE+'/capabilities',headers={'Host':'evil.example'}).status_code==403
        upload=client.post(BASE+'/sources',data={'file':(io.BytesIO(Path(s.sources[0].path).read_bytes()),'test.csv')},headers=headers)
        assert upload.status_code==201,upload.json
        body=s.to_dict();body['sources']=[{'id':'data','handle':upload.json['data']['handle']}]
        draft=client.post(BASE+'/evaluations',json={'spec':body},headers=headers).json['data']
        def submit(kind,**kw):
            payload={'kind':kind,'client_request_id':kind+str(time.monotonic()),**kw}
            response=client.post(BASE+'/jobs',json=payload,headers=headers)
            assert response.status_code==202,response.json
            return terminal(client,response.json['data'])
        inspection=submit('inspect',evaluation_id=draft['id'],revision=1)
        assert inspection['state']=='succeeded',inspection
        assert 'path' not in inspection['output']['effective_spec']['sources'][0]
        job=submit('evaluate',evaluation_id=draft['id'],revision=1,fingerprint=inspection['output']['fingerprint'])
        assert job['state']=='succeeded',job
        rid=job['output']['result_id']
        assert app.test_client().get(BASE+'/results/'+rid).status_code==404
        result=client.get(BASE+'/results/'+rid).json['data']
        assert next(m for m in result['measurements'] if m['metric']=='accuracy')['value']==0
        ref=next(ref for m in result['measurements'] for ref in m['evidence_refs'])
        evidence=submit('resolve_evidence',result_id=rid,reference=ref,reveal_values=True)
        assert evidence['state']=='succeeded',evidence
        assert evidence['output']['values_disclosed']
        export=submit('export',result_id=rid,format='html')
        assert export['state']=='succeeded',export
        artifacts=client.get(BASE+f'/results/{rid}/artifacts').json['data']
        assert {'html','json','private_result','private_manifest'}=={a['kind'] for a in artifacts}
        files={a['kind']:client.get(BASE+'/artifacts/'+a['id']+'/content').data for a in artifacts}
        assert b'projection_digest' in files['json']
        client2=app.test_client();token2=client2.get(BASE+'/session').json['data']['csrf_token']
        reopened=client2.post(BASE+'/results/import',data={'result':(io.BytesIO(files['private_result']),'result.json'),'manifest':(io.BytesIO(files['private_manifest']),'manifest.json')},headers={'X-CSRF-Token':token2})
        assert reopened.status_code==201,reopened.json
        assert client.get('/confidenceguard').status_code==200
        assert client.get('/confidenceguard/assets/client.js').status_code==200
        # Accepted DataTrust forms still require their original token.
        assert client.post('/new').status_code==400
    finally:app.extensions['confidenceguard_store'].cleanup()


def test_cli_three_tasks_and_contracts(tmp_path):
    for kind,text,kw in [('binary_classification','id,y,p\n1,0,0\n2,1,1\n',{'prediction':'p'}),('multiclass_classification','id,y,p\n1,a,a\n2,b,b\n3,c,a\n',{'prediction':'p'}),('regression','id,y,p\n1,1,2\n2,2,2\n',{'prediction':'p'})]:
        folder=tmp_path/kind;folder.mkdir();s=spec(folder,text,kind,**kw);manifest=folder/'spec.json';manifest.write_text(json.dumps(s.to_dict()))
        result=CliRunner().invoke(main,['evaluate','--spec',str(manifest),'--out',str(folder/'out.html'),'--json-out',str(folder/'out.json')])
        assert result.exit_code==0,result.output
    from confidenceguard.schema import schemas,openapi,examples
    for example in examples()['evaluations'].values():
        # Exercise semantic request examples without making a schema validator a runtime dependency.
        value=json.loads(json.dumps(example['spec']))
        value['sources']=[{'id':'predictions','path':str(tmp_path/'source.csv')}]
        EvaluationSpec.from_dict(value)
        assert schemas()['$defs']['SourceHandle']['additionalProperties'] is False
    assert openapi()['openapi']=='3.1.0'
