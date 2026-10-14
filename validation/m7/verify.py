"""M7 public populations, offline execution and representative canonical artifacts."""
from dataclasses import replace
import hashlib
import os
import json
from pathlib import Path
import platform
import socket
import tempfile
import time
import zipfile

import numpy as np
from PIL import Image
from datatrust import *
from datatrust.image_models import registry

ROOT=Path(__file__).parent


def sha(path):
    with Path(path).open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()


def run():
    data=ROOT/'data'; out=ROOT/os.environ.get('M7_RESULT_DIR','results'); reports=out/'reports'; reports.mkdir(parents=True,exist_ok=True)
    natural=json.loads((data/'natural_manifest.json').read_text())
    for item in natural['images']: assert sha(data/item['path'])==item['sha256']
    selected={x['id'] for x in natural['images']}
    with zipfile.ZipFile(data/'annotations_trainval2017.zip') as archive: original=json.loads(archive.read('annotations/instances_val2017.json'))
    prepared=dict(original,images=[x for x in original['images'] if x['id'] in selected],annotations=[x for x in original['annotations'] if x['image_id'] in selected])
    coco=data/'coco_subset.json'
    if not coco.exists(): coco.write_text(json.dumps(prepared)+'\n')
    manifest=data/'public_unlabeled.jsonl'; manifest.write_text(''.join(json.dumps({'path':x['path'],'id':str(x['id'])})+'\n' for x in natural['images']))
    labelled=data/'public_multilabel.jsonl'
    categories={i:sorted({a['category_id'] for a in prepared['annotations'] if a['image_id']==i}) for i in selected}
    labelled.write_text(''.join(json.dumps({'path':x['path'],'id':str(x['id']),'labels':categories[x['id']]})+'\n' for x in natural['images']))
    cases={
        'unlabeled':ImageInputSpec('data',ImageSourceSpec(str(manifest),'jsonl',str(data)),mapping=ImageMappingSpec(logical_id='id')),
        'multilabel':ImageInputSpec('data',ImageSourceSpec(str(labelled),'jsonl',str(data)),ImageTaskSpec('multilabel_classification'),ImageMappingSpec(logical_id='id')),
        'detection':ImageInputSpec('data',ImageSourceSpec(str(coco),'coco',str(data)),ImageTaskSpec('detection')),
        'segmentation':ImageInputSpec('data',ImageSourceSpec(str(coco),'coco',str(data)),ImageTaskSpec('segmentation')),
    }
    ledger={'status':'running','platform':platform.platform(),'python':platform.python_version(),'cases':{},'historical_reuse':'M1–M6 source/data/artifacts preserved; classification and archive verifiers and repository tests cover shared seams.'}
    completed={}
    for name,item in cases.items():
        spec=ImageAuditSpec((item,),allowed_roots=(str(ROOT.absolute()),),dataset_name=f'{name.title()} image evidence')
        tick=time.monotonic()
        existing=reports/name/'analysis.json'
        if existing.exists():
            payload=json.loads(existing.read_text()); private_path=next((reports/name/'.datatrust-private').glob('*/manifest.json'))
            private=json.loads(private_path.read_text()); profile=dict(payload['profile'])
            for key in ['examples','disclosure','export_identity']: profile.pop(key,None)
            result=ImageAuditResult(profile,payload['checks'],payload['evidence'],payload['findings'],payload['coverage'],payload['execution'],payload['generated_at'],private)
        else: result=DataTrust.audit_images(spec)
        assert result.profile['occurrences']==len(natural['images'])
        assert str(data.absolute()) not in result.json_text()
        if name in {'detection','segmentation'}:
            annotation=next(x['data'] for x in result.evidence if x['family']=='annotations')
            assert annotation['object_visits']==len(prepared['annotations'])
        directory=reports/name; directory.mkdir(mode=0o700,exist_ok=True)
        artifacts=ImageReportArtifacts(html_path=str(directory/'review.html'),pdf_path=str(directory/'review.pdf'),json_path=str(existing),qa_metadata={}) if existing.exists() else result.generate_artifacts(directory/'review.pdf',format='pdf',json_path=directory/'analysis.json')
        ledger['cases'][name]={'seconds':time.monotonic()-tick,'occurrences':len(natural['images']),'execution':result.execution,'coverage':result.coverage,'html_sha256':sha(artifacts.html_path),'pdf_sha256':sha(artifacts.pdf_path),'json_sha256':sha(artifacts.json_path),'qa':artifacts.qa_metadata}
        completed[name]=result
        print(name,'verified',flush=True)
    # Classification uses an explicit supplied categorical outcome; these categories are derived fixture context, not ground-truth scene labels.
    classification=data/'classification.jsonl'; classification.write_text(''.join(json.dumps({'path':x['path'],'labels':str(categories[x['id']][0]) if categories[x['id']] else 'no_supplied_objects'})+'\n' for x in natural['images']))
    item=ImageInputSpec('classification',ImageSourceSpec(str(classification),'jsonl',str(data)),ImageTaskSpec('classification'))
    result=DataTrust.audit_images(ImageAuditSpec((item,),allowed_roots=(str(ROOT.absolute()),)))
    directory=reports/'classification'; directory.mkdir(mode=0o700,exist_ok=True); a=result.generate_artifacts(directory/'final.pdf',format='pdf',json_path=directory/'final.json')
    ledger['cases']['classification']={'occurrences':result.profile['occurrences'],'pdf_sha256':sha(a.pdf_path),'coverage':result.coverage}
    # Controlled source overlap and version change, with explicit logical keys and frame mismatch.
    with tempfile.TemporaryDirectory(dir=data) as temp:
        root=Path(temp)
        for name in ['a','b']:
            p=root/name; p.mkdir(); Image.new('RGB',(40,24) if name=='a' else (80,48),'red').save(p/'image.png')
            (p/'manifest.jsonl').write_text(json.dumps({'id':'sample','path':'image.png','objects':[{'category':1,'bbox':[2,3,12,15] if name=='a' else [4,6,24,30]}]})+'\n')
        inputs=tuple(ImageInputSpec(name,ImageSourceSpec(str(root/name/'manifest.jsonl'),'jsonl',str(root/name)),ImageTaskSpec('detection'),ImageMappingSpec(logical_id='id')) for name in ['a','b'])
        spec=ImageAuditSpec(inputs,comparisons=(ImageComparisonSpec('a','b'),),allowed_roots=(str(ROOT.absolute()),))
        result=DataTrust.audit_images(spec); evidence=next(x['data'] for x in result.evidence if x['family']=='versions')
        assert evidence['changes']['annotation_payload_changes_blocked']==1
        directory=reports/'comparison'; directory.mkdir(mode=0o700,exist_ok=True); a=result.generate_artifacts(directory/'final.pdf',format='pdf',json_path=directory/'final.json')
        ledger['cases']['comparison']={'pdf_sha256':sha(a.pdf_path),'evidence':evidence,'source_deleted_after_validation':True}
    # Explicit local examples are a separate variant of completed evidence.
    result=completed['segmentation']; refs=tuple(ref for ref,loc in result.private['locators'].items() if loc.get('normalized',{}).get('comparable') and loc.get('normalized',{}).get('task')=='segmentation')[:2]
    directory=reports/'disclosed'; directory.mkdir(mode=0o700,exist_ok=True)
    a=result.generate_artifacts(directory/'review.pdf',format='pdf',json_path=directory/'analysis.json',disclosure=ImageDisclosureOptions(refs,True),allowed_roots=(str(ROOT.absolute()),))
    ledger['cases']['disclosed']={'pdf_sha256':sha(a.pdf_path),'examples':len(refs)}
    # Actual model-enabled audit with network sockets forbidden.
    profile=registry()['selection']; assert profile['status']=='passed'
    model=ROOT/'models'/profile['default']['model'].split('/')[-1]
    original_connect=socket.socket.connect
    def offline(*args,**kwargs): raise RuntimeError('Network disabled in offline M7 audit validation.')
    socket.socket.connect=offline
    try:
        config=replace(ImageAnalysisConfig(),models=ImageModelOptions(str(model)),limits=replace(ImageWorkLimits(),embedding_images=32,details=20))
        spec=ImageAuditSpec((cases['unlabeled'],),allowed_roots=(str(ROOT.absolute()),))
        result=DataTrust.audit_images(spec,config)
        assert result.coverage['families']['embeddings']['embedded']>0
    finally: socket.socket.connect=original_connect
    directory=reports/'model'; directory.mkdir(mode=0o700,exist_ok=True); a=result.generate_artifacts(directory/'review.pdf',format='pdf',json_path=directory/'analysis.json')
    ledger['cases']['model']={'pdf_sha256':sha(a.pdf_path),'execution':result.execution,'coverage':result.coverage,'network':'disabled'}
    ledger['status']='passed'; (out/'verification.json').write_text(json.dumps(ledger,indent=2,allow_nan=False)+'\n')
    print('M7 validation passed',flush=True)


if __name__=='__main__': run()
