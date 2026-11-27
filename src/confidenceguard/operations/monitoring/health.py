"""Monitoring-system health and the coverage map (plan G.2 "Monitoring health", standing D).

Health reports:
- freshness per source;
- volume;
- quarantine and failed batches;
- known producer loss;
- processing backlog;
- failed operations jobs;
- untimed opportunities, which belong to no window;
- window closure and maturity backlog;
- detector status: standing, power, cursor lag, late exclusions.

The coverage map states, per monitoring dimension, whether a formal detector with adequate power
covers it, or whether it is covered only descriptively, underpowered, not configured, or stale.
**Absence of conditions is never shown as health.**
"""
import time
from datetime import datetime, timezone

from ...history_contracts import instant
from . import definitions, windows

DEFAULT_MAX_SILENCE_NS = 6 * 3600 * 10**9
DIMENSIONS = {
    'integrity': {'missing_field'},
    'behavior': {'abstention', 'failure'},
    'matured_performance': {'error', 'high_confidence_error'},
    'calibration_and_uncertainty': {'brier'},
}
DESCRIPTIVE_ONLY = {'longitudinal': 'drift against the frozen reference (CG3 distances)',
                    'execution_and_identity': 'identity standings (S4)'}
# Not monitored in CG7 (disclosed in the closure report): the G.2 policy dimension (supplied actions against a
# frozen CG5 replay and its constraint ledger).
NOT_YET = {'policy': 'policy monitoring (supplied actions against a frozen CG5 replay) is not implemented in CG7'}


def report(installation, deployment_id, *, now_tick=None):
    from . import context
    now_tick = time.time_ns() if now_tick is None else int(now_tick)
    now = datetime.fromtimestamp(now_tick / 1e9, tz=timezone.utc)
    scope = installation.scope
    ctx = context.deployment(installation, deployment_id)
    current = definitions.confirmed(installation, deployment_id)
    definition = current['spec'] if current else {}
    max_silence = int((definition.get('health') or {}).get('max_silence_ns', DEFAULT_MAX_SILENCE_NS))
    out = {'deployment': deployment_id, 'at': now.isoformat(), 'sources': [], 'conditions': [],
           'statement': 'Absence of conditions is not evidence of health; read coverage, freshness, maturity backlog '
                        'and detector power alongside.'}
    with installation.db.connect() as conn:
        for source in ctx['sources']:
            row = conn.execute(
                '''SELECT max(received_at) AS last, count(*) FILTER (WHERE received_at > %s - interval '1 day') AS batches_day,
                          count(*) FILTER (WHERE state = 'failed') AS failed,
                          count(*) FILTER (WHERE state IN ('received', 'processing') AND received_at < %s - interval '15 minutes')
                              AS backlog,
                          coalesce(sum(producer_dropped), 0) AS dropped,
                          coalesce(sum((counts->>'rows_received')::bigint), 0) AS rows_received,
                          coalesce(sum((counts->>'rows_quarantined')::bigint), 0) AS rows_quarantined
                   FROM ops_batches WHERE org_id = %s AND source_id = %s''',
                (now, now, scope.org_id, source)).fetchone()
            last = row['last']
            silence = None if last is None else int((now - last).total_seconds() * 1e9)
            item = {'source': source, 'last_received': None if last is None else last.isoformat(), 'silence_ns': silence,
                    'batches_last_day': row['batches_day'], 'failed_batches': row['failed'], 'backlog_batches': row['backlog'],
                    'producer_dropped_rows': int(row['dropped']), 'rows_received': int(row['rows_received']),
                    'quarantine_rate': (int(row['rows_quarantined']) / int(row['rows_received'])) if row['rows_received'] else None}
            out['sources'].append(item)
            if silence is None or silence > max_silence:
                out['conditions'].append({'kind': 'source_silent', 'source': source, 'severity': 'high',
                                          'detail': f'not monitored since {item["last_received"] or "registration"}'})
            if row['failed']:
                out['conditions'].append({'kind': 'batches_failed', 'source': source, 'severity': 'high', 'count': row['failed']})
            if row['backlog']:
                out['conditions'].append({'kind': 'processing_backlog', 'source': source, 'severity': 'medium',
                                          'count': row['backlog']})
            if row['dropped']:
                out['conditions'].append({'kind': 'producer_known_loss', 'source': source, 'severity': 'medium',
                                          'rows': int(row['dropped'])})
        failed_jobs = conn.execute(
            "SELECT count(*) AS n FROM jobs WHERE org_id = %s AND kind LIKE 'ops_%%' AND state IN ('failed', 'dead') "
            "AND finished_at > %s - interval '1 day'", (scope.org_id, now)).fetchone()['n']
        out['failed_jobs_last_day'] = failed_jobs
        if failed_jobs:
            out['conditions'].append({'kind': 'jobs_failed', 'severity': 'high', 'count': failed_jobs})
        out['untimed_opportunities'] = conn.execute(
            "SELECT count(DISTINCT key) AS n FROM fact_index WHERE catalog_id = %s AND namespace = %s AND kind = 'opportunity' "
            "AND event_tick IS NULL", (ctx['catalog_id'], ctx['namespace'])).fetchone()['n']
        if not current:
            out['coverage'] = {d: {'status': 'not_configured'} for d in [*DIMENSIONS, 'regions', *DESCRIPTIVE_ONLY, *NOT_YET]}
            out['conditions'].append({'kind': 'not_monitored', 'severity': 'high', 'detail': 'no confirmed definition'})
            return out
        version = current['version']
        phases = {r['phase']: r['m'] for r in conn.execute(
            'SELECT phase, max(window_index) AS m FROM ops_window_evaluations WHERE org_id = %s AND deployment_id = %s '
            'AND definition_version = %s GROUP BY phase', (scope.org_id, deployment_id, version)).fetchall()}
        detectors = [dict(r) for r in conn.execute(
            'SELECT detector_id, kind, phase, standing, plan, units, alarms, late_excluded, cursor_window FROM ops_detectors '
            'WHERE org_id = %s AND deployment_id = %s AND definition_version = %s ORDER BY detector_id',
            (scope.org_id, deployment_id, version)).fetchall()]
    start = instant(definition['start'])
    length = int(definition['window_ns'])
    lateness = int(definition['allowed_lateness_ns'])
    horizon = definitions.maturity_ns(definition)
    expected_close = (now_tick - lateness - start) // length - 1
    expected_maturity = (now_tick - lateness - horizon - start) // length - 1
    last_close, last_maturity = phases.get('close'), phases.get('maturity')
    out['windows'] = {'version': version, 'last_closed': last_close, 'last_matured': last_maturity,
                      'expected_closed': expected_close, 'expected_matured': expected_maturity,
                      'maturity_backlog_windows': max(0, (last_close if last_close is not None else -1)
                                                      - (last_maturity if last_maturity is not None else -1)),
                      'next_maturity': windows.iso(start + ((last_maturity if last_maturity is not None else -1) + 2) * length
                                                   + horizon + lateness)}
    stale = expected_close >= 0 and (last_close is None or expected_close - last_close >= 2)
    if stale:
        out['conditions'].append({'kind': 'monitoring_stale', 'severity': 'high',
                                  'detail': f'windows evaluated through {last_close}, expected {expected_close}'})
    out['detectors'] = []
    for det in detectors:
        plan = det['plan']
        expected = expected_close if det['phase'] == 'close' else expected_maturity
        lag = None if det['cursor_window'] is None else max(0, expected - det['cursor_window'])
        out['detectors'].append({'id': det['detector_id'], 'kind': det['kind'], 'statistic': plan['statistic'],
                                 'standing': det['standing'], 'power': plan.get('power'), 'units': det['units'],
                                 'alarms': det['alarms'], 'late_excluded': det['late_excluded'], 'cursor': det['cursor_window'],
                                 'lag_windows': lag, 'reasons': plan.get('reasons', [])})
    out['coverage'] = coverage(definition, detectors, stale)
    return out


def _region_detectors(detectors):
    return [d for d in detectors if d['kind'] == 'sm1'
            and (d['plan']['statistic'] == 'region_membership' or d['plan'].get('region') is not None)]


def coverage(definition, detectors, stale):
    out = {}
    groups = {dimension: [d for d in detectors if d['kind'] == 'sm1' and d['plan']['statistic'] in statistics]
              for dimension, statistics in DIMENSIONS.items()}
    groups['regions'] = _region_detectors(detectors)       # frozen CG4 regions: exposure and in-region detectors (S7)
    for dimension, relevant in groups.items():
        if stale and relevant:
            status = 'stale'
        elif any(d['standing'] == 'formal' for d in relevant):
            status = 'formal'
        elif any(d['standing'] == 'insufficient_power' for d in relevant):
            status = 'insufficient_power'
        elif relevant:
            status = 'descriptive'
        elif dimension == 'regions':
            status = 'not_configured'
        else:
            status = 'descriptive_measures_only' if dimension != 'integrity' or definition.get('rules') else 'not_configured'
        out[dimension] = {'status': status, 'detectors': [d['detector_id'] for d in relevant]}
    for dimension, note in DESCRIPTIVE_ONLY.items():
        out[dimension] = {'status': 'stale' if stale else 'descriptive_measures_only', 'note': note}
    for dimension, note in NOT_YET.items():
        out[dimension] = {'status': 'not_configured', 'note': note}
    return out


def record(installation, deployment_id, *, now_tick=None):
    """Compute health and record its conditions as D signals (one per kind, source and day)."""
    import uuid
    from psycopg.types.json import Jsonb
    result = report(installation, deployment_id, now_tick=now_tick)
    current = definitions.confirmed(installation, deployment_id)
    if current is None:
        return result
    day = result['at'][:10]
    with installation.db.transaction() as conn:
        for condition in result['conditions']:
            key = f"{deployment_id}:{current['version']}:health:{condition['kind']}:{condition.get('source', '')}:{day}"
            conn.execute('''INSERT INTO ops_signals(org_id, id, deployment_id, definition_version, source, source_id, standing,
                                severity, payload, dedupe_key)
                            VALUES (%s, %s, %s, %s, 'health', %s, 'D', %s, %s, %s) ON CONFLICT (org_id, dedupe_key) DO NOTHING''',
                         (installation.scope.org_id, uuid.uuid4(), deployment_id, current['version'], condition['kind'],
                          condition['severity'], Jsonb(condition), key))
    return result

