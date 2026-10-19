"""CG2 declarations. CG1 contracts and defaults remain unchanged."""
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
import copy
import math

from .contracts import (Contract, EvaluationSpec, EvaluationConfig, EvaluationError,
                        ComparisonSpec, DecisionPolicySpec, nested, sequence, choice, name, positive)

CG2_SPEC = 'confidenceguard.evaluation_spec/1.1'
CG2_RESULT = 'confidenceguard.evaluation_result/1.1'
CG2_METHOD = 'calibration_uncertainty_v1'
STUDY_SCHEMA = 'confidenceguard.study_spec/1.0'
APPLICATION_SCHEMA = 'confidenceguard.application_spec/1.0'
FITTED_SCHEMA = 'confidenceguard.fitted_method/1.0'
ASSESSMENT_SCHEMA = 'confidenceguard.assessment/1.0'
CALIBRATORS = {'identity', 'platt', 'isotonic', 'beta', 'temperature', 'dirichlet'}
CONFORMAL = {'lac', 'aps', 'raps', 'split', 'normalized', 'cqr'}


def finite(value, label, minimum=None):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise EvaluationError(f'{label} requires a finite number.')
    if minimum is not None and value < minimum:
        raise EvaluationError(f'{label} is outside its domain.')


def level(value):
    try:
        if isinstance(value, bool): raise InvalidOperation
        if not isinstance(value,(str,int,float)) or len(str(value))>160:raise InvalidOperation
        d = Decimal(str(value))
        if not d.is_finite() or not 0 < d < 1 or d.as_tuple().exponent < -128: raise InvalidOperation
    except (InvalidOperation, ValueError):
        raise EvaluationError('Levels must be decimal numbers strictly inside (0,1).')
    text=format(d,'f')
    return text.rstrip('0').rstrip('.') if '.' in text else text


@dataclass(frozen=True)
class QuantileField(Contract):
    level: str
    column: str
    def __post_init__(self):
        object.__setattr__(self, 'level', level(self.level)); name(self.column)


@dataclass(frozen=True)
class SampleSpec(Contract):
    source: str
    key_columns: tuple
    draw_column: str
    value_column: str
    meaning: str = 'empirical_distribution'
    def __post_init__(self):
        name(self.source); name(self.draw_column); name(self.value_column)
        if not isinstance(self.key_columns, (list, tuple)) or not self.key_columns:
            raise EvaluationError('Predictive samples require explicit event keys.')
        object.__setattr__(self, 'key_columns', tuple(self.key_columns))
        for v in self.key_columns: name(v)
        choice(self.meaning, {'empirical_distribution', 'iid_monte_carlo'}, 'sample meaning')


@dataclass(frozen=True)
class RepresentationSpec(Contract):
    run: str
    logits: dict = field(default_factory=dict)
    binary_logit: str | None = None
    scale: str | None = None
    scale_model: dict | None = None
    quantiles: tuple = ()
    quantile_model: dict | None = None
    samples: SampleSpec | None = None
    def __post_init__(self):
        name(self.run); sequence(self, 'quantiles', QuantileField); nested(self, 'samples', SampleSpec, True)
        if not isinstance(self.logits, dict): raise EvaluationError('Logits require a class mapping.')
        for k, v in self.logits.items(): name(k); name(v)
        if self.logits and self.binary_logit: raise EvaluationError('Choose vector logits or binary log-odds.')
        for v in (self.binary_logit, self.scale):
            if v is not None: name(v)
        levels = [Decimal(q.level) for q in self.quantiles]
        if levels != sorted(set(levels)): raise EvaluationError('Quantile levels must be unique and increasing.')
        for binding in (self.scale_model, self.quantile_model):
            if binding is not None:
                from .contracts import ModelIdentity
                ModelIdentity.from_dict(binding)
        if self.scale and not self.scale_model: raise EvaluationError('A supplied scale requires its predictor identity.')
        if self.quantiles and not self.quantile_model: raise EvaluationError('Supplied quantiles require their predictor identity.')


@dataclass(frozen=True)
class RolePartition(Contract):
    role: str
    source: str
    key_columns: tuple
    def __post_init__(self):
        choice(self.role, {'F','S','C','E'}, 'partition role'); name(self.source)
        if not isinstance(self.key_columns, (list, tuple)) or not self.key_columns:
            raise EvaluationError('Role partitions require keys.')
        object.__setattr__(self, 'key_columns', tuple(self.key_columns))
        for v in self.key_columns: name(v)


@dataclass(frozen=True)
class RoleSpec(Contract):
    namespace: str
    column: str | None = None
    values: dict = field(default_factory=lambda: {'F':'F', 'S':'S', 'C':'C', 'E':'E'})
    partitions: tuple = ()
    proportions: dict = field(default_factory=dict)
    seed: int = 0
    unit: str = 'event'
    def __post_init__(self):
        name(self.namespace); sequence(self, 'partitions', RolePartition)
        choice(self.unit, {'event','entity'}, 'separation unit')
        if sum(bool(v) for v in (self.column, self.partitions, self.proportions)) != 1:
            raise EvaluationError('Choose a role column, explicit partitions, or seeded proportions.')
        if self.column: name(self.column)
        if not isinstance(self.values, dict) or any(v not in {'F','S','C','E'} for v in self.values.values()):
            raise EvaluationError('Role values map to F/S/C/E.')
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0: raise EvaluationError('Invalid seed.')
        if self.proportions:
            if set(self.proportions)-{'F','S','C','E'}: raise EvaluationError('Invalid split roles.')
            for v in self.proportions.values(): finite(v, 'split proportion', 0)
            if abs(math.fsum(self.proportions.values())-1)>1e-12: raise EvaluationError('Split proportions must sum to one.')


@dataclass(frozen=True)
class SeparationSpec(Contract):
    base_predictions_independent: bool = False
    evaluation_independent: bool = False
    exchangeable_scores: bool = False
    labels_representative: bool = False
    preserve_membership: bool = True
    training_partitions: tuple = ()
    def __post_init__(self):
        for attr in ('base_predictions_independent','evaluation_independent','exchangeable_scores','labels_representative','preserve_membership'):
            if not isinstance(getattr(self, attr), bool): raise EvaluationError('Independence declarations must be boolean.')
        sequence(self, 'training_partitions', RolePartition)


@dataclass(frozen=True)
class MethodSpec(Contract):
    id: str
    kind: str
    run: str
    input: str = 'probabilities'
    parent: str | None = None
    levels: tuple = ('0.9',)
    epsilon: float = 1e-15
    regularization: float | None = None
    penalty: float = 0.0
    k_reg: int = 0
    lower_quantile: str = '0.05'
    upper_quantile: str = '0.95'
    max_iterations: int = 1000
    tolerance: float = 1e-8
    def __post_init__(self):
        name(self.id); name(self.run); choice(self.kind, CALIBRATORS|CONFORMAL, 'method')
        choice(self.input, {'probabilities','probability_logit','score','logits','point','normalized','quantiles'}, 'method input')
        if self.parent: name(self.parent)
        if not isinstance(self.levels, (tuple,list)) or not self.levels: raise EvaluationError('Method levels require an array.')
        object.__setattr__(self, 'levels', tuple(level(v) for v in self.levels))
        if len(set(self.levels)) != len(self.levels): raise EvaluationError('Duplicate method levels.')
        finite(self.epsilon, 'epsilon')
        if not 0 < self.epsilon < .01: raise EvaluationError('Invalid logarithmic epsilon.')
        if self.regularization is not None: finite(self.regularization, 'regularization', 0)
        if self.kind=='dirichlet' and (self.regularization is None or self.regularization<=0):
            raise EvaluationError('Dirichlet requires explicit positive identity-L2 regularization.')
        finite(self.penalty, 'RAPS penalty', 0)
        if isinstance(self.k_reg,bool) or not isinstance(self.k_reg,int) or self.k_reg<0: raise EvaluationError('Invalid RAPS rank cutoff.')
        positive(self.max_iterations, 'max_iterations'); positive(self.tolerance, 'tolerance', False)
        object.__setattr__(self, 'lower_quantile', level(self.lower_quantile))
        object.__setattr__(self, 'upper_quantile', level(self.upper_quantile))
        if Decimal(self.lower_quantile)>=Decimal(self.upper_quantile): raise EvaluationError('CQR quantiles must be ordered.')


@dataclass(frozen=True)
class SelectionSpec(Contract):
    id: str
    candidates: tuple
    objective: str = 'log_loss'
    coverage_tolerance: float | None = None
    pilot_fraction: float = .5
    def __post_init__(self):
        name(self.id)
        if not isinstance(self.candidates,(tuple,list)) or not self.candidates: raise EvaluationError('Selection requires candidates.')
        object.__setattr__(self,'candidates',tuple(self.candidates))
        for v in self.candidates: name(v)
        if len(set(self.candidates))!=len(self.candidates): raise EvaluationError('Duplicate selection candidates.')
        choice(self.objective, {'log_loss','brier','efficiency'}, 'selection objective')
        if self.coverage_tolerance is not None:
            finite(self.coverage_tolerance,'coverage tolerance',0)
            if self.coverage_tolerance>=1: raise EvaluationError('Coverage tolerance must be below one.')
        finite(self.pilot_fraction,'pilot fraction')
        if not 0<self.pilot_fraction<1: raise EvaluationError('Pilot fraction must lie inside (0,1).')


@dataclass(frozen=True)
class InferenceSpec(Contract):
    mode: str = 'descriptive'
    confidence: float = .95
    replicates: int = 2000
    seed: int = 0
    adjustment: str = 'pointwise'
    metrics: tuple = ()
    scopes: tuple = ('paired',)
    inference_required: bool = False
    work_units: int = 1000000000
    minimum_tail: int = 20
    material_difference: float | None = None
    def __post_init__(self):
        choice(self.mode, {'descriptive','independent_rows','independent_clusters'}, 'inference mode')
        choice(self.adjustment, {'pointwise','bonferroni'}, 'confidence adjustment')
        finite(self.confidence,'confidence')
        if not 0<self.confidence<1: raise EvaluationError('Invalid confidence level.')
        for attr in ('replicates','work_units','minimum_tail'): positive(getattr(self,attr),attr)
        if isinstance(self.seed,bool) or not isinstance(self.seed,int) or self.seed<0: raise EvaluationError('Invalid inference seed.')
        if not isinstance(self.inference_required,bool): raise EvaluationError('inference_required must be boolean.')
        if not isinstance(self.metrics,(list,tuple)): raise EvaluationError('Inference metrics require an array.')
        object.__setattr__(self,'metrics',tuple(self.metrics))
        for v in self.metrics: name(v)
        if len(set(self.metrics))!=len(self.metrics): raise EvaluationError('Duplicate inference metrics.')
        if not isinstance(self.scopes,(list,tuple)) or not self.scopes or len(set(self.scopes))!=len(self.scopes): raise EvaluationError('Declare unique inference scopes.')
        object.__setattr__(self,'scopes',tuple(self.scopes))
        for v in self.scopes:name(v)
        if self.mode!='descriptive' and not self.metrics: raise EvaluationError('Declare inferential contrasts before outcomes are inspected.')
        if self.material_difference is not None: finite(self.material_difference,'material difference',0)


@dataclass(frozen=True)
class MethodLimits(Contract):
    candidates: int = 16
    variants: int = 16
    parameter_elements: int = 1000000
    sample_cells: int = 100000000
    method_bytes: int = 64*1024**2
    max_nesting: int = 32
    def __post_init__(self):
        for k,v in self.to_dict().items(): positive(v,k)


@dataclass(frozen=True)
class ReliabilitySpec(Contract):
    evaluation: EvaluationSpec
    roles: RoleSpec
    representations: tuple = ()
    methods: tuple = ()
    selections: tuple = ()
    fitted_methods: tuple = ()
    membership_sidecars: tuple = ()
    comparisons: tuple = ()
    variant_policies: tuple = ()
    separation: SeparationSpec = field(default_factory=SeparationSpec)
    inference: InferenceSpec = field(default_factory=InferenceSpec)
    limits: MethodLimits = field(default_factory=MethodLimits)
    calibration_edges: tuple = ()
    calibration_strategy: str = 'fixed'
    output_path: str | None = None
    schema_version: str = CG2_SPEC
    def __post_init__(self):
        nested(self,'evaluation',EvaluationSpec); nested(self,'roles',RoleSpec)
        choice(self.calibration_strategy,{'fixed','fit_equal_frequency'},'calibration bin strategy')
        if self.calibration_strategy=='fit_equal_frequency' and self.calibration_edges:raise EvaluationError('Choose explicit edges or fit-derived equal-frequency bins.')
        for attr,cls in [('representations',RepresentationSpec),('methods',MethodSpec),('selections',SelectionSpec),('comparisons',ComparisonSpec),('variant_policies',DecisionPolicySpec)]: sequence(self,attr,cls)
        for attr,cls in [('separation',SeparationSpec),('inference',InferenceSpec),('limits',MethodLimits)]: nested(self,attr,cls)
        choice(self.schema_version,{CG2_SPEC,STUDY_SCHEMA,APPLICATION_SCHEMA},'CG2 schema')
        runs={r.id:r for r in self.evaluation.runs}; sources={s.id for s in self.evaluation.sources}
        if any(not r.key_columns for r in runs.values()): raise EvaluationError('CG2 requires explicit event keys for every base run.')
        if self.roles.unit=='entity' and any(not r.entity_columns for r in runs.values()): raise EvaluationError('Entity separation requires entity columns.')
        for items in (self.methods,self.selections,self.representations):
            ids=[getattr(v,'id',getattr(v,'run',None)) for v in items]
            if len(ids)!=len(set(ids)): raise EvaluationError('Duplicate CG2 declarations.')
        if any(r.run not in runs for r in self.representations) or any(m.run not in runs for m in self.methods): raise EvaluationError('Unknown CG2 base run.')
        for rep in self.representations:
            if self.evaluation.task.kind!='regression' and (rep.scale or rep.quantiles or rep.samples):raise EvaluationError('Regression scale/quantile/sample bindings require a regression task.')
            if rep.logits and set(rep.logits)!=set(self.evaluation.task.classes): raise EvaluationError('Logits must cover the complete class universe.')
            if rep.binary_logit and self.evaluation.task.kind!='binary_classification': raise EvaluationError('Scalar logits require binary classification.')
            if rep.samples and rep.samples.source not in sources: raise EvaluationError('Unknown sample source.')
        for p in (*self.roles.partitions,*self.separation.training_partitions):
            if p.source not in sources: raise EvaluationError('Unknown role/training partition source.')
        if len(self.methods)>self.limits.candidates: raise EvaluationError('Method candidate admission exceeded.','candidate_limit')
        mids={m.id for m in self.methods}; family_ids={s.id for s in self.selections}
        selected_ids=[mid for s in self.selections for mid in s.candidates]
        if len(selected_ids)!=len(set(selected_ids)):raise EvaluationError('A candidate belongs to one selection family; declare separate candidate IDs for separate fits.')
        for s in self.selections:
            if set(s.candidates)-mids: raise EvaluationError('Unknown selection candidate.')
            members=[m for m in self.methods if m.id in s.candidates]
            if len({m.run for m in members})!=1: raise EvaluationError('Selection families use one frozen base model.')
            conformal=all(m.kind in CONFORMAL for m in members)
            if conformal!=(s.objective=='efficiency') or not conformal and any(m.kind not in CALIBRATORS for m in members): raise EvaluationError('Selection objective does not match its method family.')
            if conformal and len({m.levels for m in members})!=1: raise EvaluationError('Conformal selection requires identical nominal levels.')
        if not isinstance(self.fitted_methods,(tuple,list)) or any(not isinstance(v,dict) for v in self.fitted_methods): raise EvaluationError('Fitted methods require data-only objects.')
        object.__setattr__(self,'fitted_methods',tuple(copy.deepcopy(self.fitted_methods)))
        if not isinstance(self.membership_sidecars,(tuple,list)):raise EvaluationError('Membership sidecars require an array.')
        object.__setattr__(self,'membership_sidecars',tuple(copy.deepcopy(self.membership_sidecars)))
        imported={v.get('id') for v in self.fitted_methods}
        if len(imported)!=len(self.fitted_methods) or imported & mids: raise EvaluationError('Duplicate fitted/method identifiers.')
        if any(p.run not in mids|imported for p in self.variant_policies) or len({p.id for p in (*self.evaluation.policies,*self.variant_policies)})!=len(self.evaluation.policies)+len(self.variant_policies):raise EvaluationError('Variant policies require unique IDs and explicit derived runs.')
        if len({(p.left,p.right) for p in self.comparisons})!=len(self.comparisons):raise EvaluationError('Duplicate comparison edges.')
        for m in self.methods:
            if m.parent and m.parent not in mids|imported and m.parent not in {'selected:'+s for s in family_ids}: raise EvaluationError('Unknown parent method.')
        if self.output_path is not None: name(self.output_path)
        if not isinstance(self.calibration_edges,(list,tuple)): raise EvaluationError('Calibration edges require an array.')
        edges=tuple(self.calibration_edges)
        if edges and (len(edges)<2 or edges[0]!=0 or edges[-1]!=1 or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in edges) or any(a>=b for a,b in zip(edges,edges[1:]))): raise EvaluationError('Calibration edges must increase from zero to one.')
        object.__setattr__(self,'calibration_edges',edges)

    @classmethod
    def from_dict(cls,value,*,base_directory=None):
        value=copy.deepcopy(value)
        if isinstance(value,dict) and base_directory is not None:
            value['evaluation']=EvaluationSpec.from_dict(value.get('evaluation'),base_directory=base_directory)
            if value.get('output_path') and not Path(value['output_path']).is_absolute(): value['output_path']=str(Path(base_directory)/value['output_path'])
        return super().from_dict(value)


MethodStudySpec = ReliabilitySpec
ApplicationSpec = ReliabilitySpec


def parse_spec(value, *, base_directory=None):
    if isinstance(value,(EvaluationSpec,ReliabilitySpec)): return copy.deepcopy(value)
    if not isinstance(value,dict): raise EvaluationError('A typed specification is required.')
    cls=ReliabilitySpec if value.get('schema_version') in {CG2_SPEC,STUDY_SCHEMA,APPLICATION_SCHEMA} else EvaluationSpec
    return cls.from_dict(value,base_directory=base_directory)
