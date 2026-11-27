# SciFact Research Claims

Scientific claims paired with published research abstracts and supplied evidence judgments.

**Difficulty · Medium.** 5,183 abstracts, 100 queries, 100 chunks and 72 supplied positive judgments. The label is based on the workload evaluated in Text Reliability. [Publisher](https://github.com/allenai/scifact).

## Start here

- [Input - Research Abstracts.jsonl](Input%20-%20Research%20Abstracts.jsonl)
- [Input - Research Claims.jsonl](Input%20-%20Research%20Claims.jsonl)
- [Input - Extractive Text Chunks.jsonl](Input%20-%20Extractive%20Text%20Chunks.jsonl)
- [Input - Supplied Relevance Judgments.jsonl](Input%20-%20Supplied%20Relevance%20Judgments.jsonl)
- Recommended DataTrust report — [PDF](Recommended%20-%20Claim%2C%20evidence%20and%20extractive%20chunk%20review.pdf) · [HTML](Recommended%20-%20Claim%2C%20evidence%20and%20extractive%20chunk%20review.html).

## Task and settings

Claim, evidence and extractive chunk review. The saved configuration declares these inputs and roles — Research Abstracts (Documents, Corpus), Research Claims (Queries, Corpus), Extractive Text Chunks (Chunks, Corpus), Supplied Relevance Judgments (Judgments, Corpus).

## What DataTrust found and what was checked

Independent publisher parity and exact text readback verified the extractive chunks and declared evidence bindings.

## Missed coverage and limitations

It gives no retrieval effectiveness score and unjudged documents remain unknown.

## Usefulness

Useful for checking retrieval input integrity.

## Reproduce it manually

Open the input files above and choose this workflow in DataTrust. Use the saved field roles, declarations, and limits. The visible input names are for review. The saved configuration resolves the exact retained sources and related assets.

[Saved configuration](Technical%20Evidence/Configuration%20-%20Claim%2C%20evidence%20and%20extractive%20chunk%20review.json) · [Exact replay instructions](../../Technical%20Archive/Replay%20Instructions.md).

## Additional analyses

- Abstract corpus quality — [PDF](Additional%20Analyses/Abstract%20corpus%20quality/DataTrust%20-%20Abstract%20corpus%20quality.pdf) · [HTML](Additional%20Analyses/Abstract%20corpus%20quality/DataTrust%20-%20Abstract%20corpus%20quality.html). [Inputs and settings](Additional%20Analyses/Abstract%20corpus%20quality).

The original attempt, independent checks and earlier versions are in [Technical Evidence](Technical%20Evidence).
