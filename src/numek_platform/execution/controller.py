"""Single-leader controller.

Leadership is a database row with an epoch that increases on every change of
holder. Controller writes assert ``(holder, epoch)`` inside their own
transaction, so a deposed controller cannot act even if it still believes it
leads.
"""
import os
import threading
import time
import uuid

from ..errors import PlatformError
from . import jobs as job_store


def acquire_leadership(conn, holder, ttl_seconds=15):
    """Take or renew leadership. Returns the epoch held, or None if another leader is live."""
    with conn.transaction():
        row = conn.execute(
            '''INSERT INTO controller_leadership(singleton, holder, epoch, expires_at)
               VALUES (true, %s, 1, now() + make_interval(secs => %s))
               ON CONFLICT (singleton) DO UPDATE SET
                   holder = EXCLUDED.holder,
                   epoch = CASE WHEN controller_leadership.holder = EXCLUDED.holder
                                THEN controller_leadership.epoch ELSE controller_leadership.epoch + 1 END,
                   expires_at = EXCLUDED.expires_at
               WHERE controller_leadership.holder = EXCLUDED.holder OR controller_leadership.expires_at < now()
               RETURNING epoch''', (holder, ttl_seconds)).fetchone()
    return None if row is None else row['epoch']


def assert_leader(conn, holder, epoch):
    row = conn.execute('SELECT holder, epoch, expires_at > now() AS live FROM controller_leadership FOR SHARE').fetchone()
    if row is None or row['holder'] != holder or row['epoch'] != epoch or not row['live']:
        raise PlatformError('This controller is not the current leader.', 'not_leader')


class Controller:
    def __init__(self, db, *, gc=None, holder=None, ttl_seconds=15, gc_every_seconds=300):
        self.db = db
        self.gc = gc
        self.holder = holder or f'controller-{os.getpid()}-{uuid.uuid4().hex[:8]}'
        self.ttl_seconds = ttl_seconds
        self.gc_every_seconds = gc_every_seconds
        self.epoch = None
        self._last_gc = 0.0

    def run_once(self):
        with self.db.connect() as conn:
            self.epoch = acquire_leadership(conn, self.holder, self.ttl_seconds)
            if self.epoch is None:
                return {'leader': False}
            with conn.transaction():
                assert_leader(conn, self.holder, self.epoch)
                expired = job_store.expire_leases(conn)
                dead_inline = job_store.expire_inline(conn)
        report = {'leader': True, 'epoch': self.epoch, 'expired': len(expired), 'dead_inline': len(dead_inline)}
        if self.gc is not None and time.monotonic() - self._last_gc >= self.gc_every_seconds:
            self._last_gc = time.monotonic()
            report['gc'] = self.gc.run_once()
        return report

    def run(self, stop, interval=None):
        interval = interval or max(self.ttl_seconds / 3, 1)
        while not stop.is_set():
            try:
                self.run_once()
            except PlatformError:
                pass
            stop.wait(interval)


def run_in_thread(controller, stop=None):
    stop = stop or threading.Event()
    thread = threading.Thread(target=controller.run, args=(stop,), daemon=True, name='numek-controller')
    thread.start()
    return stop, thread
