# New York Taxi Trips

Two source-month extracts from New York City Taxi and Limousine Commission yellow taxi trip records.

**Difficulty · Ultra Complex.** Two million trips per month, four million rows analyzed with disk-backed execution. The label is based on the workload evaluated in Dataset Comparisons. [Publisher](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page).

## Start here

- [Input - January Trips.csv](Input%20-%20January%20Trips.csv)
- [Input - February Trips.csv](Input%20-%20February%20Trips.csv)
- Recommended DataTrust report — [PDF](Recommended%20-%20January%20and%20February%20trip%20comparison.pdf) · [HTML](Recommended%20-%20January%20and%20February%20trip%20comparison.html).

## Task and settings

January and February trip comparison. The saved configuration declares these inputs and roles — January Trips (Reference, Regression, target `duration_minutes`), February Trips (Current, Regression, target `duration_minutes`).

## What DataTrust found and what was checked

DataTrust found repeated selected inputs with different durations and distributions worth comparing. Independent checks covered source populations, signed differences, selected segments and supervised cleanup on a separate small replay.

## Missed coverage and limitations

The measurements apply to the stated hardware and workload. Forced spill under default scratch was unestablished.

## Usefulness

Useful for comparing known input populations.

## Reproduce it manually

Open the input files above and choose this workflow in DataTrust. Use the saved field roles, declarations, and limits. The visible input names are for review. The saved configuration resolves the exact retained sources and related assets.

[Saved configuration](Technical%20Evidence/Configuration%20-%20January%20and%20February%20trip%20comparison.json) · [Exact replay instructions](../../Technical%20Archive/Replay%20Instructions.md).

## Additional analyses

- Cancellation and recovery control — [HTML](Additional%20Analyses/Cancellation%20and%20recovery%20control/DataTrust%20-%20Cancellation%20and%20recovery%20control.html). [Inputs and settings](Additional%20Analyses/Cancellation%20and%20recovery%20control).

The original attempt, independent checks and earlier versions are in [Technical Evidence](Technical%20Evidence).
