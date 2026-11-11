"""Lossless feature normalization and explicit availability; no learned transforms."""
from decimal import Decimal, InvalidOperation
import math
import re
from .contracts import ClockSpec, EvaluationError, digest
from .feature_contracts import FeatureField
from . import compat

STATES={'observed','missing','invalid','unavailable','not_retained'}
FEATURE_TIME_POLICY='declared_information_cutoff_v2'


def information_cutoff(view,row):
    """Retain the declared owner clock, including missing/invalid states."""
    if view.information_cutoff is None:return None
    tick,state=compat.clock((row or {}).get(view.information_cutoff.column),view.information_cutoff)
    return {'policy':FEATURE_TIME_POLICY,'clock':view.information_cutoff.to_dict(),
            'tick_ns':str(tick) if tick is not None else None,'state':state}


def outcome_bound_fields(evaluation,views,source_identities=None):
    """Observable direct label bindings, including byte-identical source aliases.

    This is a positive contamination check, not proof that other columns or
    externally supplied representations are independent of outcomes.
    """
    outcome=evaluation.effective_outcomes
    if outcome is None:return set()
    identities=source_identities or {};target=identities.get(outcome.source,{})
    outcome_columns={outcome.column}
    if outcome.status_column:outcome_columns.add(outcome.status_column)
    runs={r.id:r for r in evaluation.runs};found=set()
    for view in views:
        run=runs.get(view.run or evaluation.runs[0].id)
        if run is None:continue
        source=view.source or run.source;identity=identities.get(source,{})
        same=source==outcome.source or bool(target.get('sha256') and identity.get('sha256')==target['sha256'] and identity.get('bytes')==target.get('bytes'))
        if same:found.update(view.id+'.'+field.id for field in view.fields if field.column in outcome_columns)
    return found


def predicate_masks(cells, clause, cache=None):
    """Exact masks for an internally frozen feature population.

    The optional cache is owned by one discovery operation, never persisted or
    accepted from a request. Retaining the cells guards object-identity reuse;
    callers must not mutate their sealed population. Arrays are read-only and
    admission stops retaining masks at 32 MiB. Uncached computation is identical.
    """
    import numpy as np
    key=('structured_predicate',id(cells),digest(clause))
    if cache is not None and key in cache:
        original,valid,mask=cache[key]
        if original is not cells:raise AssertionError('Structured population identity changed.')
        return valid,mask
    valid=np.array([c['state'] not in {'unavailable','not_retained'} for c in cells])
    mask=np.array([predicate(c,clause['op'],clause['value'],clause['kind']) for c in cells])
    if cache is not None:
        used=cache.get('_structured_mask_bytes',0);size=valid.nbytes+mask.nbytes
        if used+size<=32*1024**2:
            valid.flags.writeable=False;mask.flags.writeable=False
            cache[key]=(cells,valid,mask);cache['_structured_mask_bytes']=used+size
    return valid,mask


def normalize(value, field, *, available_ns=None, effective_ns=None, availability_state='undeclared', source_type='lexical'):
    if isinstance(field,dict): field=FeatureField.from_dict(field)
    lexical=value if isinstance(value,str) else str(value) if value is not None else None
    result={'kind':field.kind,'state':'observed','lexical':lexical,'canonical':None,
            'available_ns':str(available_ns) if available_ns is not None else None,
            'effective_ns':str(effective_ns) if effective_ns is not None else None,
            'availability_state':availability_state,'source_type':source_type}
    if lexical is None or lexical in field.missing_values:
        result['state']='missing'; return result
    if any(0xd800<=ord(c)<=0xdfff for c in lexical): result['state']='invalid'; return result
    try:
        if field.kind in {'categorical','text','asset'}: canonical=lexical
        elif field.kind=='boolean':
            if lexical in field.boolean_true: canonical='true'
            elif lexical in field.boolean_false: canonical='false'
            else: raise ValueError('Invalid Boolean spelling')
        elif field.kind=='integer':
            if not re.fullmatch(r'[+-]?[0-9]+',lexical) or len(lexical)>1024: raise ValueError('Invalid integer')
            canonical=str(int(lexical))
        elif field.kind=='decimal':
            if len(lexical)>1024: raise ValueError('Numeric token bound')
            number=Decimal(lexical)
            if not number.is_finite() or abs(number.as_tuple().exponent)>10000: raise ValueError('Invalid decimal')
            # as_tuple avoids context-dependent Decimal.normalize rounding.
            sign,digits,exponent=number.as_tuple(); digits=list(digits)
            while len(digits)>1 and digits[-1]==0: digits.pop(); exponent+=1
            if not any(digits): canonical='0e0'
            else: canonical=('-' if sign else '')+''.join(map(str,digits))+'e'+str(exponent)
        elif field.kind=='float':
            number=float(lexical)
            if not math.isfinite(number) or number==0 and Decimal(lexical)!=0: raise ValueError('Nonfinite or underflow')
            canonical=number.hex()
        elif field.kind=='timestamp':
            tick,state=compat.clock(lexical,ClockSpec(field.column))
            if state!='valid': raise ValueError('Invalid instant')
            canonical=str(tick)
        else: raise ValueError('Unknown type')
        result['canonical']=canonical
    except (ValueError,InvalidOperation,OverflowError): result['state']='invalid'
    return result


def value(cell):
    if cell['state']!='observed': return None
    kind=cell['kind']; canonical=cell['canonical']
    if kind in {'integer','timestamp'}: return int(canonical)
    if kind=='decimal': return Decimal(canonical)
    if kind=='float': return float.fromhex(canonical)
    if kind=='boolean': return canonical=='true'
    return canonical


def learner_number(cell):
    """A lossy diagnostic conversion is never an exact predicate conversion."""
    number=value(cell)
    if number is None:return None,'not_observed'
    try:
        converted=float(number)
        if not math.isfinite(converted):return None,'not_representable'
        if converted==0 and number!=0:return None,'underflow'
        exact=(int(converted)==number) if isinstance(number,int) else Decimal.from_float(converted)==number if isinstance(number,Decimal) else True
        return converted,'exact' if exact else 'rounded'
    except (ValueError,OverflowError,TypeError):return None,'not_representable'


def predicate(cell,op,bound,kind):
    if op=='state':return cell['state']==bound
    if cell['state']!='observed':return False
    actual=value(cell)
    def canonical(v):return value({'state':'observed','kind':kind,'canonical':v})
    if op=='not_in':return actual not in {canonical(v) for v in bound}
    if op=='interval':return canonical(bound[0])<actual<=canonical(bound[1])
    target=canonical(bound)
    return actual==target if op=='eq' else actual<=target if op=='le' else actual>target


def apply_availability(cell, *, view, cutoff_ns=None, as_of_ns=None, declaration='unknown',cutoff_state=None):
    result=dict(cell)
    tick=cell.get('available_ns')
    limit=cutoff_ns if view=='available_at_decision' else as_of_ns
    allowed=declaration=='at_decision' and view=='available_at_decision' or declaration=='at_decision' and (as_of_ns is None or cutoff_ns is None or cutoff_ns<=as_of_ns)
    if tick is not None: allowed=limit is not None and int(tick)<=int(limit)
    if view=='available_at_decision' and cutoff_state is not None and cutoff_state!='valid':allowed=False
    if not allowed:
        result['state']='unavailable';result['canonical']=None
    return result


def feature_projection(spec, evaluation):
    projections={s.id:set() for s in evaluation.sources}
    runs={r.id:r for r in evaluation.runs}
    for view in spec.features:
        run=runs.get(view.run or spec.objectives[0].run)
        if run is None: raise EvaluationError('Feature view binds an unknown run.')
        sid=view.source or run.source
        if sid not in projections: raise EvaluationError('Feature view source is absent.')
        projections[sid].update(view.key_columns or run.key_columns)
        projections[sid].update(f.column for f in view.fields)
        for clock in (view.available_at,view.information_cutoff,*(f.available_at for f in view.fields),*(f.effective_at for f in view.fields)):
            if clock: projections[sid].add(clock.column)
    if spec.roles.column:
        for run in evaluation.runs: projections[run.source].add(spec.roles.column)
    return projections


def missing_cell(kind, state='not_retained'):
    if state not in STATES: raise EvaluationError('Invalid feature state.')
    return {'kind':kind,'state':state,'lexical':None,'canonical':None,'available_ns':None,
            'effective_ns':None,'availability_state':'undeclared','source_type':'unretained'}
