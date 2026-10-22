"""Strict opt-in historical contracts. No database, HTTP or analytical imports."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from .contracts import (Contract, ClockSpec, CohortSpec, SourceSpec, EvaluationConfig,
                        EvaluationError, nested, sequence, name, positive, choice, digest)
from .method_contracts import parse_spec

HISTORY_METHOD = 'longitudinal_reliability_v1'
HISTORY_RESULT = 'confidenceguard.longitudinal_result/1.0'


def strings(obj, attr, nonempty=False):
    value = getattr(obj, attr)
    if not isinstance(value, (list, tuple)) or nonempty and not value:
        raise EvaluationError(f'{attr} requires an array of names.')
    for item in value:
        name(item)
    if len(set(value)) != len(value):
        raise EvaluationError(f'Duplicate {attr}.')
    object.__setattr__(obj, attr, tuple(value))


def instant(value):
    from .compat import clock
    tick, state = clock(value, ClockSpec('instant'))
    if state != 'valid':
        raise EvaluationError('An unambiguous instant is required.', 'invalid_clock')
    return tick


def now():
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class WorkspaceConfig(Contract):
    max_bytes: int = 64 * 1024**3
    free_disk_bytes: int = 2 * 1024**3
    chunk_bytes: int = 32 * 1024**2
    max_record_bytes: int = 8 * 1024**2
    saving: bool = False
    schema_version: str = 'confidenceguard.workspace_config/1.0'

    def __post_init__(self):
        for attr in ('max_bytes', 'free_disk_bytes', 'chunk_bytes', 'max_record_bytes'):
            positive(getattr(self, attr), attr)
        if self.chunk_bytes < self.max_record_bytes or not isinstance(self.saving, bool):
            raise EvaluationError('Invalid workspace recording configuration.')
        choice(self.schema_version, {'confidenceguard.workspace_config/1.0'}, 'workspace schema')


@dataclass(frozen=True)
class HistoricalRunBinding(Contract):
    run: str
    entity_namespace: str | None = None
    event_columns: tuple = ()
    opportunity_columns: tuple = ()
    target_columns: tuple = ()
    target_instance: str = 'default'
    opportunity_at: ClockSpec | None = None
    information_cutoff: ClockSpec | None = None
    available_at: ClockSpec | None = None
    attempt_column: str | None = None
    slot_column: str | None = None
    slot: str = 'default'
    revision_column: str | None = None
    predecessor_column: str | None = None
    correction_reason_column: str | None = None
    features: dict = field(default_factory=dict)

    def __post_init__(self):
        for attr in ('run', 'target_instance', 'slot'):
            name(getattr(self, attr))
        if self.entity_namespace is not None:name(self.entity_namespace)
        for attr in ('event_columns', 'opportunity_columns', 'target_columns'):
            strings(self, attr)
        for attr in ('opportunity_at', 'information_cutoff', 'available_at'):
            nested(self, attr, ClockSpec, True)
        for attr in ('attempt_column', 'slot_column', 'revision_column', 'predecessor_column', 'correction_reason_column'):
            if getattr(self, attr) is not None:
                name(getattr(self, attr))
        if not isinstance(self.features, dict):
            raise EvaluationError('Features map retained column names to numeric/categorical semantics.')
        for column, meaning in self.features.items():
            name(column)
            choice(meaning, {'numeric', 'categorical'}, 'feature semantics')
        if bool(self.predecessor_column) != bool(self.correction_reason_column):
            raise EvaluationError('Corrections require predecessor and reason bindings.')


@dataclass(frozen=True)
class PredictionBatchSpec(Contract):
    evaluation: object
    namespace: str
    outcome_definition_version: str
    bindings: tuple
    authority: str = 'supplied'
    history_complete: bool = False
    operation: str = 'ingest'
    name: str = 'Prediction batch'
    schema_version: str = 'confidenceguard.prediction_batch_spec/1.0'

    def __post_init__(self):
        object.__setattr__(self, 'evaluation', parse_spec(self.evaluation))
        sequence(self, 'bindings', HistoricalRunBinding)
        for attr in ('namespace', 'outcome_definition_version', 'authority', 'name'):
            name(getattr(self, attr))
        choice(self.operation, {'ingest', 'evaluate', 'study', 'fit', 'apply'}, 'recording operation')
        choice(self.schema_version, {'confidenceguard.prediction_batch_spec/1.0'}, 'batch schema')
        if not isinstance(self.history_complete, bool):
            raise EvaluationError('history_complete must be boolean.')
        spec = self.base
        if {b.run for b in self.bindings} != {r.id for r in spec.runs} or len(self.bindings) != len(spec.runs):
            raise EvaluationError('Bind every base run exactly once.')
        if any(not r.key_columns for r in spec.runs):
            raise EvaluationError('Historical predictions require explicit keys.', 'historical_keys_required')

    @property
    def base(self):
        return getattr(self.evaluation, 'evaluation', self.evaluation)

    @classmethod
    def from_dict(cls, value, *, base_directory=None):
        value = dict(value)
        if 'evaluation' in value:
            value['evaluation'] = parse_spec(value['evaluation'], base_directory=base_directory)
        return super().from_dict(value)


@dataclass(frozen=True)
class OutcomeRevisionSpec(Contract):
    source: SourceSpec
    namespace: str
    outcome_definition_version: str
    event_columns: tuple
    column: str
    revision_column: str
    order_column: str
    available_at: ClockSpec
    target_columns: tuple = ()
    target_instance: str = 'default'
    authority: str = 'supplied'
    status_column: str | None = None
    due_at: ClockSpec | None = None
    target_at: ClockSpec | None = None
    history_complete: bool = False
    schema_version: str = 'confidenceguard.outcome_revision_spec/1.0'

    def __post_init__(self):
        nested(self, 'source', SourceSpec)
        nested(self, 'available_at', ClockSpec)
        for attr in ('due_at', 'target_at'):
            nested(self, attr, ClockSpec, True)
        strings(self, 'event_columns', True)
        strings(self, 'target_columns')
        for attr in ('namespace', 'outcome_definition_version', 'column', 'revision_column', 'order_column', 'target_instance', 'authority'):
            name(getattr(self, attr))
        if self.status_column is not None:
            name(self.status_column)
        if not isinstance(self.history_complete, bool):
            raise EvaluationError('history_complete must be boolean.')
        choice(self.schema_version, {'confidenceguard.outcome_revision_spec/1.0'}, 'revision schema')


@dataclass(frozen=True)
class HistoricalCorrectionSpec(Contract):
    kind: str
    key: str
    revision: str
    predecessor: str
    authority: str
    available_at: str
    reason: str
    changes: dict
    schema_version: str = 'confidenceguard.historical_correction_spec/1.0'

    def __post_init__(self):
        choice(self.kind, {'prediction', 'context', 'opportunity'}, 'correction kind')
        for attr in ('key', 'revision', 'predecessor', 'authority', 'reason'):
            name(getattr(self, attr))
        instant(self.available_at)
        if not isinstance(self.changes, dict) or not self.changes:
            raise EvaluationError('Declare corrected attributes explicitly.')
        choice(self.schema_version, {'confidenceguard.historical_correction_spec/1.0'}, 'correction schema')


@dataclass(frozen=True)
class HistoricalWindow(Contract):
    id: str
    start: str
    end: str

    def __post_init__(self):
        name(self.id)
        if instant(self.start) >= instant(self.end):
            raise EvaluationError('Windows are nonempty half-open intervals.')


@dataclass(frozen=True)
class HistoricalComparison(Contract):
    id: str
    reference_window: str
    current_window: str
    reference_variant: str
    current_variant: str
    kind: str = 'temporal'
    second_reference_variant: str | None = None
    second_current_variant: str | None = None

    def __post_init__(self):
        for attr in ('id', 'reference_window', 'current_window', 'reference_variant', 'current_variant'):
            name(getattr(self, attr))
        choice(self.kind, {'temporal', 'matched', 'combined', 'contrast_change'}, 'historical comparison')
        if self.kind == 'contrast_change' and not (self.second_reference_variant and self.second_current_variant):
            raise EvaluationError('Contrast changes require both second variants.')


@dataclass(frozen=True)
class LongitudinalInferenceSpec(Contract):
    mode: str = 'descriptive'
    metrics: tuple = ()
    confidence: float = .95
    replicates: int = 2000
    seed: int = 0
    adjustment: str = 'bonferroni'
    independent_units: bool = False
    independent_periods: bool = False
    stationary: bool = False
    finite_moments: bool = False
    complete_bins: bool = False
    known_serial_dependence: bool = False
    known_common_shocks: bool = False
    known_nonstationarity: bool = False
    bin_ns: str | None = None
    block_length: int | None = None
    sensitivity_lengths: tuple = ()
    minimum_tail: int = 20
    work_units: int = 1000000000
    inference_required: bool = False
    exploratory: bool = True

    def __post_init__(self):
        choice(self.mode, {'descriptive', 'independent_periods', 'entity_clusters', 'moving_blocks', 'paired_rows', 'paired_clusters'}, 'historical inference')
        strings(self, 'metrics')
        choice(self.adjustment, {'pointwise', 'bonferroni'}, 'adjustment')
        if isinstance(self.confidence, bool) or not 0 < self.confidence < 1:
            raise EvaluationError('Confidence must be inside (0,1).')
        for attr in ('replicates', 'minimum_tail', 'work_units'):
            positive(getattr(self, attr), attr)
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise EvaluationError('Seed must be a nonnegative integer.')
        for attr in ('independent_units', 'independent_periods', 'stationary', 'finite_moments', 'complete_bins', 'known_serial_dependence', 'known_common_shocks', 'known_nonstationarity', 'inference_required', 'exploratory'):
            if not isinstance(getattr(self, attr), bool):
                raise EvaluationError(f'{attr} must be boolean.')
        if self.mode != 'descriptive' and not self.metrics:
            raise EvaluationError('Declare the complete inferential metric family.')
        if self.bin_ns is not None and (not isinstance(self.bin_ns, str) or not self.bin_ns.isdigit() or int(self.bin_ns) <= 0):
            raise EvaluationError('bin_ns requires an exact positive decimal integer string.')
        if self.block_length is not None:
            positive(self.block_length, 'block length')
        if not isinstance(self.sensitivity_lengths, (tuple, list)):
            raise EvaluationError('sensitivity_lengths requires an array.')
        if len(self.sensitivity_lengths) > 3 or len(set(self.sensitivity_lengths)) != len(self.sensitivity_lengths):
            raise EvaluationError('Declare at most three distinct sensitivity block lengths.')
        for length in self.sensitivity_lengths:
            positive(length, 'sensitivity block length')
        object.__setattr__(self, 'sensitivity_lengths', tuple(self.sensitivity_lengths))


@dataclass(frozen=True)
class LongitudinalSpec(Contract):
    namespace: str
    windows: tuple
    variants: tuple = ()
    batch_ids: tuple = ()
    comparisons: tuple = ()
    catalog_sequence: int | None = None
    prediction_catalog_sequence: int | None = None
    prediction_as_of: str | None = None
    as_of: str | None = None
    authority: str = 'supplied'
    maturity: str = 'mature_as_of'
    followup_ns: str | None = None
    roles: tuple = ('E', 'evaluation', 'production', 'unknown')
    slots: tuple = ('default',)
    attempts: dict = field(default_factory=dict)
    cohorts: tuple = ()
    features: dict = field(default_factory=dict)
    calibration_edges: tuple = tuple(i / 10 for i in range(11))
    material_thresholds: dict = field(default_factory=dict)
    drift_thresholds: dict = field(default_factory=dict)
    event_costs: dict = field(default_factory=dict)
    inference: LongitudinalInferenceSpec = field(default_factory=LongitudinalInferenceSpec)
    config: EvaluationConfig = field(default_factory=EvaluationConfig)
    restates: str | None = None
    restatement_reason: str | None = None
    outcome_only: bool = False
    context_view: str = 'original'
    max_windows: int = 120
    max_variants: int = 16
    max_comparisons: int = 64
    max_scan_records: int = 30000000
    min_segment_bins: int = 5
    min_segment_support: int = 30
    change_candidates: int = 5
    seasonal_period: int | None = None
    name: str = 'Longitudinal reliability assessment'
    schema_version: str = 'confidenceguard.longitudinal_spec/1.0'

    def __post_init__(self):
        for attr in ('namespace', 'authority', 'name'):
            name(getattr(self, attr))
        sequence(self, 'windows', HistoricalWindow)
        sequence(self, 'comparisons', HistoricalComparison)
        sequence(self, 'cohorts', CohortSpec)
        for attr in ('variants', 'batch_ids', 'roles', 'slots'):
            strings(self, attr)
        if len(self.slots) != 1:raise EvaluationError('Select exactly one prediction slot per assessment; slots cannot be pooled.','historical_slot_selection')
        nested(self, 'inference', LongitudinalInferenceSpec)
        nested(self, 'config', EvaluationConfig)
        if self.config.sampling.mode != 'descriptive':
            raise EvaluationError('Use historical inference, not row-independent legacy intervals.')
        if self.catalog_sequence is not None:
            positive(self.catalog_sequence, 'catalog sequence')
        if self.prediction_catalog_sequence is not None:
            positive(self.prediction_catalog_sequence, 'prediction catalog sequence')
            if self.catalog_sequence is not None and self.prediction_catalog_sequence > self.catalog_sequence:
                raise EvaluationError('Prediction snapshot cannot exceed the catalog snapshot.')
        if self.prediction_as_of is not None:instant(self.prediction_as_of)
        if self.as_of is not None:
            instant(self.as_of)
        choice(self.maturity, {'mature_as_of', 'equal_followup', 'observed'}, 'maturity policy')
        choice(self.context_view, {'original', 'revised'}, 'context view')
        if self.maturity == 'equal_followup' and (not isinstance(self.followup_ns, str) or not self.followup_ns.isdigit() or int(self.followup_ns) <= 0):
            raise EvaluationError('Equal follow-up requires positive followup_ns.')
        if not isinstance(self.outcome_only, bool) or bool(self.restates) != bool(self.restatement_reason):
            raise EvaluationError('Restatements require a predecessor and reason.')
        for attr in ('max_windows', 'max_variants', 'max_comparisons', 'max_scan_records', 'min_segment_bins', 'min_segment_support','change_candidates'):
            positive(getattr(self, attr), attr)
        if not self.windows or len(self.windows) > self.max_windows or len(self.variants) > self.max_variants or len(self.comparisons) > self.max_comparisons:
            raise EvaluationError('Historical declaration admission exceeded.', 'history_declaration_limit')
        groups = sum(len(c.categories)+2 if c.categories else len(c.edges)+2 for c in self.cohorts)
        if len(self.cohorts) > self.config.max_cohorts or groups > self.config.max_groups:
            raise EvaluationError('Historical cohort declaration admission exceeded.', 'history_declaration_limit')
        for attr in ('windows', 'comparisons'):
            if len({v.id for v in getattr(self, attr)}) != len(getattr(self, attr)):
                raise EvaluationError('Duplicate historical declaration ID.')
        windows = {w.id for w in self.windows}
        if any({c.reference_window, c.current_window} - windows for c in self.comparisons):
            raise EvaluationError('Unknown compared window.')
        for attr in ('features', 'attempts', 'material_thresholds', 'drift_thresholds','event_costs'):
            if not isinstance(getattr(self, attr), dict):
                raise EvaluationError(f'{attr} must be a mapping.')
        for key, value in self.features.items():
            name(key); choice(value, {'numeric', 'categorical'}, 'feature semantics')
        import math
        for key, value in self.material_thresholds.items():
            name(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise EvaluationError('Material thresholds must be finite and nonnegative.')
        from .history_metrics import DRIFT_MEASURES
        if len(self.drift_thresholds) > self.config.max_groups:
            raise EvaluationError('Drift threshold field admission exceeded.')
        for field_name, thresholds in self.drift_thresholds.items():
            name(field_name)
            if not isinstance(thresholds, dict) or not thresholds or set(thresholds)-DRIFT_MEASURES:
                raise EvaluationError('Drift thresholds require named supported distances.')
            for value in thresholds.values():
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                    raise EvaluationError('Drift thresholds must be finite and nonnegative.')
        if len(self.event_costs)>self.config.max_classes+1:raise EvaluationError('Cost action admission exceeded.')
        for action,outcomes in self.event_costs.items():
            name(action)
            if not isinstance(outcomes,dict) or not outcomes or len(outcomes)>self.config.max_classes:raise EvaluationError('Costs require bounded outcome mappings.')
            for outcome,cost in outcomes.items():
                name(outcome)
                if isinstance(cost,bool) or not isinstance(cost,(int,float)) or not math.isfinite(cost):raise EvaluationError('Event costs must be finite.')
        edges = self.calibration_edges
        if not isinstance(edges, (tuple, list)) or len(edges) < 2 or edges[0] != 0 or edges[-1] != 1 or any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in edges) or any(a >= b for a, b in zip(edges, edges[1:])):
            raise EvaluationError('Calibration edges must increase from zero to one.')
        object.__setattr__(self, 'calibration_edges', tuple(edges))
        if self.seasonal_period is not None:
            positive(self.seasonal_period, 'seasonal period')
        choice(self.schema_version, {'confidenceguard.longitudinal_spec/1.0'}, 'longitudinal schema')


@dataclass(frozen=True)
class HistoricalEvidenceManifest(Contract):
    operation_id: str
    objects: tuple
    metadata: dict
    schema_version: str = 'confidenceguard.historical_evidence_manifest/1.0'

    def __post_init__(self):
        name(self.operation_id)
        choice(self.schema_version, {'confidenceguard.historical_evidence_manifest/1.0'}, 'evidence schema')
        if not isinstance(self.objects, (tuple, list)) or not isinstance(self.metadata, dict):
            raise EvaluationError('Invalid historical evidence manifest.')
        object.__setattr__(self, 'objects', tuple(self.objects))

    @property
    def content_digest(self):
        return digest(self.to_dict())
