# NUMEK CG4 — Independent technical review

Review completed: 29 October 2026, Asia/Kolkata. Scope: the delivered dirty working tree, final installed review wheel, and technical-review ZIP. This is a read-only review; no fixes, commits, pushes, cleanup, or changes to repository evidence were made.

## 1. Executive verdict

**FAIL for founder acceptance of the current delivery.** Two independently reproduced high-severity defects violate the delivered temporal and evidence-reuse safeguards and permit `finite_sample` confirmed findings through affected paths. The finite interval arithmetic itself is not the demonstrated problem.

The implementation has substantial engineering and scientific evidence. Its narrow finite procedures are defensible under their assumptions, general inadequately qualified approximate confirmation is refused, and the five stated synthetic recovery panels genuinely meet their locked criteria. The wheel and review ZIP faithfully contain the reviewed implementation, including the defects. A bounded correction pass is justified; a new architecture or deferred general statistical research is not.

Findings: **0 critical, 2 high, 1 medium, 1 low, and 1 documentation-only.** Existing tests passing does not resolve these findings: the reviewer reproduced the defects outside the existing tests while 111 selected repository tests passed.

## 2. Authoritative baseline and coverage

The [founder-approved closure revision](/Users/drivyaanshyadav/Desktop/Numek/validation/cg4/CLOSURE_SCOPE_REVISION.md), [supported methods](/Users/drivyaanshyadav/Desktop/Numek/validation/cg4/SUPPORTED_METHODS.md), and [qualification matrix](/Users/drivyaanshyadav/Desktop/Numek/validation/cg4/QUALIFICATION_MATRIX.md) govern acceptance. General BCa/cluster/ranking research, unfinished objective/history/geometry campaigns, and landmark promotion are not reinstated as delivery requirements.

Baseline documents inspected included the permanent master context, architecture/current-state CG4 and compatibility sections, CG4 technical documentation, concise and historical implementation findings, implementation status, review quickstart, protocols, entity-arm methodology, null bridge, and the repository Verification skill. Historical milestone prose was used for integration context, not treated as new qualification.

Direct code review covered investigation preparation/orchestration, feature contracts/normalization/retention, supplied and offline representations, structured/CatBoost/geometric/landmark proposals, membership validation/application, reconciliation/fidelity/stability, freezing, confirmation and numerical admission, evidence-use identities/ledger, historical reconstruction/replay, storage/publication/backup/restore/deletion, result/disclosure/reporting, CLI, local transport and served JavaScript. Shared CG1–CG3/DataTrust integration changes were traced through reducers, source projection, capture, worker supervision, runtime admission and Unicode compatibility. This was a risk-directed audit, not a claim that every legacy line or every possible population was exhaustively validated.

**Independently executed:**

- 68 focused tests covering null isolation, closure policy, method admission, entity arms, frozen observation semantics, membership/native boundaries, disclosure, deletion and review packaging; all passed.
- 43 focused integration tests covering CLI/API, history, work admission, reconciliation, representations, outcome observation, live exposure, supervisor cleanup and runtime compatibility; all passed.
- Adversarial temporal, exposure-replay and state-predicate probes described below. The high-severity paths used public investigation/freezing/confirmation services and actual synthetic retained workspaces; no production functions were monkeypatched.
- All 200 retained current-selector recovery trials: hashes, profile consistency, completion, recovery arithmetic and criteria. Independent beta-quantile reconstruction of 427 native Bernoulli contrast intervals and their finding states.
- All 2,200 retained reduced/default full-pipeline null trials: hashes and actual assessment-based false-confirmation/noncoverage counts. Independent AST comparison of the five transferred finite functions against their original capsule.
- Archive CRC, every payload hash, archive entry safety and file-set coverage, repository correspondence, final wheel/source/installed-package parity, and final source-capsule identity.
- Actual served browser, from the installed final wheel, reopening an unchanged historical AP assessment row inside an explicitly labeled synthetic UI fixture. The wrapper is reviewer-created; it is not represented as an original complete assessment bundle. Canonical report template behavior was inspected separately.
- Representative retained rendered PDF pages, including both assessment pages and discovery beginning/end/overlap pages, were visually inspected. The original claim that every final page was inspected is retained implementation evidence, not newly repeated reviewer work.

**Existing evidence only:** the full 150,000 finite simulation campaign; 30,000 entity-arm null and 2,000 power trials; remaining partial-null simulations beyond inspected summaries/harness; large capacity workloads; optional encoder inference; broad legacy regression; Python 3.12/3.14 runs; and the full installed product/backup reproduction receipt. These were inspected in source/results where relevant, not rerun as new campaigns. Linux/Windows execution and a new dependency installation were not performed.

The git baseline was `ba3cf1606152e64ebe7b64778f5202c49ab30f64`, **not** the delivered source identity: 41 tracked files were modified and much of CG4 was untracked. Full untracked status was captured. The product boundary is the runtime inventory and source capsule, not `git HEAD` or only `git diff`.

## 3. Severity-ranked confirmed findings

### H1 — Historical features lose their declared information cutoff

**Severity: High; acceptance blocker.**

**Locations:** `Prepared.load_features`, [investigation.py:202](/Users/drivyaanshyadav/Desktop/Numek/src/confidenceguard/investigation.py:202); `capture_typed`/`cells_from_row`, [investigation_history.py:85](/Users/drivyaanshyadav/Desktop/Numek/src/confidenceguard/investigation_history.py:85) and [investigation_history.py:128](/Users/drivyaanshyadav/Desktop/Numek/src/confidenceguard/investigation_history.py:128); `HistoricalPrepared.load_features`, [investigation_history.py:349](/Users/drivyaanshyadav/Desktop/Numek/src/confidenceguard/investigation_history.py:349), especially line 375.

**Expected:** a frozen `FeatureViewSpec.information_cutoff` has the same availability meaning for live and retained evidence. If the required cutoff was not retained, reconstruction must preserve an unavailable/refused state rather than substitute a later clock.

**Actual/reproduction:** 720 synthetic rows declared cutoff `2026-01-01T00:00:00Z`, feature availability `2026-01-01T12:00:00Z`, and prediction time `2026-01-02T00:00:00Z`. Live preparation marked both typed fields unavailable for all 720 rows and discovery returned zero candidates. After ordinary v2 ingestion and historical reconstruction, both fields became observed for all rows. The historical path produced ten candidates and a `confirmed`, `finite_sample` assessment with H outcomes disclosed. The recorded run had H support 205, split into 103 members and 102 comparison records.

**Root cause:** the live loader parses the declared cutoff column. Typed retention preserves the field clocks and view declaration but not a normalized per-owner information-cutoff value. The historical loader always passes `owner_record['prediction_tick']` to `apply_availability`, ignoring `view.information_cutoff`.

**Impact:** values acquired after the declared information boundary can define supposedly available-at-decision gates and pass formal confirmation on retained data. The reverse clock ordering can also incorrectly exclude usable features. A `finite_sample` interval cannot repair a changed membership/time interpretation. The probe establishes temporal-contract failure; it is not itself a Monte Carlo demonstration of increased type-I error.

**Correction:** retain/reconstruct the actual declared cutoff per owner and use it consistently. Refuse or report unavailable when an older retained record cannot establish that cutoff. Preserve existing result bytes and distinguish corrected interpretation where memberships change. Add live/retained parity and confirmation-negative tests for cutoffs earlier/later than prediction time and absent/invalid retained cutoffs.

**Evidence:** `temporal_probe.py`, `temporal-probe.json`, and `temporal-probe-confirmation.json` in the reviewer evidence directory. The script creates only synthetic files outside the repository.

### H2 — Replay exposure loses source aliases and can be reset by a new namespace

**Severity: High; acceptance blocker.**

**Locations:** `_population`, [investigation_replay.py:16](/Users/drivyaanshyadav/Desktop/Numek/src/confidenceguard/investigation_replay.py:16), especially lines 20–22; `replay_investigation`, [investigation_replay.py:106](/Users/drivyaanshyadav/Desktop/Numek/src/confidenceguard/investigation_replay.py:106), lines 110–112. Compare the shared identity policy in [evidence_use.py:19](/Users/drivyaanshyadav/Desktop/Numek/src/confidenceguard/evidence_use.py:19) and `population_identifiers` at line 45.

**Expected:** locally observed outcome disclosure remains observable when the same original file/keys are investigated under a different namespace. A scoped declaration of no exposure must not override an exposure the product itself can identify. This is a promised local safeguard, not a demand for global tracking of unknown external copies.

**Actual/reproduction:** learn an origin gate on separate synthetic identities, ingest a disjoint 720-row target population, and replay the origin gate on the target's retained history. Replay discloses target outcome-dependent effect 1.0 over all 720 planned records. Then investigate the **same unchanged target CSV** under a renamed namespace, freeze claims and inspect/confirm. Inspection has no admissibility reasons; confirmation returns `confirmed`, `finite_sample`, with H outcomes disclosed.

The same failure was independently reproduced with durable evidence-use tracking enabled and the same workspace explicitly supplied to later discovery/confirmation. The ledger contains `outcome_disclosure`, `discovery_selection`, and `confirmation` records. The same-namespace negative control refused with `known_session_exposure`, showing that the gap specifically concerns identity transfer rather than an absent reservation.

**Root cause:** replay builds only namespace-dependent event/entity digests. Other paths use `population_identifiers`, which also records retained original source path/inode and original key aliases. Replay therefore discards available alias evidence before reserving disclosure. Both the session and durable ledgers faithfully store an insufficient identity set.

**Impact:** known prior H use can be presented as an independently admissible confirmation after namespace changes, including through ordinary public Python services. This violates the implementation's local evidence-integrity promise. The experiment deliberately supplied an incorrect unexposed declaration to verify that known local use wins; it did not require changing outcomes, paths, model artifacts or production code.

**Correction:** route replay/restatement population identity through the shared source-alias policy before disclosure; preserve H-only selection semantics. Examine other outcome-disclosure callers for the same omission. For affected older replay records, recover alias evidence where possible or explicitly retain an incomplete-continuity boundary; do not infer freshness from missing aliases. Add end-to-end tests for both tracking modes, renamed namespaces, original live files and historical reconstruction.

**Evidence:** `replay_exposure_probe.py`, `replay_exposure_durable_probe.py`, `replay-exposure-probe.json` (same-namespace control), `replay-exposure-probe-renamed.json`, and `replay-exposure-probe-durable.json`.

### M1 — Browser omits the record-specific standing warning for historical approximate findings

**Severity: Medium; product/report consistency.**

**Locations:** `renderAssessment`, [investigation-client.js:121](/Users/drivyaanshyadav/Desktop/Numek/src/confidenceguard/static/investigation-client.js:121), especially lines 127–137; compare [investigation_sections.html:29](/Users/drivyaanshyadav/Desktop/Numek/src/confidenceguard/templates/investigation_sections.html:29) and [CG4_CONFIDENCEGUARD.md:26](/Users/drivyaanshyadav/Desktop/Numek/docs/CG4_CONFIDENCEGUARD.md:26).

**Expected:** reopening a historical approximate confirmed assessment preserves its original state and adds an explicit current-standing warning beside the result, consistent with canonical HTML/PDF.

**Actual/reproduction:** an unchanged retained AP row rendered in the actual final-wheel browser as `confirmed`, effect `0.6940678721385692`, interval `[0.67242, 0.71406]`, delta `.2`, and strength `approximate`. The result section had no historical/current-qualification warning. The canonical template explicitly adds one when strength is approximate.

**Impact/limits:** the browser can be read as endorsing an unsupported historical confirmation. It does show approximate strength, and the separate freeze-controls section says current ranking confirmation is unavailable; those mitigate severity. This is not a demonstrated bypass of current method admission, and the historical numeric bytes should not be rewritten.

**Root cause/correction:** the JS renderer lacks the conditional warning already present in the template. Add that display qualification without changing the stored state; test local/shareable reopening and parity with canonical reports. Reviewer screenshot: `historical-browser.png`; fixture provenance is in `historical-manifest.json`.

### L1 — State-only columns are silently omitted from structured discovery

**Severity: Low; bounded discovery correctness.**

**Location:** `propose`, [discovery_rules.py:29](/Users/drivyaanshyadav/Desktop/Numek/src/confidenceguard/discovery_rules.py:29), early return at line 30 before state predicates are added at line 42.

**Expected:** supported missing/invalid predicates are considered even when a field has no observed values, or the excluded vocabulary is explicitly reported.

**Actual/reproduction:** one integer field has 60 missing and 60 invalid values, with loss zero versus one. At default minimum support 30, automatic search returns zero atoms, zero candidates and `search_complete=True`. The existing exact membership implementation accepts the `state=invalid` gate, applies to all 120 records and selects the 60 invalid records exactly.

**Root cause:** an empty observed-value list skips the whole field, including valid state predicates. **Impact:** a simple missingness/invalidity failure mechanism can be missed; completeness refers to a silently reduced vocabulary. This does not invalidate finite inference or imply every heuristic must recover every population.

**Correction:** generate state predicates independently of observed-value numeric/category vocabulary and keep unavailable/not-retained semantics intact. One focused regression fixture is sufficient. Evidence: `state_probe.py` and `state-probe.json`.

### D1 — Current documentation contradicts delivered method and closure standing

**Classification: Documentation-only; low severity.**

**Locations:** [CG4_CONFIDENCEGUARD.md:3](/Users/drivyaanshyadav/Desktop/Numek/docs/CG4_CONFIDENCEGUARD.md:3) says implementation/qualification is in progress and the scope is the entire milestone; [CG4_CONFIDENCEGUARD.md:552](/Users/drivyaanshyadav/Desktop/Numek/docs/CG4_CONFIDENCEGUARD.md:552) says AUC/AP percentile confirmation is registered. These contradict the approved revision and the same document's lines 19–35. [CURRENT_STATE.md:451](/Users/drivyaanshyadav/Desktop/Numek/docs/CURRENT_STATE.md:451) also describes CG4 as under authorized implementation despite its final-candidate opening.

**Exact implementation behavior:** `_method_refusal` in [confirmation.py:48](/Users/drivyaanshyadav/Desktop/Numek/src/confidenceguard/confirmation.py:48) rejects nonranking percentile requests and returns `general_ranking_percentile_confirmation_not_qualified` for AUC/AP. Inspection attaches that refusal before assessment; the assessment skips H metric evaluation for affected claims. BCa is separately refused at line 333. Focused admission tests passed. **The ranking contradiction is documentation-only, not a current registration bug.**

**Impact/correction:** readers can select incompatible methods or mistake a deliberate scope deferral for an unfinished mandatory campaign. Align present-tense status and registration claims with the approved closure revision, retaining explicitly historical records as history. Do not edit historical experiment bytes or claim founder acceptance.

## 4. Statistical assessment and the null-evidence bridge

The defensible shipping procedures are the registered Bernoulli Clopper–Pearson component intervals, registered confusion-cell F1 composition, fixed-bin bounded calibration residual composition, and Hoeffding bounded means/transforms. Their validity requires the declared IID eligible population, genuinely predeclared bounds/thresholds, frozen membership/observation semantics and complete family allocation. Pointwise contribution bounds for RMSE concern squared residuals. Conditional rates such as precision and recall retain their own denominators.

The independent entity-arm design is mathematically narrower than arbitrary cluster inference: IID complete entities, at most one potential record per entity per frozen comparison arm **before** outcome/class filtering, with within-entity cross-arm dependence allowed. The structural check counts potential observations and refuses duplicates rather than opportunistically selecting one observed row. Bonferroni needs valid marginal component bounds, not independent arms. Declared complete extraction and entity independence cannot be established by local code.

The implementation retains all actual frozen hypotheses in the family allocation, including refused/unavailable claims. It freezes thresholds, objectives, observation policy, membership coverage and numerical protocol; source rebinding cannot silently revise these. `confirmed`, `unreproduced`, `inconclusive`, `statistically_inadmissible` and exploratory states are meaningfully distinct. Work/memory/tail admission, all-valid replicates, numerical retry restrictions and predeclared restatement allocation are safeguards, not coverage theorems. Default historical restatements remain descriptive.

Independent calculations reconstructed **427** retained current-selector contrast intervals using native correct/error counts and beta quantiles at `.05 / actual_family_size / 2`. Maximum endpoint discrepancy was **9.992e-15**; all finding states agreed. There were 376 confirmed and 51 inconclusive claims. Rare-failure alone had 70 confirmed and 14 inconclusive, confirming that 40/40 recovery is not 40 universally confirmed hypotheses.

General BCa, complete-entity bootstrap, percentile ranking, unbounded generic means, temporal/common-shock inference, and native R2/nonadditive intervals without registration are **not defensible new formal claims**. Current public confirmation refuses the approximate routes. In retained qualification, heavy-lognormal BCa had 112 noncovering intervals among 984 available, with 16 refusals; unequal-cluster BCa had 72/1,000 noncoverage. Agreement with SciPy does not cure undercoverage. AUC/AP panels used only one frozen synthetic family-size profile; their 57/1,000 and 46/1,000 noncoverage observations do not establish general ranking coverage. The approved deferral is appropriate.

The null bridge's probability argument is sound **conditionally**: given D/S, independent fitting randomness and the full frozen family, valid elementary intervals with total allocated error at most alpha imply a family bound by the union bound. Overlap/correlation between hypotheses does not invalidate Bonferroni. Integrating over D/S selection preserves the bound if the stated H-independence and sampling assumptions actually hold.

I independently verified unchanged ASTs for `binomial_interval`, `bounded_interval`, `finite_interval`, `orient` and `classify` against the old null capsule, and recomputed actual outcomes across all 2,000 reduced and 200 default trial files: **1/2,000 and 0/200** false-confirmation families. They retain their old source identity. The 1,000-trial partial-null summary explicitly records that the requested-size-one subset contained no null claims and therefore supplies no null-claim control evidence for that subset.

Hashes plus these diagnostics are insufficient to establish independence. The current three-strategy H-label perturbation test verifies unchanged D/S artifacts/shortlist/family and exposure refusal on its fixture, and the inspected code supports the main D/S-only learner/selector boundary. It does not cover every temporal/replay identity path. H1 and H2 demonstrate missing enforcement outside that fixture. Therefore **the mathematical transfer is acceptable, but the implemented end-to-end bridge is not sufficiently reliable for founder acceptance until those gaps are corrected**. No new massive null sweep is required merely to repair those engineering invariants.

## 5. Discovery assessment

The five current-selector claims are verified as five separate synthetic envelopes with 40,000 generated observations each, locked precision/recall thresholds `.70/.70`, and target 32 successes out of 40. Each has 40 successes. Recomputed H medians:

| Envelope | Precision | Recall | IoU |
|---|---:|---:|---:|
| Broad moderate / narrow severe | .990319 | .989405 | .977899 |
| Interaction | 1.000000 | 1.000000 | 1.000000 |
| Parity | .750316 | .994374 | .747286 |
| Categorical / numeric conjunction | .999190 | .997158 | .991651 |
| Rare failure | .954359 | .969856 | .924576 |

The primary endpoint is the **unique union of S-selected shortlist regions**, assessed on H, retaining unavailable oracle members in recall. It is neither the first displayed gate nor an oracle-best candidate. The same locked seed range is reused across archetypes; these are not 200 independent demonstrations of arbitrary-population recovery. Forty successes have a per-envelope two-sided exact 95% Monte Carlo success-probability lower endpoint of about .9119, not certainty of success on future datasets.

Rare completion retains the original source/profile and the 29 existing trials plus 11 missing trials. Independent source comparison found the relevant proposal, discovery, reconciliation and stability function ASTs unchanged from source59 to the final runtime. This supports transfer in that boundary; it does not qualify every other objective or representation.

The simpler-baseline comparison is a real limitation. In the retained interaction baseline, the primary native one-gate median H IoU is **.134535**, versus **.493086** for low-order rules and **.494499** for the shallow tree. Native loses to low-order rules on 30/40 paired seeds; the recorded adjusted median paired gain is negative. Its secondary full-shortlist union has median IoU about **.997981**. These are different endpoints and must not be substituted. The current UX explains severity-first selection, extra support/coverage anchors, exploratory status and distinct union counts; it does not advertise measured baseline superiority. I did not establish a separate false-advertising defect from this distinction.

Approximate explanations cannot redefine learned membership in the inspected pipeline: only frozen membership artifacts determine masks, and the separate explanation carries `kind=approximate`, `defines_membership=False`, fit/evaluation populations and joint-applicability fidelity. Exact predicates identify their identity-based fidelity rather than pretending it is surrogate validation. CatBoost category tags and JSON reload define frozen learned membership; D-only geometry fixes transforms/centers/support and treats out-of-support rows as unavailable.

Nevertheless explanation quality is weak in some admitted cases. I independently observed rare CatBoost surrogate minimum H precision **.097598** across 74 recorded gates; minimum S precision was .110727. Minimum recorded perturbation median IoU was **.255924**. High shortlist recovery does not establish faithful explanation, stable boundaries, causal meaning or future reliability. The browser exposes detailed evidence, but stronger visible quality cues would be a useful usability improvement, not a newly invented universal fidelity acceptance threshold.

The landmark method's 21-pair futility result rejects promotion on its stated profile; it remains experimental. It does not prove universal inferiority. The retained curved fallback anchor is separate from full current-selector geometric qualification. Other unfinished objective/history/geometry panels remain unqualified as authorized.

Realistic evidence also limits generalization: injected tabular Bank/Wine recovery was strong, while retained injected AG News precision/recall were about .218/.488 and CIFAR-10 about .176/.154. These experiments do not establish natural failure-region truth or general semantic recovery. Their independence-refused assessments were not converted into fresh confirmations.

## 6. Security and integrity assessment

Observed strengths include spawned native workers; no pickle input for membership/vector artifacts; bounded model/tree/CTR metadata; pinned CatBoost and verified publisher encoder files; CPU/local-only model loading with remote code disabled; root-confined regular-file admission; protected staging and catalog visibility transactions; explicit migration after backup; content-addressed immutable evidence; restored-workspace branch/continuity markers; and deletion of dependent protected state.

Local API protections inspected and exercised include loopback host/origin checks, CSRF on mutations, session-owned source/model/result/family handles, revision/fingerprint binding, workspace authorization and shared worker exclusion. Public errors use fixed guidance rather than raw sensitive exception text. These are appropriate for the declared local single-user workbench, not remote multiuser authentication.

The disclosure projection withholds learned parameters, source locators, vectors, private declarations and reopening bundles. It checks related small cells, protects overlap families conservatively and keeps shareable imports from recovering withheld data. Exact aggregate permission does not grant parameter disclosure. Targeted sentinel/disclosure tests passed; no additional unauthorized network disclosure or native code-execution vulnerability was established.

H2 is a confirmed evidence-integrity failure despite those safeguards. Resource budgets are sampled/enforced operational limits, not hard OS quotas or a hostile-code sandbox; parent serialization/allocation and sampled overshoot remain constraints. Hashes identify bytes, not anonymization, publisher authenticity for arbitrary supplied models, or truth of declarations. The review did not establish universal exploit resistance or differential privacy.

## 7. Product, architecture and compatibility

CG4 remains a fixed capability within ConfidenceGuard. Typed evidence and investigation modules call shared native metric reducers rather than inventing a browser-specific statistic. The private DataTrust adapter, fixed worker services and canonical result/disclosure/artifact coordinator preserve module boundaries. There is substantial dense/compact orchestration code, but no evidence justifying a new framework or architecture rewrite.

Python/CLI/API services were exercised through targeted tests and independent public workflows. Browser result reopening was tested against actual served final-wheel JavaScript. Canonical report projections remain consistent in their numerical basis; M1 identifies the current-standing display discrepancy. Shareable output appropriately suppresses some explanations/details rather than elevating them. Partial export behavior retains surviving HTML/JSON.

Contract evolution is explicit: historical CG1/CG2 versions remain accepted; prediction batch v2 and catalog v2 opt into typed storage; original variant identities/old result bytes remain preserved; frozen hypothesis version 1.1 binds the expanded policy while version 1.0 remains readable. Earlier paired-precision semantics are not silently recast as the corrected common-issued-base/distinct-positive-denominator estimand. H1 is a genuine retained-semantics compatibility defect.

Python modernization requires 3.12+, with 3.13 primary and scoped 3.14 capability evidence. Locked environments and observed final installed imports support the macOS ARM64 runtime. Unicode case folding is pinned to preserve prior accepted representations, and runtime admission recognizes the exact Torch CPU build while recording its actual identity. Linux/Windows locks resolve dependencies but are not executed product support. The broad metadata requirement `>=3.12` is not evidence that every future Python version or every optional encoder works. Existing 3.14 Lingua/Torch-2.8 limitations and the separate CG4 Torch-2.10 profile remain legitimate boundaries.

## 8. Delivery verification

- Runtime source capsule: `2632e65e5b1b98a3902189fd67b441c35cf97b3239ffc36c78faca2f21997ab8`. I recomputed the inventory digest, verified all capsule file hashes and compared runtime entries with current source; no mismatch.
- Final wheel: `datatrust-0.1.0-py3-none-any.whl`, SHA-256 `929d864aec8ebbcaed774d54e4ab120ae81577ff21a9eedc3e14f2906c36f3ad`. All **196** runtime/static/data files match current source. All 196 installed copies in the final review environment also match, with site-packages origins and no source override. No new environment was built.
- ZIP SHA-256: `29e9efedc993258bc89a2a7f6f50d7ed9909a9a1bf0c7b20b77f05dac47d069e`; matches the external checksum. **52,747** entries, including `MANIFEST.json`, **52,746** hashed payload files, expanded size 1,104,913,207 bytes. CRC and every payload hash pass. No duplicate, unsafe path, unexpected symlink/special-file or privileged-mode entry was found.
- **52,740** payload paths correspond directly to repository files; independently hashed bytes all match. Six remaining generated/alias entries are the start page, source-final inventory, tracked patch, wheel parity inventory, synthetic backup copy and packaged wheel. Their archive hashes were checked; the wheel was independently compared as above.
- Source/tests/docs/constraints/required qualification evidence and source capsules are included; irrelevant frontend labs/environments/model weights/external datasets are outside the declared boundary. Evidence completeness supports a reviewable handoff, not independent truth of all self-reported receipts. No material source/wheel/ZIP mismatch was found.
- Repository status is unchanged byte-for-byte from the initial captured full status, and all 387 baseline source/test/doc/skill/constraint file hashes are unchanged. Reviewer files are outside the working tree.

Delivery integrity therefore passes. It cannot compensate for the behavior of the faithfully delivered defective code.

## 9. Answers to the five suspected inconsistencies

1. Ranking-percentile registration: stale documentation; current public confirmation refuses before H metric evaluation. Historical numerical adapters remain callable internally for research/reproduction and do not themselves publish a new formal product confirmation.
2. First-gate versus union recovery: the retained baseline weakness is real; the qualified claim is shortlist-union recovery. The current UX discloses heuristic selection and distinct union support. No universal superiority claim is justified.
3. Weak fidelity/stability: real and retained; the membership and explanation objects remain separate. No new exact/fidelity guarantee was found. M1 separately concerns historical **statistical** standing, not surrogate fidelity.
4. Stale completion status: confirmed documentation-only contradiction, including the opening CG4 status and a later current-state paragraph.
5. Null-evidence bridge: its conditional mathematical argument is defensible and retained numeric evidence is intact. Its local engineering enforcement is incomplete because of H1/H2. Source hashes alone do not close that gap.

## 10. Smallest justified correction priorities

1. Correct replay/restatement exposure aliases and declared-cutoff retention/reconstruction. Treat both as blockers. Preserve historical bytes and make any incomplete older semantics explicit.
2. Add narrow regressions reproducing the two public-workflow failures, including durable/session tracking and live/retained time parity; recheck affected history/confirmation/exposure/interfaces/disclosure/compatibility. Do not launch replacement statistical research.
3. Add the browser historical-approximation standing warning and fix state-only structured vocabulary. Reconcile current documentation against the approved revision.
4. Freeze the corrected source; rebuild the wheel/ZIP and verify their inventories and affected installed/browser workflows. Reuse genuinely unchanged recovery/kernel/resource evidence with explicit boundaries. A new massive 28-panel qualification campaign is not justified by these corrections alone.

Founder acceptance should wait for evidence that the two high-severity counterexamples refuse or preserve the correct unavailable state. This report does not authorize implementation changes.

## 11. Residual limitations and investigation items

Valid documented limitations include restricted inference populations, conservative finite intervals and weak near-threshold power, unknown external dependence/exposure, selective-label estimands, imperfect surrogate fidelity/stability, proxy/native-metric differences (notably R2), experiment-specific recovery, incomplete new-selector objective/history/geometry evidence, failed landmark promotion, platform/encoder limits and storage measurements that are not discovery-capacity claims.

I did not establish additional confirmed defects concerning ineffective timestamps, feature-revision fallback, parent resource peaks, or arbitrary external copies. These remain possible follow-up investigation areas only if concrete use cases require them; they are not new acceptance gates. No new causal, global-alpha, universal-recovery or universal-platform requirement is imposed.

## 12. Independent conclusion

The review establishes that the declared delivery artifacts match, the five stated recovery results and inspected confirmation arithmetic are reproducible from retained evidence, and current general approximate confirmation is refused. It also establishes two public-workflow integrity failures that let the product report formal finite-sample confirmation under incorrectly reconstructed timing or overlooked locally known exposure.

**CG4 is not ready for founder acceptance in its current delivered form.** It is a substantial, bounded implementation that warrants targeted corrections and an affected-scope re-review. Deferred general statistical research remains deferred.

## Reviewer evidence links

- [Temporal public-workflow reproduction](/Users/drivyaanshyadav/.codex/visualizations/2026/10/28/01a183ba-42e3-7a61-8980-f4c252877cbe/CG4-independent-review/temporal-probe-confirmation.json)
- [Durable replay exposure reproduction](/Users/drivyaanshyadav/.codex/visualizations/2026/10/28/01a183ba-42e3-7a61-8980-f4c252877cbe/CG4-independent-review/replay-exposure-probe-durable.json)
- [Independent 200-trial / 427-interval audit](/Users/drivyaanshyadav/.codex/visualizations/2026/10/28/01a183ba-42e3-7a61-8980-f4c252877cbe/CG4-independent-review/independent-numerical-audit.json)
- [Independent 2,200-null-trial audit](/Users/drivyaanshyadav/.codex/visualizations/2026/10/28/01a183ba-42e3-7a61-8980-f4c252877cbe/CG4-independent-review/independent-null-audit.json)
- [Complete delivery correspondence](/Users/drivyaanshyadav/.codex/visualizations/2026/10/28/01a183ba-42e3-7a61-8980-f4c252877cbe/CG4-independent-review/independent-complete-inventory-comparison.json)
- [68 focused passing tests](/Users/drivyaanshyadav/.codex/visualizations/2026/10/28/01a183ba-42e3-7a61-8980-f4c252877cbe/CG4-independent-review/focused-tests.txt)
- [43 integration passing tests](/Users/drivyaanshyadav/.codex/visualizations/2026/10/28/01a183ba-42e3-7a61-8980-f4c252877cbe/CG4-independent-review/integration-tests.txt)
- [Read-only baseline verification](/Users/drivyaanshyadav/.codex/visualizations/2026/10/28/01a183ba-42e3-7a61-8980-f4c252877cbe/CG4-independent-review/read-only-verification.json)

![Historical approximate assessment in the served final-wheel browser](/Users/drivyaanshyadav/.codex/visualizations/2026/10/28/01a183ba-42e3-7a61-8980-f4c252877cbe/CG4-independent-review/historical-browser.png)
