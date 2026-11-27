# Fixed-threshold optional model qualification

## Native English financial documents

The authored control population contained 600 native PDF and DOCX records grouped into eight financial topics. The pinned profile did not meet the admission criteria. It emitted 225 contradiction candidates, of which 200 matched the frozen contradiction labels. Twenty-five emitted candidates corresponded to insufficient evidence. Support precision and recall and contradiction recall were 100% on the authored population.

The 60 BEA transfer records concern 20 source lines from one release. All 60 records were examined and returned abstentions at the fixed threshold. Transfer to other formats and sources remains open.

[Candidate record](m9_document_requalification_baseline_01.json) · [Authored inference ledger](../cross_representation/bea_gdp_2024q4/reports/m9_document_requalification/baseline_01/authored_ledger.json) · [BEA inference ledger](../cross_representation/bea_gdp_2024q4/reports/m9_document_requalification/baseline_01/bea_transfer_ledger.json)

## COCO supplied-caption association

The local model emitted 169 swap candidates across 400 evaluated associations. Of those candidates, 165 were planted swaps. Precision was 97.63% and recall was 82.50%, with every registered unit examined.

The shared-category stratum contained 92 correct associations and 92 swaps. Of the swaps, 58 were flagged. Hard-stratum recall was 63.04%. Repeated donor images and shared scene categories limit independence. The source truth is publisher association membership, and no practitioner or separate caption-truth assessment was performed.

The profile satisfies its overall fixed numerical criteria. Shipping admission requires a separate founder decision. The ordinary baseline still abstains.

[Candidate record](m9_caption_requalification_baseline_01.json) · [Inference ledger](../cross_representation/coco_2017_val/reports/m9_caption_requalification/baseline_01/coco_ledger.json) · [Composition sensitivity](model_population_sensitivity.json)
