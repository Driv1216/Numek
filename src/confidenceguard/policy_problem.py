"""Admitted development problem: no database, source or E accessor crosses here."""
from dataclasses import dataclass,replace
from types import SimpleNamespace
import math
from decimal import Decimal
from .contracts import EvaluationError
from .policy_runtime import read_value

@dataclass(frozen=True)
class DevelopmentProblem:
    task: object
    anchor: str
    limits: object
    budget: object
    input: object
    frames: dict
    identities: dict
    phase: str = 'selection'

    def materialize(self,run,role):
        if role!='S': raise EvaluationError('Optimizer admission contains development evidence only.','policy_role_sealed')
        if run not in self.frames: raise EvaluationError('Policy run was not admitted.','policy_run')
        return self.frames[run]

    def bind_policy(self,policy):
        from .policy_contracts import referenced_runs,validate_bound_references
        if policy.task!=self.task: raise EvaluationError('Policy task differs from admitted development evidence.','incompatible_policy_input')
        identity=dict(self.identities.get(policy.run,{}))
        if identity:
            refs=referenced_runs(policy.to_dict(),identity['features'])
            if refs:
                if set(refs)-self.identities.keys():raise EvaluationError('Referenced upstream run is absent.','policy_input_contract')
                identity['referenced_runs']={key:self.identities[key] for key in refs}
            validate_bound_references(policy,identity)
        if identity is None or policy.input_identity and policy.input_identity!=identity: raise EvaluationError('Policy input semantics differ.','incompatible_policy_input')
        return replace(policy,input_identity=identity)

    def cutpoints(self,run,role,value):
        events,_=self.materialize(run,role); values=set()
        for event in events:
            v,state=read_value(value,event,run,self.budget)
            if state=='observed' and isinstance(v,(float,int,Decimal)) and not isinstance(v,bool) and math.isfinite(v): values.add(v)
            if len(values)>self.limits.max_cutpoints: raise EvaluationError('Cutpoint admission exceeded.','policy_cutpoint_limit')
        return [str(v) if isinstance(v,Decimal) else v for v in sorted(values)]


def admit(pstore,study):
    runs=set([pstore.anchor]+[p.run for p in (*study.candidates,*study.baselines)]+[f.template['run'] for f in study.families])
    from .policy_optimization import bind
    prototypes=[bind(f.template,{p.id:p.values[0] if p.values else 0 for p in f.parameters}) for f in study.families]
    pstore.project([*study.candidates,*study.baselines,*prototypes])
    # Other finite options may reference additional registered upstream runs.
    def scan(v):
        if isinstance(v,dict):
            if v.get('kind') in __import__('confidenceguard.policy_contracts',fromlist=['VALUE_KINDS']).VALUE_KINDS and v.get('run'):pstore.projected_runs.add(v['run'])
            for x in v.values():scan(x)
        elif isinstance(v,(list,tuple)):
            for x in v:scan(x)
    for family in study.families:
        for parameter in family.parameters:scan(parameter.values)
    if pstore.projected_runs-pstore.runs.keys():raise EvaluationError('Finite option references an undeclared run.','policy_run')
    frames={run:pstore.materialize(run,'S') for run in sorted(runs)}
    from .policy_optimization import all_metrics
    from .policy_metrics import _ranking
    native={}
    for metric in all_metrics(study).values():
        if metric.metric not in {'roc_auc','average_precision'}: continue
        for run in runs:
            from .policy_contracts import PolicySpec
            policy=PolicySpec(pstore.task,run,{'root':{'kind':'action','action':{'kind':'supplied'}}},'root',{'kind':'abstain'},{'kind':'unavailable'})
            events,records=frames[run]
            native[(run,metric.id)]=_ranking(metric,events,records,policy,pstore.budget)
    # Budget is a counter/limit interface, with immutable precomputed native S
    # diagnostics replacing its preparation-only native reducer reference.
    pstore.budget.policy_native_rankings=native
    pstore.budget.policy_store=None
    return DevelopmentProblem(pstore.task,pstore.anchor,pstore.limits,pstore.budget,SimpleNamespace(batches=pstore.input.batches),frames,{run:pstore.policy_identity(run) for run in pstore.runs})
