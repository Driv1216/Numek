import csv
import hashlib
import json
from pathlib import Path

from validation.config import (
    COMPARISON_ROOT,
    MUTATION_ROOT,
    PREPARED_ROOT,
    REPORT_ROOT,
    REPORT_SECTIONS,
    RESULT_ROOT,
    VALIDATION_ROOT,
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_manifest(manifest_path: Path, entries_key: str) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for entry in manifest[entries_key].values():
        path = VALIDATION_ROOT / entry.get("prepared_path", entry.get("path"))
        if not path.exists():
            raise AssertionError(f"Missing manifest artifact: {path}")
        if sha256(path) != entry.get("prepared_sha256", entry.get("sha256")):
            raise AssertionError(f"Checksum mismatch for generated artifact: {path}")


def verify_reports() -> None:
    reports = sorted(REPORT_ROOT.glob("*.html"))
    if len(reports) != 10:
        raise AssertionError(f"Expected 10 DataTrust reports, found {len(reports)}.")
    for report in reports:
        html = report.read_text(encoding="utf-8")
        missing = [section for section in REPORT_SECTIONS if section not in html]
        if missing:
            raise AssertionError(f"{report} is missing sections: {missing}")


def verify_results() -> None:
    assertions = json.loads((RESULT_ROOT / "mutation_assertions.json").read_text(encoding="utf-8"))
    if not assertions or not all(item["passed"] for item in assertions):
        raise AssertionError("One or more controlled mutation assertions failed.")

    with (RESULT_ROOT / "runtime_measurements.csv").open(encoding="utf-8") as handle:
        timings = list(csv.DictReader(handle))
    if len(timings) != 10 or not all(row["under_30s"] == "True" for row in timings):
        raise AssertionError("Runtime measurements are incomplete or exceed the 30s gate.")

    with (RESULT_ROOT / "leakage_review.csv").open(encoding="utf-8") as handle:
        leakage_reviews = list(csv.DictReader(handle))
    if not leakage_reviews or not all(
        row["classification_matches_review"] == "True" for row in leakage_reviews
    ):
        raise AssertionError("Leakage review coverage is incomplete or contains a classification mismatch.")


def verify_comparison() -> None:
    expected = [
        COMPARISON_ROOT / "ADULT_COMPARISON.md",
        COMPARISON_ROOT / "comparison_metadata.json",
        COMPARISON_ROOT / "evidently_adult.html",
        COMPARISON_ROOT / "evidently_adult.json",
    ]
    missing = [str(path) for path in expected if not path.exists() or path.stat().st_size == 0]
    if missing:
        raise AssertionError(f"Missing adjacent-tool comparison artifacts: {missing}")

    comparison = (COMPARISON_ROOT / "ADULT_COMPARISON.md").read_text(encoding="utf-8")
    for heading in ("## Overlap", "## Divergence", "## DataTrust-Specific Synthesis"):
        if heading not in comparison:
            raise AssertionError(f"Adjacent-tool comparison is missing {heading}.")
    if "does not claim superiority" not in comparison:
        raise AssertionError("Adjacent-tool comparison must explicitly avoid superiority claims.")


def verify_all() -> None:
    verify_manifest(PREPARED_ROOT / "manifest.json", "datasets")
    verify_manifest(MUTATION_ROOT / "manifest.json", "mutations")
    verify_reports()
    verify_results()
    verify_comparison()


if __name__ == "__main__":
    verify_all()
    print("Validation corpus verification passed.")
