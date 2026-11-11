"""One finite, locked CPU method-integration campaign. No device speed claims."""
from dataclasses import replace
from pathlib import Path
import csv
import hashlib
import importlib.metadata
import json
import os
import time

import numpy as np
from confidenceguard import (TaskDefinition,PredictorSpec,OutputBinding,FeatureField,DecisionSpec,ExecutionSpec,
    SourceSpec,OutcomeSnapshotSpec,RoleSpec,AuxiliaryStudySpec,AuxiliaryCandidate,fit_auxiliary,assess_auxiliary)

ROOT=Path(__file__).resolve().parent
PROFILES={'scale':['histogram','mlp'],'quantiles':['histogram','mlp'],'failure_risk':['logistic','histogram','mlp']}
PROTOCOL={'schema':'cg6.cpu_positive_controls/1.0','seeds':[11,29,47,71,97],'profiles':PROFILES,
    'rows':5000,'roles':{'F':2000,'S':1000,'C':500,'E':1500},'candidate_parameters':'approved bounded defaults',
    'criteria':{'improved_seeds':4,'median_relative_improvement':.05},'comparison':'constant baseline on the same E roots',
    'primary_losses':{'scale':'scale_squared_error','quantiles':'pinball_loss','failure_risk':'brier'},
    'standing':'Designed learnable CPU method-integration controls; no dataset-wide or device-wide improvement promise',
    'scale_envelope':'y=Rademacher*(0.1+1.5*(x+1)^2)*abs(N(0,1)); primary point=0',
    'quantile_envelope':'y=4*x+(0.1+0.5*abs(x))*N(0,1); primary point=0',
    'risk_envelope':'P(y=no|x)=sigmoid(5*x); frozen primary always predicts yes',
    'resource_envelope':{'device':'cpu','max_seconds_per_service':180,'threads':2,'max_rss_bytes':6*1024**3}}


def write(path,value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n');path.chmod(0o600)


def data(kind,seed):
    root=ROOT/'results'/'positive-controls'/kind/str(seed);root.mkdir(parents=True,exist_ok=True)
    path=root/'inputs.csv';rng=np.random.Generator(np.random.PCG64(seed));x=rng.uniform(-1,1,PROTOCOL['rows'])
    if kind=='scale':y=rng.choice([-1.,1.],len(x))*(.1+1.5*(x+1)**2)*np.abs(rng.normal(size=len(x)))
    elif kind=='quantiles':y=4*x+(.1+.5*np.abs(x))*rng.normal(size=len(x))
    else:y=np.where(rng.random(len(x))<1/(1+np.exp(-5*x)),'no','yes')
    roles=['F']*2000+['S']*1000+['C']*500+['E']*1500
    with path.open('w',newline='') as out:
        writer=csv.writer(out);writer.writerow(['id','entity','x','y','role']);writer.writerows((i,i,float(v),label,r) for i,(v,label,r) in enumerate(zip(x,y,roles)))
    path.chmod(0o600)
    task=TaskDefinition('binary_classification','Synthetic failure event',classes=('no','yes'),positive_class='yes') if kind=='failure_risk' else TaskDefinition('regression','Synthetic response',units='synthetic units')
    outputs=(OutputBinding('probabilities',classes=('no','yes')),) if kind=='failure_risk' else (OutputBinding('point'),)
    predictor=PredictorSpec('primary',task,'constant',(FeatureField('x','x','float',role='model_input'),),outputs,
        architecture={'values':{'output':[.1,.9] if kind=='failure_risk' else 0.}},decision=DecisionSpec(rule='probability_argmax' if kind=='failure_risk' else 'none'),provenance={'training':'closed-form fixed reference; no fitted parameters'})
    namespace='cg6-positive-'+kind+'-'+str(seed)
    return ExecutionSpec((predictor,),(SourceSpec('input',str(path)),),'input',('id',),namespace,entity_columns=('entity',),
        outcomes=OutcomeSnapshotSpec('input','y',('id',)),roles=RoleSpec(namespace,column='role',unit='entity'))


def main():
    lock=ROOT/'positive_control_protocol.json'
    if lock.exists():
        if json.loads(lock.read_text())!=PROTOCOL:raise RuntimeError('Positive-control protocol differs from the frozen campaign')
    else:write(lock,PROTOCOL)
    result_path=ROOT/'results'/'positive-controls'/'receipt.json'
    if result_path.exists():raise RuntimeError('Campaign already has a receipt; reuse it or diagnose a documented defect')
    config={**PROTOCOL['resource_envelope'],'free_disk_bytes':1,'max_details':2}
    config.pop('device');config['max_seconds']=config.pop('max_seconds_per_service')
    records=[];started=time.monotonic()
    for kind,profiles in PROFILES.items():
        for seed in PROTOCOL['seeds']:
            s=data(kind,seed);baseline=None
            for family in ['constant',*profiles]:
                fitted=fit_auxiliary(AuxiliaryStudySpec(s,kind,'primary',candidates=(AuxiliaryCandidate(family,family,seed=seed),)),config)
                assessed=assess_auxiliary(s,fitted.private['auxiliary_artifacts'][0],config)
                metric=PROTOCOL['primary_losses'][kind]
                m=next(m for m in assessed.data['measurements'] if m['metric']==metric)
                if m['value_state']!='finite':raise RuntimeError('Positive-control objective is not finite')
                if family=='constant':baseline=m['value']
                record={'kind':kind,'seed':seed,'family':family,'loss':m['value'],'support':m['denominator'],'baseline':baseline,
                    'relative_improvement':None if family=='constant' else (baseline-m['value'])/baseline,
                    'artifact_digest':fitted.private['auxiliary_artifacts'][0]['artifact_digest'],'fit_binding':fitted.binding,'assessment_binding':assessed.binding}
                records.append(record);print(json.dumps({k:record[k] for k in ('kind','seed','family','loss','relative_improvement')}),flush=True)
                write(ROOT/'results'/'positive-controls'/kind/str(seed)/(family+'-receipt.json'),record)
    qualification=[]
    for kind,profiles in PROFILES.items():
        for family in profiles:
            values=[r['relative_improvement'] for r in records if r['kind']==kind and r['family']==family]
            count=sum(v>0 for v in values);median=float(np.median(values));passed=count>=4 and median>=.05
            qualification.append({'kind':kind,'family':family,'improved_seeds':count,'median_relative_improvement':median,'passed':passed})
    source={}
    for p in sorted((ROOT.parent.parent/'src'/'confidenceguard').rglob('*.py')):
        source[str(p.relative_to(ROOT.parent.parent))]=hashlib.sha256(p.read_bytes()).hexdigest()
    receipt={'protocol':PROTOCOL,'protocol_sha256':hashlib.sha256(lock.read_bytes()).hexdigest(),'records':records,'qualification':qualification,
        'passed':all(q['passed'] for q in qualification),'duration_seconds':time.monotonic()-started,'hardware_profile':'CG6-MAC-01 / CPU',
        'runtime':{p:importlib.metadata.version(p) for p in ('torch','scikit-learn','skops','numpy','safetensors')},'source_sha256':source}
    write(result_path,receipt)
    print(json.dumps({'passed':receipt['passed'],'qualification':qualification}),flush=True)
    if not receipt['passed']:raise SystemExit(1)


if __name__=='__main__':main()
