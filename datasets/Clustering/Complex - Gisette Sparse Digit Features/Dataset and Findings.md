# Gisette Sparse Digit Features

Derived handwritten-digit features with controlled complete-row proportions.

**Difficulty · Complex.** 320 rows and 1,000 features in each prepared completeness variant. The label is based on the workload evaluated in Clustering. [Publisher](https://archive.ics.uci.edu/dataset/170).

## Start here

- [Input - Gisette Sparse Digit Features.csv](Input%20-%20Gisette%20Sparse%20Digit%20Features.csv)
- Recommended DataTrust report — [PDF](Recommended%20-%20Clustering%20coverage%20at%20the%2080%20percent%20boundary.pdf) · [HTML](Recommended%20-%20Clustering%20coverage%20at%20the%2080%20percent%20boundary.html).

## Task and settings

Clustering coverage at the 80 percent boundary. The task uses declared features without a prediction target.

## What DataTrust found and what was checked

The recommended report shows exactly 80% complete rows and flags redundant and near-constant features. The neighboring variants checked how the workflow treats coverage thresholds.

## Missed coverage and limitations

The results apply to the controlled projection.

## Usefulness

Useful for understanding the rows available to a distance calculation.

## Reproduce it manually

Open the input files above and choose this workflow in DataTrust. Use the saved field roles, declarations, and limits. The visible input names are for review. The saved configuration resolves the exact retained sources and related assets.

[Saved configuration](Technical%20Evidence/Configuration%20-%20Clustering%20coverage%20at%20the%2080%20percent%20boundary.json) · [Exact replay instructions](../../Technical%20Archive/Replay%20Instructions.md).

## Additional analyses

- Just above 80 percent complete — [PDF](Additional%20Analyses/Just%20above%2080%20percent%20complete/DataTrust%20-%20Just%20above%2080%20percent%20complete.pdf) · [HTML](Additional%20Analyses/Just%20above%2080%20percent%20complete/DataTrust%20-%20Just%20above%2080%20percent%20complete.html). [Inputs and settings](Additional%20Analyses/Just%20above%2080%20percent%20complete).
- Exactly 50 percent complete — [PDF](Additional%20Analyses/Exactly%2050%20percent%20complete/DataTrust%20-%20Exactly%2050%20percent%20complete.pdf) · [HTML](Additional%20Analyses/Exactly%2050%20percent%20complete/DataTrust%20-%20Exactly%2050%20percent%20complete.html). [Inputs and settings](Additional%20Analyses/Exactly%2050%20percent%20complete).
- Just below 50 percent complete — [PDF](Additional%20Analyses/Just%20below%2050%20percent%20complete/DataTrust%20-%20Just%20below%2050%20percent%20complete.pdf) · [HTML](Additional%20Analyses/Just%20below%2050%20percent%20complete/DataTrust%20-%20Just%20below%2050%20percent%20complete.html). [Inputs and settings](Additional%20Analyses/Just%20below%2050%20percent%20complete).

The original attempt, independent checks and earlier versions are in [Technical Evidence](Technical%20Evidence).
