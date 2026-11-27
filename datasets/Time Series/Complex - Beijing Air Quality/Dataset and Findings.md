# Beijing Air Quality

Hourly air quality and weather observations from Beijing monitoring stations.

**Difficulty · Complex.** 420,768 hourly records, 10 columns and 12 monitoring stations. The label is based on the workload evaluated in Time Series. [Publisher](https://archive.ics.uci.edu/dataset/501).

## Start here

- [Input - Observations.csv](Input%20-%20Observations.csv)
- Recommended DataTrust report — [PDF](Recommended%20-%20Station%20time%20coverage%20and%20measurements.pdf) · [HTML](Recommended%20-%20Station%20time%20coverage%20and%20measurements.html).

## Task and settings

Station time coverage and measurements. The station identifies the series. The saved source clock uses the `time` column and the Asia/Shanghai timezone. PM2.5 is one of the named measurements.

## What DataTrust found and what was checked

Independent interval, time-grid and equivalent wide/long checks verify how missing observations and fold declarations are handled.

## Missed coverage and limitations

General multivariate sensitivity remains unestablished.

## Usefulness

Useful for reviewing station coverage and time splits.

## Reproduce it manually

Open the input files above and choose this workflow in DataTrust. Use the saved field roles, declarations, and limits. The visible input names are for review. The saved configuration resolves the exact retained sources and related assets.

[Saved configuration](Technical%20Evidence/Configuration%20-%20Station%20time%20coverage%20and%20measurements.json) · [Exact replay instructions](../../Technical%20Archive/Replay%20Instructions.md).

## Additional analyses

- Wide and long layouts with time folds — [PDF](Additional%20Analyses/Wide%20and%20long%20layouts%20with%20time%20folds/DataTrust%20-%20Wide%20and%20long%20layouts%20with%20time%20folds.pdf) · [HTML](Additional%20Analyses/Wide%20and%20long%20layouts%20with%20time%20folds/DataTrust%20-%20Wide%20and%20long%20layouts%20with%20time%20folds.html). [Inputs and settings](Additional%20Analyses/Wide%20and%20long%20layouts%20with%20time%20folds).

The original attempt, independent checks and earlier versions are in [Technical Evidence](Technical%20Evidence).
