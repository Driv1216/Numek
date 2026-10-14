"""Focused correction evidence: exact witnesses, bounded overlap and human prose."""
from dataclasses import replace
import json
from pathlib import Path

import pytest
from datatrust import *
from datatrust.cross import _core,finalize
from datatrust.cross_presentation import report_view
from datatrust.renderer import render_analysis_result
from tests.m9.test_integrity import table_spec


def complete(spec,config=None):
    config=config or CrossRepresentationAnalysisConfig()
    return finalize(_core(spec,config),spec,config)


def data(result,family):
    return next(e['data'] for e in result.evidence if e['family']==family)


def test_structural_examples_are_bounded_exact_and_private(tmp_path):
    secret='PRIVATE_ID_SENTINEL'
    s=table_spec(tmp_path,[{'id':secret,'value':1,'unprojected':'extra'},{'id':secret,'value':2},{'value':3}],[{'id':'unrelated','value':0}])
    config=CrossRepresentationAnalysisConfig(limits=CrossWorkLimits(witnesses=1))
    r=complete(s,config);identity=data(r,'identities');relationship=data(r,'relationships')
    assert identity['cardinality_violations']==1 and identity['invalid_keys_total']==1
    duplicate=next(d for d in identity['details'] if d['reason']=='duplicate_logical_identity')
    resolved=[r.resolve_evidence(ref,allowed_roots=(str(tmp_path),),reveal_content=True) for ref in duplicate['evidence_refs']]
    assert len(resolved)==2 and all(x['excerpt']==secret for x in resolved)
    assert len({json.dumps(x['location']) for x in resolved})==2
    assert any(d['reason']=='left_required_endpoint_missing' for d in relationship['details'])
    for d in relationship['details']:
        assert d['target_id'] in r.profile['review_targets']
        for ref in d['evidence_refs']: assert r.resolve_evidence(ref,allowed_roots=(str(tmp_path),))['status']=='resolved'
    original=r.json_text();view=report_view(r);html=render_analysis_result(r)
    assert r.json_text()==original and secret not in html+original and str(tmp_path) not in html+original
    assert 'source_1:' not in html and "{'" not in html and 'Priority review actions' in html
    assert view['actions'][0]['explanation'] and 'key groups' in html
    review=r.review_dispositions();review.set(duplicate['target_id'],'confirm','private reviewer note')
    assert ReviewDispositionSet.from_dict(review.to_dict(),result=r).entries==review.entries
    (tmp_path/'left.jsonl').write_text('changed')
    with pytest.raises((AnalysisError,ValueError)): r.resolve_evidence(duplicate['evidence_refs'][0],allowed_roots=(str(tmp_path),))


def test_association_orphan_examples_resolve_declared_row(tmp_path):
    s=table_spec(tmp_path,[{'id':'a','value':1}],[{'id':'b','value':1}])
    path=tmp_path/'links.jsonl';path.write_text(json.dumps({'id':'link','left_id':'a','right_id':'PRIVATE_MISSING_ENDPOINT'}))
    s=replace(s,inputs=(*s.inputs,CrossRepresentationInputSpec('links',str(path),format='jsonl')),relationships=(replace(s.relationships[0],association_source='links'),))
    r=complete(s);e=data(r,'relationships');assert e['invalid_association_rows']==1 and e['associations']==0
    d=next(d for d in e['details'] if d['reason']=='association_endpoint_unresolved')
    assert {r.resolve_evidence(ref,allowed_roots=(str(tmp_path),),reveal_content=True)['excerpt'] for ref in d['evidence_refs']}=={'a','PRIVATE_MISSING_ENDPOINT'}
    assert 'PRIVATE_MISSING_ENDPOINT' not in r.json_text()


@pytest.mark.parametrize('fmt',['pdf','docx'])
def test_document_text_containment_resolves_without_mapping(tmp_path,fmt):
    text='PRIVATE_PASSAGE_SENTINEL: the enterprise reported a profitable operating year with stable recurring revenue.'
    path=tmp_path/('evidence.'+fmt)
    if fmt=='pdf':
        from reportlab.pdfgen.canvas import Canvas
        doc=Canvas(str(path));doc.drawString(20,750,'Opening note. '+text+' Closing note.');doc.save()
    else:
        from docx import Document
        doc=Document();doc.add_paragraph('Opening note. '+text+' Closing note.')
        doc.add_table(rows=1,cols=1).cell(0,0).text='Table note. '+text+' Additional context.'
        doc.save(path)
    records=tmp_path/'text.jsonl';records.write_text(json.dumps({'id':'t1','text':text}))
    s=CrossRepresentationAuditSpec((CrossRepresentationInputSpec('text',str(records),kind='text',format='jsonl'),CrossRepresentationInputSpec('doc',str(path),kind='document',format=fmt)),separation=(CrossSeparationSpec('overlap','text','doc',mode='content',left_keys=('text',),right_keys=('text',)),),allowed_roots=(str(tmp_path),))
    r=complete(s);e=data(r,'separation')
    assert e['status']=='violated' and e['left_affected_records']==e['right_affected_records']==1
    locations=[]
    for d in (d for d in e['details'] if d['reason']=='exact_literal_containment'):
        for ref in d['evidence_refs']:
            resolved=r.resolve_evidence(ref,allowed_roots=(str(tmp_path),),reveal_content=True)
            assert resolved['excerpt']==text and 'span' in resolved['location'];locations.append(resolved['location'])
    if fmt=='docx': assert any(loc['kind']=='table' for loc in locations)
    assert text not in r.json_text()+json.dumps(r.private)
    bounded=complete(s,CrossRepresentationAnalysisConfig(limits=CrossWorkLimits(discovery_visits=1)))
    e=data(bounded,'separation');assert e['status']=='inconclusive' and e['candidate_coverage']['bounded'] and e['violated']==0


def test_image_pixel_overlap_and_similarity_remain_distinct(tmp_path):
    from PIL import Image
    pixels=[((x*17+y*13)%223,(x*x*7+y*11)%223,(x*y*19+x*5)%223) for y in range(32) for x in range(32)]
    image=Image.new('RGB',(32,32));image.putdata(pixels)
    image.save(tmp_path/'a.png');image.save(tmp_path/'b.bmp')
    # Same luminance shape, different pixels: a perceptual candidate rather than exact identity.
    changed=Image.new('RGB',(32,32));changed.putdata([(r+1,g+1,b+1) for r,g,b in pixels]);changed.save(tmp_path/'c.png')
    for side,paths in [('left',['a.png']),('right',['b.bmp','c.png'])]:
        (tmp_path/(side+'.jsonl')).write_text('\n'.join(json.dumps({'id':str(i),'path':p}) for i,p in enumerate(paths)))
    inputs=tuple(CrossRepresentationInputSpec(side,str(tmp_path/(side+'.jsonl')),kind='image',format='jsonl') for side in ('left','right'))
    s=CrossRepresentationAuditSpec(inputs,separation=(CrossSeparationSpec('images','left','right',mode='assets'),),allowed_roots=(str(tmp_path),))
    r=complete(s);e=data(r,'separation')
    assert e['left_affected_records']==e['right_affected_records']==1
    assert e['investigation_candidates']==1 and e['candidate_coverage']['similarity_establishes_violation'] is False
    assert any(d['reason']=='exact_oriented_sha256' for d in e['details'])
    candidate=next(d for d in e['details'] if d['match_kind']=='investigation_candidate')
    for ref in candidate['evidence_refs']: assert r.resolve_evidence(ref,allowed_roots=(str(tmp_path),),reveal_content=True)['image']
    bounded=data(complete(s,CrossRepresentationAnalysisConfig(limits=CrossWorkLimits(candidates=1))),'separation')
    assert bounded['candidate_coverage']['bounded'] and bounded['left_affected_records']==bounded['right_affected_records']==1
    (tmp_path/'right.jsonl').write_text(json.dumps({'id':'only','path':'c.png'}))
    r=complete(s);e=data(r,'separation')
    assert e['shared_units']==0 and e['violated']==0 and e['investigation_candidates']==1 and e['status']=='satisfied'
    assert any(f['family']=='separation' and f['priority']=='Moderate' for f in r.findings)


def test_completed_investigation_page_uses_private_structural_witnesses(tmp_path):
    from datatrust.web import create_app
    s=table_spec(tmp_path,[{'id':'private_duplicate','value':1},{'id':'private_duplicate','value':1}],[{'id':'other','value':1}])
    r=complete(s);app=create_app(tmp_path/'app',data_roots=(tmp_path,));client=app.test_client()
    client.get('/cross-representation')
    with client.session_transaction() as session: token=session['form_token']
    client.post('/cross-representation',data={'form_token':token})
    with client.session_transaction() as session: job=app.extensions['datatrust_m9_store'].jobs[session['m9_job']]
    job.update(state='completed',result=r,reviews=r.review_dispositions(),spec=s.to_dict())
    target=next(d['target_id'] for d in data(r,'identities')['details'] if d['reason']=='duplicate_logical_identity')
    response=client.post('/cross-representation/investigate',data={'form_token':token,'target':target})
    assert response.status_code==200 and b'Repeated logical identity' in response.data
    assert [x['excerpt'] for x in job['view']]==['private_duplicate','private_duplicate']
    assert 'private_duplicate' not in render_analysis_result(r)
    app.extensions['datatrust_m9_store'].cleanup()
