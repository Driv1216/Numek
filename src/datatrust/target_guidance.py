import re
from typing import Iterable, List

import pandas as pd


EXPLICIT_OUTCOME_TOKENS = {"target", "label", "outcome"}
EVENT_OUTCOME_TOKENS = {
    "approved",
    "approval",
    "default",
    "defaulted",
    "survived",
    "disease",
    "diagnosis",
    "churn",
    "fraud",
    "subscribed",
    "conversion",
    "converted",
    "attrition",
}
GENERIC_OUTCOME_TOKENS = {"risk", "class", "result", "response"}
SUPPRESSING_TOKENS = {
    "prior",
    "previous",
    "historical",
    "past",
    "score",
    "probability",
    "prob",
    "prediction",
    "predicted",
    "estimate",
    "estimated",
    "feature",
    "input",
}
IDENTIFIER_TOKENS = {"id", "identifier", "uuid", "guid"}
TARGET_GROUP_ORDER = ("outcome_word", "small_class_set", "advanced", "disabled")


def assess_target_series(series: pd.Series, name: str) -> dict:
    """Describe one column's suitability for the classification target picker."""
    labeled_count = int(series.notna().sum())
    missing_count = int(series.isna().sum())
    unique_count = int(series.nunique(dropna=True))
    unique_rate = _percentage(unique_count, labeled_count)
    is_numeric = bool(pd.api.types.is_numeric_dtype(series))
    tokens = column_name_tokens(name)
    token_set = set(tokens)
    matched_outcome_tokens = sorted(
        token_set.intersection(EXPLICIT_OUTCOME_TOKENS | EVENT_OUTCOME_TOKENS)
    )
    matched_generic_tokens = sorted(token_set.intersection(GENERIC_OUTCOME_TOKENS))
    matched_suppressing_tokens = sorted(token_set.intersection(SUPPRESSING_TOKENS))
    matched_identifier_tokens = sorted(token_set.intersection(IDENTIFIER_TOKENS))
    class_ceiling = min(20, max(2, labeled_count // 2))

    reason_codes: List[str] = []
    disabled = labeled_count == 0
    requires_override = False

    if disabled:
        group = "disabled"
        reason_codes.append("no_usable_labels")
        explanation = "No usable values are available for this target."
        selector_explanation = explanation
    elif unique_count <= 1:
        group = "advanced"
        requires_override = True
        reason_codes.append("single_class")
        explanation = (
            f"{name} has only {unique_count} distinct value across {labeled_count} "
            "labeled rows. Classification requires at least two outcomes."
        )
        selector_explanation = "Only one outcome is represented."
    else:
        near_unique = labeled_count >= 20 and unique_rate >= 95
        identifier_named = bool(matched_identifier_tokens)
        if near_unique or identifier_named:
            group = "advanced"
            requires_override = True
            if identifier_named:
                reason_codes.append("identifier_name")
            if near_unique:
                reason_codes.append("near_unique")
            if identifier_named and near_unique:
                concern = "its name looks identifier-like and its values are nearly unique"
            elif identifier_named:
                concern = "its name looks identifier-like"
            else:
                concern = "its values are nearly unique"
            explanation = (
                f"{name} has {unique_count} distinct values across {labeled_count} labeled "
                f"rows ({unique_rate}% distinct); {concern}. Using it as the prediction "
                "outcome may not produce a meaningful classification reliability assessment."
            )
            selector_explanation = "This looks more like an identifier than a classification outcome."
        elif unique_count > class_ceiling:
            group = "advanced"
            requires_override = True
            if is_numeric:
                reason_codes.append("continuous_numeric")
                explanation = (
                    f"{name} has {unique_count} distinct numeric values across "
                    f"{labeled_count} labeled rows ({unique_rate}% distinct), above the "
                    f"small-outcome guidance limit of {class_ceiling}. It may represent a "
                    "continuous measure rather than a classification outcome."
                )
                selector_explanation = "This looks more like a continuous measurement than a classification outcome."
            else:
                reason_codes.append("many_categories")
                explanation = (
                    f"{name} has {unique_count} distinct categories across {labeled_count} "
                    f"labeled rows ({unique_rate}% distinct), above the small-outcome "
                    f"guidance limit of {class_ceiling}. Using it would create many "
                    "classification outcomes."
                )
                selector_explanation = "This has too many categories for an ordinary classification outcome."
        else:
            outcome_signal = bool(matched_outcome_tokens)
            signal_suppressed = outcome_signal and bool(matched_suppressing_tokens)
            if outcome_signal and not signal_suppressed:
                group = "outcome_word"
                reason_codes.extend(("small_class_set", "outcome_name_signal"))
                explanation = (
                    f"Its name contains outcome-style wording and it has {unique_count} "
                    "observed values. DataTrust has not selected it for you."
                )
                selector_explanation = "Its name suggests an outcome."
            else:
                group = "small_class_set"
                reason_codes.append("small_class_set")
                if signal_suppressed:
                    reason_codes.append("outcome_signal_suppressed")
                    explanation = (
                        f"It has {unique_count} observed values. Outcome-style wording was "
                        "not used for prioritization because the name also describes prior "
                        "or derived information."
                    )
                    selector_explanation = "Could be used as a classification outcome, but its name describes prior or derived information."
                elif matched_generic_tokens:
                    reason_codes.append("generic_outcome_word")
                    explanation = (
                        f"It has {unique_count} observed values. Generic wording such as "
                        f"{', '.join(matched_generic_tokens)} is not enough to infer intent."
                    )
                    selector_explanation = "Could be used as a classification outcome, but its name does not establish the intended outcome."
                else:
                    explanation = (
                        f"It has {unique_count} observed values, which is structurally "
                        "compatible with a small-set classification target."
                    )
                    selector_explanation = "Could be used as a classification outcome."

    return {
        "name": str(name),
        "dtype": str(series.dtype),
        "is_numeric": is_numeric,
        "labeled_row_count": labeled_count,
        "missing_count": missing_count,
        "missing_rate": _percentage(missing_count, len(series)),
        "observed_distinct_count": unique_count,
        "observed_class_count": unique_count,
        "unique_rate": unique_rate,
        "small_class_ceiling": class_ceiling,
        "name_tokens": tokens,
        "matched_outcome_tokens": matched_outcome_tokens,
        "matched_generic_tokens": matched_generic_tokens,
        "matched_suppressing_tokens": matched_suppressing_tokens,
        "group": group,
        "reason_codes": reason_codes,
        "explanation": explanation,
        "selector_explanation": selector_explanation,
        "requires_override": requires_override,
        "disabled": disabled,
    }


def assess_target_options(data: pd.DataFrame) -> List[dict]:
    """Return target assessments grouped predictably while preserving source order."""
    options = [assess_target_series(data[column], str(column)) for column in data.columns]
    return sorted(options, key=lambda option: TARGET_GROUP_ORDER.index(option["group"]))


def column_name_tokens(value: str) -> List[str]:
    """Split common identifier styles into lowercase whole tokens."""
    separated = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", str(value))
    separated = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", separated)
    return re.findall(r"[a-z0-9]+", separated.lower())


def group_target_options(options: Iterable[dict]) -> dict:
    """Return presentation groups without changing option order."""
    grouped = {group: [] for group in TARGET_GROUP_ORDER}
    for option in options:
        grouped[option["group"]].append(option)
    return grouped


def _percentage(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100, 2)
