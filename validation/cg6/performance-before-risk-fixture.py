"""Named-host finite workloads. Calibrate once, freeze admission, then measure."""
from dataclasses import replace
from pathlib import Path
import argparse,csv,hashlib,json,time,importlib.metadata,os
import numpy as np
from confidenceguard import (TaskDefinition,PredictorSpec,OutputBinding,FeatureField,ExecutionSpec,SourceSpec,OutcomeSnapshotSpec,RoleSpec,
    DeviceSpec,ExecutionLimits,ArtifactFile,DecisionSpec,execute_predictor,RobustnessSpec,ScenarioSpec,TransformationSpec,run_robustness,
    AuxiliaryStudySpec,AuxiliaryCandidate,fit_auxiliary,AttackSpec)
from confidenceguard.execution.adapters import torch_architecture

ROOT=Path(__file__).resolve().parent
CONFIG={'free_disk_bytes':1024**3,'threads':2,'max_rss_bytes':6*1024**3,'workspace_bytes':16*1024**3,
        'max_seconds':1800,'private_bytes':128*1024**2,'result_bytes':32*1024**2,'max_details':2}


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n');path.chmod(0o600)


def artifact(path):
    return ArtifactFile(path.name,str(path),hashlib.sha256(path.read_bytes()).hexdigest())


def numeric(directory,n,dim=50,device='cpu',hidden=(),classification=False):
    import torch
    from safetensors.torch import save_file
    directory.mkdir(parents=True,exist_ok=True);path=directory/'inputs.csv';rng=np.random.default_rng(731)
    with path.open('w',newline='') as out:
        w=csv.writer(out);w.writerow(['id','entity','role','batch',*[f'x{j}' for j in range(dim)],'y'])
        for i in range(n):
            x=rng.normal(size=dim);y=float(x[0]+.1*rng.normal()) if not classification else ('yes' if i%2 else 'no')
            w.writerow([i,i,('F','S','C','E')[i%4],i//100,*x,y])
    task=TaskDefinition('binary_classification','Synthetic benchmark target',classes=('no','yes'),positive_class='yes') if classification else TaskDefinition('regression','Synthetic benchmark target',units='synthetic')
    p=PredictorSpec('torch',task,'constant',tuple(FeatureField('x'+str(i),'x'+str(i),'float',role='model_input') for i in range(dim)),
        (OutputBinding('probabilities',classes=('no','yes'),activation='softmax'),) if classification else (OutputBinding('point'),),
        architecture={'kind':'mlp','input_dim':dim,'hidden':list(hidden),'output_dim':2 if classification else 1},decision=DecisionSpec(rule='probability_argmax' if classification else 'none'))
    torch.manual_seed(73);model=torch_architecture(p,{});weight=directory/'weights.safetensors';save_file(model.state_dict(),str(weight))
    p=replace(p,adapter='torch',files=(artifact(weight),),entry=weight.name)
    namespace='cg6-perf-'+directory.name
    return ExecutionSpec((p,),(SourceSpec('input',str(path)),),'input',('id',),namespace,entity_columns=('entity',),
        outcomes=OutcomeSnapshotSpec('input','y',('id',)),roles=RoleSpec(namespace,column='role',unit='entity'),device=DeviceSpec(device),
        limits=ExecutionLimits(cache_bytes=0,retained_rows=2))


def classical(s,directory):
    import skops.io as sio
    from sklearn.linear_model import LinearRegression
    m=LinearRegression();m.coef_=np.ones(len(s.predictors[0].inputs))/len(s.predictors[0].inputs);m.intercept_=0.;m.n_features_in_=len(m.coef_)
    m.feature_names_in_=np.asarray([f.column for f in s.predictors[0].inputs],dtype=object)
    path=directory/'reference.skops';sio.dump(m,path)
    return replace(s.predictors[0],id='classical',adapter='sklearn',preprocessing={},architecture={},entry=path.name,files=(artifact(path),),outputs=(OutputBinding('point','predict'),))


def modalities(directory,n,kind,device):
    from PIL import Image
    from tokenizers import Tokenizer,models,pre_tokenizers
    from safetensors.torch import save_file
    import torch
    s=numeric(directory,n,1,device,classification=True);p=s.predictors[0]
    rows=list(csv.DictReader(open(s.sources[0].path)))
    if kind=='text':
        tok=Tokenizer(models.WordLevel({'[UNK]':0,'[PAD]':1,'word':2},unk_token='[UNK]'));tok.pre_tokenizer=pre_tokenizers.Whitespace()
        f=directory/'tokenizer.json';tok.save(str(f));extra=(artifact(f),)
        for i,r in enumerate(rows):r['x0']='word '*255+str(i)
        pre={'kind':'text','tokenizer':f.name,'padding_id':1};arch={'kind':'text','vocabulary':3,'embedding_dim':64,'output_dim':2};field='text'
    else:
        extra=();rng=np.random.default_rng(219)
        for i,r in enumerate(rows):
            f=directory/('image-'+str(i)+'.png');Image.fromarray(rng.integers(0,256,(224,224,3),dtype=np.uint8)).save(f);r['x0']=f.name
        pre={'kind':'image','image_size':[224,224]};arch={'kind':'cnn','channels':3,'output_dim':2};field='asset'
    with open(s.sources[0].path,'w',newline='') as out:w=csv.DictWriter(out,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    p=replace(p,inputs=(FeatureField('x0','x0',field,role='model_input'),),preprocessing=pre,architecture=arch)
    torch.manual_seed(73);model=torch_architecture(p,{});f=directory/'modality.safetensors';save_file(model.state_dict(),str(f))
    return replace(s,predictors=(replace(p,files=(artifact(f),*extra),entry=f.name),))


def run_one(name,profile,directory,config):
    n=profile['rows'];device=profile.get('device','cpu');kind=profile['kind'];dim=profile.get('fields',50)
    if kind in {'text','image'}:s=modalities(directory,n,kind,device)
    else:s=numeric(directory,n,dim,device,profile.get('hidden',()),classification=profile.get('target')=='failure_risk' or kind=='capacity')
    if kind=='tabular':s=replace(s,predictors=(*s.predictors,classical(s,directory)))
    if kind=='auxiliary':
        target=profile['target'];p=s.predictors[0];base=replace(p,adapter='constant',files=(),entry=None,architecture={'values':{'output':[.1,.9] if target=='failure_risk' else 0.}},outputs=(OutputBinding('probabilities',classes=('no','yes')),) if target=='failure_risk' else (OutputBinding('point'),))
        s=replace(s,predictors=(base,))
    source_root=ROOT.parents[1]/'src'
    def source_map():return {str(p.relative_to(source_root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(source_root.rglob('*')) if p.is_file() and p.suffix in {'.py','.js','.html','.css','.json'}}
    frozen_source=source_map()
    before={'load_average':list(os.getloadavg()),'free_disk_bytes':__import__('shutil').disk_usage(directory).free};started=time.monotonic()
    if kind=='auxiliary':
        candidate=AuxiliaryCandidate(profile['family'],profile['family'],parameters=profile.get('parameters',{}))
        result=fit_auxiliary(AuxiliaryStudySpec(s,profile['target'],'torch',candidates=(candidate,),quantile_rearrange=profile.get('quantile_rearrange',False)),config)
    elif kind in {'tabular','streaming'}:
        scenarios=tuple(ScenarioSpec('scenario_'+str(i),(TransformationSpec('noise','noise',('x0',),parameters={'scale':.1*(i+1)}),),outcome_relation='label_preserving',outcome_reason='Synthetic measurement corruption benchmark') for i in range(profile['scenarios']))
        result=run_robustness(RobustnessSpec(s,scenarios),config)
    elif kind=='capacity':
        from confidenceguard import (as_reliability_spec,FeatureViewSpec,PolicyInputSpec,PolicySpec,PolicyApplicationSpec,PolicyMetricSpec,replay_policy,PolicyStressSpec,stress_policy)
        from confidenceguard.contracts import digest
        from confidenceguard.sources import key
        s=replace(s,context_fields=(FeatureField('batch','batch','categorical'),),batch_columns=('batch',))
        completed=execute_predictor(s,config);bridge=as_reliability_spec(completed,directory=directory/'bridge')
        members={str(i//100):[key({'id':str(j)},('id',),None) for j in range(i,min(i+100,n))] for i in range(0,n,100)}
        batches=({'id':'day','field':'batch.id','closed_at':'2026-11-07T00:00:00Z','members':{k:{'count':len(v),'digest':digest(sorted(v))} for k,v in members.items()}},)
        features=(FeatureViewSpec('batch',(FeatureField('id','batch','categorical'),),availability='at_decision'),)
        inp=PolicyInputSpec(bridge.roles,evaluation=bridge.evaluation,features=features,batches=batches)
        nodes={'root':{'kind':'capacity','batch':'day','ranking':{'kind':'probability','target':'yes'},'budget':50,'admitted':'yes','overflow':'skip'},
               'yes':{'kind':'action','action':{'kind':'label','label':'yes'}},'skip':{'kind':'action','action':{'kind':'abstain'}}}
        policy=PolicySpec(s.task,'torch',nodes,'root',{'kind':'abstain'},{'kind':'unavailable'})
        application=PolicyApplicationSpec(inp,policy,metrics=(PolicyMetricSpec('issued','issued_coverage',basis='operational'),),role='all')
        bound=replay_policy(application,config);application=replace(application,policy=PolicySpec.from_dict(next(iter(bound.private['policies'].values()))))
        scenarios=tuple(ScenarioSpec('shift_'+str(i),(TransformationSpec('noise','noise',('x0',),parameters={'scale':.1*(i+1)}),)) for i in range(3))
        result=stress_policy(PolicyStressSpec(RobustnessSpec(s,scenarios),application.to_dict(),'batch'),config)
    elif kind=='attacks':
        scenario=ScenarioSpec('search',attack=AttackSpec('pgd',('x0',),access='white_box',epsilon=.1,steps=40,restarts=5,queries_per_root=250))
        result=run_robustness(RobustnessSpec(s,(scenario,)),config)
    else:result=execute_predictor(s,config)
    elapsed=time.monotonic()-started
    if source_map()!=frozen_source:raise RuntimeError('Source changed during measurement; this run cannot qualify final-source performance')
    record={'name':name,'profile':profile,'hardware':'CG6-MAC-01','before':before,'elapsed_seconds':elapsed,'execution':result.execution,
        'devices':result.data['cg6'].get('devices',{}),'binding':result.binding,'output_records':result.data['coverage']['complete_output_records'],
        'output_bytes':(result.private.get('output_artifact') or {}).get('bytes',0),'loaded_models':len(s.predictors),'source_sha256':frozen_source,
        'execution_spec':s.to_dict(),'concurrent_load_policy':'Recorded host load; no parallel numerical qualification campaign during measured acceptance'}
    record['passed']=elapsed<=profile.get('elapsed_seconds',config['max_seconds']) and result.execution['peak_worker_rss_bytes']<=config['max_rss_bytes']
    write(directory/'receipt.json',record);print(json.dumps({'name':name,'elapsed_seconds':elapsed,'passed':record['passed']}),flush=True);return record


def main():
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['calibrate','measure']);parser.add_argument('--name');args=parser.parse_args()
    calibration=ROOT/'results'/'performance-calibration'
    if args.mode=='calibrate':
        receipt=calibration/'receipt.json'
        if receipt.exists():raise RuntimeError('The one bounded calibration pass already exists; reuse it')
        profiles={'tabular':{'kind':'tabular','rows':500,'fields':50,'scenarios':1},'device-cpu':{'kind':'device','rows':1000,'fields':128,'hidden':[512,512]},'device-mps':{'kind':'device','rows':1000,'fields':128,'hidden':[512,512],'device':'mps'},'auxiliary':{'kind':'auxiliary','target':'scale','rows':1000,'fields':50,'family':'mlp','parameters':{'epochs':5,'patience':3}}}
        values=[run_one(k,p,calibration/k,{**CONFIG,'max_seconds':180}) for k,p in profiles.items()]
        write(receipt,{'hardware':'CG6-MAC-01','purpose':'one bounded admission calibration; not workload acceptance','records':values});return
    protocol=json.loads((ROOT/'performance_protocol.json').read_text());records=[]
    for name,p in protocol['profiles'].items():
        if args.name and args.name!=name:continue
        directory=ROOT/'results'/'performance'/name
        if (directory/'receipt.json').exists():raise RuntimeError('Existing measured receipt must be reused or addressed by a documented targeted correction')
        record=run_one(name,p,directory,protocol['config']);record['protocol_sha256']=hashlib.sha256((ROOT/'performance_protocol.json').read_bytes()).hexdigest();write(directory/'receipt.json',record);records.append(record)
    if not records:raise RuntimeError('No admitted workload selected')
    if not all(r['passed'] for r in records):raise SystemExit(1)

if __name__=='__main__':main()
