# NUMEK / new composition review

The first two proposal sets were rejected and remain preserved under `archive/round-01/` and `archive/round-02/`.

This replacement set is in `round-03/`: five live art-direction proofs, each with an original visual, a working interaction, an application study and an evidence view. The complete landing pages and full three-screen prototypes remain after the creative-direction checkpoint requested in the brief.

Run from the repository root:

```sh
python3 -m http.server 4175 --bind 127.0.0.1 --directory frontend-visual-lab-v2
```

- Full-size selector: http://127.0.0.1:4175/?direction=01
- Comparison: http://127.0.0.1:4175/comparison.html
- Reference extraction and motion previews: http://127.0.0.1:4175/research/round-03/
- Standalone studies: http://127.0.0.1:4175/round-03/01.html through `05.html`
- Evidence deep link example: http://127.0.0.1:4175/round-03/04.html?view=finding#workspace
- Narrow embedded viewport: http://127.0.0.1:4175/round-03/responsive.html?direction=01

No installation or build step is required. Three.js is vendored with its license from the already installed sibling experiment. Fonts and their license notices are local. `round-03/build.py` regenerates the direction HTML from stored regression evidence; it does not run analysis or write validation files.

Each direction owns its composition and CSS. Shared code supplies the identical source evidence, basic typography declarations, chart/table primitives, interaction state and verification page. The application compositions differ: a wide aligned chart, report reading, numeric overview, guided investigation and evidence atlas.

`round-03/captures/` contains actual browser captures and two motion GIFs assembled from 18 sequential browser frames each, with reading holds. `research/round-03/` holds genuine reference captures, precise observations and critique.

All changes remain within this isolated folder. No production code, Flask route, report, engine, validation fixture, test or sibling experiment was modified. No commit, push, integration or deployment.
