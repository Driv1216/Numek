"""Backend-neutral observations for ConfidenceGuard tests (CG7 S3d test port).

The same suites run on catalog v2 and on the NUMEK platform. Assertions that
used to read v2 internals (SQLite rows, ``evidence_use`` facts, ``objects/``
files) observe the equivalent invariant through these helpers instead:

* ``evidence_uses``    the durable evidence-use records, v2 payload shape;
* ``stored_evidence``  the authoritative stored evidence bytes (v2 ``objects/``;
                       the platform object store, not its materialized copies);
* ``object_file``      the file holding one object's authoritative bytes;
* ``object_retained``  whether an object's bytes are still stored.
"""
from pathlib import Path


def on_platform(ws):
    from confidenceguard.platform_catalog import PlatformCatalog
    return isinstance(ws.catalog, PlatformCatalog)


def evidence_uses(ws):
    from confidenceguard.evidence_use import EvidenceUseLedger
    return EvidenceUseLedger(ws).records()


def _store_files(ws):
    """Stored *evidence* objects of the workspace. Evidence-use membership objects are governance
    records (every governed read stages one), not evidence, and are left out."""
    root = Path(ws.catalog.store.root)
    with ws.catalog.db.connect() as conn:
        rows = conn.execute("SELECT physical_key FROM objects WHERE catalog_id = %s AND state IN ('active', 'tombstoned') "
                            "AND codec <> 'exposure_membership_v1' ORDER BY physical_key", (ws.catalog.catalog_id,)).fetchall()
    return {r['physical_key']: root / r['physical_key'] for r in rows if (root / r['physical_key']).is_file()}


def stored_evidence(ws, *, hashed=False):
    import hashlib
    files = _store_files(ws) if on_platform(ws) else {p.name: p for p in sorted((Path(ws.path) / 'objects').iterdir())}
    return {name: (hashlib.sha256(p.read_bytes()).hexdigest() if hashed else p.read_bytes()) for name, p in files.items()}


def object_file(ws, object_id):
    if not on_platform(ws):
        return ws.catalog._object_path(object_id)
    from confidenceguard.platform_catalog import _uuid
    row = ws.catalog._object_row(_uuid(object_id))
    return Path(ws.catalog.store.root) / row['physical_key']


def object_retained(ws, object_id):
    if not on_platform(ws):
        return ws.catalog._object_path(object_id).exists()
    from confidenceguard.platform_catalog import _uuid
    with ws.catalog.db.connect() as conn:
        row = conn.execute('SELECT state, physical_key FROM objects WHERE id = %s', (_uuid(object_id),)).fetchone()
    return row is not None and row['state'] not in ('reclaimed',) and (Path(ws.catalog.store.root) / row['physical_key']).exists()


def codec_counts(ws):
    """Stored objects of this workspace by codec (active objects only)."""
    if not on_platform(ws):
        from contextlib import closing
        with closing(ws.catalog._connect()) as db:
            return dict(db.execute("SELECT encoding, count(*) FROM objects WHERE state='active' GROUP BY encoding").fetchall())
    with ws.catalog.db.connect() as conn:
        rows = conn.execute("SELECT codec, count(*) AS n FROM objects WHERE catalog_id = %s AND state = 'active' GROUP BY codec",
                            (ws.catalog.catalog_id,)).fetchall()
    return {r['codec']: r['n'] for r in rows}
