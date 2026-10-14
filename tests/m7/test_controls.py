from dataclasses import replace
import json
import os
import numpy as np
from PIL import Image
import pytest
from datatrust import *
from datatrust.image_annotations import frame,box,orient_mask,segmentation
from datatrust.image_assets import capture
from tests.m7.test_foundation import fixture,run,family


def test_declared_resize_and_crop_masks():
    asset={'decode':'decoded','width':40,'height':20,'orientation':1}
    spec=ImageAnnotationSpec(coordinate_frame='declared',frame_width=20,frame_height=10,transform=(2,0,0,0,2,0))
    geo,reason=frame(spec,asset,{})
    assert not reason and box([1,2,5,6],'xyxy',geo)==[2,4,10,12]
    mask=orient_mask(np.ones((10,20),dtype=np.uint8),spec,asset,geo)
    assert mask.shape==(20,40)
    crop=replace(spec,transform=(1,0,0,0,1,0))
    geo,reason=frame(crop,asset,{})
    assert reason is None
    with pytest.raises(ValueError): orient_mask(np.ones((10,20),dtype=np.uint8),crop,asset,geo)


@pytest.mark.parametrize('orientation',range(1,9))
def test_mask_orientation_matches_image(orientation):
    from PIL import ImageOps
    array=np.arange(12,dtype=np.uint8).reshape(3,4)
    image=Image.fromarray(array); exif=image.getexif(); exif[274]=orientation; image.info['exif']=exif.tobytes()
    expected=np.asarray(ImageOps.exif_transpose(image))
    asset={'width':4,'height':3,'orientation':orientation}
    actual=orient_mask(array,ImageAnnotationSpec(),asset,{'width':4,'height':3})
    assert np.array_equal(actual,expected)


def test_multilabel_matched_populations(tmp_path):
    spec=fixture(tmp_path,rows=[{'path':'image.png','labels':['a','b']},{'path':'image.png','labels':['a']},{'path':'image.png','labels':[]},{'path':'image.png','labels':None}],task='multilabel_classification',annotations=ImageAnnotationSpec(categories=('a','b')))
    r=run(spec); data=family(r,'multilabel_composition')
    assert data['complete_population']==3 and data['pairs'][0]['both_present']==1
    assert r.coverage['families']['multilabel_composition']['charged_population_visits']==3


def test_polygon_reference_raster_and_bound():
    from pycocotools import mask
    polygons=[[1,1,7,1,7,6,1,6]]
    facts,array=segmentation(polygons,10,8,ImageWorkLimits(),[0])
    expected=mask.decode(mask.merge(mask.frPyObjects(polygons,8,10)))
    assert np.array_equal(array,expected) and facts['area']==30
    facts,array=segmentation(polygons,10,8,replace(ImageWorkLimits(),segmentation_pixels=1),[0])
    assert array is None and facts['area'] is None


def test_hardlink_identity_and_special_file_rejection(tmp_path):
    spec=fixture(tmp_path); os.link(tmp_path/'image.png',tmp_path/'hard.png')
    p=tmp_path/'data.jsonl'; p.write_text(json.dumps({'path':'image.png'})+'\n'+json.dumps({'path':'hard.png'})+'\n')
    r=run(spec)
    assert family(r,'inventory')['physical_alias_locations']==1
    fifo=tmp_path/'fifo'; os.mkfifo(fifo)
    with pytest.raises(AnalysisError): capture(fifo,(tmp_path,))


def test_segmentation_overlay_and_source_change(tmp_path):
    coco={'images':[{'id':1,'file_name':'image.png','width':40,'height':24}],'categories':[{'id':1,'name':'object'}],'annotations':[{'id':1,'image_id':1,'category_id':1,'bbox':[1,1,10,10],'segmentation':[[1,1,11,1,11,11,1,11]]}]}
    fixture(tmp_path); p=tmp_path/'coco.json'; p.write_text(json.dumps(coco))
    item=ImageInputSpec('s',ImageSourceSpec(str(p),'coco',str(tmp_path)),ImageTaskSpec('segmentation'))
    r=run(ImageAuditSpec((item,),allowed_roots=(str(tmp_path),)))
    ref=next(iter(r.private['locators']))
    value=r.resolve_evidence(ref,allowed_roots=(tmp_path,),reveal_image=True,overlays=True)
    assert value['frame_compatible'] and value['image_disclosed']
    p.write_text(json.dumps(dict(coco,categories=[])))
    with pytest.raises(AnalysisError): r.resolve_evidence(ref,allowed_roots=(tmp_path,),reveal_image=True)


def test_different_version_dimensions_block_geometry(tmp_path):
    a=fixture(tmp_path/'a'); b=fixture(tmp_path/'b')
    Image.new('RGB',(80,48),'red').save(tmp_path/'b'/'image.png')
    bpath=tmp_path/'b'/'data.jsonl'; bpath.write_text(json.dumps({'id':'001','path':'image.png','objects':[{'category':1,'bbox':[4,6,24,30]}]})+'\n')
    spec=ImageAuditSpec((replace(a.inputs[0],id='a'),replace(b.inputs[0],id='b')),comparisons=(ImageComparisonSpec('a','b'),),allowed_roots=(str(tmp_path),))
    data=family(run(spec),'versions')
    assert data['changes']['annotation_payload_changes_blocked']==1


def test_public_export_survives_deleted_source(tmp_path):
    spec=fixture(tmp_path); r=run(spec); (tmp_path/'image.png').unlink()
    output=tmp_path/'exports'; output.mkdir()
    r.generate_artifacts(output/'historical.html',json_path=output/'historical.json')
    assert (output/'historical.html').exists()


def test_partial_execution_options_keep_image_metadata_defaults():
    config=ImageAnalysisConfig.from_dict({'execution':{'max_seconds':60}})
    assert config.execution.max_source_bytes==1024**3
    assert config.execution.max_combined_source_bytes==4*1024**3


def test_repeated_missing_location_is_not_multiple_assets(tmp_path):
    spec=fixture(tmp_path,rows=[{'path':'missing.png'}]*8,task='unlabeled')
    result=run(spec,replace(ImageAnalysisConfig(),limits=replace(ImageWorkLimits(),assets=1)))
    assert result.profile['occurrences']==8
    assert len(result.private['unavailable'])==1


def test_media_admission_precedes_content_read(monkeypatch,tmp_path):
    import datatrust.image_sources as sources
    from datatrust.images import execute_core
    spec=fixture(tmp_path)
    called=[]; original=sources.capture
    def checked(path,*args,**kwargs):
        if str(path).endswith('image.png'): called.append(path)
        return original(path,*args,**kwargs)
    monkeypatch.setattr(sources,'capture',checked)
    with pytest.raises(AnalysisError) as exc:
        execute_core(spec,replace(ImageAnalysisConfig(),source_limits=replace(ImageSourceLimits(),media_per_input_bytes=1)))
    assert exc.value.code=='media_byte_limit' and not called


def test_coco_category_names_gate_annotation_comparison(tmp_path):
    fixture(tmp_path)
    inputs=[]
    for name,label,box in [('a','cat',[1,1,10,10]),('b','dog',[2,2,10,10])]:
        payload={'images':[{'id':1,'file_name':'image.png','width':40,'height':24}],'categories':[{'id':1,'name':label}],'annotations':[{'id':1,'image_id':1,'category_id':1,'bbox':box}]}
        path=tmp_path/f'{name}.json'; path.write_text(json.dumps(payload))
        inputs.append(ImageInputSpec(name,ImageSourceSpec(str(path),'coco',str(tmp_path)),ImageTaskSpec('detection')))
    spec=ImageAuditSpec(tuple(inputs),comparisons=(ImageComparisonSpec('a','b'),),allowed_roots=(str(tmp_path),))
    r=run(spec)
    assert family(r,'versions')['changes']['taxonomy_changes']==1
    assert family(r,'versions')['changes']['annotation_payload_changes_blocked']==1
    assert family(r,'annotation_disagreement')['compatible_exact_raster_groups_with_differences']==0


def test_cross_input_groups_require_shared_namespace(tmp_path):
    spec=fixture(tmp_path,rows=[{'path':'image.png','group':'subject'}],task='unlabeled')
    item=replace(spec.inputs[0],mapping=ImageMappingSpec(groups=('group',)))
    inputs=(replace(item,id='a'),replace(item,id='b'))
    combined=ImageAuditSpec(inputs,split_requirements=(ImageSplitRequirement('a','b',group_separation=True),),allowed_roots=(str(tmp_path),))
    assert family(run(combined),'split_requirements')['group_separation_applicability']=='blocked'
    combined=replace(combined,inputs=tuple(replace(x,namespace='shared') for x in inputs))
    assert family(run(combined),'split_requirements')['complete_declared_group_overlap_occurrences']==1


def test_binary_instance_png_collection(tmp_path):
    array=np.zeros((24,40),dtype=np.uint8); array[3:15,2:12]=255; Image.fromarray(array).save(tmp_path/'instance.png')
    spec=fixture(tmp_path,rows=[{'path':'image.png','objects':[{'category':'object','mask':'instance.png'}]}],task='segmentation',annotations=ImageAnnotationSpec(categories=('object',),mask_encoding='binary_png'))
    result=run(spec)
    assert family(result,'annotations')['mask_pixels']==960
    assert not family(result,'annotations')['invalidity_reasons']


def test_invalid_classification_blocks_duplicate_disagreement(tmp_path):
    spec=fixture(tmp_path,rows=[{'path':'image.png','labels':'known'},{'path':'image.png','labels':'outside'}],task='classification',annotations=ImageAnnotationSpec(categories=('known',)))
    r=run(spec)
    assert family(r,'annotation_disagreement')['compatible_exact_raster_groups_with_differences']==0
    assert family(r,'annotation_disagreement')['payload_difference_groups_blocked']==1



def test_binary_instance_preview_uses_verified_frame(tmp_path):
    pixels=np.zeros((24,40),dtype=np.uint8); pixels[3:15,2:12]=255; Image.fromarray(pixels).save(tmp_path/'instance.png')
    spec=fixture(tmp_path,rows=[{'path':'image.png','objects':[{'category':'object','mask':'instance.png'}]}],task='segmentation',annotations=ImageAnnotationSpec(categories=('object',),mask_encoding='binary_png'))
    r=run(spec); ref=next(iter(r.private['locators']))
    assert r.resolve_evidence(ref,allowed_roots=(tmp_path,),reveal_image=True,overlays=True)['image_disclosed']


def test_semantic_resize_overlay(tmp_path):
    pixels=np.zeros((12,20),dtype=np.uint8); pixels[3:6,2:8]=1; Image.fromarray(pixels).save(tmp_path/'mask.png')
    ann=ImageAnnotationSpec(categories=(0,1),coordinate_frame='declared',frame_width=20,frame_height=12,transform=(2,0,0,0,2,0))
    spec=fixture(tmp_path,rows=[{'path':'image.png','mask':'mask.png'}],task='segmentation',annotations=ann)
    r=run(spec); ref=next(iter(r.private['locators']))
    assert r.resolve_evidence(ref,allowed_roots=(tmp_path,),reveal_image=True,overlays=True)['frame_compatible']


def test_missing_reference_is_reserved_against_export_collision(tmp_path):
    spec=fixture(tmp_path,rows=[{'path':'missing.png'}],task='unlabeled')
    r=run(spec)
    with pytest.raises(Exception): r.generate_artifacts(tmp_path/'missing.png')
    assert not (tmp_path/'missing.png').exists()


def test_rgb_semantic_mask_preserves_lexical_category_ids(tmp_path):
    pixels=np.zeros((24,40,3),dtype=np.uint8); pixels[3:8,2:12]=[255,0,0]; Image.fromarray(pixels).save(tmp_path/'rgb.png')
    ann=ImageAnnotationSpec(categories=('001',),mask_encoding='rgb_png',color_mapping={'0,0,0':0,'255,0,0':'001'})
    spec=fixture(tmp_path,rows=[{'path':'image.png','mask':'rgb.png'}],task='segmentation',annotations=ann)
    r=run(spec); assert not family(r,'annotations')['invalidity_reasons']
    assert next(iter(r.private['locators'].values()))['normalized']['labels']==['001']
    assert family(r,'composition')['mask_occupancy']['mean']==50/960
