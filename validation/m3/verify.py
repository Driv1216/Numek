"""Offline independent mathematics, bounded derivations, and artifact QA."""
import argparse
from collections import Counter
from dataclasses import replace
import hashlib
import json
import math
import platform
import statistics
import subprocess
import tarfile
import tempfile
import time
import zipfile
from pathlib import Path
import numpy as np
import pandas as pd
from datatrust import (DataTrust,DatasetSpec,TaskSpec,AnalysisConfig,AnnotationOptions,AnnotationSpec,FeatureOptions)
from datatrust.presentation import report_view

ROOT=Path(__file__).parent


def hashfile(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def assert_references(r):
    payload=json.loads(r.json_text(),parse_constant=lambda v:(_ for _ in ()).throw(AssertionError(v)))
    ids={e['id'] for e in payload['evidence']}
    for e in payload['evidence']:
        for ptr in e['measurement_refs']:
            node=payload
            for key in ptr.split('/')[1:]:node=node[int(key)] if isinstance(node,list) else node[key]
    for c in payload['checks']:assert set(c['evidence_refs'])<=ids
    for f in payload['findings']:assert f['evidence_refs'] and set(f['evidence_refs'])<=ids


def independent(r,frame):
    targets=list(r.task.target_names)
    if r.task.kind=='multilabel_classification':
        rows=list(frame[targets].itertuples(index=False,name=None));complete=[row for row in rows if all(pd.notna(v) and v in (0,1) for v in row)]
        cardinalities=[sum(row) for row in complete];counts=Counter(complete);m=r.profile['multilabel']
        assert m['complete_vector_count']==len(complete)
        assert math.isclose(m['cardinality'],statistics.mean(cardinalities)) if complete else m['cardinality'] is None
        if complete:assert math.isclose(m['density'],sum(cardinalities)/len(complete)/len(targets))
        if m['combinations']['status']=='completed':assert {tuple(v['vector']):v['count'] for v in m['combinations']['records']}==counts
        assert m['observed_cells']==sum(pd.notna(v) and v in (0,1) for row in rows for v in row)
        for pair in m['pairs']:
            a,b=(targets.index(t) for t in pair['targets']);cells=Counter((row[a],row[b]) for row in rows if pd.notna(row[a]) and pd.notna(row[b]) and row[a] in (0,1) and row[b] in (0,1))
            assert (pair['n00'],pair['n01'],pair['n10'],pair['n11'])==tuple(cells.get(v,0) for v in [(0,0),(0,1),(1,0),(1,1)])
            positive_union=cells[(0,1)]+cells[(1,0)]+cells[(1,1)]
            assert pair['jaccard']==(cells[(1,1)]/positive_union if positive_union else None)
    elif r.task.kind=='regression':
        multi=r.profile['multioutput_regression']
        for out in multi['outputs']:
            finite=sorted(v for v in frame[out['target']] if pd.notna(v) and math.isfinite(v));t=out['statistics']
            assert out['finite_count']==len(finite)
            if not finite:assert t is None;continue
            assert math.isclose(t['mean'],statistics.mean(finite),rel_tol=1e-12,abs_tol=1e-12)
            if len(finite)>1:assert math.isclose(t['sample_std'],statistics.stdev(finite),rel_tol=1e-12,abs_tol=1e-12)
            for key,prob in [('p1',.01),('p5',.05),('q1',.25),('median',.5),('q3',.75),('p95',.95),('p99',.99)]:
                position=(len(finite)-1)*prob;lo=math.floor(position);hi=math.ceil(position);value=finite[lo]+(finite[hi]-finite[lo])*(position-lo)
                assert math.isclose(t['quantiles'][key],value,rel_tol=1e-12,abs_tol=1e-12)
            assert all(not set(c['columns'])&set(targets) for c in (out['search'] or {}).get('candidates',[]))
        for dep in multi['output_dependencies']:
            if dep['pearson'] is None:continue
            a,b=dep['targets'];pairs=[(x,y) for x,y in zip(frame[a],frame[b]) if pd.notna(x) and pd.notna(y) and math.isfinite(x) and math.isfinite(y)]
            xs,ys=zip(*pairs);xm=statistics.mean(xs);ym=statistics.mean(ys)
            pearson=sum((x-xm)*(y-ym) for x,y in pairs)/math.sqrt(sum((x-xm)**2 for x in xs)*sum((y-ym)**2 for y in ys))
            assert math.isclose(dep['pearson'],pearson,abs_tol=1e-12)
        assert multi['complete_vector_count']==sum(all(pd.notna(v) and math.isfinite(v) for v in row) for row in frame[targets].itertuples(index=False,name=None))


def cases(temp):
    manifest=json.loads((ROOT/'manifest.json').read_text())
    for source in manifest['sources'].values():
        archive=ROOT/'data/raw'/source['archive'];assert hashfile(archive)==source['archive_sha256']
        for member,sha in source['members'].items():
            if archive.suffix=='.zip':
                with zipfile.ZipFile(archive) as bundle:content=bundle.read(member)
            elif archive.name.endswith('.tar.gz'):
                with tarfile.open(archive) as bundle:content=bundle.extractfile(member).read()
            else:content=subprocess.check_output(['bsdtar','-xOf',str(archive),member])
            assert hashlib.sha256(content).hexdigest()==sha
    for name,c in manifest['datasets'].items():
        source=ROOT/c['file'];assert hashfile(source)==c['sha256'];frame=pd.read_csv(source)
        task=TaskSpec.from_dict(c['task']);config=AnalysisConfig.from_dict(c['config'])
        assert frame.shape==(c['rows'],c['columns'])
        yield name,source,frame,task,config,name=='scene'
        masked=frame.copy()
        for i,t in enumerate(task.target_names):masked.loc[(np.arange(len(frame))+i)%4==0,t]=np.nan
        path=temp/(name+'_masked.csv');masked.to_csv(path,index=False)
        yield name+'_masked',path,masked,task,replace(config,annotations=AnnotationOptions(AnnotationSpec('expected'))),False
        if name in {'energy','linnerud'}:
            feature_config=replace(config,regression=None,annotations=None)
            features=tuple(c for c in frame.columns if c not in task.target_names)
            yield name+'_clustering',source,frame,TaskSpec('clustering',feature_columns=features),feature_config,False
            yield name+'_anomaly',source,frame,TaskSpec('anomaly_detection',feature_columns=features),feature_config,False
    n=240;feature_names=[f'measurement_{i:03d}_with_explicit_source_unit' for i in range(350)];targets=[f'annotation_label_{i:02d}' for i in range(48)]
    frame=pd.DataFrame({c:np.arange(n,dtype=float)*(i+1)+np.sin(np.arange(n)) for i,c in enumerate(feature_names)})
    for i,t in enumerate(targets):frame[t]=np.where((np.arange(n)+i)%11==0,np.nan,((np.arange(n)+i)%3==0).astype(float))
    source=temp/'wide.csv';frame.to_csv(source,index=False)
    yield 'wide',source,frame,TaskSpec('multilabel_classification',targets=tuple(targets)),AnalysisConfig(annotations=AnnotationOptions(AnnotationSpec('expected'))),True
    for kind,targets in [('regression',('y','z')),('multilabel_classification',('y','z')),('classification',('y',))]:
        frame=pd.DataFrame({'x':range(30),**{t:np.full(30,np.nan) for t in targets}});source=temp/(kind+'_empty.csv');frame.to_csv(source,index=False)
        yield kind+'_empty',source,frame,TaskSpec(kind,targets=targets),AnalysisConfig(annotations=AnnotationOptions()),True
    frame=pd.DataFrame({'x':range(60),'y':['a' if i%2 else 'b' for i in range(60)],'state':['observed' if i%3 else 'intentionally_unlabeled' for i in range(60)]})
    frame.loc[frame['state']=='intentionally_unlabeled','y']=np.nan
    source=temp/'partial_classification.csv';frame.to_csv(source,index=False)
    yield 'partial_classification',source,frame,TaskSpec('classification','y'),AnalysisConfig(annotations=AnnotationOptions(AnnotationSpec('unknown','state'))),True


def verify_all(write_artifacts=False):
    destination=ROOT/'results/presentation';old=destination/'manifest.json'
    if old.exists():
        for c in json.loads(old.read_text())['cases']:
            for filename,sha in c.get('artifacts',{}).items():assert hashfile(ROOT/filename)==sha
    summary={'validation_type':'internal','external_method_validity':'not_established','python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__,'platform':platform.platform(),'cases':[]}
    with tempfile.TemporaryDirectory(prefix='datatrust-m3-') as temporary:
        temp=Path(temporary)
        for name,source,frame,task,config,pdf in cases(temp):
            started=time.monotonic();r=DataTrust.from_spec(DatasetSpec(source,dataset_name=name.replace('_',' ').title()),task,config).analyze_result();elapsed=time.monotonic()-started
            assert r.execution['status']=='completed' and r.schema_version=='1.2';assert_references(r);independent(r,frame)
            view=report_view(r);assert view['qa']['appendix_detail_rows']<=config.presentation.appendix_rows
            record={'name':name,'passed':True,'rows':len(frame),'columns':len(frame.columns),'source_sha256':hashfile(source),'elapsed_seconds':elapsed,'runtime_target_met':elapsed<30,
                    'frame_bytes':r.execution['frame_bytes'],'result_bytes':len(r.json_text().encode()),
                    'diagnostic_work':{'annotation_cohorts':r.profile.get('annotation_cohorts',{}).get('comparisons',0),
                                       'label_pairs':r.profile.get('multilabel',{}).get('pair_search',{}).get('comparisons',0),
                                       'output_dependencies':r.profile.get('multioutput_regression',{}).get('dependency_search',{}).get('comparisons',0),
                                       'input_relationships':r.profile.get('multioutput_regression',{}).get('relationship_work',{})},
                    'qa':view['qa'],'artifacts':{}}
            if write_artifacts:
                # A new run is a new output directory; never regenerate historic outputs.
                path=destination/name;path.mkdir(parents=True,exist_ok=True)
                started=time.monotonic();art=r.generate_artifacts(path/'report.pdf' if pdf else path/'report.html',format='pdf' if pdf else 'html',json_path=path/'analysis.json');record['artifact_seconds']=time.monotonic()-started
                for location in [art.html_path,art.pdf_path,art.json_path]:
                    if location:record['artifacts'][str(Path(location).relative_to(ROOT))]=hashfile(location)
                if pdf:
                    from pypdf import PdfReader
                    pages=PdfReader(art.pdf_path).pages;texts=[p.extract_text() for p in pages];record['pdf_pages']=len(pages)
                    executive_pages=next((i for i,text in enumerate(texts) if '3. Dataset, roles' in text),len(pages))
                    appendix_pages=sum('8. Technical appendix' in text or any(c.check_id in text for c in r.checks) and i>=next((j for j,t in enumerate(texts) if '8. Technical appendix' in t),len(pages)) for i,text in enumerate(texts))
                    record['executive_pages']=executive_pages;record['appendix_pages']=appendix_pages
                    assert executive_pages<=2
                    if name=='scene':assert len(pages)<=8 and appendix_pages<=4,(name,len(pages),appendix_pages)
                    if name=='wide':assert len(pages)<=12 and appendix_pages<=6,(name,len(pages),appendix_pages)
            summary['cases'].append(record)
    if write_artifacts:
        old.parent.mkdir(parents=True,exist_ok=True);old.write_text(json.dumps(summary,indent=2)+'\n')
    return summary

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--write-artifacts',action='store_true');args=parser.parse_args();print(json.dumps(verify_all(args.write_artifacts),indent=2))
