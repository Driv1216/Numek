"""Temporal dashboards (M5; plan Stage 5), built in node from the representative cases.

- every finding is in the ledger with its recorded priority (High or Moderate) and opens the topic chapter that holds
  its cited evidence;
- tile faces state recorded counts: clock cells by parse state, occupied over expected slots where a schedule was
  declared, window comparisons meeting the configured investigation settings, features whose availability is unknown;
- continuity is never assessed without a declared schedule: such sources are listed as not requested (once; an
  excluded continuity check stays excluded);
- ticks are read in the recorded clock unit (nanoseconds, or days for civil dates) and never shown as raw integers;
- unsearched behavioral scope is bounded, and no score is mentioned outside the methodology group.
"""
import json
import re
from datetime import datetime, timezone

import pytest

from dashboard_harness import ROOT, Node, analysis, cases, folder, needs_node, params
from datatrust.dashboard_companion import build

M5 = [c for c in cases() if c['composition'] == 'temporal']
TOPIC = {'chronology': 'chronology', 'ordering': 'chronology', 'repetition': 'chronology', 'elapsed_chronology': 'chronology', 'freshness': 'chronology',
         'continuity': 'continuity', 'panel': 'continuity', 'lookback': 'continuity', 'availability_unknown': 'availability', 'revision_history': 'availability',
         'outcome_maturity': 'availability', 'evaluation': 'evaluation'}


@pytest.fixture(scope='module')
def node(tmp_path_factory):
    return Node(str(ROOT / 'tests/dashboard_entry.ts'), tmp_path_factory.mktemp('temporal'))


def dashboard(node, case):
    value = analysis(case)
    return value, node.call('temporal', value, build(value, (folder(case) / 'report.html').read_text()))


def records(value, check):
    return [e for e in value['evidence'] if e['check_id'] == check]


@needs_node
@pytest.mark.parametrize('case', params(M5))
def test_every_finding_opens_its_cited_topic_with_its_recorded_priority(node, case):
    value, d = dashboard(node, case)
    assert sorted(f['ref'] for f in d['findings']) == sorted(f['id'] for f in value['findings'])
    recorded = {f['id']: f for f in value['findings']}
    topic = {e['id']: TOPIC.get(e['check_id'], 'behavior') for e in value['evidence']}
    tiles = {t['id'] for t in d['tiles']}
    for f in d['findings']:
        assert f['rank'] == {'kind': 'priority', 'value': recorded[f['ref']]['priority'], 'label': recorded[f['ref']]['priority'], 'order': f['rank']['order']}
        assert f['tile'] == topic[recorded[f['ref']]['evidence_refs'][0]] and f['tile'] in tiles
        assert f['locator']['kind'] in ('anchor', 'index_position')
    assert [t['id'] for t in d['tiles']][0] == 'timeline' and d['tiles'][0]['hero']
    text = json.dumps([d['tiles'], d['statement'], d['unknowns']])
    assert not re.search(r'\b\d{13,}\b', text), 'raw ticks on a face'
    assert 'score' not in text.lower()


@needs_node
@pytest.mark.parametrize('case', params(M5))
def test_faces_state_recorded_counts(node, case):
    value, d = dashboard(node, case)
    tiles = {t['id']: t for t in d['tiles']}
    cells = sum(e['data']['cells'] for e in records(value, 'chronology'))
    valid = sum(e['data']['parse_states'].get('valid', 0) for e in records(value, 'chronology'))
    assert tiles['chronology']['label'] == (f'All {cells:,} clock cells valid' if valid == cells else f'{cells - valid:,} of {cells:,} clock cells not valid')
    comparisons = [c for e in records(value, 'behavior_windows') for c in e['data']['comparisons']]
    if comparisons:
        meets = sum(1 for c in comparisons if c.get('distribution_review') or c.get('missingness_review'))
        assert tiles['behavior']['label'] == f'{meets:,} of {len(comparisons):,} window comparisons'
    features = {f for e in records(value, 'availability_unknown') for f in e['data']['features']}
    if features:
        assert tiles['availability']['label'] == f"{len(features):,} feature{'s' if len(features) != 1 else ''}: availability unknown"


@needs_node
@pytest.mark.parametrize('case', params(M5))
def test_continuity_is_assessed_only_against_a_declared_schedule(node, case):
    value, d = dashboard(node, case)
    continuity = records(value, 'continuity')
    declared = [e for e in continuity if e['data']['schedule'] != 'none']
    face = next(t for t in d['tiles'] if t['id'] == 'continuity')
    if declared:
        expected = sum(e['data']['expected_records_or_opportunities'] for e in declared)
        occupied = sum(e['data']['occupied_distinct_slots'] for e in declared)
        assert face['label'] == f'{occupied:,} of {expected:,} expected slots occupied'
        assert not d['coverage']['notRequested']
    else:
        assert face['detail'] == 'No schedule declared: continuity not assessed.'
        excluded = value['coverage']['checks'][continuity[0]['id']]['status'] != 'completed'
        listed = [i for i in d['coverage']['notRequested'] if i['text'].startswith('Continuity against a schedule')]
        assert len(listed) == (0 if excluded else len(continuity))
        if excluded:
            assert any(i['text'] == 'Excluded · continuity' for i in d['coverage']['excluded'])


@needs_node
@pytest.mark.parametrize('case', params([c for c in M5 if c['name'] == 'm5_bike']))
def test_declared_schedule_violation_is_critical_on_continuity(node, case):
    value, d = dashboard(node, case)
    high = next(f for f in value['findings'] if f['priority'] == 'High')
    assert high['evidence_type'] == 'declared_violation'
    assert next(t for t in d['tiles'] if t['id'] == 'continuity')['tone'] == 'critical'


@needs_node
@pytest.mark.parametrize('case', params(M5))
def test_timeline_reads_ticks_in_the_recorded_unit(node, case):
    value, d = dashboard(node, case)
    units = records(value, 'chronology')[0]['data']['clock_units']
    ticks = [int(h[k]) for e in records(value, 'panel') for h in e['data']['retained_histories'] for k in ('first_tick', 'last_tick')]
    to_s = (lambda t: t * 86400) if units == 'civil days' else (lambda t: t / 1e9)
    first = datetime.fromtimestamp(to_s(min(ticks)), timezone.utc).strftime('%Y-%m-%d')
    assert d['tiles'][0]['label'].startswith(first)


@needs_node
@pytest.mark.parametrize('case', params([c for c in M5 if c['name'] == 'm5_electricity']))
def test_unsearched_behavioral_scope_is_bounded(node, case):
    value, d = dashboard(node, case)
    unsearched = [u for u in value['coverage']['unsearched_analytical_scope'] if u.get('unsearched_scope')]
    assert len(d['coverage']['bounded']) == len(unsearched) == 1
    assert d['state']['bounded']
