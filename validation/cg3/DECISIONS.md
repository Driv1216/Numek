# Decisions, capability qualification and exclusions

## Implemented

One product and one reducer path: pre-filter projected inputs and actual frozen
outputs are retained in immutable JSONL, selected under catalog K/source A and
materialized once into supervised DuckDB. SQLite owns durable metadata and
publication, not labels or analytical payloads. Original CG1/CG2 assessments are
never rewritten into deduplicated historical populations.

Canonical identities separate event, target, opportunity, entity, predictor/variant,
slot, attempt and correction. Overlaps preserve provenance but count one logical
fact; conflicting payloads refuse commitment. Source chronology, outcome order,
withdrawals, delayed labels, equal follow-up, frozen-prediction outcome restatement,
explicit context corrections and missing reconstruction are first-class states.

Publication has one SQLite visibility boundary, protected immutable files,
idempotent receipts, cooperative OS locks, precommit cancellation, crash recovery,
dependency-previewed deletion and verified SQLite-API backups. Local browser grants
are process/workspace scoped and single-use on attachment. DataTrust history and
legacy standalone workflows remain independent and available.

Descriptive capabilities include three-task performance, calibration and supplied/
conformal uncertainty evolution, empirical distribution distances, feature retention
and observation diagnostics, matched variants, temporal contrast changes, declared
cohort standardization/mix/within, trends/lag/seasonal diagnostics and bounded
exploratory change candidates. Python, CLI, API, browser and reports share services.

## Explicit assumptions and qualifications

Identity/artifact hashes and completeness/authority of supplied outcome history are
declarations. Missing identities narrow conclusions; changed target/horizon/units/
classes or incompatible uncertainty/score semantics block dependent contrasts.
Observed labels do not establish full-population performance; equal maturity does
not establish representativeness. Post-outcome cohorts are investigative context,
not pre-prediction composition. Historical model/time contrasts are associational.

Inference is conditional on frozen artifacts and observation rules. Independent
periods require actual independent units and periods; whole-entity inference needs
independent complete clusters; moving blocks need regular complete bins,
stationary weak dependence and a defensible supplied block length plus independent
regimes. The support floors are admission rules, not validity theorems. Invalid,
degenerate, nonfinite or unsupported inference refuses; multiplicity families do
not shrink around unavailable contrasts. No fitting/missing-label uncertainty,
sequential guarantee or change-point post-selection significance is claimed.

The retained 100-trial AR(1), n=300, L=5 experiment covered only 79% at nominal 90%
(95% Monte Carlo Wilson interval about 70.0–85.8%); misspecified IID covered 52%.
The n=1200 supplement covered 86% for primary L=20 (MC interval 77.9–91.5%).
Sensitivity lengths are exploratory and do not replace the primary or cure the
negative evidence. Users must qualify dependence/block choices; CG3 cannot certify
general finite-sample temporal coverage.

JSONL is simple, addressable and appendable but expensive. The million-opportunity
probe retained about 7.29 GB from 148 MB supplied inputs; sample-heavy 10k×100-draw
probe about 2.67 GB from 30 MB inputs. These include projected inputs, outputs,
provenance, directory and catalog overhead. Timing/resource results are measured
local workloads under concurrent load, not unlimited-history capacity promises.
Physical verification and record parsing are separately counted; one materialization
pass does not mean each byte is read once in total. Format-version boundaries allow
future encodings without changing logical identities; no second format is introduced.

Conservative shareable projection jointly protects related metric families and
withholds detailed drift/mix/feature/chart payloads where necessary. Exact local
reports retain substantive evidence. Arbitrary cross-export reconstruction and
revocation of already exported files are not claimed.

## Deliberate exclusions

Automatic slice discovery, policy optimization, model/auxiliary execution,
automatic recalibration, adaptive temporal conformal guarantees, continuous
scheduling/ingestion, alerts/incidents, streaming/distributed storage, hosted
multi-user access, causal attribution and a universal reliability score.

CG3 is complete, including corrections R1–R3, as confirmed by the user on 2026-10-21. Recorded qualification limits and deliberate exclusions remain unchanged.
