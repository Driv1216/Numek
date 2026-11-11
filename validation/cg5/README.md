# CG5 implementation and verification

## CG5 completion — 2026-11-06

The founder has confirmed CG5 is fully completed, including implementation,
independent review, R01–R09 and D1–D5 corrections, engineering verification and
the implementation understanding gate. This decision supersedes pending-review,
pending-understanding and pending-founder-acceptance language retained below.
CG1–CG5 are complete within their approved scopes; scientific limitations and
source-specific historical evidence remain unchanged. No CG6 work is implied.

The [final implementation explainer](CG5_FINAL_IMPLEMENTATION_EXPLAINER.md) covers architecture, source files,
policy semantics, optimization, statistical assessment, four execution scenarios,
corrections, limitations, glossary and 15 technical questions. Its quick
requirements review found all 13 requested areas present and no material issues
in the technical spot-checks; no test suite was rerun for that document review.
The explained 190-file runtime identity is
`7d3f64affcbc9491223e23294482149848f3bd945a7aaefce33af4af7b3fc3b9`.

CG5 is not founder-accepted. The independent review identified material defects in
the original verified implementation. See [the authorized targeted correction
record](review-corrections-20261104/REVIEW_CORRECTIONS.md) for R01–R09, historical
constraints, hybrid search, tie refinement, admission guidance and new evidence.
The second re-review identified D1–D5; the targeted corrections and current evidence
are in [the D1–D5 correction report](defect-corrections-20261105/DEFECT_CORRECTIONS.md).
The original verification and workload receipts remain historical.

The approved revised plan is implemented in six dependency units: contracts and
interpreter; authoritative action evidence; bounded optimization; frozen independent
assessment; historical/artifact integration; Python/CLI/API/browser interfaces.
This directory records source identity, synthetic engineering checks and measured
workloads. It does not confer causal policy value, deployment approval or universal
capacity. A review ZIP is a separate later workflow.

`implementation_baseline.json` hashes the modified/untracked CG4 starting source,
rather than committed HEAD. Existing CG4 scientific qualification limits remain
in force. General unequal-cluster, temporal, ranking-percentile and unbounded
population inference have not been newly qualified.

## Verification entry points

- `tests/cg5`: interpreter truth tables, action/loss/denominator oracles, exact sweep,
  fixed-cell solver versus exhaustive references, bound refusal, exposure, immutable
  families, scheduled looks, upstream applications, lifecycle and interfaces.
- `qualify_schemas.py`: strict generated-schema positive/negative references.
- `measure.py`: one grouped sweep, contextual MILP and immutable historical workload,
  plus representative three-task report exports.
- `finite_diagnostics.py`: six fixed null and six fixed power stories. Before
  execution, expected null supports are at most one of six and power supports at
  least five of six. These small synthetic diagnostics are regression evidence,
  not a general statistical qualification campaign. Seeds and sizes stay fixed.
- `serve.py`: loopback-only synthetic host for served browser verification.
- `results`: receipts and scope-specific evidence. Generated source data, private
  workspaces and protected bundles are scratch, never portable product exports.

Run with `PYTHONPATH=src` and the retained CG4 Python 3.13 verification environment.
The solver profile requires SciPy 1.18.1 / bundled HiGHS 1.12.0; no dependency is
installed automatically. Schema validation uses the separate existing schema runtime.

## Reused evidence and applicability

| Existing evidence | Applicability to CG5 | Additional CG5 check |
|---|---|---|
| CG1 normalized inputs, native reducers and source guards | Same constructors, supplied inputs and issued-only metrics | Hypothetical action relation, new opportunity denominators and cost contributions |
| CG2 fitted application/conformal kernels and protected membership | Frozen upstream artifacts; no CG5 fitting | Imported calibrator application, missing sidecar refusal and uncertainty state arithmetic |
| CG3 reconstruction/authority/maturity and immutable catalog | Same CG3 selections, catalog v2, revisions and fact codecs | Frozen policy across windows, mix/drift adapters, restatement and packet dependency graph |
| CG4 exact predicates, timing and membership | Existing frozen region application; no rediscovery | Ternary routing and missing development-provenance refusal |
| CG4 finite CP/Hoeffding kernels | Same registered numerical construction and scientific restrictions | Policy-specific estimands/components, full family allocation and conservative conditional contrasts |
| DataTrust spawned worker, sampled RSS/deadline/disk and publication | No runtime extraction or new worker | Policy operation supervision, fixed solver limits and interruption-spent reservation |
| Existing packet codec/backup/delete/report exporter | Same bounded packet and canonical HTML/PDF mechanisms | New packet kind, protected family/result reopening, dependency deletion and portable privacy |

Actual command results, measured runtime, browser observations and evidence
applicability are recorded in [VERIFICATION.md](VERIFICATION.md).
