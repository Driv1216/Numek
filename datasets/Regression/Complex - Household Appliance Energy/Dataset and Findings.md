# Household Appliance Energy

Electricity use by household appliances alongside nearby weather and room-sensor readings.

**Difficulty · Complex.** 19,735 time-indexed records and 29 columns, with explicit availability declarations. The label is based on the workload evaluated in Regression. [Publisher](https://archive.ics.uci.edu/dataset/374).

## Start here

- [Input - Household Appliance Energy.csv](Input%20-%20Household%20Appliance%20Energy.csv)
- Recommended DataTrust report — [PDF](Recommended%20-%20Appliance%20energy%20and%20predictor%20availability.pdf) · [HTML](Recommended%20-%20Appliance%20energy%20and%20predictor%20availability.html).

## Task and settings

Appliance energy and predictor availability. The target column is `Appliances`. Context or identifier columns include `date`.

## What DataTrust found and what was checked

DataTrust profiles energy use, extremes and repeated-input variation. Independent grouped checks and before-versus-after recording controls test availability-sensitive interpretations.

## Missed coverage and limitations

Associations and contemporaneous measurements do not establish safe future inputs or causality.

## Usefulness

Useful if the intended prediction time is clear.

## Reproduce it manually

Open the input files above and choose this workflow in DataTrust. Use the saved field roles, declarations, and limits. The visible input names are for review. The saved configuration resolves the exact retained sources and related assets.

[Saved configuration](Technical%20Evidence/Configuration%20-%20Appliance%20energy%20and%20predictor%20availability.json) · [Exact replay instructions](../../Technical%20Archive/Replay%20Instructions.md).

## Additional analyses

- Predicting before energy use is recorded — [PDF](Additional%20Analyses/Predicting%20before%20energy%20use%20is%20recorded/DataTrust%20-%20Predicting%20before%20energy%20use%20is%20recorded.pdf) · [HTML](Additional%20Analyses/Predicting%20before%20energy%20use%20is%20recorded/DataTrust%20-%20Predicting%20before%20energy%20use%20is%20recorded.html). [Inputs and settings](Additional%20Analyses/Predicting%20before%20energy%20use%20is%20recorded).
- Analyzing at the time of recording — [PDF](Additional%20Analyses/Analyzing%20at%20the%20time%20of%20recording/DataTrust%20-%20Analyzing%20at%20the%20time%20of%20recording.pdf) · [HTML](Additional%20Analyses/Analyzing%20at%20the%20time%20of%20recording/DataTrust%20-%20Analyzing%20at%20the%20time%20of%20recording.html). [Inputs and settings](Additional%20Analyses/Analyzing%20at%20the%20time%20of%20recording).

The original attempt, independent checks and earlier versions are in [Technical Evidence](Technical%20Evidence).
