# CG6 completion and founder acceptance

Current standing, **2026-11-08: CG6 is done and founder-accepted**. CG1–CG6 are
complete within their approved scopes. The founder's decision supersedes earlier
pending-review, pending-understanding and pending-founder-acceptance language.

Implementation, engineering verification, independent review, R1–R6 corrections
and the [final implementation explainer](CG6_FINAL_IMPLEMENTATION_EXPLAINER.md)
are complete. No further CG6 review/correction/understanding work is implied.
Actual NVIDIA runtime qualification remains separately pending compatible hardware
and nonblocking. CG7 requires a separate founder instruction.

The accepted runtime/assets identity covers 230 files:
`aa72f09caa5bc5b174db5b4253add54a9fba8b3ecec3309c99f0beb0608fbf6a`.
The [correction report](review-corrections-r1-r6/REVIEW_CORRECTIONS.md),
`review-corrections-r1-r6/source-identity.json` and
`review-corrections-r1-r6/closure.json` retain the exact corrected-source and
executed/reused evidence standing. The correction integration passed 135 tests
with ten NVIDIA skips on Python 3.13 and 53 tests in the Python 3.12 subset.
The final two R1 bridge/restatement writer changes received exact-source follow-ups:
17 passes on 3.13 and nine on 3.12. All 230 runtime/assets match the corrected wheel.
Counts overlap and are not summed.

The explainer covers all 16 requested areas, six diagrams, every CG6-specific
Python source file, execution stories, mathematics, R1–R6, limitations, glossary
and 15 detailed technical questions. Documentation/source-reference checks did
not rerun implementation tests or qualification campaigns. Living docs were
updated after the sealed correction receipts; their recorded documentation hashes
identify the earlier snapshots. Receipts, historical artifacts and runtime code
remain unchanged.

## Hardware and historical engineering evidence

CPU and MPS are qualified on CG6-MAC-01 (Apple M4, 10 CPU/10 GPU cores, 16 GiB
unified memory; primary Python 3.13.17/Torch 2.8.0). CUDA code and device-independent
contracts are complete. No CPU test, substitute or MPS observation is presented as
CUDA runtime execution/parity/memory/performance evidence.

All 21 host-admitted performance profiles passed their frozen envelopes on their
recorded historical source; they were not rerun after R1–R6. In particular, old
attack timings are not corrected-source throughput claims. The
original larger tabular/streaming references remain explicitly not admitted;
separately named smaller profiles are not relabeled as those originals.

Original engineering verification followed `agents/skills/verify/skills.md`: the
comprehensive affected gate passed 655 tests, then source-scoped correction gates
passed 68 and 9 tests.
Separate Python 3.12 CPU compatibility passed 57 tests. Focused counts overlap;
they are not added as unique test totals. CUDA hardware skips remain explicit.
The final high-floor selection check, strict schemas and base-only installed wheel
passed. The original 126-file ConfidenceGuard wheel comparison is historical;
the corrected 230-file whole-runtime comparison is identified above.

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
Scientific assumptions, legitimate refusals and scope limits remain unchanged
by founder acceptance.
