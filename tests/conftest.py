"""Backend selection shared by the ConfidenceGuard suites (CG7 S3d test port).

``NUMEK_PLATFORM_DSN`` runs every new workspace on a shared platform
installation. Workspace-level backup and restore is intentionally a P-LOCAL
contract: a workspace on a shared installation refuses ``backup`` with
``backup_scope`` (the installation backup covers it; see
``tests/platform/test_cg3_on_platform.py``). Tests marked ``workspace_backup``
therefore run, unchanged, on P-LOCAL platform workspaces when the shared DSN is
set: each such workspace gets its own managed cluster, stopped afterwards.
Without the DSN the marker does nothing (catalog v2).
"""
import os
from pathlib import Path

import pytest

DSN_ENV = 'NUMEK_PLATFORM_DSN'


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
