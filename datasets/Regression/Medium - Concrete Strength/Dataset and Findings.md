# Concrete Strength

Concrete mixture ingredients, age and measured compressive strength.

**Difficulty · Medium.** 1,030 laboratory measurements and 12 columns in a dependency control. The label is based on the workload evaluated in Regression. [Publisher](https://archive.ics.uci.edu/dataset/165).

## Start here

- [Input - Concrete Strength.csv](Input%20-%20Concrete%20Strength.csv)
- Recommended DataTrust report — [PDF](Recommended%20-%20Strength%20measurements%20and%20input%20dependencies.pdf) · [HTML](Recommended%20-%20Strength%20measurements%20and%20input%20dependencies.html).

## Task and settings

Strength measurements and input dependencies. The target column is `strength_mpa`.

## What DataTrust found and what was checked

The report shows repeated measurements, target dispersion and dependency candidates under the selected settings. Independent calculations check arithmetic, repeated inputs and removed components.

## Missed coverage and limitations

The prepared control is documented separately from the original source.

## Usefulness

Useful for inspecting controlled dependencies and repeat variability.

## Reproduce it manually

Open the input files above and choose this workflow in DataTrust. Use the saved field roles, declarations, and limits. The visible input names are for review. The saved configuration resolves the exact retained sources and related assets.

[Saved configuration](Technical%20Evidence/Configuration%20-%20Strength%20measurements%20and%20input%20dependencies.json) · [Exact replay instructions](../../Technical%20Archive/Replay%20Instructions.md).

## Additional analyses

- Strength measurements with dependency search off — [PDF](Additional%20Analyses/Strength%20measurements%20with%20dependency%20search%20off/DataTrust%20-%20Strength%20measurements%20with%20dependency%20search%20off.pdf) · [HTML](Additional%20Analyses/Strength%20measurements%20with%20dependency%20search%20off/DataTrust%20-%20Strength%20measurements%20with%20dependency%20search%20off.html). [Inputs and settings](Additional%20Analyses/Strength%20measurements%20with%20dependency%20search%20off).

The original attempt, independent checks and earlier versions are in [Technical Evidence](Technical%20Evidence).
