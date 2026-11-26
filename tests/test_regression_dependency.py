"""regression_dependency_v1 (Stage 6B, J2): the founder-approved opt-in feature -> target dependency search.

- off is the default and changes nothing: no block, no finding, no key in records or fingerprints;
- on, the retained regression corpus raises exactly the dossier's four hand-reviewed flags and none elsewhere;
- planted relationships are found by family; identifiers are gated; a permuted target raises nothing;
- severity follows declared availability only (unknown Moderate, unavailable High, available Low);
- multi-output runs one block per output under one shared budget; CLI and config JSON reach the option.
"""
import json
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from datatrust import AnalysisConfig, DataTrust, DatasetSpec, RegressionDependencyOptions, RegressionOptions, TargetExpectations, TaskSpec
from datatrust.contracts import DependencyLimits, omit_default_delimiter
from datatrust.regression_dependency import search

ROOT = Path(__file__).resolve().parents[1]
REG = ROOT / 'validation/regression'
ON = RegressionOptions(dependency_search=True)


def run(path, target, options=ON, kind='regression', targets=None, features=None):
    task = TaskSpec(kind, target) if targets is None else TaskSpec(kind, targets=tuple(targets), feature_columns=features)
    return DataTrust.from_spec(DatasetSpec(str(path)), task, AnalysisConfig(regression=options)).analyze()


def flags(result):
    block = result['profile']['regression'].get('dependency_search')
    return {(f['feature'], f['family'], f['form']) for f in block['flags']} if block else set()


def test_the_option_is_off_by_default_and_never_recorded_when_off():
    assert RegressionOptions().dependency_search is None
    assert 'dependency_search' not in omit_default_delimiter(asdict(RegressionOptions()))
    assert RegressionOptions.from_dict({'dependency_search': True}).dependency_search == RegressionDependencyOptions()
    assert RegressionOptions.from_dict({'dependency_search': {'limits': {'max_features': 8}}}).dependency_search.limits == DependencyLimits(max_features=8)
    assert RegressionOptions.from_dict({'dependency_search': False}).dependency_search is None
    for bad in ({'dependency_search': 'yes'}, {'dependency_search': {'other': 1}}, {'unknown': 1}):
        with pytest.raises(ValueError):
            RegressionOptions.from_dict(bad)


def test_off_adds_no_block_and_no_finding():
    result = run(REG / 'data/mutations/sum.csv', 'outcome', RegressionOptions())
    assert 'dependency_search' not in result['profile']['regression']
    assert not any(f['code'].startswith('regression_dependency') for f in result['findings'])
    assert not any(c['check_id'] == 'regression_dependency_search' for c in result['checks'])


# The dossier's negative corpus (DOSSIER.md §4.2) and its four hand-reviewed flags.
NEGATIVE = {f'mutation:{m}': (REG / f'data/mutations/{m}.csv', 'outcome') for m in (
    'copy', 'affine', 'sum', 'sparse_copy', 'missing_nonfinite', 'constant', 'constraint_union', 'rounded_legitimate',
    'heavy_tail_legitimate', 'skew_legitimate', 'bounded_legitimate', 'zero_inflated_count', 'repeated_measurements')}
NEGATIVE.update({'presentation:ambiguous': (REG / 'data/presentation/ambiguous.csv', 'outcome'),
                 'presentation:partial': (REG / 'data/presentation/partial.csv', 'outcome'),
                 'concrete': (REG / 'data/prepared/concrete.csv', 'strength_mpa'),
                 'bike_hour': (REG / 'data/prepared/bike_hour.csv', 'cnt'),
                 'bike_day': (REG / 'data/prepared/bike_day.csv', 'cnt'),
                 'bike_hour_components_removed': (REG / 'data/prepared/bike_hour_components_removed.csv', 'cnt'),
                 'bike_day_components_removed': (REG / 'data/prepared/bike_day_components_removed.csv', 'cnt')})
REVIEWED = {'mutation:sum': {'a'}, 'mutation:missing_nonfinite': {'input'}, 'mutation:constraint_union': {'input'}, 'presentation:partial': {'qa_optional_failure'}}


@pytest.mark.parametrize('name', sorted(NEGATIVE))
def test_the_retained_corpus_raises_only_the_reviewed_flags(name):
    path, target = NEGATIVE[name]
    found = {feature for feature, _, _ in flags(run(path, target))}
    assert found == REVIEWED.get(name, set()), (name, found)


def frame(n=600, seed=0):
    rng = np.random.default_rng(seed)
    product = rng.choice([f'p{i}' for i in range(8)], n)
    x = rng.uniform(1, 100, n)
    return rng, pd.DataFrame({'product': product, 'x': x, 'noise': rng.normal(size=n),
                              'price': [10.0 + 3 * int(p[1:]) for p in product], 'logx': np.log(x) * 7})


def write(tmp_path, data, name='d.csv'):
    path = tmp_path / name
    data.to_csv(path, index=False)
    return path


def test_planted_relationships_are_found_by_family(tmp_path):
    rng, d = frame()
    d['band'] = pd.cut(d['x'], [0, 20, 40, 60, 80, 100], labels=['a', 'b', 'c', 'd', 'e']).astype(str)
    d['tier'] = np.floor(d['x'] / 10) * 5
    path = write(tmp_path, d)
    by_target = {t: flags(run(path, t)) for t in ('price', 'logx', 'tier', 'x')}
    assert ('product', 'categorical_determination', None) in by_target['price']
    assert ('x', 'monotone_mapping', 'strict') in by_target['logx']
    assert ('x', 'monotone_mapping', 'step') in by_target['tier']
    assert ('band', 'target_interval_coding', None) in by_target['x']
    assert not any(f[0] == 'noise' for fs in by_target.values() for f in fs)


def test_identifiers_are_gated_and_a_permuted_target_raises_nothing(tmp_path):
    rng, d = frame()
    d['order_id'] = [f'o{i}' for i in range(len(d))]
    for seed in range(5):
        d['shuffled'] = np.random.default_rng(seed).permutation(d['price'].to_numpy())
        block = search(d, 'shuffled', DependencyLimits(), features=['product', 'order_id', 'x', 'noise'])
        assert block['flags'] == [] and block['status'] == 'completed'
    assert block['identifier_exclusions']['R-ID-1'] == ['order_id']


@pytest.mark.parametrize('state,code,severity', [('unknown', 'regression_dependency_availability_unknown', 'Moderate'),
                                                 ('unavailable_at_prediction', 'regression_dependency_unavailable', 'High'),
                                                 ('available_at_prediction', 'regression_dependency_declared_available', 'Low')])
def test_severity_follows_declared_availability_only(tmp_path, state, code, severity):
    _, d = frame()
    path = write(tmp_path, d[['product', 'noise', 'price']])
    declared = {} if state == 'unknown' else {'product': state}
    result = run(path, 'price', RegressionOptions(feature_availability=declared, dependency_search=True))
    finding = next(f for f in result['findings'] if f['code'].startswith('regression_dependency'))
    assert (finding['code'], finding['severity'], finding['version']) == (code, severity, 'regression_dependency_v1')
    if state == 'unknown':  # 'leakage' only as a possibility, never as a conclusion
        assert finding['evidence'].count('leakage') == finding['evidence'].count('Whether this is leakage or a legitimate rule')
    check = next(c for c in result['checks'] if c['check_id'] == 'regression_dependency_search')
    assert check['execution'] == 'completed'
    assert result['methodology_id'] == 'tabular_regression_v1'


def test_the_budget_bounds_the_search_and_names_what_was_not_searched(tmp_path):
    _, d = frame()
    path = write(tmp_path, d)
    result = run(path, 'price', RegressionOptions(dependency_search=RegressionDependencyOptions(DependencyLimits(max_features=2))))
    block = result['profile']['regression']['dependency_search']
    assert block['status'] == 'bounded' and block['budget_used']['features'] == 2 and len(block['unsearched_features']) == 2


def test_multi_output_runs_one_block_per_output_under_a_shared_budget(tmp_path):
    _, d = frame()
    d['price2'] = d['price'] * 2 + 1
    path = write(tmp_path, d)
    options = RegressionOptions(dependency_search=RegressionDependencyOptions(DependencyLimits(max_checks=5)))
    result = DataTrust.from_spec(DatasetSpec(str(path)), TaskSpec('regression', targets=('price', 'price2')), AnalysisConfig(regression=options)).analyze()
    outputs = result['profile']['multioutput_regression']['outputs']
    blocks = [o['dependency_search'] for o in outputs]
    assert sum(b['budget_used']['checks'] for b in blocks[-1:]) == 5 and blocks[-1]['status'] == 'bounded'
    assert any(f['feature'] == 'product' for f in blocks[0]['flags'])
    assert any(f['code'] == 'regression_dependency_availability_unknown' for f in result['findings'])


def test_the_cli_flag_reaches_the_option(tmp_path):
    from click.testing import CliRunner
    from datatrust.cli import main
    _, d = frame()
    path = write(tmp_path, d[['product', 'noise', 'price']])
    out = tmp_path / 'r.json'
    done = CliRunner().invoke(main, ['audit', str(path), '--task', 'regression', '--target', 'price', '--regression-dependency-search',
                                     '--out', str(tmp_path / 'r.html'), '--json-out', str(out)])
    assert done.exit_code == 0, done.output
    assert json.loads(out.read_text())['profile']['regression']['dependency_search']['flags']


def test_the_app_toggle_turns_the_search_on_and_the_review_says_so(tmp_path):
    from test_app_api import _post, _token, _upload_only
    from datatrust.web import create_app
    _, d = frame()
    app = create_app(tmp_path / 'jobs', max_upload_mib=1)
    app.config.update(TESTING=True)
    try:
        client = app.test_client()
        token = _token(client)
        _upload_only(client, token, d[['product', 'noise', 'price']].to_dict('list'))
        _post(client, token, '/core/job/analysis', {'mode': 'regression'})
        base = {'target': 'price', 'regression_options_submitted': '1', 'target_kind': 'unspecified'}
        off = _post(client, token, '/core/job/configure', base).json['data']['job']
        assert off['config']['regression'] is not None and 'dependency_search' not in off['config']['regression']
        on = _post(client, token, '/core/job/configure', {**base, 'regression_dependency_search': 'on'}).json['data']['job']
        assert on['config']['regression']['dependency_search'] and any('opt-in dependency search' in u for u in on['review']['unknowns'])
        generated = _post(client, token, '/core/job/generate', {'advanced_target_ack': 'confirmed'})  # 8 prices: a review-needed target
        assert generated.status_code == 200, generated.json
        analysis = json.loads(client.get('/api/datatrust/v1/core/job/analysis').get_data(as_text=True))
        assert analysis['profile']['regression']['dependency_search']['flags']
    finally:
        app.extensions['confidenceguard_store'].cleanup()
        app.extensions['datatrust_job_store'].cleanup()


# Review fixes (2026-11-25) -----------------------------------------------------------------------------------------------

from datatrust.contracts import FeatureOptions


def test_declared_semantics_reach_the_search(tmp_path):
    rng = np.random.default_rng(3)
    store = rng.integers(0, 20, 600)
    d = pd.DataFrame({'store_code': store, 'noise': rng.normal(size=600), 'y': store * 2.5 + 1})
    path = write(tmp_path, d)
    declared = DataTrust.from_spec(DatasetSpec(str(path)), TaskSpec('regression', 'y'),
                                   AnalysisConfig(regression=ON, features=FeatureOptions({'store_code': 'identifier'}))).analyze()
    # declaring a meaning moves the run to the role-aware method: the search runs per output there
    assert declared['methodology_id'] == 'tabular_annotation_regression_v1'
    block = declared['profile']['multioutput_regression']['outputs'][0]['dependency_search']
    assert block['identifier_exclusions']['declared_identifier'] == ['store_code'] and not any(f['feature'] == 'store_code' for f in block['flags'])
    wide = pd.DataFrame({'grade': np.repeat(np.arange(400), 2) % 400, 'y': np.repeat(np.arange(400), 2) * 1.5})
    near_unique = search(wide, 'y', DependencyLimits(), features=['grade'])
    exempt = search(wide, 'y', DependencyLimits(), features=['grade'], declared_categorical=['grade'])
    assert near_unique['identifier_exclusions'] == {'near_unique': ['grade']} and exempt['identifier_exclusions'] == {}


def test_single_target_findings_link_to_the_search_evidence(tmp_path):
    _, d = frame()
    result = run(write(tmp_path, d[['product', 'noise', 'price']]), 'price')
    finding = next(f for f in result['findings'] if f['code'].startswith('regression_dependency'))
    evidence = {e['id']: e for e in result['evidence']}
    assert finding['evidence_refs'] and all(evidence[ref]['check_id'] == 'regression_dependency_search' for ref in finding['evidence_refs'])


def test_multi_output_records_a_check_and_reads_context_availability(tmp_path):
    from datatrust.contracts import ContextOptions
    _, d = frame()
    d['price2'] = d['price'] * 2 + 1
    path = write(tmp_path, d)
    context = ContextOptions.from_dict({'prediction': {'objective': None, 'point': 'at order'}, 'columns': {'product': {'availability': 'unavailable_at_prediction'}}})
    result = DataTrust.from_spec(DatasetSpec(str(path)), TaskSpec('regression', targets=('price', 'price2')),
                                 AnalysisConfig(regression=ON, context=context)).analyze()
    assert {c['scope'] for c in result['checks'] if c['check_id'] == 'regression_dependency_search'} == {'price', 'price2'}
    assert any(f['code'] == 'regression_dependency_unavailable' and f['severity'] == 'High' for f in result['findings'])


def test_an_interruption_keeps_what_was_searched_as_partial():
    from datatrust.contracts import AnalysisError
    _, d = frame()
    calls = []

    def checkpoint(stage):
        calls.append(stage)
        if len(calls) > 2:
            raise AnalysisError('Cooperative elapsed-time safeguard reached.', code='resource_limit', stage=stage)
    block = search(d, 'price', DependencyLimits(), checkpoint=checkpoint)
    assert block['status'] == 'partial' and len(block['checks']) == 2 and block['unsearched_features'] and block['reason']


def test_false_means_off():
    assert RegressionOptions(dependency_search=False).dependency_search is None
