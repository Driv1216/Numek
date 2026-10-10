"""Report display regressions; analytical result and legacy HTML stay untouched."""

import copy
import re

import pytest
from pypdf import PdfReader

from datatrust import AnalysisConfig, DataTrust, DatasetSpec, TaskSpec
from datatrust.renderer import render_analysis_result


def profile(tmp_path, raw, config=None):
    source = tmp_path / "source.csv"
    source.write_text(raw)
    return DataTrust.from_spec(DatasetSpec(source), TaskSpec("dataset_profile"), config).analyze_result()


def test_unavailable_summaries_empty_references_and_readable_metadata(tmp_path):
    result = profile(tmp_path, "constant,empty,numeric\nsame,,1\nsame,,2\nsame,,3\nsame,,4\n")
    before = copy.deepcopy(result.to_dict())
    html = render_analysis_result(result)
    assert "1 observed value," in html and "1 observed values" not in html
    assert "Summary unavailable: no finite observations." in html
    assert "Min None" not in html and "Q1 None" not in html
    assert "Bounded parsed-row references:" not in html
    assert "Custom missing tokens: None configured; explicit column types: None configured." in html
    assert "Exclusions: Missing values: 0; Non finite values: 0" in html
    assert "{'missing_values'" not in html and '"max_seconds": null' not in html
    assert "Cooperative elapsed-time limit" in html and "Not set" in html
    assert "Fewer than four finite observations" in html
    assert result.to_dict() == before
    # JSON remains the machine-readable evidence, including the original wording.
    assert "1 observed values" in result.json_text()


def test_single_duplicate_wording_and_nonempty_references(tmp_path):
    result = profile(tmp_path, "constant,numeric\nsame,1\nsame,1\nsame,2\nsame,3\n")
    html = render_analysis_result(result)
    assert "1 row repeats an earlier complete parsed row" in html
    assert "1 group; 2 participating rows" in html
    assert "1 repeated row beyond" in html
    assert "1 exact group; 2 participating rows; largest group: 2 rows" in html
    assert "Bounded parsed-row references:" in html
    assert "1 groups" not in html and "1 repeated rows" not in html


def test_numeric_unavailable_reason_and_escaping_literal_configuration(tmp_path):
    config = AnalysisConfig.from_dict({"parsing": {
        "missing_policy": "custom", "na_values": ["", "<NA>"],
        "column_types": {"account_code": "string"},
    }})
    result = profile(tmp_path, "account_code,value\n001,8\n002,8\n003,8\n004,8\n", config)
    html = render_analysis_result(result)
    assert "The interquartile range is zero" in html and "zero_iqr" not in html
    assert "account_code: string" in html.replace("<wbr>", "")  # Literal column names remain literal.
    assert 'Custom missing tokens: "", "\\u003cNA\\u003e"' in html
    assert "<NA>" not in html


@pytest.mark.parametrize("kind,target", [("dataset_profile", None), ("classification", "label")])
def test_real_pdf_readable_disclosure_and_all_evidence_preserved(tmp_path, kind, target):
    source = tmp_path / "source.csv"
    source.write_text("constant,empty,numeric,label\nsame,,1,a\nsame,,2,b\nsame,,3,a\nsame,,4,b\n")
    result = DataTrust.from_spec(DatasetSpec(source), TaskSpec(kind, target)).analyze_result()
    before = copy.deepcopy(result.to_dict())
    bundle = result.generate_artifacts(tmp_path / "report.pdf", format="pdf")
    text = "\n".join(page.extract_text() for page in PdfReader(bundle.pdf_path).pages)
    assert "Cooperative elapsed-time limit" in text
    assert "Not set" in text and '"max_seconds"' not in text
    assert "{'missing_values'" not in text
    assert result.to_dict() == before
    if kind == "dataset_profile":
        assert "Summary unavailable: no finite observations" in text
        assert not re.search(r"Bounded parsed-row references:\s*\.", text)
        for evidence in result.evidence:
            assert evidence.id in text
        assert "1 observed value," in text
    else:
        assert "1. Decision Summary" in text and "8. Technical Appendix" in text
