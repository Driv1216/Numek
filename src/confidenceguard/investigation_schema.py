"""Generated CG4 declarations plus explicit local-transport contracts."""
from dataclasses import fields,is_dataclass,MISSING
import copy
import types
from typing import get_args,get_origin,get_type_hints
from . import feature_contracts,investigation_contracts


def extend(definitions):
    sequences={'FeatureViewSpec':{'fields':'FeatureField'},'InvestigationSpec':{'objectives':'FailureObjectiveSpec','features':'FeatureViewSpec','representations':'DiscoveryRepresentationSpec'},'ConfirmationSpec':{'restatement_schedule':'ConfirmationLook'}}
    enums={'FeatureField':{'kind':['categorical','boolean','integer','decimal','float','timestamp','text','asset'],'role':['context','model_input','prediction_derived','retrospective']},
        'FeatureViewSpec':{'owner':['opportunity','prediction_revision'],'availability':['unknown','at_decision','dated']},
        'DiscoveryRepresentationSpec':{'kind':['supplied','retained','e5_text','dinov2_image'],'normalization':['none','l2'],'availability':['unknown','at_decision','dated'],'runtime_profile':['encoders_cpu_v1','encoders_cpu_py314_v1']},
        'FailureObjectiveSpec':{'comparator':['complement','overall','ceiling','paired','reference_period'],'direction':['auto','higher','lower','absolute','nominal_shortfall']},
        'DiscoveryRoles':{'unit':['entity','independent_rows']},'InvestigationSpec':{'feature_time_view':['available_at_decision','retrospective']},
        'ConfirmationSpec':{'method':['finite','bca','percentile'],'sampling':['independent_rows','independent_entities','independent_entity_arms','descriptive','unsupported_temporal'],
            'upstream_independence':['unknown','declared_independent','known_overlap'],'external_exposure':['unknown','declared_unexposed','known_exposed'],
            'membership_scope':['full_population','supported_population'],'outcome_scope':['observed_labels','complete_population'],'replicate_policy':['fixed','nominal_admission']}}
    def annotation(t):
        origin=get_origin(t)
        if origin in (types.UnionType,__import__('typing').Union):return {'anyOf':[annotation(a) for a in get_args(t)]}
        if t is type(None):return {'type':'null'}
        if is_dataclass(t):return {'$ref':'#/$defs/'+t.__name__}
        return {'type':{str:'string',int:'integer',float:'number',bool:'boolean',tuple:'array',dict:'object'}.get(t,'object')}
    for module in (feature_contracts,investigation_contracts):
        for name,cls in vars(module).items():
            if not isinstance(cls,type) or not is_dataclass(cls) or cls.__module__!=module.__name__ or name=='FrozenHypothesisSet':continue
            properties={};required=[];hints=get_type_hints(cls)
            for field in fields(cls):
                schema=annotation(hints[field.name])
                if field.name in sequences.get(name,{}):schema['items']={'$ref':'#/$defs/'+sequences[name][field.name]}
                if field.name in enums.get(name,{}):schema['enum']=enums[name][field.name]
                if field.name=='schema_version':schema['const']=field.default
                properties[field.name]=schema
                if field.default is MISSING and field.default_factory is MISSING:required.append(field.name)
            definitions[name]={'type':'object','additionalProperties':False,'properties':properties,'required':required}
    definitions['InvestigationSpec']['properties']['strategies']['items']={'enum':['structured','catboost','geometric','landmark']}
    definitions['ConfirmationSpec']['allOf']=[{
        'if':{'properties':{'sampling':{'const':'independent_entity_arms'}},'required':['sampling']},
        'then':{'properties':{'method':{'const':'finite'}}}}]
    definitions['DiscoveryRepresentationSpec']['properties']['model_digest']={'anyOf':[{'type':'string','pattern':'^[0-9a-f]{64}$'},{'type':'null'}],
        'description':'Supplied producer declaration, not publisher authentication. For pinned encoders, binds the verified model.safetensors SHA-256.'}
    definitions['DiscoveryRepresentationSpec']['allOf']=[
        {'if':{'properties':{'kind':{'const':kind}},'required':['kind']},
         'then':{'properties':{'dimensions':{'anyOf':[{'const':dimensions},{'type':'null'}]}}}}
        for kind,dimensions in feature_contracts.ENCODER_DIMENSIONS.items()]
    definitions['InvestigationSpec']['oneOf']=[{'required':['evaluation'],'properties':{'evaluation':{'$ref':'#/$defs/EvaluationSpec'},'history':{'type':'null'}}},
        {'required':['history'],'properties':{'evaluation':{'type':'null'},'history':{'type':'object','additionalProperties':False,'required':['workspace_path','selection'],
           'properties':{'workspace_path':{'type':'string'},'selection':{'$ref':'#/$defs/LongitudinalSpec'}}}}}]
    for name in ('MembershipArtifact','FrozenHypothesisSet','InvestigationResult','ConfirmationAssessment','ConfirmationFeasibility'):
        definitions[name]={'type':'object','description':'Data-only, content-bound CG4 evidence. Strict shape, dimensions, dependencies and digests are validated by the application service.'}
    definitions['MembershipArtifact'].update(required=['schema_version','algorithm_version','kind','parameters','features','representation','objective_identity','artifact_digest'],
        additionalProperties=False,properties={'schema_version':{'const':'confidenceguard.membership_artifact/1.0'},'algorithm_version':{'type':'string'},'kind':{'enum':['structured','catboost','geometric','landmark']},'parameters':{'type':'object'},'features':{'type':'array','items':{'type':'string'}},'representation':{'type':['string','null']},'objective_identity':{'type':['object','null']},'artifact_digest':{'type':'string','pattern':'^[0-9a-f]{64}$'}})
    for name,version in [('InvestigationResult',investigation_contracts.INVESTIGATION_RESULT),('ConfirmationAssessment',investigation_contracts.CONFIRMATION_RESULT)]:
        definitions[name].update(required=['schema_version','methodology_id','analysis_id','investigation','coverage'],properties={
            'schema_version':{'const':version},'methodology_id':{'const':investigation_contracts.INVESTIGATION_METHOD},'analysis_id':{'type':'string'},'investigation':{'type':'object'},'coverage':{'type':'object'}})
    definitions['TransportDiscoveryRepresentationSpec']=copy.deepcopy(definitions['DiscoveryRepresentationSpec'])
    p=definitions['TransportDiscoveryRepresentationSpec']['properties'];p.pop('matrix_path');p.pop('model_directory');p['matrix_handle']={'type':'string'};p['model_handle']={'type':'string'};p['keys_source']={'$ref':'#/$defs/SourceHandle'}
    definitions['TransportInvestigationSpec']=copy.deepcopy(definitions['InvestigationSpec'])
    t=definitions['TransportInvestigationSpec'];t.pop('oneOf');t['properties']['evaluation']={'anyOf':[{'$ref':'#/$defs/TransportEvaluationSpec'},{'type':'null'}]}
    t['properties']['history']={'anyOf':[{'type':'null'},{'type':'object','additionalProperties':False,'required':['selection'],'properties':{'selection':{'$ref':'#/$defs/LongitudinalSpec'}}}]}
    t['properties']['representations']['items']={'$ref':'#/$defs/TransportDiscoveryRepresentationSpec'}
    definitions['InvestigationRequest']={'type':'object','additionalProperties':False,'required':['spec'],'properties':{'spec':{'$ref':'#/$defs/TransportInvestigationSpec'},'config':{'$ref':'#/$defs/EvaluationConfig','description':'CG4 defaults result_bytes to 268435456; other EvaluationConfig defaults apply. Explicit caller budgets are retained.'},'expected_revision':{'type':'integer','minimum':1}}}
    definitions['HypothesisFreezeRequest']={'type':'object','additionalProperties':False,'required':['result_id'],'properties':{
        'result_id':{'type':'string'},'candidate_ids':{'type':'array','items':{'type':'string'},'minItems':1,'maxItems':32,'uniqueItems':True},
        'confirmation':{'$ref':'#/$defs/ConfirmationSpec'},'practical_thresholds':{'type':'object','additionalProperties':{'type':'number','minimum':0},
            'description':'Explicit per-selected-candidate thresholds in authoritative metric units, frozen before H. No universal default.'}}}
    definitions['InvestigationJobRequest']={'type':'object','additionalProperties':False,'required':['kind','client_request_id','investigation_id','revision'],
        'properties':{'kind':{'enum':['investigation_inspect','investigation_discover','confirmation_inspect','investigation_confirm','investigation_replay']},'client_request_id':{'type':'string'},'investigation_id':{'type':'string'},'revision':{'type':'integer','minimum':1},'fingerprint':{'type':'string'},'hypothesis_handle':{'type':'string'},'confirmation_fingerprint':{'type':'string'},'retain':{'type':'boolean'},'result_id':{'type':'string'},'reason':{'type':'string'}}}
    definitions['TransportFeatureEnrichmentSpec']=copy.deepcopy(definitions['FeatureEnrichmentSpec'])
    definitions['TransportFeatureEnrichmentSpec']['properties']['source']={'$ref':'#/$defs/SourceHandle'}
    job=definitions['WorkspaceJobRequest']['properties']
    job['kind']['enum']+=['enrich_features','prepare_representations','annotate_investigation','retry_confirmation','inspect_restatement_confirmation','restate_confirmation']
    job['spec']['anyOf'].append({'$ref':'#/$defs/TransportFeatureEnrichmentSpec'})
    job.update(text={'type':'string','maxLength':8192},references={'type':'array','items':{'type':'string'}},replicates={'type':'integer','minimum':1},look_id={'type':'string'})
    definitions['FrozenHypothesisSet'].update(additionalProperties=False,required=['schema_version','origin_analysis_id','origin_analysis_digest','investigation_spec','input_fingerprint','files','hypotheses','artifacts','models','confirmation_spec','evaluation_config','D_S_units','D_S_events','family_digest','content_digest'],
        properties={'schema_version':{'enum':['confidenceguard.frozen_hypothesis_set/1.0','confidenceguard.frozen_hypothesis_set/1.1']},'origin_analysis_id':{'type':'string'},'origin_analysis_digest':{'type':'string'},
            'investigation_spec':{'$ref':'#/$defs/InvestigationSpec'},'input_fingerprint':{'type':'string'},'files':{'type':'object'},'hypotheses':{'type':'array','minItems':1,'maxItems':32,'items':{'type':'object'}},
            'artifacts':{'type':'object','additionalProperties':{'$ref':'#/$defs/MembershipArtifact'}},'models':{'type':'object','additionalProperties':{'type':'string'}},
            'confirmation_spec':{'$ref':'#/$defs/ConfirmationSpec'},'evaluation_config':{'$ref':'#/$defs/EvaluationConfig'},'D_S_units':{'type':'array','items':{'type':'string'}},'D_S_events':{'type':'array','items':{'type':'string'}},'family_digest':{'type':'string'},'content_digest':{'type':'string'}})
    definitions['LegacyJobRequest']=definitions['JobRequest'];definitions['JobRequest']={'anyOf':[{'$ref':'#/$defs/LegacyJobRequest'},{'$ref':'#/$defs/InvestigationJobRequest'}]}
    for name in ('PredictionBatchSpec','TransportPredictionBatchSpec'):
        p=definitions[name]['properties'];p['schema_version']={'enum':['confidenceguard.prediction_batch_spec/1.0','confidenceguard.prediction_batch_spec/2.0']}
        p['feature_views']={'type':'array','items':{'$ref':'#/$defs/FeatureViewSpec'}}
        p['discovery_representations']={'type':'array','items':{'$ref':'#/$defs/'+('TransportDiscoveryRepresentationSpec' if name.startswith('Transport') else 'DiscoveryRepresentationSpec')}}


def capabilities():
    return {'spec_schema':'confidenceguard.investigation_spec/1.0','result_schema':investigation_contracts.INVESTIGATION_RESULT,
        'confirmation_schema':investigation_contracts.CONFIRMATION_RESULT,'methodology_id':investigation_contracts.INVESTIGATION_METHOD,
        'frozen_hypothesis_schema':'confidenceguard.frozen_hypothesis_set/1.1',
        'strategies':['structured','catboost','geometric','landmark'],'landmark_standing':'original_NUMEK_failed_promotion_profile',
        'landmark_qualification_evidence':dict(investigation_contracts.LANDMARK_PROMOTION_EVIDENCE),
        'joint_BCa_confirmation':'refused_pending_resolution_of_locked_coverage_failures',
        'ranking_percentile_confirmation':'refused_general_operating_envelope_not_qualified',
        'closure_acceptance_revision':'founder_approved_2026_10_28',
        'roles':['D','S','H'],'CG2_roles_unchanged':True,'maximum_hypotheses':32,'membership':['member','nonmember','unavailable'],
        'default_result_bytes':256*1024**2,'other_evaluation_defaults_unchanged':True,
        'confirmation':['registered_finite_sample_under_declared_assumptions'],'moving_blocks_in_confirmation':False,
        'entity_arm_finite':{'sampling':'independent_entity_arms','requires':'IID complete entities; at most one potential observation per frozen comparison arm',
            'structural_check':'Admitted H records, before outcome/class/label-availability filtering',
            'general_entity_bootstrap_promoted':False},
        'exposure_guarantee_scope':'predeclared_study_only','missing_history_proves_freshness':False}


def paths():
    routes={'/investigations':['get','post'],'/investigations/{id}':['get','put','delete'],'/hypothesis-sets':['post'],
        '/hypothesis-sets/import':['post'],'/hypothesis-sets/{id}':['get'],'/hypothesis-sets/{id}/content':['get'],
        '/investigation-assets':['post'],'/results/{id}/investigation/{section}':['get'],
        '/workspace/evidence-use':['get','post'],'/workspace/investigations/{id}/open':['post']}
    result={}
    for path,methods in routes.items():
        result[path]={}
        for method in methods:
            parameters=[{'name':piece[1:-1],'in':'path','required':True,'schema':{'type':'string'}} for piece in path.split('/') if piece.startswith('{')]
            if path=='/results/{id}/investigation/{section}':
                parameters[-1]['schema']['enum']=['summary','candidates','overlap','assessments','strategies','history']
                parameters.extend([{'name':'limit','in':'query','schema':{'type':'integer','minimum':1,'maximum':100}},
                    {'name':'cursor','in':'query','schema':{'type':'string','pattern':'^[0-9]+$'}},
                    {'name':'audience','in':'query','schema':{'enum':['local','shareable']}}])
            if method in {'post','put','delete'}:parameters.append({'name':'X-CSRF-Token','in':'header','required':True,'schema':{'type':'string'}})
            operation={'operationId':method+'_cg4_'+path.replace('/','_').replace('{','').replace('}',''),'parameters':parameters,
                'description':'For result sections, summary is a bounded display projection; candidates and overlap are paginated. Canonical exports retain complete evidence. Session-owned CG4 operation. Historical evidence additionally requires workspace authorization. Analytics run only through fixed /jobs kinds.',
                'responses':{'200':{'description':'Versioned evidence envelope or explicit protected data-only download'},'403':{'description':'Session/workspace authorization required'},'409':{'description':'Busy, stale revision or fingerprint'}}}
            if path.startswith('/investigations') and method in {'post','put'}:operation['requestBody']={'required':True,'content':{'application/json':{'schema':{'$ref':'#/components/schemas/InvestigationRequest'}}}}
            if path=='/hypothesis-sets' and method=='post':operation['requestBody']={'required':True,'content':{'application/json':{'schema':{'$ref':'#/components/schemas/HypothesisFreezeRequest'}}}}
            result[path][method]=operation
    return result


def example(evaluation):
    return {'spec':{'schema_version':'confidenceguard.investigation_spec/1.0','evaluation':evaluation,'roles':{'namespace':'prediction-events','unit':'entity'},
        'features':[{'id':'context','availability':'at_decision','fields':[{'id':'region','column':'region','kind':'categorical'}]}],
        'objectives':[{'id':'errors','metric':'error_rate','run':'candidate','direction':'higher','units':'fraction','practical_threshold':.05}],
        'strategies':['structured','catboost','geometric']},'config':{},'qualification':'Synthetic configuration; declare entity columns before execution. No measured result.'}
