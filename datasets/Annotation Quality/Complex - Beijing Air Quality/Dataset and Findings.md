# Beijing Air Quality

A Beijing air quality panel with controlled PM2.5 observation and status cases.

**Difficulty · Complex.** 2,400 rows, 12 columns, and station-specific measurement-state rules. The label is based on the workload evaluated in Annotation Quality. [Publisher](https://archive.ics.uci.edu/dataset/501).

## Start here

- [Input - Beijing Air Quality.csv](Input%20-%20Beijing%20Air%20Quality.csv)
- Recommended DataTrust report — [PDF](Recommended%20-%20PM2.5%20measurement%20states.pdf) · [HTML](Recommended%20-%20PM2.5%20measurement%20states.html).

## Task and settings

PM2.5 measurement states. The target column is `PM2.5`. Grouping columns include `qual_cohort`.

## What DataTrust found and what was checked

The report distinguishes unavailable, invalid and unresolved annotations. The corrected oracle counted 423 absent and 105 invalid values under the effective CSV policy.

## Missed coverage and limitations

The original oracle classified several literal NA values differently and is preserved.

## Usefulness

Useful for reviewing measurement coverage by cohort.

## Reproduce it manually

Open the input files above and choose this workflow in DataTrust. Use the saved field roles, declarations, and limits. The visible input names are for review. The saved configuration resolves the exact retained sources and related assets.

[Saved configuration](Technical%20Evidence/Configuration%20-%20PM2.5%20measurement%20states.json) · [Exact replay instructions](../../Technical%20Archive/Replay%20Instructions.md).

The original attempt, independent checks and earlier versions are in [Technical Evidence](Technical%20Evidence).
