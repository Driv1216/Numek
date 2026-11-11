"""Strict schema admission against generated CG1-CG5 definitions."""
import argparse,copy,json,hashlib
from pathlib import Path
from jsonschema import Draft202012Validator

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True);args=parser.parse_args()
    root=Path(__file__).resolve().parents[2];source=root/'src/confidenceguard/schemas';schema=json.loads((source/'contracts.json').read_text());examples=json.loads((source/'examples.json').read_text());defs=schema['$defs'];cases=[]
    Draft202012Validator.check_schema(schema)
    def check(label,definition,value,expected=True):
        errors=list(Draft202012Validator({'$defs':defs,'$ref':'#/$defs/'+definition}).iter_errors(value));cases.append({'case':label,'expected':expected,'accepted':not errors,'passed':(not errors)==expected,'errors':[{'pointer':'/'+('/'.join(map(str,e.absolute_path))),'message':e.message} for e in errors[:3]]})
    for task,spec in examples['policies'].items():
        check(task+' transport','TransportPolicyStudySpec',spec)
        bad=copy.deepcopy(spec);bad['unregistered_execution']='python';check(task+' unknown top level','TransportPolicyStudySpec',bad,False)
        bad=copy.deepcopy(spec);bad['candidates'][0]['nodes']['root']['action']['python']='print(1)';check(task+' executable action','TransportPolicyStudySpec',bad,False)
        bad=copy.deepcopy(spec);bad['input']['evaluation']['sources'][0]={'id':'data','path':'/private.csv'};check(task+' path instead of owned handle','TransportPolicyStudySpec',bad,False)
    for job in ['policy_inspect','policy_optimize','policy_replay','policy_preview','policy_assessment_inspect','policy_assess','policy_history','policy_restate','policy_inspect_look','policy_assess_look']:
        value={'kind':job,'client_request_id':'synthetic','policy_study_id':'owned','revision':1};check(job,'JobRequest',value)
        value['solver_options']={'threads':8};check(job+' solver injection','PolicyJobRequest',value,False)
    for kind,action in [('label',{'kind':'label','label':'a'}),('numeric',{'kind':'numeric','value':2}),('expected_cost',{'kind':'expected_cost','costs':'c','actions':[{'kind':'abstain'}]})]:
        check(kind,'PolicyAction',action);bad={**action,'threshold':.1};check(kind+' inapplicable field','PolicyAction',bad,False)
    base=copy.deepcopy(examples['policies']['binary_classification'])
    policy=base['candidates'][0]
    application={'schema_version':'confidenceguard.policy_application_spec/1.0','input':base['input'],'policy':policy,
        'constraints':[{'id':'coverage','metric':{'id':'coverage','metric':'issued_coverage','direction':'maximize'},'operator':'ge','bound':.5}]}
    check('application historical constraints','TransportPolicyApplicationSpec',application)
    bad=copy.deepcopy(application);bad['constraints'][0]['metric']['python']='callback';check('application constraint injection','TransportPolicyApplicationSpec',bad,False)
    template=copy.deepcopy(policy);template['nodes']={
        'root':{'kind':'rules','rules':[{'when':{'kind':'compare','value':{'kind':'probability','target':policy['task']['positive_class']},'op':'ge','constant':{'parameter':'route'}},'then':'high'}],'otherwise':'low'},
        'high':{'parameter':'high'},'low':{'parameter':'low'}}
    leaf={'kind':'action','action':{'kind':'abstain'}}
    base['families']=[{'id':'hybrid','kind':'composition','backend':'hybrid','template':template,'routing_parameters':['route'],
        'parameters':[{'id':'route','values':[.2,.8]},{'id':'high','kind':'node','values':[leaf]},{'id':'low','kind':'node','values':[leaf]}]}]
    check('hybrid finite route and leaf declarations','TransportPolicyStudySpec',base)
    bad=copy.deepcopy(base);bad['families'][0]['backend']='unregistered';check('hybrid unregistered backend','TransportPolicyStudySpec',bad,False)
    bad=copy.deepcopy(base);bad['families'][0]['routing_parameters']=['route','route'];check('hybrid duplicate routing identities','TransportPolicyStudySpec',bad,False)
    bad=copy.deepcopy(base);bad['families'][0]['routing_parameters']=True;check('hybrid malformed routing identities','TransportPolicyStudySpec',bad,False)
    result={'documents':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in source.glob('*.json')},'cases':cases,'passed':all(c['passed'] for c in cases)}
    Path(args.out).parent.mkdir(parents=True,exist_ok=True);Path(args.out).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'cases':len(cases),'passed':result['passed']}))
    if not result['passed']:raise SystemExit(1)
if __name__=='__main__':main()
