# New York Taxi Trip Events

New York taxi pickup and drop-off timestamps in their original event order.

**Difficulty · Complex.** 250,000 native Parquet event rows with multiple supplied clocks. The label is based on the workload evaluated in Time Series. [Publisher](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page).

## Start here

- [Input - Observed Records.parquet](Input%20-%20Observed%20Records.parquet)
- Recommended DataTrust report — [PDF](Recommended%20-%20Irregular%20trip%20event%20timing.pdf) · [HTML](Recommended%20-%20Irregular%20trip%20event%20timing.html).

## Task and settings

Irregular trip event timing. The saved configuration declares these inputs and roles — Observed Records (Dataset, Dataset profile).

## What DataTrust found and what was checked

Independent checks verified clock fields, differences, missingness and invalid observations. DataTrust reports irregular events under their declared interpretation.

## Missed coverage and limitations

Gaps between these events do not imply an outage.

## Usefulness

Useful for checking whether supplied event times support the intended measurement.

## Reproduce it manually

Open the input files above and choose this workflow in DataTrust. Use the saved field roles, declarations, and limits. The visible input names are for review. The saved configuration resolves the exact retained sources and related assets.

[Saved configuration](Technical%20Evidence/Configuration%20-%20Irregular%20trip%20event%20timing.json) · [Exact replay instructions](../../Technical%20Archive/Replay%20Instructions.md).

The original attempt, independent checks and earlier versions are in [Technical Evidence](Technical%20Evidence).
