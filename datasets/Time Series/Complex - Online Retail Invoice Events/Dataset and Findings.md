# Online Retail Invoice Events

UK retailer transactions observed as invoice events.

**Difficulty · Complex.** 50,000 invoice lines and nine fields, with irregular timestamps. The label is based on the workload evaluated in Time Series. [Publisher](https://archive.ics.uci.edu/dataset/502).

## Start here

- [Input - Retail.csv](Input%20-%20Retail.csv)
- Recommended DataTrust report — [PDF](Recommended%20-%20Invoice%20event%20timing.pdf) · [HTML](Recommended%20-%20Invoice%20event%20timing.html).

## Task and settings

Invoice event timing. The configuration treats `invoice_time` as an event clock in the Europe/London timezone.

## What DataTrust found and what was checked

The audit examines the supplied event times and counts, with independent checks of event timing and supplied opportunities. It uses an event workflow with no assumed fixed cadence.

## Missed coverage and limitations

Ordinary gaps between invoices are not evidence of an outage.

## Usefulness

Useful for understanding the observed event stream.

## Reproduce it manually

Open the input files above and choose this workflow in DataTrust. Use the saved field roles, declarations, and limits. The visible input names are for review. The saved configuration resolves the exact retained sources and related assets.

[Saved configuration](Technical%20Evidence/Configuration%20-%20Invoice%20event%20timing.json) · [Exact replay instructions](../../Technical%20Archive/Replay%20Instructions.md).

The original attempt, independent checks and earlier versions are in [Technical Evidence](Technical%20Evidence).
