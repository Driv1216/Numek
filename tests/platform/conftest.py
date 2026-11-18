"""Shared fixtures: a real PostgreSQL cluster managed by P-LOCAL itself.

One cluster per session; one migrated template database; each test gets its
own database cloned from the template, plus a fresh object store.
"""
import os
import shutil
import sys
import tempfile
import uuid
from pathlib import Path

import pytest

pytest.importorskip('psycopg')

from numek_platform.db import Database  # noqa: E402
from numek_platform.db.migrator import migrate  # noqa: E402
from numek_platform.errors import PlatformError  # noqa: E402

HERE = Path(__file__).resolve().parent


@pytest.fixture(scope='session')
def cluster():
    from numek_platform.local import LocalCluster
    root = Path(tempfile.mkdtemp(prefix='nmk-')).resolve()
    try:
        cluster = LocalCluster(root / 'cluster')
    except PlatformError as exc:
        shutil.rmtree(root, ignore_errors=True)
        pytest.skip(str(exc))
    try:
        cluster.start()
        cluster.create_database('numek_template')
        migrate(Database(cluster.dsn('numek_template')))
        yield cluster
    finally:
        cluster.stop()
        shutil.rmtree(root, ignore_errors=True)


class Platform:
    def __init__(self, cluster, root):
        from numek_platform.objects import LocalObjectStore
        from numek_platform.scope import create_org
        from numek_platform.evidence.catalogs import create_catalog
        self.cluster = cluster
        self.name = 't_' + uuid.uuid4().hex[:12]
        self.db = Database(cluster.create_database(self.name, template='numek_template'))
        self.root = root
        self.store = LocalObjectStore(root / 'store')
        with self.db.transaction() as conn:
            self.scope = create_org(conn, 'org-' + self.name)
            self.catalog_id = create_catalog(conn, self.scope, 'history')

    def new_org(self, label):
        from numek_platform.scope import create_org
        from numek_platform.evidence.catalogs import create_catalog
        with self.db.transaction() as conn:
            scope = create_org(conn, f'{label}-{self.name}')
            catalog_id = create_catalog(conn, scope, 'history')
        return scope, catalog_id


@pytest.fixture
def platform(cluster, tmp_path):
    instance = Platform(cluster, tmp_path.resolve())
    yield instance
    cluster.drop_database(instance.name)


@pytest.fixture
def job_path(monkeypatch):
    """Make tests/platform importable by job child processes."""
    current = os.environ.get('PYTHONPATH', '')
    monkeypatch.setenv('PYTHONPATH', os.pathsep.join(p for p in (str(HERE), current) if p))
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    return HERE
