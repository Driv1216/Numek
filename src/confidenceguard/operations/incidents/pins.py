"""Retention pins and observation retention (plan H.8).

**What a pin protects.** A pin protects observation facts whose opportunity event tick lies in ``[start, end)``.
- **Incident pins** cover the incident's evidence windows. They stay live while the incident is open, and until
  90 days after it is resolved.
- **Analyst pins** carry an expiry.
- Reserve-study and proposal pins use the same table. Studies pin explicitly here; proposals arrive in S8.

**What retention does.** Retention tombstones observation facts older than the system's ``observation_days``
(default 400): an opportunity is purged with its whole revision chain, its predictions, context and samples,
and its outcomes. It does this through the platform purge, at a new K and tombstone epoch.
- It skips every fact in a live pin, and reports how many it skipped.
- Window evaluations whose windows lost facts become ``summary_only``. Their packets keep aggregates and
  population digests, and they are labelled not recomputable.
- Untimed opportunities belong to no window, and retention by time leaves them alone.
"""
import uuid
from datetime import timedelta

from ...contracts import EvaluationError

DEFAULT_OBSERVATION_DAYS = 400
MAX_PURGE_PER_SWEEP = 20000


def pin(installation, system_id, start, end, *, reason, actor, expires_at, holder_kind='analyst', holder_id=None):
    from .. import audit_action, registry
    from ...history_contracts import instant
    if holder_kind == 'analyst' and expires_at is None:
        raise EvaluationError('Analyst pins carry an expiry.', 'invalid_pin')
    system = registry.system(installation, system_id)
    scope = installation.scope
    pin_id = uuid.uuid4()
    with installation.db.transaction() as conn:
        conn.execute('''INSERT INTO ops_pins(org_id, id, catalog_id, namespace, start_tick, end_tick, holder_kind, holder_id, reason,
                            expires_at, created_by) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)''',
                     (scope.org_id, pin_id, system['catalog_id'], system['namespace'], instant(start), instant(end), holder_kind,
                      holder_id or actor, reason, expires_at, actor))
        audit_action(conn, scope, actor, 'retention.pin', str(pin_id), {'system': system_id, 'start': start, 'end': end, 'reason': reason})
    return str(pin_id)


def live_pins(conn, scope, catalog_id, now):
    return [(int(r['start_tick']), int(r['end_tick'])) for r in conn.execute(
        '''SELECT start_tick, end_tick FROM ops_pins WHERE org_id = %s AND catalog_id = %s AND released_at IS NULL
           AND (expires_at IS NULL OR expires_at > %s)''', (scope.org_id, catalog_id, now)).fetchall()]


def set_policy(installation, system_id, observation_days):
    scope = installation.scope
    with installation.db.transaction() as conn:
        conn.execute('''INSERT INTO ops_retention_policies(org_id, system_id, observation_days) VALUES (%s, %s, %s)
                        ON CONFLICT (org_id, system_id) DO UPDATE SET observation_days = EXCLUDED.observation_days, updated_at = clock_timestamp()''',
                     (scope.org_id, system_id, observation_days))


def observation_sweep(installation, *, now):
    """Purge observation facts past retention outside live pins; mark affected window evaluations summary_only."""
    from numek_platform.evidence.maintenance import purge_facts
    from numek_platform.execution import jobs
    scope = installation.scope
    reports = []
    with installation.db.connect() as conn:
        systems = conn.execute('''SELECT s.id, s.catalog_id, s.namespace, coalesce(p.observation_days, %s) AS days FROM ops_systems s
                                  LEFT JOIN ops_retention_policies p ON p.org_id = s.org_id AND p.system_id = s.id
                                  WHERE s.org_id = %s ORDER BY s.id''', (DEFAULT_OBSERVATION_DAYS, scope.org_id)).fetchall()
    for system in systems:
        horizon = int((now - timedelta(days=system['days'])).timestamp() * 1e9)
        with installation.db.connect() as conn:
            pins = live_pins(conn, scope, system['catalog_id'], now)
            # Opportunities every revision of which is before the horizon (a correction into retention keeps the chain).
            rows = conn.execute('''SELECT key, max(event_tick) AS tick, min(event_tick) AS first FROM fact_index
                                   WHERE catalog_id = %s AND kind = 'opportunity' AND event_tick IS NOT NULL
                                   AND NOT EXISTS (SELECT 1 FROM fact_tombstones t WHERE t.catalog_id = fact_index.catalog_id
                                                   AND t.kind = 'opportunity' AND t.key = fact_index.key AND t.revision = fact_index.revision)
                                   GROUP BY key HAVING max(event_tick) < %s ORDER BY key LIMIT %s''',
                                (system['catalog_id'], horizon, MAX_PURGE_PER_SWEEP)).fetchall()
            pinned = [r for r in rows if any(a <= int(r['first']) < b or a <= int(r['tick']) < b for a, b in pins)]
            purge = [r for r in rows if r not in pinned]
            keys = [bytes(r['key']) for r in purge]
            identities, ticks = [], [int(r['tick']) for r in purge] + [int(r['first']) for r in purge]
            if keys:
                facts = conn.execute('''SELECT f.kind, f.key, f.revision FROM fact_index f
                                        WHERE f.catalog_id = %s AND (f.key = ANY(%s) OR f.opportunity_key = ANY(%s)
                                              OR (f.kind = 'outcome' AND f.target_key IN (SELECT target_key FROM fact_index o
                                                  WHERE o.catalog_id = %s AND o.kind = 'opportunity' AND o.key = ANY(%s))))''',
                                     (system['catalog_id'], keys, keys, system['catalog_id'], keys)).fetchall()
                identities = sorted({(r['kind'], bytes(r['key']).hex(), r['revision']) for r in facts})
        report = {'system': system['id'], 'horizon_days': system['days'], 'opportunities_purged': len(purge),
                  'facts_purged': 0, 'pinned_opportunities_skipped': len(pinned), 'windows_summary_only': 0}
        if identities:
            with installation.db.connect() as conn:
                lease, _row = jobs.start_inline(conn, scope, 'ops_observation_retention', idempotency_key=uuid.uuid4().hex,
                                                owner='confidenceguard:retention')
            receipt = purge_facts(installation.db, scope, lease, system['catalog_id'], identities,
                                  request_id=f'retention:{system["id"]}:{uuid.uuid4().hex}',
                                  reason=f'observation retention ({system["days"]} days)')
            with installation.db.transaction() as conn:
                jobs.complete(conn, lease, receipt)
                candidates = conn.execute(
                    '''SELECT e.id, e.start_tick, e.end_tick FROM ops_window_evaluations e
                       JOIN ops_deployments d ON d.org_id = e.org_id AND d.id = e.deployment_id
                       WHERE d.system_id = %s AND e.org_id = %s AND e.start_tick <= %s AND e.end_tick > %s
                             AND e.reproducibility = 'reproducible' ''',
                    (system['id'], scope.org_id, max(ticks), min(ticks))).fetchall()
                hit = [c['id'] for c in candidates if any(int(c['start_tick']) <= t < int(c['end_tick']) for t in ticks)]
                if hit:
                    conn.execute("UPDATE ops_window_evaluations SET reproducibility = 'summary_only' WHERE org_id = %s AND id = ANY(%s)",
                                 (scope.org_id, hit))
                report['windows_summary_only'] = len(hit)
            report.update(facts_purged=receipt['purged'], catalog_sequence=receipt['sequence'])
        reports.append(report)
    return reports
