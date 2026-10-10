"""Strict M5 contracts. Observation meaning and scheduling are independent."""
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
import json
import math
import re
from typing import Optional
from datatrust.contracts import (_construct, _names, _positive, AnalysisConfig, CsvParseOptions,
    TaskSpec, PresentationLimits, json_safe)
from datatrust.m4_contracts import ExecutionOptions


def choice(value, values, label):
    if value not in values: raise ValueError(f'{label} must be one of {sorted(values)}.')


def nested(owner, name, cls):
    value = getattr(owner, name)
    if isinstance(value, dict): object.__setattr__(owner, name, (cls.from_dict(value) if hasattr(cls,'from_dict') else _construct(cls,value)))
    elif value is None and name in {'source','clock','schedule','task','config','evaluation','execution','limits','behavior','presentation'}: raise ValueError(f'{name} cannot be null.')
    elif value is not None and not isinstance(value, cls): raise ValueError(f'{name} must be {cls.__name__}.')


class Contract:
    @classmethod
    def from_dict(cls, value):
        try:return _construct(cls, value)
        except (TypeError,AttributeError) as exc:raise ValueError(f'Invalid {cls.__name__} declaration: {exc}') from exc
    def to_dict(self): return json_safe(asdict(self))


@dataclass(frozen=True)
class ClockSpec(Contract):
    column: str
    kind: str = 'instant'
    encoding: str = 'iso'
    format: Optional[str] = None
    epoch_unit: Optional[str] = None
    timezone: Optional[str] = None
    timezone_column: Optional[str] = None
    ambiguity: str = 'unresolved'
    fold_column: Optional[str] = None
    date_convention: Optional[str] = None

    def __post_init__(self):
        if not isinstance(self.column, str) or not self.column: raise ValueError('Clock column is required.')
        choice(self.kind, {'instant','civil_date','local_datetime'}, 'clock kind')
        choice(self.encoding, {'iso','format','epoch','native'}, 'clock encoding')
        choice(self.ambiguity, {'unresolved','earlier','later'}, 'DST ambiguity')
        if self.encoding == 'format' and not self.format: raise ValueError('Explicit format is required.')
        if self.encoding == 'epoch': choice(self.epoch_unit, {'s','ms','us','ns'}, 'epoch unit')
        elif self.epoch_unit is not None: raise ValueError('epoch_unit requires epoch encoding.')
        if self.format is not None and self.encoding != 'format': raise ValueError('format requires format encoding.')
        if self.timezone and self.timezone_column: raise ValueError('Choose one timezone binding.')
        if self.kind != 'instant' and (self.timezone or self.timezone_column or self.fold_column or self.ambiguity != 'unresolved'): raise ValueError('Timezone resolution requires an instant clock.')
        if self.date_convention not in {None,'start_of_day'}: raise ValueError('Only explicit start_of_day date convention is supported.')


@dataclass(frozen=True)
class MeasurementSpec(Contract):
    name: str
    column: Optional[str] = None
    representation: str = 'quantitative'
    unit: Optional[str] = None
    meaning: Optional[str] = None
    past_observation: bool = False
    def __post_init__(self):
        if not self.name: raise ValueError('Measurement name is required.')
        choice(self.representation, {'quantitative','categorical','boolean','string'}, 'value representation')
        if not isinstance(self.past_observation, bool): raise ValueError('past_observation must be boolean.')


@dataclass(frozen=True)
class ActiveInterval(Contract):
    start: str
    end: str
    entity: tuple = ()
    measurement: Optional[str] = None
    closed: str = 'left'
    def __post_init__(self):
        object.__setattr__(self, 'entity', tuple(self.entity))
        choice(self.closed,{'left','right','both','neither'},'interval closure')
        if not isinstance(self.start, str) or not isinstance(self.end, str): raise ValueError('Interval endpoints must be exact strings.')


@dataclass(frozen=True)
class ScheduleSpec(Contract):
    kind: str = 'none'
    cadence_ns: Optional[str] = None
    anchor: Optional[str] = None
    civil_unit: Optional[str] = None
    timezone: Optional[str] = None
    month_end: str = 'skip'
    source_id: Optional[str] = None
    time_column: Optional[str] = None
    entity_columns: tuple = ()
    measurement_column: Optional[str] = None
    expectation: str = 'required_record'
    collection_status_column: Optional[str] = None
    collection_active_values: tuple = ('active',)
    def __post_init__(self):
        choice(self.kind, {'none','fixed','civil','supplied'}, 'schedule kind')
        choice(self.expectation, {'required_record','collection_opportunity'}, 'schedule expectation')
        choice(self.month_end, {'skip','last_day'}, 'month-end behavior')
        object.__setattr__(self,'entity_columns',_names(self.entity_columns,'schedule entity columns'))
        object.__setattr__(self,'collection_active_values',_names(self.collection_active_values,'collection active values'))
        if self.kind == 'fixed':
            if not self.anchor or not isinstance(self.cadence_ns,str) or not self.cadence_ns.isdigit() or int(self.cadence_ns)<=0: raise ValueError('Fixed schedules need an anchor and positive exact cadence_ns string.')
        if self.kind == 'civil':
            choice(self.civil_unit, {'daily','weekly','monthly'}, 'civil schedule unit')
            if not self.anchor or not self.timezone: raise ValueError('Civil schedules need anchor and timezone.')
        if self.kind == 'supplied' and (not self.source_id or not self.time_column): raise ValueError('Supplied schedules need source_id and time_column.')
        if self.kind != 'fixed' and self.cadence_ns is not None or self.kind not in {'fixed','civil'} and self.anchor is not None: raise ValueError('Incompatible schedule fields.')
        if self.kind != 'supplied' and (self.source_id or self.time_column or self.entity_columns or self.measurement_column or self.collection_status_column): raise ValueError('Supplied schedule fields require kind=supplied.')
        if self.kind != 'civil' and (self.civil_unit or self.timezone): raise ValueError('Civil schedule fields require kind=civil.')


@dataclass(frozen=True)
class TemporalSpec(Contract):
    clock: ClockSpec
    measurements: tuple
    observation: str = 'measurement'
    layout: str = 'wide'
    entity_columns: tuple = ()
    observation_keys: tuple = ()
    measurement_column: Optional[str] = None
    value_column: Optional[str] = None
    schedule: ScheduleSpec = field(default_factory=ScheduleSpec)
    active_intervals: tuple = ()
    unique_observations: bool = False
    source_order_is_arrival: bool = False
    dense_long: bool = False
    assessment_time: Optional[str] = None
    max_adjacency_ns: Optional[str] = None
    required_lookback_ns: Optional[str] = None
    def __post_init__(self):
        nested(self,'clock',ClockSpec); nested(self,'schedule',ScheduleSpec)
        object.__setattr__(self,'measurements',tuple(MeasurementSpec.from_dict(x) if isinstance(x,dict) else x for x in self.measurements))
        object.__setattr__(self,'active_intervals',tuple(ActiveInterval.from_dict(x) if isinstance(x,dict) else x for x in self.active_intervals))
        if any(not isinstance(x,ActiveInterval) for x in self.active_intervals): raise ValueError('Invalid lifecycle interval.')
        for name in ('entity_columns','observation_keys'): object.__setattr__(self,name,_names(getattr(self,name),name))
        choice(self.observation,{'measurement','event','snapshot'},'observation meaning');choice(self.layout,{'wide','long'},'layout')
        if not self.measurements or any(not isinstance(x,MeasurementSpec) for x in self.measurements) or len({x.name for x in self.measurements}) != len(self.measurements): raise ValueError('Unique declared measurements are required.')
        if self.layout=='wide':
            if self.measurement_column or self.value_column or self.dense_long: raise ValueError('Long-layout fields cannot be used in wide layout.')
            columns=[x.column or x.name for x in self.measurements]
            if len(set(columns))!=len(columns): raise ValueError('Wide measurements must have unique columns.')
        elif not self.measurement_column or not self.value_column or len({x.representation for x in self.measurements})!=1 or any(x.column for x in self.measurements): raise ValueError('Long layout needs measurement/value columns and one representation family.')
        for name in ('max_adjacency_ns','required_lookback_ns'):
            v=getattr(self,name)
            if v is not None and (not isinstance(v,str) or not v.isdigit() or int(v)<=0): raise ValueError(f'{name} must be a positive exact duration string.')
        for name in ('unique_observations','source_order_is_arrival','dense_long'):
            if not isinstance(getattr(self,name),bool): raise ValueError(f'{name} must be boolean.')


@dataclass(frozen=True)
class TemporalSourceSpec(Contract):
    path: str
    format: str = 'csv'
    dataset_name: Optional[str] = None
    purpose: Optional[str] = None
    source_filename: Optional[str] = None
    parsing: CsvParseOptions = field(default_factory=CsvParseOptions)
    def __post_init__(self):
        if not isinstance(self.path,(str,Path)) or not str(self.path) or re.search(r'^[a-zA-Z]+://|[*?\[\]]',str(self.path)): raise ValueError('Source must be one local file, without globs or remote URLs.')
        choice(self.format,{'csv','parquet'},'temporal source format'); nested(self,'parsing',CsvParseOptions)
        if self.format=='parquet' and self.parsing != CsvParseOptions(): raise ValueError('CSV missing-token/type options do not apply to typed Parquet.')


@dataclass(frozen=True)
class TemporalInputSpec(Contract):
    id: str
    source: TemporalSourceSpec
    temporal: Optional[TemporalSpec] = None
    role: str = 'dataset'
    task: TaskSpec = field(default_factory=lambda:TaskSpec('dataset_profile'))
    config: AnalysisConfig = field(default_factory=AnalysisConfig)
    def __post_init__(self):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',self.id): raise ValueError('Invalid stable source ID.')
        choice(self.role,{'dataset','train','validation','test','reference','current','history','schedule','expectations'},'temporal input role')
        nested(self,'source',TemporalSourceSpec);nested(self,'temporal',TemporalSpec);nested(self,'task',TaskSpec);nested(self,'config',AnalysisConfig)
        if self.role not in {'history','schedule','expectations'} and self.temporal is None: raise ValueError('Analytical sources require temporal semantics.')
        if self.role in {'history','schedule','expectations'} and self.temporal is not None: raise ValueError('Auxiliary inputs cannot enter ordinary temporal profiling.')
        if self.temporal and self.source.format=='csv' and self.temporal.clock.encoding=='native': raise ValueError('Native clocks require typed Parquet.')
        if self.config.parsing!=CsvParseOptions():raise ValueError('Temporal CSV parsing belongs in source.parsing; competing base-config parsing is rejected.')
        if self.role in {'history','schedule','expectations'} and self.task!=TaskSpec('dataset_profile'):raise ValueError('Auxiliary inputs cannot declare ordinary target/feature tasks.')
        if self.config.execution or self.config.advanced: raise ValueError('Execution and temporal investigation settings belong at job level.')
    @property
    def dataset(self): return self.source


@dataclass(frozen=True)
class FeatureAvailabilitySpec(Contract):
    id: str
    source_id: str
    features: tuple
    cutoff: ClockSpec
    method: str = 'timestamp'
    availability: Optional[ClockSpec] = None
    source_clock: Optional[ClockSpec] = None
    delay_ns: Optional[str] = None
    static: Optional[str] = None
    authoritative: bool = True
    replaces: Optional[str] = None
    def __post_init__(self):
        nested(self,'cutoff',ClockSpec);nested(self,'availability',ClockSpec);nested(self,'source_clock',ClockSpec)
        object.__setattr__(self,'features',_names(self.features,'bound features'))
        if not self.features or not self.id: raise ValueError('Availability declarations require ID and explicit features.')
        choice(self.method,{'timestamp','delay','static'},'availability method')
        if self.method=='timestamp' and self.availability is None: raise ValueError('Timestamp availability requires a clock.')
        if self.method=='delay' and (not self.source_clock or not isinstance(self.delay_ns,str) or not re.fullmatch(r'[+-]?\d+',self.delay_ns)): raise ValueError('Delay requires named source_clock and exact signed delay_ns.')
        if self.method=='static' and self.static not in {'available_at_prediction','unknown'}: raise ValueError('Static availability is available_at_prediction or unknown.')
        if self.method!='timestamp' and self.availability or self.method!='delay' and (self.source_clock or self.delay_ns is not None) or self.method!='static' and self.static: raise ValueError('Competing availability representations.')
        for clock in (self.availability,self.source_clock):
            if clock and (clock.kind!=self.cutoff.kind or clock.kind=='local_datetime'): raise ValueError('Availability/cutoff require compatible resolved clock semantics.')
        if self.method=='delay' and self.source_clock.kind!='instant': raise ValueError('Nanosecond delays require instant clocks.')
        if not isinstance(self.authoritative,bool): raise ValueError('authoritative must be boolean.')


@dataclass(frozen=True)
class FeatureHistorySpec(Contract):
    id: str
    source_id: str
    history_source_id: str
    features: tuple
    observation_keys: tuple
    history_keys: tuple
    value_columns: dict
    availability: ClockSpec
    cutoff: ClockSpec
    value_units: dict = field(default_factory=dict)
    source_observation_clock: Optional[ClockSpec] = None
    history_observation_clock: Optional[ClockSpec] = None
    revision_id_column: Optional[str] = None
    selected_revision_id_column: Optional[str] = None
    tie_order_column: Optional[str] = None
    tie_order_meaning: Optional[str] = None
    state_column: Optional[str] = None
    state_values: dict = field(default_factory=lambda:{'valid':'valid','known_missing':'known_missing','retracted':'retracted','unknown':'unknown'})
    null_semantics: str = 'unknown'
    completeness: str = 'unknown'
    coverage_start: Optional[str] = None
    coverage_end: Optional[str] = None
    initial_creation_included: bool = False
    baseline_time: Optional[str] = None
    latest_available_required: bool = False
    absolute_tolerance: Optional[float] = None
    relative_tolerance: Optional[float] = None
    def __post_init__(self):
        nested(self,'availability',ClockSpec);nested(self,'cutoff',ClockSpec)
        nested(self,'source_observation_clock',ClockSpec);nested(self,'history_observation_clock',ClockSpec)
        for name in ('features','observation_keys','history_keys'): object.__setattr__(self,name,_names(getattr(self,name),name))
        if not self.features or not self.observation_keys or len(self.observation_keys)!=len(self.history_keys): raise ValueError('Histories require explicit feature and exact key bindings.')
        if bool(self.source_observation_clock)!=bool(self.history_observation_clock):raise ValueError('Observation-key clocks require explicit declarations on both sides.')
        if self.source_observation_clock:
            a,b=self.source_observation_clock,self.history_observation_clock
            if a.column not in self.observation_keys or b.column not in self.history_keys or self.observation_keys.index(a.column)!=self.history_keys.index(b.column) or a.kind!=b.kind:raise ValueError('Observation-key clock bindings require compatible mapped key components.')
        if not isinstance(self.value_units,dict) or set(self.value_units)-set(self.features) or any(not isinstance(x,str) for x in self.value_units.values()):raise ValueError('History value_units must bind named features to unit strings.')
        if set(self.value_columns)!=set(self.features) or any(not isinstance(v,str) or not v for v in self.value_columns.values()): raise ValueError('History value_columns must map every bound feature.')
        if self.availability.kind!=self.cutoff.kind or self.cutoff.kind=='local_datetime': raise ValueError('Revision availability and cutoff require compatible resolved clock semantics.')
        choice(self.null_semantics,{'unknown','known_missing'},'null semantics');choice(self.completeness,{'unknown','complete'},'history completeness')
        if bool(self.tie_order_column)!=bool(self.tie_order_meaning): raise ValueError('Tie order requires a declared meaning.')
        if self.selected_revision_id_column and not self.revision_id_column: raise ValueError('Selected revision IDs require history revision IDs.')
        if bool(self.coverage_start)!=bool(self.coverage_end):raise ValueError('History coverage requires both boundaries.')
        if self.completeness=='complete' and (not self.coverage_start or not self.coverage_end or not (self.initial_creation_included or self.baseline_time)): raise ValueError('Complete history needs coverage and creation or an initial-state baseline.')
        if set(self.state_values.values())-{'valid','known_missing','retracted','unknown'}: raise ValueError('Unsupported history states.')
        for name in ('absolute_tolerance','relative_tolerance'):
            v=getattr(self,name)
            if v is not None and (isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<0): raise ValueError('Value tolerances must be finite and nonnegative.')
        for name in ('initial_creation_included','latest_available_required'):
            if not isinstance(getattr(self,name),bool): raise ValueError(f'{name} must be boolean.')


@dataclass(frozen=True)
class OutcomeMaturitySpec(Contract):
    source_id: str
    target: str
    assessment_time: str
    availability: Optional[ClockSpec] = None
    source_clock: Optional[ClockSpec] = None
    delay_ns: Optional[str] = None
    fit_cutoff: Optional[str] = None
    def __post_init__(self):
        nested(self,'availability',ClockSpec);nested(self,'source_clock',ClockSpec)
        if bool(self.availability)==bool(self.source_clock): raise ValueError('Maturity needs one availability or source-clock/delay rule.')
        if (self.availability or self.source_clock).kind=='local_datetime' or self.source_clock and self.source_clock.kind!='instant': raise ValueError('Maturity requires resolved clock semantics.')
        if self.source_clock and (not isinstance(self.delay_ns,str) or not re.fullmatch(r'[+-]?\d+',self.delay_ns)): raise ValueError('Maturity delay must be an exact signed string.')
        if self.availability and self.delay_ns is not None: raise ValueError('Maturity timestamp conflicts with delay.')


@dataclass(frozen=True)
class TemporalFoldSpec(Contract):
    id: str
    train_source_id: str
    evaluation_source_id: str
    train_interval: Optional[ActiveInterval] = None
    evaluation_interval: Optional[ActiveInterval] = None
    chronology: str = 'none'
    entity_separation: str = 'none'
    group_columns: tuple = ()
    origin: Optional[ClockSpec] = None
    label_start: Optional[ClockSpec] = None
    label_end: Optional[ClockSpec] = None
    horizon_ns: Optional[str] = None
    lookback_ns: Optional[str] = None
    fit_cutoff: Optional[str] = None
    purge_ns: Optional[str] = None
    gap_basis: str = 'origin'
    label_separation_scope: str = 'global'
    disjoint_origins: bool = False
    disjoint_labels: bool = False
    def __post_init__(self):
        choice(self.gap_basis,{'origin','label'},'gap basis')
        choice(self.label_separation_scope,{'global','within_entity'},'label separation scope')
        if self.gap_basis=='label' and not self.label_end:raise ValueError('Label gap requires label endpoint clocks.')
        if self.horizon_ns and not self.label_end: raise ValueError('Horizon audit needs declared label endpoint clocks.')
        for name in ('train_interval','evaluation_interval'): nested(self,name,ActiveInterval)
        for name in ('origin','label_start','label_end'): nested(self,name,ClockSpec)
        choice(self.chronology,{'none','global','within_entity'},'chronological requirement')
        choice(self.entity_separation,{'none','disjoint','reuse_permitted'},'entity requirement')
        object.__setattr__(self,'group_columns',_names(self.group_columns,'evaluation groups'))
        if bool(self.label_start)!=bool(self.label_end): raise ValueError('Label intervals require both endpoint clocks.')
        if self.disjoint_labels and not (self.label_start and self.label_end): raise ValueError('disjoint_labels requires both label_start and label_end clock declarations (equal endpoints represent point labels).')
        for name in ('horizon_ns','lookback_ns','purge_ns'):
            v=getattr(self,name)
            if v is not None and (not isinstance(v,str) or not v.isdigit() or int(v)<=0): raise ValueError(f'{name} must be a positive exact duration string.')
        for name in ('disjoint_origins','disjoint_labels'):
            if not isinstance(getattr(self,name),bool): raise ValueError(f'{name} must be boolean.')


@dataclass(frozen=True)
class TemporalEvaluationSpec(Contract):
    folds: tuple = ()
    def __post_init__(self):
        object.__setattr__(self,'folds',tuple(TemporalFoldSpec.from_dict(x) if isinstance(x,dict) else x for x in self.folds))
        if any(not isinstance(x,TemporalFoldSpec) for x in self.folds) or len({x.id for x in self.folds})!=len(self.folds): raise ValueError('Folds must have unique IDs.')


@dataclass(frozen=True)
class SeasonalSpec(Contract):
    source_id: str
    measurement: str
    kind: str = 'elapsed'
    period_ns: Optional[str] = None
    anchor: Optional[str] = None
    phases: int = 24
    civil_phase: Optional[str] = None
    timezone: Optional[str] = None
    def __post_init__(self):
        choice(self.kind,{'elapsed','civil'},'seasonal kind');_positive(self.phases,'phases',integer=True)
        if self.kind=='elapsed' and (not self.anchor or not isinstance(self.period_ns,str) or not self.period_ns.isdigit() or int(self.period_ns)<=0): raise ValueError('Elapsed seasonality needs period_ns and anchor.')
        if self.kind=='civil':
            choice(self.civil_phase,{'hour','weekday','month'},'civil seasonal phase')
            if not self.timezone: raise ValueError('Civil phase requires timezone.')
        if self.kind=='civil' and (self.period_ns or self.anchor) or self.kind=='elapsed' and (self.civil_phase or self.timezone): raise ValueError('Incompatible seasonal fields.')


@dataclass(frozen=True)
class TemporalWorkLimits(Contract):
    max_cells: int = 100_000_000
    max_series: int = 1_000_000
    behavior_measurements: int = 32
    detailed_series: int = 64
    max_windows: int = 64
    max_folds: int = 32
    max_comparisons: int = 2048
    observation_visits: int = 1_000_000_000
    retained_details: int = 100
    witnesses: int = 5
    decoded_batch_bytes: int = 64*1024**2
    parquet_metadata_bytes: int = 16*1024**2
    def __post_init__(self):
        for name,value in asdict(self).items(): _positive(value,name,integer=True)


@dataclass(frozen=True)
class TemporalSeriesSpec(Contract):
    source_id: str
    measurement: str
    entity: tuple = ()
    def __post_init__(self):
        if not self.source_id or not self.measurement: raise ValueError('Detailed series requires source and measurement.')
        object.__setattr__(self,'entity',tuple(self.entity))
        if any(not isinstance(x,str) for x in self.entity):raise ValueError('Series entity keys must be exact strings.')


@dataclass(frozen=True)
class TemporalBehaviorSpec(Contract):
    enabled: bool = True
    windows: int = 12
    explicit_windows: tuple = ()
    reference_window: int = 0
    requested_measurements: tuple = ()
    requested_series: tuple = ()
    multivariate_pairs: tuple = ()
    min_support: int = 100
    missingness_increase: float = .05
    distribution_effect: float = .10
    normalized_w1: float = .25
    flatline_observations: int = 10
    volatility_support: int = 100
    volatility_ratio: float = 2.0
    rate_differences: bool = False
    seasonality: tuple = ()
    min_cycles: int = 8
    min_window_cycles: int = 2
    min_phase_support: int = 20
    stable_cohort: bool = True
    version: str = 'temporal_investigation_defaults_v1'
    def __post_init__(self):
        object.__setattr__(self,'multivariate_pairs',tuple(tuple(x) for x in self.multivariate_pairs))
        if any(len(x)!=2 or x[0]==x[1] or any(not isinstance(y,str) or not y for y in x) for x in self.multivariate_pairs) or len(set(tuple(sorted(x)) for x in self.multivariate_pairs))!=len(self.multivariate_pairs):raise ValueError('Multivariate pairs require distinct named measurements without duplicate unordered pairs.')
        object.__setattr__(self,'requested_series',tuple(TemporalSeriesSpec.from_dict(x) if isinstance(x,dict) else x for x in self.requested_series))
        if len(set(self.requested_series))!=len(self.requested_series):raise ValueError('Duplicate requested series.')
        object.__setattr__(self,'explicit_windows',tuple(ActiveInterval.from_dict(x) if isinstance(x,dict) else x for x in self.explicit_windows))
        object.__setattr__(self,'seasonality',tuple(SeasonalSpec.from_dict(x) if isinstance(x,dict) else x for x in self.seasonality))
        object.__setattr__(self,'requested_measurements',_names(self.requested_measurements,'requested measurements'))
        for name in ('windows','min_support','flatline_observations','volatility_support','min_cycles','min_window_cycles','min_phase_support'): _positive(getattr(self,name),name,integer=True)
        for name in ('missingness_increase','distribution_effect','normalized_w1','volatility_ratio'): _positive(getattr(self,name),name)
        if self.reference_window<0 or self.reference_window>=len(self.explicit_windows or range(self.windows)): raise ValueError('Reference window is outside the declared windows.')
        if self.volatility_ratio<=1 or self.missingness_increase>1 or self.distribution_effect>1: raise ValueError('Invalid investigation effect settings.')
        for name in ('enabled','rate_differences','stable_cohort'):
            if not isinstance(getattr(self,name),bool): raise ValueError(f'{name} must be boolean.')


@dataclass(frozen=True)
class TemporalAnalysisConfig(Contract):
    execution: ExecutionOptions = field(default_factory=ExecutionOptions)
    limits: TemporalWorkLimits = field(default_factory=TemporalWorkLimits)
    behavior: TemporalBehaviorSpec = field(default_factory=TemporalBehaviorSpec)
    presentation: PresentationLimits = field(default_factory=PresentationLimits)
    def __post_init__(self):
        for name,cls in (('execution',ExecutionOptions),('limits',TemporalWorkLimits),('behavior',TemporalBehaviorSpec),('presentation',PresentationLimits)): nested(self,name,cls)
        if self.execution.backend!='duckdb_local': raise ValueError('M5 requires duckdb_local.')
        if len(self.behavior.explicit_windows or range(self.behavior.windows))>self.limits.max_windows: raise ValueError('Window declaration exceeds hard limit.')


@dataclass(frozen=True)
class TemporalAuditSpec(Contract):
    inputs: tuple
    availability: tuple = ()
    histories: tuple = ()
    maturity: tuple = ()
    evaluation: TemporalEvaluationSpec = field(default_factory=TemporalEvaluationSpec)
    dataset_name: Optional[str] = None
    purpose: Optional[str] = None
    def __post_init__(self):
        for name,cls in (('inputs',TemporalInputSpec),('availability',FeatureAvailabilitySpec),('histories',FeatureHistorySpec),('maturity',OutcomeMaturitySpec)):
            object.__setattr__(self,name,tuple(cls.from_dict(x) if isinstance(x,dict) else x for x in getattr(self,name)))
            if any(not isinstance(x,cls) for x in getattr(self,name)): raise ValueError(f'Invalid {name} declaration.')
        nested(self,'evaluation',TemporalEvaluationSpec)
        sources={x.id:x for x in self.inputs}
        if not sources or len(sources)!=len(self.inputs): raise ValueError('Unique source IDs are required.')
        analytical={k:x for k,x in sources.items() if x.temporal}
        if not analytical: raise ValueError('At least one analytical input is required.')
        bindings={};ids={}
        for b in self.availability:
            if b.id in ids: raise ValueError('Duplicate availability binding ID.')
            if b.source_id not in analytical: raise ValueError('Availability source must be analytical.')
            names={x.name for x in analytical[b.source_id].temporal.measurements}
            if set(b.features)-names: raise ValueError('Availability references undeclared features.')
            if b.replaces:
                old=ids.get(b.replaces)
                if not old or old.source_id!=b.source_id or not set(b.features)<=set(old.features): raise ValueError('Override must explicitly replace an earlier named group rule.')
            if b.authoritative:
                for feature in b.features:
                    key=(b.source_id,feature)
                    if key in bindings and bindings[key]!=b.replaces: raise ValueError('Competing authoritative feature timing rules.')
                    bindings[key]=b.id
            ids[b.id]=b
        for collection in (self.histories,):
            if len({x.id for x in collection})!=len(collection): raise ValueError('Duplicate history IDs.')
            for b in collection:
                if b.source_id not in analytical or b.history_source_id not in sources or sources[b.history_source_id].role!='history': raise ValueError('Unresolved history source references.')
                if set(b.features)-{x.name for x in analytical[b.source_id].temporal.measurements}: raise ValueError('History references undeclared features.')
        for m in self.maturity:
            if m.source_id not in analytical or m.target not in analytical[m.source_id].task.target_names: raise ValueError('Maturity must bind a declared target.')
        if len({(x.source_id,x.target) for x in self.maturity})!=len(self.maturity): raise ValueError('Duplicate target maturity rules.')
        for x in analytical.values():
            if x.temporal.schedule.kind=='supplied' and (x.temporal.schedule.source_id not in sources or sources[x.temporal.schedule.source_id].role not in {'schedule','expectations'}): raise ValueError('Supplied schedule must reference an auxiliary source.')
        for f in self.evaluation.folds:
            if f.train_source_id not in analytical or f.evaluation_source_id not in analytical: raise ValueError('Unresolved fold sources.')
            if f.train_source_id==f.evaluation_source_id and not (f.train_interval and f.evaluation_interval): raise ValueError('Single-source folds require explicit train/evaluation windows.')
    @classmethod
    def from_dict(cls,value,*,base_directory=None):
        result=_construct(cls,value)
        if base_directory is not None:
            result=replace(result,inputs=tuple(replace(x,source=replace(x.source,path=str((Path(base_directory)/x.source.path).resolve()))) for x in result.inputs))
        return result


def exact_json(value):
    """Keep exact ticks and unsafe counts independent of JavaScript number precision."""
    if isinstance(value,int) and not isinstance(value,bool) and abs(value)>2**53-1:return str(value)
    if isinstance(value,dict):return {k:exact_json(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [exact_json(v) for v in value]
    return json_safe(value)


@dataclass
class TemporalAuditResult:
    spec: TemporalAuditSpec
    profile: dict
    declarations: dict
    parsing: dict
    checks: list
    evidence: list
    findings: list
    narrative: dict
    coverage: dict
    execution: dict
    context: dict
    generated_at: str
    schema_version: str = '1.4'
    methodology_id: str = 'temporal_reliability_v1'
    parsing_warnings: list = field(default_factory=list)
    @property
    def source_paths(self):return tuple(x.source.path for x in self.spec.inputs)
    def to_dict(self):
        v=asdict(self);v['spec']['inputs']=[{**x,'source':{**x['source'],'path':Path(x['source']['path']).name}} for x in v['spec']['inputs']]
        return exact_json(v)
    def json_text(self):return json.dumps(self.to_dict(),ensure_ascii=False,indent=2,allow_nan=False)
    def write_json(self,path):
        from datatrust.renderer import write_analysis_json
        return write_analysis_json(self,path)
    def generate_report(self,path):return self.generate_artifacts(path).html_path
    def generate_artifacts(self,path,**kwargs):
        from datatrust.renderer import write_report_artifacts
        return write_report_artifacts(self,path,**kwargs)
