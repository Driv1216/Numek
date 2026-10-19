"""Focused CG1 review evidence; consumes pinned predictions without fitting predictors.

Example: PYTHONPATH=src:. .venv/bin/python -B validation/cg1/review_corrections.py
  --out /tmp/cg1-review-evidence --schema-path /opt/homebrew/lib/python3.11/site-packages
Uses existing development jsonschema only; installs nothing. Refuses output reuse.
"""
import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
import time
from confidenceguard import EvaluationSpec,EvaluationConfig,evaluate,EvaluationResult
from confidenceguard.schema import schemas,openapi,examples
from confidenceguard.analytics import digest
from tests.cg1.test_review_corrections import sizeable_binary,assert_ledger
from tests.cg1.test_semantics_controls import paired
from confidenceguard import ProbabilitySpec,SamplingSpec,CohortSpec

BASE=Path(__file__).resolve().parent


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=Path);p.add_argument('--schema-path');args=p.parse_args()
    if args.schema_path:sys.path.append(args.schema_path)
    import jsonschema
    from pypdf import PdfReader
    out=args.out;out.mkdir(parents=True,exist_ok=False)
    schema=schemas();jsonschema.Draft202012Validator.check_schema(schema)
    for name,obj in [('contracts',schema),('openapi',openapi()),('examples',examples())]:
        assert json.loads((BASE.parents[1]/'src/confidenceguard/schemas'/(name+'.json')).read_text())==obj
    expected=json.loads((BASE/'results/reference.json').read_text())
    ledger={'methodology':'prediction_evaluation_v1','population_provenance_version':'1.1','projection_revision':'cg1_review_corrections_v1','predictor_fitting':'not rerun; pinned reference calculations reused','cases':[]}
    for case in expected['cases']:
        name=case['name'];source=BASE/'data'/(name+'.csv')
        assert hashlib.sha256(source.read_bytes()).hexdigest()==case['prediction_sha256']
        spec=EvaluationSpec.from_dict(json.loads((BASE/'data'/(name+'.json')).read_text()),base_directory=BASE/'data')
        result=evaluate(spec,EvaluationConfig(sampling=SamplingSpec('independent_rows')))
        assert_ledger(result)
        checks=[]
        for check in case['checks']:
            m=next(m for m in result.data['measurements'] if m['run']==check['run'] and m['scope']=='overall' and m['metric']==check['metric'])
            assert abs(m['value']-check['expected'])<=1e-10*max(1,abs(check['expected']))
            checks.append({**check,'observed':m['value']})
        for audience in ('local','shareable'):
            data=result.to_dict(audience=audience)
            jsonschema.validate(data,{**schema,'$ref':'#/$defs/Result'})
            if audience=='local':
                for pop in data['coverage']['populations']:jsonschema.validate(pop,{**schema,'$ref':'#/$defs/Population'})
            result.generate_artifacts(out/(name+'-'+audience+'.html'),json_path=out/(name+'-'+audience+'.json'),audience=audience)
        ledger['cases'].append({'name':name,'measurements':len(result.data['measurements']),'populations':len(result.data['coverage']['populations']),'population_mismatches':0,'reference_checks':checks,'execution':result.execution,'protected_bytes':len(result.json_text().encode()),'shareable_bytes':len(json.dumps(result.to_dict()).encode())})
    # Sizeable synthetic privacy oracle and exact local control use the same analysis.
    inputs=out/'synthetic';inputs.mkdir()
    result=sizeable_binary(inputs)
    local=result.to_private_dict();shared=result.to_dict()
    curve=next(m for m in local['measurements'] if m['metric']=='roc_pr_curve')
    threshold=curve['data']['points'][1]['threshold']
    for audience in ('local','shareable'):
        result.generate_artifacts(out/('unique-scores-'+audience+'.pdf'),format='pdf',json_path=out/('unique-scores-'+audience+'.json'),audience=audience)
    pdf=PdfReader(out/'unique-scores-shareable.pdf');text='\n'.join(page.extract_text() for page in pdf.pages)
    assert str(threshold) not in text
    assert str(threshold) not in (out/'unique-scores-shareable.html').read_text()
    assert str(threshold) not in json.dumps(shared)
    assert not any(m['metric'] in {'roc_pr_curve','ranking_score'} for m in shared['measurements'])
    assert 'Exact ranking curves and native score summaries are withheld' in text
    assert 'polyline' not in (out/'unique-scores-shareable.html').read_text()
    ledger['unique_scores']={'rows':500,'unique_score_groups':curve['data']['full_score_groups'],'local_curve_retained':len(curve['data']['points']),'first_local_threshold':threshold,'first_cumulative_count':round(curve['data']['points'][1]['tpr']*250)+round(curve['data']['points'][1]['fpr']*250),'shareable_curve_records':0,'scalar_roc_auc_unchanged':next(m['value'] for m in shared['measurements'] if m['metric']=='roc_auc')==next(m['value'] for m in local['measurements'] if m['metric']=='roc_auc'),'scalar_ap_unchanged':next(m['value'] for m in shared['measurements'] if m['metric']=='average_precision')==next(m['value'] for m in local['measurements'] if m['metric']=='average_precision'),'shareable_pdf_pages':len(pdf.pages),'shareable_pdf_threshold_absent':True,'json_html_svg_checks':'passed'}
    # Portable warnings/blockers must survive even though sensitive groups are withheld.
    left='id,y,p,q,g,entity\n'+''.join(f'{i},{i%2},{i%2},{1.2 if i==0 else .8},{"SECRET_CATEGORY" if i==0 else "COMMON"},same\n' for i in range(40))
    spec=paired(inputs,left,left.replace('0,0,0,1.2','0,1,0,1.2'),probabilities=ProbabilitySpec('q'),inline_outcome='y',entity_columns=('entity',),role='train')
    spec=replace(spec,cohorts=(CohortSpec('PRIVATE_DECLARATION','g',categories=('SECRET_CATEGORY','COMMON')),))
    from tests.cg1.test_analysis import core
    result=core(spec,EvaluationConfig(sampling=SamplingSpec('independent_rows')))
    result.generate_artifacts(out/'qualified-shareable.pdf',format='pdf',json_path=out/'qualified-shareable.json')
    data=result.to_dict();pdf=PdfReader(out/'qualified-shareable.pdf');text='\n'.join(page.extract_text() for page in pdf.pages)
    for value in ('SECRET_CATEGORY','PRIVATE_DECLARATION',str(inputs)):
        assert value not in text and value not in json.dumps(data) and value not in (out/'qualified-shareable.html').read_text()
    for value in ('not held out','inference blocked','paired comparison blocked','conflicting_asserted_outcome_copy','probability_quality:run_1','Observed labels need not represent unobserved cases.'):
        assert value in text,value
    ledger['portable_qualifications']={'finding_codes':[f['code'] for f in data['findings']],'checks':data['checks'],'limitations':data['coverage']['limitations'],'pdf_pages':len(pdf.pages),'private_values_absent':True}
    (out/'verification.json').write_text(json.dumps(ledger,indent=2)+'\n')
    print(json.dumps({'reference_checks':sum(len(c['reference_checks']) for c in ledger['cases']),'population_mismatches':0,'json_schema':'passed','pdfs':3,'unique_score_and_qualification_probes':'passed'}))


if __name__=='__main__':main()
