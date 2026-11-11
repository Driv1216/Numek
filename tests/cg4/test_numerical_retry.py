from dataclasses import replace
import pytest
from confidenceguard import investigate,freeze_hypotheses,confirm_investigation,retry_confirmation,ConfirmationSpec,EvaluationError
from .helpers import binary


@pytest.mark.parametrize('durable',[False,True])
def test_replication_increase_cannot_rescue_unqualified_ranking_confirmation(tmp_path,durable):
    spec=binary(tmp_path)
    # Non-degenerate bounded-rate contributions; keep their independent units.
    path=tmp_path/'predictions.csv'
    import csv,numpy as np
    with path.open() as stream:values=list(csv.DictReader(stream))
    rng=np.random.default_rng(44)
    for row in values:
        if rng.random()<.1:row['decision']=str(1-int(row['decision']))
        row['p']=str(float(rng.uniform(.7,.95) if row['decision']=='1' else rng.uniform(.05,.3)))
    with path.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=values[0]);writer.writeheader();writer.writerows(values)
    # The kernel remains reproducible, but its limited synthetic qualification
    # cannot be extended to general product populations by increasing B.
    spec=replace(spec,objectives=(replace(spec.objectives[0],metric='roc_auc',direction='lower'),))
    workspace=None
    if durable:
        from confidenceguard import ReliabilityWorkspace,WorkspaceConfig
        workspace=ReliabilityWorkspace.initialize(tmp_path/'workspace',WorkspaceConfig(saving=True,free_disk_bytes=1))
        workspace.evidence_tracking(True)
    result=workspace.investigate(spec) if workspace else investigate(spec)
    protocol=ConfirmationSpec(method='percentile',replicates=100,replicate_policy='fixed',max_replicates=10000,
        upstream_independence='declared_independent',external_exposure='declared_unexposed',declaration_author='fixture',declaration_reason='Independent synthetic rows and isolated population.')
    frozen=freeze_hypotheses(result,[result.data['investigation']['shortlist'][0]],confirmation=protocol)
    prior=workspace.confirm_investigation(frozen) if workspace else confirm_investigation(frozen)
    row=prior.data['investigation']['assessments'][0]
    assert row['state']=='statistically_inadmissible' and not row['H_outcomes_disclosed']
    assert row['reason']=='general_ranking_percentile_confirmation_not_qualified'
    original=frozen.to_dict()
    with pytest.raises(EvaluationError) as refused:
        if workspace:workspace.retry_confirmation(prior.data['analysis_id'],replicates=1000)
        else:retry_confirmation(prior,replicates=1000)
    assert refused.value.code=='numerical_retry_not_eligible'
    assert frozen.to_dict()==original


def test_finite_or_statistical_failures_are_not_numerical_retry_requests(tmp_path):
    result=investigate(binary(tmp_path));frozen=freeze_hypotheses(result)
    prior=confirm_investigation(frozen)
    with pytest.raises(EvaluationError) as caught:retry_confirmation(prior,replicates=100000)
    assert caught.value.code=='numerical_retry_not_eligible'
