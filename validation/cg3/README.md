# CG3 engineering verification and review

CG3 extends the existing ConfidenceGuard product with opt-in local history,
reconstructable protected facts, immutable longitudinal assessments and qualified
statistical investigation. CG3 is complete, including corrections R1–R3, as confirmed by the user on 2026-10-21.

Read [the methodology and usage](../../docs/CG3_CONFIDENCEGUARD.md),
[review quickstart](REVIEW_QUICKSTART.md), [verification ledger](VERIFICATION_LEDGER.md)
and [decisions and limits](DECISIONS.md). The technical-review ZIP contains the
final working-tree runtime, including required untracked host files, a wheel,
contracts, tests, references, synthetic evidence, reports and integrity manifests.
No customer workspace, credentials, model weights or environment is included.

The implementation baseline is `baseline.json`, captured before CG3 edits. The
repository was already dirty; the tracked patch against HEAD also includes inherited
work. `INTENDED_CHANGES.md` and the baseline/final file comparison distinguish that
fact rather than misrepresenting a clean CG3-only Git diff.

## Reproduction sources

- `fixtures.py`: deterministic supplied predictions; never fits a predictor.
- `reference.py`: independent standard-library arithmetic over pinned inputs and
  existing reports; does not import ConfidenceGuard or regenerate reports.
- `reproduce.py`: new three-task workspace and canonical reports when requested.
- `resources.py`, `backfill.py`, `reimport.py`: measured local storage workloads.
- `statistics.py`, `block_qualification.py`: sampling-design simulations, including
  deliberately misspecified inference and retained negative evidence.
- `browser_server.py`, `browser_variants.py`: synthetic local browser fixture only.
- `package_review.py`, `verify_package.py`: allowlisted delivery and clean extraction.

Do not rerun qualification or regenerate reports merely because packaging or
unrelated documentation changed. Existing evidence remains valid until its inputs
or relevant behavior change. The final wheel and extracted artifact receive
packaging checks, not another round of unchanged model qualification.
