# DataTrust app and results: research and proposal

Step four of the blend plan. Nothing is built yet; this needs your approval first.

## 1. What I researched

### 1.1 The real DataTrust interface

Sources: `src/datatrust/web.py`, `templates/ui.html`, `docs/CURRENT_STATE.md`. All were read, and none was changed. I also ran DataTrust's own read-only inspection on Adult so every screen below uses real content.

**The real app is a guided four-step flow, not a dashboard.**

| Step | Real route | What it shows today (real content for Adult) |
|---|---|---|
| **1 · Upload** | `/` → `POST /upload` | **Mode:** one of nine:<br>• Classification, Regression, Unlabeled<br>• Classification with annotations, Regression with annotations or multiple outputs<br>• Multilabel, Clustering readiness, Anomaly-detection readiness, Profiling with explicit roles<br>**Input:** one CSV, header required, at most 100 MiB.<br>**Privacy:** "processed by this local application and not sent to DataTrust or a cloud service". |
| **2 · Configure** | `/configure` | **File cards:** adult.csv, 5.03 MiB, 48,842 rows, 15 columns.<br>**Preview:** the first 10 rows.<br>**Question:** "What outcome is this dataset meant to predict?", with grouped choices and **no preselection**.<br>**Adult has no outcome-word candidates.**<br>**Nine small-set candidates:** workclass, education, education_years, marital_status, occupation, relationship, race, sex, annual_income_over_50k.<br>**Six advanced choices:** age, final_weight, capital_gain, capital_loss and hours_per_week look continuous; native_country has too many categories. Each needs an extra confirmation.<br>**Optional fields:** name, purpose. |
| **3 · Confirm** | `/confirm` | **Detected task:** binary classification, 2 classes.<br>**Counts:** 48,842 labelled rows, 0 missing labels; target split 76.07% / 23.93%.<br>**Other content:** planned checks, parsing defaults and safeguards, and an acknowledgement box when an advanced target is chosen.<br>**Action:** "Generate reliability report". |
| **4 · Result** | `/result` | **Score:** risk badge and score.<br>**Narrative:** What this means, Why this score, Principal evidence, Recommended next action.<br>**Top risks:** the top three.<br>**Also shown:** parsing review and coverage.<br>**Actions:** View full report, Download PDF, Download JSON (HTML download only for non-classification modes), New analysis. |

**Separate specialist workflows already exist** as their own pages: `/temporal`, `/text`, `/images`, `/cross-representation`, `/m4` (split audit, version comparison, advanced local analysis), and ConfidenceGuard at `/confidenceguard`.

**Hard constraints from the docs:** single-user, loopback only, non-persistent. There is **"no hosted service, accounts, persistent service database or saved report history."** Starting a new analysis discards the previous one.

### 1.2 What you loved: Modules, re-captured and reviewed

- A bold mosaic in which every tile carries a live drawing from the run.
- Huge, confident type.
- A tile grows into a full-colour chapter that holds the real evidence, such as the two contradicting rows side by side.
- Results as the report's eight topics in tiles.

**Its problem:** its left-hand runs list implies a saved history that DataTrust does not have.

### 1.3 Library references that fit an app (from `research/r4/notes.md` and round one)

- **Imersion:** a pipeline as a rail of named steps, with a large card for the current step. This maps directly onto the real four-step flow.
- **The Robot and Me:** two depths per item, "Open" and "Look under the hood". This suits a finding's plain meaning versus its exact fields.
- **Townhouse:** the product reads your artefact and draws it as one place. Chapters are close-ups carrying one real card, with mono labels on parts.
- **Heron AI:** an issue is a mark on the actual artefact, not a card beside it. This is the root of Markup.
- **Shadow Fell:** one instrument per screen, with presets written as plain questions.
- **Linear:** real UI at true scale. Restraint.

### 1.4 How comparable tools present results (public docs, read 19 Oct)

- **ydata-profiling:** a long generated report organised as Overview, Alerts and Variables.
- **Great Expectations:** Data Docs, where a results page is a list of pass/fail tables.
- **Evidently:** reports plus a monitoring dashboard.
- **Cleanlab Studio:** issues surfaced in a data-editing interface.

None of them leads with a guided question ("what outcome is this meant to predict?") or one explained verdict. **DataTrust's differentiator is interpretation and workflow**, which the master context also says. So the app should make the guided flow and the explained result excellent, rather than imitate a dashboard.

## 2. The decision I need from you first

**Saved runs.** DataTrust keeps no history; every earlier dashboard concept, including Modules, showed one.

- **A · Honest to today (recommended).** The app is the guided flow. A small "This session" note says the result disappears on New analysis, so download it first.
- **B · Propose history.** A "Recent reports" rail, clearly labelled *proposed, not in DataTrust today*. This is a product decision for you, not a design detail.

## 3. Proposal: one guided flow, then the result as Modules

### Shell (every screen)

- **App bar:** the DataTrust mark in tide, and `local · 127.0.0.1:8000` with a live dot.
- **The step rail (Imersion, drawn in Markup's line style):** four numbered nodes, Upload, Configure, Confirm and Report, on one hairline. The line fills coral as you advance, and done steps can be revisited.
- **"Other workflows" menu:** Time, Text, Images, Records ↔ documents, Comparison. These are the real separate pages, shown as links rather than built here.

### 1 · Upload: the Drop, made real

- **Modes:** the three main modes as large Modules-style tiles: Classification (explicit target), Regression (numerical target), Unlabeled (profile all columns). Each tile has a small line drawing, and a "More modes" row lists the other six.
- **The drop zone:** the hero's animated intake, now as the actual control (marching ants, tray).
- **Facts line:** CSV · header required · up to 100 MiB · nothing leaves this machine.
- **Prototype only:** "Try it with Adult" uses the bundled real Adult inspection, because a file picker can't run DataTrust in the lab.

### 2 · Configure: one question, asked well

- **File cards:** adult.csv · 5.03 MiB · 48,842 rows · 15 columns. The first 10 rows sit in a calm table that scrolls sideways.
- **The question, set large:** *What outcome is this dataset meant to predict?*
- **The choices:**
  - The real grouped options, with nothing selected.
  - Each row shows its name, distinct values, missing count and the real explanation.
  - Advanced choices are folded away and carry their real reason, such as "looks continuous" or "too many categories".
- **Selection feedback:** choosing one draws a Markup bracket around it and shows its real class split, for example annual_income_over_50k: 2 values.
- **Optional fields:** name and purpose.

### 3 · Confirm: show what will happen

- **Detected task:** Binary classification · 2 classes.
- **Counts:** 48,842 labelled rows · 0 missing labels.
- **The split:** drawn 76.07 / 23.93 with a dimension line.
- **Planned checks:** the six checks from the hero, as a list that hasn't run yet.
- **Safeguards and parsing defaults:** as one quiet mono line.
- **Advanced targets:** choosing one brings up the real acknowledgement box ("I still want to use …").
- **"Generate reliability report":** runs the hero's checking sequence in place. The six checks resolve, the score lands, and the flow moves to the result. The real run takes 0.18 s; the motion is a presentation of it, and the screen says so.

### 4 · Result: Modules as the spine, with the real result content

- **Top band:**
  - **The score tile:** 69.0, Elevated, with evidence 89.15 held at the 69 cap, drawn as a dimension line.
  - **Four plain blocks** using the real UI's own headings: *What this means · Why this score · Principal evidence · Recommended next action*.
- **The mosaic:**
  - **Tiles:** one tile per check, in DataTrust shades. Finding tiles are marked coral and carry live drawings; clear checks are quiet.
  - **Opening a tile** grows it into a chapter with two depths (Robot & Me):
    - **Open:** the plain meaning and the marked evidence. These are the hero's evidence views, larger: the class split, the hours histogram with fences, the two contradicting rows, the flagged column.
    - **Look under the hood:** the exact finding fields (code, severity, finding, evidence, modeling impact, recommendation, score effect).
- **Parsing review and coverage:** a real section of the result that earlier concepts skipped, as a thin Markup strip.
- **Exports, faithful to the real buttons:** View full report · Download PDF · Download JSON · **New analysis**, which warns that this session's result will be cleared.
- **Report index:** the eight report topics as small tiles (Modules' results idea) that open the full-report view.

### Other result types

- **Regression (Bike):** "No overall score, by design" replaces the score tile, and the mosaic shows Bike's real findings.
- **Classification:** Adult is built end to end.
- **Bike:** shown as a second example only if you want it.

### Mobile

- The step rail collapses into a "2 of 4" pill.
- Mode tiles and target choices stack.
- Chapters open full-screen.

## 4. Build order, with a checkpoint after each

1. **Shell, Upload and Configure.** Stop for review.
2. **Confirm and the generate sequence.** Stop for review.
3. **The result.** Stop for review.

## 5. What stays honest

- Every number comes from Adult's real inspection, result or report.
- The prototype's "Try it with Adult" and replayed run are labelled as such.
- There is no history, account, monitoring or collaboration.
- The score appears only for classification.
- The specialist workflows are linked, not reinvented.
