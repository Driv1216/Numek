"""Public operating cases, pinned-source checks and independent population counts."""
from dataclasses import replace
from pathlib import Path
import json
import time
from types import SimpleNamespace
from datatrust import *
from validation.m5.download import digest
ROOT=Path(__file__).parent


def run(refresh=(),render_directory=None):
    catalog=json.loads((ROOT/'data/prepared/manifest.json').read_text());records=[]
    for dataset in catalog['datasets']:
        for filename,pin in dataset['prepared'].items():assert digest(ROOT/'data/prepared'/filename)==pin['sha256']
        name=dataset['name'];manifest=ROOT/'manifests'/(name+'.json');assert digest(manifest)==dataset['manifest_sha256']
        spec=TemporalAuditSpec.from_dict(json.loads(manifest.read_text()),base_directory=manifest.parent)
        # Explicitly declared natural operating scope; all required aggregates remain full population.
        cfg=TemporalAnalysisConfig(limits=TemporalWorkLimits(behavior_measurements=8,detailed_series=16))
        started=time.monotonic();refined=ROOT/'reports/refined'/name;base=refined if refined.with_suffix('.json').exists() else ROOT/'reports'/name
        reused=base.with_suffix('.json').exists() and name not in refresh
        if name in refresh:base=ROOT/'reports/refined'/name;base.parent.mkdir(exist_ok=True)
        if reused:
            saved=json.loads(base.with_suffix('.json').read_text())
            assert TemporalAnalysisConfig.from_dict(saved['declarations']['configuration']).to_dict()==cfg.to_dict()
            for item in spec.inputs:assert saved['profile']['sources'][item.id]['source']['sha256']==digest(item.source.path)
            result=TemporalAuditResult(spec=spec,**{k:v for k,v in saved.items() if k!='spec'})
        else:
            try:result=DataTrust.audit_temporal(spec,cfg)
            except AnalysisError as exc:
                (ROOT/'results'/(name+'_failure.json')).write_text(json.dumps({'status':'failed','stage':exc.stage,'code':exc.code,'error':str(exc),'execution':getattr(exc,'execution',{}),'configuration':cfg.to_dict()},indent=2)+'\n')
                raise
        main=next(x for x in spec.inputs if x.temporal)
        assert result.profile['sources'][main.id]['rows']==dataset['rows']
        chronology=next(x['data'] for x in result.evidence if x['check_id']=='chronology' and main.id in x['source_ids'])
        assert chronology['cells']==dataset['rows']*len(main.temporal.measurements)
        assert sum(chronology['parse_states'].values())==chronology['cells']
        assert sum(v['cells'] for v in chronology['value_states'])==chronology['cells']
        if name=='beijing':
            continuity=next(x['data'] for x in result.evidence if x['check_id']=='continuity')
            assert continuity['occupied_distinct_slots']==420768*8
            assert continuity['absent_expected_records_or_opportunities']==0
            assert any(x['state']=='missing' and x['cells']>0 for x in chronology['value_states'])
        if name=='electricity':assert any(x['applicability']=='blocked' for x in result.checks)
        if name=='alfred':
            h=next(x['data'] for x in result.evidence if x['check_id']=='revision_history');assert h['comparison_states']=={'agreement':2}
        if not reused:result.write_json(base.with_suffix('.json'))
        presented=refined if base==refined else ROOT/'reports/compact'/name;
        if render_directory:presented=ROOT/'reports'/render_directory/name
        presented.parent.mkdir(exist_ok=True)
        if not presented.with_suffix('.pdf').exists():result.generate_artifacts(presented.with_suffix('.pdf'),format='pdf')
        artifacts=SimpleNamespace(html_path=presented.with_suffix('.html'),pdf_path=presented.with_suffix('.pdf'),json_path=base.with_suffix('.json'))
        from pypdf import PdfReader
        pages=len(PdfReader(artifacts.pdf_path).pages)
        records.append({'reused_completed_evidence':reused,'name':name,'status':result.execution['status'],'rows':dataset['rows'],'normalized_cells':chronology['cells'],'verification_seconds':time.monotonic()-started,'analysis_seconds':result.execution['whole_job_seconds'],'execution':result.execution,'pdf_pages':pages,'artifacts':{k:str(v.relative_to(ROOT)) for k,v in vars(artifacts).items()},'manifest_sha256':digest(manifest),'html_sha256':digest(artifacts.html_path),'json_sha256':digest(artifacts.json_path),'pdf_sha256':digest(artifacts.pdf_path),'methodology':result.methodology_id,'limitations':dataset['notes']})
        assert pages<=12
        print(name,result.execution['status'],records[-1]['verification_seconds'],'seconds',pages,'pages',flush=True)
    (ROOT/'results/public_corpus.json').write_text(json.dumps({'transform':catalog['transform'],'natural_data_validates_universal_thresholds':False,'datasets':records},indent=2)+'\n')
if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--refresh',nargs='*',choices=['bike','beijing','electricity','retail','alfred'],default=[]);parser.add_argument('--render-directory');a=parser.parse_args();run(a.refresh,a.render_directory)
