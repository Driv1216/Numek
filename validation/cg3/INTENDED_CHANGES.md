# Working-tree change boundary

The approved implementation baseline included substantial uncommitted/untracked
DataTrust UI/history and ConfidenceGuard closure work. `baseline.json` binds 829
pre-CG3 files by size/hash at HEAD f7a7db0a05611613369ce25156b5418ec108a5fe.
The delivery source is the final working tree, not a checkout of HEAD.

CG3 adds `history_*`, `longitudinal.py`, `workspace.py`, history UI/report sections,
CG3 tests and validation. Narrow hooks extend secure ingestion/capture, optional
engine/method recording, result dispatch, transport/shared jobs, CLI/public exports
and generated contracts. `compat.insert_rows` batches secure normalizer insertion;
legacy reducer mathematics and CG2 RNG behavior remain unchanged. `datatrust.web`
adds host-controlled ConfidenceGuard workspace configuration/launch authorization.
Current-state/architecture/master-context/README document this integrated state.

`source-final.json` lists final runtime/document/test hashes and compares baseline
files. `tracked-working-tree.patch` is explicitly the FULL tracked diff against
HEAD, including inherited work; it is NOT a CG3-only patch. Baseline untracked file
contents were not archived, so a byte-perfect reverse CG3 patch for those inherited
files cannot honestly be manufactured. Required final untracked runtime files are
included directly in this handoff. No reset, commit or rewrite of inherited work
was performed. Historical preservation evidence separately binds 568 CG1/CG2 files
and 36 reopened bundles.
