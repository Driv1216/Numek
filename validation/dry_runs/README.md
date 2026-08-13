# DataTrust Historical Dry-Run Workspace

This workspace contains the historical materials prepared for the archived dry-run review and
RC_003. It is separate from DataTrust runtime package code.

RC_003 has completed its founder-accepted technical review and is preserved as
historical evidence. The former mandatory five-practitioner validation round is
superseded and is no longer an active milestone, blocker, or product exit gate.

## Prepared Materials

- `TECHNICAL_REVIEWER_QUICKSTART.md`: the only setup/run instructions given to
  the uninvolved technical reviewer
- `MANUAL_FIRST_ASSESSMENT.md`: assessment completed before DataTrust
  output is visible
- `TECHNICAL_DRY_RUN_EVIDENCE.md`: technical run, comprehension, and friction
  evidence form
- `NON_TECHNICAL_COMPREHENSION.md`: separate three-minute comprehension form
- `PRACTITIONER_EVIDENCE_TEMPLATE.md`: superseded practitioner validation
  template retained for archive/history
- `FACILITATOR_INSTRUCTIONS.md`: non-assistance, anti-anchoring, timing, and
  evidence-return protocol
- `PASS_FAIL_RULES.md`: objective pass, fail, pause, and fix rules
- `release_candidate.py`: historical deterministic candidate creation tooling
- `reviewer_packet.py`: historical allowlist-only clean reviewer packet tooling
- `verify.py`: preparation-artifact verifier
- `evidence/README.md`: where completed copies are returned

## Historical Candidate Freezing

These commands document how the historical clean packet and RC_003 candidate
were created and verified:

```bash
.venv/bin/python -m validation.dry_runs.reviewer_packet create \
  --id DRY_RUN_RC_003_REVIEWER_PACKET
.venv/bin/python -m validation.dry_runs.release_candidate create \
  --id DRY_RUN_RC_003 \
  --packet-manifest validation/dry_runs/packets/DRY_RUN_RC_003_REVIEWER_PACKET.manifest.json
.venv/bin/python -m validation.dry_runs.release_candidate verify \
  --manifest validation/dry_runs/release_candidates/DRY_RUN_RC_003.json
```

The historical manifest recorded runtime code, tests, package metadata,
methodology, quickstart/protocol materials, and the example dataset. Completed
evidence was excluded so recording a session did not alter the candidate.

The clean packet uses an explicit allowlist. It contains installable DataTrust
source and blank reviewer-facing materials, while excluding existing reports,
validation results and comparisons, internal project docs, previous evidence,
tests, examples, and virtual environments. Packet verification checks required
files and prohibited paths for the historical packet.

Historical candidate manifests remain immutable records. Because the active
source documents may now be updated after RC_003, the frozen packet ZIP,
manifest JSON, and release-candidate JSON are the preserved RC_003 evidence.

## Verify Preparation

```bash
.venv/bin/python -m validation.dry_runs.verify
```

This verifier was used for historical preparation checks. It does not run or
simulate human dry runs and is not an active product-building gate.
