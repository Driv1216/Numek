# Linnerud Exercise Study

A small set of exercise measures with physiological outcomes reserved as context.

**Difficulty · Simple.** 20 rows and three exercise measures selected from six columns. The label is based on the workload evaluated in Clustering. [Publisher](https://scikit-learn.org/1.0/modules/generated/sklearn.datasets.load_linnerud.html).

## Start here

- [Input - Linnerud Exercise Study.csv](Input%20-%20Linnerud%20Exercise%20Study.csv)
- Recommended DataTrust report — [PDF](Recommended%20-%20Clustering%20feature%20readiness.pdf) · [HTML](Recommended%20-%20Clustering%20feature%20readiness.html).

## Task and settings

Clustering feature readiness. The task uses declared features without a prediction target. Context or identifier columns include `Weight`, `Waist`, `Pulse`.

## What DataTrust found and what was checked

The report identifies a scale concern among selected exercise measures. Independent checks covered eligibility, finite cases and descriptive scale.

## Missed coverage and limitations

Cohort stability and fitted clusters were not evaluated.

## Usefulness

Useful for checking that outcome measures are out of the distance calculation.

## Reproduce it manually

Open the input files above and choose this workflow in DataTrust. Use the saved field roles, declarations, and limits. The visible input names are for review. The saved configuration resolves the exact retained sources and related assets.

[Saved configuration](Technical%20Evidence/Configuration%20-%20Clustering%20feature%20readiness.json) · [Exact replay instructions](../../Technical%20Archive/Replay%20Instructions.md).

The original attempt, independent checks and earlier versions are in [Technical Evidence](Technical%20Evidence).
