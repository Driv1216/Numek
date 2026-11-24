"""Execution handoffs and execution-evidence standings (plan G.9: intervention execution).

**The handoff.** An approved proposal becomes an immutable ``ExecutionHandoff`` packet that the customer acts on.
It carries:
- the change;
- the identity the deployment should show afterwards;
- the verification plan;
- the approvals;
- the evidence references;
- a statement template the customer may sign.

NUMEK never executes it.

**Standings.** Each is recorded separately, with its time and evidence, and none implies another:

| Standing | Evidence kind | Established when |
|---|---|---|
| ``execution_declared`` | declaration | an operator or the customer records that the change was executed (and when) |
| ``identity_consistent_with_handoff`` | production | the identities declared by batches received after execution equal the handoff's expected identity |
| ``behavior_change_observed`` | production, descriptive | outcome-free measures moved toward the proposal's declared expectation |
| ``sampled_behavior_consistent`` | production | logged post-change outputs are replayed through the expected predictor (the S4 keyed-sample audit), with a Clopper–Pearson bound |
| ``execution_attested`` | signature | an Ed25519 signature verifies against the deployment's registered customer key |

For ``execution_attested``, trust rests on the customer's signing process; runtime attestation is not
implemented and never inferred.

Production evidence of what happened after execution is never merged with hypothetical replay.
"""
import base64
import hashlib
import json
import uuid
from datetime import datetime

from psycopg.types.json import Jsonb

from ...contracts import EvaluationError
from . import proposals as proposal_rules

BEHAVIOR_METRICS = ('positive_decision_rate', 'abstention_rate', 'failure_rate')


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def _record(conn, scope, proposal_id, standing, outcome, kind, evidence, actor):
    conn.execute('''INSERT INTO ops_execution_standings(org_id, id, proposal_id, standing, outcome, evidence_kind, evidence, recorded_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)''',
                 (scope.org_id, uuid.uuid4(), proposal_id, standing, outcome, kind, Jsonb(evidence), actor))
    proposal_rules._event(conn, scope, proposal_id, 'execution_standing', {'standing': standing, 'outcome': outcome}, actor)
    from .. import audit_action
    audit_action(conn, scope, actor, 'execution.standing', str(proposal_id), {'standing': standing, 'outcome': outcome, 'evidence_kind': kind})
    return {'standing': standing, 'outcome': outcome, 'evidence_kind': kind, **evidence}


def issue_handoff(installation, proposal_id, *, actor, now):
    from ..incidents.incidents import _stage, event
    from ..monitoring import context, packets
    scope = installation.scope
    proposal = proposal_rules.get(installation, proposal_id)
    if proposal['state'] != 'approved':
        raise EvaluationError('Only an approved proposal can be handed off.', 'proposal_transition')
    with installation.db.connect() as conn:
        approvals = [dict(r) for r in conn.execute("SELECT approver, decision, proposal_revision, at FROM ops_approvals WHERE org_id = %s "
                                                   "AND proposal_id = %s AND decision = 'approved'", (scope.org_id, proposal_id)).fetchall()]
    packet = {'schema_version': 'numek.execution_handoff/1', 'proposal': str(proposal_id), 'incident': str(proposal['incident_id']),
              'deployment': proposal['deployment_id'], 'kind': proposal['kind'], 'title': proposal['title'], 'change': proposal['change'],
              'expected_identity': proposal['expected_identity'], 'verification_plan': proposal['verification_plan'],
              'approvals': approvals, 'evidence': [{'basis': e['basis'], 'ref': e.get('ref'), 'validated': e['validated']}
                                                   for e in proposal['evidence_items']],
              'issued_by': actor, 'issued_at': now.isoformat(),
              'executed_by': 'customer (NUMEK never executes a production change)',
              'statement_to_sign': {'proposal': str(proposal_id), 'handoff_digest': '<this packet digest>', 'executed_at': '<ISO time>',
                                    'identity': proposal['expected_identity']}}
    ctx = context.deployment(installation, proposal['deployment_id'])
    lease, ref, packet_digest = _stage(installation, ctx, packet, 'ops_execution_handoff')

    def write(conn):
        row = proposal_rules._row(conn, scope, proposal_id, lock=True)
        conn.execute('INSERT INTO ops_handoffs(org_id, id, proposal_id, packet_object, packet_digest, issued_by, issued_at) '
                     'VALUES (%s, %s, %s, %s, %s, %s, %s)', (scope.org_id, uuid.uuid4(), proposal_id, ref.id, packet_digest, actor, now))
        proposal_rules._transition(conn, scope, row, 'handed_off', actor, {'handoff_digest': packet_digest})
        event(conn, scope, proposal['incident_id'], 'response_handed_off', {'proposal': str(proposal_id), 'handoff_digest': packet_digest}, actor)
        from .. import audit_action
        audit_action(conn, scope, actor, 'proposal.handoff', str(proposal_id), {'handoff_digest': packet_digest})
    packets.publish(installation, lease, ctx['catalog_id'], [ref], [], write)
    return {'handoff_digest': packet_digest, 'packet': json.loads(json.dumps(packet, default=str))}


def handoff(installation, proposal_id):
    from ..monitoring import packets
    with installation.db.connect() as conn:
        row = conn.execute('SELECT * FROM ops_handoffs WHERE org_id = %s AND proposal_id = %s', (installation.scope.org_id, proposal_id)).fetchone()
    if row is None:
        raise EvaluationError('No handoff for this proposal.', 'handoff_unknown')
    packet = packets.read(installation, row['packet_object'])
    if packets.packet_digest(packet) != row['packet_digest']:
        raise EvaluationError('Handoff packet differs from its record.', 'evidence_changed')
    return {'handoff_digest': row['packet_digest'], 'packet': packet}


def declare_execution(installation, proposal_id, *, executed_at, actor, detail=None, now):
    """Record ``execution_declared``; the proposal becomes executing and its verification starts."""
    from . import verification
    scope = installation.scope
    with installation.db.transaction() as conn:
        row = proposal_rules._row(conn, scope, proposal_id, lock=True)
        proposal_rules._transition(conn, scope, row, 'executing', actor, {'executed_at': executed_at.isoformat()})
        result = _record(conn, scope, proposal_id, 'execution_declared', 'established', 'declaration',
                         {'executed_at': executed_at.isoformat(), 'declared_by': actor, 'detail': detail or {}}, actor)
    proposal_rules._move_incident(installation, row['incident_id'], ['response_executing'], 'system', now)
    result['verification'] = verification.start(installation, proposal_id, executed_at=executed_at, actor=actor, now=now)
    return result


def _executed(conn, scope, proposal_id):
    row = conn.execute("SELECT evidence, recorded_at FROM ops_execution_standings WHERE org_id = %s AND proposal_id = %s "
                       "AND standing = 'execution_declared' AND outcome = 'established' ORDER BY recorded_at LIMIT 1",
                       (scope.org_id, proposal_id)).fetchone()
    if row is None:
        raise EvaluationError('Execution has not been declared.', 'execution_not_declared')
    executed = datetime.fromisoformat(row['evidence']['executed_at'])
    return executed, row['recorded_at']


def identity_consistency(installation, proposal_id, *, actor='system'):
    """Identities declared by batches received after execution (max of declared execution time and declaration)."""
    scope = installation.scope
    proposal = proposal_rules.get(installation, proposal_id)
    expected = proposal['expected_identity'] or {}
    with installation.db.transaction() as conn:
        executed, declared_at = _executed(conn, scope, proposal_id)
        since = max(executed, declared_at)
        rows = conn.execute("""SELECT outcome, evidence FROM ops_identity_standings WHERE org_id = %s AND deployment_id = %s
                               AND standing = 'declared' AND period_start >= %s ORDER BY recorded_at""",
                            (scope.org_id, proposal['deployment_id'], since)).fetchall()
        identities = [r['evidence'].get('identity') for r in rows if r['outcome'] == 'established']
        if not expected or not identities:
            outcome, evidence = 'not_evaluable', {'reason': 'no_expected_identity' if not expected else 'no_identity_declared_since_execution'}
        else:
            differing = [i for i in identities if any(str(i.get(k)) != str(v) for k, v in expected.items() if k in i)]
            comparable = [i for i in identities if set(expected) & set(i)]
            outcome = 'not_evaluable' if not comparable else 'failed' if differing else 'established'
            evidence = {'expected': expected, 'batches_compared': len(comparable), 'batches_differing': len(differing),
                        'since': since.isoformat()}
        return _record(conn, scope, proposal_id, 'identity_consistent_with_handoff', outcome, 'production', evidence, actor)


def _rates(units, positive):
    n = len(units)
    if not n:
        return None
    return {'positive_decision_rate': sum(1 for u in units if u['decision'] == positive and u['state'] in ('issued', 'hypothetical')) / n,
            'abstention_rate': sum(1 for u in units if u['state'] == 'abstained') / n,
            'failure_rate': sum(1 for u in units if u['state'] in ('failed', 'missing')) / n}


def behavior_change(installation, proposal_id, *, actor='system'):
    """Outcome-free measures before and after execution, against the proposal's declared expectations (descriptive)."""
    from ..monitoring import definitions, packets
    scope = installation.scope
    proposal = proposal_rules.get(installation, proposal_id)
    effects = [e for e in proposal['evidence']['effects'] if e['metric'] in BEHAVIOR_METRICS]
    current = definitions.confirmed(installation, proposal['deployment_id'])
    with installation.db.transaction() as conn:
        executed, _declared = _executed(conn, scope, proposal_id)
        if not effects or current is None:
            return _record(conn, scope, proposal_id, 'behavior_change_observed', 'not_evaluable', 'production',
                           {'reason': 'no_outcome_free_expectation_declared' if not effects else 'no_confirmed_definition'}, actor)
        split = int(executed.timestamp() * 1e9)
        rows = conn.execute("""SELECT DISTINCT ON (window_index) window_index, start_tick, end_tick, packet_object FROM ops_window_evaluations
                               WHERE org_id = %s AND deployment_id = %s AND definition_version = %s AND phase = 'close'
                               ORDER BY window_index, revision DESC""", (scope.org_id, proposal['deployment_id'], current['version'])).fetchall()
        before = [u for r in rows if int(r['end_tick']) <= split for u in packets.read(installation, r['packet_object'])['units']]
        after = [u for r in rows if int(r['start_tick']) >= split for u in packets.read(installation, r['packet_object'])['units']]
        positive = proposal['change'].get('positive_class') or _positive(installation, proposal['deployment_id'])
        pre, post = _rates(before, positive), _rates(after, positive)
        if pre is None or post is None:
            return _record(conn, scope, proposal_id, 'behavior_change_observed', 'not_evaluable', 'production',
                           {'reason': 'no_windows_after_execution' if post is None else 'no_windows_before_execution'}, actor)
        checks = []
        for effect in effects:
            want = float(effect['expected']) - pre[effect['metric']]
            moved = post[effect['metric']] - pre[effect['metric']]
            ok = want != 0 and moved / want >= 0.5
            checks.append({'metric': effect['metric'], 'before': pre[effect['metric']], 'after': post[effect['metric']],
                           'expected': effect['expected'], 'fraction_of_expected_change': (moved / want) if want else None, 'moved': ok})
        outcome = 'established' if all(c['moved'] for c in checks) else 'failed'
        return _record(conn, scope, proposal_id, 'behavior_change_observed', outcome, 'production',
                       {'checks': checks, 'units_before': len(before), 'units_after': len(after),
                        'standing': 'descriptive (no probability statement)'}, actor)


def _positive(installation, deployment_id):
    from ..monitoring import definitions, references
    current = definitions.confirmed(installation, deployment_id)
    task = references.load(installation, current['reference_id'])['packet']['metadata']['task']
    return task.get('positive_class')


def sampled_behavior(installation, proposal_id, *, logged_outputs, scratch, actor='system'):
    """Replay of logged post-execution outputs through the predictor the handoff expects (keyed-random sample)."""
    from .. import identity, ingest, registry
    from ..contracts import SourceContract, parse
    scope = installation.scope
    proposal = proposal_rules.get(installation, proposal_id)
    with installation.db.connect() as conn:
        executed, declared_at = _executed(conn, scope, proposal_id)
        batches = conn.execute('''SELECT b.* FROM ops_batches b JOIN ops_sources s ON s.org_id = b.org_id AND s.id = b.source_id
                                  AND s.version = b.contract_version WHERE b.org_id = %s AND s.deployment_id = %s AND b.state = 'published'
                                  AND b.received_at >= %s ORDER BY b.received_at''',
                               (scope.org_id, proposal['deployment_id'], max(executed, declared_at))).fetchall()
    rows, keys = [], None
    for batch in batches:
        contract = SourceContract.from_dict(registry.source(installation, batch['source_id'], batch['contract_version'])['contract'])
        try:
            rows += parse(contract, ingest._decrypt(installation, scope, batch))
        except EvaluationError:
            continue
        keys = [name for name, field in contract.fields.items() if field.get('identity')]
    with installation.db.transaction() as conn:
        if not rows:
            return _record(conn, scope, proposal_id, 'sampled_behavior_consistent', 'not_evaluable', 'production',
                           {'reason': 'no_retained_rows_since_execution'}, actor)
    try:
        audit = identity.audit_outputs(installation, proposal['deployment_id'], rows, key_columns=keys, logged_outputs=logged_outputs,
                                       scratch=scratch)
        outcome = 'established' if audit.get('outcome') == 'established' else 'failed' if audit.get('outcome') == 'failed' else 'not_evaluable'
    except EvaluationError as exc:
        audit, outcome = {'reason': exc.code}, 'not_evaluable'
    with installation.db.transaction() as conn:
        return _record(conn, scope, proposal_id, 'sampled_behavior_consistent', outcome, 'production', audit, actor)


def attest(installation, proposal_id, statement, signature, *, actor='customer'):
    """Verify a customer-signed execution statement ``{proposal, handoff_digest, executed_at, identity}``."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from .. import registry
    scope = installation.scope
    proposal = proposal_rules.get(installation, proposal_id)
    current = handoff(installation, proposal_id)
    if not isinstance(statement, dict) or set(statement) != {'proposal', 'handoff_digest', 'executed_at', 'identity'}:
        raise EvaluationError('A signed execution statement names proposal, handoff_digest, executed_at and identity.', 'invalid_statement')
    if statement['proposal'] != str(proposal_id) or statement['handoff_digest'] != current['handoff_digest']:
        raise EvaluationError('The statement names another proposal or handoff.', 'invalid_statement')
    key = registry.deployment(installation, proposal['deployment_id'])['attestation_public_key']
    signature = base64.b64decode(signature) if isinstance(signature, str) else signature
    evidence = {'statement': statement, 'statement_digest': hashlib.sha256(_canonical(statement)).hexdigest(),
                'trust': 'customer_signing_process', 'runtime_attestation': 'not_implemented',
                'identity_matches_handoff': statement['identity'] == proposal['expected_identity']}
    if key is None:
        outcome, evidence['reason'] = 'not_evaluable', 'no_registered_customer_key'
    else:
        evidence['key_fingerprint'] = hashlib.sha256(bytes(key)).hexdigest()
        try:
            Ed25519PublicKey.from_public_bytes(bytes(key)).verify(signature, _canonical(statement))
            outcome = 'established' if evidence['identity_matches_handoff'] else 'failed'
            if outcome == 'failed':
                evidence['reason'] = 'signed_identity_differs_from_handoff'
        except (InvalidSignature, ValueError):
            outcome, evidence['reason'] = 'failed', 'signature_does_not_verify'
    with installation.db.transaction() as conn:
        return _record(conn, scope, proposal_id, 'execution_attested', outcome, 'signature', evidence, actor)


def standings(installation, proposal_id):
    with installation.db.connect() as conn:
        rows = conn.execute('''SELECT DISTINCT ON (standing) standing, outcome, evidence_kind, evidence, recorded_at FROM ops_execution_standings
                               WHERE org_id = %s AND proposal_id = %s ORDER BY standing, recorded_at DESC''',
                            (installation.scope.org_id, proposal_id)).fetchall()
    return {r['standing']: dict(r) for r in rows}

