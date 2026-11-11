"""CG5 published contracts. Semantic admission remains in strict constructors."""
from dataclasses import fields,is_dataclass,MISSING
import types
import typing
from . import policy_contracts as c

def obj(properties,required=()):
    return {'type':'object','additionalProperties':False,'properties':properties,'required':list(required)}
def ref(name): return {'$ref':'#/$defs/'+name}
def extend(defs):
    def annotation(t):
        origin=typing.get_origin(t)
        if origin in (types.UnionType,typing.Union): return {'anyOf':[annotation(v) for v in typing.get_args(t)]}
        if t is type(None): return {'type':'null'}
        if is_dataclass(t): return ref(t.__name__)
        return {'type':{str:'string',int:'integer',float:'number',bool:'boolean',dict:'object',tuple:'array',list:'array'}.get(t,'object')}
    sequences={'PolicyInputSpec':{'representations':'RepresentationSpec','features':'FeatureViewSpec','region_representations':'DiscoveryRepresentationSpec'},
               'PolicyStudySpec':{'objectives':'PolicyMetricSpec','candidates':'PolicySpec','baselines':'PolicySpec','families':'PolicyFamilySpec','constraints':'PolicyConstraint'},
               'PolicyFamilySpec':{'parameters':'PolicyParameter'},'PolicyApplicationSpec':{'metrics':'PolicyMetricSpec','constraints':'PolicyConstraint'},'PolicyAssessmentSpec':{'claims':'PolicyClaim','restatement_schedule':'ConfirmationLook'}}
    for name,cls in vars(c).items():
        if not isinstance(cls,type) or not is_dataclass(cls) or not name.startswith('Policy'): continue
        hints=typing.get_type_hints(cls); props={}; required=[]
        for f in fields(cls):
            prop=annotation(hints[f.name])
            if f.name in sequences.get(name,{}): prop['items']=ref(sequences[name][f.name])
            if f.name=='schema_version': prop={'const':f.default}
            props[f.name]=prop
            if f.default is MISSING and f.default_factory is MISSING: required.append(f.name)
        defs[name]=obj(props,required)
    scalar={'type':['number','string','boolean']}
    defs['PolicyValue']=obj({'kind':{'enum':sorted(c.VALUE_KINDS)},'run':{'type':'string'},'target':{'type':'string'},'value':scalar,'units':{'type':'string'},'tie_policy':{'enum':['abstain','action_order']}},['kind'])
    defs['PolicyPredicate']={'oneOf':[
        obj({'kind':{'enum':['all','any']},'items':{'type':'array','minItems':1,'maxItems':16,'items':ref('PolicyPredicate')}},['kind','items']),
        obj({'kind':{'const':'not'},'item':ref('PolicyPredicate')},['kind','item']),
        obj({'kind':{'const':'compare'},'value':ref('PolicyValue'),'op':{'enum':['eq','ne','lt','le','gt','ge']},'constant':{'anyOf':[scalar,obj({'cut':{'enum':['all','none']}},['cut'])]}},['kind','value','op','constant']),
        obj({'kind':{'const':'in'},'value':ref('PolicyValue'),'values':{'type':'array','items':scalar}},['kind','value','values']),
        obj({'kind':{'const':'state'},'value':ref('PolicyValue'),'state':{'type':'string'}},['kind','value','state']),
        obj({'kind':{'const':'region'},'digest':{'type':'string'},'state':{'enum':['member','nonmember','unavailable']}},['kind','digest','state'])]}
    action_fields={'kind':{'enum':['label','numeric','supplied','argmax','threshold','expected_cost','abstain','defer','unavailable']},'label':{'type':'string'},'value':{'type':'number'},'source':{'anyOf':[ref('PolicyValue'),{'enum':['probabilities','class_scores','samples']}]},'queue':{'type':'string'},'resource':{'type':'number','minimum':0},'threshold':{'type':'number'},'direction':{'enum':['higher','lower']},'positive':{'type':'string'},'negative':{'type':'string'},'costs':{'type':'string'},'actions':{'type':'array','items':ref('PolicyAction')},'tie_policy':{'enum':['abstain','class_order','action_order']},'reason':{'type':'string'}}
    allowed={'label':({'label'},['label']),'numeric':({'value','source'},[]),'supplied':(set(),[]),'argmax':({'source','tie_policy'},[]),
             'threshold':({'source','threshold','direction','positive','negative'},['source','threshold']),
             'expected_cost':({'costs','actions','tie_policy','source'},['costs','actions']),'abstain':(set(),[]),'defer':({'queue','resource'},['queue']),'unavailable':({'reason'},[])}
    variants=[]
    for kind,(keys,required) in allowed.items():
        props={key:action_fields[key] for key in keys};props['kind']={'const':kind}
        if kind in {'argmax','expected_cost'}: props['tie_policy']={'enum':['abstain','action_order']}
        if kind=='argmax': props['source']={'enum':['probabilities','class_scores']}
        if kind=='expected_cost': props['source']={'enum':['probabilities','samples']}
        variant=obj(props,['kind',*required])
        if kind=='numeric': variant['oneOf']=[{'required':['value'],'not':{'required':['source']}},{'required':['source'],'not':{'required':['value']}}]
        variants.append(variant)
    defs['PolicyAction']={'oneOf':variants}
    defs['PolicyNode']={'oneOf':[
        obj({'kind':{'const':'action'},'action':ref('PolicyAction')},['kind','action']),
        obj({'kind':{'const':'accept'},'when':ref('PolicyPredicate'),'accepted':{'type':'string'},'rejected':{'type':'string'}},['kind','when','accepted','rejected']),
        obj({'kind':{'const':'rules'},'rules':{'type':'array','maxItems':16,'items':obj({'when':ref('PolicyPredicate'),'then':{'type':'string'}},['when','then'])},'otherwise':{'type':'string'}},['kind','rules']),
        obj({'kind':{'const':'capacity'},'batch':{'type':'string'},'ranking':ref('PolicyValue'),'resource':ref('PolicyValue'),'budget':{'type':'number','minimum':0},'direction':{'enum':['higher','lower']},'admitted':{'type':'string'},'overflow':{'type':'string'}},['kind','batch','ranking','budget','admitted','overflow'])]}
    defs['PolicySpec']['properties']['nodes']={'type':'object','minProperties':1,'maxProperties':128,'additionalProperties':ref('PolicyNode')}
    for key in ('fallback','unavailable'): defs['PolicySpec']['properties'][key]=ref('PolicyAction')
    defs['PolicyInputSpec']['oneOf']=[{'required':['evaluation'],'properties':{'evaluation':{'type':'object'},'history':{'type':'null'}}},{'required':['history'],'properties':{'history':{'type':'object'},'evaluation':{'type':'null'}}}]
    defs['PolicyParameterReference']=obj({'parameter':{'type':'string'}},['parameter'])
    import copy
    def parameterize(schema):
        result=copy.deepcopy(schema)
        if '$ref' in result and result['$ref'].split('/')[-1] in {'PolicyNode','PolicyAction','PolicyPredicate','PolicyValue'}: result['$ref']=result['$ref'].replace('Policy','PolicyPrototype')
        for key in ('oneOf','anyOf','allOf'):
            if key in result: result[key]=[parameterize(v) for v in result[key]]
        if 'properties' in result: result['properties']={key:parameterize(value) for key,value in result['properties'].items()}
        if isinstance(result.get('additionalProperties'),dict): result['additionalProperties']=parameterize(result['additionalProperties'])
        if isinstance(result.get('items'),dict): result['items']=parameterize(result['items'])
        return {'anyOf':[result,ref('PolicyParameterReference')]}
    for name in ('Value','Predicate','Action','Node'): defs['PolicyPrototype'+name]=parameterize(defs['Policy'+name])
    defs['PolicyPrototype']=parameterize(defs['PolicySpec'])
    defs['PolicyFamilySpec']['properties']['template']=ref('PolicyPrototype')
    defs['FrozenPolicy']=obj({'schema_version':{'const':'confidenceguard.frozen_policy/1.0'},'policy':ref('PolicySpec'),'policy_digest':{'type':'string'},'provenance':{'type':'object'},'content_digest':{'type':'string'}},['schema_version','policy','policy_digest','provenance','content_digest'])
    defs['FrozenPolicyFamily']=obj({'schema_version':{'const':'confidenceguard.frozen_policy_family/1.0'},'policies':{'type':'array','items':ref('PolicySpec')},'protocol':ref('PolicyAssessmentSpec'),'study':ref('PolicyStudySpec'),'selection_record_digest':{'type':'string'},'development_events':{'type':'array','items':{'type':'string'}},'development_units':{'type':'array','items':{'type':'string'}},'provenance':{'type':'object'},'assessment_family_digest':{'type':'string'},'content_digest':{'type':'string'}},['schema_version','policies','protocol','study','selection_record_digest','development_events','development_units','provenance','assessment_family_digest','content_digest'])
    from .policy_metrics import METRICS
    defs['PolicyMetricSpec']['properties']['metric']={'enum':sorted(METRICS)}
    defs['PolicyMetricSpec']['properties']['basis']={'enum':sorted(c.BASES)}
    for name,attr,values in [('PolicyMetricSpec','direction',['minimize','maximize']),('PolicyConstraint','operator',['le','ge']),('PolicyClaim','operator',['le','ge','improvement']),('PolicySearchSpec','mode',['lexicographic','weighted','pareto']),('PolicyFamilySpec','backend',['auto','sweep','enumerate','milp','hybrid','bounded'])]: defs[name]['properties'][attr]={'enum':values}
    defs['PolicyFamilySpec']['properties']['routing_parameters']={'type':'array','items':{'type':'string'},'uniqueItems':True,'maxItems':31}
    for cls in ('PolicyStudySpec','PolicyApplicationSpec'):
        public=__import__('copy').deepcopy(defs[cls]); inp=__import__('copy').deepcopy(defs['PolicyInputSpec'])
        inp['properties']['evaluation']={'anyOf':[ref('TransportEvaluationSpec'),{'type':'null'}]}
        inp['properties']['method_handles']={'type':'array','items':{'type':'string'}}
        inp['properties']['history']={'anyOf':[obj({'selection':ref('LongitudinalSpec')},['selection']),{'type':'null'}]}
        public['properties']['input']=inp
        if cls=='PolicyApplicationSpec': public['properties']['policy']={'anyOf':[ref('PolicySpec'),obj({'handle':{'type':'string'}},['handle'])]}
        public['properties']['region_family_handles']={'type':'array','items':{'type':'string'}}
        defs['Transport'+cls]=public
    defs['PolicyDraftRequest']=obj({'spec':{'oneOf':[ref('TransportPolicyStudySpec'),ref('TransportPolicyApplicationSpec')]},'config':ref('EvaluationConfig'),'expected_revision':{'type':'integer'}},['spec'])
    defs['PolicyFreezeRequest']=obj({'result_id':{'type':'string'},'policy_digests':{'type':'array','items':{'type':'string'}},'assessment':ref('PolicyAssessmentSpec'),'assessment_preview':{'type':['object','null']}},['result_id'])
    defs['PolicyJobRequest']=obj({'kind':{'enum':sorted(JOBS)},'client_request_id':{'type':'string'},'policy_study_id':{'type':'string'},'revision':{'type':'integer'},'fingerprint':{'type':'string'},'family_handle':{'type':'string'},'assessment_fingerprint':{'type':'string'},'result_id':{'type':'string'},'assessment':ref('PolicyAssessmentSpec'),'planned_e_size':{'type':'integer','minimum':1},'requested_half_width':{'type':['number','null'],'exclusiveMinimum':0},'retain':{'type':'boolean'},'look_id':{'type':'string'},'as_of':{'type':'string'},'reason':{'type':'string'}},['kind','client_request_id'])
    defs['PolicyResult']={'type':'object','required':['schema_version','methodology_id','analysis_id','policy','measurements','coverage'],'properties':{'schema_version':{'const':c.RESULT},'methodology_id':{'const':c.METHOD},'analysis_id':{'type':'string'},'policy':{'type':'object'},'measurements':{'type':'array'},'coverage':{'type':'object'}}}
    defs['JobRequest']['anyOf'].append(ref('PolicyJobRequest'))

JOBS={'policy_inspect','policy_optimize','policy_replay','policy_preview','policy_assessment_inspect','policy_assess','policy_history','policy_restate','policy_inspect_look','policy_assess_look'}
def capabilities():
    from .policy_solver import availability
    from .policy_metrics import METRICS,FORMAL_UNSUPPORTED
    return {'methodology_id':c.METHOD,'schemas':['confidenceguard.policy_'+v+'/1.0' for v in ('input','spec','study_spec','application_spec','assessment_spec','result')],
            'families':['threshold','acceptance','two_cut','finite','fixed_cells','composition','complete_batch_capacity'],
            'backends':{'sweep':'complete registered additive/confusion score groups','enumerate':'complete only if every finite candidate evaluated','milp':'independent fixed residual cells; objective equivalence and bounded tie refinement','hybrid':'finite routing_parameters enumeration with admitted inner MILP; shared solve/state budgets','bounded':'deterministic beam; best found'},
            'jobs':sorted(JOBS),'metrics':sorted(METRICS),'formal_refusals':sorted(FORMAL_UNSUPPORTED),'designs':['independent_rows','independent_entity_arms'],'solver':availability(),'limits':c.PolicyLimits().to_dict(),'grammar_limits':{'nodes':128,'depth':8,'ordered_rules':16},'randomized_policies':False,'automatic_fitting':False,
            'compatibility':{'binary_threshold':'complete grouped sweep for incremental sums/confusion metrics; general metrics require finite replay',
                'acceptance_gate':'same sweep standing for a fixed action and declared selector','two_cut':'complete ordered finite boundary pairs or explicitly bounded search',
                'fixed_cells':'MILP one choice per independent residual cell; cross-cell parameter dependencies refuse','composition':'hybrid for explicit finite routing_parameters; otherwise bounded beam or complete finite enumeration',
                'inspection':'backend_admission reports S-only domains, actual encoding refusal/dependency reasons and effective limits; no solver or E access',
                'milp_ties':'finite tied one-hot enumeration, structural complexity then canonical digest; incomplete refinement explicitly qualified',
                'capacity':'complete batches; finite enumeration/replay only; no separable MILP or IID event-risk claim',
                'milp_ratio_objectives':'only fixed denominators','milp_ratio_constraints':'registered cross-multiplication with positive support floors',
                'milp_nonadditive':'macro F1, ratio differences, ranking, calibration and general nonlinear summaries refuse; finite replay/search remain available',
                'historical':'registered underlying backend; fixed windows and additive worst-window epigraphs; retrospective standing'}}

def paths():
    result={}
    operations={'/policy-studies':['get','post'],'/policy-studies/{id}':['get','put','delete'],'/policies/import':['post'],'/policies/{id}':['get'],'/policies/{id}/content':['get'],'/policy-families':['post'],'/policy-families/import':['post'],'/policy-families/{id}':['get'],'/policy-families/{id}/content':['get'],'/results/{id}/policies/{digest}/export':['post'],'/results/{id}/policy/{section}':['get'],'/workspace/policies/{id}/open':['post']}
    for path,methods in operations.items():
        result[path]={}
        for method in methods:
            op={'operationId':method+'_cg5_'+path.replace('/','_').replace('{','').replace('}',''),'parameters':[{'name':p[1:-1],'in':'path','required':True,'schema':{'type':'string'}} for p in path.split('/') if p.startswith('{')],'responses':{'200':{'description':'Owned policy evidence or mutation receipt'},'400':{'description':'Strict declaration refusal'},'404':{'description':'Unknown or unowned handle'},'409':{'description':'Revision, fingerprint or worker conflict'}}}
            if method in {'post','put','delete'}: op['parameters'].append({'name':'X-CSRF-Token','in':'header','required':True,'schema':{'type':'string'}})
            if path.startswith('/policy-studies') and method in {'post','put'}: op['requestBody']={'required':True,'content':{'application/json':{'schema':{'$ref':'#/components/schemas/PolicyDraftRequest'}}}}
            definition={'/policy-families':'PolicyFreezeRequest','/policy-families/import':'FrozenPolicyFamily','/policies/import':'FrozenPolicy'}.get(path)
            if definition and method=='post':op['requestBody']={'required':True,'content':{'application/json':{'schema':{'$ref':'#/components/schemas/'+definition}}}}
            result[path][method]=op
    return result

def examples(evaluations):
    result={}
    import copy
    for kind,value in evaluations.items():
        evaluation=copy.deepcopy(value['spec']); run=evaluation['runs'][0]['id']; task=evaluation['task']
        action={'kind':'numeric','source':{'kind':'point'}} if kind=='regression' else {'kind':'supplied'}
        policy={'task':task,'run':run,'nodes':{'root':{'kind':'action','action':action}},'root':'root','fallback':{'kind':'abstain'},'unavailable':{'kind':'unavailable'}}
        result[kind]={'input':{'evaluation':evaluation,'roles':{'namespace':'policy-example','column':'role'}},'candidates':[policy],'objectives':[{'id':'coverage','metric':'issued_coverage','direction':'maximize','basis':'operational'}]}
    return result
