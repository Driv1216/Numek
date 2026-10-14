from dataclasses import replace
import hashlib
import json
from pathlib import Path
import numpy as np
from PIL import Image
import pytest
from datatrust import *
from datatrust.images import execute_core,finalize
from datatrust.image_assets import capture,decode,perceptual_hash
from datatrust.image_annotations import frame,box,rle_counts,segmentation,compatible
from datatrust.image_sources import safe_yaml


def family(result,name): return next(e['data'] for e in result.evidence if e['family']==name)

def fixture(tmp_path,rows=None,task='detection',annotations=None):
    tmp_path.mkdir(exist_ok=True)
    rng=np.random.default_rng(2); Image.fromarray(rng.integers(0,256,(24,40,3),dtype=np.uint8)).save(tmp_path/'image.png')
    p=tmp_path/'data.jsonl'; rows=rows if rows is not None else [{'path':'image.png','id':'001','objects':[{'category':1,'bbox':[2,3,12,15]}]}]
    p.write_text(''.join(json.dumps(r)+'\n' for r in rows))
    item=ImageInputSpec('dataset',ImageSourceSpec(str(p),'jsonl',str(tmp_path)),ImageTaskSpec(task),ImageMappingSpec(logical_id='id'),annotations or ImageAnnotationSpec(categories=(1,)))
    return ImageAuditSpec((item,),allowed_roots=(str(tmp_path),))


def run(spec,config=None):
    config=config or ImageAnalysisConfig(); return finalize(execute_core(spec,config),spec,config)


def test_core_counts_privacy_and_minimal_capture(tmp_path):
    spec=fixture(tmp_path,rows=[{'path':'image.png','id':'001','objects':[]},{'path':'image.png','id':'1','objects':None},{'path':'missing.png','id':'2'}])
    r=run(spec)
    assert r.profile['occurrences']==3
    assert family(r,'inventory')['image_locations']==1
    assert family(r,'annotations')['occurrence_states']=={'empty':1,'null':1,'absent':1}
    assert family(r,'logical_identity')['occurrences_with_duplicate_source_keys']==0
    assert not r.execution['corpus_copied']
    public=r.json_text(); assert str(tmp_path) not in public and 'image.png' not in public and '"001"' not in public
    assert all('snapshot' not in info for info in r.private['files'].values())


def test_contracts_and_safe_yaml():
    with pytest.raises(ValueError): ImageTaskSpec.from_dict({'kind':'unlabeled','infer':True})
    with pytest.raises(ValueError): ImageAnalysisConfig(hamming_radius=7)
    with pytest.raises(ValueError): ImageAnnotationSpec(coordinate_frame='declared')
    with pytest.raises(ValueError): ImageAnnotationSpec(transform=(1,0,0,0,1,0))
    with pytest.raises(ValueError): safe_yaml('names: &n [a]\ntrain: *n')
    with pytest.raises(ValueError): safe_yaml('names: [a]\nnames: [b]')
    with pytest.raises(ValueError): safe_yaml('names: [a]\ndownload: dangerous')


@pytest.mark.parametrize('orientation',range(1,9))
def test_orientation_geometry(orientation):
    asset={'decode':'decoded','width':40,'height':24,'orientation':orientation}
    geometry,reason=frame(ImageAnnotationSpec(),asset,{'declared_width':40,'declared_height':24})
    assert reason is None
    b=box([0,0,40,24],'xyxy',geometry)
    assert b==[0,0,24,40] if orientation>=5 else b==[0,0,40,24]
    with pytest.raises(ValueError): box([0,0,41,24],'xyxy',geometry)


def test_unknown_and_wrong_frames_block_comparison(tmp_path):
    spec=fixture(tmp_path,rows=[{'path':'image.png','id':'a','objects':[{'category':1,'bbox':[2,3,12,15]}]},{'path':'image.png','id':'b','width':20,'objects':[{'category':1,'bbox':[1,2,10,12]}]}])
    r=run(spec); evidence=family(r,'annotation_disagreement')
    assert evidence['compatible_exact_raster_groups_with_differences']==0
    assert evidence['payload_difference_groups_blocked']==1
    spec=replace(spec,inputs=(replace(spec.inputs[0],annotations=ImageAnnotationSpec(coordinate_frame='unknown',categories=(1,))),))
    assert family(run(spec),'annotation_disagreement')['compatible_exact_raster_groups_with_differences']==0


def test_exact_duplicate_annotation_context(tmp_path):
    spec=fixture(tmp_path,rows=[{'path':'image.png','id':'a','objects':[{'category':1,'bbox':[2,3,12,15]}]},{'path':'image.png','id':'b','objects':[{'category':1,'bbox':[1,2,10,12]}]}])
    r=run(spec)
    assert family(r,'annotation_disagreement')['compatible_exact_raster_groups_with_differences']==1
    assert family(r,'exact_duplicates_bytes')['participating_occurrences']==2


def test_rle_reference_oracle():
    from pycocotools import mask
    binary=np.zeros((9,13),dtype=np.uint8,order='F'); binary[2:8,3:9]=1
    encoded=mask.encode(binary); encoded['counts']=encoded['counts'].decode()
    counts=rle_counts(encoded['counts'],10000)
    assert sum(counts)==117 and sum(counts[1::2])==36
    result,decoded=segmentation(encoded,13,9,ImageWorkLimits(),[0])
    assert result['area']==36 and np.array_equal(decoded,binary)
    with pytest.raises(ValueError): segmentation({'size':[9,13],'counts':[116]},13,9,ImageWorkLimits(),[0])
    with pytest.raises(ValueError): rle_counts('P',100)


def test_source_changed_and_symlinks(tmp_path):
    spec=fixture(tmp_path); r=run(spec)
    Image.new('RGB',(40,24),'red').save(tmp_path/'image.png')
    ref=next(iter(r.private['locators']))
    with pytest.raises(AnalysisError): r.resolve_evidence(ref,allowed_roots=(tmp_path,),reveal_image=True)
    (tmp_path/'alias.png').symlink_to(tmp_path/'image.png')
    with pytest.raises(AnalysisError): capture(tmp_path/'alias.png',(tmp_path,))
    with pytest.raises(AnalysisError): capture(tmp_path/'../other',(tmp_path,))


def test_decode_limits_alpha_and_native_identity(tmp_path):
    Image.new('RGBA',(50,30),(10,20,30,0)).save(tmp_path/'transparent.png')
    facts,_=decode((tmp_path/'transparent.png').read_bytes(),ImageWorkLimits())
    assert facts['decode']=='decoded' and not facts['visual_eligible'] and facts['visual_exclusion']=='nontrivial_alpha'
    facts,_=decode((tmp_path/'transparent.png').read_bytes(),replace(ImageWorkLimits(),pixels_per_asset=10))
    assert facts['decode']=='pixel_safety_excluded'


def test_private_export_resolution_and_collision(tmp_path):
    spec=fixture(tmp_path); r=run(spec); out=tmp_path/'reports'; out.mkdir()
    a=r.generate_artifacts(out/'default.html',json_path=out/'default.json')
    assert a.private_manifest_path and not (out/'default.html').stat().st_mode&0o077
    ref=next(iter(r.private['locators'])); resolved=r.resolve_evidence(ref,allowed_roots=(tmp_path,),reveal_image=True,overlays=True)
    assert resolved['image_data_uri'].startswith('data:image/jpeg;base64,')
    r.generate_artifacts(out/'explicit.html',disclosure=ImageDisclosureOptions((ref,),True),allowed_roots=(tmp_path,))
    assert 'data:image/jpeg;base64,' not in (out/'default.html').read_text()
    assert 'data:image/jpeg;base64,' in (out/'explicit.html').read_text()
    with pytest.raises(ValueError): r.generate_artifacts(tmp_path/'image.png')
    manifest=dict(r.private,audit_id='other')
    with pytest.raises(ValueError): DataTrust.resolve_image_evidence(manifest,ref,r.to_dict(),allowed_roots=(tmp_path,))
