from dataclasses import replace
import pytest
from confidenceguard import ReliabilityWorkspace,WorkspaceConfig,investigate,freeze_hypotheses,inspect_confirmation,confirm_investigation,EvaluationError
from confidenceguard.evidence_use import EvidenceUseLedger
from .test_history import retained
from .test_confirmation import declared


def test_restore_and_later_consent_gaps_require_new_scoped_declarations(tmp_path):
    workspace,spec=retained(tmp_path);workspace.evidence_tracking(True)
    discovery=workspace.investigate(spec);old=freeze_hypotheses(discovery,confirmation=declared())
    workspace.backup(tmp_path/'backup')
    restored=ReliabilityWorkspace.restore(tmp_path/'backup',tmp_path/'restored')
    future=replace(spec,history={**spec.history,'workspace_path':str(restored.path)})
    preview=inspect_confirmation(old,confirmation_input=future)
    assert 'exposure_history_gap_requires_current_declaration' in preview['admissibility_reasons']
    token=EvidenceUseLedger(restored).status()['continuity_token']
    protocol=replace(declared(),exposure_history_token=token)
    current=freeze_hypotheses(discovery,confirmation=protocol)
    preview=inspect_confirmation(current,confirmation_input=future)
    assert not preview['admissibility_reasons']
    assert preview['independence']['history_gap_basis']=='current_scoped_declaration_not_system_verified_history'
    restored.evidence_tracking(False);restored.evidence_tracking(True)
    assert EvidenceUseLedger(restored).status()['continuity_token']!=token
    assert 'exposure_history_gap_requires_current_declaration' in inspect_confirmation(current,confirmation_input=future)['admissibility_reasons']
    protocol=replace(protocol,exposure_history_token=EvidenceUseLedger(restored).status()['continuity_token'])
    current=freeze_hypotheses(discovery,confirmation=protocol)
    protected=inspect_confirmation(current,confirmation_input=future,_protected=True)
    EvidenceUseLedger(restored).record('outcome_disclosure',**protected['_protected_population'])
    assert 'previously_exposed_confirmation_population' in inspect_confirmation(current,confirmation_input=future)['admissibility_reasons']


def test_historical_API_infers_tracking_and_cannot_redirect_it_to_another_workspace(tmp_path):
    workspace,spec=retained(tmp_path);workspace.evidence_tracking(True)
    discovery=investigate(spec)  # no explicit workspace keyword
    assert any(f['payload']['kind']=='discovery_selection' for f in workspace.catalog.iter_facts('evidence_use'))
    family=freeze_hypotheses(discovery,confirmation=declared())
    identity=inspect_confirmation(family)['independence']
    assert identity['local_identity_scope']=='canonical_history_keys_and_retained_original_aliases'
    assert identity['local_separation']=='system_checked'
    assessed=confirm_investigation(family)
    assert assessed.private['evidence_workspace_path']==str(workspace.path)
    assert any(f['payload']['kind']=='confirmation' for f in workspace.catalog.iter_facts('evidence_use'))
    changed=freeze_hypotheses(discovery,confirmation=declared(),practical_thresholds={c:.2 for c in discovery.data['investigation']['shortlist']})
    assert 'previously_exposed_confirmation_population' in inspect_confirmation(changed)['admissibility_reasons']
    other=ReliabilityWorkspace.initialize(tmp_path/'other',WorkspaceConfig(saving=True,free_disk_bytes=1))
    with pytest.raises(EvaluationError) as redirect:inspect_confirmation(family,workspace=other)
    assert redirect.value.code=='workspace_identity'
