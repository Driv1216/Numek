"""The results dashboard's shared projections (frontend/src/app/results/normalize.ts and resolve.ts), run in node
against every representative case with the real presentation companion.

- the composition comes from the recorded methodology, never the saved mode (an unknown one renders as recorded);
- the ledger lists every finding exactly once with its recorded rank; text and image ranks stay evidence meanings;
- the result state never confuses clean with incomplete, and coverage says what did not complete;
- the no-score reason appears once, in methodology, and never among the unknowns.
"""
import json

import pytest

from dashboard_harness import Node, analysis, cases, folder, needs_node, params
from datatrust.dashboard_companion import build

pytestmark = needs_node


@pytest.fixture(scope='module')
def normalize(tmp_path_factory):
    return Node('src/app/results/normalize.ts', tmp_path_factory.mktemp('normalize'))


@pytest.fixture(scope='module')
def resolve(tmp_path_factory):
    return Node('src/app/results/resolve.ts', tmp_path_factory.mktemp('resolve'))


def companion(case):
    return build(analysis(case), (folder(case) / 'report.html').read_text())


@pytest.mark.parametrize('case', params())
def test_composition_comes_from_the_recorded_methodology(resolve, case):
    assert resolve.call('resolveComposition', analysis(case))['composition'] == case['composition']


@pytest.mark.parametrize('case', params())
def test_ledger_lists_every_finding_once_with_its_recorded_rank(normalize, case):
    value, c = analysis(case), companion(case)
    rows = normalize.call('ledger', value, c)
    canonical = [(i, f) for i, f in enumerate(value.get('findings') or []) if f.get('code') != 'no_major_issues']
    contextual = (value.get('contextual') or {}).get('findings') or []
    assert len(rows) == len(canonical) + len(contextual)
    by_index = {r['index']: r for r in rows}
    for i, f in canonical:
        r = by_index[i]
        if 'meaning' in f and not (f.get('priority') or f.get('severity')):
            assert r['rank']['kind'] == 'evidence_meaning' and r['rank']['value'] == f['meaning']
            assert r['rank']['label'] not in {'High', 'Moderate', 'Low'}
        else:
            assert r['rank']['kind'] == 'priority' and r['rank']['value'].lower() == str(f.get('priority') or f.get('severity')).lower()
        named = next(x for x in c['findings'] if x['index'] == i)
        assert r['title'] == named['title'] and r['locator'] == named['locator']
    if all(r['rank']['kind'] == 'priority' for r in rows):
        assert [r['rank']['order'] for r in rows] == sorted(r['rank']['order'] for r in rows)


@pytest.mark.parametrize('case', params())
def test_state_and_coverage_are_honest(normalize, case):
    value, c = analysis(case), companion(case)
    cov = normalize.call('coverage', value, c, {})
    rows = normalize.call('ledger', value, c)
    state = normalize.call('resultState', value, len(rows), cov, False)
    if 'partial' in case['tags']:
        assert state['run'] == 'partial' and state['chip'] == 'partial'
    if state['chip'] == 'partial':
        assert state['run'] == 'partial' or cov['notCompleted'], 'partial needs a partial run or a check that did not complete'
        assert all(not x['text'].startswith('Excluded') for x in cov['notCompleted']), 'an excluded check is a precondition, not incompleteness'
    scope = ((value.get('guidance') or {}).get('scope') or {}).get('not_completed') or []
    if scope and all(c.get('state') == 'excluded' for c in scope) and value['execution']['status'] == 'completed':
        assert state['chip'] != 'partial'
    if 'clean' in case['tags'] and 'partial' not in case['tags']:
        assert state['chip'] in {'clean', 'partial'} and state['findings'] == 0
        assert state['chip'] == 'clean' or cov['notCompleted'], 'a clean chip is only replaced by recorded incompleteness'
    scored = (value.get('scoring') or {}).get('status') in {'computed', 'available'}
    no_score = [m for m in cov['methodology'] if m['text'] == 'No overall score']
    assert len(no_score) == (0 if scored else 1)
    for line in normalize.call('unknowns', value):
        assert 'score' not in line.lower(), 'the no-score reason is stated once, in methodology'


def test_partial_image_run_states_its_failed_check(normalize):
    value = analysis('m7_partial')
    cov = normalize.call('coverage', value, companion('m7_partial'), {})
    assert any('embeddings' in x['text'] for x in cov['notCompleted'])
