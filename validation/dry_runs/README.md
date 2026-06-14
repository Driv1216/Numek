# DataTrust V1 Dry-Run Workspace

This workspace contains the prepared materials for Milestone 3. It is separate
from DataTrust runtime package code. No human dry run has been conducted or
recorded here yet.

## Prepared Materials

- `TECHNICAL_REVIEWER_QUICKSTART.md`: the only setup/run instructions given to
  the uninvolved technical reviewer
- `MANUAL_FIRST_ASSESSMENT.md`: sealed assessment completed before DataTrust
  output is visible
- `TECHNICAL_DRY_RUN_EVIDENCE.md`: technical run, comprehension, and friction
  evidence form
- `NON_TECHNICAL_COMPREHENSION.md`: separate three-minute comprehension form
- `PRACTITIONER_EVIDENCE_TEMPLATE.md`: later Milestone 4 evidence template
- `FACILITATOR_INSTRUCTIONS.md`: non-assistance, anti-anchoring, timing, and
  evidence-return protocol
- `PASS_FAIL_RULES.md`: objective pass, fail, pause, and fix rules
- `release_candidate.py`: deterministic candidate creation and verification
- `reviewer_packet.py`: allowlist-only clean reviewer packet creation and
  verification
- `verify.py`: preparation-artifact verifier
- `evidence/README.md`: where completed copies are returned

## Freeze A Dry-Run Candidate

Create and verify a clean packet, then create the candidate only after
preparation materials and code are ready:

```bash
.venv/bin/python -m validation.dry_runs.reviewer_packet create \
  --id DRY_RUN_RC_003_REVIEWER_PACKET
.venv/bin/python -m validation.dry_runs.release_candidate create \
  --id DRY_RUN_RC_003 \
  --packet-manifest validation/dry_runs/packets/DRY_RUN_RC_003_REVIEWER_PACKET.manifest.json
.venv/bin/python -m validation.dry_runs.release_candidate verify \
  --manifest validation/dry_runs/release_candidates/DRY_RUN_RC_003.json
```

The manifest hashes runtime code, tests, package metadata, methodology,
quickstart/protocol materials, and the example dataset. Completed evidence is
excluded so recording a session does not alter the candidate. Any candidate
file change makes verification fail and requires a new candidate ID.

The clean packet uses an explicit allowlist. It contains installable DataTrust
source and blank reviewer-facing materials, while excluding existing reports,
validation results and comparisons, internal project docs, previous evidence,
tests, examples, and virtual environments. Packet verification checks required
files, prohibited paths, every file hash, and the deterministic archive hash.

Historical candidate manifests remain immutable records. Preparation
verification checks their record structure and verifies the newest candidate
against the current source and its exact packet.

## Verify Preparation

```bash
.venv/bin/python -m validation.dry_runs.verify
```

This verifies preparation artifacts and candidate integrity. It does not run or
simulate either human dry run.
