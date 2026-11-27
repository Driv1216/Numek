# Census Income

US census-derived demographic and income-category records in the official Adult data split.

**Difficulty · Medium.** 32,561 training and 16,281 test rows across 15 fields. The label is based on the workload evaluated in Dataset Comparisons. [Publisher](https://archive.ics.uci.edu/dataset/2).

## Start here

- [Input - Training Set.csv](Input%20-%20Training%20Set.csv)
- [Input - Test Set.csv](Input%20-%20Test%20Set.csv)
- Recommended DataTrust report — [PDF](Recommended%20-%20Official%20training%20and%20test%20split%20comparison.pdf) · [HTML](Recommended%20-%20Official%20training%20and%20test%20split%20comparison.html).

## Task and settings

Official training and test split comparison. The saved configuration declares these inputs and roles — Training Set (Train, Dataset profile), Test Set (Test, Dataset profile).

## What DataTrust found and what was checked

DataTrust detected exact repeated records and feature-level overlap across source splits. Independent multisets verified the comparison. The controlled three-way variant verified declared separation violations.

## Missed coverage and limitations

Similar rows do not establish person-level identity.

## Usefulness

Useful for assessing split contamination risk.

## Reproduce it manually

Open the input files above and choose this workflow in DataTrust. Use the saved field roles, declarations, and limits. The visible input names are for review. The saved configuration resolves the exact retained sources and related assets.

[Saved configuration](Technical%20Evidence/Configuration%20-%20Official%20training%20and%20test%20split%20comparison.json) · [Exact replay instructions](../../Technical%20Archive/Replay%20Instructions.md).

## Additional analyses

- Training, validation and test overlap control — [PDF](Additional%20Analyses/Training%2C%20validation%20and%20test%20overlap%20control/DataTrust%20-%20Training%2C%20validation%20and%20test%20overlap%20control.pdf) · [HTML](Additional%20Analyses/Training%2C%20validation%20and%20test%20overlap%20control/DataTrust%20-%20Training%2C%20validation%20and%20test%20overlap%20control.html). [Inputs and settings](Additional%20Analyses/Training%2C%20validation%20and%20test%20overlap%20control).

The original attempt, independent checks and earlier versions are in [Technical Evidence](Technical%20Evidence).
