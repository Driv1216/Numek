from dataclasses import replace
from pathlib import Path
import json
import time
import pytest
from click.testing import CliRunner
from datatrust import *
from datatrust.cli import main
from datatrust.temporal import execute
from datatrust.web import create_app
from .test_temporal import family


def source(tmp_path,n=240):
    p=tmp_path/'data.csv';p.write_text('time,x\n'+''.join(f'{i},{0 if i<120 else i}\n' for i in range(n)))
    t=TemporalSpec(ClockSpec('time',encoding='epoch',epoch_unit='ns'),(MeasurementSpec('x'),),schedule=ScheduleSpec('fixed',cadence_ns='1',anchor='0'))
    return TemporalAuditSpec((TemporalInputSpec('data',TemporalSourceSpec(str(p)),t),),dataset_name='Temporal <script> unsafe')


def test_behavior_zero_reference_and_runs(tmp_path):
    result=execute(source(tmp_path),TemporalAnalysisConfig(behavior=TemporalBehaviorSpec(windows=2)))
    assert result.execution['status']=='completed',str([r['data'] for r in result.evidence if 'failure' in r['data']])
    w=family(result,'behavior_windows')[0];effect=w['comparisons'][0]
    assert effect['reference_iqr']==0 and effect['normalized_w1'] is None
    assert effect['cdf_distance']==1 and effect['wasserstein_1']==179.5
    assert family(result,'runs')[0]['longest_repetition']==120
    assert any(f['title']=='Contiguous equal-value runs merit investigation' for f in result.findings)
    assert family(result,'volatility')[0]['windows'][1]['ratio'] is None


def test_detailed_series_in_main_behavior_report(tmp_path):
    from datatrust.temporal_presentation import report_view
    result=execute(source(tmp_path,24),TemporalAnalysisConfig(behavior=TemporalBehaviorSpec(windows=2)))
    record=next(x for x in result.evidence if x['check_id']=='behavior_series')
    assert record['data']['selected_series']==1
    for view in (report_view(result),report_view(result,family='behavior_series')):
        rows=next(x for x in view['topics'] if x['id']=='behavior')['rows']
        assert any(x['ref'].startswith(record['id']+' ') and x['field']=='selected series' for x in rows)
        assert any(x['ref'].startswith(record['id']+' ') and x['field']=='investigation candidates' for x in rows)
        assert not any(x['field'].startswith('details') for x in rows)
        assert any(x['ref']==record['id'] and x['field']=='details' for x in view['appendix'])


def test_cli_spawn_exports_and_collision(tmp_path):
    spec=source(tmp_path,24);manifest=tmp_path/'audit.json';manifest.write_text(json.dumps(spec.to_dict()))
    output=tmp_path/'report.html';result=CliRunner().invoke(main,['temporal','--spec',str(manifest),'--out',str(output),'--json-out',str(tmp_path/'report.json')])
    assert result.exit_code==0,result.output
    text=output.read_text();assert '&lt;script&gt;' in text and '<script> unsafe' not in text
    data=json.loads((tmp_path/'report.json').read_text());assert data['schema_version']=='1.4' and data['execution']['peak_worker_rss_bytes']>0
    assert 'scoring' not in data
    result=CliRunner().invoke(main,['temporal','--spec',str(manifest),'--out',str(spec.inputs[0].source.path)])
    assert result.exit_code==1 and 'aliases' in result.output


def test_browser_manifest_confirmation_worker_lock_downloads(tmp_path):
    spec=source(tmp_path,24);app=create_app(tmp_path/'web',data_roots=(tmp_path,));app.testing=True;client=app.test_client()
    client.get('/temporal')
    with client.session_transaction() as session:token=session['form_token']
    assert client.post('/temporal',data={'form_token':token}).status_code==302
    response=client.post('/temporal/configure',data={'form_token':token,'manifest':json.dumps(spec.to_dict()),'configuration':'{}'})
    assert response.status_code==302
    store=app.extensions['datatrust_m5_store'];j=next(iter(store.jobs.values()))
    assert client.get('/temporal/confirm').status_code==200
    assert app.extensions['datatrust_m4_store'].lock is store.lock
    store.lock.acquire()
    try:
        client.post('/temporal/run',data={'form_token':token,'fingerprint':j['fingerprint']});assert j['state']=='confirm'
    finally:store.lock.release()
    client.post('/temporal/run',data={'form_token':token,'fingerprint':j['fingerprint']})
    j['thread'].join(15)
    assert j['state']=='completed',j.get('error')
    assert client.get('/temporal/investigate?measurement=x').status_code==200
    for kind in ('json','html'):
        assert client.get('/temporal/download/'+kind).status_code==200
    path=j['artifacts']['html']['path'];path.write_text('changed')
    assert client.get('/temporal/download/html').status_code==409
    store.cleanup();app.extensions['datatrust_m4_store'].cleanup()


def test_invalid_browser_declaration_retains_fields(tmp_path):
    app=create_app(tmp_path/'web',data_roots=(tmp_path,));app.testing=True;c=app.test_client();c.get('/temporal')
    with c.session_transaction() as sess:token=sess['form_token']
    c.post('/temporal',data={'form_token':token});r=c.post('/temporal/configure',data={'form_token':token,'manifest':'{"invalid":1}','purpose':'retain this'})
    assert r.status_code==200 and b'retain this' in r.data and b'Unknown' in r.data
    app.extensions['datatrust_m5_store'].cleanup();app.extensions['datatrust_m4_store'].cleanup()


def test_render_pdf_eight_topics(tmp_path):
    from pypdf import PdfReader
    result=execute(source(tmp_path,24),TemporalAnalysisConfig())
    artifacts=result.generate_artifacts(tmp_path/'report.pdf',format='pdf',json_path=tmp_path/'result.json')
    pdf=PdfReader(artifacts.pdf_path)
    assert 8<=len(pdf.pages)<=12
    text=' '.join(p.extract_text() for p in pdf.pages)
    assert 'Availability and outcome maturity' in text and 'Methodology and coverage' in text
    assert artifacts.qa_metadata['retained_evidence_records']==len(result.evidence)
