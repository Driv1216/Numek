import hashlib
import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from datatrust import (AnalysisConfig, AnalysisError, CsvParseOptions, DataTrust,
                      DatasetSpec, ExecutionLimits, FidelityInspectionLimits, TaskSpec)
from datatrust.ingestion import inspect_unlabeled_dataset
from datatrust.renderer import render_html_report, render_analysis_result


def profile(tmp_path, text, config=None):
    path = tmp_path / 'source.csv'
    path.write_text(text, encoding='utf-8')
    return DataTrust.from_spec(DatasetSpec(path), TaskSpec('dataset_profile'), config).analyze_result()


def column(result, name):
    return next(c for c in result.profile['columns'] if c['name'] == name)


def test_frozen_classification_results_html_and_historical_checksums(monkeypatch):
    baseline = json.loads(Path('tests/fixtures/m1_classification_baseline.json').read_text())
    monkeypatch.setattr('datatrust.renderer.datetime', SimpleNamespace(now=lambda: datetime(2026, 10, 9, 12)))
    for name, case in baseline['cases'].items():
        result = DataTrust(case['path'], case['target']).analyze()
        assert result == case['result'], name
        assert hashlib.sha256(render_html_report(**result).encode()).hexdigest() == case['html_sha256'], name
    for path, digest in baseline['artifacts'].items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest, path


def test_known_missingness_duplicates_variation_and_no_scores(tmp_path):
    r = profile(tmp_path, 'label,target,empty,constant\na,1,,same\na,1,,same\nb,2,,same\nc,,,same\n')
    p = r.profile
    assert (p['row_count'], p['column_count'], p['missing_cells']) == (4, 4, 5)
    assert (p['rows_with_1_missing_feature'], p['rows_with_2_missing_features'], p['rows_with_3_plus_missing_features']) == (3, 1, 0)
    assert (p['duplicate_rows'], p['duplicate_group_count'], p['rows_in_duplicate_groups'], p['largest_duplicate_group_size']) == (1, 1, 2, 2)
    assert p['duplicate_row_examples'] == [1, 2]
    assert all(c['role'] == 'feature' for c in p['columns'])
    assert r.scoring['status'] == 'not_defined' and r.scoring['values'] is None
    assert not {'scores', 'guardrails', 'risk_level', 'target'} & p.keys()
    assert {f['code'] for f in r.findings} >= {'fully_missing_columns', 'constant_fields', 'duplicate_records'}
    constants = next(f for f in r.findings if f['code'] == 'constant_fields')
    assert 'empty' not in constants['evidence']
    assert r.execution['backend'] == 'pandas_in_memory'
    assert r.execution['limits']['max_rows'] == 1000000


def test_finite_numeric_population_differs_from_legacy(tmp_path):
    text = 'value,label\n' + '\n'.join(f'{v},{i%2}' for i, v in enumerate(list(range(1,20)) + [100, 'inf', '-inf', ''])) + '\n'
    r = profile(tmp_path, text)
    c = column(r, 'value')
    assert c['finite_count'] == 20 and c['outlier_count'] == 1 and c['outlier_rate'] == 5
    assert c['numeric_summary']['non_finite_count'] == 2
    assert c['numeric_summary']['negative_count'] == 0
    legacy = DataTrust(tmp_path / 'source.csv', 'label').analyze()['profile']['columns'][0]
    assert legacy['outlier_count'] == 3 and legacy['outlier_rate'] == 13.04
    check = next(c for c in r.checks if c.check_id == 'numeric_outliers' and c.scope == 'value')
    assert check.exclusions == [{'missing_values': 1, 'non_finite_values': 2}]


@pytest.mark.parametrize('text,reason', [('v\n1\n2\n3\n','insufficient_finite_observations'), ('v\n1\n1\n1\n2\n1\n','zero_iqr')])
def test_ineligible_iqr_is_unavailable_not_zero(tmp_path, text, reason):
    r = profile(tmp_path, text)
    assert column(r, 'v')['outlier_count'] is None
    assert next(c for c in r.checks if c.check_id == 'numeric_outliers').reason == reason


def test_fidelity_warnings_scope_privacy_and_string_override(tmp_path):
    text = 'account,token\n00123,NA\n00042,ok\n'
    r = profile(tmp_path, text)
    assert {w['code'] for w in r.parsing_warnings} == {'leading_zero_numeric_conversion', 'nonempty_token_as_missing'}
    warning = r.parsing_warnings[0]
    assert warning['observed_count'] == 2
    assert warning['inspected_population']['comparable_cells'] == 4
    assert not warning['inspected_population']['counts_are_dataset_incidence']
    assert '00123' not in json.dumps(r.parsing_warnings)
    assert len(warning['row_refs']) == 2
    config = AnalysisConfig(parsing=CsvParseOptions(missing_policy='empty_only', column_types={'account': 'string'}))
    r = profile(tmp_path, text, config)
    assert r.parsing_warnings == [] and column(r,'account')['dtype'].startswith('str')
    assert column(r,'token')['missing_count'] == 0
    assert (tmp_path/'source.csv').read_text() == text


@pytest.mark.parametrize('policy,tokens,missing', [('pandas_default', (), 3), ('empty_only', (), 1), ('custom', ('NULL',), 1), ('custom', ('NULL',''), 2)])
def test_missing_policy_has_exact_literal_semantics(tmp_path, policy, tokens, missing):
    r = profile(tmp_path, 'v,other\nNA,1\nNULL,2\n,3\n ,4\n', AnalysisConfig(parsing=CsvParseOptions(missing_policy=policy, na_values=tokens)))
    assert column(r,'v')['missing_count'] == missing


def test_numeric_override_rejects_invalid_and_unknown_columns(tmp_path):
    for overrides, match in [({'v':'numeric'}, 'invalid numeric'), ({'unknown':'string'}, 'Unknown column')]:
        with pytest.raises(ValueError, match=match):
            profile(tmp_path, 'v\n1\noops\n', AnalysisConfig(parsing=CsvParseOptions(column_types=overrides)))


def test_headers_multiline_bom_and_bounded_prefix(tmp_path):
    r = profile(tmp_path, '\ufeffid,id,\n001,NA,"line one\nline two"\n002,ok,text\n')
    assert [c['name'] for c in r.profile['columns']] == ['id','id.1','Unnamed: 2']
    assert {'duplicate_header','empty_header','leading_zero_numeric_conversion','nonempty_token_as_missing'} <= {w['code'] for w in r.parsing_warnings}
    assert r.parsing['fidelity_inspection']['comparable_cells'] == 6
    r = profile(tmp_path, 'v,other\n001,a\n002,b\n003,c\n', AnalysisConfig(fidelity_inspection=FidelityInspectionLimits(max_records=1)))
    assert r.parsing['fidelity_inspection']['records_inspected'] == 1
    assert r.parsing['fidelity_inspection']['stopping_reason'] == 'record_limit'
    assert next(w for w in r.parsing_warnings if w['code']=='leading_zero_numeric_conversion')['observed_count'] == 1
    r = profile(tmp_path, 'v,other\n001,a\n002,"long\nvalue"\n', AnalysisConfig(fidelity_inspection=FidelityInspectionLimits(max_bytes=20)))
    assert r.parsing['fidelity_inspection']['records_inspected'] == 1
    assert not r.parsing['fidelity_inspection']['complete']


def test_cell_limits_oversize_alignment_and_encoding(tmp_path):
    r = profile(tmp_path, 'a,b\n001,002\n003,004\n', AnalysisConfig(fidelity_inspection=FidelityInspectionLimits(max_cells=1)))
    assert r.parsing['fidelity_inspection']['comparable_cells'] == 1
    assert r.parsing['fidelity_inspection']['stopping_reason'] == 'cell_limit'
    with pytest.raises(AnalysisError, match='has 1 field; the header has 2'):  # WS1: a short record is refused, never padded
        profile(tmp_path, 'a,b\n001\n002,x\n')
    r = profile(tmp_path, 'a,b\n001,"'+'z'*300+'"\n', AnalysisConfig(fidelity_inspection=FidelityInspectionLimits(max_bytes=20)))
    assert r.parsing['fidelity_inspection']['comparable_cells'] == 0
    for encoding in ('latin-1','utf-16'):
        path=tmp_path/'encoded.csv';path.write_bytes('id,text\n001,café\n002,ok\n'.encode(encoding))
        r=DataTrust.from_spec(DatasetSpec(path),TaskSpec('dataset_profile'),AnalysisConfig(parsing=CsvParseOptions(encoding=encoding))).analyze_result()
        assert r.parsing['options']['encoding']==encoding and r.parsing['fidelity_inspection']['alignment_confirmed']


def test_preview_is_bounded_provisional_and_has_fidelity_warnings(tmp_path):
    path=tmp_path/'preview.csv';path.write_text('id\n'+'\n'.join(f'{i:04d}' for i in range(100))+'\n')
    preview=inspect_unlabeled_dataset(DatasetSpec(path))
    assert preview['row_count'] is None and preview['preview_row_count']==10
    assert preview['parsing']['provisional_types']
    assert preview['parsing']['fidelity_inspection']['comparable_cells']==10
    assert any(w['code']=='leading_zero_numeric_conversion' for w in preview['parsing_warnings'])


@pytest.mark.parametrize('limits,stage', [(ExecutionLimits(max_source_bytes=1),'source'), (ExecutionLimits(max_columns=1),'header'), (ExecutionLimits(max_rows=1),'CSV loading'), (ExecutionLimits(max_frame_bytes=1),'materialization'), (ExecutionLimits(max_seconds=1e-12),'source inspection')])
def test_operational_safeguards_reject_without_complete_truncated_result(tmp_path, limits, stage):
    with pytest.raises(AnalysisError) as exc:
        profile(tmp_path,'a,b\n1,2\n3,4\n',AnalysisConfig(limits=limits))
    assert exc.value.code=='resource_limit' and exc.value.stage==stage


def test_partial_failure_has_no_false_uniqueness_conclusion_and_memory_aborts(tmp_path, monkeypatch):
    def fail(_): raise RuntimeError('optional failure')
    monkeypatch.setattr('datatrust.core.exact_duplicate_evidence',fail)
    r=profile(tmp_path,'v\n1\n2\n3\n4\n')
    assert r.execution['status']=='partial' and r.profile['duplicate_rows'] is None
    assert 'unavailable' in r.narrative['duplicate_interpretation']
    assert 'Analysis incomplete' in render_analysis_result(r)
    def oom(_): raise MemoryError()
    monkeypatch.setattr('datatrust.core.exact_duplicate_evidence',oom)
    with pytest.raises(MemoryError): profile(tmp_path,'v\n1\n2\n')


def test_source_change_aborts(tmp_path, monkeypatch):
    from datatrust.core import profile_unlabeled_frame
    def changed(data,path):
        result=profile_unlabeled_frame(data,path);Path(path).write_text('v\n9\n10\n');return result
    monkeypatch.setattr('datatrust.core.profile_unlabeled_frame',changed)
    with pytest.raises(AnalysisError,match='Source changed'):profile(tmp_path,'v\n1\n2\n')


def test_strict_json_reference_resolution_and_classification_protection(tmp_path):
    r=profile(tmp_path,'v,label\ninf,0\n-inf,1\n1,0\n2,1\n')
    data=json.loads(r.json_text(),parse_constant=lambda s: pytest.fail(s))
    assert str(tmp_path) not in r.json_text()
    ids={e['id'] for e in data['evidence']}
    for check in data['checks']:
        assert set(check['evidence_refs'])<=ids
    for e in data['evidence']:
        for pointer in e['measurement_refs']:
            node=data
            for key in pointer.split('/')[1:]:node=node[int(key)] if isinstance(node,list) else node[key]
    for finding in data['findings']:assert set(finding['evidence_refs'])<=ids
    legacy=DataTrust(tmp_path/'source.csv','label').analyze()
    typed=DataTrust.from_spec(DatasetSpec(tmp_path/'source.csv'),TaskSpec('classification','label')).analyze_result()
    assert typed.to_legacy_dict()==legacy and all(v is None for v in typed.execution['limits'].values())
    with pytest.raises(ValueError,match='Non-default classification parsing'):
        DataTrust.from_spec(DatasetSpec(tmp_path/'source.csv'),TaskSpec('classification','label'),AnalysisConfig(parsing=CsvParseOptions(missing_policy='empty_only'))).analyze_result()


@pytest.mark.parametrize('value', [{'backend':'worker'}, {'parsing':{'delimiter':';;'}}, {'limits':{'max_rows':0}}, {'fidelity_inspection':{'max_bytes':float('inf')}}, {'parsing':{'column_types':{'a':[]}}}])
def test_invalid_configuration_is_rejected(value):
    with pytest.raises(ValueError): AnalysisConfig.from_dict(value)


def test_unlabeled_validation_namespace():
    from validation.unlabeled.verify import verify_all
    summary = verify_all()
    assert summary['validation_type']=='internal' and len(summary['cases'])==4
    assert all(case['passed'] for case in summary['cases'])


def test_booleans_are_categorical_and_clean_state_retains_parsing_review(tmp_path):
    r=profile(tmp_path,'identifier,flag\n001,True\n002,False\n003,True\n004,False\n')
    assert not column(r,'flag')['is_numeric'] and r.execution['status']=='completed'
    assert r.findings==[] and r.parsing_warnings
    html=render_analysis_result(r)
    assert 'No data-profile findings' in html and 'leading_zero_numeric_conversion' in html


def test_cooperative_deadline_after_required_stages_produces_honest_partial_result(tmp_path,monkeypatch):
    elapsed=[0]
    monkeypatch.setattr('datatrust.core.time.monotonic',lambda:elapsed[0])
    from datatrust.core import profile_unlabeled_frame
    def slow_basic(data,path):
        value=profile_unlabeled_frame(data,path);elapsed[0]=2;return value
    monkeypatch.setattr('datatrust.core.profile_unlabeled_frame',slow_basic)
    r=profile(tmp_path,'v\n1\n2\n3\n4\n',AnalysisConfig(limits=ExecutionLimits(max_seconds=1)))
    assert r.execution['status']=='partial' and r.profile['duplicate_rows'] is None
    assert any(c.execution=='skipped' and 'individual operations are not interruptible' in c.reason for c in r.checks)


def test_classification_fidelity_failure_never_alters_legacy_output(tmp_path,monkeypatch):
    path=tmp_path/'source.csv';path.write_text('feature,label\n1,0\n2,1\n3,0\n4,1\n')
    expected=DataTrust(path,'label').analyze()
    from datatrust.ingestion import inspect_source_tokens
    def unavailable(path,encoding,limits):
        sample=inspect_source_tokens(path,encoding,limits)
        sample.update(headers=None,records=[],records_inspected=0,complete=False,stopping_reason='inspection_unavailable')
        return sample
    monkeypatch.setattr('datatrust.ingestion.inspect_source_tokens',unavailable)
    audit=DataTrust(path,'label');assert audit.analyze()==expected
    assert any(c.check_id=='parsing_fidelity' and c.applicability=='blocked' for c in audit._last_result.checks)


def test_source_removal_is_a_snapshot_failure(tmp_path,monkeypatch):
    from datatrust.core import profile_unlabeled_frame
    def removed(data,path):
        result=profile_unlabeled_frame(data,path);Path(path).unlink();return result
    monkeypatch.setattr('datatrust.core.profile_unlabeled_frame',removed)
    with pytest.raises(AnalysisError) as error:profile(tmp_path,'v\n1\n2\n')
    assert error.value.code=='source_changed'
