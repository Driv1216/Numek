"""The CG7 operations API (plan J "API", C.6, H.10).

``/api/ops/v1`` uses the ConfidenceGuard envelope:
- success: ``{"data": ...}``;
- failure: ``{"error": {"code", "message"}}``, with mapped HTTP statuses.

**Authentication** is one of:
- a server-side session (``POST /session`` with a name and password). The cookie is ``numek_session``:
  HttpOnly, SameSite=Strict, and Secure under TLS. Sessions have idle and absolute timeouts and rotate on login.
  Mutating requests carry ``X-CSRF-Token``.
- a scoped API token (``Authorization: Bearer nmk_...``). Tokens only narrow their principal's roles.

**Authorization.** Every route declares a permission and a resource scope, recorded in ``ROUTES``:

| Permission | Covers |
|---|---|
| ``read`` | views |
| ``operate`` | acknowledging, assigning, suppressing, declaring execution |
| ``analyze`` | definitions, investigations, proposals |
| ``intervention:approve`` | approving or rejecting proposals; records only |
| ``reserve:consume`` | approving restricted investigations |
| ``admin`` | registry, channels, retention |

Principals of another organisation are refused. ``ROUTES`` also produces the OpenAPI document at
``GET /api/ops/v1/openapi.json``.

**Health.** ``/healthz`` and ``/readyz`` check the database, the controller leader and queue age. ``/metrics``
exposes Prometheus text. Request bodies and evidence values are never logged.
"""
import contextlib
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from ..contracts import EvaluationError

PREFIX = '/api/ops/v1'
# The console loads only its own bundle and talks only to this API: no external hosts, no framing.
CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; "
       "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
COOKIE = 'numek_session'
STATUS = {'unauthenticated': 401, 'forbidden': 403, 'csrf_failed': 403, 'separation_of_duties': 403, 'not_found': 404,
          'unknown_deployment': 404, 'unknown_source': 404, 'incident_unknown': 404, 'proposal_unknown': 404, 'definition_unknown': 404,
          'reference_unknown': 404, 'handoff_unknown': 404, 'stale_revision': 409, 'stale_confirmation': 409, 'incident_transition': 409,
          'proposal_transition': 409, 'run_state': 409, 'registration_conflict': 409, 'definition_state': 409,
          'self_lockout': 409, 'login_throttled': 429, 'principal_unknown': 404, 'token_unknown': 404, 'weak_password': 422, 'invalid_scope': 422,
          'invalid_principal': 422, 'invalid_egress': 422, 'recovery_evidence_required': 422, 'prerequisites_unmet': 422, 'evidence_not_independent': 422, 'platform_unavailable': 503, 'storage_full': 507}
ROUTES = []


def route(method, path, permission, scope=None, summary=''):
    """Declare a route: permission and the resource scope (``deployment`` or ``system`` from a path parameter)."""
    def decorate(fn):
        ROUTES.append({'method': method, 'path': path, 'permission': permission, 'scope': scope, 'summary': summary or fn.__doc__ or '',
                       'handler': fn})
        return fn
    return decorate


def _now():
    return datetime.now(timezone.utc)


def _when(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')) if value else _now()


def openapi():
    paths = {}
    for r in ROUTES:
        item = paths.setdefault(PREFIX + r['path'].replace('<', '{').replace('>', '}'), {})
        item[r['method'].lower()] = {'summary': r['summary'].strip().split('\n')[0], 'x-permission': r['permission'],
                                     'x-scope': r['scope'] or 'org',
                                     'responses': {'200': {'description': 'Envelope {"data": ...}'},
                                                   'default': {'description': 'Envelope {"error": {"code", "message"}}'}}}
    return {'openapi': '3.1.0', 'info': {'title': 'NUMEK ConfidenceGuard operations API', 'version': '1'},
            'components': {'securitySchemes': {'session': {'type': 'apiKey', 'in': 'cookie', 'name': COOKIE},
                                               'token': {'type': 'http', 'scheme': 'bearer'}}},
            'security': [{'session': []}, {'token': []}], 'paths': dict(sorted(paths.items()))}


# Handlers ----------------------------------------------------------------------------------------------------
# Each handler receives (installation, auth, body, query, **path) and returns JSON-serializable data.

@route('GET', '/session', 'read', summary='The authenticated principal and its organisation permissions.')
def whoami(installation, auth, body, query):
    from numek_platform import identity
    with installation.db.connect() as conn:
        granted = sorted(identity.permissions(conn, auth))
    return {'principal': {'id': str(auth.principal.id), 'name': auth.principal.name, 'kind': auth.principal.kind}, 'via': auth.via,
            'permissions': granted}


@route('GET', '/systems', 'read', summary='Registered systems.')
def systems(installation, auth, body, query):
    with installation.db.connect() as conn:
        return [dict(r) for r in conn.execute('SELECT id, name, namespace, created_at FROM ops_systems WHERE org_id = %s ORDER BY id',
                                              (installation.scope.org_id,)).fetchall()]


@route('POST', '/systems', 'admin', summary='Register a system (one evidence catalog).')
def register_system(installation, auth, body, query):
    from . import registry
    return registry.register_system(installation, body['id'], body['name'], namespace=body['namespace'])


@route('GET', '/deployments', 'read', summary='Registered deployments.')
def deployments(installation, auth, body, query):
    with installation.db.connect() as conn:
        return [dict(r) for r in conn.execute('SELECT id, system_id, name, tier, registered_identity, created_at FROM ops_deployments '
                                              'WHERE org_id = %s ORDER BY id', (installation.scope.org_id,)).fetchall()]


@route('POST', '/deployments', 'admin', summary='Register a deployment.')
def register_deployment(installation, auth, body, query):
    from . import registry
    return registry.register_deployment(installation, body['system'], body['id'], body['name'], tier=body.get('tier', 2),
                                        registered_identity=body.get('registered_identity'),
                                        attestation_public_key=body.get('attestation_public_key'))


@route('POST', '/deployments/<deployment>/sources', 'admin', 'deployment', summary='Register or version a source contract.')
def register_source(installation, auth, body, query, deployment):
    from . import registry
    return registry.register_source(installation, deployment, body['id'], body['contract'])


@route('GET', '/deployments/<deployment>/definitions', 'read', 'deployment', summary='Definition versions.')
def definitions_list(installation, auth, body, query, deployment):
    with installation.db.connect() as conn:
        return [dict(r) for r in conn.execute('SELECT version, state, spec, spec_digest, inspection, inspection_digest, created_at, confirmed_at, '
                                              'confirmed_by FROM ops_monitoring_definitions WHERE org_id = %s AND deployment_id = %s ORDER BY version',
                                              (installation.scope.org_id, deployment)).fetchall()]


@route('POST', '/deployments/<deployment>/definitions', 'analyze', 'deployment', summary='Inspect a definition (records a new version).')
def definition_inspect(installation, auth, body, query, deployment):
    from .monitoring import definitions
    return definitions.inspect(installation, deployment, body['spec'])


@route('POST', '/deployments/<deployment>/definitions/<version>/confirm', 'analyze', 'deployment',
       summary='Confirm an inspected version exactly as inspected.')
def definition_confirm(installation, auth, body, query, deployment, version):
    from .monitoring import definitions
    return definitions.confirm(installation, deployment, int(version), body['inspection_digest'], actor=_actor(auth))


@route('GET', '/deployments/<deployment>/health', 'read', 'deployment', summary='Monitoring health and the coverage map.')
def health(installation, auth, body, query, deployment):
    from .monitoring import health as health_rules
    return health_rules.report(installation, deployment)


@route('GET', '/deployments/<deployment>/detectors', 'read', 'deployment', summary='Detectors, standings and power.')
def detectors(installation, auth, body, query, deployment):
    with installation.db.connect() as conn:
        return [dict(r) for r in conn.execute(
            '''SELECT d.detector_id, d.kind, d.phase, d.standing, d.units, d.alarms, d.late_excluded, d.cursor_window, d.definition_version,
                      d.plan FROM ops_detectors d JOIN ops_monitoring_definitions m ON m.org_id = d.org_id AND m.deployment_id = d.deployment_id
                      AND m.version = d.definition_version AND m.state = 'confirmed' WHERE d.org_id = %s AND d.deployment_id = %s
               ORDER BY d.detector_id''', (installation.scope.org_id, deployment)).fetchall()]


@route('GET', '/deployments/<deployment>/signals', 'read', 'deployment', summary='Signals (cursor = created_at of the last item).')
def signals(installation, auth, body, query, deployment):
    limit = min(int(query.get('limit', 100)), 500)
    with installation.db.connect() as conn:
        rows = conn.execute('''SELECT id, source, source_id, window_index, standing, severity, payload, created_at FROM ops_signals
                               WHERE org_id = %s AND deployment_id = %s AND (%s::timestamptz IS NULL OR created_at < %s::timestamptz)
                               ORDER BY created_at DESC LIMIT %s''',
                            (installation.scope.org_id, deployment, query.get('cursor'), query.get('cursor'), limit)).fetchall()
    return {'items': [dict(r) for r in rows], 'cursor': rows[-1]['created_at'].isoformat() if len(rows) == limit else None}


@route('GET', '/deployments/<deployment>/identity', 'read', 'deployment', summary='Identity standings: latest per standing, and the recent history.')
def identity_standings(installation, auth, body, query, deployment):
    with installation.db.connect() as conn:
        latest = [dict(r) for r in conn.execute(
            '''SELECT DISTINCT ON (standing) standing, outcome, evidence, period_start, period_end, recorded_at FROM ops_identity_standings
               WHERE org_id = %s AND deployment_id = %s ORDER BY standing, recorded_at DESC''', (installation.scope.org_id, deployment)).fetchall()]
        history = [dict(r) for r in conn.execute(
            '''SELECT standing, outcome, recorded_at FROM ops_identity_standings WHERE org_id = %s AND deployment_id = %s
               ORDER BY recorded_at DESC LIMIT 50''', (installation.scope.org_id, deployment)).fetchall()]
        registered = conn.execute('SELECT registered_identity FROM ops_deployments WHERE org_id = %s AND id = %s',
                                  (installation.scope.org_id, deployment)).fetchone()
    order = ['declared', 'registered', 'spec_compatible', 'sampled_output_consistent', 'customer_signed_statement_verified']
    latest.sort(key=lambda r: order.index(r['standing']) if r['standing'] in order else 99)
    return {'ladder': order, 'latest': latest, 'history': history,
            'registered_identity': None if registered is None else registered['registered_identity'],
            'qualification': 'Each standing is separate; agreement on sampled outputs is not attestation.'}


@route('GET', '/deployments/<deployment>/estimates', 'read', 'deployment', summary='The estimator accountability ledger.')
def estimates(installation, auth, body, query, deployment):
    from .monitoring import estimators
    with installation.db.connect() as conn:
        rows = [dict(r) for r in conn.execute(
            '''SELECT s.estimator, s.window_index, s.value, s.population, s.record, s.matched FROM ops_estimates s
               JOIN ops_monitoring_definitions m ON m.org_id = s.org_id AND m.deployment_id = s.deployment_id
                    AND m.version = s.definition_version AND m.state = 'confirmed'
               WHERE s.org_id = %s AND s.deployment_id = %s ORDER BY s.estimator, s.window_index''',
            (installation.scope.org_id, deployment)).fetchall()]
    out = {}
    for name in sorted({r['estimator'] for r in rows}):
        mine = [r for r in rows if r['estimator'] == name]
        out[name] = {'assumption': estimators.ESTIMATORS[name]['assumption'], 'summary': estimators.ledger_summary(mine),
                     'windows': [{'window': r['window_index'], 'value': r['value'], 'population': r['population'],
                                  'matched_estimate': (r['matched'] or {}).get('matched_estimate'),
                                  'realized': (r['matched'] or {}).get('realized'),
                                  'realized_interval': (r['matched'] or {}).get('realized_interval'),
                                  'coverage': (r['matched'] or {}).get('coverage'),
                                  'exceedance': (r['matched'] or {}).get('exceedance')} for r in mine]}
    return {'estimators': out, 'standing': 'E', 'qualification': 'Historical accuracy of an estimator does not establish its assumptions hold now.'}


@route('GET', '/deployments/<deployment>/windows', 'read', 'deployment', summary='Recent window evaluations (units, label availability, region shares).')
def window_series(installation, auth, body, query, deployment):
    from .monitoring import packets
    limit = min(int(query.get('limit', 26)), 104)
    with installation.db.connect() as conn:
        rows = [dict(r) for r in conn.execute(
            '''SELECT DISTINCT ON (e.window_index, e.phase) e.window_index, e.phase, e.revision, e.units, e.start_tick, e.end_tick,
                      e.closure, e.catalog_sequence, e.reproducibility, e.packet_object
               FROM ops_window_evaluations e JOIN ops_monitoring_definitions m ON m.org_id = e.org_id AND m.deployment_id = e.deployment_id
                    AND m.version = e.definition_version AND m.state = 'confirmed'
               WHERE e.org_id = %s AND e.deployment_id = %s ORDER BY e.window_index DESC, e.phase, e.revision DESC''',
            (installation.scope.org_id, deployment)).fetchall()]
    windows = sorted({r['window_index'] for r in rows}, reverse=True)[:limit]
    out = []
    for index in sorted(windows):
        item = {'window': index}
        for r in (r for r in rows if r['window_index'] == index):
            packet = packets.read(installation, r['packet_object'])
            item[r['phase']] = {'units': r['units'], 'revision': r['revision'], 'closure': r['closure'], 'reproducibility': r['reproducibility'],
                                'label_availability_rate': packet.get('label_availability_rate'),
                                'region_shares': packet.get('region_shares') or {}, 'start': packet.get('start'), 'end': packet.get('end')}
        out.append(item)
    return {'windows': out}


@route('GET', '/deployments/<deployment>/sources', 'read', 'deployment',
       summary='Sources: contract, watermark, ingestion funnel, quarantine reasons (never values) and recent batches.')
def sources(installation, auth, body, query, deployment):
    from . import ingest
    from .monitoring import definitions
    limit = min(int(query.get('limit', 20)), 100)
    current = definitions.confirmed(installation, deployment)
    lateness = (current or {}).get('spec', {}).get('allowed_lateness_ns')
    out = []
    with installation.db.connect() as conn:
        rows = conn.execute("SELECT id, version, contract, contract_digest, created_at FROM ops_sources "
                            "WHERE org_id = %s AND deployment_id = %s AND state = 'active' ORDER BY id",
                            (installation.scope.org_id, deployment)).fetchall()
        for src in rows:
            mark = conn.execute('SELECT through_tick, updated_at FROM ops_watermarks WHERE org_id = %s AND source_id = %s',
                                (installation.scope.org_id, src['id'])).fetchone()
            reasons = [dict(r) for r in conn.execute(
                '''SELECT r.reason, count(*) AS rows, array_agg(DISTINCT f.field) FILTER (WHERE f.field IS NOT NULL) AS fields
                   FROM ops_quarantine q JOIN ops_batches b ON b.id = q.batch
                   CROSS JOIN LATERAL unnest(q.reasons) AS r(reason)
                   LEFT JOIN LATERAL unnest(q.fields) AS f(field) ON true
                   WHERE b.org_id = %s AND b.source_id = %s GROUP BY r.reason ORDER BY count(*) DESC, r.reason''',
                (installation.scope.org_id, src['id'])).fetchall()]
            batches = [{'batch_id': b['batch_id'], 'state': b['state'], 'mode': b['mode'], 'contract_version': b['contract_version'],
                        'raw_bytes': b['raw_bytes'], 'producer_dropped': b['producer_dropped'], 'catalog_sequence': b['catalog_sequence'],
                        'counts': {k: v for k, v in (b['counts'] or {}).items() if k != 'watermark_at_receipt'},
                        'error': (b['error'] or {}).get('code') if isinstance(b['error'], dict) else None,
                        'received_at': b['received_at'], 'finished_at': b['finished_at']}
                       for b in conn.execute('''SELECT batch_id, state, mode, contract_version, raw_bytes, producer_dropped, catalog_sequence,
                                                       counts, error, received_at, finished_at FROM ops_batches
                                                WHERE org_id = %s AND source_id = %s ORDER BY received_at DESC LIMIT %s''',
                                             (installation.scope.org_id, src['id'], limit)).fetchall()]
            contract = src['contract']
            out.append({'source': src['id'], 'contract_version': src['version'], 'contract_digest': src['contract_digest'],
                        'registered_at': src['created_at'], 'format': contract.get('format'), 'event_time': contract.get('event_time'),
                        'fields': {name: {k: v for k, v in spec.items() if k in ('type', 'required', 'identity', 'probability')}
                                   for name, spec in (contract.get('fields') or {}).items()},
                        'watermark': None if mark is None else {'through_tick': str(int(mark['through_tick'])), 'updated_at': mark['updated_at']},
                        'funnel': ingest.funnel(installation, src['id']), 'quarantine_reasons': reasons, 'batches': batches})
    return {'deployment': deployment, 'allowed_lateness_ns': lateness, 'sources': out,
            'qualification': 'Quarantine records reasons and field names only; values are held encrypted and never shown. '
                             'Late rows arrived at or before the watermark declared when their batch was received.'}


@route('POST', '/deployments/<deployment>/cycle', 'operate', 'deployment', summary='Queue a monitoring cycle (worker hosts run it).')
def cycle(installation, auth, body, query, deployment):
    from numek_platform.execution import jobs
    with installation.db.transaction() as conn:
        row = jobs.enqueue(conn, installation.scope, 'ops_monitoring_cycle', idempotency_key=f'ops-cycle:{deployment}:api:{uuid.uuid4().hex}',
                           payload={'installation': str(installation.root), 'deployment': deployment})
    return {'job': str(row['id']), 'state': row['state']}


@route('GET', '/deployments/<deployment>/conditions', 'read', 'deployment', summary='Conditions of a deployment.')
def conditions(installation, auth, body, query, deployment):
    with installation.db.connect() as conn:
        return [dict(r) for r in conn.execute('''SELECT id, key, kind, standing, severity, state, first_window, last_window, signal_count,
                                                        first_signal_at, last_signal_at, recovery FROM ops_conditions
                                                 WHERE org_id = %s AND deployment_id = %s ORDER BY created_at DESC''',
                                              (installation.scope.org_id, deployment)).fetchall()]


@route('POST', '/conditions/<condition>/suppress', 'operate', summary='Suppress a condition with a reason and an expiry.')
def suppress(installation, auth, body, query, condition):
    from .incidents import conditions as rules
    rules.suppress(installation, uuid.UUID(condition), reason=body.get('reason'), until=_when(body.get('until')), actor=_actor(auth))
    return {'condition': condition, 'state': 'suppressed'}


@route('GET', '/incidents', 'read', summary='Incidents (filter by state or deployment; cursor = number).')
def incidents_list(installation, auth, body, query):
    limit = min(int(query.get('limit', 50)), 200)
    with installation.db.connect() as conn:
        rows = conn.execute('''SELECT id, number, deployment_id, state, priority, priority_basis->>'rule' AS rule, owner, opened_at, resolved_at,
                                      resolution, escalation_level FROM ops_incidents WHERE org_id = %s
                               AND (%s::text IS NULL OR state = %s) AND (%s::text IS NULL OR deployment_id = %s)
                               AND (%s::bigint IS NULL OR number < %s) ORDER BY number DESC LIMIT %s''',
                            (installation.scope.org_id, query.get('state'), query.get('state'), query.get('deployment'), query.get('deployment'),
                             query.get('cursor'), query.get('cursor'), limit)).fetchall()
    _require_deployment_reads(installation, auth, {r['deployment_id'] for r in rows})
    return {'items': [dict(r) for r in rows], 'cursor': rows[-1]['number'] if len(rows) == limit else None}


@route('GET', '/incidents/<incident>', 'read', 'incident', summary="An incident: 'as known at detection' or now (as_known=detection|now).")
def incident(installation, auth, body, query, incident):
    from .incidents import incidents as rules
    return rules.view(installation, uuid.UUID(incident), as_known=query.get('as_known', 'now'))


@route('POST', '/incidents/<incident>/transition', 'operate', 'incident', summary='Move an incident along its lifecycle.')
def incident_transition(installation, auth, body, query, incident):
    from .incidents import incidents as rules
    return rules.transition(installation, uuid.UUID(incident), body['to'], actor=_actor(auth), expected_revision=body.get('expected_revision'),
                            resolution=body.get('resolution'), reason=body.get('reason'))


@route('POST', '/incidents/<incident>/assign', 'operate', 'incident', summary='Assign an owner.')
def incident_assign(installation, auth, body, query, incident):
    from .incidents import incidents as rules
    rules.assign(installation, uuid.UUID(incident), body['owner'], actor=_actor(auth), expected_revision=body.get('expected_revision'))
    return {'incident': incident, 'owner': body['owner']}


@route('POST', '/incidents/<incident>/priority', 'operate', 'incident', summary='Override the priority with a reason.')
def incident_priority(installation, auth, body, query, incident):
    from .incidents import incidents as rules
    rules.set_priority(installation, uuid.UUID(incident), body['priority'], reason=body.get('reason'), actor=_actor(auth),
                       expected_revision=body.get('expected_revision'))
    return {'incident': incident, 'priority': body['priority']}


@route('POST', '/incidents/<incident>/merge', 'operate', 'incident', summary='Merge another incident into this one (audited).')
def incident_merge(installation, auth, body, query, incident):
    from .incidents import incidents as rules
    return rules.merge(installation, uuid.UUID(incident), uuid.UUID(body['source']), reason=body.get('reason'), actor=_actor(auth))


@route('POST', '/incidents/<incident>/split', 'operate', 'incident', summary='Split conditions into a new incident (audited).')
def incident_split(installation, auth, body, query, incident):
    from .incidents import incidents as rules
    return rules.split(installation, uuid.UUID(incident), [uuid.UUID(c) for c in body['conditions']], reason=body.get('reason'),
                       actor=_actor(auth))


@route('GET', '/incidents/<incident>/hypotheses', 'read', 'incident', summary='Hypothesis states and requirements.')
def incident_hypotheses(installation, auth, body, query, incident):
    with installation.db.connect() as conn:
        states = [dict(r) for r in conn.execute('SELECT hypothesis_id, state, reason, evidence, knowledge_revision FROM ops_hypotheses '
                                                'WHERE org_id = %s AND incident_id = %s ORDER BY hypothesis_id',
                                                (installation.scope.org_id, uuid.UUID(incident))).fetchall()]
        requirements = [dict(r) for r in conn.execute('SELECT observation, status, reason, eta, action, hypotheses, template, triggered_run '
                                                      'FROM ops_requirements WHERE org_id = %s AND incident_id = %s ORDER BY observation',
                                                      (installation.scope.org_id, uuid.UUID(incident))).fetchall()]
    return {'hypotheses': states, 'requirements': requirements}


@route('GET', '/incidents/<incident>/similar', 'read', 'incident', summary='Recurring patterns: similar resolved incidents.')
def incident_similar(installation, auth, body, query, incident):
    from .intelligence import patterns
    return patterns.similar(installation, uuid.UUID(incident))


@route('GET', '/incidents/<incident>/report', 'read', 'incident', summary='The incident report (format=json|html; audience=local|shareable).')
def incident_report(installation, auth, body, query, incident):
    from . import reports
    audience = query.get('audience', 'shareable')
    if audience == 'local':
        _require(installation, auth, 'evidence:protected:read', 'incident', incident)
    data = reports.incident_data(installation, uuid.UUID(incident), audience=audience)
    if query.get('format') == 'html':
        return RawResponse(reports.render(data), 'text/html; charset=utf-8')
    return data


@route('POST', '/incidents/<incident>/investigations', 'analyze', 'incident', summary='Plan discriminating investigations.')
def incident_plan(installation, auth, body, query, incident):
    from .intelligence import planner
    return planner.plan(installation, uuid.UUID(incident), now=_now(), only=body.get('only'), actor=_actor(auth))


@route('GET', '/incidents/<incident>/investigations', 'read', 'incident', summary='Investigation runs of an incident.')
def incident_runs(installation, auth, body, query, incident):
    with installation.db.connect() as conn:
        return [dict(r) for r in conn.execute('''SELECT id, template, tier, state, value, cost_minutes, reasoning, reused_from, stale_fraction,
                                                        approved_by, result, error, created_at, finished_at FROM ops_investigation_runs
                                                 WHERE org_id = %s AND incident_id = %s ORDER BY created_at''',
                                              (installation.scope.org_id, uuid.UUID(incident))).fetchall()]


@route('GET', '/investigations', 'read', summary='Investigation runs across incidents (filter by state, tier or deployment).')
def runs_list(installation, auth, body, query):
    limit = min(int(query.get('limit', 100)), 200)
    with installation.db.connect() as conn:
        rows = conn.execute('''SELECT r.id, r.incident_id, i.number AS incident_number, i.priority, r.deployment_id, r.template, r.tier, r.state,
                                      r.value, r.cost_minutes, r.reasoning, r.reused_from, r.stale_fraction, r.approved_by, r.result, r.error,
                                      r.created_at, r.finished_at
                               FROM ops_investigation_runs r JOIN ops_incidents i ON i.org_id = r.org_id AND i.id = r.incident_id
                               WHERE r.org_id = %s AND (%s::text IS NULL OR r.state = %s) AND (%s::text IS NULL OR r.tier = %s)
                               AND (%s::text IS NULL OR r.deployment_id = %s) ORDER BY r.created_at DESC LIMIT %s''',
                            (installation.scope.org_id, query.get('state'), query.get('state'), query.get('tier'), query.get('tier'),
                             query.get('deployment'), query.get('deployment'), limit)).fetchall()
    _require_deployment_reads(installation, auth, {r['deployment_id'] for r in rows})
    return {'items': [dict(r) for r in rows]}


@route('POST', '/investigations/<run>/approve', 'analyze', 'run', summary='Approve a confirm or restricted run (restricted needs reserve:consume).')
def run_approve(installation, auth, body, query, run):
    from numek_platform import identity
    from .intelligence import planner
    with installation.db.connect() as conn:
        granted = identity.permissions(conn, auth)
    return planner.approve(installation, uuid.UUID(run), actor=_actor(auth), permissions=granted, spec=body.get('spec'), now=_now())


@route('POST', '/investigations/<run>/execute', 'analyze', 'run', summary='Queue a planned run for the worker hosts.')
def run_execute(installation, auth, body, query, run):
    from .intelligence import planner
    return planner.enqueue(installation, uuid.UUID(run))


@route('POST', '/incidents/<incident>/proposals', 'analyze', 'incident', summary='Draft a response proposal.')
def proposal_create(installation, auth, body, query, incident):
    from .interventions import proposals
    fields = {k: body[k] for k in ('title', 'change', 'verification_plan', 'evidence', 'effects', 'expected_identity', 'risks',
                                   'prerequisites', 'required_role') if k in body}
    return proposals.create(installation, uuid.UUID(incident), body['kind'], author=_actor(auth), **fields)


@route('GET', '/incidents/<incident>/proposals', 'read', 'incident', summary='The response comparison.')
def proposal_compare(installation, auth, body, query, incident):
    from .interventions import proposals
    return proposals.compare(installation, uuid.UUID(incident))


@route('GET', '/proposals', 'read', summary='Proposals across incidents (filter by state or deployment).')
def proposals_list(installation, auth, body, query):
    limit = min(int(query.get('limit', 100)), 200)
    with installation.db.connect() as conn:
        rows = conn.execute('''SELECT p.id, p.incident_id, i.number AS incident_number, i.priority, p.deployment_id, p.kind, p.title, p.state,
                                      p.author, p.required_role, p.evidence, p.revision, p.created_at, p.updated_at
                               FROM ops_proposals p JOIN ops_incidents i ON i.org_id = p.org_id AND i.id = p.incident_id
                               WHERE p.org_id = %s AND (%s::text IS NULL OR p.state = %s) AND (%s::text IS NULL OR p.deployment_id = %s)
                               ORDER BY p.updated_at DESC LIMIT %s''',
                            (installation.scope.org_id, query.get('state'), query.get('state'), query.get('deployment'), query.get('deployment'),
                             limit)).fetchall()
    _require_deployment_reads(installation, auth, {r['deployment_id'] for r in rows})
    items = []
    for r in rows:
        item = dict(r)
        bases = sorted({e['basis'] for e in (item.pop('evidence') or {}).get('items', [])})
        item['evidence_basis'] = bases
        items.append(item)
    return {'items': items}


@route('GET', '/proposals/<proposal>', 'read', 'proposal', summary='A proposal with its standings and verification.')
def proposal_get(installation, auth, body, query, proposal):
    from .interventions import execution, proposals
    pid = uuid.UUID(proposal)
    with installation.db.connect() as conn:
        claims = [dict(r) for r in conn.execute('SELECT claim_id, claim, state, start_window, detector_id, result FROM ops_verifications '
                                                'WHERE org_id = %s AND proposal_id = %s ORDER BY claim_id', (installation.scope.org_id, pid)).fetchall()]
    return {'proposal': proposals.get(installation, pid), 'standings': execution.standings(installation, pid), 'verification': claims}


@route('POST', '/proposals/<proposal>/submit', 'analyze', 'proposal', summary='Submit (prerequisites are checked).')
def proposal_submit(installation, auth, body, query, proposal):
    from .interventions import proposals
    return proposals.submit(installation, uuid.UUID(proposal), actor=_actor(auth), now=_now())


@route('POST', '/proposals/<proposal>/decision', 'intervention:approve', 'proposal', summary='Approve or reject (records only).')
def proposal_decide(installation, auth, body, query, proposal):
    from numek_platform import identity
    from .interventions import proposals
    with installation.db.connect() as conn:
        granted = identity.permissions(conn, auth)
    return proposals.decide(installation, uuid.UUID(proposal), body['decision'], actor=_actor(auth), permissions=granted,
                            reason=body.get('reason'), expected_revision=body.get('expected_revision'))


@route('POST', '/proposals/<proposal>/handoff', 'operate', 'proposal', summary='Issue the immutable execution handoff.')
def proposal_handoff(installation, auth, body, query, proposal):
    from .interventions import execution
    return execution.issue_handoff(installation, uuid.UUID(proposal), actor=_actor(auth), now=_now())


@route('GET', '/proposals/<proposal>/handoff', 'read', 'proposal', summary='The handoff packet (digest-verified).')
def proposal_handoff_get(installation, auth, body, query, proposal):
    from .interventions import execution
    return execution.handoff(installation, uuid.UUID(proposal))


@route('POST', '/proposals/<proposal>/execution', 'operate', 'proposal', summary='Declare that the customer executed the change.')
def proposal_execution(installation, auth, body, query, proposal):
    from .interventions import execution
    return execution.declare_execution(installation, uuid.UUID(proposal), executed_at=_when(body.get('executed_at')), actor=_actor(auth),
                                       detail=body.get('detail'), now=_now())


@route('POST', '/proposals/<proposal>/attestation', 'operate', 'proposal', summary='Verify a customer-signed execution statement.')
def proposal_attest(installation, auth, body, query, proposal):
    from .interventions import execution
    return execution.attest(installation, uuid.UUID(proposal), body['statement'], body['signature'], actor=_actor(auth))


@route('POST', '/proposals/<proposal>/standings/identity', 'operate', 'proposal', summary='Evaluate identity consistency with the handoff.')
def proposal_identity(installation, auth, body, query, proposal):
    from .interventions import execution
    return execution.identity_consistency(installation, uuid.UUID(proposal), actor=_actor(auth))


@route('POST', '/proposals/<proposal>/withdraw', 'analyze', 'proposal', summary='Withdraw a proposal.')
def proposal_withdraw(installation, auth, body, query, proposal):
    from .interventions import proposals
    proposals.withdraw(installation, uuid.UUID(proposal), actor=_actor(auth), reason=body.get('reason'))
    return {'proposal': proposal, 'state': 'withdrawn'}


@route('POST', '/channels', 'admin', summary='Register a notification channel (a webhook key is shown once).')
def channel_create(installation, auth, body, query):
    from .incidents import notify
    return notify.configure_channel(installation, body['id'], body['kind'], body['destination'], config=body.get('config'),
                                    credentials=body.get('credentials'), actor=_actor(auth))


@route('POST', '/rules', 'admin', summary='Add a notification rule.')
def rule_create(installation, auth, body, query):
    from .incidents import notify
    notify.add_rule(installation, body['id'], body['channel'], deployment_id=body.get('deployment'), min_priority=body.get('min_priority', 'P2'),
                    digest_seconds=body.get('digest_seconds'), quiet=body.get('quiet', ()), escalation_level=body.get('escalation_level', 0),
                    actor=_actor(auth))
    return {'rule': body['id']}


@route('POST', '/systems/<system>/pins', 'admin', 'system', summary='Pin an event-time range against retention (with an expiry).')
def pin_create(installation, auth, body, query, system):
    from .incidents import pins
    return {'pin': pins.pin(installation, system, body['start'], body['end'], reason=body['reason'], actor=_actor(auth),
                            expires_at=_when(body['expires_at']) if body.get('expires_at') else None)}


@route('POST', '/systems/<system>/retention', 'admin', 'system', summary='Set observation retention (days, at least 30).')
def retention_set(installation, auth, body, query, system):
    from .incidents import pins
    pins.set_policy(installation, system, int(body['observation_days']), actor=_actor(auth))
    return {'system': system, 'observation_days': int(body['observation_days'])}


# Administration ------------------------------------------------------------------------------------------------
# Every change is written to the hash-chained audit log in the transaction that makes it. Secrets (initial
# passwords, token secrets, webhook signing keys) are returned once and are never readable again.
def _principal(conn, installation, principal):
    """The principal named by a path or body id (disabled principals included, so an administrator can manage them)."""
    from numek_platform import identity
    row = conn.execute("SELECT id, kind, name FROM principals WHERE org_id = %s AND id = %s AND kind IN ('user', 'service')",
                       (installation.scope.org_id, _uuid(principal))).fetchone()
    if row is None:
        raise EvaluationError('Unknown principal.', 'principal_unknown')
    return identity.Principal(installation.scope.org_id, row['id'], row['kind'], row['name'])


def _enabled_admins(conn, installation, excluding=None):
    return conn.execute('''SELECT count(DISTINCT p.id) AS n FROM principals p JOIN role_bindings b ON b.org_id = p.org_id AND b.principal_id = p.id
                            WHERE p.org_id = %s AND NOT p.disabled AND b.role = 'admin' AND b.scope_kind = 'org'
                            AND (%s::uuid IS NULL OR p.id <> %s::uuid)''',
                        (installation.scope.org_id, excluding, excluding)).fetchone()['n']


@route('GET', '/principals', 'admin', summary='Principals with their role bindings and credential state (never secrets).')
def principals_list(installation, auth, body, query):
    with installation.db.connect() as conn:
        rows = conn.execute('''SELECT p.id, p.kind, p.name, p.disabled, p.created_at,
                                      EXISTS (SELECT 1 FROM password_credentials c WHERE c.org_id = p.org_id AND c.principal_id = p.id) AS has_password,
                                      (SELECT max(last_seen_at) FROM sessions s WHERE s.org_id = p.org_id AND s.principal_id = p.id) AS last_seen,
                                      (SELECT count(*) FROM api_tokens t WHERE t.org_id = p.org_id AND t.principal_id = p.id AND t.revoked_at IS NULL
                                              AND (t.expires_at IS NULL OR t.expires_at > now())) AS live_tokens,
                                      coalesce((SELECT jsonb_agg(jsonb_build_object('role', b.role, 'scope_kind', b.scope_kind, 'scope_id', b.scope_id)
                                                                 ORDER BY b.role, b.scope_kind, b.scope_id)
                                                FROM role_bindings b WHERE b.org_id = p.org_id AND b.principal_id = p.id), '[]') AS roles
                               FROM principals p WHERE p.org_id = %s AND p.kind IN ('user', 'service') ORDER BY p.kind, p.name''',
                            (installation.scope.org_id,)).fetchall()
    from numek_platform.identity import ROLE_PERMISSIONS, SERVICE_FORBIDDEN_ROLES
    return {'items': [dict(r) for r in rows], 'roles': {k: sorted(v) for k, v in ROLE_PERMISSIONS.items()},
            'service_forbidden_roles': sorted(SERVICE_FORBIDDEN_ROLES)}


@route('POST', '/principals', 'admin', summary='Create a user (an initial password is shown once) or a service principal (tokens only).')
def principal_create(installation, auth, body, query):
    import secrets as _secrets
    from numek_platform import identity
    from . import audit_action
    kind, name, roles = body['kind'], body['name'], list(body.get('roles') or [])
    if kind not in ('user', 'service'):
        raise EvaluationError('Principals are users or services.', 'invalid_principal')
    password = _secrets.token_urlsafe(18) if kind == 'user' else None
    with installation.db.transaction() as conn:
        principal = identity.create_principal(conn, installation.scope, kind, name)
        if password:
            identity.set_password(conn, installation.scope, principal, password)
        for role in roles:
            identity.bind_role(conn, installation.scope, principal, role)
        audit_action(conn, installation.scope, _actor(auth), 'principal.create', str(principal.id), {'kind': kind, 'name': name, 'roles': roles})
    return {'principal': str(principal.id), 'kind': kind, 'name': name, 'roles': roles, 'initial_password': password,
            'note': 'The initial password is shown once and stored only as an argon2id hash.' if password else
                    'Service principals have no password; issue a scoped token.'}


@route('POST', '/principals/<principal>/roles', 'admin', summary='Bind or unbind a role at org, system or deployment scope.')
def principal_roles(installation, auth, body, query, principal):
    from numek_platform import identity
    from . import audit_action
    action, role = body['action'], body['role']
    scope_kind, scope_id = body.get('scope_kind', 'org'), body.get('scope_id', '') if body.get('scope_kind', 'org') != 'org' else ''
    if action not in ('bind', 'unbind'):
        raise EvaluationError('The action is bind or unbind.', 'invalid_scope')
    with installation.db.transaction() as conn:
        target = _principal(conn, installation, principal)
        if action == 'bind':
            identity.bind_role(conn, installation.scope, target, role, scope_kind, scope_id)
        else:
            if role == 'admin' and scope_kind == 'org' and _enabled_admins(conn, installation, excluding=target.id) == 0:
                raise EvaluationError('This would leave the organisation without an enabled administrator.', 'self_lockout')
            conn.execute('DELETE FROM role_bindings WHERE org_id = %s AND principal_id = %s AND role = %s AND scope_kind = %s AND scope_id = %s',
                         (installation.scope.org_id, target.id, role, scope_kind, scope_id))
        audit_action(conn, installation.scope, _actor(auth), f'principal.role.{action}', str(target.id),
                     {'role': role, 'scope_kind': scope_kind, 'scope_id': scope_id})
    return {'principal': principal, 'action': action, 'role': role, 'scope_kind': scope_kind, 'scope_id': scope_id}


@route('POST', '/principals/<principal>/disable', 'admin', summary='Disable or re-enable a principal (disabling revokes its sessions and tokens).')
def principal_disable(installation, auth, body, query, principal):
    from . import audit_action
    disabled = bool(body['disabled'])
    with installation.db.transaction() as conn:
        row = {'id': _principal(conn, installation, principal).id}
        if disabled and _enabled_admins(conn, installation, excluding=row['id']) == 0:
            raise EvaluationError('This would leave the organisation without an enabled administrator.', 'self_lockout')
        conn.execute('UPDATE principals SET disabled = %s WHERE org_id = %s AND id = %s', (disabled, installation.scope.org_id, row['id']))
        if disabled:
            conn.execute('UPDATE sessions SET revoked_at = now() WHERE org_id = %s AND principal_id = %s AND revoked_at IS NULL',
                         (installation.scope.org_id, row['id']))
            conn.execute('UPDATE api_tokens SET revoked_at = now() WHERE org_id = %s AND principal_id = %s AND revoked_at IS NULL',
                         (installation.scope.org_id, row['id']))
        audit_action(conn, installation.scope, _actor(auth), 'principal.disable' if disabled else 'principal.enable', str(row['id']), {})
    return {'principal': principal, 'disabled': disabled}


@route('POST', '/principals/<principal>/password', 'admin', summary="Reset a user's password (the new one is shown once; sessions are revoked).")
def principal_password_reset(installation, auth, body, query, principal):
    import secrets as _secrets
    from numek_platform import identity
    from . import audit_action
    password = _secrets.token_urlsafe(18)
    with installation.db.transaction() as conn:
        target = _principal(conn, installation, principal)
        identity.set_password(conn, installation.scope, target, password)
        conn.execute('UPDATE sessions SET revoked_at = now() WHERE org_id = %s AND principal_id = %s AND revoked_at IS NULL',
                     (installation.scope.org_id, target.id))
        audit_action(conn, installation.scope, _actor(auth), 'principal.password.reset', str(target.id), {})
    return {'principal': principal, 'password': password, 'note': 'Shown once. The user should change it after signing in.'}


@route('POST', '/session/password', 'read', summary='Change your own password (needs the current one; other sessions are revoked).')
def own_password(installation, auth, body, query):
    from numek_platform import identity
    from numek_platform.errors import PlatformError
    from . import audit_action
    if auth.via != 'session' or auth.principal.kind != 'user':
        raise EvaluationError('Only a signed-in user can change a password.', 'invalid_principal')
    with installation.db.transaction() as conn:
        try:
            identity.verify_password(conn, installation.scope, auth.principal.name, body['current'])
        except PlatformError:
            raise EvaluationError('The current password is not correct.', 'forbidden') from None
        identity.set_password(conn, installation.scope, auth.principal, body['new'])
        conn.execute('UPDATE sessions SET revoked_at = now() WHERE org_id = %s AND principal_id = %s AND revoked_at IS NULL AND id <> %s',
                     (installation.scope.org_id, auth.principal.id, auth.session_id))
        audit_action(conn, installation.scope, _actor(auth), 'principal.password.change', str(auth.principal.id), {})
    return {'changed': True}


@route('GET', '/tokens', 'admin', summary='API tokens: scopes, expiry, revocation and last use (never secrets).')
def tokens_list(installation, auth, body, query):
    with installation.db.connect() as conn:
        return {'items': [dict(r) for r in conn.execute(
            '''SELECT t.id, p.name AS principal, p.kind, t.scopes, t.created_at, t.expires_at, t.revoked_at, t.last_used_at,
                      t.expires_at IS NOT NULL AND t.expires_at <= now() AS expired
               FROM api_tokens t JOIN principals p ON p.org_id = t.org_id AND p.id = t.principal_id
               WHERE t.org_id = %s ORDER BY t.created_at DESC''', (installation.scope.org_id,)).fetchall()]}


@route('POST', '/tokens', 'admin', summary="Issue a scoped token ('role:<role>', 'ingest:source:<id>', 'read:deployment:<id>'); shown once.")
def token_issue(installation, auth, body, query):
    from numek_platform import identity
    from . import audit_action
    scopes = list(body['scopes'])
    expires = body.get('expires_in_days')
    with installation.db.transaction() as conn:
        target = _principal(conn, installation, body['principal'])
        secret, token_id = identity.issue_token(conn, installation.scope, target, scopes,
                                                expires_in=None if expires in (None, '') else f'{int(expires)} days')
        audit_action(conn, installation.scope, _actor(auth), 'token.issue', str(token_id), {'principal': target.name, 'scopes': scopes,
                                                                                           'expires_in_days': expires})
    return {'token': secret, 'id': str(token_id), 'note': 'Shown once; stored only as a hash.'}


@route('POST', '/tokens/<token>/revoke', 'admin', summary='Revoke a token.')
def token_revoke(installation, auth, body, query, token):
    from numek_platform import identity
    from . import audit_action
    with installation.db.transaction() as conn:
        row = conn.execute('SELECT id FROM api_tokens WHERE org_id = %s AND id = %s', (installation.scope.org_id, _uuid(token))).fetchone()
        if row is None:
            raise EvaluationError('Unknown token.', 'token_unknown')
        identity.revoke_token(conn, installation.scope, row['id'])
        audit_action(conn, installation.scope, _actor(auth), 'token.revoke', str(row['id']), {})
    return {'token': token, 'revoked': True}


@route('GET', '/channels', 'admin', summary='Notification channels and rules (credentials stay in the secrets store).')
def channels_list(installation, auth, body, query):
    with installation.db.connect() as conn:
        channels = [dict(r) for r in conn.execute('SELECT id, kind, destination, config, enabled, created_at FROM ops_notification_channels '
                                                  'WHERE org_id = %s ORDER BY id', (installation.scope.org_id,)).fetchall()]
        rules = [dict(r) for r in conn.execute('SELECT id, channel_id, deployment_id, min_priority, digest_seconds, quiet, escalation_level '
                                               'FROM ops_notification_rules WHERE org_id = %s ORDER BY id', (installation.scope.org_id,)).fetchall()]
        outbox = {r['state']: r['n'] for r in conn.execute('SELECT state, count(*) AS n FROM ops_notification_outbox WHERE org_id = %s GROUP BY state',
                                                           (installation.scope.org_id,)).fetchall()}
    return {'channels': channels, 'rules': rules, 'outbox': outbox}


@route('GET', '/egress', 'admin', summary='The egress allowlist (notifications may reach only these destinations).')
def egress_list(installation, auth, body, query):
    with installation.db.connect() as conn:
        return {'items': [{**dict(r), 'cidr': None if r['cidr'] is None else str(r['cidr'])} for r in conn.execute(
            'SELECT id, scheme, host, port, cidr, created_at FROM egress_allowlist WHERE org_id = %s ORDER BY host, port',
            (installation.scope.org_id,)).fetchall()],
            'statement': 'Destinations are resolved and the resolved address is checked; link-local, metadata and loopback ranges are '
                         'refused unless an entry names them. Redirects are never followed.'}


@route('POST', '/egress', 'admin', summary='Allow a destination (scheme, host, port; optional CIDR the resolved address must fall in).')
def egress_add(installation, auth, body, query):
    import ipaddress
    from numek_platform.egress import DEFAULT_PORTS
    from . import audit_action
    scheme, host = str(body['scheme']).lower(), str(body['host']).strip().lower()
    if scheme not in DEFAULT_PORTS or not host or '/' in host or ' ' in host:
        raise EvaluationError('An entry is a scheme (https, http, smtps, smtp), a host and a port.', 'invalid_egress')
    port = int(body.get('port') or DEFAULT_PORTS[scheme])
    cidr = body.get('cidr') or None
    if not 1 <= port <= 65535:
        raise EvaluationError('Ports are 1-65535.', 'invalid_egress')
    if cidr is not None:
        try:
            cidr = str(ipaddress.ip_network(cidr, strict=True))
        except ValueError:
            raise EvaluationError('The CIDR is not a valid network.', 'invalid_egress') from None
    entry = uuid.uuid4()
    with installation.db.transaction() as conn:
        conn.execute('INSERT INTO egress_allowlist(org_id, id, scheme, host, port, cidr) VALUES (%s, %s, %s, %s, %s, %s)',
                     (installation.scope.org_id, entry, scheme, host, port, cidr))
        audit_action(conn, installation.scope, _actor(auth), 'egress.allow', str(entry), {'scheme': scheme, 'host': host, 'port': port, 'cidr': cidr})
    return {'id': str(entry), 'scheme': scheme, 'host': host, 'port': port, 'cidr': cidr}


@route('POST', '/egress/<entry>/remove', 'admin', summary='Remove an allowlist entry.')
def egress_remove(installation, auth, body, query, entry):
    from . import audit_action
    with installation.db.transaction() as conn:
        row = conn.execute('DELETE FROM egress_allowlist WHERE org_id = %s AND id = %s RETURNING scheme, host, port',
                           (installation.scope.org_id, _uuid(entry))).fetchone()
        if row is None:
            raise EvaluationError('Unknown allowlist entry.', 'not_found')
        audit_action(conn, installation.scope, _actor(auth), 'egress.remove', entry, dict(row))
    return {'id': entry, 'removed': True}


@route('GET', '/systems/<system>/retention', 'admin', 'system', summary='Observation retention and the pins that protect evidence from it.')
def retention_get(installation, auth, body, query, system):
    from .incidents.pins import DEFAULT_OBSERVATION_DAYS
    with installation.db.connect() as conn:
        policy = conn.execute('SELECT observation_days, updated_at FROM ops_retention_policies WHERE org_id = %s AND system_id = %s',
                              (installation.scope.org_id, system)).fetchone()
        pins = [{**dict(r), 'start_tick': str(int(r['start_tick'])), 'end_tick': str(int(r['end_tick']))} for r in conn.execute(
            '''SELECT p.id, p.holder_kind, p.holder_id, p.reason, p.start_tick, p.end_tick, p.expires_at, p.released_at, p.created_by, p.created_at,
                      p.released_at IS NULL AND (p.expires_at IS NULL OR p.expires_at > now()) AS live
               FROM ops_pins p JOIN ops_systems s ON s.org_id = p.org_id AND s.catalog_id = p.catalog_id
               WHERE p.org_id = %s AND s.id = %s ORDER BY p.created_at DESC LIMIT 200''', (installation.scope.org_id, system)).fetchall()]
    return {'system': system, 'observation_days': policy['observation_days'] if policy else DEFAULT_OBSERVATION_DAYS,
            'default': policy is None, 'updated_at': policy['updated_at'] if policy else None, 'pins': pins,
            'statement': 'Retention tombstones observation facts older than the policy, skipping every live pin. Windows that lose facts '
                         'become summary-only: their aggregates are kept and labelled not recomputable.'}


@route('GET', '/audit', 'admin', summary='The audit log, newest first (cursor = sequence number).')
def audit_list(installation, auth, body, query):
    limit = min(int(query.get('limit', 50)), 200)
    with installation.db.connect() as conn:
        rows = conn.execute('''SELECT seq, at, actor, action, target, payload, encode(hash, 'hex') AS hash FROM audit_log
                               WHERE org_id = %s AND (%s::bigint IS NULL OR seq < %s) ORDER BY seq DESC LIMIT %s''',
                            (installation.scope.org_id, query.get('cursor'), query.get('cursor'), limit)).fetchall()
    return {'items': [dict(r) for r in rows], 'cursor': rows[-1]['seq'] if len(rows) == limit else None}


@route('POST', '/audit/verify', 'admin', summary='Recompute the hash chain and compare it with the anchors recorded at export.')
def audit_verify(installation, auth, body, query):
    from numek_platform import audit
    with installation.db.connect() as conn:
        ok, bad = audit.verify_chain(conn, installation.scope)
        head = conn.execute('SELECT seq, encode(hash, \'hex\') AS hash FROM audit_log WHERE org_id = %s ORDER BY seq DESC LIMIT 1',
                            (installation.scope.org_id,)).fetchone()
        anchors = conn.execute('''SELECT a.seq, a.sink, a.exported_at, l.hash IS NOT NULL AND l.hash = a.hash AS matches FROM audit_anchors a
                                  LEFT JOIN audit_log l ON l.org_id = a.org_id AND l.seq = a.seq WHERE a.org_id = %s ORDER BY a.seq DESC''',
                               (installation.scope.org_id,)).fetchall()
    return {'chain_ok': ok, 'first_bad_seq': bad, 'entries': head['seq'] if head else 0, 'head': head['hash'] if head else None,
            'anchors': [dict(a) for a in anchors], 'anchors_ok': all(a['matches'] for a in anchors),
            'statement': 'The chain is tamper-evident, not tamper-proof: someone who controls the database can rewrite it after the last '
                         'anchor exported to a sink outside NUMEK. Anchors are compared here with their recorded copies; verify against the '
                         'external sink itself with `confidenceguard ops audit verify --sink` for the independent check.'}


def _uuid(value):
    try:
        return uuid.UUID(str(value))
    except ValueError:
        raise EvaluationError('Not found.', 'not_found') from None


# App --------------------------------------------------------------------------------------------------------
class RawResponse:
    def __init__(self, body, mimetype):
        self.body, self.mimetype = body, mimetype


def _actor(auth):
    return f'principal:{auth.principal.name}'


def _resource_scope(installation, kind, ident):
    """(scope_kind, scope_id) for authorization: deployments directly; incidents, proposals and runs via their deployment."""
    if kind is None or ident is None:
        return 'org', ''
    if kind in ('deployment', 'system'):
        return kind, ident
    table = {'incident': 'ops_incidents', 'proposal': 'ops_proposals', 'run': 'ops_investigation_runs'}[kind]
    try:
        key = uuid.UUID(ident)
    except ValueError:
        raise EvaluationError('Not found.', 'not_found') from None
    with installation.db.connect() as conn:
        row = conn.execute(f'SELECT deployment_id FROM {table} WHERE org_id = %s AND id = %s', (installation.scope.org_id, key)).fetchone()
    if row is None:
        raise EvaluationError('Not found.', 'not_found')
    return 'deployment', row['deployment_id']


def _require(installation, auth, permission, kind=None, ident=None):
    from numek_platform import identity
    scope_kind, scope_id = _resource_scope(installation, kind, ident)
    with installation.db.connect() as conn:
        granted = identity.permissions(conn, auth, scope_kind, scope_id)
        if scope_kind == 'deployment':
            system = conn.execute('SELECT system_id FROM ops_deployments WHERE org_id = %s AND id = %s',
                                  (installation.scope.org_id, scope_id)).fetchone()
            if system is not None:
                granted |= identity.permissions(conn, auth, 'system', system['system_id'])
    if permission not in granted:
        raise EvaluationError('Not permitted.', 'forbidden')


def _require_deployment_reads(installation, auth, deployments):
    for deployment in deployments:
        _require(installation, auth, 'read', 'deployment', deployment)


def create_app(installation, *, secure_cookies=False):
    """The operations API plus the S4 ingestion surface, on one Flask app."""
    from flask import Response, jsonify, make_response, request
    from numek_platform import identity
    from numek_platform.errors import PlatformError
    from . import web
    app = web.create_app(installation)

    def envelope_error(exc):
        code = getattr(exc, 'code', 'failed') or 'failed'
        response = jsonify({'error': {'code': code, 'message': str(exc)[:300]}})
        response.status_code = STATUS.get(code, web.STATUS.get(code, 400))
        return response

    def authenticate():
        header = request.headers.get('Authorization', '')
        with installation.db.transaction() as conn:
            if header.startswith('Bearer '):
                auth = identity.authenticate_token(conn, header[7:].strip())
            else:
                token = request.cookies.get(COOKIE)
                if not token:
                    raise EvaluationError('Authentication required.', 'unauthenticated')
                auth = identity.authenticate_session(conn, token, csrf=request.headers.get('X-CSRF-Token'),
                                                     mutating=request.method not in ('GET', 'HEAD'))
        if auth.principal.org_id != installation.scope.org_id:
            raise EvaluationError('Not permitted.', 'forbidden')
        return auth

    def handler_for(r):
        def view(**path):
            try:
                auth = authenticate()
                kind = r['scope']
                ident = next((path[p] for p in ('deployment', 'system', 'incident', 'proposal', 'run') if p in path and kind), None)
                _require(installation, auth, r['permission'], kind, ident)
                body = request.get_json(silent=True) if request.method == 'POST' else None
                if request.method == 'POST' and not isinstance(body, dict):
                    body = {}
                result = r['handler'](installation, auth, body, request.args, **path)
                if isinstance(result, RawResponse):
                    return Response(result.body, mimetype=result.mimetype)
                return Response(json.dumps({'data': result}, default=_plain), mimetype='application/json')
            except (EvaluationError, PlatformError) as exc:
                return envelope_error(exc)
            except KeyError as exc:
                return envelope_error(EvaluationError(f'Missing field {exc}.', 'invalid_request'))
        view.__name__ = f"ops_{r['handler'].__name__}"
        return view

    for r in ROUTES:
        app.add_url_rule(PREFIX + r['path'], view_func=handler_for(r), methods=[r['method']])

    @app.post(PREFIX + '/session')
    def login():
        body = request.get_json(silent=True) or {}
        name = body.get('name', '')
        try:
            with installation.db.transaction() as conn:
                if identity.login_throttled(conn, installation.scope, name):
                    raise EvaluationError('Too many failed sign-ins for this name; try again later.', 'login_throttled')
                principal = identity.verify_password(conn, installation.scope, name, body.get('password', ''))
                token, csrf = identity.create_session(conn, principal)
        except EvaluationError as exc:
            response = envelope_error(exc)
            response.headers['Retry-After'] = str(int(identity.LOGIN_FAILURE_WINDOW.total_seconds()))
            return response
        except PlatformError as exc:
            if exc.code == 'unauthenticated':
                with contextlib.suppress(PlatformError), installation.db.transaction() as conn:
                    identity.record_login_failure(conn, installation.scope, name)
            return envelope_error(exc)
        response = make_response(jsonify({'data': {'principal': principal.name, 'csrf': csrf}}))
        response.set_cookie(COOKIE, token, httponly=True, samesite='Strict', secure=secure_cookies, path='/')
        return response

    @app.delete(PREFIX + '/session')
    def logout():
        token = request.cookies.get(COOKIE)
        if token:
            try:
                with installation.db.transaction() as conn:
                    identity.revoke_session(conn, token)
            except PlatformError:
                pass
        response = make_response(jsonify({'data': {'signed_out': True}}))
        response.delete_cookie(COOKIE, path='/')
        return response

    @app.get(PREFIX + '/openapi.json')
    def spec():
        return jsonify(openapi())

    @app.get('/readyz')
    def ready():
        checks = {}
        try:
            with installation.db.connect() as conn:
                conn.execute('SELECT 1')
                checks['database'] = 'ok'
                leader = conn.execute('SELECT holder, epoch, expires_at > now() AS live FROM controller_leadership').fetchone()
                checks['controller'] = 'leading' if leader and leader['live'] else 'no_live_leader'
                age = conn.execute("SELECT extract(epoch FROM now() - min(created_at)) AS s FROM jobs WHERE state = 'queued' "
                                   "AND lane = 'essential'").fetchone()['s']
                checks['oldest_essential_job_seconds'] = None if age is None else float(age)
        except Exception:
            checks['database'] = 'unavailable'
        ready_ = checks.get('database') == 'ok'
        return jsonify({'data': {'ready': ready_, 'checks': checks}}), 200 if ready_ else 503

    @app.get('/metrics')
    def metrics():
        # Operational counts only, but still installation metadata: open to loopback scrapers (a local Prometheus or a
        # reverse proxy on the host), otherwise an authenticated principal with read permission.
        if request.remote_addr not in ('127.0.0.1', '::1'):
            try:
                _require(installation, authenticate(), 'read')
            except (EvaluationError, PlatformError) as exc:
                return envelope_error(exc)
        return Response(prometheus(installation), mimetype='text/plain; version=0.0.4')

    console = Path(__file__).resolve().parent.parent / 'static' / 'ops'

    @app.get('/')
    def root():
        from flask import redirect
        return redirect('/ops/', code=302)

    @app.get('/ops/')
    @app.get('/ops/<path:path>')
    def console_files(path=''):
        """The operations console (prebuilt). Unknown paths fall back to the app shell (client-side routes)."""
        from flask import abort, send_from_directory
        if not (console / 'index.html').is_file():
            abort(404)
        target = (console / path).resolve() if path else None
        if target is not None and target.is_file() and console in target.parents:
            response = send_from_directory(console, path)
        else:
            response = send_from_directory(console, 'index.html')
            response.headers['Cache-Control'] = 'no-store'
        response.headers['Content-Security-Policy'] = CSP
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['X-Frame-Options'] = 'DENY'
        return response

    return app


def _plain(value):
    if isinstance(value, (datetime,)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value).hex()
    import decimal
    if isinstance(value, decimal.Decimal):
        return float(value)
    raise TypeError(type(value).__name__)


def prometheus(installation):
    """Prometheus text exposition: queue depth and age per lane, batches by state, incidents by state, outbox."""
    lines = []
    with installation.db.connect() as conn:
        for row in conn.execute("SELECT lane, state, count(*) AS n, coalesce(extract(epoch FROM now() - min(created_at)), 0) AS age "
                                "FROM jobs WHERE org_id = %s GROUP BY lane, state", (installation.scope.org_id,)).fetchall():
            lines.append(f'numek_jobs{{lane="{row["lane"]}",state="{row["state"]}"}} {row["n"]}')
            if row['state'] == 'queued':
                lines.append(f'numek_jobs_oldest_queued_seconds{{lane="{row["lane"]}"}} {float(row["age"]):.1f}')
        for row in conn.execute('SELECT state, count(*) AS n FROM ops_batches WHERE org_id = %s GROUP BY state', (installation.scope.org_id,)):
            lines.append(f'numek_ingest_batches{{state="{row["state"]}"}} {row["n"]}')
        for row in conn.execute('SELECT state, count(*) AS n FROM ops_incidents WHERE org_id = %s GROUP BY state', (installation.scope.org_id,)):
            lines.append(f'numek_incidents{{state="{row["state"]}"}} {row["n"]}')
        for row in conn.execute('SELECT state, count(*) AS n FROM ops_notification_outbox WHERE org_id = %s GROUP BY state',
                                (installation.scope.org_id,)):
            lines.append(f'numek_notifications{{state="{row["state"]}"}} {row["n"]}')
        head = conn.execute('SELECT coalesce(max(head), 0) AS k FROM catalog_heads h JOIN catalogs c ON c.id = h.catalog_id '
                            'WHERE c.org_id = %s', (installation.scope.org_id,)).fetchone()['k']
        lines.append(f'numek_catalog_head_max {head}')
    lines.append(f'numek_scrape_unixtime {time.time():.0f}')
    return '\n'.join(sorted(lines)) + '\n'


def serve_guard(host, *, tls=False, trusted_proxy=False):
    """Non-loopback serving requires TLS or a declared trusted reverse proxy (plan C.2, M.4)."""
    if host not in ('127.0.0.1', '::1', 'localhost') and not (tls or trusted_proxy):
        raise EvaluationError('Serving beyond loopback requires TLS or a declared trusted reverse proxy.', 'tls_required')
    return True
