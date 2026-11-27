# Bike Share Rentals

Capital Bikeshare hourly counts arranged on a declared nominal timeline.

**Difficulty · Medium.** 17,379 hourly records in a two-column table under a nominal schedule. The label is based on the workload evaluated in Time Series. [Publisher](https://archive.ics.uci.edu/dataset/275).

## Start here

- [Input - Observations.csv](Input%20-%20Observations.csv)
- Recommended DataTrust report — [PDF](Recommended%20-%20Hourly%20rental%20cadence%20and%20gaps.pdf) · [HTML](Recommended%20-%20Hourly%20rental%20cadence%20and%20gaps.html).

## Task and settings

Hourly rental cadence and gaps. The configuration uses `observed_at` as the clock and `trip_count` as the measurement.

## What DataTrust found and what was checked

DataTrust reports coverage and gaps under the supplied schedule. Independent sorted instants and controlled civil-time cases verify the schedule logic.

## Missed coverage and limitations

Coverage is limited to the recorded population and checks.

## Usefulness

Useful for distinguishing missing scheduled hours from the clock representation chosen for the analysis.

## Reproduce it manually

Open the input files above and choose this workflow in DataTrust. Use the saved field roles, declarations, and limits. The visible input names are for review. The saved configuration resolves the exact retained sources and related assets.

[Saved configuration](Technical%20Evidence/Configuration%20-%20Hourly%20rental%20cadence%20and%20gaps.json) · [Exact replay instructions](../../Technical%20Archive/Replay%20Instructions.md).

The original attempt, independent checks and earlier versions are in [Technical Evidence](Technical%20Evidence).
