"""Contextual diagnostics (context_v1): evidence that depends on what you declare about the data.

Four kinds of statement are kept strictly apart:
  candidates     values that commonly encode absence or special cases, found by fixed rules; never applied
  declarations   exactly what you declared, with the raw values each declaration covers
  observed       what the data shows about declared and candidate codes: co-occurrence, condition exceptions
  interpreted    each declared column's applicable population, recomputed beside the untouched raw evidence
plus a bounded target-dependency search and availability findings that depend on the declared prediction point.
Nothing here changes parsed values, the profile, the findings list or any score. Pipeline or model use is never
inferred: only a supplied after-dataset can demonstrate which columns survive preprocessing (M4 before/after).
"""
from __future__ import annotations

import math

import pandas as pd

from datatrust.contracts import ContextOptions, DependencyLimits
from datatrust.wording import count_phrase

VERSION = "context_v1"
RULES = "candidate_rules_v1"
# Text values that commonly stand for an absent or unknown value. Matched case-insensitively after trimming.
PLACEHOLDER_TOKENS = ("unknown", "unk", "n/a", "na", "none", "null", "missing", "?", "-", "--", "not known",
                      "not available", "undefined", "unspecified", "nan", "blank")
# Numeric codes commonly used as sentinels. A code is a candidate only when it lies outside the range of every
# other finite value in the column and covers at least 5 rows and 1% of finite values (conservative by design).
SENTINEL_CODES = (-1, -9, -99, -999, -9999, 9, 99, 999, 9999, 99999)
MISSING_MEANINGS = {"not_collected", "refused", "censored"}
SCORE_EFFECT = "Evidence only: contextual findings (context_v1) do not change any score or legacy finding."
GATES = {"min_category_support": 5, "min_matched_rows": 100, "min_coverage": 0.8, "min_class_rows": 5}


def _finite(series):
    values = pd.to_numeric(series, errors="coerce")
    return values[values.map(lambda v: isinstance(v, (int, float)) and math.isfinite(v))]


def _is_numeric(series):
    return pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series)


def _refs(mask, limit=5):
    return [int(i) + 1 for i in mask[mask].index[:limit]]


def _rate(count, total):
    return round(100 * count / total, 2) if total else None


# ——— Candidates ———

def candidates(data, columns):
    found = []
    for name in columns:
        series = data[name]
        if _is_numeric(series):
            finite = _finite(series)
            for code in SENTINEL_CODES:
                hits = int((finite == code).sum())
                others = finite[finite != code]
                if hits < 5 or hits < 0.01 * len(finite) or others.nunique() < 2:
                    continue
                if code < others.min() or code > others.max():
                    found.append({"column": name, "value": code, "kind": "numeric_sentinel", "rows": hits, "rate": _rate(hits, len(series)),
                                  "rule": f"{RULES}: outside the range of every other finite value ({_num(others.min())} to {_num(others.max())}), at least 5 rows and 1% of finite values"})
        else:
            text = series.dropna().astype(str)
            normalised = text.str.strip().str.lower()
            for token in PLACEHOLDER_TOKENS:
                mask = normalised == token
                hits = int(mask.sum())
                if hits:
                    value = text[mask].value_counts().index[0]
                    found.append({"column": name, "value": value, "kind": "text_placeholder", "rows": hits, "rate": _rate(hits, len(series)),
                                  "rule": f"{RULES}: value matches the placeholder vocabulary"})
    return found


def _num(value):
    value = float(value)
    return int(value) if value.is_integer() else value


# ——— Declarations and interpreted populations ———

def _code_masks(series, declaration):
    """Rows matching each declared placeholder or sentinel: {(value, meaning): mask}."""
    masks = {}
    text = series.astype("string")
    for token, meaning in declaration.placeholders.items():
        masks[(token, meaning)] = (text == token).fillna(False)
    numeric = pd.to_numeric(series, errors="coerce")
    for sentinel in declaration.sentinels:
        masks[(sentinel["value"], sentinel["meaning"])] = (numeric == sentinel["value"]).fillna(False)
    return masks


def _condition(data, condition):
    """(true, unevaluable) masks for an applies_when declaration."""
    column, op, value = condition["column"], condition["op"], condition.get("value")
    series = data[column]
    if op == "is_null":
        return series.isna(), pd.Series(False, index=series.index)
    if op == "not_null":
        return series.notna(), pd.Series(False, index=series.index)
    if isinstance(value, str):
        left = series.astype("string")
    else:
        left = pd.to_numeric(series, errors="coerce")
    unevaluable = left.isna()
    compare = {"=": left == value, "!=": left != value, ">": left > value, ">=": left >= value, "<": left < value, "<=": left <= value}[op]
    return compare.fillna(False).astype(bool) & ~unevaluable, unevaluable


def interpret(data, name, declaration):
    series = data[name]
    rows = len(series)
    masks = _code_masks(series, declaration)
    declared = pd.Series(False, index=series.index)
    by_meaning = {}
    codes = []
    for (value, meaning), mask in masks.items():
        count = int(mask.sum())
        codes.append({"value": value, "meaning": meaning, "rows": count, "observed": bool(count)})
        by_meaning[meaning] = by_meaning.get(meaning, 0) + count
        declared |= mask
    parser_missing = series.isna()
    applicable = ~declared & ~parser_missing
    record = {"rows": rows, "parser_missing_rows": int(parser_missing.sum()), "declared_codes": codes, "rows_by_meaning": by_meaning,
              "declared_missing_rows": sum(v for k, v in by_meaning.items() if k in MISSING_MEANINGS),
              "structural_absence_rows": by_meaning.get("not_applicable", 0)}
    if declaration.applies_when:
        true, unevaluable = _condition(data, declaration.applies_when)
        not_applicable_codes = pd.Series(False, index=series.index)
        for (value, meaning), mask in masks.items():
            if meaning == "not_applicable":
                not_applicable_codes |= mask
        present = ~true & ~unevaluable & ~declared & ~parser_missing
        absent = true & not_applicable_codes
        record["condition"] = {**declaration.applies_when, "rows_true": int(true.sum()), "rows_false": int((~true & ~unevaluable).sum()),
                               "rows_unevaluable": int(unevaluable.sum()),
                               "exceptions": {"value_present_where_declared_not_to_apply": int(present.sum()), "present_row_refs": _refs(present),
                                              "not_applicable_code_where_condition_holds": int(absent.sum()), "absent_row_refs": _refs(absent)}}
        applicable &= true
    record["applicable_rows"] = int(applicable.sum())
    values = series[applicable]
    if _is_numeric(series):
        from datatrust.profiler import finite_numeric_evidence
        evidence = finite_numeric_evidence(pd.to_numeric(values, errors="coerce"))
        record["applicable_numeric"] = {"finite_count": evidence["finite_count"], "summary": evidence["numeric_summary"],
                                        "outlier_count": evidence["outlier_count"], "outlier_rate": evidence["outlier_rate"],
                                        "outlier_denominator": evidence["outlier_denominator"], "outlier_method": evidence["outlier_method"],
                                        "outlier_unavailable_reason": evidence["outlier_unavailable_reason"]}
    else:
        top = values.astype(str).value_counts().head(5)
        record["applicable_top_values"] = [{"value": k, "rows": int(v)} for k, v in top.items()]
    if declaration.unit:
        record["unit"] = declaration.unit
    return record


def co_occurrence(data, indicators):
    """Cross-column pairs of codes that occur in (almost) the same rows."""
    masks = []
    for item in indicators[:32]:
        series = data[item["column"]]
        if isinstance(item["value"], str):
            mask = (series.astype("string") == item["value"]).fillna(False)
        else:
            mask = (pd.to_numeric(series, errors="coerce") == item["value"]).fillna(False)
        masks.append((item, mask.astype(bool)))
    pairs = []
    for i, (a, ma) in enumerate(masks):
        for b, mb in masks[i + 1:]:
            if a["column"] == b["column"]:
                continue
            ca, cb, both = int(ma.sum()), int(mb.sum()), int((ma & mb).sum())
            if both >= 5 and both >= 0.95 * max(ca, cb):
                only_a, only_b = ma & ~mb, mb & ~ma
                pairs.append({"a": {"column": a["column"], "value": a["value"], "rows": ca}, "b": {"column": b["column"], "value": b["value"], "rows": cb},
                              "both": both, "a_only": int(only_a.sum()), "b_only": int(only_b.sum()),
                              "a_only_row_refs": _refs(only_a), "b_only_row_refs": _refs(only_b),
                              "relation": "same rows" if not only_a.any() and not only_b.any() else "same rows with exceptions"})
    return {"pairs": pairs, "indicators_examined": len(masks), "indicators_unexamined": max(0, len(indicators) - 32),
            "rule": "cross-column code pairs sharing at least 95% of their rows and at least 5 rows"}


# ——— Target dependency ———

def dependency_search(data, target, features, limits: DependencyLimits):
    t = data[target]
    rows = len(t)
    labelled = t.notna()
    result = {"target": target, "method": "categorical functional dependency (M4 gates) and quantitative class separation",
              "gates": GATES, "limits": {"max_features": limits.max_features, "max_checks": limits.max_checks, "max_row_work": limits.max_row_work},
              "checks": [], "unsearched_features": [], "status": "completed"}
    if int(labelled.sum()) < GATES["min_matched_rows"]:
        result.update(status="not_assessable", reason=f"Fewer than {GATES['min_matched_rows']} labelled rows; the gates cannot be met.",
                      unsearched_features=list(features))
        return result
    work = 0
    for index, name in enumerate(features):
        if index >= limits.max_features or len(result["checks"]) >= limits.max_checks or work + rows > limits.max_row_work:
            result["unsearched_features"] = list(features[index:])
            result["status"] = "bounded"
            break
        work += rows
        x = data[name]
        if _is_numeric(x):
            numeric = pd.to_numeric(x, errors="coerce")
            valid = labelled & numeric.map(lambda v: isinstance(v, (int, float)) and math.isfinite(v))
            groups = numeric[valid].groupby(t[valid].astype(str))
            ranges = sorted(((float(g.min()), float(g.max()), int(len(g)), str(k)) for k, g in groups), key=lambda r: r[0])
            separated = len(ranges) >= 2 and all(ranges[i][1] < ranges[i + 1][0] for i in range(len(ranges) - 1))
            matched = int(valid.sum())
            check = {"feature": name, "method": "quantitative_class_separation", "matched": matched, "coverage": round(matched / rows, 4),
                     "classes": len(ranges), "minimum_class_rows": min((r[2] for r in ranges), default=0), "separated": separated,
                     "class_ranges": [{"class": r[3], "min": _num(r[0]), "max": _num(r[1]), "rows": r[2]} for r in ranges[:10]]}
            check["flagged"] = separated and check["minimum_class_rows"] >= GATES["min_class_rows"] and matched >= GATES["min_matched_rows"] and check["coverage"] >= GATES["min_coverage"]
        else:
            valid = labelled & x.notna()
            frame = pd.DataFrame({"x": x[valid].astype(str), "t": t[valid].astype(str)})
            per = frame.groupby("x")["t"].agg(["nunique", "size"])
            matched = int(valid.sum())
            check = {"feature": name, "method": "categorical_functional_dependency", "matched": matched, "coverage": round(matched / rows, 4),
                     "source_categories": int(len(per)), "minimum_category_support": int(per["size"].min()) if len(per) else 0,
                     "violating_categories": int((per["nunique"] > 1).sum())}
            check["flagged"] = (check["source_categories"] >= 2 and check["minimum_category_support"] >= GATES["min_category_support"]
                                and matched >= GATES["min_matched_rows"] and check["coverage"] >= GATES["min_coverage"] and check["violating_categories"] == 0)
        result["checks"].append(check)
    result["row_work"] = work
    result["flagged"] = [c["feature"] for c in result["checks"] if c["flagged"]]
    return result


# ——— Findings ———

def _finding(code, title, severity, finding, evidence, recommendation, impact, columns):
    return {"code": code, "title": title, "severity": severity, "finding": finding, "evidence": evidence, "recommendation": recommendation,
            "modeling_impact": impact, "evidence_type": "contextual_review", "score_effect": SCORE_EFFECT, "version": VERSION, "columns": columns}


def _findings(block, covered):
    findings = []
    availability = block["availability"]
    search = block.get("dependency_search") or {}
    flagged = search.get("flagged", [])
    features = set(block.get("features", []))
    # Columns an existing finding already reports (regression and M3 availability contracts) are not repeated.
    unavailable = [c for c, v in availability.items() if v == "unavailable_at_prediction" and c in features and c not in covered]
    if unavailable:
        findings.append(_finding("declared_unavailable_feature", "Features declared unavailable at prediction time", "High",
                                 f"{count_phrase(len(unavailable), 'feature')} you declared unavailable at the prediction point {'is' if len(unavailable) == 1 else 'are'} present among the features.",
                                 "; ".join(unavailable), "Exclude these features from training and evaluation, or correct the declaration.",
                                 "A feature known only after the prediction point makes evaluation optimistic and fails in use.", unavailable))
    for column in flagged:
        state = availability.get(column, "unknown")
        check = next(c for c in search["checks"] if c["feature"] == column)
        detail = (f"{column}: each of {check['source_categories']} categories maps to exactly one target value ({check['matched']:,} rows, coverage {check['coverage']})"
                  if check["method"] == "categorical_functional_dependency" else
                  f"{column}: the target classes occupy non-overlapping value ranges ({check['matched']:,} rows, coverage {check['coverage']})")
        if state == "unavailable_at_prediction":
            findings.append(_finding("target_dependency_unavailable", "Target-determining feature declared unavailable", "High",
                                     f"{column} determines the target and is declared unavailable at the prediction point.", detail,
                                     "Exclude it; evaluation that uses it is invalid for the declared objective.",
                                     "The feature carries the answer and will not exist when the prediction is made.", [column]))
        elif state == "available_at_prediction":
            findings.append(_finding("deterministic_predictor_declared_available", "Deterministic predictor declared available", "Low",
                                     f"{column} determines the target and you declared it available at the prediction point.", detail,
                                     "Verify the availability decision and that the relationship holds outside this file.",
                                     "A legitimate deterministic predictor leaves little for a model to learn; if the declaration is wrong it is leakage.", [column]))
        else:
            findings.append(_finding("dependency_availability_unknown", "Target-determining feature with undeclared availability", "Moderate",
                                     f"{column} determines the target and its availability at the prediction point was not declared.", detail,
                                     "Declare when this feature becomes available before relying on it.",
                                     "Whether this is leakage or a legitimate rule depends on the prediction point.", [column]))
    for name, record in block["interpreted"].items():
        condition = record.get("condition")
        if condition and (condition["exceptions"]["value_present_where_declared_not_to_apply"] or condition["exceptions"]["not_applicable_code_where_condition_holds"]):
            ex = condition["exceptions"]
            findings.append(_finding("declared_condition_exceptions", "Declared condition does not always hold", "Moderate",
                                     f"{name} departs from its declared condition ({condition['column']} {condition['op']} {condition.get('value')}).",
                                     f"{name}: {ex['value_present_where_declared_not_to_apply']:,} rows hold a value where the declaration says it does not apply; "
                                     f"{ex['not_applicable_code_where_condition_holds']:,} rows carry a not-applicable code where it should apply.",
                                     "Review these rows: either the declaration or the records are wrong.",
                                     "Rows that contradict the declared structure are interpreted inconsistently by any rule built on it.", [name, condition["column"]]))
        missing = record["declared_missing_rows"]
        rate = _rate(missing, record["rows"]) or 0
        if rate >= 25:
            findings.append(_finding("declared_missing_population", "Declared missing values", "High" if rate >= 50 else "Moderate",
                                     f"{name}: {missing:,} of {record['rows']:,} rows ({rate}%) carry codes you declared as missing.",
                                     f"{name}: rows by declared meaning " + ", ".join(f"{k.replace('_', ' ')} {v:,}" for k, v in record["rows_by_meaning"].items()) + ".",
                                     "Treat these as missing in later steps; the parser counted them as values.",
                                     "Codes counted as values hide missingness from methods that would handle it explicitly.", [name]))
        numeric = record.get("applicable_numeric")
        if numeric and numeric.get("outlier_rate") is not None and numeric["outlier_rate"] >= 5:
            findings.append(_finding("applicable_population_outliers", "IQR review candidates in the applicable population", "Moderate",
                                     f"{name}: {numeric['outlier_count']:,} of {numeric['outlier_denominator']:,} applicable finite values ({numeric['outlier_rate']}%) fall outside the 1.5 × IQR fences.",
                                     f"{name}: applicable population of {record['applicable_rows']:,} rows after declared codes and conditions.",
                                     "Review these values within the applicable population.", "Extreme values among applicable rows can dominate scale-sensitive methods.", [name]))
        unobserved = [c["value"] for c in record["declared_codes"] if not c["observed"]]
        if unobserved:
            findings.append(_finding("declared_value_not_observed", "Declared value not found", "Low",
                                     f"{name}: {count_phrase(len(unobserved), 'declared value')} never occur{'s' if len(unobserved) == 1 else ''} in the parsed data.",
                                     f"{name}: " + ", ".join(map(str, unobserved)) + ".", "Check the declaration for a typing error or a different code.",
                                     "A declaration that matches nothing has no effect.", [name]))
    return findings


def validate(data, config):
    """Declarations must name columns the parsed data has; raises ValueError otherwise."""
    context = config.context
    if context is None:
        return
    unknown_columns = sorted(set(context.columns) - set(map(str, data.columns)))
    if unknown_columns:
        raise ValueError("Context declares unknown columns: " + ", ".join(unknown_columns) + ".")
    for name, declaration in context.columns.items():
        if declaration.applies_when and declaration.applies_when["column"] not in data.columns:
            raise ValueError(f"The condition for {name} refers to an unknown column: {declaration.applies_when['column']}.")


def not_completed(reason):
    """The block when the contextual stage did not finish: stated, never shown as clean."""
    return {"version": VERSION, "status": "not_completed", "reason": reason or "The contextual stage did not complete.", "findings": []}


def build(data, task, config, profile, roles=None, method=None):
    """The contextual block for one parsed dataset. Raw evidence, findings and scores are not touched."""
    context = config.context or ContextOptions()
    targets = list(task.target_names)
    if roles and roles.get("features") is not None:
        features = [c for c in roles["features"] if c in data.columns]
    else:
        features = [str(c) for c in data.columns if str(c) not in targets]
    availability = dict(config.regression.feature_availability) if config.regression else {}
    advanced = getattr(config, "advanced", None)
    if advanced is not None and getattr(advanced, "feature_availability", None):
        availability = {**advanced.feature_availability, **availability}
    for column, value in context.availability().items():
        availability.setdefault(column, value)
    validate(data, config)
    found = candidates(data, [str(c) for c in data.columns if str(c) not in targets])
    interpreted = {name: interpret(data, name, d) for name, d in context.columns.items() if d.placeholders or d.sentinels or d.applies_when}
    declared_codes = [{"column": n, "value": c["value"]} for n, r in interpreted.items() for c in r["declared_codes"] if c["observed"]]
    indicators = sorted({(i["column"], i["value"]): i for i in [*({"column": c["column"], "value": c["value"], "rows": c["rows"]} for c in found), *declared_codes]}.values(),
                        key=lambda i: -i.get("rows", 0))
    block = {
        "version": VERSION,
        "status": "completed",
        "prediction": {"objective": context.objective, "point": context.prediction_point, "declared": bool(context.objective or context.prediction_point)},
        "declarations": context.to_dict()["columns"],
        "availability": availability,
        "features": features,
        "candidates": found,
        "candidate_rules": {"version": RULES, "placeholder_tokens": list(PLACEHOLDER_TOKENS), "sentinel_codes": list(SENTINEL_CODES),
                            "meaning": "Candidates are suggestions only; nothing is interpreted until you declare it."},
        "interpreted": interpreted,
        "observed_dependencies": co_occurrence(data, indicators),
        "demonstrated_use": "Not observed: DataTrust does not see your pipeline. A before/after comparison can show which columns survive preprocessing.",
    }
    if task.kind == "classification" and len(targets) == 1:
        block["dependency_search"] = dependency_search(data, targets[0], features, context.limits)
    else:
        block["dependency_search"] = {"status": "not_applicable",
                                      "reason": "Runs for single-target classification; regression uses its bounded relationship search." if task.kind == "regression"
                                      else "No single classification target."}
    covered = {c for c, v in (config.regression.feature_availability if config.regression else {}).items() if v == "unavailable_at_prediction"}
    block["findings"] = _findings(block, covered)
    return block
