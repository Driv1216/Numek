import json, hashlib, copy
import pandas as pd
import pytest
from pathlib import Path
from datatrust import DataTrust, DatasetSpec, TaskSpec, AnalysisConfig, RegressionOptions
from datatrust.renderer import render_analysis_result


@pytest.fixture(autouse=True)
def frozen_string_storage():
    # Optional PyArrow must not change the measured-memory component of old snapshots.
    with pd.option_context('mode.string_storage', 'python'):
        yield

def test_frozen_current_tree_m2_results_and_reports():
    cases=json.loads(Path('tests/fixtures/m2_baseline.json').read_text())
    for name,c in cases.items():
        r=DataTrust.from_spec(DatasetSpec(**c['dataset']),TaskSpec('regression',c['target']),AnalysisConfig(regression=RegressionOptions.from_dict(c['options']))).analyze_result()
        r.generated_at='2026-10-09T00:00:00+00:00';r.execution['elapsed_seconds']=0
        # Python 3.12 removed legacy Unicode-object overhead. Deep DataFrame
        # memory is an actual runtime measurement, not an analytical method.
        # Verify it independently, preserve it in real results, and normalize
        # only that field when comparing the unchanged 3.11 golden artifact.
        expected_memory=int(pd.read_csv(c['dataset']['path']).memory_usage(index=True,deep=True).sum())
        assert r.execution['frame_bytes']==expected_memory,name
        golden=copy.deepcopy(r);golden.execution['frame_bytes']=c['result']['execution']['frame_bytes']
        assert golden.to_dict()==c['result'],name
        assert hashlib.sha256(render_analysis_result(golden).encode()).hexdigest()==c['html_sha256'],name
