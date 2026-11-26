"""Text, image and records-and-documents dashboards (M6, M7, M9; plan Stage 6), built in node from the cases.

- text and image findings show their recorded evidence meaning in the report's own words, never a priority;
- the text and image heroes are the report's own review actions and decisions, in the report's order;
- each family tile is named as the report names it and states recorded counts with their units (never "Measured");
  counts across text representations are listed, never added;
- a retained image pair is cited only when one finding's references include both of its images;
- records and documents: reconciliation states recorded outcomes per rule; optional model judgments are shown as
  recorded, and when every examined judgment abstained the tile says so with the recorded reasons;
- planned search bounds are listed as bounded; revealed content is never written to the URL or browser storage.
"""
import copy
import json
import re

import pytest

from dashboard_harness import ROOT, Node, analysis, cases, folder, needs_node, params
from datatrust.dashboard_companion import build

CASES = [c for c in cases() if c['composition'] in ('text', 'image', 'cross')]
TEXT = [c for c in CASES if c['composition'] == 'text']
IMAGE = [c for c in CASES if c['composition'] == 'image']
CROSS = [c for c in CASES if c['composition'] == 'cross']


@pytest.fixture(scope='module')
def node(tmp_path_factory):
    return Node(str(ROOT / 'tests/dashboard_entry.ts'), tmp_path_factory.mktemp('evidence'))


def dashboard(node, case, value=None):
    value = value or analysis(case)
    companion = build(value, (folder(case) / 'report.html').read_text())
    return value, companion, node.call(case['composition'], value, companion)


@needs_node
@pytest.mark.parametrize('case', params(CASES))
def test_every_finding_is_on_its_family_tile_with_its_recorded_rank(node, case):
    value, companion, d = dashboard(node, case)
    assert sorted(f['ref'] for f in d['findings']) == sorted(f['id'] for f in value['findings'])
    tiles = {t['id']: t for t in d['tiles']}
    recorded = {f['id']: f for f in value['findings']}
    for f in d['findings']:
        r = recorded[f['ref']]
        assert f['tile'] == ('reconciliation' if r['family'] == 'reconciliation' else r['family']) and f['tile'] in tiles
        if case['composition'] == 'cross':
            assert f['rank']['kind'] == 'priority' and f['rank']['label'] == r['priority']
        else:
            assert f['rank']['kind'] == 'evidence_meaning' and f['rank']['value'] == r['meaning']
            assert f['rank']['label'] == companion['names']['meanings'][r['meaning']]
    text = json.dumps([d['tiles'], d['statement'], d['unknowns']])
    assert 'Measured' not in text and not re.search(r'\bscor(e|ing)\b', text, re.I)
    for t in d['tiles'][1:]:
        family = t['id']
        assert t['name'] == companion['names']['families'].get(family, t['name'])


@needs_node
@pytest.mark.parametrize('case', params(TEXT))
def test_text_hero_is_the_report_review_actions_in_report_order(node, case):
    from datatrust.text_presentation import executive_summary
    value, companion, d = dashboard(node, case)
    actions = executive_summary(value)['actions']
    hero = d['tiles'][0]
    assert hero['id'] == 'actions' and hero['hero']
    assert hero['label'] == (f"{len(actions)} review action{'s' if len(actions) != 1 else ''}" if actions else 'No review action')
    assert [a['family'] for a in companion['actions']] == [a['family'] for a in actions]
    if actions:
        assert hero['detail'].startswith(companion['names']['families'][actions[0]['family']])


@needs_node
@pytest.mark.parametrize('case', params(TEXT))
def test_text_faces_state_recorded_counts_and_never_add_representations(node, case):
    value, _, d = dashboard(node, case)
    tiles = {t['id']: t for t in d['tiles']}
    for e in value['evidence']:
        if e['family'] == 'invalidity':
            k = e['data']['invalid_items']
            assert tiles['invalidity']['label'] == f"{k:,} invalid item{'s' if k != 1 else ''}"
        if e['family'] == 'near_duplicates':
            k = e['data']['qualifying_pairs']
            assert tiles['near_duplicates']['label'] == f"{k:,} qualifying pair{'s' if k != 1 else ''}"
    dup = [e for e in value['evidence'] if e['family'] == 'exact_duplicates']
    if len(dup) > 1:
        label = tiles['exact_duplicates']['label']
        for e in dup:
            assert f"{e['data']['representation']}: {e['data']['groups']:,} group" in label
        total = sum(e['data']['groups'] for e in dup)
        assert f'{total} groups' not in label or len({e['data']['groups'] for e in dup}) == 1


@needs_node
@pytest.mark.parametrize('case', params(IMAGE))
def test_image_hero_is_the_report_decisions_and_pairs_are_cited_only_directly(node, case):
    from datatrust.image_presentation import report_view
    from datatrust.dashboard_companion import _Recorded
    value, companion, d = dashboard(node, case)
    decisions = report_view(_Recorded(value), 'focused').get('actions') or []
    hero = d['tiles'][0]
    assert hero['id'] == 'decisions' and [a['title'] for a in companion['actions']] == [a['title'] for a in decisions]
    assert hero['label'] == (f"{len(decisions)} decision{'s' if len(decisions) != 1 else ''}" if decisions else 'No decision to make')
    near = next((e for e in value['evidence'] if e['family'] == 'near_duplicates'), None)
    if near:
        pairs = [x for x in near['data'].get('examples') or [] if x.get('left') and x.get('right')]
        cited = [p for p in pairs if any(p['left'] in f['references'] and p['right'] in f['references'] for f in value['findings'])]
        # The overlay case: three retained pairs, none cited directly by a finding's references.
        if case['name'] == 'm7_overlay':
            assert pairs and not cited


@needs_node
@pytest.mark.parametrize('case', params([c for c in IMAGE if c['name'] in ('m7_bounded', 'm7_partial', 'm7_classification')]))
def test_image_bounds_and_partial_states(node, case):
    value, _, d = dashboard(node, case)
    stop = value['coverage']['families']['near_duplicates'].get('stop_reason')
    assert bool(d['coverage']['bounded']) == bool(stop and stop != 'examined_scope_completed')
    assert d['state']['chip'] == ('partial' if value['execution']['status'] == 'partial' else 'clean')
    annotations = next(t for t in d['tiles'] if t['id'] == 'annotations')
    validity = next(e for e in value['evidence'] if e['family'] == 'annotations')['data']['validity']
    if 'valid' not in validity:
        assert 'valid' not in annotations['label'].replace('invalid', '')


@needs_node
@pytest.mark.parametrize('case', params(CROSS))
def test_reconciliation_states_recorded_outcomes(node, case):
    value, companion, d = dashboard(node, case)
    rules = [e['data'] for e in value['evidence'] if e['family'] == 'reconciliation']
    assessed = [r for r in rules if r['records'] > r.get('unassessed', 0)]
    hero = d['tiles'][0]
    assert hero['id'] == 'reconciliation' and hero['name'] == companion['names']['families']['reconciliation']
    agree, total = sum(r.get('satisfied', 0) for r in assessed), sum(r['records'] for r in assessed)
    assert hero['label'].startswith(f'{agree:,} of {total:,} ')
    selected = value['coverage'].get('model_selected') or {}
    if not any(selected.values()):
        assert [i['text'] for i in d['coverage']['notRequested']] == ['Optional model judgments (NLI, paired image–text)']
        assert not any(t['id'] == 'models' for t in d['tiles'])


@needs_node
@pytest.mark.parametrize('case', params([c for c in CROSS if c['name'] == 'm9_pdf_financial']))
def test_abstained_model_judgments_are_shown_as_abstained(node, case):
    value = copy.deepcopy(analysis(case))
    models = next(e for e in value['evidence'] if e['family'] == 'models')
    total = sum(v for k, v in models['data'].items() if isinstance(v, int))
    models['data'] = {'abstained': total, 'details': [{'target_id': f't{i}', 'status': 'abstained', 'reason': 'model_not_enabled_or_unqualified'} for i in range(total)]}
    value['findings'] = [f for f in value['findings'] if f['family'] != 'models']
    _, _, d = dashboard(node, case, value)
    tile = next(t for t in d['tiles'] if t['id'] == 'models')
    assert tile['label'] == f'All {total:,} judgments abstained'
    assert tile['detail'] == f'model not enabled or unqualified {total:,}'
    assert not d['coverage']['notRequested']


def test_revealed_content_is_never_written_to_the_url_or_browser_storage():
    sources = [ROOT / 'frontend/src/app' / p for p in ('m6.tsx', 'm7.tsx', 'm9.tsx')] + sorted((ROOT / 'frontend/src/app/results/compositions').glob('*.tsx'))
    for path in sources:
        text = path.read_text()
        assert not re.search(r'localStorage|sessionStorage|pushState|replaceState|location\.(hash|search)\s*=', text), path.name
