# SQuAD Reading Comprehension

Stanford SQuAD 2.0 development questions, passages and supplied answers.

**Difficulty · Medium.** 11,873 questions and 20,302 supplied answer spans, including 5,945 unanswerable questions. The label is based on the workload evaluated in Text Reliability. [Publisher](https://rajpurkar.github.io/SQuAD-explorer/).

## Start here

- [Input - Qa.jsonl](Input%20-%20Qa.jsonl)
- Recommended DataTrust report — [PDF](Recommended%20-%20Question%20answerability%20and%20source%20spans.pdf) · [HTML](Recommended%20-%20Question%20answerability%20and%20source%20spans.html).

## Task and settings

Question answerability and source spans. The saved configuration declares these inputs and roles — Qa (Corpus, Qa).

## What DataTrust found and what was checked

Independent source slicing matched every prepared answer span and question. Byte and UTF-16 offsets were verified on separate controls.

## Missed coverage and limitations

This evidence does not establish answer truth or question-answering model accuracy.

## Usefulness

Useful for finding broken extractive annotations.

## Reproduce it manually

Open the input files above and choose this workflow in DataTrust. Use the saved field roles, declarations, and limits. The visible input names are for review. The saved configuration resolves the exact retained sources and related assets.

[Saved configuration](Technical%20Evidence/Configuration%20-%20Question%20answerability%20and%20source%20spans.json) · [Exact replay instructions](../../Technical%20Archive/Replay%20Instructions.md).

## Additional analyses

- Extractive answer span audit — [PDF](Additional%20Analyses/Extractive%20answer%20span%20audit/DataTrust%20-%20Extractive%20answer%20span%20audit.pdf) · [HTML](Additional%20Analyses/Extractive%20answer%20span%20audit/DataTrust%20-%20Extractive%20answer%20span%20audit.html). [Inputs and settings](Additional%20Analyses/Extractive%20answer%20span%20audit).

The original attempt, independent checks and earlier versions are in [Technical Evidence](Technical%20Evidence).
