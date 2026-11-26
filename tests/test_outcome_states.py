"""Finding routes and result states for the tabular dashboards (frontend/src/app/results/finding-routes.json and
normalize.ts). Rewritten in dashboard redesign Stage 3, when the fixed 14-module mosaic and its outcome map were retired;
the guarantees are kept:

- every finding code the core, regression, M3 and contextual engines can emit (dynamic suffixes included) has an explicit
  tile route in each composition that can show it, to a tile that composition draws;
- "no major issues" is a narrative statement, never a finding, in the app and the history index alike;
- a check that failed or was interrupted makes the result partial; a precondition exclusion (blocked, even when recorded
  as skipped) never does; not-applicable checks are listed as such; a completed, finding-free result is clean.
"""
import json
import re

import pytest

from dashboard_harness import ROOT, Node, needs_node

ROUTES = json.loads((ROOT / 'frontend/src/app/results/finding-routes.json').read_text())
TILES = {
    'classification': {'score', 'target', 'leakage', 'missing', 'repeats', 'numeric', 'columns', 'other'},
    'profile': {'profile', 'missing', 'repeats', 'variation', 'numeric', 'columns', 'parsing', 'other'},
    'numeric': {'target', 'relationships', 'constraints', 'shape', 'dependencies', 'annotations', 'repeated', 'availability', 'missing', 'repeats', 'variation', 'numeric', 'columns', 'other'},
    'annotation': {'annotations', 'class', 'cohorts', 'repeated', 'missing', 'repeats', 'variation', 'numeric', 'columns', 'other'},
    'multilabel': {'labels', 'annotations', 'cardinality', 'pairs', 'constraints', 'missing', 'repeats', 'numeric', 'columns', 'other'},
    'readiness': {'geometry', 'scale', 'extremes', 'sparsity', 'categories', 'repetition', 'missing', 'columns', 'other'},
}
SUFFIXES = {'severity': ('high', 'moderate'), 'availability': ('unavailable_at_prediction', 'unknown')}


def codes(text):
    found = set(re.findall(r"(?:\badd|_risk)\(\s*['\"]([a-z_]+)['\"]\s*,", text))
    found |= set(re.findall(r"\(\s*['\"][a-z_]+['\"]\s*,\s*['\"]([a-z_]+)['\"]\s*,\s*['\"][A-Z]", text))
    found |= set(re.findall(r"\(\s*['\"]([a-z_]+)['\"]\s*,\s*['\"][A-Z][a-z]+[ -]", text))
    for prefix, var in re.findall(r"\badd\(\s*['\"]([a-z_]+_)['\"]\s*\+\s*(\w+)", text):
        found |= {prefix + s for s in SUFFIXES[var]}
    return found - set(ROUTES['narrative_only'])


def engines():
    risks = (ROOT / 'src/datatrust/risks.py').read_text()
    return {
        'classification': codes(risks[:risks.index('def summarize_risks')]),
        'unlabeled': codes(risks[risks.index('def build_unlabeled_findings'):risks.index('def build_regression_findings')]),
        'regression': codes(risks[risks.index('def build_regression_findings'):]),
        'm3': codes((ROOT / 'src/datatrust/m3.py').read_text()),
        'contextual': set(re.findall(r'_finding\("([a-z_]+)"', (ROOT / 'src/datatrust/contextual.py').read_text())),
    }


def emitted_codes():
    """Every finding code the core, regression, M3 and contextual engines can emit (used by tests/test_guidance.py)."""
    return set().union(*engines().values())


def test_route_targets_are_tiles_each_composition_draws():
    for composition, tiles in TILES.items():
        assert set(ROUTES[composition].values()) <= tiles, composition


def test_every_emitted_code_is_routed_where_it_can_appear():
    e = engines()
    assert len(e['classification']) >= 12 and len(e['unlabeled']) >= 10 and len(e['regression']) >= 12 and len(e['m3']) >= 18 and e['contextual']
    assert e['classification'] | e['contextual'] <= set(ROUTES['classification'])
    for composition in ('profile', 'numeric', 'annotation', 'multilabel', 'readiness'):
        assert e['unlabeled'] | e['contextual'] <= set(ROUTES[composition]), composition
    assert e['regression'] <= set(ROUTES['numeric'])
    m3 = set().union(*(set(ROUTES[c]) for c in ('numeric', 'annotation', 'multilabel', 'readiness')))
    assert e['m3'] <= m3, sorted(e['m3'] - m3)
    annotation_codes = {c for c in e['m3'] if 'annotation' in c}
    for composition in ('numeric', 'annotation', 'multilabel'):
        assert annotation_codes <= set(ROUTES[composition]), composition
    assert {c for c in e['m3'] if c.startswith(('constant_numerical', 'limited_numerical', 'limited_finite', 'output_', 'numerical_', 'input_target'))} <= set(ROUTES['numeric'])
    assert {'constant_observed_labels', 'limited_label_support', 'multilabel_declared_constraints'} <= set(ROUTES['multilabel'])
    assert 'conditional_scale_review' in ROUTES['readiness'] and 'constant_observed_class' in ROUTES['annotation']


def test_history_index_agrees_on_narrative_statements():
    from datatrust.api_web import NARRATIVE_ONLY
    assert set(ROUTES['narrative_only']) == NARRATIVE_ONLY


@pytest.fixture(scope='module')
def normalize(tmp_path_factory):
    return Node('src/app/results/normalize.ts', tmp_path_factory.mktemp('outcome'))


def check(check_id, applicability='applicable', execution='completed', scope='dataset', reason=None):
    return {'check_id': check_id, 'applicability': applicability, 'execution': execution, 'scope': scope, 'reason': reason}


def result(checks, status='completed', findings=()):
    return {'methodology_id': 'unlabeled_csv_profile_v1', 'schema_version': '1.0', 'findings': list(findings), 'checks': list(checks),
            'scoring': {'status': 'not_defined', 'reason': 'No validated scoring policy.', 'values': None}, 'execution': {'status': status}}


@needs_node
@pytest.mark.parametrize('checks,status,chip,group', [
    ([check('exact_duplicates')], 'completed', 'clean', None),
    ([check('exact_duplicates', execution='failed', reason='MemoryError: check failed')], 'partial', 'partial', 'notCompleted'),
    ([check('exact_duplicates', execution='skipped', reason='deadline')], 'partial', 'partial', 'notCompleted'),
    ([check('numeric_outliers', 'blocked', 'skipped', scope='x', reason='zero_iqr')], 'completed', 'clean', 'excluded'),
    ([check('numeric_outliers', 'blocked', 'not_run', reason='zero_iqr')], 'completed', 'clean', 'excluded'),
    ([check('classification_target', 'not_applicable', 'not_run', reason='No target.')], 'completed', 'clean', 'notApplicable'),
])
def test_states_keep_clean_incomplete_and_excluded_apart(normalize, checks, status, chip, group):
    value = result(checks, status)
    cov = normalize.call('coverage', value, None, {})
    state = normalize.call('resultState', value, 0, cov, False)
    assert state['chip'] == chip
    for name in ('notCompleted', 'excluded', 'notApplicable'):
        assert bool(cov[name]) == (name == group), name
    if group == 'excluded':
        assert 'no spread' in cov['excluded'][0]['reason']


@needs_node
def test_recorded_exclusions_in_scope_statements_are_not_incompleteness(normalize):
    value = result([check('numeric_outliers', 'blocked', 'not_run', scope='dependents', reason='zero_iqr')])
    value['guidance'] = {'scope': {'not_completed': [{'check': 'numeric_outliers', 'scope': 'dependents', 'state': 'excluded', 'reason': 'zero_iqr'}], 'unknowns': []}}
    cov = normalize.call('coverage', value, None, {})
    assert not cov['notCompleted'] and len(cov['excluded']) == 1
    assert normalize.call('resultState', value, 0, cov, False)['chip'] == 'clean'
