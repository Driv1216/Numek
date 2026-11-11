# CG5 engineering verification — 2026-11-04

This is the **original implementation's historical verification record**. The
independent review subsequently reproduced material defects on this exact source.
The authorized R01–R09 correction pass, plan reconciliation and new verification
are recorded in [the correction ledger](review-corrections-20261104/REVIEW_CORRECTIONS.md).
The subsequent D1–D5 pass is recorded in [its correction report](defect-corrections-20261105/DEFECT_CORRECTIONS.md).
CG5 is not founder-accepted. Original receipts and workload measurements below are
preserved; they are not relabeled as corrected-runtime evidence.

The implemented story is: **Decision policies authoring → owned local API jobs →
role-restricted prediction/outcome evidence → supervised optimization → frozen
claims and reserved assessment → immutable browser/report evidence.** Python,
CLI, API and workspace services use the same contracts and analytical services.

Engineering verification is complete for the delivered, registered scope. This
record does not confer founder acceptance, deployment approval, new CG4 research
qualification or universal capacity. Review ZIP packaging remains a later workflow.

## Source and environment

- Starting modified/untracked tree: `implementation_baseline.json`, 374 captured
  files, digest `c45ce97a705fb25f8d82f58afd6cea72a0dd92aa1353e8e0da77144860f49c61`.
- Final runtime/assets/schema map: `results/final-source.json`, digest
  `48dda6c6562cd30710e0ee03d21cc9774cc6122b17c55db31054cf9517497099`.
  Its scope is the recorded Python, JavaScript, HTML, CSS and JSON files under
  `src`; this document and other documentation are outside that digest.
- The map was checked after resuming: no source changes since the saved checkpoint.
- `results/source-preservation.json`: no missing starting files; DataTrust source
  hashes match the captured starting state. Existing CG4 changes were preserved.
- Verified runtime: macOS arm64, Python 3.13.17, NumPy 2.4.6, SciPy 1.18.1,
  bundled HiGHS 1.12.0. MILP admission remains bound to that registered solver pair.
  No dependency installation or replacement was performed.
- PDF rendering used the existing native libraries with
  `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib`. The verification host was
  loopback-only and was shut down when work was paused.

## Correctness and interfaces

| Gate | Actual result | Evidence |
|---|---|---|
| Complete CG1–CG5 suites plus DataTrust host/API/web checks | **549 passed, 1 skipped**, 548.30 seconds | `results/closure-tests.log` |
| Final assessment, solver-warning/decoding and scheduled-look checks | **23 passed**, 24.32 seconds | `results/final-affected-checks.log` |
| Final scheduled-look API and policy CLI/API/history/artifact checks | **5 passed**, 23.07 seconds | `results/final-interface-checks.log` |
| Strict CG1–CG4 generated schema references | **63 passed** | `results/schema-cg1-cg4.json` |
| Strict CG5 schema positive/negative references | **38 passed** | `results/schema-cg5.json` |
| Fixed null/power diagnostics | **0/6 null supported; 6/6 power supported**, predeclared checks passed | `results/finite-20261104/finite-diagnostics.json` |
| Final local/shareable three-task reports | **6 PDF/HTML/JSON sets**, privacy text checks passed | `results/pdf-final-audit.json` |

Counts in the focused gates overlap the comprehensive gate and must not be added
as unique test counts. The single skip is the in-suite CG2 JSON Schema check:
`jsonschema` is absent from the analytical runtime. The existing separate schema
runtime validated those CG2 transport examples as part of the 63-check schema gate.

The comprehensive command was:

```sh
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib PYTHONPATH=src:. \
  validation/cg4/py313q.nosync/bin/python -m pytest --import-mode=importlib \
  tests/cg1 tests/cg2 tests/cg3 tests/cg4 tests/cg5 \
  tests/test_app_api.py tests/test_app_default.py tests/test_web.py -q
```

The first collection attempt used pytest's default import mode and encountered
CG4 relative-import collection errors. The successful gate used importlib mode;
no production change was needed. Focused checks cover the final CG5 assessment
changes made during closure. Unaffected broad checks were reused according to
`agents/skills/verify/skills.md`.

The checks cover typed interpretation and Kleene precedence, exact/native value
semantics, task actions and cost roles, action accounting and denominator oracles,
S-only selection under E input/label mutation, exhaustive sweep/two-cut/MILP
references, incompatible encodings, solver options/warnings/scaling/decoding,
bounded search standing, finite intervals/components/multiplicity, provenance and
exposure refusal, interrupted reservations, scheduled looks, frozen upstream CG2
and CG4 inputs, historical reconstruction/restatement, packet lifecycle,
shareable-only export and Python/CLI/API three-task parity. Shared worker,
publication and catalog evidence is reused through the applicability map in
`README.md`; DataTrust analytics were not modified by CG5.

## Served workflow evidence

| Boundary | Status and observed evidence |
|---|---|
| UI renders | Decision policies workflow, task authoring, nomination, claim planning and retained records rendered in the served local workbench. |
| Client → API | Inspect/optimize/preview/freeze/assessment/export jobs completed through opaque handles, revisions and fingerprints. Separate tests cover ownership, CSRF and conflicts. |
| API → data | Supplied S/E role columns were admitted; analytical work used the spawned worker. Python/CLI/API outputs agreed for binary, multiclass and regression stories. |
| Data → response | Binary E assessment returned support 200, estimate 1.0, interval **0.9817246596–1.0**, required claim `supported`. |
| Response → UI | Final claim table displayed `supported`, **0.98172–1.0000**, support **200**. Shareable HTML/PDF/JSON download links were present. |
| Immutable reopening | Retained assessment reopened after a server restart and exported without analytical rerun. Protected frozen-family file upload succeeded. |

The guided multiclass confidence family completed grouped search and nominated
observed accuracy **0.9333333333**. The guided regression family evaluated four
finite numeric actions and completed enumeration, with nominated MAE **2.5**.
The richer contextual multiclass MILP and asymmetric regression economics are
covered by the service/interface checks and measured workloads below.

`results/browser-final.jpg` captures the reopened assessment table, retained
records and canonical export links. Browser observations were captured during
the implementation session; restarting the same completed flow merely to repeat
that evidence was unnecessary after the source identity check.

## Defects found and corrected during closure

1. Development preview matched only serialized metric digests. JavaScript can
   round-trip `1.0` as `1`, causing a retained metric to appear missing. Preview
   now compares validated metric semantics against the frozen S design; it reads
   no E values. Retained reopening showed support 200, projected support 1000 and
   an illustrative CP interval, with `alpha_spent=false` and
   `assessment_values_accessed=false`.
2. CG5 inherited the investigation ledger's same-family recomputation exemption.
   CG5 now refuses previously assessed E unless a predeclared scheduled look
   authorizes that operation. Regression checks cover repeated-use refusal and
   scheduled-look continuity, including the owned API job path.
3. Nomination-based claim planning depended on the nominee being in the first
   candidate page. It now uses the nomination identity from the summary.
4. Protected browser imports parsed and reserialized artifact JSON, potentially
   changing numeric representations and invalidating bindings. Imports now send
   the original JSON text; a served frozen-family upload passed.
5. The initial policy PDF led with a generic list of runs. The canonical template
   now places the decision record and nomination first. Final reports were
   regenerated from immutable completed results, with **no reanalysis**.

## Representative workload measurements

`results/qualified-20261104/measurements.json` records exact runtime, settings,
counters and source hashes. Its source was unchanged during the measurement.
Other correctness work was running during this session; these are engineering
workload observations, not isolated throughput benchmarks or capacity limits.

| Workload | Planned events | Elapsed selection/replay | Sampled peak worker RSS |
|---|---:|---:|---:|
| Binary grouped threshold sweep | 4,000 | 25.904 s | 181,534,720 bytes |
| Multiclass contextual fixed-cell MILP | 1,200 | 13.592 s | 199,737,344 bytes |
| Regression finite quantity choices with pinball economics | 1,200 | 6.317 s | 166,166,528 bytes |
| Frozen historical replay, retained save and reopen across two windows | 4,000 | 6.355 s | 322,633,728 bytes |

The sweep reported complete grouped empirical search. The contextual MILP used
one solver call and reported optimality for the encoded model, with authoritative
policy re-evaluation. Regression reported exact finite enumeration. Historical
replay preserved its frozen policy and immutable selection and was reopened from
the retained workspace.

The only later Python modification was repeated-assessment admission in
`policy_assessment.py`; the measured selection/replay/history paths were unchanged.
The final affected checks establish the changed admission behavior. This explicit
applicability boundary is recorded in `results/final-source.json`.

## Reports, privacy and scientific limits

Final reports are under `results/qualified-20261104/reports-final`.
`final-reports.json` in the parent directory records their hashes, template hashes
and `reanalysis=false`. Six final PDFs were reopened and text checked. Seventeen
first/central/final pages across the reports were rendered and visually inspected;
the contact sheet and page PNGs remain in local PDF-QA scratch. The decision
record appears on every first page; inspected tables and flowing text were legible.

Shareable JSON, HTML and extracted PDF text omitted tested private paths,
executable definitions/digests, source-column markers and private economic names.
Regression economic comparisons were jointly withheld. Separate export tests
establish that shareable-only export creates no protected bundle. These checks
are disclosure-contract evidence, not an anonymity guarantee.

An earlier PDF attempt lacked the native-library environment and preserved valid
HTML/JSON. Another early workload fixture used an invalid probability-constructor
keyword and was repaired. Those partial runs are not passing qualification
receipts; the qualified workload and final report receipts above are authoritative.

The twelve fixed null/power stories satisfy their predeclared regression checks;
they do not establish a general false-positive rate, power guarantee or new
scientific method. General unequal clusters, temporal/common-shock inference,
unbounded means and unsupported nonadditive claims retain explicit refusals.
Selective labels, model-implied economics, deferral quality, batch coupling,
historical replay and solver certificates retain their documented qualifications.
No review ZIP or deployment was produced.
