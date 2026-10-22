"""The app's JSON API is a second transport over the classic core flow: same jobs, same rules, tighter access."""
from io import BytesIO
import json
import re

import pandas as pd
import pytest

from datatrust.web import create_app

API = '/api/datatrust/v1'


def _csv(data: dict) -> BytesIO:
    return BytesIO(pd.DataFrame(data).to_csv(index=False).encode('utf-8'))


CLASSIFICATION = {'age': [21, 35, 47, 52, 33, 29, 61, 44] * 5, 'city': ['a', 'b', 'c', 'a', 'b', 'c', 'a', 'b'] * 5,
                  'row_id': list(range(40)), 'label': [0, 1, 0, 0, 1, 0, 0, 1] * 5}
REGRESSION = {'x': [float(i) for i in range(30)], 'z': [i % 4 for i in range(30)], 'y': [2.0 * i + 1 for i in range(30)]}


@pytest.fixture
def app(tmp_path):
    app = create_app(tmp_path / 'jobs', max_upload_mib=1)
    app.config.update(TESTING=True)
    yield app
    app.extensions['confidenceguard_store'].cleanup()
    app.extensions['datatrust_job_store'].cleanup()


def _token(client):
    return client.get(f'{API}/session').json['data']['csrf_token']


def _upload(client, token, data, mode='classification', name='demo.csv'):
    return client.post(f'{API}/core/jobs', data={'mode': mode, 'dataset': (_csv(data), name)},
                       headers={'X-CSRF-Token': token}, content_type='multipart/form-data')


def _post(client, token, path, body=None):
    return client.post(f'{API}{path}', json=body or {}, headers={'X-CSRF-Token': token})


def test_guard_requires_loopback_same_origin_csrf_and_json(app):
    client = app.test_client()
    token = _token(client)
    assert _post(client, '', '/core/job/new').status_code == 403
    assert _post(client, 'wrong', '/core/job/new').status_code == 403
    assert client.get(f'{API}/session', headers={'Host': 'evil.example'}).status_code == 403
    assert client.get(f'{API}/session', headers={'Origin': 'http://evil.example'}).status_code == 403
    assert client.get(f'{API}/session', headers={'Sec-Fetch-Site': 'cross-site'}).status_code == 403
    form = client.post(f'{API}/core/job/new', data={'x': '1'}, headers={'X-CSRF-Token': token})
    assert form.status_code == 415
    good = _post(client, token, '/core/job/new')
    assert good.status_code == 200 and good.headers['Cache-Control'] == 'no-store' and good.headers['X-Frame-Options'] == 'DENY'
    # The API token is its own secret; the classic form token does not open the API.
    with client.session_transaction() as state:
        assert state['datatrust_api_csrf'] != state.get('form_token')


def test_classic_form_token_and_confidenceguard_bypass_are_unchanged(app):
    client = app.test_client()
    client.get('/')
    assert client.post('/upload', data={'mode': 'classification'}).status_code == 400
    cg = client.get('/api/confidenceguard/v1/session').json['data']['csrf_token']
    created = client.post('/api/confidenceguard/v1/sources', json={'root_id': 'root_9', 'relative_path': 'x.csv'}, headers={'X-CSRF-Token': cg})
    assert created.status_code == 422  # reached CG's own validation, not the form-token hook
    assert client.get('/confidenceguard').status_code == 200


def test_core_classification_flow_and_session_ownership(app):
    owner, stranger = app.test_client(), app.test_client()
    token = _token(owner)
    created = _upload(owner, token, CLASSIFICATION)
    assert created.status_code == 201
    job = created.json['data']['job']
    assert job['stage'] == 'configure' and job['inspection']['row_count'] == 40
    assert {o['name'] for o in job['inspection']['target_options']} >= {'label', 'city'}
    preview = owner.get(f'{API}/core/job/target-preview?target=label').json['data']['target_info']
    assert preview['classification_subtype'] == 'binary' and owner.get(f'{API}/core/job/target-preview?target=nope').status_code == 422
    configured = _post(owner, token, '/core/job/configure', {'target': 'label', 'dataset_name': 'Demo', 'purpose': ''})
    assert configured.json['data']['next'] == 'confirm'
    assert configured.json['data']['job']['target_info']['classification_subtype'] == 'binary'
    report = _post(owner, token, '/core/job/generate')
    view = report.json['data']['job']
    assert view['stage'] == 'report' and view['artifacts'] == ['html', 'json']
    assert view['summary']['overall'] is not None
    analysis = owner.get(f'{API}/core/job/analysis')
    assert analysis.status_code == 200 and analysis.json['scoring']['status'] == 'computed'
    assert owner.get('/report').status_code == 200 and owner.get('/download/json').status_code == 200
    # Another browser session sees nothing of it.
    _token(stranger)
    assert stranger.get(f'{API}/core/job').json['data']['job'] is None
    assert stranger.get(f'{API}/core/job/analysis').status_code == 404
    assert stranger.get('/report').status_code == 404
    # Job views carry filenames only, never workspace paths.
    assert str(app.extensions['datatrust_job_store'].root) not in json.dumps(view)


def test_errors_keep_classic_messages(app):
    client = app.test_client()
    token = _token(client)
    bad = client.post(f'{API}/core/jobs', data={'mode': 'classification', 'dataset': (BytesIO(b'a,b\n1,2\n'), 'notes.txt')},
                      headers={'X-CSRF-Token': token}, content_type='multipart/form-data')
    assert bad.status_code == 422 and bad.json['error']['message'] == 'DataTrust accepts .csv files only.'
    big = client.post(f'{API}/core/jobs', data={'mode': 'classification', 'dataset': (BytesIO(b'a\n' + b'1\n' * 600_000), 'big.csv')},
                      headers={'X-CSRF-Token': token}, content_type='multipart/form-data')
    assert big.status_code == 413 and big.json['error']['message'] == 'CSV exceeds the 1 MiB local UI limit.'
    assert _post(client, token, '/core/job/generate').json['error']['message'] == 'That analysis session is no longer available. Upload the CSV again.'
    _upload(client, token, CLASSIFICATION)
    missing = _post(client, token, '/core/job/configure', {'target': 'nope'})
    assert missing.json['error'] == {**missing.json['error'], 'message': 'Choose a target column from the uploaded dataset.', 'back': 'configure'}
    assert _post(client, token, '/core/job/configure', {'target': 1}).status_code == 422
    early = _post(client, token, '/core/job/generate')
    assert early.json['error']['message'] == 'Confirm the target before generating the report.'


def test_advanced_target_requires_acknowledgement(app):
    client = app.test_client()
    token = _token(client)
    _upload(client, token, CLASSIFICATION)
    configured = _post(client, token, '/core/job/configure', {'target': 'row_id'})
    assert configured.json['data']['job']['target_info']['suitability']['requires_override'] is True
    refused = _post(client, token, '/core/job/generate')
    assert refused.status_code == 422 and refused.json['error']['back'] == 'confirm'
    assert refused.json['error']['message'] == 'Confirm that you still want to use this advanced choice as the prediction outcome.'
    assert _post(client, token, '/core/job/generate', {'advanced_target_ack': 'confirmed'}).json['data']['job']['stage'] == 'report'


def test_regression_source_change_is_refused(app):
    client = app.test_client()
    token = _token(client)
    _upload(client, token, REGRESSION, mode='regression')
    configured = _post(client, token, '/core/job/configure', {'target': 'y', 'regression_options_submitted': '1', 'target_kind': 'unspecified'})
    assert configured.json['data']['next'] == 'confirm'
    job = app.extensions['datatrust_job_store'].get(next(iter(app.extensions['datatrust_job_store'].jobs)))
    job['dataset_path'].write_text(job['dataset_path'].read_text().replace('59.0', '60.0'))
    changed = _post(client, token, '/core/job/generate')
    assert changed.status_code == 422 and changed.json['error']['message'] == 'Source changed since regression confirmation; review the target again.'
    assert client.get(f'{API}/core/job').json['data']['job']['stage'] == 'configure'


VOLATILE = re.compile(r'"(generated_at|elapsed_seconds|frame_bytes|peak_[a-z_]+|[a-z_]*_ns)": [^,}\]]+')


def _canonical(text):
    return VOLATILE.sub(r'"\1": "*"', text)


@pytest.mark.parametrize('mode,data,fields', [
    ('classification', CLASSIFICATION, {'target': 'label'}),
    ('regression', REGRESSION, {'target': 'y', 'regression_options_submitted': '1', 'target_kind': 'unspecified'}),
    ('unlabeled', CLASSIFICATION, {}),
])
def test_api_and_classic_produce_the_same_canonical_report(app, mode, data, fields):
    classic, api = app.test_client(), app.test_client()
    classic.get('/')
    with classic.session_transaction() as state:
        form_token = state['form_token']
    classic.post('/upload', data={'form_token': form_token, 'mode': mode, 'dataset': (_csv(data), 'same.csv')}, content_type='multipart/form-data')
    classic.post('/configure', data={'form_token': form_token, 'dataset_name': 'Same', 'purpose': '', **fields})
    assert classic.post('/generate', data={'form_token': form_token}).headers['Location'].endswith('/result')
    token = _token(api)
    _upload(api, token, data, mode=mode, name='same.csv')
    _post(api, token, '/core/job/configure', {'dataset_name': 'Same', 'purpose': '', **fields})
    assert _post(api, token, '/core/job/generate').json['data']['job']['stage'] == 'report'
    assert _canonical(classic.get('/download/json').get_data(as_text=True)) == _canonical(api.get('/download/json').get_data(as_text=True))
    html_classic, html_api = classic.get('/report').get_data(as_text=True), api.get('/report').get_data(as_text=True)
    stamp = re.compile(r'\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:?\d{2})?|\d+\.\d+ ?s(econds)?\b')
    assert stamp.sub('*', html_classic) == stamp.sub('*', html_api)


def test_client_bundle_is_served_under_a_strict_policy(app):
    response = app.test_client().get('/app/history')
    assert response.status_code in {200, 503}
    assert "frame-ancestors 'none'" in response.headers['Content-Security-Policy']
    assert response.headers['Referrer-Policy'] == 'no-referrer'


M3 = {'x': [1.0, 2.5, 3.0, 4.5, 5.0, 6.5, 7.0, 8.5] * 4, 'code': [1, 2, 3, 1, 2, 3, 1, 2] * 4, 'y': ['a', 'b', 'a', 'b', '', 'a', 'b', 'a'] * 4}


def test_m3_modes_need_the_representation_acknowledgement(app):
    client = app.test_client()
    token = _token(client)
    created = _upload(client, token, M3, mode='annotation_classification')
    assert created.status_code == 201 and created.json['data']['job']['m3']['task'] is None
    fields = {'role_x': 'feature', 'role_code': 'feature', 'role_y': 'target', 'semantic_code': 'categorical', 'annotation_expectation': 'expected', 'dataset_name': 'Annotated'}
    configured = _post(client, token, '/core/job/configure', fields).json['data']
    assert configured['next'] == 'confirm' and configured['job']['target_info']['roles']['targets'] == ['y']
    assert configured['job']['m3']['semantic_types'] == {'code': 'categorical'}
    refused = _post(client, token, '/core/job/generate')
    assert refused.status_code == 422 and refused.json['error']['message'] == 'Confirm the representation assumptions before generating the report.'
    assert _post(client, token, '/core/job/generate', {'representation_ack': 'confirmed'}).json['data']['job']['stage'] == 'report'
    bad = _post(client, token, '/core/job/configure', {'role_x': 'owner'})
    assert bad.status_code == 422 and bad.json['error']['message'] == 'Invalid column role.'


@pytest.mark.parametrize('mode,fields', [
    ('clustering', {'role_x': 'feature', 'role_code': 'feature', 'role_y': 'metadata', 'scale_sensitive': 'true'}),
    ('annotation_classification', {'role_x': 'feature', 'role_code': 'feature', 'role_y': 'target', 'annotation_expectation': 'unknown'}),
])
def test_m3_api_and_classic_produce_the_same_canonical_report(app, mode, fields):
    classic, api = app.test_client(), app.test_client()
    classic.get('/')
    with classic.session_transaction() as state:
        form_token = state['form_token']
    classic.post('/upload', data={'form_token': form_token, 'mode': mode, 'dataset': (_csv(M3), 'm3.csv')}, content_type='multipart/form-data')
    classic.post('/configure', data={'form_token': form_token, 'dataset_name': 'M3', **fields})
    assert classic.post('/generate', data={'form_token': form_token, 'representation_ack': 'confirmed'}).headers['Location'].endswith('/result')
    token = _token(api)
    _upload(api, token, M3, mode=mode, name='m3.csv')
    _post(api, token, '/core/job/configure', {'dataset_name': 'M3', **fields})
    assert _post(api, token, '/core/job/generate', {'representation_ack': 'confirmed'}).json['data']['job']['stage'] == 'report'
    assert _canonical(classic.get('/download/json').get_data(as_text=True)) == _canonical(api.get('/download/json').get_data(as_text=True))


def test_target_preview_sends_only_the_most_frequent_classes(app):
    client = app.test_client()
    token = _token(client)
    many = {'id': [f'row{i}' for i in range(300)], 'label': ['a', 'b', 'c'] * 100}
    assert _upload(client, token, many).status_code == 201
    info = client.get(f'{API}/core/job/target-preview?target=id').json['data']['target_info']
    assert info['class_count'] == 300 and len(info['target_distribution']) == 50
