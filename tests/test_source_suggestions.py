"""Stage 5a: advisory inspection of comparison (M4) and temporal (M5) sources, through the app API.

- each admitted source carries its bounded inspection; the specification and its fingerprint never include it;
- comparison suggestions: identity keys (R-KEY-1) and name mappings (R-MAP-1);
- temporal suggestions: clock interpretation, entity (R-ENTITY-1 pair test) and inspected spacing; the values the page's
  chips set form a valid specification that runs.
"""
import io
import json

import pandas as pd

from datatrust.web import create_app

API = '/api/datatrust/v1'


class Client:
    def __init__(self, tmp_path):
        root = tmp_path / 'data'
        root.mkdir()
        times = pd.date_range('2024-01-01', periods=72, freq='h').strftime('%Y-%m-%dT%H:%M:%S')
        pd.DataFrame({'time': list(times) * 3, 'station': ['a'] * 72 + ['b'] * 72 + ['c'] * 72, 'wd': ['N', 'S', 'E', 'W'] * 54,
                      'pm25': [float((i * 7) % 41) for i in range(216)]}).to_csv(root / 'panel.csv', index=False)
        self.app = create_app(tmp_path / 'w', data_roots=(root,), launch_token='l')
        self.app.testing = True
        self.client = self.app.test_client()
        self.client.get('/app/?launch=l')
        self.token = self.client.get(f'{API}/session').json['data']['csrf_token']

    def post(self, path, body=None):
        return self.client.post(f'{API}{path}', json=body or {}, headers={'X-CSRF-Token': self.token})

    def upload(self, text, name):
        return self.client.post(f'{API}/m4/sources', data={'dataset': (io.BytesIO(text.encode()), name)}, headers={'X-CSRF-Token': self.token}, content_type='multipart/form-data')

    def close(self):
        for key in ('datatrust_m5_store', 'datatrust_m4_store', 'confidenceguard_store'):
            store = self.app.extensions.get(key)
            if store:
                store.cleanup()


def test_temporal_source_suggestions_form_a_runnable_specification(tmp_path):
    c = Client(tmp_path)
    try:
        c.post('/temporal/start')
        job = c.post('/temporal/sources', {'root_id': 'root_0', 'relative_path': 'panel.csv', 'format': 'csv'}).json['data']['job']
        src = job['sources'][0]
        assert src['inspection']['coverage']['statement'] == 'Inspected all 216 rows.'
        clock = src['time']['clocks'][0]
        assert (clock['column'], clock['kind'], clock['naive']) == ('time', 'local_datetime', True)
        assert [e['column'] for e in src['time']['entities']] == ['station'] and clock['spacing']['label'] == '1 hour'
        assert {'column': 'pm25', 'type': 'quantitative'} in src['time']['measurements']
        # exactly what the chips set, plus the timezone the page asks for
        fields = {'dataset_name': 'Panel', 'source1_role': 'dataset', 'source1_task': 'dataset_profile', 'source1_clock': clock['column'],
                  'source1_clock_kind': clock['kind'], 'source1_encoding': clock['encoding'],
                  'source1_entities': 'station', 'source1_measurements': 'pm25|pm25|quantitative|||',
                  'source1_schedule': 'fixed', 'source1_cadence': str(clock['spacing']['nanoseconds']), 'source1_anchor': clock['spacing']['first']}
        configured = c.post('/temporal/configure', fields)
        assert configured.status_code == 200, configured.json
        view = configured.json['data']['job']
        assert '"inspection"' not in json.dumps(view['manifest']) and 'R-ENTITY-1' not in json.dumps(view['effective'])
        c.post('/temporal/run', {'fingerprint': view['fingerprint']})
        list(c.app.extensions['datatrust_m5_store'].jobs.values())[-1]['thread'].join(120)
        assert c.client.get(f'{API}/temporal/job').json['data']['job']['state'] == 'completed'
    finally:
        c.close()


def test_comparison_suggestions_keys_and_mappings_never_enter_the_specification(tmp_path):
    c = Client(tmp_path)
    try:
        c.post('/m4/start', {'mode': 'versions'})
        c.upload('customer_id,Age,city\n' + ''.join(f'{i},{20 + i % 40},{"xyz"[i % 3]}\n' for i in range(60)), 'reference.csv')
        job = c.upload('customer_id,age,City\n' + ''.join(f'{i},{21 + i % 40},{"xyz"[i % 3]}\n' for i in range(30, 90)), 'current.csv').json['data']['job']
        assert all(s['inspection']['coverage']['complete'] for s in job['sources'])
        assert [k['columns'] for k in job['suggestions']['identity_keys']] == [['customer_id']]
        assert [(m['column'], m['aligned']) for m in job['suggestions']['mappings']] == [('age', 'Age'), ('City', 'city')]
        fields = {'source1_role': 'reference', 'source2_role': 'current', 'source1_task': 'dataset_profile', 'source2_task': 'dataset_profile',
                  'identity_keys': 'customer_id', 'source2_mapping': json.dumps({'age': 'Age', 'City': 'city'})}
        view = c.post('/m4/configure', fields).json['data']['job']
        assert view['state'] == 'confirm' and view['manifest']['identity_keys'] == [['customer_id']]
        assert '"inspection"' not in json.dumps(view['manifest']) and 'R-KEY-1' not in json.dumps(view['configuration'])
        assert view['suggestions']['mappings']  # suggestions stay advisory: still listed, applied only through the declared mapping
    finally:
        c.close()


# Stage 5b: text, images, records and documents ---------------------------------------------------------------------------

import time

from tests.m7.test_foundation import fixture


def _session(app):
    client = app.test_client()
    client.get('/app/?launch=l')
    return client, client.get(f'{API}/session').json['data']['csrf_token']


def test_text_selector_discovery_and_applied_suggestions_bind(tmp_path):
    root = tmp_path / 'data'
    root.mkdir()
    (root / 'reviews.jsonl').write_text('\n'.join(json.dumps({'review_id': f'r{i}', 'body': f'The product arrived late and the box was damaged, review number {i}',
                                                               'label': ['pos', 'neg'][i % 2], 'split': ['train', 'test'][i % 2], 'meta': {'lang': 'en'}}) for i in range(30)))
    app = create_app(tmp_path / 'w', data_roots=(root,), launch_token='l')
    app.testing = True
    client, token = _session(app)
    post = lambda path, body=None: client.post(f'{API}{path}', json=body or {}, headers={'X-CSRF-Token': token})
    try:
        post('/text/start', {'preset': 'classification'})
        src = post('/text/sources', {'root_id': 'root_0', 'relative_path': 'reviews.jsonl', 'format': 'jsonl', 'source_id': 'data'}).json['data']['job']['sources'][0]
        roles = {x['selector']: {y['rule'] for y in x['suggestions']} for x in src['discovery']['selectors']}
        assert roles['body'] == {'R-TEXT-1'} and 'R-ID-1' in roles['review_id'] and roles['split'] == {'R-SPLIT-1'} and roles['label'] == {'R-CAT-1'}
        assert '/meta/lang' in roles and src['discovery']['statement'] == 'Examined the first 30 records; suggestions describe those records.'
        fields = {'s0_field_name': ['body'], 's0_field_selector': ['body'], 's0_field_kind': ['document'], 's0_field_required': ['no'], 's0_field_asset': ['no'],
                  's0_identity': 'review_id', 's0_split': 'split', 's0_annotation_field': ['body'], 's0_annotation_selector': ['label'], 's0_annotation_kind': ['classification'],
                  # the rest of the row exactly as the page's chip fills it (ANNOTATION_COLS defaults)
                  's0_annotation_expectation': ['unknown'], 's0_annotation_tokens': [''], 's0_annotation_unit': ['codepoint'], 's0_annotation_scheme': ['none'],
                  's0_annotation_overlap': ['yes'], 's0_annotation_status': [''], 's0_annotation_required_statuses': ['complete'], 's0_annotation_answerable': [''],
                  's0_annotation_content_source': [''], 's0_annotation_content_id': [''],
                  'representation': ['raw', 'nfc']}
        configured = post('/text/configure', fields)
        assert configured.status_code == 200, configured.json
        view = configured.json['data']['job']
        assert view['state'] == 'confirm', view.get('error')
        assert 'R-TEXT-1' not in json.dumps(view['manifest'])
    finally:
        app.extensions['datatrust_m6_store'].cleanup()
        app.extensions['confidenceguard_store'].cleanup()


def test_image_comparison_preset_builds_the_comparison_and_manifest_discovery(tmp_path):
    fixture(tmp_path)
    rows = lambda prefix: ''.join(json.dumps({'path': 'image.png', 'id': f'{prefix}{i}', 'tags': ['cat', 'outdoor'], 'objects': [{'category': 1, 'bbox': [2, 3, 12, 15]}]}) + '\n' for i in range(3))
    (tmp_path / 'ref.jsonl').write_text(rows('r'))
    (tmp_path / 'cur.jsonl').write_text(rows('c'))
    app = create_app(tmp_path / 'ui', data_roots=(tmp_path,), launch_token='l')
    app.testing = True
    client, token = _session(app)
    post = lambda path, body=None: client.post(f'{API}{path}', json=body or {}, headers={'X-CSRF-Token': token})

    def wait(expected):
        for _ in range(500):
            view = client.get(f'{API}/images/job').json['data']['job']
            if view['state'] != 'running':
                break
            time.sleep(.02)
        assert view['state'] == expected, view.get('error')
        return view
    try:
        post('/images/start', {'preset': 'comparison'})
        post('/images/sources', {'root_id': 'root_0', 'relative_path': 'ref.jsonl', 'asset_relative': '.', 'format': 'jsonl', 'role': 'reference', 'source_id': 'reference'})
        job = post('/images/sources', {'root_id': 'root_0', 'relative_path': 'cur.jsonl', 'asset_relative': '.', 'format': 'jsonl', 'role': 'current', 'source_id': 'current'}).json['data']['job']
        d = {x['selector']: x for x in job['sources'][0]['discovery']['selectors']}
        assert {y['rule'] for y in d['path']['suggestions']} == {'R-PATH-1'} and {y['rule'] for y in d['tags']['suggestions']} == {'R-LIST-1'}
        assert d['objects']['boxes']['consistent'] == ['xyxy', 'xywh'] and 'not established' in d['objects']['boxes']['text']
        assert job['sources'][0]['headers'] == ['path', 'id', 'tags', 'objects']
        post('/images/inspect')
        wait('configure')
        post('/images/configure', {'s0_path': 'path', 's0_logical_id': 'id', 's1_path': 'path', 's1_logical_id': 'id', 'align_logical_keys': 'no'})
        view = wait('confirm')
        assert view['manifest']['comparisons'] == [{'reference': 'reference', 'current': 'current', 'align_logical_keys': False, 'category_mapping': {}}]
    finally:
        app.extensions['datatrust_m7_store'].cleanup()
        app.extensions['confidenceguard_store'].cleanup()


def test_records_key_candidates_and_model_status_are_shown_before_selection(tmp_path):
    root = tmp_path / 'data'
    root.mkdir()
    (root / 'records.csv').write_text('invoice_id,entity,amount\n' + ''.join(f'INV{i},E{i % 4},{100 + i}.5\n' for i in range(30)))
    app = create_app(tmp_path / 'w', data_roots=(root,), launch_token='l')
    app.testing = True
    client, token = _session(app)
    post = lambda path, body=None: client.post(f'{API}{path}', json=body or {}, headers={'X-CSRF-Token': token})
    try:
        post('/cross/start')
        response = post('/cross/action', {'action': 'source', 'root_id': 'root_0', 'relative_path': 'records.csv', 'source_id': 'records', 'kind': 'structured', 'format': 'csv'})
        assert response.status_code == 200, response.json
        job = response.json['data']['job']
        src = job['sources'][0]
        assert src['headers'] == ['invoice_id', 'entity', 'amount'] and src['discovery']['keys'] == ['invoice_id']
        assert set(job['model_status']) == {'nli', 'image_text'}
        assert all(v['state'] in {'qualified', 'stale', 'not_qualified'} and v['text'] for v in job['model_status'].values())
        assert 'discovery' not in json.dumps(job['spec'])
    finally:
        app.extensions['datatrust_m9_store'].cleanup()
        app.extensions['confidenceguard_store'].cleanup()
