"""Before/after preprocessing assessment (M4 versions preset): counts reconcile with an independent pandas oracle
with and without identity keys; declared, observed, lineage and pipeline statements stay apart; existing M4 modes keep
their records; nothing is performed and improvement is never claimed."""
import io
import json
import time
from dataclasses import asdict
from pathlib import Path

import pandas as pd
import pytest

from datatrust import ComparisonSpec, DatasetInput, DatasetSpec, TaskSpec
from datatrust.m4_contracts import spec_record
from datatrust.m4_worker import compare

ROOT = Path(__file__).resolve().parents[1]
GERMAN = ROOT / 'validation/data/prepared/german_credit.csv'
FILTER = [{"kind": "filter", "description": "credit_amount < 10000"}, {"kind": "drop_columns", "columns": ["telephone"]}, {"kind": "impute", "columns": ["age"]}]


@pytest.fixture(scope='module')
def files(tmp_path_factory):
    tmp = tmp_path_factory.mktemp('ba')
    before = pd.read_csv(GERMAN); before.insert(0, 'id', range(len(before)))
    before.loc[before.index % 50 == 0, 'age'] = None
    after = before[before.credit_amount < 10000].drop(columns=['telephone']).copy()
    after['age'] = after['age'].fillna(after['age'].median())
    paths = {'before': tmp / 'before.csv', 'after': tmp / 'after.csv'}
    before.to_csv(paths['before'], index=False); after.to_csv(paths['after'], index=False)
    return tmp, before, after, paths


def assess(before_path, after_path, transformations=(), keys=()):
    task = TaskSpec('classification', 'credit_risk')
    spec = ComparisonSpec('versions', (DatasetInput('source1', 'reference', DatasetSpec(str(before_path)), task), DatasetInput('source2', 'current', DatasetSpec(str(after_path)), task)),
                          identity_keys=keys, preset='before_after', transformations=tuple(transformations))
    result = compare(spec)
    measurement = next(v for k, v in result.coverage['measurements'].items() if k.endswith('.before_after'))
    return result, measurement, {f['title'] for f in result.findings if f['scope'] == 'source1:source2'}


def test_identity_lineage_reconciles_with_a_pandas_oracle(files):
    _, before, after, paths = files
    result, m, titles = assess(paths['before'], paths['after'], FILTER, keys=(('id',),))
    dropped = before[~before.id.isin(after.id)]
    lineage, rows = m['lineage'], m['observed']['rows']
    assert lineage['identities'] == {'retained': len(after), 'dropped': len(dropped), 'added': 0} and lineage['row_level']
    assert lineage['by_class']['dropped'] == dropped.credit_risk.value_counts().to_dict() and lineage['by_class']['label_changed'] == 0
    assert rows['explained'] is True and rows['difference'] == len(after) - len(before)
    assert titles.isdisjoint({'Changes between before and after were not declared', 'Declared transformations are not reflected in the data', 'Declared imputation left missing values'})
    assert m['statement'].startswith('Fewer findings or a higher score after preprocessing does not establish improvement')
    assert m['pipeline_use'].startswith('Not observed') and result.guidance['items']


def test_without_keys_counts_still_reconcile_and_lineage_is_stated_unavailable(files):
    _, before, after, paths = files
    _, m, titles = assess(paths['before'], paths['after'], FILTER)
    rows = m['observed']['rows']
    expected = (after.credit_risk.value_counts() - before.credit_risk.value_counts()).fillna(0).astype(int).to_dict()
    assert rows['difference'] == len(after) - len(before) and rows['by_class_difference'] == expected
    assert sum(rows['by_class_difference'].values()) + rows['missing_target_difference'] == rows['difference']  # arithmetic consistency
    assert rows['explained'] is None and m['lineage'] == {'available': False, 'reason': rows['explanation']} and 'requires identity keys' in rows['explanation']
    assert 'Row changes are not explained by identity evidence' in titles


def test_declared_observed_and_undeclared_changes_stay_apart(files):
    tmp, before, _, paths = files
    same = tmp / 'same.csv'; before.to_csv(same, index=False)
    _, m, titles = assess(paths['before'], same, [{"kind": "drop_columns", "columns": ["telephone"]}])
    assert m['observed']['declared_but_not_observed'] == [{'kind': 'drop_columns', 'columns': ['telephone'], 'reason': 'still present after'}]
    assert 'Declared transformations are not reflected in the data' in titles
    dropped = tmp / 'dropped.csv'; before.drop(columns=['telephone']).to_csv(dropped, index=False)
    _, m, titles = assess(paths['before'], dropped)
    assert m['observed']['undeclared_changes'] == [{'change': 'removed', 'column': 'telephone'}] and 'Changes between before and after were not declared' in titles
    partial = before.copy(); missing = partial.index[partial.age.isna()]; partial.loc[missing[:10], 'age'] = 40
    half = tmp / 'half.csv'; partial.to_csv(half, index=False)
    _, m, titles = assess(paths['before'], half, [{"kind": "impute", "columns": ["age"]}])
    assert m['observed']['declared_imputation_remaining'] == [{'column': 'age', 'still_missing': len(missing) - 10}] and 'Declared imputation left missing values' in titles
    encoded = tmp / 'encoded.csv'; pd.get_dummies(before, columns=['housing'], prefix='housing', dtype=int).to_csv(encoded, index=False)
    _, m, _ = assess(paths['before'], encoded)
    assert [x['column'] for x in m['observed']['observed_encoding_patterns']] == ['housing']


def test_specification_rules_and_unchanged_records_for_existing_modes():
    task = TaskSpec('dataset_profile')
    inputs = (DatasetInput('a', 'reference', DatasetSpec('a.csv'), task), DatasetInput('b', 'current', DatasetSpec('b.csv'), task))
    with pytest.raises(ValueError, match='belong to the before/after preset'):
        ComparisonSpec('versions', inputs, transformations=({"kind": "impute", "columns": ["x"]},))
    with pytest.raises(ValueError, match='compares two versions'):
        ComparisonSpec('splits', (DatasetInput('a', 'train', DatasetSpec('a.csv'), task), DatasetInput('b', 'test', DatasetSpec('b.csv'), task)), preset='before_after')
    with pytest.raises(ValueError, match='names its columns'):
        ComparisonSpec('versions', inputs, preset='before_after', transformations=({"kind": "impute"},))
    plain = spec_record(asdict(ComparisonSpec('versions', inputs)))
    assert 'preset' not in plain and 'transformations' not in plain  # existing manifests, seals and canonical JSON are unchanged


def test_the_app_runs_a_before_after_assessment(files, tmp_path):
    from datatrust.web import create_app
    _, _, _, paths = files
    app = create_app(tmp_path / 'ui'); app.testing = True
    c = app.test_client(); h = {'X-CSRF-Token': c.get('/api/datatrust/v1/session').json['data']['csrf_token']}
    api = '/api/datatrust/v1'
    assert c.post(f'{api}/m4/start', json={'mode': 'before_after'}, headers=h).status_code == 201
    for name in ('before', 'after'):
        c.post(f'{api}/m4/sources', data={'delimiter': 'auto', 'dataset': (io.BytesIO(paths[name].read_bytes()), f'{name}.csv')}, headers=h, content_type='multipart/form-data')
    fields = {'source1_task': 'classification', 'source1_targets': 'credit_risk', 'source2_task': 'classification', 'source2_targets': 'credit_risk',
              'identity_keys': 'id', 'transformations': json.dumps(FILTER), 'configuration': '{}'}
    view = c.post(f'{api}/m4/configure', json=fields, headers=h).json['data']['job']
    assert view['state'] == 'confirm'
    c.post(f'{api}/m4/run', json={'fingerprint': view['fingerprint']}, headers=h)
    store = app.extensions['datatrust_m4_store']; job = next(iter(store.jobs.values()))
    for _ in range(600):
        if job['state'] != 'running': break
        time.sleep(.05)
    analysis = c.get(f'{api}/m4/analysis').json
    assert analysis['comparison']['preset'] == 'before_after' and [i['role'] for i in analysis['inputs']] == ['reference', 'current']
    m = next(v for k, v in analysis['coverage']['measurements'].items() if k.endswith('.before_after'))
    assert m['observed']['rows']['explained'] is True
    report = c.get(f'{api}/m4/download/html').get_data(as_text=True)
    assert 'Reconciliation and lineage' in report and 'does not establish improvement' in report
    store.cleanup(); app.extensions['confidenceguard_store'].cleanup()
