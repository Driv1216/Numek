from pathlib import Path

import pandas as pd
import pytest
from click.testing import CliRunner

from datatrust import DataTrust
from datatrust.cli import main
from datatrust.profiler import profile_dataset
from datatrust.risks import summarize_risks
from datatrust.scoring import score_profile


def make_csv(tmp_path: Path) -> Path:
    data = pd.DataFrame(
        {
            "income": [100, 120, None, 5000, 120],
            "segment": ["a", "a", "b", "b", "a"],
            "constant": ["x", "x", "x", "x", "x"],
            "post_default_status": ["current", "current", "late", "charged_off", "current"],
            "default": [0, 0, 1, 1, 0],
        }
    )
    path = tmp_path / "loans.csv"
    data.to_csv(path, index=False)
    return path


def test_csv_loads_and_profiles(tmp_path):
    path = make_csv(tmp_path)
    profile = profile_dataset(path, target="default", task="classification")

    assert profile["row_count"] == 5
    assert profile["column_count"] == 5
    assert profile["target"] == "default"
    assert profile["missing_rate"] > 0


def test_missing_target_raises_clear_error(tmp_path):
    path = make_csv(tmp_path)

    with pytest.raises(ValueError, match="Target column 'missing'"):
        profile_dataset(path, target="missing", task="classification")


def test_classification_target_balance_is_computed(tmp_path):
    path = make_csv(tmp_path)
    profile = profile_dataset(path, target="default", task="classification")

    assert profile["class_balance"]["class_count"] == 2
    assert profile["class_balance"]["largest_class_percentage"] == 60.0
    assert profile["class_balance"]["minority_class_percentage"] == 40.0


def test_missingness_and_duplicate_rates(tmp_path):
    path = tmp_path / "dupes.csv"
    pd.DataFrame({"x": [1, 1, None], "default": [0, 0, 1]}).to_csv(path, index=False)

    profile = profile_dataset(path, target="default", task="classification")

    assert profile["missing_rate"] == 16.67
    assert profile["duplicate_rate"] == 33.33


def test_constant_and_high_cardinality_columns_detected(tmp_path):
    path = tmp_path / "wide.csv"
    pd.DataFrame(
        {
            "id_like": [f"id_{i}" for i in range(25)],
            "constant": ["same"] * 25,
            "default": [0] * 20 + [1] * 5,
        }
    ).to_csv(path, index=False)

    profile = profile_dataset(path, target="default", task="classification")
    columns = {column["name"]: column for column in profile["columns"]}

    assert columns["constant"]["constant"] is True
    assert columns["id_like"]["high_cardinality"] is True


def test_sub_scores_are_bounded(tmp_path):
    path = make_csv(tmp_path)
    scores = score_profile(profile_dataset(path, target="default", task="classification"))

    assert 0 <= scores["overall"] <= 100
    for value in scores["sub_scores"].values():
        assert 0 <= value <= 100


def test_top_risk_summary_returns_at_most_three_findings(tmp_path):
    path = make_csv(tmp_path)
    profile = profile_dataset(path, target="default", task="classification")
    risks = summarize_risks(profile, score_profile(profile))

    assert 1 <= len(risks) <= 3


def test_python_api_generates_report(tmp_path):
    path = make_csv(tmp_path)
    output = tmp_path / "report.html"

    result = DataTrust(str(path), target="default", task="classification").generate_report(str(output))

    assert result == str(output)
    html = output.read_text(encoding="utf-8")
    assert "1. Decision Summary" in html
    assert "8. Technical Appendix" in html


def test_cli_generates_html_file(tmp_path):
    path = make_csv(tmp_path)
    output = tmp_path / "report.html"
    runner = CliRunner()

    result = runner.invoke(
        main,
        ["audit", str(path), "--target", "default", "--task", "classification", "--out", str(output)],
    )

    assert result.exit_code == 0
    assert output.exists()
    assert "DataTrust report written" in result.output


def test_cli_invalid_target_returns_useful_error(tmp_path):
    path = make_csv(tmp_path)
    runner = CliRunner()

    result = runner.invoke(
        main,
        ["audit", str(path), "--target", "not_a_column", "--out", str(tmp_path / "report.html")],
    )

    assert result.exit_code != 0
    assert "Target column 'not_a_column'" in result.output


def test_empty_dataset_raises_clear_error(tmp_path):
    path = tmp_path / "empty.csv"
    pd.DataFrame(columns=["feature", "default"]).to_csv(path, index=False)

    with pytest.raises(ValueError, match="Dataset is empty"):
        profile_dataset(path, target="default", task="classification")


def test_target_missingness_is_separate_from_class_counts(tmp_path):
    path = tmp_path / "missing-targets.csv"
    pd.DataFrame(
        {"feature": [1, 2, 3, 4], "default": [0, 1, None, None]}
    ).to_csv(path, index=False)

    profile = profile_dataset(path, target="default", task="classification")

    assert profile["target_missing_count"] == 2
    assert profile["target_missing_rate"] == 50.0
    assert profile["labeled_row_count"] == 2
    assert profile["class_balance"]["class_count"] == 2
    assert {item["label"] for item in profile["target_distribution"]} == {"0.0", "1.0"}


def test_dataset_without_usable_target_labels_raises_clear_error(tmp_path):
    path = tmp_path / "unlabeled.csv"
    pd.DataFrame({"feature": [1, 2], "default": [None, None]}).to_csv(path, index=False)

    with pytest.raises(ValueError, match="no usable labels"):
        profile_dataset(path, target="default", task="classification")


def test_fully_missing_feature_is_surfaced_and_prevents_low_risk(tmp_path):
    path = tmp_path / "missing-feature.csv"
    pd.DataFrame(
        {"empty_feature": [None] * 10, "default": [0, 1] * 5}
    ).to_csv(path, index=False)

    result = DataTrust(str(path), target="default").analyze()

    assert result["profile"]["severe_missing_columns"] == ["empty_feature"]
    assert any(risk["title"] == "Severe feature missingness" for risk in result["risks"])
    assert result["scores"]["risk_level"] != "Low"
    assert any("empty_feature" in item["explanation"] for item in result["scores"]["guardrails"])


def test_benign_status_column_is_review_only_without_score_cap(tmp_path):
    path = tmp_path / "employment.csv"
    pd.DataFrame(
        {
            "income": range(10),
            "employment_status": ["employed", "self-employed"] * 5,
            "default": [0, 1] * 5,
        }
    ).to_csv(path, index=False)

    result = DataTrust(str(path), target="default").analyze()

    assert result["profile"]["strong_leakage_candidates"] == []
    assert result["profile"]["review_only_leakage_candidates"] == ["employment_status"]
    assert result["scores"]["sub_scores"]["leakage_risk"] == 100.0
    assert result["scores"]["risk_level"] == "Low"
    assert not any(risk["title"] == "Possible target leakage" for risk in result["risks"])


def test_strong_post_outcome_column_applies_explained_guardrail(tmp_path):
    path = tmp_path / "leakage.csv"
    pd.DataFrame(
        {
            "income": range(10),
            "post_default_status": ["current", "charged_off"] * 5,
            "default": [0, 1] * 5,
        }
    ).to_csv(path, index=False)

    result = DataTrust(str(path), target="default").analyze()

    assert result["profile"]["strong_leakage_candidates"] == ["post_default_status"]
    assert result["scores"]["overall"] <= 49
    assert result["scores"]["risk_level"] == "High"
    assert result["risks"][0]["title"] == "Possible target leakage"
    assert any(item["code"] == "strong_leakage" for item in result["scores"]["guardrails"])


def test_previous_outcome_column_is_review_only_without_score_cap(tmp_path):
    path = tmp_path / "previous-outcome.csv"
    pd.DataFrame(
        {
            "income": range(10),
            "previous_campaign_outcome": ["success", "failure"] * 5,
            "subscribed": ["yes", "no"] * 5,
        }
    ).to_csv(path, index=False)

    result = DataTrust(str(path), target="subscribed").analyze()

    assert result["profile"]["strong_leakage_candidates"] == []
    assert result["profile"]["review_only_leakage_candidates"] == ["previous_campaign_outcome"]
    assert result["scores"]["sub_scores"]["leakage_risk"] == 100.0
    assert not any(item["code"] == "strong_leakage" for item in result["scores"]["guardrails"])


def test_missing_targets_are_reported_and_guardrailed(tmp_path):
    path = tmp_path / "some-unlabeled.csv"
    pd.DataFrame(
        {"feature": range(10), "default": [0, 1, None, 1, 0, 1, 0, 1, 0, 1]}
    ).to_csv(path, index=False)

    result = DataTrust(str(path), target="default").analyze()

    assert any(risk["title"] == "Missing target labels" for risk in result["risks"])
    assert result["scores"]["risk_level"] != "Low"
    assert any(item["code"] == "missing_target_labels" for item in result["scores"]["guardrails"])


def test_severe_findings_cannot_contradict_overall_low_risk(tmp_path):
    path = tmp_path / "duplicates.csv"
    base = pd.DataFrame({"feature": range(90), "default": [0, 1] * 45})
    rows = pd.concat([base, base.iloc[:10]], ignore_index=True)
    rows.to_csv(path, index=False)

    result = DataTrust(str(path), target="default").analyze()

    assert any(risk["title"] == "Duplicate records" and risk["severity"] == "High" for risk in result["risks"])
    assert result["scores"]["risk_level"] != "Low"


def test_controlled_mutations_lower_relevant_scores(tmp_path):
    clean = pd.DataFrame({"feature": range(20), "default": [0, 1] * 10})
    mutated = {
        "duplicates": pd.concat([clean, clean.iloc[:5]], ignore_index=True),
        "imbalance": pd.DataFrame({"feature": range(20), "default": [0] * 19 + [1]}),
        "constant": pd.DataFrame({"feature": ["same"] * 20, "default": [0, 1] * 10}),
        "leakage": pd.DataFrame(
            {"post_default_status": ["open", "closed"] * 10, "default": [0, 1] * 10}
        ),
    }

    clean_path = tmp_path / "clean.csv"
    clean.to_csv(clean_path, index=False)
    clean_scores = DataTrust(str(clean_path), target="default").analyze()["scores"]["sub_scores"]

    expected_score = {
        "duplicates": "uniqueness",
        "imbalance": "target_balance",
        "constant": "feature_usability",
        "leakage": "leakage_risk",
    }
    for name, data in mutated.items():
        path = tmp_path / f"{name}.csv"
        data.to_csv(path, index=False)
        scores = DataTrust(str(path), target="default").analyze()["scores"]["sub_scores"]
        score_name = expected_score[name]
        assert scores[score_name] < clean_scores[score_name]


def test_single_class_target_has_matching_finding_and_high_risk(tmp_path):
    path = tmp_path / "single-class.csv"
    pd.DataFrame({"feature": range(10), "default": [0] * 10}).to_csv(path, index=False)

    result = DataTrust(str(path), target="default").analyze()

    assert result["risks"][0]["title"] == "Unusable target variation"
    assert result["risks"][0]["severity"] == "High"
    assert result["scores"]["risk_level"] == "High"
    assert any(item["code"] == "single_target_class" for item in result["scores"]["guardrails"])


def test_multiclass_subtype_baseline_and_ratio_are_reported(tmp_path):
    path = tmp_path / "multiclass.csv"
    pd.DataFrame(
        {"feature": range(10), "label": ["a"] * 5 + ["b"] * 3 + ["c"] * 2}
    ).to_csv(path, index=False)

    profile = profile_dataset(path, target="label", task="classification")

    assert profile["classification_subtype"] == "multiclass"
    assert profile["majority_class_baseline"] == 50.0
    assert profile["majority_to_minority_ratio"] == 2.5


def test_row_missingness_excludes_target_and_uses_buckets(tmp_path):
    path = tmp_path / "row-missingness.csv"
    pd.DataFrame(
        {
            "a": [1, None, None, None],
            "b": [1, 2, None, None],
            "c": [1, 2, 3, None],
            "label": [0, None, 1, 0],
        }
    ).to_csv(path, index=False)

    profile = profile_dataset(path, target="label", task="classification")

    assert profile["missing_feature_row_count"] == 3
    assert profile["missing_feature_row_rate"] == 75.0
    assert profile["rows_with_1_missing_feature"] == 1
    assert profile["rows_with_2_missing_features"] == 1
    assert profile["rows_with_3_plus_missing_features"] == 1


def test_duplicate_groups_and_conflicting_labels_are_separate(tmp_path):
    path = tmp_path / "duplicate-evidence.csv"
    pd.DataFrame(
        {
            "feature": [1, 1, 2, 2, 3],
            "segment": ["a", "a", "b", "b", "c"],
            "label": [0, 0, 0, 1, 1],
        }
    ).to_csv(path, index=False)

    result = DataTrust(str(path), target="label").analyze()
    profile = result["profile"]

    assert profile["duplicate_rows"] == 1
    assert profile["duplicate_group_count"] == 1
    assert profile["largest_duplicate_group_size"] == 2
    assert profile["conflicting_label_group_count"] == 1
    assert profile["conflicting_label_row_count"] == 2
    conflict = next(item for item in result["findings"] if item["code"] == "conflicting_target_labels")
    assert conflict["severity"] == "Moderate"
    assert "does not change" in conflict["score_effect"]


def test_numeric_summary_handles_non_finite_values(tmp_path):
    path = tmp_path / "numeric.csv"
    pd.DataFrame(
        {"amount": [-2.0, 0.0, 2.0, float("inf"), float("-inf")], "label": [0, 1, 0, 1, 0]}
    ).to_csv(path, index=False)

    profile = profile_dataset(path, target="label", task="classification")
    amount = next(column for column in profile["columns"] if column["name"] == "amount")

    assert amount["numeric_summary"]["min"] == -2.0
    assert amount["numeric_summary"]["median"] == 0.0
    assert amount["numeric_summary"]["max"] == 2.0
    assert amount["numeric_summary"]["zero_count"] == 1
    assert amount["numeric_summary"]["negative_count"] == 1
    assert amount["numeric_summary"]["non_finite_count"] == 2


def test_zero_feature_profile_retains_clear_evidence(tmp_path):
    path = tmp_path / "target-only.csv"
    pd.DataFrame({"label": [0, 1, 0, 1]}).to_csv(path, index=False)

    result = DataTrust(str(path), target="label").analyze()

    assert result["profile"]["feature_count"] == 0
    assert result["profile"]["missing_feature_row_rate"] == 0.0
    assert any(item["code"] == "no_feature_columns" for item in result["findings"])


def test_all_findings_are_exposed_while_risks_stay_top_three(tmp_path):
    path = make_csv(tmp_path)
    result = DataTrust(str(path), target="default").analyze()

    assert len(result["risks"]) <= 3
    assert result["risks"] == result["findings"][:3]
    assert all(
        {"code", "evidence", "modeling_impact", "score_effect"}.issubset(item)
        for item in result["findings"]
    )


def test_new_evidence_keeps_existing_example_scores_stable():
    result = DataTrust("examples/loan_data.csv", target="default").analyze()

    assert result["scores"]["sub_scores"] == {
        "completeness": 99.0,
        "uniqueness": 100.0,
        "target_balance": 90.0,
        "feature_usability": 98.67,
        "leakage_risk": 60.0,
    }
    assert result["scores"]["overall"] == 49.0


def test_report_has_eight_sections_visuals_print_styles_and_escaped_context(tmp_path):
    path = make_csv(tmp_path)
    output = tmp_path / "report.html"

    DataTrust(
        str(path),
        target="default",
        dataset_name="<script>alert(1)</script>",
        purpose="Review <b>loan</b> readiness",
    ).generate_report(str(output))
    html = output.read_text(encoding="utf-8")

    for heading in (
        "1. Decision Summary",
        "2. Priority Actions",
        "3. Dataset Overview",
        "4. Target and Label Evidence",
        "5. Missingness Evidence",
        "6. Duplicate and Feature Evidence",
        "7. Scoring, Methodology, and Limitations",
        "8. Technical Appendix",
    ):
        assert heading in html
    assert "aria-label=\"Horizontal bars showing target class distribution\"" in html
    assert "aria-label=\"Horizontal bars showing missing percentage by feature\"" in html
    assert "@media print" in html
    assert "@page appendix" in html
    assert "page: appendix" in html
    assert "existing guardrails" not in html
    assert "established DataTrust formulas" not in html
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "Review &lt;b&gt;loan&lt;/b&gt; readiness" in html
    assert str(tmp_path) not in html
    assert "Feature columns" in html
    assert "Potential features" not in html
    assert "Priority actions are ordered by severity" in html


def test_report_adds_safe_wrap_points_to_long_camel_case_names(tmp_path):
    target = "CustomerApprovalOutcomeForInternationalOperations"
    path = tmp_path / "QuarterlyCustomerApprovalDataset.csv"
    pd.DataFrame({"feature": [1, 2, 3], target: [0, 1, 0]}).to_csv(
        path, index=False
    )
    output = tmp_path / "report.html"

    DataTrust(str(path), target=target).generate_report(str(output))
    html = output.read_text(encoding="utf-8")

    assert "Quarterly<wbr>Customer<wbr>Approval<wbr>Dataset" in html
    assert (
        "Customer<wbr>Approval<wbr>Outcome<wbr>For<wbr>International<wbr>Operations"
        in html
    )
    assert (
        "<td>Customer<wbr>Approval<wbr>Outcome<wbr>For<wbr>International<wbr>Operations</td>"
        in html
    )


def test_fallback_report_names_are_humanized_without_changing_custom_names(tmp_path):
    data = {"feature": [1, 2, 3, 4], "label": [0, 1, 0, 1]}
    cases = {
        "heart.csv": "Heart",
        "Titanic-Dataset.csv": "Titanic Dataset",
        "loan_default_data.csv": "Loan Default Data",
        "COVID19_data.csv": "COVID19 Data",
    }

    for filename, expected in cases.items():
        path = tmp_path / filename
        pd.DataFrame(data).to_csv(path, index=False)
        result = DataTrust(str(path), target="label").analyze()
        assert result["context"]["dataset_name"] == expected

    source_path = tmp_path / "dataset.csv"
    pd.DataFrame(data).to_csv(source_path, index=False)
    uploaded = DataTrust(
        str(source_path), target="label", source_filename="OriginalUpload_name.csv"
    ).analyze()
    custom = DataTrust(
        str(source_path), target="label", dataset_name="custom_report_name"
    ).analyze()

    assert uploaded["context"]["dataset_name"] == "Original Upload Name"
    assert uploaded["context"]["source_filename"] == "OriginalUpload_name.csv"
    assert custom["context"]["dataset_name"] == "custom_report_name"


def test_clean_report_uses_empty_state_without_removing_compatibility_finding(tmp_path):
    path = tmp_path / "clean.csv"
    pd.DataFrame({"feature": [1, 2, 3, 4], "label": [0, 1, 0, 1]}).to_csv(
        path, index=False
    )
    output = tmp_path / "clean-report.html"

    audit = DataTrust(str(path), target="label")
    result = audit.analyze()
    audit.generate_report(str(output))
    html = output.read_text(encoding="utf-8")

    assert [finding["code"] for finding in result["findings"]] == ["no_major_issues"]
    assert [risk["code"] for risk in result["risks"]] == ["no_major_issues"]
    assert "No priority actions were generated" in html
    assert "Passing these checks does not establish fairness" in html
    assert '<article class="card action-card Low">' not in html


def test_generated_findings_use_correct_singular_and_plural_grammar(tmp_path):
    singular_path = tmp_path / "singular-outlier.csv"
    pd.DataFrame(
        {"value": list(range(1, 20)) + [100], "label": [0, 1] * 10}
    ).to_csv(singular_path, index=False)
    singular = DataTrust(str(singular_path), target="label").analyze()
    outlier = next(item for item in singular["findings"] if item["code"] == "numeric_outlier_concentration")

    plural_path = tmp_path / "plural-outlier.csv"
    pd.DataFrame(
        {
            "value_a": list(range(1, 20)) + [100],
            "value_b": list(range(11, 30)) + [200],
            "label": [0, 1] * 10,
        }
    ).to_csv(plural_path, index=False)
    plural = DataTrust(str(plural_path), target="label").analyze()
    plural_outlier = next(item for item in plural["findings"] if item["code"] == "numeric_outlier_concentration")

    assert outlier["finding"].startswith("1 numeric feature has")
    assert plural_outlier["finding"].startswith("2 numeric features have")
    assert "feature(s)" not in outlier["finding"] + plural_outlier["finding"]
