"""Protected image locators and explicit, bounded standalone disclosure variants."""
from dataclasses import asdict
import base64
import copy
import hashlib
import io
import json
import os
from pathlib import Path

from datatrust.image_assets import capture,decode,error
from datatrust.image_contracts import ImageDisclosureOptions,ImageWorkLimits,ImageReportArtifacts
from datatrust.text_private import protected_directory
from datatrust.text_normalization import strict_json
from datatrust.renderer import protect_source,publish_bytes,write_analysis_json,write_report_artifacts,ArtifactCollisionError


def digest(value): return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def preview(manifest,loc,roots,*,overlays=False,labels=False):
    from PIL import Image,ImageOps,ImageDraw
    path=loc.get('path'); info=manifest['files'].get(path)
    if not info: raise ValueError('Retained image is unavailable.')
    _,raw,_=capture(path,roots,max_bytes=128*1024**2,expected=info)
    facts,_=decode(raw,ImageWorkLimits())
    if facts.get('decode')!='decoded' or 'oriented_sha256' not in facts: raise ValueError('Image representation cannot be displayed safely.')
    with Image.open(io.BytesIO(raw)) as source:
        oriented=ImageOps.exif_transpose(source).convert('RGBA')
        matte=Image.new('RGBA',oriented.size,'white')
        image=Image.alpha_composite(matte,oriented).convert('RGB')
        normalized=loc.get('normalized',{})
        if overlays:
            if not normalized.get('comparable') or normalized.get('task') not in {'detection','segmentation'}: raise ValueError('Overlay frame compatibility is unresolved.')
            draw=ImageDraw.Draw(image)
            mask_budget=[0]
            for i,obj in enumerate(normalized.get('objects',[])):
                if 'bbox' in obj:
                    draw.rectangle(obj['bbox'],outline='#ff5028',width=max(1,image.width//256))
                    if labels: draw.text(obj['bbox'][:2],str(obj.get('category','')),fill='#ff5028')
                if obj.get('mask_path'):
                    import numpy as np
                    from datatrust.image_annotations import orient_mask,frame
                    from datatrust.image_contracts import ImageAnnotationSpec
                    source_spec=next(x for x in manifest['spec']['inputs'] if x['id']==loc['source_id'])
                    ann=ImageAnnotationSpec.from_dict(source_spec['annotations'])
                    geometry,reason=frame(ann,facts,loc['annotation'])
                    mask_info=manifest['files'].get(obj['mask_path'])
                    if not mask_info or geometry is None: raise ValueError('Instance-mask overlay is unavailable.')
                    _,mask_raw,_=capture(mask_info['path'],roots,max_bytes=128*1024**2,expected=mask_info)
                    with Image.open(io.BytesIO(mask_raw)) as source_mask:
                        source_mask.load(); pixels=np.asarray(source_mask)
                    active=(~np.isin(pixels,list(ann.background+ann.ignore))).astype('uint8')
                    active=orient_mask(active,ann,facts,geometry)
                    alpha=Image.fromarray((active*90).astype('uint8'))
                    image=Image.composite(Image.new('RGB',image.size,'#ff5028'),image,alpha)
                    draw=ImageDraw.Draw(image)
                if obj.get('segmentation_source') is not None:
                    from datatrust.image_annotations import segmentation,orient_mask,frame
                    from datatrust.image_contracts import ImageAnnotationSpec
                    source_spec=next(x for x in manifest['spec']['inputs'] if x['id']==loc['source_id'])
                    ann=ImageAnnotationSpec.from_dict(source_spec['annotations'])
                    geometry,reason=frame(ann,facts,loc['annotation'])
                    if geometry is None: raise ValueError('Mask overlay frame is unresolved.')
                    _,bitmap=segmentation(obj['segmentation_source'],geometry['width'],geometry['height'],ImageWorkLimits(),mask_budget)
                    if bitmap is None: raise ValueError('Mask overlay rasterization exceeds its bound.')
                    bitmap=orient_mask(bitmap,ann,facts,geometry)
                    alpha=Image.fromarray((bitmap*90).astype('uint8'))
                    image=Image.composite(Image.new('RGB',image.size,'#ff5028'),image,alpha)
                    draw=ImageDraw.Draw(image)
            annotation=loc.get('annotation',{}); maskpath=annotation.get('mask')
            if isinstance(maskpath,str):
                input_spec=next(x for x in manifest['spec']['inputs'] if x['id']==loc['source_id'])
                root=Path(input_spec['source'].get('asset_root') or Path(input_spec['source']['path']).parent)
                mask_info=manifest['files'].get(str((root/maskpath).absolute()))
                if not mask_info: raise ValueError('Retained mask is unavailable.')
                _,mask_raw,_=capture(mask_info['path'],roots,max_bytes=128*1024**2,expected=mask_info)
                from datatrust.image_contracts import ImageAnnotationSpec
                from datatrust.image_annotations import orient_mask,frame
                import numpy as np
                ann=ImageAnnotationSpec.from_dict(input_spec['annotations'])
                geometry,reason=frame(ann,facts,annotation)
                if geometry is None: raise ValueError('Mask overlay frame is unresolved.')
                with Image.open(io.BytesIO(mask_raw)) as mask:
                    mask.load(); pixels=np.asarray(mask)
                if ann.mask_encoding=='rgb_png':
                    active=np.zeros(pixels.shape[:2],dtype=bool)
                    for key,category in ann.color_mapping.items():
                        if category not in ann.background+ann.ignore:
                            active |= np.all(pixels==np.array([int(x) for x in key.split(',')]),axis=-1)
                else: active=~np.isin(pixels,list(ann.background+ann.ignore))
                active=orient_mask(active.astype('uint8'),ann,facts,geometry)
                image=Image.composite(Image.new('RGB',image.size,'#ff5028'),image,Image.fromarray((active*90).astype('uint8')))
        image.thumbnail((1024,1024),Image.Resampling.LANCZOS)
        # Re-encoding strips metadata and prevents corpus resource fetching.
        output=io.BytesIO(); image.save(output,format='JPEG',quality=85)
        if output.tell()>1024**2: raise ValueError('Example exceeds its encoded disclosure bound.')
        return output.getvalue(),facts


def resolve_image_evidence(manifest,reference,report,*,allowed_roots,reveal_image=False,overlays=False,labels=False):
    if isinstance(manifest,(str,Path)): manifest=strict_json(Path(manifest).read_text())
    if isinstance(report,(str,Path)): report=strict_json(Path(report).read_text())
    if manifest.get('schema')!='image_private_manifest_v1' or report.get('schema_version')!='1.6' or report['profile']['audit_id']!=manifest['audit_id'] or report['profile']['private_manifest_sha256']!=digest(manifest): raise ValueError('Report and private manifest identities differ.')
    if reference in manifest['definitions']:
        return {'reference':reference,'status':'resolved_private_definition','kind':manifest['definitions'][reference]['kind'],**({'value':manifest['definitions'][reference]['value']} if labels else {})}
    loc=manifest['locators'].get(reference)
    if not loc: raise ValueError('Reference is not retained.')
    # Reverify the metadata source binding as well as the selected asset.
    item=next(x for x in manifest['spec']['inputs'] if x['id']==loc['source_id'])
    paths=[]
    if item['source']['format']!='directory': paths.append(item['source']['path'])
    associated=item['annotations'].get('associated_source')
    if associated: paths.append(associated['path'])
    for path in paths:
        info=manifest['files'].get(str(Path(path).absolute()))
        if not info: raise ValueError('Source locator is unavailable.')
        capture(path,allowed_roots,expected=info)
    result={'reference':reference,'status':'resolved','source_location':loc['location'],'source_path':loc.get('path'),'split':loc.get('split'),'group_keys':loc.get('groups'),'image_disclosed':False,'annotation_state':loc.get('normalized',{}).get('observation'),'frame_compatible':loc.get('normalized',{}).get('comparable',False)}
    if not loc.get('path'): return result|{'status':'unavailable_image'}
    if reveal_image:
        raw,facts=preview(manifest,loc,allowed_roots,overlays=overlays,labels=labels)
        result.update(display_representation='EXIF-oriented white-matte JPEG; encoded color values, ICC profile not applied',image_disclosed=True,image_data_uri='data:image/jpeg;base64,'+base64.b64encode(raw).decode(),width=facts.get('oriented_width'),height=facts.get('oriented_height'))
        if labels: result['labels']=loc.get('normalized',{}).get('labels',[])
    else: capture(loc['path'],allowed_roots,expected=manifest['files'][loc['path']])
    return result


def manifest_path(result,path,private_out): return Path(private_out) if private_out else Path(path).parent/'.datatrust-private'/result.profile['audit_id']/'manifest.json'


def write_manifest(result,path):
    path=Path(path); protected_directory(path.parent); protect_source(result.source_paths,[path])
    raw=json.dumps(result.private,sort_keys=True,ensure_ascii=True,indent=2,allow_nan=False).encode()
    if path.is_symlink(): raise ArtifactCollisionError('Private manifest destination is a symlink.')
    if path.exists():
        if path.read_bytes()!=raw or (os.name=='posix' and path.stat().st_mode&0o077): raise ArtifactCollisionError('Private destination is occupied or unprotected.')
        return str(path)
    return publish_bytes(path,raw)


class ExportView:
    def __init__(self,result,disclosure,roots):
        self.result=result; self.data=copy.deepcopy(result.to_dict()); self.data['profile']['examples']=[]
        total=0
        for ref in disclosure.references:
            resolved=result.resolve_evidence(ref,allowed_roots=roots,reveal_image=True,overlays=disclosure.overlays,labels=disclosure.labels)
            uri=resolved.get('image_data_uri')
            if not uri: raise ValueError('Example reference has no displayable image.')
            total+=len(base64.b64decode(uri.split(',',1)[1]))
            if total>8*1024**2: raise ValueError('Examples exceed their total disclosure bound.')
            self.data['profile']['examples'].append({'reference':ref,'image':uri,'labels':resolved.get('labels') if disclosure.labels else None})
        self.data['profile']['disclosure']={'policy':'explicit_examples' if disclosure.references else 'references_only',**asdict(disclosure),'encoded_bytes':total}
        self.data['profile']['export_identity']={'completed_evidence_sha256':hashlib.sha256(result.json_text().encode()).hexdigest(),'disclosure_sha256':digest(self.data['profile']['disclosure']),'example_sha256':digest(self.data['profile']['examples']), 'template_sha256':hashlib.sha256(Path(__file__).with_name('templates').joinpath('image_report.html').read_bytes()).hexdigest(),'projection_sha256':hashlib.sha256(Path(__file__).with_name('image_presentation.py').read_bytes()).hexdigest()}
        from datatrust.renderer import render_analysis_result
        self.data['profile']['export_identity']['canonical_html_sha256']=hashlib.sha256(render_analysis_result(self).encode()).hexdigest()
    def __getattr__(self,key): return getattr(self.result,key)
    def to_dict(self): return self.data
    def json_text(self): return json.dumps(self.data,ensure_ascii=False,indent=2,allow_nan=False)


def write_image_json(result,path,*,private_out=None):
    private=manifest_path(result,path,private_out); protect_source(result.source_paths,[path,private]); write_manifest(result,private)
    return write_analysis_json(ExportView(result,ImageDisclosureOptions(),()),path)


def generate_artifacts(result,path,*,format='html',html_path=None,json_path=None,private_out=None,disclosure=None,allowed_roots=(),pdf_converter=None):
    disclosure=disclosure or ImageDisclosureOptions()
    if not isinstance(disclosure,ImageDisclosureOptions): raise ValueError('Use ImageDisclosureOptions.')
    private=manifest_path(result,path,private_out); protect_source(result.source_paths,[path,html_path,json_path,private])
    view=ExportView(result,disclosure,allowed_roots)
    canonical=Path(html_path) if html_path else Path(path).with_suffix('.html') if format=='pdf' else Path(path)
    if canonical.exists() and (canonical.is_symlink() or os.name=='posix' and canonical.stat().st_mode&0o077): raise ArtifactCollisionError('Existing canonical HTML is unprotected.')
    write_manifest(result,private)
    try: artifacts=write_report_artifacts(view,path,format=format,html_path=html_path,json_path=json_path,pdf_converter=pdf_converter)
    except Exception as exc:
        if getattr(exc,'artifacts',None): exc.artifacts=ImageReportArtifacts(**asdict(exc.artifacts),private_manifest_path=str(private))
        raise
    return ImageReportArtifacts(**asdict(artifacts),private_manifest_path=str(private))
