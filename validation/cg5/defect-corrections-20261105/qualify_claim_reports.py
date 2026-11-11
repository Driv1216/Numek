"""Small D5 regression-claim report fixture, not a capacity qualification."""
from pathlib import Path
import hashlib,json
from tests.cg5.test_defect_corrections import regression_study,regression_claims,protocol,CFG
from confidenceguard.policies import optimize_policies
from confidenceguard.policy_assessment import freeze_policy_family,assess_policies
from pypdf import PdfReader

if __name__=='__main__':
    root=Path(__file__).resolve().parent/'reports';root.mkdir(exist_ok=True)
    selection=optimize_policies(regression_study(root/'data',outcome='1'),CFG)
    key=selection.data['policy']['nomination']['policy_digest']
    result=assess_policies(freeze_policy_family(selection,assessment=protocol(key,regression_claims(),2)),CFG)
    records=[]
    for audience in ('local','shareable'):
        path=root/(audience+'.pdf')
        result.generate_artifacts(path,format='pdf',json_path=path.with_suffix('.json'),audience=audience)
        pages=[page.extract_text() for page in PdfReader(path).pages]
        text='\n'.join(pages)
        for term in ('Pinball level: 0.1','Pinball level: 0.9','Loss: squared','Material error threshold: 0.5','squared_items'):
            assert term in text,term
        if audience=='shareable':
            for term in (str(root),key,'D1–D5 fixture','decision_costs'):
                assert term not in text and term not in path.with_suffix('.json').read_text(),term
        records.append({'audience':audience,'file':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                        'pages':len(pages),'changed_table_pages':[i+1 for i,p in enumerate(pages) if 'Pinball level:' in p],
                        'text_and_privacy_checks':'passed'})
    (root/'verification.json').write_text(json.dumps(records,indent=2)+'\n')
    print(json.dumps(records))
