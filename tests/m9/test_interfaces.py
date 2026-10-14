from dataclasses import replace
import io
import json
from pathlib import Path
import time
from click.testing import CliRunner
from datatrust import *
from datatrust.cli import main
from datatrust.web import create_app
from validation.m9.fixtures import financial


def wait(client,seconds=30):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        state=client.get('/cross-representation/status').json
        if state['state']!='running':
            assert state['state']!='failed',state
            return state['state']
        time.sleep(.02)
    raise AssertionError('Browser operation did not finish.')


def test_browser_financial_workflow_reviews_reload_and_exports(tmp_path):
    dataset=tmp_path/'data';spec=financial(dataset)
    app=create_app(tmp_path/'app',data_roots=(dataset,));client=app.test_client()
    assert client.get('/cross-representation').status_code==200
    with client.session_transaction() as s: token=s['form_token']
    def post(url,data=None,**kwargs): return client.post('/cross-representation/'+url,data={'form_token':token,**(data or {})},**kwargs)
    client.post('/cross-representation',data={'form_token':token})
    # Ordinary controls: no specification import or per-record span selectors.
    for source in spec.inputs:
        assert post('configure',{'action':'source','source_id':source.id,'path':source.path,'kind':source.kind,'format':source.format,'language':'en','layout':source.layout or ''}).status_code==200
    assert post('configure',{'action':'relationship','relationship_id':'support','left_source':'records','right_source':'documents','left_keys':'entity','right_keys':'entity','left_entity':'entity','right_entity':'entity','left_period':'period','right_period':'period','cutoff':'cutoff','availability':'available'}).status_code==200
    post('configure',{'action':'mapping','mapping_id':'revenue','mapping_layout':'finance','mapping_kind':'table_field','row_headers':'Metric','value_headers':'Value','row_label':'Revenue','period_headers':'Period','period_selector':'period','mapping_unit':'INR','mapping_currency':'INR'})
    post('configure',{'action':'rule','rule_id':'revenue','rule_relationship':'support','field':'revenue','mapping':'revenue','method':'decimal','unit':'INR','currency':'INR'})
    post('configure',{'action':'mapping','mapping_id':'status','mapping_layout':'finance','mapping_kind':'label_value','labels':'Business status','pattern':r'\s*:\s*(?P<value>[^\n]+)'})
    post('configure',{'action':'rule','rule_id':'status','rule_relationship':'support','field':'claim','mapping':'status','method':'nli','claim_language':'en'})
    post('preview');assert wait(client)=='configure'
    post('confirm');assert wait(client)=='confirm'
    post('run');assert wait(client)=='completed'
    with client.session_transaction() as s: job=app.extensions['datatrust_m9_store'].jobs[s['m9_job']]
    result=job['result'];original=result.json_text();e=next(x for x in result.evidence if x['population']=='rule_1')
    assert {k:e['data'][k] for k in ['satisfied','violated','conflicting_evidence']}=={'satisfied':18,'violated':1,'conflicting_evidence':1}
    disagreement=next(x['target_id'] for x in e['data']['details'] if x['status']=='violated');conflict=next(x['target_id'] for x in e['data']['details'] if x['status']=='conflicting_evidence')
    assert post('investigate',{'target':conflict}).status_code==200
    assert {'12000000','1200000'}<={v['excerpt'] for v in job['view']}
    post('review',{'target':disagreement,'disposition':'confirm','note':'PRIVATE FINANCIAL NOTE'})
    post('review',{'target':conflict,'disposition':'unresolved'})
    semantic=next(x['target_id'] for x in next(y for y in result.evidence if y['population']=='rule_2')['data']['details'])
    post('review',{'target':semantic,'disposition':'dismiss'})
    exports={k:client.get('/cross-representation/download/'+k) for k in ['json','private','html','pdf','review']}
    assert all(v.status_code==200 for v in exports.values()),{k:v.status_code for k,v in exports.items()}
    assert 'PRIVATE FINANCIAL NOTE' not in exports['json'].text and '12000000' not in exports['html'].text and str(dataset) not in exports['json'].text
    assert result.json_text()==original
    assert post('load-result',{'report':(io.BytesIO(exports['json'].data),'analysis.json'),'private':(io.BytesIO(exports['private'].data),'manifest.json')}).status_code==302
    assert all(client.get('/cross-representation/download/'+k).status_code==200 for k in ['html','pdf','json','private'])
    assert job['result'].json_text()==original
    assert post('import-review',{'review':(io.BytesIO(exports['review'].data),'review.json')}).status_code==302
    assert len(job['reviews'].entries)==3
    wrong=json.loads(exports['review'].data);wrong['audit_id']='different'
    assert post('import-review',{'review_json':json.dumps(wrong)}).status_code==400
    (dataset/'A020-1.pdf').write_bytes(b'changed')
    post('investigate',{'target':conflict});assert any(v['status']=='unavailable' for v in job['view'])
    assert len(job['reviews'].entries)==3
    app.extensions['datatrust_m9_store'].cleanup()


def test_cli_analysis_evidence_and_review_roundtrip(tmp_path):
    spec=financial(tmp_path/'data',count=3);manifest=tmp_path/'spec.json';manifest.write_text(json.dumps(spec.to_dict()))
    runner=CliRunner();out=tmp_path/'out.html';result=runner.invoke(main,['cross-representation','--spec',str(manifest),'--out',str(out),'--json-out',str(tmp_path/'analysis.json')])
    assert result.exit_code==0,result.output
    payload=json.loads((tmp_path/'analysis.json').read_text());private=tmp_path/'.datatrust-private'/payload['profile']['audit_id']/'manifest.json';target=next(iter(payload['profile']['review_targets']))
    r=runner.invoke(main,['cross-review','--report',str(tmp_path/'analysis.json'),'--manifest',str(private),'--target',target,'--disposition','confirm','--note','private note','--out',str(tmp_path/'review.json')]);assert r.exit_code==0,r.output
    r=runner.invoke(main,['cross-review','--report',str(tmp_path/'analysis.json'),'--manifest',str(private),'--import-review',str(tmp_path/'review.json'),'--out',str(tmp_path/'review-copy.json')]);assert r.exit_code==0,r.output
    assert (tmp_path/'review-copy.json').read_bytes()==(tmp_path/'review.json').read_bytes()


def test_browser_csrf_ownership_and_configuration_invalidation(tmp_path):
    app=create_app(tmp_path/'app',data_roots=(tmp_path,));c=app.test_client();c.get('/cross-representation')
    assert c.post('/cross-representation',data={}).status_code==400
    assert app.test_client().get('/cross-representation/investigate').status_code==400
    with c.session_transaction() as s:t=s['form_token']
    c.post('/cross-representation',data={'form_token':t});assert c.get('/cross-representation/configure').status_code==200
    assert c.get('/cross-representation/download/review').status_code==409
    app.extensions['datatrust_m9_store'].cleanup()
