"""A NUMEK installation: one database, one object store, one secrets store, one catalogs directory.

``installation.json`` (owner-only) names the database by environment variable
(a shared or managed PostgreSQL; the connection string is never written to
disk) or as a P-LOCAL cluster under the installation root. Catalogs created
for an installation (CG7 system catalogs) bind to its single object store, so
one installation backup covers all of them.

Layout::

    <root>/installation.json
    <root>/platform/        P-LOCAL cluster (when no DSN variable is configured)
    <root>/objects/         object store
    <root>/secrets/         data keys, reserve secrets (0700)
    <root>/catalogs/<id>/   per-catalog working directories (staging, verified copies)
"""
import json
import os
from pathlib import Path

from .errors import PlatformError
from .fsutil import private_directory, write_atomic

FORMAT = 'numek_installation/1'
CONFIG = 'installation.json'
DEFAULT_ORG = 'confidenceguard-local'


class Installation:
    def __init__(self, root):
        self.root = Path(root).absolute()
        path = self.root / CONFIG
        if not path.is_file():
            raise PlatformError('No NUMEK installation exists here.', 'installation_missing')
        self.config = json.loads(path.read_bytes())
        if self.config.get('format') != FORMAT:
            raise PlatformError('Unsupported installation configuration.', 'installation_format')
        self._db = None
        self._scope = None

    @classmethod
    def create(cls, root, *, dsn_env=None, org=DEFAULT_ORG):
        """Create (or reopen) an installation; migrates the schema and creates its organization."""
        root = private_directory(Path(root).absolute())
        if not (root / CONFIG).is_file():
            config = {'format': FORMAT, 'org': org, 'objects': 'objects', 'secrets': 'secrets', 'catalogs': 'catalogs',
                      **({'dsn_env': dsn_env} if dsn_env else {'local_cluster': 'platform'})}
            write_atomic(root / CONFIG, json.dumps(config, sort_keys=True, indent=1).encode())
        installation = cls(root)
        for key in ('objects', 'secrets', 'catalogs'):
            private_directory(installation.root / installation.config[key])
        from .db.migrator import migrate
        migrate(installation.db)
        installation.scope
        return installation

    def dsn(self):
        if self.config.get('dsn_env'):
            value = os.environ.get(self.config['dsn_env'])
            if not value:
                raise PlatformError('The installation database is not configured in this environment.', 'platform_unavailable')
            return value
        from .local import LocalCluster
        cluster = LocalCluster(self.root / self.config['local_cluster'])
        if not cluster.running():
            cluster.start()
        return cluster.dsn()

    @property
    def db(self):
        if self._db is None:
            from .db import Database
            self._db = Database(self.dsn())
        return self._db

    @property
    def store(self):
        from .objects import LocalObjectStore
        return LocalObjectStore(self.root / self.config['objects'])

    @property
    def secrets(self):
        from .secrets import FileSecretStore
        return FileSecretStore(self.root / self.config['secrets'])

    @property
    def data_keys(self):
        from .secrets import DataKeys
        return DataKeys(self.secrets)

    def catalog_root(self, catalog_id):
        return private_directory(self.root / self.config['catalogs'] / str(catalog_id))

    @property
    def scope(self):
        if self._scope is not None:
            return self._scope
        from .scope import create_org, get_org
        with self.db.transaction() as conn:
            conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))', ('numek:org:' + self.config['org'],))
            try:
                self._scope = get_org(conn, self.config['org'])
            except PlatformError:
                self._scope = create_org(conn, self.config['org'])
        return self._scope

    def stop(self):
        """Stop a P-LOCAL cluster this installation owns (no-op for an external database)."""
        if self.config.get('local_cluster'):
            from .local import LocalCluster
            LocalCluster(self.root / self.config['local_cluster']).stop()
