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


def test_reports_are_served_for_the_viewer_under_a_load_nothing_policy(app):
    """Report Experience Stage 7: the app viewer's report responses, and the guide its deep link opens."""
    from datatrust.api_web import REPORT_CSP
    from datatrust.report_format import report_csp
    client = app.test_client()
    token = _token(client)
    _upload(client, token, CLASSIFICATION)
    _post(client, token, '/core/job/configure', {'target': 'label', 'dataset_name': 'Demo', 'purpose': ''})
    _post(client, token, '/core/job/generate')
    response = client.get(f'{API}/core/job/report')
    assert response.status_code == 200 and response.headers['X-Frame-Options'] == 'SAMEORIGIN'
    assert response.headers['Content-Security-Policy'] == REPORT_CSP and response.headers['Referrer-Policy'] == 'no-referrer'
    for directive in ("default-src 'none'", 'img-src data:', "base-uri 'none'", "form-action 'none'", "frame-ancestors 'self'"):
        assert directive in REPORT_CSP
    html = response.get_data(as_text=True)
    assert 'id="understand"' in html and report_csp() in html.replace('&#39;', "'")   # the hash-pinned meta policy still applies
    assert "location.hash === '#understand'" in html and "addEventListener('hashchange'" in html


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


def test_the_csrf_token_is_minted_with_the_app_document_never_by_concurrent_api_requests(app):
    # The app document mints the token before any script runs, so every API request the page makes already carries it.
    page = app.test_client()
    page.get('/app/')
    with page.session_transaction() as state:
        minted = state['datatrust_api_csrf']
    assert _token(page) == minted
    assert _post(page, minted, '/core/job/new').status_code == 200

    # A cookie-less API request (the race on a cold load) no longer mints a token of its own: before, two concurrent
    # first requests each minted one, and the cookie the browser kept last no longer matched the page's token.
    cold = app.test_client()
    assert cold.get(f'{API}/core/job').status_code == 200
    with cold.session_transaction() as state:
        assert 'datatrust_api_csrf' not in state


def test_a_missing_or_stale_csrf_token_is_refused_with_a_code_the_client_can_recover_from(app):
    client = app.test_client()
    stale = _token(client)
    with client.session_transaction() as state:  # the session was replaced, as when another tab reset the cookie
        state.clear()
    refused = _post(client, stale, '/core/job/new')
    assert refused.status_code == 403 and refused.json['error']['code'] == 'csrf'
    # The client refetches the session's token and sends the same request once more (api.ts `call`).
    assert _post(client, _token(client), '/core/job/new').status_code == 200


# Stage 3: upload first, choose the analysis afterwards ----------------------------------------------------------------

def _upload_only(client, token, data, name='same.csv'):
    return client.post(f'{API}/core/uploads', data={'dataset': (_csv(data), name)}, headers={'X-CSRF-Token': token},
                       content_type='multipart/form-data')


M3_ALL = {'x': [1.0, 2.5, 3.0, 4.5, 5.0, 6.5, 7.0, 8.5] * 4, 'z': [0.5, 1.5, 9.0, 2.0, 3.5, 4.0, 7.5, 6.0] * 4,
          'a': [0, 1, 0, 1, 1, 0, 0, 1] * 4, 'b': [1, 1, 0, 0, 1, 0, 1, 0] * 4}
PATHS = [
    ('classification', CLASSIFICATION, {'target': 'label'}),
    ('regression', REGRESSION, {'target': 'y', 'regression_options_submitted': '1', 'target_kind': 'unspecified'}),
    ('unlabeled', CLASSIFICATION, {}),
    ('annotation_classification', M3_ALL, {'role_x': 'feature', 'role_z': 'feature', 'role_a': 'target', 'role_b': 'metadata', 'annotation_expectation': 'unknown'}),
    ('annotation_regression', M3_ALL, {'role_x': 'feature', 'role_z': 'target', 'role_a': 'feature', 'role_b': 'metadata', 'annotation_expectation': 'unknown'}),
    ('multilabel_classification', M3_ALL, {'role_x': 'feature', 'role_z': 'feature', 'role_a': 'target', 'role_b': 'target', 'annotation_expectation': 'unknown'}),
    ('clustering', M3_ALL, {'role_x': 'feature', 'role_z': 'feature', 'role_a': 'metadata', 'role_b': 'metadata', 'scale_sensitive': 'true'}),
    ('anomaly_detection', M3_ALL, {'role_x': 'feature', 'role_z': 'feature', 'role_a': 'metadata', 'role_b': 'metadata', 'scale_sensitive': 'false'}),
    ('role_profile', M3_ALL, {'role_x': 'feature', 'role_z': 'metadata', 'role_a': 'ignored', 'role_b': 'feature'}),
]


@pytest.mark.parametrize('mode,data,fields', PATHS, ids=[p[0] for p in PATHS])
def test_choosing_the_analysis_after_upload_gives_the_same_analysis(app, mode, data, fields):
    one, two = app.test_client(), app.test_client()
    ack = {'representation_ack': 'confirmed'} if mode in {'annotation_classification', 'annotation_regression', 'multilabel_classification',
                                                          'clustering', 'anomaly_detection', 'role_profile'} else {}
    t1 = _token(one)
    assert _upload(one, t1, data, mode=mode, name='same.csv').status_code == 201
    assert _post(one, t1, '/core/job/configure', {'dataset_name': 'Same', 'purpose': '', **fields}).status_code == 200
    assert _post(one, t1, '/core/job/generate', ack).json['data']['job']['stage'] == 'report'
    t2 = _token(two)
    uploaded = _upload_only(two, t2, data)
    assert uploaded.status_code == 201 and uploaded.json['data']['job']['stage'] == 'choose'
    if mode != 'unlabeled':  # first choose something else, then change it: no upload needed
        assert _post(two, t2, '/core/job/analysis', {'mode': 'unlabeled'}).status_code == 200
    assert _post(two, t2, '/core/job/analysis', {'mode': mode}).json['data']['job']['stage'] == 'configure'
    assert _post(two, t2, '/core/job/configure', {'dataset_name': 'Same', 'purpose': '', **fields}).status_code == 200
    assert _post(two, t2, '/core/job/generate', ack).json['data']['job']['stage'] == 'report'
    left, right = (c.get(f'{API}/core/job/analysis').get_data(as_text=True) for c in (one, two))
    assert _canonical(left) == _canonical(right)


def test_an_upload_alone_is_neither_configured_nor_run(app):
    client = app.test_client()
    token = _token(client)
    job = _upload_only(client, token, CLASSIFICATION).json['data']['job']
    assert job['stage'] == 'choose' and job['mode'] is None
    assert job['input_inspection']['version'] == 'input_inspection_v1' and job['input_inspection']['coverage']['complete']
    for path in ('/core/job/configure', '/core/job/generate'):
        refused = _post(client, token, path, {'target': 'label'})
        assert refused.status_code == 422 and refused.json['error']['message'] == 'Choose an analysis for this file first.'
    bad = _post(client, token, '/core/job/analysis', {'mode': 'temporal'})
    assert bad.status_code == 422 and bad.json['error']['message'] == 'Choose one of the listed analyses.'
    assert client.get(f'{API}/core/job').json['data']['job']['stage'] == 'choose'
    classic = client.get('/configure')
    assert classic.status_code == 302 and classic.headers['Location'].endswith('/')


def test_changing_the_analysis_clears_declarations_and_keeps_the_file_and_inspection(app):
    client = app.test_client()
    token = _token(client)
    _upload_only(client, token, CLASSIFICATION)
    first = _post(client, token, '/core/job/analysis', {'mode': 'classification'}).json['data']['job']
    _post(client, token, '/core/job/configure', {'target': 'label', 'dataset_name': 'Kept?'})
    assert client.get(f'{API}/core/job').json['data']['job']['stage'] == 'confirm'
    changed = _post(client, token, '/core/job/analysis', {'mode': 'regression'}).json['data']['job']
    assert changed['stage'] == 'configure' and changed['mode'] == 'regression' and changed.get('target_info') is None
    assert changed['input_inspection'] == first['input_inspection']  # same parse profile: reused
    assert changed['source_filename'] == first['source_filename']


# Stage 4b: the review shows the methodology the run records ---------------------------------------------------------

def _analysis(client):
    return json.loads(client.get(f'{API}/core/job/analysis').get_data(as_text=True))


@pytest.mark.parametrize('mode,data,fields', PATHS, ids=[p[0] for p in PATHS])
def test_the_review_names_the_methodology_the_run_records(app, mode, data, fields):
    client = app.test_client()
    token = _token(client)
    _upload_only(client, token, data)
    _post(client, token, '/core/job/analysis', {'mode': mode})
    review = _post(client, token, '/core/job/configure', {'dataset_name': 'Same', 'purpose': '', **fields}).json['data']['job']['review']
    ack = {} if mode in {'classification', 'regression', 'unlabeled'} else {'representation_ack': 'confirmed'}
    assert _post(client, token, '/core/job/generate', ack).json['data']['job']['stage'] == 'report'
    assert review['methodology'] == _analysis(client)['methodology_id'] and review['name']


@pytest.mark.parametrize('expectation,method', [('unknown', 'tabular_partial_classification_v1'), ('expected', 'classification_legacy_2026_08_13')])
def test_the_role_aware_switch_keeps_the_target_and_the_review_states_the_method(app, expectation, method):
    client = app.test_client()
    token = _token(client)
    _upload_only(client, token, CLASSIFICATION)
    _post(client, token, '/core/job/analysis', {'mode': 'classification'})
    switched = _post(client, token, '/core/job/analysis', {'mode': 'annotation_classification', 'target': 'label'}).json['data']['job']
    assert switched['m3']['task']['targets'] == ['label'] and switched['m3']['task']['features'] is None
    fields = {'role_label': 'target', 'role_row_id': 'metadata', 'annotation_expectation': expectation}
    if expectation == 'expected':
        fields['role_row_id'] = 'feature'  # nothing beyond the scored method's own declarations: the scored method runs
    review = _post(client, token, '/core/job/configure', fields).json['data']['job']['review']
    assert review['methodology'] == method and review['scored'] == (method == 'classification_legacy_2026_08_13')
    _post(client, token, '/core/job/generate', {'representation_ack': 'confirmed'})
    assert _analysis(client)['methodology_id'] == method


def test_bulk_availability_is_listed_apart_and_never_reaches_the_analysis(app):
    client = app.test_client()
    token = _token(client)
    _upload_only(client, token, REGRESSION)
    _post(client, token, '/core/job/analysis', {'mode': 'regression'})
    fields = {'target': 'y', 'regression_options_submitted': '1', 'target_kind': 'unspecified', 'availability_x': 'available_at_prediction',
              'availability_z': 'available_at_prediction', 'availability_bulk': json.dumps(['x', 'nope'])}
    review = _post(client, token, '/core/job/configure', fields).json['data']['job']['review']
    assert review['availability']['available'] == ['x', 'z'] and review['availability']['bulk'] == ['x'] and review['availability']['consequence']
    assert review['availability']['unknown'] == 0 and any('prediction point' in u for u in review['unknowns'])
    _post(client, token, '/core/job/generate')
    assert 'availability_bulk' not in json.dumps(_analysis(client))
