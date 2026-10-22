"""M7 through the app API: inspect, seal, run and view pairs locally; images and labels only on request."""
import json
import time

from datatrust.history import History
from datatrust.web import create_app
from tests.m7.test_foundation import fixture

API = '/api/datatrust/v1'
DECLARE = {'s0_task': 'detection', 's0_path': 'path', 's0_logical_id': 'id', 's0_objects': 'objects', 's0_frame': 'encoded', 's0_expectation': 'unknown'}


class Client:
    def __init__(self, tmp_path, history=None, name='a'):
        fixture(tmp_path)
        self.app = create_app(tmp_path / f'ui-{name}', data_roots=(tmp_path,), history=history, launch_token=f'l-{name}')
        self.app.testing = True
        self.client = self.app.test_client()
        self.client.get(f'/app/?launch=l-{name}')
        self.token = self.client.get(f'{API}/session').json['data']['csrf_token']
        self.store = self.app.extensions['datatrust_m7_store']

    def post(self, path, body=None):
        return self.client.post(f'{API}{path}', json=body or {}, headers={'X-CSRF-Token': self.token})

    def wait(self, expected):
        for _ in range(500):
            view = self.client.get(f'{API}/images/job').json['data']['job']
            if view['state'] != 'running':
                break
            time.sleep(.02)
        assert view['state'] == expected, view.get('error')
        return view

    def complete(self):
        self.post('/images/start', {'preset': 'manifest'})
        assert self.post('/images/sources', {'root_id': 'root_0', 'relative_path': 'data.jsonl', 'asset_relative': '.', 'format': 'jsonl', 'role': 'train', 'source_id': 's'}).status_code == 200
        assert self.post('/images/inspect').json['data']['job']['phase'] == 'inspect'
        inspected = self.wait('configure')
        assert inspected['inspected'] and inspected['preview']['occurrences'] == 1
        self.post('/images/configure', DECLARE)
        sealed = self.wait('confirm')
        self.post('/images/run', {'fingerprint': sealed['fingerprint']})
        return self.wait('completed')

    def close(self):
        self.store.cleanup()
        self.app.extensions['confidenceguard_store'].cleanup()


def test_inspect_seal_run_and_local_viewing(tmp_path):
    c = Client(tmp_path)
    done = c.complete()
    assert done['phase'] == 'run' and done['result'] is not None and str(tmp_path) not in json.dumps(done)
    analysis = c.client.get(f'{API}/images/analysis')
    assert analysis.status_code == 200 and b'data:image' not in analysis.data
    assert c.client.get(f'{API}/images/report').headers['X-Frame-Options'] == 'SAMEORIGIN'
    listing = c.client.get(f'{API}/images/pairs').json['data']
    ref = listing['references'][0]
    plain_view = c.post('/images/resolve', {'references': ref})
    assert plain_view.headers['Cache-Control'] == 'no-store' and str(tmp_path) not in json.dumps(plain_view.json)
    assert c.client.post(f'{API}/images/resolve', json={'references': ref}).status_code == 403
    assert c.post('/images/export-examples', {'references': ref}).status_code == 200
    c.close()


def test_sources_stay_inside_data_roots_and_confirmation_is_bound(tmp_path):
    c = Client(tmp_path)
    c.post('/images/start', {'preset': 'manifest'})
    refused = c.post('/images/sources', {'root_id': 'root_0', 'relative_path': '../elsewhere.jsonl', 'format': 'jsonl'})
    assert refused.status_code == 422
    c.post('/images/sources', {'root_id': 'root_0', 'relative_path': 'data.jsonl', 'asset_relative': '.', 'format': 'jsonl', 'role': 'train', 'source_id': 's'})
    c.post('/images/inspect'); c.wait('configure')
    c.post('/images/configure', DECLARE); c.wait('confirm')
    assert c.post('/images/run', {'fingerprint': 'stale'}).json['error']['message'] == 'The confirmation is stale.'
    c.close()


def test_completed_image_audit_is_saved_without_images(tmp_path):
    history = History(tmp_path / 'history'); history.set_settings(saving='on')
    c = Client(tmp_path, history)
    c.complete()
    c.app.extensions['datatrust_history_sweep']()
    entry = history.search()['items'][0]
    assert entry['workflow'] == 'm7' and entry['mode'] == 'manifest'
    for f in (tmp_path / 'history').rglob('*'):
        if f.is_file():
            assert b'data:image' not in f.read_bytes(), f
    c.close()
