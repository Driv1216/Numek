"""Local history: canonical artifacts only, verified copies, recoverable recording, gated access."""
from io import BytesIO
import json
import os
from pathlib import Path
import sqlite3
import time

from click.testing import CliRunner
import pandas as pd
import pytest

from datatrust import web
from datatrust.cli import main
from datatrust.history import History, HistoryError
from datatrust.web import create_app

API = '/api/datatrust/v1'
SENTINEL = 'zq-private-cell-value'
DATA = {'age': [21, 35, 47, 52, 33, 29, 61, 44] * 5, 'note': [f'{SENTINEL}-{i}' for i in range(40)],
        'city': ['a', 'b', 'c', 'a', 'b', 'c', 'a', 'b'] * 5, 'label': [0, 1, 0, 0, 1, 0, 0, 1] * 5}
CSV = pd.DataFrame(DATA).to_csv(index=False).encode()


class Session:
    def __init__(self, tmp_path, history, name='a', unlock=True):
        self.app = create_app(tmp_path / f'jobs-{name}', history=history, launch_token=f'launch-{name}')
        self.app.config.update(TESTING=True)
        self.client = self.app.test_client()
        if unlock:
            assert self.client.get(f'/app/?launch=launch-{name}').status_code == 303
        self.token = self.client.get(f'{API}/session').json['data']['csrf_token']

    def post(self, path, body=None):
        return self.client.post(f'{API}{path}', json=body or {}, headers={'X-CSRF-Token': self.token})

    def get(self, path):
        return self.client.get(f'{API}{path}')

    def analyse(self, save='yes', name='Demo'):
        self.client.post(f'{API}/core/jobs', data={'mode': 'classification', 'dataset': (BytesIO(CSV), 'demo.csv')},
                         headers={'X-CSRF-Token': self.token}, content_type='multipart/form-data')
        self.post('/core/job/configure', {'target': 'label', 'dataset_name': name, 'purpose': ''})
        return self.post('/core/job/generate', {'save_to_history': save}).json['data']

    def close(self):
        self.app.extensions['confidenceguard_store'].cleanup()
        self.app.extensions['datatrust_job_store'].cleanup()


@pytest.fixture
def root(tmp_path):
    return tmp_path / 'history'


def test_nothing_is_saved_before_the_first_use_choice_or_when_opted_out(tmp_path, root):
    s = Session(tmp_path, History(root))
    assert s.get('/history/state').json['data']['saving'] == 'unset'
    assert s.analyse()['history'] == {'saved': False}
    assert s.post('/history/choice', {'saving': 'on'}).json['data']['saving'] == 'on'
    assert s.analyse(save='no')['history'] == {'saved': False}
    assert s.get('/history').json['data']['total'] == 0
    assert s.analyse()['history']['saved'] is True
    assert s.get('/history').json['data']['total'] == 1
    s.close()


def test_saved_analysis_survives_a_restart_with_verified_artifacts(tmp_path, root):
    first = Session(tmp_path, History(root), 'first')
    first.post('/history/choice', {'saving': 'on'})
    eid = first.analyse(name='Restart')['history']['entry']
    first.close()
    second = Session(tmp_path, History(root), 'second')
    entry = second.get(f'/history/{eid}').json['data']
    assert entry['state'] == 'ok' and entry['dataset_name'] == 'Restart' and entry['live'] is False
    assert set(entry['artifacts']) == {'json', 'html'} and entry['score'] is not None
    analysis = second.get(f'/history/{eid}/analysis')
    assert analysis.status_code == 200 and analysis.json['scoring']['status'] == 'computed'
    report = second.get(f'/history/{eid}/report')
    assert report.status_code == 200 and report.headers['X-Frame-Options'] == 'SAMEORIGIN'
    assert second.get(f'/history/{eid}/download/json').headers['Content-Disposition'].startswith('attachment')
    second.close()


def test_history_keeps_no_dataset_source_copies_or_private_material(tmp_path, root):
    s = Session(tmp_path, History(root))
    s.post('/history/choice', {'saving': 'on'})
    s.analyse()
    files = sorted(p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file())
    for f in files:
        assert f == 'history.sqlite3' or (f.startswith('entries/') and f.split('/')[-1] in {'owner', 'manifest.json', 'analysis.json', 'report.html', 'report.pdf'}), f
        data = (root / f).read_bytes()
        assert CSV not in data and CSV.splitlines()[1] not in data
    for p in root.rglob('*'):
        assert (p.stat().st_mode & 0o077) == 0, p
    s.close()


def test_tampered_artifacts_are_refused_and_marked(tmp_path, root):
    s = Session(tmp_path, History(root))
    s.post('/history/choice', {'saving': 'on'})
    eid = s.analyse()['history']['entry']
    report = root / 'entries' / eid / 'report.html'
    report.write_text(report.read_text().replace('</body>', '<script>altered()</script></body>'))
    assert s.get(f'/history/{eid}/report').status_code == 409
    assert s.get(f'/history/{eid}').json['data']['state'] == 'altered'
    s.close()


def test_recovery_handles_every_crash_point(tmp_path, root):
    h = History(root)
    h.set_settings(saving='on')
    s = Session(tmp_path, h)
    eid = s.analyse()['history']['entry']
    s.close()
    # 1. A record interrupted before its atomic rename leaves a staging folder.
    stage = root / 'staging' / ('f' * 32)
    stage.mkdir(mode=0o700); (stage / 'owner').write_text('x'); (stage / 'analysis.json').write_text('{}')
    old = time.time() - 3600
    os.utime(stage, (old, old))
    # 2. Interrupted between rename and index commit: the entry exists without an index row.
    with sqlite3.connect(root / 'history.sqlite3') as db:
        db.execute('DELETE FROM entries WHERE id = ?', (eid,))
        # 3. An intent from a process that is gone.
        db.execute("INSERT INTO pending (id, workflow, display_name, started_at, process, pid) VALUES ('p1', 'core', 'Gone', '2026-10-19T00:00:00+00:00', 'old', 999999999)")
    restarted = History(root)
    assert not stage.exists()
    assert restarted.verify(eid)['state'] == 'ok'
    assert [p['display_name'] for p in restarted.interrupted()] == ['Gone']
    restarted.dismiss('p1')
    assert restarted.interrupted() == []
    # 4. A missing entry folder is reported, not fabricated.
    import shutil
    shutil.rmtree(root / 'entries' / eid)
    assert History(root).verify(eid)['state'] == 'missing'


def test_corrupt_index_is_rebuilt_from_manifests(tmp_path, root):
    h = History(root)
    h.set_settings(saving='on')
    s = Session(tmp_path, h)
    eid = s.analyse()['history']['entry']
    s.close()
    (root / 'history.sqlite3').write_bytes(b'not a database')
    rebuilt = History(root)
    assert rebuilt.verify(eid)['state'] == 'ok'


def test_deletion_refuses_foreign_or_symlinked_folders(tmp_path, root):
    h = History(root)
    h.set_settings(saving='on')
    s = Session(tmp_path, h)
    eid = s.analyse()['history']['entry']
    (root / 'entries' / eid / 'owner').write_text('someone else')
    assert s.post(f'/history/{eid}/delete').status_code == 409
    assert (root / 'entries' / eid).is_dir()
    outside = tmp_path / 'outside'
    outside.mkdir(); (outside / 'keep.txt').write_text('keep')
    import shutil
    shutil.rmtree(root / 'entries' / eid)
    (root / 'entries' / eid).symlink_to(outside, target_is_directory=True)
    with pytest.raises(HistoryError):
        h.delete(eid)
    assert (outside / 'keep.txt').exists()
    s.close()


def test_delete_clear_and_retention(tmp_path, root):
    h = History(root)
    h.set_settings(saving='on')
    s = Session(tmp_path, h)
    first = s.analyse(name='One')['history']['entry']
    second = s.analyse(name='Two')['history']['entry']
    assert s.post(f'/history/{first}/delete').status_code == 200 and not (root / 'entries' / first).exists()
    with sqlite3.connect(root / 'history.sqlite3') as db:
        db.execute("UPDATE entries SET created_at = '2020-01-01T00:00:00+00:00' WHERE id = ?", (second,))
    assert s.post('/history/settings', {'max_age_days': '30', 'max_total_mib': ''}).json['data']['max_age_days'] == 30
    assert s.get('/history').json['data']['total'] == 0
    third = s.analyse(name='Three')['history']['entry']
    assert third and s.post('/history/settings', {'max_total_mib': 'x'}).status_code == 422
    h.set_settings(max_total_bytes=1)
    assert s.get('/history').json['data']['total'] == 0
    h.set_settings(max_total_bytes=None)
    s.analyse(name='Four')
    assert s.post('/history/clear', {}).status_code == 422
    assert s.post('/history/clear', {'confirm': 'delete-all'}).json['data']['deleted'] == 1
    s.close()


def test_search_is_parameterised_and_filters(tmp_path, root):
    h = History(root)
    h.set_settings(saving='on')
    s = Session(tmp_path, h)
    s.analyse(name="O'Brien 100% _data")
    assert s.get('/history?q=brien').json['data']['total'] == 1
    assert s.get('/history?q=100%25').json['data']['total'] == 1
    assert s.get('/history?q=%25').json['data']['total'] == 1  # a literal %, which the name contains
    assert s.get('/history?q=1_0').json['data']['total'] == 0  # _ is literal, not a wildcard for "100"
    assert s.get("/history?q=' OR 1=1 --").json['data']['total'] == 0
    assert s.get('/history?workflow=core').json['data']['total'] == 1
    assert s.get('/history?risk=Nope').json['data']['total'] == 0
    s.close()


def test_access_needs_the_one_time_launch_link_and_csrf(tmp_path, root):
    h = History(root)
    locked = Session(tmp_path, h, 'locked', unlock=False)
    assert locked.get('/history/state').json['data'] == {'enabled': True, 'access': False}
    assert locked.get('/history').status_code == 403
    locked.client.get('/app/?launch=wrong')
    assert locked.get('/history').status_code == 403
    # The token works once.
    assert locked.client.get('/app/?launch=launch-locked').status_code == 303
    assert locked.get('/history').status_code == 200
    stranger = locked.app.test_client()
    stranger.get('/app/?launch=launch-locked')
    assert stranger.get(f'{API}/history').status_code == 403
    assert locked.client.post(f'{API}/history/choice', json={'saving': 'on'}).status_code == 403
    locked.close()


def test_no_history_turns_everything_off(tmp_path):
    s = Session(tmp_path, None)
    assert s.get('/history/state').json['data'] == {'enabled': False}
    assert s.get('/history').status_code == 404
    assert s.analyse()['history'] == {'saved': False}
    s.close()
    captured = {}
    import datatrust.cli as cli
    original = cli.run_ui
    cli.run_ui = lambda **kw: captured.update(kw)
    try:
        assert CliRunner().invoke(main, ['ui', '--no-open', '--no-history']).exit_code == 0
    finally:
        cli.run_ui = original
    assert captured['history_enabled'] is False


def test_pdf_rendered_later_is_attached_to_the_saved_entry(tmp_path, root):
    h = History(root)
    h.set_settings(saving='on')
    s = Session(tmp_path, h)
    eid = s.analyse()['history']['entry']
    assert s.client.get(f'{API}/core/job/download/pdf').headers['Content-Type'] == 'application/pdf'
    s.get('/core/job')  # any API request sweeps
    assert 'pdf' in s.get(f'/history/{eid}').json['data']['artifacts']
    assert s.get(f'/history/{eid}/download/pdf').status_code == 200
    s.close()


def test_run_ui_still_removes_its_workspace_and_prints_the_launch_link(tmp_path, monkeypatch, capsys):
    seen = {}
    def fake_run(app, **kwargs):
        seen['workspace'] = app.extensions['datatrust_job_store'].root
        assert seen['workspace'].is_dir()
    monkeypatch.setattr(web.Flask, 'run', fake_run)
    web.run_ui(port=8123, open_browser=False, history_dir=tmp_path / 'h')
    assert not seen['workspace'].exists()
    assert '/app/?launch=' in capsys.readouterr().out
    assert (tmp_path / 'h' / 'history.sqlite3').is_file()
