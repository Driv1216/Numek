# Wholesale Customer Spending

Annual spending by wholesale customers across product categories, with region and channel supporting context.

**Difficulty · Simple.** 440 customers and six quantitative spending features. The label is based on the workload evaluated in Anomaly Detection. [Publisher](https://archive.ics.uci.edu/dataset/292).

## Start here

- [Input - Wholesale Customer Spending.csv](Input%20-%20Wholesale%20Customer%20Spending.csv)
- Recommended DataTrust report — [PDF](Recommended%20-%20Anomaly%20review%20of%20customer%20spending.pdf) · [HTML](Recommended%20-%20Anomaly%20review%20of%20customer%20spending.html).

## Task and settings

Anomaly review of customer spending. The task uses declared features without a prediction target. Context or identifier columns include `Region`, `Channel`.

## What DataTrust found and what was checked

The retained checks verified finite counts, feature eligibility and source-row lookup for descriptive extremes. The recommended run emitted no top-level warning.

## Missed coverage and limitations

Unusual spending alone does not establish fraud or an error.

## Usefulness

Useful as a defensible starting point for inspecting extremes.

## Reproduce it manually

Open the input files above and choose this workflow in DataTrust. Use the saved field roles, declarations, and limits. The visible input names are for review. The saved configuration resolves the exact retained sources and related assets.

[Saved configuration](Technical%20Evidence/Configuration%20-%20Anomaly%20review%20of%20customer%20spending.json) · [Exact replay instructions](../../Technical%20Archive/Replay%20Instructions.md).

The original attempt, independent checks and earlier versions are in [Technical Evidence](Technical%20Evidence).
