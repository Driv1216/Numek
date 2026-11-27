# Bank Marketing

A subset of Portuguese bank campaign records with a supplied annotation status for the subscription outcome.

**Difficulty · Medium.** 1,800 rows, 19 columns, and separate expected and supplied label states. The label is based on the workload evaluated in Annotation Quality. [Publisher](https://archive.ics.uci.edu/dataset/222).

## Start here

- [Input - Bank Marketing.csv](Input%20-%20Bank%20Marketing.csv)
- Recommended DataTrust report — [PDF](Recommended%20-%20Partially%20recorded%20subscription%20outcomes.pdf) · [HTML](Recommended%20-%20Partially%20recorded%20subscription%20outcomes.html).

## Task and settings

Partially recorded subscription outcomes. The target column is `subscribed_term_deposit`. Grouping columns include `qual_cohort`.

## What DataTrust found and what was checked

The report identifies unavailable expected annotations and unresolved status values. Masks, cohort counts and target-state denominators were checked independently.

## Missed coverage and limitations

These are controlled missing-label patterns, with downstream training effects unassessed.

## Usefulness

Useful for triaging label backlog.

## Reproduce it manually

Open the input files above and choose this workflow in DataTrust. Use the saved field roles, declarations, and limits. The visible input names are for review. The saved configuration resolves the exact retained sources and related assets.

[Saved configuration](Technical%20Evidence/Configuration%20-%20Partially%20recorded%20subscription%20outcomes.json) · [Exact replay instructions](../../Technical%20Archive/Replay%20Instructions.md).

The original attempt, independent checks and earlier versions are in [Technical Evidence](Technical%20Evidence).
