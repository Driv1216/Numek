# CG6 engineering verification

## Founder-accepted completion and evidence boundary — 2026-11-08

The founder has confirmed CG6 is done and accepted; CG1–CG6 are complete within
their approved scopes. Earlier pending-review, pending-understanding and
pending-founder-acceptance statements are historical. The
[final implementation explainer](CG6_FINAL_IMPLEMENTATION_EXPLAINER.md) is complete
and describes the accepted 230-file runtime identity
`aa72f09caa5bc5b174db5b4253add54a9fba8b3ecec3309c99f0beb0608fbf6a`.

Explainer/documentation checks cover structure, source references, example syntax
and unchanged runtime identity; they do not rerun implementation tests,
simulations, performance, browser or PDF campaigns. Acceptance does not expand
scientific guarantees or hardware qualification. Actual NVIDIA qualification
remains pending compatible hardware and nonblocking. The sealed source/closure
receipts and original artifacts are unchanged; their documentation hashes bind
earlier snapshots, not the subsequently updated living documents.

## R1–R6 correction evidence supersedes original readiness

The independent review returned **CORRECTIONS REQUIRED**. The authorized targeted
pass and corrected-source verification are recorded in
[review-corrections-r1-r6/REVIEW_CORRECTIONS.md](review-corrections-r1-r6/REVIEW_CORRECTIONS.md).
Its source identity and executed/reused/not-rerun evidence are separate from
`results/engineering-source.json` and `results/engineering-closure.json`, which
remain unchanged original-source receipts. The original context/engineering
documents are preserved in the correction directory before these current updates.
The sections below describe the original engineering closure, not a new execution
of those gates on corrected source. No new scientific/performance/browser/PDF
campaign is implied. NVIDIA runtime qualification remains separately pending.

The correction pass passed 135 tests with 10 explicit CUDA hardware skips in its
scoped Python 3.13 integration gate, including real MPS, and 53 tests in a Python
3.12 correction/API subset. A subsequent R1 extra-field reuse correction changed
only the bridge/restatement writers; exact final-source follow-ups passed 17 and
9 tests on Python 3.13 and 3.12 respectively. The corrected wheel matches all 230
runtime/asset files. Counts overlap and are not summed. Commands, exact source
maps, intermediate failures and final closure are retained in the correction
directory; no old gate is relabeled as an exact corrected-source run.

Engineering verification is complete within the approved scope and named-host
envelopes. Independent review/corrections are complete and CG6 is founder-accepted
as recorded above.

The approved scope and completion boundary are documented in
[the implementation guide](../../docs/CG6_CONFIDENCEGUARD.md). NVIDIA hardware
availability is not a completion dependency. Actual CUDA runtime qualification is
pending; controlled substitutes and CPU checks are contract-level evidence only.

## Executed and reusable evidence

| Gate | Result | Receipt/log |
|---|---|---|
| Comprehensive CG1-CG6 and shared host/API/web gate | 655 passed, 11 skipped; 884.25 seconds | `closure-tests.log` |
| Final affected CG6, CG3 lifecycle, CG4/CG5 interfaces | 68 passed, 10 CUDA hardware skips; 217.52 seconds | `final-affected-checks.log` |
| Restored model-free restatement and deletion closure, paired CG2 | 5 passed | `storage-paired-correction.log` |
| Retained robustness contributions and JSON-authored protocol | 1 passed | `retained-protocol-correction.log` |
| Complete custom-predictor batch replay/partial-batch refusal | 2 passed | `coupled-batch-correction.log` |
| Separate strict CG6 schema examples/negative controls | 16 checks passed | `results/schema-qualification.json` |
| CPU auxiliary positive controls | All seven profiles passed locked five-seed criterion | `results/positive-controls/receipt.json` |
| Bounded-cluster qualification | Six designs x 2,000 trials passed | `results/cluster-qualification.json` |

Counts in focused checks overlap the broad gate and must not be added as unique
test counts. Ten broad-gate skips explicitly identify unavailable CUDA hardware;
the remaining skip is the optional in-runtime JSON Schema validator. Data-only
schema validation uses the separate validator runtime and is not device evidence.

The broad gate used Python 3.13.17 with real MPS exposed outside the desktop
sandbox. It covered objective/gradient/optimizer parity, finite fitting, model
round-trips, CPU producer references and MPS modalities, bounded allocator failure
and cancellation, selected attacks, roles, frozen upstream integration, immutable
codec lifecycle, owned interfaces and disclosure. NVIDIA cases remained collected.

Final corrections made during the gate and its affected follow-ups are tracked
explicitly: complete-batch custom execution, JSON factory canonicalization,
restatement descendant deletion, private contribution permissions, codec packet
reopening, auxiliary device/fitting provenance and browser presentation/navigation.
The source receipts distinguish executed, reused and pending evidence;
preliminary mixed-source runs are not relabeled as an exact final frozen-tree gate.

`results/reused-evidence.json` explains reuse of the expensive CPU scientific
controls. The original cluster-module hash is reproduced exactly by undoing only
the later metric-bound dispatch line; the qualified cluster kernel is unchanged.
No additional simulation campaign or cross-device predictive-quality campaign is
required. Same-weight device verification does not require matching trained weights
or fixed predictive improvement.

## Final compatibility, product and packaging checks

- `final-provenance-device-checks.log`: 9 passed, 1 CUDA hardware skip; 106.26 s.
- `compatibility-py312.log`: 57 passed, 19 explained skips; 504.19 s. This separate
  Python 3.12 CPU gate ran inside the desktop sandbox; eight MPS skips do not qualify
  Python 3.12 MPS. Actual primary MPS evidence is Python 3.13 outside that sandbox.
- `scale-floor-selection-check.log`: one focused high-floor control passed. Frozen
  S nomination uses the deployed scale floor; no extra quality campaign was run.
- `schema-closure-check.log`: 16 strict positive/negative checks passed on final
  schemas using the separate existing validator environment.
- `wheel-closure-base-check.log`: final installed wheel executes the eight-row
  constant pipeline with Torch/sklearn/skops/ORT/safetensors absent and reopens three
  actual historical CG5 artifacts without model/solver dependencies. The exact 126
  ConfidenceGuard source/asset hashes match the wheel (`results/wheel-closure-source.json`).
- `results/browser/workflow-verification.json`: actual guided browser workflows,
  real MPS qualification, fitting, cancellation, protocol refusal, restatement,
  restart/reopen and exports. Final export progress/completion is visible in CG6;
  its cancel control also resolves shared export jobs. The synthetic server stopped.
- `results/representative-final-reports.json`: eight representative PDFs, 55 pages,
  every page visually inspected; four browser-export pages additionally inspected.

## Named-host performance

`CG6-MAC-01.json` identifies the actual M4 Mac (10 CPU/10 GPU cores, 16 GiB unified
memory), OS/builds, power and storage observations. One bounded calibration preceded
the frozen resource/workload admission in `performance_protocol.json`. All 21
admitted CPU/MPS profiles passed their elapsed/RSS envelopes. Per-profile hashes,
sizes and observations are in `results/performance-summary.json`. Unified-memory
RSS and MPS allocation overlap; no universal GPU speedup or capacity is claimed.

Original 100k/eight-scenario tabular and million-row streaming references remain
explicitly not admitted, based on pre-run disk/control-packet estimates. Named
25k/100k profiles are distinct. No failed workload was shrunk and relabeled.

An early source-change interruption remains diagnostic in
`results/performance-interruption.json`. Before the first risk fitting measurement,
its benchmark labels were corrected to include both classes within each role;
sizes, learners, thresholds and budgets were unchanged. Thirteen passing profiles
were retained and only eight missing profiles executed in fresh processes. The
restart interrupted one uncompleted quantile measurement, then reran that same
profile. `results/performance-resumption.json` records the exact boundary.

The first MPS fitting fixture correctly refused its CPU-only constant primary
under an explicit MPS request before fitting. Only the three uncompleted MPS
profiles used the corrected equivalent frozen Torch primary. This fixture change
does not alter product source, sizes, learners, resource limits or thresholds;
`results/performance-mps-primary-fixture-correction.json` retains the disposition.
CPU/MPS fitting comparisons include the different primary adapters and finite
early stopping; they are end-to-end observations, not isolated kernel speedups.

## Final source and evidence standing

`results/engineering-source.json` records final runtime/assets. The broad gate is
reused for unaffected foundations; later affected tests, actual browser checks,
every-page PDF review and final wheel/schema checks cover corrections. This is not
represented as a single exact-source run of all 655 tests. The final browser-only
export wiring change does not invalidate numerical performance receipts.

`results/engineering-closure.json` inventories executed/reused receipts and source
hashes. `results/source-preservation.json` confirms no missing baseline files and
unchanged DataTrust source versus the captured dirty baseline. Historical CG1-CG5
evidence was not reset or relabeled. No unchanged expensive suite was rerun solely
because documentation or presentation changed.

All required engineering gates are closed. Actual CUDA inference, parity, training,
allocator/cancellation and performance remain `not_run_hardware_unavailable` until
compatible NVIDIA hardware exists. Its implementation/contracts are complete; this
pending hardware qualification is nonblocking and is never inferred from mocks.
