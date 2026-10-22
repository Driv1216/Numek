"""Self-contained supplied-prediction reports and sanitized workspace reproduction."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
from confidenceguard import ReliabilityWorkspace,WorkspaceConfig
from .fixtures import create,specification


def run(output,events=365,pdf=True):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    workspace=ReliabilityWorkspace.initialize(output/'workspace',WorkspaceConfig(saving=True))
    records=[]
    for label,kind in [('binary','binary_classification'),('multiclass','multiclass_classification'),('regression','regression')]:
        batch=create(output/'inputs'/label,kind=kind,events=events,classes=5,samples=12 if label=='regression' else 0)
        batch['namespace']='synthetic-'+label
        if 'evaluation' in batch['evaluation']:batch['evaluation']['roles']['namespace']=batch['namespace']
        receipt=workspace.ingest(batch)
        variant=next(v for v in workspace.models() if v['task']['kind']==kind)
        spec=specification([variant]);spec['namespace']=batch['namespace'];result=workspace.analyze(spec,request_id='reproduce-'+label)
        directory=output/'reports';directory.mkdir(exist_ok=True)
        paths={}
        for audience in ('local','shareable'):
            artifacts=result.generate_artifacts(directory/(label+'-'+audience+('.pdf' if pdf else '.html')),format='pdf' if pdf else 'html',audience=audience,json_path=str(directory/(label+'-'+audience+'.json')))
            paths[audience]=asdict(artifacts)
        records.append({'task':kind,'receipt':receipt,'assessment':result.data['analysis_id'],'spec':spec,'reports':paths})
    (output/'reproduction.json').write_text(json.dumps(records,indent=2)+'\n')
    return records


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True);parser.add_argument('--events',type=int,default=365);parser.add_argument('--no-pdf',action='store_true');args=parser.parse_args()
    print(json.dumps(run(args.out,args.events,not args.no_pdf),indent=2))
