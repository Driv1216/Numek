"""Independent period-target references; these proxies never replace reducers."""
from types import SimpleNamespace
import duckdb
import numpy as np
import pytest

from confidenceguard.contracts import TaskDefinition,EvaluationError
from confidenceguard.investigation_contracts import FailureObjectiveSpec
from confidenceguard.investigation_objectives import Objective


@pytest.fixture
def historical():
    con=duckdb.connect()
    con.execute('CREATE TABLE evidence(event_key VARCHAR,entity_key VARCHAR,cg4_role VARCHAR,cg4_period VARCHAR,eligible BOOLEAN,loss DOUBLE)')
    rows=[('a-r','a','D','reference',True,0.),('a-c','a','D','current',True,1.),
          ('b-r','b','D','reference',True,1.),('b-c','b','D','current',True,1.),
          ('c-r','c','D','reference',False,None),('c-c','c','D','current',True,0.),
          ('d-r','d','D','reference',True,0.),('d-c1','d','D','current',True,0.),('d-c2','d','D','current',True,1.),
          ('n-r',None,'D','reference',True,0.),('n-c',None,'D','current',True,1.),
          ('s-r','a','S','reference',True,1000.),('h-c','a','H','current',True,1000.)]
    con.executemany('INSERT INTO evidence VALUES (?,?,?,?,?,?)',rows)
    task=TaskDefinition('binary_classification','Synthetic target',classes=('0','1'),positive_class='1')
    store=SimpleNamespace(con=con,spec=SimpleNamespace(task=task))
    spec=FailureObjectiveSpec('deterioration','error_rate','model',comparator='reference_period',
                             reference_period='reference',current_period='current',units='fraction',practical_threshold=.15)
    objective=Objective(spec,store,None,'evidence','eligible','loss','diagnostic','error_rate')
    yield objective
    con.close()


def test_period_heads_and_paired_entity_means_have_distinct_denominators(historical):
    keys,targets=historical.discovery_targets();byname={t['name']:t for t in targets}
    assert len(keys)==11 and len(targets)==3
    def measured(name):
        t=byname[name];return {k:float(v) for k,e,v in zip(keys,t['eligible'],t['loss']) if e}
    assert measured('current_period')=={'a-c':1.,'b-c':1.,'c-c':0.,'d-c1':0.,'d-c2':1.,'n-c':1.}
    assert measured('reference_favorable')=={'a-r':0.,'b-r':-1.,'d-r':0.,'n-r':0.}
    assert measured('entity_paired_period_delta')=={'a-c':1.,'b-c':0.,'d-c1':.5,'d-c2':.5}
    binding=byname['entity_paired_period_delta']['binding']
    assert binding['paired_entities']==3 and binding['defined_D_targets']==4
    assert binding['current_eligible_rows']==6 and binding['reference_eligible_rows']==4
    assert binding['conditional_denominator']=='eligible_records'
    assert all(t['binding']['authoritative_metric_unchanged'] for t in targets)
    assert historical.training_support['D']['learning_target_defined_records']==6


def test_S_H_changes_cannot_change_D_targets_and_missing_pairs_are_explicit(historical):
    before=historical.discovery_targets()
    historical.store.con.execute("UPDATE evidence SET loss=-999999 WHERE cg4_role IN ('S','H')")
    after=historical.discovery_targets();assert before[0]==after[0]
    for left,right in zip(before[1],after[1]):
        np.testing.assert_array_equal(left['eligible'],right['eligible'])
        np.testing.assert_array_equal(left['loss'],right['loss'])
        assert left['binding']==right['binding']
    historical.store.con.execute('UPDATE evidence SET entity_key=NULL')
    _,targets=historical.discovery_targets()
    assert not targets[2]['eligible'].any() and targets[2]['binding']['paired_entities']==0
    assert targets[0]['eligible'].sum()==6 and targets[1]['eligible'].sum()==4
    with pytest.raises(EvaluationError):historical.training('D',period='undeclared')


def test_entity_mean_does_not_overflow_merely_because_a_finite_sum_would(historical):
    from dataclasses import replace
    historical.spec=replace(historical.spec,metric='bias',units='metres')
    historical.native_metric='bias'
    historical.store.spec.task=TaskDefinition('regression','Synthetic residual',units='metres')
    historical.store.con.execute('DELETE FROM evidence')
    historical.store.con.executemany('INSERT INTO evidence VALUES (?,?,?,?,?,?)',[
        ('a-r','a','D','reference',True,0.),('a-c1','a','D','current',True,1e308),('a-c2','a','D','current',True,1e308),
        ('b-r','b','D','reference',True,-1e308),('b-c','b','D','current',True,1e308)])
    keys,targets=historical.discovery_targets();delta=targets[2]
    assert delta['eligible'][keys.index('a-c1')] and delta['eligible'][keys.index('a-c2')]
    assert delta['loss'][keys.index('a-c1')]==1e308
    assert not delta['eligible'][keys.index('b-c')]
    assert delta['binding']['nonfinite_delta_rows']==1


@pytest.mark.parametrize('strategy',['structured','catboost','geometric'])
def test_reference_only_deterioration_proposes_a_frozen_gate_when_current_risk_is_flat(historical,tmp_path,strategy):
    """Functional target/membership reference, not an empirical recovery claim."""
    from dataclasses import replace
    from confidenceguard.feature_contracts import FeatureField
    from confidenceguard.features import normalize
    from confidenceguard.investigation import propose_diagnostic_targets
    from confidenceguard.investigation_contracts import InvestigationLimits
    from confidenceguard.investigation_membership import apply
    historical.store.con.execute('DELETE FROM evidence');rows=[];hot_by_key={}
    for entity in range(120):
        hot=entity%2==0;current=float((entity//2)%2)
        for period,loss in [('reference',0. if hot else current),('current',current)]:
            key=f'{entity:03}-{period}';rows.append((key,str(entity),'D',period,True,loss));hot_by_key[key]=hot
    historical.store.con.executemany('INSERT INTO evidence VALUES (?,?,?,?,?,?)',rows)
    keys,targets=historical.discovery_targets();truth=np.array([hot_by_key[k] for k in keys])
    field=FeatureField('hot','hot',kind='boolean')
    features={'context.hot':[normalize('true' if flag else 'false',field) for flag in truth]}
    representations={'vector':{'id':'vector','vectors':truth.astype(float)[:,None],'available':np.ones(len(keys),bool),'normalization':'none'}}
    limits=InvestigationLimits(minimum_discovery_support=10,max_nodes=1000,max_depth=1,landmarks=16,neighbors=4,stability_replicates=1)
    models={};fits=[]
    invoke=lambda strategy,targets,limits:propose_diagnostic_targets(strategy,features,representations,historical,targets,limits,
        directory=tmp_path,models=models,threads=2,reserve_fit=lambda:fits.append(1),check=lambda *args:None,memory_budget=64*1024**2)
    if strategy=='structured':
        current_only,_=invoke(strategy,targets[:1],limits)
        assert current_only==[]  # Both feature groups have exactly 50% current loss.
    proposals,status=invoke(strategy,targets,limits)
    assert status['diagnostic_target_policy']=='historical_period_heads_and_matched_entity_delta_v1'
    assert len(proposals)<=limits.candidates_per_strategy
    fresh=np.tile([False,True],100)
    outside={'context.hot':[normalize('true' if flag else 'false',field) for flag in fresh]}
    vectors={'vector':{'vectors':fresh.astype(float)[:,None],'available':np.ones(len(fresh),bool)}}
    masks=[apply(p['artifact'],outside,vectors,cache={'_models':models,'_directory':str(tmp_path),'_population_size':len(fresh),'_threads':2}) for p in proposals]
    assert any(np.array_equal(mask['member'],fresh) and mask['available'].all() for mask in masks)
    assert any(p['diagnostic_target_binding']['name'] in {'reference_favorable','entity_paired_period_delta'} for p in proposals)
    if strategy=='catboost':assert len(fits)==6  # Two predefined depths for each of three nonconstant targets.
    if strategy=='structured':
        _,fair=invoke(strategy,targets,replace(limits,max_nodes=3))
        assert fair['nodes']==3 and [s['nodes'] for s in fair['diagnostic_targets']]==[1,1,1]
        _,bounded=invoke(strategy,targets,replace(limits,max_nodes=1))
        assert bounded['nodes']==1 and not bounded['search_complete']
        assert all(s['reason']=='shared_search_budget_exhausted' for s in bounded['diagnostic_targets'][1:])


def test_historical_target_investigation_freezes_native_claim_and_ignores_H_revisions(tmp_path):
    import csv,json
    from dataclasses import replace
    from confidenceguard import ReliabilityWorkspace,WorkspaceConfig,InvestigationSpec,inspect_investigation,freeze_hypotheses
    from confidenceguard.investigation import arguments,prepared
    source=tmp_path/'periods.csv';rows=[]
    for entity in range(720):
        hot=(entity//2)%2==1;y=entity%2
        for period,when in [('reference','2026-01-01T00:00:00Z'),('current','2026-02-01T00:00:00Z')]:
            error=period=='current' or not hot
            rows.append({'id':f'{period}-{entity}','entity':str(entity),'y':str(y),'decision':str(y^int(error)),
                         'hot':str(hot).lower(),'when':when,'available':'2026-03-01T00:00:00Z'})
    with source.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    namespace='cg4-reference-only-target-contract'
    evaluation={'task':{'kind':'binary_classification','outcome_definition':'Synthetic paired periods','classes':['0','1'],'positive_class':'1'},
        'sources':[{'id':'data','path':str(source)}],
        'runs':[{'id':'model','source':'data','model':{'id':'fixed','version':'1'},'key_columns':['id'],'entity_columns':['entity'],
                 'prediction':'decision','prediction_at':{'column':'when'}}],
        'outcomes':{'source':'data','column':'y','key_columns':['id'],'available_at':{'column':'available'}}}
    view={'id':'context','availability':'at_decision','fields':[{'id':'hot','column':'hot','kind':'boolean'}]}
    workspace=ReliabilityWorkspace.initialize(tmp_path/'workspace',WorkspaceConfig(saving=True,free_disk_bytes=1))
    workspace.ingest({'schema_version':'confidenceguard.prediction_batch_spec/2.0','namespace':namespace,
        'evaluation':evaluation,'outcome_definition_version':'v1','bindings':[{'run':'model'}],'feature_views':[view]})
    variant=workspace.models()[0]['id']
    spec=InvestigationSpec.from_dict({'history':{'workspace_path':str(workspace.path),'selection':{'namespace':namespace,'variants':[variant],
        'as_of':'2026-04-01T00:00:00Z','windows':[{'id':'reference','start':'2026-01-01T00:00:00Z','end':'2026-02-01T00:00:00Z'},
        {'id':'current','start':'2026-02-01T00:00:00Z','end':'2026-03-01T00:00:00Z'}]}},
        'roles':{'namespace':namespace,'unit':'entity'},'features':[view],'strategies':['structured','catboost'],
        'objectives':[{'id':'deterioration','metric':'error_rate','run':variant,'comparator':'reference_period',
            'reference_period':'reference','current_period':'current','practical_threshold':.15}],
        'limits':{'max_depth':1,'max_nodes':1000,'candidates_per_strategy':16,'stability_replicates':1}})
    preview=inspect_investigation(spec)
    assert not preview['H_outcomes_disclosed']
    assert preview['diagnostic_fit_admission']['initial_fit_ceiling']==6
    assert preview['diagnostic_fit_admission']['stability_fit_ceiling']==12
    result=workspace.investigate(spec);before=result.to_private_dict()
    candidate=next(c for c in result.data['investigation']['candidates'] if c['strategy']=='structured')
    assert candidate['S']['effect']==1.
    assert candidate['S']['member_metric']['value']==1. and candidate['S']['comparator_metric']['value']==0.
    assert candidate['S']['members']==2*candidate['S']['conditional_members']
    assert {b['name'] for b in candidate['diagnostic_target_bindings']}=={'reference_favorable','entity_paired_period_delta'}
    assert candidate['stability']['diagnostic_target_policy']=='historical_period_heads_and_matched_entity_delta_v1'
    assert all(e['period'] in {'reference','current'} and e['period_state']=='observed' for e in candidate['examples'])
    frozen=freeze_hypotheses(result)
    assert all(h['objective']['comparator']=='reference_period' and h['objective']['metric']=='error_rate' for h in frozen.data['hypotheses'])
    effective=InvestigationSpec.from_dict(result.private['investigation_spec']);s,c,roots=arguments(effective,None,None)
    with prepared(s,c,roots) as admitted:
        indices,_,_=admitted.role_data('H');originals=admitted.store.cg4_original_keys
        H={json.loads(originals[admitted.keys[i]])[0] for i in indices}
    updates=tmp_path/'H-revisions.csv'
    with updates.open('w',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['id','y','revision','order','available','status'])
        writer.writerows((r['id'],1-int(r['y']),'revision2',1,'2026-04-15T00:00:00Z','final') for r in rows if r['id'] in H)
    workspace.update_outcomes({'source':{'id':'updates','path':str(updates)},'namespace':namespace,'outcome_definition_version':'v1',
        'event_columns':['id'],'column':'y','revision_column':'revision','order_column':'order',
        'available_at':{'column':'available'},'status_column':'status'})
    packet=spec.to_dict();packet['history']['selection']['as_of']='2026-05-01T00:00:00Z'
    changed=workspace.investigate(packet)
    assert result.private['artifacts']==changed.private['artifacts']
    assert result.private['models']==changed.private['models']
    assert result.data['investigation']['shortlist']==changed.data['investigation']['shortlist']
    assert workspace.open(result.data['analysis_id']).to_private_dict()==before
