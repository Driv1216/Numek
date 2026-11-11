import copy
import math
import numpy as np
import pytest
from confidenceguard.investigation_reconciliation import reconcile,adverse_value


def candidate(identifier,effect,support,complexity,state='finite'):
    return {'id':identifier,'objective':{'id':'objective'},'S':{'effect':effect,'effect_state':state,'conditional_members':support},
            'complexity':complexity,'_S_mask':'01' if identifier=='infinite' else '02'}


def test_extended_adverse_effect_is_preserved_in_selection():
    rows=[candidate('undefined',None,100,1,'undefined'),candidate('finite',.3,50,1),candidate('infinite',None,30,2,'positive_infinity')]
    ordered,_,selected=reconcile(rows,3,100)
    assert 'infinite' in selected and 'finite' in selected and 'undefined' not in selected
    assert next(c for c in ordered if c['id']=='undefined')['frontier'] is None


def test_shortlist_reserves_broad_material_impact_alongside_narrow_severity():
    rows=[]
    for identifier,effect,start,support in [('severe',.6,0,70),('another_severe',.59,70,90),('broad',.3,0,500)]:
        row=candidate(identifier,effect,support,2 if identifier=='broad' else 1)
        row['objective']['practical_threshold']=.15
        row['_S_mask']=(((1<<support)-1)<<start).to_bytes(125,'little').hex();rows.append(row)
    _,overlap,selected=reconcile(rows,2,1000)
    assert selected==['severe','broad']
    assert overlap['shortlist_union_support']==500


def test_material_impact_anchor_preserves_marginal_admission_and_missing_threshold_semantics():
    rows=[]
    for identifier,effect,start,support in [('severe',.6,0,30),('rejected',.4,30,400),('admitted',.3,30,250)]:
        row=candidate(identifier,effect,support,1);row['objective']['practical_threshold']=.15
        row['_S_mask']=(((1<<support)-1)<<start).to_bytes(125,'little').hex();rows.append(row)
    def novelty(row,previous):return {'admitted':row['id']!='rejected','previous':previous}
    _,_,selected=reconcile(copy.deepcopy(rows),2,1000,novelty)
    assert selected==['severe','admitted']
    for row in rows:row['objective'].pop('practical_threshold')
    _,_,selected=reconcile(rows,2,1000)
    assert selected==['severe','rejected']  # no invented material threshold


def test_exact_gate_fidelity_is_identity_with_explicit_availability_and_denominator():
    from confidenceguard.investigation_reconciliation import explanation
    def measured(member,available):
        mask={'member':np.array(member,bool),'available':np.array(available,bool)}
        return explanation({}, {'kind':'structured'}, {}, {}, {}, {}, mask, mask, None, lambda *args:None)
    result=measured([True,True,False,False,False],[True,True,True,False,False])
    expected={
        'basis':'exact_definition_identity','precision':1.,'recall':1.,'true_positive':2,
        'false_positive':0,'false_negative':0,'true_negative':1,'available':3,'unavailable':2}
    assert result['defines_membership'] and {k:result['fidelity'][k] for k in expected}==expected
    assert result['fidelity']['planned']==5 and result['fidelity']['jointly_available']==3
    assert not result['causal_interpretation']
    for member,available in [([False,False],[True,True]),([False,False],[False,False])]:
        empty=measured(member,available)['fidelity']
        assert empty['precision'] is None and empty['recall'] is None
        assert empty['available']+empty['unavailable']==2


def test_surrogate_fidelity_does_not_hide_gate_members_without_explanations():
    from confidenceguard.investigation_reconciliation import fidelity_counts
    gate={'member':np.array([1,1,1,0,0],bool),'available':np.array([1,1,1,1,0],bool)}
    surrogate={'member':np.array([1,0,0,1,1],bool),'available':np.array([1,1,0,1,1],bool)}
    measured=fidelity_counts(gate,surrogate,basis='frozen_D_fitted_surrogate')
    assert measured['planned']==5 and measured['gate_available']==measured['surrogate_available']==4
    assert measured['jointly_available']==measured['available']==3 and measured['unavailable']==2
    assert measured['gate_members_without_surrogate']==1
    assert [measured[k] for k in ('true_positive','false_positive','false_negative','true_negative')]==[1,1,1,0]
    assert measured['precision']==measured['recall']==.5 and measured['disagreement_rate']==pytest.approx(2/3)


def test_bounded_overlap_detail_prioritizes_shortlist_and_reports_omissions():
    rows=[]
    for i in range(250):
        row=candidate(f'{i:04}',.3,2,1)
        row['_S_mask']=(1|(1<<(i+1))).to_bytes(32,'little').hex();rows.append(row)
    _,overlap,selected=reconcile(rows,10,256)
    assert overlap['total_overlapping_pairs']==250*249//2
    assert overlap['retained_pairs']==1000 and overlap['omitted_pairs']==250*249//2-1000
    assert not overlap['pair_coverage_complete'] and overlap['shortlist_pairs_complete']
    expected={(a,b) for i,a in enumerate(selected) for b in selected[i+1:]}
    actual={(r['left'],r['right']) for r in overlap['pairs']}
    assert expected<=actual and len(expected)==45
    assert overlap['shortlist_union_support']==11  # shared opportunity counted once


def test_pareto_levels_agree_with_independent_partial_order_reference():
    rng=np.random.default_rng(557);rows=[candidate(str(i),float(rng.integers(0,10))/10,int(rng.integers(1,100)),int(rng.integers(1,10))) for i in range(600)]
    pending=list(copy.deepcopy(rows));expected={};level=0
    while pending:
        undominated=[]
        for c in pending:
            a=(c['S']['effect'],c['S']['conditional_members'],-c['complexity'])
            if not any(all(x>=y for x,y in zip((b['S']['effect'],b['S']['conditional_members'],-b['complexity']),a)) and any(x>y for x,y in zip((b['S']['effect'],b['S']['conditional_members'],-b['complexity']),a)) for b in pending):undominated.append(c)
        for c in undominated:expected[c['id']]=level
        ids={c['id'] for c in undominated};pending=[c for c in pending if c['id'] not in ids];level+=1
    ordered,_,_=reconcile(rows,10,100)
    assert {c['id']:c['frontier'] for c in ordered}==expected


@pytest.mark.parametrize('same_representation',[False,True])
def test_stability_cannot_borrow_recovery_from_another_representation(monkeypatch,tmp_path,same_representation):
    from types import SimpleNamespace
    from confidenceguard import investigation,investigation_objectives,investigation_reconciliation
    from confidenceguard.investigation_contracts import InvestigationLimits
    keys=[str(i) for i in range(8)]
    vectors={name:{'vectors':np.arange(4,dtype=float)[:,None],'available':np.ones(4,bool)} for name in ('A','B')}
    spec=SimpleNamespace(limits=InvestigationLimits(stability_replicates=1),
                         roles=SimpleNamespace(unit='entity'),objectives=[SimpleNamespace(id='loss')])
    objective=SimpleNamespace(discovery_targets=lambda:(keys[:4],[{'eligible':np.ones(4,bool),'loss':np.arange(4,dtype=float)}]))
    monkeypatch.setattr(investigation_objectives,'bind',lambda *args:objective)
    perfect={'representation':'B','mask':[True,True,False,False]}
    partial={'representation':'A','mask':[True,False,False,False]}
    monkeypatch.setattr(investigation,'propose_diagnostic_targets',lambda *args,**kwargs:
                        ([{'artifact':a,'head':'risk'} for a in ([perfect,partial] if same_representation else [perfect])],{}))
    monkeypatch.setattr(investigation_reconciliation,'apply',lambda a,*args,**kwargs:
                        {'member':np.array(a['mask'],bool),'available':np.ones(4,bool)})
    p=SimpleNamespace(spec=spec,keys=keys,records=[{'entity_key':k} for k in keys],store=None,
        config=SimpleNamespace(max_rss_bytes=64*1024**2,threads=1),work=SimpleNamespace(root=tmp_path),reserve_diagnostic_fit=lambda:None,
        role_data=lambda role:(np.arange(4) if role=='D' else np.arange(4,8),{},vectors))
    candidate={'id':'selected','objective':{'id':'loss'},'strategy':'geometric','head':'risk','membership_artifact':'original'}
    investigation_reconciliation.stability(p,[candidate],['selected'],
        {'original':{'representation':'A','mask':[True,True,False,False]}},{},lambda *args:None)
    result=candidate['stability']
    assert result['method']=='bounded_D_unit_bootstrap_refits_v2'
    assert result['median_membership_IoU']==(.5 if same_representation else 0.)
    assert result['results'][0]['applicable_fraction']==(1. if same_representation else None)
