# Online Retail Transactions

Invoice lines from a UK online retailer, including stock codes, quantities, prices, countries and customer identifiers.

**Difficulty · Ultra Complex.** 1,067,371 rows and nine columns, with full-population checks and grouped statistics. The label is based on the workload evaluated in Advanced Tabular Analysis. [Publisher](https://archive.ics.uci.edu/dataset/502).

## Start here

- [Input - Online Retail Transactions.csv](Input%20-%20Online%20Retail%20Transactions.csv)
- Recommended DataTrust report — [PDF](Recommended%20-%20Whole-workbook%20data%20checks.pdf) · [HTML](Recommended%20-%20Whole-workbook%20data%20checks.html).

## Task and settings

Whole-workbook data checks. The task uses declared features without a prediction target. Context or identifier columns include `invoice_id`, `stock_code`, `customer_id`, `source_ordinal`, `invoice_time`. The saved configuration contains the declared column types and parsing choices. The recorded run uses the local DuckDB backend.

## What DataTrust found and what was checked

The main report measures missingness and tests declared rules across the full worksheet extract. The independent ledger compares the findings with raw counts and selected group statistics.

## Missed coverage and limitations

They cover declared rules and groups. Commercial explanations and general inference remain outside the evidence.

## Usefulness

These checks are useful for cleaning the full extract.

## Reproduce it manually

Open the input files above and choose this workflow in DataTrust. Use the saved field roles, declarations, and limits. The visible input names are for review. The saved configuration resolves the exact retained sources and related assets.

[Saved configuration](Technical%20Evidence/Configuration%20-%20Whole-workbook%20data%20checks.json) · [Exact replay instructions](../../Technical%20Archive/Replay%20Instructions.md).

The original attempt, independent checks and earlier versions are in [Technical Evidence](Technical%20Evidence).
