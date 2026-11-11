"""Observable upstream contamination checks; declarations never erase overlap."""
import re
from ..contracts import EvaluationError,digest
from .contracts import shape,bounded
from ..sources import rows


def validate(provenance):
    member=provenance.get('training_membership')
    if member is None:return
    shape(member,{'namespace','events','units','source_digest'},{'namespace','events','units'})
    if type(member['namespace']) is not str or not member['namespace']:raise EvaluationError('Training membership requires an explicit namespace.')
    for kind in ('events','units'):
        if not isinstance(member[kind],(list,tuple)) or any(type(v) is not str or re.fullmatch('[0-9a-f]{64}',v) is None for v in member[kind]):raise EvaluationError('Training membership requires exact protected SHA-256 identities.')


def assessment_reasons(prepared):
    events=set();units=set()
    for event,unit in rows(prepared.con,f"SELECT event_key,entity_key FROM {prepared.original_table} WHERE cg_role='E'",batch=512):
        events.add(digest([prepared.spec.namespace,event]));units.add(digest([prepared.spec.namespace,unit or event]))
    reasons={}
    for p in prepared.spec.predictors:
        m=p.provenance.get('training_membership')
        if p.provenance.get('independence')=='known_overlap':reasons[p.id]='declared_known_upstream_overlap'
        if m and m['namespace']==prepared.spec.namespace and (events&set(m['events']) or units&set(m['units'])):reasons[p.id]='known_primary_training_assessment_overlap'
    for a in prepared.spec.auxiliaries:
        m=a['membership'];parent=next(p.id for p in prepared.spec.predictors if p.predictor_digest==a['parent_digest'])
        if parent in reasons:reasons[a['id']]=reasons[parent]
        if m.get('namespace')==prepared.spec.namespace and (events&set(m.get('F_events',[])+m.get('S_events',[])) or units&set(m.get('F_units',[])+m.get('S_units',[]))):reasons[a['id']]='known_auxiliary_training_selection_assessment_overlap'
    for group in prepared.spec.ensembles:
        if any(m in reasons for m in group['members']):reasons[group['id']]='ensemble_member_upstream_overlap'
    from ..membership import assessment_membership_passed
    fitted={m['id']:m for m in prepared.spec.fitted_methods}
    checks=getattr(prepared,'method_membership',{})
    for method in prepared.spec.fitted_methods:
        if method['definition']['run'] in reasons:reasons[method['id']]='frozen_method_upstream_overlap'
        if checks.get(method['id'],{}).get('status')=='contradicted':reasons[method['id']]='known_frozen_method_assessment_overlap'
        elif not assessment_membership_passed(method['id'],fitted,set(fitted),checks):
            reasons.setdefault(method['id'],'frozen_method_membership_unavailable')
    return reasons
