"""CG4 data-only declarations. D/S/H never replace CG2 F/S/C/E."""
from dataclasses import dataclass, field
import math
from .contracts import Contract, EvaluationSpec, EvaluationError, choice, name, nested, sequence, positive
from .feature_contracts import FeatureViewSpec, DiscoveryRepresentationSpec, names

INVESTIGATION_METHOD='failure_investigation_v1'
INVESTIGATION_RESULT='confidenceguard.investigation_result/1.0'
CONFIRMATION_RESULT='confidenceguard.confirmation_assessment/1.0'

# Public synthetic qualification evidence, never an inference about caller data.
# Keep the failed original method visible while its geometric fallback qualifies.
LANDMARK_PROMOTION_EVIDENCE={
    'status':'promotion_rejected_logical_futility','promoted':False,
    'proposal_version':'self_excluded_landmark_graph_v2',
    'evidence_sha256':'33905a883f5a8122a75e02e2dfe03284d019d1ea2b9d389b66fa6d09239b159c',
    'profile':'40000 IID synthetic curved-region opportunities; default 512 landmarks; matched geometric fallback.',
    'completed_pairs':21,'planned_pairs_per_family':40,
    'maximum_possible_median_IoU_gain':-.16329466018252453,'required_median_IoU_gain':.10,
    'complete_two_family_comparison':False,'controlled_resource_qualification':False,
    'scope':'Predeclared negative stopping criterion rejects promotion on this profile. It does not establish universal inferiority or qualify every fallback/representation/objective.'}


@dataclass(frozen=True)
class FailureObjectiveSpec(Contract):
    id: str
    metric: str
    run: str
    comparator: str = 'complement'
    direction: str = 'auto'
    units: str | None = None
    target: str | None = None
    interval: str | None = None
    reference_run: str | None = None
    reference_period: str | None = None
    current_period: str | None = None
    practical_threshold: float | None = None
    ceiling: float | None = None
    nominal: float | None = None
    material_error: float | None = None
    bounds: tuple = ()
    training_clip: float = 30.0
    metric_identity: dict = field(default_factory=dict)

    def __post_init__(self):
        for attr in ('id','metric','run'): name(getattr(self,attr))
        if self.units is not None:name(self.units)
        choice(self.comparator,{'complement','overall','ceiling','paired','reference_period'},'failure comparator')
        if self.direction=='auto':
            direction=('lower' if self.metric in {'accuracy','precision','recall','specificity','f1','roc_auc','average_precision','r2','interval_coverage'} or self.metric.startswith(('set_coverage@','interval_coverage@')) else
                       'absolute' if self.metric in {'bias','calibration_residual'} else 'higher')
            object.__setattr__(self,'direction',direction)
        choice(self.direction,{'higher','lower','absolute','nominal_shortfall'},'adverse direction')
        for attr in ('target','interval','reference_run','reference_period','current_period'):
            if getattr(self,attr) is not None: name(getattr(self,attr))
        for attr in ('practical_threshold','ceiling','nominal','material_error'):
            value=getattr(self,attr)
            if value is not None and (isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value)):
                raise EvaluationError(f'{attr} must be finite.')
        if self.practical_threshold is not None and self.practical_threshold<0: raise EvaluationError('Practical threshold must be nonnegative.')
        if self.comparator=='paired' and not self.reference_run: raise EvaluationError('Paired objectives require a reference run.')
        if self.comparator=='reference_period' and (not self.reference_period or not self.current_period or self.reference_period==self.current_period):raise EvaluationError('Distinct reference/current periods required.')
        if self.comparator=='ceiling' and self.ceiling is None: raise EvaluationError('A ceiling must be declared.')
        if self.direction=='nominal_shortfall' and (self.nominal is None or not 0<self.nominal<1): raise EvaluationError('Nominal shortfall requires nominal coverage.')
        if self.bounds and (len(self.bounds)!=2 or not all(isinstance(x,(int,float)) and math.isfinite(x) for x in self.bounds) or self.bounds[0]>=self.bounds[1]):
            raise EvaluationError('Bounds require an increasing finite pair.')
        object.__setattr__(self,'bounds',tuple(self.bounds))
        positive(self.training_clip,'training clip',False)
        if not isinstance(self.metric_identity,dict): raise EvaluationError('metric_identity must be an object.')


def resolve_objective_units(objective,task):
    """Bind metric units without converting values or inventing physical units."""
    from dataclasses import replace
    metric=objective.metric;physical={'mae','rmse','bias','median_absolute_error','p90_absolute_error','p95_absolute_error',
        'interval_width','central_interval_score','wis','empirical_crps'}
    target=task.units or 'target_units'
    expected='nats' if metric=='log_loss' else target+'^2' if metric=='mse' else target if metric in physical or metric.startswith(('pinball@','central_interval_score@','interval_efficiency@')) else 'count' if metric.startswith('set_efficiency@') else 'dimensionless' if metric=='r2' else 'fraction'
    supplied=objective.units
    compatible=supplied==expected or expected=='fraction' and supplied in {'probability','dimensionless'} or expected=='dimensionless' and supplied=='fraction'
    # An unknown original physical unit can be explicitly declared by the caller;
    # this declaration is not a verified physical-unit conversion.
    if supplied is not None and not compatible and (task.units is not None or expected not in {'target_units','target_units^2'}):
        raise EvaluationError('Failure-objective units differ from the authoritative metric/task units.','objective_units')
    return replace(objective,units=expected if supplied is None or compatible else supplied)


@dataclass(frozen=True)
class DiscoveryRoles(Contract):
    namespace: str
    unit: str = 'entity'
    column: str | None = None
    values: dict = field(default_factory=lambda:{'D':'D','S':'S','H':'H'})
    partitions: dict = field(default_factory=dict)
    proportions: tuple = (.5,.25,.25)
    seed: int = 0

    def __post_init__(self):
        name(self.namespace); choice(self.unit,{'entity','independent_rows'},'CG4 sampling unit')
        if self.column is not None: name(self.column)
        if not isinstance(self.values,dict) or set(self.values.values())-{'D','S','H'}: raise EvaluationError('Role values must map to D/S/H.')
        if not isinstance(self.partitions,dict) or set(self.partitions)-{'D','S','H'}: raise EvaluationError('Invalid role partitions.')
        if self.column and self.partitions: raise EvaluationError('Choose a role column or partitions.')
        if len(self.proportions)!=3 or any(isinstance(x,bool) or not isinstance(x,(float,int)) or not math.isfinite(x) or x<=0 for x in self.proportions) or abs(sum(self.proportions)-1)>1e-12:
            raise EvaluationError('D/S/H proportions must be positive and sum to one.')
        object.__setattr__(self,'proportions',tuple(self.proportions))
        if isinstance(self.seed,bool) or not isinstance(self.seed,int) or self.seed<0: raise EvaluationError('Nonnegative integer seed required.')


@dataclass(frozen=True)
class InvestigationLimits(Contract):
    max_nodes: int = 1000000
    max_depth: int = 6
    numeric_bins: int = 16
    categorical_values: int = 32
    minimum_discovery_support: int = 30
    candidates_per_strategy: int = 256
    shortlist: int = 10
    max_hypotheses: int = 32
    diagnostic_rows: int = 100000
    diagnostic_fits: int = 512
    geometric_rows: int = 20000
    landmarks: int = 512
    neighbors: int = 16
    pca_dimensions: int = 64
    max_vector_dimensions: int = 16384
    max_distance_operations: int = 2000000000
    inference_work_units: int = 10000000000
    max_artifact_bytes: int = 64*1024**2
    examples_per_candidate: int = 5
    stability_replicates: int = 5
    max_encoder_windows: int = 100000
    max_encoder_tokens: int = 20000000
    max_encoder_pixels: int = 4000000000

    def __post_init__(self):
        from dataclasses import fields
        for f in fields(self): positive(getattr(self,f.name),f.name)
        if self.shortlist>self.max_hypotheses or self.max_hypotheses>32: raise EvaluationError('Confirmation shortlist exceeds the 32-hypothesis contract.')
        if self.max_depth>16 or self.landmarks>16384: raise EvaluationError('Discovery declaration exceeds artifact bounds.')


@dataclass(frozen=True)
class InvestigationSpec(Contract):
    objectives: tuple
    roles: DiscoveryRoles
    evaluation: EvaluationSpec | None = None
    history: dict | None = None
    features: tuple = ()
    representations: tuple = ()
    strategies: tuple = ('structured','catboost','geometric')
    limits: InvestigationLimits = field(default_factory=InvestigationLimits)
    feature_time_view: str = 'available_at_decision'
    as_of: str | None = None
    name: str = 'Failure investigation'
    schema_version: str = 'confidenceguard.investigation_spec/1.0'

    def __post_init__(self):
        name(self.name); sequence(self,'objectives',FailureObjectiveSpec); nested(self,'roles',DiscoveryRoles)
        nested(self,'evaluation',EvaluationSpec,True); nested(self,'limits',InvestigationLimits)
        if self.evaluation is not None:object.__setattr__(self,'objectives',tuple(resolve_objective_units(o,self.evaluation.task) if o.units is None else o for o in self.objectives))
        sequence(self,'features',FeatureViewSpec); sequence(self,'representations',DiscoveryRepresentationSpec)
        if (self.evaluation is None)==(self.history is None): raise EvaluationError('Choose supplied evaluation or retained history.')
        if self.history is not None:
            if not isinstance(self.history,dict) or set(self.history)!={'workspace_path','selection'}:raise EvaluationError('Historical selection requires workspace_path and selection.')
            name(self.history['workspace_path'])
            from .history_contracts import LongitudinalSpec
            LongitudinalSpec.from_dict(self.history['selection'])
        if not self.objectives or len({x.id for x in self.objectives})!=len(self.objectives): raise EvaluationError('Unique failure objectives required.')
        if len(self.objectives)>32 or len(self.features)>128 or len(self.representations)>16 or sum(len(v.fields) for v in self.features)>4096:raise EvaluationError('Investigation declarations exceed bounded admission.','investigation_declaration_limit')
        for items in (self.features,self.representations):
            if len({x.id for x in items})!=len(items): raise EvaluationError('Duplicate evidence view identity.')
        if not isinstance(self.strategies,(tuple,list)) or not self.strategies or set(self.strategies)-{'structured','catboost','geometric','landmark'} or len(set(self.strategies))!=len(self.strategies):
            raise EvaluationError('Unknown or duplicate discovery strategy.')
        object.__setattr__(self,'strategies',tuple(self.strategies))
        choice(self.feature_time_view,{'available_at_decision','retrospective'},'feature time view')
        if self.as_of is not None:
            from .history_contracts import instant
            instant(self.as_of)
        if self.schema_version!='confidenceguard.investigation_spec/1.0': raise EvaluationError('Unsupported investigation specification.')

    @classmethod
    def from_dict(cls,value,*,base_directory=None):
        import copy
        from pathlib import Path
        value=copy.deepcopy(value)
        if base_directory is not None:
            def path(v):return str((Path(base_directory)/v).absolute()) if not Path(v).is_absolute() else v
            if value.get('evaluation') is not None:value['evaluation']=EvaluationSpec.from_dict(value['evaluation'],base_directory=base_directory)
            if value.get('history') is not None:value['history']['workspace_path']=path(value['history']['workspace_path'])
            for r in value.get('representations',[]):
                for key in ('matrix_path','model_directory'):
                    if r.get(key):r[key]=path(r[key])
                if r.get('keys_source'):r['keys_source']['path']=path(r['keys_source']['path'])
        return super().from_dict(value)


@dataclass(frozen=True)
class ConfirmationLook(Contract):
    id: str
    as_of: str
    alpha: float

    def __post_init__(self):
        name(self.id)
        from .history_contracts import instant
        instant(self.as_of)
        if isinstance(self.alpha,bool) or not isinstance(self.alpha,(int,float)) or not 0<self.alpha<1:raise EvaluationError('A scheduled look requires an explicit error allocation.')


@dataclass(frozen=True)
class ConfirmationSpec(Contract):
    confidence: float = .95
    method: str = 'finite'
    sampling: str = 'independent_rows'
    upstream_independence: str = 'unknown'
    external_exposure: str = 'unknown'
    exposure_history_token: str | None = None
    declaration_author: str | None = None
    declaration_reason: str | None = None
    known_common_shocks: bool = False
    membership_scope: str = 'full_population'
    minimum_membership_coverage: float = 1.0
    outcome_scope: str = 'observed_labels'
    replicates: int = 20000
    replicate_policy: str = 'nominal_admission'
    max_replicates: int = 200000
    minimum_tail: int = 20
    minimum_units: int = 30
    seed: int = 0
    study_id: str | None = None
    study_alpha: float = .05
    batch_alpha: float = .05
    request_id: str | None = None
    restatement_schedule: tuple = ()
    schema_version: str = 'confidenceguard.confirmation_spec/1.0'

    def __post_init__(self):
        sequence(self,'restatement_schedule',ConfirmationLook)
        if self.restatement_schedule:
            from decimal import Decimal
            if not self.study_id or len(self.restatement_schedule)>32 or len({s.id for s in self.restatement_schedule})!=len(self.restatement_schedule):raise EvaluationError('Predeclared looks require a study identity and up to 32 unique look identities.')
            if Decimal(str(self.batch_alpha))+sum((Decimal(str(s.alpha)) for s in self.restatement_schedule),Decimal(0))>Decimal(str(self.study_alpha)):raise EvaluationError('Initial and scheduled look allocations exceed the frozen study error.')
        if isinstance(self.confidence,bool) or not 0<self.confidence<1: raise EvaluationError('Confidence must be between zero and one.')
        choice(self.method,{'finite','bca','percentile'},'CG4 inference method')
        choice(self.sampling,{'independent_rows','independent_entities','independent_entity_arms','descriptive','unsupported_temporal'},'confirmation sampling')
        if self.sampling=='independent_entity_arms' and self.method!='finite':raise EvaluationError('One potential observation per entity in each comparison arm requires the finite method.','entity_arm_method')
        choice(self.upstream_independence,{'unknown','declared_independent','known_overlap'},'upstream independence')
        choice(self.external_exposure,{'unknown','declared_unexposed','known_exposed'},'external exposure')
        choice(self.membership_scope,{'full_population','supported_population'},'membership scope')
        choice(self.outcome_scope,{'observed_labels','complete_population'},'outcome scope')
        choice(self.replicate_policy,{'fixed','nominal_admission'},'replication policy')
        if not 0<=self.minimum_membership_coverage<=1: raise EvaluationError('Invalid membership coverage floor.')
        for attr in ('replicates','max_replicates','minimum_tail','minimum_units'): positive(getattr(self,attr),attr)
        if self.replicates>self.max_replicates: raise EvaluationError('Requested replication exceeds its maximum.')
        if not 0<self.batch_alpha<=self.study_alpha<=1-self.confidence+1e-12: raise EvaluationError('Study/batch error allocation exceeds declared confidence.')
        if not isinstance(self.known_common_shocks,bool): raise EvaluationError('Common-shock declaration must be boolean.')
        if isinstance(self.seed,bool) or not isinstance(self.seed,int) or self.seed<0: raise EvaluationError('Invalid confirmation seed.')
        for attr in ('declaration_author','declaration_reason','study_id','request_id'):
            if getattr(self,attr) is not None: name(getattr(self,attr))
        if (self.upstream_independence=='declared_independent' or self.external_exposure=='declared_unexposed') and not (self.declaration_author and self.declaration_reason):
            raise EvaluationError('Independence declarations require author and scoped reason.')
        if self.exposure_history_token is not None:
            import re
            if not isinstance(self.exposure_history_token,str) or not re.fullmatch('[0-9a-f]{32}',self.exposure_history_token) or self.external_exposure!='declared_unexposed' or not (self.declaration_author and self.declaration_reason):raise EvaluationError('A current history-gap declaration requires its protected epoch token, author and scoped reason.')
        if self.schema_version!='confidenceguard.confirmation_spec/1.0': raise EvaluationError('Unsupported confirmation specification.')


def observation_policy(spec):
    """Frozen interpretation, separate from the actual H source/snapshot identity.

    Future H files and immutable outcome snapshots can be supplied later. They
    cannot change which statuses are evaluable, clock units, historical maturity,
    authority or context semantics. A retrospective feature cutoff defines the
    gate's input interpretation, rather than an outcome-only snapshot revision.
    """
    cutoff=None
    if spec.feature_time_view=='retrospective':
        cutoff=spec.as_of
        if spec.history:
            selection=spec.history['selection'];cutoff=cutoff or selection.get('prediction_as_of') or selection.get('as_of')
        if cutoff is not None:
            from .history_contracts import instant
            cutoff=str(instant(cutoff))
    if spec.evaluation is not None:
        outcome=spec.evaluation.effective_outcomes
        binding={k:v for k,v in outcome.to_dict().items() if k not in {'source','snapshot_name'}} if outcome else None
        return {'version':'cg4_observation_policy_v1','kind':'supplied','binding':binding,
                'retrospective_feature_cutoff_ns':cutoff}
    from .history_contracts import LongitudinalSpec
    selection=LongitudinalSpec.from_dict(spec.history['selection']).to_dict()
    fields=('namespace','variants','authority','maturity','followup_ns','roles','slots','attempts',
            'cohorts','features','context_view','outcome_only','calibration_edges','material_thresholds','event_costs')
    return {'version':'cg4_observation_policy_v1','kind':'retained',
            'binding':{key:selection[key] for key in fields},'retrospective_feature_cutoff_ns':cutoff}


def confirmation_family_digest(hypotheses,protocol,version='confidenceguard.frozen_hypothesis_set/1.1'):
    from .contracts import digest
    definition={'hypotheses':[h['id'] for h in hypotheses],'confidence':protocol.confidence,'study_id':protocol.study_id,
                'study_alpha':protocol.study_alpha,'batch_alpha':protocol.batch_alpha,'method':protocol.method,
                **({'restatement_schedule':[s.to_dict() for s in protocol.restatement_schedule]} if protocol.restatement_schedule else {})}
    if version=='confidenceguard.frozen_hypothesis_set/1.1':
        definition.update(identity_version='1.1',frozen_confirmation_protocol={k:v for k,v in protocol.to_dict().items() if k!='request_id' and not (k=='exposure_history_token' and v is None)})
    return digest(definition)


@dataclass(frozen=True)
class FrozenHypothesisSet:
    data: dict

    def __post_init__(self):
        import copy,json
        from .contracts import digest
        from .investigation_membership import validate
        packet=self.data
        required={'schema_version','origin_analysis_id','origin_analysis_digest','investigation_spec','input_fingerprint','files',
                  'hypotheses','artifacts','models','confirmation_spec','evaluation_config','D_S_units','D_S_events','family_digest','content_digest'}
        if not isinstance(packet,dict) or set(packet)!=required or packet['schema_version'] not in {'confidenceguard.frozen_hypothesis_set/1.0','confidenceguard.frozen_hypothesis_set/1.1'}:raise EvaluationError('Invalid frozen hypothesis set.')
        if packet['content_digest']!=digest({k:v for k,v in packet.items() if k!='content_digest'}):raise EvaluationError('Frozen hypothesis set changed.','hypothesis_changed')
        if len(json.dumps(packet,ensure_ascii=True))>64*1024**2:raise EvaluationError('Frozen family exceeds artifact admission.','hypothesis_limit')
        spec=InvestigationSpec.from_dict(packet['investigation_spec']);protocol=ConfirmationSpec.from_dict(packet['confirmation_spec'])
        from .contracts import EvaluationConfig
        EvaluationConfig.from_dict(packet['evaluation_config'])
        hypotheses=packet['hypotheses']
        if not isinstance(hypotheses,list) or not 1<=len(hypotheses)<=32 or len({h['id'] for h in hypotheses})!=len(hypotheses):raise EvaluationError('Invalid fixed hypothesis family.')
        for hypothesis in hypotheses:
            objective=FailureObjectiveSpec.from_dict(hypothesis['objective'])
            if hypothesis.get('definition_version')=='frozen_failure_hypothesis_v2' and (
                    hypothesis.get('feature_time_view')!=spec.feature_time_view or
                    hypothesis.get('population_policy',{}).get('observation_policy')!=observation_policy(spec)):
                raise EvaluationError('Frozen hypothesis and observation interpretation disagree.','hypothesis_changed')
            if objective.practical_threshold is None or objective.units is None:raise EvaluationError('Frozen practical threshold and resolved units required.')
            artifact=packet['artifacts'].get(hypothesis['membership_artifact'])
            validate(artifact,models=packet['models'])
            fields=set(artifact['features']);representations={r.id:r for r in spec.representations}
            definitions={view.id+'.'+field.id:field for view in spec.features for field in view.fields}
            if not fields<=definitions.keys():raise EvaluationError('Frozen gate references undeclared typed features.','membership_feature_contract')
            parameters=artifact['parameters']
            descriptions=(parameters.get('columns',[]) if artifact['kind']=='catboost' else
                [clause for group in parameters.get('any_of',[parameters.get('clauses',[])]) for clause in group] if artifact['kind']=='structured' else [])
            if any(definitions[d.get('field',d.get('id'))].kind!=d['kind'] for d in descriptions):raise EvaluationError('Frozen gate and declared feature kinds differ.','membership_feature_contract')
            if artifact['representation'] is not None and artifact['representation'] not in representations:raise EvaluationError('Frozen gate references an undeclared representation.','membership_feature_contract')
            representation=representations.get(artifact.get('representation'))
            if representation and representation.field:fields.add(representation.field)
            declared={v.id+'.'+f.id for v in spec.features for f in v.fields if f.outcome_derived}
            if spec.evaluation:
                from .features import outcome_bound_fields
                declared|=outcome_bound_fields(spec.evaluation,spec.features,packet['files'])
            if fields&declared:raise EvaluationError('Outcome-bound membership cannot be imported as an independent hypothesis.','outcome_derived_membership')
            if hypothesis['id']!=digest({k:v for k,v in hypothesis.items() if k!='id'}):raise EvaluationError('Hypothesis identity differs.','hypothesis_changed')
        family=confirmation_family_digest(hypotheses,protocol,packet['schema_version'])
        if family!=packet['family_digest']:raise EvaluationError('Frozen family identity differs.','hypothesis_changed')
        object.__setattr__(self,'data',copy.deepcopy(packet))

    def to_dict(self):
        import copy
        return copy.deepcopy(self.data)

    @property
    def evidence_family_digest(self):
        # Legacy bytes remain readable. Application still binds the complete
        # numerical protocol; changing B or the seed cannot reset H use.
        return confirmation_family_digest(self.data['hypotheses'],ConfirmationSpec.from_dict(self.data['confirmation_spec']))

    @classmethod
    def from_dict(cls,value):return cls(value)

    @property
    def family_digest(self):return self.data['family_digest']
