"""Private exact resolution and explicitly disclosed derivative artifacts."""
from dataclasses import replace
import base64
import copy
import io
import json
import os
from pathlib import Path

from datatrust.cross_private_base import digest
from datatrust.cross_contracts import CrossDisclosureOptions,CrossReportArtifacts,CrossRepresentationAuditSpec,CrossRepresentationAnalysisConfig
from datatrust.cross_sources import value
from datatrust.image_assets import capture
from datatrust.text_normalization import strict_json,frames
from datatrust.text_contracts import TextSourceSpec,TextWorkLimits
from datatrust.text_private import protected_directory,safe_excerpt
from datatrust.renderer import publish_bytes,protect_source,write_report_artifacts,write_analysis_json


def load(v): return strict_json(Path(v).read_text()) if isinstance(v,(str,Path)) else v


def validate(manifest,report):
    manifest,report=load(manifest),load(report)
    if manifest.get('schema')!='cross_private_manifest_v1' or report.get('schema_version')!='1.7' or manifest.get('audit_id')!=report['profile']['audit_id'] or digest(manifest)!=report['profile']['private_manifest_sha256']: raise ValueError('Original report/private evidence binding differs.')
    return manifest,report


def resolve_evidence(manifest,reference,report,*,allowed_roots,reveal_content=False):
    manifest,report=validate(manifest,report)
    loc=manifest['locators'].get(reference)
    if not loc: raise ValueError('Evidence reference is not retained.')
    if not allowed_roots: raise ValueError('Current authorized roots are required.')
    files=manifest['files'];source=loc['source'];info=files[source]
    spec=CrossRepresentationAuditSpec.from_dict(manifest['spec']);config=CrossRepresentationAnalysisConfig.from_dict(manifest['config'])
    item=next(x for x in spec.inputs if x.id==loc['source_id']);record=None;unit=loc.get('unit')
    source_info,raw,_=capture(source,allowed_roots,expected=info,max_bytes=config.limits.document_bytes if item.format in {'pdf','docx','txt'} else None)
    if item.format in {'pdf','docx','txt'}:
        record=dict(item.metadata);record.setdefault(item.id_selector,item.id);record.setdefault('layout',item.layout or 'default')
    elif item.format=='parquet':
        from datatrust.temporal_normalization import parquet_preflight
        from datatrust.temporal_contracts import TemporalWorkLimits
        reader,_=parquet_preflight(source,TemporalWorkLimits());ordinal=0
        try:
            for batch in reader.iter_batches(batch_size=1024,use_threads=False):
                for row in batch.to_pylist():
                    ordinal+=1
                    if ordinal==loc['record']['ordinal']:
                        from decimal import Decimal
                        from datetime import datetime,date
                        from datatrust.cross_sources import NativeDate,NativeTimestamp
                        record={k:NativeTimestamp(v.isoformat()) if isinstance(v,datetime) else NativeDate(v.isoformat()) if isinstance(v,date) else v for k,v in row.items()};break
                if record is not None: break
        finally: reader.close()
    else:
        for coordinate,candidate,reason in frames(source,TextSourceSpec(source,item.format,item.encoding,item.delimiter),config.execution,TextWorkLimits()):
            if 'header' not in coordinate and coordinate['ordinal']==loc['record']['ordinal']:
                record=candidate or {};break
        if item.format=='csv':
            from decimal import Decimal
            for col in item.json_columns:
                try: strict_json(record[col]);record[col]=json.loads(record[col],parse_float=Decimal)
                except (ValueError,TypeError): record[col]=None
        if item.format=='jsonl' and record:
            from decimal import Decimal
            coordinate=loc['record']
            from datatrust.image_assets import secure_open
            with secure_open(source,allowed_roots) as (handle,_):
                handle.seek(coordinate['byte_start']);raw_record=handle.read(coordinate['byte_length'])
            record=json.loads(raw_record.decode(item.encoding),parse_float=Decimal)
    if record is None: raise ValueError('Exact record is unavailable.')
    content=value(record,loc['selector']) if loc.get('selector') else record
    if loc.get('generated_claim'):
        import string
        fields=[f for _,f,_,_ in string.Formatter().parse(loc['generated_claim']) if f]
        content=loc['generated_claim'].format(**{f:value(record,f) for f in fields})
    if unit and unit['kind']=='field':
        content=value(record,unit['selector'])
        if 'span' in unit: content=content[slice(*unit['span'])]
        if digest(str(content))!=unit['value_digest']: raise ValueError('Located field differs.')
    elif unit:
        if loc.get('asset'):
            asset=loc['asset'];info=files[asset];_,asset_raw,_=capture(asset,allowed_roots,expected=info,max_bytes=config.limits.document_bytes)
            if asset_raw is None: raise ValueError('Evidence capture bound exceeded.')
            if Path(asset).suffix.lower()=='.txt': extracted=[{'kind':'text','text':asset_raw.decode(item.encoding)}]
            else:
                from datatrust.cross_documents import extract,versions
                if versions()!=report['execution'].get('parsers'): raise ValueError('Extraction version differs; exact resolution unavailable.')
                if unit.get('extraction_settings'):
                    settings=next(x for x in manifest['document_settings'] if x['asset']==asset and x['settings']==unit['extraction_settings'] and x['kind']==item.kind)
                else:
                    mapping=next(x for x in spec.mappings if x.id==unit['mapping'])
                    settings=next(x for x in manifest['document_settings'] if x['asset']==asset and x['strategy']==mapping.strategy and x['kind']==item.kind)
                extracted=extract(asset_raw,settings['format'],config.limits,strategy=settings['strategy'],parts=tuple(settings['parts']))
        else: extracted=[{'kind':'text','text':value(record,item.text_selector)}]
        matched=False
        for current in extracted:
            if current['kind']!=unit['kind'] or any(current.get(k)!=unit.get(k) for k in ('page','part','block','table') if k in unit): continue
            if unit['kind']=='table':
                content=current['rows'][unit['row']][unit['column']]
                if current['cells'][unit['row']][unit['column']]!=unit['cell_location']: raise ValueError('Cell geometry changed.')
                if 'span' in unit: content=content[slice(*unit['span'])]
            else:
                text=current['text'];start,end=unit.get('span',[0,len(text)]);content=text[start:end]
                if unit.get('geometry_digest') and digest(current.get('geometry'))!=unit['geometry_digest']: raise ValueError('Source glyph geometry changed.')
            if digest(str(content))!=unit['value_digest']: raise ValueError('Extracted evidence changed.')
            matched=True;break
        if not matched: raise ValueError('Exact extraction location is unavailable.')
    elif digest(content)!=loc['content_digest']: raise ValueError('Located value differs.')
    result={'reference':reference,'status':'resolved','location':{k:v for k,v in (unit or loc['record']).items() if k not in {'value','mapping','label','geometry_digest'}},'content_disclosed':bool(reveal_content)}
    if reveal_content:
        from decimal import Decimal
        result['excerpt']=safe_excerpt(str(content) if isinstance(content,Decimal) else content)
        result['source_path']=source
        result['asset_path']=loc.get('asset')
        result['selector']=loc.get('selector')
        result['source_id']=loc['source_id']
        if item.kind=='image' and loc.get('asset'):
            from PIL import Image,ImageOps
            from datatrust.image_assets import decode
            from datatrust.image_contracts import ImageWorkLimits
            info=files[loc['asset']];_,image_raw,_=capture(loc['asset'],allowed_roots,expected=info,max_bytes=128*1024**2)
            facts,_=decode(image_raw,ImageWorkLimits())
            if facts['decode']!='decoded': raise ValueError('Image is unavailable.')
            with Image.open(io.BytesIO(image_raw)) as image:
                image=ImageOps.exif_transpose(image).convert('RGBA');out=Image.new('RGB',image.size,'white');out.paste(image,mask=image.getchannel('A'));out.thumbnail((1024,1024));buffer=io.BytesIO();out.save(buffer,format='JPEG',quality=85)
            if buffer.tell()>1024**2: raise ValueError('Image disclosure exceeds bound.')
            result['image']='data:image/jpeg;base64,'+base64.b64encode(buffer.getvalue()).decode()
    capture(source,allowed_roots,expected=source_info)
    if loc.get('asset'): capture(loc['asset'],allowed_roots,expected=files[loc['asset']])
    return result


class ExportView:
    def __init__(self,result,disclosure,roots):
        self.result=result;self.data=copy.deepcopy(result.to_dict());examples=[];size=0
        for ref in disclosure.excerpt_refs:
            resolved=result.resolve_evidence(ref,allowed_roots=roots,reveal_content=True)
            examples.append({'reference':ref,'text':resolved['excerpt']})
        for ref in disclosure.image_refs:
            resolved=result.resolve_evidence(ref,allowed_roots=roots,reveal_content=True)
            if not resolved.get('image'): raise ValueError('Image reference required.')
            size+=len(base64.b64decode(resolved['image'].split(',',1)[1]));examples.append({'reference':ref,'image':resolved['image']})
        if size>8*1024**2: raise ValueError('Combined image disclosure exceeds bound.')
        self.data['profile']['examples']=examples
        self.data['profile']['disclosure']={'policy':'explicit_examples' if examples else 'references_only',**disclosure.to_dict()}
        self.data['profile']['export_identity']={'original_result_sha256':digest(result.to_dict()),'disclosure_sha256':digest(self.data['profile']['disclosure']),'examples_sha256':digest(examples),'template_sha256':digest(Path(__file__).with_name('templates').joinpath('cross_report.html').read_text()),'projection_sha256':digest(Path(__file__).with_name('cross_presentation.py').read_text())}
        from datatrust.renderer import render_analysis_result
        import hashlib
        self.data['profile']['export_identity']['canonical_html_sha256']=hashlib.sha256(render_analysis_result(self).encode()).hexdigest()
    def __getattr__(self,n): return getattr(self.result,n)
    def to_dict(self): return self.data
    def json_text(self): return json.dumps(self.data,ensure_ascii=False,indent=2,allow_nan=False)


def write_manifest(result,path):
    path=Path(path);protected_directory(path.parent);protect_source(result.source_paths,[path]);raw=json.dumps(result.private,ensure_ascii=True,sort_keys=True,indent=2).encode()
    if path.exists():
        if path.is_symlink() or path.read_bytes()!=raw or os.name=='posix' and path.stat().st_mode&0o077: raise ValueError('Private manifest collision.')
        return str(path)
    return publish_bytes(path,raw)


def generate_artifacts(result,path,*,format='html',html_path=None,json_path=None,private_out=None,disclosure=None,allowed_roots=(),pdf_converter=None):
    disclosure=disclosure or CrossDisclosureOptions()
    if not isinstance(disclosure,CrossDisclosureOptions): raise ValueError('Use CrossDisclosureOptions.')
    private=Path(private_out) if private_out else Path(path).parent/'.datatrust-private'/result.profile['audit_id']/'manifest.json'
    protect_source(result.source_paths,[path,html_path,json_path,private]);write_manifest(result,private)
    view=ExportView(result,disclosure,allowed_roots)
    try: artifacts=write_report_artifacts(view,path,format=format,html_path=html_path,json_path=json_path,pdf_converter=pdf_converter)
    except Exception as exc:
        a=getattr(exc,'artifacts',None)
        if a: exc.artifacts=CrossReportArtifacts(a.html_path,a.pdf_path,a.json_path,a.reused_html,str(private),qa_metadata=a.qa_metadata)
        raise
    return CrossReportArtifacts(artifacts.html_path,artifacts.pdf_path,artifacts.json_path,artifacts.reused_html,str(private),qa_metadata=artifacts.qa_metadata)


def write_json(result,path,*,private_out=None):
    private=Path(private_out) if private_out else Path(path).parent/'.datatrust-private'/result.profile['audit_id']/'manifest.json'
    protect_source(result.source_paths,[path,private])
    write_manifest(result,private)
    return write_analysis_json(result,path)
