# MultiWOZ Task Dialogues

Task-oriented conversations about services such as hotels, restaurants and travel.

**Difficulty · Complex.** 10,437 nested dialogues, with a separate flat malformed-turn control. The label is based on the workload evaluated in Text Reliability. [Publisher](https://github.com/budzianowski/multiwoz/tree/master/data/MultiWOZ_2.2).

## Start here

- [Input - Dialogues.jsonl](Input%20-%20Dialogues.jsonl)
- Recommended DataTrust report — [PDF](Recommended%20-%20Nested%20conversations%20and%20turn%20coverage.pdf) · [HTML](Recommended%20-%20Nested%20conversations%20and%20turn%20coverage.html).

## Task and settings

Nested conversations and turn coverage. The saved configuration declares these inputs and roles — Dialogues (Corpus, Conversation).

## What DataTrust found and what was checked

Independent dialogue and turn joins validate the supplied structure. The report identifies selected malformed or unusual structural cases.

## Missed coverage and limitations

Semantic quality and broader tool-link correctness remain unassessed.

## Usefulness

Useful for checking turn and ID integrity.

## Reproduce it manually

Open the input files above and choose this workflow in DataTrust. Use the saved field roles, declarations, and limits. The visible input names are for review. The saved configuration resolves the exact retained sources and related assets.

[Saved configuration](Technical%20Evidence/Configuration%20-%20Nested%20conversations%20and%20turn%20coverage.json) · [Exact replay instructions](../../Technical%20Archive/Replay%20Instructions.md).

## Additional analyses

- Flat dialogue and malformed turn controls — [PDF](Additional%20Analyses/Flat%20dialogue%20and%20malformed%20turn%20controls/DataTrust%20-%20Flat%20dialogue%20and%20malformed%20turn%20controls.pdf) · [HTML](Additional%20Analyses/Flat%20dialogue%20and%20malformed%20turn%20controls/DataTrust%20-%20Flat%20dialogue%20and%20malformed%20turn%20controls.html). [Inputs and settings](Additional%20Analyses/Flat%20dialogue%20and%20malformed%20turn%20controls).

The original attempt, independent checks and earlier versions are in [Technical Evidence](Technical%20Evidence).
