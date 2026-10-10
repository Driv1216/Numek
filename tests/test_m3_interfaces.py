import io
import json
from dataclasses import replace
from pathlib import Path
import pytest
from click.testing import CliRunner
from datatrust import *
from datatrust.cli import main
from datatrust.web import create_app
from datatrust.renderer import render_analysis_result
from datatrust.presentation import report_view


def test_cli_repeatable_targets_task_spec_conflicts_and_equivalence(tmp_path):
    source=tmp_path/'data.csv';source.write_text('x,y,z\n'+''.join(f'{i},{i%2},{i%3==0:d}\n' for i in range(40)))
    runner=CliRunner()
    out=runner.invoke(main,['audit',str(source),'--task','multilabel_classification','--target','y','--target','z','--out',str(tmp_path/'labels.html'),'--json-out',str(tmp_path/'labels.json')])
    assert out.exit_code==0,out.output
    data=json.loads((tmp_path/'labels.json').read_text());assert data['schema_version']=='1.2' and data['profile']['roles']['features']==['x']
    spec=tmp_path/'spec.json';spec.write_text(json.dumps({'kind':'multilabel_classification','targets':['y','z'],'feature_columns':['x']}))
    out=runner.invoke(main,['audit',str(source),'--task-spec',str(spec),'--out',str(tmp_path/'spec.html'),'--json-out',str(tmp_path/'spec-result.json')])
    assert out.exit_code==0,out.output
    spec_result=json.loads((tmp_path/'spec-result.json').read_text());assert spec_result['profile']==data['profile']
    for args in [['--target','y'],['--task','classification']]:
        out=runner.invoke(main,['audit',str(source),'--task-spec',str(spec),'--out',str(tmp_path/'bad.html'),*args])
        assert out.exit_code==1 and 'conflicts' in out.output
    out=runner.invoke(main,['audit',str(source),'--target','y','--out',str(tmp_path/'old.html')])
    assert out.exit_code==0 and 'DataTrust report written' in out.output


@pytest.mark.parametrize('mode,roles',[
 ('annotation_classification',{'x':'feature','y':'target','z':'ignored'}),
 ('annotation_regression',{'x':'feature','y':'target','z':'target'}),
 ('multilabel_classification',{'x':'feature','y':'target','z':'target'}),
 ('clustering',{'x':'feature','y':'feature','z':'feature'}),
 ('anomaly_detection',{'x':'feature','y':'feature','z':'feature'}),
 ('role_profile',{'x':'feature','y':'metadata','z':'ignored'}),
])
def test_guided_browser_all_m3_modes_same_completed_payload_no_reanalysis(tmp_path,monkeypatch,mode,roles):
    app=create_app(tmp_path);app.testing=True;client=app.test_client();client.get('/')
    with client.session_transaction() as s:token=s['form_token']
    content='x,y,z\n'+''.join(f'{i},{i%2},{int(i%3==0)}\n' for i in range(40))
    response=client.post('/upload',data={'form_token':token,'mode':mode,'dataset':(io.BytesIO(content.encode()),'source.csv')},content_type='multipart/form-data',follow_redirects=True)
    assert response.status_code==200 and 'Declare the task and column roles' in response.text
    assert 'option value="unknown"' in response.text if mode.startswith('annotation') else True
    response=client.post('/configure',data={'form_token':token,**{'role_'+c:r for c,r in roles.items()}},follow_redirects=True)
    assert response.status_code==200 and 'Confirm the effective analysis' in response.text
    response=client.post('/generate',data={'form_token':token,'representation_ack':'confirmed'},follow_redirects=True)
    assert 'Report available' in response.text
    with client.session_transaction() as s:job=app.extensions['datatrust_job_store'].get(s['job_id'])
    original=job['analysis_result'];assert original.schema_version=='1.2'
    python=DataTrust.from_spec(original.dataset,job['task_spec'],job['config']).analyze_result()
    assert python.profile==original.profile and python.methodology_id==original.methodology_id
    def forbidden(*args,**kwargs):pytest.fail('Completed export reanalyzed the data')
    monkeypatch.setattr('datatrust.core.run_analysis',forbidden)
    assert client.get('/download/json').status_code==200 and client.get('/report').status_code==200
    assert json.loads(client.get('/download/json').data)['profile']==original.to_dict()['profile']
    response=client.post('/configure',data={'form_token':token,**{'role_'+c:r for c,r in roles.items()},'annotation_expectation':'optional'},follow_redirects=True)
    assert response.status_code==200 and not job.get('artifacts')


def test_browser_confirmation_fingerprints_source_and_config(tmp_path):
    app=create_app(tmp_path);app.testing=True;client=app.test_client();client.get('/')
    with client.session_transaction() as s:token=s['form_token']
    client.post('/upload',data={'form_token':token,'mode':'annotation_classification','dataset':(io.BytesIO(b'x,y\n1,a\n2,b\n'),'source.csv')},content_type='multipart/form-data')
    client.post('/configure',data={'form_token':token,'role_y':'target'})
    with client.session_transaction() as s:job=app.extensions['datatrust_job_store'].get(s['job_id'])
    job['config']=replace(job['config'],annotations=AnnotationOptions(AnnotationSpec('optional')))
    response=client.post('/generate',data={'form_token':token,'representation_ack':'confirmed'},follow_redirects=True)
    assert 'changed since confirmation' in response.text and not job.get('artifacts') and 'target_info' not in job
    client.post('/configure',data={'form_token':token,'role_y':'target'})
    job['dataset_path'].write_text('x,y\n1,a\n2,b\n3,c\n')
    response=client.post('/generate',data={'form_token':token,'representation_ack':'confirmed'},follow_redirects=True)
    assert 'changed since confirmation' in response.text and not job.get('artifacts')


def test_presentation_budgets_preserve_json_and_independent_detail_counts(tmp_path):
    source=tmp_path/'wide.csv';source.write_text(','.join(['x']+[f'label{i}' for i in range(40)])+'\n'+''.join(','.join([str(i)]+[str((i+j)%2) for j in range(40)])+'\n' for i in range(40)))
    r=DataTrust.from_spec(DatasetSpec(source),TaskSpec('multilabel_classification',targets=tuple(f'label{i}' for i in range(40))),AnalysisConfig(presentation=PresentationLimits(table_rows=3,target_panels=2,feature_details=1,appendix_rows=4))).analyze_result()
    before=r.json_text();v=report_view(r);html=render_analysis_result(r)
    assert r.json_text()==before and len(r.profile['multilabel']['labels'])==40
    assert v['qa']['appendix_detail_rows']<=4
    assert any(o['computed']==40 and o['displayed']==3 for o in v['qa']['presentation_omissions'])
    assert 'Presentation truncation' in html and 'Analytical' not in html or 'uncomputed' in html


def test_optional_failure_and_memory_abort_new_checks(tmp_path,monkeypatch):
    source=tmp_path/'data.csv';source.write_text('x,a,b\n1,1,0\n2,0,1\n')
    audit=DataTrust.from_spec(DatasetSpec(source),TaskSpec('multilabel_classification',targets=('a','b')))
    def failed(*args):raise RuntimeError('failure')
    monkeypatch.setattr('datatrust.m3.multilabel_evidence',failed)
    r=audit.analyze_result();assert r.execution['status']=='partial' and r.profile['multilabel'] is None and r.profile['annotations']
    assert 'Analysis incomplete' in render_analysis_result(r)
    def oom(*args):raise MemoryError()
    monkeypatch.setattr('datatrust.m3.multilabel_evidence',oom)
    with pytest.raises(MemoryError):audit.analyze_result()


def test_annotation_browser_expected_semantics_preserve_legacy_reports(tmp_path):
    app=create_app(tmp_path);app.testing=True;client=app.test_client();client.get('/')
    with client.session_transaction() as s:token=s['form_token']
    text=b'x,y\n1,a\n2,b\n3,a\n4,b\n'
    client.post('/upload',data={'form_token':token,'mode':'annotation_classification','dataset':(io.BytesIO(text),'source.csv')},content_type='multipart/form-data')
    client.post('/configure',data={'form_token':token,'role_y':'target','annotation_expectation':'expected'})
    response=client.post('/generate',data={'form_token':token,'representation_ack':'confirmed'},follow_redirects=True)
    assert 'Report available' in response.text and 'Legacy classification score:' in response.text
    with client.session_transaction() as s:job=app.extensions['datatrust_job_store'].get(s['job_id'])
    r=job['analysis_result']
    assert r.schema_version=='1.0' and r.methodology_id=='classification_legacy_2026_08_13'
    old=DataTrust(job['dataset_path'],'y').analyze_result()
    assert r.scoring==old.scoring and r.profile==old.profile
    from datatrust.renderer import render_html_report
    legacy=r.to_legacy_dict()
    assert client.get('/report').text==render_html_report(**legacy,generated_at=__import__("datetime").datetime.fromisoformat(r.generated_at).strftime("%Y-%m-%d %H:%M:%S"))


def test_presentation_ranks_affected_fields_before_source_order(tmp_path):
    source=tmp_path/'data.csv';source.write_text('early,late,a,b\n1,,1,2\n2,,0,0\n3,,1,0\n')
    r=DataTrust.from_spec(DatasetSpec(source),TaskSpec('multilabel_classification',targets=('a','b')),AnalysisConfig(presentation=PresentationLimits(table_rows=1,feature_details=1))).analyze_result()
    v=report_view(r)
    distribution=next(t for t in v['task_tables'] if t['title']=='Observed binary assignments')
    features=next(t for t in v['feature_tables'] if t['title']=='Selected feature structure')
    assert distribution['rows'][0][0]=='b' and features['rows'][0][0]=='late'
    assert r.profile['multilabel']['labels'][0]['target']=='a'


def test_output_identity_failure_is_partial_execution(tmp_path,monkeypatch):
    import datatrust.regression as regression
    source=tmp_path/'data.csv';source.write_text('x,a,b\n'+''.join(f'{i},{i},{i*2}\n' for i in range(40)))
    original=regression.relationship_evidence
    def failed_identity(*args,**kwargs):
        value=original(*args,**kwargs)
        value['search'].update(status='partial',failure={'reason_category':'diagnostic_failure','reason':'controlled identity failure'})
        return value
    monkeypatch.setattr(regression,'relationship_evidence',failed_identity)
    r=DataTrust.from_spec(DatasetSpec(source),TaskSpec('regression',targets=('a','b'))).analyze_result()
    assert r.execution['status']=='partial'
    assert any(c.check_id=='output_identity' and c.execution.value=='failed' for c in r.checks)
    assert 'Analysis incomplete' in render_analysis_result(r)


def test_browser_launch_declarations_and_relationship_limits_are_retained(tmp_path):
    config=AnalysisConfig(annotations=AnnotationOptions(AnnotationSpec('optional')),
        regression=RegressionOptions(expectations_by_target={'y':TargetExpectations('continuous',minimum=0)},relation_limits=RegressionRelationLimits(max_single_comparisons=37)))
    app=create_app(tmp_path,analysis_config=config);app.testing=True;client=app.test_client();client.get('/')
    with client.session_transaction() as s:token=s['form_token']
    response=client.post('/upload',data={'form_token':token,'mode':'annotation_regression','dataset':(io.BytesIO(b'x,y\n1,2\n2,4\n'),'source.csv')},content_type='multipart/form-data',follow_redirects=True)
    assert 'continuous' in response.text and 'minimum' in response.text
    client.post('/configure',data={'form_token':token,'role_y':'target','annotation_expectation':'optional',
        'expectations_by_target':json.dumps({'y':{'kind':'continuous','minimum':0}})})
    with client.session_transaction() as s:job=app.extensions['datatrust_job_store'].get(s['job_id'])
    assert job['config'].regression.relation_limits.max_single_comparisons==37
    assert job['config'].regression.expectations_by_target['y'].minimum==0


def test_browser_scale_sensitivity_survives_configuration_edit(tmp_path):
    app=create_app(tmp_path,analysis_config=AnalysisConfig(features=FeatureOptions(scale_sensitive=False)));app.testing=True;client=app.test_client();client.get('/')
    with client.session_transaction() as s:token=s['form_token']
    client.post('/upload',data={'form_token':token,'mode':'clustering','dataset':(io.BytesIO(b'x\n1\n2\n'),'source.csv')},content_type='multipart/form-data')
    assert 'value="false" selected' in client.get('/configure').text
    client.post('/configure',data={'form_token':token,'scale_sensitive':'false'})
    assert 'value="false" selected' in client.get('/configure').text
