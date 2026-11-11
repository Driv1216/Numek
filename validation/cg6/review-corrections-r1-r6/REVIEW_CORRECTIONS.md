# CG6 independent-review corrections R1–R6

This is the founder-authorized bounded correction pass following the independent
review in the preceding chat. The review verdict was **CORRECTIONS REQUIRED**.
It is not a new milestone, architecture change, research campaign, understanding
gate or founder acceptance.

Reviewed runtime: `4ecc25d08f89a5983939e789ac8d1d13a46216bdf3253d9e1fa17b6ec6f723eb`.
Corrected runtime: `aa72f09caa5bc5b174db5b4253add54a9fba8b3ecec3309c99f0beb0608fbf6a`.
Final executed gate results and their exact source/test hashes are in this
directory's receipts and `closure.json`; the current source map is
`source-identity.json`. Old `results/engineering-source.json`,
`results/engineering-closure.json`, wheels, workload and scientific receipts remain
unchanged historical evidence. `baseline.json` records the correction-start dirty
tree and hashes. Seven original context/engineering documents are copied under
`baseline-documents/` before their current-state updates.

## R1 — Direct auxiliary admission

**Root cause:** Application/assessment passed an artifact through operation options,
while preparation projected/validated only auxiliaries attached to ExecutionSpec.
Additional features could be imputed as missing; their clocks and prohibited-field
checks were absent.

**Correction:** `execution/services.py::service` validates and attaches the direct
artifact before execution argument/root admission, inspection, identity preparation
or reservation. An existing identical attachment is reused with its supplied byte
locations; a conflicting artifact identity refuses. `ExecutionSpec.__post_init__`
also validates attached auxiliary identifiers/roles/known inline outcomes and dated
inputs before preparation. Existing PreparedExecution projection, clock enforcement
and identical-byte outcome-alias checks now receive the complete artifact inputs.
No separate ingestion engine or new output computation was introduced.

The new extra-feature path also exposed a related R1 reuse omission: completed
bridge and outcome-restatement writers enumerated primary/context fields only.
`execution/bridge.py` and `execution/restatement.py` now carry admitted auxiliary
source fields and clocks into their existing completed-evidence writers, excluding
internally generated prediction/vector feature names. Frozen outputs are reused;
models are not executed again. This was a bounded R1 follow-up, not a new feature.

**Evidence:** Direct application and assessment retain an additional `z` feature;
ID/entity/role/outcome inputs refuse before preparation; late, missing and invalid
availability refuse auxiliary outputs while retaining valid primary outputs; valid
availability works. Missing cutoffs and byte-identical outcome aliases refuse.
The owned API test now fits on `z`, then inspects/applies that saved handle using
the original primary execution declaration and checks retained `z` inputs.
The additional lineage regression verifies bridge fields/clocks and model-free
restatement with unchanged channels.

## R2 — Frozen ensemble semantics

**Root cause:** RobustnessAssessmentSpec compared base/auxiliary/method identities
but omitted ensemble definitions.

**Correction:** `execution/ensembles.py::ensemble_semantics` canonicalizes ordered
members, fixed complete-common-support arithmetic-mean combination and effective
DecisionSpec defaults. `RobustnessAssessmentSpec.__post_init__` includes that
definition in compatibility. `service` repeats assessment admission before staging,
identity preparation or E reservation, including direct service consumers.

**Evidence:** The reviewer's `[model,b]` → `[model,c]` replacement refuses, as do
member reordering and decision changes. Omitted versus explicitly serialized
default decisions remain equivalent. A service-level negative control proves that
changed membership never reaches evidence reservation.

## R3 — Imported CG2 provenance

**Root cause:** CG6 rejected only `contradicted` imported membership, allowing
missing/unavailable evidence to pass its formal-claim admission.

**Correction:** `execution/provenance.py::assessment_reasons` uses CG2's unchanged
`assessment_membership_passed` helper for every imported method and upstream chain.
Known overlap retains refusal; missing/unavailable required checks also refuse the
affected claim. The existing robustness family allocation and descriptive
application machinery are unchanged. No accepted CG2 implementation was modified.

**Evidence:** Unit controls match CG2 eligibility for missing, unavailable,
contradicted and passed states, including parent chains. Real CG2 identity artifacts
are fitted on F/S/C-only development records and imported into CG6. Three independent
cases establish missing refusal, passed assessment and positive-overlap refusal.
An unaffected base claim remains supported, both claims keep alpha .025, and
descriptive derived outputs remain available. No exposure history is cleared to
manufacture freshness.

## R4 — Output-bound gradient objectives

**Root cause:** Numeric/tensor and image attacks differentiated raw tensors while
normal inference applied named output sources, indices and class/postprocessing
semantics. Unrelated raw heads could change the gradient.

**Correction:** `robustness/gradient_objectives.py` projects the actual bound point
or probability tensor without detaching its graph. It applies output source,
indices, activation, complete class reordering and binary probability complements,
with aligned shape/finite/probability checks. Numeric/tensor `attacks.search` and
`image_attacks.search_image` use this shared objective and finite input-gradient
check. Missing, detached, malformed, nonfinite or unsupported paths explicitly
refuse with `gradient_unavailable`; logits/hard outputs are not substituted for
an absent differentiable analytical probability channel.

The registered increasing-point directional surrogate for absolute regression
output change remains unchanged. Squared error/log probability are smooth
monotone loss/target surrogates. The final normal candidate replay, feasibility,
best-found accounting and success definition remain authoritative and unchanged.
No failed finite search establishes robustness.

**Evidence:** Equivalent direct versus indexed/named/class-reordered/binary-sigmoid/
already-probability classifiers agree for misclassification and targeted search.
Indexed/named multi-output regression ignores an opposing unrelated head, including
loss-increase search. Each test recomputes the final objective/success from normal
replay. A real decoded-image preprocessing/8-bit candidate path checks reordered
outputs, exact pixel radius and final replay. Existing supervised Torch/tensor/image
attack oracles and real MPS modalities belong to the affected integration gate.

## R5 — Numeric missing sentinels

**Root cause:** Numeric preprocessing estimation included finite missing sentinels
although application treated them as missing.

**Correction:** `auxiliary/fitting.py::preprocessing` excludes None and declared
missing values before estimating F-only imputation/mean/scale. F/S/C/E separation,
learner objectives and frozen application transforms remain unchanged.

**Evidence:** `["1","3","-999"]` with `-999` missing produces fill/mean 2 and
standard deviation 1. The frozen transform yields `[-1,1,0]`. All-sentinel F support
retains `auxiliary_features` refusal rather than inventing fitted measurements.

## R6 — Deterministic CUDA prerequisites

**Root cause:** Default deterministic configuration omitted cuBLAS's required
workspace startup setting.

**Correction:** `execution/devices.py::configure_torch` requires the operator's
startup `CUBLAS_WORKSPACE_CONFIG` to be `:4096:8` or `:16:8` for deterministic CUDA,
before its seeding/device/allocation calls. It records the accepted setting and
does not mutate the environment after possible initialization. Missing/invalid
settings refuse clearly with `device_profile`; CPU fallback does not silently
disable determinism. CPU/MPS behavior and the explicit nondeterministic option
are unchanged. The guide documents the startup requirement.

**Evidence:** Hardware-independent controls accept both settings and reject absent,
empty and invalid settings before native configuration calls. An existing mocked
CUDA configuration test now supplies its explicit startup prerequisite. A worker
failure control proves that this refusal is not converted into a CPU restart.
These controls do not execute or qualify NVIDIA hardware.

## Verification and evidence standing

Verification follows `agents/skills/verify/skills.md`.

- `before.log`: 21 failed / 4 passed on the reviewed runtime, reproducing every
  finding before correction. The regression file was subsequently expanded.
- `focused.log`: first corrected controls, 25 passed in 12.48 s.
- `expanded-focused.log`: 50 passed in 35.91 s, including real imported-CG2 cases.
  These intermediate diagnostics are not relabeled as final-source gate runs.
- `integration-py313.json` and `.log`: the scoped primary integration gate, covering all
  CG6 checks plus CG2 integrity/protocol and selected CG5 upstream/three-task
  interfaces: **135 passed, 10 NVIDIA hardware skips in 355.80 s**. Real MPS
  allocator/cancellation, objectives, fitting/application and modalities passed.
  Its exact command, source/test hashes, skips and result are retained.
- `compatibility-py312.json` and `.log`: the bounded correction/API compatibility
  subset on the existing separate Python 3.12 environment: **53 passed in 82.88 s**.
- `lineage-before.log`: two failures established the additional-field bridge and
  restatement omission after the first gates. Only the two reuse writers and one
  new test file changed afterward. The 135-test and 53-test evidence is reused for
  every unchanged area; it is not relabeled as exact final-source execution.
- `lineage-py313.json` / `lineage-py312.json`: exact final-source focused follow-ups
  for those two writers, new field/clock regressions and relevant existing
  integration/lifecycle/API/auxiliary paths. Their receipts identify the exact sets.
  The Python 3.13 follow-up passed **17 tests in 86.83 s**.
  The Python 3.12 follow-up passed **9 tests in 56.32 s**.
- `final-package-receipt.json`: isolated final wheel build and byte comparison for
  all runtime/assets, including the new gradient helper. It is not an installed-
  wheel/base-environment rerun. Existing environments and old wheels are untouched.
  The earlier `package-receipt.json` and wheel remain intermediate evidence.

The full 655-test campaign, seven-profile CPU positive controls, six-design cluster
simulation, 21 performance profiles and browser/PDF campaigns were not rerun.
Unchanged native reducers, fitting objectives, role allocation, scientific envelopes,
cluster mathematics, catalog/lifecycle and disclosure/rendering retain their scoped
historical evidence, supplemented by the affected integration checks.

The numeric positive-control envelopes contain no finite missing sentinels, so R5
does not change their preprocessing values. R1 does not change their already shared
primary/auxiliary inputs. R3 changes claim admission, not their descriptive losses.
The cluster kernel and dispatch are unchanged. No cross-device predictive-quality
campaign is required or inferred.

Original workload measurements remain observations of their identified source and
host, not timings rerun on corrected code. In particular, attack profiles exercised
the now-corrected gradient path; no corrected-source throughput assertion is made
from those old timings. Their resource observations, larger-workload exclusions,
slower MPS finding and unified-memory qualifications remain historical evidence.
Current affected functional/device checks replace assumptions about correctness;
they do not create a new performance benchmark.

Existing actual browser and 55-page representative PDF evidence is reused for
unchanged authoring/rendering surfaces. The affected API test covers saved auxiliary
handle admission. No new browser/PDF campaign or report regeneration was required.

Old results, claims, protocol bytes and receipts remain immutable. Contract versions
and catalog v2 are unchanged; corrected reuse/admission is stricter. Old qualified
claims are not reissued. Model and auxiliary mathematical artifact identities are
not rewritten by these fixes; actual new runtime/source evidence is separately bound.

## Closure boundary

R1–R6 implementation and bounded engineering verification are recorded by
`closure.json`. Any failed diagnostic remains retained. Source-preservation checks
must find no missing baseline files, no changed DataTrust source and no changed
original CG6 result receipts. CUDA runtime execution, parity, allocation, cancellation
and performance remain `not_run_hardware_unavailable` until compatible NVIDIA
hardware exists. That pending hardware qualification is nonblocking.

No understanding gate or founder acceptance is claimed. Stop after this correction
pass; further action requires founder instruction.
