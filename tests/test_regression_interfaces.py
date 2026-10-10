import json
from io import BytesIO
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from click.testing import CliRunner

from datatrust import DataTrust,DatasetSpec,TaskSpec,AnalysisConfig,RegressionOptions,RegressionRelationLimits
from datatrust.cli import main
from datatrust.web import create_app


def source(tmp_path,n=40):
    p=tmp_path/'source.csv';pd.DataFrame({'input':np.arange(n)**2,'outcome':np.arange(n)}).to_csv(p,index=False);return p


def configure_browser(tmp_path,raw=None,defaults=None,**fields):
    app=create_app(tmp_path/'jobs',analysis_config=defaults);app.config['TESTING']=True
    client=app.test_client();client.get('/')
    with client.session_transaction() as session:token=session['form_token']
    raw=raw or source(tmp_path).read_bytes()
    response=client.post('/upload',data={'form_token':token,'mode':'regression','dataset':(BytesIO(raw),'data.csv')},content_type='multipart/form-data',follow_redirects=True)
    assert response.status_code==200,response.data
    assert b'Which numerical outcome' in response.data
    response=client.post('/configure',data={'form_token':token,'target':'outcome',**fields},follow_redirects=True)
    with client.session_transaction() as session:job=app.extensions['datatrust_job_store'].get(session['job_id'])
    return client,token,job,response


def test_cli_bundle_parity_and_target_errors(tmp_path):
    p=source(tmp_path);runner=CliRunner()
    out=runner.invoke(main,['audit',str(p),'--task','regression','--target','outcome','--out',str(tmp_path/'report.html'),'--json-out',str(tmp_path/'r.json')])
    assert out.exit_code==0,out.output
    cli=json.loads((tmp_path/'r.json').read_text());api=DataTrust(p,'outcome',task='regression').analyze_result().to_dict()
    for key in ['profile','checks','evidence','findings','narrative','scoring','parsing','coverage']:assert cli[key]==api[key]
    out=runner.invoke(main,['audit',str(p),'--task','regression','--out',str(tmp_path/'bad.html')])
    assert out.exit_code!=0 and 'explicit target' in out.output
    assert not (tmp_path/'bad.html').exists()


def test_cli_planned_bounds_exit_zero_and_failure_exit_two(tmp_path,monkeypatch):
    p=source(tmp_path);config=tmp_path/'options.json';config.write_text(json.dumps({'regression':{'relation_limits':{'max_single_comparisons':1}}}))
    runner=CliRunner()
    out=runner.invoke(main,['audit',str(p),'--task','regression','--target','outcome','--config',str(config),'--out',str(tmp_path/'bounded.html')])
    assert out.exit_code==0 and 'coverage is bounded' in out.output
    assert 'Analysis incomplete' not in (tmp_path/'bounded.html').read_text()
    def fail(*args):raise RuntimeError('optional failure')
    monkeypatch.setattr('datatrust.core.relationship_evidence',fail)
    out=runner.invoke(main,['audit',str(p),'--task','regression','--target','outcome','--out',str(tmp_path/'partial.html')])
    assert out.exit_code==2 and 'Analysis incomplete' in out.output
    assert 'Analysis incomplete' in (tmp_path/'partial.html').read_text()


def test_browser_full_flow_declarations_exports_and_parity(tmp_path):
    client,token,job,response=configure_browser(tmp_path,target_kind='count',target_maximum='30',target_units='<b>bikes</b>')
    assert b'Single-target regression' in response.data and b'&lt;b&gt;bikes&lt;/b&gt;' in response.data
    response=client.post('/generate',data={'form_token':token},follow_redirects=True)
    assert b'Download HTML' in response.data and b'Download JSON' in response.data
    assert b'No validated scoring policy' in response.data
    result=client.get('/download/json').json
    api=DataTrust.from_spec(DatasetSpec(job['dataset_path'],source_filename='data.csv'),TaskSpec('regression','outcome'),job['config']).analyze_result().to_dict()
    for key in ['profile','checks','evidence','findings','narrative','scoring','parsing','coverage']:assert result[key]==api[key]
    assert client.get('/report').status_code==200
    pdf=client.get('/download/pdf');assert pdf.status_code==200 and pdf.data.startswith(b'%PDF')
    assert client.get('/download/pdf').data==pdf.data
    assert all(not isinstance(v,pd.DataFrame) for v in job.values())


def test_browser_configured_inspection_bound_is_coverage_not_failure(tmp_path):
    from datatrust import FidelityInspectionLimits
    defaults=AnalysisConfig(fidelity_inspection=FidelityInspectionLimits(max_records=2))
    client,token,job,response=configure_browser(tmp_path,defaults=defaults)
    assert b'expected coverage disclosure, not an analysis failure' in response.data
    response=client.post('/generate',data={'form_token':token},follow_redirects=True)
    assert b'Source-token inspection coverage' in response.data and b'Analysis incomplete' not in response.data
    exported=client.get('/download/json').json
    assert exported['execution']['status']=='completed'
    assert any(w['code']=='inspection_incomplete' for w in exported['parsing_warnings'])


def test_browser_provisional_preview_numeric_override_ack_and_invalidation(tmp_path):
    raw=b'input,outcome\n1,001\n2,002\n3,003\n'
    client,token,job,response=configure_browser(tmp_path,raw=raw,column_types='{"outcome":"string"}')
    assert b'must be numeric' in response.data
    response=client.post('/configure',data={'form_token':token,'action':'preview','column_types':'{"outcome":"numeric"}'},follow_redirects=True)
    assert b'provisional' in response.data and 'target_info' not in job
    response=client.post('/configure',data={'form_token':token,'target':'outcome','column_types':'{"outcome":"numeric"}'},follow_redirects=True)
    assert b'Review this outcome choice' in response.data
    denied=client.post('/generate',data={'form_token':token},follow_redirects=True)
    assert b'Confirm that you still want' in denied.data and not (job['directory']/'report.html').exists()
    okay=client.post('/generate',data={'form_token':token,'advanced_target_ack':'confirmed'},follow_redirects=True)
    assert b'Download JSON' in okay.data
    client.post('/configure',data={'form_token':token,'action':'preview','column_types':'{"outcome":"numeric"}'})
    assert 'analysis_result' not in job and 'target_info' not in job and client.get('/download/json').status_code==404


def test_browser_source_change_reconfirmation(tmp_path):
    client,token,job,response=configure_browser(tmp_path)
    job['dataset_path'].write_text('input,outcome\n0,10\n1,20\n')
    response=client.post('/generate',data={'form_token':token},follow_redirects=True)
    assert b'Source changed since regression confirmation' in response.data
    assert not (job['directory']/'report.html').exists() and 'target_info' not in job


def test_browser_bounded_and_partial_summaries(tmp_path,monkeypatch):
    defaults=AnalysisConfig(regression=RegressionOptions(relation_limits=RegressionRelationLimits(max_single_comparisons=1)))
    client,token,job,response=configure_browser(tmp_path,defaults=defaults)
    response=client.post('/generate',data={'form_token':token},follow_redirects=True)
    assert b'Relationship search: bounded' in response.data and b'Analysis incomplete' not in response.data
    def fail(*args):raise RuntimeError('optional failure')
    monkeypatch.setattr('datatrust.core.relationship_evidence',fail)
    response=client.post('/generate',data={'form_token':token},follow_redirects=True)
    assert b'Analysis incomplete' in response.data and client.get('/download/json').json['execution']['status']=='partial'


def test_memory_and_global_deadline_abort_or_partial(tmp_path,monkeypatch):
    p=source(tmp_path)
    def oom(*args):raise MemoryError()
    monkeypatch.setattr('datatrust.core.relationship_evidence',oom)
    with pytest.raises(MemoryError):DataTrust(p,'outcome',task='regression').analyze_result()
    out=CliRunner().invoke(main,['audit',str(p),'--task','regression','--target','outcome','--out',str(tmp_path/'oom.html')])
    assert out.exit_code!=0 and not (tmp_path/'oom.html').exists()
    monkeypatch.undo()
    from datatrust import ExecutionLimits
    from datatrust.core import relationship_evidence
    elapsed=[0.]
    monkeypatch.setattr('datatrust.core.time.monotonic',lambda:elapsed[0])
    def slow(*args):elapsed[0]=2;return relationship_evidence(*args)
    monkeypatch.setattr('datatrust.core.relationship_evidence',slow)
    r=DataTrust.from_spec(DatasetSpec(p),TaskSpec('regression','outcome'),AnalysisConfig(limits=ExecutionLimits(max_seconds=1))).analyze_result()
    assert r.execution['status']=='partial'


def test_browser_retains_config_defaults_and_explicitly_clears_expectations(tmp_path):
    from datatrust import TargetExpectations
    config=AnalysisConfig(regression=RegressionOptions(TargetExpectations(minimum=0,maximum=30,nonnegative=True,units='kg'),{'input':'available_at_prediction'}))
    client,token,job,response=configure_browser(tmp_path,defaults=config)
    assert job['config'].regression==config.regression
    response=client.post('/configure',data={'form_token':token,'target':'outcome','regression_options_submitted':'1','target_minimum':'','target_maximum':'','target_units':'','availability_input':'unknown'},follow_redirects=True)
    assert job['config'].regression.expectations==TargetExpectations()
    assert job['config'].regression.feature_availability=={}
