from dataclasses import replace
from pathlib import Path
import pytest
from datatrust import *
from datatrust.scalable import Workspace, ingest


def source(tmp_path,name,text,task=None,config=None):
    p=tmp_path/name;p.write_text(text)
    return DatasetInput(name.split('.')[0],'dataset',DatasetSpec(str(p)),task or TaskSpec('dataset_profile'),config)


def test_lexical_defaults_and_chunk_invariance(tmp_path):
    item=source(tmp_path,'a.csv','id,x\n001,1\n1,2\nNA,3\nNULL,4\n A,5\nA,6\n',TaskSpec('dataset_profile',group_columns=('id',)))
    results=[]
    for batch in (64,100000):
        w=Workspace(ExecutionOptions(batch_bytes=batch),[item])
        try:
            r=ingest(w,item);results.append((r.parsing,w.con.execute('SELECT c0 FROM '+r.table+' ORDER BY _row').fetchall()))
        finally:w.close()
    assert results[0]==results[1]
    assert results[0][1]==[('001',),('1',),('NA',),('NULL',),(' A',),('A',)]


def test_worker_and_export(tmp_path):
    item=source(tmp_path,'a.csv','id,x,y\n001,1,A\n1,2,B\nNA,3,A\nNULL,4,\n',TaskSpec('classification','y',group_columns=('id',)))
    result=DataTrust.from_spec(item.dataset,item.task,AnalysisConfig(execution=ExecutionOptions())).analyze_result()
    assert result.schema_version=='1.3'
    assert result.execution['status']=='completed'
    assert result.execution['serialized_bytes']==len(result.json_text().encode('utf-8'))
    result.generate_artifacts(tmp_path/'report.html',json_path=tmp_path/'result.json')
    assert '1. Summary' in (tmp_path/'report.html').read_text()


def test_comparison_effects_and_multiplicity(tmp_path):
    a=source(tmp_path,'a.csv','id,x,y\n001,1,A\n001,1,A\n1,2,B\n',TaskSpec('classification','y',group_columns=('id',)))
    b=source(tmp_path,'b.csv','id,x,y\n001,1,B\n1,2,B\n1,2,B\n',a.task)
    spec=ComparisonSpec('splits',(replace(a,role='train'),replace(b,role='test')),identity_keys=(('id',),),evaluation_intent='entity_disjoint')
    result=DataTrust.compare(spec)
    integrity=result.coverage['measurements']['a:b.split_integrity']
    assert integrity['features']['left_rows']==3
    assert integrity['features']['right_rows']==3
    assert integrity['features']['multiset_intersection']==2
    assert integrity['units'][0]['shared_distinct_groups']==2
    assert any(f['priority']=='High' for f in result.findings)
    with pytest.raises(ValueError):result.write_json(b.dataset.path)


@pytest.mark.parametrize('kind,targets',[('dataset_profile',()),('classification',('t',)),('regression',('t','u')),('multilabel_classification',('t','u')),('clustering',()),('anomaly_detection',())])
def test_task_families(tmp_path,kind,targets):
    p=tmp_path/'task.csv';p.write_text('x,t,u\n'+''.join(f'{i},{i%2},{(i+1)%2}\n' for i in range(120)))
    task=TaskSpec(kind,targets=targets)
    config=AnalysisConfig(execution=ExecutionOptions(),features=FeatureOptions({'x':'quantitative'}))
    result=DataTrust.from_spec(DatasetSpec(str(p)),task,config).analyze_result()
    assert result.execution['status']=='completed'
    assert result.coverage['task_support']=={'dataset':kind}


def test_numerical_distribution_reference(tmp_path):
    from scipy.stats import wasserstein_distance,ks_2samp
    a=source(tmp_path,'a.csv','x\n'+''.join(f'{i}\n' for i in range(200)),config=AnalysisConfig(features=FeatureOptions({'x':'quantitative'})))
    b=source(tmp_path,'b.csv','x\n'+''.join(f'{i+20}\n' for i in range(200)),config=a.config)
    result=DataTrust.compare(ComparisonSpec('versions',(replace(a,role='reference'),replace(b,role='current'))))
    d=result.coverage['measurements']['a:b.populations']['columns'][0]
    assert d['wasserstein_1']==pytest.approx(wasserstein_distance(range(200),range(20,220)))
    assert d['cdf_distance']==pytest.approx(ks_2samp(range(200),range(20,220)).statistic)
