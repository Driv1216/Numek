import io
import json
from dataclasses import replace
from pathlib import Path
import threading
import time
import pytest
from datatrust import *
from datatrust.scalable import Workspace,ingest,inventory
from datatrust.m4_worker import analyze_scalable
from datatrust.web import create_app
from .test_foundation import source


def test_numeric_keys_and_missing_overrides(tmp_path):
    a=source(tmp_path,'a.csv','key,x\n001,1\n1,2\nNA,3\n',TaskSpec('dataset_profile',group_columns=('key',)),AnalysisConfig(parsing=CsvParseOptions(column_types={'key':'numeric'},column_missing_policies={'key':{'missing_policy':'pandas_default'}})))
    w=Workspace(ExecutionOptions(),[a])
    try:
        r=ingest(w,a);assert w.con.execute('SELECT c0 FROM '+r.table+' ORDER BY _row').fetchall()==[(1,),(1,),(None,)]
        assert r.representations['key']['origin']=='explicit_parsing'
    finally:w.close()


def test_late_type_and_structural_errors(tmp_path):
    a=source(tmp_path,'a.csv','x\n1\n2\nlate text\n')
    for n in (16,100000):
        w=Workspace(ExecutionOptions(batch_bytes=n),[a])
        try:assert ingest(w,a).types['x']=='VARCHAR'
        finally:w.close()
    bad=source(tmp_path,'bad.csv','x,y\n1,2,3\n')
    w=Workspace(ExecutionOptions(),[bad])
    try:
        with pytest.raises(AnalysisError,match='width'):ingest(w,bad)
    finally:w.close()


def test_exact_large_integer_and_mixed_key_representations(tmp_path):
    a=source(tmp_path,'a.csv','id,x\n9007199254740992,1\n9007199254740993,2\n',TaskSpec('dataset_profile',group_columns=('id',)),AnalysisConfig(parsing=CsvParseOptions(column_types={'id':'numeric'})))
    b=source(tmp_path,'b.csv','id,x\n0.5,1\n1.5,2\n',a.task,a.config)
    result=DataTrust.compare(ComparisonSpec('splits',(replace(a,role='train'),replace(b,role='test')),identity_keys=(('id',),)))
    assert result.coverage['measurements']['a:b.split_integrity']['units'][0]['blocked']=='unsafe_numeric_key_alignment'
    c=replace(b,config=AnalysisConfig())
    result=DataTrust.compare(ComparisonSpec('splits',(replace(a,role='train'),replace(c,role='test')),identity_keys=(('id',),)))
    assert result.coverage['measurements']['a:b.split_integrity']['units'][0]['blocked']=='incompatible_representations'


def test_disk_preflight_inode_accounting_and_combined_limits(tmp_path,monkeypatch):
    import datatrust.scalable as scalable
    a=source(tmp_path,'a.csv','x\n1\n')
    with pytest.raises(AnalysisError,match='Combined'):Workspace(ExecutionOptions(max_combined_source_bytes=5),[a,a])
    (tmp_path/'hard.csv').hardlink_to(a.dataset.path)
    charged,files=inventory(tmp_path);assert len(files)==1
    monkeypatch.setattr(scalable,'available',lambda _:0)
    with pytest.raises(AnalysisError,match='Scratch'):Workspace(ExecutionOptions(),[a])


def test_inference_and_no_priority_from_significance(tmp_path):
    a=source(tmp_path,'a.csv','x,category\n'+''.join(f'{i/2000},A\n' if i%2 else f'{i/2000},B\n' for i in range(2000)),config=AnalysisConfig(features=FeatureOptions({'x':'quantitative','category':'categorical'})))
    b=source(tmp_path,'b.csv','x,category\n'+''.join(f'{i/2000+.005},A\n' if i%2 else f'{i/2000+.005},B\n' for i in range(2000)),config=a.config)
    cfg=ComparisonConfig(inference=True,sampling='independent_rows')
    r=DataTrust.compare(ComparisonSpec('versions',(replace(a,role='reference'),replace(b,role='current'))),cfg)
    m=r.coverage['measurements']['a:b.populations'];assert all('adjusted_p_value' in t for t in m['tests'])
    assert not any(f['title']=='Supported input or annotation populations differ' for f in r.findings)
    same=DataTrust.compare(ComparisonSpec('versions',(replace(a,role='reference'),replace(a,id='b',role='current'))),cfg)
    assert same.coverage['measurements']['a:b.populations']['tests']==[]


def test_annotations_constraints_and_shared_budget(tmp_path):
    p=tmp_path/'a.csv';p.write_text('id,x,w,y,z,state\n'+''.join(f'{i%10:03d},{i},{i*2},{i%2},{(i+1)%2},{"observed" if i%2 else "intentionally_unlabeled"}\n' for i in range(120)))
    cfg=AnalysisConfig(execution=ExecutionOptions(),annotations=AnnotationOptions(AnnotationSpec('expected','state')),advanced=AdvancedTabularOptions(constraints=(ValueConstraint(('x',),'maximum',50),),requested_pairs=(('x','w'),),max_pair_work=120))
    r=DataTrust.from_spec(DatasetSpec(str(p)),TaskSpec('multilabel_classification',targets=('y','z'),group_columns=('id',)),cfg).analyze_result()
    ann=r.coverage['measurements']['dataset.annotations'];assert ann['targets'][0]['supplied_expected']==60 and ann['targets'][0]['observed']==120
    assert ann['targets'][0]['contradictions']==60
    assert r.coverage['advanced_job_work_units']<=120
    assert r.coverage['measurements']['dataset.constraints']['affected_row_union']==69


def test_cancel_and_deadline_cleanup(tmp_path):
    a=source(tmp_path,'a.csv','x\n1\n2\n')
    event=threading.Event();event.set()
    with pytest.raises(AnalysisError,match='cancelled'):analyze_scalable(a.dataset,a.task,AnalysisConfig(execution=ExecutionOptions(scratch_directory=str(tmp_path))),cancel=event)
    assert not list(tmp_path.glob('datatrust-m4-*'))
    with pytest.raises(AnalysisError,match='deadline'):analyze_scalable(a.dataset,a.task,AnalysisConfig(execution=ExecutionOptions(max_seconds=.001,scratch_directory=str(tmp_path))))
    assert not list(tmp_path.glob('datatrust-m4-*'))


def test_browser_split_and_artifacts(tmp_path):
    app=create_app(tmp_path/'workspace',data_roots=(tmp_path,));app.testing=True;client=app.test_client();client.get('/m4')
    with client.session_transaction() as s:token=s['form_token']
    post=lambda path,data:client.post(path,data={'form_token':token,**data},follow_redirects=True)
    post('/m4',{'mode':'splits'})
    for text in ('id,x\n001,1\n1,2\n','id,x\n001,1\n2,3\n'):post('/m4/sources',{'dataset':(io.BytesIO(text.encode()),'test.csv')})
    fields={'source1_role':'train','source2_role':'test','source1_task':'dataset_profile','source2_task':'dataset_profile','identity_keys':'id','evaluation_intent':'entity_disjoint'}
    response=post('/m4/configure',fields);assert b'Confirm declarations' in response.data
    store=app.extensions['datatrust_m4_store'];j=next(iter(store.jobs.values()))
    response=post('/m4/run',{'fingerprint':j['fingerprint']});assert response.status_code==200
    j['thread'].join(20);assert j['state']=='completed',j.get('error')
    for kind in ('html','json','pdf'):assert client.get('/m4/download/'+kind).status_code==200
    before=j['result'];assert client.get('/m4/download/html').status_code==200 and j['result'] is before
    response=post('/m4/configure',fields);assert 'result' not in j and len(j['sources'])==2
    escape=tmp_path/'escape.csv';escape.symlink_to('/etc/passwd')
    post('/m4',{'mode':'advanced'});response=post('/m4/sources',{'local_path':str(escape)});assert b'outside the configured' in response.data
    store.cleanup()


def test_segments_dependencies_and_precision_controls(tmp_path):
    from scipy.stats import spearmanr
    p=tmp_path/'advanced.csv';p.write_text('x,z,channel,label\n'+''.join(f'{i},{2*i},{"a" if i<120 else "b"},{"yes" if i<120 else "no"}\n' for i in range(240)))
    task=TaskSpec('classification','label')
    advanced=AdvancedTabularOptions(spearman_pairs=(('x','z'),),segments=(SegmentSpec('channel'),))
    cfg=AnalysisConfig(features=FeatureOptions({'x':'quantitative','z':'quantitative','channel':'categorical'}),advanced=advanced)
    r=DataTrust.from_spec(DatasetSpec(str(p)),task,cfg).analyze_result()
    dep=r.coverage['measurements']['dataset.dependencies'];pair=next(v for v in dep['pairs'] if v['columns']==['x','z'])
    assert pair['spearman']==pytest.approx(1)
    assert dep['categorical_input_target_proxies'][0]['review']
    assert r.coverage['measurements']['dataset.segments']['completed_checks']>0
    a=DatasetInput('a','reference',DatasetSpec(str(p)),task,replace(cfg,advanced=None))
    b=replace(a,id='b',role='current')
    comparison=DataTrust.compare(ComparisonSpec('versions',(a,b)),ComparisonConfig(advanced=AdvancedTabularOptions(missingness=False,dependencies=False,segments=(SegmentSpec('channel'),))))
    assert comparison.coverage['measurements']['a:b.segment_mix']['declarations'][0]['total_variation']==0
    assert any('segment' in k and k.endswith('populations') for k in comparison.coverage['measurements'])


def test_committed_partial_evidence(tmp_path,monkeypatch):
    import datatrust.m4_diagnostics as diag
    from datatrust.m4_worker import execute
    a=source(tmp_path,'a.csv','x,y\n1,2\n2,4\n')
    def broken(*args):raise RuntimeError('controlled optional failure')
    monkeypatch.setattr(diag,'dependence',broken)
    result=execute((a,),ExecutionOptions(),AdvancedTabularOptions())
    assert result.execution['status']=='partial'
    assert result.coverage['diagnostics']['a.dependencies']['status']=='failed'
    assert result.coverage['measurements']['a.structure']['row_count']==2


def test_empty_quantitative_populations_and_declared_units(tmp_path):
    a=source(tmp_path,'a.csv','x,y\n1,1\n2,2\n',TaskSpec('regression','y'),AnalysisConfig(regression=RegressionOptions(TargetExpectations(units='kg'))))
    b=source(tmp_path,'b.csv','x,y\n,1\n,2\n',a.task,AnalysisConfig(parsing=CsvParseOptions(column_types={'x':'numeric'}),regression=RegressionOptions(TargetExpectations(units='lb'))))
    r=DataTrust.compare(ComparisonSpec('versions',(replace(a,role='reference'),replace(b,role='current'))))
    columns=r.coverage['measurements']['a:b.populations']['columns']
    assert next(c for c in columns if c['column']=='y')['distribution_block']=='conflicting_declared_meanings_or_units'
    assert any(c['column']=='y' for c in r.coverage['measurements']['a:b.schema']['changes'])
    for declarations in ((ValueConstraint(('x',),'type','string'),ValueConstraint(('x',),'type','numeric')),(ValueConstraint(('x',),'allowed_values',[1]),ValueConstraint(('x',),'minimum',2))):
        with pytest.raises(ValueError,match='Contradictory'):AdvancedTabularOptions(constraints=declarations)


def test_three_source_affected_unions(tmp_path):
    inputs=tuple(source(tmp_path,name+'.csv','id,x\n001,1\n002,2\n',TaskSpec('dataset_profile',group_columns=('id',))) for name in ('a','b','c'))
    spec=ComparisonSpec('splits',tuple(replace(i,role=role) for i,role in zip(inputs,('train','validation','test'))),identity_keys=(('id',),))
    r=DataTrust.compare(spec)
    union=r.coverage['measurements']['comparison.overlap_row_unions']['a']
    assert union['records']['affected_rows']==2 and union['features']['affected_rows']==2 and union['entity']['affected_rows']==2
    assert union['entity']['completed_definitions']==2


def test_fractional_numeric_keys_cannot_collapse_decimal_identity(tmp_path):
    a=source(tmp_path,'a.csv','id,x\n0.1,1\n0.100000000000000000001,2\n',TaskSpec('dataset_profile',group_columns=('id',)),AnalysisConfig(parsing=CsvParseOptions(column_types={'id':'numeric'})))
    w=Workspace(ExecutionOptions(),[a])
    try:
        with pytest.raises(ValueError,match='decimal identity'):ingest(w,a)
    finally:w.close()


def test_unknown_type_is_inconclusive_and_schema_counts_are_fields(tmp_path):
    a=source(tmp_path,'a.csv','x,y\n,1\n,2\n')
    cfg=AnalysisConfig(advanced=AdvancedTabularOptions(missingness=False,dependencies=False,constraints=(ValueConstraint(('x',),'type','numeric'),ValueConstraint(('missing',),'required'))))
    r=DataTrust.from_spec(a.dataset,a.task,cfg).analyze_result()
    declarations=r.coverage['measurements']['dataset.constraints']['declarations']
    assert declarations[0]['blocked']=='unknown_logical_type' and declarations[0]['violations'] is None
    assert declarations[1]['violations']==1 and declarations[1]['violation_unit']=='fields'
    finding=next(f for f in r.findings if f['evidence_type']=='declared_violation')
    assert finding['priority']=='High' and finding['affected_count'] is None
