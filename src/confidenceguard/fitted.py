"""Bounded data-only fitted methods and independent, immutable assessment bindings."""
import copy
import json
import math
from pathlib import Path
from .contracts import EvaluationError, TaskDefinition, ModelIdentity, digest, strict_json, exact
from .method_contracts import MethodSpec, MethodLimits, FITTED_SCHEMA, ASSESSMENT_SCHEMA, CALIBRATORS, CONFORMAL
from .conformal import read_value, rank
from .calibration import VERSIONS as CAL_VERSIONS
from .conformal import VERSIONS as CON_VERSIONS


def shape_check(value,limits):
    stack=[(value,0,False)]; elements=0; active=set()
    while stack:
        v,depth,leaving=stack.pop()
        if leaving:
            active.remove(id(v));continue
        elements+=1
        if depth>limits.max_nesting or elements>limits.parameter_elements*8:
            raise EvaluationError('Method nesting/element admission exceeded.','method_limit')
        if isinstance(v,(dict,list,tuple)):
            if id(v) in active: raise EvaluationError('Cyclic object references are unsupported.')
            active.add(id(v));stack.append((v,depth,True))
            if isinstance(v,dict):
                if any(not isinstance(k,str) for k in v): raise EvaluationError('JSON object keys must be strings.')
                stack.extend((x,depth+1,False) for x in v.values())
            else: stack.extend((x,depth+1,False) for x in v)
        elif v is not None and not isinstance(v,(str,int,float,bool)): raise EvaluationError('Data-only JSON is required.')
        elif isinstance(v,float) and not math.isfinite(v): raise EvaluationError('Literal nonfinite values are unsupported.')


def bounded_json(raw,limits=None):
    limits=limits or MethodLimits()
    if not isinstance(raw,(str,bytes)): raise EvaluationError('A JSON document is required.')
    if len(raw.encode() if isinstance(raw,str) else raw)>limits.method_bytes: raise EvaluationError('Method byte admission exceeded.','method_limit')
    text=raw.decode('utf-8') if isinstance(raw,bytes) else raw
    # Check JSON framing depth before invoking the recursive standard-library decoder.
    depth=0; quoted=False; escaped=False
    for c in text:
        if quoted:
            if escaped: escaped=False
            elif c=='\\': escaped=True
            elif c=='"': quoted=False
        elif c=='"': quoted=True
        elif c in '[{':
            depth+=1
            if depth>limits.max_nesting: raise EvaluationError('JSON nesting limit exceeded.','method_limit')
        elif c in ']}': depth-=1
    try: value=strict_json(text)
    except (ValueError,RecursionError,UnicodeError) as exc: raise EvaluationError('Invalid method JSON.') from exc
    shape_check(value,limits)
    return value


def task_identity(task):
    value=task.to_dict() if hasattr(task,'to_dict') else task
    return {k:value.get(k) for k in ('kind','outcome_definition','classes','positive_class','units','horizon')}


def model_identity(model):
    value=model.to_dict() if hasattr(model,'to_dict') else model
    return {k:value.get(k) for k in ('id','version','artifact_sha256','preprocessing','calibration')}


def _finite_vector(value,n=None):
    if not isinstance(value,list) or n is not None and len(value)!=n or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in value):
        raise EvaluationError('Fitted coefficients require finite arrays.','invalid_method_parameters')


def validate_method(value,limits=None):
    limits=limits or MethodLimits(); shape_check(value,limits)
    if len(json.dumps(value,allow_nan=False).encode())>limits.method_bytes: raise EvaluationError('Method byte admission exceeded.','method_limit')
    required={'schema_version','id','definition','algorithm_version','task','model','input_signature','parent_digest','parameters','provenance','evidence_state','artifact_digest'}
    if not isinstance(value,dict) or set(value)!=required or value['schema_version']!=FITTED_SCHEMA: raise EvaluationError('Unsupported fitted-method structure.')
    definition=MethodSpec.from_dict(value['definition'])
    if value['id']!=definition.id or value['evidence_state']!='fitted_only': raise EvaluationError('Methods start fitted-only; assessments are separate records.')
    if value['algorithm_version']!={**CAL_VERSIONS,**CON_VERSIONS}[definition.kind]: raise EvaluationError('Unsupported method algorithm version.')
    task=TaskDefinition.from_dict(value['task']); ModelIdentity.from_dict(value['model'])
    if definition.kind in CALIBRATORS and task.kind=='regression' or definition.kind in {'platt','isotonic','beta'} and task.kind!='binary_classification' or definition.kind=='dirichlet' and task.kind!='multiclass_classification':raise EvaluationError('Fitted calibrator/task mismatch.')
    if definition.kind in {'lac','aps','raps'} and task.kind=='regression' or definition.kind in {'split','normalized','cqr'} and task.kind!='regression':raise EvaluationError('Fitted conformal/task mismatch.')
    if not isinstance(value['input_signature'],dict) or not isinstance(value['provenance'],dict): raise EvaluationError('Invalid fitted provenance.')
    if value['parent_digest'] is not None and (not isinstance(value['parent_digest'],str) or len(value['parent_digest'])!=64): raise EvaluationError('Invalid upstream binding.')
    if bool(definition.parent)!=(value['parent_digest'] is not None):raise EvaluationError('Parent identity and digest must agree.')
    if digest({k:v for k,v in value.items() if k!='artifact_digest'})!=value['artifact_digest']: raise EvaluationError('Fitted-method digest differs.','method_digest_mismatch')
    p=value['parameters']; kind=definition.kind; k=len(value['task']['classes'])
    if kind=='raps' and (definition.k_reg>k or not math.isfinite(definition.penalty*max(0,k-definition.k_reg))):raise EvaluationError('RAPS rank/penalty exceeds its class universe or numeric range.')
    if not isinstance(p,dict): raise EvaluationError('Invalid parameters.')
    keys={'identity':set(),'platt':{'coefficients','scalar_scale','mean','sd'},'beta':{'coefficients','regularization'},'isotonic':{'knots','values'},'temperature':{'temperature'},'dirichlet':{'weights','intercepts'}}
    if kind in CALIBRATORS:
        if set(p)!=keys[kind]: raise EvaluationError('Unknown fitted parameter fields.')
        if kind in {'platt','beta'}:
            _finite_vector(p['coefficients'],2 if kind=='platt' else 3)
            if p['coefficients'][0]<0 or kind=='beta' and p['coefficients'][1]<0: raise EvaluationError('Nonmonotone fitted calibration coefficients.')
        if kind=='isotonic':
            _finite_vector(p['knots']); _finite_vector(p['values'],len(p['knots']))
            if len(p['knots'])*2>limits.parameter_elements:raise EvaluationError('Isotonic parameter admission exceeded.','parameter_limit')
            if not p['knots'] or any(a>=b for a,b in zip(p['knots'],p['knots'][1:])) or any(a>b for a,b in zip(p['values'],p['values'][1:])) or any(not 0<=v<=1 for v in p['values']): raise EvaluationError('Invalid isotonic knots.')
        if kind=='dirichlet':
            if not isinstance(p['weights'],list) or len(p['weights'])!=k or k*k+k>limits.parameter_elements: raise EvaluationError('Invalid Dirichlet dimensions.')
            for row in p['weights']: _finite_vector(row,k)
            _finite_vector(p['intercepts'],k)
        for key in ('scalar_scale','mean','sd','temperature','regularization'):
            if key in p:
                _finite_vector([p[key]])
                if key!='mean' and (p[key]<0 if key=='regularization' else p[key]<=0): raise EvaluationError('Invalid positive fitted parameter.')
    else:
        if set(p)!={'thresholds'} or not isinstance(p['thresholds'],list) or len(p['thresholds'])!=len(definition.levels): raise EvaluationError('Invalid conformal thresholds.')
        for t,coverage in zip(p['thresholds'],definition.levels):
            if not isinstance(t,dict) or set(t)!={'coverage','n','rank','threshold'} or t['coverage']!=coverage: raise EvaluationError('Invalid conformal threshold fields.')
            expected=rank(t['n'],coverage)
            if isinstance(t['rank'],bool) or t['rank']!=expected: raise EvaluationError('Conformal rank differs from its level/support.')
            q=read_value(t['threshold'],allowed=('finite','positive_infinity'))
            if math.isinf(q)!=(expected==t['n']+1): raise EvaluationError('Only an unattainable finite rank permits an unbounded threshold.')
            if kind!='cqr' and q<0: raise EvaluationError('This score cannot have a negative threshold.')
            population=value['provenance'].get('calibration_population')
            if not isinstance(population,dict) or population.get('denominator')!=t['n']:raise EvaluationError('Threshold support differs from its frozen calibration population.')
    population=value['provenance'].get('fit_population')
    if population and value['provenance'].get('fit_records')!=population.get('denominator'):raise EvaluationError('Fitted support differs from its population.')
    return copy.deepcopy(value)


class FittedMethod:
    def __init__(self,value,*,limits=None): self._value=validate_method(value,limits)
    @classmethod
    def from_dict(cls,value,*,limits=None):
        if isinstance(value,(str,bytes)): value=bounded_json(value,limits)
        return cls(value,limits=limits)
    @classmethod
    def load(cls,path,*,limits=None,allowed_roots=None):
        from . import compat
        if allowed_roots is not None and not allowed_roots:raise EvaluationError('Authorized roots must not be empty.','roots_required')
        limits=limits or MethodLimits(); roots=allowed_roots if allowed_roots is not None else (str(Path(path).absolute().parent),)
        with compat.secure_open(path,roots) as (f,_): raw=f.read(limits.method_bytes+1)
        return cls.from_dict(raw,limits=limits)
    def to_dict(self): return copy.deepcopy(self._value)
    @property
    def artifact_digest(self): return self._value['artifact_digest']
    def save(self,path):
        from . import compat
        compat.destination(path); compat.publish(path,json.dumps(self._value,sort_keys=True,indent=2,allow_nan=False).encode())
        if Path(path).stat().st_mode&0o077:
            Path(path).chmod(0o600)
        return str(path)


def make_method(spec,task,model,parameters,provenance,input_signature,parent_digest=None,limits=None):
    value={'schema_version':FITTED_SCHEMA,'id':spec.id,'definition':spec.to_dict(),
           'algorithm_version':{**CAL_VERSIONS,**CON_VERSIONS}[spec.kind],
           'task':task.to_dict(),'model':model.to_dict(),'input_signature':input_signature,
           'parent_digest':parent_digest,'parameters':parameters,'provenance':provenance,'evidence_state':'fitted_only'}
    value['artifact_digest']=digest(value)
    return FittedMethod(value,limits=limits)


def compatible(method,task,model,signature,parent_digest=None):
    v=method.to_dict() if isinstance(method,FittedMethod) else method
    if task_identity(v['task'])!=task_identity(task) or model_identity(v['model'])!=model_identity(model) or v['input_signature']!=signature or v['parent_digest']!=parent_digest:
        raise EvaluationError('Method/model/task/input/upstream binding differs.','incompatible_method')


def assessment(method_digest,application_digest,result_id,outcome_snapshot,populations,qualifications,evaluation_digest):
    value={'schema_version':ASSESSMENT_SCHEMA,'method_digest':method_digest,'application_digest':application_digest,
           'result_id':result_id,'evaluation_digest':evaluation_digest,'outcome_snapshot':outcome_snapshot,'population_ids':populations,
           'evidence_state':'independently_evaluated','qualifications':qualifications,
           'meaning':'Independent evaluation is evidence presence, not proof of improvement or future coverage.'}
    value['assessment_digest']=digest(value)
    return value


def validate_assessment(value,*,method_digest=None,application_digest=None):
    required={'schema_version','method_digest','application_digest','result_id','evaluation_digest','outcome_snapshot','population_ids','evidence_state','qualifications','meaning','assessment_digest'}
    if not isinstance(value,dict) or set(value)!=required or value['schema_version']!=ASSESSMENT_SCHEMA or value['evidence_state']!='independently_evaluated' or digest({k:v for k,v in value.items() if k!='assessment_digest'})!=value['assessment_digest']:
        raise EvaluationError('Invalid assessment binding.')
    if method_digest and method_digest!=value['method_digest'] or application_digest and application_digest!=value['application_digest']: raise EvaluationError('Assessment belongs to another method/application.')
    return copy.deepcopy(value)
