"""Stage 6C (J3): readiness v2 prerequisite evidence (tabular_{clustering,anomaly}_readiness_v2).

- complete-case coverage: no finding at 80% or more, Low below 80%, Moderate below 50%;
- redundant quantitative features: exact duplicates and |r| >= 0.98 (n >= 100, >= 10 distinct values); never a defect;
- the pair search is bounded by DependencyLimits and discloses what it did not search;
- the retained energy and linnerud cases match the expectations registered in validation/guided/readiness_v2_expectations.md;
- "no model fitted; no readiness verdict" is kept.
"""
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from datatrust import AnalysisConfig, DataTrust, DatasetSpec, TaskSpec
from datatrust.contracts import DependencyLimits, FeatureOptions
from datatrust.unsupervised import redundant_features

N = 400


def run(tmp_path, frame, kind='clustering'):
    path = tmp_path / 'r.csv'
    frame.to_csv(path, index=False)
    quantitative = {c: 'quantitative' for c in frame.columns}
    return DataTrust.from_spec(DatasetSpec(str(path)), TaskSpec(kind, feature_columns=tuple(frame.columns)),
                               AnalysisConfig(features=FeatureOptions(quantitative))).analyze()


def base(seed=0):
    rng = np.random.default_rng(seed)
    return rng, pd.DataFrame({'a': rng.normal(size=N), 'b': rng.normal(size=N) * 3 + 1, 'c': rng.uniform(0, 10, N)})


@pytest.mark.parametrize('missing,review,severity', [(.10, None, None), (.30, 'low', 'Low'), (.60, 'moderate', 'Moderate')])
def test_complete_case_coverage(tmp_path, missing, review, severity):
    _, d = base()
    d.loc[: int(missing * N) - 1, 'a'] = np.nan
    r = run(tmp_path, d)
    cov = r['profile']['readiness']['complete_case_coverage']
    assert cov['complete_rows'] == N - int(missing * N) and cov['review'] == review
    found = [f for f in r['findings'] if f['code'] == 'limited_complete_case_coverage']
    assert [f['severity'] for f in found] == ([severity] if severity else [])


def test_redundant_features_are_found_and_described_as_possibly_intended(tmp_path):
    rng, d = base()
    d['a_copy'] = d['a']
    d['b_near'] = d['b'] * 2 + rng.normal(scale=.05, size=N)
    d['c_loose'] = d['c'] + rng.normal(scale=1.5, size=N)
    r = run(tmp_path, d)
    red = r['profile']['readiness']['redundant_quantitative_features']
    found = {tuple(p['features']): p['relation'] for p in red['pairs']}
    assert found == {('a', 'a_copy'): 'exact_duplicate', ('b', 'b_near'): 'near_collinear'}
    finding = next(f for f in r['findings'] if f['code'] == 'redundant_quantitative_features')
    assert finding['severity'] == 'Low' and 'may be intended' in finding['recommendation'] and 'defect' not in finding['recommendation']
    assert r['methodology_id'] == 'tabular_clustering_readiness_v2'


def test_small_or_coded_columns_are_not_compared(tmp_path):
    rng = np.random.default_rng(1)
    small = pd.DataFrame({'x': rng.normal(size=50)})
    small['y'] = small['x'] * 2
    coded = pd.DataFrame({'x': rng.integers(0, 5, N).astype(float)})
    coded['y'] = coded['x'] * 2
    assert run(tmp_path, small)['profile']['readiness']['redundant_quantitative_features']['pairs'] == []
    assert run(tmp_path, coded)['profile']['readiness']['redundant_quantitative_features']['eligible_features'] == []


def test_the_pair_search_is_bounded_and_discloses_unsearched_pairs():
    rng = np.random.default_rng(2)
    d = pd.DataFrame({f'f{i}': rng.normal(size=200) for i in range(70)})
    records = [{'feature': c, 'population': 'quantitative', 'finite_count': 200, 'distinct_count': 200} for c in d.columns]
    out = redundant_features(d, records, lambda stage: None)
    assert out['status'] == 'bounded' and len(out['searched_features']) == 64 and out['unsearched_features'] == [f'f{i}' for i in range(64, 70)]
    assert out['pairs_searched'] == 64 * 63 // 2 and out['unsearched_pairs'] == 70 * 69 // 2 - 2016
    work = redundant_features(d, records, lambda stage: None, DependencyLimits(max_row_work=200 * 10))
    assert work['status'] == 'bounded' and work['pairs_searched'] == 10 and work['stopping_reason'] == 'planned_row_work_limit'


def test_declared_quantitative_features_are_searched_first():
    rng = np.random.default_rng(3)
    d = pd.DataFrame({'assumed': rng.normal(size=200), 'declared': rng.normal(size=200)})
    records = [{'feature': 'assumed', 'population': 'assumed_quantitative', 'finite_count': 200, 'distinct_count': 200},
               {'feature': 'declared', 'population': 'quantitative', 'finite_count': 200, 'distinct_count': 200}]
    assert redundant_features(d, records, lambda stage: None)['searched_features'] == ['declared', 'assumed']


def test_retained_cases_match_the_registered_expectations():
    from validation.m3.verify import cases
    expected = {'energy': ([('relative_compactness', 'surface_area')], 768), 'linnerud': ([], 20)}
    with tempfile.TemporaryDirectory() as t:
        for name, source, frame, task, config, pdf in cases(Path(t)):
            if not name.endswith(('_clustering', '_anomaly')):
                continue
            r = DataTrust.from_spec(DatasetSpec(source), task, config).analyze()
            pairs, rows = expected[name.split('_')[0]]
            rd = r['profile']['readiness']
            assert [tuple(p['features']) for p in rd['redundant_quantitative_features']['pairs']] == pairs, name
            assert rd['complete_case_coverage']['complete_rows'] == rows == rd['complete_case_coverage']['rows'], name
            codes = {f['code'] for f in r['findings']}
            assert ('redundant_quantitative_features' in codes) == bool(pairs) and 'limited_complete_case_coverage' not in codes
            assert 'conditional_scale_review' in codes and r['methodology_id'].endswith('_readiness_v2')


def test_no_readiness_verdict_and_the_policy_states_the_thresholds(tmp_path):
    from datatrust.interpretation import interpret
    _, d = base()
    r = run(tmp_path, d, 'anomaly_detection')
    assert 'No clustering quality, anomaly correctness' in r['profile']['readiness']['limitations']
    texts = [s['text'] for s in interpret(r, 'm3')['summary']]
    assert any('no readiness verdict' in t for t in texts) and any('rows have every quantitative feature finite' in t for t in texts)
    rules = {p['rule'] for p in r['guidance']['policy']}
    assert {'Complete-case coverage', 'Redundant quantitative features', 'Pair search bounds'} <= rules
