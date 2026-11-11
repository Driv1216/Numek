# NUMEK blend plan

This plan combines four earlier directions into one site. Nothing is built yet. It needs your approval first.

## Decisions so far

- **Pages:** each product gets its own page.
- **HallucinationGuard:** shown as a clearly labelled dummy, because this is a prototype.
- **Colour:** palette A, Deep water. The site is light and never dark.
- **Sources:** the landing pages of Markup, Two Readings and Product Camera, plus Modules for everything else.

## What each source contributes

| Source | Role in the blend | Where it appears |
|---|---|---|
| **Modules** | **The spine.** Its tile grammar, type and joy run through everything. | App, results, and "what it checks" on product pages |
| **Product Camera** | **The wide shot.** It films the real products from above. | NUMEK landing only |
| **Markup** | **The line language.** Crisp hairlines, leader lines, dimension lines and crosshairs. | Everywhere, as annotation; product page heroes |
| **Two Readings** | **The command-line strip.** The real command beside the human report. | One band on each product page |

Each technique lives at one level, so nothing repeats: the camera is for the company, the drawing is for a product, and the tiles are for the app.

## The visual system

### Colour: Deep water

| Role | Colour | Rule |
|---|---|---|
| Paper | `#F3F1EC` | Every page background |
| Ink | `#0F1B22` | Text, hairlines and drawings |
| DataTrust: tide | `#2C6E8E` | Light `#D5E4EB` · dark `#163F52` |
| ConfidenceGuard: sea glass | `#3F8F86` | Light `#D6EAE6` · dark `#1F4D47` |
| HallucinationGuard: dusk | `#5A5F9A` | Light `#DFE0EE` · dark `#2E3160` |
| Evidence: coral | `#E5553B` | **Only** for marks on evidence (a finding, a flagged row, a critical score). Never decoration. |

- Colour tells you **where you are**; coral tells you **what was found**.
- Inside a product, Modules' tiles use that product's light, mid and dark shades plus neutrals, not fourteen unrelated colours.
- Severity is shown by shape and weight (filled, half-filled or outlined), not by extra colours.

### Type

- **Bricolage Grotesque** for display and text, taken from Modules, the direction you loved. Its width and optical axes give the big confident headlines and calm body text.
- **IBM Plex Mono** for figures, IDs and line labels, taken from Markup. This is where the crisp, technical feel comes from.

### Line language (from Markup)

- **Hairlines:** 1 px ink rules and frame crosshairs in the page corners.
- **Leader lines:** a dot on the object, an elbowed line, then a mono label. They draw out when something comes into view.
- **Dimension lines** with end ticks, for measured things such as the score against the 69 cap or the IQR fences.
- **Motion:** lines draw once, then hold still. There is no ambient motion, and under reduced motion every line is shown already drawn.

## Site map

| Page | Purpose |
|---|---|
| **NUMEK** (landing) | Company, mission, the camera across all three products |
| **DataTrust** | Full product page |
| **ConfidenceGuard** | Product page, marked *in development (CG1 implemented, awaiting review)* |
| **HallucinationGuard** | Short dummy page, marked *research direction, prototype placeholder* |
| **DataTrust app** | The Modules workspace, refined |
| **Adult result** | The Modules results page, refined |

In the lab, this becomes one new concept with its own page switch. The other 21 concepts stay untouched.

## Page by page

### NUMEK landing (Product Camera)

1. **Hero.** A short mission line, set large: *"Evidence for every AI decision."* Below it, three product windows sit side by side on paper, each in its product colour. Leader lines draw out to their names and statuses.
2. **Camera tour.** About seven stops in total, much shorter than Product Camera's eleven.
   - **DataTrust window, four stops:** the real Modules dashboard. Stops are the score with its dimension line and cap, the findings, the row evidence marked in coral, and the run list. Leader lines label each stop.
   - **ConfidenceGuard window, two stops:** a CG1 workbench screen drawn in the system, using its real recorded German Credit evaluation. The stops are the 72% accuracy and recall on bad credit of 13 of 60, marked in coral.
   - **HallucinationGuard window, one stop:** a dummy screen, labelled clearly.
3. **One standard of evidence.** Four short principles: evidence before verdicts; a report, not a certificate; your data stays where it is; a score only where it means something.
4. **Three product bands.** A full-width band per product in its colour, each linking to its page.
5. **Close.** "Start with DataTrust" with the run command, then the footer.

### Product page template (Markup, Modules and Two Readings)

The same sections appear on every product page, so the pages feel like one family:

1. **Hero:** a Markup-style drawing of the product's own object, with leader lines.
   - **DataTrust:** a dataset drawn as a technical object, made of column strips, gaps, and the split of the target column. It is not a full table.
   - **ConfidenceGuard:** predictions drawn as a confidence chart, with the confident errors called out.
   - **HallucinationGuard:** a paragraph with one claim bracketed (dummy).
2. **What it checks:** Modules tiles in the product's shades. Each tile opens into a chapter.
3. **Command-line strip (Two Readings):** the real command and its output on one side, the report summary on the other.
   - **DataTrust:** `datatrust audit …`
   - **ConfidenceGuard:** `confidenceguard evaluate --spec evaluation.json`
   - **HallucinationGuard:** none.
4. **Reports and running it:** the formats, local-first facts and requirements.
5. **Status band:** stated honestly (available, in development, or research).
6. **Next product:** links onward, so the pages chain together.

### App and results (Modules, refined)

- **App.** The Modules workspace: a run rail and module tiles in DataTrust's shades. Findings are marked in coral, and an opened tile shows its chapter with Markup leader lines on the drawing. The header carries a product switcher with DataTrust active and the other two shown with their status.
- **Results.** Adult as the Modules report: the eight report topics as tiles, and the score drawn as a dimension line against the 69 cap.

## Adding a future product

A new product needs four things: a colour from the reserved Deep water family, one hero drawing, its tiles, and its command-line strip. It then gets a window in the landing camera and a band on the landing page. Nothing else changes.

## Build order, with a check after the first step

1. **System and NUMEK landing:** tokens, the line kit, the hero and the camera tour. **I stop here so you can review.**
2. **DataTrust page.**
3. **ConfidenceGuard and HallucinationGuard pages.**
4. **App and results.**

## Ground rules (unchanged)

- Real figures only, with illustrations labelled.
- No hosted monitoring, certification or collaboration claims.
- Only classification runs carry a score.
- The ConfidenceGuard and HallucinationGuard statuses are shown exactly as above.
- Everything stays inside `frontend-visual-lab-v3`, with nothing committed.
