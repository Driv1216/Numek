# MASSIVE Multilingual Requests

Spoken-assistant utterances transcribed and assigned intents in many languages.

**Difficulty · Ultra Complex.** 842,571 records across 51 locales, with a separate 100 MiB text stress case. The label is based on the workload evaluated in Text Reliability. [Publisher](https://github.com/alexa/massive#accessing-and-processing-the-data).

## Start here

- [Input - Utterances.jsonl](Input%20-%20Utterances.jsonl)
- Recommended DataTrust report — [PDF](Recommended%20-%20Structural%20review%20across%2051%20locales.pdf) · [HTML](Recommended%20-%20Structural%20review%20across%2051%20locales.html).

## Task and settings

Structural review across 51 locales. The saved configuration declares these inputs and roles — Utterances (Corpus, Classification).

## What DataTrust found and what was checked

The checks verified locale populations, partitions, IDs and structural evidence. Separate long-corpus and local-window reports address other bounded tasks.

## Missed coverage and limitations

Meaning, intent label correctness and language-specific effectiveness were unassessed.

## Usefulness

Useful for checking representation and consistency over the named partitions.

## Reproduce it manually

Open the input files above and choose this workflow in DataTrust. Use the saved field roles, declarations, and limits. The visible input names are for review. The saved configuration resolves the exact retained sources and related assets.

[Saved configuration](Technical%20Evidence/Configuration%20-%20Structural%20review%20across%2051%20locales.json) · [Exact replay instructions](../../Technical%20Archive/Replay%20Instructions.md).

## Additional analyses

- 100 MiB mixed-format text workload — [PDF](Additional%20Analyses/100%20MiB%20mixed-format%20text%20workload/DataTrust%20-%20100%20MiB%20mixed-format%20text%20workload.pdf) · [HTML](Additional%20Analyses/100%20MiB%20mixed-format%20text%20workload/DataTrust%20-%20100%20MiB%20mixed-format%20text%20workload.html). [Inputs and settings](Additional%20Analyses/100%20MiB%20mixed-format%20text%20workload).
- Local model coverage on long passages — [PDF](Additional%20Analyses/Local%20model%20coverage%20on%20long%20passages/DataTrust%20-%20Local%20model%20coverage%20on%20long%20passages.pdf) · [HTML](Additional%20Analyses/Local%20model%20coverage%20on%20long%20passages/DataTrust%20-%20Local%20model%20coverage%20on%20long%20passages.html). [Inputs and settings](Additional%20Analyses/Local%20model%20coverage%20on%20long%20passages).

The original attempt, independent checks and earlier versions are in [Technical Evidence](Technical%20Evidence).
