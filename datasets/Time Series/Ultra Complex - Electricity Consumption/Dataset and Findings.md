# Electricity Consumption

Electricity consumption profiles assembled as a panel by client and nominal quarter-hour slot.

**Difficulty · Ultra Complex.** 4,488,192 rows across three fields, representing 32 clients at 140,256 nominal quarter-hour slots. The label is based on the workload evaluated in Time Series. [Publisher](https://archive.ics.uci.edu/dataset/321).

## Start here

- [Input - Client panel.csv](Input%20-%20Client%20panel.csv)
- Recommended DataTrust report — [PDF](Recommended%20-%20Full%20nominal%20electricity%20client%20panel.pdf) · [HTML](Recommended%20-%20Full%20nominal%20electricity%20client%20panel.html).

## Task and settings

Full nominal electricity client panel. The panel uses `time` as a local clock, `client` as the series key, and `demand_kw` as the measured value. The configuration asks for a fixed elapsed schedule, which needs resolved instants.

## What DataTrust found and what was checked

Independent source counts verified coverage and masks. The clock declaration left scheduled continuity blocked. The separate 64-row report shows the corrected disclosure of the block before the detailed sections.

## Missed coverage and limitations

It establishes no elapsed-time continuity over unresolved clock transitions.

## Usefulness

Useful for understanding the retained population and its observed coverage.

## Reproduce it manually

Open the input files above and choose this workflow in DataTrust. Use the saved field roles, declarations, and limits. The visible input names are for review. The saved configuration resolves the exact retained sources and related assets.

[Saved configuration](Technical%20Evidence/Configuration%20-%20Full%20nominal%20electricity%20client%20panel.json) · [Exact replay instructions](../../Technical%20Archive/Replay%20Instructions.md).

## Additional analyses

- Corrected blocked continuity disclosure - 64 rows — [HTML](Additional%20Analyses/Corrected%20blocked%20continuity%20disclosure%20-%2064%20rows/DataTrust%20-%20Corrected%20blocked%20continuity%20disclosure%20-%2064%20rows.html). [Inputs and settings](Additional%20Analyses/Corrected%20blocked%20continuity%20disclosure%20-%2064%20rows).

The original attempt, independent checks and earlier versions are in [Technical Evidence](Technical%20Evidence).
