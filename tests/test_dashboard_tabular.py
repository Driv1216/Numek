"""Classification and dataset-profile dashboards (plan Stage 2), built in node from every representative case.

- every finding code the classification and unlabeled engines can emit has an explicit tile route;
- the score appears only where scoring was computed, and equals the recorded values and governing cap;
- tile faces repeat recorded values only (class shares, rows, columns, flag counts within the column count);
- no tile from the old fixed universe (time, text, images, documents, local, reports) is drawn;
- an unscored profile never mentions a score outside the coverage ledger's methodology group.
"""
import json
import re

import pytest

from dashboard_harness import ROOT, Node, analysis, cases, folder, needs_node, params
from datatrust.dashboard_companion import build

ROUTES = json.loads((ROOT / 'frontend/src/app/results/finding-routes.json').read_text())
CLASSIFICATION_TILES = {'score', 'target', 'leakage', 'missing', 'repeats', 'numeric', 'columns', 'other'}
PROFILE_TILES = {'profile', 'missing', 'repeats', 'variation', 'numeric', 'columns', 'parsing', 'other'}
TABULAR = {'classification', 'profile', 'numeric', 'annotation', 'multilabel', 'readiness'}
OLD_UNIVERSE = {'time', 'text', 'images', 'docs', 'local', 'reports', 'conflicts', 'imbalance', 'relations'}


def codes(source):
    found = set(re.findall(r"(?:\badd|_risk)\(\s*['\"]([a-z_]+)['\"]\s*,", source))
    found |= set(re.findall(r"\(\s*['\"]([a-z_]+)['\"]\s*,\s*['\"][A-Z][a-z]+[ -]", source))
    # (flag, code, title, ...) tuples that one add() call iterates over
    found |= set(re.findall(r"\(\s*['\"][a-z_]+['\"]\s*,\s*['\"]([a-z_]+)['\"]\s*,\s*['\"][A-Z]", source))
    return found - {'no_major_issues'}


def engine_codes():
    text = (ROOT / 'src/datatrust/risks.py').read_text()
    classification = codes(text[:text.index('def summarize_risks')])
    unlabeled = codes(text[text.index('def build_unlabeled_findings'):text.index('def build_regression_findings')])
    contextual = set(re.findall(r'_finding\("([a-z_]+)"', (ROOT / 'src/datatrust/contextual.py').read_text()))
    return classification, unlabeled, contextual


def test_every_emitted_code_is_routed_to_a_tile_that_exists():
    classification, unlabeled, contextual = engine_codes()
    assert len(classification) >= 12 and len(unlabeled) >= 8 and contextual
    assert classification | contextual <= set(ROUTES['classification']), 'route these classification codes'
    assert unlabeled | contextual <= set(ROUTES['profile']), 'route these unlabeled codes'
    assert set(ROUTES['classification'].values()) <= CLASSIFICATION_TILES and set(ROUTES['profile'].values()) <= PROFILE_TILES


@pytest.fixture(scope='module')
def node(tmp_path_factory):
    return Node(str(ROOT / 'tests/dashboard_entry.ts'), tmp_path_factory.mktemp('tabular'))


def dashboard(node, case):
    value = analysis(case)
    return value, node.call(case['composition'], value, build(value, (folder(case) / 'report.html').read_text()))


@needs_node
@pytest.mark.parametrize('case', params([c for c in cases() if c['composition'] in TABULAR]))
def test_every_tabular_dashboard_routes_and_numbers_its_tiles(node, case):
    value, d = dashboard(node, case)
    ids = [t['id'] for t in d['tiles']]
    assert not set(ids) & OLD_UNIVERSE and len(ids) == len(set(ids)) and sum(t['hero'] for t in d['tiles']) <= 1
    assert all(f['tile'] in ids and f['tile'] != 'other' for f in d['findings']), 'corpus findings all open a drawn, explicitly routed tile'
    assert len([f for f in d['findings'] if not f['context']]) == len([f for f in value.get('findings') or [] if f.get('code') != 'no_major_issues'])
    if (value.get('scoring') or {}).get('status') != 'computed':
        assert 'score' not in ids
        text = ' '.join(filter(None, [d['statement'], *[t['label'] + ' ' + t['detail'] for t in d['tiles']], *d['unknowns']]))
        assert not re.search(r'\bscor(e|ing)\b', text, re.I), 'the no-score reason belongs to methodology only'


def tile(d, tile_id):
    return next(t for t in d['tiles'] if t['id'] == tile_id)


@needs_node
def test_regression_shows_its_recorded_target_and_relationship(node):
    case = next(c for c in cases() if c['name'] == 'bike_hour')
    value, d = dashboard(node, case)
    s = value['profile']['regression']['target_statistics']
    assert tile(d, 'target')['label'] == f"{s['finite_count']:,} of {s['row_count']:,} finite"
    rel = tile(d, 'relationships')
    assert rel['label'] == '1 supported relationship' and 'cnt = casual + registered' in rel['detail']
    assert next(f for f in d['findings'] if f['ref'] == 'regression_relationships_unknown')['tile'] == 'relationships'


@needs_node
def test_annotation_regression_states_its_declared_violations(node):
    value, d = dashboard(node, next(c for c in cases() if c['name'] == 'annotation_regression_single'))
    rule = value['profile']['multioutput_regression']['outputs'][0]['constraints']['rules'][0]
    assert tile(d, 'constraints')['label'] == f"{value['profile']['multioutput_regression']['outputs'][0]['constraints']['violation_union_count']} violating values"
    assert f"{rule['count']:,} of {rule['denominator']:,}" in tile(d, 'constraints')['detail'] and 'annotations' in [t['id'] for t in d['tiles']]


@needs_node
def test_multioutput_counts_complete_vectors_and_pairs_outputs(node):
    value, d = dashboard(node, next(c for c in cases() if c['name'] == 'multioutput_linnerud'))
    mo, rows = value['profile']['multioutput_regression'], value['profile']['row_count']
    assert tile(d, 'target')['label'] == f"{mo['complete_vector_count']:,} of {rows:,} complete vectors"
    assert tile(d, 'dependencies')['label'].startswith(f"{len(mo['output_dependencies'])} output pair")


@needs_node
def test_multilabel_and_annotation_gaps_read_from_recorded_coverage(node):
    value, d = dashboard(node, next(c for c in cases() if c['name'] == 'scene_masked'))
    gaps = sum(t['unavailable_expected'] for t in value['profile']['annotations']['targets'])
    assert tile(d, 'annotations')['label'] == f"{gaps:,} expected annotations missing"
    assert tile(d, 'labels')['label'] == f"{value['profile']['multilabel']['complete_vector_count']:,} of {value['profile']['row_count']:,} complete"


@needs_node
@pytest.mark.parametrize('name', ['energy_clustering', 'energy_anomaly'])
def test_readiness_never_gives_a_verdict(node, name):
    value, d = dashboard(node, next(c for c in cases() if c['name'] == name))
    r = value['profile']['readiness']
    hero = tile(d, 'geometry')
    assert hero['label'] == f"{len(r['quantitative_features'])} quantitative · {len(r['geometry_exclusions'])} excluded" and hero['detail'] == 'No model fitted; no readiness verdict.'
    assert ('extremes' in [t['id'] for t in d['tiles']]) == (name == 'energy_anomaly')


@needs_node
@pytest.mark.parametrize('case', params([c for c in cases() if c['composition'] in {'classification', 'profile'}]))
def test_tabular_dashboard_shows_recorded_values_only(node, case):
    value, d = dashboard(node, case)
    p = value['profile']
    ids = [t['id'] for t in d['tiles']]
    assert not set(ids) & OLD_UNIVERSE and len(ids) == len(set(ids))
    assert all(f['tile'] in ids for f in d['findings']), 'every finding opens a tile that exists'
    assert all(f['tile'] != 'other' for f in d['findings']), 'corpus findings are all explicitly routed'
    assert d['identity']['scale'] == f"{p['row_count']:,} rows × {p['column_count']:,} columns"
    values = value['scoring'].get('values') if value['scoring'].get('status') == 'computed' else None
    if case['composition'] == 'classification':
        assert ('score' in ids) == bool(values)
        if values:
            score = next(t for t in d['tiles'] if t['id'] == 'score')
            assert score['hero'] and score['label'] == f"{values['overall']:.1f} · {values['risk_level']}"
            caps = [g['cap'] for g in values['guardrails']]
            assert (f"Capped at {min(caps):g}" in score['detail']) if caps else ('no guardrail applied' in score['detail'])
        target = next(t for t in d['tiles'] if t['id'] == 'target')
        assert f"Majority {p['majority_class_baseline']:g}%" in target['detail']
    else:
        assert 'score' not in ids
        hero = next(t for t in d['tiles'] if t['hero'])
        assert hero['label'] == f"{p['row_count']:,} rows × {p['column_count']:,} columns"
        text = ' '.join(filter(None, [d['statement'], *[t['label'] + ' ' + t['detail'] for t in d['tiles']], *d['unknowns']]))
        assert not re.search(r'\bscor(e|ing)\b', text, re.I), 'the no-score reason belongs to methodology only'
        assert [m['text'] for m in d['coverage']['methodology']].count('No overall score') == 1
