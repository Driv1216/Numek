"""Large marginal supports can still reveal small overlapping components."""
import copy
from types import SimpleNamespace
import numpy as np

from confidenceguard.contracts import DisclosureSpec
from confidenceguard.investigation_disclosure import project,related_membership_risk,overlap_projection


def packet(member,available=None):
    member=np.asarray(member,bool);available=np.ones(len(member),bool) if available is None else np.asarray(available,bool)
    return {'records':len(member),'member_bits':np.packbits(member,bitorder='little').tobytes().hex(),
            'available_bits':np.packbits(available,bitorder='little').tobytes().hex()}


def fixture(left,right):
    candidates=[];memberships={}
    for i,mask in enumerate((left,right)):
        count=int(np.count_nonzero(mask));record={'planned':128,'available':128,'members':count,'nonmembers':128-count,
            'conditional_members':count,'conditional_nonmembers':128-count,'unavailable':0,'effect':.2,'effect_state':'finite'}
        candidates.append({'id':f'c{i}','strategy':'geometric','membership_artifact':f'a{i}',
            'objective':{'metric':'error_rate','direction':'higher','comparator':'complement','units':'fraction'},
            'D':record,'S':record,'explanation':{'fidelity':None}})
        memberships[f'a{i}']={'D':packet(mask),'S':packet(mask)}
    private={'config':{'disclosure':DisclosureSpec().to_dict()},'memberships':memberships}
    raw={'schema_version':'confidenceguard.investigation_result/1.0','methodology_id':'failure_investigation_v1',
        'analysis_id':'synthetic','generated_at':'2026-10-25T00:00:00Z','execution':{},'task':{'kind':'binary_classification'},
        'investigation':{'stage':'discovery','candidates':candidates,'assessments':[]}}
    return SimpleNamespace(private=private,to_private_dict=lambda:copy.deepcopy(raw)),candidates


def test_rare_pair_cells_withhold_whole_related_family_despite_large_margins():
    left=np.arange(128)<64;right=np.arange(128)<63
    result,candidates=fixture(left,right)
    assert related_membership_risk(result.private,candidates,[],10)
    shared=project(result)
    assert shared['coverage']['withheld_related_family']
    assert all('D' not in c and 'S' not in c for c in shared['investigation']['candidates'])
    exact=project(result,DisclosureSpec(policy='exact_aggregates_v1'))
    assert exact['investigation']['candidates'][0]['D']['members']==64
    assert not exact['disclosure']['learned_artifacts_exported']


def test_balanced_components_and_ternary_availability_are_distinct():
    left=np.arange(128)<64;right=(np.arange(128)>=32)&(np.arange(128)<96)
    result,candidates=fixture(left,right)
    assert not related_membership_risk(result.private,candidates,[],10)
    assert not project(result)['coverage']['withheld_related_family']
    # A one-event applicability difference is a small cell, not a nonmember.
    available=np.ones(128,bool);available[127]=False
    result.private['memberships']['a1']['S']=packet(right,available)
    assert related_membership_risk(result.private,candidates,[],10)


def test_rare_outcome_status_protects_related_family_and_scope_survives_projection():
    result,candidates=fixture(np.arange(128)<64,np.arange(128)>=64)
    candidates[0]['D']['outcome_status_states']={'final':127,'withdrawn':1}
    assert project(result)['coverage']['withheld_related_family']
    exact=project(result,DisclosureSpec(policy='exact_aggregates_v1'))
    assert exact['investigation']['candidates'][0]['D']['outcome_status_states']=={'final':127,'withdrawn':1}
    raw=result.to_private_dict();raw['investigation'].update(candidates=[],stage='confirmation',
        assessments=[{'candidate_id':'a','state':'unreproduced','strength':'finite_sample',
            'support':{'planned':128,'members':128,'available':128},
            'outcome_status_states':{'final':127,'withdrawn':1}}]);raw['outcomes']={'scope':'observed_labels','private_future':'STATUS_PRIVATE_SENTINEL'}
    result.to_private_dict=lambda:copy.deepcopy(raw)
    shared=project(result)
    assert shared['coverage']['withheld_related_family'] and shared['outcomes']=={'scope':'observed_labels'}
    assert 'outcome_status_states' not in shared['investigation']['assessments'][0]


def test_rare_explanation_applicability_protects_the_related_aggregate_family():
    result,candidates=fixture(np.arange(128)<64,np.arange(128)>=64)
    candidates[0]['explanation']['fidelity']={'jointly_available':127,'available':127,
        'true_positive':60,'false_positive':20,'false_negative':20,'true_negative':27,
        'unavailable':1,'gate_members_without_surrogate':1}
    shared=project(result)
    assert shared['coverage']['withheld_related_family']
    assert all('S' not in c for c in shared['investigation']['candidates'])
    exact=project(result,DisclosureSpec(policy='exact_aggregates_v1'))
    assert exact['investigation']['candidates'][0]['S']['members']==64
    assert exact['investigation']['candidates'][0]['explanation']=='Approximate explanation retained locally'


def test_missing_misaligned_or_excessive_audit_evidence_withholds():
    result,candidates=fixture(np.arange(128)<64,np.arange(128)>=64)
    assert not related_membership_risk(result.private,candidates,[],10)
    original=copy.deepcopy(result.private)
    del result.private['memberships']['a1']['D']
    assert related_membership_risk(result.private,candidates,[],10)
    result.private=copy.deepcopy(original);result.private['memberships']['a1']['D']['records']=127
    assert related_membership_risk(result.private,candidates,[],10)
    result.private=copy.deepcopy(original);result.private['memberships']['a1']['D']['records']=80_000_000
    assert related_membership_risk(result.private,candidates,[],10)


def test_confirmation_family_uses_frozen_H_memberships():
    private={'frozen_hypotheses':{'hypotheses':[{'id':f'h{i}','membership_artifact':f'a{i}'} for i in range(2)]},
        'memberships':{'a0':{'H':packet(np.arange(128)<64)},'a1':{'H':packet(np.arange(128)<63)}}}
    assert related_membership_risk(private,[],[{'hypothesis_id':'h0'},{'hypothesis_id':'h1'}],10)


def test_conservative_overlap_is_explicit_and_exact_aggregates_use_public_aliases():
    import json
    from pathlib import Path
    from jinja2 import Environment,FileSystemLoader,select_autoescape
    result,_=fixture(np.arange(128)<64,(np.arange(128)>=32)&(np.arange(128)<96))
    raw=result.to_private_dict()
    raw['investigation']['overlap']={'shortlist_union_support':96,'selection_population':128,
        'total_overlapping_pairs':1,'omitted_pairs':0,'pair_coverage_complete':True,
        'pairs':[{'left':'c0','right':'c1','intersection':32,'union':96,'jaccard':1/3,
                  'left_contained':False,'private_note':'OVERLAP_PRIVATE_SENTINEL'}],
        'private_future_field':'OVERLAP_PRIVATE_SENTINEL'}
    result.to_private_dict=lambda:copy.deepcopy(raw)
    shared=project(result);exact=project(result,DisclosureSpec(policy='exact_aggregates_v1'))
    assert shared['investigation']['overlap']==[]
    assert shared['investigation']['overlap_disclosure']['state']=='withheld'
    assert not shared['coverage']['withheld_related_family']
    overlap=exact['investigation']['overlap']
    assert overlap['shortlist_union_support']==96 and overlap['retained_pairs']==1
    assert overlap['pairs'][0]['left']=='region_1' and overlap['pairs'][0]['right']=='region_2'
    assert overlap['pairs'][0]['left_contained'] is False
    assert 'OVERLAP_PRIVATE_SENTINEL' not in json.dumps(exact)
    assert raw['investigation']['overlap']['pairs'][0]['left']=='c0'
    templates=Path(__file__).resolve().parents[2]/'src/confidenceguard/templates'
    environment=Environment(loader=FileSystemLoader(templates),autoescape=select_autoescape(['html']))
    html=environment.get_template('investigation_sections.html').render(result=shared)
    assert 'Protected overlap evidence' in html and 'omission does not establish disjointness' in html
    html=environment.get_template('investigation_sections.html').render(result=exact)
    assert '96 distinct opportunities' in html and 'region_1 / region_2' in html
    assert 'OVERLAP_PRIVATE_SENTINEL' not in html


def test_overlap_projection_does_not_copy_unrecognized_values_or_claim_complete_missing_aliases():
    projected=overlap_projection({'shortlist_union_support':'PRIVATE',
        'pair_coverage_complete':True,'pairs':[{'left':'missing','right':'c1'}]}, {'c1':'region_1'})
    assert 'shortlist_union_support' not in projected and projected['pairs']==[]
    assert projected['pair_coverage_complete'] is False and projected['shortlist_pairs_complete'] is False
