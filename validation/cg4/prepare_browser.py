"""Prepare synthetic-only evidence for reproducible CG4 browser/report verification."""
from pathlib import Path
import csv
import json
import sys

ROOT=Path(__file__).resolve().parents[2]


def main():
    sys.path.insert(0,str(ROOT/'tests/cg4'))
    from helpers import binary
    from confidenceguard import ReliabilityWorkspace,WorkspaceConfig
    directory=Path(__file__).with_name('browser_inputs_v2.nosync');directory.mkdir(exist_ok=True)
    spec=binary(directory)
    from dataclasses import replace
    from confidenceguard import ClockSpec
    path=directory/'predictions.csv'
    with path.open() as stream:values=list(csv.DictReader(stream))
    for row in values:row['when']='2026-01-01T00:00:00Z'
    with path.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=values[0]);writer.writeheader();writer.writerows(values)
    spec=replace(spec,evaluation=replace(spec.evaluation,runs=(replace(spec.evaluation.runs[0],prediction_at=ClockSpec('when')),)))
    (directory/'spec.json').write_text(json.dumps(spec.to_dict(),indent=2)+'\n')
    with (directory/'multiclass.csv').open('w',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['id','entity','y','decision','pa','pb','pc','x','role','when'])
        for i in range(720):
            x=(i//3)%2;y=(i//6)%3;prediction=(y+1)%3 if x else y
            probabilities=[.1,.1,.1];probabilities[prediction]=.8
            writer.writerow([i,i,'abc'[y],'abc'[prediction],*probabilities,x,('D','S','H')[i%3],'2026-01-01T00:00:00Z'])
    with (directory/'regression.csv').open('w',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['id','entity','y','point','lower','upper','x','role','when'])
        for i in range(720):
            x=(i//3)%2;y=float(i%13);point=y+(2 if x else -.5)
            writer.writerow([i,i,y,point,point-1,point+1,x,('D','S','H')[i%3],'2026-01-01T00:00:00Z'])
    path=directory/'workspace'
    if not path.exists():
        ws=ReliabilityWorkspace.initialize(path,WorkspaceConfig(saving=True,free_disk_bytes=1))
        ws.ingest({'evaluation':spec.evaluation.to_dict(),'namespace':spec.roles.namespace,'outcome_definition_version':'v1',
            'bindings':[{'run':'model'}],'feature_views':[v.to_dict() for v in spec.features],'schema_version':'confidenceguard.prediction_batch_spec/2.0'},request_id='synthetic-browser-batch')
    print(json.dumps({'data_root':str(directory),'workspace':str(path),'customer_evidence':False}))


if __name__=='__main__':main()
