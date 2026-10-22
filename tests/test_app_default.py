"""The DataTrust app is the interface: classic pages are retired, the app works on its own, ConfidenceGuard is untouched."""
import io

import pytest

from datatrust.web import create_app

API = '/api/datatrust/v1'
CSV = 'age,income,label\n' + ''.join(f'{20 + i % 40},{1000 + i * 7},{"yes" if i % 3 else "no"}\n' for i in range(60))


@pytest.fixture
def app(tmp_path):
    app = create_app(tmp_path / 'jobs', data_roots=(tmp_path,), classic_ui=False)
    app.config.update(TESTING=True)
    yield app
    app.extensions['confidenceguard_store'].cleanup()
    app.extensions['datatrust_job_store'].cleanup()


@pytest.mark.parametrize('path,target', [
    ('/', '/app/'), ('/result', '/app/'), ('/download/pdf', '/app/'), ('/m4', '/app/m4/sources'), ('/m4/result', '/app/m4/sources'),
    ('/temporal', '/app/temporal/sources'), ('/text/configure', '/app/text/sources'), ('/images', '/app/images/sources'),
    ('/cross-representation/configure', '/app/cross/sources'),
])
def test_classic_pages_lead_to_the_app(app, path, target):
    response = app.test_client().get(path)
    assert response.status_code == 302 and response.headers['Location'] == target


def test_classic_form_posts_no_longer_exist(app):
    client = app.test_client()
    with client.session_transaction() as state:
        state['form_token'] = 'known'
    for path in ('/upload', '/configure', '/new', '/m4', '/temporal/run', '/text/evidence', '/images/run', '/cross-representation/configure'):
        assert client.post(path, data={}).status_code == 400, path  # the form-token check still answers first
        assert client.post(path, data={'form_token': 'known'}).status_code == 404, path


def test_the_app_runs_an_analysis_and_serves_every_artifact_itself(app):
    client = app.test_client()
    assert client.get('/app/').status_code == 200
    token = client.get(f'{API}/session').json['data']['csrf_token']
    created = client.post(f'{API}/core/jobs', data={'mode': 'classification', 'dataset': (io.BytesIO(CSV.encode()), 'demo.csv')},
                          headers={'X-CSRF-Token': token}, content_type='multipart/form-data')
    assert created.status_code == 201
    post = lambda path, body: client.post(f'{API}{path}', json=body, headers={'X-CSRF-Token': token})
    assert post('/core/job/configure', {'dataset_name': 'Demo', 'purpose': '', 'target': 'label'}).status_code == 200
    assert post('/core/job/generate', {}).status_code == 200
    report = client.get(f'{API}/core/job/report')
    assert report.status_code == 200 and report.headers['X-Frame-Options'] == 'SAMEORIGIN'
    html = client.get(f'{API}/core/job/download/html')
    assert html.status_code == 200 and 'attachment' in html.headers['Content-Disposition'] and 'Demo-reliability-report.html' in html.headers['Content-Disposition']
    assert client.get(f'{API}/core/job/download/json').headers['Content-Disposition'].endswith('datatrust-analysis.json')
    pdf = client.get(f'{API}/core/job/download/pdf')
    assert pdf.status_code == 200 and pdf.data.startswith(b'%PDF')
    assert client.get(f'{API}/core/job/download/exe').status_code == 404
    assert app.test_client().get(f'{API}/core/job/download/json').status_code in {400, 404}  # another session owns nothing


def test_confidenceguard_keeps_its_page_api_and_own_csrf(app):
    client = app.test_client()
    assert client.get('/confidenceguard').status_code == 200
    assert client.get('/confidenceguard/assets/client.js').status_code == 200
    session = client.get('/api/confidenceguard/v1/session').json['data']
    refused = client.post('/api/confidenceguard/v1/sources', json={'root_id': 'root_0', 'relative_path': 'x.csv'})
    assert refused.status_code in {400, 403}  # its own token is still required
    reached = client.post('/api/confidenceguard/v1/sources', json={'root_id': 'root_9', 'relative_path': 'x.csv'}, headers={'X-CSRF-Token': session['csrf_token']})
    assert reached.status_code == 422  # its own validation, not the retired-page hook
    assert client.get('/').headers['Location'] == '/app/'  # its "DataTrust" link now lands in the app
