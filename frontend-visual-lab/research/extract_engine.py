"""Builds src/shared/engine.json for the round-two concepts from real DataTrust
output (research/engine/*.json, produced by `datatrust audit`) and the pinned CSV.
Writes only inside the lab."""
import json
from pathlib import Path
import pandas as pd

LAB = Path(__file__).resolve().parents[1]
ROOT = LAB.parent
a = json.loads((LAB / "research/engine/adult.json").read_text())
l = json.loads((LAB / "research/engine/adult-leak.json").read_text())
df = pd.read_csv(ROOT / "validation/data/prepared/adult.csv")

target = "annual_income_over_50k"
feats = [c for c in df.columns if c != target]
g = df.groupby(feats, dropna=False)[target].nunique()
conf_keys = g[g > 1].index
mask = df.set_index(feats).index.isin(conf_keys)
conf = df[mask].copy()
conf["line"] = conf.index + 2  # CSV line numbers (header is line 1)
conf = conf.sort_values(feats + ["line"])
groups = []
for _, grp in conf.groupby(feats, dropna=False, sort=False):
    groups.append(grp[["line"] + list(df.columns)].astype(str).to_dict("records"))

def cols(p):
    out = []
    for c in p["profile"]["columns"]:
        ns = c.get("numeric_summary") or {}
        out.append({k: c.get(k) for k in ["name", "dtype", "role", "is_numeric", "missing_count", "missing_rate", "unique_count", "top_value", "top_value_rate", "outlier_count", "outlier_rate", "near_constant", "high_cardinality"]} | ({"q": [ns.get("min"), ns.get("q1"), ns.get("median"), ns.get("q3"), ns.get("max")], "zero_rate": ns.get("zero_rate")} if ns else {}))
    return out

def run(p):
    s = p["scoring"]["values"]
    return {
        "name": p["dataset"]["dataset_name"],
        "rows": p["profile"]["row_count"], "columns": p["profile"]["column_count"],
        "score": s["overall"], "evidence": s["evidence_score"], "band": s["risk_level"],
        "action": s["recommended_action"], "sub": s["sub_scores"], "guardrails": s["guardrails"],
        "findings": p["findings"], "narrative": p["narrative"],
        "sha256": p["parsing"]["source_sha256"], "elapsed": p["execution"]["elapsed_seconds"],
        "methodology": p["methodology_id"], "generated": p["generated_at"],
        "leakage": p["profile"]["leakage_details"],
    }

out = {
    "source": "datatrust audit on validation/data/prepared/adult.csv and validation/data/mutations/strong_leakage.csv",
    "adult": run(a) | {
        "columns_profile": cols(a),
        "checks": [{"id": c["check_id"], "execution": c["execution"], "method": e["method"], "population": e["population"], "denominator": e["denominator"], "affected": e["affected_count"]} for c, e in zip(a["checks"], a["evidence"])],
        "coverage": a["coverage"],
        "profile": {k: a["profile"][k] for k in ["duplicate_rows", "duplicate_group_count", "largest_duplicate_group_size", "conflicting_label_group_count", "conflicting_label_row_count", "missing_cells", "missing_rate", "missing_feature_row_count", "missing_feature_row_rate", "rows_with_1_missing_feature", "rows_with_2_missing_features", "rows_with_3_plus_missing_features", "majority_class_baseline", "majority_to_minority_ratio", "feature_count", "numeric_feature_count", "non_numeric_feature_count", "target_distribution"]},
        "parsing_warning": a["parsing_warnings"][0]["interpretation"],
        "source_bytes": a["execution"]["source_bytes"],
    },
    "leak": run(l),
    "conflict_groups": groups,
    "sample_rows": df.head(14).astype(str).to_dict("records"),
}
(LAB / "src/shared/engine.json").write_text(json.dumps(out, indent=1, default=str))
print(len(groups), "groups,", sum(len(x) for x in groups), "rows")
