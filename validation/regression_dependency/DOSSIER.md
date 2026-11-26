# J2 — Regression feature→target dependency search: method and validation dossier

**Stage:** 6B (J2), research and validation only. **Status:** for the founder's decision. **No product code was written or changed.**
**Method proposed:** `regression_dependency_v1`, opt-in, evidence only.
**Date:** 2026-11-25.

Every number here comes from `validate.py` and `fixtures.py` in this folder. The full tables are in `results/tables.md` and the raw records in `results/results.json`. Both are byte-identical across reruns (see §9).

---

## 0. Summary and recommendation

| Question | Answer (evidence) |
|---|---|
| Does the permutation null stay at 0 flags? | **Yes: 0 flags in 43,500 permuted feature checks** (77 datasets × 100 seeds, every corpus). The tolerant variants also give 0. |
| False positives on retained cases? | **0.** The 108 feature checks over 23 retained regression and M3 datasets raise 4 flags. Hand review shows all 4 are real monotone relationships built into synthetic diagnostic fixtures. That is 3.70 flags and 0 false flags per 100 features. |
| Precision and recall on planted relationships? | Strict v1: precision **1.00** (18 TP, 0 FP). Recall is **0.93 on clean plants** (14/15), 0.27 under 0.1%-of-sd measurement noise, and **0 under 1% label noise**. Overall recall is 0.40 (18/45). |
| What do the gates buy? | With no support gates and no identifier gate, the same search raises **12,801 flags on pure noise** and 94 false flags on the positive corpus. Either the identifier gate or the singleton rule (m ≥ 2) alone brings the null back to 0. |
| Budget | Fits the existing `DependencyLimits` (64 features, 128 checks, 2e8 row work) at one grouped pass per feature–target pair. The largest retained case (bike_hour) uses 0.14% of the row-work limit. |
| Byte-identity when off | Achievable, but four product touchpoints need care (§5.2). Adding a plain dataclass field would break it, because `m3.py:20` and `api_web.py:98` serialize `RegressionOptions` whole. |

**Recommendation: approve `regression_dependency_v1` with four strict families, opt-in only:**
- categorical determination
- target interval coding
- strict monotone
- monotone step

Use k = 5 and m = 5 with the 80% row share, the identifier gate and the redundancy rule. **Do not include the tolerant ("near") variants in v1.** They lift noisy recall (0.27 → 0.60) and stayed null-clean here. But a "nearly determines" claim needs a larger real-world negative corpus than this dossier has (§7, risk R2). The decisions that remain the founder's are in §8.

---

## 1. The gap

- `regression.py:61` searches **numeric features only**, and only three exact forms: `exact_copy`, `affine_identity` and `pair_sum` (`regression.py:126-248`).
- A text feature that determines the target is **never examined** in regression, for example a product code with a price per code.
- A monotone non-linear recoding is never examined either: log, rank, reciprocal, a cube, or a step/bin of a feature.
- A feature that is a **binned copy of the target** is never examined. Examples are an income band when predicting income, or a decile number.
- The classification dependency search (`contextual.py:191-234`) does handle categorical determination. It runs only for single-target classification (`contextual.py:363-368`), and its regression branch says so explicitly.
- M4's categorical proxy check (`m4_diagnostics.py:376-381`) also only targets classification and multilabel tasks.

The positive corpus shows the gap concretely. On all 46 planted non-affine fixtures, the existing search reports **"none"**. It finds only the affine control (`target = 3·x + 2`), see `results/tables.md` "Per fixture".

---

## 2. Method specification: `regression_dependency_v1`

### 2.1 Population and target gates
- **Rows considered:** finite target values, as in `relationship_steps`. For each feature, the matched rows are those with a finite target and the feature present: finite if numeric, non-null otherwise.
- **Not assessable:** a target with no finite values or fewer than 5 distinct finite values (`ACTION_SUPPORT["minimum_distinct_targets"]`). This is disclosed, and nothing is searched.
- **Categorical families:** matched rows ≥ 100 and matched/finite-target coverage ≥ 80%. These are `contextual.GATES["min_matched_rows"]` and `["min_coverage"]`. They also need ≥ 5 distinct targets among the matched rows.
- **Monotone family:**
  - matched rows ≥ 30 (`ACTION_SUPPORT["minimum_overlap"]`)
  - coverage ≥ 80%
  - ≥ 20 distinct feature values
  - ≥ 5 distinct targets

### 2.2 Order and budget
- **Feature order:** the same idea as `relationship_steps`. Features whose names share a token with the target, or carry an outcome cue, go first, then file order.
- **Budget:** the existing `DependencyLimits` (§6). Each feature–target pair is one check and adds the row count to row work, the same accounting as `contextual.py:208`.
- **Bounded runs:** when a limit is reached, the status is `bounded` and the unsearched features are listed by name. One budget is shared across all outputs of a run.

### 2.3 Identifier handling (categorical families)
A feature is excluded from categorical determination and from interval coding when any of these holds, evaluated on the matched rows:

| Reason | Rule | Source |
|---|---|---|
| `declared_identifier` | declared identifier role | roles |
| `R-ID-1` | name token in {id, identifier, uuid, guid, key, index} **and** distinct ≥ 98% of matched rows | plan R-ID-1; `annotations.py:247`, `m4_diagnostics.py:134` (0.98) |
| `R-ID-2` | unique in every matched row | plan R-ID-2 |
| `near_unique` | distinct ≥ 50% of matched rows, unless declared categorical | plan J2 |

- **Monotone family:** only `R-ID-1` and declared identifiers are excluded. A continuous measurement is naturally near-unique and must stay searchable.
- **Disclosure:** every exclusion is disclosed with counts by reason and by storage type. In the negative corpus, 40 features were excluded from the categorical families, and 2 of them are text columns (bike_day `dteday` in both variants). The rest are continuous numeric measurements, which are still searched for monotone mappings.
- **Proposed disclosure sentence:** "*N* features were not searched for categorical determination: *a* identifier-like, *b* near-unique (of which *c* are numeric measurements, still searched for monotone mappings)."

### 2.4 Families

All three families come from **one grouped pass** over the matched rows, grouped by exact feature value: per value, its size, distinct targets, min, max and first target.

**F1 — categorical determination** (any storage type; text compared as strings, numeric as exact values):
- every feature value carries exactly one target value (0 violating categories, **singletons included**: a singleton cannot violate but cannot support either);
- **repeated support:** at least **k = 5** categories with **≥ m = 5 rows** each, and **≥ 80% of matched rows** in those categories. Categories with fewer than m rows, and singletons in particular, never count toward k or the 80% share;
- the population gates of §2.1.

This extends `contextual.GATES`. That rule requires every category to have ≥ 5 rows, which fails a lookup table with a long tail of rare products. Here the long-tail fixture is found (`lookup_longtail_k60`), while the context_v1 rule (ablation A3) loses it.

**F2 — target interval coding** (the feature looks binned from the target):
- after sorting categories by target minimum, each category's target range lies strictly below the next (`max_i < min_{i+1}`; a tie across categories breaks it);
- the same repeated support and population gates as F1;
- reported only when F1 does not hold. F1 implies F2 whenever its mapped values are distinct.

This reuses the `quantitative_class_separation` idea (`contextual.py:210-220`) with roles swapped: the feature's categories partition the target, instead of target classes partitioning a feature.

**F3 — monotone mapping** (numeric features only, ≥ 20 distinct values). Ties are handled explicitly:
- **A tie in the feature with different targets breaks the mapping.** This is reported as `feature_tie_with_different_targets`, with the number of conflicting values. For example, the `sum` case's `b = y − √y` repeats 0 for y = 0 and y = 1, so it is not flagged.
- **A tie in the feature with the same target is allowed:** it is still a function. The feature tie groups are counted.
- **Strict:** the mapped target values, ordered by feature value, are strictly increasing or strictly decreasing. **Both directions are tested.**
- **A tie in the target across distinct feature values breaks strictness.** It is reported as `target_ties_across_feature_values`. Such a mapping qualifies only as a **step**: weakly monotone in one direction, with repeated support on the **target levels** (≥ 5 levels with ≥ 5 rows each, ≥ 80% of rows in them). This covers y = bin(x), such as a tariff tier from a quantity.
- The form is never named. The wording says "the form of the function is not identified".

**Redundancy rule:** a feature that the existing search already verified as `exact_copy` or `affine_identity` is not tested for monotonicity. The block records it as `covered_by_existing_relationship`. Without this rule (ablation A5), the copy and affine fixtures are double-reported: 6 flags instead of 4.

### 2.5 Severity and wording (monotone ≠ leakage)

Severity depends only on declared availability. Any declaration in `RegressionOptions.feature_availability` or context availability counts.

| Declared availability | Severity | Finding code |
|---|---|---|
| unknown (default) | **Moderate** (review) | `regression_dependency_availability_unknown` |
| unavailable at prediction | **High** | `regression_dependency_unavailable` |
| available at prediction | **Low** | `regression_dependency_declared_available` |

Each sentence has three parts:
1. the observation, with rows and coverage;
2. a family caveat, which for monotone reads "not by itself leakage: unit conversions, cumulative quantities and deterministic pricing rules are monotone";
3. an availability clause.

Wording generated by the prototype:

> **Moderate:** product determines target in this file: each of its 5 supported categories (at least 5 rows each) carries exactly one target value (1,000 rows, 100.0% of finite targets). A deterministic rule can be legitimate (a price list, a lookup table). Whether this is leakage or a legitimate rule depends on when product becomes known; declare its availability.

> **High:** band records target in ranges: its 5 supported categories occupy non-overlapping target intervals (1,000 rows, 100.0% of finite targets), as a feature binned from the target would. A feature can separate the target legitimately, or be derived from it. You declared band unavailable at the prediction point, so evaluation that uses it is invalid for the declared objective.

> **Moderate (retained case `missing_nonfinite`):** outcome is a strictly increasing function of input over 97 distinct values (97 rows, 100.0% of finite targets). The form of the function is not identified. A monotone relationship is not by itself leakage: unit conversions, cumulative quantities and deterministic pricing rules are monotone. Whether this is leakage or a legitimate rule depends on when input becomes known; declare its availability.

> **Low:** target is a non-decreasing step function of x: over 1000 distinct values, each value carries one target value and the values never reverse order (1,000 rows, 100.0% of finite targets). A monotone relationship is not by itself leakage … You declared x available at the prediction point; a legitimate deterministic rule leaves little for a model to learn. Verify the declaration and that the rule holds outside this file.

- **No leakage claim without declared unavailability:** the word "leakage" appears only as a possibility until availability is declared, and never as a conclusion.
- **No score or legacy finding changes.** Findings carry `version: regression_dependency_v1` and `evidence_type: contextual_review`, like context_v1.
- **Not claimed:** model use, causality, provenance, or anything about relationships outside the searched families. Two-feature joint determination, for example, is not searched.

> **Decision point D3.** Existing regression relationship findings emit **nothing** for an `available_at_prediction` relationship (`risks.py:464-470` loops only over unavailable and unknown). The brief asks for **Low**, which matches the classification context_v1 (`contextual.py:268-272`). The prototype follows the brief. If approved, J2 regression findings would treat "available" differently from the existing copy/affine/sum findings in the same report.

---

## 3. Corpora

| Corpus | What | Datasets | Feature checks (observed) |
|---|---|---|---|
| **Negative** | Every retained regression and M3 input on disk: the 13 M2 mutations (`validation/regression/data/mutations`), the 2 presentation CSVs, concrete, bike hour/day (with and without components), M3 energy (2 outputs) and linnerud (3 outputs), and the annotation regression input. Mapped dashboard cases: `regression_sum`, `regression_bounded` (= sum.csv), `regression_constraint_union`, `regression_rounded_legitimate`, `regression_partial`, `regression_concrete`, `bike_hour`, `multioutput_energy`, `multioutput_linnerud`, `annotation_regression_single`. | 23 | 108 |
| **Stress** | M3 scene with `Att1` as a **pseudo-target** (scene has no regression target; labels excluded). It is used only for width and bounding. | 1 | 64 (229 unsearched, bounded) |
| **Positive** | 47 planted fixtures, each with 1 planted feature and 4 noise features (normal, 12-level text, 10-level code, lognormal). The plants are lookups (5/12/40/60 long-tail categories, 10% missing, numeric codes), binned targets (quintile text, decile integer, custom brackets), and monotone transforms (log, rank with ties, reciprocal, cube, floor-step). Each comes in 3 noise versions: **none**, **meas** (target + N(0, 0.001·sd)) and **label1** (1% of rows get another row's target, or a wrong band). Two more fixtures are scored separately: one below support by design and one affine control. | 47 | 235 |
| **Hard nulls** | Independent targets shaped to provoke chance determination: a 90%-zero target, Poisson(1), 5 uniform levels at n = 100, a continuous target with categories of exactly 5 rows, a 96%-zero target, and a 20-value feature at n = 60. Three of them also carry `row_id` (R-ID-1), `account_key` (2 rows per key) and many small categories. | 6 | 28 |

- **Not re-run:** `multioutput_linnerud_masked` and `multioutput_regression_empty`, whose input CSVs are not retained on disk. Both sit below every row gate by construction: 20 rows, and no finite targets.
- **Fixture integrity:** `fixtures/manifest.json` records the SHA-256 of each fixture and of the generator.

---

## 4. Validation results

### 4.1 Permutation null (target permuted over the same columns, 100 seeds, redundancy rule off)

| Corpus | Feature checks | **Proposed** | A1 no identifier gate | A2 singletons count | A3 context_v1 support | A4 naive (no gates) | A6 no identifier gate + singletons count | Tolerant (near) |
|---|---|---|---|---|---|---|---|---|
| negative | 10,800 | **0** | 0 | 0 | 0 | 1,501 | 1,501 | 0 |
| stress | 6,400 | **0** | 0 | 0 | 0 | 0 | 0 | 0 |
| positive | 23,500 | **0** | 0 | 0 | 0 | 10,700 | 10,700 | 0 |
| hard nulls | 2,800 | **0** | 0 | 0 | 0 | 600 | 600 | 0 |
| **all** | **43,500** | **0** | 0 | 0 | 0 | 12,801 | 12,801 | 0 |

- **Acceptance criterion met: 0 flags across 100 seeds.** By the rule of three, the 95% upper bound on the chance-flag rate is 3/43,500, which is **< 0.007 flags per 100 feature checks**.
- **Defense in depth:** removing the identifier gate alone (A1) or the singleton rule alone (A2) still gives 0. Removing both (A6) gives 12,801: every unique-valued column trivially "determines" any target.

### 4.2 Negative corpus (retained cases, observed data)

| Dataset | Target | Flags (strict) | Hand review |
|---|---|---|---|
| mutation:sum (= `regression_sum`, `regression_bounded`) | outcome | `a` monotone/strict | **True by construction:** a = √outcome on 0..99. The existing search reports `outcome = a + b`. |
| mutation:missing_nonfinite | outcome | `input` monotone/strict | **True by construction:** input = y² on the 97 finite y ≥ 0. |
| mutation:constraint_union (= `regression_constraint_union`) | outcome | `input` monotone/strict | **True by construction:** input = i², and the two edited rows (−1, −0.5) keep the order. |
| presentation:partial (= `regression_partial`) | outcome | `qa_optional_failure` monotone/strict | **True by construction:** = outcome² on 0..39. |
| concrete, bike_hour (± components), bike_day (± components), energy (2 outputs), linnerud (3 outputs), annotation_regression, and 10 other mutations | — | 0 | — |

- **Totals:** 108 feature checks, **4 flags, 4 reviewed true, 0 false**. That is 3.70 flags per 100 features and **0 false flags per 100 features**, with a 95% upper bound of 3/108 ≈ **2.8 per 100 features**.
- **Real datasets give 0 flags.** bike_hour and bike_day keep their known pair sum (`cnt = casual + registered`), which J2 correctly does not re-report: it is not a single-feature relationship.
- **Near flags:** one tolerant flag, `sum.b`, a near-monotone function that is real.
- **Not assessable:**
  - `presentation:ambiguous`: its target has 4 distinct values.
  - `mutation:constant`: its target is constant.
- **Linnerud** (20 rows) is assessed, but every family fails its row gate. **Scene** is bounded at 64 features and gives 0 flags.
- **Effect of turning it on:** if enabled on these retained cases, 4 of them would gain one Moderate review finding each. That is why the method must be opt-in, and why the stored outputs must not change while it is off.

### 4.3 Positive corpus

| Method | Stratum | n | TP | FN | FP | Precision | Recall | Flags / 100 features | False flags / 100 features |
|---|---|---|---|---|---|---|---|---|---|
| **strict (v1)** | all | 45 | 18 | 27 | 0 | **1.00** | 0.40 | 8.0 | 0 |
| strict | no noise | 15 | 14 | 1 | 0 | 1.00 | **0.93** | 18.7 | 0 |
| strict | measurement noise | 15 | 4 | 11 | 0 | 1.00 | 0.27 | 5.3 | 0 |
| strict | 1% label noise | 15 | 0 | 15 | 0 | – | **0** | 0 | 0 |
| strict | categorical determination | 21 | 10 | 11 | 0 | 1.00 | 0.48 | 9.5 | 0 |
| strict | target interval coding | 9 | 3 | 6 | 0 | 1.00 | 0.33 | 6.7 | 0 |
| strict | monotone mapping | 15 | 5 | 10 | 0 | 1.00 | 0.33 | 6.7 | 0 |
| strict + tolerant | all | 45 | 23 | 22 | 0 | 1.00 | 0.51 | 10.2 | 0 |
| strict + tolerant | measurement noise | 15 | 9 | 6 | 0 | 1.00 | 0.60 | 12.0 | 0 |
| strict + tolerant | 1% label noise | 15 | 0 | 15 | 0 | – | 0 | 0 | 0 |

**What each result means:**
- **Clean plants:** 14 of 15 are found, each in its intended family. This includes rank with ties and the floor-step as `monotone_mapping/step`. The one miss is `lookup_k40_n200`: 40 categories over 200 rows put only 74.5% of rows in categories with ≥ 5 rows, below the 80% gate. It is missed by design at m = 5, and found at m ≤ 3 (§4.4).
- **Measurement noise:** the 4 strict hits are lookups with 5–12 categories, where a 0.1%-of-sd perturbation leaves category ranges disjoint. They are reported as **interval coding, not determination**. That is a true observation, but the family name is weaker than reality. The wording is therefore neutral ("separate the target legitimately, or be derived from it").
- **Label noise:** 1% label noise defeats every exact method, strict and tolerant. This is the main recall limitation (R1).
- **Noise features:** 0 of 180 scored noise features were flagged, a 95% upper bound of 1.7 per 100 features.
- **Excluded from scoring:**
  - `lookup_sparse_k80_n200` (2.5 rows per category, 21.5% of rows supported): correctly not flagged.
  - `control_affine`: found by the existing search, and correctly not re-flagged by J2.
- **Combined strict precision:** positive + negative + stress gives 22 TP and 0 FP, a precision of **1.00**.

### 4.4 Choosing k and m

The repeated-support grid uses the 80% row share. The null is summed over all 77 datasets × 100 seeds.

| k | m | Null: proposal | Null: identifier gate off | Null: identifier gate off + tolerant | Clean categorical recall | All-noise categorical recall |
|---|---|---|---|---|---|---|
| any | 1 | 0 | **12,801** | **12,816** | 10/10 (k ≤ 5) | 14/30 |
| 1–5 | 2 | 0 | 0 | 0 | 10/10 | 14/30 |
| 1–5 | 3 | 0 | 0 | 0 | 10/10 | 14/30 |
| **5** | **5** | **0** | **0** | **0** | **9/10** | **13/30** |
| 1–5 | 8 | 0 | 0 | 0 | 9/10 | 13/30 |
| 8 | 2–3 | 0 | 0 | 0 | 7/10 | 10/30 |
| 8 | 5–8 | 0 | 0 | 0 | 6/10 | 9/30 |

The negative corpus has 4 flags at every grid point; they are the monotone flags, which do not depend on k or m. Full grid: `results/tables.md`.

- **m is what matters for the null.** At m = 1, singletons count as support and the null explodes as soon as the identifier gate is off. **m ≥ 2 brings it to 0 in every corpus.**
- **m = 5 is proposed** for three reasons:
  1. it equals `contextual.GATES["min_category_support"]`, so one support rule serves both tasks;
  2. 5 rows agreeing on one exact target value is evidence, while 2 agreeing rows often is not (a pair of duplicated records);
  3. it leaves margin, which matters most for the tolerant variants, where small categories inflate η² (§7, R2).

  The cost is measured: one clean fixture (`lookup_k40_n200`). **m = 3 recovers it with 0 null flags here.** That is a legitimate alternative (decision D1).
- **k has no effect on the null** (0 for all k with m ≥ 2). It only costs recall above 5: k = 8 loses the 5-category lookups. **k = 5 is proposed for coherence:**
  - if fewer than 5 supported categories held ≥ 80% of rows, those rows would take at most 4 target values;
  - regression's own `ACTION_SUPPORT` treats fewer than 5 distinct targets as not action-eligible.

  So k = 5 is the smallest value consistent with the regression gates. It means a 3-tier price table is **not** flagged (R5).
- **Honest limit:** the hard nulls did not produce chance purity even at m = 2. Strict purity over **every** category, singletons included, is itself very restrictive. The null therefore shows that m = 5 is *safe*, not that it is *necessary*.

### 4.5 Ablations on the positive corpus

| Variant | Recall (all) | Recall (clean) | False flags |
|---|---|---|---|
| **proposed** | 0.40 | 0.93 | 0 |
| A1 no identifier gate | 0.40 | 0.93 | 0 |
| A2 singletons count | 0.44 | 1.00 | 0 |
| A3 context_v1 support (every category ≥ 5) | 0.38 | 0.87 | 0 |
| A4 naive (no gates) | 0.62 | 1.00 | **94** |
| A5 no redundancy rule | 0.40 | 0.93 | 0 |

- **A2** gains recall here, but its null protection rests entirely on the identifier gate. A6 shows what happens if that gate misses a case.
- **A3** loses the long-tail lookup. That is why v1 relaxes context_v1's "every category" rule into k/m/80%.

---

## 5. Versioning design

### 5.1 Contract
- **Python:**
  - `RegressionOptions.dependency_search: RegressionDependencyOptions | None = None` (keyword-only), where `RegressionDependencyOptions(limits: DependencyLimits = DependencyLimits())`;
  - `None` means off;
  - `from_dict` accepts `"dependency_search": true | {"limits": {...}}`. It currently rejects unknown keys (`contracts.py:391`).
- **CLI:** `datatrust audit … --task regression --regression-dependency-search` sets it. Config JSON gets the equivalent key.
- **UI:** an Advanced-section toggle, off by default, beside feature availability.
- **When off:** `tabular_regression_v1` and its output are unchanged **byte for byte**. No check outcome, no block and no key is added.
- **When on:** the methodology stays `tabular_regression_v1`, and `profile.regression.dependency_search` is a self-describing block. The prototype's `search()` returns exactly this shape:
  ```
  {method_id: "regression_dependency_v1", status: completed | bounded | not_assessable | partial,
   gates: {...all thresholds...}, limits: {max_features, max_checks, max_row_work},
   checks: [per feature: matched, coverage, distinct values, identifier exclusion, per-family stats and reason],
   flags: [feature, family, form, availability, severity, finding_code, row refs, wording],
   identifier_exclusions: {reason: [columns]}, identifier_exclusion_counts, covered_by_relationships,
   unsearched_features, budget_used: {features, checks, row_work},
   meaning: "Evidence only. No flag means none found within the searched families and gates; unsearched relationships are unknown."}
  ```
  It comes with one `CheckOutcome("regression_dependency_search", …)` and findings with `version: regression_dependency_v1`.
- **Multi-output (M3):** the same block per output, with one shared budget. `m3.py:42` currently passes only quantitative-geometry features to the relationship search, so J2 there must receive `roles["features"]` to reach text columns.
- **Default-on** would require `tabular_regression_v2` and a new founder decision. v1 results would never be re-labelled.

### 5.2 Byte-identity touchpoints found in this research
These are what an implementation must handle. Each is an acceptance test.

1. `m3.py:20` writes `asdict(config.regression)` into `profile.declarations`. `api_web.py:98` writes `plain(config.regression)`. **Any** new dataclass field, even one defaulting to `None`, adds a key. Serialization must omit `dependency_search` when it is `None`, for example with a `RegressionOptions.to_dict()` used at both sites.
2. `web.py:280` rebuilds `RegressionOptions(expectations, availability, existing.relation_limits)` positionally. It would silently drop the toggle (and already drops `expectations_by_target`). It must pass the option through.
3. `contracts.py:391` `from_dict` must accept the new key and keep rejecting every other unknown key.
4. **Acceptance test:** re-run every retained regression and M3 case (each `case.json` stores `analysis_sha256`) with the option off, and require identical hashes under the existing harness normalisation. Then run with it on, and require exactly the 4 flags of §4.2 on the cases listed there, and 0 elsewhere.

---

## 6. Budget

- **Limits:** the existing `DependencyLimits` defaults, `max_features = 64`, `max_checks = 128`, `max_row_work = 2e8`. One limits object serves all outputs.
- **Cost:** one grouped pass per feature–target pair is one check, and adds the row count to row work. All three families share that pass.
- **Retained cases:**
  - the largest is bike_hour: 16 checks and 278,064 row work, **0.139% of the limit**;
  - multi-output energy: 16 checks for 8 features × 2 outputs;
  - scene stress: bounded at 64 features (154,048 row work), with 229 features disclosed as unsearched.
- **Where the limits bind:**
  - 64 features × 2 outputs fills the 128 checks exactly;
  - at 64 features, row work binds above 3.125M rows, after which fewer features are searched and the status is `bounded`.
- **Wall time** (machine-dependent, `results/timing.json`): 1M rows × 4 features (4e6 row work) took 1.06 s. Extrapolated linearly, the full 2e8 bound is about 55 s single-threaded in pandas. That is acceptable for an opt-in search, but the M4/DuckDB path should push the GROUP BY into SQL, as `m4_diagnostics.py:370-381` already does for categorical proxies.

---

## 7. Open risks

| # | Risk | Evidence | Mitigation |
|---|---|---|---|
| R1 | **Noisy relationships are missed.** Strict recall is 0 under 1% label noise and 0.27 under 0.1%-of-sd measurement noise. | §4.3 | Disclose that "no flag" means none *exact* within the searched families (the block's `meaning`). Tolerant variants are a v2 candidate. |
| R2 | **The real-world negative corpus is small.** 108 checks from 6 real sources, giving a 95% upper bound of 2.8 false flags per 100 features. The tolerant variants (η² ≥ 0.999, \|Spearman\| ≥ 0.999) were null-clean, but real data with very strong legitimate relationships was not tested. | §4.2 | Keep tolerant variants out of v1. Before any v2, add real cases with known strong legitimate predictors. |
| R3 | **Family naming under noise.** A lookup with slight target noise is reported as interval coding. | §4.3 | Neutral wording, so the sentence stays true either way. |
| R4 | **Synthetic diagnostic fixtures gain flags.** Four retained mutations contain monotone relationships by construction. | §4.2 | Opt-in only; off means byte-identical; the acceptance test pins the 4. |
| R5 | **Small rule tables are invisible.** A price table with fewer than 5 supported categories is not flagged (k = 5). | §4.4 | Disclosed in the gates. Lowering k needs a decision, because it conflicts with `minimum_distinct_targets`. |
| R6 | **Row order.** A numeric R-ID-2 sequence column (bike `instant`) is still searched for monotonicity. In a file sorted by the target it would be flagged: true, but really a row-order observation. | design | The wording already avoids "leakage". An implementation could add "row order may encode the target" when the feature is R-ID-2 and integer-stepped. |
| R7 | **Exact equality.** Purity and ordering use exact values. Floating-point recomputation of a rule could break purity, while recorded rounding does not. | design | The same stance as `exact_copy`. A tolerance like `regression.RTOL` could be added later as v2. |
| R8 | **Only single-feature dependencies.** Joint determination by two categorical columns, or a monotone function of a sum, is not searched. | scope | The block's `meaning` says unsearched relationships are unknown. |
| R9 | **Availability semantics differ.** Available maps to Low here, versus no finding in the existing regression relationships. | §2.5 | Decision D3. |
| R10 | **The serialization touchpoints** (§5.2) would break byte-identity if missed. | code reading | Acceptance tests 1–4. |

---

## 8. Decisions for the founder

- **D0 — Approve or reject** implementing `regression_dependency_v1` as specified: strict families, opt-in, evidence only. **Recommended: approve.**
- **D1 — Support size m:** 5 (recommended; consistent with context_v1, conservative) or 3 (recovers lookups that average about 5 rows per category; 0 null flags here).
- **D2 — Tolerant variants:** excluded from v1 (recommended). They are recorded as a v2 candidate, pending R2.
- **D3 — Severity for declared-available dependencies:** Low, as the brief and context_v1 specify (recommended for consistency with classification), or no finding, as existing regression relationships do today.

---

## 9. Reproduce

From the repository root, using the project virtualenv (the read-only import of `datatrust.regression` needs `duckdb`):

```bash
.venv/bin/python validation/regression_dependency/fixtures.py
```

```bash
.venv/bin/python validation/regression_dependency/validate.py
```

```bash
.venv/bin/python validation/regression_dependency/validate.py --timing
```

| File | Role |
|---|---|
| `prototype.py` | the method: `feature_stats` (one grouped pass), `decide` (gates, ablations), `search` (the versioned block, wording, severity). |
| `fixtures.py` | the positive and hard-null fixtures (seed 20261125), written to `fixtures/` with `fixtures/manifest.json`. |
| `validate.py` | the corpora, the hand review table (`REVIEW`), the null, grid, ablations and tables. It imports `src/datatrust/regression.py` read-only to know copy/affine coverage. |
| `results/results.json`, `results/tables.md` | deterministic outputs: two consecutive runs gave identical files (results.json SHA-256 `ef2f28f4…`, tables.md `f37204ef…`). |
| `results/timing.json` | wall time only; not reproducible. |

Runtime is about 2 minutes. Pinned inputs: prototype.py SHA-256 `4cf09206…`, fixtures manifest SHA-256 `8d2074ce…` (full hashes in `results/tables.md`).
