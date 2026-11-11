# Architecture and independent-review scrutiny map

## Execution and trust boundaries

Supplied CG1 predictions, frozen CG2 applications or immutable CG3 selections enter
existing normalization/authority/admission. Typed decision-time context and frozen
CG4 membership augment the policy inputs. Only admitted S frames/statistics cross
the development-backend seam. Candidate generation calls the typed interpreter
and authoritative contribution/native adapters. Selection freezes executable
policies and a development record. S-only planning precedes immutable claims,
exposure checks and irreversible E reservation. Assessment then replays the exact
family and publishes one sealed result through Python, CLI, API, workspace,
browser and canonical artifacts.

There is no new ingestion/history store, fitting stage, worker service, durable
queue, user Python/SQL interpreter, public optimizer plugin API or catalog migration.

## Six delivered units and important files

All source paths below are relative to this archive's root.

| Unit | Authoritative implementation | Independent references to inspect |
|---|---|---|
| 1. Contracts/interpreter | [policy_contracts.py](../src/confidenceguard/policy_contracts.py), [policy_runtime.py](../src/confidenceguard/policy_runtime.py) | [interpreter tests](../tests/cg5/test_interpreter.py): DAG depth, three-valued precedence, task arithmetic, costs, ties and complete batches |
| 2. Policy evidence | [policy_store.py](../src/confidenceguard/policy_store.py), [policy_metrics.py](../src/confidenceguard/policy_metrics.py), [policies.py](../src/confidenceguard/policies.py) | [metric oracles](../tests/cg5/test_metric_oracles.py), [selection tests](../tests/cg5/test_selection.py): action partition, fixed planned populations, conditional denominators and economics |
| 3. Bounded optimization | [policy_problem.py](../src/confidenceguard/policy_problem.py), [policy_optimization.py](../src/confidenceguard/policy_optimization.py), [policy_solver.py](../src/confidenceguard/policy_solver.py) | [solver/resource tests](../tests/cg5/test_solver_resources.py): exhaustive references, incompatible encodings, warnings/scaling/integrality and incomplete standing |
| 4. Frozen independent assessment | [policy_assessment.py](../src/confidenceguard/policy_assessment.py), [evidence_use.py](../src/confidenceguard/evidence_use.py), [confirmation.py](../src/confidenceguard/confirmation.py) | [assessment tests](../tests/cg5/test_assessment.py), [scheduled looks](../tests/cg5/test_scheduled.py): finite intervals, allocation, required claims, exposure and continuity |
| 5. History/artifacts | [policy_history.py](../src/confidenceguard/policy_history.py), [policy_result.py](../src/confidenceguard/policy_result.py), [history_storage.py](../src/confidenceguard/history_storage.py), [workspace.py](../src/confidenceguard/workspace.py) | [history/interface tests](../tests/cg5/test_interfaces_history.py), [upstream tests](../tests/cg5/test_upstream.py): immutable reconstruction, restatement, packets, backup/deletion and projection |
| 6. Product interfaces | [policy_cli.py](../src/confidenceguard/policy_cli.py), [policy_web.py](../src/confidenceguard/policy_web.py), [policy_schema.py](../src/confidenceguard/policy_schema.py), [policy client](../src/confidenceguard/static/policy-client.js), [canonical template](../src/confidenceguard/templates/policy_sections.html) | [three-task parity](../tests/cg5/test_three_task_interfaces.py), [generated contracts](../src/confidenceguard/schemas/contracts.json), [OpenAPI](../src/confidenceguard/schemas/openapi.json), [examples](../src/confidenceguard/schemas/examples.json) |

## Critical invariants and questions

1. **Executable identity is independent of selection and assessment identity.**
   Inspect task/input semantics, referenced upstream runs, costs affecting actions,
   timing, fallbacks, ties and interpreter version. Paths/request IDs must not define
   policy behavior. Evaluation costs must not alter replay. Examine numeric JSON
   round-trips and protected imports as well as ordinary constructor cases.
2. **Exactly one action per planned event.** Issued, abstained, deferred and
   unavailable partition P. Upstream output/feature/region states remain separate.
   Unknown earlier rules must not silently fall through. Candidate failure cannot
   shrink P or the authoritative eligible outcome base L.
3. **Denominators are part of the estimand.** Coverage uses P; observed selective
   risk uses labeled issued events; opportunity recall includes non-emission as
   failure. Precision uses each policy's own positives on the common planned base.
   Undefined support is unavailable, not feasible. All-abstain has no zero-risk seal.
4. **Economic bases remain distinct.** Inspect historical observed-outcome loss,
   model-implied loss, known charges and missing-label envelopes. Every relevant
   evaluated action needs a price/bound. Deferral has no invented reviewer benefit.
   No silent probability repair, outcome imputation or mismatched-population sum.
5. **No E-dependent adaptation.** Trace `DevelopmentProblem` and inspect/preview
   admission: E membership/metrics must not leak into prototypes, cutpoints,
   objectives, nomination or preview. E byte mutation may change fingerprints,
   but must not change the policy through analytical access.
6. **Admissible optimization only.** Check grouped score ties/endpoints, ordered
   two-cut domains, fixed routing/residual cells and fixed-denominator objectives.
   Ratio constraints require valid cross-multiplication plus positive support.
   Variable-ratio objectives and arbitrary nonlinear encodings cannot inherit a
   linear certificate. Compare all admitted paths against the implemented matrix.
7. **Solver numerics do not relax business constraints.** The registered pair is
   SciPy 1.18.1 / HiGHS 1.12.0. Inspect Boolean `parallel=False`, fixed keys/warnings,
   scaling, aggregate budgets, one-hot decoding and authoritative replay. A valid
   incumbent is not necessarily a transferable global certificate. Encoded-model
   infeasibility must not become unjustified family infeasibility.
8. **Search/retention/frontier completeness are separate.** Enumeration must cover
   the declared family; bounded beam and epsilon trade-offs remain best-found or
   sampled. Dominance/detail limits must not erase baselines or change standing.
   `objective_vector` orients maximization values negatively for sorting; compare
   actual metric values/directions rather than interpreting sorting keys as losses.
9. **Complete-batch semantics are explicit.** Check event-membership digest/count,
   closure/cutoff, whole-batch role separation, nonnegative Decimal resources, whole
   tied-group prefixes and overflow outside the guarded resource. No streaming or
   ordinary event-IID guarantee follows from batch-coupled replay.
10. **All required claims freeze before E.** Inspect complete feasibility coverage,
    populations/observation rules, practical thresholds, true bounds, sampling and
    canonical alpha allocation. Refused/sparse claims keep their allocation.
    CP and Hoeffding components/transforms must match their actual contributions;
    conditional contrasts cannot borrow an intersected positive denominator.
11. **Exposure history cannot be reset.** Check CG2 F/S/C, CG4 D/S/exposed H,
    source/canonical aliases, imported sidecars, whole entities, before-label arm
    admission, failed/cancelled reservations, deletion/restore and scheduled looks.
    CG5 deliberately refuses the CG4 same-family recomputation exemption outside
    frozen scheduled looks. Missing history is unknown, never automatically fresh.
12. **Every interface consumes completed evidence.** Trace owned handles/revisions,
    CSRF, stale fingerprints, worker contention, cancellation/publication races,
    sanitized errors, grant detachment and packet dependencies. Reopening/export
    must not reanalyze. Shareable definitions/costs/private labels and related
    feasibility/dominance/nomination must be protected jointly where required.

## Integration trace

- CG1: [contracts](../src/confidenceguard/contracts.py),
  [sources](../src/confidenceguard/sources.py), [engine](../src/confidenceguard/engine.py)
  and [native analytics](../src/confidenceguard/analytics.py) retain source admission,
  authoritative outcomes and issued-only meanings. CG5 creates hypothetical actions.
- CG2: [fitted application](../src/confidenceguard/methods.py),
  [method sources](../src/confidenceguard/method_sources.py),
  [protected membership](../src/confidenceguard/membership.py) preserve frozen kernels,
  representations and label sealing; CG5 does not fit or auto-recalibrate.
- CG3: [history selection](../src/confidenceguard/history_selection.py),
  [history metrics](../src/confidenceguard/history_metrics.py) and the catalog preserve
  as-of authority, maturity, revisions and immutable snapshots. Frozen replay and
  historical reselection are distinct retrospective operations.
- CG4: [features](../src/confidenceguard/features.py),
  [frozen membership](../src/confidenceguard/investigation_membership.py),
  [history context](../src/confidenceguard/investigation_history.py) preserve corrected
  information cutoffs and member/nonmember/unavailable behavior. A confirmed failure
  region is not evidence of intervention benefit.
- Shared host: [compat](../src/confidenceguard/compat.py),
  [worker](../src/datatrust/worker.py), [scalable supervisor](../src/datatrust/scalable.py),
  [transport](../src/confidenceguard/transport.py) and [artifacts](../src/confidenceguard/artifacts.py)
  remain the execution/publication path. Existing supervision is sampled and can overshoot.

## Limits to preserve in review conclusions

Executable, empirically feasible, optimal within an identified search space and
independently supported are four distinct conclusions. Missing labels, predictive
proxy economics and action-dependent outcomes limit interpretation. General
unequal clusters, temporal/common shocks, unbounded means and unsupported
nonadditive inference are refused. Finite intervals may be wide/inconclusive;
zero observed failures cannot prove zero population failure probability. Historical
stability, conformal marginal coverage, cohort disparity analysis and frozen CG4
regions do not establish future, conditional, fairness or causal guarantees.
