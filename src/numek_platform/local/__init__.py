"""P-LOCAL: a managed PostgreSQL cluster for one user on one machine.

The cluster listens on a Unix socket only (``listen_addresses=''``) inside an
owner-only directory, so access is limited to the operating-system user that
owns the platform root. Trust authentication over that socket is therefore
equivalent to OS-user access control, the same boundary the v2 workspace used.

macOS note: the postmaster aborts with "became multithreaded during startup"
when no valid locale is in the environment, so ``LC_ALL`` is always set.
"""
import getpass
import hashlib
import os
import platform
import re
import shutil
import subprocess
from pathlib import Path

from ..errors import PlatformError
from ..fsutil import private_directory

MIN_MAJOR = 16
SOCKET_LIMIT = 100
SEARCH = ('/opt/homebrew/opt/postgresql@17/bin', '/opt/homebrew/opt/postgresql@16/bin',
          '/usr/local/opt/postgresql@17/bin', '/usr/lib/postgresql/17/bin', '/usr/lib/postgresql/16/bin')


def find_binaries():
    """Locate PostgreSQL >= 16 server binaries (NUMEK_PG_BIN overrides)."""
    candidates = []
    if os.environ.get('NUMEK_PG_BIN'):
        candidates.append(os.environ['NUMEK_PG_BIN'])
    pg_config = shutil.which('pg_config')
    if pg_config:
        try:
            candidates.append(subprocess.run([pg_config, '--bindir'], capture_output=True, text=True, check=True).stdout.strip())
        except (OSError, subprocess.CalledProcessError):
            pass
    candidates.extend(SEARCH)
    for folder in candidates:
        postgres = Path(folder) / 'postgres'
        if postgres.is_file():
            version = subprocess.run([str(postgres), '--version'], capture_output=True, text=True).stdout
            match = re.search(r'\(PostgreSQL\)\s+(\d+)', version)   # e.g. "postgres (PostgreSQL) 17.12 (Homebrew)"
            if match and int(match.group(1)) >= MIN_MAJOR:
                return Path(folder)
    raise PlatformError('PostgreSQL 16 or newer is required for persistent workspaces. Install it (for example '
                        '`brew install postgresql@17`) or set NUMEK_PG_BIN.', 'postgres_missing')


def server_env():
    env = dict(os.environ)
    env['LC_ALL'] = os.environ.get('NUMEK_PG_LOCALE') or ('en_US.UTF-8' if platform.system() == 'Darwin' else 'C.UTF-8')
    return env


class LocalCluster:
    def __init__(self, root, *, database='numek'):
        self.root = private_directory(root)
        self.pg_root = private_directory(self.root / 'pg')
        self.data = self.pg_root / 'data'
        self.log = self.pg_root / 'server.log'
        self.database = database
        self.bin = find_binaries()
        self.socket_dir = self._socket_dir()

    def _socket_dir(self):
        preferred = self.pg_root / 'sock'
        if len(str(preferred)) + len('/.s.PGSQL.5432') < SOCKET_LIMIT:
            return private_directory(preferred)
        tag = hashlib.sha256(str(self.root).encode()).hexdigest()[:12]
        uid = os.getuid() if hasattr(os, 'getuid') else 0
        return private_directory(Path('/tmp').resolve() / f'numek-{uid}-{tag}')

    def _run(self, *args, check=True):
        result = subprocess.run([str(self.bin / args[0]), *args[1:]], capture_output=True, text=True, env=server_env())
        if check and result.returncode != 0:
            raise PlatformError(f'{args[0]} failed: {result.stderr.strip()[-400:]}', 'postgres_failed')
        return result

    def initialized(self):
        return (self.data / 'PG_VERSION').is_file()

    def init(self):
        if self.initialized():
            return False
        self._run('initdb', '-D', str(self.data), '-A', 'trust', '-U', getpass.getuser(), '-E', 'UTF8',
                  '--no-locale', '--data-checksums')
        with open(self.data / 'postgresql.conf', 'a', encoding='utf-8') as conf:
            conf.write('\n# NUMEK P-LOCAL: Unix socket only, owner-only directory.\n'
                       "listen_addresses = ''\n"
                       f"unix_socket_directories = '{self.socket_dir}'\n"
                       'unix_socket_permissions = 0700\n'
                       'fsync = on\nsynchronous_commit = on\nfull_page_writes = on\n'
                       'wal_level = replica\nmax_connections = 100\n')
        return True

    def running(self):
        return self._run('pg_ctl', '-D', str(self.data), 'status', check=False).returncode == 0

    def start(self):
        if not self.initialized():
            self.init()
        if not self.running():
            self._run('pg_ctl', '-D', str(self.data), '-l', str(self.log), '-w', '-t', '60', 'start')
        self._ensure_database()

    def stop(self):
        if self.initialized() and self.running():
            self._run('pg_ctl', '-D', str(self.data), '-w', '-m', 'fast', 'stop')

    def dsn(self, database=None):
        return f'host={self.socket_dir} dbname={database or self.database} user={getpass.getuser()}'

    def _ensure_database(self, name=None):
        import psycopg
        name = name or self.database
        with psycopg.connect(self.dsn('postgres'), autocommit=True) as conn:
            exists = conn.execute('SELECT 1 FROM pg_database WHERE datname = %s', (name,)).fetchone()
            if not exists:
                conn.execute(f'CREATE DATABASE "{name}"')

    def create_database(self, name, template=None):
        import psycopg
        with psycopg.connect(self.dsn('postgres'), autocommit=True) as conn:
            conn.execute(f'CREATE DATABASE "{name}"' + (f' TEMPLATE "{template}"' if template else ''))
        return self.dsn(name)

    def drop_database(self, name):
        import psycopg
        with psycopg.connect(self.dsn('postgres'), autocommit=True) as conn:
            conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
