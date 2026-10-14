from dataclasses import replace
import json
import shutil
import numpy as np
from PIL import Image
import pytest
from datatrust import *
from datatrust.images import execute_core,finalize
from tests.m7.test_foundation import fixture,run,family


def test_coco_yolo_manifest_geometry_parity(tmp_path):
    spec=fixture(tmp_path); expected=run(spec)
    coco={'images':[{'id':1,'file_name':'image.png','width':40,'height':24}],'categories':[{'id':1,'name':'object'}],'annotations':[{'id':1,'image_id':1,'category_id':1,'bbox':[2,3,10,12]}]}
    p=tmp_path/'coco.json'; p.write_text(json.dumps(coco))
    c=ImageInputSpec('c',ImageSourceSpec(str(p),'coco',str(tmp_path)),ImageTaskSpec('detection'),annotations=ImageAnnotationSpec(categories=(1,)))
    r=run(ImageAuditSpec((c,),allowed_roots=(str(tmp_path),)))
    assert family(r,'composition')['box_area']==family(expected,'composition')['box_area']
    images=tmp_path/'images'/'train'; labels=tmp_path/'labels'/'train'; images.mkdir(parents=True); labels.mkdir(parents=True)
    shutil.copy(tmp_path/'image.png',images/'a.png')
    (labels/'a.txt').write_text('0 0.175 0.375 0.25 0.5\n')
    y=tmp_path/'dataset.yaml'; y.write_text('train: images/train\nnames: [object]\n')
    item=ImageInputSpec('y',ImageSourceSpec(str(y),'yolo',str(tmp_path)),ImageTaskSpec('detection'))
    result=run(ImageAuditSpec((item,),allowed_roots=(str(tmp_path),)))
    assert family(result,'composition')['box_area']==family(expected,'composition')['box_area']
    (labels/'a.txt').unlink()
    assert family(run(ImageAuditSpec((item,),allowed_roots=(str(tmp_path),))),'annotations')['occurrence_states']=={'absent':1}
    item=replace(item,annotations=ImageAnnotationSpec(missing_yolo_labels_are_negative=True))
    assert family(run(ImageAuditSpec((item,),allowed_roots=(str(tmp_path),))),'annotations')['occurrence_states']=={'empty':1}


def test_semantic_mask_ids_and_mismatch(tmp_path):
    mask=np.zeros((24,40),dtype=np.uint16); mask[2:5,4:10]=1000; Image.fromarray(mask).save(tmp_path/'mask.png')
    spec=fixture(tmp_path,rows=[{'path':'image.png','mask':'mask.png','id':'a'}],task='segmentation',annotations=ImageAnnotationSpec(categories=(1000,)))
    r=run(spec)
    assert family(r,'annotations')['mask_pixels']==960
    assert not family(r,'annotations')['invalidity_reasons']
    Image.fromarray(mask[:12]).save(tmp_path/'mask.png')
    r=run(spec)
    assert family(r,'annotations')['invalidity_reasons']['mask_frame_mismatch']==1


def test_version_frame_block_and_logical_alignment(tmp_path):
    first=tmp_path/'first'; second=tmp_path/'second'; first.mkdir(); second.mkdir()
    a=fixture(first); b=fixture(second,rows=[{'path':'image.png','id':'001','width':20,'objects':[{'category':1,'bbox':[1,2,10,12]}]}])
    spec=ImageAuditSpec((replace(a.inputs[0],id='reference'),replace(b.inputs[0],id='current')),comparisons=(ImageComparisonSpec('reference','current'),),allowed_roots=(str(tmp_path),))
    data=family(run(spec),'versions')
    assert data['aligned']==1 and data['changes']['annotation_payload_changes_blocked']==1
    assert data['changes'].get('compatible_annotation_changes',0)==0


def test_near_search_matches_exhaustive_oracle(tmp_path):
    from datatrust.image_assets import decode
    rng=np.random.default_rng(44); array=rng.integers(0,256,(64,80,3),dtype=np.uint8)
    rows=[]; hashes=[]
    for i in range(12):
        image=Image.fromarray(array if i<6 else rng.integers(0,256,array.shape,dtype=np.uint8))
        path=tmp_path/f'{i}.jpg'; image.save(path,quality=50+i*4)
        facts,_=decode(path.read_bytes(),ImageWorkLimits()); hashes.append(facts['phash'])
        rows.append({'path':path.name,'id':str(i),'split':'train' if i%2 else 'test'})
    p=tmp_path/'manifest.jsonl'; p.write_text(''.join(json.dumps(r)+'\n' for r in rows))
    item=ImageInputSpec('s',ImageSourceSpec(str(p),'jsonl',str(tmp_path)),mapping=ImageMappingSpec(logical_id='id',split='split'))
    r=run(ImageAuditSpec((item,),allowed_roots=(str(tmp_path),)))
    oracle=sum((a^b).bit_count()<=6 for i,a in enumerate(hashes) for b in hashes[i+1:])
    found=family(r,'near_duplicates')['qualifying_raster_pairs']
    assert found==oracle
    cov=r.coverage['families']['near_duplicates']; assert cov['indexed_rasters']==12 and cov['cross_split_queries_complete']
    assert cov['partition_entries']==84


def test_search_caps_are_accounted(tmp_path):
    spec=fixture(tmp_path,rows=[{'path':'image.png','id':'a','split':'train'},{'path':'image.png','id':'b','split':'test'}],task='unlabeled')
    spec=replace(spec,inputs=(replace(spec.inputs[0],mapping=ImageMappingSpec(split='split')),))
    r=run(spec,replace(ImageAnalysisConfig(),limits=replace(ImageWorkLimits(),posting_visits=1,hamming_comparisons=1)))
    assert r.execution['status']=='completed'
    assert r.coverage['families']['near_duplicates']['posting_visits']<=1


def test_coco_malformed_and_duplicate_keys(tmp_path):
    fixture(tmp_path)
    p=tmp_path/'bad.json'; p.write_text('{"images":[],"images":[],"categories":[],"annotations":[]}')
    item=ImageInputSpec('c',ImageSourceSpec(str(p),'coco'),ImageTaskSpec('detection'))
    with pytest.raises(AnalysisError): run(ImageAuditSpec((item,),allowed_roots=(str(tmp_path),)))
