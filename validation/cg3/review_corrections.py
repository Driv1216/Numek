"""R1–R3 affected evidence from the original synthetic facts, without recapture."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import tarfile
import zipfile
from confidenceguard import ReliabilityWorkspace


def run(original_zip, output, *, pdf=True):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    with zipfile.ZipFile(original_zip) as archive:
        records=json.loads(archive.read('examples/reproduction.json'))
        target=output/'synthetic-backup.tar.gz';target.write_bytes(archive.read('examples/synthetic-backup.tar.gz'))
    with tarfile.open(target) as archive:
        assert all((m.isfile() or m.isdir()) and (m.name=='backup' or m.name.startswith('backup/')) and '..' not in Path(m.name).parts for m in archive.getmembers())
        archive.extractall(output,filter='data')
    workspace=ReliabilityWorkspace.restore(output/'backup',output/'workspace')
    original={r['assessment']:workspace.open(r['assessment']).to_private_dict() for r in records}
    retained={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (workspace.path/'objects').iterdir() if p.is_file()}
    evidence=[]
    for label in ('multiclass','regression'):
        old=next(r for r in records if r['task']==label+'_classification' or r['task']==label)
        spec=copy.deepcopy(old['spec']);spec['name']='CG3 independent review corrections: '+label
        spec['material_thresholds']=({'balanced_accuracy':.01,'macro_f1_observed_classes':.01,'support_weighted_f1':.01}
                                     if label=='multiclass' else {'bias':.01,'interval_coverage':.01,'interval_coverage@0.9':.01})
        spec['drift_thresholds']={'feature:feature':{'ks_distance':.1}} if label=='multiclass' else {}
        result=workspace.analyze(spec,request_id='review-corrections-'+label)
        directory=output/'reports';directory.mkdir(exist_ok=True)
        for audience in ('local','shareable'):
            # Two representative PDFs only; unchanged historical reports stay untouched.
            export_pdf=pdf and audience=='local'
            result.generate_artifacts(directory/(label+'-'+audience+('.pdf' if export_pdf else '.html')),
                format='pdf' if export_pdf else 'html',audience=audience,
                json_path=directory/(label+'-'+audience+'.json'))
        metric_names=spec['material_thresholds']
        evidence.append({'task':label,'assessment':result.data['analysis_id'],'spec':spec,
                         'materiality':[m for e in result.data['history']['comparisons'] for m in e['metrics'] if m['metric'] in metric_names],
                         'class_ece_series':[v for v in result.data['history']['temporal'] if v['metric']=='frozen_bin_ece'],
                         'drift_prioritization':[{'field':d['field'],'prioritization':d['prioritization']} for d in result.data['history']['drift']],
                         'findings':result.data['findings']})
    assert all(workspace.open(aid).to_private_dict()==data for aid,data in original.items())
    assert all(hashlib.sha256((workspace.path/'objects'/name).read_bytes()).hexdigest()==value for name,value in retained.items())
    result={'status':'passed','original_assessments_unchanged':list(original),'retained_objects_unchanged':len(retained),
            'original_zip_sha256':hashlib.sha256(Path(original_zip).read_bytes()).hexdigest(),'affected_evidence':evidence,
            'qualification':'Synthetic declared drift threshold illustrates context-specific configuration, not a universal recommendation. No inference simulation or unrelated qualification rerun.'}
    (output/'corrections.json').write_text(json.dumps(result,indent=2)+'\n')
    return {'status':'passed','assessments':len(evidence),'original_assessments_preserved':len(original)}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--original-zip',required=True);p.add_argument('--out',required=True);p.add_argument('--no-pdf',action='store_true');a=p.parse_args()
    print(json.dumps(run(a.original_zip,a.out,pdf=not a.no_pdf),indent=2))
