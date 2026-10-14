"""Paired image-text pipeline on pinned supplied COCO captions and planted swaps.

Truth concerns the supplied association, not universal caption factual correctness.
Natural media remains in its existing private M7 namespace.
"""
from dataclasses import replace
from pathlib import Path
import csv
import hashlib
import json
import zipfile
from collections import Counter

from datatrust import *
from datatrust.cross import _core
from datatrust.cross_models import preflight,algorithm_identity
from datatrust.image_assets import capture,decode
from datatrust.image_contracts import ImageWorkLimits
from datatrust.worker import run_supervised
from validation.m9.benchmark import benchmark_stage

ROOT=Path(__file__).parent.absolute();MEDIA=ROOT.parent/'m7/data';REGISTRY=ROOT.parents[1]/'src/datatrust/cross_model_artifacts.json'


def population(split,images,captions,categories):
    root=ROOT/'data'/('image_'+split);root.mkdir(parents=True,exist_ok=True);records=[];assets=[];truth={}
    for j,image in enumerate(images):
        iid=str(image['id']);assets.append({'id':iid,'path':image['path']})
        other=next((x for x in images[j+1:]+images[:j] if not categories[image['id']]&categories[x['id']]),images[(j+1)%len(images)])
        for ci,caption in enumerate(captions[image['id']][:5]):
            for label,linked in [('correct',iid),('swap',str(other['id']))]:
                record_id=f'{split}-{iid}-{ci}-{label}';records.append({'id':record_id,'image_id':linked,'caption':caption});truth[record_id]=label
    for name,rows in [('records',records),('images',assets)]:
        with (root/(name+'.csv')).open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
    spec=CrossRepresentationAuditSpec((CrossRepresentationInputSpec('records',str(root/'records.csv'),language='en'),CrossRepresentationInputSpec('images',str(root/'images.csv'),kind='image',asset_root=str(MEDIA),layout='coco_captions_v1',language='en')),relationships=(RelationshipSpec('captions','records','images',left_keys=('image_id',),cardinality='many_to_one',meaning='caption'),),rules=(ReconciliationRule('caption','captions','caption',right_field='path',method='image_text',claim_language='en'),),allowed_roots=(str(root),str(MEDIA)))
    return spec,truth


def metrics(answers,truth,threshold):
    counts=Counter()
    for target,label in truth.items():
        a=answers.get(target,{});p=a.get('predictions',[])
        prediction='flag' if p and p[0]['score']<threshold else 'clear' if p else 'abstained'
        counts[label+'_'+prediction]+=1
    tp=counts['swap_flag'];fp=counts['correct_flag'];positives=sum(v for k,v in counts.items() if k.startswith('swap_'))
    return {'counts':dict(counts),'precision':tp/(tp+fp) if tp+fp else 0,'recall':tp/positives if positives else 0,'correct_associations':sum(v for k,v in counts.items() if k.startswith('correct_')),'planted_swaps':positives,'unexamined':len(truth)-len(answers),'threshold':threshold}


def run():
    manifest=json.loads((MEDIA/'natural_manifest.json').read_text());captions={};categories={x['id']:set() for x in manifest['images']}
    with zipfile.ZipFile(MEDIA/'annotations_trainval2017.zip') as z:
        for x in json.loads(z.read('annotations/captions_val2017.json'))['annotations']: captions.setdefault(x['image_id'],[]).append(x['caption'])
        for x in json.loads(z.read('annotations/instances_val2017.json'))['annotations']:
            if x['image_id'] in categories: categories[x['image_id']].add(x['category_id'])
    eligible=[]
    for image in manifest['images']:
        info,raw,_=capture(MEDIA/image['path'],(MEDIA,),max_bytes=128*1024**2)
        if info['sha256']!=image['sha256']: raise ValueError('Pinned natural image changed.')
        facts,preview=decode(raw,ImageWorkLimits())
        if preview is not None: eligible.append(image)
    # 20 calibration families; remaining 47 untouched held-out families => 235 pairs per class.
    cfg=CrossRepresentationAnalysisConfig(models=CrossModelOptions(image_text_directory=str(ROOT/'models/image_text')))
    p=preflight(cfg.models);p['image_text']['qualification']={'threshold':-2};runs={};threshold=None
    for split,images in [('calibration',eligible[:20]),('held_out',eligible[20:])]:
        spec,original_truth=population(split,images,captions,categories);r=run_supervised(_core,(spec,cfg,p),cfg.execution);truth={}
        keys=list(original_truth)
        for item in r.private['model_inputs']: truth[item['target_id']]=original_truth[keys[r.private['locators'][item['claim_reference']]['record']['ordinal']-1]]
        stage=run_supervised(benchmark_stage,(r.private['model_inputs'],p,cfg,cfg.limits.model_seconds),cfg.execution)
        answers={x['target_id']:x for x in stage.profile['answers']}
        if split=='calibration':
            scores=sorted({v['predictions'][0]['score'] for v in answers.values() if v.get('predictions')});grid=[metrics(answers,truth,t) for t in scores]
            viable=[x for x in grid if x['precision']>=.95]
            chosen=max(viable or grid,key=lambda x:(x['precision']>=.95,x['recall'],x['precision']))
            threshold=chosen['threshold']
        m=metrics(answers,truth,threshold);runs[split]={'metrics':m,'execution':stage.execution,'coverage':stage.coverage,'core_execution':r.execution,'families':len(images),'ids_sha256':hashlib.sha256(json.dumps([x['id'] for x in images]).encode()).hexdigest()};print(split,m,flush=True)
    held=runs['held_out']['metrics'];passed=held['precision']>=.9 and held['recall']>=.6 and min(held['correct_associations'],held['planted_swaps'])>=200
    reg=json.loads(REGISTRY.read_text());reg['qualification']['image_text']={'status':'passed' if passed else 'failed','algorithm_identity':algorithm_identity(),'revision':reg['models']['image_text']['revision'],'threshold':threshold,'scope':'Pinned COCO supplied captions and planted association swaps; caption truth and external validity are not established.','eligible_layouts':['coco_captions_v1'],'eligible_mapping_kinds':['field'],'held_out':held,'ledger':'validation/m9/results/image_qualification.json'}
    REGISTRY.write_text(json.dumps(reg,indent=2)+'\n');(ROOT/'results/image_qualification.json').write_text(json.dumps({'pipeline':'manifest admission -> verified decode -> paired image/text tokens -> score -> emitted candidate','source_manifest_sha256':hashlib.sha256((MEDIA/'natural_manifest.json').read_bytes()).hexdigest(),'archive_sha256':manifest['annotation_archive_sha256'],'eligibility':'M7 opaque RGB previews; ICC and alpha exclusions apply.','negative_truth':'Planted association swaps prefer disjoint supplied object taxonomies; they are not independently adjudicated false captions.','runs':runs,'qualification':reg['qualification']['image_text']},indent=2)+'\n')


if __name__=='__main__': run()
