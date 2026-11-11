# NUMEK visual lab v2 — revised direction review

The first five proposals were rejected. They are preserved in `archive/round-01/`.

Round two is a replacement set of **five live direction studies**. Each contains an independently composed opening, actual licensed typography, original graphics, a client-side interaction, and an application/results treatment. The complete landing pages and three-screen prototypes still await the creative-direction checkpoint requested in the brief.

From the repository root:

```sh
python3 -m http.server 4175 --bind 127.0.0.1 --directory frontend-visual-lab-v2
```

- Full-size review: http://127.0.0.1:4175/
- Comparison: http://127.0.0.1:4175/comparison.html
- Research, motion previews and critique: http://127.0.0.1:4175/research/round-02/
- Standalone studies: http://127.0.0.1:4175/directions/01.html through `05.html`
- Rejected set: http://127.0.0.1:4175/archive/round-01/

The launcher’s “Full view” opens a standalone study. In each study, scroll into the application and switch between overview and evidence tabs. Direction 01’s round evidence seal aligns the layers; direction 03’s chart control switches the dimensional rendering to a flat labeled plot; direction 04 opens the population context for an exact source row.

No dependency installation is required. Fonts and license notices are copied locally from already installed Fontsource packages. No external resources are required to view the NUMEK studies. Stop the server with Ctrl+C.

`directions/build.py` regenerates the HTML from the existing stored regression fixture; it never runs an engine or rewrites validation evidence. Each direction owns its own CSS and page composition. Shared code is limited to reset/font declarations, low-level chart/table rendering and accessible local interactions.

`captures/` contains genuine browser captures. The motion GIFs use sequential actual browser frames with reading holds; they are sampled previews rather than continuous video. `research/round-02/` contains additional genuine reference captures and explicitly scoped observations. The earlier research remains available with its first-round archive.

All changes are confined to this folder. Production, Python, Flask, reports, tests, validation evidence and both other experiments remain untouched. No commits, pushes or deployment.
