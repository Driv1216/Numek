import json
import os
from io import BytesIO
from pathlib import Path

import pytest
from click.testing import CliRunner
from pypdf import PdfReader

from datatrust import DataTrust, DatasetSpec, TaskSpec
from datatrust.cli import main
from datatrust.pdf import PDFRenderError
from datatrust.renderer import ArtifactCollisionError, publish_bytes
from datatrust.web import create_app


def completed(tmp_path):
    path=tmp_path/'source.csv';path.write_text('identifier,value,label\n001,1,NA\n002,2,ok\n003,3,yes\n004,100,no\n')
    return DataTrust.from_spec(DatasetSpec(path),TaskSpec('dataset_profile')).analyze_result()


def test_real_bundle_content_discovery_reuse_and_no_reanalysis(tmp_path,monkeypatch):
    r=completed(tmp_path)
    monkeypatch.setattr(DataTrust,'analyze_result',lambda _: pytest.fail('completed export reanalyzed'))
    artifacts=r.generate_artifacts(tmp_path/'report.pdf',format='pdf',json_path=tmp_path/'analysis.json')
    assert artifacts.html_path==str(tmp_path/'report.html') and artifacts.pdf_path==str(tmp_path/'report.pdf')
    assert json.loads(Path(artifacts.json_path).read_text())==r.to_dict()
    pdf=PdfReader(artifacts.pdf_path);text='\n'.join(page.extract_text() or '' for page in pdf.pages)
    for heading in ['1. Review Summary','2. Priority Review Actions','3. Dataset and Parsing Overview','4. Missingness','5. Duplicate and Column Evidence','6. Numeric Evidence','7. Coverage, Methods, and Limitations','8. Technical Appendix']:
        assert heading in text
    assert 'leading_zero_numeric_conversion' in text and 'Source SHA-256' in text
    assert 'Overall reliability score' not in text and 'Risk' not in text
    assert str(tmp_path) not in Path(artifacts.html_path).read_text()
    identity=Path(artifacts.html_path).stat()
    reused=r.generate_artifacts(tmp_path/'second.pdf',format='pdf',html_path=artifacts.html_path)
    assert reused.reused_html and Path(artifacts.html_path).stat()==identity


@pytest.mark.parametrize('kind',['html','pdf','json','directory','symlink'])
def test_unrelated_destinations_are_never_overwritten(tmp_path,kind):
    r=completed(tmp_path);html=tmp_path/'report.html';pdf=tmp_path/'report.pdf';js=tmp_path/'analysis.json'
    occupied={'html':html,'pdf':pdf,'json':js,'directory':html,'symlink':html}[kind]
    if kind=='directory':occupied.mkdir()
    elif kind=='symlink':occupied.symlink_to(tmp_path/'nonexistent')
    else:occupied.write_bytes(b'unrelated')
    with pytest.raises(ArtifactCollisionError):r.generate_artifacts(pdf,format='pdf',json_path=js)
    if kind in {'html','pdf','json'}:assert occupied.read_bytes()==b'unrelated'
    assert not (tmp_path/'.pdf.tmp').exists()


@pytest.mark.parametrize('alias',['same','symlink','hardlink'])
def test_source_aliases_and_duplicate_destinations_rejected(tmp_path,alias):
    r=completed(tmp_path);source=Path(r.dataset.path);out=tmp_path/'alias.html'
    if alias=='same':out=source
    elif alias=='symlink':out.symlink_to(source)
    else:os.link(source,out)
    before=source.read_bytes()
    with pytest.raises(ArtifactCollisionError):r.generate_artifacts(out)
    with pytest.raises(ArtifactCollisionError):DataTrust(source,'label').generate_report(out)
    assert source.read_bytes()==before
    with pytest.raises(ArtifactCollisionError):r.generate_artifacts(tmp_path/'same.pdf',format='pdf',html_path=tmp_path/'same.pdf')


def test_no_replace_publication_handles_concurrent_creator_and_owned_cleanup(tmp_path,monkeypatch):
    dest=tmp_path/'report.pdf';unowned=tmp_path/'report.pdf.tmp';unowned.write_bytes(b'keep')
    original=os.link
    def competing(source,target):
        Path(target).write_bytes(b'concurrent unrelated');return original(source,target)
    monkeypatch.setattr('datatrust.renderer.os.link',competing)
    with pytest.raises(ArtifactCollisionError):publish_bytes(dest,b'ours')
    assert dest.read_bytes()==b'concurrent unrelated' and unowned.read_bytes()==b'keep'
    assert not list(tmp_path.glob('.datatrust-*.tmp'))


def test_pdf_failure_retains_html_json_and_exposes_artifacts(tmp_path,monkeypatch):
    r=completed(tmp_path)
    def fail(*args,**kwargs):raise PDFRenderError('Conversion failed. The HTML report is still available.')
    monkeypatch.setattr('datatrust.pdf.render_pdf_report',fail)
    with pytest.raises(PDFRenderError) as failure:r.generate_artifacts(tmp_path/'report.pdf',format='pdf',json_path=tmp_path/'analysis.json')
    artifacts=failure.value.artifacts
    assert Path(artifacts.html_path).exists() and Path(artifacts.json_path).exists() and artifacts.pdf_path is None
    assert artifacts.html_path in str(failure.value)
    assert not (tmp_path/'report.pdf').exists()


def test_legacy_explicit_html_overwrite_and_modern_class_disclosure(tmp_path):
    r=completed(tmp_path);audit=DataTrust(r.dataset.path,'label');out=tmp_path/'legacy.html';out.write_text('old report')
    assert audit.generate_report(out)==str(out)
    assert '8. Technical Appendix' in out.read_text() and 'Parsing, execution, and coverage disclosure' not in out.read_text()
    modern=DataTrust.from_spec(DatasetSpec(r.dataset.path),TaskSpec('classification','label')).analyze_result()
    artifacts=modern.generate_artifacts(tmp_path/'modern.html')
    assert 'Parsing, execution, and coverage disclosure' in Path(artifacts.html_path).read_text()
    assert '1. Decision Summary' in Path(artifacts.html_path).read_text()


def test_cli_conditional_target_config_and_artifact_paths(tmp_path):
    r=completed(tmp_path);runner=CliRunner()
    config=tmp_path/'options.json';config.write_text(json.dumps({'parsing':{'column_types':{'identifier':'string'},'missing_policy':'empty_only'}}))
    args=['audit',str(r.dataset.path),'--task','unlabeled','--out',str(tmp_path/'cli.html'),'--json-out',str(tmp_path/'cli.json'),'--config',str(config)]
    output=runner.invoke(main,args)
    assert output.exit_code==0,output.output
    assert 'HTML report:' in output.output and 'JSON report:' in output.output
    data=json.loads((tmp_path/'cli.json').read_text())
    assert data['scoring']['values'] is None and data['parsing_warnings']==[]
    for task_args, message in [([], 'requires an explicit target'), (['--task','unlabeled','--target','label'],'does not accept a target')]:
        output=runner.invoke(main,['audit',str(r.dataset.path),'--out',str(tmp_path/'error.html')]+task_args)
        assert output.exit_code!=0 and message in output.output


def test_cli_partial_execution_is_nonzero_but_reports_survive(tmp_path,monkeypatch):
    r=completed(tmp_path)
    def fail(_):raise RuntimeError('duplicate check failed')
    monkeypatch.setattr('datatrust.core.exact_duplicate_evidence',fail)
    output=CliRunner().invoke(main,['audit',str(r.dataset.path),'--task','unlabeled','--out',str(tmp_path/'partial.html')])
    assert output.exit_code==2 and 'Analysis incomplete' in output.output and (tmp_path/'partial.html').exists()


def browser(tmp_path):
    app=create_app(tmp_path/'jobs');app.config['TESTING']=True;client=app.test_client();client.get('/')
    with client.session_transaction() as s:token=s['form_token']
    raw=b'identifier,value,label\n001,1,NA\n002,2,ok\n003,3,yes\n004,100,no\n'
    response=client.post('/upload',data={'form_token':token,'mode':'unlabeled','dataset':(BytesIO(raw),'demo.csv')},content_type='multipart/form-data',follow_redirects=True)
    assert response.status_code==200 and b'leading_zero_numeric_conversion' in response.data
    assert b'What outcome is this dataset meant to predict?' not in response.data
    with client.session_transaction() as s:job=app.extensions['datatrust_job_store'].get(s['job_id'])
    return app,client,token,job,raw


def test_unlabeled_browser_full_workflow_preview_json_pdf_and_identity(tmp_path,monkeypatch):
    app,client,token,job,raw=browser(tmp_path)
    fields={'form_token':token,'dataset_name':'<b>Review</b>','missing_policy':'empty_only','column_types':'{"identifier":"string"}','na_values':'[]','encoding':'utf-8'}
    preview=client.post('/configure',data={**fields,'action':'preview'},follow_redirects=True)
    assert b'&lt;b&gt;Review&lt;/b&gt;' in preview.data and b'leading_zero_numeric_conversion' not in preview.data
    confirm=client.post('/configure',data=fields,follow_redirects=True)
    assert b'Unlabeled CSV profiling' in confirm.data and b'Operational safeguards' in confirm.data
    generated=client.post('/generate',data={'form_token':token},follow_redirects=True)
    assert b'Priority review findings' in generated.data and b'Overall reliability score' not in generated.data
    assert b'Download HTML' in generated.data and b'Download JSON' in generated.data
    data=client.get('/download/json').json
    api=DataTrust.from_spec(DatasetSpec(job['dataset_path']),TaskSpec('dataset_profile'),job['config']).analyze_result()
    assert data['profile']==api.to_dict()['profile'] and data['evidence']==api.to_dict()['evidence']
    assert all(not isinstance(v,__import__('pandas').DataFrame) for v in job.values())
    pdf=client.get('/download/pdf');assert pdf.status_code==200 and pdf.data.startswith(b'%PDF')
    assert client.get('/download/pdf').data==pdf.data
    assert job['dataset_path'].read_bytes()==raw
    # A familiar filename with a changed identity is never served, replaced, or deleted.
    job['pdf_path'].write_bytes(b'unrelated')
    rejected=client.get('/download/pdf',follow_redirects=True)
    assert b'destination is occupied' in rejected.data and job['pdf_path'].read_bytes()==b'unrelated'
    rejected=client.post('/configure',data=fields,follow_redirects=True)
    assert b'Unrecognized job artifact' in rejected.data and job['pdf_path'].read_bytes()==b'unrelated'


def test_browser_configuration_invalidates_owned_artifacts_and_cache(tmp_path):
    app,client,token,job,raw=browser(tmp_path)
    client.post('/configure',data={'form_token':token})
    client.post('/generate',data={'form_token':token});client.get('/download/pdf')
    paths=[job['report_path'],job['pdf_path'],job['json_path']]
    client.post('/configure',data={'form_token':token,'missing_policy':'empty_only'})
    assert all(not p.exists() for p in paths)
    assert 'analysis_result' not in job and client.get('/download/json').status_code==404
    client.post('/generate',data={'form_token':token})
    assert client.get('/download/pdf').status_code==200


def test_browser_pdf_failure_leaves_available_downloads(tmp_path,monkeypatch):
    app,client,token,job,raw=browser(tmp_path)
    client.post('/configure',data={'form_token':token});client.post('/generate',data={'form_token':token})
    def fail(*args,**kwargs):raise PDFRenderError('PDF generation unavailable. The HTML report is still available.')
    monkeypatch.setattr('datatrust.web.render_pdf_report',fail)
    response=client.get('/download/pdf',follow_redirects=True)
    assert b'HTML report retained at' in response.data
    assert client.get('/download').status_code==200 and client.get('/download/json').status_code==200


def test_cli_pdf_failure_prints_surviving_bundle(tmp_path,monkeypatch):
    r=completed(tmp_path)
    def fail(*args,**kwargs):raise PDFRenderError('Failed conversion; HTML report is still available.')
    monkeypatch.setattr('datatrust.pdf.render_pdf_report',fail)
    result=CliRunner().invoke(main,['audit',str(r.dataset.path),'--task','unlabeled','--format','pdf','--out',str(tmp_path/'cli.pdf'),'--json-out',str(tmp_path/'cli.json')])
    assert result.exit_code!=0 and f'HTML report: {tmp_path / "cli.html"}' in result.output
    assert f'JSON report: {tmp_path / "cli.json"}' in result.output


def test_relative_source_stays_protected_after_working_directory_changes(tmp_path,monkeypatch):
    source=tmp_path/'source.csv';source.write_text('v\n1\n2\n')
    monkeypatch.chdir(tmp_path)
    r=DataTrust.from_spec(DatasetSpec('source.csv'),TaskSpec('dataset_profile')).analyze_result()
    other=tmp_path/'other';other.mkdir();monkeypatch.chdir(other)
    with pytest.raises(ArtifactCollisionError):r.generate_artifacts(source)
    assert source.read_text()=='v\n1\n2\n'


def test_pdf_detects_canonical_html_change_before_publication(tmp_path,monkeypatch):
    from datatrust.pdf import render_pdf_report
    import weasyprint
    html=tmp_path/'source.html';html.write_text('<p>original</p>')
    def changed(*args,**kwargs):html.write_text('<p>modified</p>');return b'%PDF'
    monkeypatch.setattr(weasyprint.HTML,'write_pdf',changed)
    with pytest.raises(PDFRenderError,match='changed during conversion'):render_pdf_report(html,tmp_path/'report.pdf')
    assert not (tmp_path/'report.pdf').exists()


def test_browser_session_isolation_and_unrecognized_artifact_refusal(tmp_path):
    app,client,token,job,raw=browser(tmp_path)
    client.post('/configure',data={'form_token':token})
    stranger=app.test_client();stranger.get('/')
    assert stranger.get('/download/json').status_code==404
    report=job['directory']/'report.html';report.write_text('unrelated report')
    response=client.post('/generate',data={'form_token':token},follow_redirects=True)
    assert b'destination is occupied' in response.data and report.read_text()=='unrelated report'


def test_memory_failure_aborts_cli_and_ui_without_completed_report(tmp_path,monkeypatch):
    r=completed(tmp_path);app,client,token,job,raw=browser(tmp_path)
    client.post('/configure',data={'form_token':token})
    def oom(*args,**kwargs):raise MemoryError()
    monkeypatch.setattr('datatrust.core.profile_unlabeled_frame',oom)
    response=client.post('/generate',data={'form_token':token},follow_redirects=True)
    assert b'available memory' in response.data and not (job['directory']/'report.html').exists()
    output=CliRunner().invoke(main,['audit',str(r.dataset.path),'--task','unlabeled','--out',str(tmp_path/'oom.html')])
    assert output.exit_code!=0 and 'available memory' in output.output and not (tmp_path/'oom.html').exists()
