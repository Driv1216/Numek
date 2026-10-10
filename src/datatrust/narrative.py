from datatrust.wording import agree, be_verb, count_phrase


def build_narrative(
    profile: dict, scores: dict, risks: list, findings: list
) -> dict:
    """Build deterministic report interpretation from established evidence."""
    principal = risks[0] if risks else None
    return {
        "overall_assessment": _overall_assessment(scores),
        "score_explanation": _score_explanation(scores),
        "principal_evidence_summary": _principal_evidence_summary(principal),
        "missingness_interpretation": _missingness_interpretation(profile),
        "target_interpretation": _target_interpretation(profile),
        "duplicate_interpretation": _duplicate_interpretation(profile),
        "leakage_interpretation": _leakage_interpretation(profile),
        "finding_count": len(findings),
    }


def _overall_assessment(scores: dict) -> str:
    return (
        f"The final reliability score is {scores['overall']} "
        f"({scores['risk_level']} Risk) under the current DataTrust methodology."
    )


def _score_explanation(scores: dict) -> str:
    evidence_score = scores["evidence_score"]
    overall = scores["overall"]
    guardrails = scores["guardrails"]
    if not guardrails:
        return (
            f"Evidence score {evidence_score}; final score {overall}. "
            "No guardrail changed the evidence score."
        )

    details = "; ".join(
        f"{guardrail['code'].replace('_', ' ').capitalize()} (cap {guardrail['cap']}): "
        f"{guardrail['explanation']}"
        for guardrail in guardrails
    )
    return (
        f"Evidence score {evidence_score} → final score {overall} after applied "
        f"guardrails: {details}"
    )


def _principal_evidence_summary(principal: dict) -> str:
    if not principal:
        return "The current checks did not produce an executive finding."
    return f"{principal['finding']} {principal['modeling_impact']}"


def _missingness_interpretation(profile: dict) -> str:
    feature_columns = [
        column for column in profile["columns"] if column["role"] == "feature"
    ]
    affected = [column for column in feature_columns if column["missing_count"] > 0]
    total_missing = sum(column["missing_count"] for column in feature_columns)
    if total_missing == 0:
        return "No missing feature values were detected by the current null-value checks."

    total_feature_cells = profile["row_count"] * len(feature_columns)
    missing_feature_cell_rate = round(
        (total_missing / total_feature_cells) * 100, 2
    )
    if (total_missing / total_feature_cells) * 100 < 1:
        return (
            f"Missingness is minimal: {total_missing} of {total_feature_cells} feature "
            f"cells ({missing_feature_cell_rate}%) are missing, affecting "
            f"{profile['missing_feature_row_rate']}% of rows."
        )

    dominant = max(affected, key=lambda column: column["missing_count"])
    dominant_share = round((dominant["missing_count"] / total_missing) * 100, 2)
    if dominant_share >= 70:
        return (
            f"Missingness is concentrated in {dominant['name']}, which accounts for "
            f"{dominant_share}% of all missing feature cells. "
            f"{profile['missing_feature_row_rate']}% of rows contain at least one "
            "missing feature."
        )
    return (
        f"Missing feature values are spread across {count_phrase(len(affected), 'column')}, and "
        f"{profile['missing_feature_row_rate']}% of rows contain at least one missing "
        "feature."
    )


def _target_interpretation(profile: dict) -> str:
    class_count = profile["class_balance"]["class_count"]
    majority = profile["majority_class_baseline"]
    if class_count <= 1:
        return (
            "The labeled target contains only one observed class, so the current "
            "classification checks treat target variation as unusable."
        )
    if majority >= 75:
        return (
            f"The majority class represents {majority}% of labeled rows, meeting the "
            "current 75% threshold for a target-imbalance finding."
        )
    return (
        f"The majority class represents {majority}% of labeled rows, below the current "
        "75% target-imbalance finding threshold. This statement does not establish "
        "model quality."
    )


def _duplicate_interpretation(profile: dict) -> str:
    duplicates = profile["duplicate_rows"]
    conflicts = profile.get("conflicting_label_group_count", 0)
    if duplicates == 0:
        text = "No exact duplicate rows were detected."
    else:
        text = (
            f"{count_phrase(duplicates, 'repeated row')} {be_verb(duplicates, past=True)} detected across "
            f"{count_phrase(profile['duplicate_group_count'], 'exact duplicate group')}."
        )
    if conflicts:
        text += (
            f" {count_phrase(conflicts, 'feature-identical group')} "
            f"{agree(conflicts, 'contains', 'contain')} conflicting non-missing "
            "target labels and require context review."
        )
    else:
        text += " No feature-identical conflicting-label groups were detected."
    return text


def _leakage_interpretation(profile: dict) -> str:
    strong = profile["strong_leakage_candidates"]
    review_only = profile["review_only_leakage_candidates"]
    if not strong and not review_only:
        return (
            "No name-based leakage candidates were detected. This heuristic does not "
            "verify when every feature becomes available."
        )

    parts = []
    if strong:
        parts.append(
            f"{count_phrase(len(strong), 'strong name-based candidate')}: {', '.join(strong[:3])}"
        )
    if review_only:
        parts.append(
            f"{count_phrase(len(review_only), 'review-only name prompt')}: "
            f"{', '.join(review_only[:3])}"
        )
    return "; ".join(parts) + ". Confirm feature availability with domain context."


def build_unlabeled_narrative(profile: dict, findings: list) -> dict:
    return {
        "overall_assessment": "General dataset profiling summarizes observed input evidence. No overall scoring policy is defined for unlabeled profiling.",
        "principal_evidence_summary": findings[0]["finding"] if findings else "No data-profile review findings were generated by the completed M1 checks. Parsing warnings and coverage require separate review.",
        "recommended_action": findings[0]["recommendation"] if findings else "Review parsing disclosures, unavailable checks, and the intended data use before drawing broader conclusions.",
        "missingness_interpretation": _missingness_interpretation(profile),
        "duplicate_interpretation": ("Exact duplicate analysis was unavailable; no uniqueness conclusion was generated."
                                     if profile["duplicate_rows"] is None else
                                     f"{profile['duplicate_rows']} repeated rows beyond each group's first occurrence; legitimate repetition is possible."),
        "finding_count": len(findings),
    }


def build_regression_narrative(profile, findings):
    r=profile['regression']; t=r['target_statistics']
    evidence = (f"{t['finite_count']} of {t['row_count']} targets are finite, with {t['distinct_count']} distinct finite values." if t else 'Target numerical diagnostics are unavailable; review check execution.')
    return {'overall_assessment': 'Regression dataset evidence is available for review. Priorities describe investigation needs, not a score or readiness verdict.',
            'principal_evidence_summary': evidence,
            'recommended_action': findings[0]['recommendation'] if findings else 'Review declared expectations, parsing warnings, and the scope of completed checks.',
            'relationship_interpretation': 'Small or sparse relationships remain qualified technical evidence. No relationship conclusion covers unsearched candidates.',
            'duplicate_interpretation': 'Exact repetition and target variation within repeated inputs require context; automatic deduplication or label-error conclusions are not warranted.',
            'finding_count':len(findings)}
