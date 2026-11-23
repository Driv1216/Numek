"""The hypothesis catalog, the differential matrix, hypothesis states and information requirements (plan I.3–I.5).

**The catalog is data.** Every entry declares:
- machine-checkable ``predicts``: the observations it expects, each with the value that *supports* it, and the
  observations whose value *contradicts* it;
- ``requires``: the observations it cannot be judged without;
- at least one discriminating investigation template.

An entry whose requirements can never be monitored is ``untestable``, and its reason is shown.

**States** are recomputed with every knowledge revision:

| State | When |
|---|---|
| ``unresolved`` | A required observation is not evaluable. It becomes an information requirement, with an ETA or an action, and a deferred trigger for the discriminating template. |
| ``supported`` | At least one prediction holds and none is contradicted. |
| ``contradicted`` | A contradiction holds and nothing supports it. |
| ``contested`` | Both hold. Both are shown, and a tie-break investigation is suggested. |
| ``proposed`` | Every requirement is evaluable but no prediction is decided. |
| ``untestable`` | A requirement can never be evaluated by monitoring; the reason is shown. |

**The differential matrix** is the main reasoning surface. It crosses hypotheses with observations, marking each
cell:

| Cell | Meaning |
|---|---|
| ``✓`` | Consistent with the prediction. |
| ``✗`` | Inconsistent with the prediction. |
| ``?`` | Not evaluable. |
| (blank) | Not predicted. |

Each cell shows the observation's standing.

Everything here is association reasoning over recorded evidence. A supported hypothesis is not an established
cause.
"""
from psycopg.types.json import Jsonb

CATALOG = (
    {'id': 'H-COMP', 'title': 'Population composition shifted toward riskier groups',
     'supports': {'O-composition-shift': True, 'O-drift-feature': True, 'O-domain-shift': True},
     'contradicts': {'O-composition-shift': False},
     'requires': ('O-composition-shift',), 'templates': ('cg3_mix_decomposition', 'domain_classifier')},
    {'id': 'H-WITHIN', 'title': 'Risk degraded within groups (not explained by composition)',
     'supports': {'O-within-group-change': True, 'O-error-alarm': True},
     'contradicts': {'O-within-group-change': False},
     'requires': ('O-within-group-change',), 'templates': ('cg3_cohort_contrast', 'cg3_mix_decomposition')},
    {'id': 'H-INTEG', 'title': 'Input data integrity or pipeline change',
     'supports': {'O-integrity': True, 'O-drift-feature': True, 'O-deploy-event': True},
     'contradicts': {'O-integrity': False},
     'requires': ('O-integrity',), 'templates': ('contract_diff', 'domain_classifier')},
    {'id': 'H-DEPLOY', 'title': 'The deployed model or its configuration changed',
     'supports': {'O-identity-change': True, 'O-deploy-event': True},
     'contradicts': {'O-identity-change': False},
     'requires': ('O-identity-change',), 'templates': ('cg6_shadow_replay',)},
    {'id': 'H-CALIB', 'title': 'Calibration drifted (model-implied risk no longer matches realized risk)',
     'supports': {'O-calibration': True},
     'contradicts': {'O-calibration': False},
     'requires': ('O-calibration',), 'templates': ('cg2_recalibration_study',)},
    {'id': 'H-UNC', 'title': 'Uncertainty outputs (intervals, sets) lost coverage',
     'supports': {'O-uncertainty': True}, 'contradicts': {'O-uncertainty': False},
     'requires': ('O-uncertainty',), 'templates': ('cg2_uncertainty_study',), 'never_monitored': ('O-uncertainty',)},
    {'id': 'H-POLICY', 'title': 'The decision policy or its thresholds changed',
     'supports': {'O-policy-change': True, 'O-deploy-event': True},
     'contradicts': {'O-policy-change': False},
     'requires': ('O-policy-change',), 'templates': ('cg5_policy_replay',)},
    {'id': 'H-LABEL', 'title': 'The labelling process changed (selective or delayed labels)',
     'supports': {'O-label-availability-shift': True},
     'contradicts': {'O-label-availability-shift': False},
     'requires': ('O-label-availability-shift',), 'templates': ('label_availability_audit',)},
    {'id': 'H-MULTI', 'title': 'A shared upstream cause affects several deployments',
     'supports': {'O-multiple-deployments': True},
     'contradicts': {'O-multiple-deployments': False},
     'requires': ('O-multiple-deployments',), 'templates': ('monitoring_health_review',)},
    {'id': 'H-MON', 'title': 'A monitoring artifact (gaps, delays, failed jobs), not a model problem',
     'supports': {'O-monitoring-health': True},
     'contradicts': {'O-monitoring-health': False, 'O-error-alarm': True},
     'requires': ('O-monitoring-health',), 'templates': ('monitoring_health_review',)},
)


def _consistent():
    """Every catalog template exists and declares the hypothesis it is listed under (checked in tests)."""
    from .templates import TEMPLATES
    return all(t in TEMPLATES and h['id'] in TEMPLATES[t]['discriminates'] for h in CATALOG for t in h['templates'])
BY_ID = {h['id']: h for h in CATALOG}
TERMINAL = ('contradicted', 'untestable')


def judge(hypothesis, observations):
    """(state, reason, evidence) for one hypothesis."""
    supporting, contradicting, missing = [], [], []
    for name, wanted in hypothesis['supports'].items():
        obs = observations[name]
        if obs['value'] is None:
            continue
        if obs['value'] == wanted:
            supporting.append({'observation': name, 'value': obs['value'], 'standing': obs['standing']})
    for name, wanted in hypothesis['contradicts'].items():
        obs = observations[name]
        if obs['value'] is not None and obs['value'] == wanted:
            contradicting.append({'observation': name, 'value': obs['value'], 'standing': obs['standing']})
    for name in hypothesis['requires']:
        if observations[name]['value'] is None:
            missing.append({'observation': name, 'reason': observations[name].get('reason'), 'eta': observations[name].get('eta'),
                            'action': observations[name].get('action')})
    evidence = {'supporting': supporting, 'contradicting': contradicting, 'missing': missing}
    if missing and set(hypothesis.get('never_monitored', ())) >= {m['observation'] for m in missing}:
        return 'untestable', missing[0]['reason'], evidence
    if supporting and contradicting:
        return 'contested', 'conflicting evidence; adjudicate or run a tie-break investigation', evidence
    if contradicting:
        return 'contradicted', None, evidence
    if missing:
        return 'unresolved', 'required evidence is not yet available', evidence
    if supporting:
        return 'supported', None, evidence
    return 'proposed', None, evidence


def matrix(observations):
    """Rows: hypotheses; columns: observations; cells ✓ / ✗ / ? / '' with the observation standing."""
    columns = sorted({name for h in CATALOG for name in (*h['supports'], *h['contradicts'])})
    rows = []
    for h in CATALOG:
        cells = {}
        for name in columns:
            predicted = name in h['supports'] or name in h['contradicts']
            obs = observations[name]
            if not predicted:
                cells[name] = ''
            elif obs['value'] is None:
                cells[name] = '?'
            elif h['supports'].get(name) == obs['value']:
                cells[name] = '✓'
            elif h['contradicts'].get(name) == obs['value']:
                cells[name] = '✗'
            else:
                cells[name] = ''
        rows.append({'hypothesis': h['id'], 'title': h['title'], 'cells': cells})
    return {'columns': [{'observation': n, 'value': observations[n]['value'], 'standing': observations[n]['standing']} for n in columns],
            'rows': rows, 'legend': {'✓': 'consistent with the prediction', '✗': 'inconsistent', '?': 'not evaluable', '': 'not predicted'},
            'qualification': 'Association reasoning over recorded evidence; a supported hypothesis is not an established cause.'}


def triggered_by_formal(evidence):
    return any(e['standing'] in ('F', 'D') for e in evidence['supporting'])


def evaluate(installation, incident_id, *, knowledge_revision, actor='system'):
    """Recompute hypothesis states, the matrix and information requirements; record changes as incident events."""
    from ..incidents.incidents import event
    from . import observations as observation_rules
    ctx, observed = observation_rules.evaluate(installation, incident_id)
    scope = installation.scope
    states = {h['id']: judge(h, observed) for h in CATALOG}
    with installation.db.transaction() as conn:
        prior = {r['hypothesis_id']: r['state'] for r in conn.execute(
            'SELECT hypothesis_id, state FROM ops_hypotheses WHERE org_id = %s AND incident_id = %s FOR UPDATE',
            (scope.org_id, incident_id)).fetchall()}
        for hid, (state, reason, evidence) in states.items():
            conn.execute('''INSERT INTO ops_hypotheses(org_id, incident_id, hypothesis_id, state, reason, evidence, knowledge_revision)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (org_id, incident_id, hypothesis_id) DO UPDATE SET state = EXCLUDED.state,
                                reason = EXCLUDED.reason, evidence = EXCLUDED.evidence,
                                knowledge_revision = EXCLUDED.knowledge_revision, updated_at = clock_timestamp()''',
                         (scope.org_id, incident_id, hid, state, reason, Jsonb(evidence), knowledge_revision))
            if prior.get(hid) != state:
                event(conn, scope, incident_id, 'hypothesis_state', {'hypothesis': hid, 'from': prior.get(hid), 'to': state,
                                                                      'reason': reason, 'knowledge_revision': knowledge_revision}, actor)
        _requirements(conn, scope, incident_id, states, observed)
    return {'observations': observed, 'states': {h: s[0] for h, s in states.items()}, 'matrix': matrix(observed)}


def _requirements(conn, scope, incident_id, states, observed):
    """Missing required evidence becomes an explicit requirement with a deferred trigger for its template."""
    wanted = {}
    for hid, (state, _reason, evidence) in states.items():
        if state != 'unresolved':
            continue
        for item in evidence['missing']:
            entry = wanted.setdefault(item['observation'], {'hypotheses': [], 'template': BY_ID[hid]['templates'][0], **item})
            entry['hypotheses'].append(hid)
    open_rows = {r['observation']: r for r in conn.execute(
        "SELECT observation, status FROM ops_requirements WHERE org_id = %s AND incident_id = %s", (scope.org_id, incident_id)).fetchall()}
    for name, item in wanted.items():
        conn.execute('''INSERT INTO ops_requirements(org_id, incident_id, observation, status, reason, eta, action, hypotheses, template)
                        VALUES (%s, %s, %s, 'open', %s, %s, %s, %s, %s)
                        ON CONFLICT (org_id, incident_id, observation) DO UPDATE SET status = 'open', reason = EXCLUDED.reason,
                            eta = EXCLUDED.eta, action = EXCLUDED.action, hypotheses = EXCLUDED.hypotheses,
                            template = EXCLUDED.template, satisfied_at = NULL''',
                     (scope.org_id, incident_id, name, item['reason'] or 'not_evaluable', item['eta'], item['action'],
                      sorted(item['hypotheses']), item['template'] if item['eta'] else None))
    for name, row in open_rows.items():
        if row['status'] == 'open' and name not in wanted and observed.get(name, {}).get('value') is not None:
            conn.execute("UPDATE ops_requirements SET status = 'satisfied', satisfied_at = clock_timestamp() WHERE org_id = %s "
                         'AND incident_id = %s AND observation = %s', (scope.org_id, incident_id, name))
