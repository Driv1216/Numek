# M9 cross-representation reliability intelligence

Implemented 2026-10-13. M1–M7 are accepted; M8 audio is deliberately deferred.
M9 investigates declared relationships between supplied local records, native
documents, text and images. Its primary workflow reconciles many structured
records through reusable PDF/DOCX mappings and retains competing evidence.
It does not assign a universal reliability score or establish external truth.

## Interfaces and installation

Install `.[documents]` for native PDF/DOCX and `.[parquet]` for optional flat
scalar Parquet. Image inputs reuse `.[images]`. Optional local NLI/SigLIP use
`.[cross-models]`; artifacts must be separately provisioned and match the
publisher revisions and hashes in `cross_model_artifacts.json`. Runtime never
downloads models, calls an inference service, or executes remote model code.

```python
from datatrust import (
    DataTrust, CrossRepresentationAuditSpec, CrossRepresentationInputSpec,
    RelationshipSpec, DocumentMappingSpec, ReconciliationRule, ClockSpec,
)

spec = CrossRepresentationAuditSpec(
    inputs=(
        CrossRepresentationInputSpec("records", "/data/records.csv"),
        CrossRepresentationInputSpec("documents", "/data/documents.csv",
            kind="document", asset_root="/data", layout="finance"),
    ),
    relationships=(RelationshipSpec("support", "records", "documents",
        left_keys=("entity",), right_keys=("entity",),
        context={"entity": ["entity", "entity"], "period": ["period", "period"]},
        cutoff=ClockSpec("cutoff"), availability=ClockSpec("available")),),
    mappings=(DocumentMappingSpec("revenue", layout="finance", kind="table_field",
        headers={"label": ["Metric"], "period": ["Period"], "value": ["Value"]},
        row_column="label", row_label="Revenue", context_columns={"period": "period"},
        unit="INR", currency="INR"),),
    rules=(ReconciliationRule("revenue", "support", "revenue", mapping="revenue",
        unit="INR", currency="INR"),),
    allowed_roots=("/data",),
)
result = DataTrust.audit_cross_representation(spec)
artifacts = result.generate_artifacts("report.pdf", format="pdf", json_path="report.json")
reviews = result.review_dispositions(reviewer="Local reviewer")
target = next(iter(result.profile["review_targets"]))
reviews.set(target, "unresolved", "Further investigation required")
reviews.export("review.json", result=result)
```

Both CSVs above have logical `id` columns. The record CSV contains `entity`,
`period`, `revenue`, `cutoff`. The document manifest contains `entity`, `period`,
`path`, `available`; paths resolve against the declared root. JSON construction
rejects unknown fields and contradictions. Manifest-relative paths resolve
against the specification file, never an implicit remote URI.

```sh
datatrust cross-representation --spec audit.json --out report.pdf --format pdf --json-out report.json
datatrust cross-evidence --report report.json --manifest manifest.json --ref evidence_ID --data-root /data --show-content
datatrust cross-review --report report.json --manifest manifest.json --target item_ID --disposition unresolved --out review.json
datatrust cross-review --report report.json --manifest manifest.json --import-review review.json --out review-copy.json
datatrust ui --data-root /data
```

The browser's `/cross-representation` workflow has source/manifest, association
and context, mapping, rule, preview and confirmation controls. It can export or
import reusable specification/configuration JSON. New declaration IDs add an
item; submitting an existing ID replaces that item. Advanced JSON also supplies
separation policies, explicit association tables, conversions and work settings.
Preview is seeded and limited to 20 distinct assets across declared source/layout
strata. Counts describe this sample, including linked records without a sampled
document. Confirmation seals all referenced sources; the full audit processes
every admitted association. Editing declarations invalidates confirmation.

## Contracts and deterministic evidence

Schema `1.7`, methodology `cross_representation_reliability_v1`, is additive to
existing milestone serializers. New contracts live in `cross_contracts.py`:
inputs, relationships, mappings, rules, separation, limits, configuration,
disclosure and completed results. Reviews have independent `m9_review_v1` JSON.

Inputs are CSV, mapped scalar JSONL, optional flat scalar Parquet, TXT, directly
declared native PDF/DOCX or document manifests, and M7 raster-image manifests.
Text fields/extracts must declare their supplied provenance. Source roles,
languages, layouts, split membership and clocks are explicit metadata.

Relationship keys are composite, namespace-qualified and typed by default.
CSV strings remain lexical; JSON numbers, strings, booleans, native dates and
timestamps remain distinct. `lexical`, NFC or numeric key views require explicit
declaration, retain collision counts and block ambiguous joins. Repeated unique
keys, missing endpoints, cardinality and required/inverse gaps remain separate.
Many-to-many associations require explicit rows; duplicated association rows
are deduplicated without multiplying affected populations.

Context checks run for every declared association, including relationships
without reconciliation rules. Entity, period, version, unit and currency bindings
are paired selectors. Availability, cutoff, validity and exact/latest-as-of
selection use M5 clocks; contradictory ties remain ambiguous. Filesystem dates
do not establish publication. Optional requirements cover entity/group or exact
text/image separation and supplied ancestry up to three edges; common terminal
ancestor sources are required. Derivations and training exposure are not inferred.

Structural investigation retains bounded private source examples for missing or
repeated logical IDs, invalid relationship keys, normalization collisions,
uniqueness violations, unresolved required endpoints and invalid/duplicate
association rows. Duplicate examples retain two distinct record locations.
Each violation category retains up to `limits.witnesses` examples, with a shared
`limits.details` ceiling per relationship; composite-key component omissions are
disclosed. Examples are individually reviewable; counts still describe the full
admitted population. Portable exports contain opaque references rather than keys
or values, and resolving a reference requires the original, unchanged sources.

`content` separation now compares raw extracted PDF text, DOCX paragraphs/table
cells and TXT units with declared text fields, without requiring reconciliation
recipes. Exact whole-unit equality covers admitted units. An additional bounded
search uses M6 winnowing fingerprints to find exact containment of an entire
eligible text unit within another, with at least 50 graphemes. Source-aligned
spans/cells bind these matches to frozen extraction settings. It does not infer
semantic similarity or treat shared fingerprints as equality. Shorter partial
passages and arbitrary partial overlaps remain outside this search.

`assets` separation retains file equality and adds M7 native-raster and oriented
RGBA equality, so losslessly re-encoded images can overlap despite different
file bytes. M7 eligible opaque RGB perceptual hashes also yield review candidates
at Hamming distance at most six. These candidates never establish a deterministic
violation. `shared_units` counts distinct exact representation keys (one image
pair can share more than one representation); affected records are deduplicated
per side. Overlap examples distinguish exact representations from candidates.

Supplemental searches select up to `limits.candidates` eligible units per side in
seeded record order; text units exceeding `limits.region_chars` are excluded from
containment search, not silently truncated. M6 diagonal pair enumeration visits
both sides within the pair ceiling. Fingerprinting/comparison work shares the
job-wide discovery-visit limit; exact equality populations remain intact. Coverage
reports examined pairs, excluded units, bounds and incomplete extraction. Reached
document-search bounds cannot become a clean absence conclusion; witnessed exact
overlap remains reportable. Image similarity coverage does not change exact
equality counts. No embeddings, new model or persistent index is introduced.

Rules compare strings/categories, explicit normalized views, precision-safe
decimals with declared conventions/conversions/tolerance, or declared date
formats. Evidence number/date conventions may differ explicitly from the record.
Unknown units and context prevent unsupported comparisons. Source/role authority
can resolve competing eligible values only when uniquely declared; it establishes
comparison policy, not truth. Agreement never hides conflicting evidence.

## Native documents and discovery

Pinned pdfplumber extracts source-aligned text/glyphs and practical tables.
PDF evidence locators include physical page, extraction settings, span and
character/cell geometry. Pinned python-docx plus narrow OOXML inspection retains
package part, block/table/cell/XML location and spans. DOCX has no invented page
numbers. Body paragraphs/tables are default; other supported parts are explicit.
Revision markup, ambiguous merged tables, omissions and unsupported parts are
reported and cannot silently support a clean comparison.

A recipe is assigned to an explicit layout family. Label/section recipes use
declared literal aliases, anchors and timed bounded capture patterns. Table
recipes bind exact header aliases, row labels/record selectors, value and context
columns. PDF line-based tables are default; text-based extraction is an explicit
alternative. The engine does not try strategies until one agrees with a record.
Approved selector substitutions are escaped literals. Discovery never uses the
expected answer value. Layout changes must satisfy anchors/header bindings or
become unmatched/ambiguous. Manual span/cell overrides remain exceptional and
their narrower scope does not establish whole-document reconciliation.

Each asset/settings identity is extracted once. Equal repeated values retain
their individual occurrences. Different eligible values produce a conflict;
unknown-context candidates prevent complete assurance. No candidate means
mapping/evidence not found in examined scope, not proof that the document lacks
the fact. Default discovery bounds are 100 occurrences per document/rule,
100 tables/document and 10,000 characters/anchored region, plus job accounting.
A reached bound marks scope incomplete. Already witnessed conflicts remain
reportable; unique agreement and absence cannot be asserted across excluded work.

Coverage separates selected/processed/text-bearing/empty/text-free/failed and
unsupported pages or parts. Digitally generated PDFs and straightforward native
tables are supported. Scanned evidence remains unresolved. Supplied external OCR
extracts may participate as provenance-declared text; OCR execution, DOCX
pagination and advanced layout/embedded-image interpretation are deferred.

## Optional semantic investigation and qualification

NLI uses local pinned `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli`, English atomic
claims or simple fixed templates and M6 E5 retrieval/window principles. Retrieval
is confined to declared context-eligible supplied evidence. Claims count against
token limits; unsuitable fragments, oversized claims, undeclared/non-English
language and unsupported populations abstain. No silent truncation is used.
Different evidence occurrences reserve retrieval slots. Full extraction/search
and selected-window coverage remain distinct. Neutral or missed retrieval never
establishes falsity. Numeric/date findings cannot be overridden by NLI.

The image/text adapter uses full pinned `google/siglip-base-patch16-224` for
declared pairs and optional bounded alternative relationships. It returns paired
scores/rankings and compatibility/misassociation candidates. It makes no object,
count, spatial-grounding or factual visual verdict and does not replace joins.
Independent E5/DINO vector spaces and M7 image-copy thresholds are not reused.

Qualification covers native extraction, mappings/context, retrieval, comparisons,
model and emitted candidates, not isolated classifier accuracy. Parser/mapping,
selection/window/tokenizer/model identities, thresholds, abstention and budgets
freeze before held-out evaluation. Answerable abstentions count as recall misses;
extraction/retrieval/resource exclusions remain visible. Raw scores are not
probabilities. Changed algorithm identities invalidate packaged qualification;
unqualified or out-of-profile methods abstain while the deterministic core works.
Changes outside the measured semantic pipeline can carry forward valid qualification with an
explicit evidence-reuse record. The final correction pass preserves the measured
extractors, reconciliation/context functions, claim selection, adapters, retrieval,
tokenizers, thresholds and model artifacts; it does not claim a fresh benchmark.

The implemented shipping profiles are deliberately narrow:

- **Text:** authored English financial declarations in native PDF/DOCX, explicit
  `finance` or `financial_evidence_v1` layouts and label/text mappings. Calibration
  has 100 examples/class; held-out has 200 support, 200 contradiction and 200
  insufficient examples. Under disjoint entity/document/layout/sentence variants,
  final support and contradiction precision/recall are 1.0 and all insufficient
  examples abstain at score 0.8/margin 0.1. This is controlled qualification,
  not general natural-document reliability or language certification.
- **Image/text:** pinned eligible COCO caption families, explicit
  `coco_captions_v1` layout and supplied field mappings. 20 calibration image
  families and 47 held-out families yield 235 correct and 235 planted swapped
  held-out pairs; misassociation precision is 235/236, recall 235/235. Swaps prefer
  disjoint supplied categories; they are association negatives, not independently
  adjudicated caption-falsity labels. Alpha/ICC exclusions follow M7 decoding.

Models use CPU float32, two threads, verified local safetensors and bounded
batches. Tokenizer input bytes/work, windows, claims/pairs, inference, loading and
artifact verification are accounted. Shipping profile is bound to this measured
configuration. No model monitoring, generative judgment or external claim search
is introduced. See the qualification and resource ledgers in `validation/m9`.

## Reviews, privacy, resources and publication

HTML/PDF and the completed browser overview use stakeholder prose for findings,
reconciliation outcomes, overlap and coverage. Detailed counts and bounded review
references remain in the technical report sections; full scores, method identities
and execution/coverage payloads remain in strict JSON. Rendering does not change
analytical evidence or review bindings. Historical reports are not regenerated.

Review targets are retained record investigations or aggregate findings. Confirm,
dismiss and unresolved with optional 2,000-character notes are separate from
immutable analytics; absent means unreviewed. Aggregate confirmation does not
imply all records were inspected. Filters may hide locally dismissed items.
Snapshot JSON binds audit/result/private-manifest/target digests and exact evidence
references. Import strictly replaces the session snapshot, rejecting mismatches
or unknown targets; decisions do not transfer to reruns. Reviewer labels are
unauthenticated. Session shutdown removes state unless exported. Reopening the
matching result/manifest preserves historical decisions even if evidence is gone.

Default analytical HTML/PDF/JSON have aggregates, methods and opaque references.
Raw financial values, claims, text, paths, identifiers, source hashes, images,
vectors and notes are private. Owner-only manifests contain frozen declarations,
asset/parser/model identities and exact locators, not a saved document corpus.
Resolution rereads originals and checks content/location/settings before and after;
changed evidence is unavailable, without location repair. Explicit export variants
can disclose at most 20 excerpts of 240 characters and metadata-stripped selected
images under M7 bounds. Local inspection does not authorize portable disclosure.

One M9 orchestrator reuses the supervised worker, projected DuckDB relations,
M4 framing/keys/grouped joins, M5 clocks, M6 spans/windows, M7 secure capture/decode
and shared canonical exporters. It never nests complete milestone audits or adds
a persistent vector service, ontology or modality plugin framework.

Default shared safeguards are 2 GiB DuckDB memory, sampled 6 GiB RSS, two threads,
30 minutes global deadline, 64 GiB workspace, 2 GiB disk reserve and 32 MiB public
result. M9 provisional admission limits are 64 inputs, 128 declarations,
10 million associations, 1,000 documents/10,000 pages/50 million characters,
128 MiB/document, 256 MiB expanded DOCX and 64 MiB private result. Optional starting
ceilings are 2,000 claims, five candidates/claim, 2,000 image pairs, 600 seconds,
64 MiB tokenizer inputs and one million emitted tokens; these are safeguards,
not completion promises. Required structural populations are never reduced.

Selection round-robins declared rules with seeded ordering. Model loading counts
against allocation; small measured batches proceed only within remaining work.
Time-dependent stopping can differ by machine and is recorded. Final verification
and report assembly reserve time. Hard source/admission/global errors, mutation,
cancellation and deadline publish no completed result. Unsupported documents and
bounded discovery produce explicit inconclusive scope. Planned optional limits
produce bounded completed investigation. An unexpected isolated optional model
failure preserves a verified deterministic core with partial status.

XML/package expansion and timed pattern work are bounded; encrypted/unsupported
inputs and active/external document relationships are rejected. Hyperlinks are
inert and not fetched. PDF conversion fetches only generated report resources.
Peak RSS/workspace/spill retain all phases. Per-file verification is not an atomic
filesystem snapshot and sampled memory monitoring can overshoot.

Audio, video, OCR execution, advanced layouts, automatic corrections, fuzzy entity
merging, unrestricted claim extraction/verification, inferred lineage, cloud
services, persistent review history and a universal score remain excluded.
