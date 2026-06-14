import re
from pathlib import Path
from typing import Dict, List

import pandas as pd


STRONG_LEAKAGE_PHRASES = (
    "approved",
    "approval",
    "bad_loan",
    "charged_off",
    "collection",
    "defaulted",
    "delinquent",
    "outcome",
    "paid",
    "recovered",
    "repayment",
    "settled",
)
REVIEW_ONLY_LEAKAGE_TOKENS = {"status"}
OUTCOME_QUALIFIERS = {"actual", "final", "label", "outcome", "post", "result"}
PRIOR_CONTEXT_TOKENS = {"historical", "past", "prior", "previous"}


def profile_dataset(dataset_path: Path, target: str, task: str) -> dict:
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found: {dataset_path}")

    try:
        data = pd.read_csv(dataset_path)
    except pd.errors.EmptyDataError as exc:
        raise ValueError("Dataset is empty and cannot be analyzed.") from exc

    if target not in data.columns:
        raise ValueError(f"Target column '{target}' was not found in the dataset.")

    if task != "classification":
        raise ValueError("DataTrust V1 supports task='classification' only.")

    row_count = int(len(data))
    if row_count == 0:
        raise ValueError("Dataset is empty and cannot be analyzed.")

    target_missing_count = int(data[target].isna().sum())
    labeled_row_count = row_count - target_missing_count
    if labeled_row_count == 0:
        raise ValueError(f"Target column '{target}' has no usable labels.")

    column_count = int(len(data.columns))
    duplicate_rows = int(data.duplicated().sum())
    duplicate_rate = _safe_percentage(duplicate_rows, row_count)

    columns = [_profile_column(data, column, target) for column in data.columns]
    missing_cells = int(data.isna().sum().sum())
    total_cells = max(row_count * column_count, 1)
    missing_rate = round((missing_cells / total_cells) * 100, 2)

    target_distribution = _target_distribution(data[target])
    class_balance = _class_balance(target_distribution)
    leakage_details = _leakage_candidates(data.columns, target)
    strong_leakage_candidates = [
        item["column"] for item in leakage_details if item["classification"] == "strong"
    ]
    review_only_leakage_candidates = [
        item["column"] for item in leakage_details if item["classification"] == "review_only"
    ]
    leakage_candidates = strong_leakage_candidates + review_only_leakage_candidates
    severe_missing_columns = [
        column["name"]
        for column in columns
        if column["role"] == "feature" and column["missing_rate"] >= 50
    ]

    return {
        "dataset_path": str(dataset_path),
        "target": target,
        "task": task,
        "row_count": row_count,
        "column_count": column_count,
        "duplicate_rows": duplicate_rows,
        "duplicate_rate": duplicate_rate,
        "missing_cells": missing_cells,
        "missing_rate": missing_rate,
        "severe_missing_columns": severe_missing_columns,
        "columns": columns,
        "labeled_row_count": labeled_row_count,
        "target_missing_count": target_missing_count,
        "target_missing_rate": _safe_percentage(target_missing_count, row_count),
        "target_distribution": target_distribution,
        "class_balance": class_balance,
        "leakage_candidates": leakage_candidates,
        "strong_leakage_candidates": strong_leakage_candidates,
        "review_only_leakage_candidates": review_only_leakage_candidates,
        "leakage_details": leakage_details,
    }


def _profile_column(data: pd.DataFrame, column: str, target: str) -> Dict[str, object]:
    series = data[column]
    row_count = max(len(series), 1)
    missing_count = int(series.isna().sum())
    unique_count = int(series.nunique(dropna=True))
    dtype = str(series.dtype)
    missing_rate = round((missing_count / row_count) * 100, 2)
    unique_rate = round((unique_count / row_count) * 100, 2)
    non_null = series.dropna()

    is_numeric = bool(pd.api.types.is_numeric_dtype(series))
    outlier_count = _numeric_outliers(non_null) if is_numeric else 0
    outlier_rate = round((outlier_count / row_count) * 100, 2)

    constant = unique_count <= 1
    near_constant = unique_count > 1 and _top_value_share(series) >= 95
    high_cardinality = not is_numeric and unique_rate >= 80 and unique_count >= 20

    return {
        "name": column,
        "dtype": dtype,
        "role": "target" if column == target else "feature",
        "missing_count": missing_count,
        "missing_rate": missing_rate,
        "unique_count": unique_count,
        "unique_rate": unique_rate,
        "constant": constant,
        "near_constant": near_constant,
        "high_cardinality": high_cardinality,
        "outlier_count": outlier_count,
        "outlier_rate": outlier_rate,
    }


def _target_distribution(series: pd.Series) -> List[dict]:
    counts = series.dropna().value_counts()
    total = max(int(series.notna().sum()), 1)
    distribution = []
    for value, count in counts.items():
        distribution.append(
            {
                "label": str(value),
                "count": int(count),
                "percentage": round((int(count) / total) * 100, 2),
            }
        )
    return distribution


def _class_balance(distribution: List[dict]) -> dict:
    if not distribution:
        return {"class_count": 0, "largest_class_percentage": 0.0, "minority_class_percentage": 0.0}

    percentages = [item["percentage"] for item in distribution]
    return {
        "class_count": len(distribution),
        "largest_class_percentage": max(percentages),
        "minority_class_percentage": min(percentages),
    }


def _leakage_candidates(columns, target: str) -> List[dict]:
    candidates = []
    target_tokens = set(_tokens(target))
    for column in columns:
        if column == target:
            continue
        column_tokens = _tokens(column)
        tokens = set(column_tokens)
        matched_strong = [
            term for term in STRONG_LEAKAGE_PHRASES if _contains_phrase(column_tokens, _tokens(term))
        ]
        target_overlap = target_tokens.intersection(tokens)

        if matched_strong and tokens.intersection(PRIOR_CONTEXT_TOKENS):
            candidates.append(
                {
                    "column": column,
                    "classification": "review_only",
                    "reason": "prior or historical outcome-like name; verify availability for the current target",
                }
            )
        elif matched_strong or (target_overlap and tokens.intersection(OUTCOME_QUALIFIERS)):
            reason = (
                f"name contains outcome-like phrase(s): {', '.join(matched_strong)}"
                if matched_strong
                else f"name combines target term(s) {', '.join(sorted(target_overlap))} "
                "with an outcome qualifier"
            )
            candidates.append(
                {"column": column, "classification": "strong", "reason": reason}
            )
        elif tokens.intersection(REVIEW_ONLY_LEAKAGE_TOKENS) or target_overlap:
            reason = (
                "generic status-like name; verify when the value becomes available"
                if tokens.intersection(REVIEW_ONLY_LEAKAGE_TOKENS)
                else f"name references target term(s) {', '.join(sorted(target_overlap))}"
            )
            candidates.append(
                {"column": column, "classification": "review_only", "reason": reason}
            )
    return candidates


def _tokens(value: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", str(value).lower())


def _contains_phrase(tokens: List[str], phrase_tokens: List[str]) -> bool:
    width = len(phrase_tokens)
    return any(tokens[index : index + width] == phrase_tokens for index in range(len(tokens) - width + 1))


def _numeric_outliers(series: pd.Series) -> int:
    if len(series) < 4:
        return 0
    q1 = series.quantile(0.25)
    q3 = series.quantile(0.75)
    iqr = q3 - q1
    if iqr == 0:
        return 0
    lower = q1 - (1.5 * iqr)
    upper = q3 + (1.5 * iqr)
    return int(((series < lower) | (series > upper)).sum())


def _top_value_share(series: pd.Series) -> float:
    counts = series.value_counts(dropna=False)
    if counts.empty:
        return 0.0
    return round((int(counts.iloc[0]) / max(len(series), 1)) * 100, 2)


def _safe_percentage(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100, 2)
