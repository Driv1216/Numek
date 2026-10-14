"""Whole M9 API story with socket denial inside the actual model worker."""
from dataclasses import replace
import json
import os
from pathlib import Path
import socket

from datatrust import *
from datatrust.cross_models import algorithm_identity
from validation.m9.fixtures import financial

ROOT=Path(__file__).parent.absolute()


def offline_model(*args,**kwargs):
    def blocked(*args,**kwargs): raise RuntimeError('Network forbidden in M9 validation worker.')
    socket.socket.connect=blocked;socket.socket.connect_ex=blocked;socket.create_connection=blocked
    from datatrust.cross_models import execute
    result=execute(*args,**kwargs)
    result.execution['network_socket_operations']='blocked_inside_spawned_worker'
    return result


def run():
    import datatrust.cross as cross
    original=cross.run_supervised
    def supervise(operation,args,options,**kwargs):
        return original(offline_model if operation.__name__=='execute' else operation,args,options,**kwargs)
    cross.run_supervised=supervise
    cfg=CrossRepresentationAnalysisConfig(models=CrossModelOptions(str(ROOT/'models/nli'),str(ROOT.parent/'m6/models/multilingual-e5-small')))
    label=os.environ.get('M9_RUN_LABEL','closure')
    if not label or len(label)>64 or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in label): raise ValueError('Use a simple isolated verification label.')
    reports=ROOT/'results/reports'/label;reports.mkdir(parents=True,exist_ok=True);cases={}
    private=ROOT/'results/private'/label;data=ROOT/'data'/label
    try:
        for fmt in ('pdf','docx'):
            spec=financial(data/('api_'+fmt),format=fmt)
            result=DataTrust.audit_cross_representation(spec,cfg)
            assert result.profile['summary'].startswith(str(len(result.findings))+' review findings.')
            revenue=next(e['data'] for e in result.evidence if e['population']=='rule_1')
            assert [revenue[k] for k in ('satisfied','violated','conflicting_evidence')]==[18,1,1]
            models=next(e['data'] for e in result.evidence if e['family']=='models')
            assert models['support_candidate']==19 and models['mixed_evidence']==1,models
            assert result.execution['model_execution']['network_socket_operations']=='blocked_inside_spawned_worker'
            original_bytes=result.json_text()
            reviews=result.review_dispositions('Local acceptance reviewer')
            for status,disposition in [('violated','confirm'),('conflicting_evidence','unresolved')]:
                item=next(x for x in revenue['details'] if x['status']==status)
                reviews.set(item['target_id'],disposition,'PRIVATE_ACCEPTANCE_NOTE' if disposition=='confirm' else '')
                located=[result.resolve_evidence(r,allowed_roots=spec.allowed_roots,reveal_content=True) for r in item['evidence_refs']]
                assert all(x['status']=='resolved' for x in located)
                if status=='conflicting_evidence': assert {'12000000','1200000'} <= {x['excerpt'] for x in located}
            reviews.set(next(x for x in models['details'] if x['status']=='support_candidate')['target_id'],'dismiss')
            assert len(ReviewDispositionSet.from_dict(reviews.to_dict(),result=result).entries)==3
            assert result.json_text()==original_bytes
            base=reports/(fmt+'_financial')
            artifacts=result.generate_artifacts(str(base.with_suffix('.pdf')),format='pdf',html_path=str(base.with_suffix('.html')),json_path=str(base.with_suffix('.json')),private_out=private/fmt/'manifest.json')
            reviews.export(private/fmt/'review.json',result=result)
            public=base.with_suffix('.json').read_text()+base.with_suffix('.html').read_text()
            assert all(x not in public for x in ['12000000','1200000','PRIVATE_ACCEPTANCE_NOTE',str(ROOT/'data'),'Company A020 was'])
            reloaded=CrossRepresentationAuditResult.from_dict(json.loads(base.with_suffix('.json').read_text()),private=json.loads(Path(artifacts.private_manifest_path).read_text()))
            ReviewDispositionSet.from_dict(reviews.to_dict(),result=reloaded)
            cases[fmt]={'status':'passed','revenue':{k:revenue[k] for k in ('satisfied','violated','conflicting_evidence')},'semantic':{k:v for k,v in models.items() if k!='details'},'execution':result.execution,'coverage':result.coverage,'review_entries':3,'artifacts':{'html':str(base.with_suffix('.html').relative_to(ROOT)),'pdf':str(base.with_suffix('.pdf').relative_to(ROOT))}}
            if fmt=='pdf':
                reference=next(x for x in revenue['details'] if x['status']=='conflicting_evidence')['evidence_refs'][1]
                disclosed=result.generate_artifacts(reports/'explicit_example.pdf',format='pdf',html_path=reports/'explicit_example.html',json_path=reports/'explicit_example.json',private_out=private/fmt/'manifest.json',disclosure=CrossDisclosureOptions(excerpt_refs=(reference,)),allowed_roots=spec.allowed_roots)
                assert '12000000' in (reports/'explicit_example.html').read_text() or '1200000' in (reports/'explicit_example.html').read_text()
        spec=financial(data/'bounded')
        bounded=DataTrust.audit_cross_representation(spec,replace(cfg,limits=replace(cfg.limits,claims=2)))
        assert bounded.coverage['model_selected']['nli']==2
        assert bounded.coverage['families']['rule_2']['records']==20
        assert bounded.coverage['model_selection']['rule_2']=={'population':20,'selected':2,'not_selected':18,'requested':True}
        bounded.generate_artifacts(reports/'bounded.pdf',format='pdf',html_path=reports/'bounded.html',json_path=reports/'bounded.json',private_out=private/'bounded/manifest.json')
        cases['bounded']={'status':'passed','coverage':bounded.coverage,'execution':bounded.execution}
        outside=replace(spec,inputs=tuple(replace(x,language='fr') for x in spec.inputs),rules=tuple(replace(x,claim_language='fr') if x.method=='nli' else x for x in spec.rules))
        abstained=DataTrust.audit_cross_representation(outside,cfg)
        assert next(e['data']['abstained'] for e in abstained.evidence if e['family']=='models')==20
        cases['non_english']={'status':'passed','coverage':abstained.coverage}
    finally: cross.run_supervised=original
    ledger=ROOT/'results'/('end_to_end.json' if label=='closure' else label+'_end_to_end.json')
    if ledger.exists(): (ROOT/'results/initial_end_to_end.json').write_bytes(ledger.read_bytes())
    ledger.write_text(json.dumps({'status':'passed','algorithm_identity':algorithm_identity(),'cases':cases,'network':'Socket connect/connect_ex/create_connection blocked inside actual optional audit worker.','privacy':'Default public artifacts have no fixture values, claims, paths or review notes; private locators resolve exact native evidence.'},indent=2,allow_nan=False)+'\n')
    print('M9 native PDF/DOCX, mixed evidence, reviews, privacy, bounded and English eligibility: passed',flush=True)


if __name__=='__main__': run()
