"""Execution contexts for analytical services.

ConfidenceGuard services currently call ``compat.supervise`` at 35 sites, which
spawns a fresh supervised interpreter per phase. They will call
``ctx.run(operation, arguments, limits)`` instead:

* :class:`SpawnContext`, for the ephemeral local workbench, keeps today's
  behaviour exactly (``datatrust.worker.run_supervised``).
* :class:`InProcessContext`, for platform jobs, calls the operation directly,
  because the job process is already isolated, budgeted and supervised by its
  worker host. Deadline and cancellation are checked at phase boundaries.

Analytical functions are unchanged; only where they execute changes.
"""
import time

from ..errors import PlatformError


class SpawnContext:
    def run(self, operation, arguments, limits, *, progress=None, cancel=None, owned_snapshots=()):
        from datatrust.worker import run_supervised
        return run_supervised(operation, arguments, limits, progress=progress, cancel=cancel,
                              owned_snapshots=owned_snapshots)


class InProcessContext:
    def __init__(self, *, deadline=None, cancelled=None):
        self.deadline = deadline
        self.cancelled = cancelled or (lambda: False)

    def check(self, stage):
        if self.cancelled():
            raise PlatformError('The job was cancelled.', 'cancelled')
        if self.deadline is not None and time.monotonic() > self.deadline:
            raise PlatformError(f'Job deadline exceeded before {stage}.', 'deadline')

    def run(self, operation, arguments, limits=None, *, progress=None, cancel=None, owned_snapshots=()):
        name = getattr(operation, '__name__', 'operation')
        self.check(name)
        if cancel is not None and cancel.is_set():
            raise PlatformError('The job was cancelled.', 'cancelled')
        result = operation(*arguments, progress=progress or (lambda _value: None))
        self.check(name)
        return result
