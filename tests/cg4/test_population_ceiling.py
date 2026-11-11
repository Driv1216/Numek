"""A declared absolute ceiling must not require heterogeneous diagnostic losses."""
import csv
from dataclasses import replace
import numpy as np
import pytest

from confidenceguard import investigate,freeze_hypotheses,confirm_investigation
from confidenceguard.investigation_membership import MembershipArtifact
from .helpers import binary
from .test_confirmation import declared


@pytest.mark.parametrize('strategy',['structured','catboost'])
def test_uniform_failure_above_declared_ceiling_is_a_frozen_population_claim(tmp_path,strategy):
    spec=binary(tmp_path,strategies=(strategy,))
    path=tmp_path/'predictions.csv'
    with path.open() as stream:rows=list(csv.DictReader(stream))
    for row in rows:row['decision']=str(1-int(row['y']))
    with path.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    spec=replace(spec,objectives=(replace(spec.objectives[0],comparator='ceiling',ceiling=.1),))
    result=investigate(spec)
    candidates=result.data['investigation']['candidates']
    assert len(candidates)==1
    population=candidates[0]
    assert population['definition']=={'clauses':[]} and population['proposal_source']=='declared_ceiling_population_baseline_v1'
    assert population['D']['members']==population['D']['planned']==240
    assert population['S']['conditional_members']==240 and population['S']['effect']==pytest.approx(.9)
    assert population['S']['nonmembers']==population['S']['unavailable']==0
    assert population['stability']['method']=='fixed_population_definition_v1'
    artifact=result.private['artifacts'][population['membership_artifact']]
    applied=MembershipArtifact(artifact).apply({'unused':[{'kind':'categorical','state':'unavailable','lexical':None,'canonical':None} for _ in range(11)]})
    assert np.array_equal(applied['member'],np.ones(11,bool)) and applied['available'].all()
    if strategy=='structured':
        frozen=freeze_hypotheses(result,[population['id']],confirmation=declared())
        assessed=confirm_investigation(frozen)
        claim=assessed.data['investigation']['assessments'][0]
        assert claim['state']=='confirmed' and claim['interval']['lower']>.1
        assert claim['support']['planned']==claim['support']['available']==240


def test_population_gate_has_no_hidden_dependencies_or_empty_disjuncts():
    from confidenceguard.contracts import EvaluationError
    from confidenceguard.investigation_membership import seal,apply
    gate=seal('structured',{'clauses':[]})
    for n in (0,7):
        outcome=apply(gate,{}, {},cache={'_population_size':n})
        assert len(outcome['member'])==n and outcome['member'].all() and outcome['available'].all()
    for parameters,fields in [({'any_of':[[]]},[]),({'clauses':[]},['unused']),({'clauses':False},[])]:
        with pytest.raises(EvaluationError):seal('structured',parameters,features=fields)


def test_population_baseline_below_ceiling_is_not_shortlisted(tmp_path):
    # Original deterministic fixture has 50% error in every role; an 80% ceiling
    # admits a baseline candidate but cannot turn it into an adverse finding.
    spec=binary(tmp_path)
    spec=replace(spec,objectives=(replace(spec.objectives[0],comparator='ceiling',ceiling=.8),))
    result=investigate(spec)
    population=next(c for c in result.data['investigation']['candidates'] if c.get('proposal_source'))
    assert population['S']['effect']==pytest.approx(-.3)
    assert population['id'] not in result.data['investigation']['shortlist']
    assert population['state']=='exploratory' and not population['H_assessed']
