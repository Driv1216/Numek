# Research and product audit — 13 October 2026

## Scope and honesty

Read README, current state, architecture, master context, M5/M6/M7/M9 contracts, methodology, scoring/findings modules, Flask templates/routes, the stored Adult validation summary, and final bounded M9 JSON. Applied `agents/skills/verify/skills.md` (proportional verification) and the Vercel Verification skill. Inspected the running Flask home and M9 start/configure screens on loopback. Opened the stored reports separately in the lab for visual review. No production analysis engine was changed.

References below were opened on the actual web and inspected with browser screenshots and accessibility/DOM snapshots. A screenshot of a loader is not treated as a reviewed finished screen. No authenticated Linear/Raycast/Figma application was inspected; product UI observations are limited to the public articles, examples and manuals. Public reference content is inspiration, never customer source material.

## Reference observations and decisions

### 01 — Guided Studio

- [LPAS](https://lpas.com/): visually inspected the loaded photographic homepage. Oversized plain sans typography, very small menu, a narrow metadata row above the title, and a process declaration establish orientation. The initial animation briefly rendered a blank surface. Adopt purposeful stages and a strong distinction between the current activity and supporting context. Reject photography, full-screen video, loading animation and marketing-scale whitespace for an analysis application.
- [Naam's LPAS case study](https://studionaam.com/projects/lpas/): visually inspected the dark asymmetric case-study opening with offset project images, small service labels and restrained navigation. Read its market segmentation and deeper-reading discussion. Adopt audience/task orientation and optional deeper explanations. Do not copy its image collage, brand, or promotional tone.
- [Stripe Docs](https://docs.stripe.com/) and [development-environment guide](https://docs.stripe.com/get-started/development-environment): visually inspected both. The guide separates topic navigation, readable central instructions and a compact local contents rail. Context callouts sit adjacent to the step they explain. Adopt context attached to the active stage, explicit next steps and progressive technical detail. Do not reproduce the sprawling product taxonomy or account/AI actions.

### 02 — Analyst Console

- [Linear design refresh](https://linear.app/now/behind-the-latest-design-refresh): visually inspected the article opening and its before/after sidebar illustration. The location/view hierarchy is explicit; inactive navigation retreats visually, and content controls are compact. Adopt subdued chrome, fixed action locations and finding rows that carry useful metadata. Avoid cloning Linear's issue taxonomy or blueprints.
- [Raycast](https://www.raycast.com/): visually inspected the dark restrained opening; this is a marketing page, not evidence of application behavior.
- [Raycast Quickstart](https://manual.raycast.com/quickstart): visually inspected the manual, search affordance and tightly arranged topic list; read quickstart instructions describing search and actions. The embedded video did not display a usable application frame. Adopt command search, displayed shortcuts and context-specific commands. Reject the marketing hero and excessive accent color. Keyboard interactions in this prototype are independently designed and tested, not claimed to be a clone of the app.

### 03 — Evidence Workbench

- [Figma UI3 article](https://www.figma.com/blog/our-approach-to-designing-ui3/): visually inspected the article opening and reading surface. Read its discussion of docked panels, labels, feedback and centering working content. The live Figma editor was not accessed. Adopt content-first tools, a collapsible inspector and small contextual controls. Reject floating controls where they would obscure documentary evidence.
- [VS Code user-interface guide](https://code.visualstudio.com/docs/editing/getting-started/userinterface): visually inspected the documentation page and read its basic layout, side-by-side editing, tabs and grid discussion. Adopt source tabs, a small record explorer, adjustable pane proportions and a persistent inspector. Do not copy an IDE's terminal, extension architecture or code-centric naming.

### 04 — Decision Edition

- [Stripe Press](https://press.stripe.com/): opening initially showed branding against an empty brown surface. Later interaction with the observed “An Elegant Puzzle” link produced a loaded stack of book spines with a slim position rail. Visually inspected that state. Adopt clear edition identity, quiet metadata, typographic hierarchy and sequential reading. Reject 3D book objects and spatial navigation: they slow exact evidence review.
- [Obys Experiment](https://experiment.obys.agency/) and [About](https://experiment.obys.agency/about): attempted both visually. Both remained at black loading screens during inspection. About DOM content exposed an indexed project archive and descriptive text; no finished composition/motion was verified. Only the explicit numbered-index idea informed the concept. Do not claim observations of its experimental visuals.

### 05 — Analytical Studio

- [hellohello State of AI case study](https://www.hellohello.is/case-studies/stateofai): requested URL now displays “AI In Design / Report 2026.” Visually inspected its loaded black editorial opening, split title, ruled metadata and mixed-format case study. Do not attribute an old State of AI design to the current page. Adopt section hierarchy across narrative and graphics; reject its compressed promotional body copy for prolonged technical use.
- [The Pudding: Hamilton](https://pudding.cool/2017/03/hamilton/): visually inspected its dot-built star opening. Marks encode narrative material; the opening recommends a wide viewport. Adopt individually inspectable marks and linked contextual text. Reject decorative mark formations and wide-only interaction assumptions. No lyrics or source visuals copied.
- [Our World in Data](https://ourworldindata.org/) and [life-expectancy data page](https://ourworldindata.org/grapher/life-expectancy): visually inspected homepage and data-page surface. Read named data sources, unit, date range, processing and interpretation. Embedded chart initially showed an empty plot area; do not claim its rendered chart interaction was inspected. Adopt explicit units, denominators, source notes, chart/table equivalence and limitations beside a plot. Reject an invented time series for a static audit.

### Galleries and individual projects

Opened all three requested [websites](https://www.awwwards.com/websites/), [portfolio](https://www.awwwards.com/websites/portfolio/), and [data-visualization](https://www.awwwards.com/websites/data-visualization/) galleries. Inspected filter rails, category headings and project listings; thumbnail regions remained blank in this browser. Selected “AI in Design Report 2026” and “Structure Consulting Engineers” for deeper research. The AI project detail navigation reached its URL but retained the listing state during the immediate snapshot; web fetches for both detail pages failed. The hellohello case study was successfully inspected separately. These inaccessible project details contributed no invented design observations. LPAS was also present as an individual portfolio listing and its actual site was inspected. Gallery award status is not evidence of suitability for enterprise analysis.

## Product observations

The classification route has an understandable upload → configure → confirm → report sequence. Target selection is explicit, subtype detected afterward; edits invalidate confirmation/artifacts. New capabilities have accumulated as separate links/routes. The M9 form exposes sources, associations, recipes, rules, model settings and confirmation as one long technical surface. Those contracts are valuable; sequencing and contextual explanation can improve discovery without weakening them.

M1 profiling, M2 regression, M3 annotation/multilabel/multi-output/readiness, M4 comparison/scalable investigations, M5 timing/history/evaluation, M6 text/annotations/conversations/RAG, M7 images/annotations/splits and M9 explicit cross-representation evidence are implemented. M8 audio is deferred. Some current-state prose still reflects earlier modality milestones; newer dedicated M7/M9 docs and code govern those boundaries.

Classification's five sub-scores, evidence-score mean and explained guardrails are distinct from measured facts. Other families must not acquire a universal score/readiness verdict. M9 declared decimal reconciliation is distinct from optional narrowly qualified semantic candidates. Native PDF/DOCX extraction is not OCR; DOCX does not have inferred page numbers. Evidence disagreement is not proof of truth or a label error.

Execution is local, single-user and process-scoped; supervised DuckDB workers and bounded searches are not unlimited capacity. No hosted history, accounts, real-time monitoring or automatic fixes exist. Source hash/locator resolution is exact; private manifests and separate review snapshots have different disclosure boundaries. Default portable reports omit source content. HTML/PDF/JSON exports reuse completed evidence.

## Five designs defined before implementation

1. **Guided Studio:** an open, warm, horizontal stage ribbon; one focused stage with a contextual explanation margin; findings expand in place. Setup is a sequence.
2. **Analyst Console:** dense dark queue as the primary surface; command palette and keyboard movement; evidence appears as an adjacent transient detail. Setup is an inline command form.
3. **Evidence Workbench:** document/source canvas with record explorer, source tabs, adjustable panes and inspector. Setup opens as a manifest work area; source comparison dominates.
4. **Decision Edition:** cream/navy editorial report with contents ribbon, evidence footnotes and expandable appendix. Setup is an intake sheet; investigation is sequential reading.
5. **Analytical Studio:** light chart workspace with graph-level controls, linked populations and a record strip. Setup is a parameter tray; investigation proceeds from visible population to exact records.

Grayscale test: stage workspace, queue, document canvas, report article and interactive plot remain spatially distinct without their palettes/fonts. Shared fixtures and low-level download/state helpers do not create a common shell.

## Responsive and stored-report follow-up

At an observed 805 × 827 reference viewport, Stripe Docs replaced its desktop rails with a compact section menu while preserving the article and contextual callout. Raycast Manual moved navigation to search/menu controls; the VS Code guide exposed a Topics selector instead of its full sidebar. No phone-width reference motion or application editor behavior is claimed.

Inspected the actual stored Adult and M9 HTML reports in a browser through copies served by the lab. Adult clearly exposes the evidence-score → guardrail path and a layered decision summary. The M9 report preserves scope and scoring restrictions, but its priority section displays raw rule dictionaries and abstract source identifiers. The prototypes translate those existing facts into labeled populations and locatable source context without adding analytical claims.
