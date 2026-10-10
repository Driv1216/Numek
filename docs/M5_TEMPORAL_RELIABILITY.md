# NUMEK M5 — Temporal Reliability Intelligence

M5 adds a local temporal audit through Python, CLI and the existing browser app. It retains chronology, schedules/lifecycles, historical and panel coverage, behavioral investigation, feature availability, exact-observation revision histories, outcome maturity, supplied evaluation plans, and canonical HTML/PDF/JSON. It adds no temporal score, fitted model, generated split, backtest, cleaning or persistent monitoring.

## Start an audit

Install the optional decoder with `pip install -e '.[parquet]'`. CSV-only installations do not import PyArrow. Packaged `tzdata` supplies all M5 timezone resolution; each result records the version and relevant zone hashes.

```python
from datatrust import (
    DataTrust, TemporalAuditSpec, TemporalInputSpec, TemporalSourceSpec,
    TemporalSpec, ClockSpec, MeasurementSpec, ScheduleSpec,
    FeatureAvailabilitySpec, TemporalAnalysisConfig, TemporalBehaviorSpec,
)

spec = TemporalAuditSpec(
    inputs=(TemporalInputSpec(
        'observations', TemporalSourceSpec('observations.csv', 'csv'),
        TemporalSpec(
            ClockSpec('observed_at'),
            (MeasurementSpec('temperature', unit='C', past_observation=True),),
            entity_columns=('station',),
            schedule=ScheduleSpec('fixed', cadence_ns='3600000000000',
                                  anchor='2020-01-01T00:00:00Z'),
        ),
    ),),
    availability=(FeatureAvailabilitySpec(
        'temperature-publication', 'observations', ('temperature',),
        ClockSpec('prediction_at'), availability=ClockSpec('published_at'),
    ),),
    dataset_name='Station observation audit',
)
result = DataTrust.audit_temporal(spec, TemporalAnalysisConfig(
    behavior=TemporalBehaviorSpec(windows=12, reference_window=0),
))
result.generate_artifacts('temporal.pdf', format='pdf', json_path='temporal.json')
```

```sh
datatrust temporal --spec audit.json --config options.json --out temporal.html --json-out temporal.json
datatrust temporal --spec audit.json --out temporal.pdf --format pdf --html-out temporal-canonical.html
datatrust ui
```

The browser's Temporal audits link opens `/temporal`: add explicit CSV/Parquet sources, declare semantics, bind timing/history/maturity, add evaluation settings, review effective declarations and source hashes, then run. Guided fields cover ordinary cases; complete JSON import and export cover every public contract. Invalid declarations retain entered fields. Missing timezones or schedules preserve useful evidence while blocking dependent conclusions. Manifest paths resolve relative to the manifest. Auxiliary history/schedule/expectation sources have no analytical `temporal` declaration.

## Contracts and interpretation

`TemporalSourceSpec`, `TemporalInputSpec`, `TemporalSpec`, `FeatureAvailabilitySpec`, `FeatureHistorySpec`, `OutcomeMaturitySpec`, `TemporalEvaluationSpec`/`TemporalFoldSpec`, `TemporalAnalysisConfig` and `TemporalAuditResult` are exported. Supporting `ClockSpec`, `MeasurementSpec`, `ScheduleSpec`, `ActiveInterval`, `SeasonalSpec`, `TemporalSeriesSpec`, `TemporalBehaviorSpec` and `TemporalWorkLimits` make the declarations explicit. Dataclasses/JSON reject unknown fields, incompatible representations, competing authoritative bindings and unresolved references. Existing DatasetSpec/TaskSpec/AnalysisConfig/ComparisonSpec inputs remain unchanged.

Observation meaning (`measurement`, `event`, `snapshot`), scheduling (`none`, `fixed`, `civil`, `supplied`), layout (`wide`, `long`), entities and clock interpretation are independent. Event opportunities do not require an event to occur; absence without operating-status evidence cannot prove an outage. Snapshot differences cannot reconstruct the event path between snapshots. File order becomes arrival order only by declaration. Duplicate timestamps violate a rule only when uniqueness is required.

Clocks use exact integer nanoseconds in DuckDB HUGEINT for instants, separate day ticks for dates, and separate unresolved local clocks. ISO, explicit formats, declared epoch units and native Parquet clocks are supported. Timezone, epoch unit, day/month order and temporal roles are never inferred. Ambiguous DST folds default to unresolved; explicit fold/earlier/later choices are supported. Nonexistent times are invalid and never shifted. Date-only possible intervals cannot establish intraday order without an explicit start-of-day convention. Unsupported precision, leap-second encodings, malformed, missing and range failures remain separate.

Canonical measurement identities retain values/states and multiplicity. Wide/long evidence equivalence requires the same explicit missing cells, keys, precision, measurement identities/units, schedule/lifecycle, availability/history and analytical selection. Sparse long rows are not implicit null wide cells. `dense_long=True` fills measurement absence only for supplied observation identities; whole absent observations stay absent. Physical row references and source-order evidence are representation-specific.

Continuity counts distinct occupied slots. Fixed cadence/anchor use arithmetic counts and compressed gap intervals, including enormous gaps. Civil daily/weekly/monthly calendars use explicit timezone and month-end rules. Local subdaily DST schedules require supplied instants. Supplied opportunities and disjoint lifecycle intervals can include completely absent expected entities. Supplied schedules report missing-opportunity counts and individual point witnesses; compressed gap interval counts and longest-gap slots remain explicitly unavailable rather than equating each missing opportunity with a gap. Missing entity keys remain in global evidence and are excluded from entity checks. Without expectations, observed distances/boundaries do not establish leading/trailing completeness or entity birth/death.

Each availability rule binds named measurements; explicit group overrides replace an earlier named rule. Undeclared features remain unknown. Timestamp evidence, assumed signed delays, static assertions and history evidence keep distinct meanings. Cutoff/availability failures are unresolved, with feature-cell and affected-row-union denominators. Past-observation restrictions apply only where declared and use explicit cutoffs from availability or history-only feature bindings; known future schedules may legitimately be published before their event time. Repeated bindings with the same feature/cutoff declaration do not duplicate the restriction check.

Histories link exact observation keys. Keys are lexical by default. Optional paired `source_observation_clock`/`history_observation_clock` declarations normalize one corresponding clock component exactly across encodings and offsets; other components retain lexical identity. No clock role is inferred from a key name. Latest revisions at/before cutoff retain identical-tie multiplicity and block conflicting ties; source order cannot resolve them. Explicit integer tie order requires declared meaning and unique semantic ordering; conflicting states at the same ordinal remain ambiguous. Unknown nulls, known missing states and retractions never fall back to an older usable value. A later valid revision can restore state. Malformed keyed histories taint assurance; unassignable rows qualify completeness. Completeness defaults to unknown and complete claims require coverage plus initial creation or a baseline. Baselines establish no earlier availability. Exact accepted value equality, declared tolerances and unit/precision guards remain separate. Identified revision timing may be established independently of latest-state ambiguity. Agreement concerns supplied coverage; it never proves what a training pipeline consumed.

Outcome maturity is target-bound, independent of M3 annotation states. Evidence separates unavailable training labels at fit cutoff, missing outcomes already due/not yet due, and unknown maturity. Forecast target time after prediction is expected rather than inherently leakage.

Static/rolling supplied folds audit global/within-entity chronology, group/entity separation, origin membership/overlap, label intervals and point labels, horizons, declared origin/label gaps, available lookback boundaries, training outcome availability and seen/unseen coverage. Endpoints are explicit (half-open by default). Shared lookbacks are legitimate unless a requirement says otherwise. Source split files establish supplied membership; dataset windows establish plan feasibility. A declared origin gap is evaluated even with chronology set to none, using global boundaries; within-entity chronology uses within-entity boundaries. Unusable boundary pairs disclose a blocked gap requirement. Label disjointness requires both label endpoint clocks; equal endpoints represent point labels. Point/interval intersections are symmetric: interval starts are included and ends excluded, with the declared global/within-entity scope. Observed lookback boundaries are pooled across measurements per entity and do not establish internal continuity or feature-specific point-in-time availability.

## Configurable behavioral investigation

Defaults are versioned investigation settings, never universal defect criteria: twelve equal-span windows preserving empty windows; first reference window; support 100; missingness increase 0.05; TV/CDF 0.10; W1/reference IQR 0.25; equal quantitative run length ten with support and variation elsewhere; volatility IQR ratio 2 or 1/2 with 100 differences per side. Explicit windows, reference, support, thresholds and adjacency/rate settings are configurable.

Sparse, empty, constant or atypical references remain visible and are never replaced automatically. Below-support effects are descriptive; zero/unsafe IQR blocks normalized W1 and ratios. Runs break at missing/invalid/conflicting states, lifecycle boundaries and established gaps. Without a schedule/maximum adjacency gap, repetition describes consecutive observations without claiming continuous flatlining. Volatility uses eligible consecutive differences with both endpoints in the same window; it does not bridge missing data or gaps.

Civil weekday/month phases also support declared civil dates and local wall times; this establishes nominal calendar phase rather than elapsed or cross-zone assurance. Hour phases require intraday precision. Declared elapsed/civil seasonality reports cycles, phase support, expected opportunities when computable, common phase populations, reference weights and excluded mass. Default support requires eight cycles, two per compared window and twenty observations per included phase. Phasewise weighted effects do not establish a full seasonal explanation. Panel mix and stable-cohort effects are separate; stable cohorts condition on survival. Explicitly requested series, measurements, seasonal declarations and multivariate pairs spend bounded work across all sources before automatic searches. Requested detailed series take precedence; automatic selection uses coverage concerns, support and canonical identity and discloses bias/unsearched scope.

`behavior.multivariate_pairs=[['temperature','pressure']]` requests contemporaneous matched-observation association/coverage within each window. Identical multiplicity cannot produce a Cartesian pair population; ambiguous observations are excluded. Numerical geometry/support and units remain visible. This capability has no cross-lag mining, independent-row inference, causal claim or defect threshold. Targets additionally retain M3 annotation coverage by window. No unlike measurements are pooled.

## Execution, resources and publication

M4/M5 share the supervised worker boundary, workspace accounting, DuckDB engine, pure distribution-effect mathematics and safe artifact coordinator. One app-level lock excludes simultaneous M4/M5 browser workers. There is no backend registry, persistent database or duplicate analysis engine. Source hashes, normalization fingerprints, ordinals, columns, requirements, exclusions and bounded witnesses make retained evidence traceable.

Parquet supports a single local flat scalar file with typed nulls and physical/logical schema metadata. Nested/encrypted/remote/glob inputs are rejected. Native timestamp integers are preserved before registration. Reads disable prebuffering/threading, retain one returned batch and adapt to projected/observed width. Accepted batches target 32 MiB with a configurable 64 MiB decoded ceiling; footer decoding and oversized scalar values are capped. Native pages/dictionaries/conversion buffers can allocate before these checks. These controls bound accepted batches/application retention, not decoder peak memory; parent RSS supervision covers decoding too.

Phase planning uses compressed bytes, Parquet uncompressed metadata, actual cells/cardinality, variable-width/conversion coexistence and reservations. Estimates are not upper bounds. Wide cells and exact identity aggregation are materialized in small measurement groups to avoid hundreds of concurrent UNION/hash pipelines. Sorting/window/join operations use narrow materialized relations; gaps never expand absent slots. DuckDB spill is useful but does not guarantee completion.

Work visits are reserved before expensive statistics, ordering, phase assignment and multivariate matching. Budgeted search omissions from every family remain visible in coverage. Initial limits are provisional: 100 million cells, one million source-qualified series across the job (including declared expected series), 32 expensive measurements, 64 detailed series/windows, 32 folds, 2,048 comparisons, one billion observation visits, 100 retained details/family and five witnesses. M4 execution defaults remain 2 GiB DuckDB memory, 6 GiB sampled RSS threshold, two threads, 30 minutes, 64 GiB workspace and 32 MiB result. Existing per-source/combined row and source-byte limits also apply. Settings are engineering controls, not capacity guarantees or OS quotas.

Required aggregates cover every eligible record or fail. Contract/structural/integrity/allocation/disk/deadline/cancellation/required-stage failures publish no completed result. Invalid cells yield evidence/exclusions; no usable chronology blocks temporal conclusions. Unexpected optional failures discard uncommitted evidence and newly created intermediate tables, restore relation caches and selected-series state, and preserve earlier committed evidence as partial. This is an application rollback of the current optional algorithms, which only write new intermediate tables, not a general SQL transaction. Attempted observation visits/comparisons remain charged and are disclosed on the failed-stage record so failures cannot refund work budgets. Planned search bounds yield completed bounded execution with explicit unanswered scope. PDF/export failure preserves valid surviving artifacts. Retries never silently change precision, populations or parsing.

JSON schema 1.4/methodology `temporal_reliability_v1` preserves every retained evidence record, exact decimal-string ticks/durations and unsafe integer counts. Aggregate coverage, unsearched scope, internal detail omissions and presentation omissions are distinct. HTML/PDF use eight compact topics, escaped self-contained SVG/CSS, five executive actions and twenty metric rows/topic; HTML exposes up to 100 retained appendix rows, with a compact PDF excerpt and explicitly abbreviated long cells. Selected-series aggregate evidence appears first in the main behavioral topic; bounded per-series details remain in the appendix/JSON. Filtering/rendering completed evidence requires no analysis; deeper searches require revised declarations. Artifact destinations cannot overwrite sources or unrelated files.

## Verification evidence

The repository [Verification skill](../agents/skills/verify/skills.md) is authoritative. New evidence lives in [validation/m5](../validation/m5/README.md), with independent truth tables in `tests/m5`, a ledger of commands/source hashes, pinned public transformations and declared workload records. Public Bike Sharing, Beijing, Electricity, Retail and archived ALFRED cases retain source clock peculiarities and incomplete/release-day uncertainty. Controlled mutations establish exact expected counts, not universal thresholds.

The default-memory full electricity panel initially failed allocation. Bounded measurement-group materialization subsequently completed all 51,894,720 cells under the same defaults; this is recorded operating evidence, not a capacity guarantee. M4's earlier execution-verified closure and later source-only corrections remain distinct historical records. M5's current affected-code execution does not retroactively upgrade that history.

The narrow 2026-10-11 source-review correction pass and its separate focused execution evidence are recorded in [M5 source-review corrections](history/M5_SOURCE_REVIEW_CORRECTIONS_2026_10_11.md). It does not begin the M5 understanding pass or alter earlier M4/M5 verification history.
