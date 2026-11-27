# Gisette Sparse Digit Features

A deliberately sparse derivative of handwritten-digit features with controlled quantities of incomplete rows.

**Difficulty · Complex.** 320 rows and 1,000 features in each prepared completeness variant. The label is based on the workload evaluated in Anomaly Detection. [Publisher](https://archive.ics.uci.edu/dataset/170).

## Start here

- [Input - Gisette Sparse Digit Features.csv](Input%20-%20Gisette%20Sparse%20Digit%20Features.csv)
- Recommended DataTrust report — [PDF](Recommended%20-%20Anomaly%20coverage%20at%20the%2050%20percent%20boundary.pdf) · [HTML](Recommended%20-%20Anomaly%20coverage%20at%20the%2050%20percent%20boundary.html).

## Task and settings

Anomaly coverage at the 50 percent boundary. The task uses declared features without a prediction target.

## What DataTrust found and what was checked

The analysis reports exactly half the rows complete in the recommended variant, along with redundancy and scale evidence. Other retained reports compare adjacent eligibility boundaries.

## Missed coverage and limitations

The variants are authored controls and do not establish detector performance.

## Usefulness

Useful for separating sample coverage from anomaly review.

## Reproduce it manually

Open the input files above and choose this workflow in DataTrust. Use the saved field roles, declarations, and limits. The visible input names are for review. The saved configuration resolves the exact retained sources and related assets.

[Saved configuration](Technical%20Evidence/Configuration%20-%20Anomaly%20coverage%20at%20the%2050%20percent%20boundary.json) · [Exact replay instructions](../../Technical%20Archive/Replay%20Instructions.md).

## Additional analyses

- Just above 80 percent complete — [PDF](Additional%20Analyses/Just%20above%2080%20percent%20complete/DataTrust%20-%20Just%20above%2080%20percent%20complete.pdf) · [HTML](Additional%20Analyses/Just%20above%2080%20percent%20complete/DataTrust%20-%20Just%20above%2080%20percent%20complete.html). [Inputs and settings](Additional%20Analyses/Just%20above%2080%20percent%20complete).
- Exactly 80 percent complete — [PDF](Additional%20Analyses/Exactly%2080%20percent%20complete/DataTrust%20-%20Exactly%2080%20percent%20complete.pdf) · [HTML](Additional%20Analyses/Exactly%2080%20percent%20complete/DataTrust%20-%20Exactly%2080%20percent%20complete.html). [Inputs and settings](Additional%20Analyses/Exactly%2080%20percent%20complete).
- Just below 50 percent complete — [PDF](Additional%20Analyses/Just%20below%2050%20percent%20complete/DataTrust%20-%20Just%20below%2050%20percent%20complete.pdf) · [HTML](Additional%20Analyses/Just%20below%2050%20percent%20complete/DataTrust%20-%20Just%20below%2050%20percent%20complete.html). [Inputs and settings](Additional%20Analyses/Just%20below%2050%20percent%20complete).

The original attempt, independent checks and earlier versions are in [Technical Evidence](Technical%20Evidence).
