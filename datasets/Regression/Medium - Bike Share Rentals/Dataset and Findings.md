# Bike Share Rentals

Capital Bikeshare rental counts with calendar, weather and supplied component fields.

**Difficulty · Medium.** 17,379 hourly records and 20 columns in the recommended dependency run. The label is based on the workload evaluated in Regression. [Publisher](https://archive.ics.uci.edu/dataset/275).

## Start here

- [Input - Bike Share Rentals.csv](Input%20-%20Bike%20Share%20Rentals.csv)
- Recommended DataTrust report — [PDF](Recommended%20-%20Hourly%20rental%20count%20and%20input%20dependencies.pdf) · [HTML](Recommended%20-%20Hourly%20rental%20count%20and%20input%20dependencies.html).

## Task and settings

Hourly rental count and input dependencies. The target column is `cnt`.

## What DataTrust found and what was checked

Independent arithmetic checks characterize predictable component ties and repeated-input results. The paired report with the optional dependency search off is preserved.

## Missed coverage and limitations

The prepared dependency-control input has authored changes, and model performance remains unassessed.

## Usefulness

Useful for identifying counts that reconstruct the target.

## Reproduce it manually

Open the input files above and choose this workflow in DataTrust. Use the saved field roles, declarations, and limits. The visible input names are for review. The saved configuration resolves the exact retained sources and related assets.

[Saved configuration](Technical%20Evidence/Configuration%20-%20Hourly%20rental%20count%20and%20input%20dependencies.json) · [Exact replay instructions](../../Technical%20Archive/Replay%20Instructions.md).

## Additional analyses

- Hourly rentals with dependency search off — [PDF](Additional%20Analyses/Hourly%20rentals%20with%20dependency%20search%20off/DataTrust%20-%20Hourly%20rentals%20with%20dependency%20search%20off.pdf) · [HTML](Additional%20Analyses/Hourly%20rentals%20with%20dependency%20search%20off/DataTrust%20-%20Hourly%20rentals%20with%20dependency%20search%20off.html). [Inputs and settings](Additional%20Analyses/Hourly%20rentals%20with%20dependency%20search%20off).
- Daily rental count and input dependencies — [PDF](Additional%20Analyses/Daily%20rental%20count%20and%20input%20dependencies/DataTrust%20-%20Daily%20rental%20count%20and%20input%20dependencies.pdf) · [HTML](Additional%20Analyses/Daily%20rental%20count%20and%20input%20dependencies/DataTrust%20-%20Daily%20rental%20count%20and%20input%20dependencies.html). [Inputs and settings](Additional%20Analyses/Daily%20rental%20count%20and%20input%20dependencies).

The original attempt, independent checks and earlier versions are in [Technical Evidence](Technical%20Evidence).
