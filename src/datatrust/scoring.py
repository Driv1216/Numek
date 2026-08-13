from statistics import mean

from datatrust.wording import count_phrase, have_verb


def score_profile(profile: dict) -> dict:
    sub_scores = {
        "completeness": _clamp(100 - profile["missing_rate"]),
        "uniqueness": _clamp(100 - profile["duplicate_rate"]),
        "target_balance": _target_balance_score(profile["class_balance"]),
        "feature_usability": _feature_usability_score(profile["columns"]),
        "leakage_risk": _leakage_score(profile["strong_leakage_candidates"]),
    }
    evidence_score = round(mean(sub_scores.values()), 2)
    overall, guardrails = _apply_guardrails(evidence_score, sub_scores, profile)
    return {
        "sub_scores": sub_scores,
        "evidence_score": evidence_score,
        "overall": overall,
        "risk_level": _risk_level(overall),
        "recommended_action": _recommended_action(overall),
        "guardrails": guardrails,
    }


def _target_balance_score(class_balance: dict) -> float:
    class_count = class_balance["class_count"]
    if class_count <= 1:
        return 0.0

    expected = 100 / class_count
    largest = class_balance["largest_class_percentage"]
    if largest <= expected:
        return 100.0

    imbalance_span = 100 - expected
    penalty = ((largest - expected) / imbalance_span) * 100
    return _clamp(100 - penalty)


def _feature_usability_score(columns: list) -> float:
    feature_columns = [column for column in columns if column["role"] == "feature"]
    if not feature_columns:
        return 0.0

    penalties = 0.0
    for column in feature_columns:
        if column["missing_rate"] >= 100:
            penalties += 30
        elif column["missing_rate"] >= 50:
            penalties += 20
        elif column["missing_rate"] >= 25:
            penalties += 10
        if column["constant"]:
            penalties += 12
        elif column["near_constant"]:
            penalties += 8
        if column["high_cardinality"]:
            penalties += 8
        if column["outlier_rate"] >= 10:
            penalties += 8
        elif column["outlier_rate"] >= 5:
            penalties += 4

    normalized_penalty = penalties / max(len(feature_columns), 1)
    return _clamp(100 - normalized_penalty)


def _leakage_score(candidates: list) -> float:
    if not candidates:
        return 100.0
    # Leakage is a high-stakes risk: one plausible post-outcome column can
    # invalidate a model review even when the rest of the dataset looks healthy.
    penalty = 40 + ((len(candidates) - 1) * 15)
    return _clamp(100 - min(85, penalty))


def _risk_level(score: float) -> str:
    if score >= 85:
        return "Low"
    if score >= 70:
        return "Moderate"
    if score >= 50:
        return "Elevated"
    return "High"


def _recommended_action(score: float) -> str:
    if score >= 85:
        return "Proceed, but keep this report with the model review evidence."
    if score >= 70:
        return "Proceed with caution after reviewing the highlighted risks."
    if score >= 50:
        return "Fix the highlighted issues before using this dataset for high-stakes decisions."
    return "Do not rely on this dataset until the major reliability issues are resolved."


def _apply_guardrails(score: float, sub_scores: dict, profile: dict) -> tuple:
    guardrails = []

    if profile["strong_leakage_candidates"]:
        guardrails.append(
            _guardrail(
                "strong_leakage",
                49.0,
                f"{count_phrase(len(profile['strong_leakage_candidates']), 'strong outcome-like leakage candidate').capitalize()} require review before the dataset can be relied on: "
                + ", ".join(profile["strong_leakage_candidates"]),
            )
        )
    if profile["target_missing_count"] > 0:
        guardrails.append(
            _guardrail(
                "missing_target_labels",
                69.0,
                f"{count_phrase(profile['target_missing_count'], 'row').capitalize()} {have_verb(profile['target_missing_count'])} missing target labels and were excluded from class calculations.",
            )
        )
    if profile["class_balance"]["class_count"] <= 1:
        guardrails.append(
            _guardrail(
                "single_target_class",
                49.0,
                "The labeled target contains only one observed class, so classification training and evaluation are not defensible.",
            )
        )
    if not any(column["role"] == "feature" for column in profile["columns"]):
        guardrails.append(
            _guardrail(
                "no_feature_columns",
                49.0,
                "The dataset has no feature columns available for classification.",
            )
        )
    if profile["severe_missing_columns"]:
        guardrails.append(
            _guardrail(
                "severe_feature_missingness",
                69.0,
                "Feature columns with at least 50% missing values require resolution: "
                + ", ".join(profile["severe_missing_columns"]),
            )
        )
    if profile["duplicate_rate"] >= 10:
        guardrails.append(
            _guardrail(
                "severe_duplicates",
                69.0,
                f"Duplicate rows account for {profile['duplicate_rate']}% of the dataset.",
            )
        )
    if profile["missing_rate"] >= 25:
        guardrails.append(
            _guardrail(
                "severe_dataset_missingness",
                69.0,
                f"Missing values account for {profile['missing_rate']}% of all dataset cells.",
            )
        )
    if min(sub_scores.values()) <= 50:
        weakest = min(sub_scores, key=sub_scores.get)
        guardrails.append(
            _guardrail(
                "critical_sub_score",
                69.0,
                f"The {weakest.replace('_', ' ')} sub-score is {sub_scores[weakest]}, indicating a critical weakness.",
            )
        )

    for guardrail in guardrails:
        score = min(score, guardrail["cap"])
    return round(score, 2), guardrails


def _guardrail(code: str, cap: float, explanation: str) -> dict:
    return {"code": code, "cap": cap, "explanation": explanation}


def _clamp(value: float) -> float:
    return round(max(0.0, min(100.0, float(value))), 2)
