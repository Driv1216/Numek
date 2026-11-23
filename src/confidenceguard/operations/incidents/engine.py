"""One operations step for a deployment: signals → conditions → incidents, then time-based transitions."""
from . import conditions, incidents


def operate(installation, deployment_id, *, now, actor='system'):
    folded = conditions.process(installation, deployment_id, now=now, actor=actor)
    first = incidents.handle(installation, deployment_id, folded, now=now, actor=actor)
    timed = conditions.tick(installation, deployment_id, now=now, actor=actor)
    second = incidents.handle(installation, deployment_id, timed, now=now, actor=actor)
    from ..interventions import verification
    verified = verification.refresh_all(installation, deployment_id, now=now)
    return {'deployment': deployment_id, 'condition_changes': len(folded) + len(timed),
            'opened': first['opened'] + second['opened'], 'joined': first['joined'] + second['joined'],
            'revised': sorted(set(first['revised']) | set(second['revised'])), 'verifications': verified}
