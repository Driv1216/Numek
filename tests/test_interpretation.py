"""interpretation_v1 (src/datatrust/interpretation.py): the one deterministic interpretation shared by the dashboards and,
from Stage 6D, the reports.

- every unknown the guidance catalogue or a method can record maps to exactly one row of the resolution table: a
  declaration that would resolve it, or explicitly none;
- every number in a summary sentence is a recorded value or a count of recorded items, recomputed from the result;
- per-finding guidance is the recorded guidance, unchanged; results without guidance get none (nothing back-filled);
- the companion carries exactly interpret()'s output, and the dashboard carries exactly the companion's;
- declarations named as "would make this more conclusive" follow from the recorded configuration.
"""
import json
import re

import pytest

from dashboard_harness import ROOT, Node, analysis, cases, folder, needs_node, params
from datatrust import guidance as G
from datatrust.dashboard_companion import build
from datatrust.interpretation import UNKNOWN_RESOLUTION, interpret, resolve_fact, resolution
from datatrust.report_identity import family_of

CASES = [c for c in cases() if c['composition'] != 'generic']


def recordable_unknowns():
    lines = {u for entry in G.CATALOGUE.values() for u in entry['unknowns']}
    lines |= {u for method in G.METHOD_UNKNOWNS.values() for u in method}
    # the forms _scope writes once context declarations exist
    lines |= {'5 possible placeholder or sentinel codes were suggested but none was declared, so none was interpreted.',
              'Placeholder and sentinel codes were interpreted only where you declared them (age); other values were taken as recorded.',
              'Leakage was checked by column name and by a bounded target-dependency search (16 features checked); no prediction point was declared, so availability was not verified.',
              'Leakage was checked by column name and by a bounded target-dependency search (16 features checked); availability is as you declared it for the prediction point.'}
    return lines


def test_every_recordable_unknown_maps_to_exactly_one_resolution():
    for line in recordable_unknowns():
        matches = [key for pattern, key in UNKNOWN_RESOLUTION if re.search(pattern, line)]
        assert len(matches) == 1, (line, matches)


@pytest.mark.parametrize('case', params(CASES))
def test_summary_numbers_trace_to_the_recorded_result_and_guidance_is_never_back_filled(case):
    value = analysis(case)
    out = interpret(value, family_of(value))
    for sentence in out['summary']:
        facts = sentence['facts']
        for fact in facts:
            assert resolve_fact(value, fact) == fact['value'], (sentence['text'], fact)
        allowed = {str(f['value']) for f in facts} | {f'{f["value"]:,}' for f in facts if isinstance(f['value'], int) and not isinstance(f['value'], bool)}
        for number in re.findall(r'\d[\d,]*(?:\.\d+)?', sentence['text']):
            assert number in allowed, (case['name'], sentence['text'], number, allowed)
    recorded = value.get('guidance')
    if recorded:
        assert out['guidance_recorded'] and {k: {kk: vv for kk, vv in v.items() if kk != 'ref'} for k, v in out['findings'].items()} == recorded['items']
        for line in recorded['scope']['unknowns']:
            resolution(line)  # every recorded unknown is in the table (KeyError otherwise)
    else:
        assert not out['guidance_recorded'] and out['findings'] == {}
    assert (out['clean'] is None) == bool([f for f in value.get('findings') or [] if f.get('code') != 'no_major_issues'])


@pytest.mark.parametrize('case', params(CASES))
def test_the_companion_carries_exactly_the_interpretation(case):
    value = analysis(case)
    companion = build(value, (folder(case) / 'report.html').read_text())
    assert companion['interpretation'] == interpret(value, family_of(value))


def test_an_unknown_methodology_gets_no_interpretation():
    case = next(c for c in cases() if c['composition'] == 'generic')
    assert build(analysis(case))['interpretation'] is None


EXPECTED = {
    'bank_full': {'prediction_point', 'code_meanings'},
    'bike_hour': {'prediction_point', 'code_meanings'},
    'm4_shifted': {'identity_keys'},
    'm5_retail': {'schedule'},
    'm9_clean': {'models'},
    'energy_clustering': {'scale_sensitivity'},
}


@pytest.mark.parametrize('case', params([c for c in CASES if c['name'] in EXPECTED]))
def test_more_conclusive_follows_the_recorded_configuration(case):
    value = analysis(case)
    keys = {m['key'] for m in interpret(value, family_of(value))['more_conclusive']}
    assert EXPECTED[case['name']] <= keys, keys


@pytest.mark.parametrize('case', params([c for c in CASES if c['name'] in ('wide_200', 'm6_clean', 'm9_clean')]))
def test_a_clean_result_states_completed_scope(case):
    value = analysis(case)
    clean = interpret(value, family_of(value))['clean']
    checks = [c for c in value.get('checks') or [] if isinstance(c, dict)]
    assert clean['checks_recorded'] == len(checks) and 0 < clean['checks_completed'] <= len(checks)


@pytest.fixture(scope='module')
def node(tmp_path_factory):
    return Node(str(ROOT / 'tests/dashboard_entry.ts'), tmp_path_factory.mktemp('interpretation'))


@needs_node
@pytest.mark.parametrize('case', params([c for c in CASES if c['name'] in ('german_credit', 'bike_hour', 'm4_contaminated', 'm5_beijing', 'm6_controls', 'm7_overlay', 'm9_pdf_financial', 'wide_200')]))
def test_the_dashboard_carries_the_companion_interpretation_unchanged(node, case):
    value = analysis(case)
    companion = build(value, (folder(case) / 'report.html').read_text())
    d = node.call(case['composition'], value, companion)
    assert d['interpretation'] == json.loads(json.dumps(companion['interpretation']))
