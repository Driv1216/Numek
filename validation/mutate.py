import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from validation.config import MUTATION_ROOT, MUTATION_TARGET, PREPARED_ROOT, ensure_directories


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_mutations(base: pd.DataFrame) -> dict:
    mutations = {}

    missingness = base.copy()
    missingness["workclass"] = pd.NA
    mutations["feature_missingness_100"] = missingness

    mutations["duplicates"] = pd.concat([base, base.iloc[:5000]], ignore_index=True)

    majority_label = base[MUTATION_TARGET].value_counts().idxmax()
    majority = base[base[MUTATION_TARGET] == majority_label]
    minority = base[base[MUTATION_TARGET] != majority_label].iloc[:500]
    mutations["target_imbalance"] = pd.concat([majority, minority], ignore_index=True)

    strong_leakage = base.copy()
    strong_leakage["post_income_outcome"] = strong_leakage[MUTATION_TARGET]
    mutations["strong_leakage"] = strong_leakage

    review_only = base.copy()
    review_only["employment_status"] = review_only["workclass"]
    mutations["review_only_leakage"] = review_only

    missing_targets = base.copy()
    missing_targets.loc[missing_targets.index % 10 == 0, MUTATION_TARGET] = pd.NA
    mutations["missing_targets"] = missing_targets

    constant = base.copy()
    constant["validation_constant"] = "constant"
    mutations["constant_field"] = constant

    return mutations


def generate_mutations() -> dict:
    ensure_directories()
    base_path = PREPARED_ROOT / "adult.csv"
    if not base_path.exists():
        raise FileNotFoundError("Prepare validation/data/prepared/adult.csv before generating mutations.")

    base = pd.read_csv(base_path)
    mutations = build_mutations(base)
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base": "data/prepared/adult.csv",
        "target": MUTATION_TARGET,
        "mutations": {},
    }
    for name, data in mutations.items():
        destination = MUTATION_ROOT / f"{name}.csv"
        data.to_csv(destination, index=False)
        manifest["mutations"][name] = {
            "path": f"data/mutations/{destination.name}",
            "rows": int(len(data)),
            "columns": int(len(data.columns)),
            "sha256": sha256(destination),
        }
        print(f"Generated {name}: {len(data)} rows x {len(data.columns)} columns")

    manifest_path = MUTATION_ROOT / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    generate_mutations()
