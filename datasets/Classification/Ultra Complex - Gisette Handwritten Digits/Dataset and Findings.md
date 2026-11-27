# Gisette Handwritten Digits

Digit-recognition examples with many derived numeric features and a binary class label.

**Difficulty · Ultra Complex.** 6,000 rows and 5,001 columns, including 5,000 predictors. The label is based on the workload evaluated in Classification. [Publisher](https://archive.ics.uci.edu/dataset/170).

## Start here

- [Input - Gisette Handwritten Digits.csv](Input%20-%20Gisette%20Handwritten%20Digits.csv)
- Recommended DataTrust report — [PDF](Recommended%20-%20Full-width%20digit%20classification%20review.pdf) · [HTML](Recommended%20-%20Full-width%20digit%20classification%20review.html).

## Task and settings

Full-width digit classification review. The target column is `class`.

## What DataTrust found and what was checked

The full run checked class counts, repeated records and wide feature coverage. A separate repaired inspection check shows 500 profiled, 2,000 listed and 3,001 omitted. A configured 1,000-column analysis refused the full header before reading data rows.

## Missed coverage and limitations

The baseline report and the bounded inspection cover different tasks. Feature usefulness for a classifier remains unassessed.

## Usefulness

Useful for understanding what a wide report examined.

## Reproduce it manually

Open the input files above and choose this workflow in DataTrust. Use the saved field roles, declarations, and limits. The visible input names are for review. The saved configuration resolves the exact retained sources and related assets.

[Saved configuration](Technical%20Evidence/Configuration%20-%20Full-width%20digit%20classification%20review.json) · [Exact replay instructions](../../Technical%20Archive/Replay%20Instructions.md).

## Additional analyses

- 1,000-feature projection — [PDF](Additional%20Analyses/1%2C000-feature%20projection/DataTrust%20-%201%2C000-feature%20projection.pdf) · [HTML](Additional%20Analyses/1%2C000-feature%20projection/DataTrust%20-%201%2C000-feature%20projection.html). [Inputs and settings](Additional%20Analyses/1%2C000-feature%20projection).

The original attempt, independent checks and earlier versions are in [Technical Evidence](Technical%20Evidence).
