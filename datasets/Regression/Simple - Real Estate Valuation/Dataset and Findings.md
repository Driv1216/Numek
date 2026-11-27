# Real Estate Valuation

Property sales examples from New Taipei City with location and property attributes.

**Difficulty · Simple.** 414 valuation records, seven input and context fields, and one numeric target. The label is based on the workload evaluated in Regression. [Publisher](https://archive.ics.uci.edu/dataset/477).

## Start here

- [Input - Real Estate Valuation.csv](Input%20-%20Real%20Estate%20Valuation.csv)
- Recommended DataTrust report — [PDF](Recommended%20-%20Property%20valuation%20and%20price%20coverage.pdf) · [HTML](Recommended%20-%20Property%20valuation%20and%20price%20coverage.html).

## Task and settings

Property valuation and price coverage. The target column is `price_ntd_10k_per_ping`. Context or identifier columns include `source_row_no`.

## What DataTrust found and what was checked

Independent workbook and CSV checks verified all 414 finite prices and a median of 38.45 in the supplied units. The report measures target coverage, repeated inputs and declared price constraints.

## Missed coverage and limitations

The optional dependency search remains explicitly blocked on the disk-backed route. That route has separate technical evidence.

## Usefulness

Useful for checking the price field and plausible inputs.

## Reproduce it manually

Open the input files above and choose this workflow in DataTrust. Use the saved field roles, declarations, and limits. The visible input names are for review. The saved configuration resolves the exact retained sources and related assets.

[Saved configuration](Technical%20Evidence/Configuration%20-%20Property%20valuation%20and%20price%20coverage.json) · [Exact replay instructions](../../Technical%20Archive/Replay%20Instructions.md).

## Additional analyses

- Basic valuation without optional dependency search — [PDF](Additional%20Analyses/Basic%20valuation%20without%20optional%20dependency%20search/DataTrust%20-%20Basic%20valuation%20without%20optional%20dependency%20search.pdf) · [HTML](Additional%20Analyses/Basic%20valuation%20without%20optional%20dependency%20search/DataTrust%20-%20Basic%20valuation%20without%20optional%20dependency%20search.html). [Inputs and settings](Additional%20Analyses/Basic%20valuation%20without%20optional%20dependency%20search).

The original attempt, independent checks and earlier versions are in [Technical Evidence](Technical%20Evidence).
