"""Data-only schema surface checks in the separate validator runtime."""
from copy import deepcopy
import json
from pathlib import Path
import jsonschema

root=Path(__file__).resolve().parents[2]
schema=json.loads((root/'src/confidenceguard/schemas/contracts.json').read_text())
examples=json.loads((root/'src/confidenceguard/schemas/examples.json').read_text())['execution']
jsonschema.Draft202012Validator.check_schema(schema)
checks=[]

def check(name,definition,value,expected=True):
    candidate={'$schema':schema['$schema'],'$defs':schema['$defs'],'$ref':'#/$defs/'+definition}
    valid=jsonschema.Draft202012Validator(candidate).is_valid(value)
    checks.append({'name':name,'expected_valid':expected,'actual_valid':valid,'passed':valid==expected})

for workflow in ['execution','auxiliary','robustness','assessment','restatement']:
    value={'workflow':workflow,'spec':examples[workflow]}
    check(workflow+' owned draft','ExecutionDraftRequest',value)
    bad=deepcopy(value);bad['spec']['unexpected_execution_code']='arbitrary'
    check(workflow+' refuses unknown field','ExecutionDraftRequest',bad,False)
check('fixed job','ExecutionJobRequest',examples['job'])
bad=deepcopy(examples['job']);bad['kind']='cg6_run_arbitrary_python';check('no arbitrary job','ExecutionJobRequest',bad,False)
bad=deepcopy(examples['execution']);bad['sources']=[{'id':'input','path':'/unowned.csv'}];check('source paths cannot replace handles','TransportExecutionSpec',bad,False)
bad=deepcopy(examples['execution']);bad['auxiliaries']=[{'path':'/unowned'}];check('raw auxiliary grants prohibited','TransportExecutionSpec',bad,False)
check('explicit pending CUDA request','DeviceSpec',{'kind':'cuda','index':2})
check('invalid device','DeviceSpec',{'kind':'nvidia_simulated'},False)
result={'checks':checks,'passed':all(x['passed'] for x in checks),'validator_runtime':'separate jsonschema runtime; no analytical/device qualification'}
out=root/'validation/cg6/results/schema-qualification.json';out.parent.mkdir(exist_ok=True);out.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
if not result['passed']:raise SystemExit(1)
