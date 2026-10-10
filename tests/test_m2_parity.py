import json, hashlib
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
        assert r.to_dict()==c['result'],name
        assert hashlib.sha256(render_analysis_result(r).encode()).hexdigest()==c['html_sha256'],name
