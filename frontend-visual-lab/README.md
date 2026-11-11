# NUMEK DataTrust visual lab

Fifteen competing art directions for DataTrust, in three rounds. Each one has a landing page, a workspace and an Adult results screen, all showing identical, real evidence. Round three is the current recommendation set; rounds one and two are kept for comparison.

This lab is isolated: `frontend-design-lab/`, production code, reports, tests and validation evidence are untouched. Nothing is committed.

## Run

```sh
cd /Users/drivyaanshyadav/Desktop/Numek/frontend-visual-lab
npm install
npm run dev
```

| Page | URL |
|---|---|
| Comparison launcher | http://127.0.0.1:5190/ |
| Reference board (all rounds) | http://127.0.0.1:5190/#/board |
| Screenshot sheet | http://127.0.0.1:5190/screenshots/index.html |
| A concept screen | `http://127.0.0.1:5190/#/<concept>/<landing\|workspace\|results>` |

- Round three concept ids: `provenance`, `proof`, `engine`, `terrain`, `notebook`.
- Round two concept ids: `inspect`, `continual`, `assurance`, `argument`, `signal`.
- Round one concept ids: `census`, `instrument`, `trace`, `cells`, `screening`.

Scripts (the dev server must be running for the last three):

- `npm run build` runs a strict TypeScript check and the Vite build.
- `node scripts/verify.mjs` runs the checks.
- `node scripts/capture-concepts.mjs [ids…]` refreshes the screenshots. Set `SCROLL_SHOTS=1` to add two mid-scroll landing frames.
- `npm run capture:refs` re-captures the reference sites.

A launch config for the in-app preview pane was added at `../.claude/launch.json`. Delete it if unwanted.

## Round three: product-native

Round two still drew a score rather than demonstrating the product's core act, and its apps never let you browse the dataset. Round three sets a stricter bar (`research/DESIGN-ROUND-3.md`):

- Every hero traces, measures or explains real Adult evidence.
- Every app shows the data itself. Real distributions of all 15 columns over all 48,842 rows come from `research/extract_distributions.py`.
- Each concept carries one brand system (mark, type, palette and motion signature) across its three screens.

| | Learned from | What it does for Numek |
|---|---|---|
| **Provenance** | Getty Tracing Art, Hex | The core act as a story. One real CSV row (line 850) sits centred and turns from raw bytes into a parsed record, a profile, a conflict group, a flag and a report line as you scroll. A timeline scrubber runs below and faded neighbouring rows sit around it. The app is a catalogue of the 15 columns and a record page with a provenance chain for every finding. Spectral and Geist, ochre on gallery white. |
| **Proof** | Stripe, Ramp, Terminal Industries | Commercial-grade marketing that stays checkable. A moving indigo-to-coral mesh sits under floating cards of real evidence. A baseline calculator shows the majority-class accuracy and when the 75% target-balance rule trips, for any split. A Stripe-grade dashboard and results with the full column-profile table follow. Onest and Red Hat Mono. |
| **Engine** | anime.js, Spur, Oryzo | The audit drawn as an engineering part. The twelve real checks are line-art layers that explode on scroll, labelled with their check names, and the four with findings are red. A zoom-box density map, a console app, and results that focus the layer behind each finding. Bricolage Grotesque and Azeret Mono, signal red on graphite. |
| **Terrain** | Mont-Fort, Artificial Societies | Calm institutional presence. A three.js landscape built from the real age by hours density, with isolines and fog, and pins on real cells (the conflicting rows, the busiest region). Widely spaced Jost capitals. The results let you drag the landscape beside the findings. |
| **Notebook** | Hex, Stripe | DataTrust where ML engineers already work. The hero notebook types and runs the real Python API and prints what it returned for Adult: `(69.0, 89.15)`, the four finding titles and the report export. The app is a notebook IDE where findings are markdown cells, a real pandas cell selects the 10 conflicting rows, and a panel shows a spark for every column. Libre Baskerville italic with Albert Sans on grid paper. |

**References.** 15 new Awwwards and product sites, captured live. 10 were combined into concepts, 2 studied (Dropbox Brand set the one-brand-system rule) and 3 rejected with the reason (MindMarket, Negotiated Intelligence, Lando Norris).

### Critical assessment, round three

- **Recommended direction: Notebook, Proof and Provenance as one system.**
  - Notebook is the most honest product story: it shows the real API doing the real work, which is exactly what the target user will do.
  - Proof is the strongest commercial landing.
  - Provenance's row story is the clearest explanation of what DataTrust does that no profiler does.
  - Together they make a credible site: Proof's landing, a Provenance-style "how it works", and Notebook's app language.
- **Engine has the most ownable visual.** The exploded drawing could become the brand mark in motion. Its app is less developed than its landing.
- **Terrain is the most beautiful and the least informative.** The landscape is real data, but a density surface says little about risk. It suits a brand moment or an "about" page, not the product.
- **Remaining weaknesses:**
  - Proof's mesh still reads as Stripe; it needs its own colour story before shipping.
  - The Notebook IDE is static apart from the hero.
  - Only Adult has full evidence; the other datasets show summary values.
- **Not checked:** dark-mode variants, Safari and Firefox, a formal accessibility audit, and performance on low-end GPUs. Engine and Terrain run three.js scenes continuously.

## Round two: product-led

Round one copied each reference's subject (film, hardware, bubbles) into a costume. Round two takes only the craft (how a site presents its product, its motion, type and finish) and applies it to what Numek sells. The plan and the review against generic defaults are in `research/DESIGN-ROUND-2.md`.

**Content.** Every figure comes from real `datatrust audit` runs, saved in `research/engine/` and packed into `src/shared/engine.json` by `research/extract_engine.py`:

- **Adult:** score 69, evidence 89.15, the critical target-balance guardrail, the 12 checks with their methods, all 15 column profiles, the source SHA-256 and a 0.20 s run.
- **Conflicting labels:** the 5 groups and their 10 real CSV lines.
- **Planted leakage:** the same table scores 49 (High).
- **Argument's slider:** five controlled runs from `validation_summary.json`.
- **Report previews:** captures of the actual generated HTML report.

| | Learned from | What it does for Numek |
|---|---|---|
| **Inspect** | Heron AI, Abatable, The Shape of Intelligence | Reads a dataset the way an inspector reads a drawing. The hero is a measured drawing of the real table, with flags on the exact CSV lines and columns, each citing its check and method. A pinned Observe, Flag, Explain, Report sequence ends on the real report. |
| **Continual** | Wafer, Linear, Resend, Modal | Reliability presented as infrastructure. A generated dithered sky carries the real score path. Wireframe evidence diagrams, the app rising out of the page, a pinned method figure built from the 15 columns, and real Python, CLI and browser code. A Linear-grade dark app. |
| **Assurance** | Sharplink, USAvionix, Mercury | Aimed at the buyer. A three.js glass stack where each plate is one real sub-score (target balance short and amber), with tracked spec callouts and scroll-lit thesis copy. A calm assessments overview and a decision memo for a CTO. |
| **Argument** | The Shape of Intelligence, Twain, Anthropic | The reasoning behind the score. "Trust is a measurement" at architectural scale, with a slider across five real runs that tweens the score and guardrails. Couplets, a striped 89.15, a reading room and a long-form report. |
| **Signal** | Cerebrium, Raycast, Cognichip | A fast daily tool for ML engineers. Drifting magenta ribbons, a command palette over the app as the hero, floating fact chips and a sticky feature list swapping real panels. A keyboard-first app (⌘K, arrow keys). |

**References.** 22 new sites, captured live. Not inspectable:

- **L.I.S.A.:** behind a Cloudflare human check, which I did not bypass.
- **Edolus:** its loader stalled every time.

### Critical assessment

- **Strongest product fit: Inspect and Assurance.**
  - Inspect's drawing-plus-citation idea is DataTrust's actual value made visible. It is the most ownable direction.
  - Assurance looks like a company a CTO would buy from, and its memo is the most useful results screen of the ten.
- **Most polished app: Continual.** Its dark app is the closest to a daily-use tool. The landing borrows Wafer's sky closely, so the hero needs its own signature before it could ship.
- **Argument is the best explainer.** Its slider teaches guardrails in seconds. As a brand it leans editorial, and its app is a reading room rather than a working surface.
- **Signal is the most conventional.** It is energetic and clearly usable, but closest to the dark-SaaS template (gradient ribbons plus a palette). Its differentiation is in execution, not concept.
- **Combinations worth exploring:**
  - Inspect's landing and drawing language with Continual's app.
  - Assurance's buyer story with Inspect's evidence views.
- **Not checked:** dark-mode variants, Safari and Firefox, a formal accessibility audit, and performance on low-end GPUs. Assurance's glass uses physical transmission and is the heaviest page.

## Round one: first exploration

| | Built from | Defining decisions |
|---|---|---|
| **Census** | Sons & Daughters, Extremists on Both Sides, Cartier 365, Obys | Width-filling extended mastheads, dotted leaders, rows as squares, conflicting lines as portraits. |
| **Instrument** | Teenage Engineering EP-133, Hyperbolic, Made With GSAP | A bench analyzer: seven-segment readout, faders, a channel-strip workspace, thermal tape. |
| **Trace** | Studio Null, Unseen 2025, Hyperbolic, Igloo, Ciechanowski | A white sheet in a black frame and the real 48,842-row point cloud with tracking boxes. |
| **Cells** | ART+TECH Report, Hello Hello, Reform/Micro | A claret field of outlined cells whose shape encodes content, with dither charts. |
| **Screening** | Siena Film Foundation, Ottografie, Cartier 365, Unseen, Phantom | A film programme with a ticket-stub navigator and evidence stills. |

Round-one figures come from `validation/results/validation_summary.json` and the previous lab's Adult fixture.

## Verification

- `node scripts/verify.mjs` passed **94/94** across all fifteen concepts:
  - The launcher and the board render, and every board image resolves.
  - Every landing page links to its workspace and results screens.
  - One interaction responds in each concept: tabs, filters, the slider, ⌘K, the baseline calculator, and the hero notebook running all four cells.
  - No screen scrolls sideways at 390 px.
  - No page or console errors.
- `npm run build` passes.
- Screenshots in `public/screenshots/` are real Chromium captures, GPU rendered through Metal ANGLE:
  - a 1440 × 900 viewport
  - a 390 × 844 viewport
  - a 1440-wide full page, captured with reduced motion so smooth scrolling cannot offset it.
- In those reduced-motion full pages, pinned sections show their first step and scroll-driven effects show their resting state.
