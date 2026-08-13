import pandas as pd

from datatrust.profiler import inspect_csv_dataset
from datatrust.target_guidance import assess_target_options, assess_target_series


def _series(values, name="target"):
    return pd.Series(values, name=name)


def test_two_and_three_row_binary_targets_remain_small_class_candidates():
    for values in ([0, 1], [0, 1, 1]):
        option = assess_target_series(_series(values, "plain_value"), "plain_value")

        assert option["small_class_ceiling"] == 2
        assert option["group"] == "small_class_set"
        assert option["requires_override"] is False
        assert option["observed_distinct_count"] == 2
        assert option["observed_class_count"] == 2


def test_small_class_ceiling_boundaries_are_deterministic():
    twenty_classes = assess_target_series(
        _series(list(range(20)) * 2, "category"), "category"
    )
    twenty_one_classes = assess_target_series(
        _series(list(range(21)) * 2, "category"), "category"
    )
    half_rows = assess_target_series(_series([0, 1, 2, 0, 1, 2], "category"), "category")
    above_half = assess_target_series(_series([0, 1, 2, 3, 0, 1], "category"), "category")

    assert twenty_classes["group"] == "small_class_set"
    assert twenty_one_classes["group"] == "advanced"
    assert "continuous_numeric" in twenty_one_classes["reason_codes"]
    assert half_rows["small_class_ceiling"] == 3
    assert half_rows["group"] == "small_class_set"
    assert above_half["group"] == "advanced"


def test_camel_case_and_whole_token_outcome_names_are_elevated():
    heart = assess_target_series(_series([0, 1] * 10), "HeartDisease")
    survived = assess_target_series(_series([0, 1] * 10), "Survived")
    substring = assess_target_series(_series([0, 1] * 10), "defaultingFeature")

    assert heart["group"] == "outcome_word"
    assert heart["name_tokens"] == ["heart", "disease"]
    assert survived["group"] == "outcome_word"
    assert substring["group"] == "small_class_set"
    assert substring["matched_outcome_tokens"] == []


def test_semantic_elevation_never_claims_likelihood_or_selection():
    for name in ("family_history_disease", "existing_diagnosis", "fraud_history"):
        option = assess_target_series(_series([0, 1] * 10), name)

        assert option["group"] == "outcome_word"
        assert "selected" not in option
        assert "confidence" not in option
        assert "likely" not in option["explanation"].lower()
        assert "has not selected it for you" in option["explanation"]


def test_conservative_tokens_suppress_prior_derived_and_generic_names():
    previous = assess_target_series(
        _series(["success", "failure"] * 10), "previous_campaign_outcome"
    )
    score = assess_target_series(_series(["low", "high"] * 10), "risk_score")
    risk = assess_target_series(_series(["low", "high"] * 10), "credit_risk")

    assert previous["group"] == "small_class_set"
    assert "outcome_signal_suppressed" in previous["reason_codes"]
    assert score["group"] == "small_class_set"
    assert "generic_outcome_word" in score["reason_codes"]
    assert risk["group"] == "small_class_set"


def test_ambiguous_schema_returns_multiple_candidates_without_selection():
    data = pd.DataFrame(
        {
            "approved": [0, 1] * 10,
            "defaulted_90d": [0, 1] * 10,
            "risk_grade": ["a", "b", "c", "a", "b"] * 4,
        }
    )

    options = assess_target_options(data)

    assert [option["name"] for option in options[:2]] == ["approved", "defaulted_90d"]
    assert [option["group"] for option in options[:2]] == ["outcome_word", "outcome_word"]
    assert options[2]["name"] == "risk_grade"
    assert options[2]["group"] == "small_class_set"
    assert all("selected" not in option for option in options)


def test_identifier_continuous_many_category_single_and_missing_rules():
    identifier = assess_target_series(_series(range(20)), "customer_id")
    unique_text = assess_target_series(
        _series([f"person-{index}" for index in range(20)]), "person_name"
    )
    continuous = assess_target_series(_series([value // 2 for value in range(60)]), "amount")
    categories = assess_target_series(
        _series([f"group-{index // 2}" for index in range(60)]), "category"
    )
    single = assess_target_series(_series(["yes"] * 20), "status")
    missing = assess_target_series(_series([None, None]), "empty")

    assert {"identifier_name", "near_unique"}.issubset(identifier["reason_codes"])
    assert "20 distinct values across 20 labeled rows (100.0% distinct)" in identifier[
        "explanation"
    ]
    assert "near_unique" in unique_text["reason_codes"]
    assert "continuous_numeric" in continuous["reason_codes"]
    assert "many_categories" in categories["reason_codes"]
    assert single["reason_codes"] == ["single_class"]
    assert missing["group"] == "disabled"
    assert missing["disabled"] is True
    assert "guidance limit" not in continuous["selector_explanation"]
    assert continuous["selector_explanation"] == (
        "This looks more like a continuous measurement than a classification outcome."
    )
    assert "30 distinct numeric values across 60 labeled rows" in continuous["explanation"]
    assert all(
        option["requires_override"]
        for option in (identifier, unique_text, continuous, categories, single)
    )


def test_selector_explanations_are_concise_but_preserve_semantic_cautions():
    outcome = assess_target_series(_series([0, 1] * 10), "approved")
    ordinary = assess_target_series(_series([0, 1] * 10), "segment")
    suppressed = assess_target_series(_series([0, 1] * 10), "previous_outcome")
    generic = assess_target_series(_series([0, 1] * 10), "risk_grade")

    assert outcome["selector_explanation"] == "Its name suggests an outcome."
    assert ordinary["selector_explanation"] == "Could be used as a classification outcome."
    assert "prior or derived information" in suppressed["selector_explanation"]
    assert "does not establish the intended outcome" in generic["selector_explanation"]


def test_group_order_preserves_source_column_order():
    data = pd.DataFrame(
        {
            "plain_b": [0, 1] * 10,
            "approved": [0, 1] * 10,
            "plain_a": ["x", "y"] * 10,
            "defaulted": [0, 1] * 10,
            "customer_id": range(20),
        }
    )

    options = assess_target_options(data)

    assert [option["name"] for option in options] == [
        "approved",
        "defaulted",
        "plain_b",
        "plain_a",
        "customer_id",
    ]


def test_existing_validation_targets_follow_conservative_policy():
    adult = pd.read_csv("validation/data/prepared/adult.csv")
    german = pd.read_csv("validation/data/prepared/german_credit.csv")

    adult_option = next(
        option
        for option in assess_target_options(adult)
        if option["name"] == "annual_income_over_50k"
    )
    german_option = next(
        option
        for option in assess_target_options(german)
        if option["name"] == "credit_risk"
    )

    assert adult_option["group"] == "small_class_set"
    assert german_option["group"] == "small_class_set"


def test_csv_inspection_adds_ordered_target_options(tmp_path):
    path = tmp_path / "targets.csv"
    pd.DataFrame({"feature": [1, 2], "label": [0, 1]}).to_csv(path, index=False)

    inspection = inspect_csv_dataset(path)

    assert inspection["columns"] == ["feature", "label"]
    assert [option["name"] for option in inspection["target_options"]] == [
        "label",
        "feature",
    ]
