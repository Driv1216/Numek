"""Verification plans and recovery claims after an intervention (plan G.10, R2.5).

A proposal's plan lists claims:

| Claim | Meaning | How it is verified |
|---|---|---|
| **R1** (operational) | The incident's deterministic and descriptive conditions recover operationally. | The S6 condition lifecycle, with no outcome evidence. |
| **R2** (fixed threshold) | Risk is below a declared acceptable level ``theta``. | An SM2 recovery test on the claim's statistic. |
| **R3** (non-inferiority) | Risk is not worse than the reference by more than ``delta``. | An SM2 test with θ = L_ref + Δ. |
| **R4** (causal effect) | — | **Not claimed.** The proposal has a ``causal_evidence`` slot for randomized or staggered rollout evidence. |

**SM2 tests (R2/R3).**
- Each test starts at the first window that begins at or after the declared execution time and has not yet been
  evaluated, so the verification start is fixed before any of its units are seen.
- It is bound to the incident's member condition with the same statistic. A claim recovers that condition (S6),
  which is what an outcome-supported resolution requires.
- SM1 keeps running on the same stream. An alarm after a claim is a recurrence.

**Settling a plan.**
- Every claim established: ``verified``.
- A claim whose horizon passes without its claim: ``not_verified`` (``recovery_not_established``), and the
  incident goes back to ``investigating``.

An absent alarm is never verification.
"""
import math

from psycopg.types.json import Jsonb

from ...contracts import EvaluationError
from ...history_contracts import instant
from . import proposals as proposal_rules

CLAIMS = ('R1', 'R2', 'R3')
RESOLUTION = {'R3': 'reference_noninferiority_established', 'R2': 'threshold_recovery_established', 'R1': 'operational_recovery_observed'}


def normalize_plan(plan):
    if not isinstance(plan, dict) or not plan.get('claims'):
        raise EvaluationError('A verification plan lists at least one claim (R1, R2 or R3).', 'invalid_verification_plan')
    claims, seen = [], set()
    for claim in plan['claims']:
        if claim.get('claim') not in CLAIMS or not claim.get('id') or claim['id'] in seen:
            raise EvaluationError('Each claim has a unique id and is R1, R2 or R3 (R4 is not claimed).', 'invalid_verification_plan')
        seen.add(claim['id'])
        if claim['claim'] in ('R2', 'R3'):
            if not claim.get('statistic') or not 0 < float(claim.get('alpha', 0)) < 1 or int(claim.get('planned_support', 0)) < 30:
                raise EvaluationError('R2/R3 claims name a statistic, alpha in (0, 1) and planned support of at least 30.',
                                      'invalid_verification_plan')
            if claim['claim'] == 'R2' and 'theta' not in claim:
                raise EvaluationError('R2 declares the acceptable risk theta.', 'invalid_verification_plan')
            if claim['claim'] == 'R3' and 'delta' not in claim:
                raise EvaluationError('R3 declares the margin delta.', 'invalid_verification_plan')
        claims.append(dict(claim))
    return {'claims': claims, 'causal': 'R4 is not claimed: it requires randomized or staggered rollout evidence.'}


def feasibility(installation, proposal):
    """Problems that would stop the plan from being verified (empty when feasible)."""
    from ..monitoring import definitions, references, units
    current = definitions.confirmed(installation, proposal['deployment_id'])
    if current is None:
        return ['the deployment has no confirmed monitoring definition']
    reference = references.load(installation, current['reference_id'])
    problems = []
    for claim in proposal['verification_plan']['claims']:
        if claim['claim'] == 'R1':
            continue
        statistic = claim['statistic']
        if statistic not in units.STATISTICS:
            problems.append(f"{claim['id']}: unknown statistic {statistic}")
            continue
        record = reference['packet']['statistics'].get(statistic)
        if record is None:
            problems.append(f"{claim['id']}: the reference has no {statistic} record")
        elif claim['claim'] == 'R3' and record['lower'] is None:
            problems.append(f"{claim['id']}: the reference has no finite lower bound for {statistic} (R3 unavailable)")
    return problems


def _first_window(conn, scope, deployment_id, version, spec, phase, executed_at):
    start, length = instant(spec['start']), int(spec['window_ns'])
    tick = int(executed_at.timestamp() * 1e9)
    after = max(0, math.ceil((tick - start) / length))
    last = conn.execute('SELECT max(window_index) AS m FROM ops_window_evaluations WHERE org_id = %s AND deployment_id = %s '
                        'AND definition_version = %s AND phase = %s', (scope.org_id, deployment_id, version, phase)).fetchone()['m']
    return max(after, 0 if last is None else last + 1)


def start(installation, proposal_id, *, executed_at, actor, now):
    """Bind each claim: SM2 tests for R2/R3 (from the first window after execution), conditions for R1."""
    from ..monitoring import definitions, units
    scope = installation.scope
    proposal = proposal_rules.get(installation, proposal_id)
    current = definitions.confirmed(installation, proposal['deployment_id'])
    with installation.db.connect() as conn:
        members = [dict(r) for r in conn.execute(
            '''SELECT c.* FROM ops_incident_conditions ic JOIN ops_conditions c ON c.org_id = ic.org_id AND c.id = ic.condition_id
               WHERE ic.org_id = %s AND ic.incident_id = %s AND ic.removed_at IS NULL''', (scope.org_id, proposal['incident_id'])).fetchall()]
    detectors = {d['id']: d['statistic'] for d in current['spec']['detectors']}
    started = []
    for claim in proposal['verification_plan']['claims']:
        if claim['claim'] == 'R1':
            bound = [c for c in members if c['key'].split(':', 1)[0] in ('health', 'rule')]
            with installation.db.transaction() as conn:
                conn.execute('''INSERT INTO ops_verifications(org_id, proposal_id, claim_id, claim, condition_id, state, result)
                                VALUES (%s, %s, %s, 'R1', %s, 'running', %s)''',
                             (scope.org_id, proposal_id, claim['id'], bound[0]['id'] if bound else None,
                              Jsonb({'conditions': [str(c['id']) for c in bound]})))
            started.append({'claim': claim['id'], 'kind': 'R1', 'conditions': len(bound)})
            continue
        condition = next((c for c in members if c['key'].startswith('detector:')
                          and detectors.get(c['key'].split(':', 1)[1]) == claim['statistic']), None)
        phase = units.STATISTICS[claim['statistic']]['phase']
        with installation.db.connect() as conn:
            first = _first_window(conn, scope, proposal['deployment_id'], current['version'], current['spec'], phase, executed_at)
        detector_id = f"verify-{str(proposal_id)[:8]}-{claim['id']}"
        definitions.start_recovery(installation, proposal['deployment_id'], detector_id, claim=claim['claim'], alpha=float(claim['alpha']),
                                   planned_support=int(claim['planned_support']), statistic=claim['statistic'],
                                   theta=claim.get('theta'), delta=claim.get('delta'), start_window=first,
                                   horizon_units=claim.get('horizon_units'), condition_id=None if condition is None else condition['id'])
        with installation.db.transaction() as conn:
            conn.execute('''INSERT INTO ops_verifications(org_id, proposal_id, claim_id, claim, condition_id, detector_id, start_window, state)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, 'running')''',
                         (scope.org_id, proposal_id, claim['id'], claim['claim'], None if condition is None else condition['id'],
                          detector_id, first))
        started.append({'claim': claim['id'], 'kind': claim['claim'], 'detector': detector_id, 'start_window': first,
                        'condition': None if condition is None else str(condition['id'])})
    with installation.db.transaction() as conn:
        row = proposal_rules._row(conn, scope, proposal_id, lock=True)
        proposal_rules._transition(conn, scope, row, 'verifying', actor, {'claims': started})
    proposal_rules._move_incident(installation, proposal['incident_id'], ['verifying'], 'system', now)
    return started


def refresh(installation, proposal_id, *, now, actor='system'):
    """Settle running claims from SM2 states and condition recoveries; settle the plan when every claim is settled."""
    scope = installation.scope
    with installation.db.connect() as conn:
        claims = [dict(r) for r in conn.execute("SELECT * FROM ops_verifications WHERE org_id = %s AND proposal_id = %s ORDER BY claim_id",
                                                (scope.org_id, proposal_id)).fetchall()]
        settled = []
        for claim in claims:
            if claim['state'] != 'running':
                continue
            result = None
            if claim['claim'] == 'R1':
                ids = claim['result']['conditions']
                rows = conn.execute('SELECT id, state, recovery FROM ops_conditions WHERE org_id = %s AND id::text = ANY(%s)',
                                    (scope.org_id, ids)).fetchall() if ids else []
                if ids and all(r['state'] == 'recovered' and (r['recovery'] or {}).get('claim') == 'R1' for r in rows):
                    result = ('established', {'conditions': ids, 'wording': 'Operational condition returned to acceptable state; '
                                                                           'no outcome evidence.'})
            else:
                det = conn.execute('SELECT state, plan FROM ops_detectors WHERE org_id = %s AND detector_id = %s',
                                   (scope.org_id, claim['detector_id'])).fetchone()
                state = det['state']
                if state.get('claimed_at') is not None:
                    from ..monitoring import eprocess
                    kernel = eprocess.RecoveryTest.from_state(state)
                    result = ('established', {'claimed_at_unit': state['claimed_at'], 'units': state['units'], 'upper': kernel.upper(),
                                              'theta': det['plan']['theta'], 'error_bound': det['plan']['error_bound'],
                                              'interpretation': det['plan']['interpretation']})
                elif det['plan'].get('horizon_units') and state['units'] >= int(det['plan']['horizon_units']):
                    result = ('not_established', {'units': state['units'], 'reason': 'recovery_not_established'})
            if result:
                settled.append((claim['claim_id'], result))
    if settled:
        with installation.db.transaction() as conn:
            for claim_id, (state, result) in settled:
                conn.execute('UPDATE ops_verifications SET state = %s, result = %s, finished_at = %s WHERE org_id = %s AND proposal_id = %s '
                             'AND claim_id = %s', (state, Jsonb(result), now, scope.org_id, proposal_id, claim_id))
                proposal_rules._event(conn, scope, proposal_id, 'verification_' + state, {'claim': claim_id, **result}, actor)
    return _settle(installation, proposal_id, now=now, actor=actor)


def _settle(installation, proposal_id, *, now, actor):
    scope = installation.scope
    with installation.db.connect() as conn:
        states = [r['state'] for r in conn.execute('SELECT state FROM ops_verifications WHERE org_id = %s AND proposal_id = %s',
                                                   (scope.org_id, proposal_id)).fetchall()]
    proposal = proposal_rules.get(installation, proposal_id)
    if proposal['state'] != 'verifying' or not states or 'running' in states or 'pending' in states:
        return {'proposal': str(proposal_id), 'state': proposal['state'], 'claims': states}
    outcome = 'verified' if all(s == 'established' for s in states) else 'not_verified'
    with installation.db.transaction() as conn:
        row = proposal_rules._row(conn, scope, proposal_id, lock=True)
        proposal_rules._transition(conn, scope, row, outcome, actor, {'claims': states})
    if outcome == 'not_verified':
        proposal_rules._move_incident(installation, proposal['incident_id'], ['investigating'], 'system', now)
    return {'proposal': str(proposal_id), 'state': outcome, 'claims': states}


def refresh_all(installation, deployment_id, *, now):
    with installation.db.connect() as conn:
        ids = [r['id'] for r in conn.execute("SELECT id FROM ops_proposals WHERE org_id = %s AND deployment_id = %s AND state = 'verifying'",
                                             (installation.scope.org_id, deployment_id)).fetchall()]
    return [refresh(installation, i, now=now) for i in ids]


def resolve(installation, proposal_id, *, actor, now):
    """Resolve the incident with the strongest established claim of a verified proposal (R3 > R2 > R1)."""
    from ..incidents import incidents
    proposal = proposal_rules.get(installation, proposal_id)
    if proposal['state'] != 'verified':
        raise EvaluationError('Only a verified proposal resolves its incident.', 'proposal_transition')
    with installation.db.connect() as conn:
        claims = {r['claim'] for r in conn.execute("SELECT claim FROM ops_verifications WHERE org_id = %s AND proposal_id = %s "
                                                   "AND state = 'established'", (installation.scope.org_id, proposal_id)).fetchall()}
    # A condition records the first recovery claim that reached it; resolve with the strongest claim it recorded.
    for claim in ('R3', 'R2', 'R1'):
        if claim not in claims:
            continue
        try:
            return incidents.transition(installation, proposal['incident_id'], 'resolved', actor=actor, resolution=RESOLUTION[claim],
                                        now=now, reason=f'verified proposal {proposal_id}')
        except EvaluationError as exc:
            if exc.code != 'recovery_evidence_required':
                raise
    raise EvaluationError('No member condition recorded the established recovery claims.', 'recovery_evidence_required')
