"""Additive CG2 schema/capability documents; runtime validation remains authoritative."""
from dataclasses import fields,MISSING,is_dataclass
import copy
import importlib.util
import types
from typing import get_args,get_origin,get_type_hints,Union
from . import method_contracts as m


def extend(definitions):
    sequence_types={'ReliabilitySpec':{'representations':'RepresentationSpec','methods':'MethodSpec','selections':'SelectionSpec','comparisons':'ComparisonSpec','variant_policies':'DecisionPolicySpec'},
                    'RepresentationSpec':{'quantiles':'QuantileField'},'RoleSpec':{'partitions':'RolePartition'},'SeparationSpec':{'training_partitions':'RolePartition'}}
    enums={'MethodSpec':{'kind':sorted(m.CALIBRATORS|m.CONFORMAL),'input':['probabilities','probability_logit','score','logits','point','normalized','quantiles']},
           'InferenceSpec':{'mode':['descriptive','independent_rows','independent_clusters'],'adjustment':['pointwise','bonferroni']},
           'RoleSpec':{'unit':['event','entity']},'RolePartition':{'role':['F','S','C','E']},
           'SampleSpec':{'meaning':['empirical_distribution','iid_monte_carlo']},'SelectionSpec':{'objective':['log_loss','brier','efficiency']},
           'ReliabilitySpec':{'schema_version':[m.CG2_SPEC,m.STUDY_SCHEMA,m.APPLICATION_SCHEMA],'calibration_strategy':['fixed','fit_equal_frequency']}}
    def annotation(t):
        origin=get_origin(t)
        if origin in (types.UnionType,Union):return {'anyOf':[annotation(a) for a in get_args(t)]}
        if t is type(None):return {'type':'null'}
        if is_dataclass(t):return {'$ref':'#/$defs/'+t.__name__}
        return {'type':{str:'string',int:'integer',float:'number',bool:'boolean',dict:'object',tuple:'array',list:'array'}.get(t,'string')}
    for name,cls in vars(m).items():
        if not isinstance(cls,type) or not is_dataclass(cls) or cls.__module__!=m.__name__ or name!=cls.__name__:continue
        props={};required=[];hints=get_type_hints(cls)
        for f in fields(cls):
            prop=annotation(hints[f.name])
            if f.name in sequence_types.get(name,{}):prop['items']={'$ref':'#/$defs/'+sequence_types[name][f.name]}
            elif f.name in {'key_columns','candidates','metrics','scopes'}:prop['items']={'type':'string'}
            elif f.name=='levels':prop['items']={'type':['number','string']}
            elif f.name=='fitted_methods':prop['items']={'$ref':'#/$defs/FittedMethod'}
            if f.name in enums.get(name,{}):prop['enum']=enums[name][f.name]
            props[f.name]=prop
            if f.default is MISSING and f.default_factory is MISSING:required.append(f.name)
        definitions[name]={'type':'object','additionalProperties':False,'properties':props,'required':required}
    definitions['QuantileField']['properties']['level']={'type':['number','string']}
    for k in ('lower_quantile','upper_quantile'):definitions['MethodSpec']['properties'][k]={'type':['number','string']}
    safe={'type':'object','additionalProperties':False,'required':['value','value_state'],'properties':{'value':{'type':['number','null']},'value_state':{'enum':['finite','positive_infinity','negative_infinity','undefined']},'reason':{'type':'string'}},
          'allOf':[{'if':{'properties':{'value_state':{'const':'finite'}}},'then':{'properties':{'value':{'type':'number'}}},'else':{'properties':{'value':{'type':'null'}}}}]}
    definitions['SafeValue']=safe
    definitions['ConformalThreshold']={'type':'object','additionalProperties':False,'required':['coverage','n','rank','threshold'],'properties':{'coverage':{'type':'string'},'n':{'type':'integer','minimum':1},'rank':{'type':'integer','minimum':1},'threshold':{'$ref':'#/$defs/SafeValue'}}}
    method_props={'schema_version':{'const':m.FITTED_SCHEMA},'id':{'type':'string'},'definition':{'$ref':'#/$defs/MethodSpec'},'algorithm_version':{'type':'string'},'task':{'$ref':'#/$defs/TaskDefinition'},'model':{'$ref':'#/$defs/ModelIdentity'},'input_signature':{'type':'object'},'parent_digest':{'type':['string','null']},'parameters':{'type':'object'},'provenance':{'type':'object'},'evidence_state':{'const':'fitted_only'},'artifact_digest':{'type':'string','pattern':'^[0-9a-f]{64}$'}}
    definitions['FittedMethod']={'type':'object','additionalProperties':False,'required':list(method_props),'properties':method_props,'description':'Data-only. Field-specific finite-parameter and exact conformal-rank checks are mandatory at load.'}
    definitions['FittedCollection']={'type':'object','additionalProperties':False,'required':['schema_version','methods'],'properties':{'schema_version':{'const':'confidenceguard.fitted_collection/1.0'},'methods':{'type':'array','items':{'$ref':'#/$defs/FittedMethod'}},'membership_sidecars':{'type':'array','items':{'type':'object'}}}}
    assessment_props={k:{'type':'string'} for k in ('method_digest','application_digest','result_id','evaluation_digest','outcome_snapshot','meaning','assessment_digest')}
    assessment_props.update(schema_version={'const':m.ASSESSMENT_SCHEMA},population_ids={'type':'array','items':{'type':'string'}},evidence_state={'const':'independently_evaluated'},qualifications={'type':'object'})
    definitions['Assessment']={'type':'object','additionalProperties':False,'properties':assessment_props,'required':list(assessment_props)}
    transport=copy.deepcopy(definitions['ReliabilitySpec'])
    transport['properties']['evaluation']={'$ref':'#/$defs/TransportEvaluationSpec'}
    transport['properties']['method_handles']={'type':'array','items':{'type':'string'}}
    transport['properties']['output_path']={'type':'null','description':'Host-controlled; direct paths are not accepted.'}
    definitions['TransportReliabilitySpec']=transport
    request_union={'anyOf':[{'$ref':'#/$defs/TransportEvaluationSpec'},{'$ref':'#/$defs/TransportReliabilitySpec'}]}
    definitions['EvaluationRequest']['properties']['spec']=request_union
    definitions['Draft']['properties']['spec']=request_union
    definitions['Inspection']['properties']['effective_spec']=request_union
    definitions['Inspection']['properties']['schema_version']={'enum':['confidenceguard.inspection/1.0','confidenceguard.inspection/1.1']}
    definitions['JobRequest']['properties']['kind']['enum']+=['fit','apply','study']
    definitions['Artifact']['properties']['kind']['enum']+=['fitted_methods','application']
    old=definitions['Result'];definitions['CG1Result']=old
    new=copy.deepcopy(old);new['properties']['schema_version']={'const':m.CG2_RESULT};new['properties']['methodology_id']={'const':m.CG2_METHOD};new['properties']['cg2']={'type':'object'};new['required']+=['cg2']
    definitions['CG2Result']=new;definitions['Result']={'anyOf':[{'$ref':'#/$defs/CG1Result'},{'$ref':'#/$defs/CG2Result'}]}


def capabilities():
    return {'spec_schemas':['confidenceguard.evaluation_spec/1.0',m.CG2_SPEC,m.STUDY_SCHEMA,m.APPLICATION_SCHEMA],
            'result_schemas':['confidenceguard.evaluation_result/1.0',m.CG2_RESULT],
            'method_schema':m.FITTED_SCHEMA,'assessment_schema':m.ASSESSMENT_SCHEMA,
            'calibration_methods':sorted(m.CALIBRATORS),'conformal_methods':sorted(m.CONFORMAL),
            'statistics_extra_available':importlib.util.find_spec('scipy') is not None,
            'cg2_limits':m.MethodLimits().to_dict(),'inference_defaults':m.InferenceSpec().to_dict(),
            'artifact_states':['fitted_only','independently_evaluated','applied_unvalidated'],
            'cg2_representations':['explicit_logits','positive_supplied_scale','ordered_quantiles','long_predictive_samples'],
            'bootstrap_admission':'Nominal adjusted tails and job resources before resampling; actual BCa tails before publication.'}


def examples(base):
    result={}
    for kind,original in base.items():
        evaluation=copy.deepcopy(original['spec']);run=evaluation['runs'][0]
        run['key_columns']=['id'];evaluation['outcomes']['key_columns']=['id']
        if kind=='binary_classification':
            run['probabilities']={'positive_column':'probability'}
            methods=[{'id':'beta','kind':'beta','run':'candidate'},{'id':'lac','kind':'lac','run':'candidate','parent':'beta','levels':['0.9']}]
        elif kind=='multiclass_classification':
            run['probabilities']={'columns':{c:'p_'+c for c in evaluation['task']['classes']}}
            methods=[{'id':'temperature','kind':'temperature','run':'candidate'},{'id':'aps','kind':'aps','run':'candidate','parent':'temperature'}]
        else:methods=[{'id':'split','kind':'split','run':'candidate','input':'point','levels':['0.9','0.95']}]
        result[kind]={'spec':{'schema_version':m.STUDY_SCHEMA,'evaluation':evaluation,'roles':{'namespace':'supplied-events','column':'role'},'methods':methods},'config':{}}
    return result
