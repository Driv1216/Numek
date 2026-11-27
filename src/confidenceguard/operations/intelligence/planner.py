"""The budgeted, deterministic investigation planner (plan I.6, R2.7).

**Candidates** are the templates of non-terminal hypotheses: ``proposed``, ``supported``, ``contested`` and
``unresolved``.

**Eligibility.** A candidate must pass:
- the template's own data and compatibility check, which gives a reason when it fails;
- the tier rule: ``restricted`` is never automatic;
- the budgets;
- deduplication by logical fingerprint.

**Reuse (R2.7).** A prior run of the same template, spec and selection is reused only if *the only change since
its K is additional units*, with nothing else changed:
- no new revisions or corrections of selected opportunities;
- no outcome revisions for them;
- no tombstones in the span.

Then the new-support fraction decides: under 20% means "reuse, marked stale by x%", otherwise rerun. Any material
change means rerun.

**Value and selection.**
- Value: v = Σ_h movable(h)·weight(h), with weight 2 for hypotheses whose support includes F or D evidence, else 1.
- Selection: greedy by v / cost, with ties broken by incident priority, cost class, then template order.
- The planner returns its reasoning for every candidate it considered.

**Budgets** (``auto`` tier):
- 30 compute-minutes per deployment per day;
- 5 runs per incident;
- a 24 h cooldown per template and incident.

**Tiers.** ``auto`` runs now. ``confirm`` waits for an approver. ``restricted`` waits for an approver holding
``reserve:consume``.

**Deferred triggers.** An open information requirement with an ETA queues its template when the ETA passes and the
evidence has become evaluable.
"""
import uuid
from datetime import timedelta

from psycopg.types.json import Jsonb

from ...contracts import EvaluationError, digest
from . import hypotheses as hypothesis_rules, templates

AUTO_MINUTES_PER_DAY = 30.0
AUTO_RUNS_PER_INCIDENT = 5
COOLDOWN = timedelta(hours=24)
REUSE_SUPPORT_LIMIT = 0.20
MOVABLE = ('proposed', 'supported', 'contested', 'unresolved')


def _states(conn, scope, incident_id):
    return {r['hypothesis_id']: dict(r) for r in conn.execute(
        'SELECT hypothesis_id, state, evidence FROM ops_hypotheses WHERE org_id = %s AND incident_id = %s', (scope.org_id, incident_id)).fetchall()}


def _changes_since(conn, catalog_id, span, k):
    """(new opportunities, material changes) in the span published after K (R2.7 reuse rule)."""
    start, end = span
    new = conn.execute('''SELECT count(DISTINCT f.key) AS n FROM fact_index f JOIN publications p ON p.id = f.publication_id
                          WHERE f.catalog_id = %s AND f.kind = 'opportunity' AND f.event_tick >= %s AND f.event_tick < %s AND p.sequence > %s
                                AND f.revision = 'initial'
                                AND NOT EXISTS (SELECT 1 FROM fact_index o JOIN publications op ON op.id = o.publication_id
                                                WHERE o.catalog_id = f.catalog_id AND o.kind = 'opportunity' AND o.key = f.key
                                                AND op.sequence <= %s)''', (catalog_id, start, end, k, k)).fetchone()['n']
    material = conn.execute('''SELECT
            (SELECT count(*) FROM fact_index f JOIN publications p ON p.id = f.publication_id
             WHERE f.catalog_id = %s AND f.kind = 'opportunity' AND f.event_tick >= %s AND f.event_tick < %s AND p.sequence > %s
                   AND f.revision <> 'initial')
          + (SELECT count(*) FROM fact_index x JOIN publications px ON px.id = x.publication_id
             JOIN fact_index o ON o.catalog_id = x.catalog_id AND o.kind = 'opportunity' AND o.target_key = x.target_key
             JOIN publications op ON op.id = o.publication_id
             WHERE x.catalog_id = %s AND x.kind = 'outcome' AND px.sequence > %s AND op.sequence <= %s
                   AND o.event_tick >= %s AND o.event_tick < %s)
          + (SELECT count(*) FROM fact_tombstones t JOIN publications pt ON pt.id = t.publication_id
             WHERE t.catalog_id = %s AND pt.sequence > %s) AS n''',
                            (catalog_id, start, end, k, catalog_id, k, k, start, end, catalog_id, k)).fetchone()['n']
    prior = conn.execute('''SELECT count(DISTINCT f.key) AS n FROM fact_index f JOIN publications p ON p.id = f.publication_id
                            WHERE f.catalog_id = %s AND f.kind = 'opportunity' AND f.event_tick >= %s AND f.event_tick < %s
                                  AND p.sequence <= %s''', (catalog_id, start, end, k)).fetchone()['n']
    return new, material, prior


def plan(installation, incident_id, *, now, only=None, actor='system'):
    """Select and record investigation runs for an incident. Returns the plan with its reasoning."""
    from ..monitoring import context as deployment_context
    from . import observations as observation_rules
    scope = installation.scope
    ctx = observation_rules.context(installation, incident_id)
    incident = ctx['incident']
    deployment = deployment_context.deployment(installation, incident['deployment_id'])
    k = deployment['workspace'].status()['catalog_sequence']
    with installation.db.connect() as conn:
        states = _states(conn, scope, incident_id)
        prior_runs = [dict(r) for r in conn.execute('SELECT * FROM ops_investigation_runs WHERE org_id = %s AND incident_id = %s',
                                                    (scope.org_id, incident_id)).fetchall()]
        spent = conn.execute('''SELECT coalesce(sum(cost_minutes), 0) AS m FROM ops_investigation_runs WHERE org_id = %s AND deployment_id = %s
                                AND tier = 'auto' AND state IN ('planned', 'running', 'completed') AND created_at >= %s''',
                             (scope.org_id, incident['deployment_id'], now - timedelta(days=1))).fetchone()['m']
        requirements = [r['observation'] for r in conn.execute(
            "SELECT observation FROM ops_requirements WHERE org_id = %s AND incident_id = %s AND status = 'open'",
            (scope.org_id, incident_id)).fetchall()]
    candidates, considered = {}, []
    for template, meta in templates.TEMPLATES.items():              # a template's ``discriminates`` is the source of truth
        if only and template not in only:
            continue
        for hid in meta['discriminates']:
            row = states.get(hid)
            if row is None or row['state'] not in MOVABLE:
                continue
            weight = 2 if hypothesis_rules.triggered_by_formal(row['evidence']) else 1
            entry = candidates.setdefault(template, {'template': template, 'value': 0.0, 'movable': []})
            entry['value'] += weight
            entry['movable'].append({'hypothesis': hid, 'state': row['state'], 'weight': weight})
    for template, meta in templates.TEMPLATES.items():
        if template not in candidates and set(meta.get('supports_requirements', ())) & set(requirements) and (not only or template in only):
            candidates[template] = {'template': template, 'value': 0.5, 'movable': [],
                                    'note': 'guidance for open information requirements'}
    auto_runs = sum(1 for r in prior_runs if r['tier'] == 'auto' and r['state'] in ('planned', 'running', 'completed'))
    ranked = sorted(candidates.values(), key=lambda c: (-c['value'] / templates.TEMPLATES[c['template']]['cost'],
                                                         templates.COST_ORDER[templates.TEMPLATES[c['template']]['cost_class']],
                                                         list(templates.TEMPLATES).index(c['template'])))
    selected = []
    for candidate in ranked:
        meta = templates.TEMPLATES[candidate['template']]
        spec = templates.spec_for(candidate['template'], ctx, now)
        # Templates that run the same analysis share one logical fingerprint, so the second is a duplicate (or a
        # reuse) of the first rather than a second identical computation.
        logical = digest({**{k_: v for k_, v in spec.items() if k_ not in ('as_of', 'template')},
                          'analysis': meta.get('same_analysis_as', candidate['template'])})
        fingerprint = digest([logical, k])
        reasoning = {**candidate, 'value_per_minute': candidate['value'] / meta['cost'], 'tier': meta['tier'],
                     'incident_priority': incident['priority']}
        ok, reason = meta['eligible'](installation, ctx)
        if not ok:
            considered.append({**reasoning, 'decision': 'ineligible', 'reason': reason})
            continue
        same = [r for r in prior_runs if r['logical_fingerprint'] == logical and r['state'] in ('completed', 'reused', 'running',
                                                                                                 'awaiting_approval', 'planned')]
        if any(r['fingerprint'] == fingerprint for r in same):
            considered.append({**reasoning, 'decision': 'duplicate', 'reason': 'identical fingerprint already planned or run'})
            continue
        latest = max(same, key=lambda r: r['created_at'], default=None)
        reuse = None
        if latest is not None and latest['state'] in ('completed', 'reused'):
            with installation.db.connect() as conn:
                new, material, base = _changes_since(conn, deployment['catalog_id'], ctx['span'], latest['catalog_sequence'])
            fraction = (new / base) if base else (1.0 if new else 0.0)
            if not material and fraction < REUSE_SUPPORT_LIMIT:
                reuse = {'from': latest['id'], 'stale_fraction': fraction}
            reasoning['reuse_check'] = {'new_opportunities': new, 'material_changes': material, 'prior_opportunities': base,
                                        'decision': 'reuse' if reuse else 'rerun'}
        if meta['tier'] == 'auto' and reuse is None:
            if any(r['template'] == candidate['template'] and r['tier'] == 'auto' and now - r['created_at'] < COOLDOWN
                   and r['state'] in ('completed', 'running') for r in prior_runs):
                considered.append({**reasoning, 'decision': 'cooldown', 'reason': '24 h cooldown per template and incident'})
                continue
            if auto_runs >= AUTO_RUNS_PER_INCIDENT:
                considered.append({**reasoning, 'decision': 'budget', 'reason': 'five automatic runs per incident'})
                continue
            if spent + meta['cost'] > AUTO_MINUTES_PER_DAY:
                considered.append({**reasoning, 'decision': 'budget', 'reason': '30 automatic compute-minutes per deployment per day'})
                continue
            spent += meta['cost']
            auto_runs += 1
        state = 'reused' if reuse else 'planned' if meta['tier'] == 'auto' else 'awaiting_approval'
        run_id = uuid.uuid4()
        with installation.db.transaction() as conn:
            conn.execute('''INSERT INTO ops_investigation_runs(org_id, id, incident_id, deployment_id, template, tier, state, fingerprint,
                                logical_fingerprint, spec, catalog_sequence, value, cost_minutes, reasoning, reused_from, stale_fraction,
                                result, result_digest, result_object, finished_at, created_at)
                            SELECT %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                                   r.result, r.result_digest, r.result_object, CASE WHEN %s THEN %s END, %s
                            FROM (SELECT 1) one LEFT JOIN ops_investigation_runs r ON r.org_id = %s AND r.id = %s''',
                         (scope.org_id, run_id, incident_id, incident['deployment_id'], candidate['template'], meta['tier'], state,
                          fingerprint, logical, Jsonb(spec), k, candidate['value'], meta['cost'], Jsonb(reasoning),
                          reuse['from'] if reuse else None, reuse['stale_fraction'] if reuse else None,
                          reuse is not None, now, now, scope.org_id, reuse['from'] if reuse else None))
            from ..incidents.incidents import event
            event(conn, scope, incident_id, 'investigation_planned', {'run': str(run_id), 'template': candidate['template'],
                                                                     'state': state, 'reasoning': reasoning}, actor)
        considered.append({**reasoning, 'decision': state, 'run': str(run_id)})
        selected.append({'run': str(run_id), 'template': candidate['template'], 'state': state})
    return {'incident': str(incident_id), 'catalog_sequence': k, 'selected': selected, 'considered': considered,
            'budget': {'auto_minutes_used_today': spent, 'auto_minutes_per_day': AUTO_MINUTES_PER_DAY,
                       'auto_runs_for_incident': auto_runs, 'auto_runs_per_incident': AUTO_RUNS_PER_INCIDENT}}


def approve(installation, run_id, *, actor, permissions=(), spec=None, now):
    """Approve a confirm/restricted run (restricted needs ``reserve:consume``), then execute it."""
    from .. import audit_action
    scope = installation.scope
    with installation.db.transaction() as conn:
        run = conn.execute('SELECT * FROM ops_investigation_runs WHERE org_id = %s AND id = %s FOR UPDATE', (scope.org_id, run_id)).fetchone()
        if run is None or run['state'] != 'awaiting_approval':
            raise EvaluationError('Only a run awaiting approval can be approved.', 'run_state')
        if run['tier'] == 'restricted' and 'reserve:consume' not in permissions:
            raise EvaluationError('Restricted investigations need reserve:consume.', 'forbidden')
        conn.execute("UPDATE ops_investigation_runs SET state = 'planned', approved_by = %s, spec = spec || %s WHERE org_id = %s AND id = %s",
                     (actor, Jsonb(spec or {}), scope.org_id, run_id))
        audit_action(conn, scope, actor, 'investigation.approve', str(run_id), {'template': run['template'], 'tier': run['tier']})
    return execute(installation, run_id, now=now)


def execute(installation, run_id, *, now, scratch=None):
    """Run a planned investigation; store its result packet; append a knowledge revision (hypotheses re-evaluated)."""
    import tempfile
    from ..incidents import incidents
    from ..monitoring import context as deployment_context, packets
    from . import observations as observation_rules
    scope = installation.scope
    with installation.db.transaction() as conn:
        run = conn.execute('SELECT * FROM ops_investigation_runs WHERE org_id = %s AND id = %s FOR UPDATE', (scope.org_id, run_id)).fetchone()
        if run is None or run['state'] != 'planned':
            raise EvaluationError('Only a planned run can execute.', 'run_state')
        conn.execute("UPDATE ops_investigation_runs SET state = 'running' WHERE org_id = %s AND id = %s", (scope.org_id, run_id))
    ctx = observation_rules.context(installation, run['incident_id'])
    spec = {**run['spec'], 'request_id': f'investigation:{run_id}', 'scratch': scratch or tempfile.mkdtemp(prefix='nmk-inv-')}
    try:
        result = templates.TEMPLATES[run['template']]['run'](installation, ctx, spec)
    except EvaluationError as exc:
        state = 'refused' if exc.code in ('operator_specification_required', 'restricted_study', 'not_monitored', 'template_ineligible',
                                          'template_spec_required', 'template_data_unavailable') else 'failed'
        with installation.db.transaction() as conn:
            conn.execute('UPDATE ops_investigation_runs SET state = %s, error = %s, finished_at = %s WHERE org_id = %s AND id = %s',
                         (state, Jsonb({'code': exc.code, 'message': str(exc)}), now, scope.org_id, run_id))
            incidents.event(conn, scope, run['incident_id'], 'investigation_' + state, {'run': str(run_id), 'code': exc.code}, 'system')
        return {'run': str(run_id), 'state': state, 'code': exc.code}
    import json
    result = json.loads(json.dumps(result, default=str))
    deployment = deployment_context.deployment(installation, run['deployment_id'])
    with installation.db.connect() as conn:
        from numek_platform.execution import jobs
        lease, _row = jobs.start_inline(conn, scope, 'ops_investigation', idempotency_key=f'investigation:{run_id}', owner='confidenceguard:planner')
    ref = packets.stage(installation, lease, deployment['catalog_id'], packets.encode({'run': str(run_id), 'template': run['template'], **result}))
    result_digest = packets.packet_digest({'run': str(run_id), 'template': run['template'], **result})
    summary = {'observations': result.get('observations', {}), 'summary_digest': digest(result.get('summary'))}

    def write(conn):
        conn.execute("UPDATE ops_investigation_runs SET state = 'completed', result = %s, result_object = %s, result_digest = %s, "
                     'finished_at = %s WHERE org_id = %s AND id = %s', (Jsonb(summary), ref.id, result_digest, now, scope.org_id, run_id))
        incidents.event(conn, scope, run['incident_id'], 'investigation_completed',
                        {'run': str(run_id), 'template': run['template'], 'observations': sorted(summary['observations'])}, 'system')
    packets.publish(installation, lease, deployment['catalog_id'], [ref], [], write)
    incidents.append_revision(installation, run['incident_id'], f"investigation {run['template']} completed", now=now)
    return {'run': str(run_id), 'state': 'completed', 'observations': summary['observations']}


def run_auto(installation, incident_id, *, now):
    """Plan, then execute every planned automatic run (single host; worker hosts run the same through jobs)."""
    planned = plan(installation, incident_id, now=now)
    done = [execute(installation, s['run'], now=now) for s in planned['selected'] if s['state'] == 'planned']
    return {'plan': planned, 'executed': done}


def fire_triggers(installation, *, now):
    """Deferred triggers: open requirements past their ETA whose evidence is now evaluable queue their template."""
    from . import observations as observation_rules
    scope = installation.scope
    with installation.db.connect() as conn:
        due = [dict(r) for r in conn.execute('''SELECT r.* FROM ops_requirements r JOIN ops_incidents i ON i.org_id = r.org_id AND i.id = r.incident_id
                                                WHERE r.org_id = %s AND r.status = 'open' AND r.template IS NOT NULL AND r.eta <= %s
                                                AND r.triggered_run IS NULL AND i.state NOT IN ('resolved', 'merged')''',
                                             (scope.org_id, now)).fetchall()]
    fired = []
    for requirement in due:
        _ctx, observed = observation_rules.evaluate(installation, requirement['incident_id'])
        if observed[requirement['observation']]['value'] is None and templates.TEMPLATES[requirement['template']]['eligible'](installation, _ctx)[0] is False:
            continue
        result = plan(installation, requirement['incident_id'], now=now, only=(requirement['template'],))
        run = next((s for s in result['selected']), None)
        if run is None:
            if observed[requirement['observation']]['value'] is not None:
                # The evidence arrived and already decided the hypotheses it served: nothing left to discriminate.
                with installation.db.transaction() as conn:
                    conn.execute("UPDATE ops_requirements SET status = 'satisfied', satisfied_at = %s, reason = %s WHERE org_id = %s "
                                 'AND incident_id = %s AND observation = %s',
                                 (now, 'evidence available; hypotheses decided without the investigation', scope.org_id,
                                  requirement['incident_id'], requirement['observation']))
            continue
        with installation.db.transaction() as conn:
            conn.execute('UPDATE ops_requirements SET triggered_run = %s WHERE org_id = %s AND incident_id = %s AND observation = %s',
                         (uuid.UUID(run['run']), scope.org_id, requirement['incident_id'], requirement['observation']))
        if run['state'] == 'planned':
            execute(installation, run['run'], now=now)
        fired.append({'incident': str(requirement['incident_id']), 'observation': requirement['observation'], **run})
    return fired


def enqueue(installation, run_id):
    """Queue a planned run for the worker hosts (job kind ``ops_investigation``, investigation lane, isolated)."""
    from numek_platform.execution import jobs
    scope = installation.scope
    with installation.db.transaction() as conn:
        run = conn.execute('SELECT state FROM ops_investigation_runs WHERE org_id = %s AND id = %s', (scope.org_id, run_id)).fetchone()
        if run is None or run['state'] != 'planned':
            raise EvaluationError('Only a planned run can be queued.', 'run_state')
        row = jobs.enqueue(conn, scope, 'ops_investigation', idempotency_key=f'ops-investigation:{run_id}', lane='investigation',
                           job_class='isolated', payload={'installation': str(installation.root), 'run': str(run_id)})
    return {'run': str(run_id), 'job': str(row['id']), 'state': row['state']}


def investigation_job(job_ctx, payload):
    """Worker-host entry point (``ops_investigation``): the job process is the isolation boundary."""
    from datetime import datetime, timezone
    from numek_platform.installation import Installation
    from ...execution_context import InProcessContext, using
    installation = Installation(payload['installation'])
    with using(InProcessContext(deadline=job_ctx.deadline)):
        return execute(installation, uuid.UUID(payload['run']), now=datetime.now(timezone.utc))
