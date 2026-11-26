"""Prototype of regression_dependency_v1 (J2, research only).

This is NOT product code. Nothing under src/ imports it, and it changes no result.
It exists so that every number in DOSSIER.md can be reproduced.

One grouped pass per feature-target pair (one "check" in DependencyLimits terms) yields the
statistics for three families of feature -> target dependency:

  categorical_determination  every category of the feature carries exactly one target value
                             (a lookup table, a price list, a code that encodes the answer)
  target_interval_coding     the feature's categories occupy non-overlapping target ranges
                             (the feature looks like a binned copy of the target)
  monotone_mapping           the target is a strictly monotone function of a numeric feature
                             ("strict": log, rank, power, reciprocal ...), or a monotone step
                             function of it with repeated support ("step": y = bin(x))

Statistics and decisions are separated (`feature_stats` / `decide`) so that gate grids and
ablations re-use one pass. Decisions are evidence only: no score, no finding is changed.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field, asdict

import numpy as np
import pandas as pd

METHOD_ID = "regression_dependency_v1"

# Identifier tokens: target_guidance.IDENTIFIER_TOKENS plus the R-ID-1 tokens of the plan (key, index).
IDENTIFIER_TOKENS = frozenset({"id", "identifier", "uuid", "guid", "key", "index"})


@dataclass(frozen=True)
class Gates:
    # Reused from contextual.GATES (context_v1) and regression.ACTION_SUPPORT.
    min_matched_rows: int = 100          # contextual GATES["min_matched_rows"]
    min_target_coverage: float = 0.8     # contextual GATES["min_coverage"] / ACTION_SUPPORT 80%
    min_distinct_targets: int = 5        # ACTION_SUPPORT["minimum_distinct_targets"]
    # Repeated support (extends contextual GATES["min_category_support"] = 5).
    supported_categories_k: int = 5
    category_support_m: int = 5
    supported_row_share: float = 0.8
    # Identifier handling.
    near_unique_share: float = 0.5
    identifier_unique_share: float = 0.98  # annotations.feature_semantics / m4 name_id rule
    # Monotone mapping.
    monotone_min_distinct: int = 20
    monotone_min_rows: int = 30          # ACTION_SUPPORT["minimum_overlap"]
    # Tolerant variants: measured in the dossier, NOT proposed for v1.
    tolerant_eta2: float = 0.999
    tolerant_spearman: float = 0.999


@dataclass(frozen=True)
class Limits:
    # contracts.DependencyLimits defaults.
    max_features: int = 64
    max_checks: int = 128
    max_row_work: int = 200_000_000


@dataclass(frozen=True)
class Variant:
    """Ablation switches. The proposal is Variant()."""
    identifier_gate: bool = True
    singletons_excluded: bool = True      # support counted only from categories with >= m rows
    contextual_v1_support: bool = False   # every category >= m rows (context_v1 rule) instead of k/m/80%
    naive: bool = False                   # no support gates at all (>= 2 categories)
    redundancy_rule: bool = True          # skip features already verified as copy/affine
    step_family: bool = True
    tolerant: bool = False                # also emit near-determination / near-monotone flags


SEVERITY = {"unavailable_at_prediction": "High", "available_at_prediction": "Low", "unknown": "Moderate"}
FINDING_CODE = {"unavailable_at_prediction": "regression_dependency_unavailable",
                "available_at_prediction": "regression_dependency_declared_available",
                "unknown": "regression_dependency_availability_unknown"}


def tokens(name):
    """Same splitting as target_guidance.column_name_tokens."""
    separated = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", str(name))
    separated = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", separated)
    return re.findall(r"[a-z0-9]+", separated.lower())


def is_numeric(series):
    return pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series)


def finite(series):
    if not is_numeric(series):
        return pd.Series(False, index=series.index)
    values = series.to_numpy(dtype=float, na_value=np.nan)
    return pd.Series(np.isfinite(values), index=series.index)


def present(series):
    return finite(series) if is_numeric(series) else series.notna()


def identifier_class(name, n, distinct, gates, declared_identifiers=(), declared_categorical=()):
    """None, or the reason the feature is excluded from the categorical families."""
    share = distinct / n if n else 0.0
    if name in declared_identifiers:
        return "declared_identifier"
    if set(tokens(name)) & IDENTIFIER_TOKENS and share >= gates.identifier_unique_share:
        return "R-ID-1"
    if name in declared_categorical:
        return None
    if n >= 2 and distinct == n:
        return "R-ID-2"
    if share >= gates.near_unique_share:
        return "near_unique"
    return None


@dataclass
class Stats:
    feature: str
    numeric: bool
    matched: int
    population: int
    distinct_x: int
    distinct_y: int
    identifier: str | None
    covered: bool
    sizes: np.ndarray = field(repr=False)          # rows per feature value
    pure: np.ndarray = field(repr=False)           # feature value carries one target value
    ymin: np.ndarray = field(repr=False)
    ymax: np.ndarray = field(repr=False)
    yfirst: np.ndarray = field(repr=False)         # ordered by feature value when numeric
    ylevel_sizes: np.ndarray = field(repr=False)   # rows per target value
    ss_within: np.ndarray = field(repr=False)      # within-category sum of squares (standardised y)
    ymean: np.ndarray = field(repr=False)
    spearman: float | None = None
    example_rows: list = field(default_factory=list)


def feature_stats(data, target, feature, *, gates=Gates(), covered=frozenset(), declared_identifiers=(),
                  declared_categorical=(), want_spearman=False):
    y_all = data[target]
    ymask = finite(y_all)
    x = data[feature]
    mask = ymask & present(x)
    n = int(mask.sum())
    population = int(ymask.sum())
    numeric = is_numeric(x)
    xv = x[mask]
    yv = y_all[mask].to_numpy(dtype=float)
    key = xv.to_numpy(dtype=float) if numeric else xv.astype(str).to_numpy()
    if n:
        sd = float(np.std(yv)) or 1.0
        z = (yv - float(np.mean(yv))) / sd
        frame = pd.DataFrame({"x": key, "y": yv, "z": z, "z2": z * z})
        g = frame.groupby("x", sort=True)
        agg = g["y"].agg(["size", "nunique", "min", "max", "first"])
        zs = g["z"].agg(["sum", "mean"])
        z2 = g["z2"].sum()
        ss_within = (z2 - zs["sum"] ** 2 / agg["size"]).clip(lower=0).to_numpy()
        levels = pd.Series(yv).value_counts().to_numpy()
        distinct_y = int(len(levels))
    else:
        agg = pd.DataFrame({"size": [], "nunique": [], "min": [], "max": [], "first": []})
        zs = pd.DataFrame({"mean": []})
        ss_within = np.array([])
        levels = np.array([], dtype=int)
        distinct_y = 0
    distinct_x = int(len(agg))
    ident = identifier_class(feature, n, distinct_x, gates, declared_identifiers, declared_categorical)
    spearman = None
    if want_spearman and numeric and n >= 3:
        rx = pd.Series(key).rank().to_numpy()
        ry = pd.Series(yv).rank().to_numpy()
        if np.std(rx) > 0 and np.std(ry) > 0:
            spearman = float(np.corrcoef(rx, ry)[0, 1])
    return Stats(feature=feature, numeric=numeric, matched=n, population=population, distinct_x=distinct_x,
                 distinct_y=distinct_y, identifier=ident, covered=feature in covered,
                 sizes=agg["size"].to_numpy(dtype=int), pure=(agg["nunique"] <= 1).to_numpy(),
                 ymin=agg["min"].to_numpy(dtype=float), ymax=agg["max"].to_numpy(dtype=float),
                 yfirst=agg["first"].to_numpy(dtype=float), ylevel_sizes=levels, ss_within=ss_within,
                 ymean=zs["mean"].to_numpy(dtype=float), spearman=spearman,
                 example_rows=[int(i) + 1 for i in data.index[mask][:5]])


def _support(sizes, n, gates, variant):
    """(gate passed, supported categories, share of matched rows in supported categories)."""
    m, k = gates.category_support_m, gates.supported_categories_k
    if variant.naive:
        return len(sizes) >= 2, int(len(sizes)), 1.0
    if variant.contextual_v1_support:
        ok = len(sizes) >= 2 and (sizes.min() if len(sizes) else 0) >= m
        return bool(ok), int((sizes >= m).sum()), float(sizes[sizes >= m].sum() / n) if n else 0.0
    supported = sizes >= m if variant.singletons_excluded else sizes >= 1
    k_sup = int(supported.sum())
    share = float(sizes[supported].sum() / n) if n else 0.0
    return k_sup >= k and share >= gates.supported_row_share, k_sup, share


def decide(s: Stats, gates=Gates(), variant=Variant()):
    """Apply the gates to one feature's statistics. Returns the check record (flag or reasons)."""
    n, N = s.matched, s.population
    coverage = n / N if N else 0.0
    check = {"feature": s.feature, "matched": n, "target_coverage": round(coverage, 4), "distinct_feature_values": s.distinct_x,
             "distinct_targets": s.distinct_y, "identifier_exclusion": s.identifier, "families": {}, "flag": None}
    cat_eligible = s.identifier is None or not variant.identifier_gate
    base_ok = n >= gates.min_matched_rows and coverage >= gates.min_target_coverage and s.distinct_y >= gates.min_distinct_targets
    support_ok, k_sup, share = _support(s.sizes, n, gates, variant)
    violating = int((~s.pure).sum())

    # Categorical determination.
    fam = {"eligible": cat_eligible, "violating_categories": violating, "supported_categories": k_sup,
           "supported_row_share": round(share, 4), "singleton_categories": int((s.sizes == 1).sum())}
    if not cat_eligible:
        fam["reason"] = "identifier_excluded"
    elif not base_ok:
        fam["reason"] = "insufficient_rows_coverage_or_target_variation"
    elif not support_ok:
        fam["reason"] = "insufficient_repeated_support"
    elif violating:
        fam["reason"] = "category_with_several_target_values"
    fam["flagged"] = "reason" not in fam
    check["families"]["categorical_determination"] = fam

    # Target interval coding (binned target): categories occupy disjoint target ranges.
    order = np.lexsort((s.ymax, s.ymin))
    disjoint = len(order) >= 2 and bool(np.all(s.ymax[order][:-1] < s.ymin[order][1:]))
    fam2 = {"eligible": cat_eligible, "disjoint_target_ranges": disjoint}
    if fam["flagged"]:
        fam2["reason"] = "implied_by_categorical_determination"
    elif not cat_eligible:
        fam2["reason"] = "identifier_excluded"
    elif not base_ok:
        fam2["reason"] = "insufficient_rows_coverage_or_target_variation"
    elif not support_ok:
        fam2["reason"] = "insufficient_repeated_support"
    elif not disjoint:
        fam2["reason"] = "overlapping_target_ranges"
    fam2["flagged"] = "reason" not in fam2
    check["families"]["target_interval_coding"] = fam2

    # Monotone mapping.
    num_eligible = s.numeric and (not variant.identifier_gate or s.identifier not in {"R-ID-1", "declared_identifier"})
    fam3 = {"eligible": num_eligible}
    mono_ok = n >= gates.monotone_min_rows and coverage >= gates.min_target_coverage and s.distinct_x >= gates.monotone_min_distinct
    if num_eligible:
        conflicts = int((~s.pure).sum())
        fam3.update(feature_tie_groups=int((s.sizes > 1).sum()), conflicting_feature_ties=conflicts)
        if conflicts == 0 and len(s.yfirst) >= 2:
            diff = np.diff(s.yfirst)
            inc, dec = bool((diff > 0).all()), bool((diff < 0).all())
            weak_inc, weak_dec = bool((diff >= 0).all()), bool((diff <= 0).all())
            fam3.update(target_ties_across_feature_values=int((diff == 0).sum()),
                        direction="increasing" if inc or (weak_inc and not dec) else "decreasing" if dec or weak_dec else None,
                        strict=inc or dec, weakly_monotone=weak_inc or weak_dec)
    if not s.numeric:
        fam3["reason"] = "not_numeric"
    elif not num_eligible:
        fam3["reason"] = "identifier_excluded"
    elif s.covered and variant.redundancy_rule:
        fam3["reason"] = "covered_by_existing_relationship"
    elif not mono_ok:
        fam3["reason"] = "insufficient_distinct_values_rows_or_coverage"
    elif s.distinct_y < gates.min_distinct_targets:
        fam3["reason"] = "few_distinct_targets"
    elif fam3.get("conflicting_feature_ties"):
        fam3["reason"] = "feature_tie_with_different_targets"
    elif fam3.get("strict"):
        fam3["form"] = "strict"
    elif fam3.get("weakly_monotone") and variant.step_family:
        m, k = gates.category_support_m, gates.supported_categories_k
        lv = s.ylevel_sizes
        lk = int((lv >= m).sum()); lshare = float(lv[lv >= m].sum() / n) if n else 0.0
        fam3.update(supported_target_levels=lk, supported_level_share=round(lshare, 4))
        if lk >= k and lshare >= gates.supported_row_share:
            fam3["form"] = "step"
        else:
            fam3["reason"] = "step_without_repeated_support"
    else:
        fam3["reason"] = "not_monotone" if not fam3.get("weakly_monotone") else "target_ties_break_strictness"
    fam3["flagged"] = "reason" not in fam3
    check["families"]["monotone_mapping"] = fam3

    # Tolerant variants (measured only).
    if variant.tolerant:
        tol = {}
        if cat_eligible and base_ok and support_ok and not fam["flagged"] and not fam2["flagged"]:
            supported = s.sizes >= gates.category_support_m if variant.singletons_excluded else s.sizes >= 1
            sw = float(s.ss_within[supported].sum())
            # total SS of the supported rows around their own mean (z already standardised on all matched rows)
            sizes, means = s.sizes[supported], s.ymean[supported]
            total_mean = float((sizes * means).sum() / sizes.sum())
            sb = float((sizes * (means - total_mean) ** 2).sum())
            eta2 = sb / (sb + sw) if sb + sw > 0 else 0.0
            tol["eta2_supported"] = round(eta2, 6)
            tol["near_determination"] = eta2 >= gates.tolerant_eta2
        if num_eligible and mono_ok and not fam3["flagged"] and not (s.covered and variant.redundancy_rule) and s.spearman is not None:
            tol["spearman"] = round(s.spearman, 6)
            tol["near_monotone"] = abs(s.spearman) >= gates.tolerant_spearman
        check["tolerant"] = tol

    for family, rec in check["families"].items():
        if rec["flagged"]:
            check["flag"] = {"family": family, "form": rec.get("form"), "strength": "exact"}
            break
    if check["flag"] is None and variant.tolerant:
        tol = check.get("tolerant", {})
        if tol.get("near_determination"):
            check["flag"] = {"family": "categorical_determination", "form": "near", "strength": "near"}
        elif tol.get("near_monotone"):
            check["flag"] = {"family": "monotone_mapping", "form": "near", "strength": "near"}
    return check


def wording(flag, feature, target, check, availability):
    fam = check["families"]
    family, form = flag["family"], flag.get("form")
    n, cov = check["matched"], round(100 * check["target_coverage"], 1)
    if family == "categorical_determination":
        f = fam[family]
        observed = (f"{feature} determines {target} in this file: each of its {f['supported_categories']} supported categories "
                    f"(at least {Gates().category_support_m} rows each) carries exactly one {target} value ({n:,} rows, {cov}% of finite targets).")
    elif family == "target_interval_coding":
        f = fam["categorical_determination"]
        observed = (f"{feature} records {target} in ranges: its {f['supported_categories']} supported categories occupy non-overlapping "
                    f"{target} intervals ({n:,} rows, {cov}% of finite targets), as a feature binned from the target would.")
    elif form == "step":
        f = fam["monotone_mapping"]
        kind = "non-decreasing" if f["direction"] == "increasing" else "non-increasing"
        observed = (f"{target} is a {kind} step function of {feature}: over {check['distinct_feature_values']} distinct "
                    f"values, each value carries one {target} value and the values never reverse order ({n:,} rows, {cov}% of finite targets).")
    else:
        f = fam["monotone_mapping"]
        observed = (f"{target} is a strictly {f['direction']} function of {feature} over {check['distinct_feature_values']} distinct values "
                    f"({n:,} rows, {cov}% of finite targets). The form of the function is not identified.")
    monotone_caveat = (" A monotone relationship is not by itself leakage: unit conversions, cumulative quantities and deterministic pricing "
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
    return observed + monotone_caveat + meaning


def search(data, target, *, features=None, availability=None, covered=frozenset(), gates=Gates(), limits=Limits(),
           variant=Variant(), declared_identifiers=(), declared_categorical=(), budget=None):
    """The versioned dependency_search block for one target. `budget` is shared across targets of one run."""
    availability = availability or {}
    features = [c for c in data.columns if c != target] if features is None else list(features)
    target_tokens = set(tokens(target))
    cue = lambda c: bool(target_tokens & set(tokens(c)) or set(tokens(c)) & {"actual", "final", "outcome", "post", "result", "label", "future"})
    ordered = sorted(features, key=lambda c: not cue(c))  # same ordering idea as regression.relationship_steps
    budget = {"features": set(), "checks": 0, "row_work": 0} if budget is None else budget
    y = data[target]
    population = int(finite(y).sum())
    block = {"method_id": METHOD_ID, "target": target, "status": "completed", "gates": asdict(gates), "limits": asdict(limits),
             "variant": asdict(variant), "checks": [], "flags": [], "unsearched_features": [],
             "identifier_exclusions": {}, "covered_by_relationships": sorted(set(covered) & set(features)),
             "meaning": "Evidence only. No flag means none found within the searched families and gates; unsearched relationships are unknown."}
    if not is_numeric(y) or population == 0 or pd.Series(y[finite(y)]).nunique() < gates.min_distinct_targets:
        block.update(status="not_assessable", reason="Target has no finite values or fewer than "
                     f"{gates.min_distinct_targets} distinct finite values.", unsearched_features=ordered)
        return block
    for i, name in enumerate(ordered):
        new_feature = name not in budget["features"]
        if (new_feature and len(budget["features"]) >= limits.max_features) or budget["checks"] >= limits.max_checks \
                or budget["row_work"] + len(data) > limits.max_row_work:
            block["unsearched_features"] = ordered[i:]
            block["status"] = "bounded"
            break
        budget["features"].add(name); budget["checks"] += 1; budget["row_work"] += len(data)
        s = feature_stats(data, target, name, gates=gates, covered=covered, declared_identifiers=declared_identifiers,
                          declared_categorical=declared_categorical, want_spearman=variant.tolerant)
        check = decide(s, gates, variant)
        block["checks"].append(check)
        if s.identifier:
            block["identifier_exclusions"].setdefault(s.identifier, []).append(name)
        if check["flag"]:
            state = availability.get(name, "unknown")
            block["flags"].append({"feature": name, **check["flag"], "availability": state, "severity": SEVERITY[state],
                                   "finding_code": FINDING_CODE[state], "row_ordinals": s.example_rows,
                                   "wording": wording(check["flag"], name, target, check, state)})
    block["identifier_exclusion_counts"] = {k: len(v) for k, v in block["identifier_exclusions"].items()}
    block["budget_used"] = {"features": len(budget["features"]), "checks": budget["checks"], "row_work": budget["row_work"]}
    return block
