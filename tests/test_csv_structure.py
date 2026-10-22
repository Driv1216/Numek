"""Whole-source CSV structure validation and explicit separator choice: rows are never padded, dropped or shifted
into an index; ambiguous separators are chosen, not guessed; valid files read exactly as before."""
import csv
import io
import json
import random
import time
from pathlib import Path

import pandas as pd
import pytest
from click.testing import CliRunner

from datatrust import DataTrust, DatasetSpec, TaskSpec
from datatrust.cli import main
from datatrust.contracts import AnalysisConfig, AnalysisError, CsvParseOptions, ExecutionLimits
from datatrust import ingestion
from datatrust.ingestion import STRUCTURE_VALIDATION, resolve_delimiter, validate_csv_structure
from datatrust.web import create_app

ROOT = Path(__file__).resolve().parents[1]
GERMAN = ROOT / 'validation/data/prepared/german_credit.csv'
API = '/api/datatrust/v1'
ROWS = ''.join(f'{i},{i * 3 % 17},{"yes" if i % 3 else "no"}\n' for i in range(60))
TASKS = [TaskSpec('classification', target='y'), TaskSpec('dataset_profile'), TaskSpec('regression', target='b')]


def write(tmp_path, text, name='data.csv'):
    path = tmp_path / name
    path.write_bytes(text.encode('utf-8'))
    return path


def analyse(path, task, **parsing):
    return DataTrust.from_spec(DatasetSpec(str(path)), task, AnalysisConfig(parsing=CsvParseOptions(**parsing)) if parsing else None).analyze_result()


@pytest.mark.parametrize('task', TASKS, ids=lambda t: t.kind)
@pytest.mark.parametrize('text,expected', [
    ('a,b,y\n' + ROWS + '1,2\n', r'record 61 \(ending on line 62\) has 2 fields; the header has 3'),  # padded before
    ('a,b,y\n' + ROWS + '1,2,yes,9\n', r'record 61 \(ending on line 62\) has 4 fields; the header has 3'),
    ('a,b,y\n' + ''.join(f'{i},{i},{i % 5},{"yes" if i % 3 else "no"}\n' for i in range(60)), 'would silently become a row index'),  # shifted before
    ('a,b,y\n1,2,yes\n3,4,no,5\n6,7,yes\n', r'record 2 \(ending on line 3\) has 4 fields'),
    ('a,b,y\n0,1,2,yes\n3,4,no\n', r'record 1 \(ending on line 2\) has 4 fields'),  # one wide record then a narrow one: not an index
])
def test_malformed_structure_fails_before_any_result(tmp_path, task, text, expected):
    with pytest.raises(AnalysisError, match=expected) as caught:
        analyse(write(tmp_path, text), task)
    assert caught.value.code == 'csv_structure' and 'Nothing was analysed' in str(caught.value)


@pytest.mark.parametrize('text,delimiter,rows', [
    ('a,b\n"1,5",2\n"he said ""hi""",3\n', ',', 2),           # quoted separators and doubled quotes
    ('a,b\n1,"two\nlines"\n3,4\n', ',', 2),                    # embedded newline
    ('﻿a,b\n1,2\n', ',', 1),                              # byte-order mark
    ('a,b\r\n1,2\r\n3,4\r\n', ',', 2),                         # CRLF
    ('only\n1\n\n2\n  \n3\n', ',', 3),                         # a genuine single column; blank lines skipped
    ('a,b\n1,2\n   \n\t\n3,4\n', ',', 2),                      # whitespace-only lines are blank, as pandas reads them
    ('a\tb\n1\t2\n\t\n3\t4\n', '\t', 3),                       # a lone tab in a tab file is a row of empty cells
    ('a;b\n1;2\n3;4\n', ';', 2), ('a|b\n1|2\n', '|', 1),
    ('a,b,\n1,2,\n', ',', 1),                                  # trailing separators on every record
    ('a,b\n1,2', ',', 1),                                      # no final newline
])
def test_valid_files_validate_and_read_as_before(tmp_path, text, delimiter, rows):
    path = write(tmp_path, text)
    assert validate_csv_structure(path, CsvParseOptions(delimiter=delimiter)) == rows
    assert len(pd.read_csv(path, sep=delimiter)) == rows
    result = analyse(path, TaskSpec('dataset_profile'), delimiter=delimiter).to_dict()
    assert result['profile']['row_count'] == rows and result['parsing']['structure_validation'] == STRUCTURE_VALIDATION


def generated(rng, terminator):
    atoms = ['1', 'x', '', '"q"', '"a,b"', f'"l{terminator}m"', ' ', '\t', '"he ""x"""', 'é', 'x"y', '" "']
    sep = rng.choice([',', ';', '\t', '|'])
    width = rng.randint(1, 4)
    lines = [sep.join(f'h{j}' for j in range(width))]
    for _ in range(rng.randint(0, 6)):
        if rng.random() < 0.08:
            lines.append(rng.choice(['', '  ', '\t', ' \t ']))
        else:
            w = width if rng.random() < 0.85 else max(0, width + rng.choice([-1, 1]))
            lines.append(sep.join(rng.choice(atoms) for _ in range(w)))
    return sep, terminator.join(lines) + rng.choice(['', terminator])


@pytest.mark.parametrize('terminator', ['\n', '\r\n'])
def test_validation_agrees_with_pandas_on_generated_files(tmp_path, terminator):
    """An independent reading: whenever validation accepts, pandas reads the same records with no index shift;
    whenever pandas would pad short records or infer an index, validation refuses."""
    rng = random.Random(20261020)
    path = tmp_path / 'g.csv'
    seen = {'accepted': 0, 'padding_or_index_refused': 0}
    for _ in range(1500):
        sep, text = generated(rng, terminator)
        path.write_bytes(text.encode())
        try:
            count = validate_csv_structure(path, CsvParseOptions(delimiter=sep))
        except ValueError:
            count = None
        try:
            frame = pd.read_csv(path, sep=sep, dtype=str, keep_default_na=False)
        except (pd.errors.ParserError, pd.errors.EmptyDataError):
            frame = None
        if count is not None:
            assert frame is not None and len(frame) == count and frame.index.equals(pd.RangeIndex(count)), repr(text)
            seen['accepted'] += 1
        elif frame is not None:
            seen['padding_or_index_refused'] += 1
    assert seen['accepted'] > 500 and seen['padding_or_index_refused'] > 100


def test_readings_that_disagree_never_complete(tmp_path):
    """Lone carriage-return line endings with quoted line breaks are tokenized differently by pandas; the
    analysis refuses rather than publish records that may not be the file's."""
    text = 'h0;h1;h2;h3\r\t;"he ""x""";" ";1\r"l\rm";"he ""x""";" ";"he ""x"""'
    with pytest.raises(AnalysisError, match='read inconsistently') as caught:
        analyse(write(tmp_path, text), TaskSpec('dataset_profile'), delimiter=';')
    assert caught.value.code == 'csv_structure'


def test_validation_respects_row_limits_deadlines_and_field_size(tmp_path, monkeypatch):
    path = write(tmp_path, 'a,b\n' + ''.join(f'{i},{"x" * 200000 if i == 3 else i}\n' for i in range(50)) + '1\n')
    limit = csv.field_size_limit()
    assert validate_csv_structure(path, max_rows=10) == 11  # stops after max_rows + 1; the row limit then applies
    assert csv.field_size_limit() == limit  # a 200,000-character field is valid, as pandas reads it, and the limit is restored
    with pytest.raises(AnalysisError, match='max_rows'):
        DataTrust.from_spec(DatasetSpec(str(path)), TaskSpec('dataset_profile'), AnalysisConfig(limits=ExecutionLimits(max_rows=10))).analyze_result()
    calls = []
    monkeypatch.setattr(ingestion, 'STRUCTURE_CHECKPOINT_RECORDS', 5)

    def deadline(stage):
        calls.append(stage)
        if len(calls) > 2:
            raise AnalysisError('Cooperative elapsed-time safeguard reached.', code='resource_limit', stage=stage)
    with pytest.raises(AnalysisError, match='safeguard'):
        validate_csv_structure(path, checkpoint=deadline)
    assert calls == ['CSV structure validation'] * 3


def test_valid_results_keep_their_fingerprints(tmp_path):
    """The validation record is outside the parsing fingerprint, so seals and fingerprints of valid files hold."""
    value = analyse(GERMAN, TaskSpec('classification', target='credit_risk')).to_dict()
    parsing = value['parsing']
    assert parsing['structure_validation'] == STRUCTURE_VALIDATION
    effective = {k: parsing[k] for k in ('options', 'pandas_version', 'parser', 'delimiter', 'header', 'skip_blank_lines', 'dtypes', 'provisional_types')}
    import hashlib
    assert hashlib.sha256(json.dumps(effective, sort_keys=True).encode()).hexdigest() == parsing['fingerprint']


BANK = Path.home() / 'Downloads/bank+marketing/bank/bank-full.csv'


@pytest.mark.skipif(not BANK.is_file(), reason='Bank Marketing (bank-full.csv) is not on this machine')
def test_bank_full_statistics_and_score_are_unchanged():
    value = analyse(BANK, TaskSpec('classification', target='y'), delimiter=';').to_dict()
    values = value['scoring']['values']
    assert (values['overall'], values['risk_level'], values['evidence_score']) == (69.0, 'Elevated', 84.38)
    assert values['sub_scores'] == {'completeness': 100.0, 'uniqueness': 100.0, 'target_balance': 23.4, 'feature_usability': 98.5, 'leakage_risk': 100.0}
    assert [g['cap'] for g in values['guardrails']] == [69.0]
    assert [f['code'] for f in value['findings']] == ['target_imbalance', 'numeric_outlier_concentration']
    assert value['execution']['analyzed_rows'] == 45211 and value['execution']['analyzed_columns'] == 17


# ——— Explicit separator choice where detection is ambiguous ———

AMBIGUOUS = 'a;b|c\n1;2|3\n4;5|6\n'


def test_ambiguous_detection_names_the_candidates_and_explicit_choices_still_work(tmp_path):
    path = write(tmp_path, AMBIGUOUS)
    with pytest.raises(ValueError, match=r'more than one separator \(semicolon and vertical bar\)'):
        resolve_delimiter(path, 'auto')
    assert resolve_delimiter(path, ';') == ';' and resolve_delimiter(write(tmp_path, 'only\n1\n', 's.csv'), 'auto') == ','


def client(tmp_path):
    root = tmp_path / 'data'; root.mkdir(exist_ok=True)
    app = create_app(tmp_path / 'ui', data_roots=(root,)); app.testing = True
    c = app.test_client(); token = c.get(f'{API}/session').json['data']['csrf_token']
    return app, c, {'X-CSRF-Token': token}, root


def close(app):
    for key in ('confidenceguard_store', 'datatrust_job_store', 'datatrust_m4_store', 'datatrust_m5_store'):
        store = app.extensions.get(key)
        if store is not None:
            store.cleanup()


def test_app_refuses_an_ambiguous_upload_until_a_separator_is_chosen(tmp_path):
    app, c, h, _ = client(tmp_path)
    upload = lambda d, body=AMBIGUOUS: c.post(f'{API}/core/jobs', data={'mode': 'unlabeled', 'delimiter': d, 'dataset': (io.BytesIO(body.encode()), 'x.csv')}, headers=h, content_type='multipart/form-data')
    refused = upload('auto')
    assert refused.status_code == 422 and 'semicolon and vertical bar' in refused.json['error']['message']
    assert c.get(f'{API}/core/job').json['data']['job'] is None  # nothing was kept or analysed
    chosen = upload(';').json['data']['job']
    assert chosen['config']['parsing']['delimiter'] == ';' and chosen['inspection']['column_count'] == 2
    malformed = upload('auto', 'a,b,y\n' + ROWS + '1,2\n')
    assert malformed.status_code == 422 and 'has 2 fields; the header has 3' in malformed.json['error']['message']
    close(app)


def test_m4_and_m5_sources_refuse_ambiguous_detection(tmp_path):
    app, c, h, root = client(tmp_path)
    (root / 'amb.csv').write_text(AMBIGUOUS)
    c.post(f'{API}/m4/start', json={'mode': 'splits'}, headers=h)
    m4 = c.post(f'{API}/m4/sources', data={'delimiter': 'auto', 'dataset': (io.BytesIO(AMBIGUOUS.encode()), 'amb.csv')}, headers=h, content_type='multipart/form-data')
    assert m4.status_code == 422 and 'more than one separator' in m4.json['error']['message']
    c.post(f'{API}/temporal/start', json={}, headers=h)
    m5 = c.post(f'{API}/temporal/sources', json={'root_id': 'root_0', 'relative_path': 'amb.csv', 'format': 'csv', 'delimiter': 'auto'}, headers=h)
    assert m5.status_code == 422 and 'more than one separator' in m5.json['error']['message']
    close(app)


def test_cli_auto_refuses_an_ambiguous_file(tmp_path):
    path = write(tmp_path, AMBIGUOUS)
    out = CliRunner().invoke(main, ['audit', str(path), '--task', 'unlabeled', '--delimiter', 'auto', '--out', str(tmp_path / 'r.html')])
    assert out.exit_code != 0 and 'more than one separator' in out.output


def test_changing_the_separator_invalidates_confirmation_and_artifacts(tmp_path):
    app, c, h, _ = client(tmp_path)
    semi = GERMAN.read_text().replace(',', ';')
    c.post(f'{API}/core/jobs', data={'mode': 'classification', 'dataset': (io.BytesIO(semi.encode()), 'g.csv')}, headers=h, content_type='multipart/form-data')
    assert c.post(f'{API}/core/job/configure', json={'target': 'credit_risk', 'dataset_name': 'G'}, headers=h).status_code == 200
    assert c.post(f'{API}/core/job/generate', json={}, headers=h).status_code == 200
    assert c.get(f'{API}/core/job/download/json').status_code == 200
    changed = c.post(f'{API}/core/job/delimiter', json={'delimiter': ','}, headers=h).json['data']['job']
    assert changed['target'] is None and changed['artifacts'] == [] and changed['stage'] != 'report'
    assert c.get(f'{API}/core/job/download/json').status_code in {400, 404, 409}
    assert c.post(f'{API}/core/job/generate', json={}, headers=h).status_code >= 400  # the earlier confirmation is gone
    close(app)
