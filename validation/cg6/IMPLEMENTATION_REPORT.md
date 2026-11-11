# CG6 implementation report

## Founder acceptance and current documentation — 2026-11-08

The founder has confirmed CG6 is done and accepted. CG1–CG6 are complete within
their approved scopes; earlier pending-review, pending-understanding and
pending-founder-acceptance language is superseded. The
[final implementation explainer](CG6_FINAL_IMPLEMENTATION_EXPLAINER.md) is complete,
covering all 16 requested areas, six diagrams, complete source navigation,
algorithms/statistics, execution scenarios, R1–R6, glossary and 15 technical Q&As.

The accepted runtime/assets identity is
`aa72f09caa5bc5b174db5b4253add54a9fba8b3ecec3309c99f0beb0608fbf6a`
across 230 files. Current evidence standing is in
[the completion record](IMPLEMENTATION_STATUS.md) and the sealed correction
receipts. This living-document update changes no implementation, tests or
historical artifacts and does not reseal earlier documentation hashes. CPU/MPS
qualification retains its recorded scope; actual NVIDIA qualification remains
pending compatible hardware and nonblocking. Scientific limits are unchanged.

## Independent-review corrections

The independent review identified R1–R6 and required corrections. The authorized
bounded pass fixes direct auxiliary admission, frozen ensemble compatibility,
imported CG2 membership eligibility, bound gradient objectives, numeric missing
sentinels and deterministic CUDA startup admission. Implementation and scoped
engineering verification are complete, including extra-field bridge/restatement
reuse and Python 3.12 compatibility. See
[the correction report](review-corrections-r1-r6/REVIEW_CORRECTIONS.md) for exact
changes, current source identity, executed checks and historical-evidence reuse.
The original source/closure/wheel/performance receipts remain unchanged. All
original gate counts and measurements below refer to that historical source;
they are not relabeled as corrected-source runs. Founder acceptance is now
recorded above; NVIDIA runtime qualification remains separately pending.

CG6 implementation and engineering verification are complete within the approved
scope and named-host envelopes. CPU and MPS are qualified on CG6-MAC-01; CUDA
implementation and contract checks are complete, with actual NVIDIA runtime
qualification pending compatible hardware. Independent review and R1–R6 are
complete, and the founder has accepted CG6 as recorded above.

## Result and completion boundary

CG6 adds complete trusted predictor execution, executable/fitted auxiliaries and a
finite robustness laboratory within the existing ConfidenceGuard architecture.
CPU, Apple Silicon MPS and NVIDIA CUDA are first-class implementation targets.
Real CPU/MPS evidence uses the recorded CG6-MAC-01 Mac. CUDA implementation and
contract checks are distinct from actual NVIDIA runtime qualification, which is
pending compatible hardware and does not block unrelated acceptance.

The implementation does not claim CUDA execution, parity, allocation or throughput
from controlled substitutes, CPU results or Apple GPU results. The bounded CUDA
hardware suite remains collected with explicit unavailable-hardware reasons.

## What changed

| Subsystem/seam | Delivered behavior |
|---|---|
| `execution/` | Strict versioned predictor/application contracts, reviewed artifact loading, complete preprocessing/output channels, keyed sources/tensors/media, devices, bounded batching, coherent fallback, parity, output/failure ledgers, supplied ensembles and protected evidence |
| `auxiliary/` | F-only preprocessing/parameters, disjoint S selection/checkpoints, constant/logistic/histogram/MLP profiles, bounded independent MLP ensembles, frozen scale/quantile/risk artifacts, diagnostics and application |
| `robustness/` | Registered transformations/constraints, separate validity/outcome standing, scenarios, finite/gradient attacks, named sensitivities, common candidates/comparisons, frozen protocols, root/entity/batch-aware inference and policy worlds |
| CG1/CG2 | Unchanged normalization/native reducers and existing calibration/conformal machinery; completed predictions bridge to normalized conformal/CQR and explicitly authored consumers |
| CG4/CG5 | Frozen region transitions and exact compatible policy replay; complete isolated capacity worlds, preserved units/classes/ties/score semantics and honest refusal |
| Storage | Existing catalog v2 plus bounded `opaque_artifact_bytes_v1` objects/descriptors; copied model/media bytes, atomic publication, dependencies, backup/restore/recovery/deletion and model-free reopening/export |
| Product | Shared facade/Python/CLI/owned API jobs, guided browser controls, cancellation, saved-handle reuse, exact-output paging, canonical disclosure-driven JSON/HTML/SVG/PDF and outcome-only restatement |

No catalog-v3 migration is required: v2 already provides the relational invariants,
immutable object inventory, encoding metadata, dependencies and publication/lifecycle
machinery CG6 needs. CG6 payload/codec versions remain independent of SQLite schema
version. Old catalog-v1 workspaces retain the established backed-up v1-to-v2 path.

No remote inference, uploaded source/import execution, automatic downloads,
primary-model training, encoder fine-tuning, AutoML, distributed execution,
persistent serving, CG7 monitoring, general causal conclusions or universal
certification was added.

## Scientific and hardware evidence are separate

The locked CPU positive controls passed for all seven selected method profiles,
in five of five seeds each, exceeding the frozen four-seed / 5% median criterion.
These are scoped integration controls on designed learnable envelopes. They do
not promise improvement on every dataset, hardware profile or application.

Device checks instead exercise same-weight forward outputs, objectives, gradients,
a controlled optimizer step, finite fitting/checkpoints, artifact loading,
selection/accounting, bounded native OOM and cancellation. MPS is not required to
reproduce CPU training trajectories, fitted weights or fixed predictive gains.

The narrow cluster-ratio method retains its written Hoeffding/union-bound derivation
and six frozen designs x 2,000 trials. The qualified kernel is unchanged; only
calling metric-bound dispatch expanded. `results/reused-evidence.json` records the
source-bound rationale for reusing these expensive scientific receipts.

An executable auxiliary may be unhelpful. Infinite proper loss, inconclusive
assessment, failed finite search, unknown transformed truth and incompatible
frozen-policy inputs remain legitimate, explicitly represented findings.

## Verification actually executed

| Gate | Actual result |
|---|---|
| Comprehensive CG1-CG6/shared host/API/web gate | 655 passed, 11 skipped; 884.25 s |
| Affected CG6 and lifecycle/interface correction gate | 68 passed, 10 CUDA hardware skips; 217.52 s |
| Final provenance, CG2 integration and real MPS fitted-artifact round-trip | 9 passed, 1 CUDA skip; 106.26 s |
| Separate Python 3.12 CPU compatibility and historical interfaces | 57 passed, 19 explicitly explained skips; 504.19 s |
| Base-only installed wheel | Constant execution works with optional ML packages absent; three historical CG5 artifacts reopen without models/solver dependencies |
| Separate schema validator | 16 strict positive/negative CG6 checks passed on final schemas |
| Final high-floor scale selection control | 1 passed; S selection matches deployed frozen scale floor |
| Final wheel/source equivalence | All 126 ConfidenceGuard runtime/asset files match the final wheel |
| Representative canonical PDF set | Every page visually reviewed: eight final reports, 55 pages; four additional browser-export pages reviewed |
| Real browser | Guided execution, MPS qualification, auxiliary fit/assessment, scenario authoring, protocol freeze/assessment refusal, cancellation, later-outcome restatement, navigation, restart/reopen and HTML/PDF downloads exercised |

Focused counts overlap broad counts and are not summed as distinct tests. Ten broad
skips are unavailable CUDA hardware; the remaining skip is the optional in-runtime
JSON Schema validator, covered separately. The 3.12 gate ran in the desktop sandbox:
its eight MPS skips mean that profile has CPU compatibility evidence, not MPS
qualification. Primary real MPS qualification is Python 3.13.17 outside the sandbox.

Follow-ups are recorded in individual logs. The passing broad gate is reused for
unaffected foundations; later changes are not falsely presented as an exact
single-source broad run. No unchanged expensive scientific campaign is repeated.

## Material corrections found during implementation/verification

- Kept auxiliary risk distinct from the primary native score and preserved primary
  issuance/decisions through application and CG5 consumption.
- Kept derived execution views non-executable; retained predictor handles refer
  only to actual admitted base predictors.
- Rebound retained binaries after restore and restated outcomes without loading
  models. Deletion closure now expands descendants' owned binary/packet bundles
  to a stable fixed point.
- Made robustness contribution files private before retention; normalized JSON
  protocol defaults before content hashing; enabled large protocol packet reopening.
- Replayed complete declared custom-predictor batches for qualification and refused
  partial/cross-role batches instead of silently executing singleton inputs.
- Bound final authoritative outcomes to exact final attack variants; pre-search
  labels cannot label changed candidates. Unknown truth remains unknown.
- Separated hardware/scientific status; added complete objective/device evidence,
  source/fitting provenance and whole-tie risk ranking/selection diagnostics.
- Corrected browser navigation, advanced-spec reuse, retained evidence IDs,
  measurement detail, and empty report tables. Scoped CG6 pagination/footer/unit
  presentation changes preserve older report behavior.

## Performance scope

`CG6-MAC-01.json` records the actual M4 Mac: 10 CPU/10 GPU cores, 16 GiB unified
memory, OS/runtime, disk and power observations. The host remained on AC power
when observed during the first final workload. RSS and MPS allocation are not
added as exact distinct physical usage on unified memory.

The one bounded calibration and `performance_protocol.json` freeze admitted
workloads, sizes and resource/deadline criteria. Original 100k/eight-scenario
and million-row streaming references remain explicitly not admitted, with pre-run
storage/control-plane identity-packet reasons. Separately named 25k/100k profiles
are not relabeled as those originals. No fixed GPU speedup is required.

All 21 admitted profiles passed their predeclared elapsed/RSS envelopes:

| Profile | Elapsed | Peak worker RSS |
|---|---:|---:|
| tabular-25k | 621.01 s | 2.68 GiB |
| streaming-100k | 227.55 s | 2.51 GiB |
| device-cpu | 176.87 s | 2.68 GiB |
| device-mps | 178.77 s | 2.53 GiB |
| text-cpu | 4.50 s | 0.42 GiB |
| text-mps | 4.30 s | 0.46 GiB |
| image-cpu | 42.69 s | 0.71 GiB |
| image-mps | 43.47 s | 0.48 GiB |
| attacks-cpu | 13.38 s | 0.38 GiB |
| attacks-mps | 61.06 s | 0.40 GiB |
| capacity | 157.42 s | 1.21 GiB |
| scale-histogram | 92.57 s | 1.61 GiB |
| scale-mlp | 91.18 s | 1.44 GiB |
| quantiles-histogram | 92.77 s | 1.64 GiB |
| quantiles-mlp | 91.71 s | 1.58 GiB |
| failure_risk-logistic | 91.12 s | 1.64 GiB |
| failure_risk-histogram | 91.14 s | 1.70 GiB |
| failure_risk-mlp | 91.09 s | 1.67 GiB |
| scale-mlp-mps | 96.25 s | 1.65 GiB |
| quantiles-mlp-mps | 95.95 s | 1.71 GiB |
| failure_risk-mlp-mps | 92.18 s | 1.76 GiB |

Same-host end-to-end throughput comparisons:

| Workload | CPU source rows/items per second | MPS source rows/items per second | CPU time / MPS time |
|---|---:|---:|---:|
| fixed network | 565.40 | 559.37 | 0.989 |
| text | 444.50 | 465.00 | 1.046 |
| images | 23.42 | 23.01 | 0.982 |
| attacks | 14.95 | 3.28 | 0.219 |
| scale fitting | 1096.69 | 1039.01 | 0.947 |
| quantile fitting | 1090.43 | 1042.18 | 0.956 |
| risk fitting | 1097.79 | 1084.87 | 0.988 |

These are complete-operation observations, including source processing and
transfers. Fitting includes finite checkpoint selection/early stopping; it
is not a comparison of equal optimizer-step counts or isolated GPU kernels.
CPU fitting uses a constant primary; MPS uses its equivalent frozen Torch
primary. The end-to-end comparison includes that adapter difference.

The detailed profiles, exact source/receipt hashes and resource observations are
in `results/performance-summary.json`. These measurements qualify the recorded
host, workloads and runtime; they imply no universal GPU speedup or CUDA timing.
Auxiliary profiles contain 100,000 source rows across fixed F/S/C/E roles:
25,000 F rows fit parameters and 25,000 S rows support disjoint selection;
C/E rows are excluded from fitting and selection. These are not claims of
100,000 training rows or universal training capacity.

A risk-fixture label/role correlation was corrected before its first fitting
measurement so both classes occur within F/S. Sizes, learner defaults, limits
and thresholds were unchanged. Thirteen completed profiles were retained; the
remaining eight ran in fresh processes. One interrupted quantile measurement
had no receipt and was restarted. `results/performance-resumption.json` records
this boundary. The only runtime source change at that restart was browser
export progress/cancel wiring; numerical source was unchanged.

The first MPS scale benchmark then correctly refused a CPU-only constant
primary under an explicit MPS request before fitting began. The fixture was
corrected to an equivalent frozen Torch primary, with the same point or
classification function. Only the three uncompleted MPS fitting profiles
ran after this correction. Product source, workload sizes, learner defaults,
budgets and thresholds were unchanged. The original refusal remains in
`performance-risk-complete-mps-fixture-refusal.log`; its disposition is in
`results/performance-mps-primary-fixture-correction.json`.

## Source preservation and handoff

The pre-edit modified/untracked baseline contains 387 files. The current audit
finds no missing baseline files and byte-identical DataTrust source. Changed shared
seams, new subsystem files, schemas, dependencies and docs are recorded separately;
the pre-existing dirty CG1-CG5 tree was not reset or attributed wholesale to CG6.

See `VERIFICATION.md`, the source maps and per-gate receipts for executed/reused/
pending evidence. The public implementation guide is
`docs/CG6_CONFIDENCEGUARD.md`. Original engineering completion and source identity
remain in `results/engineering-closure.json` and `results/engineering-source.json`.
Corrected-source closure is recorded separately under `review-corrections-r1-r6/`;
the founder acceptance and completed explainer are recorded above. No further
CG6 gate is pending in the current project state. Actual NVIDIA qualification is
tracked separately. The synthetic browser server
was stopped after verification; no product service is left running.
