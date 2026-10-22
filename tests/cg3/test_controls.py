import copy
from pathlib import Path
import pytest
from .test_history import workspace,batch,longitudinal
from .test_semantics import rewrite


def test_drift_and_deterioration_are_distinct(tmp_path):
    ws=workspace(tmp_path);source=batch(tmp_path,count=200)
    path=Path(source['evaluation']['sources'][0]['path'])
    rewrite(path,lambda rows:[r.update(p='0.8',y='1' if r['when'].startswith('2026-01') else '0') for r in rows])
    ws.ingest(source);result=ws.analyze(longitudinal(ws))
    assert next(m for m in result.data['history']['comparisons'][0]['metrics'] if m['metric']=='accuracy')['value']==-1
    assert next(d for d in result.data['history']['drift'] if d['field']=='probability_class_1')['ks_distance']==0


def test_capture_does_not_leak_e_labels_to_fit_or_selection(tmp_path):
    from tests.cg2.test_methods import binary_spec
    from confidenceguard import ReliabilityWorkspace,WorkspaceConfig
    from .test_semantics import rewrite
    spec=binary_spec(tmp_path,[{'id':'lac','kind':'lac','run':'original'},{'id':'aps','kind':'aps','run':'original'}])
    spec['selections']=[{'id':'sets','candidates':['lac','aps'],'objective':'efficiency','coverage_tolerance':.2}]
    packet={'namespace':'events','outcome_definition_version':'outcome-v1','operation':'study','evaluation':spec,'bindings':[{'run':'original'}]}
    one=workspace(tmp_path);first=one.ingest(packet)
    rewrite(tmp_path/'predictions.csv',lambda rows:[r.update(y=str(1-int(r['y']))) for r in rows if r['role']=='E'])
    two=ReliabilityWorkspace.initialize(tmp_path/'other',WorkspaceConfig(saving=True,free_disk_bytes=1));second=two.ingest(packet)
    assert one.open(first['assessment_id']).private['fitted_methods']==two.open(second['assessment_id']).private['fitted_methods']


def test_joint_family_disclosure_and_no_hidden_chart_values(tmp_path):
    ws=workspace(tmp_path);ws.ingest(batch(tmp_path,count=60));result=ws.analyze(longitudinal(ws,cohorts=[{'id':'partition','column':'group','categories':['a','b']}]))
    public=result.to_dict();disclosed={m['metric'] for m in public['measurements']}
    assert all(v['metric'] in disclosed for v in public['history']['temporal'])
    assert public['history']['drift']==public['history']['mix']==[]
    assert all(not m['evidence_refs'] and not m['data'] for m in public['measurements'])
    assert 'locators' not in public and 'workspace_root' not in str(public) and 'entity-' not in str(public)
    # A tiny cohort in one window withholds the whole dependent performance family.
    private=result.data['measurements']
    if any(v['denominator'] in range(1,10) for v in private):
        assert public['history']['joint_withholding']


def test_temporal_candidates_stable_shift_seasonal_sparse_and_gaps():
    from types import SimpleNamespace
    from confidenceguard import LongitudinalSpec,make_windows
    from confidenceguard.longitudinal import _temporal
    windows=make_windows('2026-01-01T00:00:00Z','2026-01-25T00:00:00Z',cadence_ns=str(86400*10**9))
    spec=LongitudinalSpec(namespace='events',windows=windows,min_segment_bins=5,seasonal_period=4)
    def temporal(values,support=40):
        stores={('variant',w.id):SimpleNamespace(evidence=SimpleNamespace(measurements=[{'scope':'overall','metric':'accuracy','value':v,'value_state':'finite' if v is not None else 'undefined','denominator':support}])) for w,v in zip(windows,values)}
        return _temporal(stores,spec)[0]
    assert temporal([.8]*24)['change_candidates']==[]
    shifted=temporal([.8]*12+[.4]*12)
    assert shifted['change_candidates'][0]['window']==windows[12].id
    seasonal=temporal([.5,.9,.5,.1]*6)
    assert seasonal['interpretation']=='exploratory' and len(seasonal['seasonal_phases'])==4
    assert temporal([.8]*12+[.4]*12,support=1)['change_candidates']==[]
    gapped=temporal([.8]*10+[None]+[.4]*13)
    assert gapped['change_candidates']==[] and gapped['sequence_reason']=='gapped_or_overlapping_window_sequence'


def test_withheld_accuracy_has_no_exact_error_count_bypass(tmp_path):
    ws=workspace(tmp_path);source=batch(tmp_path,count=60)
    rewrite(Path(source['evaluation']['sources'][0]['path']),lambda rows:[r.update(p='0.8',y='0' if i==0 else '1') for i,r in enumerate(rows)])
    ws.ingest(source);result=ws.analyze(longitudinal(ws,cohorts=[{'id':'p','column':'group','categories':['a','b']}]))
    public=result.to_dict()
    assert not any(m['metric'] in {'accuracy','error_rate','issued_errors'} for m in public['measurements'])
    assert not any(t['metric']=='issued_errors' for t in public['history']['temporal'])


def test_historical_features_do_not_require_columns_in_separate_label_file(tmp_path):
    import csv
    ws=workspace(tmp_path);source=batch(tmp_path,count=60);labels=tmp_path/'labels.csv'
    with Path(source['evaluation']['sources'][0]['path']).open() as stream:rows=list(csv.DictReader(stream))
    with labels.open('w') as stream:
        writer=csv.DictWriter(stream,fieldnames=['id','y','available','due']);writer.writeheader();writer.writerows({k:r[k] for k in writer.fieldnames} for r in rows)
    source['evaluation']['sources'].append({'id':'labels','path':str(labels)});source['evaluation']['outcomes']['source']='labels'
    ws.ingest(source);result=ws.analyze(longitudinal(ws))
    assert any(d['field']=='feature:group' and d['status']=='completed' for d in result.data['history']['drift'])


def test_frozen_actual_costs_and_replay_independent_variant_identity(tmp_path):
    ws=workspace(tmp_path);source=batch(tmp_path,count=60);ws.ingest(source);variant=ws.models()[0]['id']
    source['evaluation']['policies']=[{'id':'diagnostic','run':'base','kind':'probability_threshold','thresholds':[.4,.6]}]
    ws.ingest(source);assert len(ws.models())==1
    costs={'0':{'0':1.,'1':5.},'1':{'0':7.,'1':2.}}
    result=ws.analyze(longitudinal(ws,event_costs=costs))
    assert all(m['value']==1.5 for m in result.data['measurements'] if m['metric']=='empirical_cost')
    assert any(m['metric']=='empirical_cost' for m in result.data['history']['comparisons'][0]['metrics'])


def test_retention_metadata_respects_earlier_catalog_snapshot(tmp_path):
    import csv
    ws=workspace(tmp_path);first=ws.ingest(batch(tmp_path));source=batch(tmp_path,'later')
    path=Path(source['evaluation']['sources'][0]['path'])
    with path.open() as stream:rows=list(csv.DictReader(stream));fields=list(rows[0])+['x']
    for row in rows:row.update(id=str(100+int(row['id'])),x='1')
    with path.open('w') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)
    source['bindings'][0]['features']['x']='numeric';ws.ingest(source)
    with pytest.raises(Exception) as e:ws.analyze(longitudinal(ws,catalog_sequence=first['catalog_sequence'],features={'x':'numeric'}))
    assert e.value.code=='feature_not_retained'
    latest=ws.analyze(longitudinal(ws,features={'x':'numeric'}))
    assert next(d for d in latest.data['history']['drift'] if d['field']=='feature:x')['reason']=='partial_feature_retention'
