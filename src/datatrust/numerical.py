"""Shared precision-safe, unrounded numerical evidence (M2 compatibility primitives)."""
import math
import numpy as np
import pandas as pd
from datatrust.contracts import TargetExpectations

def numeric_column(series):
    return pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series)


def finite_mask(series):
    return series.notna() & np.isfinite(series)


def scalar(value):
    return value.item() if hasattr(value, "item") else value


def rate(count, denominator):
    return 100 * count / denominator if denominator else None


def precision_reason(series):
    """Protect exact integers and unresolved floating variation before conversion."""
    if pd.api.types.is_integer_dtype(series) and ((series > 2**53) | (series < -(2**53))).any():
        return "integer_precision_beyond_float64"
    if series.nunique() > 1:
        lo, hi = float(series.min()), float(series.max())
        # Compute spread after scaling to avoid overflow from opposite signs.
        scale = max(abs(lo), abs(hi)) or 1
        spread = hi / scale - lo / scale
        if spread <= 128 * max(math.ulp(lo) / scale, math.ulp(hi) / scale):
            return "variation_near_floating_resolution"
    return None


def target_evidence(series, expectations):
    mask = finite_mask(series)
    finite = series[mask]
    n = len(finite)
    counts = finite.value_counts()
    integers = int(finite.map(lambda v: isinstance(v, (int, np.integer)) or float(v).is_integer()).sum())
    result = {
        "row_count": len(series), "missing_count": int(series.isna().sum()),
        "non_missing_count": int(series.notna().sum()), "finite_count": n,
        "positive_infinity_count": int((series == np.inf).sum()),
        "negative_infinity_count": int((series == -np.inf).sum()),
        "finite_rate": rate(n, len(series)), "distinct_count": int(finite.nunique()),
        "zero_count": int((finite == 0).sum()), "negative_count": int((finite < 0).sum()),
        "integer_count": integers, "non_integer_count": n - integers,
        "modal_value": scalar(counts.index[0]), "modal_count": int(counts.iloc[0]),
        "modal_share": rate(int(counts.iloc[0]), n),
        "min": scalar(finite.min()), "max": scalar(finite.max()),
        "population": "finite targets, including declared constraint violations",
        "mean": None, "sample_std": None, "quantiles": None, "iqr": None,
        "central_90_span": None, "bowley_skewness": None,
        "precision_reason": precision_reason(finite), "unavailable_statistics": {},
        "extremes": None, "rounding": None, "histogram": None, "quantile_plot": None,
        "boundary_concentration": [],
    }
    if result["distinct_count"] <= 20:
        result["histogram"] = histogram(finite, None, None, None)
    endpoints = [("observed_minimum", result["min"]), ("observed_maximum", result["max"])]
    endpoints += [(name, bound) for name, bound in (("declared_minimum", expectations.minimum), ("declared_maximum", expectations.maximum)) if bound is not None]
    for name, bound in endpoints:
        count = int(finite.map(lambda v: scalar(v) == bound).sum())
        result["boundary_concentration"].append({"boundary": name, "value": bound, "count": count,
            "share": rate(count, n), "review_candidate": n >= 20 and result["distinct_count"] > 1 and count / n >= .1,
            "interpretation": "zero concentration" if bound == 0 and expectations.kind == "count" else "boundary concentration; clipping is not established"})
    if result["precision_reason"]:
        result["unavailable_statistics"] = {name: result["precision_reason"] for name in ("mean", "sample_std", "quantiles", "iqr", "extremes", "rounding", "histogram")}
        if result["histogram"]:
            result["unavailable_statistics"].pop("histogram")
        return result
    values = finite.to_numpy(dtype=float)
    scale = float(np.max(np.abs(values))) or 1.0
    normalized = values / scale
    if len(np.unique(normalized)) < result["distinct_count"]:
        result["precision_reason"] = "scaled_variation_resolution_loss"
        result["unavailable_statistics"] = {name: result["precision_reason"] for name in ("mean", "sample_std", "quantiles", "iqr", "extremes", "rounding", "histogram")}
        if result["histogram"]:
            result["unavailable_statistics"].pop("histogram")
        return result
    probabilities = [0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99]
    q = np.quantile(normalized, probabilities, method="linear")
    result["quantiles"] = dict(zip(("p1", "p5", "q1", "median", "q3", "p95", "p99"), (float(v * scale) for v in q)))
    span = float(normalized.max() - normalized.min())
    result["quantile_plot"] = dict(zip(result["quantiles"],
        (float((v - normalized.min()) / span * 100) if span else 50. for v in q)))
    for name, v in (("mean", float(np.mean(normalized)) * scale),
                    ("sample_std", float(np.std(normalized, ddof=1)) * scale if n >= 2 else None),
                    ("iqr", float(q[4] - q[2]) * scale),
                    ("central_90_span", float(q[5] - q[1]) * scale)):
        result[name] = v if v is None or math.isfinite(v) else None
        if v is not None and not math.isfinite(v):
            result["unavailable_statistics"][name] = "statistic_overflow"
    if n < 2:
        result["unavailable_statistics"]["sample_std"] = "insufficient_observations"
    iqr = float(q[4] - q[2])
    reason = "insufficient_observations" if n < 4 else "zero_iqr" if iqr == 0 else None
    if reason:
        result["unavailable_statistics"]["extremes"] = reason
    else:
        lower, upper = q[2] - 1.5 * iqr, q[4] + 1.5 * iqr
        lower_mask, upper_mask = normalized < lower, normalized > upper
        ordinals = np.flatnonzero(mask.to_numpy()) + 1
        result["extremes"] = {
            "lower_count": int(lower_mask.sum()), "upper_count": int(upper_mask.sum()),
            "count": int((lower_mask | upper_mask).sum()), "denominator": n,
            "rate": rate(int((lower_mask | upper_mask).sum()), n),
            "lower_fence": float(lower) * scale if math.isfinite(float(lower) * scale) else None,
            "upper_fence": float(upper) * scale if math.isfinite(float(upper) * scale) else None,
            "row_ordinals": [int(v) for v in ordinals[lower_mask | upper_mask][:5]],
            "method": "finite_1.5_iqr",
        }
        result["bowley_skewness"] = float(((q[4] - q[3]) - (q[3] - q[2])) / iqr)
    if iqr == 0:
        result["unavailable_statistics"]["bowley_skewness"] = "zero_iqr"
    elif n < 4:
        result["unavailable_statistics"]["bowley_skewness"] = "insufficient_observations"
    result["histogram"] = histogram(finite, normalized, scale, iqr)
    result["rounding"] = grid_evidence(values, result["distinct_count"])
    return result


def histogram(finite, normalized, scale, iqr):
    counts = finite.value_counts().sort_index()
    if len(counts) <= 20:
        return {"method": "exact_value_counts", "denominator": len(finite), "bins": [
            {"lower": scalar(v), "upper": scalar(v), "count": int(c)} for v, c in counts.items()]}
    span = float(normalized.max() - normalized.min())
    width = 2 * iqr / len(finite)**(1 / 3)
    ratio = span / width if width > 0 else None
    bins = 40 if ratio is not None and (not math.isfinite(ratio) or ratio >= 40) else max(1, math.ceil(ratio)) if ratio is not None else min(40, math.ceil(math.log2(len(finite)) + 1))
    frequencies, edges = np.histogram(normalized, bins=bins)
    return {"method": "freedman_diaconis_capped_40" if width > 0 else "sturges_zero_iqr", "denominator": len(finite),
            "bins": [{"lower": float(edges[i] * scale), "upper": float(edges[i + 1] * scale), "count": int(v)} for i, v in enumerate(frequencies)],
            "interval_policy": "left closed, right open; final bin includes maximum"}


def grid_evidence(values, distinct):
    if len(values) < 20 or distinct < 5:
        return {"status": "blocked", "reason": "insufficient_support", "grids": [], "coarsest_aligned_step": None}
    grids = []
    for step in (1., .1, .01, .001):
        if np.max(np.abs(values)) / step >= 2**52 or max(math.ulp(float(v)) for v in (values.min(), values.max())) > step * 1e-8:
            grids.append({"step": step, "status": "blocked", "reason": "floating_resolution", "aligned_count": None, "share": None})
            continue
        scaled = values / step
        count = int((np.abs(scaled - np.rint(scaled)) <= 1e-8).sum())
        grids.append({"step": step, "status": "completed", "aligned_count": count, "share": rate(count, len(values))})
    matching = [g["step"] for g in grids if g["status"] == "completed" and g["share"] >= 95]
    return {"status": "completed" if any(g["status"] == "completed" for g in grids) else "blocked",
            "denominator": len(values), "grid_relative_tolerance": 1e-8, "grids": grids,
            "coarsest_aligned_step": matching[0] if matching else None,
            "interpretation": "Parsed numeric representation only; ordinary integer or decimal alignment is not suspicious."}


def constraint_evidence(series, expectations):
    finite = series[finite_mask(series)]
    union = pd.Series(False, index=finite.index)
    rules = []
    definitions = []
    if expectations.minimum is not None:
        definitions.append(("below_declared_minimum", expectations.minimum, lambda v: v < expectations.minimum))
    if expectations.maximum is not None:
        definitions.append(("above_declared_maximum", expectations.maximum, lambda v: v > expectations.maximum))
    if expectations.nonnegative:
        definitions.append(("declared_nonnegative", 0, lambda v: v < 0))
    if expectations.integer_required:
        definitions.append(("declared_integer", True, lambda v: not (isinstance(v, (int, np.integer)) or float(v).is_integer())))
    for name, declaration, predicate in definitions:
        bad = finite.map(lambda v: predicate(scalar(v)))
        union |= bad
        rules.append({"rule": name, "declaration": declaration, "count": int(bad.sum()),
                      "denominator": len(finite), "row_ordinals": [int(i) + 1 for i in finite.index[bad][:5]]})
    return {"declaration_source": "user_declared", "rules": rules, "denominator": len(finite),
            "violation_union_count": int(union.sum()), "compliant_finite_count": len(finite) - int(union.sum()),
            "row_ordinals": [int(i) + 1 for i in finite.index[union][:5]]}




def feature_evidence(series):
    """M3 structural numeric summaries use M2's precision/overflow gates."""
    mask=finite_mask(series);finite=series[mask];n=int(mask.sum());total=len(series)
    stats=target_evidence(series, TargetExpectations()) if n else None
    reason='no_finite_observations' if not n else stats['precision_reason'] or stats['unavailable_statistics'].get('extremes')
    e=stats['extremes'] if stats else None;q=stats['quantiles'] if stats else None
    summary={'min':scalar(finite.min()) if n else None,'max':scalar(finite.max()) if n else None,
             'q1':q['q1'] if q else None,'median':q['median'] if q else None,'q3':q['q3'] if q else None,
             'zero_count':int((finite==0).sum()),'zero_rate':rate(int((finite==0).sum()),total),
             'negative_count':int((finite<0).sum()),'negative_rate':rate(int((finite<0).sum()),total),
             'non_finite_count':int((series.notna() & ~mask).sum()),'non_finite_rate':rate(int((series.notna() & ~mask).sum()),total),
             'precision_reason':stats['precision_reason'] if stats else None,'unrounded':True}
    return {'numeric_summary':summary,'finite_count':n,'outlier_count':e['count'] if e else None,'outlier_rate':e['rate'] if e else None,
            'outlier_denominator':n,'outlier_method':'finite_1.5_iqr','outlier_unavailable_reason':reason}


def shape_evidence(finite):
    """Only the median/IQR evidence needed by annotation-population contrasts."""
    reason=precision_reason(finite)
    if reason:return {'median':None,'iqr':None,'reason':reason}
    values=finite.to_numpy(dtype=float);scale=float(np.abs(values).max()) or 1.
    normalized=values/scale
    if len(np.unique(normalized))<finite.nunique():return {'median':None,'iqr':None,'reason':'scaled_variation_resolution_loss'}
    q1,median,q3=np.quantile(normalized,[.25,.5,.75],method='linear');iqr=float(q3-q1)*scale
    if not math.isfinite(iqr):return {'median':None,'iqr':None,'reason':'statistic_overflow'}
    return {'median':float(median)*scale,'iqr':iqr,'reason':None}
