"""Seed a local demo installation for the operations console (synthetic scenario; for review and verification).

    python validation/cg7/console_demo.py <root>
    confidenceguard ops serve --installation <root> --port 8443

The demo uses the S6–S8 test scenario:
- a March degradation opens incidents;
- automatic investigations run;
- a rollback proposal is submitted and awaits approval.

Demo principals (viewer, operator, analyst, approver, reserve_steward, admin) get generated passwords. Those are written only to
``<root>/demo-credentials.json`` (owner-only), never printed. The installation runs its own P-LOCAL PostgreSQL
cluster; stop it with ``confidenceguard ops`` tooling or ``Installation(root).stop()``.
"""
import json
import os
import secrets
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'tests' / 'platform'))

from monitoring_support import DEFINITION, NS, T0, body, contract, generate, send, tick  # noqa: E402

DEPLOYMENT = 'scorecard-prod'
APR20 = datetime(2026, 4, 20, tzinfo=timezone.utc)


def main(root):
    from numek_platform import identity
    from numek_platform.installation import Installation
    from confidenceguard.operations import registry
    from confidenceguard.operations.intelligence import planner
    from confidenceguard.operations.interventions import proposals
    from confidenceguard.operations.monitoring import definitions, runtime
    root = Path(root).resolve()
    installation = Installation.create(root / 'installation')
    registry.register_system(installation, 'credit-default', 'Credit default (synthetic)', namespace=NS)
    registry.register_deployment(installation, 'credit-default', DEPLOYMENT, 'Scorecard (synthetic)', tier=1,
                                 registered_identity={'model_version': 'v1'})
    registry.register_source(installation, DEPLOYMENT, 'scorecard-events', contract())
    send(installation, generate(0, 31, 40, error_rate=0.1, seed=1, prefix='r') + generate(31, 28, 40, error_rate=0.1, seed=2)
         + generate(59, 21, 40, error_rate=0.4, seed=3), 'initial')
    inspection = definitions.inspect(installation, DEPLOYMENT, DEFINITION, now_tick=tick(T0 + timedelta(days=31)))
    definitions.confirm(installation, DEPLOYMENT, inspection['version'], inspection['inspection_digest'], actor='demo',
                        now_tick=tick(T0 + timedelta(days=30)))
    runtime.monitor_once(installation, DEPLOYMENT, now_tick=tick(APR20))
    with installation.db.connect() as conn:                 # the formal alarm's incident (not the feed-gap one)
        incident = conn.execute("SELECT i.id FROM ops_incidents i JOIN ops_conditions c ON c.id = i.anchor_condition "
                                "WHERE c.key LIKE 'detector:%%' ORDER BY i.number LIMIT 1").fetchone()['id']
    planner.run_auto(installation, incident, now=APR20)
    with installation.db.connect() as conn:
        completed = conn.execute("SELECT id FROM ops_investigation_runs WHERE incident_id = %s AND state = 'completed' LIMIT 1",
                                 (incident,)).fetchone()
    evidence = [{'basis': 'descriptive', 'summary': 'January baseline'}]
    if completed:
        evidence.insert(0, {'basis': 'hypothetical_replay', 'ref': str(completed['id'])})
    proposal = proposals.create(
        installation, incident, 'model_rollback', author='principal:analyst',
        title='Roll back to the January scorecard (v2 retrained on stable data)',
        change={'action': 'deploy_model', 'model_version': 'v2'}, expected_identity={'model_version': 'v2'}, evidence=evidence,
        effects=[{'metric': 'error_rate', 'expected': 0.1, 'interval': [0.08, 0.12], 'basis': 'hypothetical_replay'}],
        risks=['Retrained model not yet seen on April traffic'], prerequisites=['identity_registered'],
        verification_plan={'claims': [{'id': 'threshold', 'claim': 'R2', 'statistic': 'error', 'theta': 0.3, 'alpha': 0.05,
                                       'planned_support': 300}]})
    proposals.submit(installation, proposal['id'], actor='principal:analyst', now=APR20 + timedelta(hours=2))
    # Ingestion the Sources page can show: a batch with two contract failures (quarantined with reasons and field
    # names), a resend whose facts are already held (duplicates), and a producer watermark. Monitoring is unchanged.
    from confidenceguard.operations import ingest
    late = generate(80, 1, 6, error_rate=0.1, seed=9, prefix='q')
    late[0] = {**late[0], 'p': '1.7'}
    late[1] = {**late[1], 'y': '2'}
    ingest.receive(installation, 'scorecard-events', 'apr21-0', body(late))
    ingest.receive(installation, 'scorecard-events', 'apr21-0-resend', body(late[2:]))
    ingest.process_pending(installation)
    ingest.declare_watermark(installation, 'scorecard-events', '2026-04-21T00:00:00Z')
    credentials = {}
    with installation.db.transaction() as conn:
        for role in ('viewer', 'operator', 'analyst', 'approver', 'reserve_steward', 'admin'):
            principal = identity.create_principal(conn, installation.scope, 'user', role)
            password = secrets.token_urlsafe(18)
            identity.set_password(conn, installation.scope, principal, password)
            identity.bind_role(conn, installation.scope, principal, role)
            credentials[role] = password
    path = root / 'demo-credentials.json'
    path.write_text(json.dumps(credentials, indent=1))
    os.chmod(path, 0o600)
    print(json.dumps({'installation': str(installation.root), 'incident': str(incident), 'credentials_file': str(path)}))


if __name__ == '__main__':
    main(sys.argv[1])
