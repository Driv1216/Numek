# M4 adaptation (design note for review)

> **Revised in P4 so every workflow shares one theme.** The role strip no longer sits above the tiles. It becomes the **Roles hero tile**: a 2×2 tile at the top left of a single mosaic, whose chapter holds the full role cards, the declared intent and keys, and the pair's findings. The pair and per-source tiles fill in around it. See `m5-m9-adaptations.md`, section "The shared frame" and "M4 · brought in line". The rest of this note still applies.

M4 covers DataTrust's split audit, version comparison and advanced single-dataset analysis. This note proposes how it fits concept 22 without stretching the 14-tile mosaic. The approved NUMEK language (tokens, type, line kit, tiles that grow into chapters, the step rail, Viewer, sheets) stays as it is. Only the result layout adapts.

## What M4 actually produces

These details come from `m4_web.py`, `m4_report.html` and `m4_presentation.py`, and from the validation runs in `validation/m4/results/` (browser `splits`, `versions`, `advanced`; reports `clean`, `contaminated`, `shifted`, `partial`, `wide`, `long_headers`).

### Modes

| Mode | Sources | Roles |
|---|---|---|
| Split audit | 2–3 | train, validation, test |
| Version comparison | 2 | reference, current |
| Advanced | 1 | a single dataset |

### Inputs

- **Sources:** an upload, or a CSV inside a configured data root. Each source shows its raw header and a 5-row token preview.
- **Per-source declarations:** role, task, targets, features, groups, an AnalysisConfig JSON and a name mapping.
- **Comparison declarations:** identity keys, group keys and an evaluation intent, plus a JSON block for execution and advanced diagnostics.

### Run

M4 runs on a background worker. Status is polled, the run can be cancelled, and the result can be completed or partial.

### Evidence

**Findings**
- Each finding has a priority (High, Moderate or Low), a title, a scope and an evidence type (declared violation or observation).
- The scope can be one source (`current`), a pair (`reference:current`) or the dataset.
- Findings may also carry an affected count, a denominator, a next action and limitations.

**Measurements are relational**
- Per source: `structure`, `annotations`, `repeated_inputs`, `annotation_cohorts`, `segments`.
- Per pair:
  - `schema`: added, removed and changed columns
  - `split_integrity`: shared records, features and identity units, with shares
  - `populations`: per column, missingness change, cumulative-distribution (CDF) distance, Wasserstein distance, and quantiles on each side
  - `segment_mix`
- Across all sources: `comparison.overlap_row_unions`.
- In advanced mode: `missingness_structure`, `dependencies`, `constraints`, `segments` and `unsupervised_readiness`.

**Score**
- Comparisons never have one (`"Comparisons have no composite score or risk band."`).
- Advanced mode shows the existing classification score only when `scoring.status == 'available'`.

## Why the 14-tile mosaic would mislead here

The mosaic describes one table, check by check. M4's evidence is about the relationship between datasets: test rows that repeat train rows, columns that moved between versions, schema changes. Pushed into 14 tiles, the result would be wrong in three ways:

- a tile couldn't say which pair a finding is about
- most tiles (Score, Imbalance, Time, Text and so on) would read "Not for this data"
- the core of the result, overlap and drift between roles, would have no tile at all

## Proposal: the Roles layout

```
 Contaminated split                                     reference.csv ↔ current.csv · Split audit
                                                        19 Oct 2026 · 0.4 s · 1 finding · Open report ↗
 ■ No composite score: comparisons report evidence

 ┌ TRAIN ─────────────┐          overlap 240 / 240 rows          ┌ TEST ──────────────┐
 │ reference.csv       │ ●───────────────────────────────────●  │ current.csv         │
 │ 240 rows · 5 cols   │   declared: entity-disjoint ✕ (coral)   │ 240 rows · 5 cols   │
 └─────────────────────┘                                          └─────────────────────┘

 ┌ Overlap ───────────┐ ┌ Schema ─────────┐ ┌ Populations ───────────────────┐
 │ High · violated     │ │ No change        │ │ 0 of 3 columns shifted          │   ← pair tiles, emerge like
 │ ▓▓▓▓▓▓▓▓▓▓ shared   │ │ id x z ch label  │ │ x  |··•··|  z  |··•··|           │     the mosaic; each grows
 └─────────────────────┘ └──────────────────┘ └─────────────────────────────────┘     into its chapter
 ┌ train · Structure ┐ ┌ train · Repeats ┐ ┌ test · Structure ┐ ┌ test · Repeats ┐       ← per-source tiles, smaller

 Actions          High · train ↔ test · Declared evaluation separation is violated
                  Review source provenance and the declared use.   limitations…
 Coverage ▸       diagnostics, unsearched scope, excluded columns (collapsed, as in the core Report)
```

### 1. Header

It's the same as the core Report:
- **Left:** the dataset name.
- **Right, first line:** the sources and the mode.
- **Right, second line:** date, duration, findings count, and "Open report ↗".

A quiet Status line states that there's no composite score, so the empty space isn't read as a missing number.

### 2. Role strip

There's one card per source, in the Upload file-card style:
- the role label
- the file name
- rows × columns
- a short hash

Line-kit connectors (`Leader`/`Dim`) join each compared pair:
- **Split audit:** the connector is labelled with the overlap, shared records out of rows, taken from `split_integrity.records`.
- **Version comparison:** it's labelled with schema changes and the number of shifted columns.

A connector turns coral only when a finding for that pair is High or a declared violation.

### 3. Pair tiles

These are Modules tiles in DataTrust shades. They emerge on load and grow into chapters exactly like the mosaic.

| Tile | Shows | Drawing (JSON-bound) |
|---|---|---|
| **Overlap** (splits) | records, features and identity units: shared groups and shares | two bars, with the shared span in ink |
| **Schema** | added, removed and changed columns | the column chips in order, with additions and removals marked |
| **Populations** | per-column missingness change, CDF distance and Wasserstein distance, ranked | each column's quantiles, left against right, on one axis |
| **Segment mix** (if segments are declared) | segment shares on each side | paired stacked bars |

Each chapter holds the bounded table `report_view` already defines: 20 rows, and "N more in the JSON". It also holds the pair's findings in their canonical wording.

### 4. Per-source tiles

These are smaller tiles for each source's Structure, Repeated inputs and Annotations, and Segments when present. They use the same chapters.

### 5. Actions

The canonical findings, in their wording:
- priority, title, next action, affected count out of denominator, limitations
- scopes shown with role names, for example `train ↔ test` instead of `source1:source2`

### 6. Coverage

This is collapsed, as on the core Report: diagnostics status, population, unsearched scope and excluded columns. A partial run shows the existing warning banner above everything else.

### Advanced mode

There's one source, so there's no strip connector. The tile row becomes that dataset's advanced checks: Structure, Repeated inputs, Missingness structure, Dependencies, Constraints, Segments and Unsupervised readiness. A Score tile appears only when the canonical scoring is available.

## The M4 steps in the app

The step rail reads **Sources · Configure · Confirm · Report**. Running is the Confirm ticker, driven by the real worker progress, with Cancel.

### 1. Sources

- **Choose the mode:** three mode tiles in the Upload style (Split audit, Version comparison, Advanced).
- **Add sources one at a time:** either the drop zone, or **a data root and a relative path**. The roots are listed by alias only.
- **Preview each source:** its card shows the raw header and the 5-row preview, labelled provisional. The source limit is enforced by the server (3, 2 or 1).

### 2. Configure

There's one panel per source:
- **Role, task, targets, features, groups:** targets, features and groups are picked as column chips from that source's header. The app still sends the classic comma-separated fields.
- **Advanced settings, collapsed:** the AnalysisConfig JSON and the name mapping.

Then the comparison settings:
- identity keys and group keys, built as composite rows of aligned names
- the evaluation intent
- an execution and diagnostics JSON section, collapsed

### 3. Confirm

- A readable summary of the effective specification: each source with its role, task and hash, then the keys and the intent.
- The exact manifest and configuration JSON in collapsible sections.
- The binding statement from the classic page.

### 4. Report

The Roles layout above.

### History

- The canonical HTML and JSON are recorded through the existing lazy export path.
- A PDF is added once one has been downloaded.
- The entry is saved as `workflow: m4`, with mode set to `splits`, `versions` or `advanced`.
- Saved entries open in the same layout, read-only.

## Decisions for you

1. **Roles layout instead of the 14-tile mosaic** for split audits and version comparisons, with the M4 tiles for advanced mode. I recommend this.
2. **Column chips** for targets, features, groups and keys instead of comma-separated text. The request contract stays the same. I recommend this.
3. **No file browsing** under the data roots. Paths are typed relative to a listed root alias. Listing the contents of directories would be a new capability, so I recommend leaving it out.

## M3 needs no new layout

The six M3 modes run on the core job store and produce single-dataset results:
- multilabel, clustering, anomaly readiness
- annotation-aware classification and regression
- explicit-role profiling

Their results use the approved 14-tile mosaic through the same adapter. Finding codes that don't belong to any of the 14 modules go to the Reports tile, so nothing is hidden. Their Configure step is a per-column role table (feature, target, metadata, group, ignored) with semantic types, using the existing Configure vocabulary. The annotation and expectation declarations sit in collapsed JSON sections, and the representation acknowledgement uses the existing advanced-target pattern.
