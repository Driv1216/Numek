# M9 implementation verification

The repository [Verification skill](../../agents/skills/verify/skills.md) governed
focused foundational checks, coherent implementation and affected closure. M1–M7
acceptance remains settled; historical evidence is preserved. No external gate,
persistent review service or verification campaign is introduced.

## Final targeted corrections (2026-10-13)

The final correction pass added private bounded source witnesses to structural
findings, raw native document/text containment, exact M7 raster overlap and bounded
perceptual image candidates, and stakeholder prose in the browser and reports.
Contracts and M1–M7 code remain unchanged. Historical artifacts and measurements
below were preserved; this pass did not rerun the full suite, models, benchmarks,
resource experiments, live browser scenario or PDF QA.

**13 distinct focused cases passed.** Six new correction cases cover structural
source resolution/privacy/review binding and mutation, association orphans,
native PDF and DOCX containment (including DOCX cell spans), image representation
equality versus perceptual candidates and work bounds, immutable human rendering,
and the completed investigation Flask route. Seven existing cases exercise
duplicate uniqueness, explicit association deduplication/orphans, normalization
collisions, ancestry deduplication, PDF/DOCX financial reconciliation and exact
locators, and same-source split scopes. The initial image fixture used a degenerate
gradient whose perceptual hash did not meet the declared radius; a deterministic
textured fixture replaced it and the directly affected case passed. The six new
cases subsequently passed together; DOCX cell, image budget and report-priority
assertions passed in the final three-case focused check. No PDF was rendered.

Source-level comparison with the prior inspection ZIP (algorithm identity
`7feb987e5ce6c419ed60be68eac4b6b20b98f1dd5a9f69ba4f6ef458f547e6f6`)
confirmed byte-identical `cross_models.py`, `cross_documents.py`,
`cross_sources.py` and `cross_contracts.py`. AST comparisons confirmed unchanged
`clock`, `context`, `relationship_contexts`, `transform`, `canonical`, `compare`,
`discover`, `reconcile`, `required`, and the `_core` model selection/claim
construction block. Relationship evidence additions preserve existing edge/count
semantics, covered by the focused cases. Existing model qualification is explicitly
carried forward in `cross_model_artifacts.json`, with original evaluated identities
and thresholds retained; there are no fresh model or capacity claims. Supplemental
overlap heuristics are separate from these qualified semantic methods.

Files changed: `cross.py`, `cross_diagnostics.py`, `cross_private.py`,
`cross_presentation.py`, `cross_web.py`, `cross_model_artifacts.json`,
`templates/cross_ui.html`, `templates/cross_report.html` (all under
`src/datatrust/`), `tests/m9/test_targeted_corrections.py`,
`docs/M9_CROSS_REPRESENTATION_RELIABILITY.md`, and this evidence note.

Focused commands used (follow-up runs targeted only intervening edits/failures):

```bash
PYTHONPATH=src:. .venv/bin/pytest --import-mode=importlib -q tests/m9/test_targeted_corrections.py tests/m9/test_integrity.py::test_duplicate_unique_keys_block_no_cartesian tests/m9/test_integrity.py::test_explicit_associations_dedup_and_orphans tests/m9/test_integrity.py::test_numeric_normalization_collision_not_merge tests/m9/test_integrity.py::test_declared_two_hop_ancestry_deduplicates_endpoints tests/m9/test_foundation.py::test_financial_reusable_conflicts_and_exact_locations tests/m9/test_controls.py::test_same_source_split_scopes
PYTHONPATH=src:. .venv/bin/pytest --import-mode=importlib -q tests/m9/test_targeted_corrections.py::test_image_pixel_overlap_and_similarity_remain_distinct
PYTHONPATH=src:. .venv/bin/pytest --import-mode=importlib -q tests/m9/test_targeted_corrections.py
PYTHONPATH=src:. .venv/bin/pytest --import-mode=importlib -q 'tests/m9/test_targeted_corrections.py::test_document_text_containment_resolves_without_mapping[docx]' tests/m9/test_targeted_corrections.py::test_image_pixel_overlap_and_similarity_remain_distinct tests/m9/test_targeted_corrections.py::test_structural_examples_are_bounded_exact_and_private
```

Remaining limits: exact containment examines complete raw units of at least 50
graphemes within the configured selection/region/work bounds, not arbitrary partial
or semantic overlap. Perceptual hashes require M7 visual eligibility and are only
review candidates. More than one exact image representation can share an overlap
key; affected-record counts remain deduplicated. Native extraction, no-OCR limits
and narrow semantic qualification profiles remain unchanged. Current presentation
was checked through HTML and Flask rendering; existing PDF/browser ledgers below
describe the earlier presentation, not a fresh visual inspection of this pass.

## Recorded evidence

- Repository compatibility suite: **493 passed**, six dependency deprecation
  warnings, 49.62 seconds. Final affected M9 suite: **33 passed**, 9.36 seconds,
  including additional independent DST-fold, two-hop ancestry/deduplicated
  endpoints and mutation-before-publication controls. Earlier collection failed
  with a missing repository path/import mode; the corrected command below passed.
- [Full native API pipeline](results/end_to_end.json): 20 records/21 PDFs and
  separately 20 records/21 DOCX documents; 18 revenue agreements, one discrepancy,
  one conflict; 19 support candidates and one mixed semantic result. Actual
  optional workers had socket connect/connect_ex/create_connection blocked.
  Exact locators, all review statuses, strict reload, separate notes, privacy,
  explicit disclosure, bounded claims and non-English abstention passed.
- [Live browser financial story](results/browser_acceptance.json): ordinary
  source/relationship/mapping/rule controls, two reusable recipes, sample preview,
  one confirmation and full native run. Both cells/passages and context eligibility
  were inspected. Analytical HTML/PDF/JSON, protected manifest and separate review
  downloaded; snapshots restored in a new session, another audit's review was
  rejected, and reopened downloads preserved original analytical evidence.
  Changing one authored PDF made that reference unavailable while the three
  historical decisions remained readable. The temporary server was stopped.
- [PDF inspection](results/pdf_qa.json): all **29 pages** across native PDF/DOCX,
  bounded-model and explicitly disclosed variants were rendered with bundled
  Poppler and visually inspected. Tables, counts, conflicts, coverage, method
  details and footers are readable without clipping/overlap. Human views retain
  five examples/actions per block; JSON preserves computed bounded details and
  omissions. [Example analytical HTML](results/reports/closure/pdf_financial.html)
  and [PDF](results/reports/closure/pdf_financial.pdf) omit source content.
- [Wheel/runtime](results/package_runtime.json): new modules, templates, pinned
  registry and extras included; models/corpora excluded. Python 3.11 on the recorded
  local arm64 host was exercised; package supports Python 3.10+, but no separate
  Python 3.10 interpreter run is claimed.

Tests cover strict contracts and typed keys, precision/locale/date conventions,
association duplicates/orphans and blocked Cartesian joins, wrong layouts,
missing/symlink evidence, DOCX revision/merged/package limits, authority/as-of ties,
discovery bounds, separation/ancestry, provenance/privacy, cancellation, source
mutation, isolated optional faults, surviving exports, CSRF/ownership/collisions,
guided controls and review replacement/binding. M5 exact-clock tests and existing
M4–M7 worker/export evidence remain valid where reused.

## Qualified optional populations

[Text qualification](results/text_qualification.json) measures native extraction,
declared mapping/context, E5 retrieval, NLI and emitted candidates. Calibration
has 100/class and held-out has 200 each of support, contradiction and insufficient
evidence, separated by entities, document bytes, authored layout families and
sentence variants. Final operating point is score 0.8/margin 0.1. On these narrow
controls support/contradiction precision and recall are 1.0; all 200 insufficient
cases abstain, with zero false findings and no unexamined held-out cases. These
authored financial controls do not establish natural-document or general claim
verification accuracy. Shared templates/families are not independent population
samples; raw scores are not calibrated probabilities.

[Paired image/text qualification](results/image_qualification.json) reuses pinned
licensed COCO bytes/captions and M7 decoding. Twenty calibration image families
are separated from 47 held-out families. Held-out has 235 correct and 235 planted
swapped associations; precision 235/236, recall 235/235, one false flag. Swaps
prefer disjoint supplied categories and are association negatives, not independent
caption-falsity adjudications. ICC/alpha exclusions remain explicit.

Both model workers were network-blocked. Only explicit measured financial-native
English and COCO caption profiles ship as qualified; other populations abstain.
[Qualification reuse](results/qualification_reuse.json) records the evaluated
algorithm identity and the final identity. Two subsequent reporting-only changes
corrected the summary's optional-finding count and exposed per-rule selected/not-
selected denominators. Extraction, context, selection, retrieval, tokenization,
models, thresholds and emitted evidence did not change; their valid qualification
evidence was reused. Fresh shipping audits verified final counts and coverage.

## CPU measurements and limits

[Small workload](results/small_resources.json): 10,000 records/associations and
field reconciliations, 50 simple native PDF pages, **23.97 seconds**, 0.171 GiB
sampled RSS, 0.016 GiB workspace.

[Large workload](results/large_resources.json): one million records, five million
explicit document-reference rows/associations with all declared context checks,
1,000 simple native PDF pages, **485.67 seconds**, 2.36 GiB sampled RSS, 2.98 GiB
workspace and 0.78 GiB spill. It does not measure one million field reconciliations.
Concurrent local verification load was present. Initial narrower measurements are
retained separately; they are not advertised as final scope. The final changes
after these runs only affected summary/selection reporting, not workload execution.

These are engineering measurements on authored layouts, not arbitrary-document
capacity or latency guarantees. Resource ceilings remain provisional. Loading,
tokenization, inference, actual admitted/abstained/unselected work, per-phase peaks
and final verification are recorded. A two-claim bounded audit retains the full
20-record population, two selected claims and 18 unselected claims. Hard required
failures remain atomic; an isolated optional model fault preserves only verified
deterministic evidence with partial status.

## Reproduction

Use the existing environment or install the project extras `documents`,
`cross-models`, `images`, `parquet`, `dev`, plus development-only ReportLab.
Provision exact publisher model bytes with `model_download.py` (explicit
development network operation); runtime audits never download. Image qualification
uses the pinned M7 corpus and caption archive. Generated data/model bytes and
private manifests/disclosures are ignored, not bundled into the package.

```sh
PYTHONPATH=src:. .venv/bin/pytest --import-mode=importlib -q
M9_RUN_LABEL=reproduction1 PYTHONPATH=src:. .venv/bin/python -m validation.m9.verify
PYTHONPATH=src:. .venv/bin/python -m validation.m9.benchmark
PYTHONPATH=src:. .venv/bin/python -m validation.m9.image_benchmark
PYTHONPATH=src:. .venv/bin/python -m validation.m9.resources
PYTHONPATH=src:. .venv/bin/python -m validation.m9.resources --large
PYTHONPATH=src:. .venv/bin/python -m validation.m9.browser_server
```

Use a fresh verification label to preserve collision-safe analytical artifacts.
Qualification scripts deliberately refresh their own registry entries/ledgers;
do not rerun unchanged expensive benchmarks solely for another documentation edit.
The browser server admits only the generated validation data root, binds loopback
and cleans owned sessions on shutdown. PDF QA uses read-only Poppler renders.

Model/tokenizer warnings and unavailable writable Fontconfig cache messages were
observed; report conversion succeeded and visual inspection passed. No general
semantic validity, OCR, audio/video, model monitoring or unrestricted verification
claim follows from these results.
