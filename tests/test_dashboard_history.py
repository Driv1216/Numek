"""History outcomes, filters and saved older results (plan Stage 7).

- each saved entry has one outcome worded for its workflow: "Score X · band" only where a score was recorded; else its
  recorded findings and how many are High, a partial run, or no threshold-level finding. Nothing says "no score";
- the workflow filter uses the index's own workflow column; the classification risk band only ever matches scored
  results (classification, or an M4 advanced analysis with a standalone score);
- older results saved through the history API's own save path (classification schema 1.0, regression 1.1, M3 1.2, and
  M4 to M9 results without finding guidance) reopen through the saved-analysis route onto their workflow's dashboard,
  with the "recorded by an earlier version" note listing exactly what they lack.
"""
import hashlib
from pathlib import Path

import pytest

from dashboard_harness import Node, ROOT, analysis, cases, folder, needs_node
from datatrust.api_web import _history_meta
from datatrust.dashboard_companion import build
from datatrust.history import History
from test_dashboard_companion import Session

WORKFLOW = {'classification': 'core', 'numeric': 'core', 'profile': 'core', 'annotation': 'core', 'multilabel': 'core', 'readiness': 'core',
            'comparison': 'm4', 'structure': 'm4', 'temporal': 'm5', 'text': 'm6', 'image': 'm7', 'cross': 'm9'}
NAMES = ['classification_legacy_app', 'regression_concrete', 'regression_partial', 'regression_rounded_legitimate', 'm3_scene', 'm4_contaminated',
         'm4_advanced_browser', 'm5_bike', 'm5_alfred', 'm6_controls', 'm7_overlay', 'm7_partial', 'm9_pdf_financial', 'm9_clean']
SAVED = [c for c in cases() if c['name'] in NAMES and (folder(c) / 'analysis.json').exists() and (folder(c) / 'report.html').exists()]
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


@pytest.fixture(scope='module')
def saved(tmp_path_factory):
    root = tmp_path_factory.mktemp('history')
    history = History(root / 'history')
    history.set_settings(saving='on')
    ids = {}
    for c in SAVED:
        stored, page = folder(c) / 'analysis.json', folder(c) / 'report.html'
        ids[c['name']] = history.record(workflow=WORKFLOW[c['composition']], mode=c.get('variant') or c['composition'], meta=_history_meta(stored),
                                        artifacts={'json': (stored, sha(stored)), 'html': (page, sha(page))})
    return root, history, ids


@pytest.fixture(scope='module')
def node(tmp_path_factory):
    return Node(str(ROOT / 'tests/dashboard_entry.ts'), tmp_path_factory.mktemp('history-node'))


@needs_node
def test_each_entry_has_one_outcome_worded_for_its_workflow(saved, node):
    _, history, ids = saved
    assert len(ids) == len(SAVED) >= 10
    for e in history.search(limit=100)['items']:
        o = node.call('outcome', {'score': e['score'], 'risk': e['risk_level'], 'findings': e['summary']['findings'], 'status': e['summary']['execution_status']})
        findings = [f for f in e['summary']['findings'] if f['code'] != 'no_major_issues']
        high = sum(f['severity'] == 'High' for f in findings)
        if e['summary']['execution_status'] == 'partial':
            assert o['text'].startswith('Partial')
        elif e['score'] is not None:
            assert o['text'] == f"Score {e['score']:.1f} · {e['risk_level']}"
        elif findings:
            assert o['text'] == f"{len(findings):,} finding{'s' if len(findings) != 1 else ''}" + (f' · {high:,} High' if high else '')
            assert o['cls'] == ('is-elev' if high else 'is-find')
        else:
            assert o['text'] == 'No threshold-level findings'
        assert 'no score' not in o['text'].lower()
        if e['score'] is None:
            assert 'score' not in o['text'].lower()


def test_workflow_and_risk_band_filters_follow_the_index(saved):
    _, history, ids = saved
    for workflow in {WORKFLOW[c['composition']] for c in SAVED}:
        items = history.search(workflow=workflow, limit=100)['items']
        assert items and all(e['workflow'] == workflow for e in items)
        assert len(items) == sum(WORKFLOW[c['composition']] == workflow for c in SAVED)
    scored = [e for e in history.search(limit=100)['items'] if e['risk_level']]
    assert scored, 'the legacy classification result is scored'
    for band in {e['risk_level'] for e in scored}:
        items = history.search(risk=band, limit=100)['items']
        assert items and all(e['score'] is not None and e['workflow'] in {'core', 'm4'} for e in items)


@needs_node
@pytest.mark.parametrize('name', [n for n in NAMES if n in {c['name'] for c in SAVED}])
def test_saved_older_results_reopen_on_their_workflow_dashboard(saved, node, name):
    root, history, ids = saved
    case = next(c for c in SAVED if c['name'] == name)
    s = Session(root, history)
    try:
        response = s.client.get(f"/api/datatrust/v1/history/{ids[name]}/analysis")
        assert response.status_code == 200
        value = response.json
        companion = s.get(f"/history/{ids[name]}/presentation").json['data']
    finally:
        s.close()
    assert value == analysis(case)
    d = node.call(case['composition'], value, companion)
    assert d['composition'] == case['composition']
    assert len(d['findings']) == len([f for f in value.get('findings') or [] if f.get('code') != 'no_major_issues'])
    expected = (['check outcomes'] if not isinstance(value.get('checks'), list) else []) + ([] if value.get('guidance') else ['scope statements (finding guidance)'])
    assert d['state']['historical'] == expected
    # The saved report's own bytes decide every link into it.
    assert all(f['locator']['kind'] in {'anchor', 'section', 'index_position', 'none'} for f in d['findings'])
