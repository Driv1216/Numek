"""Exact source-bound investigation. Original data is never embedded in portable reports."""
import json
from .contracts import EvaluationSpec,EvaluationConfig,EvaluationError,digest
from .sources import records,scalar
from . import compat


def resolve_evidence(result,reference,*,allowed_roots,reveal_values=False,max_characters=240):
    from .result import EvaluationResult
    EvaluationResult.from_dict(result.to_private_dict(),private=result.private)
    if not allowed_roots:raise EvaluationError('Current authorized roots are required.','roots_required')
    if not isinstance(reveal_values,bool):raise EvaluationError('reveal_values must be boolean.')
    if isinstance(max_characters,bool) or not isinstance(max_characters,int) or not 1<=max_characters<=240:raise EvaluationError('Excerpt bound must be 1–240 characters.')
    loc=result.private['locators'].get(reference)
    if not loc:raise EvaluationError('Evidence reference is not retained.','unknown_reference')
    spec=EvaluationSpec.from_dict(result.private['spec']);config=EvaluationConfig.from_dict(result.private['config'])
    resolved=[]
    for location in (loc,*loc.get('related',[])):
        source=next(s for s in spec.sources if s.id==location['source']);info=result.private['files'][source.id]
        compat.capture(source.path,allowed_roots,expected=info)
        record=None
        for coordinate,candidate in records(source.path,source,config):
            if candidate is not None and coordinate['ordinal']==location['ordinal']:record=candidate;break
        if record is None or digest({c:scalar(record.get(c)) for c in location['projection_columns']})!=location['projection_digest']:raise EvaluationError('Exact record is unavailable.','evidence_changed')
        compat.capture(source.path,allowed_roots,expected=info)
        resolved.append((location,record))
    output={'reference':reference,'status':'resolved','location':{'ordinal':loc['ordinal'],'related_ordinals':[l['ordinal'] for l,_ in resolved[1:]]},'values_disclosed':bool(reveal_values)}
    if reveal_values:
        values=[{c:record.get(c) for c in location['columns']} for location,record in resolved]
        raw=json.dumps(values,ensure_ascii=True,allow_nan=False)
        output['excerpt']=raw[:max_characters];output['excerpt_truncated']=len(raw)>max_characters
    return output
