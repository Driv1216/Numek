"""Sparse append and repeated cutoff reconstruction against an existing synthetic corpus."""
import argparse,csv,json,time
from pathlib import Path
from confidenceguard import ReliabilityWorkspace
from .fixtures import specification


def run(root,output,count=100):
    root=Path(root);output=Path(output);output.mkdir(exist_ok=False,parents=True)
    ws=ReliabilityWorkspace(root/'workspace');before=ws.status()
    with ws.catalog._connect() as db:
        predictions={r['id']:(r['sha256'],r['bytes'],ws.catalog._object_path(r['id']).stat().st_mtime_ns) for r in db.execute("SELECT * FROM objects WHERE kind='prediction' AND state='active'")}
        query_plan=[list(row) for row in db.execute("EXPLAIN QUERY PLAN SELECT fact_digest FROM facts WHERE kind=? AND key=? AND revision=?",('prediction','example','initial'))]
    with (root/'inputs'/'predictions.csv').open() as stream:rows=[row for _,row in zip(range(count),csv.DictReader(stream))]
    path=output/'updates.csv'
    with path.open('w') as stream:
        writer=csv.DictWriter(stream,fieldnames=['id','outcome','revision','order','available','due']);writer.writeheader()
        for row in rows:writer.writerow({'id':row['id'],'outcome':str(1-int(row['outcome'])),'revision':'backfill-1','order':'1','available':'2027-03-01T00:00:00Z','due':row['due']})
    revision={'source':{'id':'updates','path':str(path)},'namespace':'synthetic-events','outcome_definition_version':'synthetic-outcome-v1','event_columns':['id'],
        'column':'outcome','revision_column':'revision','order_column':'order','available_at':{'column':'available'},'due_at':{'column':'due'}}
    start=time.monotonic();receipt=ws.update_outcomes(revision,request_id='sparse-qualification');seconds=time.monotonic()-start
    with ws.catalog._connect() as db:
        after={r['id']:(r['sha256'],r['bytes'],ws.catalog._object_path(r['id']).stat().st_mtime_ns) for r in db.execute("SELECT * FROM objects WHERE kind='prediction' AND state='active'")}
    assert predictions==after
    assessments=[]
    for cutoff in ('2026-06-01T00:00:00Z','2027-02-01T00:00:00Z','2027-04-01T00:00:00Z'):
        spec=specification(ws.models(),cohort=False);spec['as_of']=cutoff
        start=time.monotonic();result=ws.analyze(spec)
        assessments.append({'as_of':cutoff,'seconds':time.monotonic()-start,'scan':result.data['history']['materialization'],'execution':result.execution})
    result={'updates':count,'existing_predictions':before['facts']['prediction'],'append_seconds':seconds,'receipt':receipt,
        'prediction_objects_unchanged':True,'indexed_identity_query_plan':query_plan,'before':before,'after':ws.status(),'reconstructions':assessments}
    (output/'backfill.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--out',required=True);p.add_argument('--count',type=int,default=100);a=p.parse_args();run(a.root,a.out,a.count)
