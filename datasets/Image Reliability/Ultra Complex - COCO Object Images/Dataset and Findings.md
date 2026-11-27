# COCO Object Images

The admitted part of COCO validation images and publisher object annotations.

**Difficulty · Ultra Complex.** 1,279 locally admitted images and 9,419 object annotations, including polygons and encoded masks. The label is based on the workload evaluated in Image Reliability. [Publisher](https://cocodataset.org/#download).

## Start here

- [Input - Object Annotations.json](Input%20-%20Object%20Annotations.json)
- [Input - Image Files](Input%20-%20Image%20Files)
- Recommended DataTrust report — [PDF](Recommended%20-%20Object%20masks%20and%20image%20geometry.pdf) · [HTML](Recommended%20-%20Object%20masks%20and%20image%20geometry.html).

## Task and settings

Object masks and image geometry. The saved configuration declares these inputs and roles — Photos and Object Annotations (Dataset, Segmentation).

## What DataTrust found and what was checked

Independent checks verified original coordinate bounds and RLE structure, plus a full natural-mask and box witness and controlled geometry cases. In 101 RLE annotations, the publisher scalar area differed from the encoded bitmap count.

## Missed coverage and limitations

Full polygon pixel parity and semantic annotation quality remain unassessed.

## Usefulness

Useful for checking annotation structure and coordinate consistency.

## Reproduce it manually

Open the input files above and choose this workflow in DataTrust. Use the saved field roles, declarations, and limits. The visible input names are for review. The saved configuration resolves the exact retained sources and related assets.

[Saved configuration](Technical%20Evidence/Configuration%20-%20Object%20masks%20and%20image%20geometry.json) · [Exact replay instructions](../../Technical%20Archive/Replay%20Instructions.md).

## Additional analyses

- Bounding box annotation review — [PDF](Additional%20Analyses/Bounding%20box%20annotation%20review/DataTrust%20-%20Bounding%20box%20annotation%20review.pdf) · [HTML](Additional%20Analyses/Bounding%20box%20annotation%20review/DataTrust%20-%20Bounding%20box%20annotation%20review.html). [Inputs and settings](Additional%20Analyses/Bounding%20box%20annotation%20review).
- Image label coverage review — [PDF](Additional%20Analyses/Image%20label%20coverage%20review/DataTrust%20-%20Image%20label%20coverage%20review.pdf) · [HTML](Additional%20Analyses/Image%20label%20coverage%20review/DataTrust%20-%20Image%20label%20coverage%20review.html). [Inputs and settings](Additional%20Analyses/Image%20label%20coverage%20review).
- Overlaps between image versions — [PDF](Additional%20Analyses/Overlaps%20between%20image%20versions/DataTrust%20-%20Overlaps%20between%20image%20versions.pdf) · [HTML](Additional%20Analyses/Overlaps%20between%20image%20versions/DataTrust%20-%20Overlaps%20between%20image%20versions.html). [Inputs and settings](Additional%20Analyses/Overlaps%20between%20image%20versions).
- YOLO annotations with unknown labels — [PDF](Additional%20Analyses/YOLO%20annotations%20with%20unknown%20labels/DataTrust%20-%20YOLO%20annotations%20with%20unknown%20labels.pdf) · [HTML](Additional%20Analyses/YOLO%20annotations%20with%20unknown%20labels/DataTrust%20-%20YOLO%20annotations%20with%20unknown%20labels.html). [Inputs and settings](Additional%20Analyses/YOLO%20annotations%20with%20unknown%20labels).

The original attempt, independent checks and earlier versions are in [Technical Evidence](Technical%20Evidence).
