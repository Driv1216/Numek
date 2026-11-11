"""Synthetic corrected assessment/history projections; no capacity qualification."""
from pathlib import Path
from dataclasses import replace
import argparse
import hashlib
import json

from confidenceguard import optimize_policies, assess_policies, freeze_policy_family
from confidenceguard.contracts import CohortSpec
from confidenceguard.policy_contracts import PolicyClaim, PolicyAssessmentSpec
from confidenceguard.policy_history import analyze_policy_history
from tests.cg5.helpers import study
from tests.cg5.test_review_corrections import history_application, CFG


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True)
    root=Path(parser.parse_args().out).resolve();root.mkdir(parents=True,exist_ok=True)
    spec=study(root/'assessment-data')
    spec=replace(spec,input=replace(spec.input,evaluation=replace(spec.input.evaluation,
        cohorts=(CohortSpec('private cohort','group',categories=('a','b')),))))
    selection=optimize_policies(spec,CFG);key=selection.data['policy']['nomination']['policy_digest']
    metric=spec.objectives[0]
    protocol=PolicyAssessmentSpec((PolicyClaim('overall accuracy',key,metric,'ge',.8),
        PolicyClaim('private scoped claim',key,replace(metric,id='private cohort metric',scope='cohort_0/category_0'),'ge',.8)),
        sampling='independent_rows',upstream_independence='declared_independent',external_exposure='declared_unexposed',
        declaration_author='Synthetic qualification',declaration_reason='Disjoint synthetic event roles')
    assessment=assess_policies(freeze_policy_family(selection,assessment=protocol),CFG)
    _,application=history_application(root/'historical-data')
    history=analyze_policy_history(application,CFG)
    receipts=[]
    from pypdf import PdfReader
    for kind,result in [('assessment',assessment),('history',history)]:
        directory=root/kind;directory.mkdir(exist_ok=True)
        for audience in ('local','shareable'):
            path=directory/(audience+'.pdf')
            artifacts=result.generate_artifacts(path,format='pdf',json_path=directory/(audience+'.json'),audience=audience)
            pages=[p.extract_text() for p in PdfReader(path).pages];text='\n'.join(pages)
            assert all(p.strip() for p in pages)
            if kind=='assessment':
                assert 'issued_accuracy' in text and 'observed_outcome' in text and '40 eligible' in text and 'ge 0.8' in text
            if kind=='history' and audience=='local':
                for term in ('Historical constraints by window','a_floor','b_floor','b_support','feasible','violated','undefined'):
                    assert term in text,term
            if audience=='shareable':
                for extension in ('html','json'):
                    projection=path.with_suffix('.'+extension).read_text()
                    for marker in (str(root),'private scoped claim','private cohort',key,'decision_costs','positive_column'):
                        assert marker not in projection,marker
                for marker in (str(root),'private scoped claim','private cohort',key): assert marker not in text,marker
                assert artifacts.private_manifest_path is None
            path.with_suffix('.pdf.txt').write_text(text)
            relevant=[i+1 for i,p in enumerate(pages) if 'Frozen independent assessment' in p or 'Historical constraints by window' in p]
            receipts.append({'file':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'pages':len(pages),
                'relevant_pages':relevant,'audience':audience,'kind':kind,'text_checks':'passed'})
    (root/'reports.json').write_text(json.dumps({'scope':'Four synthetic assessment/history JSON/HTML/PDF projections; text/privacy checks. Visual QA is recorded separately.',
        'reports':receipts},indent=2)+'\n')
    print(json.dumps(receipts))


if __name__=='__main__': main()
