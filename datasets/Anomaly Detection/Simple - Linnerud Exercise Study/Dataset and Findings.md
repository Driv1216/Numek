# Linnerud Exercise Study

Exercise and physiological measurements in a small multivariate teaching dataset.

**Difficulty · Simple.** 20 rows and three exercise measures selected from six columns. The label is based on the workload evaluated in Anomaly Detection. [Publisher](https://scikit-learn.org/1.0/modules/generated/sklearn.datasets.load_linnerud.html).

## Start here

- [Input - Linnerud Exercise Study.csv](Input%20-%20Linnerud%20Exercise%20Study.csv)
- Recommended DataTrust report — [PDF](Recommended%20-%20Anomaly%20review%20of%20exercise%20measures.pdf) · [HTML](Recommended%20-%20Anomaly%20review%20of%20exercise%20measures.html).

## Task and settings

Anomaly review of exercise measures. The task uses declared features without a prediction target. Context or identifier columns include `Weight`, `Waist`, `Pulse`.

## What DataTrust found and what was checked

The report identifies unequal quantitative scales and retains descriptive review candidates. The reference checks verified the eligibility and marginal statistics.

## Missed coverage and limitations

It gives no fitted anomaly model or clinical interpretation.

## Usefulness

Useful as a small, readable check of feature selection.

## Reproduce it manually

Open the input files above and choose this workflow in DataTrust. Use the saved field roles, declarations, and limits. The visible input names are for review. The saved configuration resolves the exact retained sources and related assets.

[Saved configuration](Technical%20Evidence/Configuration%20-%20Anomaly%20review%20of%20exercise%20measures.json) · [Exact replay instructions](../../Technical%20Archive/Replay%20Instructions.md).

The original attempt, independent checks and earlier versions are in [Technical Evidence](Technical%20Evidence).
