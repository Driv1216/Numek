"""Scoped large-raster, annotation-heavy and semantic-mask CPU measurements."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import time
import numpy as np
from PIL import Image
from datatrust import *

ROOT=Path(__file__).parent


def run():
    ledger={}
    with tempfile.TemporaryDirectory(prefix='numek-m7-resources-') as temp:
        root=Path(temp)
        large=root/'large'; large.mkdir()
        Image.new('RGB',(7168,4096),'#527694').save(large/'large.png')
        masks=root/'masks'; masks.mkdir()
        for i in range(50):
            Image.new('RGB',(256,256),(i*3%256,i*5%256,i*7%256)).save(masks/f'image-{i}.png')
            mask=np.zeros((256,256),dtype=np.uint16); mask[20:100+i,30:120+i]=i+1
            Image.fromarray(mask).save(masks/f'mask-{i}.png')
        (masks/'manifest.jsonl').write_text(''.join(json.dumps({'path':f'image-{i%50}.png','mask':f'mask-{i%50}.png'})+'\n' for i in range(500)))
        coco=root/'coco'; coco.mkdir()
        Image.new('RGB',(640,400),'#75a5c5').save(coco/'sample.png')
        payload={'images':[{'id':i,'file_name':'sample.png','width':640,'height':400} for i in range(40)],'categories':[{'id':i,'name':f'category-{i}'} for i in range(8)],'annotations':[{'id':i,'image_id':i//100,'category_id':i%8,'bbox':[float(i%500),float(i%250),10.,20.]} for i in range(4000)]}
        (coco/'instances.json').write_text(json.dumps(payload)+'\n')
        cases={
            'large_raster':ImageInputSpec('large',ImageSourceSpec(str(large))),
            'semantic_16bit_masks':ImageInputSpec('masks',ImageSourceSpec(str(masks/'manifest.jsonl'),'jsonl',str(masks)),ImageTaskSpec('segmentation'),annotations=ImageAnnotationSpec(categories=tuple(range(51)))),
            'annotation_heavy':ImageInputSpec('coco',ImageSourceSpec(str(coco/'instances.json'),'coco',str(coco)),ImageTaskSpec('detection')),
        }
        for name,item in cases.items():
            start=time.monotonic(); result=DataTrust.audit_images(ImageAuditSpec((item,),allowed_roots=(str(root),)),replace(ImageAnalysisConfig(),limits=replace(ImageWorkLimits(),details=5)))
            annotation=next(e['data'] for e in result.evidence if e['family']=='annotations')
            if name=='annotation_heavy': assert annotation['object_visits']==4000
            if name=='semantic_16bit_masks': assert annotation['mask_pixels']==500*256*256 and not annotation['invalidity_reasons']
            source_root=Path(item.source.asset_root or item.source.path)
            ledger[name]={'seconds':time.monotonic()-start,'source_bytes':sum(p.stat().st_size for p in source_root.rglob('*') if p.is_file()),'occurrences':result.profile['occurrences'],'execution':result.execution,'coverage':result.coverage,'annotations':annotation,'claim':'Narrow authored CPU workload; no general corpus capacity guarantee.'}
            print(name,'measured',flush=True)
    (ROOT/'results/release/resources.json').write_text(json.dumps(ledger,indent=2,allow_nan=False)+'\n')


if __name__=='__main__': run()
