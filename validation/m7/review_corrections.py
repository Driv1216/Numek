"""Focused, authored M7 review fixture and artifacts; no model/historical rerun."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time

import numpy as np
from PIL import Image,ImageDraw
from pypdf import PdfReader
from datatrust import *
from datatrust.image_models import registry
from datatrust.image_presentation import report_view

ROOT=Path(__file__).parent


def synthetic_spec(root):
    root=Path(root); root.mkdir(parents=True,exist_ok=True)
    inputs=[]
    rng=np.random.default_rng(77)
    detection=rng.integers(30,225,(64,80,3),dtype=np.uint8)
    segmentation=rng.integers(30,225,(24,40,3),dtype=np.uint8)
    for role in ('train','test'):
        folder=root/role; folder.mkdir(exist_ok=True)
        Image.fromarray(detection).save(folder/'private-image.png')
        Image.fromarray(detection).save(folder/'near.jpg',quality=65 if role=='train' else 92)
        Image.new('RGB',(32,24),'black').save(folder/'dark.png')
        (folder/'corrupt.png').write_bytes(b'not an image')
        rows=([
            {'path':'private-image.png','id':'same','subject':'nullification','session':'left','objects':[{'category':1,'bbox':[2,3,20,25]}]},
            {'path':'private-image.png','id':'duplicate','subject':'other','session':'shared','objects':[{'category':1,'bbox':[-1,3,20,25]}]},
            {'path':'private-image.png','id':'duplicate','subject':None,'session':'shared','objects':[]},
            {'path':'corrupt.png','id':'corrupt','subject':'bad','session':None},
            {'path':'missing.png','id':'missing','subject':'unknown','objects':[]},
            {'path':'dark.png','id':'dark','subject':'dark','session':'one','objects':[{'category':99,'bbox':[0,0,12,12]}]},
            {'path':'near.jpg','id':'near','subject':'near','session':'left','objects':[]},
        ] if role=='train' else [
            {'path':'private-image.png','id':'same','subject':'nullification','session':'right','objects':[{'category':1,'bbox':[4,3,22,25]}]},
            {'path':'private-image.png','id':'other','subject':'third','session':'shared','width':40,'objects':[{'category':1,'bbox':[1,1,10,10]}]},
            {'path':'dark.png','id':'dark','subject':'dark','session':None,'objects':None},
            {'path':'near.jpg','id':'near','subject':'near','session':'right','objects':[]},
        ])
        path=folder/'data.jsonl'; path.write_text(''.join(json.dumps(x)+'\n' for x in rows))
        inputs.append(ImageInputSpec(role,ImageSourceSpec(str(path),'jsonl',str(folder)),ImageTaskSpec('detection'),ImageMappingSpec(logical_id='id',split=None,groups=('subject','session')),ImageAnnotationSpec(categories=(1,),expectation='required'),namespace='authored',role=role))
    for role,offset in [('reference',0),('current',6)]:
        folder=root/role; folder.mkdir(exist_ok=True)
        Image.fromarray(segmentation).save(folder/'private-image.png')
        mask=np.zeros((24,40),dtype=np.uint8); mask[3:11,2+offset:14+offset]=1
        Image.fromarray(mask).save(folder/'same-mask.png')
        path=folder/'data.jsonl'; path.write_text(json.dumps({'path':'private-image.png','id':'mask-1','mask':'same-mask.png'})+'\n')
        inputs.append(ImageInputSpec(role,ImageSourceSpec(str(path),'jsonl',str(folder)),ImageTaskSpec('segmentation'),ImageMappingSpec(logical_id='id'),ImageAnnotationSpec(categories=(1,),expectation='required'),role=role))
    return ImageAuditSpec(tuple(inputs),split_requirements=(ImageSplitRequirement('train','test',asset_separation=True,group_separation=True),),comparisons=(ImageComparisonSpec('train','test'),ImageComparisonSpec('reference','current')),allowed_roots=(str(root.absolute()),),dataset_name='M7 focused corrections - synthetic issue-rich review',purpose='Authored controls demonstrate concurrent integrity problems, declared separation, compatibility blockers and a changed mask. No customer content.')


def run(*,presentation_only=False,output_prefix=None):
    out=ROOT/'results/review_corrections'; out.mkdir(parents=True,exist_ok=True)
    if presentation_only:
        data=json.loads((out/'private-default.json').read_text())
        for key in ('examples','disclosure','export_identity'): data['profile'].pop(key,None)
        manifest=json.loads((out/'.datatrust-private'/data['profile']['audit_id']/'manifest.json').read_text())
        result=ImageAuditResult(**data,private=manifest)
        spec=ImageAuditSpec.from_dict(manifest['spec'])
        analysis_seconds=None  # reuse completed evidence; do not run analysis again
    else:
        spec=synthetic_spec(out/'fixture')
        config=replace(ImageAnalysisConfig(),quality_expectations={'min_width':64,'min_contrast':.05})
        started=time.monotonic(); result=DataTrust.audit_images(spec,config)
        analysis_seconds=time.monotonic()-started
    original=result.to_dict()
    prefix=output_prefix if output_prefix is not None else 'final-' if presentation_only else ''
    artifacts=result.generate_artifacts(out/(prefix+'private-default.pdf'),format='pdf',json_path=out/(prefix+'private-default.json'))
    ref=next(ref for ref,loc in result.private['locators'].items() if loc.get('normalized',{}).get('comparable') and loc['normalized']['task']=='segmentation')
    disclosed=result.generate_artifacts(out/(prefix+'synthetic-overlay.pdf'),format='pdf',json_path=out/(prefix+'synthetic-overlay.json'),disclosure=ImageDisclosureOptions((ref,),overlays=True),allowed_roots=spec.allowed_roots)
    assert result.to_dict()==original
    assert 'data:image/' not in Path(artifacts.html_path).read_text()
    assert 'data:image/jpeg;base64,' in Path(disclosed.html_path).read_text()
    for path in (artifacts.html_path,artifacts.json_path):
        text=Path(path).read_text()
        assert str((out/'fixture').absolute()) not in text
        assert 'nullification' not in text and 'private-image.png' not in text and 'same-mask.png' not in text
    qa=[]
    for pdf in (Path(artifacts.pdf_path),Path(disclosed.pdf_path)):
        folder=out/'pdf_qa'/pdf.stem; folder.mkdir(parents=True,exist_ok=True)
        reader=PdfReader(pdf); text='\n'.join(p.extract_text() or '' for p in reader.pages)
        for heading in ['Resolve source and identity problems','Resolve declared split separation','Review annotation integrity','Resolve comparison and coverage limits','Investigate visual and repetition evidence']:
            assert heading in text,(pdf.name,heading)
        subprocess.run([shutil.which('pdftoppm'),'-scale-to','1400','-png',str(pdf),str(folder/'page')],check=True,capture_output=True)
        pages=sorted(folder.glob('page-*.png')); assert len(pages)==len(reader.pages)
        for start in range(0,len(pages),4):
            sheet=Image.new('RGB',(1100,1540),'#dce5df'); draw=ImageDraw.Draw(sheet)
            for i,p in enumerate(pages[start:start+4]):
                with Image.open(p) as im:
                    im.thumbnail((520,730)); x=15+(i%2)*550; y=26+(i//2)*770
                    sheet.paste(im,(x,y)); draw.text((x,y-18),p.stem,fill='black')
            sheet.save(folder/f'contact-{start//4+1}.jpg')
        qa.append({'pdf':str(pdf.relative_to(ROOT)),'sha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),'pages':len(reader.pages),'rendered_pages':[str(p.relative_to(ROOT)) for p in pages],'visual_review':'pending'})
    ledger={'scope':'Independent M7 review corrections only; no encoder, historical or capacity reruns.','analysis_seconds':analysis_seconds,'presentation_reused_completed_analysis':presentation_only,'profile':result.profile,'coverage':result.coverage,'executive':report_view(result)['actions'],'public_defaults_checked':True,'projection_did_not_mutate_result':True,'benchmark_interpretation':registry()['review_evidence'],'pdf_qa':qa,'status':'rendered_pending_visual_review'}
    (out/'artifacts.json').write_text(json.dumps(ledger,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'out':str(out),'analysis_seconds':analysis_seconds,'pdfs':[(q['pdf'],q['pages']) for q in qa]},indent=2))


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(); parser.add_argument('--presentation-only',action='store_true'); parser.add_argument('--output-prefix')
    args=parser.parse_args(); run(presentation_only=args.presentation_only,output_prefix=args.output_prefix)
