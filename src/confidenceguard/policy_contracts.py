"""Strict data-only CG5 contracts. No analytical or transport dependencies."""
from dataclasses import dataclass, field, fields
from decimal import Decimal, InvalidOperation
import copy
import json
import math
from pathlib import Path

from .contracts import (Contract, EvaluationError, EvaluationSpec, TaskDefinition,
                        digest, name, choice, nested, sequence, positive)
from .method_contracts import RoleSpec, SeparationSpec, RepresentationSpec
from .feature_contracts import FeatureViewSpec, DiscoveryRepresentationSpec

METHOD = 'policy_selection_v1'
RESULT = 'confidenceguard.policy_result/1.0'
INTERPRETER = 'typed_policy_interpreter_v1'
VALUE_KINDS = {'constant', 'field', 'probability', 'score', 'class_score', 'selector',
               'confidence', 'margin', 'point', 'quantile', 'sample_mean', 'sample_median',
               'scale', 'interval_width', 'interval_state', 'set_size', 'set_state',
               'output_state', 'region'}
VALUE_KINDS|={'argmax_class','argmax_score_class','supplied_decision'}
ACTION_KINDS = {'label', 'numeric', 'supplied', 'argmax', 'threshold', 'expected_cost',
                'abstain', 'defer', 'unavailable'}
BASES = {'observed_outcome', 'model_implied', 'operational', 'partial_lower', 'partial_upper'}


def fail(message, code='policy_contract'):
    raise EvaluationError(message, code)


def finite(value, label='value', minimum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        fail(f'{label} must be a finite number.')
    if minimum is not None and value < minimum:
        fail(f'{label} is outside its declared domain.')
    return value


def bounded_json(value, *, maximum=64*1024**2, depth=24, elements=1000000):
    """Bound shape before recursive copies/digests; reject executable/nonfinite values."""
    todo=[(value, 0)]; count=0; size=0
    while todo:
        item, level=todo.pop(); count+=1
        if level>depth or count>elements: fail('Policy JSON shape exceeds admission.', 'policy_shape_limit')
        if type(item) is dict:
            if any(type(k) is not str for k in item): fail('Policy object keys must be strings.')
            size+=sum(len(k.encode())+8 for k in item)
            todo.extend((v, level+1) for v in item.values())
        elif type(item) in (list, tuple):
            size+=len(item)*8; todo.extend((v, level+1) for v in item)
        elif type(item) is str: size+=len(item.encode('utf-8', errors='surrogatepass'))+8
        elif item is None or type(item) in (bool, int): size+=32
        elif type(item) is float:
            finite(item); size+=32
        else: fail('Policies accept JSON data only.')
        if size>maximum: fail('Policy JSON exceeds byte admission.', 'policy_byte_limit')


def shape(value, required, optional=()):
    if type(value) is not dict or not set(required)<=value.keys() or set(value)-set(required)-set(optional):
        fail('Invalid typed policy object fields.')


def referenced_runs(definition,features):
    runs=set(); fields_used=set()
    def scan(v):
        if isinstance(v,dict):
            if v.get('kind') in VALUE_KINDS:
                if v.get('run'):runs.add(v['run'])
                if v['kind']=='field':fields_used.add(v['target'])
            for value in v.values():scan(value)
        elif isinstance(v,(list,tuple)):
            for value in v:scan(value)
    scan(definition.get('nodes',{}))
    for view in features:
        if view.get('run') and any(view['id']+'.'+f['id'] in fields_used for f in view['fields']):runs.add(view['run'])
    runs.discard(definition['run']);return sorted(runs)


def validate_bound_references(policy,identity):
    fields={v['id']+'.'+f['id'] for v in identity['features'] for f in v['fields']}
    regions=set(identity['regions'])
    terminal=[n['action'] for n in policy.nodes.values() if n['kind']=='action']
    classifier=(policy.task.kind=='binary_classification' and {a.get('label') for a in terminal if a['kind']=='label'}==set(policy.task.classes) and all(a['kind'] in {'label','abstain','defer','unavailable'} for a in terminal))
    def scan(v,in_ranking=False):
        if isinstance(v,dict):
            if v.get('kind')=='field' and v['target'] not in fields:fail('Policy refers to an undeclared typed feature.','policy_input_contract')
            if v.get('kind')=='region':
                target=v.get('digest',v.get('target'))
                if target not in regions:fail('Policy refers to an undeclared frozen region.','policy_input_contract')
            if v.get('kind')=='score' and not in_ranking and not classifier:fail('A correctness acceptance selector requires its explicit selection-score declaration.','policy_native_score_not_selector')
            for key,value in v.items():scan(value,in_ranking or key=='ranking' or v.get('kind')=='threshold')
        elif isinstance(v,(list,tuple)):
            for value in v:scan(value,in_ranking)
    scan(policy.nodes)


def value_ref(value):
    shape(value, {'kind'}, {'target', 'run', 'value', 'units','tie_policy'})
    choice(value['kind'], VALUE_KINDS, 'policy input')
    kind=value['kind']
    if kind=='constant':
        if 'value' not in value or type(value['value']) not in (str, int, float, bool): fail('A constant needs a scalar value.')
    elif kind in {'field','probability','class_score','quantile','interval_width','interval_state','set_size','set_state','region'}:
        name(value.get('target'))
    elif 'value' in value or 'target' in value: fail('This input does not take a target/value.')
    if 'run' in value: name(value['run'])
    if 'units' in value: name(value['units'])
    if 'tie_policy' in value:
        if kind not in {'argmax_class','argmax_score_class'}: fail('Tie behavior applies only to class assignment summaries.')
        choice(value['tie_policy'],{'abstain','action_order'},'assignment tie behavior')
    return value


def predicate(value, level=0):
    if level>16: fail('Predicate nesting exceeds admission.', 'policy_shape_limit')
    if type(value) is not dict: fail('A typed predicate is required.')
    kind=value.get('kind')
    if kind in {'all','any'}:
        shape(value, {'kind','items'})
        if type(value['items']) is not list or not 1<=len(value['items'])<=16: fail('Predicate composition needs 1–16 items.')
        for item in value['items']: predicate(item, level+1)
    elif kind=='not': shape(value, {'kind','item'}); predicate(value['item'], level+1)
    elif kind=='compare':
        shape(value, {'kind','value','op','constant'})
        value_ref(value['value']); choice(value['op'], {'eq','ne','lt','le','gt','ge'}, 'comparison')
        c=value['constant']
        if type(c) is dict:
            shape(c, {'cut'}); choice(c['cut'], {'all','none'}, 'cut endpoint')
        elif type(c) not in (str,int,float,bool): fail('Comparisons need a typed scalar constant.')
    elif kind=='in':
        shape(value, {'kind','value','values'}); value_ref(value['value'])
        if type(value['values']) is not list or not 1<=len(value['values'])<=256 or any(type(v) not in (str,int,float,bool) for v in value['values']): fail('Set membership requires finite scalar values.')
    elif kind=='state':
        shape(value, {'kind','value','state'}); value_ref(value['value'])
        choice(value['state'], {'observed','missing','invalid','unavailable','not_retained'}, 'input state')
    elif kind=='region':
        shape(value, {'kind','digest','state'}); name(value['digest'])
        choice(value['state'], {'member','nonmember','unavailable'}, 'region state')
    else: fail('Unsupported policy predicate.')


def action(value, task):
    shape(value, {'kind'}, {'label','value','source','queue','resource','threshold','direction','positive',
                           'negative','tie_policy','costs','actions','reason'})
    kind=value['kind']; choice(kind, ACTION_KINDS, 'policy action')
    allowed={
        'label': {'label'}, 'numeric': {'value','source'}, 'supplied': set(),
        'argmax': {'source','tie_policy'}, 'threshold': {'source','threshold','direction','positive','negative'},
        'expected_cost': {'costs','actions','tie_policy','source'}, 'abstain': set(),
        'defer': {'queue','resource'}, 'unavailable': {'reason'}}[kind]
    if set(value)-{'kind'}-allowed: fail('Fields do not apply to this action.')
    classification=task.kind!='regression'
    if kind=='label':
        if not classification or value.get('label') not in task.classes: fail('Label action differs from the task.')
    if kind=='numeric':
        if classification or ('value' in value)==('source' in value): fail('Numeric action requires one regression value/source.')
        if 'value' in value: finite(value['value'])
        else:
            value_ref(value['source'])
            if value['source']['kind'] not in {'point','quantile','sample_mean','sample_median','constant'}: fail('Unsupported numeric action source.')
    if kind=='argmax':
        if not classification: fail('Argmax requires classification.')
        choice(value.get('source','probabilities'), {'probabilities','class_scores'}, 'argmax source')
    if kind=='threshold':
        if task.kind!='binary_classification': fail('Threshold labels require binary classification.')
        value_ref(value.get('source')); finite(value.get('threshold'))
        if value.get('positive',task.positive_class) not in task.classes or value.get('negative',next(c for c in task.classes if c!=task.positive_class)) not in task.classes: fail('Threshold actions must use the declared classes.')
        choice(value.get('direction','higher'), {'higher','lower'}, 'threshold direction')
    if kind=='defer':
        name(value.get('queue')); finite(value.get('resource',1), minimum=0)
    if kind=='unavailable': name(value.get('reason','declared_unavailable'))
    if kind=='expected_cost':
        name(value.get('costs'))
        if type(value.get('actions')) is not list or not value['actions'] or len(value['actions'])>256: fail('Expected cost requires declared actions.')
        for a in value['actions']:
            if a.get('kind') in {'expected_cost','argmax','threshold','supplied'}: fail('Expected cost alternatives must be fixed actions.')
            action(a, task)
        choice(value.get('source','probabilities'), {'probabilities','samples'}, 'predictive distribution')
        if classification!=(value.get('source','probabilities')=='probabilities'): fail('Predictive cost source differs from the task.')
    if 'tie_policy' in value: choice(value['tie_policy'], {'abstain','action_order'}, 'action tie policy')


def validate_policy(task, nodes, root, fallback, unavailable):
    bounded_json(nodes)
    if type(nodes) is not dict or not nodes or len(nodes)>128: fail('Policies require 1–128 named nodes.')
    name(root)
    for a in (fallback, unavailable): action(a, task)
    if any(a['kind'] not in {'label','numeric','abstain','defer','unavailable'} or a['kind']=='numeric' and 'source' in a for a in (fallback,unavailable)):
        fail('Fallbacks must be terminal input-independent actions.')
    edges={}; rules=0
    for key,node in nodes.items():
        name(key)
        if type(node) is not dict: fail('Typed policy nodes required.')
        kind=node.get('kind')
        if kind=='action': shape(node, {'kind','action'}); action(node['action'], task); refs=[]
        elif kind=='rules':
            shape(node, {'kind','rules'}, {'otherwise'})
            if type(node['rules']) is not list or not 1<=len(node['rules'])<=16: fail('Ordered rules require 1–16 branches.')
            refs=[]; rules+=len(node['rules'])
            for rule in node['rules']:
                shape(rule, {'when','then'}); predicate(rule['when']); refs.append(rule['then'])
            if node.get('otherwise') is not None: refs.append(node['otherwise'])
        elif kind=='accept':
            shape(node, {'kind','when','accepted','rejected'}); predicate(node['when']); refs=[node['accepted'],node['rejected']]
        elif kind=='capacity':
            shape(node, {'kind','batch','ranking','budget','admitted','overflow'}, {'resource','direction'})
            name(node['batch']); value_ref(node['ranking']); finite(node['budget'], minimum=0)
            if 'resource' in node: value_ref(node['resource'])
            choice(node.get('direction','higher'), {'higher','lower'}, 'capacity ranking')
            refs=[node['admitted'],node['overflow']]
        else: fail('Unsupported policy node.')
        if any(type(r) is not str or r not in nodes for r in refs): fail('Policy references an absent node.')
        edges[key]=refs
    if rules>16 or root not in nodes: fail('Policy rule/root admission exceeded.')
    active=set(); done=set(); heights={}
    def visit(key, depth):
        if depth>8 or key in active: fail('Policy is cyclic or exceeds depth 8.')
        if key in done:
            if depth+heights[key]-1>8:fail('Shared policy path exceeds depth 8.')
            return
        active.add(key)
        for child in edges[key]: visit(child, depth+1)
        active.remove(key); done.add(key);heights[key]=1+max((heights[c] for c in edges[key]),default=0)
    visit(root, 1)
    if done!=nodes.keys(): fail('Unreachable policy nodes are not admitted.')
    def queues(key):
        node=nodes[key]
        if node['kind']=='action':
            a=node['action']; alternatives=a.get('actions',[a])
            return {v['queue'] for v in alternatives if v['kind']=='defer'}
        return set().union(*(queues(child) for child in edges[key]))
    for node in nodes.values():
        if node['kind']=='capacity' and queues(node['admitted'])&queues(node['overflow']): fail('Capacity overflow must be outside the guarded process resource.')


def cost_table(table):
    if type(table) is dict and table.get('kind')=='numeric_loss':
        shape(table, {'kind','loss'}, {'level','nonissued'})
        choice(table['loss'], {'absolute','squared','pinball','signed'}, 'numeric decision loss')
        finite(table.get('level',.5),minimum=0)
        if table.get('level',.5)>1: fail('Numeric loss level exceeds one.')
        for v in table.get('nonissued',{}).values(): finite(v)
        return
    if type(table) is not dict or not table or len(table)>256: fail('A bounded cost declaration is required.')
    for key,row in table.items():
        name(key)
        if type(row) is not dict or not row: fail('Costs map action keys to outcome costs.')
        for outcome,v in row.items():
            name(outcome)
            try: d=Decimal(str(v))
            except (InvalidOperation,ValueError): fail('Invalid cost.')
            if isinstance(v,bool) or not d.is_finite() or not math.isfinite(float(d)) or len(str(v))>160: fail('Costs must be finite decimal values.')


@dataclass(frozen=True)
class PolicySpec(Contract):
    task: TaskDefinition
    run: str
    nodes: dict
    root: str
    fallback: dict
    unavailable: dict
    decision_costs: dict = field(default_factory=dict)
    input_identity: dict = field(default_factory=dict)
    schema_version: str = 'confidenceguard.policy_spec/1.0'

    def __post_init__(self):
        nested(self,'task',TaskDefinition); name(self.run)
        if self.schema_version!='confidenceguard.policy_spec/1.0': fail('Unsupported policy schema.')
        for v in (self.nodes,self.fallback,self.unavailable,self.decision_costs,self.input_identity): bounded_json(v)
        validate_policy(self.task,self.nodes,self.root,self.fallback,self.unavailable)
        if type(self.decision_costs) is not dict or type(self.input_identity) is not dict: fail('Policy identity and economics require objects.')
        for key,table in self.decision_costs.items(): name(key); cost_table(table)
        for node in self.nodes.values():
            if node['kind']=='action' and node['action']['kind']=='expected_cost' and node['action']['costs'] not in self.decision_costs: fail('Decision cost declaration is absent.')
            if node['kind']=='action' and node['action']['kind']=='expected_cost':
                declaration=node['action']; table=self.decision_costs[declaration['costs']]
                for alternative in declaration['actions']:
                    key=alternative.get('label') if alternative['kind']=='label' else 'deferred:'+alternative['queue'] if alternative['kind']=='defer' else 'abstained' if alternative['kind']=='abstain' else 'unavailable'
                    if self.task.kind!='regression' and (key not in table or set(table[key])!=set(self.task.classes)): fail('Decision costs must cover every possible declared outcome for every alternative.')
                    if self.task.kind=='regression' and (table.get('kind')!='numeric_loss' or alternative['kind']!='numeric' and key not in table.get('nonissued',{})): fail('Predictive-sample decisions need a complete registered numeric loss.')
        for attr in ('nodes','fallback','unavailable','decision_costs','input_identity'):
            object.__setattr__(self,attr,copy.deepcopy(getattr(self,attr)))

    @property
    def policy_digest(self): return digest({'interpreter':INTERPRETER,'definition':self.to_dict()})


@dataclass(frozen=True)
class PolicyLimits(Contract):
    max_candidates: int = 4096
    max_cutpoints: int = 1000000
    max_search_states: int = 1000000
    predicate_events: int = 100000000
    action_cells: int = 100000000
    contribution_cells: int = 100000000
    metric_records: int = 65536
    dominance_pairs: int = 10000000
    max_cells: int = 32
    max_options: int = 256
    solver_variables: int = 8192
    solver_rows: int = 8192
    solver_nonzeros: int = 1000000
    solver_calls: int = 64
    solver_nodes: int = 100000
    solver_seconds: float = 300
    beam_width: int = 64
    assessment_policies: int = 8
    assessment_claims: int = 256
    assessment_components: int = 4096
    materialized_bytes: int = 1024**3
    def __post_init__(self):
        for f in fields(self): positive(getattr(self,f.name),f.name,integer=f.name!='solver_seconds')


@dataclass(frozen=True)
class PolicyInputSpec(Contract):
    roles: RoleSpec
    evaluation: EvaluationSpec | None = None
    history: dict | None = None
    representations: tuple = ()
    fitted_methods: tuple = ()
    membership_sidecars: tuple = ()
    separation: SeparationSpec = field(default_factory=SeparationSpec)
    features: tuple = ()
    regions: tuple = ()
    region_representations: tuple = ()
    batches: tuple = ()
    run_bindings: dict = field(default_factory=dict)
    feature_time_view: str = 'available_at_decision'
    as_of: str | None = None
    schema_version: str = 'confidenceguard.policy_input/1.0'

    def __post_init__(self):
        nested(self,'roles',RoleSpec); nested(self,'evaluation',EvaluationSpec,True); nested(self,'separation',SeparationSpec)
        for attr,cls in [('representations',RepresentationSpec),('features',FeatureViewSpec),('region_representations',DiscoveryRepresentationSpec)]: sequence(self,attr,cls)
        if (self.evaluation is None)==(self.history is None): fail('Choose supplied or retained policy evidence.')
        if self.history is not None:
            shape(self.history, {'workspace_path','selection'})
            from .history_contracts import LongitudinalSpec
            LongitudinalSpec.from_dict(self.history['selection'])
        if self.evaluation and any(not r.key_columns for r in self.evaluation.runs): fail('Policies require explicit unique event keys.')
        choice(self.feature_time_view, {'available_at_decision','retrospective'}, 'feature time view')
        if self.schema_version!='confidenceguard.policy_input/1.0': fail('Unsupported policy input schema.')
        if type(self.run_bindings) is not dict: fail('Run bindings require an explicit alias-to-retained-run mapping.')
        for alias,target in self.run_bindings.items(): name(alias); name(target)
        for attr in ('fitted_methods','membership_sidecars','regions','batches'):
            values=getattr(self,attr)
            if not isinstance(values,(list,tuple)) or any(type(v) is not dict for v in values): fail('Protected policy inputs require data-only object arrays.')
            bounded_json(values); object.__setattr__(self,attr,tuple(copy.deepcopy(values)))
        for region in self.regions:
            shape(region, {'artifact','models','provenance'}, {'feature_contracts','representation_contract'})
            from .investigation_membership import validate
            validate(region['artifact'],models=region['models'])
            actual={v.id:v.to_dict() for v in self.features}
            for contract in region.get('feature_contracts',[]):
                declared=FeatureViewSpec.from_dict(contract)
                if actual.get(declared.id)!=declared.to_dict(): fail('Frozen region feature contracts differ from policy inputs.','membership_feature_contract')
            rep=region.get('representation_contract')
            if rep is not None:
                supplied=next((r for r in self.region_representations if r.id==rep.get('id')),None)
                if supplied is None: fail('A frozen region representation binding is missing.','membership_feature_contract')
                compare={k:v for k,v in supplied.to_dict().items() if k not in {'matrix_path','keys_source','model_directory'}}
                if supplied.kind=='retained': compare['kind']=rep.get('kind')
                if compare!=rep: fail('Frozen representation semantics differ.','membership_feature_contract')
            shape(region['provenance'], {'feature_time_policy','development_events','development_units','independence'}, {'origin_analysis_digest'})
            choice(region['provenance']['independence'], {'unknown','declared_independent','known_overlap'}, 'region provenance')
        for batch in self.batches:
            shape(batch, {'id','field','closed_at','members'})
            name(batch['id']); name(batch['field'])
            from .history_contracts import instant
            instant(batch['closed_at'])
            if type(batch['members']) is not dict: fail('Batch completeness maps canonical batch values to count/digest.')
            for key,member in batch['members'].items():
                name(key); shape(member, {'count','digest'}); positive(member['count'],'batch count'); name(member['digest'])

    @classmethod
    def from_dict(cls,value,*,base_directory=None):
        value=copy.deepcopy(value)
        if base_directory is not None and value.get('evaluation'):
            value['evaluation']=EvaluationSpec.from_dict(value['evaluation'],base_directory=base_directory).to_dict()
        return super().from_dict(value)


@dataclass(frozen=True)
class PolicyParameter(Contract):
    id: str
    kind: str = 'finite'
    values: tuple = ()
    value: dict | None = None
    lower: str | None = None
    upper: str | None = None
    count: int | None = None
    endpoints: bool = True
    def __post_init__(self):
        name(self.id); choice(self.kind, {'finite','cutpoints','grid','node'}, 'policy parameter')
        if not isinstance(self.values,(list,tuple)): fail('Parameter values require an array.')
        bounded_json(self.values); object.__setattr__(self,'values',tuple(copy.deepcopy(self.values)))
        if self.kind in {'finite','node'} and not self.values: fail('Finite parameter choices cannot be empty.')
        if self.kind=='cutpoints': value_ref(self.value)
        if self.kind=='grid':
            if self.value is not None: value_ref(self.value)
            positive(self.count,'grid count')
            if self.count<2 or self.count>1000000: fail('Grid count must lie within [2,1000000].')
            try: a,b=Decimal(str(self.lower)),Decimal(str(self.upper))
            except InvalidOperation: fail('Grid bounds require decimals.')
            if not a.is_finite() or not b.is_finite() or a>=b or not math.isfinite(float(a)) or not math.isfinite(float(b)): fail('Grid bounds must increase and be finite.')
        if type(self.endpoints) is not bool: fail('Parameter endpoints must be Boolean.')


@dataclass(frozen=True)
class PolicyFamilySpec(Contract):
    id: str
    template: dict
    parameters: tuple
    kind: str = 'finite'
    backend: str = 'auto'
    routing_parameters: tuple = ()
    def __post_init__(self):
        name(self.id); sequence(self,'parameters',PolicyParameter)
        choice(self.kind, {'threshold','acceptance','two_cut','finite','fixed_cells','composition'}, 'policy family')
        choice(self.backend, {'auto','sweep','enumerate','milp','hybrid','bounded'}, 'policy backend')
        if not self.parameters or len({p.id for p in self.parameters})!=len(self.parameters): fail('Unique policy parameters required.')
        if len(self.parameters)>32: fail('Parameter count exceeds admission.')
        bounded_json(self.template); object.__setattr__(self,'template',copy.deepcopy(self.template))
        name(self.template.get('run'))
        used=set()
        def scan(v):
            if type(v) is dict:
                if set(v)=={'parameter'}: used.add(v['parameter'])
                else:
                    for x in v.values(): scan(x)
            elif isinstance(v,(tuple,list)):
                for x in v: scan(x)
        scan(self.template)
        if used!={p.id for p in self.parameters}: fail('Template parameter bindings differ from their declarations.')
        if not isinstance(self.routing_parameters,(list,tuple)) or any(type(v) is not str for v in self.routing_parameters): fail('Routing parameters require named finite choices.')
        object.__setattr__(self,'routing_parameters',tuple(self.routing_parameters))
        if len(set(self.routing_parameters))!=len(self.routing_parameters) or set(self.routing_parameters)-used: fail('Routing parameter identities differ.')
        if self.routing_parameters:
            if len(self.routing_parameters)==len(self.parameters) or any(p.kind not in {'finite','node'} for p in self.parameters if p.id in self.routing_parameters): fail('Hybrid search requires finite outer routes and remaining leaf choices.')
            if self.backend not in {'auto','hybrid','enumerate','bounded'}: fail('Outer routes require hybrid, finite enumeration or bounded search.')
        elif self.backend=='hybrid': fail('Hybrid search requires explicit routing parameters.')


@dataclass(frozen=True)
class PolicyMetricSpec(Contract):
    id: str
    metric: str
    direction: str = 'minimize'
    basis: str = 'observed_outcome'
    scope: str = 'overall'
    target: str | None = None
    interval: str | None = None
    units: str = 'fraction'
    weight: float = 1.
    cost: str | None = None
    loss: str = 'absolute'
    level: float = .5
    bounds: tuple = ()
    def __post_init__(self):
        for v in (self.id,self.metric,self.scope,self.units): name(v)
        basis={'model_implied_cost':'model_implied','partial_lower':'partial_lower','partial_upper':'partial_upper','selective_partial_lower':'partial_lower','selective_partial_upper':'partial_upper'}.get(self.metric)
        operational={'issued_coverage','abstention_rate','deferral_rate','unavailable_rate','input_unavailable_rate','issued_count','abstention_count','deferral_count','unavailable_count','resource_mean','resource_total','operational_charge','charge_total'}
        if self.metric in operational: basis='operational'
        if basis:
            if self.basis not in {'observed_outcome',basis}: fail('Metric name and evidence basis disagree.')
            object.__setattr__(self,'basis',basis)
        choice(self.direction, {'minimize','maximize'}, 'objective direction'); choice(self.basis,BASES,'metric basis')
        choice(self.loss, {'absolute','squared','signed','pinball','material'}, 'numeric loss')
        finite(self.weight,minimum=0); finite(self.level,minimum=0)
        if self.level>1: fail('Pinball level requires [0,1].')
        if self.target is not None: name(self.target)
        if self.cost is not None: name(self.cost)
        if not isinstance(self.bounds,(list,tuple)) or self.bounds and (len(self.bounds)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in self.bounds) or self.bounds[0]>=self.bounds[1]): fail('Contribution bounds must be finite and increasing.')
        object.__setattr__(self,'bounds',tuple(self.bounds))


@dataclass(frozen=True)
class PolicyConstraint(Contract):
    id: str
    metric: PolicyMetricSpec
    operator: str
    bound: float
    minimum_support: int = 1
    def __post_init__(self):
        name(self.id); nested(self,'metric',PolicyMetricSpec)
        choice(self.operator, {'le','ge'}, 'constraint operator'); finite(self.bound); positive(self.minimum_support,'minimum support')


@dataclass(frozen=True)
class PolicySearchSpec(Contract):
    mode: str = 'lexicographic'
    seed: int = 0
    absolute_tolerance: float = 1e-10
    relative_tolerance: float = 1e-8
    epsilon_constraints: tuple = ()
    def __post_init__(self):
        choice(self.mode, {'lexicographic','weighted','pareto'}, 'selection mode')
        if type(self.seed) is not int or self.seed<0: fail('Seed requires a nonnegative integer.')
        finite(self.absolute_tolerance,minimum=0); finite(self.relative_tolerance,minimum=0)
        bounded_json(self.epsilon_constraints)
        if not isinstance(self.epsilon_constraints,(list,tuple)) or len(self.epsilon_constraints)>64: fail('Epsilon schedules exceed solve admission.')
        for schedule in self.epsilon_constraints:
            if not isinstance(schedule,(list,tuple)): fail('Each epsilon solve requires an array of bounds.')
            for bound in schedule:
                shape(bound, {'metric_id','operator','bound'}); name(bound['metric_id'])
                choice(bound['operator'],{'le','ge'},'epsilon bound'); finite(bound['bound'])


@dataclass(frozen=True)
class PolicyStudySpec(Contract):
    input: PolicyInputSpec
    objectives: tuple
    candidates: tuple = ()
    families: tuple = ()
    constraints: tuple = ()
    baselines: tuple = ()
    evaluation_costs: dict = field(default_factory=dict)
    charges: dict = field(default_factory=dict)
    imported_policies: tuple = ()
    search: PolicySearchSpec = field(default_factory=PolicySearchSpec)
    limits: PolicyLimits = field(default_factory=PolicyLimits)
    name: str = 'Decision policy study'
    schema_version: str = 'confidenceguard.policy_study_spec/1.0'
    def __post_init__(self):
        nested(self,'input',PolicyInputSpec); nested(self,'search',PolicySearchSpec); nested(self,'limits',PolicyLimits)
        for attr,cls in [('objectives',PolicyMetricSpec),('constraints',PolicyConstraint),('candidates',PolicySpec),('baselines',PolicySpec),('families',PolicyFamilySpec)]: sequence(self,attr,cls)
        name(self.name)
        if self.schema_version!='confidenceguard.policy_study_spec/1.0': fail('Unsupported policy study schema.')
        if not self.objectives or not (self.candidates or self.families): fail('Policies and an explicit objective are required.')
        if len(self.objectives)>16 or len(self.constraints)>128 or len(self.candidates)+len(self.baselines)>self.limits.max_candidates: fail('Policy declarations exceed admission.')
        if len({v.id for v in self.objectives})!=len(self.objectives) or len({v.id for v in self.constraints})!=len(self.constraints): fail('Duplicate objective/constraint identity.')
        bounded_json(self.evaluation_costs); bounded_json(self.charges)
        if not isinstance(self.imported_policies,(list,tuple)): fail('Imported policies require protected packets.')
        for packet in self.imported_policies: FrozenPolicy.from_dict(packet)
        object.__setattr__(self,'imported_policies',tuple(copy.deepcopy(self.imported_policies)))
        for key,table in self.evaluation_costs.items(): name(key); cost_table(table)
        for key,v in self.charges.items(): name(key); finite(v,minimum=0)
        tasks={digest(p.task.to_dict()) for p in (*self.candidates,*self.baselines)}
        for family in self.families:
            if 'task' not in family.template: fail('Every policy prototype binds a task.')
            tasks.add(digest(TaskDefinition.from_dict(family.template['task']).to_dict()))
        if len(tasks)>1 or self.input.evaluation and tasks and tasks!={digest(self.input.evaluation.task.to_dict())}: fail('Policy and evidence tasks differ.')

    @property
    def study_design_digest(self): return digest(self.to_dict())

    @classmethod
    def from_dict(cls,value,*,base_directory=None):
        value=copy.deepcopy(value)
        if base_directory is not None: value['input']=PolicyInputSpec.from_dict(value['input'],base_directory=base_directory).to_dict()
        return super().from_dict(value)


@dataclass(frozen=True)
class PolicyApplicationSpec(Contract):
    input: PolicyInputSpec
    policy: PolicySpec
    role: str = 'E'
    metrics: tuple = ()
    evaluation_costs: dict = field(default_factory=dict)
    charges: dict = field(default_factory=dict)
    limits: PolicyLimits = field(default_factory=PolicyLimits)
    name: str = 'Frozen policy replay'
    schema_version: str = 'confidenceguard.policy_application_spec/1.0'
    constraints: tuple = ()
    def __post_init__(self):
        nested(self,'input',PolicyInputSpec); nested(self,'policy',PolicySpec); nested(self,'limits',PolicyLimits)
        sequence(self,'metrics',PolicyMetricSpec); sequence(self,'constraints',PolicyConstraint)
        choice(self.role,{'F','S','C','E','all'},'replay role'); name(self.name)
        if len(self.constraints)>128 or len({c.id for c in self.constraints})!=len(self.constraints): fail('Unique bounded replay constraints required.')
        if self.schema_version!='confidenceguard.policy_application_spec/1.0': fail('Unsupported application schema.')
        for table in self.evaluation_costs.values(): cost_table(table)
        for v in self.charges.values(): finite(v,minimum=0)


@dataclass(frozen=True)
class PolicyClaim(Contract):
    id: str
    policy_digest: str
    metric: PolicyMetricSpec
    operator: str
    bound: float
    comparator: str | None = None
    minimum_support: int = 1
    weight: str | None = None
    required: bool = True
    def __post_init__(self):
        name(self.id); name(self.policy_digest); nested(self,'metric',PolicyMetricSpec)
        choice(self.operator, {'le','ge','improvement'}, 'claim operator'); finite(self.bound)
        positive(self.minimum_support,'claim support')
        if self.operator=='improvement' and (not self.comparator or self.bound<0): fail('Improvement requires a comparator and nonnegative material threshold.')
        if type(self.required) is not bool: fail('Required-claim flag must be Boolean.')
        if self.weight is not None:
            try: d=Decimal(str(self.weight))
            except InvalidOperation: fail('Invalid claim weight.')
            if not d.is_finite() or not 0<d<=1: fail('Claim weight requires (0,1].')


@dataclass(frozen=True)
class PolicyAssessmentSpec(Contract):
    claims: tuple
    sampling: str = 'descriptive'
    confidence: float = .95
    upstream_independence: str = 'unknown'
    external_exposure: str = 'unknown'
    declaration_author: str | None = None
    declaration_reason: str | None = None
    known_common_shocks: bool = False
    study_id: str | None = None
    study_alpha: str = '0.05'
    batch_alpha: str = '0.05'
    exposure_history_token: str | None = None
    restatement_schedule: tuple = ()
    schema_version: str = 'confidenceguard.policy_assessment_spec/1.0'
    def __post_init__(self):
        sequence(self,'claims',PolicyClaim)
        if not self.claims or len({c.id for c in self.claims})!=len(self.claims): fail('Unique frozen claims required.')
        choice(self.sampling, {'descriptive','independent_rows','independent_entity_arms','independent_entities','unsupported_temporal'}, 'assessment sampling')
        choice(self.upstream_independence, {'unknown','declared_independent','known_overlap'}, 'upstream independence')
        choice(self.external_exposure, {'unknown','declared_unexposed','known_exposed'}, 'external exposure')
        finite(self.confidence)
        if not 0<self.confidence<1: fail('Confidence requires (0,1).')
        try: total,batch=Decimal(str(self.study_alpha)),Decimal(str(self.batch_alpha))
        except InvalidOperation: fail('Invalid error allocation.')
        if not 0<batch<=total<=Decimal(str(1-self.confidence))+Decimal('1e-14'): fail('Error budget exceeds confidence.')
        weights=[c.weight for c in self.claims]
        if any(w is not None for w in weights) and (any(w is None for w in weights) or sum(Decimal(str(w)) for w in weights)>1): fail('Allocate every claim weight or use equal allocation.')
        if self.upstream_independence=='declared_independent' or self.external_exposure=='declared_unexposed':
            name(self.declaration_author); name(self.declaration_reason)
        if type(self.known_common_shocks) is not bool: fail('Common-shock flag requires Boolean.')
        from .investigation_contracts import ConfirmationLook
        sequence(self,'restatement_schedule',ConfirmationLook)
        if self.restatement_schedule and (not self.study_id or batch+sum(Decimal(str(x.alpha)) for x in self.restatement_schedule)>total): fail('Scheduled looks exceed the frozen study budget.')
        if self.schema_version!='confidenceguard.policy_assessment_spec/1.0': fail('Unsupported assessment schema.')


@dataclass(frozen=True)
class FrozenPolicy:
    data: dict
    def __post_init__(self):
        bounded_json(self.data)
        shape(self.data, {'schema_version','policy','policy_digest','provenance','content_digest'})
        if self.data['schema_version']!='confidenceguard.frozen_policy/1.0': fail('Unsupported frozen policy.')
        policy=PolicySpec.from_dict(self.data['policy'])
        if not policy.input_identity: fail('Frozen policies must bind their upstream input semantics.','policy_input_contract')
        if self.data['policy_digest']!=policy.policy_digest or self.data['content_digest']!=digest({k:v for k,v in self.data.items() if k!='content_digest'}): fail('Frozen policy binding differs.','policy_changed')
        object.__setattr__(self,'data',copy.deepcopy(self.data))
    def to_dict(self): return copy.deepcopy(self.data)
    @classmethod
    def from_dict(cls,value): return cls(value)


@dataclass(frozen=True)
class FrozenPolicyFamily:
    data: dict
    def __post_init__(self):
        bounded_json(self.data)
        shape(self.data, {'schema_version','policies','protocol','study','selection_record_digest',
                          'development_events','development_units','provenance','assessment_family_digest','content_digest'})
        if self.data['schema_version']!='confidenceguard.frozen_policy_family/1.0': fail('Unsupported frozen policy family.')
        spec=PolicyAssessmentSpec.from_dict(self.data['protocol']); study=PolicyStudySpec.from_dict(self.data['study'])
        definitions=[PolicySpec.from_dict(p) for p in self.data['policies']]
        if any(not p.input_identity for p in definitions): fail('Frozen assessment policies require bound upstream semantics.','policy_input_contract')
        policies={p.policy_digest for p in definitions}
        if len(policies)!=len(self.data['policies']) or len(policies)>study.limits.assessment_policies or len(spec.claims)>study.limits.assessment_claims: fail('Assessment family exceeds admission.')
        if any(c.policy_digest not in policies or c.comparator is not None and c.comparator not in policies for c in spec.claims): fail('Claim policy/comparator is absent.')
        provenance=self.data['provenance']
        if type(provenance) is not dict or not isinstance(provenance.get('nominated'),list) or not provenance['nominated'] or set(provenance['nominated'])-policies: fail('Frozen nominations must belong to the assessed family.')
        covered=required_constraint_coverage(study,spec,provenance['nominated'])
        if provenance.get('required_constraints_covered')!=covered: fail('Frozen constraint coverage differs from the complete required constraints.','policy_changed')
        packet={k:v for k,v in self.data.items() if k not in {'content_digest','assessment_family_digest'}}
        if digest(packet)!=self.data['assessment_family_digest'] or digest({k:v for k,v in self.data.items() if k!='content_digest'})!=self.data['content_digest']: fail('Frozen policy family changed.','policy_changed')
        object.__setattr__(self,'data',copy.deepcopy(self.data))
    @property
    def family_digest(self): return self.data['assessment_family_digest']
    def to_dict(self): return copy.deepcopy(self.data)
    @classmethod
    def from_dict(cls,value): return cls(value)


def required_constraint_claims(requirement,protocol,policy):
    """Only mandatory direct claims can establish a required study constraint."""
    return [c for c in protocol.claims if c.required and c.policy_digest==policy and c.comparator is None
            and c.operator==requirement.operator and c.bound==requirement.bound
            and c.metric==requirement.metric and c.minimum_support>=requirement.minimum_support]


def required_constraint_coverage(study,protocol,policies):
    return {p:all(required_constraint_claims(c,protocol,p) for c in study.constraints) for p in policies}
