# M3 internal validation

This namespace retains new evidence without regenerating M1/M2/classification or
historical reports. Engineering checks do not establish external methodology
validity, customer usefulness, label correctness, clustering quality, or anomaly
correctness.

## Sources and reproducibility

`manifest.json` pins official archive/member/prepared SHA-256, actual dimensions,
column mappings, task/configuration, attribution and available license information:

- UCI Energy Efficiency: 768 rows, eight inputs, two outputs. Orientation and
  glazing-distribution codes are declared categorical.
- Mulan Scene: 2,407 rows, 294 features, six XML-declared binary labels. Dense
  ARFF/XML conversion is validation-only; runtime input remains CSV. No explicit
  dataset license was found in the distributed files; public availability does
  not establish an additional license.
- Linnerud: twenty rows, three inputs/outputs, taken from official scikit-learn
  1.7.2 release tables. No runtime scikit-learn dependency; release COPYING is
  pinned with the data and description members.

Pinned archives are under `data/raw/`; official download/source URLs and expected
hashes are in `prepare.py` and the manifest. Preparation needs `openpyxl` for the
Energy workbook and `bsdtar` for Scene RAR extraction. Preparation validates
archive hashes and constructs deterministic CSVs with no label guessing.

```bash
.venv/bin/python -m pip install -r validation/m3/requirements.txt
PYTHONPATH=src .venv/bin/python -m validation.m3.prepare
PYTHONPATH=src .venv/bin/python -m validation.m3.verify
```

Verification works offline with pinned sources and checks existing report hashes.
It independently asserts counts, combinations, cardinality, density, contingencies,
Jaccard, quantile interpolation, centered paired Pearson, target exclusion, source
identity and evidence-reference resolution. Fifteen cases include deterministic
partial-output masks, feature-only clustering/anomaly views, a 240-row/398-column
wide case, empty classification/regression/multilabel supervision, and explicit
intentional absence. Derived views do not establish public anomaly/cluster truth.

## Retained evidence

`results/presentation/manifest.json` records analytical time, measured frame size,
result bytes, environment, presentation counts/bounds/omissions, render time,
HTML/JSON/PDF hashes, and PDF executive/appendix/page budgets. JSON retains all
computed evidence, including details omitted from human reports. `--write-artifacts`
creates a fresh report set; existing PDF/JSON destinations are refused. Use a
separate new evidence directory or preserve/move an agent-owned previous run
before explicitly producing another set; historical artifacts must not be replaced.

The six presentation cases cover Scene, the wide synthetic case, three empty
supervision cases, and partial classification. PDF review renders every page and
inspects wrapping, readable fonts, empty states, denominators, page transitions,
and appendix size. Visual-review and real-browser evidence are recorded separately
under `results/`; they are not simulated user/product acceptance.

Algorithmic tests also run in an isolated Python environment with numpy 1.23.5,
pandas 1.5.3, Flask 3.0.0, Click 8.1.3, Jinja2 3.1.2, and pytest 7.0.0. Frozen
M1/M2 parity is asserted within the current environment; minimum-version checks
use independent mathematical assertions rather than hiding dtype differences.

Broad split/version analysis, disk-backed execution, neighborhood/model analysis,
and other modalities remain outside this milestone.

The final internal verification record is [results/verification.json](results/verification.json).
It distinguishes the full-suite run (271 tests), final focused run (77), and
minimum-dependency run (75), plus four legacy validators and fifteen M3 cases.
[Visual QA](results/visual_qa/manifest.json) retains contact sheets for all 45
reviewed PDF pages. [Browser QA](results/browser/manifest.json) retains seven real
workflow exports and screenshots. Scene and wide reports meet eight/twelve-page
budgets. Final exports reused completed evidence without reanalysis.
