# DataTrust qualification matrix

The frozen register defines required coverage. Execution standing refers to the recorded variants.

| Case | Standing | Level | Machine minutes | Status | Independent oracle |
|---|---|---|---:|---|---|
| `classification/iris_balanced` | mandatory | A | 2 | Analytical checks passed for executed variants | Raw CSV class counter, row-width and cell counts; score formula over raw profile. |
| `classification/bank_availability` | mandatory | B | 4 | Analytical checks passed for executed variants | Independent source-token and typed-label counts; paired declaration and score ledger. |
| `classification/dry_bean_multiclass` | mandatory | B | 3 | Analytical checks passed for executed variants | Independent ARFF class counters, per-class share and legacy score components. |
| `classification/guardrail_controls` | mandatory | B | 4 | Recorded failure or blocker; see attempts | Independent set/group counts and legacy score reproduction for each fixed variant. |
| `classification/scania_rare` | mandatory | C | 6 | Analytical checks passed for executed variants | Independent raw file counters, missing marker counts, class imbalance and feature penalty contributions. |
| `classification/gisette_wide` | mandatory | D | 14 | Analytical checks passed for executed variants | Read native matrix and labels independently; verify selected columns, class frequencies and report scope. |
| `regression/real_estate_price` | mandatory | A | 3 | Recorded failure or blocker; see attempts | Open workbook independently, compute finite counts, grouped repeats and linear-interpolation quantiles. |
| `regression/epa_ratings` | mandatory | B | 4 | Analytical checks passed for executed variants | Independent CSV filter, sorted finite statistics, tie counts and exact grouped dependencies. |
| `regression/appliances_availability` | mandatory | C | 5 | Analytical checks passed for executed variants | Independent time-block grouping, finite/tail counts, same-input spread and negative control permutations. |
| `regression/superconductivity_j2_bound` | mandatory | C | 5 | Analytical checks passed for executed variants | Separate raw CSV scan, column eligibility/group tests and declared feature order under 64-feature budget. |
| `regression/taxi_prediction_time` | mandatory | C | 7 | Analytical checks passed for executed variants | Independent Parquet row-group ordinal, clock subtraction and missing/reversed/atypical interval ledger. |
| `regression/taxi_scale` | mandatory | D | 17 | Analytical checks passed for executed variants | Independent streaming Parquet counts, decimal timings and selected output-population verification. |
| `regression/bike_concrete_controls` | mandatory | B | 4 | Analytical checks passed for executed variants | Arithmetic reference, constraint and repeat-input calculations, inspect removed components independently. |
| `regression/strict_families_and_nulls` | mandatory | C | 9 | Analytical checks passed for executed variants | Separate group sorting, monotone/range tests, exact arithmetic, repeated support, family false-positive counts. |
| `profiling/wholesale_roles` | mandatory | A | 3 | Analytical checks passed for executed variants | Independent typed/raw counts, role membership, duplicates and finite distributions. |
| `profiling/retail_roles_and_bounded_head` | mandatory | C | 5 | Analytical checks passed for executed variants | Independent original/head counts and mapping; set/presence checks for misleading suggestions. |
| `annotation/partial_class` | mandatory | B | 4 | Analytical checks passed for executed variants | Independent mask, class × status counters, same-input conflicting labels and cohort denominators. |
| `annotation/partial_numeric` | mandatory | B | 3 | Analytical checks passed for executed variants | Independent masks and cohort count/quantile arithmetic. |
| `annotation/beijing_measurement_states` | mandatory | C | 5 | Analytical checks passed for executed variants | Independent expected-target union/intersection and support by station. |
| `multioutput/energy_linnerud` | mandatory | B | 4 | Analytical checks passed for executed variants | Independent target-per-row bitsets, finite counts, pair matches and quantile checks. |
| `multioutput/shared_budget` | mandatory | C | 5 | Analytical checks passed for executed variants | Independent candidate order and cumulative row-work ledger. |
| `multilabel/coco_vectors` | mandatory | C | 6 | Analytical checks passed for executed variants | Independent per-image sets, category pairs, supports, cardinality, density and declared false/unknown distinction. |
| `clustering/eligibility_and_scale` | mandatory | B | 3 | Analytical checks passed for executed variants | Independent finite masks, quantiles and centered Pearson. |
| `anomaly/eligibility_and_scale` | mandatory | B | 3 | Analytical checks passed for executed variants | Finite masks, marginal quantiles, eligibility, extremes and source-row lookups. |
| `readiness/sparse_redundancy` | mandatory | C | 5 | Analytical checks passed for executed variants | Independent complete row masks, centered correlation at threshold, and feature-pair work counters. |
| `comparisons/adult_split_and_intents` | mandatory | B | 4 | Analytical checks passed for executed variants | Independent multisets, set overlap and left/right affected-row unions. |
| `comparisons/german_versions` | mandatory | B | 4 | Analytical checks passed for executed variants | Publisher coding manuals, manual alignment and independent effect/support calculations. |
| `comparisons/retail_before_after` | mandatory | C | 5 | Analytical checks passed for executed variants | Independent transformation replay and signed deltas; compare frozen and current policies. |
| `advanced/retail_single_source` | mandatory | C | 6 | Analytical checks passed for executed variants | Independent streaming grouped counts, CDF/TV/Wasserstein references and 2×2 statistics. |
| `comparisons/taxi_disk` | mandatory | D | 22 | Analytical checks passed for executed variants | Independent Parquet/CSV population receipts, directional effects and segments, scratch/cleanup watchdog. |
| `temporal/bike_regular_and_retail_events` | mandatory | B | 5 | Analytical checks passed for executed variants | Independent sorted instants, schedule/gap checks, locked duplicate and DST controls. |
| `temporal/beijing_layout_and_folds` | mandatory | C | 7 | Analytical checks passed for executed variants | Independent time-grid, interval endpoint and wide/long equivalence calculations. |
| `temporal/bea_revisions` | mandatory | B | 4 | Analytical checks passed for executed variants | Publisher release times and independent as-of selection per stable row key. |
| `temporal/electricity_panel` | mandatory | D | 21 | Analytical checks passed for executed variants | Independent archive slot/client count, DST ambiguity map and grouped event/measurement masks. |
| `temporal/taxi_irregular` | mandatory | C | 5 | Analytical checks passed for executed variants | Independent elapsed-time and already-missing/invalid clock populations by source field. |
| `text/scifact_corpus_retrieval` | mandatory | B | 4 | Analytical checks passed for executed variants | Independent lexical ID map, extractive readback and unknown judgment accounting. |
| `text/squad_span_qa` | mandatory | B | 4 | Analytical checks passed for executed variants | Extract original spans by independent substring check with byte and UTF-16 fixtures. |
| `text/ewt_sequence_tags` | mandatory | B | 3 | Analytical checks passed for executed variants | Token, sentence, range and empty-node counts; independent sequence-tag validation. |
| `text/multiwoz_conversation` | mandatory | C | 5 | Analytical checks passed for executed variants | Independent dialogue/turn joins, structural checks and malformed-turn ledger. |
| `text/massive_guided_and_full` | mandatory | D | 21 | Analytical checks passed for executed variants | Independent per-locale/partition/intent counts, exact lexical IDs and authored contamination pairs. |
| `text/paired_multilabel_generation` | mandatory | C | 5 | Analytical checks passed for executed variants | Independent compatible joins, exact duplicate pair checks and Unicode text boundary controls. |
| `text/long_corpus_and_local_models` | mandatory | D | 20 | Analytical checks passed for executed variants | Independent source and tokens/windows sample, small exhaustive duplicate reference, expected failure and cleanup. |
| `images/pet_classes_and_masks` | mandatory | C | 7 | Recorded failure or blocker; see attempts | Independent stem/label/mask code and dimension checks with verified small manual sample. |
| `images/coco_detection_segmentation` | mandatory | D | 23 | Analytical checks passed for executed variants | Independent original annotation counts, dimensions, box normalization and mask polygon/RLE reference. |
| `images/splits_versions_and_privacy` | mandatory | C | 6 | Analytical checks passed for executed variants | Independent file/raster fingerprints, annotated expected overlap and selected authorized references. |
| `cross_representation/bea_pdf_docx` | mandatory | C | 8 | Analytical checks passed for executed variants | Independent stratified 20-cell transcription per vintage, Workbook locators and hand-checked units. |
| `cross_representation/mixed_and_reviews` | mandatory | C | 7 | Analytical checks passed for executed variants | Hand-specified relationship graph and verified source spans, media and canaries. |
| `cross_representation/fanout_limit` | mandatory | D | 20 | Analytical checks passed for executed variants | Independent generated row cardinality and integer partition oracle; measure scratch and cleanup. |
| `cross_representation/m9_document_requalification` | mandatory | C | 48 | Recorded failure or blocker; see attempts | Frozen family-disjoint source-cell and claim labels, separate independent BEA adjudication. |
| `cross_representation/m9_caption_requalification` | mandatory | C | 40 | Analytical checks passed for executed variants | Independent image-family and donor ledger, documented association labels and ambiguous negatives. |
| `integration/history_and_disclosure` | mandatory | B | 8 | Analytical checks passed for executed variants | Independent file hashes, declared content exclusions and stored artifact round trip. |
| `integration/report_profiles_and_navigation` | mandatory | B | 12 | Recorded failure or blocker; see attempts | PDF page render and endpoint link validation, human/agent observations signed separately. |
| `text/long_corpus_1gib_extension` | optional | D | 24 | Not assessed | Independent record/work counters and resource sampler. |
| `temporal/household_large_reserve` | reserve | D | 19 | Reserve | Independent time keys, continuity and missing markers by population. |
| `images/open_images_convention_reserve` | reserve | C | 12 | Reserve | Original CSV IDs, dimensions and explicit conversion calculations. |
| `practitioner/external_review` | optional | B | 0 | Not assessed | Direct human task completion, interview observations and reviewed artifacts. |
