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


def build_unlabeled_findings(profile: dict) -> List[dict]:
    """Evidence-based review priorities, with no scoring or readiness verdict."""
    findings = []
    columns = profile["columns"]

    def add(code, title, fact, evidence, recommendation, severity, check_id, impact):
        findings.append({"code": code, "title": title, "finding": fact, "evidence": evidence,
                         "recommendation": recommendation, "severity": severity,
                         "modeling_impact": impact, "evidence_type": "review_observation",
                         "check_id": check_id})

    empty = [c for c in columns if c["unique_count"] == 0]
    if empty:
        add("fully_missing_columns", "Fully missing columns", f"{count_phrase(len(empty), 'column')} {agree(len(empty), 'contains', 'contain')} no observed values.",
            ", ".join(c["name"] for c in empty), "Confirm whether these fields were expected; investigate collection or parsing before choosing how to handle them.",
            "High", "missingness", "These fields provide no observed input information in this dataset.")
    missing = [c for c in columns if c["unique_count"] > 0 and c["missing_rate"] >= 25]
    if missing:
        add("column_missingness", "Substantial column missingness", "Some columns have at least 25% missing values.",
            "; ".join(f"{c['name']}: {c['missing_count']} of {profile['row_count']} rows ({c['missing_rate']}%)" for c in missing),
            "Confirm the selected missing-value policy and investigate collection coverage before imputing or excluding values.",
            "High" if any(c["missing_rate"] >= 50 for c in missing) else "Moderate", "missingness", "Missing inputs can reduce usable coverage or make analysis sensitive to handling choices.")
    if profile["missing_rate"] >= 10:
        add("dataset_missingness", "Dataset-wide missingness", f"{profile['missing_rate']}% of parsed cells are missing.",
            f"{profile['missing_cells']} missing cells; {profile['missing_feature_row_rate']}% of rows are affected.",
            "Review missingness by column and row; avoid assuming row deletion or imputation is appropriate.",
            "High" if profile["missing_rate"] >= 25 else "Moderate", "missingness", "Cell-level averages can hide uneven coverage across records.")
    elif not empty and not missing and profile["missing_feature_row_rate"] >= 25:
        add("widespread_row_missingness", "Widespread row missingness", f"{profile['missing_feature_row_rate']}% of rows contain missing inputs.",
            f"{profile['missing_feature_row_count']} of {profile['row_count']} rows; one/two/three-plus missing-column buckets are reported.",
            "Assess row-level reach before choosing any missing-value handling strategy.",
            "High" if profile["missing_feature_row_rate"] >= 50 else "Moderate", "missingness", "A low cell-level rate may still affect many records.")
    rate = profile["duplicate_rate"]
    if rate is not None and profile["duplicate_rows"]:
        add("duplicate_records", "Exact repeated records", f"{profile['duplicate_rows']} rows repeat an earlier complete parsed row ({rate}%).",
            f"{profile['duplicate_group_count']} groups; {profile['rows_in_duplicate_groups']} participating rows; largest group {profile['largest_duplicate_group_size']}.",
            "Review whether repetition represents valid repeated events, deliberate weighting, or unintended copying. Do not automatically deduplicate.",
            "High" if rate >= 10 else "Moderate" if rate >= 2 else "Low", "exact_duplicates", "Repetition changes effective coverage and may matter to later dataset splitting.")
    for flag, code, title, predicate, advice in (
        ("constant", "constant_fields", "Observed constant fields", lambda c: c["unique_count"] == 1,
         "Confirm whether constants are expected metadata or intended variable inputs; remove nothing automatically."),
        ("near_constant", "near_constant_fields", "Near-constant fields", lambda c: not c["top_value_is_missing"],
         "Review whether rare values are legitimate and important before changing these fields."),
        ("high_cardinality", "high_cardinality_categoricals", "High-cardinality text or categories", lambda c: True,
         "Check whether these fields are identifiers, free text, or categories requiring deliberate encoding."),
    ):
        affected = [c for c in columns if c[flag] and predicate(c)]
        if affected:
            add(code, title, f"{count_phrase(len(affected), 'column')} {agree(len(affected), 'meets', 'meet')} the {title.lower()} review rule.",
                "; ".join(f"{c['name']}: {c['unique_count']} observed values, {c['top_value_rate']}% top share" for c in affected),
                advice, "Moderate" if code == "constant_fields" else "Low",
                "categorical_cardinality" if flag == "high_cardinality" else "column_variation",
                "Observed distributions need interpretation against the intended data use; rarity or cardinality alone is not a defect.")
    nonfinite = [c for c in columns if c.get("numeric_summary") and c["numeric_summary"]["non_finite_count"]]
    if nonfinite:
        add("non_finite_values", "Non-finite numeric values", "Some numeric fields contain infinity values.",
            "; ".join(f"{c['name']}: {c['numeric_summary']['non_finite_count']} values" for c in nonfinite),
            "Confirm whether infinities represent intended sentinels or arithmetic/collection issues and whether downstream tools accept them.",
            "High", "numeric_summary", "Non-finite values may be incompatible with downstream calculations; their origin is not established by this check.")
    outliers = [c for c in columns if c.get("outlier_rate") is not None and c["outlier_rate"] >= 5]
    if outliers:
        add("numeric_outlier_concentration", "IQR review candidates", "Some fields have at least 5% of finite values outside the 1.5-IQR fences.",
            "; ".join(f"{c['name']}: {c['outlier_count']} of {c['outlier_denominator']} finite values ({c['outlier_rate']}%)" for c in outliers),
            "Review distributions, units, and legitimate rare observations. Skew or an IQR flag does not prove a data error.",
            "Moderate", "numeric_outliers", "Extreme observations can influence some analyses; this check does not establish task suitability.")
    findings.sort(key=lambda item: -_severity_rank(item["severity"]))
    return findings


def build_regression_findings(profile):
    """Regression priorities; weak relationships and representation never escalate."""
    feature_profile = dict(profile, columns=[c for c in profile['columns'] if c['role'] == 'feature'],
                           missing_cells=profile['missing_feature_cells'], missing_rate=profile['missing_feature_cell_rate'])
    findings = build_unlabeled_findings(feature_profile)
    for finding in findings:
        if finding['check_id'] == 'missingness':
            finding['check_id'] = 'feature_missingness'
    r = profile['regression']
    t = r['target_statistics']
    base = '/profile/regression/'

    def add(code, title, fact, detail, advice, priority, paths, evidence_type='contextual_review'):
        findings.append({'code': code, 'title': title, 'finding': fact, 'evidence': detail,
            'recommendation': advice, 'severity': priority, 'modeling_impact': 'This evidence informs dataset interpretation before model training.',
            'evidence_type': evidence_type, 'measurement_paths': paths})

    if t:
        path = [base + 'target_statistics']
        if t['missing_count']:
            add('regression_missing_targets','Missing numerical targets',f"{t['missing_count']} of {t['row_count']} targets are missing.",
                'Finite and missing populations are reported separately.', 'Review collection coverage and the selected missing-token policy; exclude nothing automatically.',
                'High' if t['missing_count']/t['row_count'] >= .25 else 'Moderate',path,'observed_fact')
        nonfinite = t['positive_infinity_count'] + t['negative_infinity_count']
        if nonfinite:
            add('regression_nonfinite_targets','Non-finite numerical targets',f'{nonfinite} targets contain infinity values.',
                f"Positive infinity: {t['positive_infinity_count']}; negative infinity: {t['negative_infinity_count']}.",
                'Investigate arithmetic, collection, or sentinel conventions; these values are excluded from finite distributions.', 'High',path,'observed_fact')
        if t['distinct_count'] == 1:
            add('regression_constant_target','Observed constant target','Only one distinct finite target value is represented.',
                f"{t['finite_count']} finite observations.",'Confirm the intended outcome and whether collection or selection explains the absent variation.', 'High',path)
        if t['finite_count'] < 4:
            add('regression_limited_observations','Limited finite target observations',f"Only {t['finite_count']} finite target observations are available.",
                'Methods requiring more support are blocked; no universal training-size threshold is implied.', 'Review collection scope and unavailable methods.', 'Moderate',path)
        if t['precision_reason']:
            add('regression_precision_review','Numerical precision limits','Some floating-point statistics or relationships cannot safely resolve the observed target values.',
                t['precision_reason'],'Review source precision and representation; exact counts and extrema remain available.', 'Moderate',path)
        candidates = [b for b in t['boundary_concentration'] if b['review_candidate']]
        if t['distinct_count'] > 1 and (t['finite_count'] >= 20 and (t['modal_share'] >= 95 or t['iqr'] == 0) or candidates):
            add('regression_target_concentration','Target concentration review','Finite targets concentrate at a common value or boundary.',
                f"Most-common-value share: {t['modal_share']:.2f}%; boundary candidates: {len(candidates)}.",
                'Review legitimate point masses, measurement limits, or collection rules; concentration does not establish clipping or an error.', 'Low',path)
        if t['extremes'] and t['extremes']['rate'] >= 5:
            e=t['extremes']
            add('regression_target_extremes','Extreme target review candidates',f"{e['count']} of {e['denominator']} finite targets exceed 1.5-IQR fences.",
                f"Lower: {e['lower_count']}; upper: {e['upper_count']}.", 'Review units and legitimate tails; an IQR flag does not prove a bad observation.', 'Low',path)
    constraints = r['constraints']
    if constraints and constraints['violation_union_count']:
        add('regression_declared_constraints','Declared target constraint violations',f"{constraints['violation_union_count']} finite targets violate at least one user-declared requirement.",
            '; '.join(f"{v['rule']}: {v['count']}" for v in constraints['rules']),
            'Confirm the declaration and investigate violating observations; no values were removed.', 'High',[base+'constraints'],'declared_constraint_violation')
    unavailable = [c for c,v in r['feature_availability'].items() if v == 'unavailable_at_prediction']
    if unavailable:
        add('regression_declared_availability','Columns declared unavailable at prediction time',f"{count_phrase(len(unavailable), 'feature column')} {agree(len(unavailable), 'is', 'are')} declared unavailable at the intended prediction time.",
            ', '.join(unavailable),'Verify the intended input set and collection timing. This declaration does not establish actual model use or leakage.', 'High',[base+'feature_availability'],'user_declared_context')
    search = r['search']
    cues = r['name_candidates'] if search else []
    if cues:
        add('regression_name_review','Target-related feature names','Some feature names warrant an availability review.',
            ', '.join(c['column'] for c in cues),'Confirm availability and provenance; names alone do not establish leakage, including historical fields.', 'Low',[base+'name_candidates'])
    for availability in ('unavailable_at_prediction','unknown'):
        selected = [(i,g) for i,g in enumerate(r['relationship_groups']) if g['action_eligible'] and g['availability'] == availability]
        if selected:
            add('regression_relationships_'+availability,'Supported target relationships',f"{count_phrase(len(selected), 'distinct target relationship')} {agree(len(selected), 'meets', 'meet')} the support and coverage requirements.",
                '; '.join(g['expression'] for _,g in selected),
                'Verify feature availability and derivation against the intended prediction time; observed algebra alone does not prove leakage.',
                'High' if availability == 'unavailable_at_prediction' else 'Moderate', [base+f'relationship_groups/{i}' for i,_ in selected])
    repeated=r['repeated_inputs']
    if repeated and repeated['varying_group_count']:
        add('regression_repeated_input_variation','Target variation within repeated inputs',f"{count_phrase(repeated['varying_group_count'], 'feature-identical group')} {agree(repeated['varying_group_count'], 'contains', 'contain')} varying finite targets.",
            f"{repeated['varying_rows']} participating rows.", 'Review repeated measurements, stochastic outcomes, omitted context, and recording precision; contradictory labels are not established.', 'Low',[base+'repeated_inputs'])
    if not profile['feature_count']:
        add('regression_no_features','No feature inputs','The dataset contains only the selected target.', 'Feature checks are not applicable.',
            'Confirm whether feature inputs were intended; target evidence remains available.', 'Moderate',['/profile/feature_count'])
    for finding in findings:
        code = finding['code']
        if code.startswith('regression_relationships_'):
            finding['population'] = {'name': 'fully verified relationship overlap scopes', 'denominator': None, 'detail': 'Each witness reports its own overlap and finite-target coverage.'}
            finding['limitations'] = 'Observed identities and supplied availability do not establish actual model use, independent provenance, or leakage.'
            finding['modeling_impact'] = 'An outcome-derived field unavailable at the intended prediction time may invalidate the intended feature set.'
        elif code in {'regression_declared_availability','regression_name_review'}:
            finding['population'] = {'name': 'feature columns', 'denominator': profile['feature_count']}
            finding['limitations'] = 'Feature timing is user-declared or unknown; names alone do not establish availability or leakage.'
            finding['modeling_impact'] = 'Collection timing can determine whether a proposed feature is usable for the intended outcome.'
        elif code.startswith('regression_'):
            all_rows = code in {'regression_missing_targets','regression_nonfinite_targets'}
            finding['population'] = {'name': 'all parsed rows' if all_rows else 'finite targets', 'denominator': profile['row_count'] if all_rows else int(t['finite_count']) if t else None}
            finding['limitations'] = ('Requirements are user-declared; violations do not independently verify the declaration.' if code == 'regression_declared_constraints' else
                'Repeated measurements, stochastic outcomes, omitted context, and recording precision can explain variation; contradictory labels are not established.' if code == 'regression_repeated_input_variation' else
                'Distribution/precision/support observations need context; these rules do not prove recording error or define a training sample requirement.')
            finding['modeling_impact'] = ('Absent or infinite outcomes reduce the population available for numerical outcome analysis.' if all_rows else
                'Declared violations may make observations incompatible with the intended outcome definition.' if code == 'regression_declared_constraints' else
                'Observed variation, support, or repeated-input behavior can affect interpretation of the intended outcome.')
        else:
            check_id = finding['check_id']
            if check_id == 'exact_duplicates':
                finding['population'] = {'name': 'all complete parsed rows, including the target and nulls', 'denominator': profile['row_count']}
            elif check_id == 'feature_missingness':
                finding['population'] = {'name': 'parsed feature cells', 'denominator': profile['row_count'] * profile['feature_count'], 'detail': 'Row-level reach is separately reported using all parsed rows.'}
            elif check_id in {'numeric_summary', 'numeric_outliers'}:
                finding['population'] = {'name': 'finite values by affected feature', 'denominator': None, 'detail': 'Each referenced column retains its own finite denominator; infinity counts use all parsed rows.'}
                finding['measurement_paths'] = []
                for i, c in enumerate(profile['columns']):
                    if c['role'] == 'feature' and (check_id == 'numeric_outliers' and c.get('outlier_rate') is not None and c['outlier_rate'] >= 5 or check_id == 'numeric_summary' and c.get('numeric_summary') and c['numeric_summary']['non_finite_count']):
                        finding['measurement_paths'].append(f'/profile/columns/{i}/' + ('outlier_count' if check_id == 'numeric_outliers' else 'numeric_summary'))
                finding.pop('check_id')
            else:
                finding['population'] = {'name': 'feature columns', 'denominator': profile['feature_count']}
            finding['limitations'] = 'These shared structural observations require context; rarity, repetition, and IQR candidates alone do not prove errors.'
    return sorted(findings,key=lambda f: -_severity_rank(f['severity']))
