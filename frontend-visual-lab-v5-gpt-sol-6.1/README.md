# NUMEK visual lab v5

The rejected first round is preserved under `archive/rejected-round-01/`. The active replacement is `research/round-02/`. None of the rejected SVG studies or their generator is reused.

## Run

From the repository root:

```sh
python3 -m http.server 5175 --bind 127.0.0.1 --directory frontend-visual-lab-v5-gpt-sol-6.1
```

- Live direction studies: http://127.0.0.1:5175/research/round-02/
- Research, motion captures and all fifteen screen comparisons: http://127.0.0.1:5175/research/round-02/research.html
- Example direct route: http://127.0.0.1:5175/research/round-02/?concept=c&screen=results

The top review control selects a direction. Landing, Application and Analysis switch its three views. Design notes describe actual influences, motion, product boundaries and weaknesses.

No install or build is required. Fonts and public sample data are local. The studies make no external requests unless a reference link is opened. Font licenses accompany the local files.

## Review status

This is the revised creative-direction checkpoint: five browser-based composition and motion studies, two marketing scenes each, with application and analytical result proofs. Complete prototypes and full landing narratives follow direction review.

Evidence is under `research/round-02/evidence/`. Desktop captures use 1440 × 900; phone captures use 390 × 844. Motion GIFs use actual browser screenshots and recorded frame intervals, with longer opening/closing holds for readability.

All work is isolated here. No production sources, existing experiments, tests, reports, validation evidence or repository context documents were modified. No commits or pushes.
