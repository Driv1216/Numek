# ConfidenceGuard longitudinal reliability

Implemented methodology: `longitudinal_reliability_v1`. Historical contracts have
independent `confidenceguard.* /1.0` identities. CG1/CG2 1.0/1.1 contracts and
mathematical procedures remain available. This is one ConfidenceGuard workspace,
with optional history alongside standalone evaluation, fitting and application.

## Use

```python
from confidenceguard import ReliabilityWorkspace, WorkspaceConfig
workspace = ReliabilityWorkspace.initialize('/absolute/local/workspace',
    WorkspaceConfig(saving=True))
receipt = workspace.ingest(prediction_batch_spec)
preview = workspace.inspect(longitudinal_spec)
result = workspace.analyze(longitudinal_spec,
    expected_fingerprint=preview['fingerprint'], request_id='assessment-request')
result.generate_artifacts('/absolute/output/history.pdf', format='pdf',
    audience='shareable', json_path='/absolute/output/history.json')
restatement = workspace.restate(result.data['analysis_id'],
    as_of='2027-02-01T00:00:00Z', reason='Delayed labels received')
```

Initialize without `saving=True` to require a separate saving opt-in. The CLI has
`confidenceguard workspace --path PATH` commands for init, saving, status, models,
ingest, outcomes, correct, inspect, analyze, restate, assessments, open, export,
backup, restore, recover, deletion-preview and delete. Run `--help` on a command.
`confidenceguard ui --workspace PATH` prints a one-time browser launch link.
The API uses registered source handles; browser clients cannot supply storage or
scratch paths. Inspect effective populations before confirming a historical job.
Changed declarations require a new inspection. Filtering completed evidence does
not execute analytics. A restatement is a new immutable assessment.

`validation.cg3.reproduce` generates supplied synthetic predictions and an example
workspace/reports without executing a predictor. `validation.cg3.resources` measures
historical workloads; `validation.cg3.statistics` evaluates sampling designs.

## Capture and identities

`history_capture` extends the secure projected source ingestion boundary. Stage A
writes every parsed admitted projected row immediately after ingestion and before
`Store.prepare()`. This includes missing/invalid/duplicate/unmatched rows, lexical
strings, raw clocks, role and auxiliary inputs. Original source hashes, mappings,
projection and clock interpretations accompany protected capture metadata.
Projection is reconstructable; the original file's byte stream is not. Inspection
alone never records facts.

Stage B writes normalized intrinsic prediction outputs, representation inputs and
actual frozen method outputs before CG2 E projection. It does not refit or apply
an absent method. The capture sink is write-only to analytical fitting/selection.
Raw E facts remain protected and are not queried by optimizers.

Canonical tuple identities distinguish entity, source event, outcome target
(event/definition version/target instance), opportunity (target/stable occasion),
variant (predictor/auxiliary identities, ordered method digests, representation,
decision policy), slot and attempt. Lexical keys are never trimmed/coerced.
Hashes index canonical identities; full keys remain protected in evidence.
Entity namespaces default explicitly to the batch namespace and can be bound separately.
Batches are provenance containers. Same identity/revision/payload counts once;
conflicts refuse publication. Different opportunities remain repeated observations.
Retries are attempts, and multiple attempts require explicit selection. Each
assessment selects one slot; multiple slots are evaluated separately and cannot
be pooled into duplicate opportunity rows. Samples
belong to a particular prediction observation/revision and never add events.

Missing model artifact hashes qualify identity claims. A model name alone does
not establish unchanged mathematics. Supply explicit historical event/opportunity
bindings where CG1/CG2 keys need different semantics. Initial outcome snapshots
use outcome keys as event keys; complex event/target bindings use the explicit
outcome revision importer. Time is never synthesized from file order.

Corrections require an existing predecessor, stable revision, reason, authority
and availability. Roles/entities cannot be reassigned as corrections. Prediction
corrections reenter through the shared normalizer; opportunity/context corrections
use `HistoricalCorrectionSpec`. Competing heads/ambiguous attempts are excluded
and counted, with qualification. Temporal windows cannot locate invalid clocks;
these opportunities are separately counted as unlocated, rather than assigned a
fabricated date. Raw records remain available.

## Selection and historical interpretation

Selection materializes retained facts into supervised DuckDB once per assessment;
all windows/metrics reuse those relations. It freezes catalog sequence K, applies
source availability A and correction heads, selects opportunities/attempts,
applies windows and follow-up, resolves authoritative outcome revisions, then
constructs role/output/metric-specific populations. No many-to-many join may
multiply a performance observation.

A target's highest ordered eligible outcome revision wins before validity is
interpreted. Withdrawals/invalidations do not revive older labels. Ambiguous
orders, unknown potentially eligible availability and inconsistent chronology
prevent qualified selection. Provisional/unresolved labels are retained as states
and excluded from final/observed-label performance. Incomplete supplied revision
histories cannot establish what happened before the retained first record.

K is workspace knowledge, A is reconstructed source availability. Late imports
cannot enter earlier K. Equal follow-up imposes an opportunity-specific cutoff
and excludes insufficiently aged opportunities and later revisions. Unknown due
rules qualify maturity; observed-label descriptions remain possible. Undated
initial snapshots are usable only in the explicitly undated-current assessment
path (`as_of=None`); they do not establish historical source-as-of availability.

Outcome-only restatements freeze the predecessor prediction/opportunity/context
catalog snapshot and source availability cutoff while admitting later outcome
revisions. Metadata retention declarations also resolve at the frozen snapshot;
a later feature-retention extension cannot appear in an earlier view. Partial
retention qualifies/refuses the affected drift evidence rather than treating
unretained values as missing data. Windows, cohorts,
artifacts and other analytical declarations remain fixed. A method/partition
change is a separate analysis. Previous assessment bytes and digests do not change.
Legacy saved assessments remain their original duplicate populations. Historical
union populations are newly identified evidence.

## Storage, publication and lifecycle

SQLite is authoritative for workspace settings, identities, operations, revisions,
inventories, receipts and deletion state. DuckDB is disposable supervised scratch.
Labels, probabilities, features and losses reside in immutable protected JSONL,
not SQLite analytical tables. Capture metadata containing fitted parameters is
also protected evidence, not catalog JSON.

UTF-8 uncompressed JSONL uses versioned data-only envelopes and bounded records,
32 MiB target chunks (records never split). The identity directory provides
object/offset/length addressing and indexed overlap checks. Logical fact digests
are independent of encoding; future formats require new readers, not in-place
rewrites. JSONL pays row-parsing and repeated-field storage costs. It is a measured
local format, not an unlimited-history capacity promise. Wide probabilities and
predictive samples receive separate workload evidence.

The operation lock covers each mutation/analysis; object access is shared for
readers and exclusive for recovery/deletion. Order: operation, object access,
short SQLite transaction. Downloads never upgrade locks. Contention is bounded;
no persistent queue is introduced. SQLite FULL synchronization is required; WAL
is selected only for fixed SQLite runtimes, otherwise DELETE/FULL. Local filesystems
with functioning locking/fsync are required; network/shared storage is unsupported.

The parent reserves space, begins hidden pending inventory, receives worker
staging, verifies records/digests, publishes immutable objects without replacement,
fsyncs, then activates directory/inventory and receipt in one SQLite transaction.
That transaction is visibility. Precommit cancellation publishes no completed
history; commitment wins later cancellation. Repeated matching request IDs return
receipts. A failed recording never reports saved history. Ephemeral completed
evaluation can be attached separately to the failure.

Recovery removes pending/orphan objects and continues durable deletion plans.
It never adopts an orphan or regenerates changed committed evidence. Corrupt
catalogs require explicit restore/repair. Missing/deleted selected fact objects
refuse reconstruction; completed retained assessment exports remain immutable.
Purged facts cannot be silently resurrected by reimporting their old identity.

Saving is off by default. The default persistent ceiling is 64 GiB with a 2 GiB
free-space reserve and no age eviction. Limits refuse recording rather than evict
history. Stopping saving preserves reads. Deletion previews freeze dependencies
and K. Removing batch association differs from evidence purge. Evidence purge
expands affected capture objects transitively, including raw/derived copies and
overlap provenance, and lists potentially affected assessments. Deleting only an
assessment preserves reusable facts. Tombstones precede unlinking; readers hold
objects shared. Full purge retires the instance and revokes grants. Retained
reports may still contain disclosed aggregates; local deletion cannot revoke
previously exported copies.

Backups use SQLite's backup API plus every verified committed object, with a
completion manifest. Destinations must be new and outside the live workspace.
Restore validates all files into a new instance identity, preserving analytical
identities. A live SQLite main-file copy is not a backup. Catalog version 1 is
initialized transactionally; unsupported future versions refuse. No historical
format conversion or schema-upgrade migration is needed for the initial release;
a future migration must require a verified backup and transaction.

## Browser authorization and disclosure

A random launch token is process/workspace scoped, single-use, expires after ten
minutes, and redirects immediately to a clean URL. Logs redact launch queries;
no-referrer/no-store/loopback/CSP/session ownership/CSRF remain enforced. CSRF alone
cannot enumerate history. DataTrust history grants do not authorize CG history.
Detach/restart/purge invalidates workspace result/artifact access. Browser paths
are host-controlled. These are local OS-user protections, not encryption or
hosted multi-user security.

Canonical HTML/PDF/JSON answer the five product questions. Protected local bundles
retain lineage/evidence locators. Conservative shareable projection jointly
withholds related small populations and dependent deltas; event chart payloads, ranking details, feature/context tables and decomposition
are withheld for that policy. Safe aggregate timelines remain visible. Related
metric families are withheld jointly across windows/cohorts/variants, without
suppressing independent safely disclosable families. Local and explicitly exact aggregates retain substantive views. Saved
shareable imports cannot elevate. Arbitrary reconstruction across independently
exported reports is not claimed to be prevented.

## Analytical methods and interpretation

Fixed, calendar and bounded rolling half-open windows share exact clock parsing.
Calendar utilities expose timezone/DST boundaries. Drift uses empirical KS,
Wasserstein-1, categorical TV/Jensen-Shannon, missing/invalid rates, category mass,
and frozen reference histograms. Scores need compatible orientation/scale.
Distributions do not establish degradation or multivariate stability. Performance,
frozen-bin calibration/high-confidence, quantile/sample and conformal/supplied
uncertainty reducers reuse CG1/CG2. Infinite losses, empty/full/unbounded outputs
retain their meanings. Observation profiles expose observed/unobserved retained
covariates; representativeness is not inferred from equal maturity.

Comparison qualification applies per edge and dependent metric: target/horizon/
units/class changes block supervised deltas; model/artifact changes identify
variants; different period plus different variant is combined change. Matched
contrasts recompute common opportunities. A contrast's evolution is associational,
not causal difference-in-differences. Changed cohort partitions require one frozen
recomputation. Interval/set nominal semantics and native score meaning must match.
Selective labels constrain the estimand to eligible observed labels. Planned
output failures remain operational evidence and successful-output metrics do not
establish full planned-population performance.

Exhaustive cohort finite means receive symmetric mix/within decomposition with
exact reconciliation. MSE is decomposed, not RMSE. Common-support standardization
reports excluded mass for disappearing groups; missing groups are never imputed.
AUC/AP/F1/ECE/R-squared have no fabricated subgroup decomposition. Trends,
lag-one dependence, declared seasonal phases and bounded weighted change-point
scores remain descriptive/exploratory, with gaps and minimum segment lengths.

A frozen optional `event_costs` matrix supports actual categorical action/outcome
cost means, including declared abstention costs; unmapped states are excluded and
disclosed. This does not execute or optimize a different policy. CG1 replay
definitions remain in their original assessments and capture metadata; diagnostic
replays do not change actual prediction variant identity.

Historical inference supports finite mean/rate/ratio/RMSE contrasts and tie-aware
AUC/AP for eligible independent-period/entity designs. Contributions are recomputed
under joint resampling; conditional denominators are not averaged across groups.
Matched uncertainty outputs use metric-specific common eligibility. Mean-based
matched variant contrast changes use joint within-period event contributions.
Nonadditive contrast-change inference is unavailable.

Independent periods require disjoint opportunities/targets and declared unit and
period independence; repeated entities, known serial dependence and common shocks
refuse this design. Entity resampling draws the union of independent whole entities
with shared period weights and event weighting; shared outcome dependence must
fit within clusters. Cross-entity common shocks are not corrected by clustering.
Moving blocks require regular complete bins, known empty versus missing distinction,
stationary weakly dependent regimes, finite moments, supplied independent block
length and defensible period independence. Noncircular overlapping blocks are
drawn uniformly, concatenated and truncated. L=1 is not dependence correction.
Known trend/break/seasonality violations refuse ordinary stationary inference.

New historical support floors are 30 participating/effective denominator units
per relevant arm/conditional population, with class support for rank metrics.
Moving blocks additionally require 30 nonoverlapping/effective block equivalents.
These floors do not prove validity. No universal block length is selected.
Declared sensitivity lengths are exploratory and never replace the primary.

Families freeze metrics, edges, windows and declared cohort groups (including
missing/other states) before computation; unavailable contrasts do not shrink
Bonferroni tails. Pointwise remains explicitly labeled. Work admission divides
the frozen budget across the family/sensitivities. Invalid/degenerate replicates,
nonfinite estimates, inadequate support/tails/dependence/resources refuse affected
intervals; required inference fails the assessment. No adaptive retry or hidden
replicate deletion occurs. Existing CG2 procedures/RNG remain unchanged.

Finite simulations are evidence of limitations as well as correctness. The
qualification run's short-block AR(1) experiment substantially undercovers its
nominal level, while misspecified IID is worse. This is retained in the ledger;
it reinforces that block choice/support floors cannot establish finite-sample
coverage. Intervals remain approximate assumption-qualified investigations.
No missing-label correction, causal attribution, sequential error control or
post-selection significance is claimed.

## Scope and verification

Automatic slices, policy optimization, model execution, automatic recalibration,
adaptive/temporal conformal guarantees, ingestion scheduling, alerts/incidents,
streaming/distributed storage and hosted multi-user access remain excluded.

See `validation/cg3/README.md` and its executed ledger for references, lifecycle
faults, workloads, privacy/browser/PDF evidence, compatibility checks and the final
allowlisted technical review ZIP. CG3 is complete, including corrections R1–R3, as confirmed by the user on 2026-10-21. Recorded methodology and resource qualifications remain applicable.

## Independent-review corrections (2026-10-21)

New assessments record `historical_interpretation_v2`. Original assessments,
protected facts and the original review ZIP remain unchanged. CG3 is complete, including corrections R1–R3, as confirmed by the user on 2026-10-21.

Historical scalar identities now bind metric/family/method version/units and
applicable target, nominal level, interval definition, quantile level, calibration
partition, threshold and measurement-specific method/artifact dimensions. Observed
bin counts and fitted diagnostic values are not definition dimensions. Predictor
and ordered calibration/conformal artifact identities remain bound by each variant
and comparison edge: comparing different artifacts is still an explicit variant
comparison, not an unchanged-artifact temporal claim. Only equivalent metric
identities receive direct deltas. Native intervals use paired common eligibility
per interval, independent of unrelated intervals on either variant. Comparison,
cohort, timeline, browser selector and report labels retain distinct definitions;
conservative shareable exports use aliases without revealing private target labels.

Materiality has an explicit interpretation policy. Accuracy, balanced accuracy,
F1 variants and ranking measures are higher-is-better; declared losses are
lower-is-better. Signed bias and calibration intercept use distance from zero;
calibration slope uses distance from one. Coverage uses change in shortfall below
its compatible nominal level: extra overcoverage is not itself called degradation.
Efficiency and width remain separate evidence. Observation/population availability
rates support unsigned absolute-change descriptions, without an adverse-performance
claim. An unregistered metric, missing nominal level, nonfinite effect or unsupported
target-dependent contrast-of-contrasts receives an unavailable practical assessment
with a reason. There is no default lower-is-better fallback or statistical
confirmation. The threshold continues to bind the metric name and applies to each
retained target/nominal identity, including declared cohorts.

All drift distances remain available descriptively. Optional `drift_thresholds`
freeze field-specific distance thresholds, for example a domain-chosen
`{"feature:amount":{"wasserstein_1":1000}}` in the feature's native units. This is
configuration syntax, not a recommended cutoff. Supported distances are KS,
Wasserstein-1, total variation and Jensen-Shannon divergence in nats. No thresholds
are supplied automatically. Each drift record states no threshold, within declared
thresholds, exceeded thresholds, or unavailable requested effect. Only an exceeded
declared threshold produces an Investigation-priority distribution-change finding;
this remains descriptive materiality, without a p-value or degradation claim.
Missing requested field names are explicitly listed in completed evidence.

See `validation/cg3/review-corrections/README.md` for the focused correction ledger,
new examples and source changes. No additional ZIP was requested or created. Earlier passing
security/lifecycle/workload/model qualification is reused where unchanged.
