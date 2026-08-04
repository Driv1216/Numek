import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from datatrust import DataTrust

from validation.config import (
    MUTATION_ROOT,
    MUTATION_TARGET,
    PUBLIC_DATASETS,
    REPORT_ROOT,
    REPORT_SECTIONS,
    RESULT_ROOT,
    VALIDATION_ROOT,
    ensure_directories,
)


MUTATION_EXPECTATIONS = {
    "feature_missingness_100": {
        "score": "feature_usability",
        "guardrail": "severe_feature_missingness",
    },
    "duplicates": {"score": "uniqueness"},
    "target_imbalance": {"score": "target_balance"},
    "strong_leakage": {"score": "leakage_risk", "guardrail": "strong_leakage"},
    "review_only_leakage": {"unchanged_score": "leakage_risk"},
    "missing_targets": {"guardrail": "missing_target_labels"},
    "constant_field": {"score": "feature_usability"},
    "conflicting_labels": {
        "unchanged_score": "uniqueness",
        "finding": "conflicting_target_labels",
    },
}


def _analyze(name: str, path: Path, target: str) -> dict:
    report_path = REPORT_ROOT / f"{name}.html"
    audit = DataTrust(str(path), target=target, task="classification")
    started = perf_counter()
    audit.generate_report(str(report_path))
    elapsed = perf_counter() - started
    result = audit.analyze()
    html = report_path.read_text(encoding="utf-8")
    missing_sections = [section for section in REPORT_SECTIONS if section not in html]
    if missing_sections:
        raise AssertionError(f"{name} report is missing sections: {missing_sections}")
    if elapsed >= 30:
        raise AssertionError(f"{name} report took {elapsed:.3f}s, exceeding the 30s gate.")

    return {
        "name": name,
        "dataset_path": str(path.relative_to(VALIDATION_ROOT)),
        "report_path": str(report_path.relative_to(VALIDATION_ROOT)),
        "runtime_seconds": round(elapsed, 6),
        "row_count": result["profile"]["row_count"],
        "column_count": result["profile"]["column_count"],
        "overall": result["scores"]["overall"],
        "risk_level": result["scores"]["risk_level"],
        "sub_scores": result["scores"]["sub_scores"],
        "guardrails": result["scores"]["guardrails"],
        "risks": result["risks"],
        "finding_codes": [finding["code"] for finding in result["findings"]],
        "leakage_details": result["profile"]["leakage_details"],
        "target_missing_count": result["profile"]["target_missing_count"],
        "classification_subtype": result["profile"]["classification_subtype"],
        "missing_feature_row_rate": result["profile"]["missing_feature_row_rate"],
        "duplicate_group_count": result["profile"]["duplicate_group_count"],
        "conflicting_label_group_count": result["profile"]["conflicting_label_group_count"],
    }


def _verify_mutations(results: dict) -> list:
    baseline = results["adult"]
    assertions = []
    for mutation, expectation in MUTATION_EXPECTATIONS.items():
        result = results[f"mutation_{mutation}"]
        if "score" in expectation:
            score = expectation["score"]
            passed = result["sub_scores"][score] < baseline["sub_scores"][score]
            detail = (
                f"{score}: {baseline['sub_scores'][score]} -> {result['sub_scores'][score]}"
            )
        elif "unchanged_score" in expectation:
            score = expectation["unchanged_score"]
            passed = result["sub_scores"][score] == baseline["sub_scores"][score]
            detail = (
                f"{score}: {baseline['sub_scores'][score]} -> {result['sub_scores'][score]}"
            )
        else:
            passed = True
            detail = "guardrail-only expectation"

        expected_guardrail = expectation.get("guardrail")
        if expected_guardrail:
            codes = [item["code"] for item in result["guardrails"]]
            passed = passed and expected_guardrail in codes
            detail += f"; guardrails={codes}"
        expected_finding = expectation.get("finding")
        if expected_finding:
            passed = passed and expected_finding in result["finding_codes"]
            detail += f"; findings={result['finding_codes']}"
        assertions.append(
            {
                "mutation": mutation,
                "passed": passed,
                "detail": detail,
            }
        )

    failures = [item for item in assertions if not item["passed"]]
    if failures:
        raise AssertionError(f"Mutation directional assertions failed: {failures}")
    return assertions


def _write_timings(results: dict) -> None:
    with (RESULT_ROOT / "runtime_measurements.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["name", "dataset_path", "rows", "columns", "runtime_seconds", "under_30s"],
            lineterminator="\n",
        )
        writer.writeheader()
        for result in results.values():
            writer.writerow(
                {
                    "name": result["name"],
                    "dataset_path": result["dataset_path"],
                    "rows": result["row_count"],
                    "columns": result["column_count"],
                    "runtime_seconds": result["runtime_seconds"],
                    "under_30s": result["runtime_seconds"] < 30,
                }
            )


def _write_leakage_reviews(results: dict) -> None:
    review_notes = json.loads(
        (VALIDATION_ROOT / "leakage_reviews.json").read_text(encoding="utf-8")
    )
    rows = []
    for result in results.values():
        for item in result["leakage_details"]:
            review = review_notes.get(item["column"])
            if not review:
                raise AssertionError(
                    f"Leakage flag {item['column']} in {result['name']} has no reviewed classification."
                )
            rows.append(
                {
                    "dataset": result["name"],
                    "column": item["column"],
                    "datatrust_classification": item["classification"],
                    "datatrust_reason": item["reason"],
                    **review,
                    "classification_matches_review": (
                        item["classification"] == review["reviewed_classification"]
                    ),
                }
            )
    with (RESULT_ROOT / "leakage_review.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(rows[0].keys()), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def run_validation() -> dict:
    ensure_directories()
    results = {}
    for name, spec in PUBLIC_DATASETS.items():
        results[name] = _analyze(name, spec["path"], spec["target"])

    for path in sorted(MUTATION_ROOT.glob("*.csv")):
        name = f"mutation_{path.stem}"
        results[name] = _analyze(name, path, MUTATION_TARGET)

    assertions = _verify_mutations(results)
    _write_timings(results)
    _write_leakage_reviews(results)
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "results": results,
        "mutation_assertions": assertions,
    }
    (RESULT_ROOT / "validation_summary.json").write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (RESULT_ROOT / "mutation_assertions.json").write_text(
        json.dumps(assertions, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output


if __name__ == "__main__":
    summary = run_validation()
    print(f"Generated {len(summary['results'])} complete DataTrust validation reports.")
