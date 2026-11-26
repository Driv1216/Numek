"""J2 validation: reproduces every number in DOSSIER.md.

Run from the repository root:
    python validation/regression_dependency/fixtures.py
    python validation/regression_dependency/validate.py            # writes results/results.json, results/tables.md
    python validation/regression_dependency/validate.py --timing   # also writes results/timing.json (machine-dependent)

results.json and tables.md are deterministic (no timings, fixed seeds); a rerun is byte-identical.
The existing relationship search (src/datatrust/regression.py) is imported read-only to know which features it
already verifies as copy/affine. No product code is changed or monkey-patched.
"""
import hashlib
import json
import sys
import time
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "src"))

import prototype as P  # noqa: E402

NULL_SEEDS = range(100)
GRID_K = (1, 2, 3, 5, 8)
GRID_M = (1, 2, 3, 5, 8)
REG = REPO / "validation/regression"
M3 = REPO / "validation/m3/data/prepared"
CASES = REPO / "validation/report_experience/work.nosync/dashboard/cases"

# ——— Negative corpus: retained regression and M3 cases ———
NEGATIVE = [
    *[dict(name=f"mutation:{m}", path=REG / f"data/mutations/{m}.csv", targets=["outcome"],
           cases={"sum": ["regression_sum", "regression_bounded"], "constraint_union": ["regression_constraint_union"],
                  "rounded_legitimate": ["regression_rounded_legitimate"]}.get(m, []))
      for m in ("copy", "affine", "sum", "sparse_copy", "missing_nonfinite", "constant", "constraint_union", "rounded_legitimate",
                "heavy_tail_legitimate", "skew_legitimate", "bounded_legitimate", "zero_inflated_count", "repeated_measurements")],
    dict(name="presentation:ambiguous", path=REG / "data/presentation/ambiguous.csv", targets=["outcome"], cases=[]),
    dict(name="presentation:partial", path=REG / "data/presentation/partial.csv", targets=["outcome"], cases=["regression_partial"]),
    dict(name="concrete", path=REG / "data/prepared/concrete.csv", targets=["strength_mpa"], cases=["regression_concrete"]),
    dict(name="bike_hour", path=REG / "data/prepared/bike_hour.csv", targets=["cnt"], cases=["bike_hour"]),
    dict(name="bike_hour_components_removed", path=REG / "data/prepared/bike_hour_components_removed.csv", targets=["cnt"], cases=[]),
    dict(name="bike_day", path=REG / "data/prepared/bike_day.csv", targets=["cnt"], cases=[]),
    dict(name="bike_day_components_removed", path=REG / "data/prepared/bike_day_components_removed.csv", targets=["cnt"], cases=[]),
    dict(name="m3:energy", path=M3 / "energy.csv", targets=["heating_load", "cooling_load"], cases=["multioutput_energy"]),
    dict(name="m3:linnerud", path=M3 / "linnerud.csv", targets=["Weight", "Waist", "Pulse"], cases=["multioutput_linnerud"]),
    dict(name="annotation_regression", path=CASES / "annotation_regression_single/inputs/annotation_regression.csv",
         targets=["yield_kg"], cases=["annotation_regression_single"]),
]
# Wide stress only: scene has no regression target; Att1 is a pseudo-target, labels are excluded.
STRESS = [dict(name="m3:scene_pseudo_target", path=M3 / "scene.csv", targets=["Att1"], cases=["m3_scene"],
               exclude=["Beach", "Sunset", "FallFoliage", "Field", "Mountain", "Urban"])]
NOT_RERUN = {"multioutput_linnerud_masked": "input CSV not retained on disk (20-row linnerud derivative; below every row gate)",
             "multioutput_regression_empty": "input CSV not retained on disk (no finite targets by construction)"}

# Hand review of every exact flag on the negative corpus, from each case's construction (validation/regression/mutate.py,
# the presentation CSVs). Unreviewed flags are reported as such and counted as false positives.
REVIEW = {
    ("mutation:sum", "outcome", "a"): ("true_relationship_by_construction", "a = sqrt(outcome) with outcome = 0..99, so outcome = a^2 is strictly increasing in a."),
    ("mutation:missing_nonfinite", "outcome", "input"): ("true_relationship_by_construction", "input = y^2 over 97 finite y = 0..96, so the target is a strictly increasing function of input."),
    ("mutation:constraint_union", "outcome", "input"): ("true_relationship_by_construction", "input = i^2 for i = 0..99 and outcome = i except rows 1-2 set to -1 and -0.5, which keep the order: strictly increasing."),
    ("presentation:partial", "outcome", "qa_optional_failure"): ("true_relationship_by_construction", "qa_optional_failure = outcome^2 with outcome = 0..39: strictly increasing."),
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rel(path):
    return str(Path(path).resolve().relative_to(REPO))


def existing_covered(data, target, features):
    """Features the existing search verifies as exact copy or affine identity of the target (read-only import)."""
    from datatrust.contracts import RegressionOptions
    from datatrust.regression import relationship_evidence
    try:
        result = relationship_evidence(data, target, RegressionOptions(), lambda *a: None, feature_columns=features)
    except Exception as exc:  # disclosed, never silent
        return set(), [], f"{type(exc).__name__}: {exc}"
    rels = [{"method": r["method"], "columns": r["columns"], "expression": r["expression"]} for r in result["relationships"]]
    covered = {r["columns"][0] for r in result["relationships"] if r["method"] in {"exact_copy", "affine_identity"}}
    return covered, rels, None


VARIANTS = {
    "proposed": P.Variant(tolerant=True),
    "A1_no_identifier_gate": P.Variant(identifier_gate=False),
    "A2_singletons_count": P.Variant(singletons_excluded=False),
    "A3_contextual_v1_support": P.Variant(contextual_v1_support=True),
    "A4_naive_no_support": P.Variant(naive=True, identifier_gate=False),
    "A5_no_redundancy_rule": P.Variant(redundancy_rule=False),
    "A6_no_identifier_gate_singletons_count": P.Variant(identifier_gate=False, singletons_excluded=False),
}
# Grids: the proposal; the same with the identifier gate off (isolates what k and m contribute); and the tolerant
# variant with the identifier gate off (where repeated support is the only protection against small-category inflation).
GRIDS = {"grid": P.Variant(), "grid_noid": P.Variant(identifier_gate=False), "grid_noid_tolerant": P.Variant(identifier_gate=False, tolerant=True)}


def evaluate(data, targets, features_for, covered_for, *, gates=P.Gates(), limits=P.Limits(), grid=False):
    """Stats once per feature-target (budget shared across targets); decisions for every variant and grid point."""
    budget = {"features": set(), "checks": 0, "row_work": 0}
    out = {"targets": {}, "budget": budget}
    for t in targets:
        y = data[t]
        record = {"searched": [], "unsearched": [], "flags": {v: [] for v in VARIANTS}, "near_flags": [], "status": "completed",
                  "identifier_exclusions": {}, "text_identifier_exclusions": 0, **{g: {} for g in GRIDS}}
        out["targets"][t] = record
        if not P.is_numeric(y) or int(P.finite(y).sum()) == 0 or y[P.finite(y)].nunique() < gates.min_distinct_targets:
            record["status"] = "not_assessable"; record["unsearched"] = list(features_for(t)); continue
        tt = set(P.tokens(t))
        feats = sorted(features_for(t), key=lambda c: not (tt & set(P.tokens(c)) or set(P.tokens(c)) & {"actual", "final", "outcome", "post", "result", "label", "future"}))
        for i, f in enumerate(feats):
            if (f not in budget["features"] and len(budget["features"]) >= limits.max_features) or budget["checks"] >= limits.max_checks \
                    or budget["row_work"] + len(data) > limits.max_row_work:
                record["unsearched"] = feats[i:]; record["status"] = "bounded"; break
            budget["features"].add(f); budget["checks"] += 1; budget["row_work"] += len(data)
            s = P.feature_stats(data, t, f, gates=gates, covered=covered_for(t), want_spearman=True)
            record["searched"].append(f)
            if s.identifier:
                record["identifier_exclusions"].setdefault(s.identifier, []).append(f)
                record["text_identifier_exclusions"] += not s.numeric
            for name, variant in VARIANTS.items():
                c = P.decide(s, gates, variant)
                if c["flag"] and c["flag"]["strength"] == "exact":
                    record["flags"][name].append({"feature": f, "family": c["flag"]["family"], "form": c["flag"]["form"]})
                elif c["flag"] and name == "proposed":
                    record["near_flags"].append({"feature": f, "family": c["flag"]["family"]})
            if grid:
                for k in GRID_K:
                    for m in GRID_M:
                        g = replace(gates, supported_categories_k=k, category_support_m=m)
                        for gname, gvariant in GRIDS.items():
                            c = P.decide(s, g, gvariant)
                            if c["flag"]:
                                record[gname].setdefault(f"k{k}_m{m}", []).append({"feature": f, "family": c["flag"]["family"], "strength": c["flag"]["strength"]})
    return out


def load(spec):
    data = pd.read_csv(spec["path"])
    excluded = set(spec["targets"]) | set(spec.get("exclude", []))
    features = [c for c in data.columns if c not in excluded]
    return data, features


def observed_run(spec, *, with_block=True):
    data, features = load(spec)
    covered, existing, error = {}, {}, {}
    for t in spec["targets"]:
        cv, rels, err = existing_covered(data, t, features)
        covered[t], existing[t], error[t] = cv, rels, err
    result = evaluate(data, spec["targets"], lambda t: features, lambda t: covered[t], grid=True)
    blocks = {}
    if with_block:
        budget = {"features": set(), "checks": 0, "row_work": 0}
        for t in spec["targets"]:
            blocks[t] = P.search(data, t, features=features, covered=covered[t], budget=budget)
    return data, features, covered, existing, error, result, blocks


def null_run(data, targets, features, *, seeds=NULL_SEEDS):
    """Target permutation over the same columns. Redundancy rule is not applied (nothing is covered)."""
    totals = {v: 0 for v in VARIANTS}; near = 0; grid = {g: {} for g in GRIDS}; checks = 0; examples = []
    for seed in seeds:
        rng = np.random.default_rng(seed)
        permuted = data.copy()
        for t in targets:
            permuted[t] = data[t].to_numpy()[rng.permutation(len(data))]
        r = evaluate(permuted, targets, lambda t: features, lambda t: frozenset(), grid=True)
        for t, rec in r["targets"].items():
            checks += len(rec["searched"])
            for v in VARIANTS:
                totals[v] += len(rec["flags"][v])
                if v == "proposed" and rec["flags"][v] and len(examples) < 5:
                    examples.append({"seed": seed, "target": t, "flags": rec["flags"][v]})
            near += len(rec["near_flags"])
            for gname in GRIDS:
                for key, flags in rec[gname].items():
                    grid[gname][key] = grid[gname].get(key, 0) + len(flags)
    return {"seeds": len(seeds), "feature_checks": checks, "flags": totals, "near_flags": near, "grid": grid, "proposed_examples": examples}


def per100(flags, features):
    return round(100 * flags / features, 3) if features else None


def main(timing=False):
    fixtures = json.loads((HERE / "fixtures/manifest.json").read_text())
    results = {"method_id": P.METHOD_ID, "gates": P.asdict(P.Gates()), "limits": P.asdict(P.Limits()),
               "null_seeds": len(NULL_SEEDS), "grid": {"k": GRID_K, "m": GRID_M},
               "prototype_sha256": sha(HERE / "prototype.py"), "fixtures_manifest_sha256": sha(HERE / "fixtures/manifest.json"),
               "negative": [], "stress": [], "positive": [], "hard_null": [], "not_rerun": NOT_RERUN}

    # ——— Negative corpus ———
    for spec in NEGATIVE + STRESS:
        data, features, covered, existing, error, r, blocks = observed_run(spec)
        null = null_run(data, spec["targets"], features)
        entry = {"name": spec["name"], "file": rel(spec["path"]), "sha256": sha(spec["path"]), "rows": len(data), "features": len(features),
                 "dashboard_cases": spec["cases"], "targets": {}, "null": null,
                 "budget": {"features": len(r["budget"]["features"]), "checks": r["budget"]["checks"], "row_work": r["budget"]["row_work"]}}
        for t, rec in r["targets"].items():
            flags = []
            for f in rec["flags"]["proposed"]:
                label, note = REVIEW.get((spec["name"], t, f["feature"]), ("UNREVIEWED", "No hand review recorded; counted as a false positive."))
                block_flag = next((b for b in blocks[t]["flags"] if b["feature"] == f["feature"]), None)
                flags.append({**f, "review": label, "review_note": note, "severity_if_undeclared": block_flag["severity"] if block_flag else None,
                              "wording": block_flag["wording"] if block_flag else None})
            entry["targets"][t] = {"status": rec["status"], "searched": len(rec["searched"]), "unsearched": len(rec["unsearched"]),
                                   "identifier_exclusions": {k: v for k, v in rec["identifier_exclusions"].items()},
                                   "covered_by_existing": sorted(covered[t]), "existing_relationships": existing[t], "existing_error": error[t],
                                   "flags": flags, "near_flags": rec["near_flags"],
                                   "ablation_flags": {v: rec["flags"][v] for v in VARIANTS if v != "proposed"},
                                   "grid_flags": {k: len(v) for k, v in rec["grid"].items()},
                                   "text_identifier_exclusions": rec["text_identifier_exclusions"]}
        (results["stress"] if spec in STRESS else results["negative"]).append(entry)

    # ——— Positive corpus ———
    for name, meta in fixtures["positive"].items():
        path = HERE / meta["file"]
        spec = dict(name=name, path=path, targets=["target"])
        data, features, covered, existing, error, r, blocks = observed_run(spec)
        rec = r["targets"]["target"]
        planted = meta["planted_feature"]
        exact = {f["feature"]: f for f in rec["flags"]["proposed"]}
        near = {f["feature"]: f for f in rec["near_flags"]}
        entry = {"name": name, "sha256": sha(path), "family": meta["family"], "noise": meta["noise"], "note": meta["note"],
                 "planted": planted, "features": len(features), "covered_by_existing": sorted(covered["target"]),
                 "existing_relationships": existing["target"],
                 "planted_exact": planted in exact, "planted_family_found": exact.get(planted, {}).get("family"),
                 "planted_form": exact.get(planted, {}).get("form"), "planted_near": planted in near,
                 "false_exact": [f for f in exact if f != planted], "false_near": [f for f in near if f != planted],
                 "identifier_exclusions": rec["identifier_exclusions"],
                 "ablation_planted": {v: any(f["feature"] == planted for f in rec["flags"][v]) for v in VARIANTS},
                 "ablation_false": {v: sum(f["feature"] != planted for f in rec["flags"][v]) for v in VARIANTS},
                 "grid_planted": {k: any(f["feature"] == planted for f in v) for k, v in rec["grid"].items()},
                 "grid_false": {k: sum(f["feature"] != planted for f in v) for k, v in rec["grid"].items()},
                 "check": next(c for c in blocks["target"]["checks"] if c["feature"] == planted)["families"],
                 "null": null_run(data, ["target"], features)}
        results["positive"].append(entry)

    # ——— Hard nulls ———
    for name, meta in fixtures["hard_null"].items():
        path = HERE / meta["file"]
        spec = dict(name=name, path=path, targets=["target"])
        data, features, covered, existing, error, r, blocks = observed_run(spec)
        rec = r["targets"]["target"]
        results["hard_null"].append({"name": name, "sha256": sha(path), "rows": len(data), "features": len(features),
                                     "observed_flags": {v: rec["flags"][v] for v in VARIANTS}, "observed_grid": {k: len(v) for k, v in rec["grid"].items()},
                                     "observed_grid_noid": {k: len(v) for k, v in rec["grid_noid"].items()},
                                     "identifier_exclusions": rec["identifier_exclusions"], "null": null_run(data, ["target"], features)})

    results["summary"] = summarise(results)
    (HERE / "results").mkdir(exist_ok=True)
    text = json.dumps(results, indent=1, sort_keys=True, default=lambda o: sorted(o) if isinstance(o, (set, frozenset)) else str(o)) + "\n"
    (HERE / "results/results.json").write_text(text)
    (HERE / "results/tables.md").write_text(tables(results))
    if timing:
        (HERE / "results/timing.json").write_text(json.dumps(benchmark(), indent=1) + "\n")
    print(json.dumps(results["summary"]["headline"], indent=1))


def summarise(res):
    s = {}
    # Null: every corpus, permuted.
    groups = {"negative": res["negative"], "stress": res["stress"], "positive": res["positive"], "hard_null": res["hard_null"]}
    s["null"] = {}
    for g, items in groups.items():
        checks = sum(i["null"]["feature_checks"] for i in items)
        s["null"][g] = {"datasets": len(items), "feature_checks": checks,
                        "flags": {v: sum(i["null"]["flags"][v] for i in items) for v in VARIANTS},
                        "near_flags": sum(i["null"]["near_flags"] for i in items)}
    all_items = [i for items in groups.values() for i in items]
    s["null"]["all"] = {"datasets": len(all_items), "feature_checks": sum(i["null"]["feature_checks"] for i in all_items),
                        "flags": {v: sum(i["null"]["flags"][v] for i in all_items) for v in VARIANTS},
                        "near_flags": sum(i["null"]["near_flags"] for i in all_items)}
    # Grid over the null and the corpora.
    grid = {}
    pos_cat = [p for p in res["positive"] if p["family"] in {"categorical_determination", "target_interval_coding"} and p["note"] != "below_support_by_design"]
    for k in GRID_K:
        for m in GRID_M:
            key = f"k{k}_m{m}"
            grid[key] = {"k": k, "m": m,
                         "null_flags_all": sum(i["null"]["grid"]["grid"].get(key, 0) for i in all_items),
                         "null_flags_hard": sum(i["null"]["grid"]["grid"].get(key, 0) for i in res["hard_null"]),
                         "null_flags_noid": sum(i["null"]["grid"]["grid_noid"].get(key, 0) for i in all_items),
                         "null_flags_noid_tolerant": sum(i["null"]["grid"]["grid_noid_tolerant"].get(key, 0) for i in all_items),
                         "hard_observed_flags_noid": sum(i["observed_grid_noid"].get(key, 0) for i in res["hard_null"]),
                         "hard_observed_flags": sum(i["observed_grid"].get(key, 0) for i in res["hard_null"]),
                         "negative_flags": sum(t["grid_flags"].get(key, 0) for i in res["negative"] for t in i["targets"].values()),
                         "categorical_recall_clean": sum(p["grid_planted"].get(key, False) for p in pos_cat if p["noise"] == "none"),
                         "categorical_recall_clean_of": sum(p["noise"] == "none" for p in pos_cat),
                         "categorical_recall_all": sum(p["grid_planted"].get(key, False) for p in pos_cat),
                         "categorical_recall_all_of": len(pos_cat),
                         "positive_false": sum(p["grid_false"].get(key, 0) for p in res["positive"])}
    s["grid"] = grid
    # Positive corpus metrics.
    scored = [p for p in res["positive"] if p["note"] == ""]
    def metrics(items, near=False):
        tp = sum(p["planted_exact"] or (near and p["planted_near"]) for p in items)
        fp = sum(len(p["false_exact"]) + (len(p["false_near"]) if near else 0) for p in items)
        feats = sum(p["features"] for p in items)
        return {"datasets": len(items), "planted": len(items), "tp": tp, "fn": len(items) - tp, "fp": fp,
                "precision": round(tp / (tp + fp), 4) if tp + fp else None, "recall": round(tp / len(items), 4) if items else None,
                "features": feats, "flags_per_100_features": per100(tp + fp, feats), "false_flags_per_100_features": per100(fp, feats)}
    s["positive"] = {}
    for label, near in (("strict", False), ("strict_plus_tolerant", True)):
        s["positive"][label] = {"all": metrics(scored, near)}
        for noise in ("none", "meas", "label1"):
            s["positive"][label][f"noise_{noise}"] = metrics([p for p in scored if p["noise"] == noise], near)
        for fam in ("categorical_determination", "target_interval_coding", "monotone_mapping"):
            s["positive"][label][fam] = metrics([p for p in scored if p["family"] == fam], near)
    s["positive"]["by_design"] = [{"name": p["name"], "note": p["note"], "planted_exact": p["planted_exact"], "check": p["check"]}
                                   for p in res["positive"] if p["note"]]
    s["positive"]["ablation"] = {v: {"recall": round(sum(p["ablation_planted"][v] for p in scored) / len(scored), 4),
                                     "recall_clean": round(sum(p["ablation_planted"][v] for p in scored if p["noise"] == "none") / sum(p["noise"] == "none" for p in scored), 4),
                                     "false_flags": sum(p["ablation_false"][v] for p in res["positive"])} for v in VARIANTS}
    # Negative corpus.
    neg_flags = [dict(dataset=i["name"], target=t, **f) for i in res["negative"] for t, r in i["targets"].items() for f in r["flags"]]
    neg_features = sum(r["searched"] for i in res["negative"] for r in i["targets"].values())
    reviewed_true = sum(f["review"] == "true_relationship_by_construction" for f in neg_flags)
    s["negative"] = {"datasets": len(res["negative"]), "feature_checks": neg_features, "flags": len(neg_flags),
                     "reviewed_true": reviewed_true, "false_or_unreviewed": len(neg_flags) - reviewed_true,
                     "flags_per_100_features": per100(len(neg_flags), neg_features),
                     "false_flags_per_100_features": per100(len(neg_flags) - reviewed_true, neg_features),
                     "near_flags": sum(len(r["near_flags"]) for i in res["negative"] for r in i["targets"].values()),
                     "identifier_exclusions": sum(len(v) for i in res["negative"] for r in i["targets"].values() for v in r["identifier_exclusions"].values()),
                     "text_identifier_exclusions": sum(r["text_identifier_exclusions"] for i in res["negative"] for r in i["targets"].values()),
                     "ablation_flags": {v: sum(len(r["ablation_flags"][v]) for i in res["negative"] for r in i["targets"].values()) for v in VARIANTS if v != "proposed"}}
    stress_flags = sum(len(r["flags"]) for i in res["stress"] for r in i["targets"].values())
    s["stress"] = {"flags": stress_flags, "near_flags": sum(len(r["near_flags"]) for i in res["stress"] for r in i["targets"].values()),
                   "searched": sum(r["searched"] for i in res["stress"] for r in i["targets"].values()),
                   "unsearched": sum(r["unsearched"] for i in res["stress"] for r in i["targets"].values())}
    # Combined precision (positive corpus + reviewed negative corpus), strict.
    p = s["positive"]["strict"]["all"]
    tp, fp = p["tp"] + reviewed_true, p["fp"] + (len(neg_flags) - reviewed_true) + stress_flags
    s["combined_strict"] = {"tp": tp, "fp": fp, "precision": round(tp / (tp + fp), 4) if tp + fp else None}
    s["headline"] = {"null_flags_proposed_all_corpora": s["null"]["all"]["flags"]["proposed"],
                     "null_feature_checks": s["null"]["all"]["feature_checks"],
                     "null_near_flags": s["null"]["all"]["near_flags"],
                     "positive_strict": s["positive"]["strict"]["all"], "positive_strict_clean": s["positive"]["strict"]["noise_none"],
                     "negative": {k: s["negative"][k] for k in ("flags", "reviewed_true", "false_or_unreviewed", "feature_checks")},
                     "combined_strict_precision": s["combined_strict"]["precision"]}
    return s


def fmt(v):
    return "–" if v is None else f"{v:.3f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v)


def tables(res):
    s = res["summary"]; out = ["# J2 validation tables (generated by validate.py; do not edit)\n"]
    out.append(f"prototype.py sha256 `{res['prototype_sha256']}`; fixtures manifest sha256 `{res['fixtures_manifest_sha256']}`\n")
    out.append("## Permutation null (target permuted, 100 seeds)\n")
    out.append("| Corpus | Datasets | Feature checks | Proposed | A1 no identifier gate | A2 singletons count | A3 context_v1 support | A4 naive | A5 no redundancy | A6 no identifier gate + singletons count | Tolerant (near) |")
    out.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for g in ("negative", "stress", "positive", "hard_null", "all"):
        n = s["null"][g]; f = n["flags"]
        out.append(f"| {g} | {n['datasets']} | {n['feature_checks']:,} | {f['proposed']} | {f['A1_no_identifier_gate']} | {f['A2_singletons_count']} | "
                   f"{f['A3_contextual_v1_support']} | {f['A4_naive_no_support']} | {f['A5_no_redundancy_rule']} | {f['A6_no_identifier_gate_singletons_count']} | {n['near_flags']} |")
    out.append("\n## Repeated-support grid (k supported categories, each with >= m rows; 80% row share)\n")
    out.append("| k | m | Null flags, proposal (100 seeds, all corpora) | of which hard nulls | Null flags, identifier gate off | Null flags, identifier gate off + tolerant | Hard nulls as observed, identifier gate off | Negative corpus flags | Categorical recall, clean | Categorical recall, all noise | Positive false flags |")
    out.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for key, g in s["grid"].items():
        out.append(f"| {g['k']} | {g['m']} | {g['null_flags_all']:,} | {g['null_flags_hard']:,} | {g['null_flags_noid']:,} | {g['null_flags_noid_tolerant']:,} | {g['hard_observed_flags_noid']} | {g['negative_flags']} | "
                   f"{g['categorical_recall_clean']}/{g['categorical_recall_clean_of']} | {g['categorical_recall_all']}/{g['categorical_recall_all_of']} | {g['positive_false']} |")
    out.append("\n## Positive corpus (planted, one planted feature + 4 noise features per dataset)\n")
    out.append("| Method | Stratum | Datasets | TP | FN | FP | Precision | Recall | Flags / 100 features | False flags / 100 features |")
    out.append("|---|---|---|---|---|---|---|---|---|---|")
    for label in ("strict", "strict_plus_tolerant"):
        for key, m in s["positive"][label].items():
            out.append(f"| {label} | {key} | {m['datasets']} | {m['tp']} | {m['fn']} | {m['fp']} | {fmt(m['precision'])} | {fmt(m['recall'])} | "
                       f"{fmt(m['flags_per_100_features'])} | {fmt(m['false_flags_per_100_features'])} |")
    out.append("\n### Per fixture (strict = proposed v1)\n")
    out.append("| Fixture | Family planted | Noise | Strict | Family found | Tolerant only | Existing search | Other flags |")
    out.append("|---|---|---|---|---|---|---|---|")
    for p in res["positive"]:
        ex = "; ".join(r["expression"] for r in p["existing_relationships"]) or "none"
        out.append(f"| {p['name']} | {p['family']} | {p['noise']} | {'yes' if p['planted_exact'] else 'no'} | "
                   f"{(p['planted_family_found'] or '') + ('/' + p['planted_form'] if p['planted_form'] else '')} | "
                   f"{'yes' if p['planted_near'] else ''} | {ex} | {len(p['false_exact'])} |")
    out.append("\n### Ablations on the positive corpus\n")
    out.append("| Variant | Recall (all) | Recall (clean) | False flags |")
    out.append("|---|---|---|---|")
    for v, a in s["positive"]["ablation"].items():
        out.append(f"| {v} | {fmt(a['recall'])} | {fmt(a['recall_clean'])} | {a['false_flags']} |")
    out.append("\n## Negative corpus (retained regression and M3 cases, observed data)\n")
    out.append("| Dataset | Rows | Features | Target | Status | Searched | Identifier exclusions | Covered by existing copy/affine | Existing relationships | Strict flags | Near flags | A4 naive flags |")
    out.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for i in res["negative"] + res["stress"]:
        for t, r in i["targets"].items():
            ids = ", ".join(f"{k}: {len(v)}" for k, v in r["identifier_exclusions"].items()) or "0"
            ex = "; ".join(x["expression"] for x in r["existing_relationships"]) or "none"
            fl = "; ".join(f"{f['feature']} ({f['family']}/{f['form'] or ''}, {f['review']})" for f in r["flags"]) or "0"
            out.append(f"| {i['name']} | {i['rows']:,} | {i['features']} | {t} | {r['status']} | {r['searched']} | {ids} | {', '.join(r['covered_by_existing']) or '–'} | "
                       f"{ex} | {fl} | {len(r['near_flags'])} | {len(r['ablation_flags']['A4_naive_no_support'])} |")
    n = s["negative"]
    out.append(f"\nNegative corpus totals: {n['datasets']} datasets, {n['feature_checks']} feature checks, {n['flags']} strict flags "
               f"({n['reviewed_true']} reviewed true by construction, {n['false_or_unreviewed']} false or unreviewed), "
               f"{fmt(n['flags_per_100_features'])} flags / 100 features, {fmt(n['false_flags_per_100_features'])} false flags / 100 features; "
               f"{n['identifier_exclusions']} identifier exclusions ({n['text_identifier_exclusions']} of them text columns); near flags {n['near_flags']}.")
    out.append(f"Ablation flags on the negative corpus: " + ", ".join(f"{k} {v}" for k, v in n["ablation_flags"].items()) + ".")
    out.append(f"Stress (scene pseudo-target): {s['stress']['flags']} strict flags, {s['stress']['near_flags']} near flags, "
               f"{s['stress']['searched']} searched, {s['stress']['unsearched']} unsearched (bounded at 64 features).")
    out.append(f"Combined strict precision (positive + reviewed negative + stress): {s['combined_strict']['tp']} TP, {s['combined_strict']['fp']} FP, "
               f"precision {fmt(s['combined_strict']['precision'])}.")
    out.append(f"Not re-run: " + "; ".join(f"{k} ({v})" for k, v in res["not_rerun"].items()) + ".")
    out.append("\n## Hard nulls (independent targets shaped to provoke chance determination)\n")
    out.append("| Fixture | Rows | Features | Identifier exclusions | Observed: proposed | A1 | A2 | A3 | A4 naive | A6 | Null (100 seeds): proposed | A2 | A4 naive | A6 |")
    out.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for h in res["hard_null"]:
        o = h["observed_flags"]; nl = h["null"]["flags"]
        ids = ", ".join(f"{k}: {len(v)}" for k, v in h["identifier_exclusions"].items()) or "0"
        out.append(f"| {h['name']} | {h['rows']} | {h['features']} | {ids} | {len(o['proposed'])} | {len(o['A1_no_identifier_gate'])} | {len(o['A2_singletons_count'])} | "
                   f"{len(o['A3_contextual_v1_support'])} | {len(o['A4_naive_no_support'])} | {len(o['A6_no_identifier_gate_singletons_count'])} | {nl['proposed']} | {nl['A2_singletons_count']} | {nl['A4_naive_no_support']} | {nl['A6_no_identifier_gate_singletons_count']} |")
    out.append("\n## Budget (DependencyLimits: 64 features, 128 checks, 2e8 row work)\n")
    out.append("| Dataset | Features | Checks | Row work | Share of row-work limit |")
    out.append("|---|---|---|---|---|")
    for i in res["negative"] + res["stress"]:
        b = i["budget"]
        out.append(f"| {i['name']} | {b['features']} | {b['checks']} | {b['row_work']:,} | {100 * b['row_work'] / 2e8:.4f}% |")
    return "\n".join(out) + "\n"


def benchmark():
    """Machine-dependent wall time for the grouped pass (informational only)."""
    rng = np.random.default_rng(7)
    rows = []
    for n in (100_000, 1_000_000):
        frame = pd.DataFrame({"cat": rng.integers(0, 50, n).astype(str), "code": rng.integers(0, 30, n), "x": rng.normal(size=n),
                              "x2": rng.lognormal(size=n), "target": rng.normal(size=n)})
        t0 = time.perf_counter()
        block = P.search(frame, "target")
        rows.append({"rows": n, "features": 4, "row_work": block["budget_used"]["row_work"], "seconds": round(time.perf_counter() - t0, 3)})
    return {"note": "Wall time on the machine that ran validate.py --timing; not part of the reproducible results.", "runs": rows}


if __name__ == "__main__":
    main(timing="--timing" in sys.argv)
