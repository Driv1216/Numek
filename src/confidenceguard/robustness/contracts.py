"""Registered robustness experiments, threat models, and frozen claim families."""
from dataclasses import dataclass,field
import copy

from ..contracts import Contract,EvaluationError,nested,sequence,choice,name,positive,digest
from ..execution.contracts import ExecutionSpec,bounded,shape,finite,strings

OPERATIONS={
    'identity':set(),'missing':{'rate','condition','mode'},'noise':{'scale','mode'},'round':{'step'},'censor':{'lower','upper'},
    'category':{'transitions','rate'},'set':{'values'},'finite_difference':{'step','direction'},'permutation':{'grouped'},
    'text_whitespace':{'mode'},'text_unicode':{'form'},'text_edit':{'mode','edits'},'text_truncate':{'characters'},'text_span':{'spans'},
    'image_noise':{'scale'},'image_blur':{'radius'},'image_brightness':{'factor'},'image_contrast':{'factor'},
    'image_compression':{'quality'},'image_occlusion':{'box','value'},'image_geometry':{'mode','angle'},
}


def predicate(value):
    shape(value,{'field','op','value'},{'field','op','value'})
    name(value['field']);choice(value['op'],{'eq','ne','lt','le','gt','ge','in','missing'},'scenario predicate')
    if value['op']=='in' and (not isinstance(value['value'],list) or not value['value']):raise EvaluationError('Membership predicates need a nonempty finite array.')
    if value['op']=='missing' and type(value['value']) is not bool:raise EvaluationError('Missingness predicates require an explicit Boolean.')
    bounded(value)


@dataclass(frozen=True)
class TransformationSpec(Contract):
    id: str
    operation: str
    fields: tuple = ()
    parameters: dict = field(default_factory=dict)
    constraints: dict = field(default_factory=dict)
    relations: tuple = ()
    stage: str = 'raw'
    realism: str = 'artificial'
    schema_version: str = 'confidenceguard.transformation_spec/1.0'

    def __post_init__(self):
        name(self.id);choice(self.operation,set(OPERATIONS),'transformation')
        object.__setattr__(self,'fields',strings(self.fields,'transformation fields'))
        shape(self.parameters,OPERATIONS[self.operation]);object.__setattr__(self,'parameters',bounded(self.parameters))
        choice(self.stage,{'raw','canonical_image','tensor'},'transformation stage');choice(self.realism,{'artificial','declared_realistic'},'scenario realism')
        if self.operation!='identity' and not self.fields:raise EvaluationError('Transformation fields are required.')
        if 'condition' in self.parameters:predicate(self.parameters['condition'])
        if self.operation=='missing':choice(self.parameters.get('mode','independent'),{'independent','block'},'missingness pattern')
        if self.operation=='permutation' and self.parameters.get('grouped',True) is not True:raise EvaluationError('Use separate frozen transformation groups for independent permutations.')
        if 'rate' in self.parameters and not 0<=self.parameters['rate']<=1:raise EvaluationError('Corruption rate must be inside [0,1].')
        for key in ('scale','radius'):
            if key in self.parameters:finite(self.parameters[key],key,minimum=0)
        for key in ('factor','step'):
            if key in self.parameters:finite(self.parameters[key],key,minimum=1e-15)
        if self.operation=='text_edit':
            choice(self.parameters.get('mode','delete'),{'delete','transpose','replace'},'text edit')
            positive(self.parameters.get('edits',1),'edit budget')
        if self.operation=='text_truncate':positive(self.parameters.get('characters',256),'text truncation')
        for f,c in self.constraints.items():
            name(f);shape(c,{'mutable','lower','upper','integer','step','categories','repair'})
            for b in ('lower','upper'):
                if b in c:finite(c[b],b)
            if 'lower' in c and 'upper' in c and c['lower']>c['upper']:raise EvaluationError('Inconsistent feature bounds.')
            for b in ('mutable','integer','repair'):
                if b in c and type(c[b]) is not bool:raise EvaluationError('Boolean constraint settings required.')
            if 'step' in c:finite(c['step'],'constraint step',minimum=1e-15)
        for r in self.relations:
            shape(r,{'coefficients','operator','bound','tolerance'},{'coefficients','operator','bound'})
            choice(r['operator'],{'le','ge','eq'},'cross-field relation')
            finite(r['bound']);finite(r.get('tolerance',0.),minimum=0)
            for f,v in r['coefficients'].items():name(f);finite(v)
        object.__setattr__(self,'constraints',bounded(self.constraints));object.__setattr__(self,'relations',tuple(bounded(self.relations)))
        if self.schema_version!='confidenceguard.transformation_spec/1.0':raise EvaluationError('Unsupported transformation schema.')


@dataclass(frozen=True)
class AttackSpec(Contract):
    algorithm: str
    fields: tuple
    objective: str = 'output_change'
    access: str = 'black_box'
    norm: str = 'linf'
    epsilon: float = .1
    steps: int = 40
    restarts: int = 5
    queries_per_root: int = 1000
    step_size: float = .01
    threshold: float = 0.
    target_class: str | None = None
    domains: dict = field(default_factory=dict)
    constraints: dict = field(default_factory=dict)
    stage: str = 'raw'
    relations: tuple = ()

    def __post_init__(self):
        choice(self.algorithm,{'enumerate','random','coordinate','text','fgsm','pgd'},'attack algorithm')
        choice(self.stage,{'raw','canonical_image','tensor'},'attack stage')
        choice(self.objective,{'output_change','misclassification','targeted','loss_increase'},'attack objective')
        choice(self.access,{'black_box','white_box'},'attack access');choice(self.norm,{'linf','l2','discrete'},'attack norm')
        object.__setattr__(self,'fields',strings(self.fields,'attack fields',True))
        for k in ('steps','restarts','queries_per_root'):positive(getattr(self,k),k)
        for k in ('epsilon','step_size','threshold'):finite(getattr(self,k),k,minimum=0)
        if self.algorithm in {'fgsm','pgd'} and self.access!='white_box':raise EvaluationError('Gradient attacks require white-box access.')
        if self.algorithm in {'fgsm','pgd'} and self.norm not in {'linf','l2'}:raise EvaluationError('Gradient attacks require a registered continuous norm.')
        if self.objective=='targeted' and self.target_class is None:raise EvaluationError('Targeted attacks need a frozen target class.')
        if self.threshold and self.objective not in {'output_change','loss_increase'}:raise EvaluationError('This attack objective has no numerical success threshold.')
        if self.algorithm=='enumerate' and set(self.domains)!=set(self.fields):raise EvaluationError('Enumeration requires a complete finite domain.')
        if set(self.domains)-set(self.fields) or any(not isinstance(v,list) or not v for v in self.domains.values()):raise EvaluationError('Attack domains must be nonempty finite arrays for declared mutable fields.')
        TransformationSpec('attack_constraints','identity',constraints=self.constraints,relations=self.relations)
        object.__setattr__(self,'relations',tuple(bounded(self.relations)))
        object.__setattr__(self,'domains',bounded(self.domains));object.__setattr__(self,'constraints',bounded(self.constraints))


@dataclass(frozen=True)
class ScenarioSpec(Contract):
    id: str
    transformations: tuple = ()
    replicates: int = 1
    outcome_relation: str = 'unknown'
    outcome_reason: str | None = None
    filter: dict | None = None
    mixture_field: str | None = None
    mixture_weights: dict = field(default_factory=dict)
    metamorphic: dict | None = None
    attack: AttackSpec | None = None
    variant_outcomes: dict = field(default_factory=dict)
    outcome_rule: dict = field(default_factory=dict)

    def __post_init__(self):
        name(self.id);sequence(self,'transformations',TransformationSpec);nested(self,'attack',AttackSpec,True)
        positive(self.replicates,'scenario replicates')
        choice(self.outcome_relation,{'unknown','label_preserving','authoritative_variant','reference_label_diagnostic','registered_transform'},'outcome relation')
        if self.outcome_relation!='unknown' and not self.outcome_reason:raise EvaluationError('Outcome relations require explicit provenance/reason.')
        if self.filter is not None:predicate(self.filter)
        if bool(self.mixture_field)!=bool(self.mixture_weights):raise EvaluationError('Mixtures require a field and frozen masses.')
        if self.mixture_weights:
            for v in self.mixture_weights.values():finite(v,'mixture mass',minimum=0)
            if abs(sum(self.mixture_weights.values())-1)>1e-12:raise EvaluationError('Mixture masses must sum to one.')
        if self.metamorphic:
            shape(self.metamorphic,{'relation','channel','atol','rtol','direction','permutation','factor','offset'},{'relation','channel'})
            choice(self.metamorphic['relation'],{'invariant','monotone','equivariant'},'metamorphic relation')
            for k in ('atol','rtol'):finite(self.metamorphic.get(k,0.),k,minimum=0)
        if self.variant_outcomes and self.outcome_relation!='authoritative_variant':raise EvaluationError('Variant labels require authoritative-variant standing.')
        object.__setattr__(self,'variant_outcomes',bounded(self.variant_outcomes))
        if self.outcome_relation=='registered_transform':
            shape(self.outcome_rule,{'operation','factor','offset','classes'},{'operation'})
            choice(self.outcome_rule['operation'],{'affine_regression_v1','class_map_v1'},'registered outcome operation')
            if self.outcome_rule['operation']=='affine_regression_v1':
                if 'classes' in self.outcome_rule:raise EvaluationError('Affine outcome rules cannot include class mappings.')
                finite(self.outcome_rule.get('factor',1.));finite(self.outcome_rule.get('offset',0.))
            elif set(self.outcome_rule)!={'operation','classes'} or not isinstance(self.outcome_rule['classes'],dict):raise EvaluationError('Class outcome rules require an explicit frozen map.')
        elif self.outcome_rule:raise EvaluationError('An outcome rule requires registered-transform standing.')
        object.__setattr__(self,'outcome_rule',bounded(self.outcome_rule))


@dataclass(frozen=True)
class RobustnessSpec(Contract):
    execution: ExecutionSpec
    scenarios: tuple
    comparisons: tuple = ()
    seed: int = 0
    role: str | None = None
    regions: tuple = ()
    sensitivity: dict = field(default_factory=dict)
    schema_version: str = 'confidenceguard.robustness_spec/1.0'

    def __post_init__(self):
        nested(self,'execution',ExecutionSpec);sequence(self,'scenarios',ScenarioSpec)
        if not self.scenarios or len({s.id for s in self.scenarios})!=len(self.scenarios) or any(s.id=='original' for s in self.scenarios):raise EvaluationError('Unique named scenarios are required.')
        if type(self.seed) is not int or self.seed<0:raise EvaluationError('Invalid experiment seed.')
        if self.role is not None:choice(self.role,{'F','S','C','E'},'experiment role')
        fields={f.column for p in self.execution.predictors for f in p.inputs}|{f.column for f in self.execution.context_fields}
        prohibited=set(self.execution.key_columns)|set(self.execution.entity_columns)|set(self.execution.batch_columns)
        prohibited.update(f.column for f in self.execution.context_fields if f.outcome_derived or f.role=='retrospective')
        if self.execution.outcomes:prohibited.add(self.execution.outcomes.column)
        if self.execution.roles and self.execution.roles.column:prohibited.add(self.execution.roles.column)
        for s in self.scenarios:
            if s.outcome_rule:
                op=s.outcome_rule['operation']
                if (op=='affine_regression_v1')!=(self.execution.task.kind=='regression'):raise EvaluationError('Outcome rule task differs.')
                if op=='class_map_v1' and (set(s.outcome_rule['classes'])!=set(self.execution.task.classes) or set(s.outcome_rule['classes'].values())-set(self.execution.task.classes)):raise EvaluationError('Outcome class mapping must cover the complete admitted class order.')
            if s.filter and s.filter['field'] not in fields:raise EvaluationError('Scenario filters require declared context/input fields.')
            if s.filter and s.filter['field'] in prohibited:raise EvaluationError('Scenario filters cannot use identities, roles or known retrospective/outcome fields.')
            if s.mixture_field and s.mixture_field not in fields:raise EvaluationError('Mixtures require a declared frozen cohort field.')
            for t in s.transformations:
                if set(t.fields)-fields or set(t.fields)&prohibited:raise EvaluationError('A transformation cannot change identity, roles, outcomes or undeclared inputs.','transformation_field')
                if t.parameters.get('condition',{}).get('field') in prohibited:raise EvaluationError('Outcome/identity-derived missingness is not an admitted independent scenario.')
                if t.stage=='tensor' and not all(p.preprocessing.get('kind')=='tensor' for p in self.execution.predictors if set(t.fields)&{f.column for f in p.inputs}):raise EvaluationError('Tensor transformations need explicit prepared tensor inputs.')
                if t.stage!='tensor' and any(p.preprocessing.get('kind')=='tensor' and set(t.fields)&{f.column for f in p.inputs} for p in self.execution.predictors):raise EvaluationError('Prepared-vector transformations must explicitly name the tensor stage.')
                if t.stage=='canonical_image' and not t.operation.startswith('image_'):raise EvaluationError('Canonical image stage requires an image operation.')
            if s.attack and (set(s.attack.fields)-fields or set(s.attack.fields)&prohibited):raise EvaluationError('Invalid attack fields.')
        for edge in self.comparisons:
            shape(edge,{'left','right'},{'left','right'})
            if not {edge['left'],edge['right']}<=self.execution.predictor_ids or edge['left']==edge['right']:raise EvaluationError('Invalid predictor comparison.')
        object.__setattr__(self,'comparisons',tuple(bounded(self.comparisons)))
        object.__setattr__(self,'regions',tuple(bounded(self.regions)))
        from .regions import validate_region
        for region in self.regions:validate_region(region,fields)
        from .sensitivity import validate as validate_sensitivity
        validate_sensitivity(self.sensitivity,self.execution);object.__setattr__(self,'sensitivity',bounded(self.sensitivity))
        if self.schema_version!='confidenceguard.robustness_spec/1.0':raise EvaluationError('Unsupported robustness schema.')


@dataclass(frozen=True)
class RobustnessClaim(Contract):
    id: str
    predictor: str
    scenario: str
    metric: str
    operator: str
    threshold: float
    bounds: tuple | None = None
    minimum_support: int = 30

    def __post_init__(self):
        for f in ('id','predictor','scenario'):name(getattr(self,f))
        import re
        if not re.fullmatch(r'(coverage_delta|efficiency_delta|uncertainty_availability_delta)@(0?\.\d+)',self.metric):
            choice(self.metric,{'loss_delta','confidence_delta','flip_rate','output_failure_rate','metamorphic_violation','attack_success','brier_delta','log_loss_delta','point_delta','probability_max_change','confidently_wrong_transition'},'robustness claim')
        elif not 0<float(self.metric.split('@')[1])<1:raise EvaluationError('Invalid uncertainty claim coverage.')
        choice(self.operator,{'le','ge'},'claim operator');finite(self.threshold);positive(self.minimum_support,'claim support')
        if self.bounds is not None:
            if len(self.bounds)!=2:raise EvaluationError('Two true contribution bounds required.')
            for v in self.bounds:finite(v)
            if self.bounds[0]>self.bounds[1]:raise EvaluationError('Contribution bounds must be ordered.')
            object.__setattr__(self,'bounds',tuple(self.bounds))


@dataclass(frozen=True)
class FrozenRobustnessProtocol(Contract):
    study: RobustnessSpec
    claims: tuple
    development_events: tuple
    development_units: tuple
    confidence: float = .95
    sampling: str = 'independent_roots'
    max_cluster_size: int | None = None
    upstream_independence: str = 'unknown'
    external_exposure: str = 'unknown'
    batch_field: str | None = None
    runtime_profiles: dict = field(default_factory=dict)
    content_digest: str = ''
    schema_version: str = 'confidenceguard.frozen_robustness_protocol/1.0'

    def __post_init__(self):
        nested(self,'study',RobustnessSpec);sequence(self,'claims',RobustnessClaim)
        if not self.claims or len({c.id for c in self.claims})!=len(self.claims):raise EvaluationError('A nonempty unique claim family is required.')
        choice(self.sampling,{'independent_roots','independent_entities','independent_batches'},'robustness sampling')
        if self.batch_field is not None:name(self.batch_field)
        if self.sampling=='independent_batches':
            fields={f.column for f in self.study.execution.context_fields}
            if self.batch_field not in fields:raise EvaluationError('Independent-batch inference requires a declared batch context field.')
        for c in self.claims:
            if c.predictor not in self.study.execution.predictor_ids or c.scenario not in {s.id for s in self.study.scenarios}:raise EvaluationError('Claim binding is absent.')
        if not 0<self.confidence<1:raise EvaluationError('Invalid family confidence.')
        if self.max_cluster_size is not None:positive(self.max_cluster_size,'true maximum cluster size')
        choice(self.upstream_independence,{'unknown','declared_independent'},'upstream independence')
        choice(self.external_exposure,{'unknown','declared_unexposed'},'external exposure')
        object.__setattr__(self,'runtime_profiles',bounded(self.runtime_profiles))
        if self.schema_version!='confidenceguard.frozen_robustness_protocol/1.0':raise EvaluationError('Unsupported frozen robustness protocol.')
        value=self.to_dict();value.pop('content_digest')
        if self.content_digest!=digest(value):raise EvaluationError('Frozen robustness protocol changed.','robustness_protocol_changed')

    @classmethod
    def create(cls,**kwargs):
        study=RobustnessSpec.from_dict(kwargs['study']) if isinstance(kwargs['study'],dict) else kwargs['study']
        raw={**kwargs,'study':study.to_dict(),
             'claims':[(RobustnessClaim.from_dict(c) if isinstance(c,dict) else c).to_dict() for c in kwargs['claims']]}
        # Populate defaults through the dataclass signature before binding.
        from dataclasses import fields,MISSING
        for f in fields(cls):
            if f.name not in raw and f.default is not MISSING:raw[f.name]=f.default
            elif f.name not in raw and f.default_factory is not MISSING:raw[f.name]=f.default_factory()
        raw.pop('content_digest',None);raw['content_digest']=digest(raw)
        return cls.from_dict(raw)


@dataclass(frozen=True)
class RobustnessAssessmentSpec(Contract):
    protocol: FrozenRobustnessProtocol
    execution: ExecutionSpec
    schema_version: str = 'confidenceguard.robustness_assessment_spec/1.0'

    def __post_init__(self):
        nested(self,'protocol',FrozenRobustnessProtocol);nested(self,'execution',ExecutionSpec)
        original=self.protocol.study.execution
        def semantics(e):
            from ..execution.ensembles import ensemble_semantics
            d=e.to_dict();outcome=d.get('outcomes')
            if outcome:outcome={k:v for k,v in outcome.items() if k!='source'}
            return {'namespace':d['namespace'],'key_columns':d['key_columns'],'entity_columns':d['entity_columns'],
                    'task':e.task.to_dict(),'predictors':[p.predictor_digest for p in e.predictors],'batch_columns':d['batch_columns'],
                    'context_fields':d['context_fields'],'cohorts':d['cohorts'],'roles':d['roles'],'outcomes':outcome,'information_cutoff':d['information_cutoff'],
                    'auxiliaries':[a['artifact_digest'] for a in e.auxiliaries],'fitted_methods':[m['artifact_digest'] for m in e.fitted_methods],
                    'ensembles':ensemble_semantics(e.ensembles),
                    'device':d['device'],'limits':d['limits'],'evidence_retention':d['evidence_retention']}
        if semantics(original)!=semantics(self.execution):raise EvaluationError('Assessment cannot replace frozen predictor/population semantics.','robustness_assessment_binding')
        if self.execution.roles is None:raise EvaluationError('Assessment requires explicit E membership.')
        if self.schema_version!='confidenceguard.robustness_assessment_spec/1.0':raise EvaluationError('Unsupported assessment schema.')


@dataclass(frozen=True)
class PolicyStressSpec(Contract):
    robustness: RobustnessSpec
    application: dict
    batch_field: str | None = None
    schema_version: str = 'confidenceguard.policy_stress_spec/1.0'

    def __post_init__(self):
        nested(self,'robustness',RobustnessSpec);object.__setattr__(self,'application',bounded(self.application))
        from ..policy_contracts import PolicyApplicationSpec
        application=PolicyApplicationSpec.from_dict(self.application)
        batch_targets={b['field'] for b in application.input.batches}
        batch_columns={f.column for v in application.input.features for f in v.fields if v.id+'.'+f.id in batch_targets}
        if self.batch_field is not None and self.batch_field not in batch_columns:raise EvaluationError('Policy-stress batch binding differs from frozen policy inputs.')
        for s in self.robustness.scenarios:
            changed={f for t in s.transformations for f in t.fields}|(set(s.attack.fields) if s.attack else set())
            if changed&batch_columns:raise EvaluationError('A policy world cannot change frozen batch ownership.','policy_batch_contract')
        if self.schema_version!='confidenceguard.policy_stress_spec/1.0':raise EvaluationError('Unsupported policy stress schema.')
