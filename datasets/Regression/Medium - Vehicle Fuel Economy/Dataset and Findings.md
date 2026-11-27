# Vehicle Fuel Economy

US EPA vehicle specifications and published fuel economy ratings.

**Difficulty · Medium.** 5,454 gasoline configurations from 2020 through 2024 across 84 recorded columns. The label is based on the workload evaluated in Regression. [Publisher](https://www.fueleconomy.gov/feg/download.shtml).

## Start here

- [Input - Vehicle Fuel Economy.csv](Input%20-%20Vehicle%20Fuel%20Economy.csv)
- Recommended DataTrust report — [PDF](Recommended%20-%20Combined%20fuel%20economy%20reliability.pdf) · [HTML](Recommended%20-%20Combined%20fuel%20economy%20reliability.html).

## Task and settings

Combined fuel economy reliability. The target column is `comb08`. Context or identifier columns include `id`, `createdOn`, `modifiedOn`.

## What DataTrust found and what was checked

The report found 5,454 finite combined MPG ratings ranging from 9 to 59 miles per gallon, with a median of 22. Independent checks verified filtered counts, sorted statistics and selected grouped relationships.

## Missed coverage and limitations

Availability in a real forecasting system depends on when each field becomes known.

## Usefulness

Useful for reviewing redundant and post-test information.

## Reproduce it manually

Open the input files above and choose this workflow in DataTrust. Use the saved field roles, declarations, and limits. The visible input names are for review. The saved configuration resolves the exact retained sources and related assets.

[Saved configuration](Technical%20Evidence/Configuration%20-%20Combined%20fuel%20economy%20reliability.json) · [Exact replay instructions](../../Technical%20Archive/Replay%20Instructions.md).

## Additional analyses

- Predicting before the rating is recorded — [PDF](Additional%20Analyses/Predicting%20before%20the%20rating%20is%20recorded/DataTrust%20-%20Predicting%20before%20the%20rating%20is%20recorded.pdf) · [HTML](Additional%20Analyses/Predicting%20before%20the%20rating%20is%20recorded/DataTrust%20-%20Predicting%20before%20the%20rating%20is%20recorded.html). [Inputs and settings](Additional%20Analyses/Predicting%20before%20the%20rating%20is%20recorded).
- Analyzing after the rating is recorded — [PDF](Additional%20Analyses/Analyzing%20after%20the%20rating%20is%20recorded/DataTrust%20-%20Analyzing%20after%20the%20rating%20is%20recorded.pdf) · [HTML](Additional%20Analyses/Analyzing%20after%20the%20rating%20is%20recorded/DataTrust%20-%20Analyzing%20after%20the%20rating%20is%20recorded.html). [Inputs and settings](Additional%20Analyses/Analyzing%20after%20the%20rating%20is%20recorded).

The original attempt, independent checks and earlier versions are in [Technical Evidence](Technical%20Evidence).
