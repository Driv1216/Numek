"""Job process entry point.

Launched as ``python -m numek_platform.execution._child`` with native thread
caps already in its environment, so they apply before NumPy, BLAS, DuckDB or
Torch are imported. Keep this module import-light.

Warm processes run many jobs sequentially. Each job gets a fresh context and
scratch directory; after the job the context must be unreachable, scratch is
removed and registered module-state probes must be unchanged. A violation
recycles the process (the job's own result is still reported).
"""
import gc
import importlib
import os
import shutil
import sys
import time
import traceback
import uuid
import weakref
from multiprocessing.connection import Connection

THREAD_VARIABLES = ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS',
                    'NUMEXPR_NUM_THREADS')
from numek_platform.execution.probes import probe_state as _probe_state, register_state_probe  # noqa: F401


class JobContext:
    """Everything a job may use. Lives only for one job."""

    def __init__(self, spec):
        from ..db import Database
        from ..objects import LocalObjectStore
        from ..scope import OrgScope
        from .jobs import JobLease

        lease = spec['lease']
        self.lease = JobLease(uuid.UUID(lease['org_id']), uuid.UUID(lease['job_id']), lease['fence'],
                              lease['kind'], lease['owner'])
        self.scope = OrgScope(self.lease.org_id)
        self.db = Database(spec['dsn'], application_name=f"numek-job-{lease['kind']}")
        self.store = LocalObjectStore(spec['store_root'])
        self.threads = spec['threads']
        self.deadline = time.monotonic() + spec['seconds']
        self.scratch = os.path.join(spec['scratch_root'], f"{self.lease.job_id.hex}.{self.lease.fence}")
        os.makedirs(self.scratch, mode=0o700)
        os.chmod(self.scratch, 0o700)

    def check(self, stage='job'):
        if time.monotonic() > self.deadline:
            raise TimeoutError(f'Job deadline exceeded during {stage}.')

    def close(self):
        shutil.rmtree(self.scratch, ignore_errors=True)


def _apply_thread_limits(threads):
    try:
        from threadpoolctl import threadpool_limits
        threadpool_limits(limits=threads)
    except ImportError:
        pass


def _load(spec):
    module_name, _, attribute = spec['function'].partition(':')
    return getattr(importlib.import_module(module_name), attribute)


def _run(function, spec):
    context = JobContext(spec)
    reference = weakref.ref(context)
    try:
        result = function(context, spec['payload'])
    finally:
        context.close()
        del context
    gc.collect()
    return result, reference() is None


def main():
    connection = Connection(int(os.environ['NUMEK_CHILD_FD']))
    warm = os.environ.get('NUMEK_CHILD_MODE') == 'warm'
    _apply_thread_limits(int(os.environ.get('NUMEK_JOB_THREADS', '1')))
    while True:
        try:
            message, spec = connection.recv()
        except EOFError:
            return
        if message == 'exit':
            return
        try:
            function = _load(spec)                         # import first: probes may register at import
            before = _probe_state() if warm else None
            result, released = _run(function, spec)
        except BaseException as exc:  # reported to the host; the host decides retry semantics
            code = getattr(exc, 'code', None) or ('deadline' if isinstance(exc, TimeoutError) else 'job_failed')
            connection.send(('error', {'code': code, 'message': str(exc)[:2000], 'type': type(exc).__name__,
                                       'retryable': bool(getattr(exc, 'retryable', False)),
                                       'trace': traceback.format_exc(limit=8)[-4000:]}))
            if not warm:
                return
            continue
        clean = released and (not warm or _probe_state() == before)
        connection.send(('result', {'result': result, 'isolation_clean': clean}))
        if not warm or not clean:
            return


if __name__ == '__main__':
    sys.exit(main())
