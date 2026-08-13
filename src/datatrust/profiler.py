import math
import re
import warnings
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from datatrust.target_guidance import assess_target_options, assess_target_series


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


def load_csv_dataset(
    dataset_path: Path, *, usecols: Optional[List[str]] = None, nrows: Optional[int] = None
) -> pd.DataFrame:
    """Read a CSV and translate parser/filesystem failures into product errors."""
    path = Path(dataset_path)
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")
    if not path.is_file():
        raise ValueError(f"Dataset path is not a file: {path}")

    try:
        return pd.read_csv(path, usecols=usecols, nrows=nrows)
    except pd.errors.EmptyDataError as exc:
        raise ValueError("Dataset is empty and cannot be analyzed.") from exc
    except pd.errors.ParserError as exc:
        raise ValueError("CSV could not be parsed as a comma-delimited file with a header.") from exc
    except UnicodeDecodeError as exc:
        raise ValueError("CSV must use a text encoding that pandas can read (UTF-8 recommended).") from exc
    except PermissionError as exc:
        raise ValueError(f"Dataset cannot be read: {path}") from exc
    except OSError as exc:
        raise ValueError(f"Dataset could not be read: {exc}") from exc


def inspect_csv_dataset(dataset_path: Path, preview_rows: int = 10) -> dict:
    """Return upload-stage facts without requiring a target selection."""
    data = load_csv_dataset(dataset_path)
    if len(data) == 0:
        raise ValueError("Dataset is empty and cannot be analyzed.")
    if len(data.columns) == 0:
        raise ValueError("Dataset must contain at least one named column.")

    preview = []
    for record in data.head(preview_rows).to_dict(orient="records"):
        preview.append({str(name): _display_scalar(value) for name, value in record.items()})

    return {
        "row_count": int(len(data)),
        "column_count": int(len(data.columns)),
        "columns": [str(column) for column in data.columns],
        "preview": preview,
        "target_options": assess_target_options(data),
    }


def inspect_classification_target(dataset_path: Path, target: str) -> dict:
    """Return target confirmation facts using the same rules as full profiling."""
    data = load_csv_dataset(dataset_path)
    if target not in data.columns:
        raise ValueError(f"Target column '{target}' was not found in the dataset.")
    if len(data) == 0:
        raise ValueError("Dataset is empty and cannot be analyzed.")

    target_missing_count = int(data[target].isna().sum())
    labeled_row_count = int(data[target].notna().sum())
    if labeled_row_count == 0:
        raise ValueError(f"Target column '{target}' has no usable labels.")
    distribution = _target_distribution(data[target])
    return {
        "target": target,
        "row_count": int(len(data)),
        "labeled_row_count": labeled_row_count,
        "target_missing_count": target_missing_count,
        "target_missing_rate": _safe_percentage(target_missing_count, len(data)),
        "target_distribution": distribution,
        "class_count": len(distribution),
        "classification_subtype": _classification_subtype(len(distribution)),
        "suitability": assess_target_series(data[target], target),
    }


def profile_dataset(dataset_path: Path, target: str, task: str) -> dict:
    if task != "classification":
        raise ValueError("DataTrust supports task='classification' only.")

    data = load_csv_dataset(dataset_path)
    if target not in data.columns:
        raise ValueError(f"Target column '{target}' was not found in the dataset.")

    row_count = int(len(data))
    if row_count == 0:
        raise ValueError("Dataset is empty and cannot be analyzed.")

    target_missing_count = int(data[target].isna().sum())
    labeled_row_count = row_count - target_missing_count
    if labeled_row_count == 0:
        raise ValueError(f"Target column '{target}' has no usable labels.")

    column_count = int(len(data.columns))
    feature_names = [column for column in data.columns if column != target]
    duplicate_rows = int(data.duplicated().sum())
    duplicate_rate = _safe_percentage(duplicate_rows, row_count)
    duplicate_details = _duplicate_details(data, feature_names, target)

    columns = [_profile_column(data, column, target) for column in data.columns]
    feature_columns = [column for column in columns if column["role"] == "feature"]
    numeric_feature_count = sum(bool(column["is_numeric"]) for column in feature_columns)
    missing_cells = int(data.isna().sum().sum())
    total_cells = max(row_count * column_count, 1)
    missing_rate = round((missing_cells / total_cells) * 100, 2)
    row_missingness = _feature_row_missingness(data, feature_names)

    target_distribution = _target_distribution(data[target])
    class_balance = _class_balance(target_distribution)
    class_count = class_balance["class_count"]
    minority_percentage = class_balance["minority_class_percentage"]
    majority_to_minority_ratio = (
        round(class_balance["largest_class_percentage"] / minority_percentage, 2)
        if minority_percentage > 0
        else None
    )
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
        "feature_count": len(feature_names),
        "numeric_feature_count": numeric_feature_count,
        "non_numeric_feature_count": len(feature_names) - numeric_feature_count,
        "duplicate_rows": duplicate_rows,
        "duplicate_rate": duplicate_rate,
        **duplicate_details,
        "missing_cells": missing_cells,
        "missing_rate": missing_rate,
        **row_missingness,
        "severe_missing_columns": severe_missing_columns,
        "columns": columns,
        "labeled_row_count": labeled_row_count,
        "target_missing_count": target_missing_count,
        "target_missing_rate": _safe_percentage(target_missing_count, row_count),
        "target_distribution": target_distribution,
        "class_balance": class_balance,
        "classification_subtype": _classification_subtype(class_count),
        "majority_class_baseline": class_balance["largest_class_percentage"],
        "majority_to_minority_ratio": majority_to_minority_ratio,
        "leakage_candidates": leakage_candidates,
        "strong_leakage_candidates": strong_leakage_candidates,
        "review_only_leakage_candidates": review_only_leakage_candidates,
        "leakage_details": leakage_details,
    }


def _profile_column(data: pd.DataFrame, column: str, target: str) -> Dict[str, object]:
    series = data[column]
    row_count = max(len(series), 1)
    missing_count = int(series.isna().sum())
    non_null_count = int(series.notna().sum())
    unique_count = int(series.nunique(dropna=True))
    dtype = str(series.dtype)
    missing_rate = round((missing_count / row_count) * 100, 2)
    unique_rate = round((unique_count / row_count) * 100, 2)
    non_null = series.dropna()

    is_numeric = bool(pd.api.types.is_numeric_dtype(series))
    numeric_summary = _numeric_summary(non_null, row_count) if is_numeric else None
    outlier_count = _numeric_outliers(non_null) if is_numeric else 0
    outlier_rate = round((outlier_count / row_count) * 100, 2)

    constant = unique_count <= 1
    top_value_count, top_value_rate, raw_top_value = _top_value_details(series)
    near_constant = unique_count > 1 and top_value_rate >= 95
    high_cardinality = not is_numeric and unique_rate >= 80 and unique_count >= 20
    top_value_hidden = bool(high_cardinality and raw_top_value is not None)
    top_value_is_missing = bool(raw_top_value is not None and pd.isna(raw_top_value))
    top_value = None
    if raw_top_value is not None and not top_value_hidden and not top_value_is_missing:
        top_value = str(raw_top_value)

    return {
        "name": column,
        "dtype": dtype,
        "role": "target" if column == target else "feature",
        "is_numeric": is_numeric,
        "missing_count": missing_count,
        "missing_rate": missing_rate,
        "non_null_count": non_null_count,
        "unique_count": unique_count,
        "unique_rate": unique_rate,
        "constant": constant,
        "near_constant": near_constant,
        "high_cardinality": high_cardinality,
        "top_value": top_value,
        "top_value_count": top_value_count,
        "top_value_rate": top_value_rate,
        "top_value_hidden": top_value_hidden,
        "top_value_is_missing": top_value_is_missing,
        "outlier_count": outlier_count,
        "outlier_rate": outlier_rate,
        "numeric_summary": numeric_summary,
    }


def _feature_row_missingness(data: pd.DataFrame, feature_names: list) -> dict:
    if not feature_names:
        return {
            "missing_feature_row_count": 0,
            "missing_feature_row_rate": 0.0,
            "rows_with_1_missing_feature": 0,
            "rows_with_2_missing_features": 0,
            "rows_with_3_plus_missing_features": 0,
        }

    per_row = data[feature_names].isna().sum(axis=1)
    impacted = int((per_row > 0).sum())
    return {
        "missing_feature_row_count": impacted,
        "missing_feature_row_rate": _safe_percentage(impacted, len(data)),
        "rows_with_1_missing_feature": int((per_row == 1).sum()),
        "rows_with_2_missing_features": int((per_row == 2).sum()),
        "rows_with_3_plus_missing_features": int((per_row >= 3).sum()),
    }


def _duplicate_details(data: pd.DataFrame, feature_names: list, target: str) -> dict:
    repeated = data[data.duplicated(keep=False)]
    if repeated.empty:
        duplicate_group_count = 0
        largest_duplicate_group_size = 0
    else:
        group_sizes = repeated.value_counts(dropna=False)
        duplicate_group_count = int(len(group_sizes))
        largest_duplicate_group_size = int(group_sizes.max())

    conflicting_group_count = 0
    conflicting_row_count = 0
    if feature_names:
        labeled = data[data[target].notna()]
        grouped = labeled.groupby(feature_names, dropna=False, sort=False)[target].agg(
            label_count="nunique", row_count="size"
        )
        conflicts = grouped[grouped["label_count"] > 1]
        conflicting_group_count = int(len(conflicts))
        conflicting_row_count = int(conflicts["row_count"].sum()) if not conflicts.empty else 0

    return {
        "duplicate_group_count": duplicate_group_count,
        "largest_duplicate_group_size": largest_duplicate_group_size,
        "conflicting_label_group_count": conflicting_group_count,
        "conflicting_label_row_count": conflicting_row_count,
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


def _classification_subtype(class_count: int) -> str:
    if class_count <= 1:
        return "single-class"
    if class_count == 2:
        return "binary"
    return "multiclass"


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
                f"name contains outcome-like wording: {', '.join(matched_strong)}"
                if matched_strong
                else f"name combines target terms {', '.join(sorted(target_overlap))} "
                "with an outcome qualifier"
            )
            candidates.append({"column": column, "classification": "strong", "reason": reason})
        elif tokens.intersection(REVIEW_ONLY_LEAKAGE_TOKENS) or target_overlap:
            reason = (
                "generic status-like name; verify when the value becomes available"
                if tokens.intersection(REVIEW_ONLY_LEAKAGE_TOKENS)
                else f"name references target terms {', '.join(sorted(target_overlap))}"
            )
            candidates.append({"column": column, "classification": "review_only", "reason": reason})
    return candidates


def _tokens(value: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", str(value).lower())


def _contains_phrase(tokens: List[str], phrase_tokens: List[str]) -> bool:
    width = len(phrase_tokens)
    return any(tokens[index : index + width] == phrase_tokens for index in range(len(tokens) - width + 1))


def _numeric_outliers(series: pd.Series) -> int:
    # Preserve the established scoring behavior exactly; finite-only descriptive
    # statistics are calculated separately in _numeric_summary.
    if len(series) < 4:
        return 0
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        q1 = series.quantile(0.25)
        q3 = series.quantile(0.75)
    iqr = q3 - q1
    if iqr == 0:
        return 0
    lower = q1 - (1.5 * iqr)
    upper = q3 + (1.5 * iqr)
    return int(((series < lower) | (series > upper)).sum())


def _numeric_summary(series: pd.Series, row_count: int) -> dict:
    numeric = pd.to_numeric(series, errors="coerce")
    finite_mask = numeric.map(lambda value: bool(math.isfinite(float(value))) if pd.notna(value) else False)
    finite = numeric[finite_mask]
    non_finite_count = int((numeric.notna() & ~finite_mask).sum())
    zero_count = int((finite == 0).sum())
    negative_count = int((finite < 0).sum())

    def statistic(name: str):
        if finite.empty:
            return None
        if name == "min":
            value = finite.min()
        elif name == "q1":
            value = finite.quantile(0.25)
        elif name == "median":
            value = finite.median()
        elif name == "q3":
            value = finite.quantile(0.75)
        else:
            value = finite.max()
        return _python_scalar(value)

    return {
        "min": statistic("min"),
        "q1": statistic("q1"),
        "median": statistic("median"),
        "q3": statistic("q3"),
        "max": statistic("max"),
        "zero_count": zero_count,
        "zero_rate": _safe_percentage(zero_count, row_count),
        "negative_count": negative_count,
        "negative_rate": _safe_percentage(negative_count, row_count),
        "non_finite_count": non_finite_count,
        "non_finite_rate": _safe_percentage(non_finite_count, row_count),
    }


def _top_value_details(series: pd.Series) -> tuple:
    counts = series.value_counts(dropna=False)
    if counts.empty:
        return 0, 0.0, None
    count = int(counts.iloc[0])
    return count, _safe_percentage(count, len(series)), counts.index[0]


def _display_scalar(value) -> str:
    if pd.isna(value):
        return ""
    return str(value)


def _python_scalar(value):
    if value is None or pd.isna(value):
        return None
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float):
        return round(value, 6)
    return value


def _safe_percentage(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100, 2)
