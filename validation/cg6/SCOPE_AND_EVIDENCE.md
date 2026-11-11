# CG6 scope and evidence map

The approved plan in the chat controls scope. The founder confirmed CG6 is done
and accepted on 2026-11-08; CG1–CG6 are complete within their approved scopes.
This map links implemented scope to evidence; acceptance comes from the founder's
decision, not this map. Current corrected-source standing is in
[the completion record](IMPLEMENTATION_STATUS.md),
[verification record](VERIFICATION.md) and
[R1–R6 record](review-corrections-r1-r6/REVIEW_CORRECTIONS.md).
The [final implementation explainer](CG6_FINAL_IMPLEMENTATION_EXPLAINER.md)
provides the complete teaching walkthrough. NVIDIA runtime qualification remains
pending hardware and nonblocking; scientific limits and historical evidence
retain their original scope.

| Approved area | Implementation | Principal evidence |
|---|---|---|
| Complete classical, ONNX, Torch and trusted-host prediction | `execution/contracts.py`, `adapters.py`, `store.py`, `services.py`, `legacy.py` | `test_execution.py`, `test_devices.py`, `test_output_states.py`, `test_role_inputs.py`, producer references and complete-pipeline checks |
| CPU/MPS/CUDA implementation, bounded devices and coherent failure handling | `execution/devices.py`, `batch_admission.py`, adapters and supervision | `test_cuda_contracts.py`, `test_device_objectives.py`, `test_device_failures.py`, `test_complete_predictor_batches.py`; actual NVIDIA checks explicitly pending |
| Fitted scale, quantiles, risk and independent MLP ensembles | `auxiliary/contracts.py`, `fitting.py`, `composite.py`, `services.py`, `diagnostics.py` | `test_auxiliary.py`, `test_ensembles.py`, `test_diagnostics.py`, locked CPU positive controls; real MPS fitting and artifact round-trip |
| Frozen CG2 calibration/conformal integration | `execution/bridge.py`, `frozen.py`; existing CG2 services | `test_integration.py`, `test_output_states.py`, final provenance/device gate |
| Registered transformations, constraints, outcome relations and modalities | `robustness/transformations.py`, `contracts.py`, `services.py` | `test_robustness.py`, `test_transform_oracles.py`, `test_modalities.py`; identity, impossible-domain and uncertain-outcome controls |
| Sensitivity, finite/gradient attacks and matched comparisons | `robustness/sensitivity.py`, `attacks.py`, `image_attacks.py`, services | Analytic continuous/discrete attack oracles, common-candidate/transfer and charged-work checks; CPU/MPS measured attack profiles |
| Frozen independent assessment and finite root/entity inference | `robustness/inference.py`; existing exposure/reservation kernels | `test_assessment.py`, six locked cluster designs x 2,000 trials, refusal/allocation/contamination controls |
| Frozen regions and complete policy worlds | `robustness/regions.py`, `policy.py`; existing CG4/CG5 services | `test_policy_stress.py`, `test_risk_consumer.py`, upstream interface gates and complete-capacity benchmark |
| Immutable binary retention within catalog v2 | `execution/artifact_bytes.py`, `storage.py`, `restatement.py`; existing catalog lifecycle | CG3/CG6 commit, recovery, backup/restore, relocation and transitive-deletion checks; restart/reopen/export without model execution |
| Python, CLI, owned API and guided browser | Shared facades; `execution/cli.py`, `web.py`, `static/execution-*` | `test_interfaces.py`, affected host/API/web gate, actual guided browser stories and cancellation |
| Canonical protected/shareable reporting | `execution/result.py`, shared disclosure and report templates | `results/representative-final-reports.json`: eight representative reports/55 reviewed pages and four browser-export pages |
| Named hardware and realistic resource envelopes | `CG6-MAC-01.json`, `performance_protocol.json`, `performance.py` | Source-bound per-profile receipts; predeclared unadmitted larger profiles remain explicit capacity limits |
| Compatibility, packaging and historical evidence | Python 3.13 primary; separate 3.12 and base-only wheel environments | `compatibility-py312.log`, `wheel-closure-base-check.log`, strict schema checks and original dirty-tree preservation audit |
| Corrected admission, ensemble semantics, provenance, bound gradients, missing sentinels and CUDA startup | `execution/services.py`, `contracts.py`, `ensembles.py`, `provenance.py`, `devices.py`, `bridge.py`, `restatement.py`; `auxiliary/fitting.py`; `robustness/contracts.py`, `gradient_objectives.py`, attacks | `review-corrections-r1-r6/`: 135/53-test affected gates and exact final-source 17/9-test lineage follow-ups; 230-file wheel comparison; counts overlap |

Paths in the implementation column are relative to `src/confidenceguard/`; test
filenames are under `tests/cg6/`. Detailed logs and receipts are under this directory.

The seven complete stories in the plan are represented by: classical pipeline and
matched corruption checks; real CPU/MPS and pending-CUDA workflow; fitted scale/
quantile to CG2 assessment and stress; explicit risk to CG5 consumption; bounded
offline modalities; attacks followed by complete policy worlds; and retained
restart/reopen/export/restatement/lifecycle. Unknown truth, missing provenance,
inconclusive inference and unsuccessful finite search remain honest findings.

No catalog-v3 migration, NVIDIA procurement, new research campaign, remote inference,
primary training, AutoML, distributed execution or persistent serving is required.
Founder acceptance and this documentation update do not initiate CG7 work or
regenerate the original source-bound receipts.
