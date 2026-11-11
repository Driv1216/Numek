"""Each synthetic story models a new process; within-story exposure is preserved."""
import pytest
@pytest.fixture(autouse=True)
def isolated_process_ledger(monkeypatch):
    from confidenceguard import evidence_use
    monkeypatch.setattr(evidence_use,'_SESSION_USES',[])
