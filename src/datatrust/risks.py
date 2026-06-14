from typing import List


def summarize_risks(profile: dict, scores: dict) -> List[dict]:
    candidates = []

    if profile["strong_leakage_candidates"]:
        names = ", ".join(profile["strong_leakage_candidates"][:3])
        candidates.append(
            (10,
            _risk(
                "Possible target leakage",
                f"Strong outcome-like column names such as {names} may expose information unavailable at prediction time.",
                "Confirm when each flagged value becomes available and exclude post-outcome fields before training or validation.",
                "High",
            )
            )
        )

    if profile["target_missing_count"] > 0:
        candidates.append(
            (20,
            _risk(
                "Missing target labels",
                f"{profile['target_missing_count']} row(s) ({profile['target_missing_rate']}%) have no target label and were excluded from class calculations.",
                "Resolve, exclude, or separately account for unlabeled rows before model training and evaluation.",
                severity_from_rate(profile["target_missing_rate"], 0.01, 10),
            )
            )
        )

    if profile["class_balance"]["class_count"] <= 1:
        candidates.append(
            (
                21,
                _risk(
                    "Unusable target variation",
                    "The labeled target contains only one observed class, so a classifier cannot learn or be evaluated across outcomes.",
                    "Collect or select labeled examples from at least two target classes before training or evaluation.",
                    "High",
                ),
            )
        )

    if profile["severe_missing_columns"]:
        names = ", ".join(profile["severe_missing_columns"][:3])
        candidates.append(
            (30,
            _risk(
                "Severe feature missingness",
                f"Feature columns with at least 50% missing values include: {names}.",
                "Review each severe column and decide whether to recollect, impute, add an explicit missing indicator, or exclude it.",
                "High" if any(
                    column["missing_rate"] >= 90
                    for column in profile["columns"]
                    if column["name"] in profile["severe_missing_columns"]
                ) else "Moderate",
            )
            )
        )
    elif profile["missing_rate"] >= 10:
        candidates.append(
            (30,
            _risk(
                "High missingness",
                "A meaningful share of dataset cells are missing, which can make model behavior harder to defend.",
                "Review missingness by column and decide whether values should be imputed, collected again, or excluded.",
                severity_from_rate(profile["missing_rate"], 10, 25),
            )
            )
        )

    if profile["duplicate_rate"] >= 2:
        candidates.append(
            (40,
            _risk(
                "Duplicate records",
                "Duplicate rows may cause the model to overfit repeated examples or inflate validation confidence.",
                "Deduplicate records or confirm that repeated rows represent legitimate repeated events.",
                severity_from_rate(profile["duplicate_rate"], 2, 10),
            )
            )
        )

    balance = profile["class_balance"]
    if balance["largest_class_percentage"] >= 75:
        candidates.append(
            (50,
            _risk(
                "Target imbalance",
                "The target is dominated by one class, so headline accuracy may hide poor minority-class performance.",
                "Use class-sensitive metrics and consider resampling, weighting, or collecting more minority examples.",
                severity_from_rate(balance["largest_class_percentage"], 75, 90),
            )
            )
        )

    if profile["review_only_leakage_candidates"]:
        names = ", ".join(profile["review_only_leakage_candidates"][:3])
        candidates.append(
            (65,
            _risk(
                "Leakage review prompts",
                f"Columns such as {names} have generic status or target-related names, but their names alone are not strong leakage evidence.",
                "Confirm when these values become available; this review prompt does not reduce the leakage score or cap the overall score.",
                "Low",
            )
            )
        )

    constant_columns = _columns_matching(profile, "constant")
    if constant_columns:
        candidates.append(
            (60,
            _risk(
                "Low-value constant fields",
                f"{len(constant_columns)} feature column(s) contain only one observed value.",
                "Remove constant fields from modeling inputs unless they are required for downstream lineage.",
                "Moderate",
            )
            )
        )

    if not any(column["role"] == "feature" for column in profile["columns"]):
        candidates.append(
            (
                60,
                _risk(
                    "No usable feature columns",
                    "The dataset contains a target column but no feature columns for classification.",
                    "Add the intended prediction-time feature columns before training or evaluation.",
                    "High",
                ),
            )
        )

    high_cardinality = _columns_matching(profile, "high_cardinality")
    if high_cardinality:
        candidates.append(
            (61,
            _risk(
                "High-cardinality categoricals",
                f"{len(high_cardinality)} categorical feature(s) have many distinct values relative to row count.",
                "Check whether these fields are identifiers or need careful encoding before modeling.",
                "Moderate",
            )
            )
        )

    outlier_columns = [
        column
        for column in profile["columns"]
        if column["role"] == "feature" and column["outlier_rate"] >= 5
    ]
    if outlier_columns:
        candidates.append(
            (62,
            _risk(
                "Numeric outlier concentration",
                f"{len(outlier_columns)} numeric feature(s) have notable IQR-based outlier rates.",
                "Inspect the outlier rows and confirm whether they are real edge cases or data entry errors.",
                "Moderate",
            )
            )
        )

    if not candidates:
        candidates.append(
            (100,
            _risk(
                "No major V1 issues detected",
                "The current checks did not find severe missingness, duplication, imbalance, leakage, or feature usability problems.",
                "Proceed with model validation and add drift, fairness, and label-quality checks before production use.",
                "Low",
            )
            )
        )

    candidates.sort(key=lambda item: (item[0], -_severity_rank(item[1]["severity"]), item[1]["title"]))
    return [item[1] for item in candidates[:3]]


def severity_from_rate(value: float, moderate_threshold: float, high_threshold: float) -> str:
    if value >= high_threshold:
        return "High"
    if value >= moderate_threshold:
        return "Moderate"
    return "Low"


def _columns_matching(profile: dict, flag: str) -> list:
    return [
        column["name"]
        for column in profile["columns"]
        if column["role"] == "feature" and column.get(flag)
    ]


def _risk(title: str, finding: str, recommendation: str, severity: str) -> dict:
    return {
        "title": title,
        "finding": finding,
        "recommendation": recommendation,
        "severity": severity,
    }


def _severity_rank(severity: str) -> int:
    return {"Low": 1, "Moderate": 2, "High": 3}.get(severity, 0)
