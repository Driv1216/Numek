"""Read-only compatibility checks; never rewrite CG1 historical evidence."""
import argparse
import hashlib
import json
from pathlib import Path
from confidenceguard import EvaluationResult,EvaluationSpec,EvaluationConfig,evaluate

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--baseline',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if a.out.exists():raise ValueError('Use a new evidence path.')
    baseline=json.loads(a.baseline.read_text());checked=[]
    for name,expected in baseline.items():
        if name.startswith(('src/datatrust/','tests/cg1/','validation/cg1/')):
            assert sha(name)==expected,name;checked.append(name)
    base=Path('validation/cg1');references=json.loads((base/'results/reference.json').read_text());cases=[]
    for case in references['cases']:
        name=case['name'];source=base/'data'/(name+'.csv');assert sha(source)==case['prediction_sha256']
        spec=EvaluationSpec.from_dict(json.loads((base/'data'/(name+'.json')).read_text()),base_directory=(base/'data').absolute())
        result=evaluate(spec,EvaluationConfig(sampling={'mode':'independent_rows'}))
        for check in case['checks']:
            m=next(m for m in result.data['measurements'] if m['run']==check['run'] and m['scope']=='overall' and m['metric']==check['metric'])
            assert abs(m['value']-check['expected'])<=1e-10*max(1,abs(check['expected'])),check
        cases.append({'name':name,'metric_checks':len(case['checks']),'execution':result.execution})
    reopened=[]
    for manifest in sorted((base/'results').glob('**/.confidenceguard-private/*/manifest.json')):
        result=manifest.with_name('result.json')
        EvaluationResult.from_dict(json.loads(result.read_text()),private=json.loads(manifest.read_text()));reopened.append(str(result))
    report={'unchanged_files':len(checked),'unchanged_file_manifest_sha256':sha(a.baseline),'cg1_reference_cases':cases,'legacy_bundles_reopened':reopened,'historical_bytes_rewritten':False}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'unchanged_files':len(checked),'reference_checks':sum(v['metric_checks'] for v in cases),'legacy_bundles_reopened':len(reopened)}))

if __name__=='__main__':main()
