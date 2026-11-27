"""Conditions: persistent states built from monitoring signals (plan H.7).

**Lifecycle.**
- ``emerging → active``: by persistence (signals in k = 2 of the last n = 3 windows), a formal (F) alarm, or a
  high or critical deterministic (D) violation.
- ``emerging → lapsed``: no repeat within n windows.
- ``active → quiescent``: no signals for the hold period (2 windows).
- ``quiescent → active``: the condition recurs.
- ``quiescent → recovered``, by the declared criteria only:
  - **R1** (operational, outcome-free) for deterministic and descriptive health or rule conditions, after a further
    hold period with no signal;
  - **R2 / R3** (outcome-supported) when an SM2 recovery test bound to the condition establishes its claim.
- ``* → suppressed → (prior state)``: an operator suppresses with a reason and an expiry.

**An absent alarm is never recovery.** A detector condition that goes quiet stays quiescent until an SM2 claim
establishes recovery.

Windows are counted in monitoring windows: the latest closed window of the deployment's definition. Conditions
with no window (health) count days.

Every transition is an append-only event in the same transaction as the state change.
"""
import uuid
from datetime import timedelta

from psycopg.types.json import Jsonb

from ...contracts import EvaluationError

PERSISTENCE_K, PERSISTENCE_N = 2, 3
HOLD_WINDOWS = 2
R1_HOLD_WINDOWS = 2
OPEN = ('emerging', 'active', 'quiescent', 'suppressed')
IGNORED_KINDS = {'rule_unevaluable'}         # folded into the empty-window and health conditions
SEVERITY = {'info': 0, 'low': 1, 'medium': 2, 'high': 3, 'critical': 4}
STANDING = {'E': 0, 'P': 1, 'D': 2, 'F': 2}
R1_SOURCES = ('health', 'rule')
R1_WORDING = 'Operational condition returned to acceptable state; no outcome evidence.'


def key_of(signal):
    payload = signal['payload'] or {}
    if signal['source'] == 'health':
        return f"health:{signal['source_id']}:{payload.get('source', '')}"
    return f"{signal['source']}:{signal['source_id']}"


def _event(conn, scope, condition_id, before, after, reason, actor, detail=None):
    conn.execute('INSERT INTO ops_condition_events(org_id, condition_id, from_state, to_state, reason, actor, detail) '
                 'VALUES (%s, %s, %s, %s, %s, %s, %s)', (scope.org_id, condition_id, before, after, reason, actor,
                                                         Jsonb(detail or {})))


def _immediate(standing, severity):
    return standing == 'F' or (standing == 'D' and severity in ('critical', 'high'))


def _persistent(windows, current):
    if current is None:
        return False
    recent = {w for w in windows if w is not None and w > current - PERSISTENCE_N}
    return len(recent) >= PERSISTENCE_K


def current_window(conn, scope, deployment_id):
    row = conn.execute("""SELECT max(e.window_index) AS w FROM ops_window_evaluations e
                          JOIN ops_monitoring_definitions d ON d.org_id = e.org_id AND d.deployment_id = e.deployment_id
                               AND d.version = e.definition_version AND d.state = 'confirmed'
                          WHERE e.org_id = %s AND e.deployment_id = %s AND e.phase = 'close'""",
                       (scope.org_id, deployment_id)).fetchone()
    return row['w']


def process(installation, deployment_id, *, now, actor='system'):
    """Fold unprocessed signals into conditions. Returns [(condition_id, change)] for incident handling."""
    scope = installation.scope
    changes = []
    with installation.db.transaction() as conn:
        conn.execute('SELECT 1 FROM ops_deployments WHERE org_id = %s AND id = %s FOR UPDATE', (scope.org_id, deployment_id))
        signals = conn.execute('SELECT * FROM ops_signals WHERE org_id = %s AND deployment_id = %s AND processed_at IS NULL '
                               'ORDER BY created_at, id', (scope.org_id, deployment_id)).fetchall()
        current = current_window(conn, scope, deployment_id)
        for signal in signals:
            payload = signal['payload'] or {}
            if signal['source'] == 'recovery':
                change = _recovery(conn, scope, signal, actor)
                if change:
                    changes.append(change)
            elif payload.get('kind') not in IGNORED_KINDS:
                changes.append(_fold(conn, scope, deployment_id, signal, current, now, actor))
            conn.execute('UPDATE ops_signals SET processed_at = %s WHERE org_id = %s AND id = %s', (now, scope.org_id, signal['id']))
    return changes


def _fold(conn, scope, deployment_id, signal, current, now, actor):
    key = key_of(signal)
    payload = signal['payload'] or {}
    row = conn.execute(f"SELECT * FROM ops_conditions WHERE org_id = %s AND deployment_id = %s AND key = %s "
                       f"AND state IN {OPEN} FOR UPDATE", (scope.org_id, deployment_id, key)).fetchone()
    window = signal['window_index']
    if row is None:
        condition_id = uuid.uuid4()
        state = 'active' if _immediate(signal['standing'], signal['severity']) else 'emerging'
        conn.execute('''INSERT INTO ops_conditions(org_id, id, deployment_id, definition_version, key, kind, standing, severity,
                            state, first_window, last_window, windows, signal_count, first_signal_at, last_signal_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1, %s, %s)''',
                     (scope.org_id, condition_id, deployment_id, signal['definition_version'], key,
                      payload.get('kind') or signal['source'], signal['standing'], signal['severity'], state, window, window,
                      [window] if window is not None else [], now, now))
        _event(conn, scope, condition_id, None, state, 'created', actor, {'signal': str(signal['id'])})
        change = (condition_id, 'created_' + state)
    else:
        condition_id = row['id']
        windows = list(row['windows'])
        if window is not None and window not in windows:
            windows = (windows + [window])[-16:]
        standing = signal['standing'] if STANDING[signal['standing']] > STANDING[row['standing']] else row['standing']
        severity = signal['severity'] if SEVERITY[signal['severity']] > SEVERITY[row['severity']] else row['severity']
        state = row['state']
        reason = None
        if state == 'emerging' and (_immediate(standing, severity) or _persistent(windows, current if current is not None else window)):
            state, reason = 'active', 'persistence' if not _immediate(standing, severity) else 'formal_or_deterministic'
        elif state == 'quiescent':
            state, reason = 'active', 'recurred'
        conn.execute('''UPDATE ops_conditions SET windows = %s, last_window = coalesce(%s, last_window), signal_count = signal_count + 1,
                            last_signal_at = %s, standing = %s, severity = %s, state = %s, revision = revision + 1,
                            updated_at = clock_timestamp() WHERE org_id = %s AND id = %s''',
                     (windows, window, now, standing, severity, state, scope.org_id, condition_id))
        if reason:
            _event(conn, scope, condition_id, row['state'], state, reason, actor, {'signal': str(signal['id'])})
        change = (condition_id, 'became_active' if reason else 'attached')
    conn.execute('INSERT INTO ops_condition_signals(org_id, condition_id, signal_id) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING',
                 (scope.org_id, condition_id, signal['id']))
    return change


def _recovery(conn, scope, signal, actor):
    payload = signal['payload'] or {}
    condition_id = payload.get('condition')
    if not condition_id:
        return None
    row = conn.execute('SELECT * FROM ops_conditions WHERE org_id = %s AND id = %s FOR UPDATE', (scope.org_id, condition_id)).fetchone()
    if row is None or row['state'] not in OPEN:
        return None
    if payload.get('kind') == 'recovery_not_established':
        _event(conn, scope, row['id'], row['state'], row['state'], 'recovery_not_established', actor, payload)
        return (row['id'], 'recovery_not_established')
    if signal['standing'] != 'F':
        # R2.5: a test outside the formal admission (maturity, unit design, reference design) is never recovery
        # evidence; its indication is recorded and the condition's state is unchanged.
        _event(conn, scope, row['id'], row['state'], row['state'], 'descriptive_recovery_indication', actor,
               {'claim': payload.get('claim'), 'signal': str(signal['id']), 'reasons': payload.get('reasons', []),
                'wording': payload.get('wording')})
        return (row['id'], 'descriptive_only')
    evidence = {'claim': payload['claim'], 'signal': str(signal['id']), 'wording': payload['wording'],
                'theta': payload['theta'], 'units': payload['units'], 'interpretation': payload['interpretation']}
    if row['state'] == 'quiescent':
        conn.execute("UPDATE ops_conditions SET state = 'recovered', recovery = %s, revision = revision + 1, "
                     'updated_at = clock_timestamp() WHERE org_id = %s AND id = %s', (Jsonb(evidence), scope.org_id, row['id']))
        _event(conn, scope, row['id'], 'quiescent', 'recovered', payload['claim'], actor, evidence)
        return (row['id'], 'recovered')
    conn.execute('UPDATE ops_conditions SET recovery = %s, revision = revision + 1 WHERE org_id = %s AND id = %s',
                 (Jsonb({**evidence, 'pending_quiescence': True}), scope.org_id, row['id']))
    _event(conn, scope, row['id'], row['state'], row['state'], 'recovery_claim_pending_quiescence', actor, evidence)
    return (row['id'], 'recovery_pending')


def tick(installation, deployment_id, *, now, actor='system'):
    """Time- and window-based transitions. Returns [(condition_id, change)]."""
    scope = installation.scope
    changes = []
    with installation.db.transaction() as conn:
        current = current_window(conn, scope, deployment_id)
        rows = conn.execute(f'SELECT * FROM ops_conditions WHERE org_id = %s AND deployment_id = %s AND state IN {OPEN} '
                            'ORDER BY created_at FOR UPDATE', (scope.org_id, deployment_id)).fetchall()
        for row in rows:
            row = dict(row)
            # Transitions chain within one tick (for example active -> quiescent -> recovered when an established
            # recovery claim was waiting for quiescence), so the outcome never depends on whether the claim arrived
            # before or after the condition went quiet. Each step is its own event; at most three steps are possible.
            for _step in range(3):
                new, reason, recovery = _next(row, current, now)
                if new is None:
                    break
                conn.execute('UPDATE ops_conditions SET state = %s, recovery = coalesce(%s, recovery), prior_state = NULL, '
                             'suppressed_until = CASE WHEN %s THEN NULL ELSE suppressed_until END, revision = revision + 1, '
                             'updated_at = clock_timestamp() WHERE org_id = %s AND id = %s',
                             (new, Jsonb(recovery) if recovery else None, row['state'] == 'suppressed', scope.org_id, row['id']))
                _event(conn, scope, row['id'], row['state'], new, reason, actor, recovery or {})
                changes.append((row['id'], new))
                was_suppressed = row['state'] == 'suppressed'
                row.update(state=new, recovery=recovery or row['recovery'], prior_state=None,
                           suppressed_until=None if was_suppressed else row['suppressed_until'])
                if new not in OPEN:
                    break
    return changes


def _elapsed(row, current, now):
    """Quiet time in windows (window-scoped conditions) or days (health conditions)."""
    if row['last_window'] is not None and current is not None:
        return current - row['last_window']
    return (now - row['last_signal_at']) // timedelta(days=1)


def _next(row, current, now):
    state = row['state']
    if state == 'suppressed':
        if row['suppressed_until'] is not None and now >= row['suppressed_until']:
            return row['prior_state'] or 'active', 'suppression_expired', None
        return None, None, None
    quiet = _elapsed(row, current, now)
    if state == 'emerging' and quiet >= PERSISTENCE_N:
        return 'lapsed', 'no_repeat_within_window_horizon', None
    if state == 'active' and quiet >= HOLD_WINDOWS:
        return 'quiescent', 'no_signals_for_hold_period', None
    if state == 'quiescent':
        pending = row['recovery'] or {}
        if pending.get('pending_quiescence'):
            evidence = {k: v for k, v in pending.items() if k != 'pending_quiescence'}
            return 'recovered', evidence['claim'], evidence
        if row['key'].split(':', 1)[0] in R1_SOURCES and row['standing'] in ('D', 'P') and quiet >= HOLD_WINDOWS + R1_HOLD_WINDOWS:
            return 'recovered', 'R1', {'claim': 'R1', 'wording': R1_WORDING, 'quiet': int(quiet)}
    return None, None, None


def suppress(installation, condition_id, *, reason, until, actor):
    if not reason or until is None:
        raise EvaluationError('Suppression requires a reason and an expiry.', 'invalid_suppression')
    scope = installation.scope
    with installation.db.transaction() as conn:
        row = conn.execute('SELECT * FROM ops_conditions WHERE org_id = %s AND id = %s FOR UPDATE', (scope.org_id, condition_id)).fetchone()
        if row is None or row['state'] not in ('emerging', 'active', 'quiescent'):
            raise EvaluationError('Only an open condition can be suppressed.', 'condition_state')
        conn.execute("UPDATE ops_conditions SET state = 'suppressed', prior_state = %s, suppressed_until = %s, "
                     'suppression_reason = %s, revision = revision + 1 WHERE org_id = %s AND id = %s',
                     (row['state'], until, reason, scope.org_id, condition_id))
        _event(conn, scope, condition_id, row['state'], 'suppressed', reason, actor, {'until': until.isoformat()})
        from .. import audit_action
        audit_action(conn, scope, actor, 'condition.suppress', str(condition_id), {'reason': reason, 'until': until.isoformat()})
