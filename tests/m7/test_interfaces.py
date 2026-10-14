from dataclasses import replace
import json
from pathlib import Path
import threading
import time
from click.testing import CliRunner
import pytest
from datatrust import *
from datatrust.cli import main
from datatrust.web import create_app
from tests.m7.test_foundation import fixture,run


def test_supervised_python_and_cli_equivalence(tmp_path):
    spec=fixture(tmp_path); result=DataTrust.audit_images(spec)
    path=tmp_path/'spec.json'; path.write_text(json.dumps(spec.to_dict()))
    out=tmp_path/'reports'; out.mkdir()
    cli=CliRunner().invoke(main,['images','--spec',str(path),'--out',str(out/'review.html'),'--json-out',str(out/'review.json')])
    assert cli.exit_code==0,cli.output
    payload=json.loads((out/'review.json').read_text())
    assert payload['profile']['occurrences']==result.profile['occurrences']==1
    assert payload['schema_version']=='1.6'
    assert (out/'review.html').exists()


def token(client):
    client.get('/images')
    with client.session_transaction() as session: return session['form_token']


def post(client,url,data): return client.post(url,data=dict(data,form_token=token(client)),follow_redirects=False)


def await_job(app,client,expected):
    with client.session_transaction() as session: jid=session['m7_job']
    job=app.extensions['datatrust_m7_store'].jobs[jid]
    for _ in range(300):
        if job['state']!='running': break
        time.sleep(.02)
    assert job['state']==expected,job.get('error')
    return job


def test_browser_standard_preset_confirmation_inspector_and_exports(tmp_path):
    fixture(tmp_path); app=create_app(tmp_path/'workspace',data_roots=(tmp_path,)); client=app.test_client()
    assert post(client,'/images',{'preset':'manifest'}).status_code==302
    assert post(client,'/images/sources',{'source_id':'s','local_path':str(tmp_path/'data.jsonl'),'asset_root':str(tmp_path),'format':'jsonl','role':'train'}).status_code==200
    post(client,'/images/inspect',{}); initial=await_job(app,client,'configure')['inspected']
    post(client,'/images/configure',{'s0_task':'detection','s0_path':'path','s0_logical_id':'id','s0_objects':'objects','s0_frame':'encoded','s0_expectation':'unknown'})
    j=await_job(app,client,'confirm')
    assert client.get('/images/confirm').status_code==200
    assert j['sources'][0]['task']['kind']=='detection'
    assert j['inspected'] is initial
    assert b'objects' in client.get('/images/configure').data
    post(client,'/images/run',{'confirm':'yes'}); j=await_job(app,client,'completed')
    assert client.get('/images/download/json').status_code==200
    assert client.get('/images/download/private').status_code==200
    native_pdf=client.get('/images/download/pdf')
    assert native_pdf.status_code==200 and native_pdf.data.startswith(b'%PDF')
    ref=next(iter(j['result'].private['locators']))
    viewed=post(client,'/images/investigate',{'reference':ref,'overlays':'yes'})
    assert viewed.status_code==200 and b'data:image/jpeg;base64,' in viewed.data
    assert viewed.headers['Cache-Control']=='no-store'
    assert j['view_options']['overlays']
    assert b'value="yes" checked' in viewed.data
    assert b'data:image/jpeg;base64,' not in client.get('/images/download/html').data
    stranger=app.test_client(); assert stranger.get('/images/download/json').status_code==400
    assert client.post('/images/run',data={'confirm':'yes'}).status_code==400
    app.extensions['datatrust_m7_store'].cleanup()


def test_cancellation_publishes_no_result(tmp_path):
    spec=fixture(tmp_path); cancel=threading.Event(); cancel.set()
    with pytest.raises(AnalysisError) as exc: DataTrust.audit_images(spec,cancel=cancel)
    assert exc.value.code=='cancelled'


def test_optional_native_fault_preserves_core_only(monkeypatch,tmp_path):
    import datatrust.images as images
    spec=fixture(tmp_path); core=run(spec)
    model={'dummy':'verified'}
    monkeypatch.setattr(images,'preflight',lambda *args:model)
    calls=[]
    def supervise(operation,args,options,**kwargs):
        calls.append(operation.__name__)
        if operation.__name__=='execute_core':
            core.private['model_selection']=[]
            return core
        if operation.__name__=='execute_model': raise AnalysisError('PRIVATE_PAYLOAD',code='worker_terminated',stage='model')
        return operation(*args)
    monkeypatch.setattr(images,'run_supervised',supervise)
    r=images.audit_images(spec,replace(ImageAnalysisConfig(),models=ImageModelOptions(str(tmp_path))))
    assert r.execution['status']=='partial' and r.execution['model_failure']['code']=='worker_terminated'
    assert not any(x['family']=='embeddings' for x in r.evidence)
    assert 'PRIVATE_PAYLOAD' not in r.json_text() and calls==['execute_core','execute_model','finalize']


def test_source_integrity_optional_fault_is_fatal(monkeypatch,tmp_path):
    import datatrust.images as images
    spec=fixture(tmp_path); core=run(spec)
    monkeypatch.setattr(images,'preflight',lambda *args:{'dummy':'verified'})
    def supervise(operation,args,options,**kwargs):
        if operation.__name__=='execute_core': core.private['model_selection']=[]; return core
        raise AnalysisError('changed',code='source_changed')
    monkeypatch.setattr(images,'run_supervised',supervise)
    with pytest.raises(AnalysisError) as exc: images.audit_images(spec,replace(ImageAnalysisConfig(),models=ImageModelOptions(str(tmp_path))))
    assert exc.value.code=='source_changed'


def test_changed_source_after_reused_browser_seal_blocks_export(tmp_path):
    fixture(tmp_path); app=create_app(tmp_path/'workspace',data_roots=(tmp_path,)); client=app.test_client()
    post(client,'/images',{'preset':'manifest'})
    post(client,'/images/sources',{'source_id':'s','local_path':str(tmp_path/'data.jsonl'),'asset_root':str(tmp_path),'format':'jsonl','role':'train'})
    post(client,'/images/inspect',{}); initial=await_job(app,client,'configure')['inspected']
    post(client,'/images/configure',{'s0_task':'detection','s0_path':'path','s0_objects':'objects','s0_mask':'mask','s0_frame':'encoded'})
    j=await_job(app,client,'confirm'); assert j['inspected'] is initial
    (tmp_path/'data.jsonl').write_text(json.dumps({'path':'image.png','objects':[]})+'\n')
    post(client,'/images/run',{'confirm':'yes'}); j=await_job(app,client,'failed')
    assert not j.get('result') and not j.get('artifacts')
    app.extensions['datatrust_m7_store'].cleanup()
