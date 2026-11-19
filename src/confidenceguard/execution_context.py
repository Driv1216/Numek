"""Where ConfidenceGuard's analytical phases execute (CG7 execution-agnostic services).

Services call ``ctx.run(operation, arguments, config, progress=..., cancel=..., deadline=...)``
instead of spawning a process themselves. The active context decides how:

* :class:`SpawnContext` (the default; the ephemeral local workbench and every
  caller that sets nothing) runs each phase in a fresh supervised interpreter
  with DataTrust's resource limits, exactly as before.
* :class:`InProcessContext` (persistent platform jobs, whose process is already
  isolated, budgeted and supervised by its worker host; and migration
  validation) calls the phase directly. Arguments and results cross the
  boundary by pickling, as they do for a spawned phase, so callers and phases
  never share mutable state. Cancellation and the deadline are checked at phase
  boundaries, and process-local governance (worker reservations, study
  authority) is isolated per phase and its attempts are closed when it ends.

Analytical functions are unchanged; only where they execute changes.
"""
import contextlib
import contextvars
import pickle
import time

from .contracts import EvaluationError

_ACTIVE = contextvars.ContextVar('confidenceguard_execution_context', default=None)


def _limited(config, deadline):
    from . import compat
    limits = compat.options(config)
    if deadline is not None:
        from dataclasses import replace
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise EvaluationError('Operation deadline exhausted before the next phase.', 'deadline_exceeded')
        limits = replace(limits, max_seconds=min(limits.max_seconds, remaining))
    return limits


def _evaluation_error(exc):
    error = EvaluationError('Evaluation stopped; inspect the execution code and configured limits.', exc.code, exc.stage)
    error.execution = getattr(exc, 'execution', {})
    return error


class SpawnContext:
    """Fresh supervised interpreter per phase (DataTrust worker, process-tree limits)."""
    kind = 'spawn'

    def run(self, operation, arguments, config, *, progress=None, cancel=None, deadline=None):
        from datatrust.contracts import AnalysisError
        from datatrust.worker import run_supervised
        limits = _limited(config, deadline)
        try:
            return run_supervised(operation, arguments, limits, progress=progress, cancel=cancel)
        except AnalysisError as exc:
            raise _evaluation_error(exc) from exc


class InProcessContext:
    """Run phases in the current (already isolated) process with phase-boundary budget checks."""
    kind = 'in_process'

    def __init__(self, *, deadline=None, cancel=None):
        self.deadline = deadline
        self.cancel = cancel

    def _check(self, cancel, deadline, stage):
        for event in (self.cancel, cancel):
            if event is not None and event.is_set():
                raise EvaluationError('Operation cancelled.', 'cancelled', stage)
        for limit in (self.deadline, deadline):
            if limit is not None and time.monotonic() > limit:
                raise EvaluationError('Operation deadline exhausted.', 'deadline_exceeded', stage)

    def run(self, operation, arguments, config, *, progress=None, cancel=None, deadline=None):
        from datatrust.contracts import AnalysisError
        from .platform_catalog import process_scope
        stage = getattr(operation, '__name__', 'operation')
        self._check(cancel, deadline, stage)
        arguments = pickle.loads(pickle.dumps(tuple(arguments)))           # same isolation as a spawned phase
        try:
            with process_scope():
                result = operation(*arguments, progress=progress or (lambda *_args, **_kwargs: None))
        except AnalysisError as exc:
            raise _evaluation_error(exc) from exc
        self._check(cancel, deadline, stage)
        return pickle.loads(pickle.dumps(result))


class _Dispatch:
    """``ctx``: the module-level entry point services call."""

    @property
    def current(self):
        return _ACTIVE.get() or _DEFAULT

    def run(self, operation, arguments, config, *, progress=None, cancel=None, deadline=None):
        return self.current.run(operation, arguments, config, progress=progress, cancel=cancel, deadline=deadline)


_DEFAULT = SpawnContext()
ctx = _Dispatch()


@contextlib.contextmanager
def using(context):
    """Run the enclosed service calls under ``context`` (for example a platform job's InProcessContext)."""
    token = _ACTIVE.set(context)
    try:
        yield context
    finally:
        _ACTIVE.reset(token)
