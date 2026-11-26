"""regression_dependency_v1: an opt-in feature -> target dependency search for numerical outcomes (Stage 6B, J2).

Founder-approved 2026-11-25 as specified in validation/regression_dependency/DOSSIER.md: strict families only, k = m = 5
with an 80% supported-row share, the identifier gate and the redundancy rule; declared-available dependencies are Low.
Evidence only: it adds a self-describing block and findings, and changes no score, no existing finding and nothing when
off (RegressionOptions.dependency_search is None).

One grouped pass per feature-target pair (one check in DependencyLimits terms) gives three families:
- categorical_determination: every feature value carries exactly one target value (a lookup table, a price list);
- target_interval_coding: the feature's categories occupy non-overlapping target ranges (a binned copy of the target);
- monotone_mapping: the target is a strictly monotone function of a numeric feature, or a monotone step function of it
  with repeated support on the target levels. The form of the function is never named.
"""
import re
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

METHOD_ID = "regression_dependency_v1"
IDENTIFIER_TOKENS = frozenset({"id", "identifier", "uuid", "guid", "key", "index"})
OUTCOME_CUES = {"actual", "final", "outcome", "post", "result", "label", "future"}
SEVERITY = {"unavailable_at_prediction": "High", "available_at_prediction": "Low", "unknown": "Moderate"}
FINDING_CODE = {"unavailable_at_prediction": "regression_dependency_unavailable",
                "available_at_prediction": "regression_dependency_declared_available",
                "unknown": "regression_dependency_availability_unknown"}
MEANING = "Evidence only. No flag means none found within the searched families and gates; unsearched relationships are unknown."


@dataclass(frozen=True)
class Gates:
    min_matched_rows: int = 100          # contextual.GATES["min_matched_rows"]
    min_target_coverage: float = 0.8     # contextual.GATES["min_coverage"]
    min_distinct_targets: int = 5        # regression.ACTION_SUPPORT["minimum_distinct_targets"]
    supported_categories_k: int = 5      # repeated support: k categories ...
    category_support_m: int = 5          # ... of at least m rows each (founder decision D1)
    supported_row_share: float = 0.8     # ... holding at least this share of matched rows
    near_unique_share: float = 0.5
    identifier_unique_share: float = 0.98
    monotone_min_distinct: int = 20
    monotone_min_rows: int = 30          # regression.ACTION_SUPPORT["minimum_overlap"]


GATES = Gates()


def tokens(name):
    separated = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", str(name))
    separated = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", separated)
    return re.findall(r"[a-z0-9]+", separated.lower())


def _numeric(series):
    return pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series)


def _finite(series):
    if not _numeric(series):
        return pd.Series(False, index=series.index)
    return pd.Series(np.isfinite(series.to_numpy(dtype=float, na_value=np.nan)), index=series.index)


def _present(series):
    return _finite(series) if _numeric(series) else series.notna()


def identifier_class(name, n, distinct, declared_identifiers=(), declared_categorical=()):
    """None, or why the feature is excluded from the categorical families (dossier §2.3)."""
    share = distinct / n if n else 0.0
    if name in declared_identifiers:
        return "declared_identifier"
    if set(tokens(name)) & IDENTIFIER_TOKENS and share >= GATES.identifier_unique_share:
        return "R-ID-1"
    if name in declared_categorical:
        return None
    if n >= 2 and distinct == n:
        return "R-ID-2"
    if share >= GATES.near_unique_share:
        return "near_unique"
    return None


def _support(sizes, n):
    supported = sizes >= GATES.category_support_m
    k = int(supported.sum())
    share = float(sizes[supported].sum() / n) if n else 0.0
    return k >= GATES.supported_categories_k and share >= GATES.supported_row_share, k, share


def check_feature(data, target, feature, *, covered=frozenset(), declared_identifiers=(), declared_categorical=()):
    """One grouped pass and the three family decisions for one feature. Returns (check record, example row ordinals)."""
    y_all = data[target]
    ymask = _finite(y_all)
    x = data[feature]
    mask = ymask & _present(x)
    n, population = int(mask.sum()), int(ymask.sum())
    numeric = _numeric(x)
    yv = y_all[mask].to_numpy(dtype=float)
    key = x[mask].to_numpy(dtype=float) if numeric else x[mask].astype(str).to_numpy()
    if n:
        agg = pd.DataFrame({"x": key, "y": yv}).groupby("x", sort=True)["y"].agg(["size", "nunique", "min", "max", "first"])
        levels = pd.Series(yv).value_counts().to_numpy()
    else:
        agg = pd.DataFrame({"size": [], "nunique": [], "min": [], "max": [], "first": []})
        levels = np.array([], dtype=int)
    sizes = agg["size"].to_numpy(dtype=int)
    pure = (agg["nunique"] <= 1).to_numpy()
    ymin, ymax, yfirst = (agg[c].to_numpy(dtype=float) for c in ("min", "max", "first"))
    distinct_x, distinct_y = int(len(agg)), int(len(levels))
    ident = identifier_class(feature, n, distinct_x, declared_identifiers, declared_categorical)
    coverage = n / population if population else 0.0
    check = {"feature": feature, "matched": n, "target_coverage": round(coverage, 4), "distinct_feature_values": distinct_x,
             "distinct_targets": distinct_y, "identifier_exclusion": ident, "families": {}, "flag": None}
    eligible = ident is None
    base_ok = n >= GATES.min_matched_rows and coverage >= GATES.min_target_coverage and distinct_y >= GATES.min_distinct_targets
    support_ok, k_sup, share = _support(sizes, n)
    violating = int((~pure).sum())

    fam = {"eligible": eligible, "violating_categories": violating, "supported_categories": k_sup,
           "supported_row_share": round(share, 4), "singleton_categories": int((sizes == 1).sum())}
    if not eligible:
        fam["reason"] = "identifier_excluded"
    elif not base_ok:
        fam["reason"] = "insufficient_rows_coverage_or_target_variation"
    elif not support_ok:
        fam["reason"] = "insufficient_repeated_support"
    elif violating:
        fam["reason"] = "category_with_several_target_values"
    fam["flagged"] = "reason" not in fam
    check["families"]["categorical_determination"] = fam

    order = np.lexsort((ymax, ymin))
    disjoint = len(order) >= 2 and bool(np.all(ymax[order][:-1] < ymin[order][1:]))
    fam2 = {"eligible": eligible, "disjoint_target_ranges": disjoint}
    if fam["flagged"]:
        fam2["reason"] = "implied_by_categorical_determination"
    elif not eligible:
        fam2["reason"] = "identifier_excluded"
    elif not base_ok:
        fam2["reason"] = "insufficient_rows_coverage_or_target_variation"
    elif not support_ok:
        fam2["reason"] = "insufficient_repeated_support"
    elif not disjoint:
        fam2["reason"] = "overlapping_target_ranges"
    fam2["flagged"] = "reason" not in fam2
    check["families"]["target_interval_coding"] = fam2

    mono_eligible = numeric and ident not in {"R-ID-1", "declared_identifier"}
    fam3 = {"eligible": mono_eligible}
    mono_ok = n >= GATES.monotone_min_rows and coverage >= GATES.min_target_coverage and distinct_x >= GATES.monotone_min_distinct
    if mono_eligible:
        fam3.update(feature_tie_groups=int((sizes > 1).sum()), conflicting_feature_ties=violating)
        if violating == 0 and len(yfirst) >= 2:
            diff = np.diff(yfirst)
            inc, dec = bool((diff > 0).all()), bool((diff < 0).all())
            weak_inc, weak_dec = bool((diff >= 0).all()), bool((diff <= 0).all())
            fam3.update(target_ties_across_feature_values=int((diff == 0).sum()),
                        direction="increasing" if inc or (weak_inc and not dec) else "decreasing" if dec or weak_dec else None,
                        strict=inc or dec, weakly_monotone=weak_inc or weak_dec)
    if not numeric:
        fam3["reason"] = "not_numeric"
    elif not mono_eligible:
        fam3["reason"] = "identifier_excluded"
    elif feature in covered:
        fam3["reason"] = "covered_by_existing_relationship"
    elif not mono_ok:
        fam3["reason"] = "insufficient_distinct_values_rows_or_coverage"
    elif distinct_y < GATES.min_distinct_targets:
        fam3["reason"] = "few_distinct_targets"
    elif fam3.get("conflicting_feature_ties"):
        fam3["reason"] = "feature_tie_with_different_targets"
    elif fam3.get("strict"):
        fam3["form"] = "strict"
    elif fam3.get("weakly_monotone"):
        lk = int((levels >= GATES.category_support_m).sum())
        lshare = float(levels[levels >= GATES.category_support_m].sum() / n) if n else 0.0
        fam3.update(supported_target_levels=lk, supported_level_share=round(lshare, 4))
        if lk >= GATES.supported_categories_k and lshare >= GATES.supported_row_share:
            fam3["form"] = "step"
        else:
            fam3["reason"] = "step_without_repeated_support"
    else:
        fam3["reason"] = "not_monotone"
    fam3["flagged"] = "reason" not in fam3
    check["families"]["monotone_mapping"] = fam3

    for family, rec in check["families"].items():
        if rec["flagged"]:
            check["flag"] = {"family": family, "form": rec.get("form")}
            break
    return check, [int(i) + 1 for i in data.index[mask][:5]]


def wording(flag, feature, target, check, availability):
    """Observation, family caveat and availability clause (dossier §2.5). 'Leakage' is never a conclusion."""
    fam = check["families"]
    family, form = flag["family"], flag.get("form")
    n, cov = check["matched"], round(100 * check["target_coverage"], 1)
    if family == "categorical_determination":
        f = fam[family]
        observed = (f"{feature} determines {target} in this file: each of its {f['supported_categories']} supported categories "
                    f"(at least {GATES.category_support_m} rows each) carries exactly one {target} value ({n:,} rows, {cov}% of finite targets).")
    elif family == "target_interval_coding":
        f = fam["categorical_determination"]
        observed = (f"{feature} records {target} in ranges: its {f['supported_categories']} supported categories occupy non-overlapping "
                    f"{target} intervals ({n:,} rows, {cov}% of finite targets), as a feature binned from the target would.")
    elif form == "step":
        kind = "non-decreasing" if fam["monotone_mapping"]["direction"] == "increasing" else "non-increasing"
        observed = (f"{target} is a {kind} step function of {feature}: over {check['distinct_feature_values']:,} distinct "
                    f"values, each value carries one {target} value and the values never reverse order ({n:,} rows, {cov}% of finite targets).")
    else:
        observed = (f"{target} is a strictly {fam['monotone_mapping']['direction']} function of {feature} over {check['distinct_feature_values']:,} "
                    f"distinct values ({n:,} rows, {cov}% of finite targets). The form of the function is not identified.")
    caveat = (" A monotone relationship is not by itself leakage: unit conversions, cumulative quantities and deterministic pricing "
              "rules are monotone." if family == "monotone_mapping" else
              " A deterministic rule can be legitimate (a price list, a lookup table)." if family == "categorical_determination" else
              " A feature can separate the target legitimately, or be derived from it.")
    if availability == "unavailable_at_prediction":
        meaning = f" You declared {feature} unavailable at the prediction point, so evaluation that uses it is invalid for the declared objective."
    elif availability == "available_at_prediction":
        meaning = (f" You declared {feature} available at the prediction point; a legitimate deterministic rule leaves little for a model to learn. "
                   "Verify the declaration and that the rule holds outside this file.")
    else:
        meaning = f" Whether this is leakage or a legitimate rule depends on when {feature} becomes known; declare its availability."
    return observed + caveat + meaning


def search(data, target, limits, *, features=None, availability=None, covered=frozenset(), declared_identifiers=(),
           declared_categorical=(), budget=None, checkpoint=None):
    """The versioned dependency_search block for one target. `budget` is shared across the targets of one run."""
    availability = availability or {}
    features = [c for c in data.columns if c != target] if features is None else [c for c in features if c != target]
    target_tokens = set(tokens(target))
    cue = lambda c: bool(target_tokens & set(tokens(c)) or set(tokens(c)) & OUTCOME_CUES)
    ordered = sorted(features, key=lambda c: not cue(c))
    budget = {"features": set(), "checks": 0, "row_work": 0} if budget is None else budget
    y = data[target]
    population = int(_finite(y).sum())
    block = {"method_id": METHOD_ID, "target": target, "status": "completed", "gates": asdict(GATES),
             "limits": {"max_features": limits.max_features, "max_checks": limits.max_checks, "max_row_work": limits.max_row_work},
             "checks": [], "flags": [], "unsearched_features": [], "identifier_exclusions": {},
             "covered_by_relationships": sorted(set(covered) & set(features)), "meaning": MEANING}
    if not _numeric(y) or population == 0 or y[_finite(y)].nunique() < GATES.min_distinct_targets:
        block.update(status="not_assessable", reason=f"The target has no finite values or fewer than {GATES.min_distinct_targets} distinct finite values.",
                     unsearched_features=ordered)
    else:
        for i, name in enumerate(ordered):
            new = name not in budget["features"]
            if (new and len(budget["features"]) >= limits.max_features) or budget["checks"] >= limits.max_checks \
                    or budget["row_work"] + len(data) > limits.max_row_work:
                block["unsearched_features"] = ordered[i:]
                block["status"] = "bounded"
                break
            if checkpoint:
                try:
                    checkpoint("regression dependency search")
                except Exception as exc:  # a cooperative safeguard: keep what was searched, name what was not
                    if getattr(exc, "code", None) != "resource_limit":
                        raise
                    block.update(status="partial", reason=str(exc), unsearched_features=ordered[i:])
                    break
            budget["features"].add(name)
            budget["checks"] += 1
            budget["row_work"] += len(data)
            check, rows = check_feature(data, target, name, covered=covered, declared_identifiers=declared_identifiers,
                                        declared_categorical=declared_categorical)
            block["checks"].append(check)
            if check["identifier_exclusion"]:
                block["identifier_exclusions"].setdefault(check["identifier_exclusion"], []).append(name)
            if check["flag"]:
                state = availability.get(name, "unknown")
                block["flags"].append({"feature": name, **check["flag"], "availability": state, "severity": SEVERITY[state],
                                       "finding_code": FINDING_CODE[state], "row_ordinals": rows,
                                       "wording": wording(check["flag"], name, target, check, state)})
    block["identifier_exclusion_counts"] = {k: len(v) for k, v in block["identifier_exclusions"].items()}
    block["budget_used"] = {"features": len(budget["features"]), "checks": budget["checks"], "row_work": budget["row_work"]}
    return block


def covered_features(relationships):
    """Features the existing search already verified as an exact copy or affine identity (the redundancy rule)."""
    return frozenset(r["columns"][0] for r in relationships or []
                     if r.get("method") in {"exact_copy", "affine_identity"} and len(r.get("columns") or []) == 1 and r.get("verified_rows", 1))
