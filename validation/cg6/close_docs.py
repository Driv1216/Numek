"""Finalize engineering documentation only after the finite evidence gate closes."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
CG6=ROOT/'validation/cg6'

def replace_once(path,old,new):
    value=path.read_text()
    if old not in value:raise RuntimeError('Expected documentation checkpoint absent: '+str(path))
    path.write_text(value.replace(old,new,1))

def main():
    closure=json.loads((CG6/'results/engineering-closure.json').read_text())
    assert closure['implementation']=='complete'
    performance=json.loads((CG6/'results/performance-summary.json').read_text())
    assert performance['passed'] and len(performance['profiles'])==21
    report=CG6/'IMPLEMENTATION_REPORT.md'
    replace_once(report,
        'Engineering closure is in progress. The approved plan is implemented across the\nthree focused subsystems; final admitted performance measurements and a small\nbrowser export-control follow-up remain. No independent technical review,\nunderstanding-gate completion or founder acceptance is claimed here.',
        'CG6 implementation and engineering verification are complete within the approved\nscope and named-host envelopes. CPU and MPS are qualified on CG6-MAC-01; CUDA\nimplementation and contract checks are complete, with actual NVIDIA runtime\nqualification pending compatible hardware. Independent technical review, the\nunderstanding gate and founder acceptance remain subsequent steps.')
    value=report.read_text();start=value.index('Completed admitted measurements so far:');end=value.index('\n## Source preservation and handoff',start)
    table=['All 21 admitted profiles passed their predeclared elapsed/RSS envelopes:',
        '', '| Profile | Elapsed | Peak worker RSS |','|---|---:|---:|']
    for row in performance['profiles']:
        table.append(f"| {row['name']} | {row['elapsed_seconds']:.2f} s | {row['peak_worker_rss_bytes']/1024**3:.2f} GiB |")
    table+=['','Same-host end-to-end throughput comparisons:',
        '', '| Workload | CPU source rows/items per second | MPS source rows/items per second | CPU time / MPS time |',
        '|---|---:|---:|---:|']
    for pair in performance['same_host_comparisons']:
        table.append(f"| {pair['workload']} | {pair['cpu_items_per_second']:.2f} | {pair['mps_items_per_second']:.2f} | {pair['cpu_seconds_divided_by_mps_seconds']:.3f} |")
    table+=['','These are complete-operation observations, including source processing and',
        'transfers. Fitting includes finite checkpoint selection/early stopping; it',
        'is not a comparison of equal optimizer-step counts or isolated GPU kernels.',
        'CPU fitting uses a constant primary; MPS uses its equivalent frozen Torch',
        'primary. The end-to-end comparison includes that adapter difference.']
    table+=['', 'The detailed profiles, exact source/receipt hashes and resource observations are',
        'in `results/performance-summary.json`. These measurements qualify the recorded',
        'host, workloads and runtime; they imply no universal GPU speedup or CUDA timing.',
        'Auxiliary profiles contain 100,000 source rows across fixed F/S/C/E roles:',
        '25,000 F rows fit parameters and 25,000 S rows support disjoint selection;',
        'C/E rows are excluded from fitting and selection. These are not claims of',
        '100,000 training rows or universal training capacity.',
        '', 'A risk-fixture label/role correlation was corrected before its first fitting',
        'measurement so both classes occur within F/S. Sizes, learner defaults, limits',
        'and thresholds were unchanged. Thirteen completed profiles were retained; the',
        'remaining eight ran in fresh processes. One interrupted quantile measurement',
        'had no receipt and was restarted. `results/performance-resumption.json` records',
        'this boundary. The only runtime source change at that restart was browser',
        'export progress/cancel wiring; numerical source was unchanged.', '']
    table+=['The first MPS scale benchmark then correctly refused a CPU-only constant',
        'primary under an explicit MPS request before fitting began. The fixture was',
        'corrected to an equivalent frozen Torch primary, with the same point or',
        'classification function. Only the three uncompleted MPS fitting profiles',
        'ran after this correction. Product source, workload sizes, learner defaults,',
        'budgets and thresholds were unchanged. The original refusal remains in',
        '`performance-risk-complete-mps-fixture-refusal.log`; its disposition is in',
        '`results/performance-mps-primary-fixture-correction.json`.', '']
    report.write_text(value[:start]+'\n'.join(table)+value[end:])
    replace_once(report,'Final engineering completion will precede independent\ntechnical review, any targeted corrections, the final understanding gate and\nfounder acceptance. Actual NVIDIA qualification is tracked separately.',
        'Engineering completion is recorded in `results/engineering-closure.json`, with\nsource identity in `results/engineering-source.json`. Independent technical review,\nany targeted corrections, the understanding gate and founder acceptance follow.\nActual NVIDIA qualification is tracked separately. The synthetic browser server\nwas stopped after verification; no product service is left running.')
    replace_once(report,'| Separate schema validator | 16 strict positive/negative CG6 checks passed |',
        '| Separate schema validator | 16 strict positive/negative CG6 checks passed on final schemas |\n| Final high-floor scale selection control | 1 passed; S selection matches deployed frozen scale floor |\n| Final wheel/source equivalence | All 126 ConfidenceGuard runtime/asset files match the final wheel |')
    (CG6/'IMPLEMENTATION_STATUS.md').write_text('''# CG6 engineering completion

The approved implementation and finite engineering verification are complete.
Independent technical review, the understanding gate and founder acceptance are
subsequent steps. Actual NVIDIA qualification remains separately pending and
does not block unrelated acceptance.

CPU and MPS are qualified on CG6-MAC-01 (Apple M4, 10 CPU/10 GPU cores, 16 GiB
unified memory; primary Python 3.13.17/Torch 2.8.0). CUDA code and device-independent
contracts are complete. No CPU test, substitute or MPS observation is presented as
CUDA runtime execution/parity/memory/performance evidence.

All 21 host-admitted performance profiles passed their frozen envelopes. The
original larger tabular/streaming references remain explicitly not admitted;
separately named smaller profiles are not relabeled as those originals.

Verification followed `agents/skills/verify/skills.md`: the comprehensive affected
gate passed 655 tests, then source-scoped correction gates passed 68 and 9 tests.
Separate Python 3.12 CPU compatibility passed 57 tests. Focused counts overlap;
they are not added as unique test totals. CUDA hardware skips remain explicit.
The final high-floor selection check, strict schemas and base-only installed wheel
passed. All 126 ConfidenceGuard runtime/assets match the final wheel.

The seven locked CPU scientific profiles and six-design cluster campaign passed;
valid expensive evidence was reused with recorded applicability. Every page of
eight representative final PDFs (55 pages), plus four browser-export pages, was
reviewed. Actual browser authoring, MPS execution, fitting, cancellation, frozen
assessment refusal, restatement, restart/reopen and exports were exercised. The
synthetic server is stopped.

Catalog v2 is retained with the bounded opaque binary codec and existing lifecycle.
No original baseline file is missing; DataTrust source is byte-identical to the
captured pre-edit dirty tree. Historical CG1-CG5 evidence remains intact.

Review [the implementation report](IMPLEMENTATION_REPORT.md),
[verification details](VERIFICATION.md), [scope map](SCOPE_AND_EVIDENCE.md),
`results/engineering-closure.json`, `results/engineering-source.json` and
`results/performance-summary.json`. No required engineering gate remains open.
''')
    verification=CG6/'VERIFICATION.md';value=verification.read_text()
    value=value.replace('Engineering closure is still in progress. This record does not confer independent\ntechnical review, understanding-gate completion or founder acceptance.',
        'Engineering verification is complete within the approved scope and named-host\nenvelopes. Independent review, the understanding gate and founder acceptance are\nsubsequent steps.')
    marker='## Named-host performance';value=value[:value.index(marker)]+'''## Final compatibility, product and packaging checks

- `final-provenance-device-checks.log`: 9 passed, 1 CUDA hardware skip; 106.26 s.
- `compatibility-py312.log`: 57 passed, 19 explained skips; 504.19 s. This separate
  Python 3.12 CPU gate ran inside the desktop sandbox; eight MPS skips do not qualify
  Python 3.12 MPS. Actual primary MPS evidence is Python 3.13 outside that sandbox.
- `scale-floor-selection-check.log`: one focused high-floor control passed. Frozen
  S nomination uses the deployed scale floor; no extra quality campaign was run.
- `schema-closure-check.log`: 16 strict positive/negative checks passed on final
  schemas using the separate existing validator environment.
- `wheel-closure-base-check.log`: final installed wheel executes the eight-row
  constant pipeline with Torch/sklearn/skops/ORT/safetensors absent and reopens three
  actual historical CG5 artifacts without model/solver dependencies. The exact 126
  ConfidenceGuard source/asset hashes match the wheel (`results/wheel-closure-source.json`).
- `results/browser/workflow-verification.json`: actual guided browser workflows,
  real MPS qualification, fitting, cancellation, protocol refusal, restatement,
  restart/reopen and exports. Final export progress/completion is visible in CG6;
  its cancel control also resolves shared export jobs. The synthetic server stopped.
- `results/representative-final-reports.json`: eight representative PDFs, 55 pages,
  every page visually inspected; four browser-export pages additionally inspected.

## Named-host performance

`CG6-MAC-01.json` identifies the actual M4 Mac (10 CPU/10 GPU cores, 16 GiB unified
memory), OS/builds, power and storage observations. One bounded calibration preceded
the frozen resource/workload admission in `performance_protocol.json`. All 21
admitted CPU/MPS profiles passed their elapsed/RSS envelopes. Per-profile hashes,
sizes and observations are in `results/performance-summary.json`. Unified-memory
RSS and MPS allocation overlap; no universal GPU speedup or capacity is claimed.

Original 100k/eight-scenario tabular and million-row streaming references remain
explicitly not admitted, based on pre-run disk/control-packet estimates. Named
25k/100k profiles are distinct. No failed workload was shrunk and relabeled.

An early source-change interruption remains diagnostic in
`results/performance-interruption.json`. Before the first risk fitting measurement,
its benchmark labels were corrected to include both classes within each role;
sizes, learners, thresholds and budgets were unchanged. Thirteen passing profiles
were retained and only eight missing profiles executed in fresh processes. The
restart interrupted one uncompleted quantile measurement, then reran that same
profile. `results/performance-resumption.json` records the exact boundary.

The first MPS fitting fixture correctly refused its CPU-only constant primary
under an explicit MPS request before fitting. Only the three uncompleted MPS
profiles used the corrected equivalent frozen Torch primary. This fixture change
does not alter product source, sizes, learners, resource limits or thresholds;
`results/performance-mps-primary-fixture-correction.json` retains the disposition.
CPU/MPS fitting comparisons include the different primary adapters and finite
early stopping; they are end-to-end observations, not isolated kernel speedups.

## Final source and evidence standing

`results/engineering-source.json` records final runtime/assets. The broad gate is
reused for unaffected foundations; later affected tests, actual browser checks,
every-page PDF review and final wheel/schema checks cover corrections. This is not
represented as a single exact-source run of all 655 tests. The final browser-only
export wiring change does not invalidate numerical performance receipts.

`results/engineering-closure.json` inventories executed/reused receipts and source
hashes. `results/source-preservation.json` confirms no missing baseline files and
unchanged DataTrust source versus the captured dirty baseline. Historical CG1-CG5
evidence was not reset or relabeled. No unchanged expensive suite was rerun solely
because documentation or presentation changed.

All required engineering gates are closed. Actual CUDA inference, parity, training,
allocator/cancellation and performance remain `not_run_hardware_unavailable` until
compatible NVIDIA hardware exists. Its implementation/contracts are complete; this
pending hardware qualification is nonblocking and is never inferred from mocks.
'''
    verification.write_text(value)
    replace_once(ROOT/'docs/CG6_CONFIDENCEGUARD.md','Implementation is in progress. The approved architecture remains controlled local',
        'Implementation and engineering verification are complete. The approved architecture remains controlled local')
    replace_once(ROOT/'README.md','Engineering closure is in progress; independent review and the understanding gate are subsequent steps.',
        'Engineering verification is complete; independent review and the understanding gate are subsequent steps. All 21 admitted Mac performance profiles passed.')
    replace_once(ROOT/'docs/CURRENT_STATE.md','The approved CG6 implementation is in closure verification.',
        'The approved CG6 implementation and engineering verification are complete within the recorded Mac profiles.')
    replace_once(ROOT/'docs/NUMEK_MASTER_CONTEXT.md','CG6 is implementing the approved controlled local execution architecture',
        'CG6 implements the approved controlled local execution architecture')
    replace_once(ROOT/'docs/NUMEK_MASTER_CONTEXT.md','Engineering closure remains in progress; independent review and understanding follow it.',
        'Engineering verification is complete, including all 21 admitted named-Mac performance profiles; independent review and understanding follow it.')
    print('Finalized CG6 engineering documentation; independent review/acceptance remain separate')

if __name__=='__main__':main()
