"""Comparison and advanced single-dataset dashboards (M4; plan Stage 4), built in node from the representative cases.

- pair findings are scoped "role ↔ role" and keep their recorded priority; a declared violation says so on its tile;
- population faces rank the recorded CDF distances, largest first;
- before and after leads with the recorded row reconciliation; the advanced analysis leads with its structure;
- blocked alignment is an exclusion, listed once, and never makes a completed run partial; a failed check does;
- bounded diagnostics (unsearched scope) are listed in the bounded group;
- no score is mentioned outside the methodology group unless a standalone classification score was recorded.
"""
import json

import pytest

from dashboard_harness import ROOT, Node, analysis, cases, folder, needs_node, params
from datatrust.dashboard_companion import build

M4 = [c for c in cases() if c['composition'] in ('comparison', 'structure')]


@pytest.fixture(scope='module')
def node(tmp_path_factory):
    return Node(str(ROOT / 'tests/dashboard_entry.ts'), tmp_path_factory.mktemp('comparison'))


def dashboard(node, case):
    value = analysis(case)
    return value, node.call(case['composition'], value, build(value, (folder(case) / 'report.html').read_text()))


def named(name):
    return [c for c in M4 if c['name'] == name]


@needs_node
@pytest.mark.parametrize('case', params(M4))
def test_every_m4_finding_is_in_the_ledger_with_its_recorded_priority(node, case):
    value, d = dashboard(node, case)
    assert d['composition'] == case['composition']
    assert sorted(f['ref'] for f in d['findings']) == sorted(f['id'] for f in value['findings'])
    recorded = {f['id']: f for f in value['findings']}
    tiles = {t['id']: t for t in d['tiles']}
    for f in d['findings']:
        assert f['rank']['kind'] == 'priority' and f['rank']['label'] == recorded[f['ref']]['priority']
        assert f['tile'] in tiles
    heroes = [t for t in d['tiles'] if t['hero']]
    assert len(heroes) == 1
    text = json.dumps([d['tiles'], d['statement'], d['unknowns']])
    if not (value.get('scoring') or {}).get('status') == 'available':
        assert 'score' not in text.lower().replace('scored', ''), 'scoring is stated once, in the methodology group'


@needs_node
@pytest.mark.parametrize('case', params(named('m4_contaminated') + named('m4_splits_browser')))
def test_split_violation_is_named_on_its_pair(node, case):
    value, d = dashboard(node, case)
    overlap = next(t for t in d['tiles'] if t['id'].endswith('.split_integrity'))
    assert overlap['label'] == 'High · declared requirement violated' and overlap['tone'] == 'critical'
    roles = [i['role'] for i in value['inputs']]
    pair = next(f for f in d['findings'] if f['tile'] == overlap['id'])
    assert pair['scope'] == f'{roles[0]} ↔ {roles[1]}'


@needs_node
@pytest.mark.parametrize('case', params(named('m4_shifted')))
def test_schema_change_names_the_recorded_storage_change(node, case):
    value, d = dashboard(node, case)
    change = value['coverage']['measurements']['reference:current.schema']['changes'][0]
    schema = next(t for t in d['tiles'] if t['id'].endswith('.schema'))
    assert schema['detail'] == f"{change['column']}: {change['left_storage']} → {change['right_storage']}"


@needs_node
@pytest.mark.parametrize('case', params(named('m4_before_after')))
def test_before_after_leads_with_recorded_lineage(node, case):
    value, d = dashboard(node, case)
    m = value['coverage']['measurements']['source1:source2.before_after']
    hero = d['tiles'][0]
    assert hero['hero'] and hero['id'].endswith('.before_after')
    assert hero['label'] == f"{m['observed']['rows']['before']:,} → {m['observed']['rows']['after']:,} rows"
    assert hero['detail'] == m['observed']['rows']['explanation']
    # Blocked alignment (telephone was dropped) is an exclusion, listed once; the completed run is not partial.
    assert value['execution']['status'] == 'completed' and d['state']['chip'] == 'findings'
    assert not d['coverage']['notCompleted'] and len(d['coverage']['excluded']) == 1
    assert d['coverage']['excluded'][0]['text'] == 'Excluded · Columns not aligned · reference ↔ current'


@needs_node
@pytest.mark.parametrize('case', params(named('m4_before_after') + named('m4_shifted')))
def test_population_face_names_the_largest_recorded_cdf_distance(node, case):
    value, d = dashboard(node, case)
    for t in (t for t in d['tiles'] if t['id'].endswith('.populations')):
        columns = value['coverage']['measurements'][t['id']]['columns']
        top = max(columns, key=lambda c: c.get('cdf_distance') or 0)
        if not any(f['tile'] == t['id'] for f in d['findings']):
            assert top['column'] in t['detail']


@needs_node
@pytest.mark.parametrize('case', params(named('m4_partial') + named('m4_advanced_partial')))
def test_failed_diagnostic_makes_the_result_partial_once(node, case):
    value, d = dashboard(node, case)
    failed = [c for c in value['checks'] if c['execution'] == 'failed']
    assert failed and d['state']['chip'] == 'partial'
    assert len(d['coverage']['notCompleted']) == len(failed)
    assert all(item['text'].startswith('Failed · ') for item in d['coverage']['notCompleted'])


@needs_node
@pytest.mark.parametrize('case', params(named('m4_wide') + named('m4_long_headers')))
def test_advanced_analysis_leads_with_structure_and_lists_bounded_diagnostics(node, case):
    value, d = dashboard(node, case)
    hero = d['tiles'][0]
    m = value['coverage']['measurements']['dataset.structure']
    assert hero['id'] == 'dataset.structure' and hero['label'] == f"{m['row_count']:,} rows · {m['column_count']:,} columns"
    unsearched = [k for k, diag in value['coverage']['diagnostics'].items() if (diag.get('unsearched_scope') or 0) > 0]
    assert len(d['coverage']['bounded']) == len(unsearched) > 0
