"""Object reclamation (garbage collection).

Invariants (R2.1):

I-1  A committed reference never points at reclaimed bytes: only ``pending``
     (stale) or ``tombstoned`` (eligible) rows may become ``reclaiming``, under
     ``FOR UPDATE``; publishers hold the row while referencing it. Bytes are
     unlinked only after ``reclaiming`` commits.
I-2  Pending objects of a live attempt (current fence, running) are never
     reclaimed, and stale ones only after ``pending_ttl``.
I-3  A tombstoned object is reclaimed only after ``grace``, with no active
     ``gc_holds`` row and no live read pin on its catalog whose maintenance
     floor is below the object's tombstone epoch.
"""
import datetime as dt
import uuid

from ..execution.jobs import TERMINAL

LIVE_PIN = '''
    released_at IS NULL AND (
        (job_id IS NOT NULL AND EXISTS (SELECT 1 FROM jobs j WHERE j.id = read_pins.job_id
                                         AND j.fence = read_pins.fence AND j.state = 'running'))
        OR (job_id IS NULL AND expires_at > now()))'''


class GarbageCollector:
    def __init__(self, db, store, *, grace=dt.timedelta(hours=24), pending_ttl=dt.timedelta(hours=6)):
        self.db, self.store = db, store
        self.grace, self.pending_ttl = grace, pending_ttl

    def run_once(self):
        report = {'pins_released': self.release_dead_pins(), 'reclaimed': 0, 'staging_removed': 0}
        for object_id in self._candidates():
            if self._reclaim(object_id):
                report['reclaimed'] += 1
        report['reclaimed'] += self._finish_interrupted()
        report['staging_removed'] = self._clean_staging()
        return report

    def release_dead_pins(self):
        with self.db.transaction() as conn:
            rows = conn.execute(
                f'''UPDATE read_pins SET released_at = clock_timestamp()
                    WHERE released_at IS NULL AND NOT ({LIVE_PIN}) RETURNING id''').fetchall()
        return len(rows)

    def _eligible_sql(self):
        return f'''
            (o.state = 'pending' AND o.created_at < now() - %(pending_ttl)s
             AND NOT EXISTS (SELECT 1 FROM jobs j WHERE j.id = o.job_id AND j.fence = o.fence AND j.state = 'running'))
            OR
            (o.state = 'tombstoned' AND o.tombstoned_at < now() - %(grace)s
             AND NOT EXISTS (SELECT 1 FROM gc_holds h WHERE h.released_at IS NULL)
             AND NOT EXISTS (SELECT 1 FROM read_pins WHERE read_pins.catalog_id = o.catalog_id
                             AND read_pins.maintenance_epoch < o.tombstone_mepoch AND {LIVE_PIN}))'''

    def _candidates(self):
        with self.db.connect() as conn:
            rows = conn.execute(f'SELECT o.id FROM objects o WHERE {self._eligible_sql()} ORDER BY o.id',
                                {'pending_ttl': self.pending_ttl, 'grace': self.grace}).fetchall()
        return [r['id'] for r in rows]

    def _reclaim(self, object_id):
        with self.db.transaction() as conn:
            row = conn.execute(
                f'''SELECT o.id, o.physical_key FROM objects o WHERE o.id = %(id)s AND ({self._eligible_sql()})
                    FOR UPDATE OF o''',
                {'id': object_id, 'pending_ttl': self.pending_ttl, 'grace': self.grace}).fetchone()
            if row is None:
                return False
            conn.execute("UPDATE objects SET state = 'reclaiming' WHERE id = %s", (object_id,))
        self.store.unlink(row['physical_key'])
        with self.db.transaction() as conn:
            conn.execute("UPDATE objects SET state = 'reclaimed' WHERE id = %s AND state = 'reclaiming'", (object_id,))
        return True

    def _finish_interrupted(self):
        """Complete reclamations interrupted between commit and unlink."""
        with self.db.connect() as conn:
            rows = conn.execute("SELECT id, physical_key FROM objects WHERE state = 'reclaiming'").fetchall()
        for row in rows:
            self.store.unlink(row['physical_key'])
            with self.db.transaction() as conn:
                conn.execute("UPDATE objects SET state = 'reclaimed' WHERE id = %s AND state = 'reclaiming'", (row['id'],))
        return len(rows)

    def _clean_staging(self):
        """Remove staging areas of terminal or superseded attempts (and stale unknown ones)."""
        removed = 0
        now = dt.datetime.now(dt.timezone.utc)
        with self.db.connect() as conn:
            for job_id, fence, path in list(self.store.staging_attempts()):
                if job_id is None:
                    stale = True
                else:
                    job = conn.execute('SELECT state, fence FROM jobs WHERE id = %s', (job_id,)).fetchone()
                    if job is None:
                        age = now - dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc)
                        stale = age > self.pending_ttl
                    else:
                        stale = job['state'] in TERMINAL or job['fence'] != fence or job['state'] == 'queued'
                if stale:
                    self.store.remove_staging(path)
                    removed += 1
        return removed


def add_hold(db, reason):
    hold_id = uuid.uuid4()
    with db.transaction() as conn:
        conn.execute('INSERT INTO gc_holds(id, reason) VALUES (%s, %s)', (hold_id, reason))
    return hold_id


def release_hold(db, hold_id):
    with db.transaction() as conn:
        conn.execute('UPDATE gc_holds SET released_at = now() WHERE id = %s AND released_at IS NULL', (hold_id,))
