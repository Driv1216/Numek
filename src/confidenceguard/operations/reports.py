"""Incident reports (plan J "Reports"): one data packet, rendered as JSON, HTML and PDF.

The report follows the incident workspace:
1. what, where, since, how many, and the priority with its reason;
2. the evidence ladder by standing;
3. the differential matrix, information requirements and investigations;
4. the response comparison, execution standings and verification, with R1, R2 and R3 kept separate;
5. the timeline;
6. what was known at detection;
7. limitations.

**Audiences.**
- ``local`` keeps actor names, internal ids and evidence-use references.
- ``shareable`` removes them and keeps aggregates and standings.

Neither audience contains unit-level evidence: packets carry only hashes, and reports never carry those either.
No overall reliability score or production approval is defined.
"""
import json
from pathlib import Path

from ..contracts import EvaluationError, digest

STANDING_LABEL = {'D': 'Deterministic violation', 'F': 'Formal sequential evidence', 'P': 'Practical effect (descriptive)',
                  'E': 'Estimate (named assumption)'}
LIMITATIONS = (
    'Alarms concern the included matured observed-label population; they establish neither average risk nor cause.',
    'Hypothesis states are association reasoning over recorded evidence; a supported hypothesis is not an established cause.',
    'Hypothetical replay estimates what a change would have done on recorded inputs and is never merged with production evidence.',
    'Recovery claims R2/R3 concern the average conditional risk since verification started; a causal effect (R4) is not claimed.',
    'Absence of conditions is not evidence of health; read coverage, freshness and detector power alongside.',
    'No overall reliability score or production approval is defined.')


def incident_data(installation, incident_id, *, audience='shareable'):
    from .incidents import incidents as incident_rules
    from .interventions import execution, proposals
    if audience not in ('shareable', 'local'):
        raise EvaluationError('Audience is shareable or local.', 'invalid_audience')
    scope = installation.scope
    view = incident_rules.view(installation, incident_id)
    detection = incident_rules.view(installation, incident_id, as_known='detection')
    incident = view['incident']
    with installation.db.connect() as conn:
        conditions = [dict(r) for r in conn.execute(
            '''SELECT c.id, c.key, c.kind, c.standing, c.severity, c.state, c.first_window, c.last_window, c.signal_count, c.recovery,
                      ic.rule, ic.link FROM ops_incident_conditions ic JOIN ops_conditions c ON c.org_id = ic.org_id AND c.id = ic.condition_id
               WHERE ic.org_id = %s AND ic.incident_id = %s AND ic.removed_at IS NULL ORDER BY ic.joined_at''', (scope.org_id, incident_id)).fetchall()]
        wording = {}
        for row in conn.execute('''SELECT DISTINCT ON (cs.condition_id) cs.condition_id, s.payload FROM ops_condition_signals cs
                                   JOIN ops_signals s ON s.org_id = cs.org_id AND s.id = cs.signal_id WHERE cs.org_id = %s
                                   AND cs.condition_id = ANY(%s) ORDER BY cs.condition_id, s.created_at''',
                                (scope.org_id, [c['id'] for c in conditions])).fetchall():
            wording[row['condition_id']] = row['payload']
        hypotheses = [dict(r) for r in conn.execute('SELECT hypothesis_id, state, reason, evidence FROM ops_hypotheses WHERE org_id = %s '
                                                    'AND incident_id = %s ORDER BY hypothesis_id', (scope.org_id, incident_id)).fetchall()]
        requirements = [dict(r) for r in conn.execute('SELECT observation, status, reason, eta, action, hypotheses FROM ops_requirements '
                                                      'WHERE org_id = %s AND incident_id = %s ORDER BY observation', (scope.org_id, incident_id)).fetchall()]
        runs = [dict(r) for r in conn.execute('SELECT id, template, tier, state, result, error, approved_by, created_at FROM ops_investigation_runs '
                                              'WHERE org_id = %s AND incident_id = %s ORDER BY created_at', (scope.org_id, incident_id)).fetchall()]
        proposal_ids = [r['id'] for r in conn.execute('SELECT id FROM ops_proposals WHERE org_id = %s AND incident_id = %s ORDER BY created_at',
                                                      (scope.org_id, incident_id)).fetchall()]
        verifications = {pid: [dict(r) for r in conn.execute('SELECT claim_id, claim, state, start_window, result FROM ops_verifications '
                                                            'WHERE org_id = %s AND proposal_id = %s ORDER BY claim_id', (scope.org_id, pid)).fetchall()]
                         for pid in proposal_ids}
    comparison = proposals.compare(installation, incident_id)
    proposal_rows = []
    for item in comparison['proposals']:
        pid = __import__('uuid').UUID(item['proposal'])
        proposal_rows.append({**item, 'standings': {k: {'outcome': v['outcome'], 'evidence_kind': v['evidence_kind']}
                                                    for k, v in execution.standings(installation, pid).items()},
                              'verification': [{'claim_id': v['claim_id'], 'claim': v['claim'], 'state': v['state'],
                                                'start_window': v['start_window'],
                                                'wording': (v['result'] or {}).get('wording') or (v['result'] or {}).get('interpretation')}
                                               for v in verifications.get(pid, [])]})
    ladder = {}
    for c in conditions:
        payload = wording.get(c['id']) or {}
        ladder.setdefault(c['standing'], []).append({
            'condition': c['key'], 'state': c['state'], 'severity': c['severity'], 'windows': [c['first_window'], c['last_window']],
            'signals': c['signal_count'], 'joined_by': c['rule'], 'link': (c['link'] or {}).get('link'),
            'wording': payload.get('wording'), 'not_established': payload.get('not_established'),
            'assumptions': payload.get('assumptions'), 'recovery': c['recovery'], 'id': str(c['id'])})
    knowledge = view['knowledge']
    recovery = {'R1': [], 'R2': [], 'R3': []}
    for c in conditions:
        claim = (c['recovery'] or {}).get('claim')
        if claim in recovery and c['state'] == 'recovered':
            recovery[claim].append(c['key'])
    data = {
        'schema_version': 'confidenceguard.incident_report/1.0', 'audience': audience,
        'incident': {'number': incident['number'], 'deployment': incident['deployment_id'], 'state': incident['state'],
                     'priority': incident['priority'], 'priority_why': incident['priority_basis'].get('why'),
                     'priority_rule': incident['priority_basis'].get('rule'), 'priority_table': incident['priority_basis'].get('table'),
                     'impact': incident['priority_basis'].get('impact'), 'opened_at': incident['opened_at'],
                     'resolved_at': incident['resolved_at'], 'resolution': incident['resolution'], 'owner': incident['owner'],
                     'escalation_level': incident['escalation_level'], 'id': str(incident['id'])},
        'ladder': [{'standing': s, 'label': STANDING_LABEL[s], 'conditions': ladder[s]} for s in ('D', 'F', 'P', 'E') if s in ladder],
        'differential': knowledge.get('differential'), 'hypotheses': hypotheses, 'requirements': requirements,
        'investigations': [{'template': r['template'], 'tier': r['tier'], 'state': r['state'],
                            'settled': sorted(((r['result'] or {}).get('observations') or {}).keys()),
                            'refusal': (r['error'] or {}).get('code'), 'approved_by': r['approved_by'], 'id': str(r['id'])} for r in runs],
        'responses': {'proposals': proposal_rows, 'prior_mitigations': comparison['prior_mitigations'], 'qualification': comparison['qualification']},
        'recovery': {'R1_operational': recovery['R1'], 'R2_threshold': recovery['R2'], 'R3_noninferiority': recovery['R3'],
                     'R4_causal': 'not claimed'},
        'timeline': [{'at': e['at'], 'kind': e['kind'], 'actor': e['actor']} for e in view['events']],
        'detection': {'catalog_sequence': incident['catalog_sequence'], 'known_at': detection['knowledge'].get('known_at'),
                      'signals': len(detection['knowledge'].get('signals', [])), 'conditions': len(detection['knowledge'].get('conditions', [])),
                      'dossier_digest': incident['dossier_digest']},
        'knowledge': {'as_known': view['as_known'], 'catalog_sequence': knowledge.get('catalog_sequence')},
        'limitations': list(LIMITATIONS)}
    data = json.loads(json.dumps(data, default=str))
    if audience == 'shareable':
        data = _shareable(data)
    data['report_digest'] = digest(data)
    return data


def _shareable(data):
    """Remove actor names, internal ids and evidence references; keep aggregates and standings."""
    data['incident'].pop('owner', None)
    data['incident'].pop('id', None)
    for rung in data['ladder']:
        for c in rung['conditions']:
            c.pop('id', None)
    for run in data['investigations']:
        run.pop('id', None)
        run.pop('approved_by', None)
    for event in data['timeline']:
        event['actor'] = 'system' if event['actor'] == 'system' else 'operator'
    for proposal in data['responses']['proposals']:
        proposal.pop('proposal', None)
    data['detection'].pop('dossier_digest', None)
    for prior in data['responses']['prior_mitigations']:
        prior.pop('proposal', None)
        prior.pop('incident', None)
    return data


def render(data):
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    env = Environment(loader=FileSystemLoader(Path(__file__).parent.parent / 'templates'), autoescape=select_autoescape(['html']),
                      trim_blocks=True, lstrip_blocks=True)
    return env.get_template('incident_report.html').render(report=data)


def export(installation, incident_id, out, *, format='html', audience='shareable', json_path=None):
    """Write the report (HTML, or PDF with its canonical HTML alongside) and optionally the JSON packet."""
    from .. import compat
    import hashlib
    data = incident_data(installation, incident_id, audience=audience)
    out = Path(out)
    html_path = out if format == 'html' else out.with_suffix('.html')
    html = render(data).encode()
    html_path.write_bytes(html)
    written = {'html': str(html_path), 'report_digest': data['report_digest']}
    if format == 'pdf':
        compat.pdf(html_path, out, hashlib.sha256(html).hexdigest())
        written['pdf'] = str(out)
    if json_path:
        Path(json_path).write_text(json.dumps(data, indent=2, sort_keys=True))
        written['json'] = str(json_path)
    return written
