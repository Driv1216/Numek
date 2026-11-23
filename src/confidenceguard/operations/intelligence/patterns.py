"""Recurring patterns (plan I.7): deterministic incident signatures and previous mitigations.

An incident's signature is a typed token set:
- the deployment;
- the condition keys of its members;
- the inputs those conditions depend on structurally;
- the hypotheses currently supported;
- the kinds of deployment event in its span.

Similar past incidents are those with a Jaccard similarity of at least 0.6. They are shown with their
resolution, their verification evidence (R1/R2/R3 recovery claims), and any response proposals, which arrive
with S8 interventions.

Similarity is deterministic; there is no learned similarity.
"""
from ...contracts import digest

THRESHOLD = 0.6


def signature(installation, incident_id):
    from ..incidents.incidents import _dependencies
    from . import observations as observation_rules
    ctx = observation_rules.context(installation, incident_id)
    scope = installation.scope
    tokens = {f"deployment:{ctx['incident']['deployment_id']}"}
    with installation.db.connect() as conn:
        for condition in ctx['members']:
            tokens.add(f"condition:{condition['key']}")
            tokens |= {f'input:{x}' for x in _dependencies(conn, scope, condition)['inputs']}
        tokens |= {f"hypothesis:{r['hypothesis_id']}" for r in conn.execute(
            "SELECT hypothesis_id FROM ops_hypotheses WHERE org_id = %s AND incident_id = %s AND state = 'supported'",
            (scope.org_id, incident_id)).fetchall()}
    event = observation_rules.deployment_event(installation, ctx)
    tokens |= {f"event:{e['kind']}" for e in event['evidence'].get('events', [])}
    return sorted(tokens)


def similar(installation, incident_id, *, threshold=THRESHOLD):
    scope = installation.scope
    mine = set(signature(installation, incident_id))
    with installation.db.connect() as conn:
        others = [dict(r) for r in conn.execute(
            "SELECT id, number, deployment_id, resolution, resolution_detail, resolved_at FROM ops_incidents WHERE org_id = %s "
            "AND id <> %s AND state = 'resolved' ORDER BY resolved_at DESC LIMIT 500", (scope.org_id, incident_id)).fetchall()]
    out = []
    for other in others:
        theirs = set(signature(installation, other['id']))
        jaccard = len(mine & theirs) / len(mine | theirs) if mine | theirs else 0.0
        if jaccard >= threshold:
            out.append({'incident': str(other['id']), 'number': other['number'], 'jaccard': jaccard, 'shared': sorted(mine & theirs),
                        'resolution': other['resolution'], 'verification': (other['resolution_detail'] or {}).get('recovery'),
                        'proposals': [], 'note': 'Previous mitigations and their verification; proposals arrive with S8.'})
    return {'incident': str(incident_id), 'signature': sorted(mine), 'signature_digest': digest(sorted(mine)),
            'similar': sorted(out, key=lambda o: (-o['jaccard'], o['number']))}
