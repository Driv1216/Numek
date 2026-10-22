"""M9 through the app API: guided actions, preview, seal, run, investigation, review and reopen; paths stay local."""
import io
import json
import time

from datatrust.history import History
from datatrust.web import create_app
from validation.m9.fixtures import financial

API = '/api/datatrust/v1'


class Client:
    def __init__(self, tmp_path, history=None, name='a'):
        self.spec = financial(tmp_path, count=20)
        self.app = create_app(tmp_path / f'ui-{name}', data_roots=(tmp_path,), history=history, launch_token=f'l-{name}')
        self.app.testing = True
        self.client = self.app.test_client()
        self.client.get(f'/app/?launch=l-{name}')
        self.token = self.client.get(f'{API}/session').json['data']['csrf_token']
        self.store = self.app.extensions['datatrust_m9_store']

    def post(self, path, body=None):
        return self.client.post(f'{API}{path}', json=body or {}, headers={'X-CSRF-Token': self.token})

    def wait(self, expected):
        for _ in range(1500):
            view = self.client.get(f'{API}/cross/job').json['data']['job']
            if view['state'] != 'running':
                break
            time.sleep(.02)
        assert view['state'] == expected, view.get('error')
        return view

    def complete(self):
        self.post('/cross/start')
        imported = self.post('/cross/action', {'action': 'import', 'spec_json': json.dumps(self.spec.to_dict()), 'config_json': '{}'})
        assert imported.status_code == 200, imported.json
        assert self.post('/cross/preview').json['data']['job']['phase'] == 'preview'
        assert self.wait('configure')['preview']['sample_only'] is True
        self.post('/cross/seal'); sealed = self.wait('confirm')
        assert self.post('/cross/run', {'fingerprint': 'stale'}).json['error']['message'] == 'The confirmation is stale.'
        self.post('/cross/run', {'fingerprint': sealed['fingerprint']})
        return self.wait('completed')

    def close(self):
        self.store.cleanup()
        self.app.extensions['confidenceguard_store'].cleanup()


def test_lifecycle_investigation_review_and_disclosure(tmp_path):
    c = Client(tmp_path)
    done = c.complete()
    assert done['result']['findings'] >= 1 and str(tmp_path) not in json.dumps(done)
    analysis = c.client.get(f'{API}/cross/analysis').json
    assert analysis['profile']['documents'] == 21 and '12000000' not in json.dumps(analysis)
    target = next(t for t, v in analysis['profile']['review_targets'].items() if v.get('detail', {}).get('status') == 'conflicting_evidence')
    shown = c.post('/cross/investigate', {'target': target})
    assert shown.headers['Cache-Control'] == 'no-store' and str(tmp_path) not in json.dumps(shown.json)
    assert {'12000000', '1200000'} <= {e.get('excerpt') for e in shown.json['data']['evidence']}
    assert c.client.post(f'{API}/cross/investigate', json={'target': target}).status_code == 403
    reviewed = c.post('/cross/review', {'target': target, 'disposition': 'confirm', 'note': 'checked'}).json['data']['job']
    assert reviewed['reviews'][target]['disposition'] == 'confirm'
    review_json = c.client.get(f'{API}/cross/download/review').get_data(as_text=True)
    assert c.post('/cross/import-review', {'review_json': review_json}).status_code == 200
    assert c.post('/cross/import-review', {'review_json': '{"bogus": 1}'}).status_code == 400
    assert c.post('/cross/disclose', {'excerpt_refs': shown.json['data']['evidence'][0]['reference']}).status_code == 200
    c.close()


def test_reopen_needs_the_user_supplied_private_manifest(tmp_path):
    c = Client(tmp_path)
    c.complete()
    report = c.client.get(f'{API}/cross/download/json').data
    private = c.client.get(f'{API}/cross/download/private').data
    c.post('/cross/new')
    refused = c.client.post(f'{API}/cross/load-result', data={'report': (io.BytesIO(report), 'analysis.json'), 'private': (io.BytesIO(b'{}'), 'manifest.json')},
                            headers={'X-CSRF-Token': c.token}, content_type='multipart/form-data')
    assert refused.status_code == 400
    reopened = c.client.post(f'{API}/cross/load-result', data={'report': (io.BytesIO(report), 'analysis.json'), 'private': (io.BytesIO(private), 'manifest.json')},
                             headers={'X-CSRF-Token': c.token}, content_type='multipart/form-data')
    assert reopened.status_code == 200 and reopened.json['data']['job']['state'] == 'completed'
    c.close()


def test_sources_stay_inside_data_roots_and_saved_entries_hold_no_excerpts(tmp_path):
    history = History(tmp_path / 'history'); history.set_settings(saving='on')
    c = Client(tmp_path, history)
    c.post('/cross/start')
    refused = c.post('/cross/action', {'action': 'source', 'source_id': 'x', 'root_id': 'root_0', 'relative_path': '../outside.csv', 'kind': 'structured', 'format': 'csv'})
    assert refused.status_code == 422
    c.complete()
    c.app.extensions['datatrust_history_sweep']()
    entry = history.search()['items'][0]
    assert entry['workflow'] == 'm9' and entry['mode'] == 'records_documents'
    for f in (tmp_path / 'history').rglob('*'):
        if f.is_file():
            assert b'12000000' not in f.read_bytes() and str(tmp_path).encode() not in f.read_bytes(), f
    c.close()
