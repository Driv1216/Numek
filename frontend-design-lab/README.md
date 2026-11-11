# NUMEK DataTrust — Frontend Design Lab

Five isolated React + TypeScript prototypes. No production code was changed; no commits or pushes. Preview servers were stopped at the user's request.

## Run

```sh
cd /Users/drivyaanshyadav/Desktop/Numek/frontend-design-lab
npm ci
npm run dev
```

Dependencies are already installed in this workspace. `npm run dev` is sufficient now. Stop with Ctrl+C.

- Launcher: http://127.0.0.1:5178/
- Guided Studio: http://127.0.0.1:5178/guided
- Analyst Console: http://127.0.0.1:5178/console
- Evidence Workbench: http://127.0.0.1:5178/workbench
- Decision Edition: http://127.0.0.1:5178/edition
- Analytical Studio: http://127.0.0.1:5178/analytical
- Screenshot gallery: http://127.0.0.1:5178/screenshots/index.html

Append `?view=new` to any concept URL to open its setup journey. The launcher also provides direct setup links and independent side-by-side comparison frames.

```sh
npm run build
npm run preview
```

`build` runs strict TypeScript checking and Vite bundling. `preview` serves the compiled build on the same port. The screenshot gallery is a development/source artifact, not included in the compiled application.

## Explore comparable tasks

1. Start a new analysis. Choose Classification or Connected evidence, select a fixture, inspect its input shape and declare its meaning. Classification requires an explicit outcome; confirmation is required before opening stored results.
2. Open Adult classification. Select findings and inspect the population, implications, recommendations and score effects. The actual conflicting-row excerpt includes CSV lines 850 and 22763.
3. Switch to connected evidence. Inspect A019's discrepancy and A020's competing PDFs. Explore agreement records and the decimal coverage ledger. Open actual copied synthetic PDFs.
4. Read methods, limitations and artifact options. Existing HTML/JSON copies are downloadable; M9 also has an existing PDF. Separate prototype review JSON does not modify analytical evidence.

Console shortcuts: Cmd/Ctrl+K commands; `/` search; J/K or arrow keys move; Enter shows inspector; N opens setup; Escape closes commands. Workbench panes resize via the range control, separator dragging, or focused separator arrow keys. Analytical marks and histogram bins are keyboard-selectable; tables expose the same populations.

## Evidence provenance

- Adult: stored `validation/results/validation_summary.json`, original `validation/reports/adult.html`, and public `validation/data/prepared/adult.csv`.
- M9: `validation/m9/results/reports/final/bounded.json`, original HTML/PDF, and the synthetic `validation/m9/data/bounded` inputs/PDFs.
- Adult: 48,842 rows; class populations 37,155 and 11,687; existing final score 69; evidence-score mean 89.15; critical target-balance guardrail; five conflicting-label groups / ten rows.
- M9 decimal rule: 20 records; 21 candidate occurrences; 18 agreements; one discrepancy; one conflict; zero incomplete records. No M9 overall score.
- Histogram bins are descriptive counts from the pinned CSV. Their selection does not recompute scores or imply a new diagnostic.

All portable fixture copies live in `public/fixtures/`. The Adult JSON is a lab projection of a validation summary, not a newly generated canonical analytical result. M9 JSON is the existing strict result. Source extraction/reproduction scripts in `research/` write only into this lab; they are not required to run the application.

## Deliverables

- `research/DESIGN-RESEARCH.md`: source audit, actual inspected references, borrowed/rejected decisions and access limits.
- `DESIGN-COMPARISON.md`: structural differentiation and practical tradeoffs.
- `screenshots/`: actual browser JPEGs, full-page desktop and 390px examples, connected/classification detail states, and stored report captures.
- `VERIFICATION.md`: completed evidence and limits.
- `src/concepts/`: five separate component trees and scoped styles.

## Boundaries

No real file ingestion, analysis execution, private source resolver, model inference, customer data, persistent history or production integration. Configuration is a fixture preview; M9 uses the known recipe rather than a general recipe editor. Other implemented families are discoverable in the capability map, but only classification and M9 have interactive setup. Reviews live in memory and reset on reload; review downloads are prototype JSON, not production-bound snapshots. DOCX/image/text-specific and optional semantic-model investigation states are documented rather than separately prototyped. M8 audio is deferred.

Existing reports open unchanged. No new PDF generation is simulated. Desktop/narrow screenshots were captured before the last small contrast, progress-label and review-state refinements; no further tests or recaptures were run after the user's stop request.
