# Proposal: Workstream 2. Accurate modules and layered reports from existing evidence

**Status:** approved 2026-10-20 (Q1: the versioned JSON block; Q2: per-column contributors, verified against the scoring implementation's own normalisation and rounding rather than assuming points sum to 100 − sub-score; Q3: all slices in one go). Implemented 2026-10-20; see section 7.
**Depends on:** Workstream 1 (outcome states, explicit mapping, provenance), which is complete.
**Unchanged:**
- the UI design, mosaic, layout, type, colours and navigation
- scoring formulas, thresholds and numeric results
- historical artifacts and the legacy direct-API report bytes
- ConfidenceGuard

**No new analysis.** Every sentence added here is derived from evidence that a run already records.

## 1. What I found

Each item below was reproduced on 2026-10-20 against the working tree, mostly on Bank Full (69.0 · Elevated).

### 1.1 Module content in the app

| # | Module | Defect |
|---|---|---|
| C1 | Score | The note says *"The score is the sum of what the other modules found."* It is actually the **mean** of five sub-scores (84.38 for Bank Full), then capped by the lowest triggered guardrail (69.0). Nothing tells the reader the score is a heuristic policy, not a validated estimate. |
| C2 | Gaps · Duplicates · Outliers · Leakage | Each note always says "Feeds the … sub-score", even on regression, unlabeled and M3 runs, which have **no score**. The effect notes are written for classification only. |
| C3 | Gaps | "0 empty cells" is literally true but incomplete. Bank Full's `poutcome` is 81.75 % `unknown`, and `job`, `education` and `contact` also carry `unknown`. The module never says that missingness means *parser-recognised* missing tokens, or that placeholders like these were **not assessed**. |
| C4 | Imbalance | The tile reads **"Moderate · critical"**, mixing two different scales. *Moderate* is the finding's review priority; *critical* means the target-balance sub-score (23.4) triggered a scoring guardrail. Class counts and shares are in the JSON but not shown. |
| C5 | Leakage | The quiet text says *"No column name or value prompts"*. The classification check is name-only (`legacy_name_heuristic`), so "value" is wrong. "Leakage risk 100" also reads as *no leakage*. Bank Full's `duration` is known only after the call, and a name check cannot see that. |
| C6 | Outliers | `pdays` and `previous` have **zero IQR** (q1 = q3), so the legacy policy records `outlier_rate 0.0` and the chart draws them as clean zero bars. Zero here means *fences undefined*, not *no outliers*. |
| C7 | Outliers / feature usability | `default` (98.2 % `no`) is near-constant and costs 8 penalty points (the sub-score is 98.5), but no finding or module text explains this. The score has an **unexplained contributor**. |
| C8 | Outliers | The chart's denominator is unstated. Classification uses *total rows, non-finite included* (`legacy_1.5_iqr`). The other tasks use *finite values* (`finite_1.5_iqr`). Charts show at most 12–16 columns without saying how many were left out. |
| C9 | Duplicates · Conflicts | Equality is never defined: whole parsed rows, target included, versus feature-identical rows with differing labels. How missing values compare in each is not said. |
| C10 | Conflicts · Relationships | Their drawings are **schematic**. Conflicts is never labelled schematic; Relationships only in the chapter. |
| C11 | Time · Text · Images · Documents | In a table run the chapter says *"Time reads time data; this run is a table."* It doesn't say which workflow produces that evidence or that nothing about it was assessed here. |
| C12 | Reports | The tile always says "HTML · PDF · JSON", even when no PDF exists yet. It should show actual artifact states. |
| C13 | Local | It shows elapsed time and rows but not the execution properties: backend, limits, completed or partial. |

### 1.2 Finding guidance

Every core and M3 finding already has `finding`, `evidence`, `modeling_impact` and `recommendation`. They are short, generic, and sometimes prescriptive without conditions. Examples from Bank Full:

- **`target_imbalance`**
  - The recommendation says *"consider resampling, weighting, or collecting more minority examples."*
  - It doesn't first establish class-sensitive evaluation.
  - It gives no conditions for avoiding resampling, such as a calibrated-probability use or grouped and temporal splits.
- **`numeric_outlier_concentration`**
  - The evidence says *"Affected fields: balance, duration, campaign."*
  - The per-field counts, rates and denominators are in the profile but not cited.
  - Facts like `balance` running from −8,019 to 102,127 with 8.3 % negative and 7.8 % zero aren't used.
  - It gives no guidance against capping a legitimate heavy tail.
- **Nothing anywhere separates facts, possible impacts, options and unknowns.**

M4 to M9 findings carry `action`, `next_action` and `limitations`. Their families number about 20 in M4, 20 in M5, 33 in M6, 14 in M7 and 7 statuses in M9. None says when *not* to act, or how to check the consequence of acting.

### 1.3 Reports

The classification report (8 sections) and the regression, unlabeled and M3 reports (8 each) already contain:
- an executive summary
- priority actions
- technical sections
- an appendix

They lack:
1. **A preprocessing-guidance layer** covering options, prerequisites, alternatives, contraindications and verification.
2. **An executive statement of completed scope and unresolved unknowns.** Examples: semantic placeholders were not assessed; prediction-time availability was not verified.
3. **A thresholds and policy table**, such as the 5 % IQR review rate, the 75 % majority threshold, the 25 / 50 % missingness bands and the 10 % duplicate guardrail. These live only in code.
4. **The feature-usability contributors** (C7) and **zero-IQR qualification** (C6) in the technical layer.

The app's classification report is the legacy body plus provenance. Its direct legacy API render must keep its established bytes.

## 2. Design

### 2.1 One versioned guidance record per finding, in canonical JSON

New results gain a single top-level, additive block:

```json
"guidance": {
  "version": "finding_guidance_v1",
  "items": {
    "<finding code or family>": {
      "observed":    ["balance: 4,729 of 45,211 rows (10.46 %) outside 1.5×IQR fences [−1,962, 3,462]; min −8,019, max 102,127; 3,766 negative, 3,514 zero"],
      "impact":      ["…possible, conditional consequences…"],
      "investigate": ["…what to look at first…"],
      "options":     [{"option": "…", "prerequisites": "…", "avoid_when": "…", "verify": "…"}],
      "unknowns":    ["…what this run did not assess…"]
    }
  }
}
```

**How it is built**
- `src/datatrust/guidance.py` holds one small builder per finding code (core and M3) or family (M4–M9).
- Each builder receives the finding and the result. Every number in `observed` is read from the canonical profile or evidence, with its population and denominator.
- Builders choose their wording conditionally from that evidence. Examples:
  - a heavy tail versus negative values
  - zero IQR
  - a multiclass versus a binary target
  - a declared versus a heuristic availability

**What doesn't change**
- Findings keep their existing fields and wording.
- The legacy classification projection (`to_legacy_dict`) and the direct-API dict stay exactly as they are.

**Why it goes in the JSON**
- JSON, HTML, PDF and the saved view then show the same text from the same bytes.
- Old saved entries, which have no block, say *"Guidance was not recorded by the version that produced this analysis."*

**Boundaries**
- Guidance never prescribes a pipeline, never ranks options as optimal, and never implies an unperformed analysis.
- Every option carries `avoid_when` and `verify`.
- Every item carries `unknowns`.
- Facts, impacts, options and unknowns are separate fields, rendered under separate labels.

**Example: `target_imbalance` on Bank Full**

| Field | Content |
|---|---|
| Observed | `no` 39,922 (88.3 %), `yes` 5,289 (11.7 %), 45,211 labelled rows; majority baseline 88.3 %; ratio 7.55 : 1. |
| Impact | Accuracy can look high while the minority class is missed; default thresholds may suit the majority. |
| Investigate | Whether the observed share matches the deployment population; whether the minority class has enough rows per later split. |
| Option: class-sensitive evaluation | **Prerequisite:** none. Evaluate per-class recall and precision, PR-AUC, and a confusion matrix at the decision threshold. **Avoid when:** never; it changes no data. **Verify:** report the metrics for both classes on a held-out split. |
| Option: class weights or a threshold choice | **Avoid when:** calibrated probabilities are the product, unless you recalibrate. **Verify:** compare per-class metrics and calibration before and after, on the same split. |
| Option: resampling | **Avoid when:** rows are grouped or time-ordered and resampling would cross splits; or before the train/test split. **Verify:** resample only inside training folds, then check minority-class metrics on untouched data. |
| Unknowns | Deployment prevalence and the cost of each error type were not supplied. |

### 2.2 Module content within the existing design

The tiles stay compact; chapters gain at most one short "what to check first" line plus a pointer to the report section.

**Score**
- The note reads: *"Mean of five sub-scores (evidence score 84.38), then capped at 69.0 by the lowest triggered guardrail. A heuristic review policy, not a validated probability of model success."*
- Every triggered guardrail is listed, with the governing one marked.

**Gaps**
- It states the missing-token policy in effect (pandas defaults, `empty_only` or custom tokens) and counts cells and rows with their denominators.
- It adds one fixed sentence: *"Text values such as 'unknown' are data values, not missing, unless declared; their meaning was not assessed."*
- Declarations themselves arrive in WS3.

**Duplicates · Conflicts**
- **Duplicates** means whole parsed rows, target included, with missing values equal to missing. It gives the counts and the group-size distribution.
- **Conflicts** means feature-identical rows with more than one non-missing label.
- Both name what they cannot tell apart: repeated legitimate events versus copies.

**Imbalance**
- It shows class counts and shares; for more than 8 classes, the top 8 plus "other".
- Two separate lines: **Review priority: Moderate**, and **Scoring policy: target-balance sub-score 23.4 ≤ 50 → critical-sub-score guardrail.**
- The mixed label goes.

**Leakage**
- It names the method actually run: names only for classification, declared availability plus bounded relationship search for regression, declared inputs for M3.
- A clear result reads: *"No outcome-like names among 16 features. Whether each feature is available at prediction time was not verified."*
- "Leakage risk 100" is relabelled *"Name-check sub-score 100"*.

**Outliers**
- It states the population per methodology: total rows for the legacy classification policy, finite values elsewhere.
- Zero-IQR columns are drawn as hatched *"fences undefined"* marks, not zero bars, and listed. Their JSON values are unchanged.
- It lists every feature-usability contributor (missingness band, constant, near-constant, high cardinality, IQR band) with its points, which sum to the sub-score.
- It discloses columns left out of the chart.

**Relationships**
- Applies to regression and M3 regression.
- It gives the search method, support thresholds, bounded or exhaustive status, unsearched scope, and the availability status of each relationship.
- The schematic drawing is labelled schematic on the tile too, or drawn from the actual relationship groups when they exist.

**Time · Text · Images · Documents** (in a table run)
- *"Not part of this analysis. Temporal evidence comes from the Temporal workflow (M5)…"*, and so on for each workflow, with what that workflow would need as input.
- In their own workflows, their hero chapters gain one line each covering inputs supplied, evidence retained, and unresolved or unsearched scope. All of this already exists in their canonical `coverage`.

**Local**
- Backend, materialisation, rows × columns, configured limits, completed or partial, elapsed time.
- Labelled *"Execution property, not a data check"*.

**Reports**
- Actual states: *"HTML ready · JSON ready · PDF on request"* or *"… PDF ready"*.
- For saved entries, what is saved and whether guidance and provenance were recorded.

**Effect notes become mode-aware (C2).** Regression, unlabeled and M3 runs say *"Evidence only: no score is defined for this task."*

**Charts** (bindings and labels only; designs unchanged)
- Imbalance draws every class share.
- The Outliers population and zero-IQR changes above.
- Duplicates says *"N of M groups drawn"*.
- Conflicts, Relationships, Time, Text, Images and Docs say *schematic* wherever they are not data-bound.

### 2.3 Layered reports

The same four layers apply to the classification, regression, unlabeled and M3 reports. Existing sections are reused, and new content goes where it belongs:

1. **Executive understanding.** This is the existing summary, plus a **"Completed scope and open questions"** box. The box covers:
   - what ran
   - what was excluded or not assessed, using WS1's check states
   - the unknowns gathered from all guidance items
   - one qualified conclusion
2. **Technical analysis.** The existing sections, plus:
   - class counts
   - the per-feature outlier table with population, fences, zero-IQR qualification and sign and zero counts
   - feature-usability contributors
   - the missingness policy statement
   - the duplicate and conflict definitions
3. **Preprocessing guidance.** A new section rendered from `guidance`. For each finding: Observed → Possible impact → Investigate first → Options (prerequisites · avoid when · verify) → Unknowns.
4. **Methodology and reproducibility.** The existing disclosure and provenance, plus a **thresholds and policy table** keyed by `methodology_id`. The table is static text that mirrors the constants the methodology uses, and a test checks it against the code.

**The legacy classification report** keeps its established body. The four layers are inserted the way WS1's provenance was, and the direct legacy API keeps its exact bytes.

**M4–M9 reports** gain the guidance layer rendered from `guidance`, and their existing summaries gain the scope and unknowns box. They already contain technical and methodology layers.

## 3. Delivery in three slices, each closed and verified

| Slice | Content | Why first |
|---|---|---|
| **2A** | `guidance.py` framework; all 54 core and M3 codes; the 14 module texts and chart fixes; the four report layers for classification, regression, unlabeled and M3 | It sets the pattern, and Bank Full and Bike exercise it end to end |
| **2B** | M4 and M5 families: guidance and report layers | They use the same builder interface; their findings carry titles and ids, which need a stable key per kind |
| **2C** | M6, M7 and M9 families: guidance, report layers and hero-chapter scope lines | They have the most families, and their keys already exist (`family`, `meaning`) |

I would pause after 2A so you can review the guidance format and tone on real reports before it is repeated about 90 more times.

## 4. Verification (proportionate, following `agents/skills/verify/skills.md`)

**Coverage**
- Every finding code or family that an engine can emit has a guidance builder. This uses the same static plus runtime approach as WS1's `outcome-map` test.

**Fact traceability**
- Every number in `observed` is checked against a value in the canonical profile or evidence for that run.
- Every option has non-empty `prerequisites`, `avoid_when` and `verify`.

**Consistency**
- The HTML and PDF guidance section renders exactly the JSON block.
- The saved view shows the same text.
- Old entries show "not recorded".

**Unchanged numbers**
- Bank Full: statistics, sub-scores, findings and 69.0 · Elevated.
- The comma baseline: the only differences are `guidance` and the report text.
- The legacy direct-API render keeps its bytes.
- Frozen fixtures are re-frozen with WS1's guarded technique. Each case must reproduce its old frozen HTML hash with the pre-change templates before its new hash is recorded.

**Charts**
- The feature-usability contributor points sum to exactly 100 − the sub-score for every validation dataset.
- Zero-IQR columns are never drawn as zero.
- Class shares sum to 100 %.

**Reports**
- One headless pass covers all 14 modules for Bank Full, Bike, an unlabeled run and an M3 annotation run, plus one dense-evidence case and one incomplete case. It checks overflow, clipping and contrast, with no screenshots unless you ask.
- PDFs are checked for every changed report.
- The existing M5 PDF page-count test (8–12 pages) is respected. Any other report that grows past its readability budget is reported to you, not silently trimmed.

**Full suite**
- Run once at the close of each slice.
- Plus API/classic parity.

## 5. Limits of this workstream

- **Guidance is review support, not validated advice.** Its scientific qualification (are these the right options and contraindications?) belongs to the independent qualification programme. Here it is checked only for traceability and internal consistency.
- **No new detection.** Placeholders, sentinels such as `pdays = −1`, and prediction-time availability are only *named as unknowns* here. Detecting and declaring them is Workstream 3.
- **Report length grows.** The guidance layer adds roughly 1–3 PDF pages for a typical run. The plan accepts deeper reports; the page budgets are verified rather than assumed.

## 6. Questions for you

1. **Where guidance lives.** Should it be a versioned top-level `guidance` block in canonical JSON for new results (recommended, because JSON, HTML, PDF and saved views stay identical)? Or presentation-only text derived at render time, with JSON unchanged?
2. **Feature-usability contributors.** Should the app and reports show each column's penalty points, which sum to the sub-score (recommended, because it explains C7)? Or only name the contributing columns?
3. **Delivery.** Should I build in slices 2A → 2B → 2C with a review pause after 2A (recommended)? Or all three slices before one review?

## 7. Implementation record (2026-10-20)

**Guidance**
- `src/datatrust/guidance.py` holds `finding_guidance_v1`:
  - 51 catalogue entries
  - an explicit key for each of the 54 core and M3 codes, 46 M4 and M5 titles, and 20 M6, M7 and M9 families
  - observers that cite only recorded values (core profile fields; M4–M9 finding fields and their referenced evidence records, including M4 measurement pointers)
  - the scope summary and qualified conclusion
  - the classification score explanation
  - the policy tables
- It is computed once, where each result is produced (core, M4 ×2, M5, M6, M7, M9), before each workflow's existing size budget.
- It is stored as a keyword-only `guidance` field and serialized only when present, so older or reloaded results keep their bytes and digests. M9's private binding is unaffected.

**Scoring explanation (Q2)**
- `scoring.feature_usability_contributions` is now the single source the scoring code itself uses, with identical arithmetic.
- The test re-derives every column's points from the profile with an independent oracle. It then applies the implementation's normalisation by feature count, the clamp and the 2-decimal rounding, and requires equality with the recorded sub-score.
- For Bank Full: 24 points ÷ 16 features → 98.5.

**Reports**
- `templates/guidance_layers.html` provides the scope box, the guidance section, the score explanation and the policy table.
- It is included in the regression, unlabeled, M3, M4, M5, M6, M7 and M9 templates.
- It is inserted into the legacy classification body at its section boundaries; the direct legacy API keeps its bytes.

**App**
- **Tile labels:**
  - findings read "<severity> priority"
  - the scoring-policy fact is separate (C4)
  - the leakage sub-score is relabelled "Name-check sub-score" (C5)
- **Mode-aware effect notes (C2).**
- **Module facts:**
  - **Gaps (C3):** the missing-value rule, and the note that placeholders were not assessed
  - **Duplicates and Conflicts (C9):** their equality definitions
  - **Imbalance (C4):** class counts and shares
  - **Leakage (C5):** the method that ran, and what it does not verify
  - **Outliers (C6, C7, C8):**
    - the population
    - the zero-IQR list, with assessed counts excluding those columns
    - usability points and contributors
    - numeric feature columns only (this also fixed a WS1 count that included text columns)
  - **Local (C13):** status, materialisation and limits
  - **Reports (C12):** actual files
- **Score note (C1):** the mean of five sub-scores, then capped, as a heuristic.
- **Time, Text, Images and Docs chapters (C11):** name their workflow.
- **"Check first" line** in each finding chapter.
- **The recorded scope conclusion** on core, M3 and every M4–M9 result page, live and saved.
- **Charts:**
  - Imbalance draws every class share
  - Outliers marks zero-IQR columns as dashed "IQR 0", states its population and the columns drawn, and no longer draws text columns
  - Duplicates states the groups drawn
  - every non-data drawing is labelled schematic
- **Adapter fix:** a check that is `blocked` takes precedence over `skipped`. M5 records precondition blocks that way, so they read as exclusions, not interruptions.

**Tests**
- New: `tests/test_guidance.py` (19) covering:
  - catalogue coverage by AST and source scan
  - option completeness
  - fact traceability (every number in every observed line must be a value the canonical result records) on 10 classification datasets, regression, unlabeled and M3
  - the scoring oracle
  - policy-table behaviour
  - Bank Full specifics
  - HTML ↔ JSON text identity on both classification paths
  - "not recorded" behaviour for older results
  - live/saved identity
- `tests/test_outcome_states.py` gained 3 tests.
- Updated, because they pinned superseded output:
  - the label "High · incomplete" is now "High priority · incomplete"
  - the M3 legacy-body test now includes `_with_layers`
- Fixtures re-frozen from the committed originals under one combined guard. With the original templates, current code reproduces every original frozen HTML hash, and the JSON differs only by `structure_validation` and `guidance`.

**Verification**
- Full suite: 705 passed, 1 skipped, plus M9 42.
- Canonical outputs (core, clustering, M4, M5) are identical to WS1 apart from `guidance`; the M5 seal is unchanged.
- API/classic parity holds.
- Bank Full: 69.0 · Elevated.
- Headless pass: all chapter facts, report layers and PDF; Reports shows "PDF ready" once it exists; no overflow at 1440 px or 390 px with chapters open; no console errors.
