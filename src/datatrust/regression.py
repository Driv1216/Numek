"""Regression evidence primitives. No loading, models, scores, or rendering.

Identity tolerances scale against variation, never the absolute target level.
Search limits bound formula comparisons, not pandas allocations or wall time.
"""
import hashlib
import math
from dataclasses import asdict
from itertools import combinations

import numpy as np
import pandas as pd

from datatrust.contracts import AnalysisError
from datatrust.target_guidance import column_name_tokens

ACTION_SUPPORT = {"minimum_overlap": 30, "minimum_distinct_targets": 5, "minimum_target_coverage": 80}
RTOL = 1e-10


from datatrust.numerical import (numeric_column, finite_mask, scalar, rate, precision_reason, target_evidence, histogram, grid_evidence, constraint_evidence)


def validate_target(data, target, options):
    if target not in data.columns:
        raise AnalysisError(f"Target column '{target}' was not found in the dataset.", code="invalid_target", stage="target")
    if not numeric_column(data[target]):
        raise AnalysisError(f"Regression target '{target}' must be numeric and not boolean. Numeric-looking strings require an explicit numeric parsing override; invalid tokens are never coerced.", code="invalid_target", stage="target")
    if not finite_mask(data[target]).any():
        raise AnalysisError(f"Regression target '{target}' has no finite observations.", code="no_finite_target", stage="target")
    unknown = set(options.feature_availability) - set(data.columns)
    if unknown or target in options.feature_availability:
        raise AnalysisError("Feature availability must reference existing feature columns only: " + ", ".join(sorted(unknown | ({target} if target in options.feature_availability else set()))), code="invalid_declaration", stage="target")


def name_candidates(columns, target):
    target_tokens = set(column_name_tokens(target))
    result = []
    for column in columns:
        tokens = set(column_name_tokens(column))
        if target_tokens & tokens or tokens & {"actual", "final", "outcome", "post", "result", "label", "future"}:
            result.append({"column": column, "historical_qualifier": bool(tokens & {"prior", "previous", "historical", "past"}),
                           "reason": "Name cue only; verify when this field becomes available."})
    return result


def relationship_evidence(data, target, options, checkpoint, *, feature_columns=None):
    steps = relationship_steps(data, target, options, checkpoint, feature_columns=feature_columns)
    while True:
        try:
            next(steps)
        except StopIteration as done:
            return done.value


def relationship_steps(data, target, options, checkpoint, *, feature_columns=None, shared_usage=None):
    y = data[target]
    ym = finite_mask(y)
    population = int(ym.sum())
    features = [c for c in data.columns if c != target] if feature_columns is None else list(feature_columns)
    eligible = [c for c in features if numeric_column(data[c])]
    cues = name_candidates(eligible, target)
    cue_names = {c["column"] for c in cues if not c["historical_qualifier"]}
    ordered = sorted(eligible, key=lambda c: c not in cue_names)
    limits = options.relation_limits
    pool = ordered[:limits.max_pair_features]
    used = {"single": 0, "pair": 0} if shared_usage is None else shared_usage
    ledger = []
    entries = {}
    relationships = []
    pool_exclusions = [{"column": c, "reason_category": "planned_pool_limit"} for c in ordered[len(pool):]]

    def entry(method, columns):
        key = (method, tuple(columns))
        if key in entries:
            return entries[key]
        item = {"method": method, "columns": columns, "status": "not_run", "reason_category": None,
                "overlap_count": None, "target_coverage": None, "screened_rows": 0, "verified_rows": 0}
        ledger.append(item)
        entries[key] = item
        return item

    def reserve(item, group, count):
        maximum = limits.max_single_comparisons if group == "single" else limits.max_pair_comparisons
        if used[group] + count > maximum:
            item.update(status="skipped", reason_category="planned_work_limit")
            return False
        used[group] += count
        return True

    def overlap(columns):
        mask = ym.copy()
        for c in columns:
            mask &= finite_mask(data[c])
        return mask

    def add(item, mask, coefficient=None, intercept=None, tolerance=0., constant_component=None):
        index = data.index[mask]
        n = len(index)
        reasons = []
        if n < ACTION_SUPPORT["minimum_overlap"]:
            reasons.append("small_overlap")
        distinct = int(y[mask].nunique())
        if distinct < ACTION_SUPPORT["minimum_distinct_targets"]:
            reasons.append("few_distinct_targets")
        if rate(n, population) < ACTION_SUPPORT["minimum_target_coverage"]:
            reasons.append("sparse_target_coverage")
        availability = [options.feature_availability.get(c, "unknown") for c in item["columns"]]
        context = "unavailable_at_prediction" if "unavailable_at_prediction" in availability else "available_at_prediction" if all(v == "available_at_prediction" for v in availability) else "unknown"
        ident = f"relationship.{len(relationships)}"
        expression = f"{target} = " + (item["columns"][0] if item["method"] == "exact_copy" else f"{coefficient} * {item['columns'][0]} + {intercept}" if item["method"] == "affine_identity" else " + ".join(item["columns"]))
        relationships.append({"id": ident, "method": item["method"], "columns": item["columns"], "expression": expression,
            "overlap_count": n, "target_coverage": rate(n, population), "total_row_coverage": rate(n, len(data)),
            "target_distinct_count": distinct, "support_sha256": hashlib.sha256(index.to_numpy(dtype='int64').tobytes()).hexdigest(),
            "coefficient": coefficient, "intercept": intercept, "constant_component": constant_component,
            "normalized_tolerance": tolerance, "fully_verified": True,
            "availability": context, "availability_by_column": dict(zip(item["columns"], availability)),
            "declaration_source": "user_declared_or_unknown", "action_eligible": not reasons,
            "non_escalation_reasons": reasons, "row_ordinals": [int(i) + 1 for i in index[:5]],
            "excluded_rows": len(data) - n, "missing_target_count": int(y.isna().sum()),
            "nonfinite_target_count": int((y.notna() & ~ym).sum()),
            "feature_exclusions": {c: {"missing": int(data[c].isna().sum()), "nonfinite": int((data[c].notna() & ~finite_mask(data[c])).sum())} for c in item["columns"]}})
        item.update(status="verified_relationship", reason_category=None, verified_rows=n, relationship_id=ident)

    # Register scope before execution so interruption discloses every unsearched candidate.
    for method in ("exact_copy", "affine_identity"):
        for c in eligible:
            entry(method, [c])
    for a, b in combinations(pool, 2):
        entry("pair_sum", [a, b])
    target_positions = np.flatnonzero(ym.to_numpy())
    screen_positions = target_positions[np.linspace(0, len(target_positions) - 1, min(len(target_positions), limits.max_screen_rows), dtype=int)]
    target_min, target_max = float(y[ym].min()), float(y[ym].max())
    def run_candidates():
        copies = set()
        for method in ("exact_copy", "affine_identity"):
            for c in eligible:
                item = entry(method, [c])
                yield method
                checkpoint("regression relationship candidate")
                mask = overlap([c]); n = int(mask.sum())
                item.update(overlap_count=n, target_coverage=rate(n, population))
                if method == "affine_identity" and c in copies:
                    item.update(status="excluded", reason_category="redundant_check")
                    continue
                yy, xx = y[mask], data[c][mask]
                minimum = 2 if method == "exact_copy" else 20
                distinct = 2 if method == "exact_copy" else 5
                if n < minimum or yy.nunique() < distinct or (method == "affine_identity" and xx.nunique() < 5):
                    item.update(status="blocked", reason_category="insufficient_support")
                    continue
                if method == "exact_copy":
                    if not reserve(item, "single", n):
                        continue
                    # Object scalars preserve integer equality when float/int dtypes differ.
                    matched = yy.astype(object).eq(xx.astype(object))
                    item.update(status="verified_no_relationship", verified_rows=n, exact_match_count=int(matched.sum()))
                    if matched.all():
                        add(item, mask); copies.add(c)
                    continue
                if precision_reason(yy) or precision_reason(xx):
                    item.update(status="blocked", reason_category="unsafe_arithmetic")
                    continue
                xv, yv = xx.to_numpy(dtype=float), yy.to_numpy(dtype=float)
                xs, ys = max(np.abs(xv).max(), 1e-300), max(np.abs(yv).max(), 1e-300)
                xn, yn = xv / xs, yv / ys
                low, high = int(np.argmin(xn)), int(np.argmax(xn))
                slope = (yn[high] - yn[low]) / (xn[high] - xn[low])
                offset = yn[low] - slope * xn[low]
                spread = float(np.ptp(yn))
                allowance = 32 * np.finfo(float).eps * (1 + abs(float(slope)) + abs(float(offset)))
                if allowance > spread * 1e-6:
                    item.update(status="blocked", reason_category="unsafe_arithmetic")
                    continue
                tolerance = RTOL * spread + allowance
                a, b = float(slope * ys / xs), float(offset * ys)
                if not math.isfinite(a) or not math.isfinite(b):
                    item.update(status="blocked", reason_category="unsafe_arithmetic")
                    continue
                if not reserve(item, "single", n):
                    continue
                reconstructed = slope * xn + offset
                item.update(status="verified_no_relationship", verified_rows=n)
                if np.max(np.abs(yn - reconstructed)) <= tolerance:
                    # Exact translations have a canonical scalar expression, even
                    # when normalized anchor arithmetic slightly perturbs a or b.
                    differences = yy.astype(object) - xx.astype(object)
                    if differences.nunique() == 1 and math.isfinite(float(differences.iloc[0])):
                        a, b = 1., scalar(differences.iloc[0])
                    add(item, mask, a, b, tolerance / spread)
    
        for a, b in combinations(pool, 2):
            item = entry("pair_sum", [a, b])
            yield "pair_sum"
            checkpoint("regression pair candidate")
            if used["pair"] >= limits.max_pair_comparisons:
                item.update(status="skipped", reason_category="planned_work_limit")
                continue
            # Screen the common finite-target sample before scanning full columns.
            sample = data.iloc[screen_positions]
            sm = finite_mask(sample[a]) & finite_mask(sample[b])
            sy, sa, sb = (sample[c][sm] for c in (target, a, b))
            if len(sy) >= 20 and sy.nunique() >= 5 and not any(precision_reason(s) for s in (sy, sa, sb)):
                ss = max(abs(target_min), abs(target_max), float(sa.abs().max()), float(sb.abs().max()), 1e-300)
                sny, sna, snb = (s.to_numpy(dtype=float) / ss for s in (sy, sa, sb))
                if not reserve(item, "pair", len(sy)):
                    continue
                item["screened_rows"] = len(sy)
                # Conservative screen: full verification rejects arithmetic whose
                # roundoff exceeds 1e-6 of target spread. Include that entire bound
                # here so an unsampled extreme cannot cause a false screen rejection.
                screen_tolerance = (RTOL + 1e-6) * (target_max / ss - target_min / ss)
                if np.max(np.abs(sny - sna - snb)) > screen_tolerance:
                    item.update(status="screened_no_candidate")
                    continue
            mask = overlap([a, b]); n = int(mask.sum())
            item.update(overlap_count=n, target_coverage=rate(n, population))
            if n < 20 or y[mask].nunique() < 5:
                item.update(status="blocked", reason_category="insufficient_support")
                continue
            yy, aa, bb = y[mask], data[a][mask], data[b][mask]
            if any(precision_reason(s) for s in (yy, aa, bb)):
                item.update(status="blocked", reason_category="unsafe_arithmetic")
                continue
            scale = max(float(yy.abs().max()), float(aa.abs().max()), float(bb.abs().max()), 1e-300)
            yn, an, bn = (s.to_numpy(dtype=float) / scale for s in (yy, aa, bb))
            spread = float(np.ptp(yn))
            allowance = 32 * np.finfo(float).eps
            if allowance > spread * 1e-6:
                item.update(status="blocked", reason_category="unsafe_arithmetic")
                continue
            tolerance = RTOL * spread + allowance
            if not item["screened_rows"]:
                size = min(n, limits.max_screen_rows)
                positions = np.linspace(0, n - 1, size, dtype=int)
                if not reserve(item, "pair", size):
                    continue
                item["screened_rows"] = size
                if np.max(np.abs(yn[positions] - an[positions] - bn[positions])) > tolerance:
                    item.update(status="screened_no_candidate")
                    continue
            if not reserve(item, "pair", n):
                item["screen_match"] = True
                continue
            item.update(status="verified_no_relationship", verified_rows=n)
            if np.max(np.abs(yn - an - bn)) <= tolerance:
                constant = {"column": a, "value": scalar(aa.iloc[0])} if aa.nunique() == 1 else {"column": b, "value": scalar(bb.iloc[0])} if bb.nunique() == 1 else None
                add(item, mask, tolerance=tolerance / spread, constant_component=constant)
    failure = None
    try:
        yield from run_candidates()
    except MemoryError:
        raise
    except AnalysisError as exc:
        if exc.code != "resource_limit":
            raise
        failure = {"reason_category": "execution_interruption", "reason": str(exc)}
    except Exception as exc:
        failure = {"reason_category": "diagnostic_failure", "reason": f"{type(exc).__name__}: candidate execution failed; unfinished candidates support no conclusion."}
    if failure:
        for item in ledger:
            if item["status"] == "not_run":
                item.update(status="skipped", reason_category=failure["reason_category"])
    bounded = bool(pool_exclusions or any(i["reason_category"] == "planned_work_limit" for i in ledger))
    search = {"status": "partial" if failure else "bounded" if bounded else "exhaustive_within_methods", "failure": failure, "limits": asdict(limits),
        "eligible_columns": eligible, "selected_pair_columns": pool, "pool_exclusions": pool_exclusions,
        "comparisons": used, "candidates": ledger, "candidate_count": len(ledger),
        "fully_verified_count": sum(i["verified_rows"] > 0 for i in ledger),
        "skipped_count": sum(i["reason_category"] == "planned_work_limit" for i in ledger),
        "interrupted_candidate_count": sum(i["reason_category"] in {"execution_interruption", "diagnostic_failure"} for i in ledger),
        "screen_scope": {"method": "evenly_spaced_finite_target_rows; sparse samples fall back to evenly spaced full-overlap rows", "row_ordinals": [int(i)+1 for i in screen_positions]},
        "meaning": "No observed relationship means only none verified in the searched scope; unsearched relationships are unknown."}
    return {"relationships": relationships, "relationship_groups": consolidate_relationships(relationships), "search": search,
            "name_candidates": name_candidates(features, target)}


def consolidate_relationships(relationships):
    """Consolidate equivalent witnesses, without conflating distinct mappings."""
    groups = []
    for r in relationships:
        matched = None
        for group in groups:
            witness = next(item for item in relationships if item["id"] == group["relationship_ids"][0])
            equivalent = r["support_sha256"] == witness["support_sha256"] and r["columns"] == witness["columns"] and (
                r["method"] == witness["method"] or
                {r["method"], witness["method"]} == {"exact_copy", "affine_identity"} and
                all(item["method"] == "exact_copy" or item["coefficient"] == 1 and item["intercept"] == 0 for item in (r, witness)))
            if r["method"] == "pair_sum" and r["constant_component"] and len(witness["columns"]) == 1:
                remaining = [c for c in r["columns"] if c != r["constant_component"]["column"]]
                equivalent = remaining == witness["columns"] and (
                    witness["method"] == "exact_copy" and r["constant_component"]["value"] == 0 or
                    witness["method"] == "affine_identity" and witness["coefficient"] == 1 and witness["intercept"] == r["constant_component"]["value"])
            if equivalent:
                matched = group; break
        if matched is None:
            matched = {"id": f"relationship_group.{len(groups)}", "expression": r["expression"],
                       "columns": r["columns"], "availability": r["availability"], "action_eligible": r["action_eligible"],
                       "relationship_ids": [], "support_scopes": []}
            groups.append(matched)
        matched["relationship_ids"].append(r["id"])
        matched["support_scopes"].append({"relationship_id": r["id"], "support_sha256": r["support_sha256"], "overlap_count": r["overlap_count"], "target_coverage": r["target_coverage"], "availability": r["availability"], "non_escalation_reasons": r["non_escalation_reasons"]})
    return groups


def repeated_input_evidence(data, target, *, feature_columns=None):
    features = [c for c in data.columns if c != target] if feature_columns is None else list(feature_columns)
    if not features:
        return None
    frame = data[finite_mask(data[target])]
    grouped = frame.groupby(features, dropna=False, sort=False)
    groups = grouped[target].agg(count="size", distinct="nunique", minimum="min", maximum="max")
    repeated = groups[groups["count"] > 1]
    varying = repeated[repeated["distinct"] > 1]
    examples = []
    group_ids = grouped.ngroup()
    # Group ordinals follow the same stable source order as the aggregation.
    example_ordinals = groups.index.get_indexer(varying.head(5).index)
    for group_ordinal, row in zip(example_ordinals, varying.head(5).to_dict(orient="records")):
        low, high = scalar(row["minimum"]), scalar(row["maximum"])
        span = high - low
        examples.append({"count": int(row["count"]), "distinct_count": int(row["distinct"]), "min": low, "max": high,
                         "span": span if isinstance(span, int) or math.isfinite(span) else None,
                         "span_unavailable_reason": "statistic_overflow" if not isinstance(span, int) and not math.isfinite(span) else None,
                         "row_ordinals": [int(i) + 1 for i in frame.index[group_ids == group_ordinal][:5]]})
    return {"denominator": len(frame), "repeated_group_count": len(repeated), "participating_rows": int(repeated["count"].sum()),
            "varying_group_count": len(varying), "varying_rows": int(varying["count"].sum()),
            "largest_group": int(repeated["count"].max()) if len(repeated) else 0, "examples": examples,
            "interpretation": "Variation may reflect repeated measurements, stochastic outcomes, or omitted context; contradictory labels are not established."}


def multioutput_evidence(data, targets, features, options, diagnostic_limits, checkpoint, *, relationship_features=None, annotations=None):
    """One shared input pool and round-robin M2 formula search across outputs."""
    from dataclasses import replace
    from datatrust.contracts import TargetExpectations, RegressionRelationLimits
    from datatrust.multilabel import repeated_inputs
    outputs = []; active = []; used = {'single':0,'pair':0}
    relationship_features = features if relationship_features is None else relationship_features
    violation_union = np.zeros(len(data), bool)
    complete = np.ones(len(data),bool); observed = np.zeros(len(data),np.int32)
    for t in targets:
        expectations = options.expectations_by_target.get(t, options.expectations if len(targets)==1 else TargetExpectations())
        valid = finite_mask(data[t]).to_numpy() if numeric_column(data[t]) else np.zeros(len(data),bool)
        complete &= valid; observed += valid
        record = {'target':t,'expectations':asdict(expectations),'statistics':None,'constraints':None,'relationships':[],
                  'relationship_groups':[],'search':None,'name_candidates':[], 'finite_count':int(valid.sum()), 'blocked_reason':None}
        if valid.any():
            record['statistics'] = target_evidence(data[t],expectations)
            record['constraints'] = constraint_evidence(data[t],expectations)
            s=data[t]; bad=np.zeros(len(data),bool)
            for bound,cmp in ((expectations.minimum,lambda a,b:a<b),(expectations.maximum,lambda a,b:a>b)):
                if bound is not None: bad |= valid & cmp(s,bound).fillna(False).to_numpy()
            if expectations.nonnegative: bad |= valid & (s<0).fillna(False).to_numpy()
            if expectations.integer_required: bad |= valid & s.map(lambda v: pd.notna(v) and not (isinstance(v,(int,np.integer)) or float(v).is_integer())).to_numpy()
            violation_union |= bad
            active.append((record, relationship_steps(data,t,replace(options,expectations=expectations),checkpoint,feature_columns=relationship_features,shared_usage=used)))
        else:
            record['blocked_reason']='no_finite_observed_targets'
        outputs.append(record)
    # Each step advances one candidate. All outputs have the same feature pool,
    # so copy, affine, and sum stages progress in declared target order.
    while active:
        remaining=[]
        for record,steps in active:
            try: next(steps);remaining.append((record,steps))
            except StopIteration as done: record.update(done.value)
        active=remaining
    pairs=[]; pair_used=0; excluded=[]; pool=targets[:diagnostic_limits.max_output_pair_targets]
    for a,b in combinations(pool,2):
        checkpoint('output dependency pair')
        if pair_used + len(data)*3 > diagnostic_limits.max_output_comparisons:
            excluded.append({'targets':[a,b],'reason':'planned_work_limit'}); continue
        pair_used+=len(data)*3
        mask=finite_mask(data[a]) & finite_mask(data[b]) if numeric_column(data[a]) and numeric_column(data[b]) else pd.Series(False,index=data.index)
        aa,bb=data[a][mask],data[b][mask];n=len(aa);reason=None;pearson=None;identities=[]
        if n<20 or aa.nunique()<5 or bb.nunique()<5: reason='insufficient_paired_support'
        elif precision_reason(aa) or precision_reason(bb): reason='unsafe_arithmetic'
        else:
            x=aa.to_numpy(dtype=float);y=bb.to_numpy(dtype=float)
            x=x/(np.max(np.abs(x)) or 1);y=y/(np.max(np.abs(y)) or 1)
            x=x-x.mean();y=y-y.mean();den=float(np.linalg.norm(x)*np.linalg.norm(y))
            if den and math.isfinite(den): pearson=max(-1.,min(1.,float(np.dot(x,y)/den)))
            else: reason='unsafe_or_zero_variation'
        if n:
            dep_options=replace(options, feature_availability={},relation_limits=RegressionRelationLimits(diagnostic_limits.max_output_comparisons,1,1,512))
            rel=relationship_evidence(data[[a,b]],b,dep_options,checkpoint,feature_columns=[a])
            for r in rel['relationships']:
                identities.append({key:value for key,value in r.items() if key not in {'action_eligible','non_escalation_reasons','availability','availability_by_column','declaration_source'}})
        pairs.append({'targets':[a,b],'finite_overlap':n,'coverage':n/len(data),'pearson':pearson,'pearson_unavailable_reason':reason,'identities':identities,
                      'identity_search':rel['search'] if n else None,'scope':'output_dependencies','interpretation':'Output association/identity does not establish leakage, causation, performance, or expendability.'})
    from collections import Counter
    vectors = None
    if complete.any():
        from datatrust.profiler import exact_duplicate_evidence
        vectors=exact_duplicate_evidence(data.loc[complete,targets])
    return {'outputs':outputs,'complete_vector_count':int(complete.sum()),'partial_vector_count':int(((observed>0)&~complete).sum()),
            'empty_vector_count':int((observed==0).sum()),'observed_component_histogram':{str(v):int(c) for v,c in sorted(Counter(observed.tolist()).items())},
            'constraint_violation_row_union':int(violation_union.sum()),'complete_vector_repetition':vectors,
            'repeated_inputs':repeated_inputs(data,features,targets,'regression',diagnostic_limits,annotations=annotations),
            'output_dependencies':pairs,'dependency_search':{'selected_targets':pool,'excluded_targets':targets[len(pool):],'excluded_pairs':excluded,'comparisons':pair_used,
                                                           'status':'bounded' if excluded or len(pool)<len(targets) else 'completed'},
            'relationship_work':dict(used),'feature_availability':options.feature_availability,
            'interpretation':'Per-output units and observed populations remain separate. Relationships in observed data say nothing about unavailable outputs.'}
