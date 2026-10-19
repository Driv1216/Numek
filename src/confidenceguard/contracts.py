"""Independent, strict ConfidenceGuard contracts (no Flask or analytical imports)."""
from dataclasses import asdict, dataclass, field, fields
import hashlib
import json
import math
from pathlib import Path

SPEC_SCHEMA = 'confidenceguard.evaluation_spec/1.0'
RESULT_SCHEMA = 'confidenceguard.evaluation_result/1.0'
METHOD = 'prediction_evaluation_v1'


class EvaluationError(ValueError):
    def __init__(self, message, code='invalid_specification', stage='validation'):
        super().__init__(message)
        self.code, self.stage = code, stage


def exact(value):
    if isinstance(value, dict): return {str(k): exact(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)): return [exact(v) for v in value]
    if isinstance(value, Path): return str(value)
    if isinstance(value, int) and not isinstance(value, bool) and abs(value) > 2**53-1: return str(value)
    if isinstance(value, float) and not math.isfinite(value): raise ValueError('Nonfinite JSON requires a value_state.')
    return value


def digest(value):
    return hashlib.sha256(json.dumps(exact(value), sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def strict_json(text):
    def pairs(items):
        result = {}
        for k, v in items:
            if k in result: raise EvaluationError('Duplicate JSON object key.')
            result[k] = v
        return result
    def reject(v): raise EvaluationError('Nonfinite JSON is unsupported.')
    def finite(v):
        value=float(v)
        if not math.isfinite(value):reject(v)
        return value
    return json.loads(text, object_pairs_hook=pairs, parse_constant=reject,parse_float=finite)


def choice(value, options, name):
    if value not in options: raise EvaluationError(f'Unsupported {name}.')


def name(value):
    if not isinstance(value, str) or not value or len(value)>512 or any(ord(c)<32 or 0xd800<=ord(c)<=0xdfff for c in value):
        raise EvaluationError('Names and selectors must be nonempty text without control characters.')


def positive(value, label, integer=True):
    if isinstance(value, bool) or not isinstance(value, int if integer else (float,int)) or not math.isfinite(value) or value<=0:
        raise EvaluationError(f'{label} must be positive.')


class Contract:
    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict) or set(value)-{f.name for f in fields(cls)}: raise EvaluationError(f'Invalid {cls.__name__} fields.')
        try: return cls(**value)
        except (TypeError, AttributeError) as exc: raise EvaluationError(f'Invalid {cls.__name__}.') from exc
    def to_dict(self): return exact(asdict(self))


def nested(obj, attr, cls, optional=False):
    value = getattr(obj, attr)
    if optional and value is None: return
    if isinstance(value, dict): value=cls.from_dict(value);object.__setattr__(obj,attr,value)
    if not isinstance(value,cls): raise EvaluationError(f'{attr} requires {cls.__name__}.')


def sequence(obj, attr, cls):
    value=getattr(obj,attr)
    if not isinstance(value,(tuple,list)): raise EvaluationError(f'{attr} requires an array.')
    value=tuple(cls.from_dict(v) if isinstance(v,dict) else v for v in value)
    if any(not isinstance(v,cls) for v in value): raise EvaluationError(f'Invalid {attr}.')
    object.__setattr__(obj,attr,value)


@dataclass(frozen=True)
class SourceSpec(Contract):
    id: str
    path: str
    format: str = 'csv'
    encoding: str = 'utf-8-sig'
    delimiter: str = ','
    def __post_init__(self):
        name(self.id);name(self.path);choice(self.format,{'csv','parquet'},'source format')
        if not isinstance(self.delimiter,str) or len(self.delimiter)!=1: raise EvaluationError('Delimiter must be one character.')


@dataclass(frozen=True)
class ClockSpec(Contract):
    column: str
    encoding: str = 'iso'
    timezone: str | None = None
    format: str | None = None
    epoch_unit: str | None = None
    ambiguity: str = 'unresolved'
    def __post_init__(self):
        name(self.column)
        choice(self.encoding,{'iso','format','epoch'},'clock encoding')
        choice(self.ambiguity,{'unresolved','earlier','later'},'clock ambiguity')
        if self.encoding=='format' and not self.format: raise EvaluationError('Clock format is required.')
        if self.encoding=='epoch': choice(self.epoch_unit,{'s','ms','us','ns'},'epoch unit')


@dataclass(frozen=True)
class TaskDefinition(Contract):
    kind: str
    outcome_definition: str
    classes: tuple = ()
    positive_class: str | None = None
    units: str | None = None
    horizon: str | None = None
    material_error: float | None = None
    def __post_init__(self):
        choice(self.kind,{'binary_classification','multiclass_classification','regression'},'task')
        name(self.outcome_definition)
        if not isinstance(self.classes,(list,tuple)): raise EvaluationError('classes requires an array.')
        object.__setattr__(self,'classes',tuple(self.classes))
        for c in self.classes: name(c)
        if len(set(self.classes))!=len(self.classes): raise EvaluationError('Class names must be unique.')
        if self.kind=='binary_classification' and (len(self.classes)!=2 or self.positive_class not in self.classes): raise EvaluationError('Binary tasks require two classes and a positive class.')
        if self.kind=='multiclass_classification' and len(self.classes)<2: raise EvaluationError('Multiclass tasks require a class universe.')
        if self.kind=='regression' and (self.classes or self.positive_class is not None): raise EvaluationError('Regression has no class universe.')
        if self.material_error is not None: positive(self.material_error,'material_error',False)


@dataclass(frozen=True)
class ModelIdentity(Contract):
    id: str
    version: str
    display_name: str = ''
    artifact_sha256: str | None = None
    preprocessing: str | None = None
    calibration: str | None = None
    def __post_init__(self): name(self.id);name(self.version)


@dataclass(frozen=True)
class ProbabilitySpec(Contract):
    positive_column: str | None = None
    columns: dict = field(default_factory=dict)
    def __post_init__(self):
        if bool(self.positive_column)==bool(self.columns): raise EvaluationError('Use a positive probability column or a complete class mapping.')
        if self.positive_column: name(self.positive_column)
        if not isinstance(self.columns,dict): raise EvaluationError('Probability columns require a mapping.')
        for k,v in self.columns.items(): name(k);name(v)


@dataclass(frozen=True)
class ScoreSpec(Contract):
    column: str | None = None
    columns: dict = field(default_factory=dict)
    direction: str = 'higher'
    meaning: str = 'event_ranking'
    def __post_init__(self):
        if bool(self.column)==bool(self.columns): raise EvaluationError('Scores require a scalar or class mapping.')
        choice(self.direction,{'higher','lower'},'score direction')
        choice(self.meaning,{'event_ranking','class_scores','selection'},'score meaning')
        if self.column: name(self.column)
        if not isinstance(self.columns,dict): raise EvaluationError('Score columns require a mapping.')
        for k,v in self.columns.items(): name(k);name(v)
        if self.columns and self.meaning!='class_scores': raise EvaluationError('Vector scores require class_scores meaning.')
        if self.columns and self.direction!='higher': raise EvaluationError('Comparable class scores require higher-is-preferred semantics for argmax.')


@dataclass(frozen=True)
class DecisionSpec(Contract):
    column: str | None = None
    rule: str = 'none'
    threshold: float | None = None
    tie_policy: str = 'abstain'
    state_column: str | None = None
    state_values: dict = field(default_factory=lambda:{'issued':'issued','abstained':'abstained','failed':'failed','missing':'missing'})
    candidate_evaluation: bool = False
    def __post_init__(self):
        choice(self.rule,{'none','probability_threshold','score_threshold','probability_argmax','score_argmax'},'decision rule')
        choice(self.tie_policy,{'abstain','class_order'},'tie policy')
        for v in (self.column,self.state_column):
            if v: name(v)
        if self.rule.endswith('threshold') and (self.threshold is None or isinstance(self.threshold,bool) or not math.isfinite(self.threshold)): raise EvaluationError('A finite decision threshold is required.')
        if self.rule=='probability_threshold' and not 0<=self.threshold<=1: raise EvaluationError('Probability thresholds require [0,1].')
        if not isinstance(self.state_values,dict) or any(v not in {'issued','abstained','failed','missing'} for v in self.state_values.values()): raise EvaluationError('Invalid issuance state mapping.')
        if not isinstance(self.candidate_evaluation,bool): raise EvaluationError('candidate_evaluation must be boolean.')


@dataclass(frozen=True)
class PredictionIntervalSpec(Contract):
    id: str
    lower: str
    upper: str
    coverage: float
    meaning: str = 'prediction'
    central: bool = True
    provenance: str = 'supplied'
    def __post_init__(self):
        for v in (self.id,self.lower,self.upper): name(v)
        if isinstance(self.coverage,bool) or not 0<self.coverage<1: raise EvaluationError('Interval coverage must lie inside (0,1).')
        choice(self.meaning,{'prediction','mean_confidence','parameter_confidence'},'interval meaning')
        if not isinstance(self.central,bool): raise EvaluationError('central must be boolean.')


@dataclass(frozen=True)
class PredictionRunSpec(Contract):
    id: str
    source: str
    model: ModelIdentity
    key_columns: tuple = ()
    prediction: str | None = None
    decision: DecisionSpec = field(default_factory=DecisionSpec)
    probabilities: ProbabilitySpec | None = None
    score: ScoreSpec | None = None
    selection: ScoreSpec | None = None
    intervals: tuple = ()
    prediction_at: ClockSpec | None = None
    generated_at: str | None = None
    role: str = 'unknown'
    inline_outcome: str | None = None
    inline_outcome_role: str = 'agreement_assertion'
    horizon: str | None = None
    entity_columns: tuple = ()
    def __post_init__(self):
        name(self.id);name(self.source);nested(self,'model',ModelIdentity);nested(self,'decision',DecisionSpec)
        for attr,cls in [('probabilities',ProbabilitySpec),('score',ScoreSpec),('selection',ScoreSpec),('prediction_at',ClockSpec)]: nested(self,attr,cls,True)
        sequence(self,'intervals',PredictionIntervalSpec)
        for attr in ('key_columns','entity_columns'):
            value=getattr(self,attr)
            if not isinstance(value,(list,tuple)): raise EvaluationError(f'{attr} requires an array.')
            for v in value:name(v)
            object.__setattr__(self,attr,tuple(value))
        choice(self.role,{'unknown','train','calibration','selection','evaluation','production'},'evaluation role')
        choice(self.inline_outcome_role,{'agreement_assertion','non_authoritative_copy'},'inline outcome role')
        if len(self.intervals)>3: raise EvaluationError('CG1 supports up to three interval levels per run.')
        if self.selection and (not self.selection.column or self.selection.meaning!='selection'): raise EvaluationError('Selection requires an explicit scalar selection score.')


@dataclass(frozen=True)
class OutcomeSnapshotSpec(Contract):
    source: str
    column: str
    key_columns: tuple = ()
    snapshot_name: str | None = None
    status_column: str | None = None
    status_values: dict = field(default_factory=lambda:{'final':'final','observed':'observed','provisional':'provisional','invalid':'invalid','conflicting':'conflicting'})
    available_at: ClockSpec | None = None
    due_at: ClockSpec | None = None
    target_at: ClockSpec | None = None
    def __post_init__(self):
        name(self.source);name(self.column)
        if not isinstance(self.key_columns,(tuple,list)): raise EvaluationError('Outcome keys require an array.')
        object.__setattr__(self,'key_columns',tuple(self.key_columns))
        for v in self.key_columns:name(v)
        for attr in ('available_at','due_at','target_at'):nested(self,attr,ClockSpec,True)
        if not isinstance(self.status_values,dict) or any(v not in {'final','observed','provisional','invalid','conflicting'} for v in self.status_values.values()): raise EvaluationError('Invalid outcome status mapping.')


@dataclass(frozen=True)
class ContextSnapshotSpec(Contract):
    source: str
    key_columns: tuple = ()
    assertions: dict = field(default_factory=dict)
    def __post_init__(self):
        name(self.source)
        if not isinstance(self.key_columns,(list,tuple)): raise EvaluationError('Context keys require an array.')
        object.__setattr__(self,'key_columns',tuple(self.key_columns))
        if not isinstance(self.assertions,dict) or any(not isinstance(v,dict) for v in self.assertions.values()): raise EvaluationError('Context assertions map run IDs and canonical columns to run columns.')


@dataclass(frozen=True)
class CohortSpec(Contract):
    id: str
    column: str
    categories: tuple = ()
    edges: tuple = ()
    prediction_derived: bool = False
    def __post_init__(self):
        name(self.id);name(self.column)
        if not isinstance(self.categories,(list,tuple)) or not isinstance(self.edges,(list,tuple)): raise EvaluationError('Cohort categories/edges require arrays.')
        object.__setattr__(self,'categories',tuple(self.categories));object.__setattr__(self,'edges',tuple(self.edges))
        if bool(self.categories)==bool(self.edges): raise EvaluationError('Declare cohort categories or fixed numerical edges.')
        if self.categories:
            for v in self.categories:name(v)
            if len(set(self.categories))!=len(self.categories):raise EvaluationError('Duplicate cohort categories.')
        if self.edges and (len(self.edges)<2 or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in self.edges) or any(a>=b for a,b in zip(self.edges,self.edges[1:]))): raise EvaluationError('Cohort edges must be finite and increasing.')
        if not isinstance(self.prediction_derived,bool):raise EvaluationError('prediction_derived must be boolean.')


@dataclass(frozen=True)
class DecisionPolicySpec(Contract):
    id: str
    run: str
    kind: str
    thresholds: tuple = ()
    interval: str | None = None
    costs: dict = field(default_factory=dict)
    def __post_init__(self):
        name(self.id);name(self.run)
        choice(self.kind,{'probability_threshold','score_threshold','confidence_abstention','selection_abstention','interval_abstention','supplied_cost'},'policy')
        if not isinstance(self.thresholds,(list,tuple)):raise EvaluationError('Policy thresholds require an array.')
        object.__setattr__(self,'thresholds',tuple(self.thresholds))
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in self.thresholds):raise EvaluationError('Policy thresholds must be finite.')
        if self.kind in {'probability_threshold','confidence_abstention'} and any(not 0<=v<=1 for v in self.thresholds):raise EvaluationError('Probability cutoffs require [0,1].')
        if not isinstance(self.costs,dict) or any(not isinstance(v,dict) or any(isinstance(c,bool) or not isinstance(c,(int,float)) or not math.isfinite(c) for c in v.values()) for v in self.costs.values()):raise EvaluationError('Costs map actions to outcomes to finite costs.')


@dataclass(frozen=True)
class ComparisonSpec(Contract):
    left: str
    right: str
    def __post_init__(self):
        name(self.left);name(self.right)
        if self.left==self.right:raise EvaluationError('Comparison requires distinct runs.')


@dataclass(frozen=True)
class DisclosureSpec(Contract):
    policy: str = 'conservative_aggregates_v1'
    minimum_denominator: int = 10
    minimum_component: int = 10
    display_labels: dict = field(default_factory=dict)
    schema_version: str = 'confidenceguard.disclosure/1.0'
    def __post_init__(self):
        if self.schema_version!='confidenceguard.disclosure/1.0':raise EvaluationError('Unsupported disclosure schema.')
        choice(self.policy,{'conservative_aggregates_v1','exact_aggregates_v1'},'disclosure policy')
        positive(self.minimum_denominator,'minimum_denominator');positive(self.minimum_component,'minimum_component')
        if not isinstance(self.display_labels,dict):raise EvaluationError('display_labels requires a mapping.')
        for k,v in self.display_labels.items():name(k);name(v)


@dataclass(frozen=True)
class SamplingSpec(Contract):
    mode: str = 'descriptive'
    def __post_init__(self):choice(self.mode,{'descriptive','independent_rows'},'sampling mode')


@dataclass(frozen=True)
class EvaluationConfig(Contract):
    max_source_bytes: int = 5*1024**3
    max_combined_source_bytes: int = 8*1024**3
    max_rows: int = 10000000
    max_combined_rows: int = 30000000
    max_columns: int = 1000
    memory_bytes: int = 2*1024**3
    max_rss_bytes: int = 6*1024**3
    threads: int = 2
    batch_bytes: int = 32*1024**2
    max_record_bytes: int = 8*1024**2
    workspace_bytes: int = 64*1024**3
    free_disk_bytes: int = 2*1024**3
    max_seconds: float = 1800
    result_bytes: int = 32*1024**2
    private_bytes: int = 64*1024**2
    probability_cells: int = 100000000
    max_cohorts: int = 4
    max_groups: int = 32
    max_classes: int = 256
    max_policies: int = 16
    max_thresholds: int = 201
    max_details: int = 100
    witnesses: int = 5
    curve_points: int = 201
    calibration_bins: int = 10
    support_warning: int = 100
    bin_support_warning: int = 20
    high_confidence: float = .9
    probability_tolerance: float = 1e-6
    scratch_directory: str | None = None
    sampling: SamplingSpec = field(default_factory=SamplingSpec)
    disclosure: DisclosureSpec = field(default_factory=DisclosureSpec)
    def __post_init__(self):
        nested(self,'sampling',SamplingSpec);nested(self,'disclosure',DisclosureSpec)
        for f in fields(self):
            if f.name not in {'sampling','disclosure','scratch_directory','high_confidence','probability_tolerance'}:positive(getattr(self,f.name),f.name,f.name!='max_seconds')
        if not 0<self.high_confidence<=1 or not 0<=self.probability_tolerance<=1e-3:raise EvaluationError('Invalid probability diagnostic settings.')
        if self.curve_points<2:raise EvaluationError('curve_points requires at least two points.')


@dataclass(frozen=True)
class EvaluationSpec(Contract):
    task: TaskDefinition
    sources: tuple
    runs: tuple
    outcomes: OutcomeSnapshotSpec | None = None
    context: ContextSnapshotSpec | None = None
    cohorts: tuple = ()
    policies: tuple = ()
    comparison: ComparisonSpec | None = None
    as_of: str | None = None
    name: str = 'ConfidenceGuard evaluation'
    schema_version: str = SPEC_SCHEMA
    def __post_init__(self):
        nested(self,'task',TaskDefinition)
        for attr,cls in [('sources',SourceSpec),('runs',PredictionRunSpec),('cohorts',CohortSpec),('policies',DecisionPolicySpec)]:sequence(self,attr,cls)
        for attr,cls in [('outcomes',OutcomeSnapshotSpec),('context',ContextSnapshotSpec),('comparison',ComparisonSpec)]:nested(self,attr,cls,True)
        if self.schema_version!=SPEC_SCHEMA:raise EvaluationError('Unsupported evaluation schema.')
        if not 1<=len(self.runs)<=2:raise EvaluationError('CG1 requires one or two prediction runs.')
        for values in (self.sources,self.runs,self.cohorts,self.policies):
            if len({v.id for v in values})!=len(values):raise EvaluationError('Duplicate declaration IDs.')
        sids={s.id for s in self.sources};rids={r.id for r in self.runs}
        if not sids or any(r.source not in sids for r in self.runs):raise EvaluationError('Unknown prediction source.')
        if any(x and x.source not in sids for x in (self.outcomes,self.context)):raise EvaluationError('Unknown outcome/context source.')
        if self.comparison and {self.comparison.left,self.comparison.right}-rids:raise EvaluationError('Unknown compared run.')
        if self.comparison and any(not r.key_columns for r in self.runs):raise EvaluationError('Paired comparisons require explicit keys.')
        if len(self.runs)>1 and not self.outcomes and any(r.inline_outcome for r in self.runs):raise EvaluationError('Choose one authoritative outcome binding before comparing inline outcomes.')
        if self.as_of and (not self.outcomes or not self.outcomes.available_at):raise EvaluationError('as_of requires outcome availability.')
        if self.cohorts and not (self.context or self.outcomes):raise EvaluationError('Cohorts require canonical context.')
        if any(p.run not in rids for p in self.policies):raise EvaluationError('Unknown policy run.')
        for r in self.runs:
            if r.probabilities:
                if r.probabilities.positive_column and self.task.kind!='binary_classification':raise EvaluationError('Positive probability columns require a binary task.')
                if r.probabilities.columns and set(r.probabilities.columns)!=set(self.task.classes):raise EvaluationError('Probability mappings must cover the class universe.')
            if r.score and (r.score.columns and set(r.score.columns)!=set(self.task.classes) or r.score.column and (r.score.meaning!='event_ranking' or self.task.kind!='binary_classification')):raise EvaluationError('Invalid task score representation.')
            if r.intervals and self.task.kind!='regression':raise EvaluationError('Intervals require regression.')
            rule=r.decision.rule
            if rule.startswith('probability') and not r.probabilities:raise EvaluationError('Probability derivation requires probabilities.')
            if rule.startswith('score') and not r.score:raise EvaluationError('Score derivation requires scores.')
            if rule.endswith('threshold') and self.task.kind!='binary_classification':raise EvaluationError('Threshold decisions require binary classification.')
            if rule=='score_argmax' and not r.score.columns:raise EvaluationError('Score argmax requires a complete class vector.')
        name(self.name)

    @classmethod
    def from_dict(cls,value,*,base_directory=None):
        import copy
        value=copy.deepcopy(value)
        if base_directory is not None:
            for s in value.get('sources',[]):s['path']=str(Path(base_directory)/s['path']) if not Path(s['path']).is_absolute() else s['path']
        return super().from_dict(value)


OutcomeSpec = OutcomeSnapshotSpec
