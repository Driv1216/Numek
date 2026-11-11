"""One-gate synthetic browser input for zero-pair overlap/identity reporting."""
import csv
import hashlib
import json
from pathlib import Path


def main():
    parent=Path(__file__).resolve().parent/'browser_inputs_v2.nosync'
    target=parent/'overlap-workflow-v1'
    if target.exists():raise RuntimeError('Preserve the original synthetic fixture.')
    target.mkdir()
    path=target/'predictions.csv'
    with path.open('w',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['id','entity','y','decision','p','hot','role','when'])
        for i in range(720):
            hot=(i//3)%2;y=(i//6)%2;decision=y^hot
            writer.writerow([str(i),str(i),str(y),str(decision),'.8' if decision else '.2',
                'true' if hot else 'false',('D','S','H')[i%3],'2026-01-01T00:00:00Z'])
    spec=json.loads((parent/'spec.json').read_text());spec['evaluation']['sources'][0]['path']=str(path)
    spec.update(name='CG4 zero-pair overlap and exact-gate evidence',representations=[],strategies=['structured'],
        features=[{'id':'context','availability':'at_decision','fields':[{'id':'hot','column':'hot','kind':'boolean','role':'context'}]}])
    spec['roles']['namespace']='cg4-browser-overlap-workflow-v1';spec['limits'].update(max_depth=1,stability_replicates=1)
    (target/'spec.json').write_text(json.dumps(spec,indent=2)+'\n')
    manifest={'customer_evidence':False,'purpose':'Zero-pair union support, exact definition fidelity and export workflow only; not recovery qualification.',
        'temporal_availability':'Synthetic caller declaration; not real acquisition-clock evidence.',
        'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in target.iterdir() if p.is_file()}}
    (target/'input-manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    print(str(target))


if __name__=='__main__':main()
