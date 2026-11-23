"""Incidents: anchor-compatible grouping, detection dossiers, knowledge revisions and lifecycle (plan H.7, G.10).

**Opening.** A condition that becomes active, decided by the versioned priority table at P1 or P2, either joins an
open incident or opens its own. A P3 or P4 condition remains a visible condition.

**Grouping is anchor-compatible and never transitive.** A condition joins an incident only when all of these hold:
- it has a *direct* link to the incident's **anchor**:
  - ``exact``: both follow the same recorded deployment event; or
  - ``population_overlap``: the Jaccard similarity of the evaluated window populations (event hashes) is ≥ 0.5;
- it is compatible: same deployment, and overlapping time.

Links to other members never count. Otherwise the condition opens its own incident, and a ``related_incident``
suggestion is recorded when any weaker relation exists. Every grouping decision is an event recording the rule,
the link and the rationale. Contradiction with a leading hypothesis is checked once hypotheses exist (S7).

**Dossiers and revisions.** The detection dossier is an immutable packet of the knowledge state at K_open:
- signals;
- window evaluations with their digests and evidence uses;
- detector plans and states;
- the reference;
- health;
- identity standings;
- deployment events.

Knowledge revisions are appended, never rewritten, so a view can show "as known at detection" or "now".

**Lifecycle.** ``open → acknowledged → investigating → response_proposed → response_executing → verifying →
resolved``, then ``reopened``.
- Operator edits use optimistic revisions.
- Outcome-supported resolutions require the matching recovery evidence on a member condition:
  - ``operational_recovery_observed`` needs R1;
  - ``threshold_recovery_established`` needs R2;
  - ``reference_noninferiority_established`` needs R3.
- ``accepted_risk`` and the other operator decisions require a reason, and are never recovery.

**Split and merge** are operator actions, audited and reversible (each is the other's inverse). A merge keeps every
condition's original standing.

**Pins.** An incident pins its conditions' windows against retention until it is resolved and 90 days have passed.
"""
import time
import uuid
from datetime import timedelta

from psycopg.types.json import Jsonb

from ...contracts import EvaluationError
from ..monitoring import packets, windows as window_math
from . import notify, priority as priority_table

OPEN_STATES = ('open', 'acknowledged', 'investigating', 'response_proposed', 'response_executing', 'verifying', 'reopened')
TRANSITIONS = {
    'open': {'acknowledged', 'investigating', 'resolved'},
    'acknowledged': {'investigating', 'resolved'},
    'investigating': {'response_proposed', 'resolved'},
    'response_proposed': {'response_executing', 'investigating', 'resolved'},
    'response_executing': {'verifying', 'investigating'},
    'verifying': {'resolved', 'investigating'},
    'resolved': {'reopened'},
    'reopened': {'acknowledged', 'investigating', 'resolved'},
    'merged': set(),
}
OUTCOME_RESOLUTIONS = {'operational_recovery_observed': 'R1', 'threshold_recovery_established': 'R2',
                       'reference_noninferiority_established': 'R3'}
OPERATOR_RESOLUTIONS = ('accepted_risk', 'operator_false_positive', 'monitoring_artifact', 'closed_without_recovery_evidence')
ACK_SLA = {'P1': timedelta(minutes=15), 'P2': timedelta(hours=1), 'P3': timedelta(hours=24), 'P4': None}
OVERLAP_THRESHOLD = 0.5
RELATED_THRESHOLD = 0.2
REOPEN_WITHIN = timedelta(days=30)
PIN_AFTER_RESOLUTION = timedelta(days=90)


# Evidence of a condition ---------------------------------------------------------------------------------------
def _definition(conn, scope, deployment_id, version):
    row = conn.execute('SELECT spec FROM ops_monitoring_definitions WHERE org_id = %s AND deployment_id = %s AND version = %s',
                       (scope.org_id, deployment_id, version)).fetchone()
    return None if row is None else row['spec']


def _span(conn, scope, condition):
    """[start, end) ticks covered by a condition: its windows, or its signal times (health)."""
    if condition['first_window'] is not None and condition['definition_version'] is not None:
        spec = _definition(conn, scope, condition['deployment_id'], condition['definition_version'])
        if spec is not None:
            start, _ = window_math.window_ticks(spec['start'], spec['window_ns'], min(condition['windows'] or [condition['first_window']]))
            _, end = window_math.window_ticks(spec['start'], spec['window_ns'], max(condition['windows'] or [condition['last_window']]))
            return start, end
    first = int(condition['first_signal_at'].timestamp() * 1e9)
    last = int(condition['last_signal_at'].timestamp() * 1e9)
    return first - 86400 * 10**9, last + 86400 * 10**9


def _population(installation, conn, condition):
    """Event hashes of the units in the condition's evaluated windows (latest close revision)."""
    if not condition['windows']:
        return set()
    rows = conn.execute("""SELECT DISTINCT ON (window_index) packet_object FROM ops_window_evaluations
                           WHERE org_id = %s AND deployment_id = %s AND definition_version = %s AND phase = 'close'
                                 AND window_index = ANY(%s) ORDER BY window_index, revision DESC""",
                        (installation.scope.org_id, condition['deployment_id'], condition['definition_version'],
                         list(condition['windows']))).fetchall()
    out = set()
    for row in rows:
        out |= {u['event'] for u in packets.read(installation, row['packet_object'])['units']}
    return out


def _events_before(conn, scope, condition, span):
    start = span[0]
    rows = conn.execute("""SELECT id FROM ops_deployment_events WHERE org_id = %s AND deployment_id = %s
                           AND at <= to_timestamp(%s / 1e9) AND at >= to_timestamp(%s / 1e9) - interval '7 days'""",
                        (scope.org_id, condition['deployment_id'], start + 7 * 86400 * 10**9, start)).fetchall()
    return {str(r['id']) for r in rows}


def link(installation, conn, anchor, condition):
    """Direct link of ``condition`` to ``anchor`` (strength, detail) or None, and whether they are compatible."""
    scope = installation.scope
    span_a, span_c = _span(conn, scope, anchor), _span(conn, scope, condition)
    compatible = anchor['deployment_id'] == condition['deployment_id'] and span_a[0] < span_c[1] and span_c[0] < span_a[1] + _hold(conn, scope, anchor)
    shared = _events_before(conn, scope, anchor, span_a) & _events_before(conn, scope, condition, span_c)
    if shared:
        return {'strength': 'exact', 'deployment_events': sorted(shared)}, compatible
    from ..intelligence import association
    found = association.structural(_dependencies(conn, scope, anchor), _dependencies(conn, scope, condition))
    if found:
        return found, compatible
    pa, pc = _population(installation, conn, anchor), _population(installation, conn, condition)
    if pa and pc:
        jaccard = len(pa & pc) / len(pa | pc)
        if jaccard >= OVERLAP_THRESHOLD:
            return {'strength': 'population_overlap', 'jaccard': jaccard}, compatible
        if jaccard >= RELATED_THRESHOLD:
            return {'strength': 'related_only', 'jaccard': jaccard}, compatible
    return None, compatible


def _dependencies(conn, scope, condition):
    from ..intelligence import association
    spec = (_definition(conn, scope, condition['deployment_id'], condition['definition_version'])
            if condition['definition_version'] else None)
    identity = conn.execute('SELECT registered_identity FROM ops_deployments WHERE org_id = %s AND id = %s',
                            (scope.org_id, condition['deployment_id'])).fetchone()['registered_identity']
    return association.dependencies(condition, spec, identity)


def impact(installation, conn, condition):
    """Impact axes for the priority table: affected volume, region exposure share and region source standing."""
    scope = installation.scope
    out = {'affected_units': 0, 'region': None, 'region_share': None, 'region_source_standing': None,
           'basis': 'units selected in the condition windows (close evaluations); excess outcomes are not estimated here'}
    if condition['windows'] and condition['definition_version']:
        rows = conn.execute("""SELECT DISTINCT ON (window_index) units, packet_object FROM ops_window_evaluations
                               WHERE org_id = %s AND deployment_id = %s AND definition_version = %s AND phase = 'close'
                                     AND window_index = ANY(%s) ORDER BY window_index, revision DESC""",
                            (scope.org_id, condition['deployment_id'], condition['definition_version'],
                             list(condition['windows']))).fetchall()
        out['affected_units'] = sum(r['units'] for r in rows)
        source, _, ident = condition['key'].partition(':')
        plan = None
        if source == 'detector':
            plan = conn.execute('SELECT plan FROM ops_detectors WHERE org_id = %s AND deployment_id = %s AND definition_version = %s '
                                'AND detector_id = %s', (scope.org_id, condition['deployment_id'], condition['definition_version'],
                                                         ident)).fetchone()
        region = plan['plan'].get('region') if plan else None
        if region:
            members = defined = 0
            for row in rows:
                share = packets.read(installation, row['packet_object']).get('region_shares', {}).get(region) or {}
                members += share.get('members', 0)
                defined += share.get('defined', 0)
            out.update(region=region, region_share=(members / defined) if defined else None,
                       region_source_standing=plan['plan'].get('region_source_standing'))
    return out


def _hold(conn, scope, condition):
    spec = _definition(conn, scope, condition['deployment_id'], condition['definition_version']) if condition['definition_version'] else None
    return 2 * int(spec['window_ns']) if spec else 2 * 86400 * 10**9


# Dossier and revisions -----------------------------------------------------------------------------------------
def _knowledge(installation, deployment_id, condition_ids, *, now):
    from ..monitoring import context, health
    scope = installation.scope
    ctx = context.deployment(installation, deployment_id)
    with installation.db.connect() as conn:
        conditions = [dict(r) for r in conn.execute('SELECT * FROM ops_conditions WHERE org_id = %s AND id = ANY(%s) ORDER BY created_at',
                                                    (scope.org_id, list(condition_ids))).fetchall()]
        signals = [dict(r) for r in conn.execute(
            '''SELECT s.id, s.source, s.source_id, s.window_index, s.standing, s.severity, s.payload, s.created_at, cs.condition_id
               FROM ops_condition_signals cs JOIN ops_signals s ON s.org_id = cs.org_id AND s.id = cs.signal_id
               WHERE cs.org_id = %s AND cs.condition_id = ANY(%s) ORDER BY s.created_at''',
            (scope.org_id, list(condition_ids))).fetchall()]
        windows = sorted({w for c in conditions for w in (c['windows'] or [])})
        evaluations = [dict(r) for r in conn.execute(
            '''SELECT id, phase, window_index, revision, catalog_sequence, packet_digest, evidence_use_id, reproducibility
               FROM ops_window_evaluations WHERE org_id = %s AND deployment_id = %s AND window_index = ANY(%s)
               ORDER BY window_index, phase, revision''', (scope.org_id, deployment_id, windows)).fetchall()] if windows else []
        detectors = [dict(r) for r in conn.execute(
            '''SELECT d.detector_id, d.kind, d.standing, d.units, d.alarms, d.late_excluded, d.cursor_window, d.definition_version,
                      d.plan->>'statistic' AS statistic, d.plan->>'m0' AS m0, d.plan->>'alpha' AS alpha
               FROM ops_detectors d JOIN ops_monitoring_definitions m ON m.org_id = d.org_id AND m.deployment_id = d.deployment_id
                    AND m.version = d.definition_version AND m.state = 'confirmed'
               WHERE d.org_id = %s AND d.deployment_id = %s ORDER BY d.detector_id''', (scope.org_id, deployment_id)).fetchall()]
        reference = conn.execute('''SELECT r.id, r.rule_digest, r.catalog_sequence, r.packet_digest FROM ops_references r
                                    JOIN ops_monitoring_definitions m ON m.reference_id = r.id AND m.state = 'confirmed'
                                    WHERE r.org_id = %s AND r.deployment_id = %s''', (scope.org_id, deployment_id)).fetchone()
        identity = [dict(r) for r in conn.execute(
            '''SELECT DISTINCT ON (standing) standing, outcome, evidence, recorded_at FROM ops_identity_standings
               WHERE org_id = %s AND deployment_id = %s ORDER BY standing, recorded_at DESC''', (scope.org_id, deployment_id)).fetchall()]
        events = [dict(r) for r in conn.execute(
            "SELECT id, kind, at, identity FROM ops_deployment_events WHERE org_id = %s AND deployment_id = %s "
            "AND at >= %s - interval '30 days' ORDER BY at", (scope.org_id, deployment_id, now)).fetchall()]
    k = ctx['workspace'].status()['catalog_sequence']
    return k, {'deployment': deployment_id, 'known_at': now.isoformat(), 'catalog_sequence': k, 'conditions': conditions,
               'signals': signals, 'window_evaluations': evaluations, 'detectors': detectors,
               'reference': None if reference is None else dict(reference), 'identity_standings': identity,
               'deployment_events': events,
               'health': health.report(installation, deployment_id, now_tick=int(now.timestamp() * 1e9))}, ctx


def _stage(installation, ctx, value, kind):
    from numek_platform.execution import jobs
    with installation.db.connect() as conn:
        lease, _row = jobs.start_inline(conn, installation.scope, kind, idempotency_key=uuid.uuid4().hex,
                                        owner=f'confidenceguard:{__import__("os").getpid()}')
    import json
    value = json.loads(json.dumps(value, default=str))           # datetimes and UUIDs as text, digest of what is stored
    ref = packets.stage(installation, lease, ctx['catalog_id'], packets.encode(value))
    return lease, ref, packets.packet_digest(value)


def _number(conn, scope):
    conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))', (f'incident-number:{scope.org_id}',))
    return conn.execute('SELECT coalesce(max(number), 0) + 1 AS n FROM ops_incidents WHERE org_id = %s', (scope.org_id,)).fetchone()['n']


def event(conn, scope, incident_id, kind, payload, actor):
    return conn.execute('INSERT INTO ops_incident_events(org_id, incident_id, kind, payload, actor) VALUES (%s, %s, %s, %s, %s) '
                        'RETURNING seq', (scope.org_id, incident_id, kind, Jsonb(payload), actor)).fetchone()['seq']


def _pin(conn, scope, catalog_id, namespace, span, incident_id, actor, reason):
    conn.execute('''INSERT INTO ops_pins(org_id, id, catalog_id, namespace, start_tick, end_tick, holder_kind, holder_id, reason,
                        created_by) VALUES (%s, %s, %s, %s, %s, %s, 'incident', %s, %s, %s)''',
                 (scope.org_id, uuid.uuid4(), catalog_id, namespace, span[0], span[1], str(incident_id), reason, actor))


def open_incident(installation, condition_id, *, now, actor='system', prio=None):
    scope = installation.scope
    with installation.db.connect() as conn:
        condition = dict(conn.execute('SELECT * FROM ops_conditions WHERE org_id = %s AND id = %s', (scope.org_id, condition_id)).fetchone())
        tier = conn.execute('SELECT tier FROM ops_deployments WHERE org_id = %s AND id = %s',
                            (scope.org_id, condition['deployment_id'])).fetchone()['tier']
        context = None if prio else impact(installation, conn, condition)
    level, basis = prio or priority_table.decide(condition, tier, context)
    k, knowledge, ctx = _knowledge(installation, condition['deployment_id'], [condition_id], now=now)
    knowledge['kind'] = 'detection_dossier'
    lease, ref, dossier_digest = _stage(installation, ctx, knowledge, 'ops_incident_dossier')
    incident_id = uuid.uuid4()
    sla = ACK_SLA[level]

    def write(conn):
        number = _number(conn, scope)
        conn.execute('''INSERT INTO ops_incidents(org_id, id, number, deployment_id, anchor_condition, state, priority, priority_basis,
                            escalation_due_at, catalog_sequence, dossier_object, dossier_digest, opened_at)
                        VALUES (%s, %s, %s, %s, %s, 'open', %s, %s, %s, %s, %s, %s, %s)''',
                     (scope.org_id, incident_id, number, condition['deployment_id'], condition_id, level, Jsonb(basis),
                      None if sla is None else now + sla, k, ref.id, dossier_digest, now))
        conn.execute("INSERT INTO ops_incident_conditions(org_id, incident_id, condition_id, rule, joined_at) VALUES (%s, %s, %s, 'anchor', %s)",
                     (scope.org_id, incident_id, condition_id, now))
        seq = event(conn, scope, incident_id, 'opened', {'anchor': str(condition_id), 'priority': level, 'priority_basis': basis,
                                                         'dossier_digest': dossier_digest, 'catalog_sequence': k}, actor)
        _pin(conn, scope, ctx['catalog_id'], ctx['namespace'], _span(conn, scope, condition), incident_id, actor, 'incident evidence')
        notify.enqueue(conn, scope, _row(conn, scope, incident_id), seq, 'opened', now=now)
        return number
    number = packets.publish(installation, lease, ctx['catalog_id'], [ref], [], write)
    return {'incident': str(incident_id), 'number': number, 'priority': level, 'basis': basis}


def _row(conn, scope, incident_id, lock=False):
    row = conn.execute('SELECT * FROM ops_incidents WHERE org_id = %s AND id = %s' + (' FOR UPDATE' if lock else ''),
                       (scope.org_id, incident_id)).fetchone()
    if row is None:
        raise EvaluationError('Unknown incident.', 'incident_unknown')
    return dict(row)


def members(conn, scope, incident_id):
    return [r['condition_id'] for r in conn.execute(
        'SELECT condition_id FROM ops_incident_conditions WHERE org_id = %s AND incident_id = %s AND removed_at IS NULL ORDER BY joined_at',
        (scope.org_id, incident_id)).fetchall()]


def append_revision(installation, incident_id, reason, *, now):
    scope = installation.scope
    with installation.db.connect() as conn:
        incident = _row(conn, scope, incident_id)
        ids = members(conn, scope, incident_id)
    k, knowledge, ctx = _knowledge(installation, incident['deployment_id'], ids, now=now)
    from ..intelligence import hypotheses
    judged = hypotheses.evaluate(installation, incident_id, knowledge_revision=incident['knowledge_revision'] + 1)
    knowledge.update(kind='knowledge_revision', reason=reason, incident=str(incident_id), hypotheses=judged['states'],
                     differential=judged['matrix'], observations=judged['observations'])
    lease, ref, packet_digest = _stage(installation, ctx, knowledge, 'ops_incident_revision')

    def write(conn):
        row = _row(conn, scope, incident_id, lock=True)
        revision = row['knowledge_revision'] + 1
        conn.execute('''INSERT INTO ops_incident_revisions(org_id, incident_id, revision, reason, catalog_sequence, packet_object,
                            packet_digest) VALUES (%s, %s, %s, %s, %s, %s, %s)''',
                     (scope.org_id, incident_id, revision, reason, k, ref.id, packet_digest))
        conn.execute('UPDATE ops_incidents SET knowledge_revision = %s WHERE org_id = %s AND id = %s', (revision, scope.org_id, incident_id))
        event(conn, scope, incident_id, 'knowledge_revision', {'revision': revision, 'reason': reason, 'catalog_sequence': k}, 'system')
        return revision
    return packets.publish(installation, lease, ctx['catalog_id'], [ref], [], write)


# Automatic handling of condition changes ------------------------------------------------------------------------
def handle(installation, deployment_id, changes, *, now, actor='system'):
    """Group or open incidents for newly active conditions; revise incidents whose members changed."""
    scope = installation.scope
    opened, joined, revised = [], [], set()
    for condition_id, change in changes:
        with installation.db.connect() as conn:
            condition = dict(conn.execute('SELECT * FROM ops_conditions WHERE org_id = %s AND id = %s', (scope.org_id, condition_id)).fetchone())
            current = conn.execute('SELECT incident_id FROM ops_incident_conditions WHERE org_id = %s AND condition_id = %s AND removed_at IS NULL',
                                   (scope.org_id, condition_id)).fetchone()
        if current is not None:
            revised.add(current['incident_id'])
            continue
        if condition['state'] != 'active':
            continue
        reopened = _reopen_for_recurrence(installation, condition, now=now, actor=actor)
        if reopened:
            revised.add(reopened)
            continue
        target, detail, related = _group(installation, condition)
        if target is not None:
            with installation.db.transaction() as conn:
                conn.execute("INSERT INTO ops_incident_conditions(org_id, incident_id, condition_id, rule, link, joined_at) VALUES "
                             "(%s, %s, %s, %s, %s, %s)", (scope.org_id, target, condition_id, detail['rule'], Jsonb(detail), now))
                event(conn, scope, target, 'condition_joined', {'condition': str(condition_id), **detail}, actor)
                ctx = _catalog(conn, scope, deployment_id)
                _pin(conn, scope, ctx['catalog_id'], ctx['namespace'], _span(conn, scope, condition), target, actor, 'incident evidence')
            joined.append(str(target))
            revised.add(target)
            continue
        with installation.db.connect() as conn:
            tier = conn.execute('SELECT tier FROM ops_deployments WHERE org_id = %s AND id = %s', (scope.org_id, deployment_id)).fetchone()['tier']
            context = impact(installation, conn, condition)
        level, basis = priority_table.decide(condition, tier, context)
        if not priority_table.at_least(level, 'P2'):
            continue                                                       # P3/P4: a visible condition, no incident
        result = open_incident(installation, condition_id, now=now, actor=actor, prio=(level, basis))
        opened.append(result['incident'])
        from ..intelligence import hypotheses
        hypotheses.evaluate(installation, result['incident'], knowledge_revision=0, actor=actor)
        if related:
            with installation.db.transaction() as conn:
                for other, reason in related:
                    conn.execute('INSERT INTO ops_related_incidents(org_id, incident_id, related_id, reason) VALUES (%s, %s, %s, %s) '
                                 'ON CONFLICT DO NOTHING', (scope.org_id, result['incident'], other, Jsonb(reason)))
                    event(conn, scope, result['incident'], 'related_incident_suggested', {'related': str(other), **reason}, actor)
    for incident_id in revised:
        append_revision(installation, incident_id, 'member conditions changed', now=now)
    return {'opened': opened, 'joined': joined, 'revised': [str(i) for i in revised]}


def _catalog(conn, scope, deployment_id):
    row = conn.execute('SELECT s.catalog_id, s.namespace FROM ops_deployments d JOIN ops_systems s ON s.org_id = d.org_id AND s.id = d.system_id '
                       'WHERE d.org_id = %s AND d.id = %s', (scope.org_id, deployment_id)).fetchone()
    return dict(row)


def _group(installation, condition):
    """(incident, decision, related suggestions): anchor-compatible join or None."""
    scope = installation.scope
    related = []
    with installation.db.connect() as conn:
        candidates = conn.execute(f'''SELECT i.id, i.anchor_condition FROM ops_incidents i WHERE i.org_id = %s AND i.deployment_id = %s
                                      AND i.state IN {OPEN_STATES} ORDER BY i.opened_at''',
                                  (scope.org_id, condition['deployment_id'])).fetchall()
        for candidate in candidates:
            anchor = dict(conn.execute('SELECT * FROM ops_conditions WHERE org_id = %s AND id = %s',
                                       (scope.org_id, candidate['anchor_condition'])).fetchone())
            found, compatible = link(installation, conn, anchor, condition)
            if found and found['strength'] in ('exact', 'structural', 'population_overlap') and compatible:
                rule = {'exact': 'direct_link', 'structural': 'structural_link', 'population_overlap': 'population_overlap'}[found['strength']]
                return candidate['id'], {'rule': rule, 'anchor': str(anchor['id']), 'link': found,
                                         'rationale': f"{found['strength']} link to the anchor and compatible in deployment and time"}, []
            if found or compatible:
                related.append((candidate['id'], {'link': found, 'time_compatible': compatible,
                                                  'note': 'suggestion only; never merged automatically'}))
    return None, None, related


def _reopen_for_recurrence(installation, condition, *, now, actor):
    """A recurring condition (same key) of a recently resolved incident reopens that incident."""
    scope = installation.scope
    with installation.db.transaction() as conn:
        row = conn.execute('''SELECT i.id FROM ops_incidents i JOIN ops_incident_conditions ic ON ic.org_id = i.org_id AND ic.incident_id = i.id
                              JOIN ops_conditions c ON c.org_id = ic.org_id AND c.id = ic.condition_id
                              WHERE i.org_id = %s AND i.deployment_id = %s AND i.state = 'resolved' AND c.key = %s AND c.id <> %s
                                    AND i.resolved_at >= %s ORDER BY i.resolved_at DESC LIMIT 1 FOR UPDATE OF i''',
                           (scope.org_id, condition['deployment_id'], condition['key'], condition['id'], now - REOPEN_WITHIN)).fetchone()
        if row is None:
            return None
        incident = _row(conn, scope, row['id'], lock=True)
        conn.execute("UPDATE ops_incidents SET state = 'reopened', resolution = NULL, resolved_at = NULL, revision = revision + 1, "
                     'escalation_due_at = %s WHERE org_id = %s AND id = %s',
                     (None if ACK_SLA[incident['priority']] is None else now + ACK_SLA[incident['priority']], scope.org_id, row['id']))
        conn.execute("INSERT INTO ops_incident_conditions(org_id, incident_id, condition_id, rule, link, joined_at) VALUES (%s, %s, %s, 'recurrence', %s, %s)",
                     (scope.org_id, row['id'], condition['id'], Jsonb({'key': condition['key']}), now))
        conn.execute("UPDATE ops_pins SET expires_at = NULL WHERE org_id = %s AND holder_kind = 'incident' AND holder_id = %s AND released_at IS NULL",
                     (scope.org_id, str(row['id'])))
        seq = event(conn, scope, row['id'], 'reopened', {'condition': str(condition['id']), 'previous_resolution': incident['resolution']}, actor)
        notify.enqueue(conn, scope, _row(conn, scope, row['id']), seq, 'reopened', now=now)
    return row['id']


# Operator actions ------------------------------------------------------------------------------------------------
def _check_revision(row, expected):
    if expected is not None and row['revision'] != expected:
        raise EvaluationError('The incident changed since it was read; reload it.', 'stale_revision')


def transition(installation, incident_id, to_state, *, actor, expected_revision=None, resolution=None, reason=None, now=None):
    from .. import audit_action
    now = now or _now()
    scope = installation.scope
    with installation.db.transaction() as conn:
        row = _row(conn, scope, incident_id, lock=True)
        _check_revision(row, expected_revision)
        if to_state not in TRANSITIONS[row['state']]:
            raise EvaluationError(f"An incident cannot move from {row['state']} to {to_state}.", 'incident_transition')
        detail = None
        if to_state == 'resolved':
            detail = _resolution_evidence(conn, scope, incident_id, resolution, reason)
        conn.execute('''UPDATE ops_incidents SET state = %s, revision = revision + 1,
                            acknowledged_at = CASE WHEN %s = 'acknowledged' THEN %s ELSE acknowledged_at END,
                            escalation_due_at = CASE WHEN %s IN ('acknowledged', 'investigating', 'resolved') THEN NULL ELSE escalation_due_at END,
                            resolution = %s, resolution_detail = %s, resolved_at = CASE WHEN %s = 'resolved' THEN %s ELSE NULL END
                        WHERE org_id = %s AND id = %s''',
                     (to_state, to_state, now, to_state, resolution if to_state == 'resolved' else None,
                      Jsonb(detail) if detail else None, to_state, now, scope.org_id, incident_id))
        if to_state == 'resolved':
            conn.execute("UPDATE ops_pins SET expires_at = %s WHERE org_id = %s AND holder_kind = 'incident' AND holder_id = %s AND released_at IS NULL",
                         (now + PIN_AFTER_RESOLUTION, scope.org_id, str(incident_id)))
        seq = event(conn, scope, incident_id, 'state_changed', {'from': row['state'], 'to': to_state, 'resolution': resolution,
                                                                 'reason': reason, 'evidence': detail}, actor)
        audit_action(conn, scope, actor, 'incident.transition', str(incident_id), {'from': row['state'], 'to': to_state,
                                                                                    'resolution': resolution})
        notify.enqueue(conn, scope, _row(conn, scope, incident_id), seq, 'resolved' if to_state == 'resolved' else 'state_changed', now=now)
    return {'incident': str(incident_id), 'state': to_state, 'resolution': resolution}


def _resolution_evidence(conn, scope, incident_id, resolution, reason):
    if resolution in OUTCOME_RESOLUTIONS:
        claim = OUTCOME_RESOLUTIONS[resolution]
        rows = conn.execute('''SELECT c.id, c.recovery FROM ops_incident_conditions ic JOIN ops_conditions c ON c.org_id = ic.org_id AND c.id = ic.condition_id
                               WHERE ic.org_id = %s AND ic.incident_id = %s AND ic.removed_at IS NULL AND c.state = 'recovered'
                                     AND c.recovery->>'claim' = %s''', (scope.org_id, incident_id, claim)).fetchall()
        if not rows:
            raise EvaluationError(f'{resolution} requires a member condition recovered with {claim} evidence.', 'recovery_evidence_required')
        return {'claim': claim, 'conditions': [str(r['id']) for r in rows], 'recovery': [r['recovery'] for r in rows]}
    if resolution in OPERATOR_RESOLUTIONS:
        if not reason:
            raise EvaluationError('An operator resolution requires a reason.', 'resolution_reason_required')
        return {'operator_decision': resolution, 'reason': reason, 'recovery': resolution == 'accepted_risk' and 'not recovery'}
    raise EvaluationError('Unknown resolution.', 'invalid_resolution')


def assign(installation, incident_id, owner, *, actor, expected_revision=None):
    from .. import audit_action
    scope = installation.scope
    with installation.db.transaction() as conn:
        row = _row(conn, scope, incident_id, lock=True)
        _check_revision(row, expected_revision)
        conn.execute('UPDATE ops_incidents SET owner = %s, revision = revision + 1 WHERE org_id = %s AND id = %s', (owner, scope.org_id, incident_id))
        event(conn, scope, incident_id, 'owner_changed', {'from': row['owner'], 'to': owner}, actor)
        audit_action(conn, scope, actor, 'incident.assign', str(incident_id), {'owner': owner})


def set_priority(installation, incident_id, level, *, reason, actor, expected_revision=None, now=None):
    from .. import audit_action
    now = now or _now()
    if level not in priority_table.RANK or not reason:
        raise EvaluationError('A priority override names P1-P4 and a reason.', 'invalid_priority')
    scope = installation.scope
    with installation.db.transaction() as conn:
        row = _row(conn, scope, incident_id, lock=True)
        _check_revision(row, expected_revision)
        basis = {**row['priority_basis'], 'override': {'from': row['priority'], 'to': level, 'reason': reason, 'by': actor}}
        conn.execute('UPDATE ops_incidents SET priority = %s, priority_basis = %s, revision = revision + 1 WHERE org_id = %s AND id = %s',
                     (level, Jsonb(basis), scope.org_id, incident_id))
        seq = event(conn, scope, incident_id, 'priority_changed', {'from': row['priority'], 'to': level, 'reason': reason}, actor)
        audit_action(conn, scope, actor, 'incident.priority', str(incident_id), {'from': row['priority'], 'to': level, 'reason': reason})
        notify.enqueue(conn, scope, _row(conn, scope, incident_id), seq, 'priority_changed', now=now)


def merge(installation, target_id, source_id, *, reason, actor):
    """Move every current condition of ``source`` into ``target`` (operator_merge); ``source`` becomes merged."""
    from .. import audit_action
    scope = installation.scope
    if not reason:
        raise EvaluationError('A merge requires a reason.', 'invalid_merge')
    with installation.db.transaction() as conn:
        first, second = sorted([target_id, source_id], key=str)
        _row(conn, scope, first, lock=True), _row(conn, scope, second, lock=True)
        target, source = _row(conn, scope, target_id), _row(conn, scope, source_id)
        if target['deployment_id'] != source['deployment_id'] or source['state'] not in OPEN_STATES or target['state'] not in OPEN_STATES:
            raise EvaluationError('Only open incidents of one deployment can be merged.', 'invalid_merge')
        moved = members(conn, scope, source_id)
        conn.execute('UPDATE ops_incident_conditions SET removed_at = clock_timestamp() WHERE org_id = %s AND incident_id = %s AND removed_at IS NULL',
                     (scope.org_id, source_id))
        for condition_id in moved:
            conn.execute("INSERT INTO ops_incident_conditions(org_id, incident_id, condition_id, rule, link) VALUES (%s, %s, %s, 'operator_merge', %s)",
                         (scope.org_id, target_id, condition_id, Jsonb({'from': str(source_id), 'reason': reason})))
        conn.execute("UPDATE ops_incidents SET state = 'merged', merged_into = %s, revision = revision + 1, escalation_due_at = NULL "
                     'WHERE org_id = %s AND id = %s', (target_id, scope.org_id, source_id))
        conn.execute("UPDATE ops_pins SET holder_id = %s WHERE org_id = %s AND holder_kind = 'incident' AND holder_id = %s",
                     (str(target_id), scope.org_id, str(source_id)))
        event(conn, scope, target_id, 'merged_in', {'source': str(source_id), 'conditions': [str(c) for c in moved], 'reason': reason}, actor)
        event(conn, scope, source_id, 'merged_into', {'target': str(target_id), 'reason': reason,
                                                     'inverse': 'split the listed conditions out of the target'}, actor)
        audit_action(conn, scope, actor, 'incident.merge', str(target_id), {'source': str(source_id), 'reason': reason})
    return {'target': str(target_id), 'moved': [str(c) for c in moved]}


def split(installation, incident_id, condition_ids, *, reason, actor, now=None):
    """Move conditions (never the anchor) into a new incident anchored on the first of them."""
    from .. import audit_action
    now = now or _now()
    scope = installation.scope
    if not reason or not condition_ids:
        raise EvaluationError('A split names conditions and a reason.', 'invalid_split')
    with installation.db.connect() as conn:
        row = _row(conn, scope, incident_id)
        current = {str(c) for c in members(conn, scope, incident_id)}
    wanted = [str(c) for c in condition_ids]
    if str(row['anchor_condition']) in wanted or not set(wanted) <= current:
        raise EvaluationError('Split only current non-anchor conditions.', 'invalid_split')
    with installation.db.transaction() as conn:
        conn.execute('UPDATE ops_incident_conditions SET removed_at = clock_timestamp() WHERE org_id = %s AND incident_id = %s '
                     'AND condition_id = ANY(%s) AND removed_at IS NULL', (scope.org_id, incident_id, [uuid.UUID(c) for c in wanted]))
        event(conn, scope, incident_id, 'split_out', {'conditions': wanted, 'reason': reason}, actor)
        audit_action(conn, scope, actor, 'incident.split', str(incident_id), {'conditions': wanted, 'reason': reason})
    created = open_incident(installation, uuid.UUID(wanted[0]), now=now, actor=actor)
    with installation.db.transaction() as conn:
        conn.execute("UPDATE ops_incident_conditions SET rule = 'operator_split' WHERE org_id = %s AND incident_id = %s",
                     (scope.org_id, created['incident']))
        for condition_id in wanted[1:]:
            conn.execute("INSERT INTO ops_incident_conditions(org_id, incident_id, condition_id, rule, link) VALUES (%s, %s, %s, 'operator_split', %s)",
                         (scope.org_id, created['incident'], uuid.UUID(condition_id), Jsonb({'from': str(incident_id), 'reason': reason})))
        event(conn, scope, created['incident'], 'split_from', {'source': str(incident_id), 'conditions': wanted, 'reason': reason,
                                                               'inverse': 'merge this incident back into the source'}, actor)
    return created


def escalate_due(installation, *, now):
    """Escalation timers: an unacknowledged incident past its acknowledgement SLA escalates (notified per level)."""
    scope = installation.scope
    out = []
    with installation.db.transaction() as conn:
        rows = conn.execute("SELECT * FROM ops_incidents WHERE org_id = %s AND state IN ('open', 'reopened') AND escalation_due_at <= %s "
                            'ORDER BY escalation_due_at FOR UPDATE SKIP LOCKED', (scope.org_id, now)).fetchall()
        for row in rows:
            level = row['escalation_level'] + 1
            sla = ACK_SLA[row['priority']]
            conn.execute('UPDATE ops_incidents SET escalation_level = %s, escalation_due_at = %s WHERE org_id = %s AND id = %s',
                         (level, None if sla is None else now + sla, scope.org_id, row['id']))
            seq = event(conn, scope, row['id'], 'escalated', {'level': level, 'priority': row['priority'],
                                                              'reason': 'not acknowledged within the SLA'}, 'system')
            notify.enqueue(conn, scope, _row(conn, scope, row['id']), seq, 'escalated', now=now)
            out.append({'incident': str(row['id']), 'level': level})
    return out


def view(installation, incident_id, *, as_known='now'):
    """The incident with its dossier ("as known at detection") or its latest knowledge revision ("now")."""
    scope = installation.scope
    with installation.db.connect() as conn:
        row = _row(conn, scope, incident_id)
        latest = conn.execute('SELECT packet_object, packet_digest, revision FROM ops_incident_revisions WHERE org_id = %s AND incident_id = %s '
                              'ORDER BY revision DESC LIMIT 1', (scope.org_id, incident_id)).fetchone()
        events = [dict(r) for r in conn.execute('SELECT seq, kind, payload, actor, at FROM ops_incident_events WHERE org_id = %s '
                                                'AND incident_id = %s ORDER BY seq', (scope.org_id, incident_id)).fetchall()]
        current = [str(c) for c in members(conn, scope, incident_id)]
    if as_known == 'detection' or latest is None:
        knowledge, expected = packets.read(installation, row['dossier_object']), row['dossier_digest']
    else:
        knowledge, expected = packets.read(installation, latest['packet_object']), latest['packet_digest']
    if packets.packet_digest(knowledge) != expected:
        raise EvaluationError('Incident knowledge differs from its record.', 'evidence_changed')
    return {'incident': row, 'members': current, 'events': events, 'knowledge': knowledge,
            'as_known': 'detection' if as_known == 'detection' or latest is None else f"revision {latest['revision']}"}


def _now():
    from datetime import datetime, timezone
    return datetime.fromtimestamp(time.time(), tz=timezone.utc)

