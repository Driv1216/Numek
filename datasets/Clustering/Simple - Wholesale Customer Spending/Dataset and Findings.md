# Wholesale Customer Spending

Annual product-category spending recorded for wholesale customers.

**Difficulty · Simple.** 440 customers and six selected spending features. The label is based on the workload evaluated in Clustering. [Publisher](https://archive.ics.uci.edu/dataset/292).

## Start here

- [Input - Wholesale Customer Spending.csv](Input%20-%20Wholesale%20Customer%20Spending.csv)
- Recommended DataTrust report — [PDF](Recommended%20-%20Clustering%20readiness%20of%20spending%20features.pdf) · [HTML](Recommended%20-%20Clustering%20readiness%20of%20spending%20features.html).

## Task and settings

Clustering readiness of spending features. The task uses declared features without a prediction target. Context or identifier columns include `Region`, `Channel`.

## What DataTrust found and what was checked

The retained readiness checks trace which features are quantitative and verify finite counts and Pearson calculations. The selected analysis emitted no top-level warning.

## Missed coverage and limitations

It does not establish useful clusters or valid customer segments.

## Usefulness

Useful for a first pass over the declared inputs.

## Reproduce it manually

Open the input files above and choose this workflow in DataTrust. Use the saved field roles, declarations, and limits. The visible input names are for review. The saved configuration resolves the exact retained sources and related assets.

[Saved configuration](Technical%20Evidence/Configuration%20-%20Clustering%20readiness%20of%20spending%20features.json) · [Exact replay instructions](../../Technical%20Archive/Replay%20Instructions.md).

The original attempt, independent checks and earlier versions are in [Technical Evidence](Technical%20Evidence).
