"""PDFs of saved analyses: rendered from the verified saved HTML, without the dataset, bound to that HTML's digest,
one conversion at a time, and safe against abandoned locks, deletion, alteration and converter failure."""
import json
import os
import threading
from pathlib import Path

import pytest

from datatrust import DataTrust, DatasetSpec, TaskSpec
from datatrust.history import PDF_LOCK, History, HistoryError
from datatrust.pdf import PDFRenderError, render_pdf_report
from tests.test_history import Session

ROOT = Path(__file__).resolve().parents[1]


def saved_entry(tmp_path, root):
    """A history entry from a real analysis whose dataset is then deleted."""
    data = tmp_path / 'data.csv'
    data.write_text((ROOT / 'validation/data/prepared/german_credit.csv').read_text())
    result = DataTrust.from_spec(DatasetSpec(str(data)), TaskSpec('classification', target='credit_risk')).analyze_result()
    artifacts = result.generate_artifacts(tmp_path / 'out' / 'report.html', json_path=tmp_path / 'out' / 'analysis.json')
    from datatrust.ingestion import source_digest
    kinds = {k: (p, source_digest(p)) for k, p in (('json', artifacts.json_path), ('html', artifacts.html_path))}
    history = History(root)
    eid = history.record(workflow='core', mode='classification', artifacts=kinds, meta={'dataset_name': 'German'})
    data.unlink()
    return history, eid


def manifest(history, eid):
    return json.loads((history.entries / eid / 'manifest.json').read_text())


def fake_pdf(html, out, *, expected_html_sha256=None):
    Path(out).write_bytes(b'%PDF-1.7 test\n')


def test_a_saved_pdf_is_made_from_the_saved_html_after_a_restart(tmp_path):
    history, eid = saved_entry(tmp_path, tmp_path / 'h')
    before = history.usage()['bytes']
    restarted = History(tmp_path / 'h')
    view = restarted.generate_pdf(eid, render_pdf_report)
    assert view['state'] == 'ok' and 'pdf' in view['artifacts']
    record = {a['kind']: a for a in manifest(restarted, eid)['artifacts']}
    assert record['pdf']['html_sha256'] == record['html']['sha256'] and record['pdf']['origin'] == 'saved_html'
    assert restarted.file(eid, 'pdf').read_bytes().startswith(b'%PDF')
    assert restarted.usage()['bytes'] == before + record['pdf']['bytes']  # retention counts the PDF
    assert restarted.generate_pdf(eid, fake_pdf)['artifacts'].count('pdf') == 1  # never replaced
    assert not list(restarted.staging.iterdir()) and not (restarted.entries / eid / PDF_LOCK).exists()


def test_one_conversion_at_a_time(tmp_path):
    history, eid = saved_entry(tmp_path, tmp_path / 'h')
    started, release, errors = threading.Event(), threading.Event(), []

    def slow(html, out, **kw):
        started.set(); release.wait(10); fake_pdf(html, out)
    worker = threading.Thread(target=lambda: history.generate_pdf(eid, slow))
    worker.start(); started.wait(10)
    try:
        history.generate_pdf(eid, fake_pdf)
    except HistoryError as exc:
        errors.append(str(exc))
    release.set(); worker.join(10)
    assert errors and 'already being generated' in errors[0]
    assert [a['kind'] for a in manifest(history, eid)['artifacts']].count('pdf') == 1


@pytest.mark.parametrize('lock', [
    {'pid': 2 ** 22 + 12345, 'started': 0},          # its process is gone
    {'pid': os.getpid(), 'started': 1},              # far older than the stale bound
    'not json',                                      # unreadable and old
])
def test_an_abandoned_lock_does_not_block_generation(tmp_path, lock):
    history, eid = saved_entry(tmp_path, tmp_path / 'h')
    path = history.entries / eid / PDF_LOCK
    path.write_text(lock if isinstance(lock, str) else json.dumps({'token': 'x', 'process': 'gone', **lock}))
    os.utime(path, (1, 1))
    assert 'pdf' in history.generate_pdf(eid, fake_pdf)['artifacts']


def test_a_live_lock_is_respected_and_recovery_clears_abandoned_work(tmp_path):
    history, eid = saved_entry(tmp_path, tmp_path / 'h')
    import time
    (history.entries / eid / PDF_LOCK).write_text(json.dumps({'token': 'x', 'pid': os.getpid(), 'process': 'other', 'started': time.time()}))
    with pytest.raises(HistoryError, match='already being generated'):
        history.generate_pdf(eid, fake_pdf)
    (history.entries / eid / PDF_LOCK).write_text(json.dumps({'token': 'x', 'pid': 2 ** 22 + 12345, 'process': 'gone', 'started': 0}))
    leftover = history.staging / f'.pdf-{eid}-abandoned.pdf'
    leftover.write_bytes(b'partial'); os.utime(leftover, (1, 1))
    History(tmp_path / 'h')
    assert not (history.entries / eid / PDF_LOCK).exists() and not leftover.exists()


def test_deletion_during_generation_keeps_nothing(tmp_path):
    history, eid = saved_entry(tmp_path, tmp_path / 'h')

    def delete_midway(html, out, **kw):
        history.delete(eid); fake_pdf(html, out)
    with pytest.raises(HistoryError, match='deleted while its PDF was generated'):
        history.generate_pdf(eid, delete_midway)
    assert not (history.entries / eid).exists() and not list(history.staging.iterdir())


def test_altered_saved_html_is_never_converted(tmp_path):
    history, eid = saved_entry(tmp_path, tmp_path / 'h')
    report = history.entries / eid / 'report.html'
    report.write_text(report.read_text() + '<!-- changed -->')
    with pytest.raises(HistoryError, match='changed on disk'):
        history.generate_pdf(eid, fake_pdf)
    assert history.verify(eid)['state'] == 'altered'


def test_converter_failure_leaves_the_entry_as_it_was(tmp_path):
    history, eid = saved_entry(tmp_path, tmp_path / 'h')
    before = manifest(history, eid)

    def broken(html, out, **kw):
        raise PDFRenderError('PDF generation is unavailable.')
    with pytest.raises(PDFRenderError):
        history.generate_pdf(eid, broken)
    assert manifest(history, eid) == before and not (history.entries / eid / PDF_LOCK).exists() and not list(history.staging.iterdir())


def test_a_pdf_bound_to_other_html_is_not_served(tmp_path):
    history, eid = saved_entry(tmp_path, tmp_path / 'h')
    history.generate_pdf(eid, fake_pdf)
    value = manifest(history, eid)
    next(a for a in value['artifacts'] if a['kind'] == 'pdf')['html_sha256'] = '0' * 64
    (history.entries / eid / 'manifest.json').write_text(json.dumps(value))
    with pytest.raises(HistoryError, match='different report'):
        history.file(eid, 'pdf')


def test_the_api_makes_a_saved_pdf_with_csrf_and_history_access(tmp_path):
    root = tmp_path / 'history'
    first = Session(tmp_path, History(root), 'first')
    first.post('/history/choice', {'saving': 'on'})
    eid = first.analyse(name='Saved PDF')['history']['entry']
    first.close()
    second = Session(tmp_path, History(root), 'second')
    assert second.client.post(f'/api/datatrust/v1/history/{eid}/pdf', json={}).status_code == 403  # no CSRF token
    locked = Session(tmp_path, History(root), 'third', unlock=False)
    assert locked.post(f'/history/{eid}/pdf').status_code == 403  # no launch-token access
    made = second.post(f'/history/{eid}/pdf')
    assert made.status_code == 200 and 'pdf' in made.json['data']['artifacts']
    assert made.json['data']['presentation']['package_version'] and made.json['data']['presentation']['app_build']
    download = second.get(f'/history/{eid}/download/pdf')
    assert download.status_code == 200 and download.data.startswith(b'%PDF')
    second.close(); locked.close()
