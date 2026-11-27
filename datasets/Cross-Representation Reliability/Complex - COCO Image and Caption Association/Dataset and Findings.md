# COCO Image and Caption Association

Publisher COCO validation images and supplied captions with controlled swapped associations.

**Difficulty · Complex.** 400 associations, including 184 in a harder shared-category group. The label is based on the workload evaluated in Cross-Representation Reliability. [Publisher](https://cocodataset.org/#download).

## Start here

- [Input - Benchmark Photos and Caption Records](Input%20-%20Benchmark%20Photos%20and%20Caption%20Records)
- [Input - Benchmark Population.json](Input%20-%20Benchmark%20Population.json)
- Retained benchmark summary — [Results ledger](../../Technical%20Archive/cross_representation/coco_2017_val/reports/m9_caption_requalification/baseline_01/candidate_record.json).

## Task and settings

Fixed-threshold image and caption benchmark. The frozen benchmark pairs a supplied caption with its publisher image or a deliberately swapped image at the recorded fixed threshold.

## What DataTrust found and what was checked

The retained benchmark flagged 165 of 200 planted swaps. Precision was 97.63%, overall recall 82.50%, and recall on shared-category swaps 63.04%.

## Missed coverage and limitations

It does not establish whether captions are true descriptions. The optional model remains inactive. The benchmark produced a results ledger, with no native PDF or HTML.

## Usefulness

Useful as a bounded association check.

## Reproduce it manually

Open the benchmark population and supplied assets here, then compare them with the archived inference ledger. Running the frozen benchmark again requires the pinned evaluation runtime and weights. The ordinary product leaves the optional profile inactive.

[Saved configuration](Technical%20Evidence/Configuration%20-%20Fixed-threshold%20image%20and%20caption%20benchmark.json) · [Exact replay instructions](../../Technical%20Archive/Replay%20Instructions.md).

The original attempt, independent checks and earlier versions are in [Technical Evidence](Technical%20Evidence).
