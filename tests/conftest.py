"""Platform installation for the ConfidenceGuard suites (CG7 S3).

Every ConfidenceGuard workspace is stored on the NUMEK platform (catalog v2 is
retired as a writer). Unless the caller provides ``NUMEK_PLATFORM_DSN``, the
session starts one managed PostgreSQL cluster (P-LOCAL) and points the variable
at it, so workspaces share one installation instead of starting a cluster each;
it is stopped and removed when the session ends.

Workspace-level backup and restore is intentionally a P-LOCAL
contract: a workspace on a shared installation refuses ``backup`` with
``backup_scope`` (tested in ``tests/platform/test_cg3_on_platform.py``;
installation-level backup of such workspaces is a tracked limitation). Tests marked ``workspace_backup``
therefore run, unchanged, on P-LOCAL platform workspaces when the shared DSN is
set: each such workspace gets its own managed cluster, stopped afterwards.
Without a DSN the marker does nothing (every workspace is then P-LOCAL anyway).
"""
import os
import shutil
import tempfile
from pathlib import Path

import pytest

DSN_ENV = 'NUMEK_PLATFORM_DSN'
_SESSION = {}


def pytest_sessionstart(session):
    if os.environ.get(DSN_ENV):
        return
    from numek_platform.errors import PlatformError
    from numek_platform.local import LocalCluster
    root = Path(tempfile.mkdtemp(prefix='nmk-cg-')).resolve()
    try:
        cluster = LocalCluster(root / 'cluster')
        cluster.start()
    except PlatformError:
        shutil.rmtree(root, ignore_errors=True)      # no PostgreSQL binaries: workspace tests report it
        return
    os.environ[DSN_ENV] = cluster.dsn()
    _SESSION.update(cluster=cluster, root=root)


def pytest_sessionfinish(session, exitstatus):
    cluster = _SESSION.pop('cluster', None)
    if cluster is not None:
        os.environ.pop(DSN_ENV, None)
        try:
            cluster.stop()
        finally:
            shutil.rmtree(_SESSION.pop('root'), ignore_errors=True)


def pytest_configure(config):
    config.addinivalue_line('markers', 'workspace_backup: workspace backup/restore; runs on P-LOCAL under a shared DSN')


@pytest.fixture(autouse=True)
def _workspace_backup_backend(request, monkeypatch):
    if request.node.get_closest_marker('workspace_backup') is None or not os.environ.get(DSN_ENV):
        yield
        return
    from confidenceguard import ReliabilityWorkspace
    original = ReliabilityWorkspace.initialize.__func__

    def local(cls, path, config=None, *, platform=None):
        return original(cls, path, config, platform=True)

    monkeypatch.delenv(DSN_ENV)
    monkeypatch.setattr(ReliabilityWorkspace, 'initialize', classmethod(local))
    tmp = Path(request.getfixturevalue('tmp_path'))
    try:
        yield
    finally:
        from numek_platform.local import LocalCluster
        for version in tmp.rglob('PG_VERSION'):
            if version.parent.name == 'data' and version.parent.parent.name == 'pg':
                try:
                    LocalCluster(version.parent.parent.parent).stop()
                except Exception:
                    pass
