# M6 implementation evidence

The repository Verification skill governed coherent implementation units,
focused foundational checks and comprehensive closure. The original repository
suite passed **385 tests**; the subsequently added browser cancellation regression
passed independently. [Closure ledger](results/closure.json) records inputs,
source hashes, new evidence and historical reuse. These are engineering checks,
not independent product validation or universal reliability guarantees.

The subsequent independent-review correction pass passed **400 tests in 33.51s**.
See [correction details](REVIEW_CORRECTIONS.md) and the separate
[correction ledger](results/review_corrections/closure.json). Original reports,
measurements and ledgers below remain historical evidence. The new report projection
uses unchanged completed analytics; it is not a rerun of those datasets.

## Recorded evidence

- [Public-data checks](results/verification.json): SMS 5,574 records; UD English
  2,001 and Hindi 1,659 sentences; SQuAD v2 11,873 examples; 128 source-ordered
  OpenAssistant conversation paths; SciFact 5,183 documents, 100 queries,
  72 judgments and 100 extractive chunks; four authored images with sixteen
  pairing associations. Counts and applicable annotation/relationship checks use
  independent prepared-data oracles. Dataset transformations and licenses are
  in [raw](data/manifest.json) and [prepared](data/prepared_manifest.json) manifests.
- [Candidate calibration](results/calibration.json): fixed banding grid and
  bucket caps, exact all-pairs oracle, threshold-boundary/multilingual/code/long/
  template controls, pre-cap/post-cap recall and charged work. Shipping profile
  is 20 × 7, cap 1,024; ≥99% recall concerns the recorded ordinary strata only.
  Forced saturation found about 3.06% of oracle positives under its imposed cap.
- [100 MiB](results/capacity_100mib_final.json) and
  [1 GiB](results/capacity_1gib_final.json) narrow JSONL workloads: 14,953 and
  153,074 full-population records, respectively. The 1 GiB run took 207.33 seconds,
  sampled peak RSS 2.13 GiB, workspace 7.56 GiB, with no measured spill. Expensive
  investigations selected at most 128 units. An initial failed run is retained
  separately; earlier runs are historical measurements, not final certificates.
- [Stress measurements](results/stress.json): 200,000 supplied tokens, 10,000
  asset references to 100 physical assets, and actual CPU model processing of
  sixteen long documents. Generated temporary sources were deleted after each
  run; their locators correctly become unavailable.
- [Presentation](results/presentation.json) and [page QA](results/pdf_qa.json):
  default and explicitly disclosed Unicode/invalidity/model reports plus Hindi,
  QA and retrieval reports. Every page of the five PDFs was rendered and visually
  inspected: 53 pages, 10–12 per report. Analytical topics remain intact;
  continuing tables and whitespace are retained rather than cutting evidence.
- [Browser screenshot](results/browser-completed.jpg): guided CSV mapping,
  configuration retention, confirmation/reconfirmation, supervised execution,
  completed result and downloads. Live witness resolution rejected a changed
  source signature; reconfirmation and rerun produced an exact local witness.
  Current Flask integration checks additionally cover PDF/JSON delivery, private
  session isolation, CSRF, excerpt caches, source changes and cancellation.
- [Runtime lock](runtime-lock.txt) and [publisher identity](results/model_publisher_identity.json)
  pin the validated macOS ARM64/Python 3.11 CPU environment and actual E5 files.
  Lingua and E5 tests run with network sockets disabled. The lock is a validated
  local environment, not a cross-platform capacity promise.

## Reproduction

Run from the repository root with `PYTHONPATH=src`. Raw/prepared corpus bytes,
model files and protected private manifests are excluded from Git. Development
downloads are explicit; production analysis never downloads.

```sh
PYTHONPATH=src .venv/bin/python -m validation.m6.download
PYTHONPATH=src .venv/bin/python -m validation.m6.prepare
PYTHONPATH=src .venv/bin/python -m validation.m6.model_download
PYTHONPATH=src .venv/bin/python -m validation.m6.verify
PYTHONPATH=src .venv/bin/python -m validation.m6.stress
PYTHONPATH=src .venv/bin/python -m validation.m6.presentation
PYTHONPATH=src .venv/bin/python -m pytest -q
```

`calibrate` reproduces the bounded fixed-grid engineering calibration; it writes
the shipping profile only under its documented acceptance rule. `benchmark`
accepts `--mib` and `--out`, requiring disk/RSS headroom. `refresh_reports` reuses
completed compatible analysis to render a new template variant without overwriting
earlier artifacts. `pdf_qa` requires Poppler (its local path is explicit in the
script), renders every page, and leaves visual review pending until actual inspection.

Historical M1–M5 reports and evidence were preserved. The repository's original
classification and dry-run archive verifiers passed during closure; broader
unaffected milestone evidence is reused rather than regenerated.
