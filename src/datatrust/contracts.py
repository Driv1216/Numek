"""Small, serializable contracts for local CSV analysis.

No result contains a DataFrame or promises a particular execution backend.
"""

import codecs
import json
import math
from dataclasses import asdict, dataclass, field, fields
from enum import Enum
from pathlib import Path
from typing import Optional


class Applicability(str, Enum):
    APPLICABLE = "applicable"
    NOT_APPLICABLE = "not_applicable"
    BLOCKED = "blocked"
    UNSUPPORTED = "unsupported"


class ExecutionStatus(str, Enum):
    NOT_RUN = "not_run"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


def _positive(value, label, *, integer=False, optional=False):
    if value is None and optional:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a positive {'integer' if integer else 'number'}.")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite or value <= 0 or (integer and not isinstance(value, int)):
        raise ValueError(f"{label} must be a positive {'integer' if integer else 'number'}.")


def _construct(cls, value):
    if not isinstance(value, dict):
        raise ValueError(f"{cls.__name__} must be an object.")
    unknown = set(value) - {item.name for item in fields(cls)}
    if unknown:
        raise ValueError(f"Unknown {cls.__name__} fields: {', '.join(sorted(unknown))}.")
    return cls(**value)


@dataclass(frozen=True)
class DatasetSpec:
    path: str
    format: str = "csv"
    sample_unit: str = "row"
    dataset_name: Optional[str] = None
    purpose: Optional[str] = None
    source_filename: Optional[str] = None

    def __post_init__(self):
        if not isinstance(self.path, (str, Path)) or not str(self.path):
            raise ValueError("Dataset path must identify a local file.")
        if self.format != "csv" or self.sample_unit != "row":
            raise ValueError("M1 supports local CSV files with sample_unit='row' only.")


def _names(value, label):
    if not isinstance(value, (list, tuple)) or any(not isinstance(v, str) or not v for v in value):
        raise ValueError(f"{label} must be a sequence of nonempty column names.")
    if len(set(value)) != len(value):
        raise ValueError(f"Duplicate names in {label}.")
    return tuple(value)


@dataclass(frozen=True)
class TaskSpec:
    kind: str = "classification"
    target: Optional[str] = None
    targets: tuple = field(default=(), kw_only=True)
    feature_columns: Optional[tuple] = field(default=None, kw_only=True)
    metadata_columns: tuple = field(default=(), kw_only=True)
    group_columns: tuple = field(default=(), kw_only=True)

    def __post_init__(self):
        kinds = {"classification", "regression", "multilabel_classification", "dataset_profile", "clustering", "anomaly_detection"}
        if not isinstance(self.kind, str) or self.kind not in kinds:
            raise ValueError("Unsupported tabular task kind.")
        for name in ("targets", "metadata_columns", "group_columns"):
            object.__setattr__(self, name, _names(getattr(self, name), name))
        if self.feature_columns is not None:
            object.__setattr__(self, "feature_columns", _names(self.feature_columns, "feature_columns"))
        if self.target is not None and (not isinstance(self.target, str) or not self.target):
            raise ValueError("target must be a nonempty column name.")
        if self.target is not None and self.targets:
            raise ValueError("Do not supply competing target and targets declarations.")
        count = len(self.target_names)
        if self.kind == "classification" and count != 1:
            raise ValueError("Classification requires an explicit target column (exactly one).")
        if self.kind in {"regression", "multilabel_classification"} and not count:
            raise ValueError(f"{self.kind} requires an explicit target column or target tuple.")
        if self.kind in {"dataset_profile", "clustering", "anomaly_detection"} and count:
            raise ValueError("Unlabeled dataset profiling does not accept a target.")
        if set(self.target_names) & (set(self.metadata_columns) | set(self.group_columns)):
            raise ValueError("Targets cannot be metadata or group keys.")
        if self.feature_columns is not None and set(self.feature_columns) & (set(self.target_names) | set(self.metadata_columns) | set(self.group_columns)):
            raise ValueError("Feature roles overlap targets or metadata.")

    @property
    def target_names(self):
        return (self.target,) if self.target is not None else self.targets

    @classmethod
    def from_dict(cls, value):
        return _construct(cls, value)


@dataclass(frozen=True)
class AnnotationState:
    expectation: Optional[str] = None
    annotation_status: str = "unspecified"

    def __post_init__(self):
        if not isinstance(self.expectation, (str,type(None))) or self.expectation not in {None, "expected", "optional", "unknown"}:
            raise ValueError("Invalid annotation expectation override.")
        if not isinstance(self.annotation_status,str) or self.annotation_status not in {"unspecified", "observed", "intentionally_unlabeled", "unknown", "uncertain"}:
            raise ValueError("Invalid annotation status.")
        if self.expectation == "expected" and self.annotation_status == "intentionally_unlabeled":
            raise ValueError("An expected annotation cannot be intentionally absent.")


def canonical_status_values():
    return {"expected": AnnotationState("expected"), "optional": AnnotationState("optional"),
            "observed": AnnotationState(annotation_status="observed"),
            "intentionally_unlabeled": AnnotationState("optional", "intentionally_unlabeled"),
            "unknown": AnnotationState("unknown", "unknown"),
            "uncertain": AnnotationState(annotation_status="uncertain")}


@dataclass(frozen=True)
class AnnotationSpec:
    expectation: str = "unknown"
    status_column: Optional[str] = None
    status_values: Optional[dict] = None

    def __post_init__(self):
        if not isinstance(self.expectation,str) or self.expectation not in {"expected", "optional", "unknown"}:
            raise ValueError("Annotation expectation must be expected, optional, or unknown.")
        if self.status_column is not None and (not isinstance(self.status_column, str) or not self.status_column):
            raise ValueError("status_column must be a column name.")
        if self.status_values is not None:
            if self.status_column is None or not isinstance(self.status_values, dict):
                raise ValueError("status_values requires a status_column and a token mapping.")
            converted = {}
            for token, state in self.status_values.items():
                if not isinstance(token, str):
                    raise ValueError("Status tokens must be literal strings.")
                state = _construct(AnnotationState, state) if isinstance(state, dict) else state
                if not isinstance(state, AnnotationState):
                    raise ValueError("Status mappings must contain AnnotationState declarations.")
                if (state.expectation or self.expectation) == "expected" and state.annotation_status == "intentionally_unlabeled":
                    raise ValueError("An expected annotation cannot be intentionally absent.")
                converted[token] = state
            object.__setattr__(self, "status_values", converted)


@dataclass(frozen=True)
class AnnotationOptions:
    default: AnnotationSpec = field(default_factory=AnnotationSpec)
    per_target: dict = field(default_factory=dict)

    def __post_init__(self):
        if isinstance(self.default, dict):
            object.__setattr__(self, "default", _construct(AnnotationSpec, self.default))
        if not isinstance(self.default, AnnotationSpec) or not isinstance(self.per_target, dict):
            raise ValueError("Invalid AnnotationOptions.")
        converted = {k: _construct(AnnotationSpec, v) if isinstance(v, dict) else v for k, v in self.per_target.items()}
        if any(not isinstance(k, str) or not isinstance(v, AnnotationSpec) for k, v in converted.items()):
            raise ValueError("per_target must map target names to AnnotationSpec.")
        object.__setattr__(self, "per_target", converted)

    @classmethod
    def from_dict(cls, value):
        return _construct(cls, value)


@dataclass(frozen=True)
class FeatureOptions:
    semantic_types: dict = field(default_factory=dict)
    scale_sensitive: Optional[bool] = None

    def __post_init__(self):
        if not isinstance(self.semantic_types, dict) or any(not isinstance(k, str) or not k or not isinstance(v,str) or v not in {"quantitative", "categorical", "identifier", "unknown"} for k, v in self.semantic_types.items()):
            raise ValueError("Invalid feature semantic_types mapping.")
        if self.scale_sensitive is not None and not isinstance(self.scale_sensitive, bool):
            raise ValueError("scale_sensitive must be boolean or null.")


@dataclass(frozen=True)
class MultilabelOptions:
    minimum_positive: Optional[int] = None
    maximum_positive: Optional[int] = None
    mutually_exclusive: tuple = ()
    requires: tuple = ()

    def __post_init__(self):
        for name in ("minimum_positive", "maximum_positive"):
            value = getattr(self, name)
            if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
                raise ValueError(f"{name} must be a nonnegative integer.")
        if self.minimum_positive is not None and self.maximum_positive is not None and self.minimum_positive > self.maximum_positive:
            raise ValueError("Contradictory positive-count bounds.")
        for name in ("mutually_exclusive", "requires"):
            value = getattr(self, name)
            if not isinstance(value, (tuple, list)):
                raise ValueError(f"{name} must be a sequence.")
            groups = tuple(_names(v, name) for v in value)
            if any(len(g) < 2 or (name == "requires" and len(g) != 2) for g in groups):
                raise ValueError("Constraint groups require at least two labels; requirements require two.")
            if len(set(groups)) != len(groups):
                raise ValueError("Duplicate label constraints.")
            object.__setattr__(self, name, groups)


@dataclass(frozen=True)
class DiagnosticLimits:
    max_multilabel_pair_targets: int = 32
    max_output_pair_targets: int = 32
    max_multilabel_comparisons: int = 20000000
    max_output_comparisons: int = 20000000
    max_cohort_comparisons: int = 20000000
    max_patterns: int = 10000
    max_examples: int = 5

    def __post_init__(self):
        for item in fields(self):
            _positive(getattr(self, item.name), item.name, integer=True)


@dataclass(frozen=True)
class PresentationLimits:
    executive_actions: int = 5
    target_panels: int = 6
    feature_details: int = 20
    table_rows: int = 20
    appendix_rows: int = 100

    def __post_init__(self):
        for item in fields(self):
            _positive(getattr(self, item.name), item.name, integer=True)


@dataclass(frozen=True)
class CsvParseOptions:
    encoding: str = "utf-8"
    missing_policy: str = "pandas_default"
    na_values: tuple = ()
    column_types: dict = field(default_factory=dict)
    column_missing_policies: dict = field(default_factory=dict, kw_only=True)
    delimiter: str = field(default=",", kw_only=True)

    def __post_init__(self):
        if not isinstance(self.delimiter, str) or len(self.delimiter) != 1 or self.delimiter in {'"', "\r", "\n"}:
            raise ValueError("delimiter must be one character other than a quote or a line break.")
        if not isinstance(self.encoding, str):
            raise ValueError("encoding must be a supported text encoding.")
        try:
            codecs.lookup(self.encoding)
        except LookupError as exc:
            raise ValueError(f"Unknown text encoding: {self.encoding}.") from exc
        if not isinstance(self.missing_policy, str) or self.missing_policy not in {"pandas_default", "empty_only", "custom"}:
            raise ValueError("missing_policy must be pandas_default, empty_only, or custom.")
        if not isinstance(self.na_values, (tuple, list)) or any(not isinstance(v, str) for v in self.na_values):
            raise ValueError("na_values must be a list of literal strings.")
        object.__setattr__(self, "na_values", tuple(self.na_values))
        if self.missing_policy != "custom" and self.na_values:
            raise ValueError("na_values are only allowed with missing_policy='custom'.")
        if not isinstance(self.column_types, dict) or any(
            not isinstance(k, str) or not isinstance(v, str) or v not in {"string", "numeric"}
            for k, v in self.column_types.items()
        ):
            raise ValueError("column_types must map resolved column names to string or numeric.")
        object.__setattr__(self, "column_types", dict(self.column_types))
        if not isinstance(self.column_missing_policies, dict):
            raise ValueError("column_missing_policies must be an object.")
        for name, policy in self.column_missing_policies.items():
            if not isinstance(name, str) or not name or not isinstance(policy, dict) or set(policy) - {"missing_policy", "na_values"}:
                raise ValueError("Invalid per-column missing policy.")
            CsvParseOptions(missing_policy=policy.get("missing_policy", "empty_only"), na_values=policy.get("na_values", ()))


@dataclass(frozen=True)
class FidelityInspectionLimits:
    max_bytes: int = 1048576
    max_records: int = 200
    max_cells: int = 20000

    def __post_init__(self):
        for item in fields(self):
            _positive(getattr(self, item.name), item.name, integer=True)


@dataclass(frozen=True)
class ExecutionLimits:
    max_source_bytes: Optional[int] = None
    max_rows: Optional[int] = None
    max_columns: Optional[int] = None
    max_frame_bytes: Optional[int] = None
    max_seconds: Optional[float] = None

    def __post_init__(self):
        for item in fields(self):
            _positive(getattr(self, item.name), item.name, integer=item.name != "max_seconds", optional=True)

    @classmethod
    def unlabeled_defaults(cls):
        return cls(100 * 1048576, 1000000, 1000, 512 * 1048576)


@dataclass(frozen=True)
class TargetExpectations:
    kind: str = "unspecified"
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    nonnegative: Optional[bool] = None
    integer_required: Optional[bool] = None
    units: Optional[str] = None

    def __post_init__(self):
        if not isinstance(self.kind, str) or self.kind not in {"unspecified", "continuous", "count"}:
            raise ValueError("Target kind must be unspecified, continuous, or count.")
        for name in ("minimum", "maximum"):
            value = getattr(self, name)
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)):
                raise ValueError(f"{name} must be a finite number or null.")
        for name in ("nonnegative", "integer_required"):
            if getattr(self, name) is not None and not isinstance(getattr(self, name), bool):
                raise ValueError(f"{name} must be a boolean or null.")
            if self.kind == "count":
                if getattr(self, name) is False:
                    raise ValueError("Count targets require nonnegative integer values.")
                object.__setattr__(self, name, True)
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("Target minimum must not exceed maximum.")
        lower = max(0, self.minimum if self.minimum is not None else 0) if self.nonnegative else self.minimum
        if self.maximum is not None and lower is not None and lower > self.maximum:
            raise ValueError("Target declarations have an impossible intersection.")
        if self.integer_required and lower is not None and self.maximum is not None and math.ceil(lower) > math.floor(self.maximum):
            raise ValueError("Declared range contains no permitted integer.")
        if self.units is not None and (not isinstance(self.units, str) or not self.units.strip() or len(self.units) > 80):
            raise ValueError("Units must be nonempty text of at most 80 characters.")


@dataclass(frozen=True)
class RegressionRelationLimits:
    max_single_comparisons: int = 20000000
    max_pair_comparisons: int = 20000000
    max_pair_features: int = 32
    max_screen_rows: int = 512

    def __post_init__(self):
        for item in fields(self):
            _positive(getattr(self, item.name), item.name, integer=True)


@dataclass(frozen=True)
class RegressionOptions:
    expectations: TargetExpectations = field(default_factory=TargetExpectations)
    feature_availability: dict = field(default_factory=dict)
    relation_limits: RegressionRelationLimits = field(default_factory=RegressionRelationLimits)

    expectations_by_target: dict = field(default_factory=dict, kw_only=True)

    def __post_init__(self):
        if not isinstance(self.expectations_by_target, dict):
            raise ValueError("expectations_by_target must be an object.")
        mapped = {k: _construct(TargetExpectations, v) if isinstance(v, dict) else v for k, v in self.expectations_by_target.items()}
        if any(not isinstance(k, str) or not isinstance(v, TargetExpectations) for k, v in mapped.items()):
            raise ValueError("Invalid per-output expectations.")
        object.__setattr__(self, "expectations_by_target", mapped)
        if not isinstance(self.expectations, TargetExpectations):
            raise ValueError("expectations must be TargetExpectations.")
        if not isinstance(self.relation_limits, RegressionRelationLimits):
            raise ValueError("relation_limits must be RegressionRelationLimits.")
        allowed = {"available_at_prediction", "unavailable_at_prediction", "unknown"}
        if not isinstance(self.feature_availability, dict) or any(not isinstance(k, str) or not isinstance(v, str) or v not in allowed for k, v in self.feature_availability.items()):
            raise ValueError("Feature availability must map column names to available_at_prediction, unavailable_at_prediction, or unknown.")
        object.__setattr__(self, "feature_availability", dict(self.feature_availability))

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict) or set(value) - {"expectations", "feature_availability", "relation_limits", "expectations_by_target"}:
            raise ValueError("RegressionOptions must contain only expectations, feature_availability, and relation_limits.")
        return cls(_construct(TargetExpectations, value.get("expectations", {})),
                   value.get("feature_availability", {}),
                   _construct(RegressionRelationLimits, value.get("relation_limits", {})),
                   expectations_by_target=value.get("expectations_by_target", {}))


CONTEXT_MEANINGS = ("not_collected", "not_applicable", "refused", "censored", "category")
AVAILABILITY_VALUES = ("available_at_prediction", "unavailable_at_prediction", "unknown")
CONDITION_OPERATORS = ("=", "!=", ">", ">=", "<", "<=", "is_null", "not_null")


def _finite_scalar(value):
    return isinstance(value, (str, int, float)) and not isinstance(value, bool) and not (isinstance(value, float) and not math.isfinite(value))


@dataclass(frozen=True)
class ColumnContext:
    """What you declare about one column (context_v1). Declarations never change parsed values, findings or scores;
    they produce a separate interpreted view beside the raw evidence."""
    availability: Optional[str] = None
    placeholders: dict = field(default_factory=dict)
    sentinels: tuple = ()
    applies_when: Optional[dict] = None
    unit: Optional[str] = None

    def __post_init__(self):
        if self.availability is not None and self.availability not in AVAILABILITY_VALUES:
            raise ValueError("Availability must be available_at_prediction, unavailable_at_prediction or unknown.")
        if not isinstance(self.placeholders, dict) or any(not isinstance(k, str) or not k or v not in CONTEXT_MEANINGS for k, v in self.placeholders.items()):
            raise ValueError("Placeholders map text values to one of: " + ", ".join(CONTEXT_MEANINGS) + ".")
        if not isinstance(self.sentinels, (list, tuple)):
            raise ValueError("Sentinels must be a list.")
        sentinels = []
        for item in self.sentinels:
            if not isinstance(item, dict) or set(item) - {"value", "meaning"} or isinstance(item.get("value"), bool) \
                    or not isinstance(item.get("value"), (int, float)) or not math.isfinite(item["value"]) or item.get("meaning") not in CONTEXT_MEANINGS:
                raise ValueError("Each sentinel needs a finite numeric value and a declared meaning.")
            sentinels.append({"value": item["value"], "meaning": item["meaning"]})
        if len({s["value"] for s in sentinels}) != len(sentinels):
            raise ValueError("A sentinel value is declared twice.")
        object.__setattr__(self, "sentinels", tuple(sentinels))
        if self.applies_when is not None:
            c = self.applies_when
            if not isinstance(c, dict) or set(c) - {"column", "op", "value"} or not isinstance(c.get("column"), str) or not c["column"] \
                    or c.get("op") not in CONDITION_OPERATORS or (c["op"] not in {"is_null", "not_null"} and not _finite_scalar(c.get("value"))):
                raise ValueError("applies_when needs a column, an operator (" + ", ".join(CONDITION_OPERATORS) + ") and a scalar value.")
            object.__setattr__(self, "applies_when", dict(c))
        if self.unit is not None and (not isinstance(self.unit, str) or len(self.unit) > 40):
            raise ValueError("A unit is a short text label.")


@dataclass(frozen=True)
class DependencyLimits:
    """Bounds of the target-dependency search: features examined, feature-target checks, and row work."""
    max_features: int = 64
    max_checks: int = 128
    max_row_work: int = 200_000_000

    def __post_init__(self):
        for item in fields(self):
            _positive(getattr(self, item.name), item.name, integer=True)


@dataclass(frozen=True)
class ContextOptions:
    """Optional context (context_v1): the prediction objective and point, and per-column declarations."""
    objective: Optional[str] = None
    prediction_point: Optional[str] = None
    columns: dict = field(default_factory=dict)
    limits: DependencyLimits = field(default_factory=DependencyLimits)

    def __post_init__(self):
        for name in ("objective", "prediction_point"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or len(value) > 500):
                raise ValueError(f"{name} must be text of at most 500 characters.")
        if not isinstance(self.columns, dict) or any(not isinstance(k, str) or not k for k in self.columns):
            raise ValueError("Context columns must map column names to declarations.")
        object.__setattr__(self, "columns", {k: _construct(ColumnContext, v) if isinstance(v, dict) else v for k, v in self.columns.items()})
        if any(not isinstance(v, ColumnContext) for v in self.columns.values()):
            raise ValueError("Invalid column declaration.")
        if isinstance(self.limits, dict):
            object.__setattr__(self, "limits", _construct(DependencyLimits, self.limits))
        if not isinstance(self.limits, DependencyLimits):
            raise ValueError("limits must be DependencyLimits.")

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict) or set(value) - {"prediction", "columns", "limits"}:
            raise ValueError("Context must contain only prediction, columns and limits.")
        prediction = value.get("prediction") or {}
        if not isinstance(prediction, dict) or set(prediction) - {"objective", "point"}:
            raise ValueError("prediction must contain only objective and point.")
        return cls(prediction.get("objective") or None, prediction.get("point") or None, value.get("columns", {}), value.get("limits", {}))

    def to_dict(self):
        return {"prediction": {"objective": self.objective, "point": self.prediction_point},
                "columns": {k: {f.name: getattr(v, f.name) for f in fields(v) if getattr(v, f.name) not in (None, {}, ())} for k, v in self.columns.items()},
                "limits": asdict(self.limits)}

    def availability(self):
        return {k: v.availability for k, v in self.columns.items() if v.availability}


@dataclass(frozen=True)
class AnalysisConfig:
    parsing: CsvParseOptions = field(default_factory=CsvParseOptions)
    fidelity_inspection: FidelityInspectionLimits = field(default_factory=FidelityInspectionLimits)
    limits: Optional[ExecutionLimits] = None
    regression: Optional[RegressionOptions] = None
    annotations: Optional[AnnotationOptions] = field(default=None, kw_only=True)
    features: FeatureOptions = field(default_factory=FeatureOptions, kw_only=True)
    multilabel: Optional[MultilabelOptions] = field(default=None, kw_only=True)
    diagnostics: DiagnosticLimits = field(default_factory=DiagnosticLimits, kw_only=True)
    presentation: PresentationLimits = field(default_factory=PresentationLimits, kw_only=True)
    execution: object = field(default=None, kw_only=True)
    advanced: object = field(default=None, kw_only=True)
    context: Optional[ContextOptions] = field(default=None, kw_only=True)  # context_v1; omitted from records when absent

    def __post_init__(self):
        from datatrust.m4_contracts import ExecutionOptions, AdvancedTabularOptions
        for name, cls in (("execution", ExecutionOptions), ("advanced", AdvancedTabularOptions)):
            if getattr(self, name) is not None and not isinstance(getattr(self, name), cls):
                raise ValueError(f"{name} must be {cls.__name__}.")
        if self.advanced is not None and self.execution is not None and self.execution.backend != "duckdb_local":
            raise ValueError("Advanced tabular diagnostics require duckdb_local.")
        for name, cls in (("annotations", AnnotationOptions), ("features", FeatureOptions), ("multilabel", MultilabelOptions), ("diagnostics", DiagnosticLimits), ("presentation", PresentationLimits)):
            value = getattr(self, name)
            if not isinstance(value, cls) and not (name in {"annotations", "multilabel"} and value is None):
                raise ValueError(f"{name} must be {cls.__name__}.")
        if not isinstance(self.parsing, CsvParseOptions):
            raise ValueError("parsing must be CsvParseOptions.")
        if not isinstance(self.fidelity_inspection, FidelityInspectionLimits):
            raise ValueError("fidelity_inspection must be FidelityInspectionLimits.")
        if self.limits is not None and not isinstance(self.limits, ExecutionLimits):
            raise ValueError("limits must be ExecutionLimits or None.")
        if self.regression is not None and not isinstance(self.regression, RegressionOptions):
            raise ValueError("regression must be RegressionOptions or None.")
        if isinstance(self.context, dict):
            object.__setattr__(self, "context", ContextOptions.from_dict(self.context))
        if self.context is not None and not isinstance(self.context, ContextOptions):
            raise ValueError("context must be ContextOptions or None.")
        if self.context is not None and self.regression is not None:
            # The existing regression availability contract stays the source of truth; the two must agree.
            for column, value in self.context.availability().items():
                declared = self.regression.feature_availability.get(column)
                if declared is not None and declared != value:
                    raise ValueError(f"Availability for {column} is declared twice with different values.")

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict):
            raise ValueError("Analysis configuration must be a JSON object.")
        unknown = set(value) - {"parsing", "fidelity_inspection", "limits", "regression", "annotations", "features", "multilabel", "diagnostics", "presentation", "execution", "advanced", "context"}
        if unknown:
            raise ValueError(f"Unknown AnalysisConfig fields: {', '.join(sorted(unknown))}.")
        from datatrust.m4_contracts import ExecutionOptions, AdvancedTabularOptions
        return cls(
            parsing=_construct(CsvParseOptions, value.get("parsing", {})),
            fidelity_inspection=_construct(FidelityInspectionLimits, value.get("fidelity_inspection", {})),
            limits=_construct(ExecutionLimits, value["limits"]) if value.get("limits") is not None else None,
            regression=RegressionOptions.from_dict(value["regression"]) if value.get("regression") is not None else None,
            annotations=AnnotationOptions.from_dict(value["annotations"]) if value.get("annotations") is not None else None,
            features=_construct(FeatureOptions, value.get("features", {})),
            multilabel=_construct(MultilabelOptions, value["multilabel"]) if value.get("multilabel") is not None else None,
            diagnostics=_construct(DiagnosticLimits, value.get("diagnostics", {})),
            presentation=_construct(PresentationLimits, value.get("presentation", {})),
            execution=ExecutionOptions.from_dict(value["execution"]) if value.get("execution") is not None else None,
            advanced=AdvancedTabularOptions.from_dict(value["advanced"]) if value.get("advanced") is not None else None,
            context=_context_from_record(value["context"]) if value.get("context") is not None else None,
        )


def _context_from_record(value):
    """Accepts the declaration layout ({prediction, columns, limits}) and the record layout asdict() produces."""
    if isinstance(value, dict) and "prediction" not in value and {"objective", "prediction_point"} & set(value):
        return ContextOptions(value.get("objective"), value.get("prediction_point"), value.get("columns", {}), value.get("limits", {}))
    return ContextOptions.from_dict(value)


@dataclass
class CheckOutcome:
    check_id: str
    applicability: Applicability = Applicability.APPLICABLE
    execution: ExecutionStatus = ExecutionStatus.COMPLETED
    scope: str = "dataset"
    reason: Optional[str] = None
    evidence_refs: list = field(default_factory=list)
    exclusions: list = field(default_factory=list)
    version: str = "1"


@dataclass
class EvidenceRecord:
    id: str
    check_id: str
    measurement_refs: list
    population: str
    denominator: Optional[int] = None
    affected_count: Optional[int] = None
    affected_columns: list = field(default_factory=list)
    row_refs: list = field(default_factory=list)
    method: str = "deterministic"
    thresholds: dict = field(default_factory=dict)
    source_ids: tuple = field(default=(), kw_only=True)
    source_pair: tuple = field(default=(), kw_only=True)
    population_id: Optional[str] = field(default=None, kw_only=True)


@dataclass(frozen=True)
class ReportArtifacts:
    html_path: Optional[str] = None
    pdf_path: Optional[str] = None
    json_path: Optional[str] = None
    reused_html: bool = False
    qa_metadata: Optional[dict] = field(default=None, kw_only=True)


class AnalysisError(ValueError):
    """An actionable execution or configuration failure, with a stage/code."""

    def __init__(self, message, *, code="analysis_failed", stage="analysis"):
        super().__init__(message)
        self.code = code
        self.stage = stage


_PARSE_OPTION_KEYS = {"encoding", "missing_policy", "na_values", "column_types"}


def omit_default_delimiter(value):
    """Records of CsvParseOptions leave out the default comma delimiter (its last field), so comma files keep the
    exact records, fingerprints and seals they had before the delimiter became configurable."""
    if isinstance(value, dict):
        record = {k: omit_default_delimiter(v) for k, v in value.items()}
        if _PARSE_OPTION_KEYS <= record.keys() and record.get("delimiter") == ",":
            record.pop("delimiter")
        if {"parsing", "fidelity_inspection"} <= record.keys() and "context" in record and record["context"] is None:
            record.pop("context")
        return record
    if isinstance(value, (tuple, list)):
        return type(value)(omit_default_delimiter(v) for v in value)
    return value


def json_safe(value):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        record = {str(k): json_safe(v) for k, v in value.items()}
        if _PARSE_OPTION_KEYS <= record.keys() and record.get("delimiter") == ",":
            record.pop("delimiter")
        if {"parsing", "fidelity_inspection"} <= record.keys() and "context" in record and record["context"] is None:
            record.pop("context")
        return record
    if isinstance(value, (tuple, list)):
        return [json_safe(v) for v in value]
    if hasattr(value, "item"):
        return json_safe(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None if math.isnan(value) else ("Infinity" if value > 0 else "-Infinity")
    return value


@dataclass
class AnalysisResult:
    dataset: DatasetSpec
    task: TaskSpec
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
    schema_version: str = "1.0"
    guidance: dict = field(default_factory=dict, kw_only=True)  # finding_guidance_v1 and later; absent before
    contextual: dict = field(default_factory=dict, kw_only=True)  # context_v1 and later; absent before

    @property
    def source_paths(self):
        return (self.dataset.path,)

    def to_legacy_dict(self):
        if self.methodology_id != "classification_legacy_2026_08_13":
            raise ValueError("Only classification has a legacy result projection.")
        return {
            "profile": self.profile,
            "scores": self.scoring["values"],
            "risks": self.findings[:3],
            "findings": self.findings,
            "narrative": self.narrative,
            "context": self.context,
            # A file read with another separator says so; comma files keep the exact legacy projection.
            **({"parsing": {"delimiter": delimiter}} if (delimiter := (self.parsing or {}).get("options", {}).get("delimiter")) else {}),
        }

    def to_dict(self):
        value = asdict(self)
        if self.schema_version != '1.3':
            for record in value['evidence']:
                for key in ('source_ids', 'source_pair', 'population_id'): record.pop(key, None)
        if self.schema_version in {"1.0", "1.1"}:
            value["task"] = {"kind": self.task.kind, "target": self.task.target_names[0] if self.task.target_names else None}
        value["dataset"]["path"] = self.context["source_filename"]
        value["profile"].pop("dataset_path", None)
        if not value["guidance"]:
            value.pop("guidance")
        if not value["contextual"]:
            value.pop("contextual")
        return json_safe(value)

    def json_text(self):
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, allow_nan=False) + "\n"

    def write_json(self, path):
        from datatrust.renderer import write_analysis_json
        return write_analysis_json(self, path)

    def generate_artifacts(self, path, *, format="html", html_path=None, json_path=None):
        from datatrust.renderer import write_report_artifacts
        return write_report_artifacts(self, path, format=format, html_path=html_path, json_path=json_path)

    def generate_report(self, path, *, format="html", html_path=None):
        artifacts = self.generate_artifacts(path, format=format, html_path=html_path)
        return artifacts.pdf_path if format == "pdf" else artifacts.html_path
