# NUMEK visual lab v2

**Status: creative-direction review.** The research board and fifteen static composition drawings are ready. The five interactive prototypes have not been implemented; the brief requests approval of the five directions first.

From the repository root:

```sh
python3 -m http.server 4175 --bind 127.0.0.1 --directory frontend-visual-lab-v2
```

- Review board: http://127.0.0.1:4175/
- Compact overview: http://127.0.0.1:4175/?overview
- All fifteen studies: http://127.0.0.1:4175/studies.html
- References: http://127.0.0.1:4175/#research
- Direction comparison: http://127.0.0.1:4175/#comparison

No installation, production server or backend is needed. Stop with Ctrl+C.

## Contents

- `research/REVIEW.md`: concise proposal and review checkpoint.
- `research/research.json`: sources, actual observations, limitations and capture provenance.
- `research/screenshots/`: genuine 1280 × 720 browser captures. These are attributed reference material, not NUMEK assets.
- `research/directions.json`: proposed identity, landing progression, app structure, results, motion, typography and risks for each direction.
- `research/studies/`: fifteen original SVG composition drawings. Static sketches, not application screenshots. Typography uses local substitutes for the candidate families described in the proposal.
- `research/representative-content.json`: curated facts from existing regression engineering fixtures. No new analytical result is claimed.
- `research/review-captures/`: browser QA of the review board itself.
- `research/build_studies.py`: regenerates the static drawings and curated content from existing repository evidence; writes only inside this lab.

All work is local and isolated. Existing labs, production, tests, reports and validation evidence are preserved. No commits or pushes.

Following approval, each concept will get its own composition, styles and application structure. Only comparable mock content and low-level accessibility utilities should be shared; a common themed screen template would defeat this exploration.
