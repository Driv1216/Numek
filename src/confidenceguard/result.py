"""Immutable completed evidence, audience projections and strict bundle reopening."""
from dataclasses import dataclass, field
import copy
import json
import re
from .contracts import RESULT_SCHEMA, METHOD, DisclosureSpec, EvaluationSpec, EvaluationConfig, EvaluationError, exact, digest, strict_json


def completed_shape(value):
    for key in ('name','generated_at'):
        if not isinstance(value.get(key),str):raise EvaluationError('Invalid completed result fields.')
    for key in ('task','coverage','outcomes'):
        if not isinstance(value.get(key),dict):raise EvaluationError('Invalid completed result object.')
    for key in ('measurements','runs','findings','checks'):
        if not isinstance(value.get(key),list) or any(not isinstance(v,dict) for v in value[key]):raise EvaluationError('Invalid completed result records.')
    run_ids=[r.get('id') for r in value['runs']]
    if any(not isinstance(v,str) for v in run_ids) or len(set(run_ids))!=len(run_ids):raise EvaluationError('Invalid run identities.')
    ids=[]
    for m in value['measurements']:
        if any(not isinstance(m.get(k),str) for k in ('id','run','scope','family','metric','population_id')):raise EvaluationError('Invalid measurement fields.')
        if m['run'] not in run_ids or m.get('value_state') not in {'finite','undefined','positive_infinity','negative_infinity'} or not isinstance(m.get('data'),dict):raise EvaluationError('Invalid measurement semantics.')
        n=m.get('denominator')
        if isinstance(n,bool) or not (isinstance(n,int) and n>=0 or isinstance(n,str) and n.isascii() and n.isdigit()):raise EvaluationError('Invalid measurement denominator.')
        v=m.get('value')
        if m['value_state']=='finite':
            if isinstance(v,bool) or not isinstance(v,(float,int)):raise EvaluationError('Finite measurements require a number.')
        elif v is not None:raise EvaluationError('Nonfinite/unavailable values require null plus a value-state.')
        ids.append(m['id'])
    if len(set(ids))!=len(ids):raise EvaluationError('Duplicate measurement identities.')
    if value['coverage'].get('population_provenance_version')=='1.1':
        populations=value['coverage'].get('populations',[])
        if not isinstance(populations,list) or any(not isinstance(p,dict) or not isinstance(p.get('id'),str) or p.get('run') not in run_ids or not isinstance(p.get('scope'),str) or p.get('denominator_kind') not in {'eligible_records','evaluation_support','class_conditional_records','paired_base_support','not_evaluated'} for p in populations):raise EvaluationError('Invalid population ledger.')
        ledger={p['id']:p for p in populations}
        if len(ledger)!=len(populations):raise EvaluationError('Duplicate population identities.')
        for m in value['measurements']:
            p=ledger.get(m['population_id'])
            if p is None or any(p.get(k)!=m.get(k) for k in ('run','scope','denominator','denominator_kind')):raise EvaluationError('Measurement population differs from ledger.')
            for c in m['data'].get('classes',[]):
                for key,nkey in [('precision_population_id','predicted'),('recall_population_id','support')]:
                    if key in c and (c[key] not in ledger or any(ledger[c[key]].get(k)!=m[k] for k in ('run','scope')) or ledger[c[key]].get('denominator')!=c.get(nkey)):raise EvaluationError('Class-conditional population differs from support.')
            for side in ('left','right'):
                key=side+'_population_id'
                if key in m['data'] and (m['data'][key] not in ledger or ledger[m['data'][key]].get('denominator')!=m['data'].get(side+'_denominator') or ledger[m['data'][key]].get('run')!=m['data'].get(side+'_run') or ledger[m['data'][key]].get('scope')!=m['scope']):raise EvaluationError('Paired conditional population differs from support.')


@dataclass
class EvaluationResult:
    data: dict
    private: dict = field(repr=False)
    execution: dict = field(default_factory=dict)
    binding: dict = field(default_factory=dict)

    def seal(self):
        payload={**self.data,'execution':self.execution}
        self.private['analysis_digest']=digest(payload)
        self.binding={'analysis_digest':digest(payload),'private_manifest_digest':digest(self.private)}
        return self

    def to_private_dict(self):
        return exact(copy.deepcopy({**self.data,'execution':self.execution,'binding':self.binding}))

    def json_text(self):
        """Private worker protocol: count the whole returned payload, not a redacted view."""
        return json.dumps(exact({'result':self.to_private_dict(),'manifest':self.private}),ensure_ascii=True,allow_nan=False)

    def to_dict(self,audience='shareable',disclosure=None):
        if audience=='local':return self.to_private_dict()
        if audience!='shareable':raise EvaluationError('Unsupported result audience.')
        from .disclosure import project
        return project(self,disclosure)

    @classmethod
    def from_dict(cls,value,*,private=None):
        if isinstance(value,str):value=strict_json(value)
        from .method_contracts import CG2_RESULT,CG2_METHOD
        cg2=isinstance(value,dict) and value.get('schema_version')==CG2_RESULT and value.get('methodology_id')==CG2_METHOD
        if not isinstance(value,dict) or not cg2 and (value.get('schema_version')!=RESULT_SCHEMA or value.get('methodology_id')!=METHOD):raise EvaluationError('Unsupported completed result.')
        if cg2:
            from .fitted import shape_check
            from .method_contracts import MethodLimits
            shape_check(value,MethodLimits())
        if not isinstance(value.get('analysis_id'),str) or not re.fullmatch('[0-9a-f]{32}',value['analysis_id']):raise EvaluationError('Invalid analysis identity.')
        completed_shape(value)
        if value.get('audience')=='shareable':
            if private is not None:raise EvaluationError('A shareable projection cannot be elevated to an exact result.')
            if digest({k:v for k,v in value.items() if k!='projection_digest'})!=value.get('projection_digest'):raise EvaluationError('Shareable projection digest differs.')
            return SharedResult(copy.deepcopy(value))
        required={'schema_version','methodology_id','analysis_id','generated_at','name','task','runs','outcomes','comparison','measurements','checks','findings','coverage','execution','binding'}
        if cg2:required.add('cg2')
        if set(value)!=required or not isinstance(private,dict) or private.get('schema')!='confidenceguard.private_manifest/1.0':raise EvaluationError('Exact reopening requires the protected result and manifest.')
        payload={k:v for k,v in value.items() if k!='binding'};b=value['binding']
        if set(b)!={'analysis_digest','private_manifest_digest'} or digest(payload)!=b['analysis_digest'] or private.get('analysis_digest')!=b['analysis_digest'] or digest(private)!=b['private_manifest_digest'] or private.get('analysis_id')!=value['analysis_id']:raise EvaluationError('Result/manifest identity differs.')
        if not isinstance(value['measurements'],list) or not isinstance(value['runs'],list) or not isinstance(private.get('files'),dict) or not isinstance(private.get('locators'),dict):raise EvaluationError('Invalid result structure.')
        EvaluationSpec.from_dict(private.get('spec'));EvaluationConfig.from_dict(private.get('config'))
        if cg2:
            from .method_contracts import ReliabilitySpec
            from .fitted import FittedMethod,validate_assessment
            from .methods import assessment_basis
            spec=ReliabilitySpec.from_dict(private.get('cg2_spec'))
            methods={m['id']:FittedMethod(m,limits=spec.limits).to_dict() for m in private.get('fitted_methods',[])}
            from .membership import validate as validate_membership,assessment_membership_passed
            imported_ids={m['id'] for m in spec.fitted_methods}
            for sidecar in private.get('membership_sidecars',[]):
                validate_membership(sidecar,spec.limits)
                if not set(sidecar['method_digests'])&{m['artifact_digest'] for m in methods.values()}:raise EvaluationError('Membership sidecar binds no supplied fitted method.')
            cg=value.get('cg2')
            if not isinstance(cg,dict) or set(cg.get('methods',{}))!=set(methods):raise EvaluationError('CG2 method inventory differs.')
            basis=assessment_basis({k:v for k,v in value.items() if k not in {'execution','binding'}})
            if basis!=cg.get('assessment_basis_digest'):raise EvaluationError('CG2 assessment evidence basis differs.')
            apps=cg.get('applications',{})
            if set(apps)!=set(methods):raise EvaluationError('CG2 application inventory differs.')
            for key,method in methods.items():
                app=apps[key]
                if cg['methods'][key].get('evidence_state')!='fitted_only' or cg['methods'][key].get('artifact_digest')!=method['artifact_digest'] or app.get('method_digest')!=method['artifact_digest'] or app.get('evidence_state')!='applied_unvalidated' or digest({k:v for k,v in app.items() if k not in {'application_digest','assessment_eligible'}})!=app.get('application_digest'):raise EvaluationError('CG2 method/application binding differs.')
            populations={p['id'] for p in value['coverage']['populations']}
            ledger={p['id']:p for p in value['coverage']['populations']}
            for state in cg.get('fit_status',{}).values():
                for key in ('fit_population','calibration_population'):
                    pop=state.get(key)
                    if pop is not None and (pop.get('id') not in ledger or ledger[pop['id']]!=pop):raise EvaluationError('Fitting population differs from the completed ledger.')
            for record in cg.get('assessments',[]):
                key=next((k for k,m in methods.items() if m['artifact_digest']==record.get('method_digest')),None)
                if key is None:raise EvaluationError('Assessment refers to an unknown method.')
                validate_assessment(record,method_digest=methods[key]['artifact_digest'],application_digest=apps[key]['application_digest'])
                if record['evaluation_digest']!=basis or record['result_id']!=value['analysis_id'] or record['outcome_snapshot']!=value['outcomes'].get('snapshot_digest') or set(record['population_ids'])-populations or not apps[key].get('assessment_eligible') or not spec.separation.evaluation_independent or not spec.separation.base_predictions_independent:raise EvaluationError('Independent assessment is incompatible with its evidence.')
                if record['qualifications'].get('future_coverage_established') is not False or not assessment_membership_passed(key,methods,imported_ids,cg.get('prior_membership_checks',{})):raise EvaluationError('Assessment contradicts its qualification or prior membership.')
            views=cg.get('evidence_views',{});assessed={r['method_digest'] for r in cg.get('assessments',[])}
            if set(views)!=set(methods):raise EvaluationError('Evidence-state inventory differs.')
            for key,method in methods.items():
                has_assessment=method['artifact_digest'] in assessed;view=views[key]
                if bool(apps[key].get('assessment_eligible'))!=has_assessment or view.get('method_state')!=('independently_evaluated' if has_assessment else 'fitted_only') or view.get('application_state')!=('independently_evaluated' if has_assessment else 'applied_unvalidated') or view.get('method_digest')!=method['artifact_digest'] or view.get('application_digest')!=apps[key]['application_digest']:raise EvaluationError('Evidence state requires its exact independent assessment.')
        ids=[m.get('id') for m in value['measurements'] if isinstance(m,dict)]
        if len(ids)!=len(value['measurements']) or len(set(ids))!=len(ids):raise EvaluationError('Invalid measurement identities.')
        data={k:copy.deepcopy(v) for k,v in value.items() if k not in {'execution','binding'}}
        return cls(data,copy.deepcopy(private),copy.deepcopy(value['execution']),copy.deepcopy(b))

    @property
    def source_paths(self):return tuple(v['path'] for v in self.private['files'].values())

    def generate_artifacts(self,path,**kwargs):
        from .artifacts import generate_artifacts
        return generate_artifacts(self,path,**kwargs)

    def resolve_evidence(self,reference,*,allowed_roots,reveal_values=False,max_characters=240):
        from .private import resolve_evidence
        return resolve_evidence(self,reference,allowed_roots=allowed_roots,reveal_values=reveal_values,max_characters=max_characters)


@dataclass
class SharedResult:
    data: dict
    def to_dict(self,audience='shareable',**kwargs):
        if audience!='shareable':raise EvaluationError('Exact data is unavailable in this projection.')
        from .disclosure import harden_shared
        return harden_shared(self.data)
    def to_private_dict(self):raise EvaluationError('Exact data is unavailable in this projection.')
    def resolve_evidence(self,*args,**kwargs):raise EvaluationError('Exact resolution requires a protected result bundle.')
    def generate_artifacts(self,path,**kwargs):
        from .artifacts import generate_artifacts
        return generate_artifacts(self,path,**kwargs)


@dataclass
class Inspection:
    data: dict
    execution: dict
    def json_text(self):return json.dumps(exact({'data':self.data,'execution':self.execution}),allow_nan=False)
    def to_dict(self):return exact({**self.data,'execution':self.execution})
