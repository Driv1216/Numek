"""Strict typed evidence declarations; independent of analytical and HTTP code."""
from dataclasses import dataclass, field
from .contracts import Contract, EvaluationError, SourceSpec, ClockSpec, choice, name, nested, sequence, positive

ENCODER_DIMENSIONS={'e5_text':384,'dinov2_image':768}


def names(values, label, *, required=False):
    if not isinstance(values, (tuple, list)) or required and not values:
        raise EvaluationError(f'{label} requires an array of names.')
    for value in values: name(value)
    if len(set(values)) != len(values): raise EvaluationError(f'Duplicate {label}.')
    return tuple(values)


@dataclass(frozen=True)
class FeatureField(Contract):
    id: str
    column: str
    kind: str = 'categorical'
    role: str = 'context'
    units: str | None = None
    missing_values: tuple = ('',)
    boolean_true: tuple = ('true', '1', 'True')
    boolean_false: tuple = ('false', '0', 'False')
    available_at: ClockSpec | None = None
    effective_at: ClockSpec | None = None
    outcome_derived: bool = False

    def __post_init__(self):
        name(self.id); name(self.column)
        choice(self.kind, {'categorical','boolean','integer','decimal','float','timestamp','text','asset'}, 'feature type')
        choice(self.role, {'context','model_input','prediction_derived','retrospective'}, 'feature role')
        if self.units is not None: name(self.units)
        for attr in ('missing_values','boolean_true','boolean_false'):
            value=getattr(self,attr)
            if not isinstance(value,(tuple,list)) or any(not isinstance(x,str) for x in value): raise EvaluationError(f'Invalid {attr}.')
            object.__setattr__(self,attr,tuple(value))
        if set(self.boolean_true)&set(self.boolean_false): raise EvaluationError('Boolean spellings overlap.')
        for attr in ('available_at','effective_at'): nested(self,attr,ClockSpec,True)
        if not isinstance(self.outcome_derived,bool): raise EvaluationError('outcome_derived must be boolean.')


@dataclass(frozen=True)
class FeatureViewSpec(Contract):
    id: str
    fields: tuple
    source: str | None = None
    key_columns: tuple = ()
    owner: str = 'opportunity'
    run: str | None = None
    revision: str = 'initial'
    predecessor: str | None = None
    authority: str = 'supplied'
    reason: str | None = None
    available_at: ClockSpec | None = None
    information_cutoff: ClockSpec | None = None
    availability: str = 'unknown'
    schema_version: str = 'confidenceguard.feature_view_spec/1.0'

    def __post_init__(self):
        for attr in ('id','revision','authority'): name(getattr(self,attr))
        sequence(self,'fields',FeatureField)
        if not self.fields or len({f.id for f in self.fields})!=len(self.fields): raise EvaluationError('Feature fields require unique identities.')
        object.__setattr__(self,'key_columns',names(self.key_columns,'feature keys'))
        choice(self.owner,{'opportunity','prediction_revision'},'feature owner')
        choice(self.availability,{'unknown','at_decision','dated'},'feature availability declaration')
        if self.owner=='prediction_revision' and self.run is None: raise EvaluationError('Prediction-owned features require a run.')
        for attr in ('source','run','predecessor','reason'):
            if getattr(self,attr) is not None: name(getattr(self,attr))
        if bool(self.predecessor)!=bool(self.reason): raise EvaluationError('Feature revisions require predecessor and reason together.')
        for attr in ('available_at','information_cutoff'): nested(self,attr,ClockSpec,True)
        if self.schema_version!='confidenceguard.feature_view_spec/1.0': raise EvaluationError('Unsupported feature view.')


@dataclass(frozen=True)
class DiscoveryRepresentationSpec(Contract):
    id: str
    kind: str = 'supplied'
    matrix_path: str | None = None
    keys_source: SourceSpec | None = None
    key_columns: tuple = ()
    dimensions: int | None = None
    run: str | None = None
    producer: str = 'supplied'
    model_digest: str | None = None
    normalization: str = 'none'
    available_at: ClockSpec | None = None
    content_available_at: ClockSpec | None = None
    availability: str = 'unknown'
    field: str | None = None
    model_directory: str | None = None
    runtime_profile: str = 'encoders_cpu_v1'
    max_windows_per_event: int = 32
    schema_version: str = 'confidenceguard.discovery_representation_spec/1.0'

    def __post_init__(self):
        name(self.id); name(self.producer)
        if self.model_digest is not None:
            import re
            if not isinstance(self.model_digest,str) or not re.fullmatch('[0-9a-f]{64}',self.model_digest):raise EvaluationError('Model digest must be a lowercase SHA-256 identity.','representation_identity')
        choice(self.kind,{'supplied','retained','e5_text','dinov2_image'},'discovery representation')
        choice(self.normalization,{'none','l2'},'representation normalization')
        choice(self.availability,{'unknown','at_decision','dated'},'representation content availability')
        choice(self.runtime_profile,{'encoders_cpu_v1','encoders_cpu_py314_v1'},'encoder runtime')
        object.__setattr__(self,'key_columns',names(self.key_columns,'representation keys'))
        nested(self,'keys_source',SourceSpec,True)
        for attr in ('available_at','content_available_at'): nested(self,attr,ClockSpec,True)
        if self.dimensions is not None: positive(self.dimensions,'dimensions')
        if self.kind in ENCODER_DIMENSIONS and self.dimensions is not None and self.dimensions!=ENCODER_DIMENSIONS[self.kind]:
            raise EvaluationError('Declared dimensions differ from the pinned encoder profile.','vector_shape')
        positive(self.max_windows_per_event,'max_windows_per_event')
        if self.kind=='supplied' and (not self.matrix_path or self.keys_source is None or not self.key_columns):
            raise EvaluationError('Supplied vectors require a matrix and explicitly keyed metadata.')
        if self.kind in {'e5_text','dinov2_image'} and (not self.field or not self.model_directory): raise EvaluationError('Offline encoding requires a field and verified local model directory.')
        if self.schema_version!='confidenceguard.discovery_representation_spec/1.0': raise EvaluationError('Unsupported discovery representation.')


@dataclass(frozen=True)
class FeatureEnrichmentSpec(Contract):
    source: SourceSpec
    namespace: str
    view: FeatureViewSpec
    acquired_at: str
    opportunity_column: str = 'opportunity_key'
    prediction_revision_column: str | None = None
    predecessor_column: str | None = None
    schema_version: str = 'confidenceguard.feature_enrichment_spec/1.0'

    def __post_init__(self):
        nested(self,'source',SourceSpec);nested(self,'view',FeatureViewSpec)
        for value in (self.namespace,self.opportunity_column):name(value)
        from .history_contracts import instant
        instant(self.acquired_at)
        if self.view.owner=='prediction_revision' and not self.prediction_revision_column:raise EvaluationError('Prediction enrichment requires exact prediction fact identities.')
        if self.predecessor_column is not None:name(self.predecessor_column)
        if self.prediction_revision_column is not None:name(self.prediction_revision_column)
        if self.schema_version!='confidenceguard.feature_enrichment_spec/1.0':raise EvaluationError('Unsupported feature enrichment.')
