# Online Retail Transactions

A UK retailer invoice extract and a controlled copy with declared preparation changes.

**Difficulty · Complex.** 50,000 invoice lines per side, with paired transformations. The label is based on the workload evaluated in Dataset Comparisons. [Publisher](https://archive.ics.uci.edu/dataset/502).

## Start here

- [Input - Before Preparation.csv](Input%20-%20Before%20Preparation.csv)
- [Input - After Preparation.csv](Input%20-%20After%20Preparation.csv)
- Recommended DataTrust report — [PDF](Recommended%20-%20Before%20and%20after%20a%20declared%20transformation.pdf) · [HTML](Recommended%20-%20Before%20and%20after%20a%20declared%20transformation.html).

## Task and settings

Before and after a declared transformation. The saved configuration declares these inputs and roles — Before Preparation (Reference, Dataset profile), After Preparation (Current, Dataset profile).

## What DataTrust found and what was checked

The report makes gains, losses and unchanged parts of the preparation visible. Independent replay of the transformation and signed effects checked the main comparisons.

## Missed coverage and limitations

Other transformations and general causal conclusions remain outside the check.

## Usefulness

Useful for judging this preparation pass.

## Reproduce it manually

Open the input files above and choose this workflow in DataTrust. Use the saved field roles, declarations, and limits. The visible input names are for review. The saved configuration resolves the exact retained sources and related assets.

[Saved configuration](Technical%20Evidence/Configuration%20-%20Before%20and%20after%20a%20declared%20transformation.json) · [Exact replay instructions](../../Technical%20Archive/Replay%20Instructions.md).

The original attempt, independent checks and earlier versions are in [Technical Evidence](Technical%20Evidence).
