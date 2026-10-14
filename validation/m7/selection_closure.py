"""Final pinned-model execution, isolated-fault projection, and review-pipeline evidence."""
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import socket
import time

import numpy as np
from PIL import Image, ImageDraw
from datatrust import *
from datatrust.contracts import AnalysisError
from datatrust.image_assets import perceptual_hash
from datatrust.image_models import registry
from validation.m7.benchmark import prepare, score_queries, metrics

ROOT=Path(__file__).parent


def run():
    out=ROOT/os.environ.get('M7_RESULT_DIR','results/release'); reports=out/'reports'; ledger={}
    profile=registry()['selection']; assert profile['status']=='passed'
    model=profile['default']['model']; directory=ROOT/'models'/model.split('/')[-1]
    data=ROOT/'data'
    spec=ImageAuditSpec((ImageInputSpec('data',ImageSourceSpec(str(data/'public_unlabeled.jsonl'),'jsonl',str(data))),),allowed_roots=(str(data.absolute()),))
    config=replace(ImageAnalysisConfig(),models=ImageModelOptions(str(directory)),limits=replace(ImageWorkLimits(),embedding_images=32,details=20))
    connect=socket.socket.connect
    def offline(*args,**kwargs): raise RuntimeError('Network disabled in M7 selection closure.')
    socket.socket.connect=offline
    try:
        result=DataTrust.audit_images(spec,config)
        assert result.coverage['families']['embeddings']['embedded']==32
        assert result.evidence[-1]['data']['model']['model']==model
        folder=reports/'model_release'; folder.mkdir(parents=True,exist_ok=True)
        a=result.generate_artifacts(folder/'review.pdf',format='pdf',json_path=folder/'analysis.json')
        ledger['model']={'model':model,'network':'disabled','model_directory_outside_dataset_root':True,'coverage':result.coverage,'execution':result.execution,'pdf':str(Path(a.pdf_path).relative_to(ROOT))}
        # Inject the native-worker failure boundary, retaining actual core/final integrity work.
        import datatrust.images as images
        supervise=images.run_supervised
        def isolated(operation,args,options,**kwargs):
            if operation.__name__=='execute_model': raise AnalysisError('Discarded private model failure',code='worker_terminated',stage='model')
            return supervise(operation,args,options,**kwargs)
        images.run_supervised=isolated
        try: partial=images.audit_images(spec,config)
        finally: images.run_supervised=supervise
        assert partial.execution['status']=='partial'
        assert not any(e['family']=='embeddings' for e in partial.evidence)
        folder=reports/'partial'; folder.mkdir(parents=True,exist_ok=True)
        a=partial.generate_artifacts(folder/'review.pdf',format='pdf',json_path=folder/'analysis.json')
        ledger['partial']={'fault':'injected isolated worker termination; real core and final verification','execution':partial.execution,'pdf':str(Path(a.pdf_path).relative_to(ROOT))}
    finally: socket.socket.connect=connect
    bounded=DataTrust.audit_images(spec,replace(ImageAnalysisConfig(),limits=replace(ImageWorkLimits(),posting_visits=1,hamming_comparisons=1)))
    assert bounded.execution['status']=='completed'
    assert bounded.coverage['families']['near_duplicates']['stop_reason']!='examined_scope_completed'
    folder=reports/'bounded'; folder.mkdir(parents=True,exist_ok=True)
    a=bounded.generate_artifacts(folder/'review.pdf',format='pdf',json_path=folder/'analysis.json')
    ledger['bounded']={'coverage':bounded.coverage,'pdf':str(Path(a.pdf_path).relative_to(ROOT))}
    # Exhaustive fixture reference search under the three-suggestion review setting.
    metadata=prepare(); vectors=np.load(ROOT/'results'/f'{model.split("/")[-1]}-vectors.npy')
    hashes=[]
    for item in metadata:
        with Image.open(item['path']) as im: hashes.append(perceptual_hash(im))
    pipeline={}; review_rows=[]
    for split in ('calibration','held_out'):
        references=[i for i,x in enumerate(metadata) if x['split']==split and x['method'] in {'reference','authored_distractor'}]
        rows=[]
        for row in score_queries(metadata,vectors,split):
            i=row['query']; ph=[j for j in references if i!=j and (hashes[i]^hashes[j]).bit_count()<=6]
            model_suggestions=[j for score,truth,j in row['top'] if score>=profile['default']['threshold']]
            suggestions=sorted(set(ph+model_suggestions),key=lambda j:(0 if j in ph else 1,(hashes[i]^hashes[j]).bit_count(),-float(vectors[i]@vectors[j]),j))[:3]
            entries=[(1.,metadata[i]['family'] is not None and metadata[i]['family']==metadata[j]['family'] and not row['no_copy'],j) for j in suggestions]
            rows.append(dict(row,top=entries))
            if split=='held_out' and entries: review_rows.append(dict(row,top=entries,ph=ph))
        pipeline[split]=metrics(rows,.5)
    ledger['review_pipeline']={'method':'exhaustive radius-six reference search, then calibrated encoder; deduplicate and retain three suggestions/query; self matches excluded','metrics':pipeline,'claim':'Pipeline held-out precision differs from encoder-only calibration; low-information perceptual confounds remain investigation candidates.'}
    # Inspect a fixed, diverse sample: transforms, useful model additions, and false candidates.
    sample=[]
    for method in ('jpeg','resize','brightness','crop10','rotation','padding','overlay','crop40','authored_distractor','reference'):
        row=next((r for r in review_rows if r['method']==method),None)
        if row: sample.append(row)
    sample+=next(([r] for r in review_rows if any(not t for s,t,j in r['top'])),[])
    sample+=next(([r] for r in review_rows if any(t and j not in r['ph'] for s,t,j in r['top'])),[])
    target=out/'model_inspection/private'; target.mkdir(parents=True,exist_ok=True)
    for part in range(0,len(sample),4):
        sheet=Image.new('RGB',(1100,1000),'white'); draw=ImageDraw.Draw(sheet)
        for n,row in enumerate(sample[part:part+4]):
            i=row['query']; j=row['top'][0][2]; y=n*250
            for column,index in enumerate((i,j)):
                with Image.open(metadata[index]['path']) as im:
                    im=im.convert('RGB'); im.thumbnail((520,210)); sheet.paste(im,(column*550,y+30))
            draw.text((10,y+8),f'{row["method"]}: query {i} / candidate {j}; known copy={row["top"][0][1]}; phash={j in row["ph"]}',fill='black')
        sheet.save(target/f'contact-{part//4+1}.jpg')
    ledger['internal_inspection']={'sample':[{'query':r['query'],'method':r['method'],'candidate':r['top'][0][2],'known_copy':r['top'][0][1]} for r in sample],'visual_review':'pending','private_contact_sheets':str(target.relative_to(ROOT))}
    (out/'selection_closure.json').write_text(json.dumps(ledger,indent=2,allow_nan=False)+'\n')
    print('Final model and failure/coverage artifacts verified',flush=True)


if __name__=='__main__': run()
