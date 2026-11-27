# New York Taxi Trips

New York yellow taxi trip records with a duration calculated from recorded pickup and drop-off times.

**Difficulty · Ultra Complex.** 1,000,000 January trips and 22 fields in the measured scale run. The label is based on the workload evaluated in Regression. [Publisher](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page).

## Start here

- [Input - New York Taxi Trips.csv](Input%20-%20New%20York%20Taxi%20Trips.csv)
- Recommended DataTrust report — [PDF](Recommended%20-%20One-million-trip%20duration%20analysis.pdf) · [HTML](Recommended%20-%20One-million-trip%20duration%20analysis.html).

## Task and settings

One-million-trip duration analysis. The target column is `duration_minutes`. Context or identifier columns include `source_row_ordinal`, `duration_status`, `tpep_pickup_datetime`, `tpep_dropoff_datetime`. The recorded run uses the local DuckDB backend.

## What DataTrust found and what was checked

Independent clock arithmetic and row-group counts verified the recorded duration population. Separate month and prediction-time reports show examples of timing assumptions and candidate inputs.

## Missed coverage and limitations

Timing fields used to construct the outcome cannot serve as unknown future information for a forecasting task.

## Usefulness

Useful for checking duration coverage and limits at scale.

## Reproduce it manually

Open the input files above and choose this workflow in DataTrust. Use the saved field roles, declarations, and limits. The visible input names are for review. The saved configuration resolves the exact retained sources and related assets.

[Saved configuration](Technical%20Evidence/Configuration%20-%20One-million-trip%20duration%20analysis.json) · [Exact replay instructions](../../Technical%20Archive/Replay%20Instructions.md).

## Additional analyses

- Prediction-time declarations on January trips — [PDF](Additional%20Analyses/Prediction-time%20declarations%20on%20January%20trips/DataTrust%20-%20Prediction-time%20declarations%20on%20January%20trips.pdf) · [HTML](Additional%20Analyses/Prediction-time%20declarations%20on%20January%20trips/DataTrust%20-%20Prediction-time%20declarations%20on%20January%20trips.html). [Inputs and settings](Additional%20Analyses/Prediction-time%20declarations%20on%20January%20trips).
- Prediction-time declarations on February trips — [PDF](Additional%20Analyses/Prediction-time%20declarations%20on%20February%20trips/DataTrust%20-%20Prediction-time%20declarations%20on%20February%20trips.pdf) · [HTML](Additional%20Analyses/Prediction-time%20declarations%20on%20February%20trips/DataTrust%20-%20Prediction-time%20declarations%20on%20February%20trips.html). [Inputs and settings](Additional%20Analyses/Prediction-time%20declarations%20on%20February%20trips).

The original attempt, independent checks and earlier versions are in [Technical Evidence](Technical%20Evidence).
