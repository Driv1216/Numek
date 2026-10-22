"""Contextual diagnostics (context_v1): declarations produce a separate interpreted view; raw evidence, legacy findings
and scores never change; candidates are conservative and never applied; the dependency search is bounded and
honest about its scope; availability findings follow the declared prediction point; declarations are sealed."""
import io
import json
import re
from dataclasses import asdict
from pathlib import Path

import pandas as pd
import pytest

from datatrust import AnalysisConfig, DataTrust, DatasetSpec, ExecutionLimits, RegressionOptions, TaskSpec
from datatrust.annotations import specification_fingerprint
from datatrust.contextual import candidates
from datatrust.contracts import ContextOptions, DependencyLimits, json_safe, omit_default_delimiter
from datatrust.web import create_app

ROOT = Path(__file__).resolve().parents[1]
GERMAN = ROOT / 'validation/data/prepared/german_credit.csv'
BANK = ROOT / 'validation/data/prepared/bank_marketing.csv'
API = '/api/datatrust/v1'
BANK_CONTEXT = {"prediction": {"objective": "decide which clients to call", "point": "before the first contact"},
                "columns": {"duration": {"availability": "unavailable_at_prediction"},
                            "pdays": {"sentinels": [{"value": -1, "meaning": "not_applicable"}], "applies_when": {"column": "previous", "op": ">", "value": 0}, "unit": "days"},
                            "previous_campaign_outcome": {"placeholders": {"unknown": "not_applicable"}, "applies_when": {"column": "previous", "op": ">", "value": 0}},
                            "contact": {"placeholders": {"unknown": "not_collected"}}}}


def run(path, task, **config):
    return DataTrust.from_spec(DatasetSpec(str(path)), task, AnalysisConfig(**config) if config else None).analyze_result()


@pytest.fixture(scope='module')
def bank():
    plain = run(BANK, TaskSpec('classification', target='subscribed_term_deposit'))
    declared = run(BANK, TaskSpec('classification', target='subscribed_term_deposit'), context=BANK_CONTEXT)
    return plain, declared


def test_an_absent_context_leaves_every_record_and_seal_unchanged():
    config = AnalysisConfig()
    assert 'context' not in omit_default_delimiter(asdict(config)) and 'context' not in json_safe(asdict(config))
    task = TaskSpec('classification', 'credit_risk')
    columns = list(pd.read_csv(GERMAN, nrows=0).columns)
    with_context = AnalysisConfig(context={"columns": {"age": {"unit": "years"}}})
    assert specification_fingerprint(task, config, columns) != specification_fingerprint(task, with_context, columns)  # declarations are sealed
    assert AnalysisConfig.from_dict({"context": BANK_CONTEXT}).context.columns['pdays'].sentinels[0]['value'] == -1
    assert AnalysisConfig.from_dict(json.loads(json.dumps(json_safe(asdict(with_context))))).context == with_context.context  # record layout round-trips


@pytest.mark.parametrize('declaration,message', [
    ({"columns": {"x": {"placeholders": {"unknown": "nothing"}}}}, 'Placeholders map'),
    ({"columns": {"x": {"sentinels": [{"value": "a", "meaning": "not_applicable"}]}}}, 'finite numeric value'),
    ({"columns": {"x": {"applies_when": {"column": "y", "op": "~", "value": 1}}}}, 'applies_when'),
    ({"columns": {"x": {"availability": "sometimes"}}}, 'Availability'),
    ({"columns": {}, "extra": 1}, 'only prediction'),
])
def test_invalid_declarations_are_refused(declaration, message):
    with pytest.raises(ValueError, match=message):
        ContextOptions.from_dict(declaration)


def test_regression_availability_contract_wins_and_conflicts_are_refused():
    with pytest.raises(ValueError, match='declared twice'):
        AnalysisConfig(regression=RegressionOptions(feature_availability={'temp': 'available_at_prediction'}),
                       context={"columns": {"temp": {"availability": "unavailable_at_prediction"}}})
    agreeing = AnalysisConfig(regression=RegressionOptions(feature_availability={'temp': 'unavailable_at_prediction'}),
                              context={"columns": {"temp": {"availability": "unavailable_at_prediction"}}})
    result = run(ROOT / 'validation/regression/data/prepared/bike_hour.csv', TaskSpec('regression', target='cnt'), regression=agreeing.regression, context=agreeing.context)
    assert 'regression_declared_availability' in [f['code'] for f in result.findings]
    assert 'declared_unavailable_feature' not in [f['code'] for f in result.contextual['findings']]  # not repeated


def test_declarations_never_change_raw_evidence_legacy_findings_or_scores(bank):
    plain, declared = bank
    a, b = plain.to_dict(), declared.to_dict()
    for key in ('profile', 'checks', 'evidence', 'findings', 'narrative', 'scoring', 'coverage'):
        assert a[key] == b[key], key
    assert plain.to_legacy_dict() == declared.to_legacy_dict()
    assert a['scoring']['values']['overall'] == 69.0


def test_bank_interpretations_match_an_independent_pandas_oracle(bank):
    _, declared = bank
    data = pd.read_csv(BANK)
    pdays = declared.contextual['interpreted']['pdays']
    applicable = (data.previous > 0) & (data.pdays != -1)
    values = data.pdays[applicable].astype(float)
    q1, q3 = values.quantile(.25), values.quantile(.75)
    assert pdays['applicable_rows'] == int(applicable.sum()) == 8257
    assert pdays['applicable_numeric']['outlier_count'] == int(((values < q1 - 1.5 * (q3 - q1)) | (values > q3 + 1.5 * (q3 - q1))).sum()) == 49
    assert pdays['condition']['exceptions']['value_present_where_declared_not_to_apply'] == int(((data.previous <= 0) & (data.pdays != -1)).sum()) == 0
    outcome = declared.contextual['interpreted']['previous_campaign_outcome']['condition']['exceptions']
    expected = data.index[(data.previous > 0) & (data.previous_campaign_outcome == 'unknown')]
    assert outcome['not_applicable_code_where_condition_holds'] == len(expected) == 5 and outcome['absent_row_refs'] == [int(i) + 1 for i in expected]
    contact = declared.contextual['interpreted']['contact']
    assert contact['declared_missing_rows'] == int((data.contact == 'unknown').sum()) == 13020
    codes = {f['code']: f for f in declared.contextual['findings']}
    assert codes['declared_unavailable_feature']['columns'] == ['duration'] and codes['declared_missing_population']['severity'] == 'Moderate'
    assert codes['declared_condition_exceptions']['columns'] == ['previous_campaign_outcome', 'previous']


def test_without_declarations_only_candidates_and_co_occurrence_are_reported(bank):
    plain, _ = bank
    c = plain.contextual
    assert c['interpreted'] == {} and c['findings'] == [] and not c['prediction']['declared']
    assert {(x['column'], x['value']) for x in c['candidates']} == {('pdays', -1), ('previous_campaign_outcome', 'unknown'), ('contact', 'unknown'), ('education', 'unknown'), ('job', 'unknown')}
    pair = c['observed_dependencies']['pairs'][0]
    assert {pair['a']['column'], pair['b']['column']} == {'pdays', 'previous_campaign_outcome'} and pair['both'] == 36954 and pair['a_only'] + pair['b_only'] == 5
    assert c['dependency_search']['status'] == 'completed' and c['dependency_search']['flagged'] == [] and len(c['dependency_search']['checks']) == 16


@pytest.mark.parametrize('values,expected', [
    ([-1] * 30 + list(range(-5, 6)) * 10, False),        # −1 inside the range of the other values: a real value
    ([999] * 3 + list(range(1, 120)) * 1, False),        # under 1% of rows… and under 5 rows
    ([999] * 6 + list(range(1, 120)) * 2, True),         # outside the range, 6 rows, 2.5%
])
def test_sentinel_candidates_are_conservative(values, expected):
    frame = pd.DataFrame({'x': values})
    assert any(c['value'] == 999 or c['value'] == -1 for c in candidates(frame, ['x'])) is expected


def copied(tmp_path, rows=None, noise=False, name='col_17'):
    data = pd.read_csv(GERMAN)
    if rows:
        data = data.head(rows).copy()
    data[name] = data.credit_risk
    if noise:
        data.loc[data.index[:20], name] = data.credit_risk[:20].map({'good': 'bad', 'bad': 'good'})
    path = tmp_path / 'g.csv'
    data.to_csv(path, index=False)
    return path


def test_dependency_search_gates_scope_and_abstention(tmp_path):
    task = TaskSpec('classification', 'credit_risk')
    assert run(copied(tmp_path), task).contextual['dependency_search']['flagged'] == ['col_17']
    assert run(copied(tmp_path, noise=True), task).contextual['dependency_search']['flagged'] == []  # gates require no exceptions
    small = run(copied(tmp_path, rows=60), task).contextual['dependency_search']
    assert small['status'] == 'not_assessable' and len(small['unsearched_features']) == 21
    bounded = run(copied(tmp_path), task, context={"limits": {"max_features": 3}}).contextual['dependency_search']
    assert bounded['status'] == 'bounded' and len(bounded['checks']) == 3 and 'col_17' in bounded['unsearched_features']
    found = run(copied(tmp_path), task).contextual['findings']
    assert [f['code'] for f in found] == ['dependency_availability_unknown']
    declared = run(copied(tmp_path), task, context={"prediction": {"point": "before"}, "columns": {"col_17": {"availability": "unavailable_at_prediction"}}}).contextual['findings']
    assert {f['code'] for f in declared} == {'declared_unavailable_feature', 'target_dependency_unavailable'}


def test_unknown_declared_columns_fail_and_a_deadline_is_reported_not_hidden(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match='unknown columns: nope'):
        run(GERMAN, TaskSpec('classification', 'credit_risk'), context={"columns": {"nope": {"unit": "x"}}})
    elapsed = [0]
    monkeypatch.setattr('datatrust.core.time.monotonic', lambda: elapsed[0])
    from datatrust import contextual
    original = contextual.validate
    def slow(*args, **kwargs):  # the deadline passes just before the contextual stage
        elapsed[0] = 5
        return original(*args, **kwargs)
    monkeypatch.setattr(contextual, 'validate', slow)
    path = tmp_path / 'u.csv'; path.write_text('a,b\n' + ''.join(f'{i},{i % 3}\n' for i in range(40)))
    result = run(path, TaskSpec('dataset_profile'), limits=ExecutionLimits(max_seconds=1))
    assert result.contextual['status'] == 'not_completed' and result.execution['status'] == 'partial'
    assert any(c.check_id == 'contextual_evidence' and c.execution == 'skipped' for c in result.checks)


def test_contextual_guidance_is_traceable(bank):
    _, declared = bank
    value = declared.to_dict()
    items = {k: v for k, v in value['guidance']['items'].items() if k.startswith('context.')}
    assert {v['catalogue'] for v in items.values()} == {'declared_unavailable', 'condition_exceptions', 'declared_missing'}
    from tests.test_guidance import assert_traceable
    assert_traceable(value)
    assert any('interpreted only where you declared them' in u for u in value['guidance']['scope']['unknowns'])


# ——— App: suggestions, declarations, sealing ———

def client(tmp_path):
    app = create_app(tmp_path / 'ui'); app.testing = True
    c = app.test_client(); h = {'X-CSRF-Token': c.get(f'{API}/session').json['data']['csrf_token']}
    return app, c, h


def test_app_suggests_declares_seals_and_invalidates(tmp_path):
    app, c, h = client(tmp_path)
    head = pd.read_csv(BANK).sample(3000, random_state=1)  # the first rows hold only pdays = −1, so no suggestion is possible there
    c.post(f'{API}/core/jobs', data={'mode': 'classification', 'dataset': (io.BytesIO(head.to_csv(index=False).encode()), 'bank.csv')}, headers=h, content_type='multipart/form-data')
    info = c.get(f'{API}/core/job/context').json['data']
    assert ('pdays', -1) in {(x['column'], x['value']) for x in info['candidates']} and info['context'] is None
    bad = c.post(f'{API}/core/job/configure', json={'target': 'subscribed_term_deposit', 'dataset_name': 'B', 'context': json.dumps({"columns": {"nope": {"unit": "x"}}})}, headers=h)
    assert bad.status_code == 422 and 'nope' in bad.json['error']['message']
    declared = json.dumps({"prediction": {"objective": None, "point": "before the first contact"}, "columns": {"duration": {"availability": "unavailable_at_prediction"}}})
    ok = c.post(f'{API}/core/job/configure', json={'target': 'subscribed_term_deposit', 'dataset_name': 'B', 'context': declared}, headers=h)
    assert ok.status_code == 200 and ok.json['data']['job']['config']['context']['columns']['duration']['availability'] == 'unavailable_at_prediction'
    assert c.post(f'{API}/core/job/generate', json={}, headers=h).status_code == 200
    analysis = c.get(f'{API}/core/job/analysis').json
    assert [f['code'] for f in analysis['contextual']['findings']] == ['declared_unavailable_feature']
    job = app.extensions['datatrust_job_store'].get(next(iter(app.extensions['datatrust_job_store'].jobs)))
    job['config'] = job['config'].__class__(**{**job['config'].__dict__, 'context': None})  # a context changed outside configure
    assert c.post(f'{API}/core/job/generate', json={}, headers=h).status_code == 422
    changed = c.post(f'{API}/core/job/configure', json={'target': 'subscribed_term_deposit', 'dataset_name': 'B', 'context': ''}, headers=h).json['data']['job']
    assert changed['artifacts'] == [] and changed['config']['context'] is None
    app.extensions['confidenceguard_store'].cleanup(); app.extensions['datatrust_job_store'].cleanup()
