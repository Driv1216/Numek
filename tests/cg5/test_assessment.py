from dataclasses import replace
import copy
import pytest

from confidenceguard.contracts import EvaluationConfig,EvaluationError
from confidenceguard.policy_contracts import PolicyAssessmentSpec,PolicyClaim,PolicyMetricSpec,FrozenPolicyFamily
from confidenceguard.policies import optimize_policies
from confidenceguard.policy_assessment import freeze_policy_family,preview_policy_assessment,inspect_policy_assessment,assess_policies
from .helpers import study

CONFIG=EvaluationConfig(free_disk_bytes=1)


def protocol(result,bound=.5):
    key=result.data['policy']['nomination']['policy_digest']
    return PolicyAssessmentSpec((PolicyClaim('accuracy_requirement',key,PolicyMetricSpec('accuracy','issued_accuracy','maximize'),'ge',bound),),
        sampling='independent_rows',upstream_independence='declared_independent',external_exposure='declared_unexposed',
        declaration_author='Synthetic fixture',declaration_reason='Separate IID synthetic opportunities and isolated development.')


def test_freeze_preview_independent_assessment_and_immutable_reopen(tmp_path):
    result=optimize_policies(study(tmp_path),CONFIG); p=protocol(result)
    preview=preview_policy_assessment(result,p,planned_e_size=1000)
    assert not preview['assessment_values_accessed'] and not preview['alpha_spent']
    assert preview['claims'][0]['scenario_conditional_support']==1000
    browser_protocol=p.to_dict();browser_protocol['claims'][0]['metric']['weight']=1
    assert preview_policy_assessment(result,browser_protocol,planned_e_size=1000)['claims'][0]['scenario_conditional_support']==1000
    frozen=freeze_policy_family(result,assessment=p)
    inspection=inspect_policy_assessment(frozen,CONFIG)
    assert inspection['assessment_values_disclosed'] is False
    assert not inspection['admissibility_reasons']
    assessed=assess_policies(frozen,CONFIG,expected_fingerprint=inspection['fingerprint'])
    claim=assessed.data['policy']['assessments'][0]
    assert claim['state']=='supported' and claim['lower']>.5 and claim['upper']==1
    assert claim['support']==40 and claim['family_size']==1
    assert type(assessed).from_dict(assessed.to_private_dict(),private=assessed.private).data==assessed.data
    repeated=inspect_policy_assessment(frozen,CONFIG)
    assert 'assessment_population_previously_exposed' in repeated['admissibility_reasons']
    with pytest.raises(EvaluationError):
        changed=frozen.to_dict(); changed['protocol']['claims'][0]['bound']=.1; FrozenPolicyFamily.from_dict(changed)


def test_exposed_assessment_cannot_be_repackaged_as_fresh_family(tmp_path):
    result=optimize_policies(study(tmp_path),CONFIG); frozen=freeze_policy_family(result,assessment=protocol(result))
    assess_policies(frozen,CONFIG)
    changed=freeze_policy_family(result,assessment=protocol(result,.6))
    inspection=inspect_policy_assessment(changed,CONFIG)
    assert 'assessment_population_previously_exposed' in inspection['admissibility_reasons']
    refused=assess_policies(changed,CONFIG)
    assert refused.data['policy']['assessments'][0]['state']=='unsupported'
    assert not refused.data['measurements']


def test_missing_assumptions_and_general_cluster_design_refuse_without_metrics(tmp_path):
    result=optimize_policies(study(tmp_path),CONFIG); p=protocol(result)
    p=replace(p,sampling='independent_entities')
    frozen=freeze_policy_family(result,assessment=p)
    assert inspect_policy_assessment(frozen,CONFIG)['claims'][0]['method_refusal']=='sampling_design_not_registered'
    assessed=assess_policies(frozen,CONFIG)
    assert assessed.data['policy']['assessments'][0]['state']=='unsupported'
    assert not assessed.data['measurements']


def test_failed_assessment_reservation_remains_spent(tmp_path,monkeypatch):
    from confidenceguard import policy_assessment
    result=optimize_policies(study(tmp_path),CONFIG);frozen=freeze_policy_family(result,assessment=protocol(result))
    original=policy_assessment.compat.supervise
    def fail(operation,args,config,**kwargs):
        if operation is policy_assessment._assess_worker: raise EvaluationError('Injected worker interruption','cancelled')
        return original(operation,args,config,**kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(policy_assessment.compat,'supervise',fail)
        with pytest.raises(EvaluationError): assess_policies(frozen,CONFIG)
    other=freeze_policy_family(result,assessment=protocol(result,.7))
    assert 'assessment_population_previously_exposed' in inspect_policy_assessment(other,CONFIG)['admissibility_reasons']


def test_finite_reference_coverage_and_family_weights():
    import math,numpy as np
    from confidenceguard.confirmation import binomial_interval,bounded_interval
    from confidenceguard.policy_assessment import claim_alpha
    for n in range(1,9):
        intervals=[binomial_interval(np.array([1.]*k+[0.]*(n-k)),.05) for k in range(n+1)]
        for p in (.1,.5,.9):
            coverage=sum(math.comb(n,k)*p**k*(1-p)**(n-k) for k,(lo,hi) in enumerate(intervals) if lo<=p<=hi)
            assert coverage>=.95-1e-12
    a=PolicyClaim('a','digest',PolicyMetricSpec('m','issued_coverage'),'le',1,weight='0.25')
    b=replace(a,id='b',weight='0.5');p=PolicyAssessmentSpec((a,b))
    assert claim_alpha(p,a)==.0125 and claim_alpha(p,b)==.025
    lo,hi=bounded_interval(np.array([.2,.4,.6]),(0,1),.05)
    radius=math.sqrt(math.log(40)/6)
    assert lo==max(0,.4-radius) and hi==min(1,.4+radius)
