"""``numek`` command line: local cluster, schema, maintenance, backups and processes."""
import getpass
import importlib
import json
import signal
import threading
from pathlib import Path

import click

from .db import Database
from .db.migrator import migrate, schema_version
from .errors import PlatformError


def _emit(value):
    click.echo(json.dumps(value, indent=2, sort_keys=True, default=str))


def _database(dsn, path):
    if dsn:
        return Database(dsn)
    if path:
        from .local import LocalCluster
        return Database(LocalCluster(path).dsn())
    raise click.UsageError('Provide --dsn or --path.')


@click.group()
def main():
    """NUMEK evidence and execution platform."""


@main.group()
def local():
    """Managed local PostgreSQL cluster (P-LOCAL)."""


@local.command('init')
@click.option('--path', required=True, type=click.Path(path_type=Path))
def local_init(path):
    from .local import LocalCluster
    cluster = LocalCluster(path)
    cluster.start()
    applied = migrate(Database(cluster.dsn()))
    _emit({'path': str(path), 'applied_migrations': applied, 'schema_version': schema_version(Database(cluster.dsn()))})


@local.command('start')
@click.option('--path', required=True, type=click.Path(path_type=Path))
def local_start(path):
    from .local import LocalCluster
    LocalCluster(path).start()
    _emit({'running': True})


@local.command('stop')
@click.option('--path', required=True, type=click.Path(path_type=Path))
def local_stop(path):
    from .local import LocalCluster
    LocalCluster(path).stop()
    _emit({'running': False})


@local.command('status')
@click.option('--path', required=True, type=click.Path(path_type=Path))
def local_status(path):
    from .local import LocalCluster
    cluster = LocalCluster(path)
    running = cluster.running()
    _emit({'initialized': cluster.initialized(), 'running': running, 'user': getpass.getuser(),
           'schema_version': schema_version(Database(cluster.dsn())) if running else None})


@main.group()
def db():
    """Schema management."""


@db.command('migrate')
@click.option('--dsn')
@click.option('--path', type=click.Path(path_type=Path))
def db_migrate(dsn, path):
    database = _database(dsn, path)
    _emit({'applied': migrate(database), 'schema_version': schema_version(database)})


@main.command('gc')
@click.option('--dsn')
@click.option('--path', type=click.Path(path_type=Path))
@click.option('--objects', 'objects_root', required=True, type=click.Path(path_type=Path))
def gc_command(dsn, path, objects_root):
    """Reclaim eligible objects once."""
    from .evidence.gc import GarbageCollector
    from .objects import LocalObjectStore
    _emit(GarbageCollector(_database(dsn, path), LocalObjectStore(objects_root)).run_once())


@main.group()
def backup():
    """Consistent backups (database snapshot + objects + wrapped keyring)."""


@backup.command('create')
@click.option('--dsn')
@click.option('--path', type=click.Path(path_type=Path))
@click.option('--objects', 'objects_root', required=True, type=click.Path(path_type=Path))
@click.option('--secrets', 'secrets_root', required=True, type=click.Path(path_type=Path))
@click.option('--destination', required=True, type=click.Path(path_type=Path))
@click.option('--include-terminal-raw', is_flag=True)
@click.option('--config', 'config_path', type=click.Path(path_type=Path, exists=True, dir_okay=False),
              help='The installation configuration file to include (with its digest).')
@click.password_option('--passphrase', prompt='Backup passphrase')
def backup_create(dsn, path, objects_root, secrets_root, destination, include_terminal_raw, config_path, passphrase):
    from .backup import create_backup
    from .objects import LocalObjectStore
    from .secrets import FileSecretStore
    _emit(create_backup(_database(dsn, path), LocalObjectStore(objects_root), FileSecretStore(secrets_root),
                        destination, passphrase=passphrase, include_terminal_raw=include_terminal_raw,
                        config_bytes=None if config_path is None else config_path.read_bytes()))


@backup.command('verify')
@click.option('--source', required=True, type=click.Path(path_type=Path, exists=True))
def backup_verify(source):
    from .backup import verify_backup
    _emit(verify_backup(source))


@main.command('worker')
@click.option('--dsn', required=True)
@click.option('--objects', 'objects_root', required=True, type=click.Path(path_type=Path))
@click.option('--registry', required=True, help='module:attribute of a numek_platform Registry')
@click.option('--lanes', default='essential,investigation,maintenance')
def worker(dsn, objects_root, registry, lanes):
    """Run a worker host until interrupted."""
    from .execution.host import WorkerHost
    module, _, attribute = registry.partition(':')
    host = WorkerHost(Database(dsn), objects_root, registry=getattr(importlib.import_module(module), attribute),
                      lanes=lanes.split(','))
    _run_until_signal(host.run)


@main.command('controller')
@click.option('--dsn', required=True)
@click.option('--objects', 'objects_root', required=True, type=click.Path(path_type=Path))
def controller(dsn, objects_root):
    """Run the controller (single active leader) until interrupted."""
    from .evidence.gc import GarbageCollector
    from .execution.controller import Controller
    from .objects import LocalObjectStore
    database = Database(dsn)
    _run_until_signal(Controller(database, gc=GarbageCollector(database, LocalObjectStore(objects_root))).run)


def _run_until_signal(target):
    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    target(stop)


def run():
    try:
        main(standalone_mode=True)
    except PlatformError as exc:
        raise click.ClickException(f'{exc} [{exc.code}]') from exc
