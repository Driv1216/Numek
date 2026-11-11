from dataclasses import replace
import json,csv
from confidenceguard import (fit_methods,PolicySpec,PolicyInputSpec,PolicyStudySpec,PolicyMetricSpec,PolicyApplicationSpec,PolicyAssessmentSpec,PolicyClaim,FeatureViewSpec,FeatureField)
from confidenceguard.method_contracts import RoleSpec
from confidenceguard.contracts import EvaluationSpec
from confidenceguard.policies import optimize_policies,replay_policy
from confidenceguard.policy_assessment import freeze_policy_family,inspect_policy_assessment
from tests.cg2.test_methods import binary_spec
from .helpers import evidence,threshold
CFG={'free_disk_bytes':1}

def test_frozen_CG2_outputs_apply_without_refitting_and_missing_membership_refuses(tmp_path):
    raw=binary_spec(tmp_path);fitted=fit_methods(raw,CFG)
    before=(tmp_path/'predictions.csv').read_bytes()
    inp=PolicyInputSpec(RoleSpec.from_dict(raw['roles']),evaluation=EvaluationSpec.from_dict(raw['evaluation']),fitted_methods=tuple(fitted.private['fitted_methods']),membership_sidecars=tuple(fitted.private['membership_sidecars']))
    task=inp.evaluation.task
    p=PolicySpec(task,'beta',{'root':{'kind':'action','action':{'kind':'argmax'}}},'root',{'kind':'abstain'},{'kind':'unavailable'})
    result=optimize_policies(PolicyStudySpec(inp,(PolicyMetricSpec('accuracy','issued_accuracy','maximize'),),candidates=(p,)),CFG)
    key=result.data['policy']['nomination']['policy_digest']
    assert result.private['policies'][key]['input_identity']['method_digest']==fitted.private['fitted_methods'][0]['artifact_digest']
    protocol=PolicyAssessmentSpec((PolicyClaim('requirement',key,PolicyMetricSpec('accuracy','issued_accuracy','maximize'),'ge',.1),),sampling='independent_rows',upstream_independence='declared_independent',external_exposure='declared_unexposed',declaration_author='fixture',declaration_reason='Synthetic upstream roles checked')
    frozen=freeze_policy_family(result,assessment=protocol)
    assert not inspect_policy_assessment(frozen,CFG)['admissibility_reasons']
    absent=replace(inp,membership_sidecars=())
    assert 'upstream_membership_unavailable_or_contradicted' in inspect_policy_assessment(frozen,CFG,assessment_input=absent)['admissibility_reasons']
    assert (tmp_path/'predictions.csv').read_bytes()==before


def test_CG4_frozen_ternary_membership_and_outcome_context_refusal(tmp_path):
    from confidenceguard.investigation_membership import seal
    inp=evidence(tmp_path);view=FeatureViewSpec('context',(FeatureField('group','group'),),availability='at_decision')
    artifact=seal('structured',{'clauses':[{'field':'context.group','op':'eq','value':'a','kind':'categorical'}]},features=['context.group'])
    provenance={'feature_time_policy':'declared_information_cutoff_v2','development_events':[],'development_units':[],'independence':'unknown'}
    inp=replace(inp,features=(view,),regions=({'artifact':artifact,'models':{},'provenance':provenance},))
    p=threshold(inp.evaluation.task);nodes=p.to_dict()['nodes'];nodes['root']['when']={'kind':'region','digest':artifact['artifact_digest'],'state':'member'}
    p=replace(p,nodes=nodes);replayed=replay_policy(PolicyApplicationSpec(inp,p,role='S',metrics=(PolicyMetricSpec('coverage','issued_coverage'),)),CFG)
    assert len(replayed.private['action_ledger'])==40
    assert sum(a['value']=='yes' for a in replayed.private['action_ledger'])==20
    # Unknown imported region development provenance is not repaired by scoped
    # upstream/external declarations on the assessment protocol.
    selected=optimize_policies(PolicyStudySpec(inp,(PolicyMetricSpec('coverage','issued_coverage','maximize'),),candidates=(p,)),CFG)
    key=selected.data['policy']['nomination']['policy_digest'];protocol=PolicyAssessmentSpec((PolicyClaim('coverage',key,PolicyMetricSpec('coverage','issued_coverage','maximize'),'ge',.5),),sampling='independent_rows',upstream_independence='declared_independent',external_exposure='declared_unexposed',declaration_author='fixture',declaration_reason='External declaration cannot repair missing region provenance')
    family=freeze_policy_family(selected,assessment=protocol)
    assert 'region_development_provenance_unavailable' in inspect_policy_assessment(family,CFG)['admissibility_reasons']
