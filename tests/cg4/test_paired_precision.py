"""Paired precision uses one issued base and distinct positive denominators."""
import csv
import copy
import numpy as np
import pytest
from confidenceguard import InvestigationSpec
from confidenceguard.investigation import arguments, prepared
from confidenceguard.investigation_membership import seal
from confidenceguard.investigation_objectives import bind


def fixture_spec(directory):
    path=directory/'paired.csv'
    with path.open('w',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['id','entity','role','y','current','reference','x'])
        for i in range(720):
            x=(i//3)%2;y=(i//6)%2
            writer.writerow([i,i,('D','S','H')[i%3],y,1 if x else y,y,x])
    return InvestigationSpec.from_dict({'evaluation':{
        'task':{'kind':'binary_classification','classes':['0','1'],'positive_class':'1','outcome_definition':'Synthetic paired precision'},
        'sources':[{'id':'data','path':str(path)}],
        'runs':[{'id':name,'source':'data','model':{'id':'paired-fixture','version':name},
                 'key_columns':['id'],'entity_columns':['entity'],'prediction':name} for name in ('current','reference')],
        'outcomes':{'source':'data','column':'y','key_columns':['id']}},
        'roles':{'namespace':'paired-precision-'+directory.name,'unit':'entity','column':'role'},
        'features':[{'id':'context','availability':'at_decision','fields':[{'id':'x','column':'x','kind':'categorical'}]}],
        'objectives':[{'id':'precision','metric':'precision','run':'current','reference_run':'reference',
                       'comparator':'paired','practical_threshold':.1}],
        'strategies':['structured'],'limits':{'max_nodes':10000,'candidates_per_strategy':8,'shortlist':3,'stability_replicates':1}})


def test_paired_native_precision_preserves_each_models_positive_denominator(tmp_path):
    spec=fixture_spec(tmp_path);s,c,roots=arguments(spec,None,None)
    with prepared(s,c,roots) as p:
        objective=bind(s.objectives[0],p.store);indices,features,_=p.role_data('D')
        member=np.array([cell['canonical']=='1' for cell in features['context.x']])
        artifact=seal('structured',{'clauses':[{'field':'context.x','kind':'categorical','op':'eq','value':'1'}]},
                      features=['context.x'],objective=objective.identity)
        measurement=p.evaluate(objective,'D',indices,{'member':member,'available':np.ones(len(indices),bool),
                                                    'reason':np.full(len(indices),'available')},artifact)
        # Direct fixture calculation: 60 true positives among current's 120
        # positive decisions; reference has only the 60 true positive decisions.
        assert measurement['member_metric']['value']==pytest.approx(.5)
        assert measurement['comparator_metric']['value']==pytest.approx(1.)
        assert measurement['conditional_members']==120
        assert measurement['conditional_nonmembers']==60
        assert measurement['effect']==pytest.approx(.5)


def test_paired_precision_diagnostic_can_learn_differing_positive_decisions(tmp_path):
    spec=fixture_spec(tmp_path);s,c,roots=arguments(spec,None,None)
    with prepared(s,c,roots) as p:
        objective=bind(s.objectives[0],p.store);keys,eligible,loss=objective.training('D')
        assert eligible.sum()==240
        assert sorted(set(np.round(loss[eligible],12)))==pytest.approx([-8/9,0,4/9])
        assert np.mean(loss[eligible])==pytest.approx(0.)


@pytest.mark.parametrize('case',['multiclass','missing_reference_decision'])
def test_paired_precision_requires_common_issued_base_without_common_positive_base(tmp_path,case):
    from dataclasses import replace
    spec=fixture_spec(tmp_path)
    if case=='multiclass':
        task=replace(spec.evaluation.task,kind='multiclass_classification',classes=('0','1','2'),positive_class=None)
        spec=replace(spec,evaluation=replace(spec.evaluation,task=task),objectives=(replace(spec.objectives[0],target='1'),))
    else:
        path=tmp_path/'paired.csv'
        with path.open() as stream:rows=list(csv.DictReader(stream))
        rows[3]['reference']=''
        with path.open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    s,c,roots=arguments(spec,None,None)
    with prepared(s,c,roots) as p:
        objective=bind(s.objectives[0],p.store);indices,features,_=p.role_data('D')
        member=np.array([cell['canonical']=='1' for cell in features['context.x']])
        artifact=seal('structured',{'clauses':[]},objective=objective.identity)
        measured=p.evaluate(objective,'D',indices,{'member':member,'available':np.ones(len(indices),bool),
                                                  'reason':np.full(len(indices),'available')},artifact)
        count=120 if case=='multiclass' else 119
        assert measured['member_metric']['value']==pytest.approx(60/count)
        assert measured['comparator_metric']['value']==1
        assert measured['conditional_members']==count and measured['conditional_nonmembers']==60


def declared():
    from confidenceguard import ConfirmationSpec
    return ConfirmationSpec(upstream_independence='declared_independent',external_exposure='declared_unexposed',
        declaration_author='independently generated synthetic fixture',declaration_reason='Isolated generated rows in a distinct test namespace; no upstream learning.')


def test_paired_precision_discovery_and_finite_confirmation_use_distinct_supports(tmp_path):
    from confidenceguard import investigate,freeze_hypotheses,confirm_investigation
    result=investigate(fixture_spec(tmp_path));assert result.data['investigation']['shortlist']
    frozen=freeze_hypotheses(result,confirmation=declared())
    assessed=confirm_investigation(frozen)
    rows=assessed.data['investigation']['assessments'];assert rows
    assert all(row['effect']==pytest.approx(.5) for row in rows)
    assert all(row['support']['conditional_members']==120 and row['support']['conditional_nonmembers']==60 for row in rows)
    assert all(row['member_metric']['value']==pytest.approx(.5) and row['comparator_metric']['value']==1 for row in rows)
    assert all(row['state']=='confirmed' and row['strength']=='finite_sample' for row in rows)
    from scipy.stats import binomtest
    confidence=1-.05/(2*len(rows))
    current=binomtest(60,120).proportion_ci(confidence_level=confidence,method='exact')
    reference=binomtest(60,60).proportion_ci(confidence_level=confidence,method='exact')
    assert all(row['interval']['lower']==pytest.approx(reference.low-current.high) and
               row['interval']['upper']==pytest.approx(reference.high-current.low) for row in rows)


def test_constructed_legacy_paired_precision_family_stays_readable_but_refuses_reassessment(tmp_path):
    from confidenceguard import investigate,freeze_hypotheses,inspect_confirmation,confirm_investigation
    from confidenceguard.contracts import digest
    from confidenceguard.investigation_contracts import FrozenHypothesisSet,confirmation_family_digest
    result=investigate(fixture_spec(tmp_path));packet=freeze_hypotheses(result,confirmation=declared()).to_dict()
    # Explicitly constructed compatibility specimen, not purported historical
    # evidence. Its hashes are recomputed so this tests semantic admission.
    aliases={};artifacts={}
    for old,artifact in packet['artifacts'].items():
        identity=copy.deepcopy(artifact['objective_identity']);identity.pop('paired_population_version')
        identity.pop('paired_eligible_population');identity['definition_version']='failure_objective_v1'
        replacement=seal(artifact['kind'],artifact['parameters'],features=artifact['features'],
                         representation=artifact['representation'],objective=identity)
        aliases[old]=replacement['artifact_digest'];artifacts[replacement['artifact_digest']]=replacement
    packet['artifacts']=artifacts
    for h in packet['hypotheses']:
        h['membership_artifact']=aliases[h['membership_artifact']];h['id']=digest({k:v for k,v in h.items() if k!='id'})
    packet['family_digest']=confirmation_family_digest(packet['hypotheses'],declared())
    packet['content_digest']=digest({k:v for k,v in packet.items() if k!='content_digest'})
    legacy=FrozenHypothesisSet.from_dict(packet);assert legacy.to_dict()==packet
    preview=inspect_confirmation(legacy)
    assert all('legacy_paired_precision_population_unqualified' in row['admissibility_reasons'] for row in preview['membership'])
    assessed=confirm_investigation(legacy)
    assert all(row['state']=='statistically_inadmissible' and not row['H_outcomes_disclosed'] for row in assessed.data['investigation']['assessments'])
    assert legacy.to_dict()==packet


def test_paired_precision_qualification_generator_has_distinct_denominators_and_fresh_seeds(tmp_path):
    import importlib.util
    import sys
    from pathlib import Path
    directory=Path(__file__).resolve().parents[2]/'validation/cg4'
    sys.path.insert(0,str(directory))
    try:
        descriptor=importlib.util.spec_from_file_location('cg4_paired_precision_qualification',directory/'qualify_objectives.py')
        module=importlib.util.module_from_spec(descriptor);descriptor.loader.exec_module(module)
        spec,region=module.generate(tmp_path,7,12000,'paired_precision')
    finally:sys.path.pop(0)
    assert module.PROTOCOL['panel_specific_seed_ranges']['paired_precision']==[380000,380039]
    assert module.PROTOCOL['criterion']=={'H_precision':.7,'H_recall':.7,'minimum_successes_of_40':32}
    with (tmp_path/'predictions.csv').open() as stream:rows=list(csv.DictReader(stream))
    y=np.array([int(row['outcome']) for row in rows]);current=np.array([int(row['prediction']) for row in rows]);reference=np.array([int(row['reference']) for row in rows])
    assert np.array_equal(current[~region],reference[~region])
    assert np.count_nonzero(region&(current==1))>np.count_nonzero(region&(reference==1))
    assert np.array_equal(current[y==1],reference[y==1])
    assert len(spec.evaluation.runs)==2 and spec.objectives[0].comparator=='paired'
