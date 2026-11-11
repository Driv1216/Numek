# Evidence guide: executed, reused and packaging-only

## Executed CG5 engineering evidence

The original [verification record](../validation/cg5/VERIFICATION.md) is retained
unchanged, including its pre-packaging statement that no review ZIP yet existed.
The following are completed records, not commands rerun for this archive.

| Evidence | Result and boundary |
|---|---|
| [Comprehensive correctness/host log](../validation/cg5/results/closure-tests.log) | 549 passed, one skipped, 548.30 seconds; CG1–CG5 plus affected DataTrust API/default/web suites |
| [Final affected checks](../validation/cg5/results/final-affected-checks.log) | 23 passed; final assessment, solver warning/decoding and scheduled-look changes |
| [Final interface checks](../validation/cg5/results/final-interface-checks.log) | 5 passed; owned scheduled-look API and policy/history/artifact integration |
| [CG1–CG4 schema references](../validation/cg5/results/schema-cg1-cg4.json) | 63 passed in the existing separate schema environment |
| [CG5 strict schema references](../validation/cg5/results/schema-cg5.json) | 38 passed, including rejected unknown/executable/path/solver-option declarations |
| [Finite diagnostic receipt](../validation/cg5/results/finite-20261104/finite-diagnostics.json) | Twelve fixed full-service synthetic stories: 0/6 null and 6/6 power supported; expectations were predeclared. No general error/power qualification. |
| [Workload receipt](../validation/cg5/results/qualified-20261104/measurements.json) | Binary grouped sweep, contextual multiclass MILP, finite regression economics and two-window history; records exact source/runtime/settings/counters and sampled RSS |
| [Browser evidence](../validation/cg5/results/browser-final.jpg) | Reopened frozen assessment, supported claim, interval/support and shareable export links; other observed steps are narrated in the verification record |
| [Final report audit](../validation/cg5/results/pdf-final-audit.json) | Six final reports, first-page decision record and shareable JSON/HTML/PDF text checks |
| [Final report hashes/template receipt](../validation/cg5/results/qualified-20261104/final-reports.json) | Exports reopened completed evidence; `reanalysis=false` |

The focused test groups overlap the comprehensive gate: do not add their counts
as distinct passes. The skipped in-suite CG2 validator lacked `jsonschema` in the
analytical environment; the separate schema gate covered its transport examples.
Final assessment changes were checked narrowly after the coherent broad gate.
The workload source was stable during measurement. Its only later Python change
was tighter repeated-assessment admission; measured selection/replay/history paths
were unchanged, and final affected checks cover the changed path. See the source
map's explicit applicability note.

## Reused CG1–CG4 evidence

[CG5's applicability map](../validation/cg5/README.md) defines the reuse boundary.
All current runtime source and the complete tests are supplied, rather than an
assumed external API. Prior verification/qualification records and 38 immutable
CG4 source-only snapshots are retained with their original identities. Their
results retain their original methods, selectors, profiles, platforms and seeds.

Start with:

- [CG1 verification and correction context](../validation/cg1/README.md).
- [CG2 method/role/distribution context](../validation/cg2/README.md).
- [CG3 ledger](../validation/cg3/VERIFICATION_LEDGER.md) and
  [corrections](../validation/cg3/review-corrections/README.md).
- [CG4 supported methods](../validation/cg4/SUPPORTED_METHODS.md),
  [qualification matrix](../validation/cg4/QUALIFICATION_MATRIX.md),
  [closure scope revision](../validation/cg4/CLOSURE_SCOPE_REVISION.md),
  [null evidence bridge](../validation/cg4/NULL_EVIDENCE_BRIDGE.md) and
  [review corrections](../validation/cg4/REVIEW_CORRECTIONS.md).

CP/Hoeffding numerical kernels, frozen CG2 application, CG3 reconstruction/codecs,
CG4 exact predicates/membership and shared worker/publication controls are reused
only in unchanged scope. Old BCa/cluster/ranking/temporal negative evidence remains
negative or unqualified. Prior scientific trials are not newly executed CG5 tests;
source snapshots let reviewers inspect the actual versions associated with them.

## Representative samples

[Final reports](../validation/cg5/results/qualified-20261104/reports-final/) contain
local and shareable HTML/JSON/PDF for all three tasks. Protected companion packets
are synthetic local engineering evidence. Other governing CG5 samples include the
[qualified study/input/history directory](../validation/cg5/results/qualified-20261104/),
[retained browser workspace](../validation/cg5/results/browser-retained/),
[protected frozen family](../validation/cg5/results/browser-frozen-family.json),
[finite diagnostic inputs](../validation/cg5/results/finite-20261104/) and
[PDF visual QA](../validation/cg5/results/pdf-qa/).

All supplied fixture outcomes are already exposed engineering data. Neither an
independence checkbox nor a new synthetic namespace turns them into fresh evidence
for a product claim. Exact local artifacts may contain synthetic event IDs,
costs and original workstation paths; shareable projection is a separate contract.

## Packaging-only evidence

The new wheel was built from a temporary clean copy with already installed build
tools, using the existing [wheel builder](../validation/cg4/build_review_wheel.py).
[Build/parity evidence](../wheel/verification.json) records exact runtime/static
parity. No clean install, new analytical reproduction or platform qualification is
claimed by that build. Historical wheel/reproduction records remain historical.

[PACKAGING_INVENTORY.json](PACKAGING_INVENTORY.json) records captured repository
files and explicit exclusion boundaries. [REFERENCES.json](REFERENCES.json) records
all included Markdown path references and historical exceptions. The final
external integrity receipt records archive hashing, CRC, full manifest coverage,
source-map consistency and safe extraction. None is an independent review verdict.

Existing CG4 reviewer probe outputs referenced by an old absolute workstation path
are supplied in [historical-cg4-review](historical-cg4-review/). The
[attachment map](HISTORICAL_REFERENCE_ATTACHMENTS.json) binds their original paths
and bytes. These are old CG4 review records, not an independent CG5 review.
