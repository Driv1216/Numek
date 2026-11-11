"""Bounded registered transformations with independent validity accounting."""
import copy
from decimal import Decimal,InvalidOperation
import hashlib
import io
import json
from pathlib import Path
import unicodedata

import numpy as np

from ..contracts import EvaluationError,digest
from .contracts import TransformationSpec


def condition(record,p,unavailable=()):
    if p is None:return True
    if p['field'] in unavailable:return None
    v=record.get(p['field']);other=p['value'];op=p['op']
    if op=='missing':return (v is None or v=='')==p['value']
    if v is None or v=='':return None
    if op in {'eq','ne','in'}:return v==other if op=='eq' else v!=other if op=='ne' else v in other
    try:v=Decimal(str(v));other=Decimal(str(other))
    except InvalidOperation:return None
    return {'lt':v<other,'le':v<=other,'gt':v>other,'ge':v>=other}[op]


def feasible(original,record,constraints,relations):
    reasons=[];repaired=[]
    for field,c in constraints.items():
        v=record.get(field);before=original.get(field)
        if c.get('mutable',True) is False and v!=before:reasons.append('immutable_field:'+field);continue
        if v is None or v=='':continue
        if isinstance(v,list):
            try:
                x=np.asarray(v,float);before_array=np.asarray(before,float)
                if x.shape!=before_array.shape or not np.isfinite(x).all():raise ValueError()
                if c.get('integer') or c.get('step') or c.get('categories'):reasons.append('discrete_tensor_constraint_not_registered:'+field);continue
                if c.get('repair'):
                    repaired_x=np.clip(x,c.get('lower',-np.inf),c.get('upper',np.inf))
                    if not np.array_equal(x,repaired_x):record[field]=repaired_x.tolist();repaired.append(field)
                    x=repaired_x
                if np.any(x<c.get('lower',-np.inf)) or np.any(x>c.get('upper',np.inf)):reasons.append('tensor_bounds:'+field)
            except (TypeError,ValueError):reasons.append('invalid_tensor_constraint:'+field)
            continue
        if 'categories' in c:
            if v not in c['categories']:reasons.append('category_constraint:'+field)
            continue
        try:x=Decimal(str(v))
        except InvalidOperation:reasons.append('non_numeric_constraint:'+field);continue
        if not x.is_finite():reasons.append('nonfinite_constraint:'+field);continue
        old=x
        if c.get('repair'):
            if 'lower' in c:x=max(x,Decimal(str(c['lower'])))
            if 'upper' in c:x=min(x,Decimal(str(c['upper'])))
            if c.get('integer'):x=x.to_integral_value()
            if c.get('step'):
                step=Decimal(str(c['step']));origin=Decimal(str(c.get('lower',0)));x=origin+((x-origin)/step).to_integral_value()*step
            if x!=old:record[field]=str(x);repaired.append(field)
        if 'lower' in c and x<Decimal(str(c['lower'])) or 'upper' in c and x>Decimal(str(c['upper'])):reasons.append('bounds_constraint:'+field)
        if c.get('integer') and x!=x.to_integral_value():reasons.append('integer_constraint:'+field)
        if c.get('step') and (x-Decimal(str(c.get('lower',0))))%Decimal(str(c['step']))!=0:reasons.append('step_constraint:'+field)
    for r in relations:
        try:
            value=sum(Decimal(str(v))*Decimal(str(record[f])) for f,v in r['coefficients'].items());bound=Decimal(str(r['bound']));tol=Decimal(str(r.get('tolerance',0)))
            ok=value<=bound+tol if r['operator']=='le' else value>=bound-tol if r['operator']=='ge' else abs(value-bound)<=tol
        except (KeyError,TypeError,InvalidOperation):ok=False
        if not ok:reasons.append('cross_field_constraint')
    return not reasons,reasons,repaired


def canonical_image(path,prepared,limits):
    from PIL import Image,ImageOps
    if path not in prepared.assets:raise EvaluationError('Image was not captured.','image_input')
    with Image.open(prepared.assets[path]) as image:
        if image.width*image.height>limits.max_image_pixels:raise EvaluationError('Image decoding pixel limit exceeded.','image_limit')
        return ImageOps.exif_transpose(image).convert('RGB')


def transform(record,t,rng,prepared,permuted=None):
    out=copy.deepcopy(record);p=t.parameters;op=t.operation;changes=[]
    block_missing=op=='missing' and p.get('mode')=='block' and rng.random()<p.get('rate',1.)
    for f in t.fields:
        old=out.get(f);value=old
        if op=='identity':pass
        elif op=='missing':
            selected=block_missing if p.get('mode')=='block' else rng.random()<p.get('rate',1.)
            if condition(record,p.get('condition')) is True and selected:value=''
        elif op=='set':value=p.get('values',{}).get(f,old)
        elif op=='permutation':value=(permuted or {}).get(f,old)
        elif op=='category':
            if rng.random()<p.get('rate',1.):
                choices=p.get('transitions',{}).get(str(old),[])
                if choices:value=choices[int(rng.integers(len(choices)))]
        elif op in {'noise','round','censor','finite_difference'}:
            if old is None or old=='':continue
            if t.stage=='tensor':
                try:x=np.asarray(old,float)
                except (ValueError,TypeError):return out,{'structural_valid':False,'domain_feasible':None,'reason':'invalid_tensor','repairs':[]}
                if not isinstance(old,list) or not x.size or not np.isfinite(x).all():return out,{'structural_valid':False,'domain_feasible':None,'reason':'invalid_tensor','repairs':[]}
                if op=='noise':
                    z=rng.normal(0,p.get('scale',1.),x.shape);value=x*(1+z) if p.get('mode','additive')=='multiplicative' else x+z
                elif op=='round':value=np.rint(x/p.get('step',1.))*p.get('step',1.)
                elif op=='censor':value=np.clip(x,p.get('lower',-np.inf),p.get('upper',np.inf))
                else:value=x+p.get('step',.01)*p.get('direction',1)
                if not np.isfinite(value).all():return out,{'structural_valid':False,'domain_feasible':None,'reason':'nonfinite_tensor','repairs':[]}
                out[f]=value.tolist();changes.append(f);continue
            try:x=float(old)
            except (ValueError,TypeError):return out,{'structural_valid':False,'domain_feasible':None,'reason':'non_numeric_transformation','repairs':[]}
            if op=='noise':
                z=float(rng.normal(0,p.get('scale',1.)));value=x*(1+z) if p.get('mode','additive')=='multiplicative' else x+z
            elif op=='round':value=float((Decimal(str(old))/Decimal(str(p.get('step',1.)))).to_integral_value()*Decimal(str(p.get('step',1.))))
            elif op=='censor':value=min(p.get('upper',float('inf')),max(p.get('lower',-float('inf')),x))
            else:value=x+p.get('step',.01)*p.get('direction',1)
        elif op.startswith('text_'):
            if not isinstance(old,str):return out,{'structural_valid':False,'domain_feasible':None,'reason':'text_input_type','repairs':[]}
            if op=='text_whitespace':value=' '.join(old.split()) if p.get('mode','collapse')=='collapse' else old.replace(' ','  ')
            elif op=='text_unicode':
                form=p.get('form','NFC')
                if form not in {'NFC','NFD','NFKC','NFKD'}:raise EvaluationError('Unknown Unicode normalization.')
                value=unicodedata.normalize(form,old)
            elif op=='text_truncate':value=old[:p.get('characters',256)]
            elif op=='text_span':
                spans=p.get('spans',[])
                if not isinstance(spans,list) or len(spans)>1024:raise EvaluationError('Bounded registered spans required.')
                cursor=0;parts=[]
                for span in spans:
                    if set(span)!={'start','end','replacement'} or any(type(span[k]) is not int for k in ('start','end')) or not isinstance(span['replacement'],str) or not cursor<=span['start']<=span['end']<=len(old):raise EvaluationError('Text spans must be ordered, disjoint and within input bounds.')
                    parts.extend([old[cursor:span['start']],span['replacement']]);cursor=span['end']
                parts.append(old[cursor:]);value=''.join(parts)
            else:
                chars=list(old)
                for _ in range(p.get('edits',1)):
                    if not chars:break
                    i=int(rng.integers(len(chars)));mode=p.get('mode','delete')
                    if mode=='delete':chars.pop(i)
                    elif mode=='replace':chars[i]='?'
                    elif i+1<len(chars):chars[i],chars[i+1]=chars[i+1],chars[i]
                value=''.join(chars)
        elif op.startswith('image_'):
            from PIL import Image,ImageFilter,ImageEnhance
            image=canonical_image(old,prepared,prepared.spec.limits)
            if op=='image_noise':
                a=np.asarray(image,dtype=np.float32)/255.;a=np.clip(a+rng.normal(0,p.get('scale',.05),a.shape),0,1);image=Image.fromarray(np.rint(a*255).astype(np.uint8))
            elif op=='image_blur':image=image.filter(ImageFilter.GaussianBlur(p.get('radius',1.)))
            elif op=='image_brightness':image=ImageEnhance.Brightness(image).enhance(p.get('factor',1.))
            elif op=='image_contrast':image=ImageEnhance.Contrast(image).enhance(p.get('factor',1.))
            elif op=='image_compression':
                quality=p.get('quality',75)
                if type(quality) is not int or not 1<=quality<=100:raise EvaluationError('Invalid JPEG quality.')
                stream=io.BytesIO();image.save(stream,format='JPEG',quality=quality);stream.seek(0)
                with Image.open(stream) as compressed:image=compressed.convert('RGB').copy()
            elif op=='image_occlusion':
                a=np.asarray(image).copy();x0,y0,x1,y1=p.get('box',[0,0,image.width//4,image.height//4])
                if not 0<=x0<=x1<=image.width or not 0<=y0<=y1<=image.height:raise EvaluationError('Occlusion box is out of bounds.')
                a[y0:y1,x0:x1]=p.get('value',0);image=Image.fromarray(a)
            else:
                mode=p.get('mode','flip_horizontal')
                if mode=='flip_horizontal':image=image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                elif mode=='rotate':image=image.rotate(p.get('angle',0))
                else:raise EvaluationError('Unsupported image geometry.')
            stream=io.BytesIO();image.save(stream,format='PNG');raw=stream.getvalue();sha=hashlib.sha256(raw).hexdigest()
            path=prepared.work.root/('transformed-'+sha+'.png')
            if not path.exists():prepared.work.check('transformed media reservation',len(raw));path.write_bytes(raw)
            value=str(path);prepared.assets[value]=str(path)
            if not hasattr(prepared,'generated_assets'):prepared.generated_assets={}
            prepared.generated_assets[value]={'path':str(path),'sha256':sha,'bytes':len(raw)}
        else:raise EvaluationError('Transformation implementation is absent.','transformation_unavailable')
        if isinstance(value,float) and not np.isfinite(value):return out,{'structural_valid':False,'domain_feasible':None,'reason':'nonfinite_transformation','repairs':[]}
        out[f]=value
        if old!=value:changes.append(f)
    valid,reasons,repairs=feasible(record,out,t.constraints,t.relations)
    return out,{'structural_valid':True,'domain_feasible':valid,'reason':reasons,'repairs':repairs,'changed_fields':changes,
                'realism':t.realism,'label_preservation_established':False,'stage':t.stage}


def transformed_truth(original,relation,rule,variant_outcomes,identity,task):
    if relation in {'unknown','reference_label_diagnostic'}:return {'value':None,'valid':False,'reason':'unknown_transformed_outcome'}
    if relation=='authoritative_variant':
        value=variant_outcomes.get(identity)
        if not isinstance(value,dict) or value.get('status') not in {'observed','final'} or not value.get('authority'):return {'value':None,'valid':False,'reason':'variant_outcome_unavailable'}
        y=value.get('value');valid=type(y) in (int,float) and np.isfinite(y) if task.kind=='regression' else y in task.classes
        return {'value':y if valid else None,'valid':bool(valid),'reason':None if valid else 'variant_outcome_invalid'}
    if relation=='registered_transform' and original['valid']:
        y=original['value']
        y=rule.get('factor',1.)*y+rule.get('offset',0.) if rule['operation']=='affine_regression_v1' else rule['classes'][y]
        valid=bool(np.isfinite(y)) if task.kind=='regression' else y in task.classes
        return {'value':y if valid else None,'valid':valid,'reason':None if valid else 'transformed_outcome_nonfinite'}
    return copy.deepcopy(original)


def variant(event,scenario,replicate,seed,prepared,permuted=None):
    out=copy.deepcopy(event);ledger=[]
    rng=np.random.Generator(np.random.PCG64(int(digest([seed,event['event_key'],scenario.id,replicate])[:16],16)))
    for t in scenario.transformations:
        if t.parameters.get('condition',{}).get('field') in event.get('unavailable_fields',[]):
            ledger.append({'transformation':t.id,'structural_valid':True,'domain_feasible':False,'reason':'conditional_feature_unavailable','repairs':[]});continue
        out['record'],validity=transform(out['record'],t,rng,prepared,(permuted or {}).get(t.id))
        ledger.append({'transformation':t.id,**validity})
    content={k:({'asset_sha256':prepared.generated_assets[v]['sha256']} if isinstance(v,str) and v in getattr(prepared,'generated_assets',{}) else v) for k,v in out['record'].items()}
    identity=digest([event['event_key'],scenario.id,replicate,content])
    out['truth']=transformed_truth(event['truth'],scenario.outcome_relation,scenario.outcome_rule,scenario.variant_outcomes,identity,prepared.spec.task)
    out['variant']={'id':identity,'root_event':event['event_key'],'scenario':scenario.id,'replicate':replicate,
                    'outcome_relation':scenario.outcome_relation,'outcome_reason':scenario.outcome_reason,'outcome_rule':scenario.outcome_rule,'validity':ledger,
                    'applicable':all(v['structural_valid'] and v['domain_feasible'] for v in ledger),'input_record':out['record']}
    return out


def materialized_content(record,prepared):
    return {k:({'asset_sha256':prepared.generated_assets[v]['sha256']} if isinstance(v,str) and v in getattr(prepared,'generated_assets',{}) else v) for k,v in record.items()}
