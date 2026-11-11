from dataclasses import replace
import numpy as np
import pytest
from confidenceguard import EvaluationConfig
from confidenceguard.investigation import investigate,inspect_investigation
from confidenceguard.investigation_membership import MembershipArtifact
from confidenceguard.confirmation import feasibility
from confidenceguard.investigation_contracts import ConfirmationSpec
from .helpers import binary


def test_interaction_recovery_and_H_is_sealed(tmp_path):
    spec=binary(tmp_path);preview=inspect_investigation(spec)
    assert not preview['H_outcomes_disclosed']
    result=investigate(spec,expected_fingerprint=preview['fingerprint'])
    candidates=result.data['investigation']['candidates']
    assert candidates and max(c['S']['effect'] for c in candidates)==pytest.approx(1.)
    assert all(c['state']=='exploratory' and not c['H_assessed'] for c in candidates)
    import csv
    path=tmp_path/'predictions.csv'
    with path.open() as stream:rows=list(csv.DictReader(stream))
    for row in rows:
        if row['role']=='H':row['y']=str(1-int(row['y']))
    with path.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    changed=investigate(spec)
    assert result.private['artifacts']==changed.private['artifacts']
    fields=('planned','available','members','nonmembers','conditional_members','conditional_nonmembers','effect','effect_state')
    assert [{k:c['S'][k] for k in fields} for c in candidates]==[{k:c['S'][k] for k in fields} for c in changed.data['investigation']['candidates']]


def test_nominal_bootstrap_admission_32_hypotheses():
    spec=ConfirmationSpec(method='bca')
    for components,expected in ((1,25600),(2,51200),(4,102400)):
        result=feasibility(spec,32,[components]*32,units=100,records=100,work_budget=10**12,available_bytes=10**9).to_dict()
        assert result['minimum_nominal_replicates']==expected
        assert result['effective_replicates']==expected
    result=feasibility(replace(spec,replicate_policy='fixed'),32,[1]*32,units=100,records=100,work_budget=10**12,available_bytes=10**9).to_dict()
    assert 'insufficient_nominal_tail_resolution' in result['reasons']
