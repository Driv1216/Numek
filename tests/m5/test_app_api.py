"""M5 through the app API: same jobs and rules as the classic temporal routes, tighter source access."""
import json
import re

from datatrust.history import History
from datatrust.web import create_app

API = '/api/datatrust/v1'
FIELDS = {'dataset_name': 'Temporal', 'source1_role': 'dataset', 'source1_task': 'dataset_profile', 'source1_clock': 'time',
          'source1_encoding': 'epoch', 'source1_epoch_unit': 'ns', 'source1_measurements': 'x||quantitative|||',
          'source1_schedule': 'fixed', 'source1_cadence': '1', 'source1_anchor': '0'}


def data(tmp_path, n=240):
    root = tmp_path / 'data'; root.mkdir(exist_ok=True)
    (root / 'series.csv').write_text('time,x\n' + ''.join(f'{i},{0 if i < n // 2 else i}\n' for i in range(n)))
    return root


class Client:
    def __init__(self, tmp_path, history=None, name='a'):
        self.app = create_app(tmp_path / f'w-{name}', data_roots=(data(tmp_path),), history=history, launch_token=f'l-{name}')
        self.app.testing = True
        self.client = self.app.test_client()
        self.client.get(f'/app/?launch=l-{name}')
        self.token = self.client.get(f'{API}/session').json['data']['csrf_token']
        self.store = self.app.extensions['datatrust_m5_store']

    def post(self, path, body=None):
        return self.client.post(f'{API}{path}', json=body or {}, headers={'X-CSRF-Token': self.token})

    def ready(self):
        self.post('/temporal/start')
        assert self.post('/temporal/sources', {'root_id': 'root_0', 'relative_path': 'series.csv', 'format': 'csv'}).status_code == 200
        return self.post('/temporal/configure', FIELDS).json['data']['job']

    def run(self):
        view = self.ready()
        self.post('/temporal/run', {'fingerprint': view['fingerprint']})
        list(self.store.jobs.values())[-1]['thread'].join(120)
        return self.client.get(f'{API}/temporal/job').json['data']['job']

    def close(self):
        self.store.cleanup()
        self.app.extensions['confidenceguard_store'].cleanup()


def test_guided_flow_artifacts_and_investigation(tmp_path):
    c = Client(tmp_path)
    view = c.ready()
    assert view['state'] == 'confirm' and str(tmp_path) not in json.dumps(view)
    assert c.post('/temporal/run', {'fingerprint': 'stale'}).json['error']['message'] == 'Source, timezone data or declarations changed; review and confirm again.'
    c.post('/temporal/run', {'fingerprint': view['fingerprint']})
    list(c.store.jobs.values())[-1]['thread'].join(120)
    done = c.client.get(f'{API}/temporal/job').json['data']['job']
    assert done['state'] == 'completed' and done['result'] is not None
    analysis = c.client.get(f'{API}/temporal/analysis').json
    assert analysis['context']['dataset_name'] == 'Temporal' and analysis['evidence']
    report = c.client.get(f'{API}/temporal/report')
    assert report.status_code == 200 and report.headers['X-Frame-Options'] == 'SAMEORIGIN'
    assert c.client.get(f'{API}/temporal/investigate?measurement=x').status_code == 200
    assert c.client.get(f'{API}/temporal/download/json').status_code == 200
    c.close()


def test_sources_stay_inside_data_roots(tmp_path):
    c = Client(tmp_path)
    (tmp_path / 'outside.csv').write_text('time,x\n0,1\n')
    (tmp_path / 'data' / 'link.csv').symlink_to(tmp_path / 'outside.csv')
    c.post('/temporal/start')
    for relative in ('../outside.csv', str(tmp_path / 'outside.csv'), 'link.csv'):
        refused = c.post('/temporal/sources', {'root_id': 'root_0', 'relative_path': relative, 'format': 'csv'})
        assert refused.status_code == 422 and 'outside allowed local data roots' in refused.json['error']['message'], relative
    assert c.post('/temporal/sources', {'root_id': 'root_0', 'relative_path': 'series.csv', 'format': 'xls'}).json['error']['message'] == 'Choose CSV or Parquet explicitly.'
    c.close()


def test_completed_audit_is_saved_without_the_browser_watching(tmp_path):
    history = History(tmp_path / 'history'); history.set_settings(saving='on')
    c = Client(tmp_path, history)
    c.run()
    c.app.extensions['datatrust_history_sweep']()
    entry = history.search()['items'][0]
    assert entry['workflow'] == 'm5' and entry['dataset_name'] == 'Temporal' and entry['source_filename'] == 'series.csv'
    c.close()


def test_api_and_classic_produce_the_same_canonical_audit(tmp_path):
    api = Client(tmp_path, name='api')
    api.run()
    api_json = api.client.get(f'{API}/temporal/analysis').get_data(as_text=True)
    app = create_app(tmp_path / 'w-classic', data_roots=(tmp_path / 'data',)); app.testing = True
    client = app.test_client(); client.get('/temporal')
    with client.session_transaction() as s:
        token = s['form_token']
    client.post('/temporal', data={'form_token': token})
    client.post('/temporal/sources', data={'form_token': token, 'format': 'csv', 'local_path': str(tmp_path / 'data' / 'series.csv')})
    client.post('/temporal/configure', data={'form_token': token, **FIELDS})
    store = app.extensions['datatrust_m5_store']; j = next(iter(store.jobs.values()))
    client.post('/temporal/run', data={'form_token': token, 'fingerprint': j['fingerprint']}); j['thread'].join(120)
    classic_json = client.get('/temporal/download/json').get_data(as_text=True)
    volatile = re.compile(r'"(generated_at|[a-z_]*seconds|[a-z_]*_bytes|peak_[a-z_]+|[a-z_]*rss[a-z_]*|ledger|phase_plan)": ("[^"]*"|[-0-9.e]+|null|\{[^{}]*\}|\[[^\[\]]*\])')
    norm = lambda text: volatile.sub(r'"\1": "*"', text)
    assert json.loads(api_json)['evidence'] and norm(api_json) == norm(classic_json)
    api.close(); store.cleanup()
