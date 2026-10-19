"""Closure references, schemas and selected canonical reports; no predictor fitting.

Requires the isolated development jsonschema target. PDF generation is explicit.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time
from confidenceguard import EvaluationSpec,EvaluationConfig,evaluate
from confidenceguard.schema import schemas,examples,openapi

BASE=Path(__file__).resolve().parent


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--pdf',action='store_true');parser.add_argument('--out',type=Path);args=parser.parse_args()
    import jsonschema
    definitions=schemas();jsonschema.Draft202012Validator.check_schema(definitions)
    for example in examples()['evaluations'].values():jsonschema.validate(example,{**definitions,'$ref':'#/$defs/EvaluationRequest'})
    for example in examples()['jobs'].values():jsonschema.validate(example,{**definitions,'$ref':'#/$defs/JobRequest'})
    for kind,example in examples()['response_examples'].items():
        target={'session':'Session','source':'Source','draft':'Draft','job':'Job','error':'Error','measurement':'Measurement'}[kind]
        jsonschema.validate(example if kind in {'error','measurement'} else example['data'],{**definitions,'$ref':'#/$defs/'+target})
    bundled=BASE.parents[1]/'src/confidenceguard/schemas'
    for filename,value in [('contracts.json',definitions),('openapi.json',openapi()),('examples.json',examples())]:
        (bundled/filename).write_text(json.dumps(value,indent=2)+'\n')
    expected=json.loads((BASE/'results/reference.json').read_text());ledger={'reference_fitting_reused':True,'methodology':'prediction_evaluation_v1','schemas':'Draft202012 schemas, requests and results passed','cases':[]}
    out=args.out or BASE/'results'/('closure-'+str(time.time_ns()));out.mkdir(parents=True,exist_ok=False)
    for case in expected['cases']:
        name=case['name'];source=BASE/'data'/(name+'.csv')
        assert hashlib.sha256(source.read_bytes()).hexdigest()==case['prediction_sha256']
        s=EvaluationSpec.from_dict(json.loads((BASE/'data'/(name+'.json')).read_text()),base_directory=BASE/'data')
        result=evaluate(s,EvaluationConfig(sampling={'mode':'independent_rows'}))
        for check in case['checks']:
            m=next(m for m in result.data['measurements'] if m['run']==check['run'] and m['scope']=='overall' and m['metric']==check['metric'])
            assert abs(m['value']-check['expected'])<=1e-10*max(1,abs(check['expected'])),check
        jsonschema.validate(result.to_private_dict(),{**definitions,'$ref':'#/$defs/Result'})
        jsonschema.validate(result.to_dict(),{**definitions,'$ref':'#/$defs/Result'})
        artifacts=[]
        for audience in ('local','shareable'):
            path=out/(name+'-'+audience+('.pdf' if args.pdf else '.html'))
            tick=time.monotonic();a=result.generate_artifacts(path,format='pdf' if args.pdf else 'html',json_path=path.with_suffix('.json'),audience=audience)
            artifacts.append({'audience':audience,'pdf':a.pdf_path,'html':a.html_path,'seconds':time.monotonic()-tick})
        ledger['cases'].append({'name':name,'checks':len(case['checks']),'execution':result.execution,'protected_bytes':len(result.json_text().encode()),'shareable_bytes':len(json.dumps(result.to_dict()).encode()),'artifacts':artifacts})
    (BASE/'results/closure.json').write_text(json.dumps(ledger,indent=2)+'\n')
    print(json.dumps({'cases':len(ledger['cases']),'independent_metric_checks':sum(c['checks'] for c in ledger['cases']),'pdfs':6 if args.pdf else 0,'schema_validation':'passed'}))


if __name__=='__main__':main()
