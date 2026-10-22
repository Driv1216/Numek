"""M4 through the app API: the same jobs and rules as the classic routes, tighter source access."""
import io
import json
import re
import threading

from datatrust import m4_web
from datatrust.history import History
from datatrust.web import create_app

API = '/api/datatrust/v1'
SPLIT = ('id,x,label\n001,1,a\n1,2,b\n7,4,a\n', 'id,x,label\n001,1,a\n2,3,b\n9,5,b\n')
FIELDS = {'source1_role': 'train', 'source2_role': 'test', 'source1_task': 'dataset_profile', 'source2_task': 'dataset_profile',
          'identity_keys': 'id', 'evaluation_intent': 'entity_disjoint'}


class Client:
    def __init__(self, tmp_path, history=None, name='a'):
        self.app = create_app(tmp_path / f'workspace-{name}', data_roots=(tmp_path / 'data',), history=history, launch_token=f'launch-{name}')
        self.app.testing = True
        self.client = self.app.test_client()
        self.client.get(f'/app/?launch=launch-{name}')
        self.token = self.client.get(f'{API}/session').json['data']['csrf_token']
        self.store = self.app.extensions['datatrust_m4_store']

    def post(self, path, body=None):
        return self.client.post(f'{API}{path}', json=body or {}, headers={'X-CSRF-Token': self.token})

    def upload(self, text, name='part.csv'):
        return self.client.post(f'{API}/m4/sources', data={'dataset': (io.BytesIO(text.encode()), name)}, headers={'X-CSRF-Token': self.token}, content_type='multipart/form-data')

    def job(self):
        return next(iter(self.store.jobs.values()))

    def split(self):
        self.post('/m4/start', {'mode': 'splits'})
        for i, text in enumerate(SPLIT):
            assert self.upload(text, f'part{i}.csv').status_code == 200
        return self.post('/m4/configure', FIELDS).json['data']['job']

    def close(self):
        self.store.cleanup()
        self.app.extensions['confidenceguard_store'].cleanup()


def test_data_root_containment(tmp_path):
    data = tmp_path / 'data'; data.mkdir()
    (data / 'inside.csv').write_text('id,x\n1,2\n')
    (tmp_path / 'outside.csv').write_text('id,x\n1,2\n')
    (data / 'escape.csv').symlink_to(tmp_path / 'outside.csv')
    c = Client(tmp_path)
    roots = c.client.get(f'{API}/session').json['data']['roots']
    assert roots == [{'id': 'root_0', 'label': 'data'}]
    c.post('/m4/start', {'mode': 'versions'})
    for relative in ('../outside.csv', str(tmp_path / 'outside.csv'), 'escape.csv', 'missing.csv'):
        refused = c.post('/m4/sources', {'root_id': 'root_0', 'relative_path': relative})
        assert refused.status_code == 422 and 'outside the configured data roots' in refused.json['error']['message'], relative
    assert c.post('/m4/sources', {'root_id': 'root_9', 'relative_path': 'inside.csv'}).status_code == 422
    added = c.post('/m4/sources', {'root_id': 'root_0', 'relative_path': 'inside.csv'}).json['data']['job']
    assert added['sources'][0]['origin'] == 'local' and added['sources'][0]['filename'] == 'inside.csv'
    assert str(data) not in json.dumps(added)
    c.close()


def test_split_flow_stale_confirmation_and_busy_worker(tmp_path):
    (tmp_path / 'data').mkdir()
    c = Client(tmp_path)
    view = c.split()
    assert view['state'] == 'confirm' and view['fingerprint']
    assert str(tmp_path) not in json.dumps(view['manifest'])
    stale = c.post('/m4/run', {'fingerprint': 'old'})
    assert stale.status_code == 422 and stale.json['error']['message'] == 'The confirmation is stale.'
    lock = c.store.lock
    assert lock.acquire(blocking=False)
    try:
        busy = c.post('/m4/run', {'fingerprint': view['fingerprint']})
        assert busy.json['error']['message'] == 'One local worker is already active; cancel it or wait for completion.'
    finally:
        lock.release()
    assert c.post('/m4/run', {'fingerprint': view['fingerprint']}).json['data']['job']['state'] in {'running', 'completed'}
    c.job()['thread'].join(30)
    done = c.client.get(f'{API}/m4/job').json['data']['job']
    assert done['state'] == 'completed' and done['result']['findings'] >= 1
    analysis = c.client.get(f'{API}/m4/analysis')
    assert analysis.status_code == 200 and analysis.json['scoring']['status'] == 'not_applicable'
    report = c.client.get(f'{API}/m4/report')
    assert report.status_code == 200 and report.headers['X-Frame-Options'] == 'SAMEORIGIN'
    assert c.client.get(f'{API}/m4/download/json').status_code == 200
    # Editing declarations invalidates the result, as in the classic flow.
    assert c.post('/m4/configure', FIELDS).json['data']['job']['result'] is None
    c.close()


def test_cancel_publishes_nothing(tmp_path, monkeypatch):
    (tmp_path / 'data').mkdir()
    started = threading.Event()
    def slow(spec, config, *, progress, cancel, owned_snapshots):
        started.set(); cancel.wait(10)
        raise RuntimeError('stopped')
    monkeypatch.setattr(m4_web, 'compare', slow)
    c = Client(tmp_path)
    view = c.split()
    c.post('/m4/run', {'fingerprint': view['fingerprint']})
    assert started.wait(5)
    assert c.post('/m4/cancel').status_code == 200
    c.job()['thread'].join(10)
    final = c.client.get(f'{API}/m4/job').json['data']['job']
    assert final['state'] == 'cancelled' and final['result'] is None
    assert c.client.get(f'{API}/m4/analysis').status_code == 400
    c.close()


def test_completed_comparison_is_saved_without_the_browser_watching(tmp_path):
    (tmp_path / 'data').mkdir()
    history = History(tmp_path / 'history')
    history.set_settings(saving='on')
    c = Client(tmp_path, history)
    view = c.split()
    c.post('/m4/run', {'fingerprint': view['fingerprint']})
    c.job()['thread'].join(30)
    c.app.extensions['datatrust_history_sweep']()  # what any request or shutdown does
    page = history.search()
    assert page['total'] == 1
    entry = page['items'][0]
    assert entry['workflow'] == 'm4' and entry['mode'] == 'splits' and set(entry['artifacts']) == {'json', 'html'}
    assert entry['source_filename'] == 'part0.csv ↔ part1.csv' and entry['score'] is None
    assert c.client.get(f'{API}/m4/job').json['data']['job']['saved_entry'] == entry['id']
    c.close()


def test_api_and_classic_produce_the_same_canonical_comparison(tmp_path):
    (tmp_path / 'data').mkdir()
    api = Client(tmp_path, name='api')
    view = api.split()
    api.post('/m4/run', {'fingerprint': view['fingerprint']})
    api.job()['thread'].join(30)
    api_json = api.client.get(f'{API}/m4/analysis').get_data(as_text=True)

    app = create_app(tmp_path / 'workspace-classic', data_roots=(tmp_path / 'data',)); app.testing = True
    client = app.test_client(); client.get('/m4')
    with client.session_transaction() as s:
        token = s['form_token']
    post = lambda path, data: client.post(path, data={'form_token': token, **data}, follow_redirects=True)
    post('/m4', {'mode': 'splits'})
    for i, text in enumerate(SPLIT):
        post('/m4/sources', {'dataset': (io.BytesIO(text.encode()), f'part{i}.csv')})
    post('/m4/configure', FIELDS)
    store = app.extensions['datatrust_m4_store']; j = next(iter(store.jobs.values()))
    post('/m4/run', {'fingerprint': j['fingerprint']}); j['thread'].join(30)
    classic_json = client.get('/m4/download/json').get_data(as_text=True)

    volatile = re.compile(r'"(generated_at|[a-z_]*seconds|[a-z_]*_bytes|peak_[a-z_]+|path|directory|[a-z_]*workspace[a-z_]*|rss[a-z_]*|[a-z_]*_ns)": ("[^"]*"|[-0-9.e]+|null)')
    norm = lambda text: volatile.sub(r'"\1": "*"', re.sub(r'source-[0-9a-f]{32}\.csv', 'source.csv', text))
    assert json.loads(api_json)['findings'] and json.loads(api_json)['inputs'][0]['role'] == 'train'
    assert norm(api_json) == norm(classic_json)
    api.close(); store.cleanup()
