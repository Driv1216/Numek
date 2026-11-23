"""Retention of received raw bodies and quarantined rows, and crypto-shredding of their day keys (R2.7).

* Raw bodies of terminal batches are tombstoned after ``raw_days`` (default 7); a batch that is
  not yet processed keeps its raw body (it is still needed for recovery and backups include it).
* Encrypted quarantined rows are tombstoned after ``quarantine_days`` (default 30).
* Tombstoned objects are reclaimed by garbage collection (holds and read pins still apply).
* A day key whose objects are all tombstoned or reclaimed, and whose day is past retention, is
  destroyed live. That is reported as ``destroyed_live``: deletion is complete only once every
  backup keyring holding the key has expired or been destroyed, which the platform does not track,
  so the report never says the data is deleted.
"""
from datetime import datetime, timedelta, timezone

RAW_DAYS = 7
QUARANTINE_DAYS = 30


def sweep(installation, *, raw_days=RAW_DAYS, quarantine_days=QUARANTINE_DAYS, now=None):
    now = now or datetime.now(timezone.utc)
    scope = installation.scope
    report = {'raw_tombstoned': 0, 'quarantine_tombstoned': 0, 'keys_destroyed_live': [],
              'deletion_status': 'destroyed_live; complete only after every backup holding these keys expires (not tracked)'}
    with installation.db.transaction() as conn:
        def tombstone(ids):
            """Tombstone active objects, each under its own catalog's maintenance epoch (GC invariant I-3)."""
            if not ids:
                return 0
            total = 0
            for row in conn.execute('SELECT catalog_id, array_agg(id) AS ids FROM objects WHERE id = ANY(%s) AND state = %s '
                                    'GROUP BY catalog_id ORDER BY catalog_id', (ids, 'active')).fetchall():
                mepoch = conn.execute('UPDATE catalog_maintenance SET epoch = epoch + 1 WHERE catalog_id = %s RETURNING epoch',
                                      (row['catalog_id'],)).fetchone()['epoch']
                total += conn.execute("""UPDATE objects SET state = 'tombstoned', tombstoned_at = clock_timestamp(),
                                         tombstone_mepoch = %s WHERE id = ANY(%s) AND state = 'active'""",
                                      (mepoch, row['ids'])).rowcount
            return total

        raw = [r['raw_object'] for r in conn.execute(
            """SELECT raw_object FROM ops_batches WHERE org_id = %s AND state IN ('published', 'quarantined', 'failed')
               AND received_at < %s""", (scope.org_id, now - timedelta(days=raw_days)))]
        report['raw_tombstoned'] = tombstone(raw)
        rows = [r['rows_object'] for r in conn.execute(
            """SELECT DISTINCT q.rows_object FROM ops_quarantine q JOIN objects o ON o.id = q.rows_object
               WHERE q.org_id = %s AND o.created_at < %s AND o.state = 'active'""",
            (scope.org_id, now - timedelta(days=quarantine_days)))]
        report['quarantine_tombstoned'] = tombstone(rows)
        candidates = conn.execute(
            """SELECT k.key_id, k.day, k.purpose FROM ops_raw_keys k JOIN key_records r ON r.key_id = k.key_id
               WHERE k.org_id = %s AND r.state = 'active' AND k.day < %s
               AND NOT EXISTS (SELECT 1 FROM objects o WHERE o.key_id = k.key_id AND o.state IN ('pending', 'active'))""",
            (scope.org_id, (now - timedelta(days=max(raw_days, quarantine_days))).date())).fetchall()
        for key in candidates:
            installation.data_keys.destroy_live(conn, scope, key['key_id'])
            report['keys_destroyed_live'].append({'key': str(key['key_id']), 'day': key['day'].isoformat(), 'purpose': key['purpose']})
    return report


def retention_job(ctx, payload):
    from numek_platform.installation import Installation
    from .incidents import pins
    installation = Installation(payload['installation'])
    report = sweep(installation)
    report['observations'] = pins.observation_sweep(installation, now=datetime.now(timezone.utc))
    return report
