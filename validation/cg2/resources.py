"""Measured CG2 operating probes; settings are not capacity promises."""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import time
from confidenceguard import study,EvaluationConfig,EvaluationError
from confidenceguard import compat
from confidenceguard.result import Inspection
from .fixtures import prepare


def spill_probe(config,*,progress=None):
    from confidenceguard.conformal import thresholds
    work=compat.workspace(config,512*1024**2,progress)
    try:
        if progress:progress({'owned_workspace':str(work.root),'stage':'exact_conformal_spill_probe'})
        # A permuted exact score relation forces external ORDER BY at low memory.
        work.con.execute('CREATE TABLE scores AS SELECT ((i*15485863)%10000019)::DOUBLE score FROM range(10000000) t(i)')
        values=thresholds(work.con,'scores',['0.5','0.9','0.999'],work.check)
        work.check('spill probe finalization')
        return Inspection({'thresholds':values,'scope':'CG2 exact order-statistic reducer on the shared supervised workspace'}, {'status':'completed','peak_workspace_bytes':work.peak})
    finally:work.close()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True);parser.add_argument('--only-spill',action='store_true');args=parser.parse_args()
    args.out.mkdir(parents=True,exist_ok=False);records=[]
    def save(): (args.out/'resources.json').write_text(json.dumps(records,indent=2,allow_nan=False))
    for label,kind,options in ([] if args.only_spill else [('ordinary','binary',{}),('wide-class','multiclass',{'classes':24}),('sample-heavy','regression',{'samples':200})]):
        start=time.monotonic();spec=prepare(args.out/label,kind,**options)
        result=study(spec)
        records.append({'case':label,'rows':1200,**options,'status':'completed','resources':result.execution,'wall_seconds':time.monotonic()-start})
        save()
    if not args.only_spill:
        spec=prepare(args.out/'adjusted-bootstrap','binary');spec['methods']=[{'id':'beta','kind':'beta','run':'original'}];spec.pop('selections');spec['comparisons']=[{'left':'original','right':'beta'}]
        spec['inference']={'mode':'independent_rows','metrics':['log_loss','brier'],'adjustment':'bonferroni','replicates':4000,'seed':42}
        result=study(spec);records.append({'case':'adjusted-bootstrap','status':'completed','resources':result.execution,'intervals':result.data['cg2']['inference']})
    save()
    config=EvaluationConfig(memory_bytes=32*1024**2,threads=1,max_seconds=180,free_disk_bytes=256*1024**2)
    try:
        result=compat.supervise(spill_probe,(config,),config)
        records.append({'case':'actual-spill','status':'completed','resources':result.execution,'result':result.data})
        assert result.execution['peak_spill_bytes']>0,'The probe must observe real spill, not merely a low-memory setting.'
    except Exception as exc:
        records.append({'case':'actual-spill','status':'failed','code':getattr(exc,'code',type(exc).__name__),'resources':getattr(exc,'execution',{})})
        save();raise
    try:
        if args.only_spill:compat.supervise(spill_probe,(config,),replace(config,max_rss_bytes=32*1024**2))
        else:study(spec,EvaluationConfig(max_rss_bytes=32*1024**2))
    except EvaluationError as exc:
        assert not getattr(exc,'execution',{}).get('completed_result_published',False)
        records.append({'case':'resource-stop','status':'expected_stop','code':exc.code,'resources':getattr(exc,'execution',{})})
    else:raise AssertionError('RSS probe did not stop.')
    (args.out/'resources.json').write_text(json.dumps(records,indent=2,allow_nan=False))
    print(json.dumps([{'case':v['case'],'status':v['status'],'spill_bytes':v.get('resources',{}).get('peak_spill_bytes')} for v in records]))

if __name__=='__main__':main()
