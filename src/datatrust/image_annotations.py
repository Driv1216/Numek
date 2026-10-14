"""Supplied annotation integrity and verified coordinate mappings, never correction."""
from collections import Counter
import hashlib
import io
import json
import math

from datatrust.image_assets import capture, oriented_point, error


def absent(value): return isinstance(value,dict) and value=={'__absent__':True}

def state(value):
    if absent(value): return 'absent'
    if value is None: return 'null'
    if value==[]: return 'empty'
    return 'observed'

def scalar(value): return isinstance(value,(str,int)) and not isinstance(value,bool) and value!=''

def canonical(value): return json.dumps(value,sort_keys=True,ensure_ascii=True,separators=(',',':'),allow_nan=False)

def frame(spec,asset,payload):
    if asset.get('decode')!='decoded': return None,'image_dimensions_unavailable'
    if spec.coordinate_frame=='unknown': return None,'unknown_coordinate_frame'
    w,h=asset['width'],asset['height']; ow,oh=(h,w) if asset['orientation']>=5 else (w,h)
    if spec.coordinate_frame=='encoded': fw,fh=w,h
    elif spec.coordinate_frame=='oriented': fw,fh=ow,oh
    else: fw,fh=spec.frame_width,spec.frame_height
    for key,expected in [('declared_width',fw),('declared_height',fh)]:
        observed=payload.get(key,{'__absent__':True})
        if not absent(observed) and observed is not None and (isinstance(observed,bool) or observed!=expected): return None,'declared_dimension_mismatch'
    if spec.frame_width and (spec.frame_width,spec.frame_height)!=(fw,fh): return None,'declared_dimension_mismatch'
    def transform(x,y):
        if spec.coordinate_frame=='oriented': return x,y
        if spec.coordinate_frame=='declared':
            a,b,c,d,e,f=spec.transform; x,y=a*x+b*y+c,d*x+e*y+f
        return oriented_point(x,y,w,h,asset['orientation'])
    # The supplied affine frame must map its corners into the actual image.
    if spec.coordinate_frame=='declared':
        points=[transform(x,y) for x,y in [(0,0),(fw,0),(0,fh),(fw,fh)]]
        if any(not -1e-9<=x<=ow+1e-9 or not -1e-9<=y<=oh+1e-9 for x,y in points): return None,'frame_mapping_out_of_bounds'
    return {'width':fw,'height':fh,'oriented_width':ow,'oriented_height':oh,'transform':transform,
            'basis':{'frame':spec.coordinate_frame,'width':fw,'height':fh,'transform':list(spec.transform)}},None


def box(value,fmt,geometry):
    if not isinstance(value,list) or len(value)!=4 or any(isinstance(x,bool) or not isinstance(x,(float,int)) or not math.isfinite(x) for x in value): raise ValueError('invalid_box_values')
    if geometry is None: raise ValueError('coordinate_comparison_blocked')
    w,h=geometry['width'],geometry['height']; a,b,c,d=value
    if fmt=='xywh': x1,y1,x2,y2=a,b,a+c,b+d
    elif fmt=='normalized_cxcywh': x1,y1,x2,y2=(a-c/2)*w,(b-d/2)*h,(a+c/2)*w,(b+d/2)*h
    else: x1,y1,x2,y2=a,b,c,d
    if not 0<=x1<x2<=w or not 0<=y1<y2<=h: raise ValueError('box_out_of_bounds_or_nonpositive')
    points=[geometry['transform'](x,y) for x,y in [(x1,y1),(x2,y1),(x1,y2),(x2,y2)]]
    xs,ys=zip(*points)
    return [min(xs),min(ys),max(xs),max(ys)]


def rle_counts(value,limit):
    if isinstance(value,list):
        if len(value)>limit: error('rle_run_limit')
        if any(isinstance(x,bool) or not isinstance(x,int) or x<0 for x in value): raise ValueError('invalid_rle_counts')
        return value
    if not isinstance(value,str): raise ValueError('invalid_rle_counts')
    counts=[]; p=0
    while p<len(value):
        x=0; shift=0
        while True:
            if p>=len(value): raise ValueError('unterminated_rle')
            c=ord(value[p])-48; p+=1
            if not 0<=c<=63 or shift>=65: raise ValueError('invalid_rle_encoding')
            x|=(c&31)<<shift; shift+=5
            if not c&32:
                if c&16: x|=-1<<shift
                break
        if len(counts)>2: x+=counts[-2]
        if x<0: raise ValueError('negative_rle_run')
        counts.append(x)
        if len(counts)>limit: error('rle_run_limit')
    return counts


def segmentation(value,w,h,limits,budget):
    import numpy as np
    if isinstance(value,dict):
        size=value.get('size')
        if size!=[h,w] or any(isinstance(v,bool) for v in size or []): raise ValueError('rle_dimension_mismatch')
        counts=rle_counts(value.get('counts'),limits.rle_runs)
        if sum(counts)!=w*h: raise ValueError('rle_run_total')
        area=sum(counts[1::2]); bitmap=None
        if budget[0]+w*h<=limits.segmentation_pixels and w*h<=limits.pixels_per_asset:
            budget[0]+=w*h; flat=np.zeros(w*h,dtype=np.uint8); pos=0
            for i,n in enumerate(counts):
                if i%2: flat[pos:pos+n]=1
                pos+=n
            bitmap=flat.reshape((h,w),order='F')
        return {'kind':'rle','area':area,'empty':area==0,'runs':len(counts)},bitmap
    if not isinstance(value,list) or not value: raise ValueError('invalid_polygon_collection')
    vertices=0
    for polygon in value:
        if not isinstance(polygon,list) or len(polygon)<6 or len(polygon)%2 or any(isinstance(v,bool) or not isinstance(v,(float,int)) or not math.isfinite(v) for v in polygon): raise ValueError('invalid_polygon')
        vertices+=len(polygon)//2
        if vertices>limits.polygon_vertices: error('polygon_vertex_limit')
        points=list(zip(polygon[::2],polygon[1::2]))
        if any(not 0<=x<=w or not 0<=y<=h for x,y in points): raise ValueError('polygon_out_of_bounds')
        area=abs(sum(x*y2-x2*y for (x,y),(x2,y2) in zip(points,points[1:]+points[:1])))/2
        if area==0: raise ValueError('degenerate_polygon')
    bitmap=None
    if budget[0]+w*h<=limits.segmentation_pixels and w*h<=limits.pixels_per_asset:
        from pycocotools import mask
        budget[0]+=w*h
        encoded=mask.frPyObjects(value,h,w); bitmap=mask.decode(mask.merge(encoded))
    return {'kind':'polygons','vertices':vertices,'area':int(bitmap.sum()) if bitmap is not None else None,'raster_examined':bitmap is not None},bitmap


def mask_file(store,item,path,asset,geometry,budget):
    import numpy as np
    from PIL import Image
    info,raw=store.media_file(path,item.id,kind='mask')
    if raw is None:
        _,raw,seconds=capture(path,store.roots,max_bytes=store.config.source_limits.asset_capture_bytes,expected=info,check=store.check)
        store.read_bytes+=info['bytes']; store.hash_seconds+=seconds
    if raw is None: raise ValueError('mask_capture_safety_excluded')
    with Image.open(io.BytesIO(raw)) as mask:
        if mask.format!='PNG' or getattr(mask,'n_frames',1)!=1: raise ValueError('unsupported_mask_format')
        if mask.width*mask.height>store.config.limits.pixels_per_asset or mask.width*mask.height*16>store.config.limits.decode_bytes: raise ValueError('mask_pixel_safety_excluded')
        if geometry is None or mask.size!=(geometry['width'],geometry['height']): raise ValueError('mask_frame_mismatch')
        store.decoded_pixels+=mask.width*mask.height
        if store.decoded_pixels>store.config.limits.decoded_pixels: error('decoded_pixel_work_limit')
        mask.load(); data=np.asarray(mask)
        spec=item.annotations
        if spec.mask_encoding=='rgb_png':
            if data.ndim!=3 or data.shape[2]!=3 or not spec.color_mapping: raise ValueError('rgb_mask_mapping_required')
            colors,counts=np.unique(data.reshape(-1,3),axis=0,return_counts=True)
            occupancy={}; observed_categories=[]; foreground_pixels=0
            for color,n in zip(colors,counts):
                key=','.join(map(str,color))
                if key not in spec.color_mapping: raise ValueError('unmapped_mask_color')
                cat=spec.color_mapping[key]; occupancy[str(cat)]=occupancy.get(str(cat),0)+int(n)
                if cat not in observed_categories: observed_categories.append(cat)
                if cat not in spec.background+spec.ignore: foreground_pixels+=int(n)
        else:
            if data.ndim!=2 or data.dtype.kind not in 'uib': raise ValueError('mask_integer_ids_required')
            ids,counts=np.unique(data,return_counts=True)
            if spec.mask_encoding=='binary_png' and set(map(int,ids))-{0,1,255}: raise ValueError('nonbinary_instance_mask')
            occupancy={str(int(v)):int(n) for v,n in zip(ids,counts)}
        allowed=set(map(str,spec.categories+spec.background+spec.ignore))
        if spec.mask_encoding!='binary_png' and spec.categories and set(occupancy)-allowed: raise ValueError('unknown_mask_category')
        if spec.mask_encoding=='binary_png':
            background=set(spec.background+spec.ignore); active=~np.isin(data,list(background)); data=active.astype('uint8')
            occupancy={'foreground':int(active.sum()),'background':int(active.size-active.sum())}
        aligned=orient_mask(data,spec,asset,geometry)
        digest=hashlib.sha256(aligned.tobytes() if spec.mask_encoding=='binary_png' else aligned.astype('<i8').tobytes()+canonical({'size':aligned.shape,'color_mapping':spec.color_mapping}).encode()).hexdigest()
        detail={'kind':'mask','empty':not any(v for k,v in occupancy.items() if k not in {'background',*map(str,spec.background+spec.ignore)}),'occupancy':occupancy,'pixels':mask.width*mask.height,'raster_sha256':digest,'path':str(path)}
        if spec.mask_encoding=='rgb_png': detail.update(observed_categories=observed_categories,foreground_pixels=foreground_pixels,empty=foreground_pixels==0)
        return detail,data


def orient_mask(data,spec,asset,geometry):
    import numpy as np
    from PIL import Image
    if spec.coordinate_frame=='declared':
        a,b,c,d,e,f=spec.transform
        if b or d or c or f or abs(a*geometry['width']-asset['width'])>1e-9 or abs(e*geometry['height']-asset['height'])>1e-9 or a<=0 or e<=0:
            raise ValueError('mask_common_coverage_unresolved')
        data=np.asarray(Image.fromarray(data).resize((asset['width'],asset['height']),Image.Resampling.NEAREST))
    if spec.coordinate_frame!='oriented':
        orientation=asset['orientation']
        if orientation==2: data=np.fliplr(data)
        elif orientation==3: data=np.rot90(data,2)
        elif orientation==4: data=np.flipud(data)
        elif orientation==5: data=np.swapaxes(data,0,1)
        elif orientation==6: data=np.rot90(data,-1)
        elif orientation==7: data=np.flipud(np.fliplr(np.swapaxes(data,0,1)))
        elif orientation==8: data=np.rot90(data,1)
    return np.ascontiguousarray(data)


def normalize(store,item,oid,payload,asset,objects=None):
    spec=item.annotations; task=item.task.kind
    geometry,blocked=frame(spec,asset,payload)
    value=payload['labels'] if task in {'classification','multilabel_classification'} else payload['mask'] if task=='segmentation' and not absent(payload['mask']) else objects if objects is not None else payload['objects']
    observed=state(value); reasons=[]; labels=[]; normalized=[]; segment_details=[]
    status=payload.get('status'); supplied_status=spec.status_mapping.get(status,status if status in {'complete','partial','uncertain','intentionally_unlabeled','unknown'} else 'unknown') if isinstance(status,str) else 'unknown'
    expectation='required' if supplied_status=='complete' else spec.expectation
    if expectation=='required' and observed in {'absent','null'}: reasons.append('required_annotation_missing')
    if task=='unlabeled': observed='not_applicable'
    elif task=='classification':
        if observed=='observed':
            if not scalar(value): reasons.append('invalid_classification_label')
            else: labels=[value]
    elif task=='multilabel_classification':
        if observed in {'observed','empty'}:
            if not isinstance(value,list): reasons.append('invalid_multilabel_collection')
            else:
                labels=[v for v in value if scalar(v)]
                if len(labels)!=len(value): reasons.append('invalid_multilabel_member')
                if len(set(canonical(v) for v in labels))!=len(labels): reasons.append('duplicate_multilabel_member')
    elif task=='segmentation' and not absent(payload['mask']) and isinstance(payload['mask'],str):
        root=Path(item.source.asset_root or (item.source.path if item.source.format=='directory' else Path(item.source.path).parent))
        try:
            detail,_=mask_file(store,item,root/payload['mask'],asset,geometry,store.segment_budget)
            segment_details.append(detail)
            if spec.mask_encoding=='binary_png':
                if scalar(payload['labels']): labels.append(payload['labels'])
            elif spec.mask_encoding=='rgb_png': labels.extend(v for v in detail['observed_categories'] if v not in spec.background+spec.ignore)
            else: labels.extend(int(k) if k.isdigit() else k for k in detail['occupancy'] if k not in set(map(str,spec.background+spec.ignore)))
            normalized.append({'mask_sha256':detail['raster_sha256']})
        except ValueError as exc: reasons.append(str(exc))
    elif observed in {'observed','empty'}:
        if not isinstance(value,list): reasons.append('invalid_object_collection')
        else:
            provided_ids=[canonical(obj['id']) for obj in value if isinstance(obj,dict) and 'id' in obj]
            if len(provided_ids)!=len(set(provided_ids)): reasons.append('duplicate_object_identity')
            for ordinal,obj in enumerate(value):
                store.annotation_visits+=1
                if store.annotation_visits>store.config.limits.annotations: error('annotation_limit')
                if not isinstance(obj,dict): reasons.append('invalid_object'); continue
                cat=obj.get('category',obj.get('category_id'))
                if not scalar(cat): reasons.append('invalid_object_category'); continue
                labels.append(cat); part={'category':cat,'annotation_ref':'annotation_'+hashlib.sha256(f'{store.audit_id}:{oid}:{spec.scheme}:{ordinal}'.encode()).hexdigest()[:24]}
                if 'id' in obj: part['id']=obj['id']
                if 'iscrowd' in obj and (isinstance(obj['iscrowd'],bool) or obj['iscrowd'] not in {0,1}): reasons.append('invalid_crowd_flag')
                part['crowd']=obj.get('iscrowd',0)
                if 'bbox' in obj:
                    try: part['bbox']=box(obj['bbox'],obj.get('format','xywh' if item.source.format=='coco' else spec.box_format),geometry)
                    except ValueError as exc: reasons.append(str(exc))
                elif task=='detection': reasons.append('missing_object_box')
                if task=='segmentation':
                    try:
                        if geometry is None: raise ValueError('coordinate_comparison_blocked')
                        if isinstance(obj.get('mask'),str):
                            root=Path(item.source.asset_root or Path(item.source.path).parent)
                            detail,bitmap=mask_file(store,item,root/obj['mask'],asset,geometry,store.segment_budget)
                            part['segmentation']=detail['raster_sha256']; part['mask_path']=str((root/obj['mask']).absolute())
                            segment_details.append(detail)
                            normalized.append(part)
                            continue
                        detail,bitmap=segmentation(obj.get('segmentation'),geometry['width'],geometry['height'],store.config.limits,store.segment_budget)
                        store.vertices+=detail.get('vertices',0); store.runs+=detail.get('runs',0)
                        if store.vertices>store.config.limits.polygon_vertices or store.runs>store.config.limits.rle_runs: error('segmentation_work_limit')
                        segment_details.append(detail)
                        if bitmap is not None:
                            bitmap=orient_mask(bitmap,spec,asset,geometry)
                        part['segmentation']=hashlib.sha256(bitmap.tobytes()).hexdigest() if bitmap is not None else obj.get('segmentation')
                        part['segmentation_source']=obj.get('segmentation')
                        if bitmap is None: reasons.append('segmentation_raster_comparison_unexamined')
                    except ValueError as exc: reasons.append(str(exc))
                normalized.append(part)
    categories=spec.categories or tuple(store.categories.get(item.id,()))
    if categories and any(v not in categories or type(v)!=type(next((c for c in categories if c==v),None)) for v in labels): reasons.append('unknown_category')
    if blocked and task in {'detection','segmentation'} and observed in {'observed','empty'}: reasons.append('geometric_checks_blocked')
    blockers=[r for r in reasons if r in {'coordinate_comparison_blocked','geometric_checks_blocked','segmentation_raster_comparison_unexamined','mask_common_coverage_unresolved'}]
    reasons=[r for r in reasons if r not in blockers]
    if blocked=='declared_dimension_mismatch': reasons.append(blocked)
    comparable=not blockers and not reasons and (task in {'classification','multilabel_classification'} or (geometry is not None and not reasons and observed in {'observed','empty'}))
    result={'annotation_ref':'annotation_'+hashlib.sha256(f'{store.audit_id}:{oid}:{spec.scheme}:bundle'.encode()).hexdigest()[:24],'validity':'partial' if reasons and (labels or normalized or segment_details) else 'invalid' if reasons else 'valid' if observed in {'observed','empty'} else 'unobserved','task':task,'scheme':spec.scheme,'observation':observed,'expectation':expectation,'status':supplied_status,'reasons':sorted(set(reasons)),'blocked_checks':sorted(set(blockers)),
            'labels':labels,'objects':normalized,'segmentation':segment_details,'frame':geometry['basis'] if geometry else None,
            'oriented_size':[geometry['oriented_width'],geometry['oriented_height']] if geometry else None,'frame_block_reason':blocked,
            'comparable':comparable,'taxonomy':list(categories),'taxonomy_identity':hashlib.sha256(canonical(store.category_definitions.get(item.id,list(categories))).encode()).hexdigest()}
    result['payload_sha256']=hashlib.sha256(canonical(value).encode()).hexdigest()
    result['normalized_sha256']=hashlib.sha256(canonical({'labels':sorted(labels,key=canonical),'objects':sorted([{k:v for k,v in obj.items() if k not in {'segmentation_source','annotation_ref','mask_path'}} for obj in normalized],key=canonical)}).encode()).hexdigest()
    return result


def compatible(left,right,category_mapping=None):
    if left['task']!=right['task'] or left['scheme']!=right['scheme']: return False,'annotation_scheme_mismatch'
    if not left['comparable'] or not right['comparable']: return False,'annotation_invalid_or_frame_unresolved'
    mapping=category_mapping or {}
    if (left['taxonomy']!=right['taxonomy'] or left.get('taxonomy_identity')!=right.get('taxonomy_identity')) and not mapping: return False,'category_semantics_unresolved'
    if mapping and (any(str(v) not in mapping for v in left['labels']) or (right['taxonomy'] and any(v not in right['taxonomy'] for v in mapping.values()))): return False,'category_mapping_incomplete_or_invalid'
    if left['task'] in {'detection','segmentation'} and left['oriented_size']!=right['oriented_size']: return False,'image_coordinate_frames_differ'
    return True,None


from pathlib import Path
