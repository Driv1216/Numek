# English Web Treebank

Universal Dependencies English Web Treebank test data with token and part-of-speech labels.

**Difficulty · Medium.** 2,001 test sentences and 25,147 integer-ID token and tag pairs. The label is based on the workload evaluated in Text Reliability. [Publisher](https://github.com/UniversalDependencies/UD_English-EWT).

## Start here

- [Input - Ud.jsonl](Input%20-%20Ud.jsonl)
- Recommended DataTrust report — [PDF](Recommended%20-%20Part-of-speech%20tag%20alignment.pdf) · [HTML](Recommended%20-%20Part-of-speech%20tag%20alignment.html).

## Task and settings

Part-of-speech tag alignment. The saved configuration declares these inputs and roles — Ud (Corpus, Token).

## What DataTrust found and what was checked

An independent CoNLL-U parser matched every supplied token and tag. The sequence excludes 359 multiword ranges and four empty nodes as intended.

## Missed coverage and limitations

Linguistic quality and unseen tag accuracy were unassessed.

## Usefulness

Useful for alignment and export validation.

## Reproduce it manually

Open the input files above and choose this workflow in DataTrust. Use the saved field roles, declarations, and limits. The visible input names are for review. The saved configuration resolves the exact retained sources and related assets.

[Saved configuration](Technical%20Evidence/Configuration%20-%20Part-of-speech%20tag%20alignment.json) · [Exact replay instructions](../../Technical%20Archive/Replay%20Instructions.md).

The original attempt, independent checks and earlier versions are in [Technical Evidence](Technical%20Evidence).
