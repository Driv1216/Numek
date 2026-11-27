# Wholesale Customer Spending

Annual product-category spending from a wholesale distributor, with channel and region used as context.

**Difficulty · Simple.** 440 rows and eight columns, including six spending fields. The label is based on the workload evaluated in Unlabeled Data Profiling. [Publisher](https://archive.ics.uci.edu/dataset/292).

## Start here

- [Input - Wholesale Customer Spending.csv](Input%20-%20Wholesale%20Customer%20Spending.csv)
- Recommended DataTrust report — [PDF](Recommended%20-%20Spending%20profile%20with%20declared%20roles.pdf) · [HTML](Recommended%20-%20Spending%20profile%20with%20declared%20roles.html).

## Task and settings

Spending profile with declared roles. The task uses declared features without a prediction target. Context or identifier columns include `Channel`, `Region`.

## What DataTrust found and what was checked

The profile and independent counts distinguish spending fields from region/channel metadata and report descriptive distributions.

## Missed coverage and limitations

The report does not assign a prediction target or establish customer segments.

## Usefulness

Useful before asking a descriptive or modeling question.

## Reproduce it manually

Open the input files above and choose this workflow in DataTrust. Use the saved field roles, declarations, and limits. The visible input names are for review. The saved configuration resolves the exact retained sources and related assets.

[Saved configuration](Technical%20Evidence/Configuration%20-%20Spending%20profile%20with%20declared%20roles.json) · [Exact replay instructions](../../Technical%20Archive/Replay%20Instructions.md).

## Additional analyses

- Profile without role declarations — [PDF](Additional%20Analyses/Profile%20without%20role%20declarations/DataTrust%20-%20Profile%20without%20role%20declarations.pdf) · [HTML](Additional%20Analyses/Profile%20without%20role%20declarations/DataTrust%20-%20Profile%20without%20role%20declarations.html). [Inputs and settings](Additional%20Analyses/Profile%20without%20role%20declarations).

The original attempt, independent checks and earlier versions are in [Technical Evidence](Technical%20Evidence).
