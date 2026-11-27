# Iris Flowers

Measurements of iris petals and sepals used to classify three flower species.

**Difficulty · Simple.** 150 observations, four measurements, and three balanced species labels. The label is based on the workload evaluated in Classification. [Publisher](https://archive.ics.uci.edu/dataset/53).

## Start here

- [Input - Iris Flowers.csv](Input%20-%20Iris%20Flowers.csv)
- Recommended DataTrust report — [PDF](Recommended%20-%20Flower%20species%20classification%20review.pdf) · [HTML](Recommended%20-%20Flower%20species%20classification%20review.html).

## Task and settings

Flower species classification review. The target column is `species`.

## What DataTrust found and what was checked

The report finds three extra repeated rows and no missing cells. Independent CSV counts verified 50 labels per species and the recorded legacy scoring.

## Missed coverage and limitations

It does not establish classification accuracy on other data. The separate missing-label control retains the 81.82 oracle discrepancy and the reconciled 81.83 legacy value.

## Usefulness

Useful as a reference case with easy checks by hand.

## Reproduce it manually

Open the input files above and choose this workflow in DataTrust. Use the saved field roles, declarations, and limits. The visible input names are for review. The saved configuration resolves the exact retained sources and related assets.

[Saved configuration](Technical%20Evidence/Configuration%20-%20Flower%20species%20classification%20review.json) · [Exact replay instructions](../../Technical%20Archive/Replay%20Instructions.md).

## Additional analyses

- Missing species labels - rounding review — [PDF](Additional%20Analyses/Missing%20species%20labels%20-%20rounding%20review/DataTrust%20-%20Missing%20species%20labels%20-%20rounding%20review.pdf) · [HTML](Additional%20Analyses/Missing%20species%20labels%20-%20rounding%20review/DataTrust%20-%20Missing%20species%20labels%20-%20rounding%20review.html). [Inputs and settings](Additional%20Analyses/Missing%20species%20labels%20-%20rounding%20review).
- Conflicting labels on repeated measurements — [PDF](Additional%20Analyses/Conflicting%20labels%20on%20repeated%20measurements/DataTrust%20-%20Conflicting%20labels%20on%20repeated%20measurements.pdf) · [HTML](Additional%20Analyses/Conflicting%20labels%20on%20repeated%20measurements/DataTrust%20-%20Conflicting%20labels%20on%20repeated%20measurements.html). [Inputs and settings](Additional%20Analyses/Conflicting%20labels%20on%20repeated%20measurements).
- Hidden copy of the target — [PDF](Additional%20Analyses/Hidden%20copy%20of%20the%20target/DataTrust%20-%20Hidden%20copy%20of%20the%20target.pdf) · [HTML](Additional%20Analyses/Hidden%20copy%20of%20the%20target/DataTrust%20-%20Hidden%20copy%20of%20the%20target.html). [Inputs and settings](Additional%20Analyses/Hidden%20copy%20of%20the%20target).

The original attempt, independent checks and earlier versions are in [Technical Evidence](Technical%20Evidence).
