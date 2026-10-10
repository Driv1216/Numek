"""Pinned data, independent scalable mathematics and completed artifact closure."""
from dataclasses import replace
import hashlib
import json
import math
from pathlib import Path
import platform
import tempfile
import time

import numpy as np
import pandas as pd
from datatrust import *
from datatrust.m4_worker import execute

ROOT=Path(__file__).parent


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def references(result):
    value=json.loads(result.json_text(),parse_constant=lambda _:(_ for _ in ()).throw(AssertionError()))
    ids={e['id'] for e in value['evidence']}
    for record in value['evidence']:
        for pointer in record['measurement_refs']:
            node=value
            for key in pointer.split('/')[1:]:node=node[int(key)] if isinstance(node,list) else node[key.replace('~1','/').replace('~0','~')]
    assert all(set(c['evidence_refs'])<=ids for c in value['checks'])
    assert all(set(f['evidence_refs'])<=ids for f in value['findings'])


def independent(result,frame):
    assert result.profile['row_count']==len(frame)
    assert result.profile['duplicate_count']==frame.duplicated().sum()
    for c in result.profile['columns']:
        s=frame[c['name']];assert c['missing_count']==s.isna().sum();assert c['unique_count']==s.nunique()
        numeric=c.get('numerical')
        if not numeric or numeric['precision_block']:continue
        values=s[np.isfinite(s)].to_numpy(dtype=float);assert numeric['finite_count']==len(values)
        assert numeric['mean']==__import__('pytest').approx(float(np.mean(values)),rel=1e-12,abs=1e-12)
        for k,p in [('p1',.01),('p5',.05),('q1',.25),('median',.5),('q3',.75),('p95',.95),('p99',.99)]:assert numeric['quantiles'][k]==__import__('pytest').approx(float(np.quantile(values,p)),rel=1e-12,abs=1e-12)


def pinned():
    baseline=ROOT.parent/'data/prepared/manifest.json'
    for name,c in json.loads(baseline.read_text())['datasets'].items():
        p=ROOT.parent/c['prepared_path'];assert digest(p)==c['prepared_sha256']
        yield name,p,TaskSpec('classification',c['target']),AnalysisConfig()
    manifest=json.loads((ROOT.parent/'regression/manifest.json').read_text());c=manifest['datasets']['concrete'];p=ROOT.parent/'regression'/c['file'];assert digest(p)==c['sha256']
    yield 'concrete',p,TaskSpec('regression',c['target']),AnalysisConfig()
    for name,c in json.loads((ROOT.parent/'m3/manifest.json').read_text())['datasets'].items():
        p=ROOT.parent/'m3'/c['file'];assert digest(p)==c['sha256']
        yield name,p,TaskSpec.from_dict(c['task']),AnalysisConfig.from_dict(c['config'])


def run():
    records=[];artifacts=[];destination=ROOT/'results/reports';destination.mkdir(parents=True,exist_ok=True)
    previous=ROOT/'results/verification.json'
    owned={path:sha for case in json.loads(previous.read_text()).get('artifacts',[]) for path,sha in case['files'].items()} if previous.exists() else {}
    with tempfile.TemporaryDirectory(prefix='numek-m4-validator-') as tmp:
        temp=Path(tmp)
        for name,p,task,config in pinned():
            started=time.monotonic();r=DataTrust.from_spec(DatasetSpec(str(p),dataset_name=name),task,replace(config,execution=ExecutionOptions())).analyze_result()
            assert r.execution['status']=='completed',(name,[c.reason for c in r.checks if c.execution.value=='failed'])
            references(r);independent(r,pd.read_csv(p))
            records.append({'name':name,'rows':r.profile['row_count'],'columns':r.profile['column_count'],'source_sha256':digest(p),'seconds':time.monotonic()-started,'peak_rss':r.execution['peak_worker_rss_bytes'],'result_bytes':len(r.json_text().encode()),'checks':[c.check_id for c in r.checks]})
            if name in {'energy','scene'}:
                # Compatible canonical numeric interpretation, independent controlled split.
                frame=pd.read_csv(p);a=temp/(name+'-reference.csv');b=temp/(name+'-current.csv');frame.iloc[::2].to_csv(a,index=False);frame.iloc[1::2].to_csv(b,index=False)
                spec=ComparisonSpec('versions',(DatasetInput('reference','reference',DatasetSpec(str(a)),task,config),DatasetInput('current','current',DatasetSpec(str(b)),task,config)),dataset_name=name+' controlled versions')
                comparative=DataTrust.compare(spec);assert comparative.execution['status']=='completed';references(comparative)
        p=temp/'clean.csv';p.write_text('id,x,z,channel,label\n'+''.join(f'{i:04d},{i},{i*2},{"a" if i%2 else "b"},{"yes" if i%3 else "no"}\n' for i in range(240)))
        task=TaskSpec('classification','label',group_columns=('id',));cfg=AnalysisConfig(features=FeatureOptions({'x':'quantitative','z':'quantitative','channel':'categorical'}))
        clean=DatasetInput('reference','reference',DatasetSpec(str(p)),task,cfg)
        current=replace(clean,id='current',role='current')
        cases={'clean':DataTrust.compare(ComparisonSpec('versions',(clean,current),dataset_name='Clean identical populations'))}
        contamination=DataTrust.compare(ComparisonSpec('splits',(replace(clean,role='train'),replace(current,role='test')),identity_keys=(('id',),),evaluation_intent='entity_disjoint',dataset_name='Declared split separation violation'))
        cases['contaminated']=contamination
        shifted=pd.read_csv(p,dtype={'id':str});shifted['x']+=100;shifted.loc[:59,'z']=np.nan;bp=temp/'shifted.csv';shifted.to_csv(bp,index=False)
        cases['shifted']=DataTrust.compare(ComparisonSpec('versions',(clean,replace(current,dataset=DatasetSpec(str(bp)))),dataset_name='Controlled numerical and missingness shift'))
        partial=cases['shifted'];partial=replace(partial,execution=dict(partial.execution,status='partial'),checks=list(partial.checks),coverage={**partial.coverage,'diagnostics':dict(partial.coverage['diagnostics'])})
        partial.checks.append(CheckOutcome('controlled_optional_failure',execution=ExecutionStatus.FAILED,reason='Controlled isolated optional diagnostic failure.'))
        partial.coverage['diagnostics']['controlled_optional_failure']={'status':'failed','population':'controlled optional scope','reason':'Controlled verification fixture; not a naturally occurring failure.'}
        cases['partial']=partial
        for name,width in [('wide',80),('long_headers',12)]:
            frame=pd.DataFrame({('measurement_'+str(i)+'_with_explicit_source_unit_'+('a_very_long_declared_name_'*6 if name=='long_headers' else '')):np.arange(240,dtype=float)*(i+1)+np.sin(np.arange(240)) for i in range(width)})
            path=temp/(name+'.csv');frame.to_csv(path,index=False)
            cases[name]=DataTrust.from_spec(DatasetSpec(str(path),dataset_name=name),TaskSpec('clustering'),AnalysisConfig(advanced=AdvancedTabularOptions(max_features=16,max_pairs=16))).analyze_result()
        from pypdf import PdfReader
        for name,result in cases.items():
            references(result);folder=destination/name;folder.mkdir(exist_ok=True)
            # Refresh only this validator's hash-bound outputs. Runtime exports still never replace.
            outputs=[folder/filename for filename in ('report.html','report.pdf','analysis.json')]
            for output in outputs:
                if output.exists():
                    relative=str(output.relative_to(ROOT))
                    if output.is_symlink() or owned.get(relative)!=digest(output):raise ValueError('Verification output ownership changed: '+relative)
            for output in outputs:output.unlink(missing_ok=True)
            bundle=result.generate_artifacts(folder/'report.pdf',format='pdf',json_path=folder/'analysis.json')
            pages=PdfReader(bundle.pdf_path).pages;text=[p.extract_text() for p in pages]
            assert len(pages)<=(16 if name=='wide' else 12),(name,len(pages))
            executive=next(i for i,t in enumerate(text) if '3. Sources and declarations' in t);assert executive<=2,(name,executive)
            artifacts.append({'name':name,'pages':len(pages),'executive_pages':executive,'files':{str(Path(location).relative_to(ROOT)):digest(location) for location in [bundle.html_path,bundle.pdf_path,bundle.json_path]}})
    record={'status':'passed','verification':'independent mathematics over compatible canonical interpretations; deterministic mutations are not natural drift or evaluation ground truth','python':platform.python_version(),'duckdb':__import__('duckdb').__version__,'cases':records,'artifacts':artifacts}
    (ROOT/'results/verification.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record,indent=2))

if __name__=='__main__':run()
