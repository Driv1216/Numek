# NUMEK: foundation first, then one direction

A checkpoint document. Nothing has been built from it yet.

## Why the twenty didn't fit

Each round started from other companies' websites and pointed their techniques at Adult's numbers. The result was a set of styles applied to a data report, not a company. Three habits made it worse:

- **The tool, not the company.** Every direction was about DataTrust's output. None was about what NUMEK believes or why it exists.
- **Numbers as content.** 48,842 / 89.15 / 69.0 appeared on every screen, so the pages read as reports rather than as a brand.
- **One trick per direction.** Round three in particular: a cutaway, a relief, a stack. A trick is not an identity.

## What NUMEK is (from its own documents)

From `docs/NUMEK_MASTER_CONTEXT.md`:

> Teams using AI for real decisions need inspectable evidence about data before training, model behavior during deployment, and generated outputs after generation.

Four things follow from that sentence and the decisions recorded in the document:

1. **There are three moments.** The data *before* training, the model *during* deployment, and the output *after* generation. NUMEK's mission spans all three.
2. **The stakes are real decisions.** Credit, insurance, hiring and other high-stakes systems are named as the original vision.
3. **Evidence comes before verdicts.** NUMEK chose a reliability report over a certificate, transparent sub-scores over an opaque number, and guardrails so that "severe risks cannot be concealed by healthy averages."
4. **It runs where the data lives.** Execution is local-first.

The initial user is an ML/data lead who has to explain reliability to a CTO, a risk lead or a customer. The site therefore has to work for both of them at once.

## Your answers

- **Audience:** everyone at once. That means engineers, AI/risk leaders and investors or partners.
- **Feeling:** a mix of serious and authoritative, ambitious and frontier, and a sharp developer tool. I would assign one job to each:
  - **Authority comes from the method:** precise drawing, visible rules, no hype words.
  - **Ambition comes from the mission:** large type, scale, and the full arc from data to output.
  - **Sharpness comes from the product:** real commands and real output, shown at true scale.
- **Lead with the mission.** DataTrust is the first proof, not the headline.
- **Closest so far:** round one (Markup, Every Row, The Issue, Passage, Two Readings) and Modules.

What those six share: each one has a **system**, not a trick. There is a repeatable grammar (a mark on the evidence, a tile with a live drawing, a chapter field) that could run a whole company's materials. That is what to keep.

## Proposed direction: The Evidence Mark

**Idea.** NUMEK owns one graphic act: **marking the evidence.** It uses a precise corner bracket with a small numbered tag, drawn exactly around the thing being verified, whether that is a row, a prediction or a sentence. It is the logo, the illustration style, the UI pattern for a finding and the report's annotation, all at once. It inherits Markup's strongest idea and lifts it from one dataset to the whole company.

**Mission spine.** The landing page follows *the life of one AI decision* through the three moments:

| Moment | What's marked | Status shown honestly |
|---|---|---|
| Before: the data | Two rows identical in every feature, with different labels | **DataTrust**, available now, with real evidence |
| During: the model | A confident prediction that turns out wrong | **ConfidenceGuard**, see the question below |
| After: the output | A generated sentence with an unsupported claim | **HallucinationGuard**, research direction, labelled |

### Landing structure

1. **Hero.** A short mission line set very large. Working draft: *"AI makes real decisions. NUMEK shows the evidence."* Beneath it is one decision drawn as a path: a data row, then a model score, then a generated sentence. Three evidence marks snap onto it in turn.
2. **The problem.** One proof only: an average that looks healthy (89.15) hiding a critical weakness, and the guardrail that refuses to let it (69.0). That is the whole philosophy in one figure. It is the only place the score appears on the landing page.
3. **Three moments.** Three tiles using Modules' grammar: ink for what was found, ghost for context. DataTrust's tile is live and opens into depth. The other two are drawn and labelled as their real status.
4. **DataTrust, in depth.** The marked dataset, from Markup and Every Row: four real findings, each marked on its evidence, then the six representations it reads, as tiles.
5. **Two readings.** The real CLI and the report a risk lead reads, side by side (from Two Readings). This section is for engineers and decision-makers together.
6. **Principles.** A short, authoritative manifesto in The Issue's editorial register: evidence before verdicts; reports, not certificates; your data stays on your machine; methods you can read.
7. **Close.** "Run it on your own data": two commands, plus a plain line on research directions.

### Identity system

| Part | Proposal |
|---|---|
| **Wordmark** | NUMEK in a wide grotesk, framed by the evidence mark's corner brackets. The mark works alone as an icon. |
| **Type** | Archivo, using its width axis: expanded for mission statements, normal for text. IBM Plex Mono for evidence. One family with two voices: frontier and exact. |
| **Colour** | Paper `#F4F3EF` and ink `#111315` as the base. One signal colour, used only for marks: `#FF4A1C`. Three quiet moment colours (data slate, model ochre, output sage) appear only on their tiles. |
| **Grammar** | A finding is always a mark, a capability is always a tile, and a chapter is always a full-width field. The same three rules run the site, the app, reports and decks. |
| **Motion** | Marks draw on, snap to their evidence, then hold still. Tiles grow into chapters. There is no ambient drift and nothing moves without meaning. |

### App and results (after the landing is approved)

The app is a workspace where every finding is a mark on its evidence, with tiles for runs. Results is the report as The Issue's reading room, with marks in the margin. Both come only after the landing page lands.

### What it will not do

- No numbers as decoration. Figures appear only where they prove a point.
- No single-trick hero.
- No dark AI gradients or glow.
- No claims beyond what exists: no certification, monitoring or hosted service.

## Alternative, if the mark feels too graphic

**The Record.** The same mission spine, presented as an institution's publication, built on The Issue's register: covers, contents and chapter fields. This is more authoritative and less tool-like. I recommend the Evidence Mark because it serves all three feelings, where The Record mostly serves one.

## One question before building

The original brief said ConfidenceGuard and HallucinationGuard are research directions only. `docs/NUMEK_MASTER_CONTEXT.md` (17 Oct) now says **ConfidenceGuard CG1 is implemented** as a separate prediction-evaluation product and is awaiting your review. How should the "during" moment be shown: as research direction, or as a second product in development?
