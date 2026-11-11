# NUMEK ConfidenceGuard CG5 — Independent Technical Review

**Purpose: independent review handoff.** CG5 implementation and internal engineering
verification are complete. This archive does not contain an independent CG5 review,
founder acceptance, a deployment decision or authorization to proceed to CG6.

Read in this order:

1. [Review architecture, invariants and scrutiny map](review/ARCHITECTURE_AND_SCRUTINY.md).
2. [CG5 behavior and scientific boundaries](docs/CG5_CONFIDENCEGUARD.md) and
   [the original engineering verification record](validation/cg5/VERIFICATION.md).
3. [Executed evidence versus reused evidence](review/EVIDENCE_GUIDE.md).
4. [Integrity, environment and optional reproduction instructions](review/REPRODUCTION.md).
5. [Packaging scope, exclusions and limitations](review/PACKAGING_SCOPE.md).

The current project decisions are in [CURRENT_STATE](docs/CURRENT_STATE.md),
[MASTER_CONTEXT](docs/NUMEK_MASTER_CONTEXT.md) and [ARCHITECTURE](docs/ARCHITECTURE.md).
Their historical sections preserve earlier pending-review language. The current
CG1–CG4 completion decision supersedes that old status language, while the
[CG4 supported-method limits](validation/cg4/SUPPORTED_METHODS.md) remain scientific
boundaries. Historical CG1–CG4 quickstarts and wheels are context, not instructions
to treat an older runtime as this CG5 candidate. Use the wheel under root `wheel/`.

## Exact candidate identity

The recorded verified source map is
[final-source.json](validation/cg5/results/final-source.json): **190 Python,
JavaScript, HTML, CSS and JSON files**, map digest
`48dda6c6562cd30710e0ee03d21cc9774cc6122b17c55db31054cf9517497099`.
Every mapped file matches the packaged source byte-for-byte. The full runtime is
also delivered, including assets outside that map's extensions. The new source-only
wheel matches **all 212 runtime/static files**; its build and parity receipt are in
[wheel/verification.json](wheel/verification.json).

[MANIFEST.json](MANIFEST.json) provides the size and SHA-256 of every payload file.
Its own bytes are covered by the external ZIP checksum. Check that external checksum
before extraction, then run the inventory verifier. The adjacent `.integrity.json`
records ZIP/CRC, manifest, source identity and safe-extraction checks; it is outside
the archive to avoid a self-referential final archive hash.

## What to decide in the independent review

Assess the correctness and actual scope of the delivered behavior. In particular,
challenge denominator choices, loss bounds, algebraic solver admission, candidate
re-evaluation, certificate wording, role isolation, frozen-family coverage,
reservation continuity, private disclosure and historical input identity. Passing
tests and packaging integrity are evidence to inspect, not a substitute for your
judgment. Please distinguish implementation defects, unsupported declarations,
legitimate scientific refusals and inconclusive evidence.

The scope is the six CG5 units described in the scrutiny map. Review packaging
made no production source changes, installed no dependencies, ran no analytical
workloads, regenerated no completed results and did not rerun the full test suite.
