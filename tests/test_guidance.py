"""finding_guidance_v1: every finding kind has guidance; observed facts trace to the canonical result; options carry
prerequisites, contraindications and verification; the score explanation reconciles with the scoring
implementation; JSON, HTML and saved views carry the same text; results without a block stay byte-identical."""
import ast
import html
import json
import math
import re
from pathlib import Path

import pytest

from datatrust import AnalysisConfig, AnnotationOptions, AnnotationSpec, DataTrust, DatasetSpec, TaskSpec
from datatrust import guidance as G
from datatrust import scoring
from datatrust.contracts import CsvParseOptions
from datatrust.renderer import render_analysis_result, write_report_artifacts
from tests.test_outcome_states import emitted_codes

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src/datatrust'
BASELINE = json.loads((ROOT / 'tests/fixtures/m1_classification_baseline.json').read_text())['cases']
BANK = Path.home() / 'Downloads/bank+marketing/bank/bank-full.csv'


# ——— Coverage: every finding kind an engine can emit has an entry ———

def calls(name, method):
    tree = ast.parse((SRC / f'{name}.py').read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == method:
            yield node


def m4_m5_titles():
    titles = set()
    for name in ('m4_diagnostics', 'comparison', 'temporal_diagnostics', 'temporal_behavior', 'temporal_availability', 'temporal_evaluation', 'before_after'):
        for node in calls(name, 'finding'):
            if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
                titles.add(node.args[1].value)
    loops = re.findall(r"\(\s*'([A-Z][^']+)',\s*' OR '", (SRC / 'm4_diagnostics.py').read_text())  # titles iterated in a loop
    unlabeled = re.findall(r'add\("[a-z_]+", "([^"]+)"', (SRC / 'risks.py').read_text())
    unlabeled += re.findall(r'\("(?:constant|near_constant|high_cardinality)", "[a-z_]+", "([^"]+)"', (SRC / 'risks.py').read_text())
    return titles | set(loops) | set(unlabeled)


def families():
    found = set()
    for name in ('text_diagnostics', 'text_search', 'image_diagnostics', 'image_search'):
        for node in calls(name, 'add'):
            kw = {k.arg: ast.unparse(k.value) for k in node.keywords}
            if 'violations' in kw and kw['violations'] != '0' and node.args:
                a = node.args[0]
                if isinstance(a, ast.Constant):
                    found.add(a.value)
                elif 'exact_duplicates_' in ast.unparse(a):
                    found |= {f'exact_duplicates_{r}' for r in ('bytes', 'native', 'oriented')}
    m9 = re.search(r"'title':\{([^}]*)\}", (SRC / 'cross.py').read_text()).group(1)
    return found | set(re.findall(r"'([a-z_]+)':'Review", m9))


def test_every_finding_kind_has_an_explicit_entry():
    assert emitted_codes() - set(G.CODE_KEY) - G.NARRATIVE_ONLY == set()
    titles = m4_m5_titles()
    assert len(titles) >= 40 and titles - set(G.TITLE_KEY) == set(), titles - set(G.TITLE_KEY)
    fams = families()
    assert len(fams) >= 18 and fams - set(G.FAMILY_KEY) == set(), fams - set(G.FAMILY_KEY)
    used = set(G.CODE_KEY.values()) | set(G.TITLE_KEY.values()) | set(G.FAMILY_KEY.values())
    assert used <= set(G.CATALOGUE) and set(G.CATALOGUE) - used == {'generic_review'}


def test_every_option_has_prerequisites_contraindications_and_verification():
    for key, entry in G.CATALOGUE.items():
        assert entry['impact'] and entry['investigate'] and entry['options'], key
        for option in entry['options']:
            assert all(option[k].strip() for k in ('option', 'prerequisites', 'avoid_when', 'verify')), (key, option)


# ——— Fact traceability against the canonical result ———

NUMBER = re.compile(r'(?<![A-Za-z_])-?\d[\d,]*(?:\.\d+)?')


def numbers_in(value, out):
    if isinstance(value, bool) or value is None:
        return out
    if isinstance(value, (int, float)):
        out.add(round(float(value), 9))
    elif isinstance(value, str):
        for token in re.findall(r'-?\d+(?:\.\d+)?', value):
            out.add(round(float(token), 9))
    elif isinstance(value, dict):
        for k, v in value.items():
            numbers_in(k, out); numbers_in(v, out)
    elif isinstance(value, list):
        for v in value:
            numbers_in(v, out)
    return out


def assert_traceable(value):
    canonical = numbers_in({k: v for k, v in value.items() if k != 'guidance'}, set()) | {1.5}  # 1.5 × IQR is the method's constant
    for ref, item in value['guidance']['items'].items():
        for line in item['observed']:
            for token in NUMBER.findall(line):
                number = round(float(token.replace(',', '')), 9)
                assert number in canonical, f'{ref}: {number} in "{line}" is not a value the result records'


def run(path, task, config=None):
    return DataTrust.from_spec(DatasetSpec(str(path)), task, config).analyze_result()


CLASSIFICATION = ['adult', 'german_credit', 'mutation_conflicting_labels', 'mutation_constant_field', 'mutation_duplicates',
                  'mutation_feature_missingness_100', 'mutation_missing_targets', 'mutation_review_only_leakage', 'mutation_strong_leakage', 'mutation_target_imbalance']


@pytest.mark.parametrize('case', CLASSIFICATION)
def test_classification_guidance_is_traceable_and_reconciles_with_scoring(case):
    c = BASELINE[case]
    value = run(ROOT / c['path'], TaskSpec('classification', target=c['target'])).to_dict()
    g = value['guidance']
    legacy_items = {k for k in g['items'] if not k.startswith('context.')}  # contextual items (context_v1) are listed separately
    assert g['version'] == G.VERSION and legacy_items == {f['code'] for f in value['findings'] if f['code'] not in G.NARRATIVE_ONLY}
    assert_traceable(value)
    # Independent oracle: the feature-usability rules re-derived from the profile, then the implementation's rounding.
    usability = g['scoring']['feature_usability']
    features = [col for col in value['profile']['columns'] if col['role'] == 'feature']
    def points(col):
        p = 30 if col['missing_rate'] >= 100 else 20 if col['missing_rate'] >= 50 else 10 if col['missing_rate'] >= 25 else 0
        p += 12 if col['constant'] else 8 if col['near_constant'] else 0
        p += 8 if col['high_cardinality'] else 0
        p += 8 if col['outlier_rate'] >= 10 else 4 if col['outlier_rate'] >= 5 else 0
        return p
    expected = {col['name']: points(col) for col in features if points(col)}
    assert {c['column']: sum(r['points'] for r in c['rules']) for c in usability['contributors']} == expected
    assert usability['raw_points'] == sum(expected.values()) and usability['feature_count'] == len(features)
    recomputed = round(max(0.0, min(100.0, 100 - usability['raw_points'] / max(len(features), 1))), 2) if features else 0.0
    assert recomputed == usability['sub_score'] == value['scoring']['values']['sub_scores']['feature_usability']
    sub = value['scoring']['values']['sub_scores']
    assert g['scoring']['evidence_score']['mean'] == round(sum(sub.values()) / len(sub), 2) == value['scoring']['values']['evidence_score']
    caps = [x['cap'] for x in g['scoring']['guardrails']]
    assert value['scoring']['values']['overall'] == round(min([g['scoring']['evidence_score']['mean'], *caps]), 2)
    assert [x['governing'] for x in g['scoring']['guardrails']] == [x == min(caps) for x in caps]


def test_policy_table_matches_the_scoring_rules():
    column = lambda **kw: {'name': 'c', 'role': 'feature', 'missing_rate': 0, 'constant': False, 'near_constant': False, 'high_cardinality': False, 'outlier_rate': 0, **kw}
    rule = lambda **kw: [p for _, rules in scoring.feature_usability_contributions([column(**kw)]) for _, p in rules]
    assert (rule(missing_rate=25), rule(missing_rate=50), rule(missing_rate=100)) == ([10], [20], [30])
    assert (rule(constant=True), rule(near_constant=True), rule(high_cardinality=True)) == ([12], [8], [8])
    assert (rule(outlier_rate=5), rule(outlier_rate=10), rule(outlier_rate=4.99)) == ([4], [8], [])
    assert [scoring._risk_level(x) for x in (85, 84.99, 70, 69.99, 50, 49.99)] == ['Low', 'Moderate', 'Moderate', 'Elevated', 'Elevated', 'High']
    table = ' '.join(f"{p['rule']} {p['threshold']} {p['effect']}" for p in G.POLICY['classification_legacy_2026_08_13'])
    for text in ('10 / 20 / 30', '12 / 8', '4 / 8', 'capped at 69', 'capped at 49', '≥ 85 Low · ≥ 70 Moderate · ≥ 50 Elevated', '≥ 75%', '≥ 95%'):
        assert text in table, text


def test_regression_unlabeled_and_m3_guidance_are_traceable(tmp_path):
    results = [run(ROOT / 'validation/regression/data/prepared/bike_hour.csv', TaskSpec('regression', target='cnt')),
               run(ROOT / 'validation/data/prepared/german_credit.csv', TaskSpec('dataset_profile'))]
    path = tmp_path / 'm3.csv'
    path.write_text('x,y,s\n1,a,unknown\n2,b,uncertain\n3,,unknown\n4,,oops\n5,,observed\n6,a,intentionally_unlabeled\n')
    results.append(run(path, TaskSpec('classification', 'y'), AnalysisConfig(annotations=AnnotationOptions(AnnotationSpec('expected', 's')))))
    for result in results:
        value = result.to_dict()
        assert value['guidance']['items'] and 'scoring' not in value['guidance']
        assert_traceable(value)
        assert all(item['catalogue'] != 'generic_review' for item in value['guidance']['items'].values())
    bike = results[0].to_dict()['guidance']
    assert bike['scope']['not_completed'] == [{'check': 'numeric_outliers', 'scope': 'holiday', 'state': 'excluded', 'reason': 'zero_iqr'}]
    assert 'excluded by a method' in bike['scope']['conclusion'] and 'did not complete' not in bike['scope']['conclusion']


@pytest.mark.skipif(not BANK.is_file(), reason='Bank Marketing (bank-full.csv) is not on this machine')
def test_bank_full_guidance_names_zero_iqr_and_the_unexplained_contributor():
    value = run(BANK, TaskSpec('classification', target='y'), AnalysisConfig(parsing=CsvParseOptions(delimiter=';'))).to_dict()
    assert value['scoring']['values']['overall'] == 69.0  # unchanged
    assert_traceable(value)
    outliers = ' '.join(value['guidance']['items']['numeric_outlier_concentration']['observed'])
    assert 'IQR is zero for pdays, previous' in outliers and "'not assessable'" in outliers
    contributors = {c['column']: c['rules'] for c in value['guidance']['scoring']['feature_usability']['contributors']}
    assert contributors['default'] == [{'rule': 'near-constant (top value ≥ 95%)', 'points': 8}]
    assert sum(r['points'] for rules in contributors.values() for r in rules) == 24  # 24 ÷ 16 features → 98.5
    imbalance = value['guidance']['items']['target_imbalance']
    assert imbalance['observed'][0] == 'Classes among 45,211 labelled rows: no 39,922 (88.3%); yes 5,289 (11.7%).'


# ——— One text everywhere ———

def text_of(markup):
    return ' '.join(html.unescape(re.sub(r'<[^>]+>', ' ', markup)).split())


@pytest.mark.parametrize('legacy', [False, True])
def test_reports_render_exactly_the_recorded_guidance(tmp_path, legacy):
    c = BASELINE['mutation_duplicates']
    result = run(ROOT / c['path'], TaskSpec('classification', target=c['target']))
    artifacts = write_report_artifacts(result, tmp_path / 'r.html', legacy_html=legacy)
    report = text_of(Path(artifacts.html_path).read_text())
    g = result.to_dict()['guidance']
    for heading in ('Completed scope and open questions', 'Preprocessing guidance', 'How the score was reached', 'Thresholds and policy', 'Provenance'):
        assert heading in report, heading
    assert ' '.join(g['scope']['conclusion'].split()) in report
    for item in g['items'].values():
        for line in item['observed'] + item['impact'] + item['investigate'] + item['unknowns']:
            assert ' '.join(line.split()) in report, line
        for option in item['options']:
            for field in ('option', 'prerequisites', 'avoid_when', 'verify'):
                assert ' '.join(option[field].split()) in report


def test_results_without_a_block_keep_their_bytes_and_say_so(tmp_path):
    result = run(ROOT / 'validation/data/prepared/german_credit.csv', TaskSpec('dataset_profile'))
    assert 'guidance' in result.to_dict()
    result.guidance = {}
    assert 'guidance' not in result.to_dict()  # an older result's JSON is reproduced exactly
    report = text_of(render_analysis_result(result))
    assert 'Guidance was not recorded by the version that produced this analysis.' in report
    assert 'Scope and open questions were not recorded' in report


def test_saved_analyses_carry_the_same_guidance(tmp_path):
    from datatrust.history import History
    from tests.test_history import Session
    s = Session(tmp_path, History(tmp_path / 'history'))
    s.post('/history/choice', {'saving': 'on'})
    eid = s.analyse(name='Guided')['history']['entry']
    live = s.get('/core/job/analysis').json['guidance']
    saved = s.get(f'/history/{eid}/analysis').json['guidance']
    assert live == saved and saved['version'] == G.VERSION
    s.close()
