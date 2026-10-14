"""Fixed offline CPU benchmark: family-disjoint calibration, burden, and held-out recall."""
from dataclasses import replace
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import socket
import time

import numpy as np
from PIL import Image,ImageEnhance,ImageDraw,ImageOps
import psutil
from datatrust import ImageModelOptions
from datatrust.image_models import MODELS,preflight,load_encoder,encode
from datatrust.image_assets import perceptual_hash

ROOT=Path(__file__).parent


def prepare():
    manifest=json.loads((ROOT/'data/natural_manifest.json').read_text())
    directory=ROOT/'data/benchmark'; directory.mkdir(exist_ok=True)
    metadata=[]
    methods=['jpeg','resize','brightness','crop10','rotation','padding','overlay','crop40']
    for i,item in enumerate(manifest['images']):
        with Image.open(ROOT/'data'/item['path']) as source: original=ImageOps.exif_transpose(source).convert('RGB'); original.thumbnail((512,512))
        variants=[('reference',original)]
        w,h=original.size
        for method in methods:
            image=original.copy()
            if method=='resize': image=image.resize((max(1,w//2),max(1,h//2)))
            elif method=='brightness': image=ImageEnhance.Brightness(image).enhance(.7)
            elif method=='crop10': image=image.crop((w//10,h//10,w-w//10,h-h//10))
            elif method=='crop40': image=image.crop((w//5,h//5,w-w//5,h-h//5))
            elif method=='rotation': image=image.transpose(Image.Transpose.ROTATE_90)
            elif method=='padding': image=ImageOps.expand(image,border=max(w,h)//8,fill=(128,128,128))
            elif method=='overlay': ImageDraw.Draw(image).rectangle((0,h*.8,w*.3,h),fill='white')
            variants.append((method,image))
        for method,image in variants:
            path=directory/f'{i:03d}-{method}.jpg'
            if not path.exists(): image.save(path,quality=50 if method=='jpeg' else 90)
            metadata.append({'path':str(path),'family':i,'method':method,'split':item['split']})
    rng=np.random.default_rng(731)
    while len(metadata)<2000:
        i=len(metadata); ordinal=i-1152; path=directory/(f'authored-v2-{i}.png' if ordinal<64 else f'authored-{i}.png')
        if not path.exists():
            # Authored distractors include structure, flat areas and repeated motifs, not just noise.
            array=rng.integers(0,256,(128,128,3),dtype=np.uint8)
            if ordinal<32:
                array[:]=[(ordinal*41)%256,(ordinal*73)%256,(ordinal*19)%256]; image=Image.fromarray(array)
            elif i%3:
                array[:]=rng.integers(0,256,3)
                image=Image.fromarray(array); draw=ImageDraw.Draw(image)
                for _ in range(8):
                    x,y=rng.integers(0,100,2); draw.rectangle((int(x),int(y),int(x+20),int(y+20)),fill=tuple(map(int,rng.integers(0,256,3))))
            else: image=Image.fromarray(array)
            image.save(path)
        metadata.append({'path':str(path),'family':None,'method':'authored_distractor','split':'calibration' if ordinal%2==0 else 'held_out','control':'blank' if ordinal<32 else 'repeated_motif' if i%3 else 'noise'})
    return metadata


def score_queries(metadata,vectors,split):
    references=[i for i,x in enumerate(metadata) if x['split']==split and x['method'] in {'reference','authored_distractor'}]
    queries=[i for i,x in enumerate(metadata) if x['family'] is not None and x['split']==split and x['method']!='reference']
    natural=[i for i,x in enumerate(metadata) if x['split']==split and x['method']=='reference']
    reference_matrix=vectors[references]; entries=[]
    controls=[i for i,x in enumerate(metadata) if x['split']==split and x['method']=='authored_distractor']
    for index in queries+natural+controls:
        scores=reference_matrix@vectors[index]
        truth=[metadata[r]['family']==metadata[index]['family'] and metadata[r]['family'] is not None for r in references]
        no_copy=index in natural or index in controls
        if no_copy: scores=np.where(np.array(truth)|(np.array(references)==index),-2,scores); truth=[False]*len(truth)
        order=np.argsort(-scores,kind='stable')[:3]
        entries.append({'query':index,'method':metadata[index]['method'],'no_copy':no_copy,'top':[(float(scores[j]),bool(truth[j]),references[j]) for j in order]})
    return entries


def metrics(entries,threshold):
    tp=fp=0; recalls={}; no_copy=0; false_no_copy=0; details=[]
    for row in entries:
        retained=[(s,t,j) for s,t,j in row['top'] if s>=threshold]
        tp+=sum(t for s,t,j in retained); fp+=sum(not t for s,t,j in retained)
        if row['no_copy']: no_copy+=1; false_no_copy+=sum(not t for s,t,j in retained)
        else: recalls.setdefault(row['method'],[]).append(any(t for s,t,j in retained))
        if len(details)<200: details.append({'query':row['query'],'no_copy':row['no_copy'],'retained':retained})
    recall={k:float(np.mean(v)) for k,v in recalls.items()}
    return {'macro_recall':float(np.mean(list(recall.values()))) if recall else 0,'recall_by_transform':recall,'precision':tp/(tp+fp) if tp+fp else 1.,'false_suggestions_per_100_no_copy_queries':100*false_no_copy/max(1,no_copy),'true_candidates':tp,'false_candidates':fp,'no_copy_queries':no_copy,'inspection_sample':details}


def run():
    metadata=prepare(); out=ROOT/'results'; out.mkdir(exist_ok=True)
    original_connect=socket.socket.connect
    def offline(*args,**kwargs): raise RuntimeError('Network disabled during M7 benchmark.')
    results={}; process=psutil.Process(); baseline={}
    hashes=[]
    for item in metadata:
        with Image.open(item['path']) as image: hashes.append(perceptual_hash(image))
    for split in ['calibration','held_out']:
        positives=[(i,x) for i,x in enumerate(metadata) if x['split']==split and x['method'] not in {'reference','authored_distractor'}]
        matches={x['family']:j for j,x in enumerate(metadata) if x['split']==split and x['method']=='reference'}
        recalls={}
        for i,item in positives: recalls.setdefault(item['method'],[]).append((hashes[i]^hashes[matches[item['family']]]).bit_count()<=6)
        baseline[split]={k:float(np.mean(v)) for k,v in recalls.items()}
    socket.socket.connect=offline
    try:
        for model in MODELS:
            root=ROOT/'models'/model.split('/')[-1]
            provenance=preflight(ImageModelOptions(str(root)),benchmark=True)
            started=time.monotonic(); processor,encoder=load_encoder(provenance,2); load_seconds=time.monotonic()-started
            vectors=[]; peak=process.memory_info().rss
            for begin in range(0,len(metadata),8):
                images=[]
                for item in metadata[begin:begin+8]:
                    with Image.open(item['path']) as image: images.append(image.convert('RGB'))
                vectors.extend(encode(processor,encoder,images,provenance)); peak=max(peak,process.memory_info().rss)
                if begin%256==0: print(model,begin,'/',len(metadata),flush=True)
            vectors=np.stack(vectors)
            cold_seconds=time.monotonic()-started
            with Image.open(metadata[0]['path']) as image: probe=image.convert('RGB')
            repeat=encode(processor,encoder,[probe],provenance)[0]
            repeat_error=float(np.max(np.abs(repeat-vectors[0])))
            if repeat_error>1e-6: raise AssertionError('Embedding repeat-run stability failed.')
            calibration=score_queries(metadata,vectors,'calibration'); thresholds=sorted({1.000001}|{s for r in calibration for s,t,j in r['top']})
            candidates=[(metrics(calibration,t),t) for t in thresholds]
            eligible=[(m,t) for m,t in candidates if m['precision']>=.95 and m['false_suggestions_per_100_no_copy_queries']<=5]
            calibrated,threshold=max(eligible,key=lambda pair:(pair[0]['macro_recall'],-pair[0]['false_candidates'],pair[1]))
            held=metrics(score_queries(metadata,vectors,'held_out'),threshold)
            baseline_macro=float(np.mean(list(baseline['held_out'].values())))
            # Repeated-copy baseline union is measured independently of encoder threshold.
            references={x['family']:j for j,x in enumerate(metadata) if x['split']=='held_out' and x['method']=='reference'}
            union={}; useful_new=0
            for row in score_queries(metadata,vectors,'held_out'):
                if row['no_copy']: continue
                item=metadata[row['query']]; p=(hashes[row['query']]^hashes[references[item['family']]]).bit_count()<=6
                v=any(s>=threshold and t for s,t,j in row['top']); union.setdefault(item['method'],[]).append(p or v); useful_new+=v and not p
            union_macro=float(np.mean([np.mean(v) for v in union.values()]))
            results[model]={'revision':MODELS[model],'threshold':threshold,'images':len(metadata),'cold_seconds':cold_seconds,'load_seconds':load_seconds,'peak_rss_bytes':peak,'artifact_bytes':sum(v['bytes'] for v in provenance['files'].values()),'repeat_max_abs_error':repeat_error,'calibration':calibrated,'held_out':held,'perceptual_baseline_macro':baseline_macro,'pipeline_union_macro':union_macro,'useful_new_copies':useful_new,'practical_default':cold_seconds<=600 and peak<=4*1024**3,'practical_higher_quality':cold_seconds<=1200 and peak<=6*1024**3,'held_out_burden_passed':held['precision']>=.9 and held['false_suggestions_per_100_no_copy_queries']<=10,'artifact_hashes':{k:v['sha256'] for k,v in provenance['files'].items()}}
            np.save(out/f'{model.split("/")[-1]}-vectors.npy',vectors)
            (out/'model_benchmark.json').write_text(json.dumps({'status':'running','models':results,'baseline':baseline,'platform':platform.platform(),'python':platform.python_version()},indent=2)+'\n')
            del encoder,processor,vectors
            import gc; gc.collect()
            print(model,'completed',round(cold_seconds,2),held['macro_recall'],held['precision'],flush=True)
    finally: socket.socket.connect=original_connect
    eligible=[(name,r) for name,r in results.items() if r['practical_default'] and r['held_out_burden_passed'] and r['useful_new_copies']>0]
    selection={'status':'blocked','reason':'No practical model demonstrated benefit at the held-out review burden.'}
    if eligible:
        best=max(r['held_out']['macro_recall'] for _,r in eligible)
        name,default=min([(n,r) for n,r in eligible if r['held_out']['macro_recall']>=best-.01],key=lambda pair:(pair[1]['held_out']['false_candidates'],pair[1]['cold_seconds'],pair[1]['peak_rss_bytes'],pair[1]['artifact_bytes']))
        selection={'status':'passed','default':{'model':name,'threshold':default['threshold']}}
        better=[(n,r) for n,r in results.items() if r['practical_higher_quality'] and r['held_out_burden_passed'] and r['held_out']['macro_recall']>=default['held_out']['macro_recall']+.03 and r['held_out']['false_candidates']<=default['held_out']['false_candidates']]
        if better:
            n,r=max(better,key=lambda pair:pair[1]['held_out']['macro_recall']); selection['higher_quality']={'model':n,'threshold':r['threshold']}
    registry_path=Path(__file__).parents[2]/'src/datatrust/image_model_artifacts.json'; registry=json.loads(registry_path.read_text()); registry['selection']=selection; registry_path.write_text(json.dumps(registry,indent=2)+'\n')
    fixture_hashes={Path(x['path']).name:hashlib.sha256(Path(x['path']).read_bytes()).hexdigest() for x in metadata}
    ledger={'fixture_sha256':hashlib.sha256(json.dumps(fixture_hashes,sort_keys=True).encode()).hexdigest(),'fixture_files':fixture_hashes,'status':selection['status'],'selection':selection,'models':results,'baseline':baseline,'platform':platform.platform(),'python':platform.python_version(),'cpu_threads':2,'network':'disabled during model execution','population':'128 COCO natural families, 1024 transformed derivatives, 848 authored distractors; first 64 natural families calibration, next 64 held-out; authored controls partitioned between calibration/evaluation and queried without self matches; 32 blank controls plus repeated motifs/noise. Calibration uses 95% precision/5 false per 100 after retained natural-only burden failure','claim':'Fixture-specific internal candidate calibration, not production recall or semantic correctness.'}
    (out/'model_benchmark.json').write_text(json.dumps(ledger,indent=2)+'\n'); print(json.dumps(selection),flush=True)


if __name__=='__main__': run()
