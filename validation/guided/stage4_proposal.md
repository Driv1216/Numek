# Stage 4 proposal: Start page and tabular guided configuration

Status: **4a approved and built** (2026-11-25; see README "Stage 4a"). R-ID-2 was later narrowed to whole-number and text columns. 4b follows.

## What is already built (4a backend)

- `target_guidance.regression_target_groups(inspection)`: numerical-outcome groups taken from the full-file input inspection, replacing the 10-row preview assessment as the picker's source.
- `applicability.applicable_analyses(inspection)`: the "Start from a CSV" list. Every analysis is listed with a state (can run now, needs more input, or probably not useful), a reason and the rules behind it. It never ranks, preselects or blocks.
- Both appear in the job view as `suggestions`. They are advisory: neither enters analysis JSON, specifications or fingerprints.
- **Tests:** `tests/test_input_suggestions.py` covers eight retained datasets, the no-target case and identifier exclusion.
- **Fixed on the way:** an inspection bug claimed Beijing's `time` was unique. Uniqueness tracking could restart on a later chunk; it is now chosen on the first chunk only, with a regression test.

## Gate 4a: regression target grouping (please approve or amend)

| Group | Rule | Shown as |
|---|---|---|
| **Outcome-word numeric** | R-NUM-1, more than *c* distinct values, not identifier-like, name has an outcome token and no prior/derived token | first, "outcome-style wording in the name" |
| **Other numeric** | as above, without the name signal | "the name does not suggest an outcome; that does not rule it out" |
| **Review needed** | numeric, but: identifier-like (R-ID-1/2 or id/uuid/guid name), epoch-like (R-TIME-2), constant, at most *c* distinct values ("may be a category code"), a code/class/category name, or fewer than 4 values | collapsed. Choosable, then asks for the existing confirmation |
| **Unavailable** | not read as numbers, or no finite values | collapsed. Points to "declare it numeric" under CSV interpretation |

- **Threshold *c***: `min(20, max(2, rows // 2))`. This is the same small-set ceiling classification uses, and the same 20 the confirmation step uses for "numeric category ambiguity".
- **Consistency check:** on every retained dataset, any column the confirmation step would flag for an acknowledgement is in Review or Unavailable. It never appears in the first two groups.
- **Outcome tokens:** target, label, outcome, price, cost, amount, total, count, cnt, sales, revenue, demand, quantity, load, strength, yield, income, salary, consumption, usage, value, rating.
- **Suppressing tokens:** classification's existing list (prior, previous, historical, score, prediction, estimate, …).
- Nothing is preselected.

**Results on retained datasets**

| Dataset | Outcome-word | Other numeric | Review | Unavailable |
|---|---|---|---|---|
| Bike Hour | cnt | hr, temp, atemp, hum, windspeed, casual, registered | instant, season, yr, mnth, holiday, weekday, workingday, weathersit | dteday |
| Concrete | strength_mpa | 7 mix components | age_days (14 values) | — |
| Energy | heating_load, cooling_load | — | 8 design inputs (2–12 values each) | — |
| Bank Marketing | — | age, balance, day, duration, campaign, pdays, previous | — | 10 text columns |
| German Credit | credit_amount | duration_months, age | 4 small-count columns | 14 text columns |
| Linnerud (20 rows, *c* = 10) | — | Chins, Situps, Jumps, Weight, Pulse | Waist (9 values) | — |
| Scene | — | 294 attributes | 6 indicator labels | — |
| Beijing | — | PM2.5, PM10, TEMP, PRES, DEWP, RAIN, WSPM | — | time, station, wd |

**Known limits**
- `hr` (hour of day, 24 values) counts as "many values".
- `duration` in Bank Marketing is an ordinary numeric option. Inspection can't know it is post-outcome; G0 availability covers that.
- Name tokens are ordering hints only. They don't establish intent.

**Also for your review:** R-ENTITY-1, as approved, matches Beijing's wind direction (`wd`) as well as `station`. It only matters in Stage 5 (temporal), so I'd tighten it there, rather than now, if you want.

## Start page and flow (4a interface)

**Same rail, same four steps.**
- Step 1 is renamed from "Upload" to "Start".
- Picking an analysis happens inside Step 1, after the file is read, so Configure, Confirm and Report are unchanged.
- Visual language is kept: Deep Water, the `ap-mode` tiles and drawings, `ap-sec` sections and the drop zone.

```
Step 1 · Start
What do you want to check?

┌ Start from a CSV ─────────────────────┐  ┌ I know what I need ───────────────────────┐
│ Drop a CSV · separator: auto          │  │ Understand a dataset                   →  │
│ Read on this machine. Then we show    │  │ Prepare data for prediction            →  │
│ which analyses fit; you choose.       │  │ Readiness for clustering or anomalies  →  │
└───────────────────────────────────────┘  │ Compare datasets or splits             ↗  │
                                           │ Data over time                         ↗  │
All analyses (search) ▾                    │ Text and language data                 ↗  │
                                           │ Images and annotations                 ↗  │
                                           │ Records and documents                  ↗  │
                                           └───────────────────────────────────────────┘
```

- **Intent cards.**
  - Single-CSV intents (the first three) ask for the file, then show only their analyses.
  - Multi-source intents (↗) open their existing flows (`/app/m4`, `/app/temporal`, …) as today.
- **After a CSV is read** (upload only, stage `choose`), the same page shows:
  - file facts and the inspection coverage statement;
  - three lists: **Can run now**, **Needs more input** and **Probably not useful**. Each entry shows its reason and rule IDs. Every entry, including the unlikely ones, opens its analysis;
  - "Profile this dataset" first under Can run now.
- **All analyses:** a searchable list of every analysis with a one-line purpose. It replaces the "Other workflows" header menu with an "All analyses" link. The last-used analysis is remembered per viewer in `localStorage` (guarded).
- **Change analysis:** a link on Configure returns to the list with the file kept (`POST /core/job/analysis`).

**User-facing names**

| Name | Analysis |
|---|---|
| Dataset profile | `unlabeled` |
| Profile with chosen columns | `role_profile` |
| Category outcome | `classification` |
| Numerical outcome | `regression` |
| Several numerical outcomes | `annotation_regression`, 2 or more targets |
| Several labels per row | `multilabel_classification` |
| Partially labelled: category | `annotation_classification` |
| Partially labelled: number | `annotation_regression`, 1 target |
| Clustering readiness | `clustering` |
| Anomaly-detection readiness | `anomaly_detection` |

Internal IDs are not shown.

**Numerical outcome picker.** The regression Configure step uses the groups above, following the classification layout: grouped options on the left and the selected target's preview on the right. The 10-row "provisional" options list goes.

## Configuration and review (4b, after 4a is accepted)

- **Three layers** in each tabular Configure (G1–G7): Essential, Recommended context and Advanced.
  - Each field in `flow.tsx` gains `why` (what it enables) and `ifMissing` (what can't be concluded without it).
  - Regression's CSV interpretation and JSON fields move to Advanced.
- **G0 availability.** Every column starts unknown, with a per-column select. The bulk "Mark selected columns as available" action needs a dialog that:
  - lists every column being declared;
  - states the consequence (Bank Marketing's `duration` as the example);
  - requires a checkbox before it applies.

  The review page shows the counts and lists bulk-declared columns separately.
- **Role suggestions as ghost chips** in M3, accepted one at a time. Every column still defaults to feature.
- **"Switch to role-aware classification"** (and its regression and profile counterparts): a confirmation stating the methodology that will run and that no composite score is computed.
- **Review panel** on Confirm: the methodology from the same `effective_policy` the run uses, declarations, assumptions, unknowns and opt-ins not requested.
  - **Test:** the review methodology equals the recorded `methodology_id` for every mode and after the switch.

## Verification (Stage 4)

- `tests/test_input_suggestions.py` (done), `tests/test_target_guidance.py` extended, and the API tests.
- Captures of every changed screen at five sizes under `work.nosync/guided/visual/stage4/`. Walkthrough of every intent.

## Decisions requested

1. Approve the regression grouping: the threshold *c*, the review reasons and the outcome-token list (or amend them).
2. Approve the user-facing analysis names and the Start-page structure (Step 1 renamed "Start"; choosing happens within it).
3. R-ENTITY-1 precision: tighten in Stage 5 (recommended), or now.
