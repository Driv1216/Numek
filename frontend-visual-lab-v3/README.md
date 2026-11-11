# NUMEK visual lab v3

Twenty independent visual directions for NUMEK and DataTrust: two rounds of five, then a round of ten. Each has a landing page, an application home and an analysis result.

- **Round one (01–05)** was approved at the creative-direction checkpoint on 16 Oct 2026 and built afterwards.
- **Round two (06–10)** was built on 17 Oct from the World-Class Creative Reference Library. It replaces an earlier round two that was scrapped at review.
- **22 NUMEK blend** is the current direction, following [research/BLEND_PLAN.md](research/BLEND_PLAN.md). It combines the Product Camera, Markup and Two Readings landings with Modules as the spine, in the Deep water palette. Step one, the NUMEK landing, is built for review.
- **21 The Evidence Mark** was the previous attempt. It was written from NUMEK's own thesis after round three was judged not to fit, and is described in [research/NUMEK_FOUNDATION.md](research/NUMEK_FOUNDATION.md). Only its landing page is built, for review.
- **Round three (11–20)** was researched from library sites not used in rounds one and two, proposed on the [round-three board](research/round-three/index.html), approved, and built on 18 Oct.

This folder is isolated. Production code, the other labs, reports, tests and validation evidence are untouched. Nothing is committed or pushed.

## Run

```sh
cd /Users/drivyaanshyadav/Desktop/Numek/frontend-visual-lab-v3
npm install
npm run dev
```

| What | URL |
|---|---|
| Comparison launcher | http://127.0.0.1:5313/ |
| Research board and direction proposals (round one) | http://127.0.0.1:5313/research/ |
| Research board (round two) | http://127.0.0.1:5313/research/round-two.html |
| Research board and the ten proposals (round three) | http://127.0.0.1:5313/research/round-three/ |
| Screenshot sheet (stills, mobile, storyboards, recordings) | http://127.0.0.1:5313/screenshots/ |
| A screen | `http://127.0.0.1:5313/#/<concept>/<landing\|app\|results>` |

Concept ids are `markup`, `every-row`, `issue`, `passage` and `two-readings` (round one), `provenance`, `collection`, `modules`, `camera` and `lexicon` (round two), and `cutaway`, `line`, `instrument`, `footnote`, `cells`, `resolution`, `relief`, `file`, `slab` and `findings` (round three), `evidence` (21) and `numek` (22). Append `?clean` to hide the small lab navigation pill, for example `#/issue/landing?clean`. In the desktop app's preview pane, `visual-lab-v3` in `../.claude/launch.json` starts the same server.

Scripts (the dev server must be running for the capture scripts):

- `npx tsc --noEmit -p .` runs the strict type check. `npx vite build` builds the app.
- `node scripts/capture-concepts.mjs [--no-video] [--mobile-only] [ids…]` regenerates `public/screenshots/`.
- `node research/scripts/capture-refs.mjs [ids…]` re-captures the reference sites. `python3 research/scripts/contact.py` rebuilds the contact sheets.
- `.venv/bin/python frontend-visual-lab-v3/scripts/extract_fixture.py`, run from the repository root, rebuilds the fixture from preserved evidence (read-only).
- `REFS=references-r2.json node research/scripts/capture-refs.mjs` and `REFS=references-r3.json …` re-capture the round-two reference sets (in `research/captures/` and `research/motion/`).
- `.venv/bin/python frontend-visual-lab-v3/scripts/extract_columns.py`, run from the repository root, rebuilds the per-column distributions used by Collection and Product Camera (read-only).
- Round three: `node research/scripts/awwwards-list.mjs` and `awwwards-sites.mjs` list the library's winner pages; `REFS=references-r4.json node research/scripts/capture-deep.mjs` makes the deep captures in `research/r4/`; `CAPTURE_SET=r4 python3 research/scripts/contact.py` builds their sheets; `python3 research/scripts/notes-to-refs.py` turns `research/r4/notes.md` into the board's reference list.
- `.venv/bin/python frontend-visual-lab-v3/scripts/extract_relief.py`, run from the repository root, rebuilds Relief's surfaces: Adult age × hours counts (summing to 48,842) and Bike mean count by weekday × hour (read-only).

## Shared content

All twenty use one fixture (`src/fixture/`), built from repository evidence:

- **Adult audit:** 48,842 × 15, final score 69.0 (Elevated), evidence score 89.15, and the critical-sub-score guardrail (target balance 47.86). Findings, sub-scores, the eight report topics and per-column appendix come from `validation/reports/adult.html`. Per-row flags come from `validation/data/prepared/adult.csv` and match the report: 49 duplicate groups with 52 repeated rows, 5 conflicting-label groups covering 10 rows, 3,620 rows with gaps, and 13,496 `hours_per_week` IQR outliers.
- **Run list:** German Credit and Bank Marketing (`validation_summary.json`), Bike hourly (the regression JSON, plus 48 real hours from its CSV), SMS 5,574, COCO 128/875/61 ICC, and M9 finance (20 records, 21 PDFs, 18 agreements, 1 discrepancy, 1 conflict).
- **Column distributions (round two):** min, max, quartiles, 32-bin histograms and top values for every column of Adult, German Credit, Bank Marketing and Bike hourly, read from the prepared CSVs in `validation/`.
- **Product facts:** the real CLI command, its output lines and the UI's default port 8000 come from `src/datatrust/cli.py`.
- **Scores:** only classification runs carry a score. Everywhere else the screen says no score is defined.
- **Illustrative material, labelled on screen:** the text excerpt, the image scene, the timing diagram and the finance record/PDF values. The 18/1/1 finance counts are real.
- **Not shown:** ConfidenceGuard, HallucinationGuard, hosted monitoring, certification or collaboration features. None appear as products.

## Round one: the five concepts and their real influences

| # | Concept | Idea | Drawn from (inspected) |
|---|---|---|---|
| 01 | **Markup** | The dataset is drawn as a technical sheet. Each finding is a numbered vermilion mark on the exact cells, with a title block and a markup schedule. The score is drawn as a dimension line. | Heron AI (subject drawn, then annotated in place), Studio Freight/Hyperbolic (object plus line drawing, precise margins), Praetorian spec sheets, Checkpoint Research crosshairs |
| 02 | **Every Row** | All 48,842 rows are WebGL marks. The same marks rearrange into Target, Missingness, Duplicates, Conflicts and Outliers. Prose and marks share one colour key. | The Pudding/Hamilton (persistent rearranging marks, linked prose), Obys (named arrangements), The Seventh Eye (units on a spine), Riotters/Aevion |
| 03 | **The Issue** | Each audit is published as an issue: a cover with the score, contents with dotted leaders, colour-field chapters, printed pages, back issues, a colophon, and a reading room with margin notes. | State of AI Design and the hellohello case study (chapter fields, numerals, contents lists), Sons & Daughters (chapter word, leaders), 14islands/Cartier 365 (pages as compositions), Ottografie |
| 04 | **Passage** | Six representations, six material colours. Panels slide over one another horizontally. The app is a Miller-column drill from run to topic, finding, evidence and the actual rows. | LPAS and Studio Naam (horizontal panels, category colour system), Chartogne-Taillet (spaced place names, index strip), Elektra (large-type index), Reform/Micro |
| 05 | **Two Readings** | Every result exists as machine output and as human evidence. A sentence opens on the real CLI and the rendered summary. Recursive's MONO axis morphs JSON into prose. | Made With GSAP (sentence that opens on the product, scrubbed type), Riotters (one fact at a time), Linear (true-scale UI), Raycast (keycaps), Wafer |

## Critical comparison, round one

**01 Markup.**
- *Strongest:* the most ownable idea. The product's core act, pointing at evidence, becomes the visual system, and the landing and app clearly share one identity. The dimensioned score with its hatched cap zone is the clearest explanation of the guardrail across all five.
- *Weak:* at "Fit" scale on the results screen the drawing's text is small (the 1 : 1 toggle and the schedule compensate). The register is narrow, close to architecture-studio styling. The sheet thumbnails on the dashboard are generic glyphs rather than each run's own drawing.

**02 Every Row.**
- *Strongest:* the most truthful. Every number on screen is visible as marks, and the conflicts view, with five enlarged pairs in disagreeing class colours, is the single best evidence moment in the lab.
- *Weak:* at 48k units the population at rest reads as grey texture, so the hero lacks drama until you scroll. The dashboard band (118,175 units at 2 px) is tall and its colour coding is hard to see on 1× displays. The leakage finding has no meaningful arrangement of its own.

**03 The Issue.**
- *Strongest:* the most finished and the most enterprise-credible. It reads like something a risk lead would forward. The reading room (chapter rail, footnotes that light margin notes, real appendix) is a genuinely good report reader, and data-generated covers make the dashboard distinctive.
- *Weak:* it is the least "software"-feeling. The newsstand dashboard is better for browsing than for doing. Its strength is presentation rather than investigation, and the cover-lift transition is subtle.

**04 Passage.**
- *Strongest:* the clearest picture of DataTrust's breadth. The overlapping horizontal panels work well, and the Miller drill that ends on the two real rows with only the label differing is the most practical investigation UI here.
- *Weak:* the panel artefacts for time, text and images are illustrations rather than real outputs. Horizontal pinning is long on laptops, and on mobile it falls back to a vertical stack. The hero needed a product trail added late to avoid an empty middle.

**05 Two Readings.**
- *Strongest:* the best expression of local-first and engineer–stakeholder communication. The opening sentence that reveals the real CLI beside the rendered summary is the strongest hero motion in the lab. The workspace (session timeline, ⌘K, a draggable machine/human split) feels like real software.
- *Weak:* the first viewport is sparse until the scroll begins. Dark-plus-terminal is the closest of the five to familiar developer-tool styling, which the paper human panes only partly offset. The axis morph is subtle on small text.

**Overall.**
- *Most distinctive identities:* Markup and Every Row.
- *Most launch-ready:* The Issue.
- *Best product tools:* Passage's drill-down and Two Readings' workspace.
- *A strong hybrid:* The Issue's reading room for stakeholders, plus Passage's drill or Every Row's arrangements for engineers.

**Still needs refinement in any direction:**
- Real upload, configuration and empty states.
- Light/dark coverage. Each concept ships one theme.
- Text and image result screens built from real M6/M7 outputs rather than illustrations.
- Accessibility audit beyond the basics already in place: keyboard focus, reduced motion, text alternatives for canvases.

## Round two: the five concepts and their real influences

The reference library asked for ideas that make NUMEK the subject and use exceptional web design as the means, borrowing how a subject is presented rather than what is presented. Each direction starts from something DataTrust actually does. The captures, contact sheets and honest notes are on the [round-two board](research/round-two.html).

| # | Concept | Idea | Drawn from (inspected) |
|---|---|---|---|
| 06 | **Provenance** | One finding traced from line 16,685 of `adult.csv`, through parse, profile, comparison and conflict, to page six of the report. The hero threads real Adult rows along a curve; a pinned scrubber stages one object per step. | Getty Tracing Art (objects on a path from origin to outcome), Persepolis Reimagined (pinned chapters), Ottografie and Studio Null (restraint, precise chrome) |
| 07 | **Collection** | Every column is an object turned from its real histogram: numeric columns become vessels, with the IQR-outlier zones darker; categorical columns become stacked totems, with gaps left hollow. Datasets are collections of these objects. | Monolith (catalogue on plinths, page-wide wordmark, time/place/scroll header), vvisual (numbered grid), Pangram Pangram (specimen spreads) |
| 08 | **Modules** | DataTrust as fourteen colour tiles, each with a live drawing from a real run, where ink is what the module found and ghost is context. Tiles grow into chapters (FLIP via clip-path). The app shows each run's result per module, and the results screen is the report's eight topics as tiles. | Dropbox Brand (mosaic index of drawn tiles), Cash App Brand (items that open into stories), Reform/Micro (flat colour, big grotesque), BlueYard (calm ledger) |
| 09 | **Product Camera** | The DataTrust interface built at full fidelity as live DOM. The landing films it: a tilted window settles flat, then a scroll-driven camera pans and zooms across score, sub-scores, findings, row evidence, fences, columns, export and runs. The app and results are the same UI at 1:1, with working tabs. | Apple MacBook Pro (product on a dark stage, captions), Linear and Raycast (real UI as the hero, secondary), Studio Freight/Hyperbolic (context, then close crop) |
| 10 | **Lexicon** | Nine words for what goes wrong in data (Ambiguity, Imbalance, Absence, Excess, Hindsight, Tautology, Repetition, Discrepancy, Constancy) and one for what remains (Reliability). Each word is set huge, with real evidence drifting past at its own depth. The app is a concordance by run; the result is Adult as a dictionary entry. | Exo Ape's Ottografie (depth-layered drift around a title, a single floating control), Sons & Daughters (large serif on dark), Obys Experiment (scroll-reactive type), Awwwards exhibition page (word index, partial) |

## Critical comparison, round two

**06 Provenance.**
- *Strongest:* it explains how DataTrust reaches a conclusion better than any other direction. Following one finding end to end makes "evidence-based" concrete, and the trace format also works for Bike's sum relationship and the finance discrepancy.
- *Weak:* it is linear by nature, so breadth (six representations) is told in a short list rather than shown. The 820vh pinned trace is long, and the hero thread is busy on small screens.

**07 Collection.**
- *Strongest:* the most original image system in either round. Every object is generated from the file's real distribution, so a dataset's character shows at a glance: the spiky `hours_per_week` vessel or the hollow base of `occupation`. It is calm, premium and unlike any data-tool brand.
- *Weak:* the metaphor needs its legend (darker bands mean outside the fences; hollow means missing). Objects for text, image and document runs do not exist, and the app says so rather than inventing them. It is better for exploring than for acting on findings.

**08 Modules.**
- *Strongest:* the clearest map of what DataTrust does and what each check changes (score, guardrail, evidence only, no score defined), and the best-systematised identity: one drawing rule, one palette, one tile grammar from brand page to app. The growing tiles feel crafted.
- *Weak:* it is the most brand-guideline in register, and the closest structurally to its reference, though grid, palette and drawings are NUMEK's own. Fourteen colours need discipline in real use, and small tiles hold only a hint of their drawing.

**09 Product Camera.**
- *Strongest:* the most launch-ready and the most "software". The product is the hero, every pixel is real UI, and the same components serve landing, app and results. The camera makes a dense screen legible one idea at a time.
- *Weak:* the least distinctive as a brand; dark product-tour pages are a familiar genre. Its quality depends on the interface itself, and the tour is long (about 11 screens of scroll).

**10 Lexicon.**
- *Strongest:* the most memorable and the most human. Naming failure modes gives NUMEK a vocabulary it could own (Hindsight for leakage, Tautology for a target rebuilt from its features), and the dictionary results page is a genuinely new way to read an audit.
- *Weak:* the poetry costs some precision. The words need their senses ("leakage", "duplicate rows") alongside them, and the drifting fragments can overlap. It is the weakest as a working tool; the concordance is browsable but shallow.

**Overall, round two.**
- *Most distinctive identities:* Collection and Lexicon.
- *Most launch-ready:* Product Camera.
- *Clearest explanation of the product:* Modules for breadth, Provenance for depth.
- *A strong hybrid:* Lexicon's vocabulary and type as the brand voice, Modules' tile system for the site's structure, and Product Camera's interface for the app.

## Round three: the ten concepts and their real influences

The brief for this round: only library sites not used in rounds one or two, analysed the way round one was. 42 sites were captured headlessly (stills, scroll storyboards, a 45-second recording, observed fonts, libraries and headings, and scripted hover, click and drag where a site depends on it). Every site has Seen / Take / Leave notes in `research/r4/notes.md`, and the [round-three board](research/round-three/index.html) shows the 43 references, the ten proposals and a comparison matrix.

Honest status of the research:
- **Not inspected:** Subdivisions (a CloudFront 403 on every frame) and Navigate (an SSL handshake failure). Neither informs any direction.
- **Partial:** Unseen (loader only; its Awwwards gallery page was used instead), Active Theory, US Avionix, Chladni, basement's machine mode, F-List and Floema (consent dialogs blocked the content).
- **Weak captures:** Bluejack, Reckoner, Vizz, SentientX, Level2, Montfort and Zentry. These are noted but not leaned on.

| # | Concept | Idea | Drawn from (inspected) |
|---|---|---|---|
| 11 | **Cutaway** | Adult drawn as one isometric slab: 15 column strips on a 48,842-row base, notches where values are missing, the target strip split 76.07 / 23.93. A camera visits parts of the drawing chapter by chapter. A labelled "what if" recomputes the score from DataTrust's published rules (60 / 40 would give balance 80 and no cap). | Townhouse (the product draws what it read as one place; chapters are close-ups with a real card; mono labels on parts), Mind Robotics (isometric line drawing with small cards pinned to parts), Kriss AI (one model of the whole operation, visited stop by stop) |
| 12 | **The Local Line** | One continuous line carries `adult.csv` through Read, Profile, Check, Score and Report on this machine, as plain engineering drawings with exact counts. The page uses system fonts only, practising "nothing fetched". | Grid to Page (one travelling line through a physical process; labelled drawings with exact numbers; a page that practises its principle), DeepBook (pinned sentences beside a reassembling system drawing), Imersion (a pipeline as a rail of named steps) |
| 13 | **Instrument** | DataTrust as a scientific instrument that stays on screen: Adult as a radial plot of its 15 columns, plain-language questions on the left, a legend with counts on the right, the row range along the foot. Each section asks one question and the instrument answers. | Shadow Fell (object in the centre, filter rail, legend with counts, range slider, presets as plain questions), Anime.js (a persistent frame where each capability performs live, with the exact code beside it) |
| 14 | **Footnote** | One long sentence is the whole proposition. Its nouns carry numbered footnotes that open real evidence, and small live inserts (a sparkline, a waffle of the target split, row chips) sit inside the line. | Watson (one huge sentence with footnoted nouns and live inserts), Mind Robotics (key words marked with pill highlights), Robot & Me (rows with a facts column and two depths: open, or look under the hood) |
| 15 | **Cells** | A strict grid that names its own construction, then fills cell by cell with Adult's real figures. One accent colour marks only what changed the score. The app and results reuse the same cells. | Aspen Search (strict cell grid, live clocks, numbered rows with line glyphs, one accent), Grids03 (a page that shows its own columns and gutters before content), ArtTech (an outline grid that fills as you read) |
| 16 | **Resolution** | An infinite, draggable wall of artefact tiles from every run: rows, columns, histograms, text lines, image counts and record-to-PDF pairs. Tiles resolve from a coarse veil to full detail as they enter. | Phantom (an infinite draggable wall with tiny mono captions; coarse-to-exact resolution as the loading language), GMB (a typographic index as the alternative view) |
| 17 | **Relief** | One plaster surface cast from the data: Adult's age × hours density as a hillshaded relief, with the IQR fences cut into it. Only the evidence "windows" carry colour. Bike sharing gets its own surface; runs without a natural surface say so. | Immersive Home (a monochrome material ground where only real content carries colour; windows let into it; serif captions; a counter loader), Seasoned (objects turning in soft light on a field) |
| 18 | **The File** | `adult.csv` as a physical stack of 40 sheets, each about 1,221 rows. The stack parts by the target, pulls out two disagreeing rows, shows a hollow band of gaps and the bands beyond the fences, is measured against the cap, and folds into three reports. | Deferred Damage (one object carried through the story, changing state per fact, one figure beside it), Oryzo (an ordinary object staged like a flagship product with design-tool guides; the staging is borrowed, not the jokes), Seasoned (soft gradient fields) |
| 19 | **Slab** | The NUMEK wordmark built from slabs. On scroll, every slab slides into one of five bars whose heights are Adult's real sub-scores, with the critical line at 50 and the cap at 69. Panels open behind shutters. | Aim by Obys (blocks that assemble the wordmark and later act as shutters; a hairline header), Neutomni (columns of rising height on a shared baseline), Siena (a credits block beside a giant title; a "now showing" selector) |
| 20 | **Findings First** | The landing page is the product: a searchable index of every finding across the local runs, each with its severity and its effect on the score. Then three method cards, a jury-style score table (weight and contribution per measure, then the guardrail) and the run list. | Field Rank (the product's real tables as the landing page; method in three numbered cards; mono for IDs; search as the main action), Robot & Me (rows with two depths: open, or look under the hood), Unseen via its Awwwards page (a transparent weighted scoring table) |

Every figure in these ten comes from the shared fixture. Relief's surfaces come from a new read-only extract (`src/fixture/relief.generated.json`). Schematic material is labelled on screen: Line's time sketch, Relief's text-line, image-tile and record-pair panels, and Cutaway's "what if", which is a calculation from the published rules, not a product feature.

## Critical comparison, round three

**11 Cutaway.**
- *Strongest:* the clearest single picture of a dataset. Every height, notch and split is a real number, and travelling around one drawing ties the chapters together. The "what if" is the best explanation of the guardrail in the lab: moving the target split shows exactly when the cap stops applying.
- *Weak:* the isometric detail is fine-grained, so on mobile the camera chapters lose most of their labels. Non-tabular runs only get small generic unit drawings.

**12 The Local Line.**
- *Strongest:* the most honest expression of "local". The page fetches no fonts, and the line never leaves the frame. The five check branches with their exact counts are an excellent one-screen summary of what DataTrust checks.
- *Weak:* system type makes it plain, and the identity depends entirely on the line drawing. The dark palette sits close to developer-tool styling.

**13 Instrument.**
- *Strongest:* the best "ask your data a question" interaction. Questions phrased in plain language, with the matching JSON beside them, make the product feel like a precise tool rather than a report.
- *Weak:* radial plots are hard to read exactly. The legend carries the numbers, so the dial is partly atmosphere, and the instrument shape fits tables much better than text or images.

**14 Footnote.**
- *Strongest:* the most trustworthy in tone. Every claim is one click from its evidence, which is exactly DataTrust's promise, and the inline inserts are small and real.
- *Weak:* the first viewport is quiet. It reads as excellent writing more than as a product, and its strength depends on copy quality.

**15 Cells.**
- *Strongest:* the most systematic and the easiest to extend. One grid and one accent rule serve the landing, the app and the results, and the construction intro makes the grid itself the message.
- *Weak:* it is the closest to a familiar Swiss-template look. Without the intro it could pass for many studios' sites.

**16 Resolution.**
- *Strongest:* the best picture of breadth. Rows, columns, text, images and record-to-PDF pairs share one wall, and the clusters on the results page group them clearly.
- *Weak:* an infinite wall can feel aimless. The index view and filters are necessary, not optional. Dragging is less discoverable on touch, and the tiles are small.

**17 Relief.**
- *Strongest:* the most beautiful and unexpected image. The surface is genuinely cast from 48,842 rows, so the forty-hour ridge is the dataset's own shape, and the coloured windows make the findings stand out.
- *Weak:* the surface is a smoothed density and needs its caption to be read correctly. Only two runs have a natural surface. The tilted stage is heavy on low-end devices; it is 2D canvas, so no WebGL is needed.

**18 The File.**
- *Strongest:* the most physical and the easiest to remember. The stack's states are to scale (the minority band, the hollow band of gaps, the bands beyond the fences), and "two sheets, one difference" lands the conflicting-labels finding instantly.
- *Weak:* it is one object for one dataset, so other runs are shown as plainer cards. The CSS 3D stack simplifies on small screens.

**19 Slab.**
- *Strongest:* the boldest brand. The wordmark that becomes the five sub-scores is an ownable moment, and it encodes the critical-sub-score cap directly.
- *Weak:* the constructivist register is loud and slightly historical. The morph works once; after that the bars are simply a bar chart.

**20 Findings First.**
- *Strongest:* the most launch-ready and the most useful. A visitor sees real findings in the first viewport, and the workspace (filters, a findings table and a detail pane with evidence and raw fields) is close to a shippable product screen. The jury-style score table is the most transparent score explanation of all twenty.
- *Weak:* the least distinctive. Its identity rests on typographic care and the method cards, and it could read as a well-made SaaS table.

**Overall, round three.**
- *Most distinctive identities:* Relief, The File and Slab.
- *Most launch-ready:* Findings First, then Cells.
- *Best explanation of the score:* Cutaway's "what if" and Findings First's score table.
- *Best for breadth:* Resolution.
- *A strong hybrid:* Findings First's table and workspace as the product, Relief or The File as the brand image on the landing page, and Cutaway's "what if" inside results.

## 22 NUMEK blend (current direction), step one

Built from [research/BLEND_PLAN.md](research/BLEND_PLAN.md):
- **Colour:** Deep water. Paper `#F3F1EC`, ink `#0F1B22`, DataTrust tide `#2C6E8E`, ConfidenceGuard sea glass `#3F8F86`, HallucinationGuard dusk `#5A5F9A`, and coral `#E5553B` used only for evidence.
- **Type:** Bricolage Grotesque, from Modules, with IBM Plex Mono for figures and labels, from Markup.

**The landing page, top to bottom:**
1. **Hero:** "Evidence for every AI decision.", with the three product windows tilting flat beneath it.
2. **Camera tour:** seven stops filmed by the Product Camera.
   - **DataTrust:** the real Modules dashboard (its tiles, states and drawings, reused from `concepts/modules` and recoloured), showing the whole window, then the score and its guardrail, then the conflicting rows.
   - **ConfidenceGuard:** a CG1 workbench screen built from CG1's recorded German Credit evaluation, showing the whole screen, then the 21.7% recall with 13 of 60 bad-credit cases caught.
   - **HallucinationGuard:** a labelled placeholder.
   - **Close of the tour:** a pull-back to all three.
   - A Markup leader line runs from each caption to what the camera is looking at, with brackets drawn on the target. They are coral when the target is evidence.
3. **Four principles,** in a hairline grid with crosshairs.
4. **Three product bands,** each previewing its future page hero as a line drawing with leader labels and a dimension line.
5. **Run commands and the footer.**

**Revision after review (19 Oct):**
- **Type:** changed to Schibsted Grotesk; Bricolage read as squashed.
- **Hero:** the opening shot now runs large and bleeds off the right edge, with a status line for the three products.
- **Principles:** rebuilt as a Markup sheet in `principles.tsx`. It is one technical drawing on a gridded sheet with a title block and legend: the Adult rows inside a dashed 127.0.0.1 boundary, a `datatrust audit` arrow into a report page where "certified" is struck through, and the score line from 0 to 100 with evidence 89.15 held at the 69 cap. Four numbered coral marks sit on the evidence, and a schedule underneath explains each principle. Hovering or focusing a schedule entry isolates its mark, and the sheet draws on as it enters view.
- **Product cards:** they now stack as you scroll, taking from these captured references (`research/r4/notes.md`):
  - Siena: rounded frames with a giant title and a credits block of labelled pairs
  - The Robot and Me: a right-hand column of labelled facts
  - DeepBook: a line-drawn module beside the copy, and stat tiles in a row

  Each card holds the real product window fitted to its frame, the line drawing, four stat tiles and the command.
- **Run section and footer:** retuned. The figures are now set in mono, and the footer wordmark is calmer.

**Not built yet:** the product pages, the app and the results, which are later steps. Those routes show a "comes next" page.

**Verified:**
- The strict type check and production build pass.
- All three routes load with no console errors and no horizontal overflow at 1440×900, at 390×844, and at 390×844 with reduced motion.
- Every tour stop was rendered and checked on desktop and mobile.
- Under reduced motion, the camera snaps between stops and lines appear already drawn.

### Step two: the DataTrust page (third revision, 19 Oct)

Open it from the landing ("Explore DataTrust") or at `#/numek/landing?p=datatrust`. Product pages ride on the NUMEK route as a `p` parameter, and section links use `s`.

After two rounds of review, the page has four parts:

1. **Hero: "Drop in a dataset. Get back what to fix."** The Drop (`drop.tsx`, `drop.css`) plays about six seconds when it comes into view, in three panels joined by a coral line that travels along their headers:
   - **Your file.** adult.csv (5.3 MB, the real size) drops into a marching-ants intake with a ripple. Its sha256 shows, the real sample rows stream past, and the row counter runs to 48,842.
   - **Checks.** Six checks resolve one by one with their real results: missing values 3,620 rows and repeated rows 52, both clear; contradicting labels 5 groups, unusual values 13,496 and lopsided target 76.07%, all found; leaked answers 1 column to review.
   - **Result.** The score counts to the 89.15 average, a cap line drops at 69, the score lands at 69.0, and the average is struck through. The four findings then arrive in plain English with the three report files.

   Picking a finding swaps the first panel for its real evidence, marked in Markup's style:
   - **Imbalance:** the class split, 37,155 to 11,687.
   - **Unusual values:** the `hours_per_week` histogram with the 32.5 and 52.5 fences.
   - **Contradicting labels:** rows 16,684 and 34,343 side by side.
   - **Leaked answers:** the column list with `marital_status` flagged.

   Replay restarts the run. On phones the evidence moves below the findings.
2. **Two Readings** (`readers.tsx`). "Machine output, human evidence." is set in Recursive and splits apart as you scroll. The window opens with the real command typing on the engineer's side and the decision summary on the reviewer's side. The draggable seam was removed because it lagged.
3. **What you get** (`report.tsx`, `report.css`). The real Adult report, pinned. Its eight topics turn page by page as you scroll; the contents list is also clickable. Each page is built from the audit's real content, and a coral-bracketed note says why that page matters.
4. **Run it.** Both commands, the local facts, and the exclusions listed in the report's own limits.

Removed at review: the dot-field hero, the JSON-to-sentence translation, the five-step drawing (the drop now shows that), and the ConfidenceGuard card. `field.tsx`, `how.tsx`, `elevation.tsx` and `checks.tsx` are no longer used by the page.

**Verified:**
- The strict type check and production build pass.
- The page loads with no console errors and no horizontal overflow at 1440×900, at 390×844, and at 390×844 with reduced motion.
- The drop was captured through its whole timeline, and each finding's evidence view was opened.
- Two Readings and the report were rendered at several scroll positions on desktop and mobile.
- Under reduced motion, the drop starts complete.

### Step four, part one: the DataTrust app (shell, Upload, Configure)

Researched and proposed first in [research/APP_PROPOSAL.md](research/APP_PROPOSAL.md), then approved with option B (a "Recent reports" rail labelled as proposed). Open it at `#/numek/app`.

**Grounded in the real product.** It follows DataTrust's own guided flow, Upload → Configure → Confirm → Report, and its own wording (`src/datatrust/web.py`, `templates/ui.html`; both were read, and neither was changed).

**Real Adult content.** Every Adult value on screen comes from DataTrust's own inspection, run read-only by the new `scripts/extract_inspect.py` into `src/fixture/inspect.generated.json`. That covers:
- 5.03 MiB, 48,842 rows, 15 columns, and the first 10 rows
- the grouped target options with their real explanations: no outcome-word candidates, nine small-set candidates, and six advanced choices
- for each option, the detected task, class split and real override explanation

**Entry points:** "Open DataTrust" in the site header (on the NUMEK landing and on the DataTrust page), in the DataTrust page hero, and "Open the guided app" in its Run section.

**The shell:**
- The DataTrust mark and a local status pill (`127.0.0.1:8000`).
- A four-step rail drawn in the line style: the line fills coral as you advance, and Confirm and Report are marked as next build steps.
- An "Other workflows" menu listing the real separate pages (temporal, text, images, records ↔ documents, split and comparison) without linking into them.
- **"Recent reports" rail:** dashed and hatched, tagged *Proposed*. It says that DataTrust keeps no history today.

**Upload:**
- Three Modules-style mode tiles (classification, regression, unlabeled) with line drawings, plus the six further modes.
- A marching-ants drop zone with "Choose a file" or "Try it with Adult".
- A file you pick is shown by name and size, with an honest note that the prototype continues with Adult.

**Configure:**
- File cards and the 10-row preview.
- The question *What outcome is this dataset meant to predict?* with the real groups and no preselection. Advanced choices are folded away.
- A bracketed selection panel showing the chosen column's real task, counts and class split.
- For advanced columns, DataTrust's real explanation of why it needs an extra confirmation. On phones these details appear under the choice.
- Optional name and purpose.
- "Review selection" stops at this checkpoint.

**Verified:**
- The strict type check and production build pass.
- Both steps load with no console errors and no horizontal overflow at 1440×900, 1024×768, 390×844, and 390×844 with reduced motion.
- The full flow was clicked through on desktop and phone: switching modes, trying Adult, the workflows menu, inspecting, choosing a normal and an advanced target, and the stop message.

### Step four, part two: Confirm, the result, and saved reports

At your request this was built at prototype depth, without a review checkpoint per step. The app now runs end to end: DataTrust page → Upload → Configure → Confirm → Report.

**Confirm:**
- The detected task, the four count cards and the class split for the chosen target.
- The six planned checks, which tick through when you press "Generate reliability report", then move on to the report.
- For an advanced target, the real acknowledgement box.

**Report:**
- **Score tile:** 69.0, Elevated, with a mini scale marking critical 50, cap 69 and evidence 89.15.
- **Four blocks:** the real UI's headings (What this means, Why this score, Principal evidence, Recommended next action).
- **The four findings**, each opening its evidence view from the drop.
- **All fourteen check tiles**, which grow into chapters.
- **Take it with you:** View full report, PDF and JSON downloads, and New analysis.

**Real reports:**
- `public/reports/` holds DataTrust's own HTML, PDF and JSON for Adult, German Credit and Bank Marketing. They were generated for this prototype with the real CLI, and their scores match the recorded results.
- It also holds copies of the recorded Bike-hour and SMS reports.

**Viewer and downloads:** "View full report" and "Open full result" show the actual report in a full-screen viewer, and the download buttons serve the real files.

**Recent reports (proposed):** each card opens a sheet with that run's real summary and findings. Runs with no report file (COCO, Finance) say so instead of showing dead buttons.

**Also fixed:** the mode tiles' coral brackets are now four fixed-size corners, so they are even at any size.

**Verified:**
- The strict type check and production build pass.
- All four steps load with no console errors and no horizontal overflow at 1440×900, 1024×768, 390×844, and 390×844 with reduced motion.
- The full journey was clicked through on desktop and phone: from the DataTrust page to Upload, Configure, Confirm with generate, and Report, including a chapter, the report viewer (the real report loaded) and the PDF.

### Result screen: the Modules mosaic, restored

The findings-first rearrangement was rejected. The result is now the Modules app as you loved it:
- All fourteen tiles in their original places, including the score tile.
- Each tile shows Adult's real state (label and detail) and its live drawing.
- Checks that don't apply to Adult are dimmed.
- The tiles emerge one after another on arrival with Modules' own wipe, and the bars grow in.
- Clicking a tile grows it into its chapter, with an "In Adult" box.

Above the mosaic is the original Modules header: "Adult" set large on the left, and on the right two quiet lines of facts with an "Open report" link. The score appears once, in the score tile, which already says why it is capped.

## 21 The Evidence Mark (previous attempt)

**Why it exists.** All twenty earlier directions started from other sites and applied their techniques to Adult's numbers, so none felt like NUMEK. This one starts from NUMEK's thesis in `docs/NUMEK_MASTER_CONTEXT.md`: teams need inspectable evidence about the data *before* training, the model *during* deployment and the output *after* generation. It also uses the founder's answers:
- **Audience:** all audiences.
- **Feeling:** serious, ambitious and sharp at once.
- **Order:** the mission comes first.
- **Starting point:** round one and Modules were the closest earlier directions.

**The idea.** NUMEK owns one graphic act: a signal-orange corner bracket with a numbered tag, snapped exactly around the thing being verified. The same mark is the logo, the illustration style, the way findings are shown, and the report annotation.

**Landing page, top to bottom:**
1. **Hero:** "AI makes real decisions. NUMEK shows the evidence." Three marks follow, one per moment:
   - Adult rows 16,684 and 34,343: identical features, different labels.
   - German Credit applicant 589: predicted good with 0.88 probability; the outcome was bad.
   - An illustrative generated sentence with an unsupported claim.
2. **Mission statement.**
3. **Two real cases where a healthy number hides a weakness:**
   - Adult's 89.15 average hides target balance 47.86, so the final score is 69.0.
   - CG1's model is 72% accurate but catches only 13 of 60 bad-credit cases.
4. **Three product tiles**, using the Modules grammar, with honest status:
   - DataTrust available.
   - ConfidenceGuard in development (CG1 implemented, awaiting review), at the founder's direction.
   - HallucinationGuard a research direction.
5. **A pinned walkthrough:** one mark travels across a real excerpt of `adult.csv` to each of the four findings.
6. **The six data kinds** DataTrust reads.
7. **Two readers:** the real CLI and finding JSON (using DataTrust's own keys) beside the report's decision summary.
8. **Four principles.**
9. **The run commands.**

**Data.** The model figures come from a new read-only extract, `scripts/extract_cg1.py`. It reads CG1's recorded evaluation in `validation/cg1/` and writes `src/fixture/cg1.generated.json`. The generated sentence is labelled as an illustration.

**Not built.** The app and results routes show a "comes next" page until the landing direction is approved.

**Verified.** The strict type check and production build pass. All three routes were loaded headlessly at 1440×900, at 390×844, and at 390×844 with reduced motion. There were no console errors and nothing overflowed horizontally. The pinned walkthrough was rendered at every step on desktop and mobile, and the mobile table was narrowed until it fit. Under reduced motion, every mark is shown already in place.

## Verification (proportionate to isolated prototypes)

- Strict TypeScript check and production build pass.
- All 15 screens loaded in a real browser with no console errors.
- Interactions exercised: Every Row arrangement tabs, the Passage drill to row level, the Two Readings ⌘K palette and per-finding flip, Markup mark selection.
- Screenshots captured at 1440×900 and 390×844, with scroll storyboards and landing recordings, in `public/screenshots/`. Mobile issues found in the first pass were fixed and re-captured.
- `prefers-reduced-motion` handling:
  - Markup and Issue: draw-on and cover animations are cut.
  - Every Row: arrangements snap.
  - Two Readings: the terminal is shown complete and the morphs snap.
  - Passage: the trail animation is removed.
- WebGL is required for Every Row's field. Without it a text note appears and the prose carries the content.
- Not done: screen-reader testing, cross-browser checks beyond Chromium, and performance profiling on low-end devices.

**Round two (06–10):**
- Strict TypeScript check and production build pass.
- Every screen was checked in a real browser at 1440×900 and 390×844 during the build, and the issues found were fixed: Collection's object fit and grid widths, Modules' tile layout, Camera's mobile canvas and run table, Lexicon's mobile pill and intro.
- Interactions exercised: Modules' tile-to-chapter grow, arrow navigation and close (landing, app and results); the Camera tour at every stop. Camera's tabs and export menu, and Lexicon's index and concordance, were built but not click-tested.
- Reduced motion is handled in code but was not separately tested. Modules and Lexicon drop drift and wipe-ins, Camera snaps between stops instead of gliding, and chapters open without the grow.
- Not done: the screenshot sheet and recordings for 06–10 were stopped at the user's request; only Provenance's stills were written. Screen-reader and cross-browser testing were not done either.

**Round three (11–20):**
- Strict TypeScript check and production build pass (built to a scratch folder; nothing is added to the repository).
- All 30 screens were loaded headlessly in Chromium in three modes: 1440×900, 390×844, and 390×844 with `prefers-reduced-motion: reduce`. Each page was scrolled top to bottom. There were no page errors and no console errors, and no element overflows the viewport horizontally. The only error seen was a `/favicon.ico` 404, now fixed with an inline icon in `index.html`.
- Each concept was also rendered during its build at desktop scroll positions, and the problems found were fixed. Examples: Cutaway's camera framing and section overlap; Line's missing target-balance branch and overlapping labels; Instrument's invented JSON keys and exaggerated missing arc; Relief's surface, reworked four times until it read as a smooth density; Resolution's veil remount.
- Reduced motion, as implemented:
  - Cutaway: the camera snaps between parts.
  - Cells: the grid starts fully built.
  - Slab: the wordmark starts as the five bars, and shutters start open.
  - Relief: the loader is skipped and the light stays fixed.
  - Resolution: no dissolve veil and no drag inertia; clusters start sharp.
  - The File: the stack changes state without transitions.
  - Footnote: the inserts stop cycling.
  - Line: the travelling dot is parked, while the scroll-linked track stays.
  - Instrument: the arcs change without transitions.
  - Findings First: there is little motion to remove.
- Not done: interactions were exercised only through each page's default state and scroll. Clicks, drags, filters and tabs were built but not click-tested in an automated pass. No screenshot sheet or recordings were made for 11–20 (not requested), and there was no screen-reader or cross-browser testing.
