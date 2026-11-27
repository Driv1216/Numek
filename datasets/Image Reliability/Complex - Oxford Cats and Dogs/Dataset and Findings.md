# Oxford Cats and Dogs

Oxford-IIIT Pet photos, breed labels and foreground segmentation trimaps.

**Difficulty · Complex.** 7,349 image records and 37 breed labels, with matching trimaps in companion analyses. The label is based on the workload evaluated in Image Reliability. [Publisher](https://www.robots.ox.ac.uk/~vgg/data/pets/).

## Start here

- [Input - Breed and Trimap Manifest.jsonl](Input%20-%20Breed%20and%20Trimap%20Manifest.jsonl)
- [Input - Photos and Trimaps](Input%20-%20Photos%20and%20Trimaps)
- Recommended DataTrust report — [PDF](Recommended%20-%20Pet%20breed%20annotation%20coverage.pdf) · [HTML](Recommended%20-%20Pet%20breed%20annotation%20coverage.html).

## Task and settings

Pet breed annotation coverage. The saved configuration declares these inputs and roles — Pet Photos and Trimaps (Dataset, Classification).

## What DataTrust found and what was checked

The recommended report checks the class manifest. The separate mask investigation confirmed four EXIF orientation values of zero with matching encoded mask dimensions. The targeted report explains the resulting geometry exclusions.

## Missed coverage and limitations

The full-mask report predates the corrected explanation. The correction covers six images, and broader semantic mask quality remains unassessed. The recommended classification report has a different scope from the mask review.

## Usefulness

Useful for verifying which photos can participate.

## Reproduce it manually

Open the input files above and choose this workflow in DataTrust. Use the saved field roles, declarations, and limits. The visible input names are for review. The saved configuration resolves the exact retained sources and related assets.

[Saved configuration](Technical%20Evidence/Configuration%20-%20Pet%20breed%20annotation%20coverage.json) · [Exact replay instructions](../../Technical%20Archive/Replay%20Instructions.md).

## Additional analyses

- Full mask coverage - historical wording — [PDF](Additional%20Analyses/Full%20mask%20coverage%20-%20historical%20wording/DataTrust%20-%20Full%20mask%20coverage%20-%20historical%20wording.pdf) · [HTML](Additional%20Analyses/Full%20mask%20coverage%20-%20historical%20wording/DataTrust%20-%20Full%20mask%20coverage%20-%20historical%20wording.html). [Inputs and settings](Additional%20Analyses/Full%20mask%20coverage%20-%20historical%20wording).
- Corrected geometry explanation - six-image check — [HTML](Additional%20Analyses/Corrected%20geometry%20explanation%20-%20six-image%20check/DataTrust%20-%20Corrected%20geometry%20explanation%20-%20six-image%20check.html). [Inputs and settings](Additional%20Analyses/Corrected%20geometry%20explanation%20-%20six-image%20check).
- Missing and unmatched trimap control — [PDF](Additional%20Analyses/Missing%20and%20unmatched%20trimap%20control/DataTrust%20-%20Missing%20and%20unmatched%20trimap%20control.pdf) · [HTML](Additional%20Analyses/Missing%20and%20unmatched%20trimap%20control/DataTrust%20-%20Missing%20and%20unmatched%20trimap%20control.html). [Inputs and settings](Additional%20Analyses/Missing%20and%20unmatched%20trimap%20control).

The original attempt, independent checks and earlier versions are in [Technical Evidence](Technical%20Evidence).
