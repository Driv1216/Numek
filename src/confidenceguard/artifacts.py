"""Canonical report rendering and audience-bound, collision-safe artifact bundles."""
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
from jinja2 import Environment,FileSystemLoader,select_autoescape
from .contracts import DisclosureSpec,EvaluationError,digest
from .result import EvaluationResult,SharedResult
from . import compat


@dataclass(frozen=True)
class ReportArtifacts:
    html_path: str | None = None
    pdf_path: str | None = None
    json_path: str | None = None
    private_result_path: str | None = None
    private_manifest_path: str | None = None
    reused_html: bool = False
    disclosure_digest: str | None = None
    fitted_methods_path: str | None = None


def display(value):
    if value is None:return 'Unavailable'
    if isinstance(value,bool):return 'Yes' if value else 'No'
    if isinstance(value,float):return format(value,'.8g')
    return str(value)


def view(data):
    sections={};omitted=0
    cg2=bool(data.get('cg2'))
    ordered=sorted(data['measurements'],key=lambda m:0 if m['scope']==('paired' if cg2 else 'overall') else 1 if m['scope']==('overall' if cg2 else 'paired') else 2)
    headlines=[]
    for m in ordered:
        if m['scope']=='overall' and m['metric'] in {'accuracy','mae','rmse','brier','log_loss','interval_coverage'}:
            headlines.append({'run':m['run'],'metric':m['metric'].replace('_',' '),'value':'∞' if m['value_state']=='positive_infinity' else display(m['value']),'denominator':m['denominator'],'note':m.get('reason') or m['basis']})
        family=m['family'];section=sections.setdefault(family,{'title':family.replace('_',' ').replace(':',' · ').title(),'rows':[],'charts':[],'details':[],'total':0})
        section['total']+=1
        if len(section['rows'])<20:
            value='∞' if m['value_state']=='positive_infinity' else '−∞' if m['value_state']=='negative_infinity' else display(m['value'])
            if m['value_state']=='undefined' and m.get('data') and not m.get('reason'):value='Structured evidence'
            label=m['metric'].replace('_',' ')
            if m.get('data',{}).get('target'):label+=' · '+m['data']['target']
            uncertainty=m.get('uncertainty')
            interval_label=(f"{100*uncertainty.get('level',.95):.5g}% family confidence · Bonferroni m={uncertainty.get('family_size')}" if uncertainty and uncertainty.get('adjustment')=='bonferroni' else f"{100*uncertainty.get('level',.95):.5g}% pointwise" if uncertainty else '')
            section['rows'].append({'run':m['run'],'scope':m['scope'],'metric':label,'value':value,'denominator':display(m['denominator']),'note':m.get('reason') or ('Limited observed support' if m.get('support_warning') else ''),'interval':uncertainty,'interval_label':interval_label})
            detail=m.get('data',{})
            if detail and len(section['details'])<(1 if cg2 else 2):
                compact={k:(v[:4] if isinstance(v,list) else v) for k,v in detail.items()}
                text=json.dumps(compact,ensure_ascii=False,indent=2)
                bound=900 if cg2 else 1800
                section['details'].append({'id':m['id'],'metric':m['metric'],'text':text[:bound],'truncated':len(text)>bound or any(isinstance(v,list) and len(v)>4 for v in detail.values())})
            if detail.get('bins') and 'observed_frequency' in detail['bins'][0] and len(section['charts'])<2:
                bars=[]
                for b in detail['bins']:
                    if b['observed_frequency'] is not None:bars.append({'x':40+b['bin']*320/len(detail['bins']),'width':240/len(detail['bins']),'y':180-140*b['observed_frequency'],'height':140*b['observed_frequency'],'prob_y':180-140*b['mean_probability'],'count':b['count']})
                section['charts'].append({'type':'calibration','title':str(detail.get('target','Calibration')),'bars':bars})
            elif detail.get('points') and len(section['charts'])<2:
                points=detail['points'];xy=[]
                for p in points:
                    x=p.get('coverage',p.get('fpr'));y=p.get('accepted_error_rate',p.get('tpr'))
                    if isinstance(x,(float,int)) and isinstance(y,(float,int)) and 0<=x<=1 and 0<=y<=1:xy.append(f'{40+320*x:.3f},{180-140*y:.3f}')
                if xy:section['charts'].append({'type':'curve','title':'FPR / TPR · retained score groups' if 'fpr' in points[0] else 'Coverage / accepted error rate · simulated policy','points':' '.join(xy)})
        else:omitted+=1
    cg=data.get('cg2');method_panels=[];selection_panels=[];matched=[]
    if cg:
        for m in ordered:
            if m['family']!='comparison' or m['scope']!='paired' or len(matched)>=24:continue
            metric=m['metric'].removesuffix('_right_minus_left')
            if metric not in {'brier','log_loss','mae','rmse','accuracy'} and not any(v in metric for v in ('coverage@','efficiency@')):continue
            detail=m['data'];matched.append({'left':detail.get('left_run'),'right':detail.get('right_run'),'metric':metric,'value':display(m['value']) if m['value_state']=='finite' else m['value_state'],
                 'planned':detail.get('planned_common_input_support','See detail'),'paired':m['denominator'],'qualification':m.get('reason') or detail.get('comparison_qualification','See population detail')})
        if isinstance(cg['methods'],list):method_panels=cg['methods']
        else:
            for key,m in cg['methods'].items():
                state=cg.get('evidence_views',{}).get(key,{})
                method_panels.append({'id':key,'method':m['method'],'algorithm_version':m['algorithm_version'],
                                      'method_evidence_state':state.get('method_state','fitted_only'),
                                      'application_evidence_state':state.get('application_state','applied_unvalidated')})
        for s in cg.get('selections',[]):
            candidates=s['candidates']
            selection_panels.append({'id':s['id'],'objective':s['objective'],'selected':s['selected'],
                                      'common_support':(s.get('common_population') or {}).get('denominator','Protected / see local evidence'),
                                      'candidates':json.dumps(candidates,ensure_ascii=False,indent=2)[:4000]})
    return {'matched':matched,'sections':list(sections.values()),'headlines':headlines,'omitted':omitted,'checks':data.get('checks',[])[:40],'checks_omitted':max(0,len(data.get('checks',[]))-40),'coverage_limitations':data.get('coverage',{}).get('limitations',[])+([data['coverage']['legacy_qualification']] if data.get('coverage',{}).get('legacy_qualification') else []),'cg2':cg,'method_panels':method_panels,'selection_panels':selection_panels,'limitations':['Metrics describe supplied outcomes and declared populations; ground truth and representativeness are not independently established.','Calibration bins and high-confidence settings are investigation definitions, not universal safety thresholds.','Policy replay is retrospective; different actions may change outcomes or their observation.','Statistical intervals, when enabled, are assumption-qualified; the recorded adjustment distinguishes pointwise and family confidence.','Sampled resource safeguards are not hard quotas or capacity guarantees.','No composite score, certification or production approval is defined.']}


def render_report(data):
    env=Environment(loader=FileSystemLoader(Path(__file__).parent/'templates'),autoescape=select_autoescape(['html']),trim_blocks=True,lstrip_blocks=True)
    return env.get_template('report.html').render(result=data,view=view(data))


def identical_or_publish(path,raw):
    path=Path(path)
    if path.is_symlink():raise EvaluationError('Artifact destination is unsafe.','artifact_collision')
    if path.exists():
        if not path.is_file() or path.read_bytes()!=raw:raise EvaluationError('Artifact destination is occupied.','artifact_collision')
        return True
    compat.destination(path);compat.publish(path,raw);return False


def generate_artifacts(result,path,*,format='html',html_path=None,json_path=None,disclosure=None,audience='shareable',pdf_converter=None):
    if format not in {'html','pdf'}:raise EvaluationError('Report format must be html or pdf.')
    if format=='html' and html_path is not None:raise EvaluationError('html_path applies only to PDF export.')
    if audience not in {'shareable','local'}:raise EvaluationError('Unsupported artifact audience.')
    if isinstance(result,SharedResult) and (audience!='shareable' or disclosure is not None):raise EvaluationError('A shareable import cannot change disclosure or recover exact values.')
    if isinstance(disclosure,dict):disclosure=DisclosureSpec.from_dict(disclosure)
    if isinstance(result,EvaluationResult):EvaluationResult.from_dict(result.to_private_dict(),private=result.private)
    data=result.to_dict(audience=audience,**({'disclosure':disclosure} if isinstance(result,EvaluationResult) else {}))
    canonical=Path(html_path) if html_path else Path(path).with_suffix('.html') if format=='pdf' else Path(path)
    pdf_path=Path(path) if format=='pdf' else None
    targets=[canonical,pdf_path,Path(json_path) if json_path else None];sources=result.source_paths if isinstance(result,EvaluationResult) else ()
    compat.protect(sources,targets)
    reserve=result.private['config']['free_disk_bytes'] if isinstance(result,EvaluationResult) else 0
    for target in targets:
        if target:
            parent=target.parent
            while not parent.exists():parent=parent.parent
            st=os.statvfs(parent)
            if st.f_bavail*st.f_frsize<reserve+256*1024**2:raise EvaluationError('Output filesystem lacks export reserve.','disk_exhausted')
    for target in (pdf_path,Path(json_path) if json_path else None):
        if target:compat.destination(target)
    private_result=private_manifest=None
    if isinstance(result,EvaluationResult):
        directory=compat.protected_directory(canonical.parent/'.confidenceguard-private'/result.data['analysis_id'])
        private_result=directory/'result.json';private_manifest=directory/'manifest.json'
        compat.protect(sources,[*targets,private_result,private_manifest])
        for destination,value in ((private_result,result.to_private_dict()),(private_manifest,result.private)):
            raw=json.dumps(value,ensure_ascii=True,sort_keys=True,indent=2,allow_nan=False).encode()
            identical_or_publish(destination,raw)
            if os.name=='posix' and destination.stat().st_mode&0o077:raise EvaluationError('Protected artifact is not owner-only.','unsafe_permissions')
    html=render_report(data).encode();reused=identical_or_publish(canonical,html)
    dd=digest(data.get('disclosure',{'audience':audience}))
    method_path=None
    if isinstance(result,EvaluationResult) and result.private.get('fitted_methods'):
        method_path=directory/'methods.json'
        compat.protect(sources,[method_path])
        identical_or_publish(method_path,json.dumps({'schema_version':'confidenceguard.fitted_collection/1.0','methods':result.private['fitted_methods'],'membership_sidecars':result.private.get('membership_sidecars',[])},sort_keys=True,indent=2,allow_nan=False).encode())
        if os.name=='posix' and method_path.stat().st_mode&0o077:raise EvaluationError('Fitted artifacts are private.','unsafe_permissions')
    artifacts=ReportArtifacts(str(canonical),private_result_path=str(private_result) if private_result else None,private_manifest_path=str(private_manifest) if private_manifest else None,reused_html=reused,disclosure_digest=dd,fitted_methods_path=str(method_path) if method_path else None)
    try:
        if json_path:
            compat.publish(json_path,json.dumps(data,ensure_ascii=True,indent=2,allow_nan=False).encode())
            artifacts=ReportArtifacts(**{**artifacts.__dict__,'json_path':str(json_path)})
        if pdf_path:
            (pdf_converter or compat.pdf)(canonical,pdf_path,hashlib.sha256(html).hexdigest())
            artifacts=ReportArtifacts(**{**artifacts.__dict__,'pdf_path':str(pdf_path)})
        return artifacts
    except Exception as exc:
        exc.artifacts=artifacts
        raise
