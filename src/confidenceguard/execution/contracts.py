"""CG6 data contracts. No executable imports, SQL, or browser dependencies."""
from dataclasses import dataclass, field
import copy
import math
import re

from ..contracts import (Contract, EvaluationError, TaskDefinition, SourceSpec,
                        DecisionSpec, OutcomeSnapshotSpec, CohortSpec, nested,
                        sequence, choice, name, positive, digest, ClockSpec)
from ..feature_contracts import FeatureField
from ..method_contracts import RoleSpec

METHOD = 'predictor_robustness_v1'
RESULT = 'confidenceguard.execution_result/1.0'


def shape(value, allowed, required=()):
    if not isinstance(value, dict) or set(value)-set(allowed) or set(required)-set(value):
        raise EvaluationError('Unknown or missing CG6 declaration fields.', 'execution_contract')
    return value


def finite(value, label='number', minimum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or minimum is not None and value < minimum:
        raise EvaluationError(f'Invalid {label}.', 'execution_contract')
    return value


def strings(values, label, required=False):
    if not isinstance(values, (tuple, list)) or required and not values:
        raise EvaluationError(f'{label} requires an array.', 'execution_contract')
    for v in values: name(v)
    if len(set(values)) != len(values):
        raise EvaluationError(f'Duplicate {label}.', 'execution_contract')
    return tuple(values)


def bounded(value, *, max_bytes=8*1024**2, max_depth=24):
    """Admit JSON before copying; disallow arbitrary Python objects."""
    import json
    def visit(v, depth):
        if depth > max_depth: raise EvaluationError('Declaration depth exceeded.', 'execution_limit')
        if type(v) is dict:
            if any(type(k) is not str for k in v): raise EvaluationError('JSON keys require text.')
            for x in v.values(): visit(x, depth+1)
        elif type(v) in (tuple, list):
            for x in v: visit(x, depth+1)
        elif type(v) is float: finite(v)
        elif v is not None and type(v) not in (str, int, bool): raise EvaluationError('Data-only declarations required.')
    visit(value, 0)
    if len(json.dumps(value, allow_nan=False).encode()) > max_bytes:
        raise EvaluationError('Declaration bytes exceeded.', 'execution_limit')
    return copy.deepcopy(value)


def design_fingerprint(input_fingerprint,options):
    design={k:v for k,v in options.items() if k not in {'reservation','exposure_checks'}}
    return digest({'inputs':input_fingerprint,'design':design}) if design else input_fingerprint


@dataclass(frozen=True)
class ArtifactFile(Contract):
    name: str
    path: str
    sha256: str

    def __post_init__(self):
        name(self.path)
        from pathlib import PurePosixPath
        p = PurePosixPath(self.name)
        if p.is_absolute() or '..' in p.parts or not p.parts or '\\' in self.name:
            raise EvaluationError('Artifact names must be safe relative names.', 'artifact_path')
        if not re.fullmatch('[0-9a-f]{64}', self.sha256): raise EvaluationError('Artifact SHA-256 required.')


@dataclass(frozen=True)
class DeviceSpec(Contract):
    kind: str = 'cpu'
    index: int = 0
    precision: str = 'float32'
    allow_cpu_fallback: bool = False
    deterministic: bool = True
    onnx_mode: str = 'strict'
    memory_bytes: int = 2*1024**3

    def __post_init__(self):
        choice(self.kind, {'cpu','mps','cuda','auto'}, 'device')
        choice(self.precision, {'float32','float64','float16'}, 'execution precision')
        choice(self.onnx_mode, {'strict','hybrid'}, 'ONNX placement')
        if type(self.index) is not int or self.index < 0: raise EvaluationError('Invalid device index.')
        if self.kind != 'cuda' and self.index: raise EvaluationError('Only CUDA accepts a device index.')
        if any(type(v) is not bool for v in (self.allow_cpu_fallback,self.deterministic)): raise EvaluationError('Boolean device settings required.')
        if self.kind == 'mps' and self.precision == 'float64': raise EvaluationError('MPS float64 is unsupported.', 'device_precision')
        positive(self.memory_bytes, 'device memory budget')


@dataclass(frozen=True)
class ExecutionLimits(Contract):
    batch_rows: int = 1024
    modality_batch_rows: int = 32
    batch_tensor_bytes: int = 64*1024**2
    max_artifact_bytes: int = 2*1024**3
    max_artifact_files: int = 128
    max_predictors: int = 16
    max_variants: int = 10000000
    max_output_cells: int = 100000000
    max_tokens: int = 256
    max_tokens_work: int = 20000000
    max_image_pixels: int = 16000000
    max_queries: int = 1000000
    max_candidates: int = 8
    max_fits: int = 64
    max_inference_retries: int = 3
    cache_bytes: int = 64*1024**2
    retained_rows: int = 1000

    def __post_init__(self):
        from dataclasses import fields
        for f in fields(self):
            v=getattr(self,f.name)
            if f.name in {'max_inference_retries','cache_bytes'}:
                if type(v) is not int or v<0: raise EvaluationError('Invalid execution limit.')
            else: positive(v,f.name)
        if self.max_inference_retries>3: raise EvaluationError('At most three inference halvings are admitted.')


@dataclass(frozen=True)
class OutputBinding(Contract):
    channel: str
    source: str = 'output'
    indices: tuple = ()
    classes: tuple = ()
    levels: tuple = ()
    activation: str = 'none'
    direction: str = 'higher'
    meaning: str = 'event_ranking'
    mapping: dict = field(default_factory=dict)

    def __post_init__(self):
        choice(self.channel, {'prediction','point','probabilities','logits','score','scale','quantiles','samples','issuance','risk'}, 'output channel')
        name(self.source)
        object.__setattr__(self,'classes',strings(self.classes,'output classes'))
        if not isinstance(self.indices,(tuple,list)) or any(type(i) is not int or i<0 for i in self.indices): raise EvaluationError('Invalid output indices.')
        object.__setattr__(self,'indices',tuple(self.indices))
        if not isinstance(self.levels,(tuple,list)) or any(isinstance(v,bool) or not isinstance(v,(float,int)) or not 0<v<1 for v in self.levels): raise EvaluationError('Invalid quantile levels.')
        if tuple(sorted(set(self.levels)))!=tuple(self.levels): raise EvaluationError('Quantile levels must increase strictly.')
        object.__setattr__(self,'levels',tuple(self.levels))
        if (self.channel=='quantiles') != bool(self.levels): raise EvaluationError('Quantile outputs require explicit levels.')
        choice(self.activation, {'none','sigmoid','softmax'}, 'output activation')
        if self.activation!='none' and self.channel!='probabilities': raise EvaluationError('Activation is only a declared probability postprocessor.')
        choice(self.direction, {'higher','lower'}, 'score direction')
        choice(self.meaning, {'event_ranking','selection','class_scores'}, 'score meaning')
        if self.channel=='score' and self.classes and (self.meaning!='class_scores' or self.direction!='higher'):raise EvaluationError('Vector scores require explicit comparable class-score semantics.')
        if self.mapping and (self.channel not in {'prediction','issuance'} or any(type(k) is not str or type(v) is not str for k,v in self.mapping.items())):raise EvaluationError('Discrete output mappings require named label/state values.')
        object.__setattr__(self,'mapping',bounded(self.mapping))


@dataclass(frozen=True)
class PredictorSpec(Contract):
    id: str
    task: TaskDefinition
    adapter: str
    inputs: tuple
    outputs: tuple
    files: tuple = ()
    entry: str | None = None
    preprocessing: dict = field(default_factory=dict)
    architecture: dict = field(default_factory=dict)
    decision: DecisionSpec = field(default_factory=DecisionSpec)
    registration: str | None = None
    runtime: dict = field(default_factory=dict)
    provenance: dict = field(default_factory=dict)
    retention: str = 'copy'
    execution_view_only: bool = False
    schema_version: str = 'confidenceguard.predictor_spec/1.0'

    def __post_init__(self):
        name(self.id); nested(self,'task',TaskDefinition); nested(self,'decision',DecisionSpec)
        if self.decision.column is not None or self.decision.state_column is not None:raise EvaluationError('Predictor decisions use output bindings, not source-column bindings.')
        choice(self.retention,{'copy','reference'},'model retention')
        if type(self.execution_view_only) is not bool:raise EvaluationError('Execution-view state must be Boolean.')
        choice(self.adapter, {'sklearn','onnx','torch','custom','constant'}, 'predictor adapter')
        sequence(self,'inputs',FeatureField);sequence(self,'outputs',OutputBinding);sequence(self,'files',ArtifactFile)
        if not self.inputs or len({v.id for v in self.inputs})!=len(self.inputs): raise EvaluationError('Unique predictor inputs required.')
        if any(v.outcome_derived or v.role=='retrospective' for v in self.inputs): raise EvaluationError('Outcome-derived inputs cannot execute as decision inputs.', 'outcome_input')
        if not self.outputs or len({v.channel for v in self.outputs})!=len(self.outputs): raise EvaluationError('Unique output channels required.')
        if len({v.name for v in self.files})!=len(self.files): raise EvaluationError('Duplicate artifact names.')
        if self.adapter in {'sklearn','onnx','torch'} and (not self.entry or self.entry not in {v.name for v in self.files}): raise EvaluationError('Predictor entry must name an admitted file.')
        if self.adapter=='custom' and not self.registration: raise EvaluationError('Custom predictors require a host registration.')
        for f in ('preprocessing','architecture','runtime','provenance'): object.__setattr__(self,f,bounded(getattr(self,f)))
        from .provenance import validate as validate_provenance
        validate_provenance(self.provenance)
        for output in self.outputs:
            if output.classes and not set(output.classes)<=set(self.task.classes): raise EvaluationError('Output classes differ from task.')
            if output.channel=='probabilities' and not output.classes: raise EvaluationError('Probability class order must be explicit.')
            if output.channel=='probabilities' and len(output.classes) not in {len(self.task.classes),1 if self.task.kind=='binary_classification' else len(self.task.classes)}: raise EvaluationError('Complete class probabilities required.')
        shape(self.preprocessing, {'kind','dtype','tensor_name','tensor_names','mean','scale','fill','categories','tokenizer','padding_id','image_size','image_mean','image_scale','tensor_file','keys_source','key_columns','values','scale_floor','quantile_rearrange'})
        choice(self.preprocessing.get('kind','tabular'), {'tabular','numeric','text','image','tensor'}, 'input representation')
        if self.schema_version!='confidenceguard.predictor_spec/1.0': raise EvaluationError('Unsupported predictor schema.')

    @property
    def predictor_digest(self):
        value=self.to_dict()
        value.pop('retention',None)
        if not self.execution_view_only:value.pop('execution_view_only',None)
        for output in value['outputs']:
            if not output.get('mapping'):output.pop('mapping',None)
        for f in value['files']: f.pop('path')
        return digest(value)


@dataclass(frozen=True)
class ExecutionSpec(Contract):
    predictors: tuple
    sources: tuple
    input_source: str
    key_columns: tuple
    namespace: str
    entity_columns: tuple = ()
    batch_columns: tuple = ()
    context_fields: tuple = ()
    outcomes: OutcomeSnapshotSpec | None = None
    cohorts: tuple = ()
    roles: RoleSpec | None = None
    information_cutoff: ClockSpec | None = None
    as_of: str | None = None
    auxiliaries: tuple = ()
    fitted_methods: tuple = ()
    membership_sidecars: tuple = ()
    evidence_retention: str = 'materialized_inputs'
    ensembles: tuple = ()
    device: DeviceSpec = field(default_factory=DeviceSpec)
    limits: ExecutionLimits = field(default_factory=ExecutionLimits)
    name: str = 'ConfidenceGuard predictor execution'
    schema_version: str = 'confidenceguard.execution_spec/1.0'

    def __post_init__(self):
        sequence(self,'predictors',PredictorSpec);sequence(self,'sources',SourceSpec);sequence(self,'cohorts',CohortSpec);sequence(self,'context_fields',FeatureField)
        nested(self,'device',DeviceSpec);nested(self,'limits',ExecutionLimits);nested(self,'roles',RoleSpec,True);nested(self,'outcomes',OutcomeSnapshotSpec,True)
        nested(self,'information_cutoff',ClockSpec,True)
        if self.as_of:
            from ..history_contracts import instant
            instant(self.as_of)
            if not self.outcomes or not self.outcomes.available_at:raise EvaluationError('Execution as-of requires outcome availability.')
        for f in ('input_source','namespace','name'): name(getattr(self,f))
        choice(self.evidence_retention,{'materialized_inputs','outputs_and_recipes'},'experiment retention')
        object.__setattr__(self,'key_columns',strings(self.key_columns,'event keys',True));object.__setattr__(self,'entity_columns',strings(self.entity_columns,'entity keys'))
        object.__setattr__(self,'batch_columns',strings(self.batch_columns,'batch ownership'))
        if not self.predictors or len(self.predictors)>self.limits.max_predictors or len({p.id for p in self.predictors})!=len(self.predictors): raise EvaluationError('Predictor admission exceeded.')
        if any(p.execution_view_only for p in self.predictors):raise EvaluationError('Completed derived views replay through their frozen execution/auxiliary/method contracts, not as standalone predictors.','derived_view_not_executable')
        if len({s.id for s in self.sources})!=len(self.sources) or self.input_source not in {s.id for s in self.sources}: raise EvaluationError('Invalid execution sources.')
        if self.outcomes and self.outcomes.source not in {s.id for s in self.sources}: raise EvaluationError('Outcome source is absent.')
        if any(p.task!=self.predictors[0].task for p in self.predictors): raise EvaluationError('Execution predictors require compatible tasks.')
        prohibited=set(self.key_columns)|set(self.entity_columns)|set(self.batch_columns)
        if self.outcomes and self.outcomes.source==self.input_source:prohibited.update({self.outcomes.column,self.outcomes.status_column})
        if self.roles and self.roles.column:prohibited.add(self.roles.column)
        if any(f.column in prohibited for p in self.predictors for f in p.inputs):raise EvaluationError('Identifiers, roles and authoritative outcome columns cannot be model inputs.','outcome_input')
        if any(f.available_at for p in self.predictors for f in p.inputs) and self.information_cutoff is None:raise EvaluationError('Dated model inputs require an information cutoff.','input_availability')
        from ..auxiliary.contracts import AuxiliaryArtifact
        artifacts=tuple(AuxiliaryArtifact.from_dict(v).to_dict() for v in self.auxiliaries)
        ids={p.id for p in self.predictors}
        for artifact in artifacts:
            if artifact['id'] in ids or artifact['parent_digest'] not in {p.predictor_digest for p in self.predictors}:raise EvaluationError('Attached auxiliary needs a unique ID and matching frozen parent.')
            ids.add(artifact['id'])
            fields=[FeatureField.from_dict(f) for p in artifact['predictors'] for f in p['inputs']]
            if any(f.column in prohibited for f in fields):raise EvaluationError('Identifiers, roles and authoritative outcome columns cannot be auxiliary inputs.','outcome_input')
            if any(f.available_at or f.effective_at for f in fields) and self.information_cutoff is None:raise EvaluationError('Dated auxiliary inputs require an information cutoff.','input_availability')
        object.__setattr__(self,'auxiliaries',artifacts)
        from .ensembles import validate_ensembles
        validate_ensembles(self.ensembles,ids);object.__setattr__(self,'ensembles',tuple(bounded(self.ensembles)));ids.update(g['id'] for g in self.ensembles)
        from ..fitted import FittedMethod
        methods=tuple(FittedMethod.from_dict(v).to_dict() for v in self.fitted_methods)
        for m in methods:
            if m['id'] in ids or m['definition']['run'] not in ids:raise EvaluationError('Frozen method needs a unique ID and an admitted root.')
            ids.add(m['id'])
        object.__setattr__(self,'fitted_methods',methods);object.__setattr__(self,'membership_sidecars',tuple(bounded(self.membership_sidecars)))
        if len(ids)>self.limits.max_predictors:raise EvaluationError('Combined predictor/auxiliary/method admission exceeded.')
        if self.schema_version!='confidenceguard.execution_spec/1.0': raise EvaluationError('Unsupported execution schema.')

    @property
    def task(self): return self.predictors[0].task

    @property
    def predictor_ids(self):return {p.id for p in self.predictors}|{a['id'] for a in self.auxiliaries}|{m['id'] for m in self.fitted_methods}|{g['id'] for g in self.ensembles}
