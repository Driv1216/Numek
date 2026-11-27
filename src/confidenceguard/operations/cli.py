"""``confidenceguard ops``: local administration and single-host operation of a NUMEK installation.

    confidenceguard ops init --root /srv/numek [--dsn-env NUMEK_DSN]
    confidenceguard ops user create alice --role analyst          (password read from stdin)
    confidenceguard ops token issue scorecard-producer --scope ingest:source:scorecard-events
    confidenceguard ops system register credit-default --name "Credit default" --namespace credit
    confidenceguard ops deployment register credit-default scorecard-prod --name Scorecard --tier 1
    confidenceguard ops source register scorecard-prod scorecard-events --contract contract.json
    confidenceguard ops definition inspect scorecard-prod --spec definition.json
    confidenceguard ops definition confirm scorecard-prod 1 <inspection digest>
    confidenceguard ops cycle scorecard-prod
    confidenceguard ops incidents [--state open]
    confidenceguard ops incident 3 [--as-known detection]
    confidenceguard ops report 3 --out incident-3.pdf --format pdf [--audience local] [--json-out incident-3.json]
    confidenceguard ops audit anchor --sink /var/log/numek/anchors.jsonl   (append the chain head to an external sink)
    confidenceguard ops audit verify --sink /var/log/numek/anchors.jsonl   (recompute the chain; compare every anchor in the sink)
    confidenceguard ops serve [--host 127.0.0.1 --port 8443 --workers 2 --threads 8] [--tls-cert C --tls-key K | --trusted-proxy --proxy-ips IP]
    confidenceguard ops controller
    confidenceguard ops worker [--lanes essential,investigation,maintenance]

The installation root comes from ``--installation`` or ``NUMEK_INSTALLATION``. Secrets (passwords, token
secrets, webhook keys) are printed once and never stored in the database.
"""
import json
import os
import sys
from pathlib import Path

import click


def _installation(path):
    from numek_platform.installation import Installation
    root = path or os.environ.get('NUMEK_INSTALLATION')
    if not root:
        raise click.ClickException('Name the installation with --installation or NUMEK_INSTALLATION.')
    return Installation(root)


def _echo(value):
    click.echo(json.dumps(value, indent=2, sort_keys=True, default=str))


def _guard(fn):
    import functools

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            code = getattr(exc, 'code', None)
            if code is None:
                raise
            raise click.ClickException(f'{code}: {exc}') from exc
    return wrapper


installation_option = click.option('--installation', 'root', type=click.Path(file_okay=False), envvar='NUMEK_INSTALLATION')


@click.group('ops')
def ops():
    """Reliability operations (CG7): registration, monitoring, incidents, reports and serving."""


@ops.command('init')
@click.option('--root', required=True, type=click.Path(file_okay=False))
@click.option('--dsn-env', help='Environment variable naming the PostgreSQL DSN (default: a managed local cluster).')
@_guard
def init(root, dsn_env):
    """Create (or reopen) an installation and migrate its schema."""
    from numek_platform.installation import Installation
    installation = Installation.create(root, dsn_env=dsn_env)
    _echo({'installation': str(installation.root), 'org': str(installation.scope.org_id)})


@ops.group('user')
def user():
    """Principals and roles."""


@user.command('create')
@installation_option
@click.argument('name')
@click.option('--role', 'roles', multiple=True, required=True)
@click.option('--service', is_flag=True, help='A service principal (no password; tokens only).')
@_guard
def user_create(root, name, roles, service):
    from numek_platform import identity
    installation = _installation(root)
    password = None if service else sys.stdin.readline().rstrip('\n')
    with installation.db.transaction() as conn:
        principal = identity.create_principal(conn, installation.scope, 'service' if service else 'user', name)
        if password:
            identity.set_password(conn, installation.scope, principal, password)
        for role in roles:
            identity.bind_role(conn, installation.scope, principal, role)
    _echo({'principal': str(principal.id), 'name': name, 'roles': list(roles)})


@ops.group('token')
def token():
    """Scoped API tokens."""


@token.command('issue')
@installation_option
@click.argument('name')
@click.option('--scope', 'scopes', multiple=True, required=True, help="'role:<role>' or 'ingest:source:<id>' or 'read:deployment:<id>'")
@_guard
def token_issue(root, name, scopes):
    from numek_platform import identity
    installation = _installation(root)
    with installation.db.transaction() as conn:
        row = conn.execute('SELECT id FROM principals WHERE org_id = %s AND name = %s', (installation.scope.org_id, name)).fetchone()
        if row is None:
            raise click.ClickException('Unknown principal.')
        principal = identity.get_principal(conn, installation.scope, row['id'])
        secret, token_id = identity.issue_token(conn, installation.scope, principal, list(scopes))
    _echo({'token': secret, 'id': str(token_id), 'note': 'Shown once; stored only as a hash.'})


@ops.group('system')
def system():
    """Systems (one evidence catalog each)."""


@system.command('register')
@installation_option
@click.argument('system_id')
@click.option('--name', required=True)
@click.option('--namespace', required=True)
@_guard
def system_register(root, system_id, name, namespace):
    from . import registry
    _echo(registry.register_system(_installation(root), system_id, name, namespace=namespace))


@ops.group('deployment')
def deployment():
    """Deployments."""


@deployment.command('register')
@installation_option
@click.argument('system_id')
@click.argument('deployment_id')
@click.option('--name', required=True)
@click.option('--tier', default=2, type=click.IntRange(1, 4))
@click.option('--identity', 'identity_json', help='Registered identity as JSON.')
@_guard
def deployment_register(root, system_id, deployment_id, name, tier, identity_json):
    from . import registry
    _echo(registry.register_deployment(_installation(root), system_id, deployment_id, name, tier=tier,
                                       registered_identity=json.loads(identity_json) if identity_json else None))


@ops.group('source')
def source():
    """Source contracts."""


@source.command('register')
@installation_option
@click.argument('deployment_id')
@click.argument('source_id')
@click.option('--contract', required=True, type=click.Path(exists=True, dir_okay=False))
@_guard
def source_register(root, deployment_id, source_id, contract):
    from . import registry
    _echo(registry.register_source(_installation(root), deployment_id, source_id, json.loads(Path(contract).read_text())))


@ops.group('definition')
def definition():
    """Monitoring definitions: inspect, then confirm."""


@definition.command('inspect')
@installation_option
@click.argument('deployment_id')
@click.option('--spec', required=True, type=click.Path(exists=True, dir_okay=False))
@_guard
def definition_inspect(root, deployment_id, spec):
    from .monitoring import definitions
    _echo(definitions.inspect(_installation(root), deployment_id, json.loads(Path(spec).read_text())))


@definition.command('confirm')
@installation_option
@click.argument('deployment_id')
@click.argument('version', type=int)
@click.argument('inspection_digest')
@_guard
def definition_confirm(root, deployment_id, version, inspection_digest):
    from .monitoring import definitions
    _echo(definitions.confirm(_installation(root), deployment_id, version, inspection_digest, actor='cli'))


@ops.command('cycle')
@installation_option
@click.argument('deployment_id')
@_guard
def cycle(root, deployment_id):
    """Run one monitoring cycle and operations step now (single host)."""
    from .monitoring import runtime
    _echo(runtime.monitor_once(_installation(root), deployment_id))


@ops.command('incidents')
@installation_option
@click.option('--state')
@_guard
def incidents_list(root, state):
    """List incidents (newest first)."""
    installation = _installation(root)
    with installation.db.connect() as conn:
        rows = conn.execute('''SELECT number, deployment_id, state, priority, priority_basis->>'rule' AS rule, opened_at FROM ops_incidents
                               WHERE org_id = %s AND (%s::text IS NULL OR state = %s) ORDER BY number DESC LIMIT 200''',
                            (installation.scope.org_id, state, state)).fetchall()
    _echo([dict(r) for r in rows])


def _incident_id(installation, number):
    with installation.db.connect() as conn:
        row = conn.execute('SELECT id FROM ops_incidents WHERE org_id = %s AND number = %s', (installation.scope.org_id, number)).fetchone()
    if row is None:
        raise click.ClickException('Unknown incident.')
    return row['id']


@ops.command('incident')
@installation_option
@click.argument('number', type=int)
@click.option('--as-known', type=click.Choice(['now', 'detection']), default='now')
@_guard
def incident(root, number, as_known):
    """Show an incident as known now or at detection."""
    from .incidents import incidents
    installation = _installation(root)
    view = incidents.view(installation, _incident_id(installation, number), as_known=as_known)
    _echo({'incident': view['incident'], 'members': view['members'], 'as_known': view['as_known'],
           'hypotheses': (view['knowledge'].get('hypotheses') or {})})


@ops.command('report')
@installation_option
@click.argument('number', type=int)
@click.option('--out', required=True, type=click.Path(dir_okay=False))
@click.option('--format', 'report_format', type=click.Choice(['html', 'pdf']), default='html')
@click.option('--audience', type=click.Choice(['shareable', 'local']), default='shareable')
@click.option('--json-out', type=click.Path(dir_okay=False))
@_guard
def report(root, number, out, report_format, audience, json_out):
    """Write the incident report (HTML or PDF, optional JSON)."""
    from . import reports
    installation = _installation(root)
    _echo(reports.export(installation, _incident_id(installation, number), out, format=report_format, audience=audience, json_path=json_out))


@ops.command('preflight')
@click.option('--workload', 'workload_id', required=True, help='W-REF, W-DEV or a named smaller workload such as W-DEV-S1.')
@click.option('--scratch', required=True, type=click.Path(file_okay=False), help='Scratch directory on the disk to be measured.')
@click.option('--calibration-facts', default=1_000_000, type=click.IntRange(1000), help='Facts ingested for calibration.')
@click.option('--calibration', 'calibration_path', type=click.Path(exists=True, dir_okay=False),
              help="Reuse an earlier preflight's calibration (same feature shape) instead of measuring again.")
@click.option('--out', type=click.Path(dir_okay=False), help='Write the preflight record (JSON) here.')
@_guard
def preflight(workload_id, scratch, calibration_facts, calibration_path, out):
    """Calibrate on a scratch P-LOCAL installation, project the workload, and admit it or not (plan R2.8)."""
    from . import workloads
    if workload_id not in workloads.WORKLOADS:
        raise click.ClickException(f'Unknown workload; choose from {", ".join(workloads.WORKLOADS)}.')
    calibration = json.loads(Path(calibration_path).read_text())['calibration'] if calibration_path else None
    record = workloads.preflight(workload_id, scratch, calibration=calibration, calibration_facts=calibration_facts)
    if out:
        Path(out).write_text(json.dumps(record, indent=1, sort_keys=True, default=str) + '\n')
    _echo({k: record[k] for k in ('workload', 'decision', 'reasons', 'identity', 'projection')} | {'workload': workload_id})
    if record['decision'] != 'admitted':
        sys.exit(3)


@ops.group('backup')
def backup_group():
    """Recoverable backups of the whole installation (R2.2)."""


@backup_group.command('create')
@installation_option
@click.option('--destination', required=True, type=click.Path(file_okay=False), help='A new directory outside the installation.')
@click.option('--include-terminal-raw', is_flag=True, help='Also copy raw batches already processed (within raw retention).')
@click.password_option('--passphrase', prompt='Backup passphrase', help='Wraps the keyring (at least 12 characters).')
@_guard
def backup_create(root, destination, include_terminal_raw, passphrase):
    """Database snapshot, its objects, the installation configuration and a wrapped keyring of every secret it needs."""
    from numek_platform.backup import create_backup
    from numek_platform.installation import CONFIG
    installation = _installation(root)
    config = (installation.root / CONFIG).read_bytes()
    _echo(create_backup(installation.db, installation.store, installation.secrets, destination, passphrase=passphrase,
                        include_terminal_raw=include_terminal_raw, config_bytes=config))


@ops.group('audit')
def audit_group():
    """The hash-chained audit log and its external anchors."""


@audit_group.command('anchor')
@installation_option
@click.option('--sink', required=True, type=click.Path(dir_okay=False), help='An operator-controlled file outside the installation.')
@_guard
def audit_anchor(root, sink):
    """Append the current chain head to the sink (and record it)."""
    from numek_platform import audit
    installation = _installation(root)
    with installation.db.transaction() as conn:
        seq = audit.export_anchor(conn, installation.scope, sink)
    _echo({'anchored_seq': seq, 'sink': sink})


@audit_group.command('verify')
@installation_option
@click.option('--sink', required=True, type=click.Path(exists=True, dir_okay=False))
@_guard
def audit_verify(root, sink):
    """Recompute the chain and compare it with every anchor in the sink. Exits 1 on any mismatch."""
    from numek_platform import audit
    installation = _installation(root)
    with installation.db.connect() as conn:
        ok, bad = audit.verify_against_anchors(conn, installation.scope, sink)
    _echo({'ok': ok, 'first_bad_seq': bad})
    if not ok:
        sys.exit(1)


@ops.command('serve')
@installation_option
@click.option('--host', default='127.0.0.1')
@click.option('--port', default=8443, type=click.IntRange(1, 65535))
@click.option('--workers', default=2, type=click.IntRange(1, 64), help='gunicorn worker processes.')
@click.option('--threads', default=8, type=click.IntRange(1, 256), help='Request threads per worker.')
@click.option('--timeout', default=60, type=click.IntRange(5, 3600), help='Seconds before a silent worker is replaced.')
@click.option('--tls-cert', type=click.Path(exists=True, dir_okay=False))
@click.option('--tls-key', type=click.Path(exists=True, dir_okay=False))
@click.option('--trusted-proxy', is_flag=True, help='TLS terminates at a declared trusted reverse proxy.')
@click.option('--proxy-ips', default='127.0.0.1', help='Addresses whose X-Forwarded-* headers are trusted (with --trusted-proxy).')
@_guard
def serve(root, host, port, workers, threads, timeout, tls_cert, tls_key, trusted_proxy, proxy_ips):
    """Serve the operations API, ingestion and console under gunicorn (gthread workers)."""
    from . import api, serving
    root = str(_installation(root).root)
    tls = bool(tls_cert and tls_key)
    click.echo(f"NUMEK operations API: {'https' if tls else 'http'}://{host}:{port}{api.PREFIX} "
               f"({workers} workers x {threads} threads)", err=True)
    serving.serve(root, host, port, workers=workers, threads=threads, timeout=timeout, tls_cert=tls_cert, tls_key=tls_key,
                  trusted_proxy=trusted_proxy, proxy_ips=proxy_ips)


@ops.command('controller')
@installation_option
@_guard
def controller(root):
    """Run the leader controller with the operations tasks (cycles, escalation, notifications, retention)."""
    import signal
    import threading
    from numek_platform.evidence.gc import GarbageCollector
    from numek_platform.execution.controller import Controller
    from .scheduler import OperationsTasks
    installation = _installation(root)
    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    Controller(installation.db, gc=GarbageCollector(installation.db, installation.store),
               tasks=[OperationsTasks(installation)]).run(stop)


@ops.command('worker')
@installation_option
@click.option('--lanes', default='essential,investigation,maintenance')
@_guard
def worker(root, lanes):
    """Run a worker host for the operations job kinds."""
    import signal
    import threading
    from numek_platform.execution.host import WorkerHost
    from .jobs import REGISTRY
    installation = _installation(root)
    host = WorkerHost(installation.db, installation.store.root, registry=REGISTRY, lanes=lanes.split(','))
    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    host.run(stop)
