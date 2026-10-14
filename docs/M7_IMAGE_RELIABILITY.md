# M7 — Image Reliability Intelligence

M7 adds schema **1.6**, methodology **`image_reliability_v1`**, and separate image
contracts. Accepted M1–M6 interfaces, calculations and historical artifacts remain
compatible. Image audits do not produce a universal quality score, correct labels,
infer training exposure, or turn similarity into proof of leakage.

## Installation and interfaces

```sh
python -m pip install '.[images]'
# Optional CPU embeddings, using separately provisioned verified local artifacts:
python -m pip install '.[images,image-embeddings]'
datatrust ui --data-root /absolute/dataset/root
datatrust images --spec audit.json --out review.pdf --format pdf --json-out review.json
datatrust image-evidence --manifest .datatrust-private/AUDIT_ID/manifest.json \
  --report review.json --ref image_REFERENCE --data-root /absolute/dataset/root
```

CLI exit statuses are 0 for completed evidence (including planned bounds), 2 for
exported partial core evidence, and 1 for setup, required-analysis or export failure.
Use `--example-ref`, `--overlays`, and `--disclose-labels` for an explicitly disclosed
portable variant; `--show-image` authorizes pixels during exact CLI resolution.

```python
from datatrust import (
    DataTrust, ImageAuditSpec, ImageInputSpec, ImageSourceSpec,
    ImageTaskSpec, ImageMappingSpec, ImageAnnotationSpec,
)

spec = ImageAuditSpec(
    inputs=(ImageInputSpec(
        "dataset", ImageSourceSpec("/data/manifest.jsonl", "jsonl", "/data/images"),
        ImageTaskSpec("detection"),
        ImageMappingSpec(logical_id="id", split="split", groups=("subject",)),
        ImageAnnotationSpec(categories=("car", "person"), expectation="required"),
    ),),
    allowed_roots=("/data",),
)
result = DataTrust.audit_images(spec, progress=lambda event: print(event))
result.generate_artifacts("review.pdf", format="pdf", json_path="review.json")
```

One JSONL occurrence in that example is:

```json
{"id":"001","path":"sample.png","split":"test","subject":"s1","objects":[{"category":"car","bbox":[10,20,50,80]}]}
```

The default box convention is encoded-image pixel `xyxy`. Declare `xywh` or
`normalized_cxcywh` explicitly when appropriate. Relative spec sources resolve
against the audit manifest; asset references resolve against the declared asset
root. JSON Pointer selectors are supported. CSV arrays/objects require declared
`json_columns`. A Python specification uses the paths it supplies.

`ImageAuditResult` exposes `profile`, `checks`, `evidence`, `findings`, `coverage`,
`execution`, schema/methodology identity and generation time. `to_dict()` and
`json_text()` are strict public projections. `generate_artifacts()` produces
completed-result HTML/PDF/JSON and a protected manifest. `resolve_evidence()` or
`DataTrust.resolve_image_evidence(manifest, reference, report, allowed_roots=...)`
resolves retained exact evidence. There is no path repair or approximate resolution.

## Declarations and supported inputs

All declarations are frozen dataclasses with strict `from_dict()` construction.
Unknown fields and incompatible combinations fail clearly. The contracts are
`ImageSourceSpec`, `ImageMappingSpec`, `ImageTaskSpec`, `ImageAnnotationSpec`,
`ImageInputSpec`, `ImageSplitRequirement`, `ImageComparisonSpec`, `ImageAuditSpec`,
`ImageSourceLimits`, `ImageWorkLimits`, `ImageModelOptions`, `ImageAnalysisConfig`,
and `ImageDisclosureOptions`.

- Directories inventory recursively. Class-subdirectory classification is an
  explicit layout and task. Filenames never imply labels, splits or groups.
- CSV/JSONL carry one occurrence per record. Associated annotation manifests need
  an explicit primary logical key and associated key; ambiguous bindings block
  dependent analysis.
- COCO instance JSON streams images, categories and annotations into DuckDB.
  Typed IDs, duplicate keys, references, taxonomy names, dimensions, boxes,
  polygon unions and compressed/uncompressed column-major RLE are checked.
  Classification derived from object categories requires explicit selection.
- YOLO detection supports safe standard YAML roots, split directories/path lists,
  class declarations and five-token normalized detection rows. Empty label files
  and missing files differ. Missing-as-negative is an explicit declaration.
  YAML construction, aliases and download directives are rejected.
- JPEG, PNG, BMP and single-frame WebP/TIFF are decoded. Animated/multipage assets
  and unsupported formats remain inventoried with exclusions. A readable header
  does not imply successful decoding. Truncated-image recovery is disabled.
- Semantic integer/palette/16-bit PNG, explicit RGB semantic mappings, binary
  instance PNG collections, and COCO polygons/RLE have bounded integrity checks.
  Binary instance records use `{"category":"object","mask":"instance.png"}`.
  Background/ignore values and annotation expectation/status remain independent.

Manifest inventory covers referenced assets; directory inventory covers declared
membership. It does not claim all unreferenced files under a manifest's asset root
were examined. Declare a directory input separately when that population matters.

## Identities, geometry and comparisons

Assets identify captured byte versions (SHA-256 plus verified filesystem identity).
Occurrences identify source positions, independent of asset reuse. Annotation
bundles and supplied objects have independent occurrence-bound identities and
canonical payload hashes. Logical keys preserve lexical and COCO typed distinctions.
Physical aliases remain recorded, with content processing reused.

Byte equality, native raster equality and oriented RGBA8 equality are separate
representations. Native hashing preserves mode/bit depth, palette/transparency and
unresized pixels. Oriented RGBA8 hashes EXIF-transformed pixels, preserved alpha and
ICC identity without resizing. High-bit-depth conversion and arbitrary ICC color
conversion are not silently claimed. Visual methods use eligible opaque RGB previews
up to 512 pixels on the longest side; exclusions have explicit populations.

Geometry requires known encoded, oriented or explicitly mapped affine frames,
verified dimensions and compatible schemes/category meanings. EXIF reflections and
rotations transform geometry as well as pixels. Known full resize mappings can
transform masks; partial crop/common mask coverage remains blocked. Equal aspect
ratios, names or similarity do not establish registration. Invalid annotations
cannot create an asserted compatible disagreement.

Version comparisons require declared logical alignment and unique keys. They
report additions/removals, exact overlap, population deltas, byte/raster changes,
split/group/status/taxonomy changes, and compatible canonical annotation changes.
Captured normalized mask content participates even when the relative annotation
filename is unchanged; filename equality does not establish annotation equality.
Without alignment, population and content overlap remain available. Unknown frames
produce “payloads differ; geometric comparison blocked,” not a geometric change.
Detection canonical multisets preserve supplied object IDs; automatic geometric
object matching and unrestricted pairwise mask IoU are not claimed.

Declared split requirements distinguish byte repetition and declared group overlap
from candidate similarity. `ImageSplitRequirement.group_mode` defaults to `per_key`:
each named selector is an independent separation requirement, so a shared subject
is detected even when session differs or is missing. Missing/invalid values block
only that key's population. Typed IDs remain distinct, and IDs containing "null"
are valid. Left occurrences are counted once across overlapping keys, with per-key
counts and missing/unaligned coverage retained separately.

Select `group_mode="composite"` explicitly when the intended group is the joint tuple.
Composite comparisons require all values and matching named key sets; selector
order does not change the tuple. Across sources, keys match only within an explicit
shared namespace; same-source keys share their source scope. Different key names
are not inferred to mean the same group. Partially comparable populations remain
partial, rather than claiming separation for missing or unaligned keys. Only declared
separation creates separation violations. Disk-backed relations avoid occurrence
Cartesian products.

## Methods and coverage

The required core reports inventory/decode/representation states, visual distributions
and contextual extremes, annotation states/validity, classes and object populations,
multilabel cardinality/co-occurrence, annotated negatives, box area/location/size,
crowd flags, mask occupancy and split/group composition. Boxes are never clipped.
Mask occupancy measures individual masks, not unions of overlapping instances.
Topology and semantic boundaries are not assessed.

Every eligible decoded raster gets a 64-bit DCT signature. Seven disjoint partitions
index all signatures. Declared cross-split queries run before within-split work,
querying the smaller side against the complete opposite index. Seeded round-robin
initial opportunities precede deeper bucket traversal. Radius six is checked by
XOR/popcount. Saturation and work/storage limits can omit candidates; queries,
references, loaded/visited postings, Hamming comparisons, saturated populations and
qualifying/detail omissions are disclosed per pair. Approximate chains never become
equivalence groups. “No candidate” only concerns the examined search.

Optional embeddings use verified local safetensors and pinned configuration,
processor, publisher revision/license identity and CPU runtime. No downloads,
remote code, substitutions or label predictions occur.
The local directory contains `config.json`, `preprocessor_config.json`,
`model.safetensors`, and `datatrust-model.json`. The manifest declares `model`,
`revision`, and a `files` object of SHA-256 values for those three files; all bytes
must also match the packaged publisher allowlist. Select it with
`ImageAnalysisConfig(models=ImageModelOptions("/absolute/model/directory"))`.
The development-only download helper in `validation/m7/model_download.py` shows
provisioning; runtime audits never invoke it. Selection is split-stratified,
half candidate-focused and half independent discovery, with independent slots
allocated one quarter to evaluation queries and three quarters to reference images.
Shared rasters count once. Coverage separates these purposes, eligible/selected/
encoded populations and complete versus sampled reference pools. The encoder and
cosine search share one stage allocation. Each endpoint proposes its top three;
their undirected union is then greedily capped to degree three at both endpoints.
Cross-split pairs precede within-split pairs, then descending cosine and stable
endpoint order determine retention. Coverage records union size, endpoint-cap
omissions and presentation-detail omissions separately. This deterministic review
budget is not a maximum matching or a matching-quality guarantee.

The shipping model/settings come from the [benchmark ledger](../validation/m7/results/model_benchmark.json)
and packaged `image_model_artifacts.json`. Model selection is conditioned on held-out
copy recall, false-candidate/redundancy burden, useful discoveries beyond perceptual
search, CPU time, memory and artifact size. Fixture calibration is not a universal
cosine threshold, production recall estimate or correctness claim. Failed earlier
settings remain recorded. No higher-quality mode is offered without meeting its
measured improvement and practicality criteria.

The recorded DINOv2-base encoder calibration precision is 97.06%; encoder held-out
precision is 93.94% with 12.11% macro transformed-copy recall. The separately
measured perceptual-plus-model pipeline has 89.66% held-out precision and 45.70%
macro recall; it does **not** meet the 90% combined precision target. Passing the
pinned encoder profile is not acceptance of that combined pipeline target. The
packaged review-evidence metadata preserves the exact existing measurements.
Those measurements use the original query-wise top-three protocol. Retrieval quality
after the new exported endpoint-degree cap has not been benchmarked; no matching-
quality improvement or preservation is asserted. Similarity remains investigation
evidence, particularly for low-information perceptual confounds.

## Resources, immutable evidence and failure semantics

Defaults are safeguards, not capacity promises:

| Resource | Default |
|---|---:|
| Metadata per file / combined | 1 GiB / 4 GiB |
| Referenced media per input / combined | 64 GiB / 128 GiB |
| Capturable encoded asset | 128 MiB |
| Locations / occurrences / annotation items | 100k / 1m / 10m |
| Pixels per asset / decode reservation | 32m / 512 MiB |
| Required decode work | 100 billion pixels |
| Polygon vertices / RLE runs | 10m each |
| Additional segmentation raster work | 100m pixels |
| Posting visits / Hamming comparisons | 100m / 50m |
| Bucket entries / qualifying pairs | 1,024 / 250k |
| Embedding rasters / cosine comparisons | 10k / 25m |
| Optional-stage / whole-audit deadline | 600 / 1,800 seconds |
| DuckDB memory / sampled worker RSS / threads | 2 GiB / 6 GiB / 2 |
| Workspace ceiling / free-disk reserve | 64 GiB / 2 GiB |
| Public result / private payload | 32 MiB / 64 MiB |

Repeated references within an input do not multiply media admission; separate roles
retain logical admission. Unique physical bytes and actual I/O are distinct. Image
media never inherits M4 CSV 5/8 GiB limits or its six-times-source workspace estimate.
Owned storage estimates metadata captures, relations/indexes, bounded buffers,
vectors, spill and exports.

Media is captured into one bounded immutable encoded buffer, hashed with opened-handle
identity checks, decoded and released. Oversized/unsupported assets are stream-hashed.
Only metadata needing stable multi-pass parsing is copied privately. Optional models
recapture selected media against expected hashes. Final publication securely rehashes
admitted sources and rechecks directory membership and unresolved-reference availability.
This is immutable per-file evidence, not an atomic filesystem snapshot. ctime-only
metadata changes are not treated as content mutation: file identity, size, mtime and
full byte hashes still must agree. Explicit model directories have their own narrowly
verified artifact root; they do not widen dataset authorization.

One orchestrator deadline covers preflight, required core, optional models, final
verification and assembly. Final verification reserves measured initial hash time
times 1.5 (at least 30 seconds), plus 30 seconds assembly. Models receive only the
remaining allocation and reduce population using measured throughput. A different
model never silently expands the whole deadline.

Invalid individual assets/annotations produce exclusions and evidence. Required
faults, incomplete traversal, mutation, cancellation and global resource/deadline
failure publish no completed result. Dependency/artifact/runtime errors fail preflight.
Unexpected isolated model failure discards its uncommitted evidence; verified frozen
core may return partial. Planned bounds are completed bounded evidence. PDF failure
retains valid HTML/JSON. Sampled resource limits can overshoot between observations.

## Privacy, exports and browser investigation

Portable defaults exclude images, supplied labels/identifiers, paths, source hashes,
EXIF/GPS and embedding vectors. Aggregates still contain private information. Manifests
are owner-only and contain identities/locators, not corpus copies. Existing default
artifacts remain readable after source deletion; local resolution then becomes unavailable.

Disclosure is a separate variant: at most 20 selected references, 1,024-pixel longest
side, 1 MiB per image, 8 MiB total. Re-encoded images strip source metadata; alpha
composites over white. Labels require separate opt-in. Verified overlays are generated
internally. Reports bind source evidence, manifest, selection, generated resources,
template/projection and canonical HTML digests. PDF resources are embedded; it does
not fetch corpus paths. Source/artifact aliases, traversal, symlinks, special files,
unsafe parsers and excessive allocations are rejected.

The browser offers standard-format presets, authorized local sources, asynchronous
inspection, explicit declarations, one confirmation and supervised execution. Its
session-local inspector shows retained examples/pairs, previous/next, zoom, annotation
state, method/distance, and compatible overlays. Local viewing does not authorize
portable image disclosure. Opaque session references, ownership/CSRF checks, no-store
responses, shared worker locking and cancellation remain enforced. Unresolved frames
block misleading overlays. The inspector does not edit or adjudicate annotations.

## Validation and remaining scope

See [M7 engineering evidence](../validation/m7/README.md) for executed checks, exact
datasets/model artifacts, benchmark failures and corrections, measured workloads,
page inspection and browser proof. macOS ARM64 CPU execution is measured; Windows
handle protections have source coverage but no native Windows execution evidence.
No full 100k-image decoding capacity guarantee is made.

Deferred: GPU/cloud processing, persistent indexes/services, archive/folder upload,
video/animated analysis, medical/RAW formats, panoptic/3D segmentation, unrestricted
topology and mask semantic correctness, object embeddings, automatic label correction,
learned quality scores, predictive performance, automatic registration/version matching
and universal leakage claims.
