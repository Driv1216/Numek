"""Immutable monitoring packets and the governed publish step.

A monitoring result follows H.4:
- its content is an immutable object, staged under the attempt's fence;
- its row, the activation of that object and the consumption of the reservation it was read under
  commit in one transaction.

Lock order (R2.1): job row (fence), then the exposure advisory lock, then the object rows.
"""
import json

from ...contracts import digest

JSON_CODEC = 'monitoring_packet_json_v1'
RELATION_CODEC = 'reference_relation_parquet_v1'


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), default=_plain).encode()


def _plain(value):
    import numpy as np
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).hex()
    raise TypeError(type(value).__name__)


def stage(installation, lease, catalog_id, data, codec=JSON_CODEC, records=0):
    from numek_platform.evidence.publish import stage_object
    return stage_object(installation.db, installation.store, lease, data, catalog_id=catalog_id, codec=codec,
                        records=records)


def publish(installation, lease, catalog_id, objects, reservations, write):
    """One transaction: fence, exposure lock, activate ``objects``, consume ``reservations``, then ``write(conn)``."""
    from numek_platform.evidence.publish import activate_pending
    from numek_platform.execution.jobs import assert_fence, complete
    from numek_platform.governance import ledger
    scope = installation.scope
    with installation.db.transaction() as conn:
        assert_fence(conn, lease)
        conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))', (f'exposure:{catalog_id}',))
        fresh = [ref.id for ref in objects if not getattr(ref, 'reused', False)]
        if fresh:
            activate_pending(conn, scope, lease, catalog_id, fresh)
        if reservations:
            ledger.consume(conn, scope, lease, catalog_id, reservations)
        result = write(conn)
        complete(conn, lease, {})
    return result


def read(installation, object_id):
    with installation.db.connect() as conn:
        row = conn.execute('SELECT physical_key, sha256, bytes, codec FROM objects WHERE org_id = %s AND id = %s',
                           (installation.scope.org_id, object_id)).fetchone()
    data = installation.store.read_verified(row['physical_key'], bytes(row['sha256']).hex(), row['bytes'])
    return json.loads(data) if row['codec'] == JSON_CODEC else data


def packet_digest(value):
    return digest(value)
