# M7 engineering evidence

The [consolidated closure ledger](results/release/closure.json) records completed work, source identities and historical reuse.

The repository [Verification skill](../../agents/skills/verify/skills.md) governed
coherent implementation, focused checks, comprehensive affected closure and reuse
of valid historical evidence. The full repository suite passed **452 tests in
41.95 seconds**. Final M7 checks passed **54 tests in 6.64 seconds**, including the
subsequent RGB lexical-category and reused-browser-seal corrections. Unaffected
M1–M6 checks remain valid; the classification corpus and historical dry-run archive
verifiers passed. This is internal engineering evidence, not independent product
validation or a general capacity/recall guarantee.

## Public inputs and integrity

[Fresh corpus validation](results/release/verification.json) exercises 128 pinned
COCO val2017 images as unlabeled, supplied classification, multilabel, detection
and instance segmentation inputs. The prepared COCO subset contains **875 objects**.
Controlled logical version comparison proves that differing dimensions block
geometric annotation change claims. The corpus has 61 ICC-bearing images excluded
from default visual methods; its 67 eligible images remain distinct from all 128
successfully decoded images. Structural segmentation checks cover all supplied
objects; bounded raster work reaches 99,966,584 pixels and leaves 75 occurrence
comparisons blocked, without declaring those annotations invalid.

[Input identities and individual licenses](results/release/data_identity.json)
pin image bytes, source/flickr attribution URLs and the official annotation archive
SHA-256. Raw photos and transformed examples remain local, excluded from Git,
and retain their individual licenses. There is no collective image-license claim
or redistribution of those images. Prepared classification labels are explicit
fixture context derived from supplied object categories, not adjudicated scene labels.

Tests use independent inventory/state/box and COCO mask oracles, including
compressed/uncompressed column-major RLE, polygons, semantic 16-bit/palette/RGB
PNG and binary instance collections. Formats are compared under equivalent
declarations with deliberately distinct absent/null/empty/malformed cases.
EXIF orientations/reflections, full resize transforms, blocked crop coverage,
taxonomy names and lexical IDs protect comparison eligibility. Native/byte/oriented
raster identities remain separate. Security checks include changed content,
membership and availability, special files, traversal, hard links, malicious
structured inputs, allocation exclusions, private disclosure/caches and artifact
collisions (including initially missing references).

## Search and resources

[Default-budget 100k search](results/full_search/stress.json) indexes 100,000
controlled signatures into 700,000 partition entries. It took **88.96 seconds**,
completed all **30,000 cross-split queries** for the 80k/10k/10k split arrangement,
and recovered all 100 controlled near matches. It charged 52,484,042 posting visits
and reached the 50m Hamming-comparison bound. Within-training queries received
initial opportunities but did not complete. This measures signatures/index/search,
not full-resolution decoding of 100,000 images. Small exhaustive oracles and forced
saturation tests establish the uncapped radius-six guarantee and the consequences
of capped postings and pair storage; capped recall is never called exhaustive.

The [reduced-budget stress run](results/final/stress.json) deliberately used only
2m postings/1m comparisons and recovered six of those 100 controls. Its measured
1,000 JPEG locations/10,000 occurrences completed in **10.64 seconds**, with no corpus
copy, separate logical/physical admission and measured capture/final-verification I/O.
The earlier [measurement](results/stress.json) is retained as historical scope.

[Additional workloads](results/release/resources.json) measure a 29.36m-pixel PNG
(1.19 seconds, sampled peak worker RSS 757,956,608 bytes), 500 occurrences with
50 semantic 16-bit masks (1.59 seconds, 32,768,000 mask pixels), and 4,000 supplied
boxes across 40 COCO occurrences (1.50 seconds). Inputs were authored and removed
after measurement; these narrow populations do not establish general scale capacity.
The ledgers include source bytes, decoded/raster populations, runtime, sampled RSS,
owned workspace and read-byte coverage. Resource reservations are safeguards;
Pillow/runtime overhead and sampled supervision are not exact allocator caps.

## Offline models and review quality

The [final benchmark](results/model_benchmark.json) pins 2,000 files: 128 natural
families, 1,024 transformed derivatives and 848 authored distractors. Calibration
and evaluation separate natural families and authored control partitions. No-copy
queries include blanks, repeated motifs, noise and unrelated natural images;
self matches are excluded. The benchmark records input hashes, transformed-copy
strata, top-three suggestions, precision, false burden, useful new discoveries,
CPU runtime, memory, artifact identities and repeat stability. Model execution
blocks network sockets. Publisher/model/license hashes are in the packaged registry.

The first [benchmark attempt](results/model_benchmark_initial.json) and the
[natural-only no-copy setting](results/model_benchmark_natural_only.json) remain
recorded. The latter omitted authored no-copy queries and was rejected after those
queries produced 300 false suggestions per 100 queries for every model. The final
calibration uses a conservative 95% precision / five false suggestions per 100
no-copy-query margin before held-out evaluation.

**DINOv2-base** is the measured default, threshold **0.9958711266517639**, exact
revision `f9e44c814b77203eaa57a6bdbbd535f21ede1415`, Apache-2.0 publisher artifacts.
It completed the 2,000-image CPU benchmark in **103.58 seconds**, sampled RSS
1,133,854,720 bytes and artifact bytes 346,346,896. Its held-out encoder-only macro
recall is **12.11%**, candidate precision **93.94%**, and false suggestions per 100
no-copy queries **0.82**. It adds **27 copies** beyond perceptual search. DINOv2-small
had higher recall but missed held-out precision (89.69%). SigLIP had no useful recall
at a setting meeting the difficult controls. No higher-quality mode qualifies.

[Complete review-pipeline measurement](results/release/selection_closure.json)
separately combines exhaustive fixture perceptual candidates with the calibrated
model and a three-suggestion review setting. Held-out macro recall is **45.70%**,
precision **89.66%**, false suggestions per 100 no-copy queries **5.53**. The pipeline
precision is below the encoder-only target because different flat-color images can
have the same perceptual signature. The fixed eight-pair internal visual sample
shows that confound and a useful model-only overlay copy. Rotation, padding and
heavy crops remain poorly recovered. These limitations are explicit; no fixture
threshold becomes a universal correctness, leakage or absence claim.

[Actual final model audit](results/release/selection_closure.json) encodes 32 raster
representatives, with its artifact directory outside the authorized dataset root.
[Spawned-worker offline proof](results/release/offline_worker.json) additionally
blocks socket operations inside the actual isolated model worker. Earlier audit
validators blocked sockets in the parent; the benchmark ran in that blocked process.
The worker proof removes ambiguity about Python spawn inheritance.

## Presentation, interfaces and failure boundaries

[Page QA](results/release/pdf_qa/manifest.json) records **61 visually inspected pages**
across all five tasks, version comparison, explicit disclosure, the final model,
partial core recovery and completed bounded search. All eight topics and page
footers remain present. Dense provenance and disclosed overlays were additionally
inspected at full-page resolution. Frozen completed evidence was reprojected during
presentation refinement; unaffected analytics were not rerun to change layouts.
Explicit natural-image disclosure PDFs and their page renders stay excluded from Git.

[Browser proof](results/release/browser-completed.jpg) shows authored local COCO
segmentation, standard presets, explicit declarations, one confirmation, supervised
execution and local pair/overlay investigation. Live tests verify declaration
retention, previous/next and checked overlay state. A real browser JSON download
was verified to contain no source paths or image data. Flask integration executes
native PDF output, strict JSON/private downloads, session isolation, CSRF, source
mutation, seal reuse, cancellation and separate disclosure variants. The temporary
loopback server is stopped after verification; it is not a persistent service.

Fault tests distinguish planned bounds from whole deadlines, cancel required work,
discard failed optional-model evidence, and prohibit publication after source
integrity faults. Partial and bounded canonical artifacts use actual core/final
verification with a deliberately injected optional native-worker fault. PDF failure
retains valid HTML/JSON. [Wheel inspection](results/release/wheel.json) verifies image
modules/registry/templates, optional extras and preserved text dependencies.

## Reproduction and scope

Use `PYTHONPATH=src` from the repository root and the pinned
[runtime lock](runtime-lock.txt). The measured host is a 16 GB macOS ARM64 CPU laptop.
Windows final-handle protection has source coverage but no native Windows execution
evidence. Existing M4–M6 capacity/corpus artifacts are reused, not regenerated.

```sh
PYTHONPATH=src .venv/bin/python -m validation.m7.data_download
PYTHONPATH=src .venv/bin/python -m validation.m7.model_download
PYTHONPATH=src .venv/bin/python -m validation.m7.benchmark
# Use a fresh output directory; artifact publication intentionally does not replace:
M7_RESULT_DIR=results/reproduction PYTHONPATH=src .venv/bin/python -m validation.m7.verify
M7_RESULT_DIR=results/reproduction PYTHONPATH=src .venv/bin/python -m validation.m7.selection_closure
M7_RESULT_DIR=results/reproduction PYTHONPATH=src .venv/bin/python -m validation.m7.pdf_qa
M7_RESULT_DIR=results/reproduction-search M7_FULL_SEARCH=1 M7_SIGNATURE_ONLY=1 \
  PYTHONPATH=src .venv/bin/python -m validation.m7.stress
M7_RESULT_DIR=results/reproduction PYTHONPATH=src .venv/bin/python -m validation.m7.offline_probe
PYTHONPATH=src .venv/bin/python -m pytest -q
```

Development downloads are explicit; production analysis never invokes them. PDF
rendering requires Poppler and leaves review pending until actual page inspection.
Final helper scripts that write artifact variants also require fresh destinations.
Full source membership and byte verification is per-file, not an atomic OS snapshot.
Topology, mask semantic correctness, arbitrary registration, object embeddings,
GPU/cloud/persistent indexes and universal leakage/performance predictions remain
deferred. No new external approval gate was introduced.
