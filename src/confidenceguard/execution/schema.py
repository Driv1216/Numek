"""CG6 published data contracts and owned transport declarations."""
from dataclasses import fields,is_dataclass,MISSING
import copy
import types
import typing

from . import contracts as e
from ..auxiliary import contracts as a
from ..robustness import contracts as r
from . import restatement as s


def obj(properties,required=()):
    return {'type':'object','additionalProperties':False,'properties':properties,'required':list(required)}


def ref(name):return {'$ref':'#/$defs/'+name}


def extend(defs):
    def annotation(t):
        origin=typing.get_origin(t)
        if origin in (types.UnionType,typing.Union):return {'anyOf':[annotation(v) for v in typing.get_args(t)]}
        if t is type(None):return {'type':'null'}
        if is_dataclass(t):return ref(t.__name__)
        return {'type':{str:'string',int:'integer',float:'number',bool:'boolean',tuple:'array',dict:'object',list:'array'}.get(t,'object')}
    sequences={'PredictorSpec':{'inputs':'FeatureField','outputs':'OutputBinding','files':'ArtifactFile'},
        'ExecutionSpec':{'predictors':'PredictorSpec','sources':'SourceSpec','context_fields':'FeatureField','cohorts':'CohortSpec'},
        'AuxiliaryStudySpec':{'inputs':'FeatureField','candidates':'AuxiliaryCandidate'},'AuxiliaryArtifact':{'predictors':'PredictorSpec'},
        'ScenarioSpec':{'transformations':'TransformationSpec'},'RobustnessSpec':{'scenarios':'ScenarioSpec'},
        'FrozenRobustnessProtocol':{'claims':'RobustnessClaim'},'ExecutionRestatementSpec':{'sources':'SourceSpec'}}
    names=[]
    for module in (e,a,r,s):
        for name,cls in vars(module).items():
            if not isinstance(cls,type) or not is_dataclass(cls) or cls.__module__!=module.__name__:continue
            props={};required=[];hints=typing.get_type_hints(cls)
            for f in fields(cls):
                prop=annotation(hints[f.name])
                if f.name in sequences.get(name,{}):prop['items']=ref(sequences[name][f.name])
                if f.name=='schema_version':prop={'const':f.default}
                if f.default is MISSING and f.default_factory is MISSING:required.append(f.name)
                props[f.name]=prop
            defs[name]=obj(props,required);names.append(name)
    for cls,key,values in [('DeviceSpec','kind',['cpu','mps','cuda','auto']),('DeviceSpec','precision',['float32','float64','float16']),
        ('PredictorSpec','adapter',['sklearn','onnx','torch','custom','constant']),('TransformationSpec','operation',sorted(r.OPERATIONS)),
        ('AuxiliaryStudySpec','kind',['scale','quantiles','failure_risk']),('AuxiliaryCandidate','family',['constant','logistic','histogram','mlp','mlp_ensemble'])]:
        defs[cls]['properties'][key]={'enum':values}
    handle=obj({'handle':{'type':'string'}},['handle'])
    predictor=copy.deepcopy(defs['PredictorSpec'])
    predictor['properties']['files']={'type':'array','items':obj({'name':{'type':'string'},'handle':{'type':'string'},'sha256':{'type':'string'}},['name','handle'])}
    defs['TransportPredictorSpec']={'anyOf':[handle,predictor]}
    execution=copy.deepcopy(defs['ExecutionSpec'])
    execution['properties']['sources']={'type':'array','items':obj({'id':{'type':'string'},'handle':{'type':'string'}},['id','handle'])}
    execution['properties']['predictors']={'type':'array','items':ref('TransportPredictorSpec')}
    for key in ('auxiliaries','fitted_methods','membership_sidecars'):execution['properties'].pop(key,None)
    for key in ('auxiliary_handles','method_handles'):execution['properties'][key]={'type':'array','items':{'type':'string'}}
    defs['TransportExecutionSpec']=execution
    for name in ('AuxiliaryStudySpec','RobustnessSpec','RobustnessAssessmentSpec'):
        public=copy.deepcopy(defs[name]);public['properties']['execution']=ref('TransportExecutionSpec');defs['Transport'+name]=public
    defs['TransportAuxiliaryApplication']=obj({'execution':ref('TransportExecutionSpec'),'artifact_handle':{'type':'string'},'role':{'type':['string','null']}},['execution','artifact_handle'])
    defs['TransportRobustnessAssessment']=obj({'execution':ref('TransportExecutionSpec'),'protocol_handle':{'type':'string'}},['execution','protocol_handle'])
    restatement=copy.deepcopy(defs['ExecutionRestatementSpec']);restatement['properties']['sources']=execution['properties']['sources']
    defs['TransportExecutionRestatement']=obj({'result_id':{'type':'string'},'spec':restatement},['result_id','spec'])
    policy=copy.deepcopy(defs['PolicyStressSpec']);policy['properties']['robustness']=ref('TransportRobustnessSpec');policy['properties']['application']=ref('TransportPolicyApplicationSpec')
    defs['TransportPolicyStressSpec']=policy
    defs['TransportExecutionRequest']={'anyOf':[ref('TransportExecutionSpec'),obj({'execution':ref('TransportExecutionSpec'),'qualification':obj({'reference':{'type':'array','items':{'type':'object'}},'atol':{'type':'number','minimum':0},'rtol':{'type':'number','minimum':0}})},['execution','qualification'])]}
    defs['ExecutionDraftRequest']=obj({'workflow':{'enum':['execution','auxiliary','robustness','assessment','policy_stress','restatement']},'spec':{'type':'object'},'config':ref('EvaluationConfig')},['workflow','spec'])
    mappings={'execution':'TransportExecutionRequest','auxiliary':None,'robustness':'TransportRobustnessSpec','assessment':'TransportRobustnessAssessment','restatement':'TransportExecutionRestatement','policy_stress':'TransportPolicyStressSpec'}
    defs['ExecutionDraftRequest']['allOf']=[{'if':{'properties':{'workflow':{'const':key}}},'then':{'properties':{'spec':ref(value) if value else {'anyOf':[ref('TransportAuxiliaryStudySpec'),ref('TransportAuxiliaryApplication')]}}}} for key,value in mappings.items()]
    from .web import KINDS
    defs['ExecutionJobRequest']=obj({'kind':{'enum':sorted(KINDS)},'client_request_id':{'type':'string'},'draft_id':{'type':'string'},'revision':{'type':'integer','minimum':1},'fingerprint':{'type':'string'},'retain':{'type':'boolean'}},['kind','client_request_id','draft_id','revision'])
    defs['ExecutionResult']={'type':'object','required':['schema_version','methodology_id','analysis_id','cg6','measurements','coverage'],
        'properties':{'schema_version':{'const':e.RESULT},'methodology_id':{'const':e.METHOD},'analysis_id':{'type':'string'},'cg6':{'type':'object'},'measurements':{'type':'array'},'coverage':{'type':'object'}}}
    defs['JobRequest']['anyOf'].append(ref('ExecutionJobRequest'))


def paths():
    routes={'/execution/capabilities':['get'],'/execution/files':['post'],'/execution/drafts':['get','post'],
        '/execution/drafts/{id}':['get','put','delete'],'/execution/protocols':['post'],'/execution/protocols/import':['post'],
        '/execution/protocols/{id}/content':['get'],'/execution/auxiliaries/import':['post'],'/execution/auxiliaries/{id}/content':['get'],
        '/results/{id}/execution/{section}':['get'],'/results/{id}/execution/bridge':['post'],'/workspace/execution/{id}/open':['post'],
        '/workspace/execution/protocols/{id}/open':['post']}
    out={}
    for path,methods in routes.items():
        out[path]={}
        for method in methods:
            parameters=[{'name':p[1:-1],'in':'path','required':True,'schema':{'type':'string'}} for p in path.split('/') if p.startswith('{')]
            if method!='get':parameters.append({'name':'X-CSRF-Token','in':'header','required':True,'schema':{'type':'string'}})
            out[path][method]={'operationId':method+'_cg6_'+path.replace('/','_').replace('{','').replace('}',''),
                'parameters':parameters,'responses':{'200':{'description':'Owned CG6 evidence or receipt'},'201':{'description':'Owned artifact or draft created'},'404':{'description':'Unknown or unowned handle'},'409':{'description':'Stale revision, fingerprint or active worker'}}}
    return out


def examples():
    execution={'predictors':[{'id':'reference','task':{'kind':'regression','outcome_definition':'Synthetic observed response','units':'items'},
        'adapter':'constant','inputs':[{'id':'x','column':'x','kind':'float','role':'model_input'}],
        'outputs':[{'channel':'point'}],'architecture':{'values':{'output':0.}}}],
        'sources':[{'id':'input','handle':'SOURCE_HANDLE'}],'input_source':'input','key_columns':['id'],'namespace':'synthetic-cg6-events',
        'outcomes':{'source':'input','column':'y','key_columns':['id']},'roles':{'namespace':'synthetic-cg6-events','column':'role','unit':'event'},'device':{'kind':'cpu'}}
    robustness={'execution':execution,'scenarios':[{'id':'measurement_noise','transformations':[{'id':'noise','operation':'noise','fields':['x'],'parameters':{'scale':.1}}],
        'outcome_relation':'label_preserving','outcome_reason':'Synthetic sensor measurement corruption'}]}
    return {'execution':execution,'auxiliary':{'execution':execution,'kind':'scale','base_predictor':'reference','candidates':[{'id':'baseline','family':'constant'},{'id':'histogram','family':'histogram'}]},
        'robustness':robustness,'assessment':{'protocol_handle':'PROTOCOL_HANDLE','execution':execution},
        'restatement':{'result_id':'RESULT_ID','spec':{'sources':[{'id':'later','handle':'LATER_OUTCOME_HANDLE'}],
            'outcomes':{'source':'later','column':'y','key_columns':['id']},'reason':'Later authoritative outcomes'}},
        'job':{'kind':'cg6_execute','draft_id':'DRAFT_ID','revision':1,'fingerprint':'CONFIRMATION_FINGERPRINT','client_request_id':'cg6-execute-1'}}
