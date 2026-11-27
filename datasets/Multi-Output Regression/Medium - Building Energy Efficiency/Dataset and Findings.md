# Building Energy Efficiency

Simulated energy load data for different residential building designs.

**Difficulty · Medium.** 768 rows, eight design inputs and two numerical outputs. The label is based on the workload evaluated in Multi-Output Regression. [Publisher](https://archive.ics.uci.edu/dataset/242).

## Start here

- [Input - Building Energy Efficiency.csv](Input%20-%20Building%20Energy%20Efficiency.csv)
- Recommended DataTrust report — [PDF](Recommended%20-%20Heating%20and%20cooling%20load%20outcomes.pdf) · [HTML](Recommended%20-%20Heating%20and%20cooling%20load%20outcomes.html).

## Task and settings

Heating and cooling load outcomes. The target columns are `heating_load`, `cooling_load`.

## What DataTrust found and what was checked

DataTrust separates heating and cooling populations and their shared availability. Independent checks cover per-output and joint statistics, with separate masking and shared-budget controls.

## Missed coverage and limitations

Other budget interactions and simulation-to-building transfer are unassessed.

## Usefulness

Useful for seeing whether the two targets can use the same rows and inputs.

## Reproduce it manually

Open the input files above and choose this workflow in DataTrust. Use the saved field roles, declarations, and limits. The visible input names are for review. The saved configuration resolves the exact retained sources and related assets.

[Saved configuration](Technical%20Evidence/Configuration%20-%20Heating%20and%20cooling%20load%20outcomes.json) · [Exact replay instructions](../../Technical%20Archive/Replay%20Instructions.md).

## Additional analyses

- Missing heating and cooling values — [PDF](Additional%20Analyses/Missing%20heating%20and%20cooling%20values/DataTrust%20-%20Missing%20heating%20and%20cooling%20values.pdf) · [HTML](Additional%20Analyses/Missing%20heating%20and%20cooling%20values/DataTrust%20-%20Missing%20heating%20and%20cooling%20values.html). [Inputs and settings](Additional%20Analyses/Missing%20heating%20and%20cooling%20values).
- Shared search limits for multiple outputs — [PDF](Additional%20Analyses/Shared%20search%20limits%20for%20multiple%20outputs/DataTrust%20-%20Shared%20search%20limits%20for%20multiple%20outputs.pdf) · [HTML](Additional%20Analyses/Shared%20search%20limits%20for%20multiple%20outputs/DataTrust%20-%20Shared%20search%20limits%20for%20multiple%20outputs.html). [Inputs and settings](Additional%20Analyses/Shared%20search%20limits%20for%20multiple%20outputs).

The original attempt, independent checks and earlier versions are in [Technical Evidence](Technical%20Evidence).
