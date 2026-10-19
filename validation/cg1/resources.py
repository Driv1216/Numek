"""Reproducible local engineering probes, not capacity guarantees."""
import csv
import json
from pathlib import Path
import time
from confidenceguard import *

BASE=Path(__file__).resolve().parent


def main():
    out=BASE/'results/resources';out.mkdir(parents=True,exist_ok=True);results=[]
    for label,n,k,memory in [('ordinary_binary',10000,2,256*1024**2),('wide_spill_relevant',8000,48,64*1024**2)]:
        path=out/(label+'.csv');classes=[str(i) for i in range(k)]
        with path.open('w',newline='') as f:
            writer=csv.writer(f);writer.writerow(['id','y','prediction',*[f'p{i}' for i in range(k)]])
            for row in range(n):
                target=row%k;prediction=(target+1)%k if row%7==0 else target
                p=[.25/(k-1)]*k;p[prediction]=.75
                writer.writerow([row,target,prediction,*p])
        spec=EvaluationSpec(TaskDefinition('binary_classification' if k==2 else 'multiclass_classification','Synthetic engineering probe',classes=classes,positive_class='1' if k==2 else None),(SourceSpec('probe',str(path)),),(PredictionRunSpec('probe','probe',ModelIdentity('synthetic','v1'),key_columns=('id',),prediction='prediction',probabilities=ProbabilitySpec(columns={c:'p'+c for c in classes})),),OutcomeSpec('probe','y',('id',)))
        tick=time.monotonic()
        try:
            result=evaluate(spec,EvaluationConfig(memory_bytes=memory,max_seconds=600))
            a=result.generate_artifacts(out/(label+'.html'),json_path=out/(label+'.json'))
            results.append({'name':label,'rows':n,'classes':k,'probability_cells':n*k,'seconds':time.monotonic()-tick,'status':'completed','execution':result.execution,'protected_bytes':len(result.json_text().encode()),'shareable_bytes':len(json.dumps(result.to_dict()).encode()),'html_bytes':Path(a.html_path).stat().st_size})
        except EvaluationError as exc:results.append({'name':label,'rows':n,'classes':k,'status':'failed','code':exc.code,'execution':getattr(exc,'execution',{})})
    (BASE/'results/resources.json').write_text(json.dumps({'qualification':'Measured local shapes only. Spill-relevant does not mean spill was observed. No capacity ceiling established.','probes':results},indent=2)+'\n')
    print(json.dumps([{'name':r['name'],'status':r['status'],'spill':r.get('execution',{}).get('peak_spill_bytes'),'seconds':r.get('seconds')} for r in results]))


if __name__=='__main__':main()
