# Building Energy Efficiency

Residential building design simulations with heating and cooling loads.

**Difficulty · Medium.** 768 rows and eight selected design features. The label is based on the workload evaluated in Clustering. [Publisher](https://archive.ics.uci.edu/dataset/242).

## Start here

- [Input - Building Energy Efficiency.csv](Input%20-%20Building%20Energy%20Efficiency.csv)
- Recommended DataTrust report — [PDF](Recommended%20-%20Clustering%20readiness%20of%20building%20features.pdf) · [HTML](Recommended%20-%20Clustering%20readiness%20of%20building%20features.html).

## Task and settings

Clustering readiness of building features. The task uses declared features without a prediction target. Context or identifier columns include `heating_load`, `cooling_load`.

## What DataTrust found and what was checked

The report flags similar quantitative variables and their scale differences. Independent checks cover finite masks, scale and feature correspondence.

## Missed coverage and limitations

No clusters were fitted.

## Usefulness

Useful for deciding whether to scale or review redundant feature weights.

## Reproduce it manually

Open the input files above and choose this workflow in DataTrust. Use the saved field roles, declarations, and limits. The visible input names are for review. The saved configuration resolves the exact retained sources and related assets.

[Saved configuration](Technical%20Evidence/Configuration%20-%20Clustering%20readiness%20of%20building%20features.json) · [Exact replay instructions](../../Technical%20Archive/Replay%20Instructions.md).

The original attempt, independent checks and earlier versions are in [Technical Evidence](Technical%20Evidence).
