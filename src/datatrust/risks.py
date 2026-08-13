from typing import List

from datatrust.wording import agree, be_verb, count_phrase, have_verb


def build_findings(profile: dict, scores: dict) -> List[dict]:
    """Build every supported finding in stable priority order."""
    candidates = []

    if profile["strong_leakage_candidates"]:
        names = ", ".join(profile["strong_leakage_candidates"][:3])
        candidates.append(
            (
                10,
                _risk(
                    "possible_target_leakage",
                    "Possible target leakage",
                    f"Strong outcome-like column names such as {names} may expose information unavailable at prediction time.",
                    f"{count_phrase(len(profile['strong_leakage_candidates']), 'strong name-based candidate')}: {names}.",
                    "Validation performance may look much better than real deployment performance.",
                    "Confirm when each flagged value becomes available and exclude post-outcome fields before training or validation.",
                    "High",
                    "Affects the leakage score and applies the strong-leakage score cap.",
                ),
            )
        )

    if profile["target_missing_count"] > 0:
        candidates.append(
            (
                20,
                _risk(
                    "missing_target_labels",
                    "Missing target labels",
                    f"{count_phrase(profile['target_missing_count'], 'row').capitalize()} ({profile['target_missing_rate']}%) {have_verb(profile['target_missing_count'])} no target label and {be_verb(profile['target_missing_count'], past=True)} excluded from class calculations.",
                    f"{profile['labeled_row_count']} of {profile['row_count']} rows have usable labels.",
                    "Training or evaluation may use fewer examples than the dataset row count suggests.",
                    "Resolve, exclude, or separately account for unlabeled rows before model training and evaluation.",
                    severity_from_rate(profile["target_missing_rate"], 0.01, 10),
                    "Applies the missing-target-label guardrail; target rows remain separate from completeness scoring.",
                ),
            )
        )

    if profile["class_balance"]["class_count"] <= 1:
        candidates.append(
            (
                21,
                _risk(
                    "single_target_class",
                    "Unusable target variation",
                    "The labeled target contains only one observed class, so a classifier cannot learn or be evaluated across outcomes.",
                    f"Observed classes: {profile['class_balance']['class_count']} across {profile['labeled_row_count']} labeled rows.",
                    "A classifier cannot distinguish outcomes when only one outcome is represented.",
                    "Collect or select labeled examples from at least two target classes before training or evaluation.",
                    "High",
                    "Reduces target balance to zero and applies the single-class score cap.",
                ),
            )
        )

    if profile.get("conflicting_label_group_count", 0) > 0:
        candidates.append(
            (
                25,
                _risk(
                    "conflicting_target_labels",
                    "Potentially conflicting target labels",
                    f"{count_phrase(profile['conflicting_label_group_count'], 'feature-identical group').capitalize()} {agree(profile['conflicting_label_group_count'], 'contains', 'contain')} more than one non-missing target label.",
                    f"{count_phrase(profile['conflicting_label_row_count'], 'labeled row').capitalize()} {be_verb(profile['conflicting_label_row_count'])} included in these groups.",
                    "Inconsistent labels for identical recorded features can introduce irreducible ambiguity or reveal missing time/entity context.",
                    "Review whether these are label errors, repeated entities over time, target updates, or omitted distinguishing features.",
                    "Moderate",
                    "Evidence only; this finding does not change any score or guardrail.",
                ),
            )
        )

    has_missingness_finding = False
    if profile["severe_missing_columns"]:
        has_missingness_finding = True
        names = ", ".join(profile["severe_missing_columns"][:3])
        candidates.append(
            (
                30,
                _risk(
                    "severe_feature_missingness",
                    "Severe feature missingness",
                    f"Feature columns with at least 50% missing values include: {names}.",
                    f"{count_phrase(profile['missing_feature_row_count'], 'row').capitalize()} ({profile['missing_feature_row_rate']}%) {agree(profile['missing_feature_row_count'], 'contains', 'contain')} at least one missing feature.",
                    "Dropping incomplete rows may reduce the usable sample, while unexamined imputation may distort feature meaning.",
                    "Review each severe column and decide whether to recollect, impute, add an explicit missing indicator, or exclude it.",
                    "High"
                    if any(
                        column["missing_rate"] >= 90
                        for column in profile["columns"]
                        if column["name"] in profile["severe_missing_columns"]
                    )
                    else "Moderate",
                    "Affects feature usability and applies the severe-feature-missingness guardrail.",
                ),
            )
        )
    elif profile["missing_rate"] >= 10:
        has_missingness_finding = True
        candidates.append(
            (
                30,
                _risk(
                    "high_missingness",
                    "High missingness",
                    "A meaningful share of dataset cells are missing, which can make model behavior harder to defend.",
                    f"{profile['missing_rate']}% of all cells are missing; {profile['missing_feature_row_rate']}% of rows contain a missing feature.",
                    "Missing inputs can reduce usable sample size or make model behavior depend on the chosen handling strategy.",
                    "Review missingness by column and decide whether values should be imputed, collected again, or excluded.",
                    severity_from_rate(profile["missing_rate"], 10, 25),
                    "Reduces completeness and may apply the severe-dataset-missingness guardrail.",
                ),
            )
        )

    if not has_missingness_finding and profile.get("missing_feature_row_rate", 0) >= 25:
        candidates.append(
            (
                31,
                _risk(
                    "widespread_row_missingness",
                    "Widespread row-level missingness",
                    f"{count_phrase(profile['missing_feature_row_count'], 'row').capitalize()} ({profile['missing_feature_row_rate']}%) {agree(profile['missing_feature_row_count'], 'contains', 'contain')} at least one missing feature even though dataset-wide missingness is lower.",
                    f"Rows with one missing feature: {profile['rows_with_1_missing_feature']}; two: {profile['rows_with_2_missing_features']}; three or more: {profile['rows_with_3_plus_missing_features']}.",
                    "A low cell-level percentage can still affect a large share of training examples.",
                    "Assess whether row deletion or imputation would affect too much of the dataset, and investigate the most affected columns.",
                    "High" if profile["missing_feature_row_rate"] >= 50 else "Moderate",
                    "Evidence only; this finding does not change any score or guardrail.",
                ),
            )
        )

    if profile["duplicate_rate"] >= 2:
        candidates.append(
            (
                40,
                _risk(
                    "duplicate_records",
                    "Duplicate records",
                    "Duplicate rows may cause the model to overfit repeated examples or inflate validation confidence.",
                    f"{count_phrase(profile['duplicate_rows'], 'repeated row').capitalize()} ({profile['duplicate_rate']}%) across {count_phrase(profile['duplicate_group_count'], 'group')}; largest group: {count_phrase(profile['largest_duplicate_group_size'], 'row')}.",
                    "Repeated examples can be split across training and validation data and make evaluation appear stronger than it is.",
                    "Deduplicate records or confirm that repeated rows represent legitimate repeated events.",
                    severity_from_rate(profile["duplicate_rate"], 2, 10),
                    "Reduces uniqueness and may apply the severe-duplicates guardrail.",
                ),
            )
        )

    balance = profile["class_balance"]
    if balance["largest_class_percentage"] >= 75:
        candidates.append(
            (
                50,
                _risk(
                    "target_imbalance",
                    "Target imbalance",
                    "The target is dominated by one class, so headline accuracy may hide poor minority-class performance.",
                    f"The majority-class baseline is {profile['majority_class_baseline']}%; majority-to-minority ratio: {profile['majority_to_minority_ratio']}:1.",
                    "A model may favor the majority class and underperform on less common outcomes.",
                    "Use class-sensitive metrics and consider resampling, weighting, or collecting more minority examples.",
                    severity_from_rate(balance["largest_class_percentage"], 75, 90),
                    "Reduces the target-balance score and may trigger the critical-sub-score guardrail.",
                ),
            )
        )

    constant_columns = _columns_matching(profile, "constant")
    if constant_columns:
        candidates.append(
            (
                60,
                _risk(
                    "constant_fields",
                    "Low-value constant fields",
                    f"{count_phrase(len(constant_columns), 'feature column').capitalize()} {agree(len(constant_columns), 'contains', 'contain')} only one observed value.",
                    "Affected fields: " + ", ".join(constant_columns[:3]) + ".",
                    "Constant inputs cannot help a classifier distinguish outcomes.",
                    "Remove constant fields from modeling inputs unless they are required for downstream lineage.",
                    "Moderate",
                    "Reduces the feature-usability score.",
                ),
            )
        )

    if not any(column["role"] == "feature" for column in profile["columns"]):
        candidates.append(
            (
                60,
                _risk(
                    "no_feature_columns",
                    "No usable feature columns",
                    "The dataset contains a target column but no feature columns for classification.",
                    "Feature count: 0.",
                    "A classifier has no prediction-time inputs from which to learn.",
                    "Add the intended prediction-time feature columns before training or evaluation.",
                    "High",
                    "Reduces feature usability to zero and applies the no-feature-columns score cap.",
                ),
            )
        )

    high_cardinality = _columns_matching(profile, "high_cardinality")
    if high_cardinality:
        candidates.append(
            (
                61,
                _risk(
                    "high_cardinality_categoricals",
                    "High-cardinality categoricals",
                    f"{count_phrase(len(high_cardinality), 'categorical feature').capitalize()} {have_verb(len(high_cardinality))} many distinct values relative to row count.",
                    "Affected fields: " + ", ".join(high_cardinality[:3]) + ".",
                    "Naive encoding may overfit rare values, create unstable feature spaces, or memorize identifiers.",
                    "Check whether these fields are identifiers or need careful encoding before modeling.",
                    "Moderate",
                    "Reduces the feature-usability score.",
                ),
            )
        )

    outlier_columns = [
        column
        for column in profile["columns"]
        if column["role"] == "feature" and column["outlier_rate"] >= 5
    ]
    if outlier_columns:
        candidates.append(
            (
                62,
                _risk(
                    "numeric_outlier_concentration",
                    "Numeric outlier concentration",
                    f"{count_phrase(len(outlier_columns), 'numeric feature').capitalize()} {have_verb(len(outlier_columns))} notable IQR-based outlier rates.",
                    "Affected fields: " + ", ".join(column["name"] for column in outlier_columns[:3]) + ".",
                    "Extreme values can dominate some model families or indicate collection and unit inconsistencies.",
                    "Inspect the outlier rows and confirm whether they are real edge cases or data entry errors.",
                    "Moderate",
                    "Reduces the feature-usability score at the current outlier thresholds.",
                ),
            )
        )

    if profile["review_only_leakage_candidates"]:
        names = ", ".join(profile["review_only_leakage_candidates"][:3])
        candidates.append(
            (
                65,
                _risk(
                    "leakage_review_prompts",
                    "Leakage review prompts",
                    f"Columns such as {names} have generic status or target-related names, but their names alone are not strong leakage evidence.",
                    f"{count_phrase(len(profile['review_only_leakage_candidates']), 'review-only candidate')}: {names}.",
                    "If a field is only available after the outcome, offline validation may not represent deployment.",
                    "Confirm when these values become available; this review prompt does not reduce the leakage score or cap the overall score.",
                    "Low",
                    "Evidence only; review-only leakage prompts do not change a score or guardrail.",
                ),
            )
        )

    if not candidates:
        candidates.append(
            (
                100,
                _risk(
                    "no_major_issues",
                    "No major issues detected",
                    "The current checks did not find severe missingness, duplication, imbalance, leakage, or feature usability problems.",
                    f"Overall score: {scores['overall']} ({scores['risk_level']} risk).",
                    "Passing these checks does not establish fairness, label quality, drift resilience, or production readiness.",
                    "Proceed with model validation and add drift, fairness, and label-quality checks before production use.",
                    "Low",
                    "No additional score effect.",
                ),
            )
        )

    candidates.sort(key=lambda item: (item[0], -_severity_rank(item[1]["severity"]), item[1]["title"]))
    return [item[1] for item in candidates]


def summarize_risks(profile: dict, scores: dict) -> List[dict]:
    """Return the backward-compatible executive top-three risk summary."""
    return build_findings(profile, scores)[:3]


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


def _risk(
    code: str,
    title: str,
    finding: str,
    evidence: str,
    modeling_impact: str,
    recommendation: str,
    severity: str,
    score_effect: str,
) -> dict:
    return {
        "code": code,
        "title": title,
        "finding": finding,
        "evidence": evidence,
        "modeling_impact": modeling_impact,
        "recommendation": recommendation,
        "severity": severity,
        "score_effect": score_effect,
    }


def _severity_rank(severity: str) -> int:
    return {"Low": 1, "Moderate": 2, "High": 3}.get(severity, 0)
