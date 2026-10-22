# M5, M6, M7 and M9 adaptations (revised: one mosaic, a hero tile)

**Revision.** Every result page is now a single Modules mosaic. The workflow's main evidence lives in a **hero tile**: an oversized 2×2 tile that anchors the mosaic the way Score anchors the original. There are no separate panels above the tiles. M4's role strip moves into a hero tile too (see the end of this note). The result is one theme across all ten workflows.

## The shared frame (every workflow, M4 included)

```
 Name                                                    sources · workflow
                                                         date · findings · Open report ↗
 ■ Status line: the canonical scoring reason (none of these has a score)
 [partial banner, only when the run is partial]

 ┌──────────────────────┐ ┌ Family ┐ ┌ Family ┐
 │  HERO TILE (2×2)      │ │        │ │        │        ← one mosaic: tiles emerge one after another,
 │  drawing from the     │ ├────────┤ ├────────┤          each grows into its chapter (clip-path, ← → between
 │  canonical JSON       │ │ Family │ │ Family │          chapters, Esc to close)
 └──────────────────────┘ └────────┘ └────────┘
 ┌ Family ┐ ┌ Family ┐ ┌ Family ┐ ┌ Family ┐

 Actions · canonical findings      Take it with you · downloads      Coverage ▸ (collapsed)
```

### The hero tile

- **Size and place:** 2×2, top-left, in the shade Score uses (`#163F52` with light ink).
- **The face:**
  - a label and a detail, like every tile
  - a large drawing bound only to the canonical JSON
  - never any revealed content: no text excerpts, no images, no labels
- **The chapter:** opening the tile grows it, with the same clip-path animation, into a chapter the size of the whole mosaic. That's where the full interaction lives: the timeline, Reveal text, the pairs viewer, the reconciliation table.
- **Opening on arrival:**
  - the open chapter is remembered on reload and can be linked to (`#hero`)
  - on a fresh live result, the hero chapter does **not** open by itself; the mosaic emerges first, as in Modules
- **On phones:** the chapter is full-screen, as the mosaic chapters already are.

### Family tiles

- There's one tile for each evidence family present in the canonical JSON.
- **Tone:** set by the findings that cite that family.
- **Chapter contents:**
  - the canonical meaning and action wording
  - the bounded data, at most 20 rows, then "N more in the canonical JSON"
  - the examined scope
- Absent families get no tile, so nothing is ever shown dimmed. The grid fills densely around the hero.

### Conventions kept from before

- **Request contract:** the same classic field names, sent as JSON. Closures are lifted in place, and each module's own tests are the parity gate.
- **Steps:** the rail reads **Sources · Configure · Confirm · Report**. Running is the Confirm ticker, driven by real progress, with Cancel.
- **Sources:** an upload, or a data-root alias and a relative path. There's no file browsing.
- **Configure:** collapsible panels, essentials first, then advanced JSON collapsed. Column chips are used wherever the classic form takes column names, and row builders are used for repeating rows. The request fields stay the same.
- **Live versus saved:** private inspection works only on a live result in this session. Saved entries show the same mosaic from canonical JSON, with opaque references and the read-only notice. History keeps the canonical HTML and JSON only.

---

## M5 · Temporal reliability

**Inputs:**
- CSV or Parquet sources, each with a role: analytical, or auxiliary (history, schedule, expectations)
- per-source declarations: observation meaning and layout, entities and keys, clock, measurements, scheduling and lifecycle, availability and evaluation plans

**Evidence** is grouped by the report's six topics: chronology, continuity and history, behavior, availability and outcome maturity, evaluation, methodology and coverage.

**Hero tile: Timeline**
- **The face:** one thin band per analytical source, showing:
  - its observed span (first and last instants from chronology evidence)
  - gaps from continuity evidence
  - the declared prediction time as a cap line
- **Coral marks** appear only where a finding cites them.
- **When the JSON has no span** for a source, that band is left out rather than estimated.
- **Label:** "N sources · span". **Detail:** the first finding's title, or "No qualifying finding."

**The chapter**
- the full-size timeline with labelled axes
- each band's declarations: clock kind and timezone, schedule, lifecycle
- **live only:** "Filter by measurement or family" opens the existing filtered investigation in the Viewer. It re-presents retained evidence and doesn't re-analyse.

**Family tiles:** the six report topics. Each chapter holds that topic's `report_view` rows and its findings.

**Configure:** one panel per source:
1. Role and task, with targets as chips.
2. Observation: entities and keys as chips.
3. Clock: the column as a chip. Format, epoch and DST fields appear only when the chosen encoding needs them.
4. Measurements, as a row builder.
5. Scheduling and lifecycle, collapsed.
6. Availability and evaluation, collapsed JSON.

Auxiliary roles hide the temporal fields.

---

## M6 · Text reliability

**Inputs:**
- presets: corpus, classification, multilabel, token, span, QA, generation, conversation, retrieval
- CSV or JSONL sources, plus `.txt` and image assets
- field, annotation and asset declarations, plus optional pinned offline models

**Evidence families:** corpus, identities, invalidity, exact and near duplicates, repetition, vocabulary, lexical selection, annotations, categories and disagreement, conversations, passages, retrieval.

**Hero tile: Candidates**
- **The face:** stacked bars, one per candidate family (exact duplicates, near duplicates, passages, repetition), sized by its canonical count. Near duplicates also show their sub-threshold mass as a ghost bar.
- **Label:** "N candidate groups". **Detail:** the provenance line, for example "near duplicates: 0 qualifying, 3,003 below 0.8, not transitive".

**The chapter**
- the candidate groups and pairs, with opaque references and bounded-search provenance
- **live only:**
  - **Reveal text**, an explicit POST, shows the exact passages side by side with their locators. The response is `no-store`, and a changed source returns the classic "changed or unavailable" state.
  - **Export excerpts** downloads the canonical excerpt HTML for the selected references.
- **saved:** opaque references and the read-only notice in place of Reveal and Export

**Family tiles:** every family present.

**Configure:**
1. Preset tiles.
2. Sources and assets. Encoding, delimiter and quote are collapsed for JSONL.
3. Per source: row builders for fields, annotations and assets, with field selectors as chips from the source's fields. JSON Pointer entry stays available for nested JSONL.
4. Execution, limits and offline models, collapsed.

---

## M7 · Image reliability

**Inputs:**
- presets: directory, classes, manifest, COCO detection, COCO segmentation, YOLO, masks
- the inventory inspection (`/images/inspect`), which counts occurrences before declarations

**Evidence families:** inventory, decode, exact duplicates (bytes, native, oriented), near duplicates, versions, logical identity, annotations, annotation disagreement, composition, visual quality.

**Hero tile: Pairs**
- **The face:** a pair diagram with no images. Each retained pair is two frames joined by a line kit, labelled with its family and distance or cosine, with the closest pair in ink. Excluded occurrences, for example ICC-bearing images, appear as a ghost count.
- **Label:** "N retained pairs". **Detail:** "N occurrences · M excluded from default visual methods".

**The chapter**
- **live only:** the paired viewer
  - the pair list, with next and previous
  - left and right images resolved locally through the existing evidence resolution (`img-src 'self' data:`), never written to history or exports
  - opt-in toggles for overlays and labels, and hold-to-zoom
  - **Export examples**, which downloads the canonical disclosure HTML
- **saved:** the pair list with families, distances and opaque references, no images, and the read-only notice

**Family tiles:** every family present.

**Configure:**
1. Preset tiles.
2. Sources.
3. Inventory: the inspect step runs and shows occurrences.
4. Dataset meanings, annotation format and optional pinned offline models, collapsed.

---

## M9 · Records ↔ documents

**Inputs:**
- the classic configure actions: source (records, PDF or DOCX documents, text, images), mapping, relationship, rule, models, remove, import
- a bounded preview, then a sealed confirmation, then the run

**Evidence:** identities, relationships, context, models, and reconciliation per rule. There's one review target per investigated record.

**Hero tile: Reconciliation**
- **The face:** one bar per rule, split into satisfied, violated, conflicting evidence and incomplete. The counts come from the rule measurements, for example 18 / 1 / 1. Conflicting is shown in coral and violated in coral outline.
- **Label:** "N of M records reconcile". **Detail:** "records · documents · pages".

**The chapter**
- the reconciliation table: record, status, candidate count and review disposition
- filters for all, unreviewed, confirmed, dismissed and unresolved
- **live only:**
  - selecting a row shows the frozen rule, evidence cards (excerpt or image, PDF page, table and cell locators, revealed locally), association context, and review controls (confirm, dismiss, unresolved, plus a note) that post to the existing review route
  - review import, disclosure export, and the review JSON download
- **saved:** the table with statuses and counts only, plus the read-only notice
- **Reopen with your private manifest:** offered on a saved entry. It uses the existing `load-result`, with the report JSON from history and the manifest the user supplies, and restores live investigation only because the user explicitly provided it.

**Family tiles:** identities, relationships, context, models.

**Configure:** one guided page built from the classic actions:
1. Sources, as cards per kind.
2. Field mappings, as chips.
3. Relationships.
4. Rules, as a row builder.
5. Models, optional and pinned, with their qualification shown.

A bounded Preview comes before Confirm, which shows the sealed models and the CPU allocation.

---

## M4 · brought in line (part of P4)

- **The hero tile is Roles.** It replaces the role strip above the mosaic:
  - **the face:** the role cards drawn as frames joined by line-kit connectors, labelled with the declared overlap or the schema changes, and coral where a finding for that pair is High or a declared violation
  - **label:** "Split audit · 2 roles"
  - **detail:** the declared intent and keys
- **The hero chapter:** the full role cards (file, rows × columns, hash), the declared intent and keys, and that pair's findings.
- **The pair and per-source tiles stay as they are** and fill around the hero. The page structure becomes the shared frame above.

## Build order

1. **M4 hero retrofit first.** It's small, and it establishes the shared hero-tile component.
2. Then M5, then M6, then M7, then M9.
3. One review stop at the end of P4.
