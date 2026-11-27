# US GDP Release Revisions

GDP claims and release-history records prepared to exercise which vintage was available at each cutoff.

**Difficulty · Medium.** Seven observed records and 16 release-history records, each with four columns. The label is based on the workload evaluated in Time Series. [Publisher](https://www.bea.gov/news/2025/gross-domestic-product-4th-quarter-and-year-2024-third-estimate-gdp-industry-and).

## Start here

- [Input - Observed Records.csv](Input%20-%20Observed%20Records.csv)
- [Input - Release History.csv](Input%20-%20Release%20History.csv)
- Recommended DataTrust report — [PDF](Recommended%20-%20Release%20timing%20and%20revision%20cutoffs.pdf) · [HTML](Recommended%20-%20Release%20timing%20and%20revision%20cutoffs.html).

## Task and settings

Release timing and revision cutoffs. The configuration measures `growth` on the `merit_time` clock. The release-history side supplies the available revision at each cutoff.

## What DataTrust found and what was checked

Independent publisher release times and row keys checked the selected version at each cutoff. The analysis separates observed records from revision history.

## Missed coverage and limitations

Broad real-time forecasting and revision behavior across other series remain unassessed.

## Usefulness

Useful for reviewing look-ahead exposure in this fixture.

## Reproduce it manually

Open the input files above and choose this workflow in DataTrust. Use the saved field roles, declarations, and limits. The visible input names are for review. The saved configuration resolves the exact retained sources and related assets.

[Saved configuration](Technical%20Evidence/Configuration%20-%20Release%20timing%20and%20revision%20cutoffs.json) · [Exact replay instructions](../../Technical%20Archive/Replay%20Instructions.md).

The original attempt, independent checks and earlier versions are in [Technical Evidence](Technical%20Evidence).
