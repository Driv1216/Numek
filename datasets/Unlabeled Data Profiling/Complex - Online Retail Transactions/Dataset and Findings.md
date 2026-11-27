# Online Retail Transactions

A prepared extract of Online Retail II invoice lines with lexical identifiers.

**Difficulty · Complex.** 50,000 invoice lines and nine columns, with a separate bounded inspection control. The label is based on the workload evaluated in Unlabeled Data Profiling. [Publisher](https://archive.ics.uci.edu/dataset/502).

## Start here

- [Input - Online Retail Transactions.csv](Input%20-%20Online%20Retail%20Transactions.csv)
- Recommended DataTrust report — [PDF](Recommended%20-%20Invoice%20data%20structure%20and%20field%20roles.pdf) · [HTML](Recommended%20-%20Invoice%20data%20structure%20and%20field%20roles.html).

## Task and settings

Invoice data structure and field roles. The task uses declared features without a prediction target. Context or identifier columns include `invoice_id`, `stock_code`, `customer_id`, `source_ordinal`, `invoice_time`. The saved configuration contains the declared column types and parsing choices.

## What DataTrust found and what was checked

Independent row and field counts verified the profile. A bounded control demonstrates why a later contradictory field value does not appear in first-window suggestions.

## Missed coverage and limitations

Suggestions remain tied to the inspected population.

## Usefulness

Useful for choosing identifiers and descriptions without a prediction target.

## Reproduce it manually

Open the input files above and choose this workflow in DataTrust. Use the saved field roles, declarations, and limits. The visible input names are for review. The saved configuration resolves the exact retained sources and related assets.

[Saved configuration](Technical%20Evidence/Configuration%20-%20Invoice%20data%20structure%20and%20field%20roles.json) · [Exact replay instructions](../../Technical%20Archive/Replay%20Instructions.md).

The original attempt, independent checks and earlier versions are in [Technical Evidence](Technical%20Evidence).
