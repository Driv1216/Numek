"""input_inspection_v1 (src/datatrust/inspection.py): bounded, deterministic, advisory.

- each rule fires on its fixture and stays silent where it should;
- every budget is enforced, and a partial pass says so and never claims whole-file properties;
- the default classification path reads the file once (the inspection reuses the analysis frame);
- the inspection is cached by parse fingerprint and rerun once when parsing changes.
"""
from pathlib import Path

import pandas as pd
import pytest

from datatrust import inspection as I
from datatrust import CsvParseOptions
from datatrust.inspection import InspectionBudget, inspect_table, profile_fingerprint

ROOT = Path(__file__).resolve().parents[1]
BIKE = ROOT / 'validation/regression/data/prepared/bike_hour.csv'


def _write(tmp_path, frame, name='t.csv'):
    path = tmp_path / name
    frame.to_csv(path, index=False)
    return path


def _rules(out):
    return {c['name']: {s['rule'] for s in c['suggestions']} for c in out['columns']}


def test_bike_hour_suggestions_and_complete_coverage():
    out = inspect_table(BIKE, CsvParseOptions())
    rules = _rules(out)
    assert out['version'] == 'input_inspection_v1' and out['coverage']['complete'] and out['coverage']['rows_inspected'] == 17_379
    assert out['coverage']['statement'] == 'Inspected all 17,379 rows.'
    assert 'R-TIME-1' in rules['dteday'] and 'R-ID-2' in rules['instant'] and 'R-ID-1' not in rules['instant']
    assert {'R-NUM-1'} <= rules['cnt'] and {'R-NUM-1'} <= rules['casual'] and {'R-NUM-1'} <= rules['registered']
    for name in ('holiday', 'workingday', 'yr'):
        assert 'R-BIN-1' in rules[name]
    assert out['table'][0]['rule'] == 'R-MULTI-1' and {'holiday', 'workingday', 'yr'} <= set(out['table'][0]['columns'])
    assert not any('R-ENTITY-1' in r for r in rules.values())  # entities come from the clock pair test (time_structure), not per column
    instant = next(c for c in out['columns'] if c['name'] == 'instant')
    assert instant['structural'][0] == 'A different value in every row (17,379 values).'


def test_rule_fixtures(tmp_path):
    n = 60
    frame = pd.DataFrame({
        'customer_id': [f'c{i}' for i in range(n)],
        'store': [f's{i % 4}' for i in range(n)],
        'when': pd.date_range('2024-01-01', periods=n, freq='h').astype(str),
        'epoch': [1_700_000_000 + 3600 * i for i in range(n)],
        'flag': ['yes', 'no'] * (n // 2),
        'colour': ['red', 'green', 'blue'] * (n // 3),
        'note': ['this is a fairly long free text note about the row number ' + str(i) for i in range(n)],
        'status': ['labeled', 'pending', 'skipped'] * (n // 3),
        'constant': [7] * n,
        'value': [float(i) / 3 for i in range(n)],
    })
    out = inspect_table(_write(tmp_path, frame), CsvParseOptions())
    rules = _rules(out)
    assert 'R-ID-1' in rules['customer_id']
    assert 'R-TIME-1' in rules['when'] and 'R-TIME-1' not in rules['store']
    assert 'R-TIME-2' in rules['epoch']
    assert 'R-BIN-1' in rules['flag'] and out['table'] == []  # one indicator is not a set
    assert 'R-CAT-1' in rules['colour'] and 'R-CAT-1' not in rules['customer_id']
    assert 'R-TEXT-1' in rules['note']
    assert 'R-STATUS-1' in rules['status']
    assert not any('R-ENTITY-1' in r for r in rules.values())
    assert 'R-NUM-1' in rules['value'] and 'R-NUM-1' not in rules['constant']
    constant = next(c for c in out['columns'] if c['name'] == 'constant')
    assert constant['structural'] == ['One value in every row.']
    for column in out['columns']:
        for s in column['suggestions']:
            assert s['text'] == I.RULES[s['rule']]


def test_ambiguous_dates_are_never_suggested_as_a_clock(tmp_path):
    frame = pd.DataFrame({'d': ['03/04/2024', '05/06/2024', '07/08/2024'] * 10, 'x': range(30)})
    assert 'R-TIME-1' not in _rules(inspect_table(_write(tmp_path, frame), CsvParseOptions()))['d']


def test_suggestions_are_never_applied_and_unknowns_are_stated():
    out = inspect_table(BIKE, CsvParseOptions())
    assert out['unknowns'] == I.UNKNOWNS and out['rules'] == I.RULES
    assert set(out) == {'version', 'profile', 'coverage', 'columns', 'table', 'rules', 'unknowns', 'budget'}


# budgets ---------------------------------------------------------------------------------------------------------------

def _wide(tmp_path, rows=200, cols=6):
    frame = pd.DataFrame({f'c{j}': [i * (j + 1) for i in range(rows)] for j in range(cols)})
    frame['row_id'] = range(rows)
    return _write(tmp_path, frame)


def test_row_budget_stops_with_disclosure_and_no_whole_file_claims(tmp_path):
    out = inspect_table(_wide(tmp_path), CsvParseOptions(), InspectionBudget(full_rows=50, chunk_rows=20))
    cov = out['coverage']
    assert not cov['complete'] and cov['stopped'] == 'rows' and cov['rows_inspected'] == 50
    assert cov['statement'] == 'Inspected the first 50 rows only (the inspection limit); suggestions describe those rows.'
    row_id = next(c for c in out['columns'] if c['name'] == 'row_id')
    assert row_id['structural'][0] == 'A different value in the inspected rows (50 values).'
    assert not any('every row' in line for c in out['columns'] for line in c['structural'])


def test_byte_budget_falls_back_to_the_first_rows(tmp_path):
    out = inspect_table(_wide(tmp_path), CsvParseOptions(), InspectionBudget(full_bytes=10, fallback_rows=30, chunk_rows=1000))
    assert out['coverage']['stopped'] == 'bytes' and out['coverage']['rows_inspected'] == 30
    assert out['coverage']['statement'].startswith('The file is larger than 0 MiB: inspected the first 30 rows only')


def test_an_exact_fit_is_complete(tmp_path):
    out = inspect_table(_wide(tmp_path), CsvParseOptions(), InspectionBudget(full_rows=200, chunk_rows=50))
    assert out['coverage']['complete'] and out['coverage']['rows_inspected'] == 200


def test_column_budgets_list_then_count(tmp_path):
    out = inspect_table(_wide(tmp_path, cols=9), CsvParseOptions(), InspectionBudget(profiled_columns=3, listed_columns=6))
    cov = out['coverage']
    assert (cov['columns_total'], cov['columns_profiled'], cov['columns_listed']) == (10, 3, 6)
    assert [c.get('not_profiled', False) for c in out['columns']] == [False] * 3 + [True] * 3
    assert cov['statement'].endswith('Columns 4–10 were listed, not profiled.')


def test_distinct_tracking_is_capped(tmp_path):
    out = inspect_table(_wide(tmp_path), CsvParseOptions(), InspectionBudget(distinct_cap=25))
    c1 = next(c for c in out['columns'] if c['name'] == 'c1')['observed']
    assert c1['distinct'] is None and c1['distinct_capped'] is True
    assert 'R-CAT-1' not in _rules(out)['c1']


def test_uniqueness_is_tracked_for_a_bounded_number_of_columns(tmp_path):
    out = inspect_table(_wide(tmp_path, cols=6), CsvParseOptions(), InspectionBudget(unique_tracked=1, chunk_rows=50))
    ids = [c['name'] for c in out['columns'] if any(s['role'] == 'identifier' for s in c['suggestions'])]
    assert ids == ['row_id']  # the identifier-named column is tracked first; the others are not claimed unique


def test_deadline_stops_between_chunks(tmp_path):
    ticks = iter(range(0, 100, 5))
    out = inspect_table(_wide(tmp_path), CsvParseOptions(), InspectionBudget(chunk_rows=40, deadline_seconds=4), clock=lambda: next(ticks))
    cov = out['coverage']
    assert cov['stopped'] == 'time' and cov['rows_inspected'] == 40
    assert cov['statement'] == 'Stopped after 40 rows at the 4-second inspection limit; suggestions describe those rows.'


def test_the_deadline_on_the_last_chunk_is_not_a_stop(tmp_path):
    ticks = iter(range(0, 100, 5))
    out = inspect_table(_wide(tmp_path, rows=40), CsvParseOptions(), InspectionBudget(chunk_rows=40, deadline_seconds=4), clock=lambda: next(ticks))
    assert out['coverage']['complete']


def test_reading_a_supplied_frame_equals_reading_the_file(tmp_path):
    path = _wide(tmp_path)
    frame = pd.read_csv(path)
    assert inspect_table(path, CsvParseOptions(), frame=frame) == inspect_table(path, CsvParseOptions())


def test_numeric_overrides_refuse_like_the_analysis(tmp_path):
    path = _write(tmp_path, pd.DataFrame({'x': ['1', '2', 'oops'], 'y': [1, 2, 3]}))
    with pytest.raises(ValueError, match="Column 'x' contains invalid numeric values"):
        inspect_table(path, CsvParseOptions(column_types={'x': 'numeric'}))


def test_the_fingerprint_follows_parse_options():
    assert profile_fingerprint(CsvParseOptions()) == profile_fingerprint(CsvParseOptions())
    assert profile_fingerprint(CsvParseOptions()) != profile_fingerprint(CsvParseOptions(delimiter=';'))
    assert profile_fingerprint(CsvParseOptions()) != profile_fingerprint(CsvParseOptions(encoding='latin-1'))


# web integration -------------------------------------------------------------------------------------------------------

def test_the_default_classification_path_reads_the_file_once(tmp_path, monkeypatch):
    from datatrust import web
    reads = []
    real = pd.read_csv
    monkeypatch.setattr(pd, 'read_csv', lambda *a, **k: reads.append(k.get('nrows')) or real(*a, **k))
    path = _write(tmp_path, pd.DataFrame({'x': range(40), 'label': [0, 1] * 20}))
    job = {'mode': 'classification', 'dataset_path': path, 'config': web.with_delimiter(web.AnalysisConfig(), ',')}
    sink = {}
    web.inspect_upload(job, sink)
    before = len([r for r in reads if r is None])
    web.refresh_input_inspection(job, sink.get('frame'))
    assert len([r for r in reads if r is None]) == before  # no second full read
    assert job['input_inspection']['coverage']['complete']


def test_the_inspection_is_reused_until_parsing_changes(tmp_path, monkeypatch):
    from datatrust import web
    calls = []
    real = I.inspect_table
    monkeypatch.setattr(I, 'inspect_table', lambda *a, **k: calls.append(1) or real(*a, **k))
    path = _write(tmp_path, pd.DataFrame({'x': range(10), 'y': range(10)}))
    job = {'mode': 'regression', 'dataset_path': path, 'config': web.with_delimiter(web.AnalysisConfig(), ',')}
    first = web.refresh_input_inspection(job)
    assert web.refresh_input_inspection(job) is first and len(calls) == 1
    job['mode'] = None  # the provisional profile equals the regression default: reused
    assert web.refresh_input_inspection(job) is first and len(calls) == 1
    job['mode'] = 'regression'
    job['config'] = web.with_delimiter(job['config'], ';')
    second = web.refresh_input_inspection(job)
    assert len(calls) == 2 and second['profile']['fingerprint'] != first['profile']['fingerprint']


def test_an_inspection_failure_is_recorded_not_raised(tmp_path):
    from datatrust import web
    path = _write(tmp_path, pd.DataFrame({'x': ['a', 'b']}))
    job = {'mode': None, 'dataset_path': path, 'config': web.with_delimiter(web.AnalysisConfig(), ',')}
    path.unlink()
    out = web.refresh_input_inspection(job)
    assert out['version'] == 'input_inspection_v1' and 'error' in out and 'columns' not in out


def test_uniqueness_is_never_claimed_from_a_later_chunk_alone(tmp_path):
    # Beijing-shaped: the clock repeats within the first chunk (several stations), and the last, short chunk happens to
    # hold each time once. Columns are chosen for tracking on the first chunk only, so nothing is called unique.
    times = [f'2024-01-{d:02d}' for d in range(1, 11)]
    frame = pd.DataFrame({'when': times * 3 + times[:7], 'station': ['a'] * 10 + ['b'] * 10 + ['c'] * 10 + ['d'] * 7})
    out = inspect_table(_write(tmp_path, frame), CsvParseOptions(), InspectionBudget(chunk_rows=30))
    assert not any(s['role'] == 'identifier' for c in out['columns'] for s in c['suggestions'])
    assert not any('different value' in line for c in out['columns'] for line in c['structural'])


def test_a_unique_fractional_measurement_is_not_an_identifier(tmp_path):
    frame = pd.DataFrame({'total_amount': [i * 1.37 + 0.01 for i in range(50)], 'seq': range(50), 'record_id': [i + 0.5 for i in range(50)]})
    rules = _rules(inspect_table(_write(tmp_path, frame), CsvParseOptions()))
    assert not rules['total_amount'] & {'R-ID-1', 'R-ID-2'} and 'R-ID-2' in rules['seq'] and 'R-ID-1' in rules['record_id']


# multi-source (Stage 5) -------------------------------------------------------------------------------------------------

from datatrust.inspection import SOURCE_BUDGET, identity_key_candidates, inspect_source, name_mapping_candidates, time_structure


def test_panel_entities_come_from_the_clock_pair_test(tmp_path):
    times = pd.date_range('2024-01-01', periods=50, freq='h').strftime('%Y-%m-%dT%H:%M:%S')
    frame = pd.DataFrame({'time': list(times) * 3, 'station': ['a'] * 50 + ['b'] * 50 + ['c'] * 50,
                          'wind': (['N', 'S', 'E', 'W', 'NE'] * 30), 'pm25': [float(i % 37) for i in range(150)]})
    path = _write(tmp_path, frame)
    ts = time_structure(path, inspect_source(path))
    clock = ts['clocks'][0]
    assert (clock['column'], clock['kind'], clock['naive'], clock['repeats']) == ('time', 'local_datetime', True, 100)
    assert clock['spacing']['label'] == '1 hour' and clock['spacing']['first'] == '2024-01-01T00:00:00'
    assert [e['column'] for e in ts['entities']][0] == 'station'  # one series per value: as many stations as each time repeats
    assert {'column': 'pm25', 'type': 'quantitative'} in ts['measurements'] and ts['statement'] is None


def test_a_single_series_head_says_entities_are_not_established(tmp_path):
    frame = pd.DataFrame({'day': pd.date_range('2024-01-01', periods=40, freq='D').strftime('%Y-%m-%d'), 'site': ['x'] * 40, 'v': range(40)})
    path = _write(tmp_path, frame)
    ts = time_structure(path, inspect_source(path))
    assert ts['clocks'][0]['kind'] == 'civil_date' and ts['clocks'][0]['spacing']['label'] == '1 day' and ts['entities'] == []
    assert ts['statement'].startswith('Within the inspected rows each time appears once')


def test_epoch_and_offset_clocks(tmp_path):
    frame = pd.DataFrame({'ts': [1_700_000_000 + 60 * i for i in range(30)], 'at': [f'2024-01-01T00:{i:02d}:00Z' for i in range(30)], 'v': range(30)})
    path = _write(tmp_path, frame)
    clocks = {c['column']: c for c in time_structure(path, inspect_source(path))['clocks']}
    assert (clocks['ts']['encoding'], clocks['ts']['epoch_unit'], clocks['ts']['spacing']['label']) == ('epoch', 's', '1 minute')
    assert clocks['at']['kind'] == 'instant' and not clocks['at']['naive']


def test_source_budget_reads_the_head_only(tmp_path):
    frame = pd.DataFrame({'id': range(25_000), 'v': [i % 7 for i in range(25_000)]})
    out = inspect_source(_write(tmp_path, frame))
    assert out['coverage']['rows_inspected'] == SOURCE_BUDGET.full_rows and out['coverage']['stopped'] == 'rows'


def test_parquet_reads_metadata_and_the_first_batch(tmp_path):
    path = tmp_path / 't.parquet'
    pd.DataFrame({'id': range(30_000), 'when': pd.date_range('2024-01-01', periods=30_000, freq='min')}).to_parquet(path, row_group_size=5_000)
    out = inspect_source(path, 'parquet')
    assert out['coverage']['rows_inspected'] == 20_000 and not out['coverage']['complete']
    assert out['coverage']['statement'] == 'Inspected the first 20,000 of 30,000 rows (the inspection limit); suggestions describe those rows.'
    small = tmp_path / 's.parquet'
    pd.DataFrame({'id': range(10), 'x': [0.5] * 10}).to_parquet(small)
    assert inspect_source(small, 'parquet')['coverage']['complete']


def test_identity_keys_and_name_mappings_across_sources(tmp_path):
    a = _write(tmp_path, pd.DataFrame({'customer_id': range(30), 'Age': range(30), 'city': ['x', 'y', 'z'] * 10}), 'a.csv')
    b = _write(tmp_path, pd.DataFrame({'customer_id': range(30, 60), 'age': range(30), 'City': ['x', 'y', 'z'] * 10}), 'b.csv')
    keys = identity_key_candidates({'source1': inspect_source(a), 'source2': inspect_source(b)})
    assert [k['columns'] for k in keys] == [['customer_id']] and keys[0]['rule'] == 'R-KEY-1'
    maps = name_mapping_candidates({'source1': ['customer_id', 'Age', 'city'], 'source2': ['customer_id', 'age', 'City']})
    assert [(m['column'], m['aligned']) for m in maps] == [('age', 'Age'), ('City', 'city')]
