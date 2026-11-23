"""Response proposals, approvals and the response comparison (plan I.9, J journeys).

**What a proposal states.**
- What the customer would change (data only), and the identity the deployment should show afterwards.
- Its evidence. Each item has a basis:
  - ``hypothetical_replay``: a completed investigation run, or a saved CG5 or CG6 replay or execution assessment;
  - ``independent_assessment``: a saved CG4/CG5/CG6 assessment whose read consumed a confirmation-class
    reservation, so the evidence was independent of selection;
  - ``descriptive``.

  The basis is validated against the catalog and the ledger: an assessment that was not independent cannot be
  presented as independent.
- Expected effects, with uncertainty where admitted.
- Machine-checked prerequisites.
- Risks and limitations.
- The required approver role.
- A verification plan: R1, R2 or R3 claims (``verification.py``).

**Lifecycle.**
``draft → submitted → approved | rejected → handed_off → executing → verifying → verified | not_verified``, and
``withdrawn`` from any state before execution.
- Submitting re-checks the prerequisites, and moves the incident to ``response_proposed``.
- **Approval has no side effect.** It needs a different principal from the author and the
  ``intervention:approve`` permission. It records a row, an event and an audit entry, and nothing else: no
  deployment, source, contract or job changes, and no outbound call.
"""
import uuid

from psycopg.types.json import Jsonb

from ...contracts import EvaluationError, digest
from ..identity import IDENTITY_KEYS

KINDS = ('policy_guard', 'threshold_change', 'recalibration', 'model_rollback', 'model_replacement', 'data_fix', 'monitoring_fix',
         'accepted_risk_with_mitigation')
CHANGES_IDENTITY = ('policy_guard', 'threshold_change', 'recalibration', 'model_rollback', 'model_replacement')
BASES = ('hypothetical_replay', 'independent_assessment', 'descriptive')
CONFIRMATION_KINDS = ('confirmation', 'numerical_recomputation')
TRANSITIONS = {
    'draft': {'submitted', 'withdrawn'}, 'submitted': {'approved', 'rejected', 'withdrawn', 'draft'},
    'approved': {'handed_off', 'withdrawn'}, 'rejected': {'draft'}, 'handed_off': {'executing', 'withdrawn'},
    'executing': {'verifying'}, 'verifying': {'verified', 'not_verified'}, 'verified': set(), 'not_verified': {'draft'},
    'withdrawn': set(),
}
PREREQUISITES = ('identity_registered', 'expected_identity_declared', 'predictor_registered', 'attestation_key_registered',
                 'verification_feasible', 'evidence_independent')


def _event(conn, scope, proposal_id, kind, payload, actor):
    conn.execute('INSERT INTO ops_proposal_events(org_id, proposal_id, kind, payload, actor) VALUES (%s, %s, %s, %s, %s)',
                 (scope.org_id, proposal_id, kind, Jsonb(payload), actor))


def _row(conn, scope, proposal_id, lock=False):
    row = conn.execute('SELECT * FROM ops_proposals WHERE org_id = %s AND id = %s' + (' FOR UPDATE' if lock else ''),
                       (scope.org_id, proposal_id)).fetchone()
    if row is None:
        raise EvaluationError('Unknown proposal.', 'proposal_unknown')
    return dict(row)


# Evidence ------------------------------------------------------------------------------------------------------
def validate_evidence(installation, deployment_id, items):
    """Check each item's basis against the catalog and the ledger. Returns validated items (with what was found)."""
    from ..monitoring import context
    ctx = context.deployment(installation, deployment_id)
    out = []
    with installation.db.connect() as conn:
        for item in items or ():
            if not isinstance(item, dict) or item.get('basis') not in BASES:
                raise EvaluationError('Evidence items declare a basis: hypothetical_replay, independent_assessment or descriptive.',
                                      'invalid_evidence')
            ref, found = item.get('ref'), {}
            if item['basis'] in ('independent_assessment', 'hypothetical_replay') and ref:
                run = None
                try:
                    run = conn.execute("SELECT id, template, state FROM ops_investigation_runs WHERE org_id = %s AND id = %s",
                                       (installation.scope.org_id, uuid.UUID(str(ref)))).fetchone()
                except ValueError:
                    pass
                uses = conn.execute('''SELECT u.kind, u.purpose, u.state FROM cg_assessments a JOIN publications p ON p.id = a.publication_id
                                       JOIN evidence_uses u ON u.catalog_id = a.catalog_id AND u.job_id = p.job_id
                                       WHERE a.catalog_id = %s AND a.id = %s AND a.state = 'active' ''',
                                    (ctx['catalog_id'], str(ref))).fetchall()
                if run is not None:
                    found = {'kind': 'investigation_run', 'template': run['template'], 'state': run['state']}
                elif uses:
                    found = {'kind': 'assessment', 'evidence_uses': [{'kind': u['kind'], 'purpose': u['purpose'], 'state': u['state']}
                                                                    for u in uses]}
                if item['basis'] == 'independent_assessment':
                    independent = found.get('kind') == 'assessment' and any(
                        u['kind'] in CONFIRMATION_KINDS and u['state'] == 'consumed' for u in found['evidence_uses'])
                    if not independent:
                        raise EvaluationError('Independent-assessment evidence must be a saved assessment whose read consumed a '
                                              'confirmation-class reservation.', 'evidence_not_independent')
                elif not found or (found.get('kind') == 'investigation_run' and found['state'] not in ('completed', 'reused')):
                    raise EvaluationError('Replay evidence must reference a completed investigation or a saved assessment.',
                                          'evidence_unavailable')
            elif item['basis'] != 'descriptive':
                raise EvaluationError('Replay and independent evidence reference an investigation run or an assessment.',
                                      'invalid_evidence')
            out.append({**item, 'validated': found or {'kind': 'descriptive'}})
    return out


# Prerequisites -------------------------------------------------------------------------------------------------
def check_prerequisites(installation, proposal):
    from .. import registry
    from . import verification
    dep = registry.deployment(installation, proposal['deployment_id'])
    identity = dep['registered_identity'] or {}
    results = []
    for kind in proposal['prerequisites']['declared']:
        if kind == 'identity_registered':
            ok, reason = bool({k for k in identity if k in IDENTITY_KEYS}), 'the deployment has no registered identity'
        elif kind == 'expected_identity_declared':
            expected = proposal['expected_identity'] or {}
            ok = bool(expected) and set(expected) <= set(IDENTITY_KEYS)
            reason = 'declare the identity the deployment should show after the change'
        elif kind == 'predictor_registered':
            ok, reason = bool(identity.get('predictor_spec')), 'no registered CG6 predictor spec (sampled behavior audit)'
        elif kind == 'attestation_key_registered':
            ok, reason = dep['attestation_public_key'] is not None, 'no registered customer signing key'
        elif kind == 'verification_feasible':
            problems = verification.feasibility(installation, proposal)
            ok, reason = not problems, '; '.join(problems)
        elif kind == 'evidence_independent':
            ok = any(e['basis'] == 'independent_assessment' for e in proposal['evidence'])
            reason = 'no independent assessment among the evidence'
        else:
            raise EvaluationError('Unknown prerequisite.', 'invalid_prerequisite')
        results.append({'kind': kind, 'pass': bool(ok), 'reason': None if ok else reason})
    return results


# Lifecycle -----------------------------------------------------------------------------------------------------
def create(installation, incident_id, kind, *, title, change, verification_plan, author, evidence=(), effects=(),
           expected_identity=None, risks=(), prerequisites=(), required_role='approver'):
    from .. import audit_action
    from . import verification
    if kind not in KINDS:
        raise EvaluationError('Unknown proposal kind.', 'invalid_proposal')
    if not isinstance(change, dict) or not change:
        raise EvaluationError('Describe the change as data.', 'invalid_proposal')
    scope = installation.scope
    with installation.db.connect() as conn:
        incident = conn.execute('SELECT * FROM ops_incidents WHERE org_id = %s AND id = %s', (scope.org_id, incident_id)).fetchone()
    if incident is None or incident['state'] in ('resolved', 'merged'):
        raise EvaluationError('Proposals belong to an open incident.', 'invalid_proposal')
    plan = verification.normalize_plan(verification_plan)
    declared = list(dict.fromkeys(list(prerequisites) + ['verification_feasible']
                                  + (['expected_identity_declared'] if kind in CHANGES_IDENTITY else [])))
    if set(declared) - set(PREREQUISITES):
        raise EvaluationError('Unknown prerequisite.', 'invalid_prerequisite')
    items = validate_evidence(installation, incident['deployment_id'], evidence)
    for effect in effects:
        if not isinstance(effect, dict) or 'metric' not in effect or 'expected' not in effect:
            raise EvaluationError('Effects declare a metric and an expected value.', 'invalid_proposal')
    proposal_id = uuid.uuid4()
    record = {'items': items, 'effects': list(effects)}
    with installation.db.transaction() as conn:
        conn.execute('''INSERT INTO ops_proposals(org_id, id, incident_id, deployment_id, kind, title, state, author, change,
                            expected_identity, evidence, prerequisites, risks, required_role, verification_plan)
                        VALUES (%s, %s, %s, %s, %s, %s, 'draft', %s, %s, %s, %s, %s, %s, %s, %s)''',
                     (scope.org_id, proposal_id, incident_id, incident['deployment_id'], kind, title, author, Jsonb(change),
                      Jsonb(expected_identity or {}), Jsonb(record), Jsonb({'declared': declared, 'results': None}),
                      Jsonb(list(risks)), required_role, Jsonb(plan)))
        _event(conn, scope, proposal_id, 'created', {'kind': kind, 'title': title}, author)
        audit_action(conn, scope, author, 'proposal.create', str(proposal_id), {'incident': str(incident_id), 'kind': kind})
        from ..incidents.incidents import event
        event(conn, scope, incident_id, 'proposal_created', {'proposal': str(proposal_id), 'kind': kind}, author)
    return get(installation, proposal_id)


def get(installation, proposal_id):
    with installation.db.connect() as conn:
        row = _row(conn, installation.scope, proposal_id)
    row['evidence_items'] = row['evidence']['items']
    return row


SETTLED = ('verified', 'not_verified', 'withdrawn', 'rejected')


def _transition(conn, scope, row, to_state, actor, payload=None):
    if to_state not in TRANSITIONS[row['state']]:
        raise EvaluationError(f"A proposal cannot move from {row['state']} to {to_state}.", 'proposal_transition')
    conn.execute('UPDATE ops_proposals SET state = %s, revision = revision + 1, updated_at = clock_timestamp() WHERE org_id = %s AND id = %s',
                 (to_state, scope.org_id, row['id']))
    if to_state in SETTLED:
        conn.execute("UPDATE ops_pins SET expires_at = clock_timestamp() + interval '90 days' WHERE org_id = %s "
                     "AND holder_kind = 'proposal' AND holder_id = %s AND released_at IS NULL", (scope.org_id, str(row['id'])))
    _event(conn, scope, row['id'], 'state_changed', {'from': row['state'], 'to': to_state, **(payload or {})}, actor)


def _move_incident(installation, incident_id, targets, actor, now):
    """Advance the incident along ``targets`` where its lifecycle allows (system actor, evented and notified)."""
    from ..incidents import incidents
    for target in targets:
        with installation.db.connect() as conn:
            state = conn.execute('SELECT state FROM ops_incidents WHERE org_id = %s AND id = %s',
                                 (installation.scope.org_id, incident_id)).fetchone()['state']
        if target == state:
            continue
        if target in incidents.TRANSITIONS.get(state, ()):
            incidents.transition(installation, incident_id, target, actor=actor, now=now, reason='intervention lifecycle')


def submit(installation, proposal_id, *, actor, now):
    from .. import audit_action
    scope = installation.scope
    proposal = get(installation, proposal_id)
    results = check_prerequisites(installation, proposal)
    failed = [r for r in results if not r['pass']]
    with installation.db.transaction() as conn:
        row = _row(conn, scope, proposal_id, lock=True)
        conn.execute("UPDATE ops_proposals SET prerequisites = jsonb_set(prerequisites, '{results}', %s) WHERE org_id = %s AND id = %s",
                     (Jsonb(results), scope.org_id, proposal_id))
        if failed:
            _event(conn, scope, proposal_id, 'prerequisites_failed', {'failed': failed}, actor)
            raise_after = EvaluationError('Prerequisites are not met: ' + '; '.join(f"{r['kind']}: {r['reason']}" for r in failed),
                                          'prerequisites_unmet')
        else:
            _transition(conn, scope, row, 'submitted', actor, {'prerequisites': results})
            audit_action(conn, scope, actor, 'proposal.submit', str(proposal_id), {})
            # An unresolved proposal pins its incident's evidence windows (H.8) until settled + 90 days.
            conn.execute('''INSERT INTO ops_pins(org_id, id, catalog_id, namespace, start_tick, end_tick, holder_kind, holder_id, reason, created_by)
                            SELECT org_id, gen_random_uuid(), catalog_id, namespace, start_tick, end_tick, 'proposal', %s,
                                   'unresolved proposal evidence', %s
                            FROM ops_pins WHERE org_id = %s AND holder_kind = 'incident' AND holder_id = %s AND released_at IS NULL''',
                         (str(proposal_id), actor, scope.org_id, str(row['incident_id'])))
            raise_after = None
    if raise_after is not None:
        raise raise_after
    _move_incident(installation, proposal['incident_id'], ['investigating', 'response_proposed'], 'system', now)
    return get(installation, proposal_id)


def decide(installation, proposal_id, decision, *, actor, permissions, reason=None, expected_revision=None):
    """Approve or reject. Records only: a row, an event and an audit entry (approval has no side effect)."""
    from .. import audit_action
    if decision not in ('approved', 'rejected'):
        raise EvaluationError('A decision is approved or rejected.', 'invalid_decision')
    if 'intervention:approve' not in permissions:
        raise EvaluationError('Approving interventions needs intervention:approve.', 'forbidden')
    scope = installation.scope
    with installation.db.transaction() as conn:
        row = _row(conn, scope, proposal_id, lock=True)
        if expected_revision is not None and row['revision'] != expected_revision:
            raise EvaluationError('The proposal changed since it was read.', 'stale_revision')
        if actor == row['author']:
            raise EvaluationError('The author cannot approve their own proposal.', 'separation_of_duties')
        if decision == 'rejected' and not reason:
            raise EvaluationError('A rejection needs a reason.', 'invalid_decision')
        conn.execute('INSERT INTO ops_approvals(org_id, proposal_id, approver, decision, reason, proposal_revision) VALUES (%s, %s, %s, %s, %s, %s)',
                     (scope.org_id, proposal_id, actor, decision, reason, row['revision']))
        _transition(conn, scope, row, decision, actor, {'reason': reason})
        audit_action(conn, scope, actor, 'proposal.' + ('approve' if decision == 'approved' else 'reject'), str(proposal_id),
                     {'revision': row['revision'], 'reason': reason})
    return get(installation, proposal_id)


def withdraw(installation, proposal_id, *, actor, reason):
    from .. import audit_action
    scope = installation.scope
    with installation.db.transaction() as conn:
        row = _row(conn, scope, proposal_id, lock=True)
        _transition(conn, scope, row, 'withdrawn', actor, {'reason': reason})
        audit_action(conn, scope, actor, 'proposal.withdraw', str(proposal_id), {'reason': reason})


# Response comparison -------------------------------------------------------------------------------------------
def compare(installation, incident_id):
    """Proposals side by side, with re-checked prerequisites and matched prior mitigations (plan I.9)."""
    from ..intelligence import patterns
    scope = installation.scope
    with installation.db.connect() as conn:
        rows = [dict(r) for r in conn.execute("SELECT * FROM ops_proposals WHERE org_id = %s AND incident_id = %s AND state <> 'withdrawn' "
                                              'ORDER BY created_at', (scope.org_id, incident_id)).fetchall()]
    similar = patterns.similar(installation, incident_id)['similar']
    prior = []
    with installation.db.connect() as conn:
        for other in similar:
            for p in conn.execute('SELECT id, kind, title, state FROM ops_proposals WHERE org_id = %s AND incident_id = %s',
                                  (scope.org_id, uuid.UUID(other['incident']))).fetchall():
                checks = [dict(v) for v in conn.execute('SELECT claim, state, result FROM ops_verifications WHERE org_id = %s AND proposal_id = %s',
                                                        (scope.org_id, p['id'])).fetchall()]
                prior.append({'incident': other['incident'], 'jaccard': other['jaccard'], 'proposal': str(p['id']), 'kind': p['kind'],
                              'title': p['title'], 'state': p['state'], 'verification': checks})
    out = []
    for row in rows:
        bases = sorted({e['basis'] for e in row['evidence']['items']})
        out.append({'proposal': str(row['id']), 'kind': row['kind'], 'title': row['title'], 'state': row['state'],
                    'evidence_basis': bases,
                    'strongest_basis': next((b for b in ('independent_assessment', 'hypothetical_replay', 'descriptive') if b in bases), None),
                    'effects': row['evidence']['effects'], 'prerequisites': check_prerequisites(installation, row),
                    'risks': row['risks'], 'required_role': row['required_role'],
                    'verification_plan': row['verification_plan'],
                    'causal_claim': 'not claimed (R4 requires randomized or staggered rollout evidence)'})
    return {'incident': str(incident_id), 'proposals': out, 'prior_mitigations': prior,
            'qualification': 'Hypothetical replay estimates what a change would have done on recorded inputs; it is never '
                             'merged with production evidence of what happened after execution.',
            'digest': digest([o['proposal'] for o in out])}
