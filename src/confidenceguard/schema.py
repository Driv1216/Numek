"""Versioned, dependency-free JSON Schemas and local transport description."""
from dataclasses import MISSING, fields, is_dataclass
import importlib.util
import types
from typing import get_args,get_origin,get_type_hints
from . import contracts as c


SEQUENCES={'EvaluationSpec':{'sources':'SourceSpec','runs':'PredictionRunSpec','cohorts':'CohortSpec','policies':'DecisionPolicySpec'},'PredictionRunSpec':{'intervals':'PredictionIntervalSpec'}}
ENUMS={'TaskDefinition':{'kind':['binary_classification','multiclass_classification','regression']},'SourceSpec':{'format':['csv','parquet']},'DecisionSpec':{'rule':['none','probability_threshold','score_threshold','probability_argmax','score_argmax'],'tie_policy':['abstain','class_order']},'SamplingSpec':{'mode':['descriptive','independent_rows']},'DisclosureSpec':{'policy':['conservative_aggregates_v1','exact_aggregates_v1']},'DecisionPolicySpec':{'kind':['probability_threshold','score_threshold','confidence_abstention','selection_abstention','interval_abstention','supplied_cost']},'ScoreSpec':{'meaning':['event_ranking','class_scores','selection'],'direction':['higher','lower']}}


def schemas():
    definitions={}
    def annotation(t):
        origin=get_origin(t)
        if origin in (types.UnionType,__import__('typing').Union):return {'anyOf':[annotation(a) for a in get_args(t)]}
        if t is type(None):return {'type':'null'}
        if is_dataclass(t):return {'$ref':'#/$defs/'+t.__name__}
        if t in (list,tuple) or origin in (list,tuple):return {'type':'array'}
        if t is dict:return {'type':'object'}
        return {'type':{str:'string',int:'integer',float:'number',bool:'boolean'}.get(t,'string')}
    for name,cls in vars(c).items():
        if not isinstance(cls,type) or not is_dataclass(cls) or name!=cls.__name__:continue
        props={};required=[];hints=get_type_hints(cls)
        for f in fields(cls):
            prop=annotation(hints[f.name])
            if f.name in SEQUENCES.get(name,{}):prop['items']={'$ref':'#/$defs/'+SEQUENCES[name][f.name]}
            elif f.name in {'classes','categories','key_columns','entity_columns'}:prop['items']={'type':'string'}
            elif f.name in {'edges','thresholds'}:prop['items']={'type':'number'}
            if f.name in ENUMS.get(name,{}):prop['enum']=ENUMS[name][f.name]
            props[f.name]=prop
            if f.default is MISSING and f.default_factory is MISSING:required.append(f.name)
        definitions[name]={'type':'object','additionalProperties':False,'properties':props,'required':required}
    definitions['SourceHandle']={'type':'object','additionalProperties':False,'required':['id','handle'],'properties':{'id':{'type':'string'},'handle':{'type':'string'}}}
    transport_spec={**definitions['EvaluationSpec'],'properties':{**definitions['EvaluationSpec']['properties'],'sources':{'type':'array','items':{'$ref':'#/$defs/SourceHandle'}}}}
    definitions['TransportEvaluationSpec']=transport_spec
    definitions['EvaluationRequest']={'type':'object','additionalProperties':False,'required':['spec'],'properties':{'spec':{'$ref':'#/$defs/TransportEvaluationSpec'},'config':{'$ref':'#/$defs/EvaluationConfig'},'expected_revision':{'type':'integer'}}}
    definitions['JobRequest']={'type':'object','additionalProperties':False,'required':['kind','client_request_id'],'properties':{'kind':{'enum':['inspect','evaluate','export','resolve_evidence']},'client_request_id':{'type':'string'},'evaluation_id':{'type':'string'},'revision':{'type':'integer'},'fingerprint':{'type':'string'},'result_id':{'type':'string'},'format':{'enum':['html','pdf']},'audience':{'enum':['local','shareable']},'disclosure':{'$ref':'#/$defs/DisclosureSpec'},'reference':{'type':'string'},'reveal_values':{'type':'boolean'}}}
    definitions['Job']={'type':'object','required':['id','kind','state','revision'],'properties':{'id':{'type':'string'},'kind':{'type':'string'},'state':{'enum':['pending','running','cancelling','succeeded','failed','cancelled']},'revision':{'type':'integer'},'progress':{'type':'object'},'output':{'type':'object'},'error':{'type':['object','null']}}}
    definitions['Measurement']={'type':'object','required':['id','run','scope','family','metric','denominator','value','value_state','applicability','execution','population_id'],'properties':{'id':{'type':'string'},'run':{'type':'string'},'scope':{'type':'string'},'family':{'type':'string'},'metric':{'type':'string'},'denominator':{'type':['integer','string']},'value':{'type':['number','null']},'value_state':{'enum':['finite','undefined','positive_infinity','negative_infinity']},'applicability':{'enum':['applicable','blocked']},'execution':{'enum':['completed','not_run']},'population_id':{'type':'string'},'data':{'type':'object'}}}
    definitions['Measurement']['properties']['denominator_kind']={'enum':['eligible_records','evaluation_support','class_conditional_records','paired_base_support','not_evaluated'],'description':'Record support for the referenced eligibility population. Formula denominators and model-conditional paired supports are explicit in data.'}
    definitions['Population']={'type':'object','required':['id','run','scope','definition','lineage','denominator','denominator_kind'],'properties':{'id':{'type':'string'},'run':{'type':'string'},'scope':{'type':'string'},'definition':{'type':'string'},'lineage':{'type':'object','description':'Frozen normalized-input or paired-relation lineage; protected local audience only.'},'denominator':{'type':['integer','string']},'denominator_kind':definitions['Measurement']['properties']['denominator_kind']}}
    definitions['Result']={'type':'object','required':['schema_version','methodology_id','analysis_id','measurements','coverage','runs'],'properties':{'schema_version':{'const':c.RESULT_SCHEMA},'methodology_id':{'const':c.METHOD},'analysis_id':{'type':'string'},'measurements':{'type':'array','items':{'$ref':'#/$defs/Measurement'}},'coverage':{'type':'object'},'runs':{'type':'array'},'audience':{'enum':['local','shareable']}}}
    definitions['SourceRequest']={'type':'object','additionalProperties':False,'required':['root_id','relative_path'],'properties':{'root_id':{'type':'string'},'relative_path':{'type':'string'},'format':{'enum':['csv','parquet']},'encoding':{'type':'string'},'delimiter':{'type':'string'}}}
    definitions['Source']={'type':'object','required':['handle','format','columns'],'properties':{'handle':{'type':'string'},'format':{'enum':['csv','parquet']},'columns':{'type':'array','items':{'type':'string'}}}}
    definitions['Draft']={'type':'object','required':['id','revision','spec','config','confirmation'],'properties':{'id':{'type':'string'},'revision':{'type':'integer','minimum':1},'spec':{'$ref':'#/$defs/TransportEvaluationSpec'},'config':{'type':'object'},'confirmation':{'type':['string','null']}}}
    definitions['Artifact']={'type':'object','required':['id','kind','audience','bytes'],'properties':{'id':{'type':'string'},'kind':{'enum':['html','pdf','json','private_result','private_manifest']},'audience':{'enum':['local','shareable']},'bytes':{'type':['integer','string']}}}
    definitions['Inspection']={'type':'object','required':['schema_version','fingerprint','effective_spec','effective_config','sources','runs','outcomes'],'properties':{'schema_version':{'const':'confidenceguard.inspection/1.0'},'fingerprint':{'type':'string'},'effective_spec':{'$ref':'#/$defs/TransportEvaluationSpec'},'effective_config':{'$ref':'#/$defs/EvaluationConfig'},'sources':{'type':'array'},'runs':{'type':'object'},'outcomes':{'type':'object'}}}
    error_fields={'code':{'type':'string'},'message':{'type':'string'},'request_id':{'type':'string'},'retryable':{'type':'boolean'},'field_errors':{'type':'array','items':{'type':'object','required':['pointer','code'],'properties':{'pointer':{'type':'string'},'code':{'type':'string'}}}}}
    definitions['Error']={'type':'object','required':['api_version','error'],'properties':{'api_version':{'const':'v1'},'error':{'type':'object','required':['code','message','request_id','retryable'],'properties':error_fields}}}
    definitions['Page']={'type':'object','required':['items','total','next_cursor','result_id'],'properties':{'items':{'type':'array'},'total':{'type':'integer'},'next_cursor':{'type':['string','null']},'result_id':{'type':'string'}}}
    definitions['Session']={'type':'object','required':['csrf_token','root_aliases','session_lifetime'],'properties':{'csrf_token':{'type':'string'},'root_aliases':{'type':'array','items':{'type':'object','required':['id','label'],'properties':{'id':{'type':'string'},'label':{'type':'string'}}}},'session_lifetime':{'const':'local_process'}}}
    definitions['Summary']={'type':'object','required':['analysis_id','name','task','runs','headlines','findings','comparison'],'properties':{'analysis_id':{'type':'string'},'name':{'type':'string'},'task':{'type':'object'},'runs':{'type':'array'},'headlines':{'type':'array','items':{'$ref':'#/$defs/Measurement'}},'findings':{'type':'array'},'comparison':{'type':['object','null']}}}
    from .method_schema import extend
    extend(definitions)
    return {'$schema':'https://json-schema.org/draft/2020-12/schema','$id':'confidenceguard.contracts/1.0','$defs':definitions,'$ref':'#/$defs/EvaluationSpec'}


def openapi():
    operations={'/session':['get'],'/capabilities':['get'],'/sources':['post'],'/evaluations':['post'],'/evaluations/{id}':['get','put','delete'],'/jobs':['post'],'/jobs/{id}':['get'],'/jobs/{id}/cancel':['post'],'/results/{id}':['get'],'/results/{id}/{section}':['get'],'/results/{id}/artifacts':['get'],'/artifacts/{id}/content':['get'],'/results/import':['post'],'/schemas':['get'],'/openapi.json':['get'],'/examples':['get']}
    operations.update({'/methods/import':['post'],'/methods/{id}':['get'],'/methods/{id}/content':['get']})
    paths={}
    for path,methods in operations.items():
        paths[path]={}
        for method in methods:
            op={'operationId':method+'_'+path.strip('/').replace('/','_').replace('{','').replace('}','').replace('.','_'),'responses':{}}
            params=[]
            for part in path.split('/'):
                if part.startswith('{'):params.append({'name':part[1:-1],'in':'path','required':True,'schema':{'type':'string'}})
            if method in {'post','put','delete'}:params.append({'name':'X-CSRF-Token','in':'header','required':True,'schema':{'type':'string'}})
            if params:op['parameters']=params
            if path.startswith('/results/{id}') and method=='get':
                op.setdefault('parameters',[]).append({'name':'audience','in':'query','schema':{'enum':['local','shareable'],'default':'local'},'description':'A shareable-only import always remains shareable.'})
            if path=='/results/{id}/{section}':
                next(p for p in op['parameters'] if p['name']=='section')['schema']={'enum':['summary','measurements','findings','coverage','methods','assessments']}
                for query in ('cursor','limit','run','metric','scope','family','id'):op['parameters'].append({'name':query,'in':'query','schema':{'type':'integer','minimum':1,'maximum':1000} if query=='limit' else {'type':'string'},'description':'Bounded list pagination/filter; objects do not paginate.'})
            req='JobRequest' if path=='/jobs' else 'EvaluationRequest' if path.startswith('/evaluations') and method in {'post','put'} else 'SourceRequest' if path=='/sources' else None
            if req:op['requestBody']={'required':True,'content':{'application/json':{'schema':{'$ref':'#/components/schemas/'+req}}}}
            if path=='/sources':op['requestBody']['content']['multipart/form-data']={'schema':{'type':'object','required':['file'],'properties':{'file':{'type':'string','format':'binary'},'format':{'enum':['csv','parquet']},'encoding':{'type':'string'},'delimiter':{'type':'string'}}}}
            if path=='/results/import':
                files={'type':'object','required':['result'],'properties':{'result':{'type':'string','format':'binary'},'manifest':{'type':'string','format':'binary'}}}
                op['requestBody']={'required':True,'content':{'multipart/form-data':{'schema':files}}}
            if path=='/methods/import':
                op['requestBody']={'required':True,'content':{'application/json':{'schema':{'anyOf':[{'$ref':'#/components/schemas/FittedMethod'},{'$ref':'#/components/schemas/FittedCollection'}]}},'multipart/form-data':{'schema':{'type':'object','required':['file'],'properties':{'file':{'type':'string','format':'binary'}}}}}}
            response_type='Session' if path=='/session' else 'Source' if path=='/sources' else 'Draft' if path.startswith('/evaluations') and method!='delete' else 'Job' if path.startswith('/jobs') else 'Result' if path=='/results/{id}' else None
            shape={'$ref':'#/components/schemas/'+response_type} if response_type else {'type':'array','items':{'$ref':'#/components/schemas/Artifact'}} if path=='/results/{id}/artifacts' else {'type':'object'}
            if path=='/results/{id}/{section}':shape={'anyOf':[{'$ref':'#/components/schemas/Page'},{'$ref':'#/components/schemas/Summary'},{'type':'object','description':'Completed coverage object; exact or disclosure-projected according to audience.'}]}
            status='202' if path=='/jobs' and method=='post' else '201' if method=='post' and path in {'/sources','/evaluations','/results/import','/methods/import'} else '200'
            envelope={'type':'object','required':['api_version','data'],'properties':{'api_version':{'const':'v1'},'data':shape}}
            content={'application/octet-stream':{'schema':{'type':'string','format':'binary'}}} if path=='/artifacts/{id}/content' else {'application/json':{'schema':envelope}}
            if path in {'/schemas','/openapi.json'}:content={'application/json':{'schema':{'type':'object'},'description':'Raw contract document without an API envelope.'}}
            if path=='/methods/{id}/content':content={'application/json':{'schema':{'$ref':'#/components/schemas/FittedMethod'},'description':'Protected data-only fitted method download; no API envelope.'}}
            op['responses'][status]={'description':'Session-owned completed response or accepted job.','content':content}
            for error_status in ('403','404','409','413','415','422','500'):
                op['responses'][error_status]={'description':'Structured failure; no private source content.','content':{'application/json':{'schema':{'$ref':'#/components/schemas/Error'}}}}
            paths[path][method]=op
    def references(value):
        if isinstance(value,dict):return {k:v.replace('#/$defs/','#/components/schemas/') if k=='$ref' else references(v) for k,v in value.items()}
        if isinstance(value,list):return [references(v) for v in value]
        return value
    return {'openapi':'3.1.0','info':{'title':'ConfidenceGuard local API','version':'1.0.0','description':'Loopback, session-owned transport. No hosted/multi-user service. Response additions are compatible; request fields are strict. Summary and coverage sections return objects; measurements and findings return paginated lists.'},'servers':[{'url':'/api/confidenceguard/v1'}],'paths':paths,'components':{'schemas':references(schemas()['$defs'])}}


def capabilities():
    config=c.EvaluationConfig().to_dict();config.pop('scratch_directory')
    from .method_schema import capabilities as method_capabilities
    return {**method_capabilities(),'api_version':'v1','spec_schema':c.SPEC_SCHEMA,'result_schema':c.RESULT_SCHEMA,'methodology_id':c.METHOD,'tasks':['binary_classification','multiclass_classification','regression'],'formats':['csv']+(['parquet'] if importlib.util.find_spec('pyarrow') else []),'representations':{'binary_classification':['probability','event_ranking_score','hard_decision'],'multiclass_classification':['complete_probabilities','comparable_class_scores','hard_decision'],'regression':['point','supplied_prediction_interval','selection_score']},'job_kinds':['inspect','evaluate','fit','apply','study','export','resolve_evidence'],'limits':config,'disclosure_policies':['conservative_aggregates_v1','exact_aggregates_v1'],'inference':['descriptive','qualified_independent_row_wilson','paired_bca','paired_percentile_ranking','independent_cluster_bootstrap'],'hosting':'local_single_user','decision_defaults':{'without_supplied_decision':'none','argmax_ties':'abstain'},'compatibility':'Strict requests; tolerate additive response fields.'}


def examples():
    result={}
    for kind,classes,positive in [('binary_classification',['0','1'],'1'),('multiclass_classification',['a','b','c'],None),('regression',[],None)]:
        task={'kind':kind,'outcome_definition':'Supplied reference outcome','classes':classes,'positive_class':positive}
        run={'id':'candidate','source':'predictions','model':{'id':'model','version':'v1'},'key_columns':['id'],'prediction':'prediction'}
        result[kind]={'spec':{'task':task,'sources':[{'id':'predictions','handle':'SOURCE_HANDLE'}],'runs':[run],'outcomes':{'source':'predictions','column':'outcome','key_columns':['id']}},'config':{}}
    responses={'session':{'csrf_token':'SYNTHETIC_SESSION_TOKEN','root_aliases':[{'id':'root_0','label':'predictions'}],'session_lifetime':'local_process'},'source':{'handle':'SOURCE_HANDLE','format':'csv','columns':['id','prediction','outcome']},'draft':{'id':'EVALUATION_ID','revision':1,'spec':result['binary_classification']['spec'],'config':{},'confirmation':None},'job':{'id':'JOB_ID','kind':'evaluate','state':'running','revision':2,'progress':{'stage':'prediction_metrics'},'output':{},'error':None},'error':{'api_version':'v1','error':{'code':'worker_busy','message':'Another supervised operation is active.','request_id':'SYNTHETIC_REQUEST_ID','retryable':True}}}
    response_examples={k:({'api_version':'v1','data':v} if k!='error' else v) for k,v in responses.items()}
    response_examples['measurement']={'id':'m1','run':'candidate','scope':'overall','family':'performance','metric':'accuracy','population_id':'SYNTHETIC_POPULATION','denominator':100,'value':.75,'value_state':'finite','applicability':'applicable','execution':'completed','basis':'measured','interpretation':'descriptive','method_standing':'established_method','method_version':'1','data':{},'evidence_refs':[]}
    from .method_schema import examples as method_examples
    return {'label':'Synthetic contract examples, not measured results','evaluations':result,'studies':method_examples(result),'response_examples':response_examples,'jobs':{'inspect':{'kind':'inspect','evaluation_id':'EVALUATION_ID','revision':1,'client_request_id':'inspect-1'},'evaluate':{'kind':'evaluate','evaluation_id':'EVALUATION_ID','revision':1,'fingerprint':'CONFIRMATION_FINGERPRINT','client_request_id':'evaluate-1'}}}
