"""The dashboard's presentation companion (dashboard_companion_v1): report-owned names, ranks and verified report locators.

Every locator is checked against the exact report HTML served, live or saved; ranks are what each workflow recorded
(priorities, or the text and image evidence meanings, which are never turned into priorities); nothing private is
returned; the cache never crosses scopes and follows every input that changes the result.
"""
import hashlib
import json
from io import BytesIO
from pathlib import Path

import pandas as pd
import pytest

from dashboard_harness import ROOT, analysis, cases, folder, params
from datatrust.dashboard_companion import Cache, build, disclosure_context, read_locators
from datatrust.history import History
from datatrust.web import create_app

API = '/api/datatrust/v1'
SENTINEL = 'zq-companion-private-value'
CSV = pd.DataFrame({'age': [21, 35, 47, 52, 33, 29, 61, 44] * 5, 'note': [f'{SENTINEL}-{i}' for i in range(40)],
                    'label': [0, 1, 0, 0, 1, 0, 0, 1] * 5}).to_csv(index=False).encode()


def canonical(value):
    return [f for f in value.get('findings') or [] if f.get('code') != 'no_major_issues']


@pytest.mark.parametrize('case', params())
def test_every_case_keeps_its_recorded_findings_ranks_and_only_verified_anchors(case):
    value = analysis(case)
    html = (folder(case) / 'report.html').read_text()
    c = build(value, html)
    recorded = canonical(value)
    assert [f['index'] for f in c['findings']] == [i for i, f in enumerate(value.get('findings') or []) if f.get('code') != 'no_major_issues']
    assert len(c['findings']) == len(recorded)
    ids = read_locators(html)['ids']
    for f, r in zip(c['findings'], recorded):
        if f['locator']['kind'] in {'anchor', 'section'}:
            assert f['locator']['value'] in ids, f
        if case['composition'] in {'text', 'image'}:
            assert f['rank']['kind'] == 'evidence_meaning' and f['rank']['value'] == r['meaning']
            assert f['rank']['label'] not in {'High', 'Moderate', 'Low'}, 'text and image findings record no priority'
        elif case['composition'] != 'generic':
            assert f['rank']['kind'] == 'priority'
            assert f['rank']['value'].lower() == str(r.get('priority') or r.get('severity')).lower()


def test_text_actions_and_order_are_the_reports_own():
    value = analysis('m6_controls')
    c = build(value, (folder('m6_controls') / 'report.html').read_text())
    from datatrust.dashboard_companion import _Recorded
    from datatrust.text_presentation import executive_summary
    report = executive_summary(_Recorded(value).to_dict())['actions']
    assert [(a['family'], a['meaning']) for a in c['actions']] == [(a['family'], a['meaning']) for a in report]
    assert c['actions'][0]['meaning'] == 'deterministic_violation'


def test_unknown_methodology_is_shown_as_recorded_without_a_projection():
    c = build(analysis('generic_unknown_methodology'), (folder('generic_unknown_methodology') / 'report.html').read_text())
    assert c['family'] is None and c['actions'] is None and c['concepts'] == []
    assert all(f['locator']['kind'] == 'none' for f in c['findings']) and len(c['findings']) == 2


@pytest.mark.parametrize('stored,html', [('m5/reports/beijing.json', 'm5/reports/beijing.html'),
                                         ('regression/reports/concrete.json', 'regression/reports/concrete.html'),
                                         ('m4/results/reports/contaminated/analysis.json', 'm4/results/reports/contaminated/report.html')])
def test_older_saved_reports_get_only_the_locators_their_own_bytes_contain(stored, html):
    value = json.loads((ROOT / 'validation' / stored).read_text())
    page = (ROOT / 'validation' / html).read_text()
    c = build(value, page)
    ids, rows = read_locators(page)['ids'], read_locators(page)['rows']
    for f in c['findings']:
        kind = f['locator']['kind']
        if kind in {'anchor', 'section'}:
            assert f['locator']['value'] in ids
        if kind == 'index_position':
            assert 1 <= f['locator']['value'] <= len(rows)
        if kind == 'anchor' and f['locator'].get('checked') == 'id_only':
            assert not rows
    if stored.startswith('m5/'):   # the older temporal report had 5 action cards and no finding index (Stage 0 gap)
        assert sum(f['locator']['kind'] == 'anchor' for f in c['findings']) <= 5
        assert {f['locator']['kind'] for f in c['findings'][5:]} <= {'none', 'index_position'}


def test_cache_key_follows_every_input_and_never_crosses_scopes():
    value = analysis('m6_controls_excerpts')
    data = json.dumps(value).encode()
    html = (folder('m6_controls_excerpts') / 'report.html').read_bytes()
    cache = Cache(size=4)
    first = cache.companion('live:a', data, html)
    assert cache.companion('live:a', data, html) is first
    assert cache.companion('live:b', data, html) is not first                     # another scope never reuses it
    complete = html.replace(b'Print profile: focused', b'Print profile: complete')
    assert cache.companion('live:a', data, complete) is not first                 # the served bytes and profile changed
    other = dict(value, profile=dict(value['profile'], disclosure={'policy': 'references_only'}))
    assert disclosure_context(other) != disclosure_context(value)
    keys = [k for k in cache.items]
    assert len({k[0] for k in keys}) == 2 and len(keys) == 3
    cache.forget('live:a')
    assert all(k[0] != 'live:a' for k in cache.items)


class Session:
    def __init__(self, tmp_path, history, name='a'):
        self.app = create_app(tmp_path / f'jobs-{name}', history=history, launch_token=f'launch-{name}')
        self.app.config.update(TESTING=True)
        self.client = self.app.test_client()
        assert self.client.get(f'/app/?launch=launch-{name}').status_code == 303
        self.token = self.client.get(f'{API}/session').json['data']['csrf_token']

    def post(self, path, body=None):
        return self.client.post(f'{API}{path}', json=body or {}, headers={'X-CSRF-Token': self.token})

    def get(self, path, **kwargs):
        return self.client.get(f'{API}{path}', **kwargs)

    def close(self):
        self.app.extensions['confidenceguard_store'].cleanup()
        self.app.extensions['datatrust_job_store'].cleanup()


def test_live_and_saved_companions_verify_against_the_served_report_and_stay_private(tmp_path):
    history = History(tmp_path / 'history')
    s = Session(tmp_path, history)
    s.post('/history/choice', {'saving': 'on'})
    s.client.post(f'{API}/core/jobs', data={'mode': 'classification', 'dataset': (BytesIO(CSV), 'demo.csv')},
                  headers={'X-CSRF-Token': s.token}, content_type='multipart/form-data')
    s.post('/core/job/configure', {'target': 'label', 'dataset_name': 'Demo', 'purpose': ''})
    saved = s.post('/core/job/generate', {'save_to_history': 'yes'}).json['data']['history']
    live = s.get('/core/job/presentation')
    assert live.status_code == 200 and live.headers['Cache-Control'] == 'no-store'
    data = live.json['data']
    assert data['companion'] == 'dashboard_companion_v1' and data['report']['presentation_source'] == 'report'
    served = s.client.get(f'{API}/core/job/report').data
    ids = read_locators(served)['ids']
    assert data['findings'] and all(f['locator']['kind'] == 'anchor' and f['locator']['value'] in ids for f in data['findings'])
    assert SENTINEL not in live.get_data(as_text=True)
    entry = s.get(f"/history/{saved['entry']}/presentation").json['data']
    assert [f['title'] for f in entry['findings']] == [f['title'] for f in data['findings']]
    assert entry['report']['presentation_source'] == 'report'
    # Another browser session owns nothing here; a cross-site request is refused before any route runs.
    other = Session(tmp_path, history, 'b')
    assert other.get('/core/job/presentation').status_code == 404
    assert s.get('/core/job/presentation', headers={'Sec-Fetch-Site': 'cross-site'}).status_code == 403
    other.close()
    s.close()


def test_a_saved_older_report_without_a_recorded_presentation_falls_back_honestly(tmp_path):
    from datatrust.api_web import _history_meta
    history = History(tmp_path / 'history')
    history.set_settings(saving='on')
    stored, page = ROOT / 'validation/m5/reports/beijing.json', ROOT / 'validation/m5/reports/beijing.html'
    meta = _history_meta(stored)
    meta.pop('presentation')
    sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
    eid = history.record(workflow='m5', mode='m5', meta=meta, artifacts={'json': (stored, sha(stored)), 'html': (page, sha(page))})
    s = Session(tmp_path, history)
    data = s.get(f'/history/{eid}/presentation').json['data']
    assert data['report']['presentation_id'] is None and data['report']['presentation_source'] is None
    assert len(data['findings']) == 15
    ids = read_locators(page.read_text())['ids']
    assert all(f['locator']['value'] in ids for f in data['findings'] if f['locator']['kind'] == 'anchor')
    assert any(f['locator']['kind'] != 'anchor' for f in data['findings'])
    s.close()
