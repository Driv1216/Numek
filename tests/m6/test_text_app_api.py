"""M6 through the app API: same jobs and rules as the classic text routes; reveal only on explicit request."""
import json
from pathlib import Path

from datatrust.history import History
from datatrust.web import create_app

API = '/api/datatrust/v1'
FIELDS = {'s0_field_name': ['text'], 's0_field_selector': ['text'], 's0_field_kind': ['document'], 's0_field_required': ['no'], 's0_field_asset': ['no'],
          's0_identity': 'id', 'vocabulary': 'yes', 'near_duplicates': 'no', 'passages': 'no', 'representation': ['raw', 'nfc']}


def data(tmp_path):
    root = tmp_path / 'data'; root.mkdir(exist_ok=True)
    (root / 'source.jsonl').write_text('\n'.join(json.dumps({'text': 'SECRET_MARKER <script>bad()</script>', 'id': str(i)}) for i in range(2)))
    return root


class Client:
    def __init__(self, tmp_path, history=None, name='a'):
        self.root = data(tmp_path)
        self.app = create_app(tmp_path / f'ui-{name}', data_roots=(self.root,), history=history, launch_token=f'l-{name}')
        self.app.testing = True
        self.client = self.app.test_client()
        self.client.get(f'/app/?launch=l-{name}')
        self.token = self.client.get(f'{API}/session').json['data']['csrf_token']
        self.store = self.app.extensions['datatrust_m6_store']

    def post(self, path, body=None):
        return self.client.post(f'{API}{path}', json=body or {}, headers={'X-CSRF-Token': self.token})

    def run(self):
        self.post('/text/start', {'preset': 'corpus'})
        assert self.post('/text/sources', {'root_id': 'root_0', 'relative_path': 'source.jsonl', 'format': 'jsonl', 'source_id': 'data'}).status_code == 200
        view = self.post('/text/configure', FIELDS).json['data']['job']
        assert view['state'] == 'confirm' and view['sources'][0]['headers'] == ['text', 'id']
        self.post('/text/run', {'fingerprint': view['fingerprint']})
        list(self.store.jobs.values())[-1]['thread'].join(30)
        return self.client.get(f'{API}/text/job').json['data']['job']

    def close(self):
        self.store.cleanup()
        self.app.extensions['confidenceguard_store'].cleanup()


def test_guided_rows_run_reveal_and_excerpts(tmp_path):
    c = Client(tmp_path)
    done = c.run()
    assert done['state'] == 'completed' and done['result']['findings'] >= 1
    analysis = c.client.get(f'{API}/text/analysis')
    assert analysis.status_code == 200 and b'SECRET_MARKER' not in analysis.data
    assert c.client.get(f'{API}/text/report').headers['X-Frame-Options'] == 'SAMEORIGIN'
    ref = next(x for x in analysis.json['evidence'] if x['family'] == 'exact_duplicates')['references'][0]
    hidden = c.post('/text/evidence', {'reference': ref})
    assert hidden.status_code == 200 and 'SECRET_MARKER' not in json.dumps(hidden.json)
    shown = c.post('/text/evidence', {'reference': ref, 'reveal': 'yes'})
    assert shown.headers['Cache-Control'] == 'no-store' and 'SECRET_MARKER' in json.dumps(shown.json)
    assert str(c.root) not in json.dumps(shown.json)  # file names only, never local paths
    assert c.client.post(f'{API}/text/evidence', json={'reference': ref, 'reveal': 'yes'}).status_code == 403
    assert c.post('/text/export-excerpts', {'references': ref}).status_code == 200
    (c.root / 'source.jsonl').write_text((c.root / 'source.jsonl').read_text() + '\n' + json.dumps({'text': 'changed'}))
    changed = c.post('/text/evidence', {'reference': ref, 'reveal': 'yes'})
    assert changed.status_code == 409 and changed.json['error']['code'] == 'changed_or_unavailable'
    c.close()


def test_sources_stay_inside_data_roots_and_rows_are_checked(tmp_path):
    c = Client(tmp_path)
    (tmp_path / 'outside.jsonl').write_text('{"text":"x"}')
    c.post('/text/start', {'preset': 'corpus'})
    for relative in ('../outside.jsonl', str(tmp_path / 'outside.jsonl')):
        refused = c.post('/text/sources', {'root_id': 'root_0', 'relative_path': relative, 'format': 'jsonl'})
        assert refused.status_code == 422 and refused.json['error']['message'] == 'Source must be a regular file within configured roots.'
    c.post('/text/sources', {'root_id': 'root_0', 'relative_path': 'source.jsonl', 'format': 'jsonl', 'source_id': 'data'})
    broken = c.post('/text/configure', {**FIELDS, 's0_field_kind': ['document', 'chunk']})
    assert broken.status_code == 422 and broken.json['error']['message'] == 'Content field controls are incomplete.'
    assert c.post('/text/configure', {'s0_field_name': [1]}).status_code == 422
    view = c.post('/text/configure', FIELDS).json['data']['job']
    assert c.post('/text/run', {'fingerprint': 'stale'}).json['error']['message'] == 'The confirmation is stale.' and view['fingerprint']
    c.close()


def test_completed_text_audit_is_saved_without_private_material(tmp_path):
    history = History(tmp_path / 'history'); history.set_settings(saving='on')
    c = Client(tmp_path, history)
    c.run()
    c.app.extensions['datatrust_history_sweep']()
    entry = history.search()['items'][0]
    assert entry['workflow'] == 'm6' and entry['mode'] == 'corpus' and set(entry['artifacts']) == {'json', 'html'}
    for f in (tmp_path / 'history').rglob('*'):
        if f.is_file():
            assert b'SECRET_MARKER' not in f.read_bytes(), f
    c.close()
