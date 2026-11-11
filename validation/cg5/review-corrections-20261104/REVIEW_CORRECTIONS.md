# CG5 targeted independent-review corrections

Started 2026-11-04; completion verification 2026-11-05.
CG5 is **not founder-accepted**. This record covers the authorized correction pass,
not an educational implementation report, deployment, CG6 or review ZIP.

## Reviewed source and preservation

The starting runtime was the independently reviewed modified/untracked tree, not
committed HEAD. Its 190-file runtime map digest was
`48dda6c6562cd30710e0ee03d21cc9774cc6122b17c55db31054cf9517497099`.
HEAD remains `ba3cf1606152e64ebe7b64778f5202c49ab30f64` on `main`.
`baseline.json` records 367 starting source, test and documentation files and the
starting working-tree status. Existing modified/untracked CG4 and DataTrust work
was retained. The final manifest records the exact changed files and preservation
checks; it does not compare this delivery only with committed HEAD.

## Finding resolutions

| Finding | Underlying correction | Principal functions |
|---|---|---|
| R01 | A MILP parameter can appear only at its own residual-cell entry. Reachable option graphs cannot enter any variable cell or contain capacity coupling. Every objective solve compares the decoded encoded objective and solver objective with authoritative replay, using recorded 1e-9 absolute/relative equivalence tolerances independent of nomination tolerance. Mismatch prevents certificate transfer. | `policy_optimization._fixed_cells`, `milp_family`, `milp_standing` |
| R02 | Input identity v2 binds upstream decision rules, thresholds, tie/state semantics, supplied prediction mapping, prediction clock declaration and probability-admission tolerance. Task compatibility is checked at store and development-problem binding. Frozen imports must retain bound upstream semantics. | `policy_store.PolicyStore.policy_identity`, `bind_policy`; `policy_problem.DevelopmentProblem.bind_policy`; frozen artifact constructors |
| R03 | Assessment replacement inputs preserve roles, mappings, seed/unit/partitions, batch declarations, run aliases, event/entity key bindings, cohorts/context, feature as-of and outcome as-of semantics. Historical scheduled looks retain their separately authorized outcome-only exception. | `policy_assessment._protocol_input_signature`, `_input` |
| R04 | One shared matcher requires mandatory direct claims for required study constraints. Freeze, family import validation and final support use the same invariant; support is recomputed from actual matched claim states. | `policy_contracts.required_constraint_claims`, `required_constraint_coverage`; `freeze_policy_family`, `_assess_worker`, `FrozenPolicyFamily.__post_init__` |
| R05 | Weighted/lexicographic selection ordering is shared. Separately bounded analytical nomination state retains every potentially eligible tolerance tie independently of display detail. The final nominee is always restored to the retained result. Exhausting nomination-state memory stops search with explicit incomplete standing. | `policy_optimization.selection_key`, `within_tolerance`, `choose`, `search`, `bounded_family` |
| R06 | Negating cost reverses missing-label cost extrema for utility. Explicit regression bounds describe final utility contributions and are not negated twice. Floating and canonical-decimal evaluation agree. | `policy_metrics.decimal_cost`, `_economic` |
| R07 | Historical windows intersect the original cohort/region restriction before the authoritative reducer. Evidence binds both restrictions. | `policy_history._policy_history_worker` |
| R08 | Completed claims carry full local metric/comparator definitions. Public claims retain controlled semantics, aliases, requirements and support only when interpretable; protected scope/economic/output-target claims lose their conclusion and interval together. Measurement evidence basis survives projection. Canonical tables display the actual question, interval, support and allocation. | `policy_assessment._assess_worker`; `policy_result.PolicyResult.to_dict`; `templates/policy_sections.html`; CG5-scoped note in `artifacts.view` |
| R09 | Optimize, replay and historical replay always bind execution to the internally reserved fingerprint, even without an earlier caller inspection. Supplied vector/key dependencies join the fingerprint before reservation and cannot replace their captured identities during materialization. Assessment already enforced its internally inspected fingerprint. | `policies.optimize_policies`, `replay_policy`; `policy_history.analyze_policy_history`, `_policy_history_worker`; `policy_store.PolicyStore.__init__`, `_regions` |

The previous CG5 input identity v1 remains readable as historical evidence.
Reapplication under the corrected v2 semantics refuses an incompatible binding;
it does not silently rewrite an old policy or claim the original digest still
describes corrected semantics. Raw `PolicySpec` authoring remains available.
Unknown development membership still prevents independent provenance standing.

## Approved-plan reconciliation

### Historical constraint stress

`PolicyApplicationSpec.constraints` is an optional, typed, bounded declaration.
Replay and history retain it through the common application-study adapter.
Historical results include a per-window constraint ledger with the original scope,
operator/bound, support floor, support, slack and feasible/violated/undefined state.
They also retain worst-window descriptive evidence and window supports.
Outcome-only restatement preserves the policy and constraint definitions.
The CLI/API use the same constructor. Completed API evidence has paginated
`constraint-ledger` and `worst-windows` sections. Browser protected-policy import
preserves supplied constraints instead of deleting them.

### Hybrid routing and leaf optimization

`PolicyFamilySpec.routing_parameters` explicitly identifies finite outer choices.
Backend `hybrid` (or `auto` with those declarations) enumerates routes and applies
the registered independent-cell MILP to each admitted inner model. Branches share
state, candidate, solver, memory and time limits. Every branch retains its routing
digest, solver evidence and standing. Complete outer/inner coverage is required
for complete hybrid standing. Limits or sampled Pareto schedules cannot inherit
a complete certificate.

Outer choices must produce an admitted ordered residual-cell inner model. This
does not add a generic graph/nonlinear optimizer. Other typed compositions use
finite enumeration or bounded search, or receive an explicit incompatibility.

### MILP ties

After literal objective priorities, bounded one-hot enumeration examines the
declared tolerance band. Each candidate is replayed. Selection uses structural
complexity then canonical policy digest. A final encoded infeasibility proof
establishes exhaustion of that tied space. Incomplete refinement is reported as
`solver_optimal_objectives_tie_incomplete` when objective standing survives; it
cannot be presented as a fully completed nomination. Refinement consumes the same
solver/node/time/matrix/candidate budgets as primary optimization.

### Capability and admission guidance

Inspection exposes effective limits and S-only domain/encoding guidance. MILP
preflight calls the same structural, denominator, matrix and numerical-scaling
admission as execution, without solving. Finite enumeration validates its typed
bindings. Hybrid guidance reports bounded outer coverage. Bounded composition is
explicitly partial guidance with per-candidate validation still required. Missing
registered solver profiles are unavailable, not silently supported.

Solver accounting distinguishes peak per-model variables/rows/nonzeros from total
matrix entries processed over multiple calls. Numerical qualification remains
SciPy 1.18.1 / bundled HiGHS 1.12.0 only.

## Regression coverage

`tests/cg5/test_review_corrections.py` contains the new invariant regressions:

- Cross-cell subgraphs refuse MILP for classification and regression while their
  typed executable definitions remain legal for nonseparable replay/search.
- Objective disagreement prevents certificate transfer.
- Weighted optimum and tolerance nomination survive a one-candidate display pool.
- Binary decision thresholds, multiclass tie rules and regression prediction
  mappings change identity; an old frozen binding refuses reapplication.
- Frozen roles cannot be replaced; an imported coverage flag cannot bypass
  mandatory constraint matching; stripped frozen input identity refuses import.
- Classification/regression missing-label utility envelopes have ordered endpoints.
- Historical cohort denominators, all three constraint states, immutable reopening
  and outcome-only restatement retain their definitions.
- Internal reservation binding detects prediction-source, vector and key-file
  mutation; the historical analytical worker checks its reserved fingerprint.
- Public claims remain interpretable; protected claims/intervals withhold jointly;
  public imports cannot recover private output.
- Complete hybrid/tie results match exhaustive small references; incomplete
  outer/tie coverage is qualified; guidance does not solve or adapt to E mutation.

Historical cohort tests use CG1's canonical `category_0` / `category_1` scope
identifiers. Raw display category values are not substituted for those identifiers;
the correction preserves the accepted cohort-normalization contract.

## Verification evidence and reuse

Final results are recorded in `verification.json`, `final-source.json`,
`final-affected-tests.log`, `schema-cg1-cg4.json`, `schema-cg5.json`,
`reports-20261105/reports.json` and `pdf-visual-qa.json`.

The final affected command includes the complete CG1–CG5 tests plus the existing
DataTrust host/API/web groups, using importlib mode and the retained Python 3.13
environment. No dependency replacement or installation was performed.

Four new synthetic assessment/history local/shareable JSON/HTML/PDF sets exercise
the changed projection paths. Their text/privacy checks passed. All 25 pages were
rendered and inspected in contact sheets; the changed assessment and historical
constraint tables were also inspected at full size. Existing protected reports
retain lengthy JSON detail; this correction does not redesign their pagination.

Earlier engineering gates and measured workloads remain historical evidence.
Passing a retained gate does not invalidate the independent counterexamples.
Unchanged ingestion, CG1–CG4 numerical kernels, DataTrust analytics, catalog/packet
codecs, artifact publication and worker supervision reuse their prior evidence,
supplemented by the affected gate. Old optimizer timings are not reclassified as
new corrected-runtime capacity measurements. No new broad null/power campaign,
platform qualification or CG4 research promotion is claimed.

## Remaining limitations

- Search and tie refinement remain bounded; exhausted limits produce explicit
  incomplete standing or an atomic resource refusal.
- Hybrid certification concerns admitted finite encoded models and complete
  recorded outer coverage, within solver tolerances.
- Bound input-identity v1 policies need explicit new binding before v2 replay.
- Private scoped/economic claims can be absent from public output; their original
  family allocation is retained, not redistributed.
- Population support remains conditional on declared observation, independence,
  true bounds and exposure assumptions. No causal/future/deployment guarantee.
- Deferred CG4 cluster/BCa/ranking/temporal research remains deferred.

## Final affected-scope gate — 2026-11-05

| Check | Result |
|---|---|
| Complete CG1–CG5 suites and DataTrust host/API/web groups | **576 passed, 1 skipped**, 571.61 seconds |
| New regression module | 20 test functions, **27 executed cases**, included in that gate |
| Strict generated schema reference checks | **107 passed**: CG1–CG4 63, CG5 44 |
| Original R04 optional-constraint counterexample | Mandatory feasibility correctly **not established** |
| New local/shareable assessment and history artifacts | Four JSON/HTML/PDF sets; text/privacy checks passed; all **25 PDF pages** visually inspected |
| CLI/owned API immutable reopening | Ledger and worst-window evidence match; shareable withholding and session ownership pass; no analytical rerun |
| JavaScript syntax and tracked whitespace check | Passed |

The single skip is CG2's optional JSON Schema validator in the analytical Python
environment. Separate schema qualification ran in the retained schema environment;
it is not an untested schema claim. The corrected runtime stayed unchanged through
the final suite and artifact checks. No dependency installation was performed.

The corrected runtime contains 190 files. Its SHA-256 is the hash of the UTF-8
canonical JSON path-to-file-SHA-256 map (sorted keys, separators `,` and `:`):

`cecde695823502f5744268d7bb5c62edfe223eb07c2cd819de2fe2e601ed1ef2`

### Exact changed runtime paths

All paths below are relative to the repository root; the complete hashes are in
`final-source.json`. They are changes against the captured review baseline.

| File | Changed functions or definitions and purpose |
|---|---|
| `src/confidenceguard/policy_contracts.py` | `PolicyFamilySpec.__post_init__`, `PolicyApplicationSpec.__post_init__`, `FrozenPolicy.__post_init__`, `FrozenPolicyFamily.__post_init__`, `required_constraint_claims`, `required_constraint_coverage`: typed routing/constraints, bound imports and mandatory claim matching |
| `src/confidenceguard/policy_store.py` | `PolicyStore.__init__`, `policy_identity`, `bind_policy`, `_regions`: behavioral input identity and reserved representation snapshots |
| `src/confidenceguard/policy_problem.py` | `DevelopmentProblem.bind_policy`: task compatibility at backend binding |
| `src/confidenceguard/policy_assessment.py` | `freeze_policy_family`, `_protocol_input_signature`, `_assess_worker`: frozen population rules, shared required-claim coverage, complete claim semantics and recomputed support |
| `src/confidenceguard/policies.py` | `_inspect_worker`, `optimize_policies`, `_application_study`, `_replay_worker`, `replay_policy`: S-only guidance, internal fingerprint binding and application constraints |
| `src/confidenceguard/policy_optimization.py` | `selection_key`, `within_tolerance`, `choose`, `_fixed_cells`, `milp_family`, `milp_standing`, `select_backend`, `hybrid_family`, `family_guidance`, `bounded_family`, `search`: separability, objective verification, bounded hybrid/ties, consistent nomination and independent display retention |
| `src/confidenceguard/policy_solver.py` | `solve`: common numerical preflight and peak/aggregate matrix accounting |
| `src/confidenceguard/policy_metrics.py` | `decimal_cost`, `_economic`: ordered missing-label utility envelopes |
| `src/confidenceguard/policy_history.py` | `_policy_history_worker`, `analyze_policy_history`: scope intersections, reserved fingerprint, per-window constraint ledger and worst-window evidence |
| `src/confidenceguard/policy_result.py` | `PolicyResult.to_dict`: interpretable public claims with joint private withholding |
| `src/confidenceguard/policy_web.py` | `register.evidence`: paginated completed constraint and worst-window sections |
| `src/confidenceguard/policy_schema.py` | `extend`, `capabilities`: generated hybrid/constraint declarations and honest admission guidance |
| `src/confidenceguard/artifacts.py` | `view`: evidence-basis annotation confined to CG5 |
| `src/confidenceguard/templates/policy_sections.html` | Assessment question/support/allocation columns and historical constraint/worst-window rendering |
| `src/confidenceguard/static/policy-client.js` | Protected policy import handler: preserve typed application constraints |
| `src/confidenceguard/schemas/contracts.json` | Regenerated strict contract definitions |
| `src/confidenceguard/schemas/openapi.json` | Regenerated strict API schemas |

The new regression module is `tests/cg5/test_review_corrections.py`. The existing
`validation/cg5/qualify_schemas.py` adds positive and negative checks for the new
typed declarations. `qualify_reports.py` and `qualify_reopening.py` beside this
record exercise corrected artifacts and immutable interface projection. Status,
architecture and CG5 contract documents were reconciled; original verification
receipts remain explicitly historical.

**Ready for focused independent re-review.** No identified correction remains
open in this pass. This is engineering readiness, not founder acceptance. No CG6,
ZIP or educational implementation report was started.
