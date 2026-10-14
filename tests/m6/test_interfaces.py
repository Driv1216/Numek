from dataclasses import replace
import json
from pathlib import Path
import threading
import time
import pytest
from click.testing import CliRunner
from datatrust import *
from datatrust.text import _execute
from datatrust.cli import main
from datatrust.web import create_app
from datatrust.text_web import guided
from werkzeug.datastructures import MultiDict


def source(tmp_path):
    p=tmp_path/'source.jsonl';p.write_text('\n'.join(json.dumps({'text':'SECRET_MARKER <script>bad()</script>','id':str(i)}) for i in range(2)))
    spec=TextAuditSpec((TextInputSpec('data',TextSourceSpec(str(p)),(TextFieldSpec('text','text'),),id_selector='id'),),allowed_roots=(str(tmp_path),))
    return p,spec


def config():return TextAnalysisConfig(near_duplicates=False,passages=False)


def test_supervised_api_and_cancel(tmp_path):
    p,spec=source(tmp_path);r=DataTrust.audit_text(spec,config())
    assert r.execution['peak_worker_rss_bytes']>0 and r.schema_version=='1.5'
    cancellation=threading.Event();cancellation.set()
    with pytest.raises(AnalysisError) as error:DataTrust.audit_text(spec,config(),cancel=cancellation)
    assert error.value.code=='cancelled' and not error.value.execution['completed_result_published']


def test_private_artifacts_and_excerpt_collision(tmp_path):
    p,spec=source(tmp_path);r=_execute(spec,config());out=tmp_path/'out.html';art=r.generate_artifacts(out,json_path=tmp_path/'out.json')
    assert 'SECRET_MARKER' not in out.read_text() and 'SECRET_MARKER' not in Path(art.json_path).read_text()
    assert Path(art.private_manifest_path).stat().st_mode&0o077==0
    exported=json.loads(Path(art.json_path).read_text())
    import hashlib
    assert exported['profile']['export_identity']['canonical_html_sha256']==hashlib.sha256(out.read_bytes()).hexdigest()
    reference=next(x for x in r.evidence if x['family']=='exact_duplicates')['references'][0]
    from datatrust import DataTrust
    resolved=DataTrust.resolve_text_evidence(art.private_manifest_path,reference,art.json_path,allowed_roots=(tmp_path,),reveal_content=True)
    assert resolved['excerpt'].startswith('SECRET_MARKER')
    with pytest.raises(ValueError):r.generate_artifacts(out,excerpt_refs=(reference,),allowed_roots=(tmp_path,))
    excerpt=r.generate_artifacts(tmp_path/'excerpt.html',excerpt_refs=(reference,),allowed_roots=(tmp_path,))
    html=Path(excerpt.html_path).read_text();assert 'SECRET_MARKER' in html and '&lt;script&gt;' in html and '<script>bad()' not in html
    manifest=json.loads(Path(art.private_manifest_path).read_text());manifest['sources']['data']['sha256']='0'*64
    with pytest.raises(ValueError):DataTrust.resolve_text_evidence(manifest,reference,art.json_path,allowed_roots=(tmp_path,))
    with pytest.raises(ValueError):r.generate_artifacts(p)


def test_cli_manifest_and_evidence(tmp_path):
    p,spec=source(tmp_path);manifest=tmp_path/'spec.json';manifest.write_text(json.dumps(spec.to_dict()));cfg=tmp_path/'cfg.json';cfg.write_text(json.dumps(config().to_dict()))
    runner=CliRunner();r=runner.invoke(main,['text','--spec',str(manifest),'--config',str(cfg),'--out',str(tmp_path/'report.html'),'--json-out',str(tmp_path/'report.json')])
    assert r.exit_code==0,r.output
    report=json.loads((tmp_path/'report.json').read_text());ref=next(x for x in report['evidence'] if x['family']=='exact_duplicates')['references'][0]
    private=tmp_path/'.datatrust-private'/report['profile']['audit_id']/'manifest.json'
    evidence=runner.invoke(main,['text-evidence','--manifest',str(private),'--report',str(tmp_path/'report.json'),'--ref',ref,'--data-root',str(tmp_path),'--show-content'])
    assert evidence.exit_code==0 and 'SECRET_MARKER' in evidence.output


def test_browser_guided_confirmation_run_and_private_reveal(tmp_path):
    p,spec=source(tmp_path);app=create_app(tmp_path/'ui',data_roots=(tmp_path,));client=app.test_client();client.get('/text')
    with client.session_transaction() as s:token=s['form_token']
    base={'form_token':token}
    assert client.post('/text',data=base|{'preset':'corpus'}).status_code==302
    assert client.post('/text/sources',data=base|{'local_path':str(p),'source_id':'data','format':'jsonl'}).status_code==200
    assert client.get('/text/configure').status_code==200
    data=MultiDict(list((base|{'s0_field_name':'text','s0_field_selector':'text','s0_field_kind':'document','s0_field_required':'no','s0_field_asset':'no','s0_identity':'id','vocabulary':'yes','near_duplicates':'no','passages':'no'}).items())+[('representation','raw'),('representation','nfc')])
    response=client.post('/text/configure',data=data);assert response.status_code==302,response.data
    assert client.get('/text/confirm').status_code==200
    assert client.post('/text/run',data=base|{'confirm':'yes'}).status_code==302
    store=app.extensions['datatrust_m6_store']
    with client.session_transaction() as s:j=store.jobs[s['m6_job']]
    j['thread'].join(20);assert j['state']=='completed',j.get('error')
    assert client.get('/text/result').status_code==200
    pdf=client.get('/text/download/pdf');assert pdf.status_code==200 and pdf.data.startswith(b'%PDF')
    assert b'SECRET_MARKER' not in client.get('/text/download/json').data
    ref=next(x for x in j['result'].evidence if x['family']=='exact_duplicates')['references'][0]
    assert b'SECRET_MARKER' in client.post('/text/evidence',data=base|{'reference':ref,'reveal':'yes'}).data
    outsider=app.test_client();assert outsider.get('/text/download/json').status_code==400
    assert client.post('/text/evidence',data={'reference':ref}).status_code==400
    assert client.post('/text/export-excerpts',data=base|{'references':ref}).status_code==200
    p.write_text(p.read_text()+'\n'+json.dumps({'text':'changed source'}))
    assert client.post('/text/export-excerpts',data=base|{'references':ref}).status_code==409
    assert client.get('/text/download/json').status_code==409
    store.cleanup()


def test_associated_annotation_table_and_retrieval_union(tmp_path):
    doc=tmp_path/'doc.jsonl';doc.write_text(json.dumps({'id':'d','text':'abcdef'}))
    ann=tmp_path/'ann.jsonl';ann.write_text('\n'.join(json.dumps(x) for x in [{'doc':'d','label':'POSITIVE'},{'doc':'missing','label':'NEGATIVE'}]))
    chunk=tmp_path/'chunk.jsonl';chunk.write_text('\n'.join(json.dumps(x) for x in [{'id':'c1','parent':'d','text':'abc','start':0,'end':3},{'id':'c2','parent':'d','text':'bcde','start':1,'end':5}]))
    spec=TextAuditSpec((TextInputSpec('docs',TextSourceSpec(str(doc)),(TextFieldSpec('text','text'),),id_selector='id'),TextInputSpec('anns',TextSourceSpec(str(ann)),role='annotations',annotations=(TextAnnotationSpec('text','label',content_source='docs',content_id_selector='doc'),)),TextInputSpec('chunks',TextSourceSpec(str(chunk)),(TextFieldSpec('text','text',kind='chunk'),),id_selector='id',retrieval=TextRetrievalSpec('chunk','docs','parent',field='text',parent_field='text',extractive=True))))
    r=_execute(spec,config());retrieval=next(x for x in r.evidence if x['family']=='retrieval')['data']
    assert retrieval['covered_source_characters_union']==5
    assert next(x for x in r.evidence if x['family']=='invalidity')['data']['reasons']['unresolved_or_ambiguous_annotation_content']==1


def test_browser_cancel_reaches_supervisor_and_releases_worker_lock(tmp_path,monkeypatch):
    p,spec=source(tmp_path)
    from datatrust import text_web
    real_audit=text_web.audit_text
    entered=threading.Event()
    def wait_for_cancel(spec,config,progress,cancel):
        entered.set()
        assert cancel.wait(5)
        return real_audit(spec,config,progress=progress,cancel=cancel)
    monkeypatch.setattr(text_web,'audit_text',wait_for_cancel)
    app=create_app(tmp_path/'ui',data_roots=(tmp_path,));client=app.test_client();client.get('/text')
    with client.session_transaction() as s:token=s['form_token']
    base={'form_token':token}
    client.post('/text',data=base|{'preset':'corpus'})
    client.post('/text/sources',data=base|{'local_path':str(p),'source_id':'data','format':'jsonl'})
    client.post('/text/configure',data=base|{'spec_json':json.dumps(spec.to_dict()),'config_json':json.dumps(config().to_dict())})
    assert client.post('/text/run',data=base|{'confirm':'yes'}).status_code==302
    assert entered.wait(5)
    assert client.post('/text/cancel',data=base).status_code==302
    store=app.extensions['datatrust_m6_store']
    with client.session_transaction() as s:j=store.jobs[s['m6_job']]
    j['thread'].join(10)
    assert j['state']=='failed' and j['error'].startswith('cancelled')
    assert not j.get('result') and not j.get('artifacts')
    assert not j['failure_execution']['completed_result_published']
    assert store.lock.acquire(blocking=False)
    store.lock.release();store.cleanup()
