# Proposal: Workstream 3. Contextual diagnostics and before/after preprocessing assessment

**Status:** approved 2026-10-20 (separate interpreted view; dependency search on by default within limits; suggestions shown automatically, never applied; 3A and 3B in one execution). Implemented 2026-10-20; see section 7.
**Depends on:** Workstreams 1 and 2, both complete.
**Unchanged:**
- scoring formulas, thresholds and every existing number
- the legacy classification contract (`analyze()`, `to_legacy_dict`, its findings and risks)
- historical artifacts
- the UI design
- ConfidenceGuard

**Contextual findings are evidence only:** they never change a score.

## 1. What the code and Bank Full show today

### 1.1 Placeholders, sentinels and conditional populations

These are the facts from Bank Full (`bank-full.csv`, 45,211 rows), all measured on 2026-10-20.

| Column | Raw value | Rows | What the data itself shows |
|---|---|---|---|
| `poutcome` | `unknown` | 36,959 | It co-occurs with `pdays = −1` in 36,954 rows. **5 rows** have `unknown` while `pdays ≠ −1`. |
| `pdays` | `−1` | 36,954 | It holds **exactly** when `previous = 0` (36,954 = 36,954, with no exceptions). |
| `contact` | `unknown` | 13,020 | 12,507 of these rows fall in May and June. |
| `education`, `job` | `unknown` | 1,857 / 288 | — |

**How DataTrust handles these today**
- `unknown` is an ordinary category and `−1` an ordinary number. The Gaps module reports 0 missing cells.
- `pdays` has zero IQR (q1 = q3 = −1), so its outliers are *not assessable*. Workstream 2 now states this.
- If `−1` meant "never contacted", the applicable population would be **8,257 rows** with q1 133 and q3 327, and **49** values would fall outside the fences. No current check can see that population.

**Declarations available today**
- Parsing `na_values` / `missing_policy` exist, but the legacy classification policy refuses non-default parsing. They would also *rewrite* the parsed values, losing the raw evidence.
- M4 has value constraints (`allowed_values`, `minimum`…), which declare validity, not meaning.
- **Nothing lets you say:**
  - "`unknown` means not collected"
  - "`−1` means not applicable"
  - "`pdays` applies only when `previous > 0`"

### 1.2 Prediction objective and availability

| Workflow | Availability declarations |
|---|---|
| Regression | Per-column `feature_availability` (available / unavailable / unknown) already exists, and it drives findings and the relationship search |
| M3, M4 | Similar maps exist |
| Classification (legacy) | **None.** Leakage is checked by column name only |

**Example: Bank Full's `duration`**
- `duration` is the length of the last call. It is known only after the call that produced the outcome.
- For an objective of *"decide whom to call"* it is unavailable. For *"explain call outcomes"* it is legitimate.
- No name check can tell these apart, and no workflow records the prediction objective or prediction point at all.

### 1.3 Target copies with neutral names

| Situation | Detected today? |
|---|---|
| Classification, copy of `y` named `col_17` or `flag` (0/1) | **No.** The check is name-only, so this is the acceptance gap |
| Regression | Yes. The bounded relationship search finds `cnt = casual + registered` and identity copies |
| M4 single-source advanced | Partly. A categorical feature→target functional-dependency proxy search runs, with gates: support ≥ 5 per category, coverage ≥ 80 %, no violating categories. It covers categorical inputs only and never reaches core classification |

### 1.4 Before/after preprocessing

**What M4 `versions` mode (reference → current) already compares:**
- schema (added, removed and retyped columns)
- value populations, with tests and multiplicity adjustment
- declared segments
- shared identity groups

**What it lacks:**
- a row-count reconciliation
- record lineage: retained, dropped and added identities, by class
- target coverage before and after
- missingness and non-finite deltas per column
- the declared transformations
- a statement of what the comparison cannot establish

## 2. Design

### 2.1 Optional context declarations (`context_v1`)

A new optional `AnalysisConfig.context`, used by classification, regression, unlabeled and M3:

```json
"context": {
  "prediction": {"objective": "decide which clients to call", "point": "before the first contact of this campaign"},
  "columns": {
    "duration": {"availability": "unavailable_at_prediction"},
    "poutcome": {"placeholders": {"unknown": "not_applicable"}},
    "pdays":    {"sentinels": [{"value": -1, "meaning": "not_applicable"}], "applies_when": {"column": "previous", "op": ">", "value": 0}, "unit": "days"},
    "contact":  {"placeholders": {"unknown": "not_collected"}}
  }
}
```

**Fields**

| Field | Allowed values |
|---|---|
| Placeholder and sentinel meanings | `not_collected` · `not_applicable` · `refused` · `censored` · `category` (a real value) |
| Availability | `available_at_prediction` · `unavailable_at_prediction` · `unknown` |
| `applies_when` operators | `=`, `≠`, `>`, `≥`, `<`, `≤`, `is_null`, `not_null` |

`applies_when` takes one condition per column, on another column.

**What a declaration does not do**
- It **never changes parsing, the profile, the findings list or the score.**
- Raw parsed evidence stays exactly as it is.
- Declarations produce a separate, *interpreted* view beside it.

**Sealing**
- The declarations are covered by the confirmation fingerprint.
- Changing any declaration invalidates the confirmation and its artifacts, and requires a new run. This is the same rule WS1 applied to separators.

**Relation to regression:** regression's existing `feature_availability` remains the source of truth. `context.columns.*.availability` is read as the same map, and the two must agree or the configuration is refused.

### 2.2 Contextual evidence block (`contextual`, versioned `context_v1`)

New results gain an additive top-level block. It is present even without declarations, and it keeps four kinds of statement strictly apart:

| Kind | What it holds | Bank Full example |
|---|---|---|
| **Candidate meanings** (never applied) | Values that commonly encode absence or special cases, found by a fixed, versioned rule set: text tokens such as `unknown`, `n/a`, `na`, `none`, `null`, `missing`, `?`, `-`, `not known`; numeric codes such as −1, −9, −99, −999, 9, 99, 999, 9999 when the code is the column's most common value or lies outside the range of the other values | `unknown` in 4 columns; `pdays = −1` as the most common value, outside the range of the rest |
| **Your declarations** | Exactly what you declared, with the count of raw values each one covers | `poutcome: unknown → not_applicable` (36,959 rows) |
| **Observed dependencies** | Co-occurrence the data shows among declared or candidate codes, and whether a declared condition holds: exceptions counted, with bounded row references | `pdays = −1 ⇔ previous = 0` holds in all 45,211 rows; `poutcome = unknown` has **5 exceptions** where `pdays ≠ −1` |
| **Demonstrated use** | Only what a supplied artifact shows. Here: which columns survive into an *after* dataset (§2.5). DataTrust never infers model use | — |

**Interpreted populations**
- For each declared column, its *applicable population* is recomputed beside the raw evidence: count, missing by declared meaning, and the numeric summary and 1.5 × IQR evidence on applicable values only.
- Example: `pdays` becomes assessable on 8,257 rows (q1 133, q3 327, 49 outside the fences), while its raw zero-IQR evidence stays untouched.
- **Declared missingness** is reported as cells and rows by meaning: *not collected* versus *not applicable*. This is what Gaps then shows alongside the parser's "0 missing".

### 2.3 Prediction objective and availability findings

These findings depend on the declared objective:

| Declaration | Contextual finding |
|---|---|
| A column declared **unavailable at prediction** is present among the features | `declared_unavailable_feature`. Classification gains the finding that regression and M3 already have. |
| A column **strongly dependent on the target** (§2.4) has availability **unknown** | `dependency_availability_unknown`: declare it before relying on the feature |
| The same column declared **available** | Reported as a *deterministic predictor to verify*, not as leakage |
| No objective declared | Every availability statement says *"availability was not declared; nothing was concluded"* |

For Bank Full, declaring the objective "before the first contact" and `duration` as unavailable produces one finding naming `duration`. Declaring it available produces none. **The finding depends on the declaration, as the plan requires.**

### 2.4 Target dependency within a selected scope (classification and M3 classification)

A bounded, evidence-only search that reuses M4's gates:

| Input type | Method | Flagged when |
|---|---|---|
| Categorical feature | Feature → target functional dependency (M4's rule as it is) | ≥ 2 categories, each with ≥ 5 rows, coverage ≥ 80 %, and no category maps to two targets |
| Quantitative feature | Exact class separation | The finite value ranges of the target classes do not overlap, with ≥ 5 rows per class and coverage ≥ 80 % |

**Scope**
- Defaults: all features, up to 64, and up to 128 feature–target checks.
- Both limits are adjustable. Unsearched features are listed as *unsearched*, never as clean.
- This catches **neutral-name copies**, such as `col_17 = y` or `flag = (y == "yes")`, and value-level proxies.

**False-positive guards**
- **Identifier-like columns** cannot pass the ≥ 5-rows-per-category gate.
- **Legitimate deterministic predictors** stay candidates until availability is declared (§2.3).
- **Small datasets** below the support gates are recorded as *not assessable*.

### 2.5 Before/after preprocessing assessment: an M4 preset

`ComparisonSpec(mode="versions", preset="before_after")` adds the following to the existing versions engine:

**Roles and inputs**
- The roles are labelled *Before* and *After*. Internally they are still reference and current, so the engine and its tests are unchanged.
- **Declared transformations:** a list of `{kind, columns, description}`. The kinds are:
  - `impute`, `drop_rows`, `drop_columns`, `cap`, `transform`, `encode`, `rename`, `deduplicate`, `filter`, `resample`, `other`
- **Optional keys:** identity and group keys.

**The run reports**

| Area | What is reported |
|---|---|
| **Count reconciliation** | Rows before − dropped + added = rows after, and the same for columns. The difference is always shown: *explained by identity evidence*, or *unexplained* when keys are absent. |
| **Lineage** (only with identity keys) | Retained, dropped and added identities overall and by target class, plus duplicates of a key on either side. Without keys: *"record-level lineage requires identity keys; only aggregate counts are compared."* |
| **Target coverage** | Class counts and shares (or the finite target distribution) before and after |
| **Missingness and non-finite deltas** | Per column. Imputation is checked against the declaration: *declared imputed, still missing N*. |
| **Distributions** | The existing population comparison |
| **Schema** | The existing schema diff, mapped to the declared transformations. Undeclared changes are listed separately. |
| **Incompatible representations** | For example, one categorical column becoming *k* encoded columns: *"not comparable as declared; declare an `encode` mapping to compare category coverage."* |
| **Remaining risks** | The existing single-source findings on *After*. Each one is labelled *still present*, *new* or *no longer flagged*. |

**The report states plainly:**
- *"Fewer findings or a higher score after preprocessing does not establish improvement; it shows what changed in the data."*
- No model-performance claim is made.
- No transformation is ever performed.

**Re-running:** changing a declared transformation changes the seal, so a new run is required.

The app gets a fourth M4 mode card, *"Before and after preprocessing"*, inside the existing M4 flow.

### 2.6 Where it appears (existing design)

- **Gaps:** declared missingness by meaning, beside the parser count.
- **Outliers:** applicable-population IQR evidence for declared sentinels.
- **Leakage:** the objective, the availability declarations, and the dependency search with its scope and unsearched features.
- **Configure:** an optional *Context* section with the objective, the prediction point, and per-column availability, placeholder, sentinel, unit and condition. Fields reuse the M3 and regression form components. The candidate meanings are shown as suggestions you can accept with one click; nothing is applied unless you accept it.
- **Reports:** a *Context and declarations* section in the technical layer. Every contextual finding gets `finding_guidance_v1` entries, and observed facts trace to the block.
- **M4:** the before/after report adds a *Reconciliation and lineage* section.

## 3. Independent scientific qualification for this workstream

The plan's qualification goal starts here, because these are new methods.

**Benchmark definitions** are frozen **before** evaluation in `validation/ws3/benchmark.json`: cases, expected outcomes, gates.

| Kind of case | Content |
|---|---|
| **True positives** | Controlled mutations of German Credit, Adult and Bank Full: a renamed exact target copy; a re-encoded copy (0/1, yes/no ↔ T/F); a categorical proxy with a 2 % label-noise variant (expected *not* detected, since the gates require zero violations); a quantitative separator |
| **Innocent cases** (false-positive checks) | Outcome-like names on unrelated columns; a legitimate deterministic predictor declared available; an identifier column; a heavy-tailed legitimate column; a zero-IQR column without a sentinel; structural absence declared correctly |
| **Placeholder and sentinel cases** | Bank Full as is; synthetic columns where −1 is a real value (expected candidate only, never applied); a declaration whose condition is violated (expected exceptions counted) |
| **Before/after cases** | Generated from Bank Full and Adult with known drops, imputations, encodings and deduplications, with and without identity keys. Expected reconciliations are computed by an independent pandas oracle, not the DuckDB engine. |

**Independence and reporting**
- Mutations of the same base dataset are reported as one family, not as independent samples.
- Results are reported as: sensitivity, false flags, abstentions (*not assessable*), unsupported cases and unsearched scope, each separately.
- An unassessed case is never counted as a correct negative.
- The report states what the benchmark population supports. It does not establish external validity.

## 4. Delivery and verification

**Two slices, verified at the close of each:**
- **3A.** Context declarations, the contextual block, candidates, interpreted populations, availability findings, the dependency search, app and report surfaces, and the qualification benchmark for these.
- **3B.** The before/after preset, the reconciliation and lineage report, the app mode, and its benchmark cases.

**Verification**
- **Unchanged numbers:** comma outputs, Bank Full (69.0 · Elevated), and the legacy classification `analyze()` dict, which must be identical.
- **Frozen fixtures:** the only change is the additive `contextual` block. The guarded re-freeze technique is reused.
- **New tests:**
  - declaration validation, sealing and invalidation
  - raw evidence never altered
  - every interpreted number checked against an independent pandas recomputation
  - the dependency gates
  - before/after reconciliation against the pandas oracle
- **Benchmark:** run once at each slice's close, with results written to `validation/ws3/results/`.
- **Full suite** and API/classic parity.
- **Browser pass:** Configure context with Bank Full, the four modules, the before/after mode, and phone width.

## 5. Limits

- **Candidate rules are heuristics.** They only suggest; a wrong suggestion costs one ignored click, never a changed number.
- **The dependency search finds exact copies, separators and functional proxies within its scope.** Noisy or multi-feature leakage beyond that scope is listed as unsearched, not ruled out.
- **Availability is only as good as your declaration.** DataTrust records it and checks consistency; it cannot observe when a value became known. M5 covers that from time data.
- **Lineage needs identity keys.** Without them, before/after stays aggregate.
- **Scoring is unchanged.** Whether a future, separately qualified methodology should use contextual evidence remains your later decision, as the plan states.

## 6. Questions for you

1. **Declarations change nothing analytical.** Should they produce only a separate, interpreted view beside the untouched raw evidence and score (recommended, because it preserves the legacy contract and the raw evidence)? Or should declared placeholders also flow into the existing missingness evidence for non-legacy tasks?
2. **Dependency search default.** Should it run by default for classification within its bounds (recommended, since it is cheap, evidence-only and needed to catch neutral-name copies)? Or only when you opt in?
3. **Candidate suggestions.** Should the fixed candidate rules show suggestions automatically on every run (recommended)? Or only when you open the Context section?
4. **Delivery.** Should I build 3A then 3B with a review pause between them (recommended, because 3A sets the declaration model that 3B's transformations reuse)? Or both in one go?

## 7. Implementation record (2026-10-20)

**Contracts**
- `ContextOptions`, `ColumnContext` and `DependencyLimits` (`context_v1`) are a keyword-only `AnalysisConfig.context`.
- An absent context is omitted from every record, the same way the comma delimiter is. M3 specification fingerprints, M4 manifests and canonical JSON are therefore unchanged when nothing is declared.
- When a context is declared, it enters the M3 fingerprint and the core confirmation seal (`context_seal`).
- Regression's `feature_availability` stays authoritative; conflicting declarations are refused.

**Engine** (`src/datatrust/contextual.py`)
- Conservative candidate rules (`candidate_rules_v1`).
- Declarations with the rows they cover.
- Applicable populations, built with the existing `finite_numeric_evidence`.
- Condition exceptions with row references.
- Cross-column co-occurrence of codes.
- The bounded dependency search, using M4's gates and a quantitative separation check.
- Findings, kept in `contextual.findings` with `version: context_v1`. Legacy findings, `to_legacy_dict` and scores are untouched.
- The stage runs as an optional check: a deadline records `contextual_evidence` as skipped and the block as `not_completed`. Declarations that name unknown columns fail loudly.

**Before/after** (`src/datatrust/before_after.py`)
- The `ComparisonSpec(preset="before_after", transformations=…)` preset runs on the versions engine (Before is reference, After is current).
- Measurement `<before>:<after>.before_after` holds declared, observed, lineage and pipeline-use statements, kept separate.
- Five findings, each with guidance entries.
- `spec_record` keeps splits and versions records unchanged.

**Surfaces**
- The guidance catalogue has 9 new entries, and the scope wording reflects what was declared and searched.
- In the app:
  - Contextual findings appear in their tiles with a *Context* badge.
  - Gaps, Outliers and Leakage gain contextual facts.
  - Configure has the Context panel, backed by the `GET /core/job/context` suggestion endpoint.
  - M4 has the *Before and after preprocessing* mode, its tile and a transformations field.
- Reports gain *Context and declarations*; M4 reports gain *Reconciliation and lineage*.

**Qualification (frozen benchmark, 29 cases)**
- All 29 agree with their frozen expectations.
- Dependency search: 4 of 4 constructed leaks detected, 0 false flags among 5 innocent cases.
- The 2 % noisy copy is missed, as designed.
- Two abstentions: the 60-row sample, and a 999 code below the 1 % floor.
- Bank interpretations and the before/after reconciliations match independent pandas oracles exactly.
- The existing strong-leakage mutation is also independently flagged by the dependency search.

**Verification**
- Full suite: 728 passed, 1 skipped, plus M9 42.
- Canonical core, M3, M4 and M5 outputs are identical to WS2 apart from `contextual` and guidance text; the M5 seal is unchanged.
- API/classic parity holds.
- Bank Full: 69.0 · Elevated, with an identical legacy dict.
- Headless pass covered the Context panel, tiles, report section, PDF, and the before/after result page.

**Deviations**
- Before/after findings use the M4 finding model (titles), consistent with the other M4 findings.
- Availability for regression stays in its existing form section; the Context panel omits it there to avoid two sources.
