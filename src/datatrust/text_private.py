"""Protected locator manifests, exact local resolution and private artifact variants."""
from dataclasses import asdict
import copy
import hashlib
import json
import os
from pathlib import Path

from datatrust.text_contracts import TextSourceSpec,TextWorkLimits,TextReportArtifacts
from datatrust.m4_contracts import ExecutionOptions
from datatrust.text_normalization import MISSING,strict_json,frames,get,verify,graphemes
from datatrust.renderer import protect_source,publish_bytes,write_report_artifacts,write_analysis_json,ArtifactCollisionError


def digest(manifest):
    return hashlib.sha256(json.dumps(manifest,sort_keys=True,ensure_ascii=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def protected_directory(path):
    path=Path(path)
    if path.is_symlink():raise ValueError('Private manifest directory cannot be a symlink.')
    if not path.exists():
        missing=[];current=path
        while not current.exists():missing.append(current);current=current.parent
        for directory in reversed(missing):directory.mkdir(mode=0o700)
    if os.name=='posix' and path.stat().st_mode & 0o077:raise ValueError('Private manifest directory must be owner-only.')
    return path


def write_manifest(result,path):
    path=Path(path);protected_directory(path.parent)
    protect_source(result.source_paths,[path])
    raw=json.dumps(result.private,sort_keys=True,ensure_ascii=True,indent=2,allow_nan=False).encode()
    if path.is_symlink():raise ArtifactCollisionError('Private manifest destination is a symlink.')
    if path.exists():
        if path.read_bytes()!=raw or os.name=='posix' and path.stat().st_mode&0o077:raise ArtifactCollisionError('Private manifest destination is occupied or unprotected.')
        return str(path)
    return publish_bytes(path,raw)


def _allowed(path,roots):
    path=Path(path).resolve()
    if not roots or not any(path.is_relative_to(Path(r).resolve()) for r in roots):raise ValueError('Evidence is outside the caller allowed roots.')
    if not path.is_file():raise ValueError('Evidence source is unavailable.')
    return path


def safe_excerpt(value,max_chars=240):
    import unicodedataplus as u
    if isinstance(max_chars,bool) or not isinstance(max_chars,int) or not 0<max_chars<=240:raise ValueError('Excerpt bounds must be 1–240 characters.')
    text=value if isinstance(value,str) else json.dumps(value,ensure_ascii=True,allow_nan=False)
    output=[];length=0
    for g in graphemes(text):
        displayed=''.join(f'[U+{ord(c):04X}]' if u.category(c) in {'Cc','Cf','Cs'} and c not in '\t\n\r' else c for c in g)
        if length+len(displayed)>max_chars:break
        output.append(displayed);length+=len(displayed)
    return ''.join(output)


def resolve_evidence(manifest,reference,*,allowed_roots,reveal_content=False,max_chars=240,expected_digest=None):
    if isinstance(manifest,(str,Path)):manifest=strict_json(Path(manifest).read_text())
    if not isinstance(manifest,dict) or manifest.get('schema')!='text_private_manifest_v1':raise ValueError('Unsupported private manifest.')
    if expected_digest and digest(manifest)!=expected_digest:raise ValueError('Private manifest does not match the report integrity binding.')
    if reference in manifest['definitions']:
        definition=manifest['definitions'][reference]
        if definition['kind']=='source':
            info=manifest['sources'][definition['source_id']];path=_allowed(info['path'],allowed_roots);verify(info)
            return {'reference':reference,'status':'resolved_source','source_path':str(path),'sha256':info['sha256']}
        return {'reference':reference,'status':'resolved_private_definition','definition':definition if reveal_content else {'kind':definition['kind']}}
    loc=manifest['locators'].get(reference)
    if not loc:raise ValueError('Reference is not retained in this private manifest.')
    sid=loc['source_id'];info=manifest['sources'][sid];path=_allowed(info['path'],allowed_roots)
    verify(info)
    if loc.get('reason')=='invalid_jsonl_record':
        with path.open('rb') as handle:handle.seek(loc['byte_start']);raw=handle.read(loc['byte_length'])
        if hashlib.sha256(raw).hexdigest()!=loc['record_sha256']:raise ValueError('Invalid-record bytes changed.')
        value=raw[:max_chars].decode('utf8',errors='backslashreplace')
    else:
        source=TextSourceSpec.from_dict(manifest['spec']['inputs'][sid]['source'])
        options=ExecutionOptions.from_dict(manifest['config']['execution']);limits=TextWorkLimits.from_dict(manifest['config']['limits'])
        record=None
        for location,candidate,reason in frames(path,source,options,limits):
            if 'header' not in location and candidate is not None and location['ordinal']==loc['ordinal']:
                record=candidate;break
        if record is None:raise ValueError('Exact record is unavailable; no nearby-record repair was attempted.')
        value=get(record,loc.get('selector')) if loc.get('selector') else record
        if value is MISSING:value={'observed_state':'absent'}
        if loc.get('reason')=='invalid_json_cell' and isinstance(value,dict) and value.get('__datatrust_invalid_json_cell__'):value=value['raw']
        asset=loc.get('asset')
        if loc.get('asset_selector'):
            asset_path=get(record,loc['asset_selector'])
            if not isinstance(asset_path,str):raise ValueError('Asset reference is unavailable.')
            asset=manifest['assets'].get(str((path.parent/asset_path).resolve()))
            if not asset:raise ValueError('Asset was not captured by this audit.')
        if asset:
            asset_path=_allowed(asset['path'],allowed_roots);verify(asset)
            if loc.get('asset_selector') or asset_path.suffix.lower()=='.txt':
                value=asset_path.read_bytes().decode(loc.get('asset_encoding') or loc.get('encoding') or 'utf-8')
            else:value={'asset_bytes':asset['bytes'],'sha256':asset['sha256']}
            verify(asset)
        if loc.get('content_sha256') and (not isinstance(value,str) or hashlib.sha256(value.encode()).hexdigest()!=loc['content_sha256']):raise ValueError('Located content failed its integrity check.')
        if loc.get('span'):
            if not isinstance(value,str):raise ValueError('Span content is unavailable.')
            value=value[loc['span'][0]:loc['span'][1]]
    verify(info)
    result={'reference':reference,'status':'resolved','source_path':str(path),'location':{k:v for k,v in loc.items() if k not in {'asset','content_sha256'}},'content_disclosed':bool(reveal_content)}
    if reveal_content:result['excerpt']=safe_excerpt(value,max_chars)
    return result


def resolve_text_evidence(manifest,reference,report,*,allowed_roots,reveal_content=False,max_chars=240):
    if isinstance(report,(str,Path)):report=strict_json(Path(report).read_text())
    if isinstance(manifest,(str,Path)):manifest=strict_json(Path(manifest).read_text())
    if report.get('schema_version')!='1.5' or report['profile']['audit_id']!=manifest.get('audit_id'):raise ValueError('Report and manifest identities differ.')
    return resolve_evidence(manifest,reference,allowed_roots=allowed_roots,reveal_content=reveal_content,max_chars=max_chars,expected_digest=report['profile']['private_manifest_sha256'])


class ExportView:
    def __init__(self,result,references,allowed_roots):
        self.result=result;self.data=copy.deepcopy(result.to_dict());self.data['profile']['excerpts']=[]
        from datatrust.text_presentation import executive_summary
        executive=executive_summary(self.data)
        self.data['profile'].update(summary=executive['summary'],executive_action_count=len(executive['actions']),technical_finding_count=executive['technical_findings'])
        if len(references)>20 or len(set(references))!=len(references):raise ValueError('Request at most 20 distinct retained excerpt references.')
        for reference in references:
            value=result.resolve_evidence(reference,allowed_roots=allowed_roots,reveal_content=True)
            if 'excerpt' not in value:raise ValueError('Excerpt references require exact retained source evidence.')
            self.data['profile']['excerpts'].append({'reference':reference,'text':value['excerpt']})
        self.data['profile']['disclosure']={'policy':'bounded_excerpts' if references else 'references_only','references':list(references),'maximum_characters':4800 if references else 0}
        from datatrust.renderer import render_analysis_result
        self.data['profile'].pop('export_fingerprint',None)
        self.data['profile'].pop('export_identity',None)
        package=Path(__file__).parent
        identity={'completed_evidence_sha256':hashlib.sha256(result.json_text().encode()).hexdigest(),'disclosure':self.data['profile']['disclosure'],'excerpt_sha256':hashlib.sha256(json.dumps(self.data['profile']['excerpts'],sort_keys=True,ensure_ascii=True).encode()).hexdigest(),'template_sha256':hashlib.sha256((package/'templates/text_report.html').read_bytes()).hexdigest(),'projection_sha256':hashlib.sha256((package/'text_presentation.py').read_bytes()).hexdigest(),'canonical_html_sha256':hashlib.sha256(render_analysis_result(self).encode()).hexdigest()}
        self.data['profile']['export_identity']=identity
        self.data['profile']['export_fingerprint']=hashlib.sha256(json.dumps(identity,sort_keys=True,ensure_ascii=True).encode()).hexdigest()
    def __getattr__(self,key):return getattr(self.result,key)
    def to_dict(self):return self.data
    def json_text(self):return json.dumps(self.data,ensure_ascii=False,indent=2,allow_nan=False)


def manifest_path(result,path,private_out=None):
    return Path(private_out) if private_out else Path(path).parent/'.datatrust-private'/result.profile['audit_id']/'manifest.json'


def write_text_json(result,path,*,private_out=None):
    private=manifest_path(result,path,private_out);protect_source(result.source_paths,[path,private]);write_manifest(result,private)
    result.last_private_manifest_path=str(private)
    return write_analysis_json(ExportView(result,(),()),path)


def generate_artifacts(result,path,*,format='html',html_path=None,json_path=None,private_out=None,excerpt_refs=(),allowed_roots=(),pdf_converter=None):
    private=manifest_path(result,path,private_out)
    protect_source(result.source_paths,[private,path,html_path,json_path])
    view=ExportView(result,tuple(excerpt_refs),allowed_roots)
    canonical=Path(html_path) if html_path else Path(path).with_suffix('.html') if format=='pdf' else Path(path)
    if canonical.exists() and os.name=='posix' and canonical.stat().st_mode&0o077:raise ArtifactCollisionError('Existing canonical HTML is not owner-only.')
    # Reject a disclosure collision before creating any public artifacts.
    write_manifest(result,private)
    try:
        artifacts=write_report_artifacts(view,path,format=format,html_path=html_path,json_path=json_path,pdf_converter=pdf_converter)
    except Exception as exc:
        if getattr(exc,'artifacts',None):exc.artifacts=TextReportArtifacts(**asdict(exc.artifacts),private_manifest_path=str(private))
        raise
    return TextReportArtifacts(**asdict(artifacts),private_manifest_path=str(private))
