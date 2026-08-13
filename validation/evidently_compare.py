import json
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

import pandas as pd
import evidently
from evidently import Report
from evidently.presets import DataSummaryPreset


VALIDATION_ROOT = Path(__file__).resolve().parent
ADULT_PATH = VALIDATION_ROOT / "data" / "prepared" / "adult.csv"
RESULT_PATH = VALIDATION_ROOT / "results" / "validation_summary.json"
OUTPUT_ROOT = VALIDATION_ROOT / "comparison"


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    adult = pd.read_csv(ADULT_PATH)
    started = perf_counter()
    report = Report([DataSummaryPreset()])
    result = report.run(adult)
    elapsed = perf_counter() - started
    result.save_html(str(OUTPUT_ROOT / "evidently_adult.html"))
    (OUTPUT_ROOT / "evidently_adult.json").write_text(result.json(), encoding="utf-8")

    datatrust = json.loads(RESULT_PATH.read_text(encoding="utf-8"))["results"]["adult"]
    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset": "Adult",
        "rows": int(len(adult)),
        "columns": int(len(adult.columns)),
        "evidently_version": evidently.__version__,
        "evidently_runtime_seconds": round(elapsed, 6),
        "datatrust_runtime_seconds": datatrust["runtime_seconds"],
        "comparison_role": "Internal supporting evidence only; not a product acceptance gate.",
    }
    (OUTPUT_ROOT / "comparison_metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    markdown = f"""# Adult Internal Adjacent-Tool Comparison

Generated: {metadata["generated_at"]}

This is internal supporting credibility evidence. It is not a product acceptance gate,
does not claim superiority, and must not be shown during blinded practitioner
reviews.

## Execution

- Dataset: prepared UCI Adult, {metadata["rows"]} rows x {metadata["columns"]} columns
- DataTrust report runtime: {metadata["datatrust_runtime_seconds"]}s
- Evidently OSS version: {metadata["evidently_version"]}, isolated validation environment
- Evidently DataSummaryPreset runtime: {metadata["evidently_runtime_seconds"]}s

Runtime values are descriptive only because the tools produce different
artifacts and this is not a performance benchmark.

## Overlap

- Both surface dataset shape, missingness, target/column distributions, and
  feature-level data-quality evidence.
- Both create a shareable HTML artifact for offline inspection.
- Both make raw quality evidence inspectable rather than hiding it behind one
  opaque metric.

## Divergence

- Evidently's DataSummaryPreset provides a broad interactive statistical
  profile, including detailed column summaries and correlations.
- DataTrust produces a smaller six-section reliability report with a target
  balance score, heuristic leakage review, deterministic top risks, recommended
  actions, and explained score guardrails.
- DataTrust classifies `marital_status` as a review-only leakage-name prompt;
  this requires human confirmation and is not an Evidently DataSummaryPreset
  concept.
- Neither artifact proves fitness for use, fairness, compliance, or label
  correctness.

## DataTrust-Specific Synthesis

- Adult DataTrust risk band: {datatrust["risk_level"]} ({datatrust["overall"]})
- Adult DataTrust top risks: {", ".join(risk["title"] for risk in datatrust["risks"])}
- Applied guardrails: {", ".join(item["code"] for item in datatrust["guardrails"]) or "none"}

The useful distinction to test with practitioners is whether DataTrust's
synthesis and action framing improve review workflow, not whether it computes
more raw profiling metrics than Evidently.
"""
    (OUTPUT_ROOT / "ADULT_COMPARISON.md").write_text(markdown, encoding="utf-8")
    print("Generated isolated Evidently Adult comparison.")


if __name__ == "__main__":
    main()
