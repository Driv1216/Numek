"""Strict, local comparative contracts. Importing these does not load DuckDB."""
from dataclasses import asdict, dataclass, field, replace
import json
import math
import re
from pathlib import Path

from datatrust.contracts import (DatasetSpec, TaskSpec, PresentationLimits, _construct,
                                  _names, _positive, json_safe)


@dataclass(frozen=True)
class ExecutionOptions:
    backend: str = 'duckdb_local'
    max_source_bytes: int = 5 * 1024**3
    max_combined_source_bytes: int = 8 * 1024**3
    max_rows: int = 10000000
    max_combined_rows: int = 30000000
    max_columns: int = 1000
    memory_bytes: int = 2 * 1024**3
    max_rss_bytes: int = 6 * 1024**3
    threads: int = 2
    batch_bytes: int = 32 * 1024**2
    max_record_bytes: int = 8 * 1024**2
    workspace_bytes: int = 64 * 1024**3
    free_disk_bytes: int = 2 * 1024**3
    max_seconds: float = 1800
    result_bytes: int = 32 * 1024**2
    scratch_directory: str = None

    def __post_init__(self):
        if self.backend not in {'duckdb_local', 'pandas_in_memory'}:
            raise ValueError('Unsupported execution backend.')
        for name, value in asdict(self).items():
            if name not in {'backend', 'scratch_directory'}:
                _positive(value, name, integer=name != 'max_seconds')
        if self.scratch_directory is not None and not isinstance(self.scratch_directory, str):
            raise ValueError('scratch_directory must be a local directory.')

    @classmethod
    def from_dict(cls, value):
        return _construct(cls, value)


@dataclass(frozen=True)
class ValueConstraint:
    columns: tuple
    rule: str
    value: object = None

    def __post_init__(self):
        object.__setattr__(self, 'columns', _names(self.columns, 'constraint columns'))
        rules = {'required', 'forbidden', 'type', 'non_null', 'finite', 'minimum', 'maximum',
                 'integer', 'nonnegative', 'allowed_values', 'unique', 'less_equal'}
        if self.rule not in rules or not self.columns:
            raise ValueError('Unsupported or empty value constraint.')
        if self.rule == 'less_equal' and len(self.columns) != 2:
            raise ValueError('less_equal requires two columns.')
        if self.rule not in {'unique', 'required', 'forbidden', 'less_equal'} and len(self.columns) != 1:
            raise ValueError('This constraint requires one column.')
        if self.rule in {'minimum', 'maximum'} and (isinstance(self.value, bool) or not isinstance(self.value, (int, float)) or not math.isfinite(self.value)):
            raise ValueError('Constraint bounds must be finite numbers.')
        if self.rule == 'type' and self.value not in {'string', 'numeric', 'integer', 'boolean'}:
            raise ValueError('Unsupported declared value type.')
        if self.rule == 'allowed_values':
            if not isinstance(self.value, (list, tuple)) or not self.value or any(isinstance(v, (dict, list, tuple)) or v is None or isinstance(v, float) and not math.isfinite(v) for v in self.value):
                raise ValueError('allowed_values must be a nonempty finite scalar sequence.')
        elif self.rule not in {'type', 'minimum', 'maximum'} and self.value is not None:
            raise ValueError('Unexpected value for constraint.')


@dataclass(frozen=True)
class SegmentSpec:
    column: str
    categories: tuple = ()
    bins: int = 0

    def __post_init__(self):
        if not isinstance(self.column, str) or not self.column:
            raise ValueError('A segment needs a column.')
        if not isinstance(self.categories, (list, tuple)) or len(self.categories)>32 or any(not isinstance(v, (str, int, float, bool)) or isinstance(v,float) and not math.isfinite(v) for v in self.categories):
            raise ValueError('Segment categories must be scalar values.')
        object.__setattr__(self, 'categories', tuple(self.categories))
        if isinstance(self.bins, bool) or not isinstance(self.bins, int) or self.bins < 0 or self.bins > 32 or self.bins == 1 or self.bins and self.categories:
            raise ValueError('Use categories or 2–32 numerical bins.')


@dataclass(frozen=True)
class AdvancedTabularOptions:
    missingness: bool = True
    dependencies: bool = True
    constraints: tuple = ()
    segments: tuple = ()
    requested_pairs: tuple = ()
    spearman_pairs: tuple = ()
    feature_availability: dict = field(default_factory=dict)
    max_features: int = 64
    max_pairs: int = 128
    max_pair_work: int = 1000000000
    max_segment_checks: int = 200
    max_patterns: int = 10000
    max_details: int = 100
    max_examples: int = 5

    def __post_init__(self):
        if not isinstance(self.missingness, bool) or not isinstance(self.dependencies, bool): raise ValueError('Diagnostic selection must be boolean.')
        for name, cls in (('constraints', ValueConstraint), ('segments', SegmentSpec)):
            value = getattr(self, name)
            if not isinstance(value, (list, tuple)):
                raise ValueError(f'{name} must be a sequence.')
            object.__setattr__(self, name, tuple(_construct(cls, v) if isinstance(v, dict) else v for v in value))
            if any(not isinstance(v, cls) for v in getattr(self, name)):
                raise ValueError(f'Invalid {name}.')
        if len(self.segments) > 4 or len({s.column for s in self.segments}) != len(self.segments):
            raise ValueError('Declare at most four distinct segment columns.')
        for name in ('requested_pairs', 'spearman_pairs'):
            pairs = tuple(_names(v, name) for v in getattr(self, name))
            if any(len(v) != 2 for v in pairs) or len(set(pairs)) != len(pairs):
                raise ValueError('Pair declarations require unique two-column pairs.')
            object.__setattr__(self, name, pairs)
        if len(self.spearman_pairs) > 16:
            raise ValueError('Declare at most sixteen Spearman pairs.')
        allowed = {'available_at_prediction', 'unavailable_at_prediction', 'unknown'}
        if not isinstance(self.feature_availability, dict) or any(not isinstance(k, str) or v not in allowed for k, v in self.feature_availability.items()):
            raise ValueError('Invalid feature availability.')
        for name in ('max_features', 'max_pairs', 'max_pair_work', 'max_segment_checks', 'max_patterns', 'max_details', 'max_examples'):
            _positive(getattr(self, name), name, integer=True)
        bounds = {}
        for c in self.constraints:
            if c.rule in {'minimum', 'maximum', 'nonnegative'}:
                b = bounds.setdefault(c.columns[0], {})
                if c.rule == 'maximum': b['upper'] = min(b.get('upper', c.value), c.value)
                else: b['lower'] = max(b.get('lower', c.value if c.rule == 'minimum' else 0), c.value if c.rule == 'minimum' else 0)
            if c.rule == 'required' and any(x.rule == 'forbidden' and set(c.columns) & set(x.columns) for x in self.constraints):
                raise ValueError('Contradictory required/forbidden fields.')
        for name, b in bounds.items():
            if b.get('lower', -math.inf) > b.get('upper', math.inf):
                raise ValueError(f'Contradictory bounds for {name}.')
            if any(c.rule == 'integer' and c.columns == (name,) for c in self.constraints) and all(k in b for k in ('lower','upper')) and math.ceil(b['lower']) > math.floor(b['upper']):
                raise ValueError('Declared range contains no integer.')
        for name in {c.columns[0] for c in self.constraints}:
            declarations=[c for c in self.constraints if c.columns==(name,)]
            types={c.value for c in declarations if c.rule=='type'}
            if len(types)>1 and types!={'numeric','integer'}:
                raise ValueError(f'Contradictory logical types for {name}.')
            sets=[set(c.value) for c in declarations if c.rule=='allowed_values']
            if sets:
                permitted=set.intersection(*sets)
                b=bounds.get(name,{})
                integer='integer' in types or any(c.rule=='integer' for c in declarations)
                numeric='numeric' in types or integer or bool(b)
                def compatible(v):
                    if numeric and (isinstance(v,bool) or not isinstance(v,(int,float))):return False
                    if types=={'string'} and not isinstance(v,str):return False
                    if types=={'boolean'} and not isinstance(v,bool):return False
                    if numeric and (v<b.get('lower',-math.inf) or v>b.get('upper',math.inf) or integer and v!=math.trunc(v)):return False
                    return True
                if not any(compatible(v) for v in permitted):raise ValueError(f'Contradictory allowed values for {name}.')

    @classmethod
    def from_dict(cls, value):
        return _construct(cls, value)


@dataclass(frozen=True)
class DatasetInput:
    id: str
    role: str
    dataset: DatasetSpec
    task: TaskSpec = field(default_factory=lambda: TaskSpec('dataset_profile'))
    config: object = None

    def __post_init__(self):
        from datatrust.contracts import AnalysisConfig
        if not isinstance(self.id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',self.id):
            raise ValueError('An input needs a stable ID of at most 80 characters.')
        if self.role not in {'train', 'validation', 'test', 'reference', 'current', 'dataset'}:
            raise ValueError('Unsupported source role.')
        for name, cls in (('dataset', DatasetSpec), ('task', TaskSpec), ('config', AnalysisConfig)):
            value = getattr(self, name)
            if isinstance(value, dict):
                value = cls.from_dict(value) if hasattr(cls, 'from_dict') else _construct(cls, value)
                object.__setattr__(self, name, value)
            if not isinstance(value, cls) and not (name == 'config' and value is None):
                raise ValueError(f'Invalid input {name}.')
        if self.config and self.config.execution is not None:
            raise ValueError('Comparison execution settings belong to ComparisonConfig, not individual inputs.')
        if self.config and self.config.advanced is not None:
            raise ValueError('Comparison diagnostics belong to ComparisonConfig.advanced, not individual inputs.')


TRANSFORMATION_KINDS = ('impute', 'drop_rows', 'drop_columns', 'cap', 'transform', 'encode', 'rename', 'deduplicate', 'filter', 'resample', 'other')


@dataclass(frozen=True)
class TransformationSpec:
    """A preprocessing step you declare for a before/after assessment. Declared, not observed: the assessment
    reports separately what the data shows, and never performs a transformation."""
    kind: str
    columns: tuple = ()
    outputs: tuple = ()
    description: str = ''

    def __post_init__(self):
        if self.kind not in TRANSFORMATION_KINDS:
            raise ValueError('Transformation kind must be one of: ' + ', '.join(TRANSFORMATION_KINDS) + '.')
        for name in ('columns', 'outputs'):
            object.__setattr__(self, name, _names(getattr(self, name), name) if getattr(self, name) else ())
        if self.kind in {'impute', 'drop_columns', 'cap', 'transform', 'encode', 'rename'} and not self.columns:
            raise ValueError(f'A {self.kind} transformation names its columns.')
        if self.kind == 'rename' and len(self.outputs) != len(self.columns):
            raise ValueError('A rename lists one output name per column.')
        if not isinstance(self.description, str) or len(self.description) > 300:
            raise ValueError('A transformation description is text of at most 300 characters.')


@dataclass(frozen=True)
class ComparisonSpec:
    mode: str
    inputs: tuple
    column_mappings: dict = field(default_factory=dict)
    identity_keys: tuple = ()
    group_keys: tuple = ()
    evaluation_intent: str = 'unknown'
    intent_pairs: tuple = ()
    dataset_name: str = None
    purpose: str = None
    preset: str = field(default=None, kw_only=True)
    transformations: tuple = field(default=(), kw_only=True)

    def __post_init__(self):
        if self.preset not in {None, 'before_after'}: raise ValueError('Unknown comparison preset.')
        if self.preset == 'before_after' and self.mode != 'versions': raise ValueError('The before/after preset compares two versions.')
        if self.transformations and self.preset != 'before_after': raise ValueError('Declared transformations belong to the before/after preset.')
        object.__setattr__(self, 'transformations', tuple(_construct(TransformationSpec, v) if isinstance(v, dict) else v for v in self.transformations))
        if any(not isinstance(v, TransformationSpec) for v in self.transformations): raise ValueError('Invalid transformation declaration.')
        object.__setattr__(self, 'inputs', tuple(_construct(DatasetInput, v) if isinstance(v, dict) else v for v in self.inputs))
        if any(not isinstance(v, DatasetInput) for v in self.inputs): raise ValueError('Invalid comparison input.')
        roles = [v.role for v in self.inputs]; ids = [v.id for v in self.inputs]
        if len(set(ids)) != len(ids) or len(set(roles)) != len(roles): raise ValueError('Input IDs and roles must be unique.')
        if self.mode == 'splits':
            if 'train' not in roles or not set(roles) <= {'train','validation','test'} or len(roles) not in {2,3}: raise ValueError('Split audit needs train and validation/test.')
        elif self.mode == 'versions':
            if set(roles) != {'reference','current'}: raise ValueError('Version comparison needs reference and current.')
        else: raise ValueError('Comparison mode must be splits or versions.')
        for name in ('identity_keys','group_keys'):
            object.__setattr__(self,name,tuple(_names(v,name) for v in getattr(self,name)))
            if any(not v for v in getattr(self,name)) or len(set(getattr(self,name))) != len(getattr(self,name)): raise ValueError('Keys must be unique nonempty composite declarations.')
        if self.evaluation_intent not in {'unknown','record_disjoint','entity_disjoint','group_disjoint','overlap_permitted'}: raise ValueError('Invalid evaluation intent.')
        if self.mode == 'versions' and self.evaluation_intent != 'unknown': raise ValueError('Evaluation intent applies to splits.')
        if self.evaluation_intent == 'entity_disjoint' and not self.identity_keys or self.evaluation_intent == 'group_disjoint' and not self.group_keys:
            raise ValueError('Disjoint-unit intent requires declared keys.')
        if not isinstance(self.column_mappings,dict) or set(self.column_mappings)-set(ids): raise ValueError('Mappings must reference input IDs.')
        for mapping in self.column_mappings.values():
            if not isinstance(mapping,dict) or any(not isinstance(k,str) or not k or not isinstance(v,str) or not v for k,v in mapping.items()) or len(set(mapping.values())) != len(mapping): raise ValueError('Column mappings must be one-to-one source-to-logical names.')
        object.__setattr__(self,'intent_pairs',tuple(_names(v,'intent pairs') for v in self.intent_pairs))
        if any(len(v)!=2 or set(v)-set(ids) for v in self.intent_pairs): raise ValueError('Intent pairs require two input IDs.')
        for name, limit in (('dataset_name',120),('purpose',1000)):
            v=getattr(self,name)
            if v is not None and (not isinstance(v,str) or len(v)>limit): raise ValueError(f'Invalid comparison {name}.')

    @classmethod
    def from_dict(cls, value, *, base_directory=None):
        result = _construct(cls, value)
        if base_directory is not None:
            result = replace(result, inputs=tuple(replace(v,dataset=replace(v.dataset,path=str((Path(base_directory)/v.dataset.path).resolve()))) for v in result.inputs))
        return result


@dataclass(frozen=True)
class ComparisonConfig:
    execution: ExecutionOptions = field(default_factory=ExecutionOptions)
    advanced: AdvancedTabularOptions = field(default_factory=lambda: AdvancedTabularOptions(missingness=False,dependencies=False))
    presentation: PresentationLimits = field(default_factory=PresentationLimits)
    sampling: str = 'unknown'
    inference: bool = False
    continuous_columns: tuple = ()
    minimum_population: int = 100
    missingness_change: float = .05
    categorical_distance: float = .10
    cdf_distance: float = .10
    normalized_wasserstein: float = .25
    category_count: int = 20
    category_share: float = .01

    def __post_init__(self):
        for name,cls in (('execution',ExecutionOptions),('advanced',AdvancedTabularOptions),('presentation',PresentationLimits)):
            if isinstance(getattr(self,name),dict): object.__setattr__(self,name,_construct(cls,getattr(self,name)))
            if not isinstance(getattr(self,name),cls): raise ValueError(f'Invalid {name}.')
        if self.execution.backend != 'duckdb_local': raise ValueError('Comparisons require duckdb_local.')
        if self.sampling not in {'unknown','independent_rows'} or not isinstance(self.inference,bool): raise ValueError('Invalid sampling/inference declaration.')
        if self.inference and self.sampling != 'independent_rows': raise ValueError('Inference requires independent_rows.')
        object.__setattr__(self,'continuous_columns',_names(self.continuous_columns,'continuous quantitative columns'))
        for name in ('minimum_population','category_count'): _positive(getattr(self,name),name,integer=True)
        for name in ('missingness_change','categorical_distance','cdf_distance','normalized_wasserstein','category_share'):
            _positive(getattr(self,name),name)
            if name != 'normalized_wasserstein' and getattr(self,name)>1: raise ValueError('Share thresholds must not exceed one.')

    @classmethod
    def from_dict(cls, value): return _construct(cls,value)


@dataclass
class ComparisonResult:
    inputs: tuple
    comparison: object
    profile: dict
    parsing: dict
    parsing_warnings: list
    checks: list
    evidence: list
    findings: list
    narrative: dict
    context: dict
    coverage: dict
    scoring: dict
    execution: dict
    generated_at: str
    methodology_id: str
    schema_version: str = '1.3'
    guidance: dict = field(default_factory=dict, kw_only=True)  # finding_guidance_v1 and later; absent before

    @property
    def source_paths(self): return tuple(v.dataset.path for v in self.inputs)

    def to_dict(self):
        value=asdict(self)
        if not value['guidance']: value.pop('guidance')
        for item in value['inputs']:
            item['dataset']['path']=Path(item['dataset']['source_filename'] or item['dataset']['path']).name
        if value['comparison']:
            value['comparison'].pop('inputs',None)
            value['comparison']=spec_record(value['comparison'])
        return json_safe(value)

    def json_text(self): return json.dumps(self.to_dict(),ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    def write_json(self,path):
        from datatrust.renderer import write_analysis_json
        return write_analysis_json(self,path)
    def generate_artifacts(self,path,*,format='html',html_path=None,json_path=None):
        from datatrust.renderer import write_report_artifacts
        return write_report_artifacts(self,path,format=format,html_path=html_path,json_path=json_path)
    def generate_report(self,path,*,format='html',html_path=None):
        a=self.generate_artifacts(path,format=format,html_path=html_path)
        return a.pdf_path if format=='pdf' else a.html_path


def spec_record(value):
    """A comparison specification record without default preset fields, so splits and versions records, seals and
    canonical JSON are exactly as before the before/after preset existed."""
    value = dict(value)
    if value.get('preset') is None: value.pop('preset', None)
    if not value.get('transformations'): value.pop('transformations', None)
    return value
