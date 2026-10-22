"""Mosaic tile outcomes from canonical JSON, through the app's own adapter (frontend/src/app/results/adapter.ts,
bundled with the frontend's esbuild and run in node). A tile's state comes from its canonical checks, never from
the absence of findings; every finding stays reachable; the governing guardrail cap is the one shown."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from datatrust import AnalysisConfig, AnnotationOptions, AnnotationSpec, DataTrust, DatasetSpec, TaskSpec
from datatrust.contracts import CsvParseOptions

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / 'frontend'
ESBUILD = FRONTEND / 'node_modules/.bin/esbuild'
MAP = json.loads((FRONTEND / 'src/app/results/outcome-map.json').read_text())
TILES = {'score', 'gaps', 'dups', 'conflicts', 'imbalance', 'leakage', 'outliers', 'relations', 'time', 'text', 'images', 'docs', 'local', 'reports'}
BANK = Path.home() / 'Downloads/bank+marketing/bank/bank-full.csv'


def emitted_codes():
    """Every finding code the core and M3 finding builders can emit, read from their source."""
    suffixes = {'severity': ('high', 'moderate'), 'availability': ('unavailable_at_prediction', 'unknown')}
    codes = set()
    for name in ('risks', 'm3'):
        text = (ROOT / 'src/datatrust' / f'{name}.py').read_text()
        codes |= set(re.findall(r"(?:\badd|_risk)\(\s*['\"]([a-z_]+)['\"]\s*,", text))
        codes |= set(re.findall(r"\(\s*['\"][a-z_]+['\"]\s*,\s*['\"]([a-z_]+)['\"]\s*,\s*['\"][A-Z][a-z]+[ -]", text))
        codes |= set(re.findall(r"\(\s*['\"]([a-z_]+)['\"]\s*,\s*['\"][A-Z][a-z]+[ -]", text))
        for prefix, var in re.findall(r"\badd\(\s*['\"]([a-z_]+_)['\"]\s*\+\s*(\w+)", text):
            codes |= {prefix + s for s in suffixes[var]}
    # Contextual findings (context_v1) are built by _finding("code", ...).
    codes |= set(re.findall(r'_finding\("([a-z_]+)"', (ROOT / 'src/datatrust/contextual.py').read_text()))
    return codes


def test_every_engine_finding_code_has_an_explicit_tile():
    codes = emitted_codes()
    assert len(codes) > 45
    known = set(MAP['findings']) | set(MAP['narrative_only'])
    assert codes - known == set(), 'map these codes in outcome-map.json'
    assert known - codes == set(), 'outcome-map.json lists a code no engine emits'
    assert set(MAP['findings'].values()) <= TILES and set(MAP['checks']) <= TILES


def test_history_index_agrees_on_narrative_statements():
    from datatrust.api_web import NARRATIVE_ONLY
    assert set(MAP['narrative_only']) == NARRATIVE_ONLY


needs_node = pytest.mark.skipif(not (shutil.which('node') and ESBUILD.exists()), reason='node and the frontend toolchain are needed')


@pytest.fixture(scope='module')
def adapter(tmp_path_factory):
    work = tmp_path_factory.mktemp('adapter')
    bundle = work / 'adapter.mjs'
    subprocess.run([str(ESBUILD), str(FRONTEND / 'src/app/results/adapter.ts'), '--bundle', '--format=esm', '--platform=node',
                    f'--outfile={bundle}', '--log-level=error'], check=True)
    script = work / 'run.mjs'
    script.write_text(f"import {{ fromAnalysis, activeTiles, governingCap, scopeStatements }} from {json.dumps(bundle.as_uri())};\n"
                      "import {{ readFileSync }} from 'node:fs';\n".replace('{{', '{').replace('}}', '}') +
                      "const a = JSON.parse(readFileSync(process.argv[2], 'utf8')); const r = fromAnalysis(a, process.argv[3]);\n"
                      "console.log(JSON.stringify({ run: r, active: activeTiles(r), cap: governingCap(a.scoring.values), scope: scopeStatements(a.checks) }));\n")

    def run(analysis, mode):
        source = work / 'analysis.json'
        source.write_text(json.dumps(analysis))
        out = subprocess.run(['node', str(script), str(source), mode], capture_output=True, text=True, check=True)
        return json.loads(out.stdout)
    return run


def check(check_id, applicability='applicable', execution='completed', scope='dataset', reason=None):
    return {'check_id': check_id, 'applicability': applicability, 'execution': execution, 'scope': scope, 'reason': reason}


def synthetic(checks, findings=(), scoring=None, profile=None, coverage=None):
    return {'methodology_id': 'unlabeled_csv_profile_v1', 'schema_version': '1.0', 'generated_at': '2026-10-20T10:00:00+00:00',
            'task': {'kind': 'dataset_profile'}, 'profile': {'columns': [], **(profile or {})}, 'findings': list(findings), 'checks': list(checks),
            'scoring': scoring or {'status': 'not_defined', 'reason': 'No validated scoring policy.', 'values': None},
            'execution': {'status': 'completed', 'analyzed_rows': 10, 'analyzed_columns': 2, 'elapsed_seconds': 0.1}, 'coverage': coverage or {}}


def finding(code, severity='Moderate'):
    return {'code': code, 'title': code.replace('_', ' '), 'severity': severity, 'finding': f'{code} observed.', 'evidence': 'x'}


@needs_node
@pytest.mark.parametrize('checks,state,dim', [
    ([check('exact_duplicates', 'not_applicable', 'not_run', reason='No rows.')], 'not_applicable', True),
    ([check('exact_duplicates')], 'clear', None),
    ([check('exact_duplicates', execution='failed', reason='MemoryError: check failed')], 'not_assessed', None),
    ([check('exact_duplicates', execution='skipped', reason='deadline')], 'not_assessed', None),
    ([check('exact_duplicates', 'blocked', 'not_run', reason='blocked')], 'not_assessed', None),
    ([], 'not_assessed', None),
])
def test_a_tile_without_findings_reports_what_its_checks_did(adapter, checks, state, dim):
    tile = adapter(synthetic(checks), 'unlabeled')['run']['dups']
    assert tile['state'] == state and tile.get('dim') == dim
    assert tile['label'] != 'No finding' or state == 'clear'  # "No finding" only within a completed scope


@needs_node
def test_failures_excluded_scopes_and_planned_bounds_stay_distinct(adapter):
    run = adapter(synthetic([check('numeric_summary'), check('numeric_outliers', scope='age'),
                             check('numeric_outliers', 'blocked', 'not_run', scope='holiday', reason='zero_iqr'),
                             check('missingness'), check('feature_missingness', execution='failed', reason='MemoryError: check failed; no conclusion was generated.')]), 'unlabeled')['run']
    outliers, gaps = run['outliers'], run['gaps']
    assert outliers['state'] == 'clear' and 'holiday' in outliers['detail']  # excluded by a method precondition: not a failure
    assert outliers['scope'] == ['Excluded · holiday: the middle half has no spread (IQR is zero), so no fences exist']
    assert gaps['state'] == 'incomplete' and gaps['label'] == 'Incomplete' and gaps['scope'][0].startswith('Failed · feature missingness')
    regression = adapter({**synthetic([check('regression_relationships')], coverage={'relationship_search': {'status': 'bounded', 'meaning': 'Pairs only.'}}),
                          'methodology_id': 'tabular_regression_v1'}, 'regression')['run']['relations']
    assert regression['state'] == 'clear' and regression['scope'] == ['Planned bound · the relationship search is bounded: Pairs only.']


@needs_node
def test_findings_and_incomplete_coverage_are_shown_together(adapter):
    tile = adapter(synthetic([check('missingness'), check('feature_missingness', execution='skipped', reason='deadline')],
                             [finding('column_missingness', 'High')]), 'unlabeled')['run']['gaps']
    # The label states review priority, not the scoring scale (WS2).
    assert tile['state'] == 'finding' and tile['label'] == 'High priority · incomplete' and tile['scope'][0].startswith('Interrupted')


@needs_node
def test_every_finding_stays_reachable_and_no_major_issues_is_not_one(adapter):
    out = adapter(synthetic([check('missingness')], [finding('no_major_issues', 'Low'), finding('brand_new_code'), finding('declared_input_unavailability', 'High')]), 'clustering')
    run = out['run']
    assert [f['code'] for f in run['reports']['findings']] == ['brand_new_code'] and run['reports']['findings'][0]['unmapped'] is True
    assert run['leakage']['findings'][0]['code'] == 'declared_input_unavailability'  # outside clustering's tiles, still shown
    assert all(f['code'] != 'no_major_issues' for t in run.values() for f in t['findings'])


@needs_node
def test_unavailable_values_are_never_shown_as_zero(adapter):
    tile = adapter(synthetic([check('exact_duplicates')]), 'unlabeled')['run']['dups']
    assert dict(tile['facts'])['Duplicate groups'] == 'Unavailable' and '0' not in dict(tile['facts']).values()


@needs_node
def test_the_governing_guardrail_cap_is_the_lowest(adapter):
    guardrails = [{'code': 'a', 'cap': 80, 'explanation': 'First cap.'}, {'code': 'b', 'cap': 69, 'explanation': 'Governing cap.'},
                  {'code': 'c', 'cap': 75, 'explanation': 'Third cap.'}]
    values = {'sub_scores': {}, 'evidence_score': 90, 'overall': 69.0, 'risk_level': 'Elevated', 'guardrails': guardrails}
    out = adapter({**synthetic([check('classification_scoring')], scoring={'status': 'computed', 'reason': None, 'values': values}),
                   'methodology_id': 'classification_legacy_2026_08_13'}, 'classification')
    assert out['cap']['cap'] == 69 and [g['code'] for g in out['cap']['governing']] == ['b']
    detail = out['run']['score']['detail']
    assert 'Capped at 69: Governing cap.' in detail and 'First cap' not in detail


@needs_node
def test_regression_tiles_follow_their_own_checks(adapter):
    value = DataTrust.from_spec(DatasetSpec(str(ROOT / 'validation/regression/data/prepared/bike_hour.csv')), TaskSpec('regression', target='cnt')).analyze_result().to_dict()
    out = adapter(value, 'regression')
    run = out['run']
    assert run['conflicts']['state'] == 'clear' and run['leakage']['state'] == 'clear'  # their regression checks completed
    assert any('holiday' in s and 'IQR is zero' in s for s in run['outliers']['scope'])
    assert run['score']['state'] == 'not_applicable' and out['active'] == 9


@needs_node
def test_m3_structured_evidence_reaches_its_tile(adapter, tmp_path):
    path = tmp_path / 'data.csv'
    path.write_text('x,y,s\n1,a,unknown\n2,b,uncertain\n3,,unknown\n4,,oops\n5,,observed\n6,a,intentionally_unlabeled\n')
    value = DataTrust.from_spec(DatasetSpec(path), TaskSpec('classification', 'y'),
                                AnalysisConfig(annotations=AnnotationOptions(AnnotationSpec('expected', 's')))).analyze_result().to_dict()
    run = adapter(value, 'annotation_classification')['run']
    shown = {f['code']: f for t in run.values() for f in t['findings']}
    expected = {f['code'] for f in value['findings'] if f['code'] not in MAP['narrative_only']}
    assert set(shown) == expected and expected
    structured = [f for f in shown.values() if isinstance(f['evidence'], list)]
    assert structured and all(not f.get('unmapped') for f in shown.values())


@needs_node
@pytest.mark.skipif(not BANK.is_file(), reason='Bank Marketing (bank-full.csv) is not on this machine')
def test_bank_full_score_tile_names_its_governing_cap(adapter):
    value = DataTrust.from_spec(DatasetSpec(str(BANK)), TaskSpec('classification', target='y'), AnalysisConfig(parsing=CsvParseOptions(delimiter=';'))).analyze_result().to_dict()
    score = adapter(value, 'classification')['run']['score']
    assert score['label'] == '69.0 · Elevated' and score['detail'].startswith('Evidence 84.38. Capped at 69: The target balance sub-score is 23.4')


@needs_node
def test_supervised_pages_state_every_check_that_did_not_complete(adapter):
    """M4 to M9 pages build tiles from evidence; their canonical checks that failed, were interrupted or excluded a
    scope are listed above the tiles, and completed or not-applicable checks add nothing."""
    out = adapter(synthetic([check('near_duplicates'), check('embeddings', execution='failed', reason='isolated_model_failure'),
                             check('passages', execution='skipped', reason='deadline'), check('ocr', 'not_applicable', 'not_run', reason='No images.'),
                             check('pairs', 'blocked', 'not_run', scope='source_2', reason='no_shared_identity')]), 'unlabeled')
    assert out['scope'] == ['Failed · embeddings: isolated model failure', 'Interrupted · passages: deadline', 'Excluded · source_2: no shared identity']
    assert adapter(synthetic([check('near_duplicates')]), 'unlabeled')['scope'] == []


@needs_node
def test_module_content_is_mode_aware_and_states_real_artifacts(adapter):
    run = adapter(synthetic([check('missingness'), check('exact_duplicates')]), 'unlabeled')['run']
    assert run['gaps']['effect'] == 'Evidence only: no score is defined for this task.'
    assert dict(run['gaps']['facts'])['Missing-value rule'] == 'pandas default missing tokens'
    assert dict(run['dups']['facts'])['Equality'].startswith('Whole parsed rows')
    assert run['reports']['label'] == 'HTML · JSON · PDF on request' and 'not a data check' in run['local']['detail']


@needs_node
def test_a_precondition_block_recorded_as_skipped_is_an_exclusion_not_an_interruption(adapter):
    """M5 records precondition blocks as blocked + skipped; blocked takes precedence."""
    out = adapter(synthetic([check('t1:flat_runs'), check('t2:flat_runs', 'blocked', 'skipped', scope='source1', reason='insufficient_history')]), 'unlabeled')
    assert out['scope'] == ['Excluded · source1: insufficient history']


@needs_node
def test_outlier_facts_count_numeric_features_only(adapter):
    """The legacy profile records a 0 rate on text columns; they were never assessed and are not counted."""
    columns = [{'name': 'job', 'role': 'feature', 'is_numeric': False, 'outlier_rate': 0.0, 'outlier_count': 0},
               {'name': 'age', 'role': 'feature', 'is_numeric': True, 'outlier_rate': 1.2, 'outlier_count': 3, 'numeric_summary': {'q1': 30, 'q3': 50}},
               {'name': 'pdays', 'role': 'feature', 'is_numeric': True, 'outlier_rate': 0.0, 'outlier_count': 0, 'numeric_summary': {'q1': -1, 'q3': -1}}]
    value = {**synthetic([check('numeric_outliers')], profile={'columns': columns, 'numeric_feature_count': 2}), 'methodology_id': 'classification_legacy_2026_08_13'}
    facts = dict(adapter(value, 'classification')['run']['outliers']['facts'])
    assert facts['Assessed for IQR candidates'] == '1' and facts['IQR is zero (fences undefined)'] == 'pdays'


@needs_node
def test_contextual_findings_reach_their_tiles_as_context(adapter):
    contextual = {'status': 'completed', 'candidates': [{'column': 'pdays', 'value': -1}], 'availability': {'duration': 'unavailable_at_prediction'},
                  'prediction': {'point': 'before the first contact', 'declared': True},
                  'interpreted': {'pdays': {'applicable_rows': 8257, 'declared_missing_rows': 0, 'structural_absence_rows': 36954, 'applicable_numeric': {'outlier_count': 49, 'outlier_rate': 0.59}}},
                  'dependency_search': {'status': 'completed', 'checks': [{}] * 16, 'unsearched_features': [], 'flagged': []},
                  'findings': [{**finding('declared_unavailable_feature', 'High'), 'columns': ['duration']}, {**finding('declared_condition_exceptions'), 'columns': ['x']}]}
    run = adapter({**synthetic([check('missingness'), check('target_leakage')]), 'contextual': contextual, 'methodology_id': 'classification_legacy_2026_08_13'}, 'classification')['run']
    assert run['leakage']['findings'][0]['context'] is True and run['gaps']['findings'][0]['code'] == 'declared_condition_exceptions'
    facts = dict(run['leakage']['facts'])
    assert facts['Prediction point'] == 'before the first contact' and facts['Dependency search'] == '16 features checked; none flagged'
    assert dict(run['outliers']['facts'])['pdays · applicable rows'] == '8,257 · 49 outside fences (0.59%)'
    assert dict(run['gaps']['facts'])['Suggested codes (not applied)'] == 'pdays = -1'
