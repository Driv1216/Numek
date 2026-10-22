"""Add synthetic task variants to the already authorized local qualification host."""
import argparse,json
from pathlib import Path
from confidenceguard import ReliabilityWorkspace
from .fixtures import create

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);a=p.parse_args();root=Path(a.root);ws=ReliabilityWorkspace(root/'workspace')
    for label,kind in [('multiclass','multiclass_classification'),('regression','regression')]:
        batch=create(root/'inputs'/label,kind=kind,events=300,samples=7 if label=='regression' else 0)
        batch['namespace']='browser-'+label
        if 'evaluation' in batch['evaluation']:batch['evaluation']['roles']['namespace']=batch['namespace']
        ws.ingest(batch)
    print(json.dumps([{'id':v['id'],'namespace':v['namespace'],'task':v['task']['kind']} for v in ws.models()]))
