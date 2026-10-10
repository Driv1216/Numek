"""Tabular roles, effective policy, and orthogonal annotation coverage.

Expectation never determines observation validity. Metadata never removes a
well-formed supplied value from descriptive evidence.
"""
from dataclasses import replace, asdict
import hashlib
import json
from collections import Counter

import numpy as np
import pandas as pd

from datatrust.contracts import (AnnotationOptions, AnnotationSpec, canonical_status_values,
                                 RegressionOptions, TargetExpectations, FeatureOptions, AnalysisError, json_safe)
from datatrust.numerical import numeric_column, finite_mask, target_evidence, shape_evidence


def resolve_roles(columns, task, config):
    targets = list(task.target_names)
    annotation = config.annotations or AnnotationOptions()
    if set(annotation.per_target) - set(targets):
        raise ValueError("Annotation declarations must reference selected targets only.")
    if not targets and annotation.default.status_column is not None:
        raise ValueError("Annotation status declarations require a target-bearing task.")
    specs = {t: annotation.per_target.get(t, annotation.default) for t in targets}
    statuses = {s.status_column for s in specs.values() if s.status_column is not None}
    metadata = set(task.metadata_columns) | set(task.group_columns) | statuses
    for target in targets:
        if target not in columns:
            raise AnalysisError(f"Target column '{target}' was not found in the dataset.", code="invalid_target", stage="target")
    requested = set(targets) | metadata | set(task.feature_columns or ())
    if requested - set(columns):
        raise ValueError("Unknown resolved columns: " + ", ".join(sorted(requested - set(columns))))
    if set(targets) & metadata or (task.feature_columns is not None and set(task.feature_columns) & metadata):
        raise ValueError("Annotation metadata/group roles overlap target or feature roles.")
    features = [c for c in columns if c not in set(targets) | metadata] if task.feature_columns is None else [c for c in columns if c in task.feature_columns]
    roles = {c: "target" if c in targets else "metadata" if c in metadata else "feature" if c in features else "ignored" for c in columns}
    if set(config.features.semantic_types) - set(features):
        raise ValueError("Feature semantic declarations must reference selected features only.")
    if config.regression is not None:
        if task.kind != "regression":
            raise ValueError("Regression options require regression task.")
        if set(config.regression.feature_availability) - set(features):
            raise AnalysisError("Feature availability must reference existing feature columns only.", code="invalid_declaration", stage="target")
        if set(config.regression.expectations_by_target) - set(targets):
            raise ValueError("Numerical expectations must reference selected targets only.")
        if len(targets) > 1 and config.regression.expectations != TargetExpectations():
            raise ValueError("Multi-output numerical expectations require expectations_by_target.")
    if config.multilabel is not None and task.kind != "multilabel_classification":
        raise ValueError("Multilabel options require multilabel_classification.")
    return {"columns": roles, "features": features, "targets": targets,
            "metadata": [c for c in columns if roles[c] == "metadata"],
            "ignored": [c for c in columns if roles[c] == "ignored"], "groups": list(task.group_columns)}


def effective_policy(columns, task, config):
    roles = resolve_roles(columns, task, config)
    names = task.target_names
    ordinary = [c for c in columns if c not in names]
    role_change = roles["features"] != ordinary or bool(roles["metadata"])
    semantic_change = bool(config.features.semantic_types)
    if config.features.scale_sensitive is not None and task.kind not in {"clustering", "anomaly_detection"}:
        raise ValueError("scale_sensitive applies to clustering/anomaly readiness only.")
    annotation_change = False
    if config.annotations is not None:
        annotation_change = any(config.annotations.per_target.get(t, config.annotations.default) != AnnotationSpec("expected") for t in names)
    m3 = task.kind in {"multilabel_classification", "clustering", "anomaly_detection"} or len(names) > 1 or role_change or semantic_change or annotation_change
    options = config.regression
    if task.kind == "regression" and len(names) == 1 and options is not None and options.expectations_by_target:
        mapped = options.expectations_by_target.get(names[0], options.expectations)
        if options.expectations != TargetExpectations() and options.expectations != mapped:
            raise ValueError("Competing scalar and mapped numerical expectations.")
        options = replace(options, expectations=mapped, expectations_by_target={})
        config = replace(config, regression=options)
    if not m3:
        legacy_task = replace(task, target=names[0] if names else None, targets=(), feature_columns=None, metadata_columns=(), group_columns=())
        return legacy_task, config, roles, None
    methods = {"classification": "tabular_partial_classification_v1", "regression": "tabular_multioutput_regression_v1" if len(names) > 1 else "tabular_annotation_regression_v1",
               "multilabel_classification": "tabular_multilabel_v1", "clustering": "tabular_clustering_readiness_v1",
               "anomaly_detection": "tabular_anomaly_readiness_v1", "dataset_profile": "tabular_role_profile_v1"}
    return task, config, roles, methods[task.kind]


def specification_fingerprint(task, config, columns):
    task, config, roles, method = effective_policy(columns, task, config)
    # Use normalized membership and effective per-target declarations.
    annotations = config.annotations or AnnotationOptions(AnnotationSpec('expected') if method is None else AnnotationSpec())
    canonical = asdict(config)
    canonical.pop('annotations')
    for key in ('execution', 'advanced'):
        if canonical.get(key) is None: canonical.pop(key, None)
    if not canonical['parsing'].get('column_missing_policies'):
        canonical['parsing'].pop('column_missing_policies', None)
    canonical_annotations = {t: asdict(annotations.per_target.get(t, annotations.default)) for t in task.target_names}
    if config.regression:
        opt=config.regression
        canonical['regression']['expectations_by_target']={t:asdict(opt.expectations_by_target.get(t,opt.expectations if len(task.target_names)==1 else TargetExpectations())) for t in task.target_names}
        canonical['regression'].pop('expectations')
        canonical['regression']['feature_availability']={c:opt.feature_availability.get(c,'unknown') for c in roles['features']}
    body = {'kind':task.kind,'roles':roles,'method':method,'annotations':canonical_annotations,'config':canonical}
    return hashlib.sha256(json.dumps(json_safe(body), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def observation(series, kind):
    absent = series.isna().to_numpy()
    if kind == "multilabel_classification":
        def indicator(v):
            if pd.isna(v): return -1
            if isinstance(v, str): return int(v) if v in {"0", "1"} else -2
            return int(v) if isinstance(v, (bool, int, float, np.integer, np.floating)) and v in (0, 1) else -2
        values = np.fromiter((indicator(v) for v in series), dtype=np.int8, count=len(series))
        valid = values >= 0
    elif kind == "regression":
        valid = finite_mask(series).to_numpy() if numeric_column(series) else np.zeros(len(series), dtype=bool)
        values = None
    else:
        valid = ~absent
        values = None
    return {"valid": valid, "absent": absent, "invalid": ~valid & ~absent, "values": values}


def normalize_target(data, target, kind, spec, *, max_examples=5):
    obs = observation(data[target], kind)
    n = len(data)
    expectation = np.full(n, spec.expectation, dtype=object)
    status = np.full(n, "unspecified", dtype=object)
    unresolved = np.zeros(n, dtype=bool)
    if spec.status_column is not None:
        mapping = spec.status_values if spec.status_values is not None else canonical_status_values()
        for i, token in enumerate(data[spec.status_column]):
            state = mapping.get(token) if isinstance(token, str) else None
            if state is None:
                unresolved[i] = True
                # An explicit expected requirement survives unresolved metadata.
                expectation[i] = "expected" if spec.expectation == "expected" else "unknown"
                status[i] = "unresolved"
            else:
                expectation[i] = state.expectation or spec.expectation
                status[i] = state.annotation_status
    expected = expectation == "expected"
    unknown = expectation == "unknown"
    contradictions = ((status == "intentionally_unlabeled") & ~obs["absent"]) | ((status == "observed") & obs["absent"])
    supplied = expected & obs["valid"]
    unavailable = expected & ~obs["valid"]
    reason_masks = {"invalid": unavailable & obs["invalid"], "unresolved_status": unavailable & obs["absent"] & unresolved,
                    "missing": unavailable & obs["absent"] & ~unresolved}
    count = lambda mask: int(np.count_nonzero(mask))
    c = {"target": target, "total_rows": n, "raw_populated": count(~obs["absent"]), "observed": count(obs["valid"]),
         "absent": count(obs["absent"]), "invalid": count(obs["invalid"]),
         "expected": count(expected), "optional": count(expectation == "optional"), "unknown": count(expectation == "unknown"),
         "supplied_expected": count(supplied), "unavailable_expected": count(unavailable),
         "unavailable_expected_by_reason": {k: count(m) for k, m in reason_masks.items()},
         "intentional_absence": count((status == "intentionally_unlabeled") & obs["absent"]),
         "intentional_declarations": count(status == "intentionally_unlabeled"),
         "unresolved_metadata": count(unresolved), "unknown_expectation_population": count(unknown),
         "declaration_inconsistencies": count(contradictions),
         "uncertain_observed": count((status == "uncertain") & obs["valid"]),
         "uncertain_absent": count((status == "uncertain") & obs["absent"]),
         "observed_coverage": count(obs["valid"]) / n if n else None,
         "expected_coverage": count(supplied) / count(expected) if count(expected) else None,
         "unknown_expectation_coverage": count(unknown) / n if n else None,
         "uncertain_validity_share": count((status == "uncertain") & obs["valid"]) / count(obs["valid"]) if count(obs["valid"]) else None,
         "unavailable_reasons": {"expected_coverage": "no_resolved_expected_annotations" if not count(expected) else None,
                                 "uncertain_validity_share": "no_observed_annotations" if not count(obs["valid"]) else None},
         "examples": {k: (np.flatnonzero(m)[:max_examples] + 1).tolist() for k, m in {"invalid": obs["invalid"], "expected_gaps": unavailable, "unresolved_metadata": unresolved, "inconsistencies": contradictions}.items()}}
    return {**obs, "expectation": expectation, "status": status, "expected": expected, "supplied": supplied,
            "unavailable": unavailable, "unresolved": unresolved, "unknown": unknown, "contradictions": contradictions, "coverage": c}


def annotation_coverage(data, task, options, groups, *, max_examples=5):
    options = options or AnnotationOptions()
    n, k = len(data), len(task.target_names)
    observed = np.zeros(n, dtype=np.int32); expected = observed.copy(); supplied = observed.copy(); unknown = observed.copy(); uncertain = observed.copy()
    per_target = []
    unions={key:np.zeros(n,bool) for key in ('invalid','declaration_inconsistencies','unresolved_metadata','unavailable_expected','expected_gaps_high','expected_gaps_moderate')}
    group_data = None
    group_result = None
    if groups:
        complete = data[groups].notna().all(axis=1)
        ids = data.loc[complete].groupby(groups, dropna=False, sort=False).ngroup()
        sizes = ids.value_counts(sort=False)
        group_data = {int(i): {"row_count": int(sizes[i]), "observed_cells": 0, "expected_cells": 0, "supplied_cells": 0,
                               "targets_observed_somewhere": 0, "unknown_cells": 0, "mixed_state_targets": 0} for i in ids.unique()}
    for target in task.target_names:
        state = normalize_target(data, target, task.kind, options.per_target.get(target, options.default), max_examples=max_examples)
        per_target.append(state["coverage"])
        for key,mask in [('invalid',state['invalid']),('declaration_inconsistencies',state['contradictions']),('unresolved_metadata',state['unresolved']),('unavailable_expected',state['unavailable'])]:
            unions[key] |= mask
        c=state['coverage']
        if c['unavailable_expected']:
            severity='high' if c['unavailable_expected']/c['expected']>=.25 else 'moderate'
            unions['expected_gaps_'+severity] |= state['unavailable']
        observed += state["valid"]; expected += state["expected"]; supplied += state["supplied"]; unknown += state["unknown"]
        uncertain += (state["status"] == "uncertain") & state["valid"]
        if group_data is not None:
            for i, indexes in ids.groupby(ids).groups.items():
                indexes = np.asarray(indexes); g = group_data[int(i)]
                for key, mask in (("observed_cells",state["valid"]),("expected_cells",state["expected"]),("supplied_cells",state["supplied"]),("unknown_cells",state["unknown"])):
                    g[key] += int(mask[indexes].sum())
                g["targets_observed_somewhere"] += int(state["valid"][indexes].any())
                g["mixed_state_targets"] += int(len(set(zip(state["expectation"][indexes], state["status"][indexes], state["valid"][indexes]))) > 1)
    counts = lambda v: {str(x): int(c) for x, c in sorted(Counter(v.tolist()).items())}
    row = {"any_observed": int((observed > 0).sum()), "complete_observed_vector": int((observed == k).sum()),
           "partial_observed_vector": int(((observed > 0) & (observed < k)).sum()), "no_observed": int((observed == 0).sum()),
           "rows_with_expected": int((expected > 0).sum()), "every_expected_supplied": int(((expected > 0) & (expected == supplied)).sum()),
           "expected_gaps": int((expected > supplied).sum()), "unknown_components": int((unknown > 0).sum()), "uncertain_observed_components": int((uncertain > 0).sum()),
           "observed_component_histogram": counts(observed), "unknown_component_histogram": counts(unknown),
           "expected_vector_coverage": int(((expected > 0) & (expected == supplied)).sum()) / int((expected > 0).sum()) if (expected > 0).any() else None}
    row["affected_row_unions"] = {key:int(mask.sum()) for key,mask in unions.items()}
    if group_data is not None:
        eligible = [g for g in group_data.values() if g["expected_cells"]]
        for i, indexes in ids.groupby(ids).groups.items():
            g = group_data[int(i)]; g["complete_vector_on_one_row"] = bool((observed[np.asarray(indexes)] == k).any())
            g["any_annotation"] = bool(g["observed_cells"]); g["all_targets_somewhere"] = g["targets_observed_somewhere"] == k
            g["expected_gap"] = g["expected_cells"] > g["supplied_cells"]
            g["expected_coverage"] = g["supplied_cells"] / g["expected_cells"] if g["expected_cells"] else None
        group_result = {"keys": groups, "excluded_incomplete_key_rows": int((~complete).sum()), "group_count": len(group_data),
                        "any_annotation_groups": sum(g["any_annotation"] for g in group_data.values()),
                        "complete_vector_on_one_row_groups": sum(g["complete_vector_on_one_row"] for g in group_data.values()),
                        "all_targets_somewhere_groups": sum(g["all_targets_somewhere"] for g in group_data.values()),
                        "expected_gap_groups": sum(g["expected_gap"] for g in group_data.values()),
                        "unknown_expectation_groups": sum(g["unknown_cells"] > 0 for g in group_data.values()),
                        "mixed_state_groups": sum(g["mixed_state_targets"] > 0 for g in group_data.values()),
                        "expected_group_denominator": len(eligible),
                        "pooled_expected_cell_coverage": sum(g["supplied_cells"] for g in eligible) / sum(g["expected_cells"] for g in eligible) if eligible else None,
                        "equally_weighted_expected_group_coverage": sum(g["expected_coverage"] for g in eligible) / len(eligible) if eligible else None,
                        "pooled_observed_cell_coverage": sum(g["observed_cells"] for g in group_data.values()) / (int(complete.sum()) * k) if complete.any() else None,
                        "equally_weighted_observed_group_coverage": sum(g["observed_cells"] / (g["row_count"] * k) for g in group_data.values()) / len(group_data) if group_data else None,
                        "interpretation": "Keys group supplied records; entities, chronology, independence, and leakage are not inferred."}
    return {"targets": per_target, "rows": row, "groups": group_result,
            "meaning": "Expectation, observation, status, and validity declarations are independent axes; counts can overlap."}, observed


def feature_semantics(data, features, options):
    result = []
    for c in features:
        s = data[c]; declared = options.semantic_types.get(c)
        if declared == "quantitative" and not numeric_column(s):
            raise ValueError(f"Declared quantitative feature {c!r} must have numeric, nonboolean storage.")
        finite = s[finite_mask(s)] if numeric_column(s) else None
        ambiguous = pd.api.types.is_bool_dtype(s) or (finite is not None and len(finite) > 0 and finite.nunique() <= 20 and finite.map(lambda v: float(v).is_integer()).all())
        name_context = any(t in c.lower().replace("-", "_").split("_") for t in ("id", "identifier", "index"))
        identifier_candidate = finite is not None and name_context and s.nunique() / len(s) >= .98
        resolved = declared or ("ambiguous_identifier" if identifier_candidate else "ambiguous_code" if ambiguous else "assumed_quantitative" if finite is not None else "categorical")
        result.append({"column": c, "declaration": declared, "semantic_type": resolved,
                       "quantitative_geometry": resolved in {"quantitative", "assumed_quantitative"},
                       "representation_assumption": "Numeric storage is treated as quantitative; meaning and units are undeclared." if resolved == "assumed_quantitative" else None,
                       "unique_share": int(s.nunique()) / len(s) if len(s) else None,
                       "identifier_name_context": name_context})
    return result


def cohort_evidence(data, task, options, semantics, observed_counts, limits, checkpoint):
    options = options or AnnotationOptions()
    def cohorts():
        yield ("any_observed_vs_none", observed_counts > 0, observed_counts == 0)
        for t in task.target_names:
            state = normalize_target(data, t, task.kind, options.per_target.get(t, options.default))
            yield (t + ":observed_vs_expected_missing", state["valid"], state["expected"] & state["absent"])
            yield (t + ":observed_vs_intentional_absence", state["valid"], (state["status"] == "intentionally_unlabeled") & state["absent"])
            yield (t + ":observed_vs_unresolved", state["valid"], (state["unknown"] | state["unresolved"]) & ~state["valid"])
    records = []; used = 0; excluded = []
    for name, a, b in cohorts():
        for semantic in semantics:
            checkpoint("annotation cohort")
            c = semantic["column"]; work = len(data)
            if used + work > limits.max_cohort_comparisons:
                excluded.append({"cohort": name, "feature": c, "reason": "planned_work_limit"}); continue
            used += work; sa, sb = data.loc[a, c], data.loc[b, c]
            row = {"cohort": name, "feature": c, "sizes": [len(sa),len(sb)], "missing_counts": [int(sa.isna().sum()),int(sb.isna().sum())],
                   "missing_shares": [int(s.isna().sum()) / len(s) if len(s) else None for s in (sa,sb)], "numerical": None,"categorical":None, "reason":None}
            if numeric_column(data[c]):
                row['nonfinite_counts'] = [int((s.notna() & ~finite_mask(s)).sum()) for s in (sa,sb)]
            if semantic["quantitative_geometry"]:
                fs = [s[finite_mask(s)] for s in (sa,sb)]
                if min(map(len, fs)) < 20: row['reason'] = 'fewer_than_20_finite_per_cohort'
                else:
                    stats = [shape_evidence(s) for s in fs]
                    if any(s['reason'] for s in stats): row['reason']='unsafe_numerical_shape'
                    else: row['numerical'] = [{'finite_count':len(f), 'median':s['median'],'iqr':s['iqr']} for f,s in zip(fs,stats)]
            else:
                counts = [s.value_counts() for s in (sa,sb)]; vocabulary = set(counts[0].index) | set(counts[1].index)
                if len(vocabulary) > 100: row['reason']='more_than_100_categories'
                elif any(s.notna().sum() == 0 for s in (sa,sb)): row['reason']='empty_observed_category_cohort'
                else:
                    proportions=[{str(k):int(v)/int(s.notna().sum()) for k,v in cnt.items()} for s,cnt in zip((sa,sb),counts)]
                    tv=.5*sum(abs(int(counts[0].get(v,0))/int(sa.notna().sum())-int(counts[1].get(v,0))/int(sb.notna().sum())) for v in vocabulary)
                    row['categorical']={'total_variation_distance':tv,'category_count':len(vocabulary),'proportions':proportions}
            records.append(row)
    return {'records':records,'comparisons':used,'excluded':excluded,'status':'bounded' if excluded else 'completed',
            'interpretation':'Within-file observed annotation populations only; contrasts do not establish representativeness, missingness mechanisms, or deployment shift.'}
