"""Independent JSON Schema checks; run in the hash-locked schema-only environment."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys

from jsonschema import Draft202012Validator

ROOT=Path(__file__).resolve().parents[2]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True);args=parser.parse_args()
    directory=ROOT/'src/confidenceguard/schemas'
    documents={name:json.loads((directory/name).read_text()) for name in ('contracts.json','openapi.json','examples.json')}
    definitions=documents['contracts.json']['$defs'];examples=documents['examples.json'];records=[]
    Draft202012Validator.check_schema(documents['contracts.json'])
    def check(name,definition,value,expected=True):
        validator=Draft202012Validator({'$defs':definitions,'$ref':'#/$defs/'+definition})
        errors=list(validator.iter_errors(value));accepted=not errors
        records.append({'case':name,'definition':definition,'expected_accepted':expected,'accepted':accepted,
            'passed':accepted==expected,'errors':[{'pointer':'/'+('/'.join(str(v) for v in e.absolute_path)),'message':e.message} for e in errors]})
    for name,example in examples['evaluations'].items():check('CG1 '+name,'TransportEvaluationSpec',example['spec'])
    for name,example in examples['studies'].items():check('CG2 '+name,'TransportReliabilitySpec',example['spec'])
    check('CG3 prediction batch','TransportPredictionBatchSpec',examples['history']['batch'])
    check('CG3 longitudinal','LongitudinalSpec',examples['history']['longitudinal'])
    check('CG4 investigation','TransportInvestigationSpec',examples['investigation']['spec'])
    for state in ('final','observed','provisional','invalid','conflicting','pending','withdrawn','invented',None,True):
        check('declared outcome status '+repr(state),'OutcomeSnapshotSpec',
            {'source':'data','column':'y','status_column':'status','status_values':{'custom_input':state}},
            state in {'final','observed','provisional','invalid','conflicting','pending','withdrawn'})
    for name,example in examples['jobs'].items():check('job '+name,'JobRequest',example)
    for name,definition in [('session','Session'),('source','Source'),('draft','Draft'),('job','Job'),('error','Error'),('measurement','Measurement')]:
        value=examples['response_examples'][name]
        if name in {'session','source','draft','job'}:
            wrapper={'$defs':definitions,'type':'object','required':['api_version','data'],
                'properties':{'api_version':{'const':'v1'},'data':{'$ref':'#/$defs/'+definition}}}
            errors=list(Draft202012Validator(wrapper).iter_errors(value))
            records.append({'case':'response envelope '+name,'expected_accepted':True,'accepted':not errors,
                'passed':not errors,'errors':[e.message for e in errors]})
            value=value['data']
        check('response '+name,definition,value)
    for kind,dimensions in [('e5_text',384),('dinov2_image',768)]:
        core={'id':'encoder','kind':kind,'field':'context.content','model_directory':'/synthetic/installed/model','dimensions':dimensions}
        transport={k:v for k,v in core.items() if k!='model_directory'};transport['model_handle']='SYNTHETIC_MODEL_HANDLE'
        for label,value,definition in [('core',core,'DiscoveryRepresentationSpec'),('transport',transport,'TransportDiscoveryRepresentationSpec')]:
            for dim,accepted in [(dimensions,True),(None,True),(dimensions+1,False),('incorrect',False),(True,False)]:
                check(f'{label} {kind} dimensions {dim!r}',definition,{**value,'dimensions':dim},accepted)
            check(f'{label} {kind} unknown property',definition,{**value,'unexpected':'value'},False)
            check(f'{label} {kind} malformed model hash',definition,{**value,'model_digest':'A'*64},False)
    # The separately published OpenAPI projection must retain the same constraint.
    components=documents['openapi.json']['components']['schemas']
    for kind,dimensions in [('e5_text',384),('dinov2_image',768)]:
        validator=Draft202012Validator({'components':{'schemas':components},'$ref':'#/components/schemas/TransportDiscoveryRepresentationSpec'})
        for dim,expected in [(dimensions,True),(dimensions+1,False)]:
            accepted=not list(validator.iter_errors({'id':'encoder','kind':kind,'field':'context.content','model_handle':'SYNTHETIC_MODEL_HANDLE','dimensions':dim}))
            records.append({'case':f'OpenAPI {kind} dimensions {dim}','expected_accepted':expected,'accepted':accepted,'passed':accepted==expected})
    data={'schema_version':'numek.cg4_schema_reference_checks/1.0','python':sys.version,
        'packages':{name:importlib.metadata.version(name) for name in ('jsonschema','attrs','referencing','jsonschema-specifications','rpds-py')},
        'documents':{name:hashlib.sha256((directory/name).read_bytes()).hexdigest() for name in documents},
        'records':records,'all_passed':all(r['passed'] for r in records),
        'scope':'Static contract/example acceptance and selected negative constraints only. Does not establish full schema/application equivalence or product/analytical correctness.'}
    output=Path(args.out);output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x') as stream:json.dump(data,stream,sort_keys=True,indent=2);stream.write('\n')
    print(json.dumps({'checks':len(records),'failed':[r['case'] for r in records if not r['passed']],'all_passed':data['all_passed']}))
    if not data['all_passed']:raise SystemExit(1)


if __name__=='__main__':main()
