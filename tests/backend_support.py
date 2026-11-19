"""Platform observations for ConfidenceGuard tests (CG7 S3).

Assertions that used to read catalog v2 internals (SQLite rows, ``evidence_use``
facts, ``objects/`` files) observe the equivalent platform invariant through
these helpers:

* ``evidence_uses``    the durable evidence-use records, in the v2 payload shape;
* ``stored_evidence``  the authoritative stored evidence bytes (the platform object
                       store; not governance membership objects or materialized copies);
* ``object_file``      the file holding one object's authoritative bytes;
* ``object_retained``  whether an object's bytes are still stored;
* ``codec_counts``     active stored objects by codec.
"""
from pathlib import Path


def on_platform(ws):
    from confidenceguard.platform_catalog import PlatformCatalog
    return isinstance(ws.catalog, PlatformCatalog)


def evidence_uses(ws):
    from confidenceguard.evidence_use import EvidenceUseLedger
    return EvidenceUseLedger(ws).records()


def _store_files(ws):
    root = Path(ws.catalog.store.root)
    with ws.catalog.db.connect() as conn:
        rows = conn.execute("SELECT physical_key FROM objects WHERE catalog_id = %s AND state IN ('active', 'tombstoned') "
                            "AND codec <> 'exposure_membership_v1' ORDER BY physical_key", (ws.catalog.catalog_id,)).fetchall()
    return {r['physical_key']: root / r['physical_key'] for r in rows if (root / r['physical_key']).is_file()}


def stored_evidence(ws, *, hashed=False):
    import hashlib
    return {name: (hashlib.sha256(p.read_bytes()).hexdigest() if hashed else p.read_bytes())
            for name, p in _store_files(ws).items()}


def object_file(ws, object_id):
    from confidenceguard.platform_catalog import _uuid
    row = ws.catalog._object_row(_uuid(object_id))
    return Path(ws.catalog.store.root) / row['physical_key']


def object_retained(ws, object_id):
    from confidenceguard.platform_catalog import _uuid
    with ws.catalog.db.connect() as conn:
        row = conn.execute('SELECT state, physical_key FROM objects WHERE id = %s', (_uuid(object_id),)).fetchone()
    return row is not None and row['state'] != 'reclaimed' and (Path(ws.catalog.store.root) / row['physical_key']).exists()


def codec_counts(ws):
    with ws.catalog.db.connect() as conn:
        rows = conn.execute("SELECT codec, count(*) AS n FROM objects WHERE catalog_id = %s AND state = 'active' GROUP BY codec",
                            (ws.catalog.catalog_id,)).fetchall()
    return {r['codec']: r['n'] for r in rows}
