"""Operations tasks run by the single-leader controller (plan C.5, H.6, H.7).

Every write the controller makes is guarded by its leadership epoch:
- monitoring cycles are enqueued as ``ops_monitoring_cycle`` jobs (one per deployment and slot; idempotent);
- escalation timers fire;
- the notification outbox is delivered;
- the daily retention job is enqueued.

A deposed controller's enqueue transaction fails ``assert_leader``. Escalation and delivery are row-locked with
``SKIP LOCKED`` and idempotent, so an overlapping run cannot double-act.
"""
import time
from datetime import datetime, timezone

from numek_platform.execution import controller as platform_controller
from numek_platform.execution import jobs

CYCLE_SECONDS = 300


class OperationsTasks:
    def __init__(self, installation, *, cycle_seconds=CYCLE_SECONDS, clock=time.time, resolver=None):
        self.installation = installation
        self.cycle_seconds = cycle_seconds
        self.clock = clock
        self.resolver = resolver

    def __call__(self, holder, epoch):
        now = datetime.fromtimestamp(self.clock(), tz=timezone.utc)
        return {'cycles_enqueued': self.enqueue_cycles(holder, epoch, now), 'retention': self.enqueue_retention(holder, epoch, now),
                'escalated': self.escalate(now), 'notifications': self.deliver(now)}

    def enqueue_cycles(self, holder, epoch, now):
        scope = self.installation.scope
        slot = int(now.timestamp()) // self.cycle_seconds
        enqueued = []
        with self.installation.db.connect() as conn:
            with conn.transaction():
                platform_controller.assert_leader(conn, holder, epoch)
                deployments = [r['deployment_id'] for r in conn.execute(
                    "SELECT deployment_id FROM ops_monitoring_definitions WHERE org_id = %s AND state = 'confirmed' ORDER BY deployment_id",
                    (scope.org_id,)).fetchall()]
                for deployment in deployments:
                    busy = conn.execute("SELECT 1 FROM jobs WHERE org_id = %s AND kind = 'ops_monitoring_cycle' AND state IN ('queued', 'running') "
                                        "AND payload->>'deployment' = %s LIMIT 1", (scope.org_id, deployment)).fetchone()
                    if busy:
                        continue
                    jobs.enqueue(conn, scope, 'ops_monitoring_cycle', idempotency_key=f'ops-cycle:{deployment}:{slot}',
                                 payload={'installation': str(self.installation.root), 'deployment': deployment})
                    enqueued.append(deployment)
        return enqueued

    def enqueue_retention(self, holder, epoch, now):
        scope = self.installation.scope
        with self.installation.db.connect() as conn:
            with conn.transaction():
                platform_controller.assert_leader(conn, holder, epoch)
                row = jobs.enqueue(conn, scope, 'ops_retention', idempotency_key=f'ops-retention:{now.date().isoformat()}',
                                   lane='maintenance', payload={'installation': str(self.installation.root)})
        return str(row['id'])

    def escalate(self, now):
        from .incidents import incidents
        return incidents.escalate_due(self.installation, now=now)

    def deliver(self, now):
        from .incidents import notify
        return notify.send_due(self.installation, now=now, resolver=self.resolver)


def controller(installation, **kwargs):
    """A platform controller that also runs the operations tasks while it leads."""
    return platform_controller.Controller(installation.db, tasks=[OperationsTasks(installation, **kwargs)])
