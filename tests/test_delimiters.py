"""CSV separators: comma stays the default and unchanged; semicolon, tab and vertical-bar files read to the same evidence."""
import csv
import io
import json
import re
import time
from pathlib import Path

import pytest
from click.testing import CliRunner

from datatrust import DataTrust, DatasetSpec, TaskSpec
from datatrust.cli import main
from datatrust.contracts import AnalysisConfig, CsvParseOptions, json_safe
from datatrust.ingestion import detect_delimiter, parsing_options_dict
from datatrust.web import create_app

ROOT = Path(__file__).resolve().parents[1]
GERMAN = ROOT / 'validation/data/prepared/german_credit.csv'
BIKE = ROOT / 'validation/regression/data/prepared/bike_hour.csv'
API = '/api/datatrust/v1'


def rewrite(source, destination, delimiter):
    """The same tokens, separated differently."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    with source.open(newline='', encoding='utf-8') as fin, destination.open('w', newline='', encoding='utf-8') as fout:
        csv.writer(fout, delimiter=delimiter, lineterminator='\n').writerows(csv.reader(fin))
    return destination


def evidence(result):
    """Everything an analysis concludes; source digests and parsing fingerprints legitimately name the file read."""
    value = result.to_dict()
    text = json.dumps({k: value[k] for k in ('profile', 'checks', 'evidence', 'findings', 'narrative', 'scoring', 'coverage')}, sort_keys=True)
    return re.sub(r'"[0-9a-f]{64}"', '"#"', text)


def test_contract_accepts_one_character_and_omits_the_default():
    assert CsvParseOptions(delimiter=';').delimiter == ';'
    for bad in ('', ';;', '"', '\n'):
        with pytest.raises(ValueError):
            CsvParseOptions(delimiter=bad)
    assert 'delimiter' not in parsing_options_dict(CsvParseOptions())
    assert parsing_options_dict(CsvParseOptions(delimiter='\t'))['delimiter'] == '\t'
    assert 'delimiter' not in json.dumps(json_safe({'parsing': {**CsvParseOptions().__dict__}}))
    assert AnalysisConfig.from_dict({'parsing': {'delimiter': '|'}}).parsing.delimiter == '|'


@pytest.mark.parametrize('text,expected', [
    ('"age";"job";"y"\n58;"management";"no"\n44;"technician";"no"\n', ';'),
    ('a\tb\tc\n1\t2\t3\n4\t5\t6\n', '\t'),
    ('a|b\n1|2\n', '|'),
    ('a,b\n"x;y",2\n"p;q",3\n', ','),   # semicolons inside quoted comma cells
    ('only\n1\n2\n', ','),              # a genuine single column
    ('a;b|c\n1;2|3\n', None),           # two candidates fit: ambiguous, so it must be chosen
    ('a;b\n1;2\n3;4;5\n', ','),         # inconsistent width
])
def test_detection_applies_only_a_clear_separator(tmp_path, text, expected):
    path = tmp_path / 'data.csv'; path.write_text(text)
    assert detect_delimiter(path) == expected


@pytest.mark.parametrize('kind,source,target', [('classification', GERMAN, 'credit_risk'), ('regression', BIKE, 'cnt'), ('dataset_profile', GERMAN, None)])
@pytest.mark.parametrize('delimiter', [';', '\t'])
def test_other_separators_read_to_the_same_evidence(tmp_path, kind, source, target, delimiter):
    task = TaskSpec(kind, target=target) if target else TaskSpec(kind)
    comma = DataTrust.from_spec(DatasetSpec(str(source)), task).analyze_result()
    copy = rewrite(source, tmp_path / 'other' / source.name, delimiter)
    other = DataTrust.from_spec(DatasetSpec(str(copy)), task, AnalysisConfig(parsing=CsvParseOptions(delimiter=delimiter))).analyze_result()
    assert evidence(other) == evidence(comma)
    assert other.to_dict()['parsing']['options']['delimiter'] == delimiter and 'delimiter' not in comma.to_dict()['parsing']['options']
    html = Path(other.generate_artifacts(tmp_path / 'r.html').html_path).read_text()
    assert 'CSV separator:' in html and 'CSV separator:' not in Path(comma.generate_artifacts(tmp_path / 'c.html').html_path).read_text()


def app_client(tmp_path, roots=()):
    app = create_app(tmp_path / 'ui', data_roots=roots or (tmp_path,)); app.testing = True
    client = app.test_client(); token = client.get(f'{API}/session').json['data']['csrf_token']
    return app, client, {'X-CSRF-Token': token}


def test_app_detects_reads_and_can_change_the_separator(tmp_path):
    app, client, h = app_client(tmp_path)
    semi = rewrite(GERMAN, tmp_path / 'semi.csv', ';')
    job = client.post(f'{API}/core/jobs', data={'mode': 'classification', 'dataset': (semi.open('rb'), 'semi.csv')}, headers=h, content_type='multipart/form-data').json['data']['job']
    assert job['delimiter_detected'] and job['config']['parsing']['delimiter'] == ';' and job['inspection']['column_count'] == 21
    info = client.get(f'{API}/core/job/target-preview?target=credit_risk').json['data']['target_info']
    assert info['class_count'] == 2
    configured = client.post(f'{API}/core/job/configure', json={'target': 'credit_risk', 'dataset_name': 'Semi'}, headers=h)
    assert configured.status_code == 200
    assert client.post(f'{API}/core/job/generate', json={}, headers=h).status_code == 200
    assert '"delimiter": ";"' in client.get(f'{API}/core/job/analysis').get_data(as_text=True)
    assert 'CSV separator: semicolon.' in client.get(f'{API}/core/job/report').get_data(as_text=True)
    changed = client.post(f'{API}/core/job/delimiter', json={'delimiter': ','}, headers=h).json['data']['job']
    assert changed['inspection']['column_count'] == 1 and changed['target'] is None and not changed['delimiter_detected'] and changed['artifacts'] == []
    assert client.post(f'{API}/core/job/delimiter', json={'delimiter': ';;'}, headers=h).status_code == 422
    app.extensions['confidenceguard_store'].cleanup(); app.extensions['datatrust_job_store'].cleanup()


def test_m3_reads_the_detected_separator(tmp_path):
    app, client, h = app_client(tmp_path)
    tab = rewrite(GERMAN, tmp_path / 'tab.csv', '\t')
    job = client.post(f'{API}/core/jobs', data={'mode': 'clustering', 'dataset': (tab.open('rb'), 'tab.csv')}, headers=h, content_type='multipart/form-data').json['data']['job']
    roles = {f'role_{c}': 'feature' for c in job['inspection']['columns']}
    assert client.post(f'{API}/core/job/configure', json={**roles, 'scale_sensitive': 'true'}, headers=h).status_code == 200
    assert client.post(f'{API}/core/job/generate', json={'representation_ack': 'confirmed'}, headers=h).status_code == 200
    assert '"delimiter": "\\t"' in client.get(f'{API}/core/job/analysis').get_data(as_text=True)
    app.extensions['confidenceguard_store'].cleanup(); app.extensions['datatrust_job_store'].cleanup()


def test_classic_upload_keeps_reading_commas(tmp_path):
    app, client, _ = app_client(tmp_path)
    client.get('/')
    with client.session_transaction() as state:
        token = state['form_token']
    semi = rewrite(GERMAN, tmp_path / 'semi.csv', ';')
    client.post('/upload', data={'form_token': token, 'mode': 'classification', 'dataset': (semi.open('rb'), 'semi.csv')}, content_type='multipart/form-data')
    job = next(iter(app.extensions['datatrust_job_store'].jobs.values()))
    assert job['config'].parsing.delimiter == ',' and job['inspection']['column_count'] == 1
    app.extensions['confidenceguard_store'].cleanup(); app.extensions['datatrust_job_store'].cleanup()


def m4_run(tmp_path, delimiter):
    from tests.m4.test_app_api import FIELDS, SPLIT
    app, client, h = app_client(tmp_path / delimiter.replace('\t', 'tab'))
    client.post(f'{API}/m4/start', json={'mode': 'splits'}, headers=h)
    for text in SPLIT:
        body = text.replace(',', delimiter)
        client.post(f'{API}/m4/sources', data={'delimiter': 'auto', 'dataset': (io.BytesIO(body.encode()), 'part.csv')}, headers=h, content_type='multipart/form-data')
    view = client.post(f'{API}/m4/configure', json=FIELDS, headers=h).json['data']['job']
    assert [s['delimiter'] for s in view['sources']] == [delimiter, delimiter]
    client.post(f'{API}/m4/run', json={'fingerprint': view['fingerprint']}, headers=h)
    store = app.extensions['datatrust_m4_store']; job = next(iter(store.jobs.values()))
    for _ in range(600):
        if job['state'] != 'running': break
        time.sleep(.05)
    value = json.loads(client.get(f'{API}/m4/analysis').get_data(as_text=True))
    store.cleanup(); app.extensions['confidenceguard_store'].cleanup()
    return value


def test_m4_semicolon_sources_match_comma_sources(tmp_path):
    comma, semi = m4_run(tmp_path, ','), m4_run(tmp_path, ';')
    strip = lambda v: re.sub(r'"[0-9a-f]{64}"|"source-[0-9a-f]{32}\.csv"|"delimiter": ";",?', '', json.dumps({k: v[k] for k in ('findings', 'evidence')}, sort_keys=True))
    assert strip(comma) == strip(semi)
    assert '"delimiter": ";"' in json.dumps(semi) and '"delimiter"' not in json.dumps(comma)


def test_m5_reads_a_semicolon_source(tmp_path):
    from tests.m5.test_app_api import FIELDS
    root = tmp_path / 'data'; root.mkdir()
    (root / 'series.csv').write_text('time;x\n' + ''.join(f'{i};{0 if i < 120 else i}\n' for i in range(240)))
    app, client, h = app_client(tmp_path, roots=(root,))
    client.post(f'{API}/temporal/start', json={}, headers=h)
    added = client.post(f'{API}/temporal/sources', json={'root_id': 'root_0', 'relative_path': 'series.csv', 'format': 'csv'}, headers=h).json['data']['job']
    assert added['sources'][0]['delimiter'] == ';' and added['sources'][0]['headers'] == ['time', 'x']
    view = client.post(f'{API}/temporal/configure', json=FIELDS, headers=h).json['data']['job']
    client.post(f'{API}/temporal/run', json={'fingerprint': view['fingerprint']}, headers=h)
    store = app.extensions['datatrust_m5_store']; list(store.jobs.values())[-1]['thread'].join(120)
    assert client.get(f'{API}/temporal/job').json['data']['job']['state'] == 'completed'
    assert '"delimiter": ";"' in client.get(f'{API}/temporal/analysis').get_data(as_text=True)
    store.cleanup(); app.extensions['confidenceguard_store'].cleanup()


def test_cli_reads_a_named_separator(tmp_path):
    semi = rewrite(GERMAN, tmp_path / 'semi.csv', ';')
    out = CliRunner().invoke(main, ['audit', str(semi), '--target', 'credit_risk', '--delimiter', 'semicolon', '--out', str(tmp_path / 'r.html'), '--json-out', str(tmp_path / 'a.json')])
    assert out.exit_code == 0, out.output
    assert json.loads((tmp_path / 'a.json').read_text())['parsing']['options']['delimiter'] == ';'
