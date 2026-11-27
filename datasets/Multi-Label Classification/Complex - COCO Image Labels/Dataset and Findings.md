# COCO Image Labels

Tabular vectors of publisher object categories for COCO validation photos.

**Difficulty · Complex.** 5,000 photos represented as 82 columns including label indicators and context. The label is based on the workload evaluated in Multi-Label Classification. [Publisher](https://cocodataset.org/#download).

## Start here

- [Input - COCO Image Labels.csv](Input%20-%20COCO%20Image%20Labels.csv)
- Recommended DataTrust report — [PDF](Recommended%20-%20Multi-label%20image%20category%20reliability.pdf) · [HTML](Recommended%20-%20Multi-label%20image%20category%20reliability.html).

## Task and settings

Multi-label image category reliability. The task declares 80 target columns. Context or identifier columns include `image_id`.

## What DataTrust found and what was checked

The report measures label support, density, cardinality and co-occurrence. Independent image-to-category sets checked the metrics. The companion partially observed run demonstrates unknown labels.

## Missed coverage and limitations

The checks do not validate object recognition or unseen categories.

## Usefulness

Useful for understanding label coverage and which labels occur together.

## Reproduce it manually

Open the input files above and choose this workflow in DataTrust. Use the saved field roles, declarations, and limits. The visible input names are for review. The saved configuration resolves the exact retained sources and related assets.

[Saved configuration](Technical%20Evidence/Configuration%20-%20Multi-label%20image%20category%20reliability.json) · [Exact replay instructions](../../Technical%20Archive/Replay%20Instructions.md).

## Additional analyses

- Partially recorded image labels — [PDF](Additional%20Analyses/Partially%20recorded%20image%20labels/DataTrust%20-%20Partially%20recorded%20image%20labels.pdf) · [HTML](Additional%20Analyses/Partially%20recorded%20image%20labels/DataTrust%20-%20Partially%20recorded%20image%20labels.html). [Inputs and settings](Additional%20Analyses/Partially%20recorded%20image%20labels).

The original attempt, independent checks and earlier versions are in [Technical Evidence](Technical%20Evidence).
