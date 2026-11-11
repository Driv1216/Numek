"""Finite auxiliary studies and immutable executable artifact descriptors."""
from dataclasses import dataclass,field
import copy

from ..contracts import Contract,EvaluationError,nested,sequence,choice,name,digest,positive
from ..feature_contracts import FeatureField
from ..execution.contracts import ExecutionSpec,PredictorSpec,bounded,shape,finite


@dataclass(frozen=True)
class AuxiliaryCandidate(Contract):
    id: str
    family: str
    seed: int = 0
    parameters: dict = field(default_factory=dict)
    ensemble_members: int | None = None

    def __post_init__(self):
        name(self.id);choice(self.family,{'constant','logistic','histogram','mlp','mlp_ensemble'},'auxiliary family')
        ensemble=self.family=='mlp_ensemble'
        if self.ensemble_members is None:object.__setattr__(self,'ensemble_members',5 if ensemble else 1)
        if ensemble:object.__setattr__(self,'family','mlp')
        if type(self.seed) is not int or self.seed<0:raise EvaluationError('Invalid fit seed.')
        positive(self.ensemble_members,'ensemble_members')
        if self.ensemble_members>16 or self.ensemble_members>1 and self.family!='mlp':raise EvaluationError('Only bounded MLP ensembles may be fitted.')
        shape(self.parameters,{'iterations','learning_rate','max_leaf_nodes','min_samples_leaf','hidden','weight_decay','batch_rows','epochs','patience','C'})
        object.__setattr__(self,'parameters',bounded(self.parameters))
        for k in ('iterations','max_leaf_nodes','min_samples_leaf','batch_rows','epochs','patience'):
            if k in self.parameters:positive(self.parameters[k],k)
        for k in ('learning_rate','C'):
            if k in self.parameters:finite(self.parameters[k],k,minimum=1e-15)
        if 'weight_decay' in self.parameters:finite(self.parameters['weight_decay'],'weight_decay',minimum=0)


@dataclass(frozen=True)
class AuxiliaryStudySpec(Contract):
    execution: ExecutionSpec
    kind: str
    base_predictor: str
    inputs: tuple = ()
    candidates: tuple = ()
    levels: tuple = (.1,.5,.9)
    failure: str = 'error'
    material_error: float | None = None
    high_confidence_threshold: float = .9
    scale_floor: float = 1e-6
    s_tuning_fraction: float = .5
    prediction_features: tuple = ()
    quantile_rearrange: bool = False
    schema_version: str = 'confidenceguard.auxiliary_study_spec/1.0'

    def __post_init__(self):
        nested(self,'execution',ExecutionSpec);sequence(self,'inputs',FeatureField);sequence(self,'candidates',AuxiliaryCandidate)
        choice(self.kind,{'scale','quantiles','failure_risk'},'auxiliary target')
        choice(self.failure,{'error','material_error','high_confidence_error','execution_failure'},'failure target')
        if self.base_predictor not in {p.id for p in self.execution.predictors}:raise EvaluationError('Auxiliary parent predictor is absent.')
        if self.execution.roles is None:raise EvaluationError('Explicit F/S/C/E separation is required.','auxiliary_roles')
        if self.inputs and any(f.outcome_derived or f.role=='retrospective' for f in self.inputs):raise EvaluationError('Outcome-derived auxiliary inputs are prohibited.')
        if self.kind in {'scale','quantiles'} and self.execution.task.kind!='regression':raise EvaluationError('Scale/quantile fitting requires regression.')
        if self.failure=='material_error' and self.material_error is None:raise EvaluationError('Material-error target requires a threshold.')
        if self.kind=='failure_risk' and self.execution.task.kind=='regression' and self.failure!='execution_failure' and (self.failure!='material_error' or self.material_error is None):raise EvaluationError('Regression failure risk requires a declared material-error threshold.')
        outcome=self.execution.outcomes
        if outcome and outcome.source==self.execution.input_source and any(f.column in {outcome.column,outcome.status_column} for f in self.inputs):raise EvaluationError('Authoritative outcome columns cannot be auxiliary inputs.','outcome_input')
        if self.material_error is not None:finite(self.material_error,'material error',minimum=0)
        finite(self.high_confidence_threshold,'high-confidence threshold',minimum=0)
        if self.high_confidence_threshold>1:raise EvaluationError('High-confidence threshold must not exceed one.')
        finite(self.scale_floor,'scale floor',minimum=1e-15)
        if not 0<self.s_tuning_fraction<1:raise EvaluationError('S tuning fraction must be inside (0,1).')
        if not isinstance(self.levels,(list,tuple)) or not self.levels or tuple(sorted(set(self.levels)))!=tuple(self.levels) or any(type(v) not in (int,float) or not 0<v<1 for v in self.levels):raise EvaluationError('Ordered quantile levels required.')
        object.__setattr__(self,'levels',tuple(self.levels))
        if set(self.prediction_features)-{'point','confidence','score','entropy'}:raise EvaluationError('Unsupported frozen prediction feature.')
        object.__setattr__(self,'prediction_features',tuple(self.prediction_features))
        if type(self.quantile_rearrange) is not bool:raise EvaluationError('quantile_rearrange requires a Boolean.')
        if not self.candidates:
            defaults=[AuxiliaryCandidate('constant','constant')]
            if self.kind=='failure_risk':defaults.append(AuxiliaryCandidate('logistic','logistic'))
            defaults.extend([AuxiliaryCandidate('histogram','histogram'),AuxiliaryCandidate('mlp','mlp')])
            object.__setattr__(self,'candidates',tuple(defaults))
        if len(self.candidates)>self.execution.limits.max_candidates or len({c.id for c in self.candidates})!=len(self.candidates):raise EvaluationError('Auxiliary candidate admission exceeded.')
        fits=sum(c.ensemble_members*(len(self.levels) if c.family=='histogram' and self.kind=='quantiles' else 1) for c in self.candidates)
        if fits>self.execution.limits.max_fits:raise EvaluationError('Auxiliary fit admission exceeded.','auxiliary_fit_limit')
        if self.schema_version!='confidenceguard.auxiliary_study_spec/1.0':raise EvaluationError('Unsupported auxiliary study.')


def artifact_basis(value):
    result=copy.deepcopy(value);result.pop('artifact_digest',None)
    for p in result.get('predictors',[]):
        p.pop('retention',None)
        if not p.get('execution_view_only'):p.pop('execution_view_only',None)
        for output in p.get('outputs',[]):
            if not output.get('mapping'):output.pop('mapping',None)
        for f in p.get('files',[]):f.pop('path',None)
    return result


@dataclass(frozen=True)
class AuxiliaryArtifact(Contract):
    id: str
    kind: str
    predictors: tuple
    parent_digest: str
    target: dict
    membership: dict
    selection: dict
    artifact_digest: str
    schema_version: str = 'confidenceguard.auxiliary_artifact/1.0'

    def __post_init__(self):
        name(self.id);choice(self.kind,{'scale','quantiles','failure_risk'},'auxiliary kind');sequence(self,'predictors',PredictorSpec)
        for key in ('target','membership','selection'):object.__setattr__(self,key,bounded(getattr(self,key)))
        if not self.predictors or self.schema_version!='confidenceguard.auxiliary_artifact/1.0' or digest(artifact_basis(self.to_dict()))!=self.artifact_digest:raise EvaluationError('Auxiliary artifact binding differs.','auxiliary_changed')
        if set(self.membership)-{'namespace','F_events','S_events','F_units','S_units','fit_data_digest','selection_data_digest','upstream_provenance'}:raise EvaluationError('Invalid auxiliary membership.')

    @classmethod
    def create(cls,**kwargs):
        kwargs['schema_version']='confidenceguard.auxiliary_artifact/1.0'
        raw={**kwargs,'predictors':[p.to_dict() if isinstance(p,PredictorSpec) else p for p in kwargs['predictors']]}
        raw['artifact_digest']=digest(artifact_basis(raw));return cls.from_dict(raw)
