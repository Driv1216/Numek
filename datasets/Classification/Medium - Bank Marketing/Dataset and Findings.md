# Bank Marketing

Records from Portuguese bank marketing calls and whether a customer subscribed to a term deposit.

**Difficulty · Medium.** 45,211 rows and 17 columns, with prediction-time availability declarations. The label is based on the workload evaluated in Classification. [Publisher](https://archive.ics.uci.edu/dataset/222).

## Start here

- [Input - Bank Marketing.csv](Input%20-%20Bank%20Marketing.csv)
- Recommended DataTrust report — [PDF](Recommended%20-%20Pre-call%20subscription%20data%20reliability.pdf) · [HTML](Recommended%20-%20Pre-call%20subscription%20data%20reliability.html).

## Task and settings

Pre-call subscription data reliability. The target column is `subscribed_term_deposit`.

## What DataTrust found and what was checked

The pre-call report flags call duration because that value is only available after a call. Independent checks verified label counts and the finding under the declared timing.

## Missed coverage and limitations

The retrospective report has a different time of use and the analyses establish neither model accuracy nor causal effects.

## Usefulness

Useful before training a pre-call model.

## Reproduce it manually

Open the input files above and choose this workflow in DataTrust. Use the saved field roles, declarations, and limits. The visible input names are for review. The saved configuration resolves the exact retained sources and related assets.

[Saved configuration](Technical%20Evidence/Configuration%20-%20Pre-call%20subscription%20data%20reliability.json) · [Exact replay instructions](../../Technical%20Archive/Replay%20Instructions.md).

## Additional analyses

- Retrospective use after the call — [PDF](Additional%20Analyses/Retrospective%20use%20after%20the%20call/DataTrust%20-%20Retrospective%20use%20after%20the%20call.pdf) · [HTML](Additional%20Analyses/Retrospective%20use%20after%20the%20call/DataTrust%20-%20Retrospective%20use%20after%20the%20call.html). [Inputs and settings](Additional%20Analyses/Retrospective%20use%20after%20the%20call).

The original attempt, independent checks and earlier versions are in [Technical Evidence](Technical%20Evidence).
