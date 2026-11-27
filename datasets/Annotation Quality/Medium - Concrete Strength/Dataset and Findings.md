# Concrete Strength

Laboratory strength measurements for concrete mixtures, prepared with missing and invalid annotation cases.

**Difficulty · Medium.** 1,030 rows, 11 columns, and separate numeric outcome states. The label is based on the workload evaluated in Annotation Quality. [Publisher](https://archive.ics.uci.edu/dataset/165).

## Start here

- [Input - Concrete Strength.csv](Input%20-%20Concrete%20Strength.csv)
- Recommended DataTrust report — [PDF](Recommended%20-%20Partially%20recorded%20strength%20measurements.pdf) · [HTML](Recommended%20-%20Partially%20recorded%20strength%20measurements.html).

## Task and settings

Partially recorded strength measurements. The target column is `strength_mpa`. Grouping columns include `qual_cohort`.

## What DataTrust found and what was checked

The report identifies invalid and unavailable annotations, repeated records and different measured strengths on equivalent inputs. An independent check used masks and quantiles.

## Missed coverage and limitations

The prepared statuses are controls and the report does not establish a material failure cause.

## Usefulness

Useful for identifying which labels need review.

## Reproduce it manually

Open the input files above and choose this workflow in DataTrust. Use the saved field roles, declarations, and limits. The visible input names are for review. The saved configuration resolves the exact retained sources and related assets.

[Saved configuration](Technical%20Evidence/Configuration%20-%20Partially%20recorded%20strength%20measurements.json) · [Exact replay instructions](../../Technical%20Archive/Replay%20Instructions.md).

The original attempt, independent checks and earlier versions are in [Technical Evidence](Technical%20Evidence).
