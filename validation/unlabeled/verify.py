"""Reproducible internal evidence checks without regenerating historical artifacts."""

import json
import tempfile
from pathlib import Path

import pandas as pd

from datatrust import DataTrust, DatasetSpec, TaskSpec
from datatrust.ingestion import source_digest
from validation.config import PUBLIC_DATASETS


def verify_all():
    root = Path(__file__).parent
    synthetic = root / "known_evidence.csv"
    before = source_digest(synthetic)
    r = DataTrust.from_spec(DatasetSpec(synthetic), TaskSpec("dataset_profile")).analyze_result()
    p = r.profile
    assert (p["row_count"], p["column_count"], p["missing_cells"]) == (12, 5, 13)
    assert (p["duplicate_rows"], p["duplicate_group_count"], p["rows_in_duplicate_groups"]) == (1, 1, 2)
    numeric = next(c for c in p["columns"] if c["name"] == "value")
    assert numeric["finite_count"] == 11 and numeric["numeric_summary"]["non_finite_count"] == 1
    assert (numeric["numeric_summary"]["min"], numeric["numeric_summary"]["q1"], numeric["numeric_summary"]["median"], numeric["numeric_summary"]["q3"], numeric["numeric_summary"]["max"]) == (-1, 1.5, 4, 6.5, 100)
    assert numeric["outlier_count"] == 2 and numeric["outlier_denominator"] == 11
    assert next(w for w in r.parsing_warnings if w["code"] == "leading_zero_numeric_conversion")["observed_count"] == 12
    assert source_digest(synthetic) == before
    summary = [{"case": "known_synthetic_evidence", "rows": 12, "columns": 5, "passed": True}]
    dimensions = {"german_credit": (1000, 20), "bank_marketing": (45211, 16), "adult": (48842, 14)}
    # Label-free views are temporary derivations of pinned tables, not unlabeled ground truth.
    with tempfile.TemporaryDirectory(prefix="datatrust-unlabeled-validation-") as temporary:
        for name, source in PUBLIC_DATASETS.items():
            digest = source_digest(source["path"])
            frame = pd.read_csv(source["path"]).drop(columns=[source["target"]])
            path = Path(temporary) / f"{name}-label-free.csv"
            frame.to_csv(path, index=False)
            result = DataTrust.from_spec(DatasetSpec(path), TaskSpec("dataset_profile")).analyze_result()
            assert (result.profile["row_count"], result.profile["column_count"]) == dimensions[name]
            assert result.scoring["values"] is None and result.execution["status"] == "completed"
            assert all(c["role"] == "feature" for c in result.profile["columns"])
            assert source_digest(source["path"]) == digest
            json.loads(result.json_text(), parse_constant=lambda value: (_ for _ in ()).throw(AssertionError(value)))
            summary.append({"case": f"{name}_label_free_view", "rows": dimensions[name][0], "columns": dimensions[name][1], "passed": True})
    return {"validation_type": "internal", "external_method_validity": "not_established", "cases": summary}


if __name__ == "__main__":
    print(json.dumps(verify_all(), indent=2))
