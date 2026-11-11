# NUMEK visual lab v4

Status: **creative-direction review; awaiting the user’s checkpoint decision**.

This folder currently contains a visual research board and five original static composition studies. It does not yet contain the five runnable product prototypes requested for the next phase.

## Review locally

Open `research/index.html`, or serve it:

```sh
cd /Users/drivyaanshyadav/Desktop/Numek/frontend-visual-lab-v4
python3 -m http.server 4314 --bind 127.0.0.1
```

Visit **http://127.0.0.1:4314/research/**. Use the five direction buttons to compare landing, home and results compositions, then inspect the attributed reference captures below. Fonts and screenshots are local; the board works without remote assets.

- `research/sources.json`: live inspection observations, attribution and limits.
- `research/directions.json`: five proposals, full-page progression, motion and tradeoffs.
- `research/content-evidence.json`: selected facts from existing Bike Hour validation reports.
- `research/motion/lpas/`: ten genuine sequential browser captures, with timestamps. This is a sampled scroll sequence, not a real-time recording.
- `research/styleframes/`: original SVG composition studies. The board uses inline SVG with bundled fonts; standalone SVG viewers may use fallback fonts.
- `research/build_board.py`: rebuilds data and markup from preserved repository examples; reads production evidence without modifying it.

The references are design research, not reusable NUMEK brand assets. The source list distinguishes live observation, case-study reading and incomplete rendering. No screenshots from prior NUMEK experiments were used as design references.

After approval: implement five independent visual systems, 15 principal screens, a comparison launcher, responsive/reduced-motion treatment, browser captures and critical final comparison. Shared fixtures are permitted; a shared visual template is not.

Production and previous labs are unchanged. No commit, push, deployment or production integration.
