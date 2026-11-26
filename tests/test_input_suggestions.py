"""Stage 4a: advisory guidance from the input inspection.

- regression target groups: nothing preselected; every column the confirmation step would flag for an acknowledgement
  is in "review" or "unavailable", on every retained tabular dataset;
- applicability: every listed analysis stays choosable, the profile always runs, and each state follows its rules.
"""
from pathlib import Path

import pandas as pd
import pytest

from datatrust import CsvParseOptions
from datatrust.applicability import STATES, applicable_analyses
from datatrust.inspection import inspect_table
from datatrust.target_guidance import REGRESSION_GROUP_ORDER, assess_regression_target, regression_target_groups

ROOT = Path(__file__).resolve().parents[1]
CORPUS = {
    'bike_hour': 'validation/regression/data/prepared/bike_hour.csv',
    'bike_day': 'validation/regression/data/prepared/bike_day.csv',
    'concrete': 'validation/regression/data/prepared/concrete.csv',
    'bank_marketing': 'validation/data/prepared/bank_marketing.csv',
    'german_credit': 'validation/data/prepared/german_credit.csv',
    'energy': 'validation/m3/data/prepared/energy.csv',
    'linnerud': 'validation/m3/data/prepared/linnerud.csv',
    'scene': 'validation/m3/data/prepared/scene.csv',
}
EXPECTED_GROUPS = {
    'bike_hour': {'outcome_word': {'cnt'}, 'numeric': {'casual', 'registered', 'temp'}, 'review': {'instant', 'season', 'holiday'}, 'unavailable': {'dteday'}},
    'concrete': {'outcome_word': {'strength_mpa'}, 'review': {'age_days'}},
    'energy': {'outcome_word': {'heating_load', 'cooling_load'}, 'review': {'orientation', 'glazing_distribution'}},
    'bank_marketing': {'numeric': {'duration', 'balance'}, 'unavailable': {'subscribed_term_deposit'}},
}


@pytest.fixture(scope='module', params=sorted(CORPUS))
def case(request):
    path = ROOT / CORPUS[request.param]
    return request.param, inspect_table(path, CsvParseOptions()), pd.read_csv(path)


def test_groups_cover_every_column_once_in_order_and_flagged_columns_are_in_review(case):
    name, inspection, data = case
    groups = regression_target_groups(inspection)
    names = [o['name'] for o in groups['options']]
    assert sorted(names) == sorted(map(str, data.columns))
    order = [REGRESSION_GROUP_ORDER.index(o['group']) for o in groups['options']]
    assert order == sorted(order)
    for option in groups['options']:
        if option['group'] in {'outcome_word', 'numeric'}:
            assert not assess_regression_target(data[option['name']], option['name'])['requires_override'], (name, option)
    by = {}
    for option in groups['options']:
        by.setdefault(option['group'], set()).add(option['name'])
    for group, expected in EXPECTED_GROUPS.get(name, {}).items():
        assert expected <= by.get(group, set()), (name, group, by.get(group))


def test_applicability_lists_every_analysis_and_never_gates(case):
    name, inspection, _ = case
    out = applicable_analyses(inspection)
    assert [a['analysis'] for a in out] == ['unlabeled', 'role_profile', 'classification', 'regression', 'multioutput', 'multilabel_classification',
                                            'annotation_classification', 'annotation_regression', 'clustering', 'anomaly_detection', 'temporal', 'comparison', 'text']
    assert all(a['state'] in STATES and a['reason'] for a in out)
    states = {a['analysis']: a['state'] for a in out}
    assert states['unlabeled'] == states['role_profile'] == 'can_run' and states['comparison'] == 'needs_input'
    assert (states['multilabel_classification'] == 'can_run') == (name in {'bike_hour', 'bike_day', 'bank_marketing', 'scene'})
    assert (states['temporal'] == 'needs_input') == (name in {'bike_hour', 'bike_day'})


def test_no_defensible_target(tmp_path):
    path = tmp_path / 'ids.csv'
    pd.DataFrame({'user_id': [f'u{i}' for i in range(30)], 'note': ['a long free-text comment about something that happened ' + str(i) for i in range(30)]}).to_csv(path, index=False)
    out = {a['analysis']: a for a in applicable_analyses(inspect_table(path, CsvParseOptions()))}
    assert out['classification']['state'] == out['regression']['state'] == 'unlikely'
    assert out['unlabeled']['state'] == 'can_run' and out['text']['state'] == 'needs_input'
    assert {o['group'] for o in regression_target_groups(inspect_table(path, CsvParseOptions()))['options']} == {'unavailable'}


def test_identifiers_are_not_counted_as_distance_features(tmp_path):
    path = tmp_path / 'one.csv'
    pd.DataFrame({'row_id': range(40), 'x': [i * 0.5 for i in range(40)]}).to_csv(path, index=False)
    out = {a['analysis']: a for a in applicable_analyses(inspect_table(path, CsvParseOptions()))}
    assert out['clustering']['state'] == 'unlikely'


def test_the_job_view_carries_the_suggestions(tmp_path):
    from test_app_api import CLASSIFICATION, _token, _upload_only
    from datatrust.web import create_app
    app = create_app(tmp_path / 'jobs', max_upload_mib=1)
    app.config.update(TESTING=True)
    try:
        client = app.test_client()
        job = _upload_only(client, _token(client), CLASSIFICATION).json['data']['job']
        assert {a['analysis'] for a in job['suggestions']['analyses']} >= {'classification', 'regression'}
        assert job['suggestions']['regression_targets']['options']
    finally:
        app.extensions['confidenceguard_store'].cleanup()
        app.extensions['datatrust_job_store'].cleanup()
