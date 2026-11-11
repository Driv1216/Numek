from dataclasses import replace
import copy
import pytest
from confidenceguard.contracts import EvaluationError,digest
from confidenceguard.investigation import investigate,freeze_hypotheses
from confidenceguard.investigation_contracts import ConfirmationSpec,FrozenHypothesisSet
from confidenceguard.confirmation import inspect_confirmation,confirm_investigation
from .helpers import binary


def test_confirmation_fingerprint_includes_current_exposure_admission(tmp_path):
    from confidenceguard import ReliabilityWorkspace,WorkspaceConfig,inspect_confirmation,confirm_investigation,freeze_hypotheses,ConfirmationSpec
    from confidenceguard.evidence_use import EvidenceUseLedger
    spec=binary(tmp_path);ws=ReliabilityWorkspace.initialize(tmp_path/'workspace',WorkspaceConfig(saving=True,free_disk_bytes=1));ws.evidence_tracking(True)
    result=ws.investigate(spec)
    frozen=freeze_hypotheses(result,confirmation=ConfirmationSpec(upstream_independence='declared_independent',external_exposure='declared_unexposed',declaration_author='fixture',declaration_reason='Independent synthetic rows in an isolated namespace.'))
    inspection=inspect_confirmation(frozen,workspace=ws,_protected=True)
    assert inspection['independence']['ledger_enabled']
    EvidenceUseLedger(ws).record('outcome_disclosure',**inspection['_protected_population'])
    with pytest.raises(EvaluationError) as caught:confirm_investigation(frozen,workspace=ws,expected_fingerprint=inspection['fingerprint'])
    assert caught.value.code=='stale_confirmation'


def declared():
    return ConfirmationSpec(upstream_independence='declared_independent',external_exposure='declared_unexposed',
                            declaration_author='synthetic fixture',declaration_reason='Independent generated entities; isolated fixture namespace.')


def fixture(tmp_path):
    spec=binary(tmp_path)
    return replace(spec,roles=replace(spec.roles,namespace='fixture-'+tmp_path.name))


def test_frozen_finite_confirmation_and_recomputation(tmp_path):
    result=investigate(fixture(tmp_path));frozen=freeze_hypotheses(result,confirmation=declared())
    preview=inspect_confirmation(frozen)
    assert not preview['H_outcomes_disclosed'] and not preview['admissibility_reasons']
    assert preview['independence']['local_identity_scope']=='live_source_keys_and_available_local_aliases'
    assessed=confirm_investigation(frozen,expected_fingerprint=preview['fingerprint'])
    rows=assessed.data['investigation']['assessments']
    assert rows and any(r['state']=='confirmed' for r in rows)
    assert all(r['interval']['lower']>.1 for r in rows if r['state']=='confirmed')
    again=confirm_investigation(frozen)
    assert [r['interval'] for r in rows]==[r['interval'] for r in again.data['investigation']['assessments']]
    shared=assessed.to_dict()
    assert 'artifacts' not in shared and 'models' not in shared and 'files' not in shared


def test_unknown_independence_and_import_integrity(tmp_path):
    result=investigate(fixture(tmp_path));frozen=freeze_hypotheses(result)
    rows=confirm_investigation(frozen).data['investigation']['assessments']
    assert all(r['state']=='statistically_inadmissible' and not r['H_outcomes_disclosed'] for r in rows)
    packet=frozen.to_dict();packet['family_digest']='0'*64
    packet['content_digest']=digest({k:v for k,v in packet.items() if k!='content_digest'})
    with pytest.raises(EvaluationError,match='family identity'):FrozenHypothesisSet(packet)


def test_changed_original_input_requires_explicit_population(tmp_path):
    spec=fixture(tmp_path);frozen=freeze_hypotheses(investigate(spec),confirmation=declared())
    path=tmp_path/'predictions.csv';path.write_text(path.read_text()+'\n')
    with pytest.raises(EvaluationError) as error:inspect_confirmation(frozen)
    assert error.value.code=='frozen_input_changed'


def test_failed_joint_BCa_profile_refuses_before_H_access(tmp_path):
    result=investigate(fixture(tmp_path));frozen=freeze_hypotheses(result,confirmation=replace(declared(),method='bca'))
    inspection=inspect_confirmation(frozen)
    assert 'joint_BCa_confirmation_qualification_unresolved' in inspection['admissibility_reasons']
    assessment=confirm_investigation(frozen)
    assert all(a['state']=='statistically_inadmissible' and not a['H_outcomes_disclosed'] for a in assessment.data['investigation']['assessments'])
    percentile=freeze_hypotheses(result,confirmation=replace(declared(),method='percentile'))
    refused=confirm_investigation(percentile)
    assert all(a['state']=='statistically_inadmissible' and a['reason']=='percentile_confirmation_registered_for_ranking_only' and not a['H_outcomes_disclosed'] for a in refused.data['investigation']['assessments'])
    finite=freeze_hypotheses(result,confirmation=declared())
    assert not inspect_confirmation(finite)['admissibility_reasons']


def test_declared_temporal_design_and_common_shocks_refuse_before_H_metrics(tmp_path):
    result=investigate(fixture(tmp_path))
    for options in ({'sampling':'unsupported_temporal'},{'known_common_shocks':True},{'sampling':'descriptive'}):
        frozen=freeze_hypotheses(result,confirmation=replace(declared(),**options))
        preview=inspect_confirmation(frozen)
        assert 'unsupported_confirmation_dependence' in preview['admissibility_reasons']
        assert preview['H_outcomes_disclosed'] is False
        assessment=confirm_investigation(frozen)
        rows=assessment.data['investigation']['assessments']
        assert rows and all(row['state']=='statistically_inadmissible' and
            'unsupported_confirmation_dependence' in row['reason'] and
            row['H_outcomes_disclosed'] is False and 'member_metric' not in row for row in rows)


def test_material_effect_thresholds_are_explicit_per_claim_before_H(tmp_path):
    spec=fixture(tmp_path);spec=replace(spec,objectives=(replace(spec.objectives[0],practical_threshold=None),))
    result=investigate(spec);selected=[result.data['investigation']['shortlist'][0]];cid=selected[0]
    with pytest.raises(EvaluationError) as missing:freeze_hypotheses(result,selected)
    assert missing.value.code=='practical_threshold_required'
    frozen=freeze_hypotheses(result,selected,practical_thresholds={cid:.15})
    assert frozen.data['hypotheses'][0]['objective']['practical_threshold']==.15
    assert result.data['investigation']['candidates'][0]['objective']['practical_threshold'] is None
    for invalid in ({cid:None},{cid:-1.},{cid:float('nan')},{'unselected':.1}):
        with pytest.raises(EvaluationError) as error:freeze_hypotheses(result,selected,practical_thresholds=invalid)
        assert error.value.code=='practical_threshold_required'


def test_unqualified_ranking_refuses_before_class_specific_H_support(tmp_path):
    import csv
    spec=fixture(tmp_path);path=tmp_path/'predictions.csv'
    with path.open() as stream:rows=list(csv.DictReader(stream))
    for index,row in enumerate(rows):
        y=int(index%10==0);prediction=y^(row['x']!=row['z'])
        row.update(y=str(y),decision=str(prediction),p='.85' if prediction else '.15')
    with path.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=rows[0]);writer.writeheader();writer.writerows(rows)
    spec=replace(spec,objectives=(replace(spec.objectives[0],metric='roc_auc',direction='lower'),))
    result=investigate(spec);frozen=freeze_hypotheses(result,[result.data['investigation']['shortlist'][0]],confirmation=replace(declared(),method='percentile'))
    row=confirm_investigation(frozen).data['investigation']['assessments'][0]
    assert row['state']=='statistically_inadmissible' and row['reason']=='general_ranking_percentile_confirmation_not_qualified'
    assert not row['H_outcomes_disclosed'] and 'ranking_class_support' not in row['support']
