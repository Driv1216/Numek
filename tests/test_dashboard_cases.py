"""The results-dashboard redesign corpus (validation/dashboard/cases.json) and its node harness.

Stage 0 guarantees, checked against the materialised cases (python -m validation.dashboard.corpus):
- the manifest is well formed: every stored source exists, every controlled builder exists, tags use the vocabulary;
- each case's recorded facts match its tags (clean, partial, high, findings) and its methodology matches the composition
  the redesign will render it with, so later stages build on correctly labelled evidence;
- stored cases are byte-identical copies of the milestone files, which stay untouched;
- every case has a rendered canonical report;
- the node harness runs the app's own ledger projection on every case, and every finding stays reachable.
"""
import hashlib
import json

import pytest

from dashboard_harness import COMPOSITIONS, ROOT, WORKFLOWS, Node, analysis, cases, folder, manifest, needs_node, params, record

# The composition each methodology is rendered with (plan section F); M4 splits by preset or mode.
METHOD_COMPOSITION = {
    'classification_legacy_2026_08_13': 'classification', 'tabular_regression_v1': 'numeric',
    'tabular_annotation_regression_v1': 'numeric', 'tabular_multioutput_regression_v1': 'numeric',
    'unlabeled_csv_profile_v1': 'profile', 'tabular_role_profile_v1': 'profile', 'tabular_partial_classification_v1': 'annotation',
    'tabular_multilabel_v1': 'multilabel', 'tabular_clustering_readiness_v1': 'readiness', 'tabular_anomaly_readiness_v1': 'readiness', 'tabular_clustering_readiness_v2': 'readiness', 'tabular_anomaly_readiness_v2': 'readiness',
    'temporal_reliability_v1': 'temporal', 'text_reliability_v1': 'text', 'image_reliability_v1': 'image',
    'cross_representation_reliability_v1': 'cross',
}
WORKFLOW_OF = {'classification': 'core', 'numeric': 'core', 'profile': 'core', 'annotation': 'core', 'multilabel': 'core', 'readiness': 'core',
               'comparison': 'm4', 'structure': 'm4', 'temporal': 'm5', 'text': 'm6', 'image': 'm7', 'cross': 'm9'}
CORE_MODES = {'classification', 'regression', 'unlabeled', 'annotation_classification', 'annotation_regression', 'multilabel_classification',
              'clustering', 'anomaly_detection', 'role_profile'}


def composition_of(value):
    method = value.get('methodology_id')
    if method in ('m4_local_2026_10_10', 'm4_local_2026_11_25'):
        comparison = value.get('comparison') or {}
        return 'comparison' if (comparison.get('preset') or comparison.get('mode')) else 'structure'
    return METHOD_COMPOSITION.get(method, 'generic')


def test_manifest_is_well_formed():
    doc = manifest()
    names = [c['name'] for c in doc['cases']]
    assert len(names) == len(set(names))
    from validation.dashboard.controlled import BUILDERS
    vocabulary = set(doc['tags']) | {'ordinary', 'wide', 'large', 'empty', 'context', 'relationship', 'annotations', 'blocked',
                                      'many_findings', 'violation', 'disclosure', 'revisions', 'synthetic'}
    for case in doc['cases']:
        assert case['composition'] in COMPOSITIONS and case['workflow'] in WORKFLOWS, case['name']
        assert case['composition'] == 'generic' or WORKFLOW_OF[case['composition']] == case['workflow'], case['name']
        assert case['workflow'] != 'core' or case['mode'] in CORE_MODES, case['name']
        assert set(case['tags']) <= vocabulary, case['name']
        source = case['source']
        assert len(source) == 1 and next(iter(source)) in {'stored', 'matrix', 'controlled'}, case['name']
        if 'stored' in source:
            assert (ROOT / 'validation' / source['stored']).is_file(), source['stored']
        if 'controlled' in source:
            assert source['controlled'] in BUILDERS or source['controlled'] == 'generic_unknown_methodology'


def test_every_composition_has_cases_for_the_verification_matrix():
    by = {}
    for case in cases():
        by.setdefault(case['composition'], set()).update(case['tags'])
    assert set(by) == COMPOSITIONS
    for composition, tags in by.items():
        if composition != 'generic':
            assert 'findings' in tags or 'clean' in tags, composition
    # Clean, partial and bounded states exist across the corpus (plan section G).
    every = set().union(*by.values())
    assert {'clean', 'partial', 'bounded', 'high', 'historical'} <= every


@pytest.mark.parametrize('case', params())
def test_recorded_facts_match_tags_and_composition(case):
    value = analysis(case)
    facts = record(case)['facts']
    if case['composition'] != 'generic':
        assert composition_of(value) == case['composition'], f"{case['name']}: {value.get('methodology_id')}"
    tags = set(case['tags'])
    if 'clean' in tags:
        assert facts['findings'] == 0
    if 'findings' in tags:
        assert facts['findings'] > 0
    if 'partial' in tags:
        assert facts['execution'] == 'partial'
    else:
        assert facts['execution'] == 'completed'
    if 'high' in tags:
        assert any(r.lower() == 'high' for r in facts['ranks'])
    if 'historical' in tags:
        assert not facts['guidance'], 'historical cases predate finding_guidance_v1'


@pytest.mark.parametrize('case', params([c for c in cases() if 'stored' in c['source']]))
def test_stored_cases_are_exact_copies_of_untouched_milestone_files(case):
    built = record(case)
    source = ROOT / 'validation' / case['source']['stored']
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    assert built['origin']['sha256'] == digest
    assert hashlib.sha256((folder(case) / 'analysis.json').read_bytes()).hexdigest() == digest


@pytest.mark.parametrize('case', params())
def test_every_case_has_a_rendered_report(case):
    record(case)
    html = (folder(case) / 'report.html').read_text()
    assert html.lower().startswith('<!doctype html')
    if case['composition'] == 'generic':
        assert 'Synthetic test-only report' in html   # no template renders an unknown methodology
    else:
        assert 'id="understand"' in html, 'rendered with the current report experience'


@pytest.fixture(scope='module')
def normalize(tmp_path_factory):
    return Node('src/app/results/normalize.ts', tmp_path_factory.mktemp('dashboard-normalize'))


@needs_node
@pytest.mark.parametrize('case', params())
def test_harness_runs_the_app_projection_and_every_finding_stays_reachable(normalize, case):
    value = analysis(case)
    rows = normalize.call('ledger', value, None)
    expected = [i for i, f in enumerate(value.get('findings') or []) if f.get('code') != 'no_major_issues']
    assert sorted(r['index'] for r in rows if not r.get('context')) == expected
