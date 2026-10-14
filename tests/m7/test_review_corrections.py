"""Regressions from independent M7 source/artifact review."""
from collections import Counter
from dataclasses import replace
import copy
import json
from pathlib import Path

import numpy as np
from PIL import Image
import pytest

from datatrust import *
from datatrust.image_models import review_pairs,registry
from datatrust.image_presentation import report_view
from tests.m7.test_foundation import fixture,run,family


@pytest.mark.parametrize('instance',[False,True])
def test_same_relative_mask_reference_detects_normalized_version_and_duplicate_changes(tmp_path,instance):
    inputs=[]
    for name,offset in [('reference',0),('current',5)]:
        root=tmp_path/name; root.mkdir()
        mask=np.zeros((24,40),dtype=np.uint8); mask[3:10,2+offset:12+offset]=1
        Image.fromarray(mask).save(root/'same-mask.png')
        row={'path':'image.png','id':'001','objects':[{'id':'object-1','category':1,'mask':'same-mask.png'}]} if instance else {'path':'image.png','id':'001','mask':'same-mask.png'}
        s=fixture(root,rows=[row],task='segmentation',annotations=ImageAnnotationSpec(categories=(1,),mask_encoding='binary_png' if instance else 'semantic_png'))
        inputs.append(replace(s.inputs[0],id=name))
    spec=ImageAuditSpec(tuple(inputs),comparisons=(ImageComparisonSpec('reference','current'),),allowed_roots=(str(tmp_path),))
    r=run(spec)
    annotations=[v['normalized'] for v in r.private['locators'].values()]
    assert len({v['payload_sha256'] for v in annotations})==1
    assert len({v['normalized_sha256'] for v in annotations})==2
    assert family(r,'versions')['changes']['compatible_annotation_changes']==1
    assert family(r,'annotation_disagreement')['compatible_exact_raster_groups_with_differences']==1
    # Taxonomy compatibility must still gate a same-reference mask change.
    incompatible=replace(inputs[1],annotations=replace(inputs[1].annotations,categories=(1,2)))
    r=run(replace(spec,inputs=(inputs[0],incompatible)))
    assert family(r,'versions')['changes']['annotation_payload_changes_blocked']==1
    assert family(r,'versions')['changes'].get('compatible_annotation_changes',0)==0


def group_spec(tmp_path,rows,mode='per_key'):
    spec=fixture(tmp_path,rows=rows,task='unlabeled')
    item=replace(spec.inputs[0],mapping=ImageMappingSpec(split='split',groups=('subject','session')))
    return replace(spec,inputs=(item,),split_requirements=(ImageSplitRequirement('train','test',group_separation=True,group_mode=mode),))


def test_per_key_groups_count_left_occurrences_once_and_accept_null_substrings(tmp_path):
    rows=[{'path':'image.png','split':'train','subject':'nullification','session':'left'},
          {'path':'image.png','split':'train','subject':'other','session':'same'},
          {'path':'image.png','split':'train','subject':'both','session':'same'},
          {'path':'image.png','split':'test','subject':'nullification','session':'right'},
          {'path':'image.png','split':'test','subject':'both','session':'same'}]
    spec=group_spec(tmp_path,rows); r=run(spec); d=family(r,'split_requirements')
    assert d['complete_group_population_left']==3
    assert sorted(k['overlap_left_occurrences'] for k in d['group_keys'])==[2,2]
    assert d['declared_group_overlap_occurrences']==3  # not four key hits
    assert d['composite_group_overlap_occurrences']==1
    assert d['group_separation_applicability']=='applicable'
    assert family(r,'composition')['group_populations'][0]['complete_group_occurrences']==5
    d=family(run(replace(spec,split_requirements=(replace(spec.split_requirements[0],group_mode='composite'),))),'split_requirements')
    assert d['declared_group_overlap_occurrences']==1


def test_missing_other_group_key_does_not_hide_per_key_overlap(tmp_path):
    rows=[{'path':'image.png','split':'train','subject':'known','session':None},
          {'path':'image.png','split':'test','subject':'known','session':'different'}]
    spec=group_spec(tmp_path,rows); d=family(run(spec),'split_requirements')
    assert d['declared_group_overlap_occurrences']==1 and d['complete_declared_group_overlap_occurrences']==0
    assert d['group_separation_applicability']=='partial'
    assert d['complete_group_population_left']==0
    assert family(run(replace(spec,split_requirements=(replace(spec.split_requirements[0],group_mode='composite'),))),'split_requirements')['declared_group_overlap_occurrences']==0


def test_group_key_order_names_types_and_namespaces_are_explicit(tmp_path):
    rows=[{'path':'image.png','subject':'001','session':1}]
    spec=fixture(tmp_path,rows=rows,task='unlabeled')
    a=replace(spec.inputs[0],id='a',mapping=ImageMappingSpec(groups=('subject','session')),namespace='shared')
    b=replace(a,id='b',mapping=ImageMappingSpec(groups=('session','subject')))
    spec=replace(spec,inputs=(a,b),split_requirements=(ImageSplitRequirement('a','b',group_separation=True,group_mode='composite'),))
    assert family(run(spec),'split_requirements')['declared_group_overlap_occurrences']==1
    # Positional values or different declared key names cannot establish a group.
    b=replace(b,mapping=ImageMappingSpec(groups=('other_subject','other_session')))
    assert family(run(replace(spec,inputs=(a,b))),'split_requirements')['group_separation_applicability']=='blocked'
    b=replace(a,id='b',namespace=None)
    assert family(run(replace(spec,inputs=(a,b))),'split_requirements')['declared_group_overlap_occurrences']==0
    with pytest.raises(ValueError): ImageSplitRequirement('a','b',group_mode='infer')
    p=tmp_path/'data.jsonl'; p.write_text(json.dumps({'path':'image.png','subject':1,'session':'1'})+'\n')
    # A typed key differs from its textual representation.
    typed=group_spec(tmp_path,[{'path':'image.png','split':'train','subject':1,'session':None},{'path':'image.png','split':'test','subject':'1','session':None}])
    assert family(run(typed),'split_requirements')['declared_group_overlap_occurrences']==0


def test_exported_model_union_bounds_both_endpoints_and_discloses_omissions(monkeypatch,tmp_path):
    import datatrust.image_models as models
    from datatrust.image_assets import capture
    spec=fixture(tmp_path,task='unlabeled')
    selected=[]
    for i in range(7):
        path=tmp_path/f'asset-{i}.png'; Image.new('RGB',(40,24),(i*20,50,100)).save(path)
        identity,_,_=capture(path,(str(tmp_path),),max_bytes=10000)
        selected.append({'path':str(path),'identity':identity,'reference':f'image_{i}','splits':['train' if i==0 else 'test'],'purpose':'discovery','memberships':[['source_1','train' if i==0 else 'test']]})
    bank=np.zeros((7,7),dtype=np.float32); bank[0,0]=1
    for i in range(1,7): bank[i,0]=.8; bank[i,i]=.6
    offset=[0]
    def encode(*args):
        n=len(args[2]); values=bank[offset[0]:offset[0]+n]; offset[0]+=n; return values
    monkeypatch.setattr(models,'load_encoder',lambda *a:(None,None)); monkeypatch.setattr(models,'encode',encode)
    provenance={'model':'test_vectors','files':{},'manifest':{},'operating_point':.75}
    result=models.execute_model(selected,provenance,spec,ImageAnalysisConfig(),30,'synthetic')
    candidates=family(result,'embeddings')['candidates']; degrees=Counter(v for p in candidates for v in (p['left'],p['right']))
    assert len(candidates)==3 and max(degrees.values())==3
    cov=result.coverage['families']['embeddings']
    assert cov['qualifying_review_pairs']==6 and cov['review_pairs_after_endpoint_cap']==3
    assert cov['endpoint_cap_omissions']==3 and cov['detail_omissions']==0
    assert not cov['matching_quality_claim'] and 'unmeasured' in cov['benchmark_scope']
    assert review_pairs([[(.8,1,True),(.9,2,False)],[(.8,0,True)],[(.9,0,False)]],limit=1)[0]==[(0,1,.8,True)]


def test_model_interpretation_preserves_exact_measured_results():
    root=Path(__file__).parents[2]; metadata=registry(); evidence=metadata['review_evidence']
    encoder=json.loads((root/'validation/m7/results/model_benchmark.json').read_text())['models']['facebook/dinov2-base']
    pipeline=json.loads((root/'validation/m7/results/release/selection_closure.json').read_text())['review_pipeline']['metrics']['held_out']
    for k in evidence['encoder_calibration']: assert evidence['encoder_calibration'][k]==encoder['calibration'][k]
    for k in evidence['encoder_held_out']: assert evidence['encoder_held_out'][k]==encoder['held_out'][k]
    for k in evidence['combined_pipeline_held_out']: assert evidence['combined_pipeline_held_out'][k]==pipeline[k]
    assert metadata['selection']['status']=='passed' and 'encoder' in metadata['selection']['status_scope']
    assert not evidence['combined_pipeline_precision_target_met']
    assert evidence['combined_pipeline_held_out']['precision']<.9


def test_issue_rich_report_keeps_important_decisions_and_full_json(tmp_path):
    from validation.m7.review_corrections import synthetic_spec
    spec=synthetic_spec(tmp_path/'fixture'); result=run(spec)
    original=copy.deepcopy(result.to_dict()); view=report_view(result)
    assert result.to_dict()==original
    assert len(view['actions'])==5
    titles=[x['title'] for x in view['actions']]
    assert titles[:3]==['Resolve source and identity problems','Resolve declared split separation','Review annotation integrity']
    assert any('compatible annotation changes' in f for a in view['actions'] for f in a['facts'])
    blocks=[b for s in view['sections'] for b in s['blocks']]
    assert len(blocks)==len(result.evidence)+1  # coverage is an additional block
    assert any(b['title']=='near duplicates' for b in blocks)
    from datatrust.renderer import render_analysis_result
    html=render_analysis_result(result)
    for title in titles: assert title in html
    assert str(tmp_path) not in html and 'same-mask.png' not in html and 'nullification' not in html
    assert 'data:image/' not in html and 'strict JSON' in html
    assert family(result,'versions')['alignment']=='blocked'


def test_existing_model_report_discloses_pipeline_target_without_changing_evidence():
    root=Path(__file__).parents[2]
    data=json.loads((root/'validation/m7/results/release/reports/model_release/analysis.json').read_text())
    result=ImageAuditResult(**data,private={'files':{}})
    before=copy.deepcopy(result.to_dict())
    from datatrust.renderer import render_analysis_result
    html=render_analysis_result(result)
    assert '97.06%' in html and '93.94%' in html and '89.66%' in html and 'Not met' in html
    assert result.to_dict()==before
