"""Additive generated historical schemas and transport discovery."""
from dataclasses import fields, is_dataclass, MISSING
import types
from typing import get_args, get_origin, get_type_hints
from . import history_contracts as contracts


def extend(definitions):
    sequences = {'PredictionBatchSpec': {'bindings': 'HistoricalRunBinding'},
                 'LongitudinalSpec': {'windows': 'HistoricalWindow', 'comparisons': 'HistoricalComparison', 'cohorts': 'CohortSpec'}}
    enums = {'LongitudinalInferenceSpec': {'mode': ['descriptive', 'independent_periods', 'entity_clusters', 'moving_blocks', 'paired_rows', 'paired_clusters'], 'adjustment': ['pointwise', 'bonferroni']},
             'HistoricalComparison': {'kind': ['temporal', 'matched', 'combined', 'contrast_change']},
             'LongitudinalSpec': {'maturity': ['mature_as_of', 'equal_followup', 'observed'], 'context_view': ['original', 'revised']},
             'PredictionBatchSpec': {'operation': ['ingest', 'evaluate', 'study', 'fit', 'apply']}}
    def annotation(t):
        origin = get_origin(t)
        if origin in (types.UnionType, __import__('typing').Union): return {'anyOf': [annotation(v) for v in get_args(t)]}
        if t is type(None): return {'type': 'null'}
        if is_dataclass(t): return {'$ref': '#/$defs/' + t.__name__}
        if t is object: return {'type': 'object'}
        return {'type': {str: 'string', int: 'integer', float: 'number', bool: 'boolean', tuple: 'array', dict: 'object'}.get(t, 'object')}
    for name, cls in vars(contracts).items():
        if not isinstance(cls, type) or not is_dataclass(cls) or cls.__module__ != contracts.__name__: continue
        properties = {}; required = []; hints = get_type_hints(cls)
        for f in fields(cls):
            value = annotation(hints[f.name])
            if f.name in sequences.get(name, {}): value['items'] = {'$ref': '#/$defs/' + sequences[name][f.name]}
            if f.name in enums.get(name, {}): value['enum'] = enums[name][f.name]
            if f.name == 'schema_version' and f.default is not MISSING: value['const'] = f.default
            properties[f.name] = value
            if f.default is MISSING and f.default_factory is MISSING: required.append(f.name)
        definitions[name] = {'type': 'object', 'additionalProperties': False, 'properties': properties, 'required': required}
    from .history_metrics import DRIFT_MEASURES
    definitions['LongitudinalSpec']['properties']['drift_thresholds'] = {
        'type': 'object', 'description': 'Declared field-specific descriptive effect thresholds; none are supplied by default. No p-value or degradation conclusion.',
        'additionalProperties': {'type': 'object', 'minProperties': 1, 'additionalProperties': False,
                                 'properties': {key: {'type': 'number', 'minimum': 0} for key in sorted(DRIFT_MEASURES)}}}
    definitions['Measurement']['properties'].update({
        'metric_key': {'type': 'string', 'description': 'Historical semantic identity, distinct across targets/nominal levels/definitions. Shareable aliases disclose no private definition.'},
        'metric_label': {'type': 'string'}, 'metric_identity': {'type': 'object'}})
    definitions['LongitudinalResult'] = {'type': 'object', 'required': ['schema_version', 'methodology_id', 'analysis_id', 'measurements', 'coverage', 'history'],
        'properties': {'schema_version': {'const': contracts.HISTORY_RESULT}, 'methodology_id': {'const': contracts.HISTORY_METHOD}, 'analysis_id': {'type': 'string'},
                       'measurements': {'type': 'array', 'items': {'$ref': '#/$defs/Measurement'}}, 'history': {'type': 'object'}, 'coverage': {'type': 'object'}}}
    definitions['TransportPredictionBatchSpec'] = {**definitions['PredictionBatchSpec'], 'properties': {**definitions['PredictionBatchSpec']['properties'],
        'evaluation': {'anyOf': [{'$ref': '#/$defs/TransportEvaluationSpec'}, {'$ref': '#/$defs/TransportReliabilitySpec'}]}}}
    definitions['TransportOutcomeRevisionSpec']={**definitions['OutcomeRevisionSpec'],'properties':{**definitions['OutcomeRevisionSpec']['properties'],'source':{'$ref':'#/$defs/SourceHandle'}}}
    definitions['WorkspaceJobRequest']={'type':'object','additionalProperties':False,'required':['kind','client_request_id'],'properties':{
        'kind':{'enum':['ingest','outcomes','analyze','restate','correct','recover','backup','delete','export','resolve_evidence']},
        'client_request_id':{'type':'string'},'spec':{'anyOf':[{'$ref':'#/$defs/TransportPredictionBatchSpec'},{'$ref':'#/$defs/TransportOutcomeRevisionSpec'},{'$ref':'#/$defs/LongitudinalSpec'},{'$ref':'#/$defs/HistoricalCorrectionSpec'}]},
        'config':{'$ref':'#/$defs/EvaluationConfig'},'fingerprint':{'type':'string'},'assessment_id':{'type':'string'},'as_of':{'type':['string','null']},'reason':{'type':'string'},'plan':{'type':'object'},'format':{'enum':['html','pdf']},'audience':{'enum':['local','shareable']},'reference':{'type':'string'},'reveal_values':{'type':'boolean'}}}



def paths():
    routes = {'/workspace/access': ['get'], '/workspace': ['get'], '/workspace/consent': ['post'], '/workspace/detach': ['post'],
              '/workspace/models': ['get'], '/workspace/assessments': ['get'], '/workspace/assessments/{id}': ['get'],
              '/workspace/inspect': ['post'], '/workspace/jobs': ['post'], '/workspace/deletion-preview': ['post']}
    result={}
    for path,methods in routes.items():
        result[path]={}
        for method in methods:
            operation={'operationId':method+'_history_'+path.replace('/','_').replace('{','').replace('}',''),
                'description':'Requires a process/workspace/session attachment redeemed through a locally issued one-time launch link.',
                'responses':{('202' if path.endswith('/jobs') else '200'):{'description':'Versioned API envelope with workspace service evidence'},'403':{'description':'Workspace authorization required'},'409':{'description':'Busy or stale confirmation'}}}
            params=[]
            if '{id}' in path:params.append({'name':'id','in':'path','required':True,'schema':{'type':'string'}})
            if method=='post':params.append({'name':'X-CSRF-Token','in':'header','required':True,'schema':{'type':'string'}})
            if params:operation['parameters']=params
            if path.endswith('/jobs'):operation['requestBody']={'required':True,'content':{'application/json':{'schema':{'$ref':'#/components/schemas/WorkspaceJobRequest'}}}}
            elif path.endswith('/inspect'):operation['requestBody']={'required':True,'content':{'application/json':{'schema':{'type':'object','required':['spec'],'properties':{'spec':{'$ref':'#/components/schemas/LongitudinalSpec'}}}}}}
            result[path][method]=operation
    return result
