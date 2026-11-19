"""Scoped study authority: a confirmation's worker reads see the reserve units that study consumed, nothing more.

Access reservations (``selection_access``) record no exposure. With an
``authority`` (a confirmation-class reservation) they admit only the sealed
reserve units in that reservation's own membership that its study family spent,
and never beyond its snapshot. Everything else stays withheld or refused.
"""
import pytest

from helpers import lease_for
from numek_platform.errors import PlatformError
from numek_platform.execution.controller import Controller
from numek_platform.governance import reader as governed, reserve as reserves
from test_governance import World

LOOK = {'id': 'april', 'as_of': '2026-04-30T00:00:00Z', 'alpha': 0.01}


@pytest.fixture
def world(platform):
    return World(platform)


def _split(world, pairs):
    sealed = sorted(p for p in pairs if p[1] in world.reserve_units())
    assert len(sealed) >= 4
    half = len(sealed) // 2
    return sealed[:half], sealed[half:]


def _confirm(world, members, read_pin, family, **kwargs):
    lease = lease_for(world.platform, kind='confirm')
    return world.reserve(lease, 'confirmation', members, read_pin, family_digest=family, consume_reserve=True, **kwargs)


def _access(world, read_pin, pairs, authority=None, purpose='selection_access'):
    lease = lease_for(world.platform, kind='worker')
    return world.reserve(lease, purpose, pairs, read_pin, authority=authority)


def _outcome_units(world, reservation, read_pin):
    got = governed.resolve(world.platform.db, world.platform.store, reservation, read_pin, kinds=['outcome'])
    return {l.entity_hash for l in got.locators}


def test_worker_inherits_exactly_the_units_its_study_consumed(platform, world):
    read_pin, pairs = world.pairs()
    mine, others = _split(world, pairs)
    study = _confirm(world, mine, read_pin, 'family-A')
    assert study.reserve_consumed_units == len(mine)
    worker = _access(world, read_pin, pairs, authority=study.id)
    seen = _outcome_units(world, worker, read_pin)
    assert {p[1] for p in mine} <= seen                                  # authorized population
    assert not seen & {p[1] for p in others}                             # population boundary
    assert worker.withheld_reserve_units == len(others)
    plain = _access(world, read_pin, pairs)                              # same read without authority
    assert not _outcome_units(world, plain, read_pin) & {p[1] for p in mine + others}
    with platform.db.connect() as conn:                                  # access is not exposure accounting
        kinds = {r['kind'] for r in conn.execute(
            'SELECT u.kind FROM exposure_registry r JOIN evidence_uses u ON u.catalog_id = r.catalog_id '
            'AND u.id = r.last_use_id WHERE r.catalog_id = %s', (platform.catalog_id,))}
        assert 'access' not in kinds
        meta = conn.execute('SELECT metadata FROM evidence_uses WHERE id = %s', (worker.id,)).fetchone()['metadata']
        assert meta['authority_use_id'] == study.id


def test_unrelated_studies_and_other_purposes_cannot_use_another_studys_units(platform, world):
    read_pin, pairs = world.pairs()
    mine, others = _split(world, pairs)
    study_a = _confirm(world, mine, read_pin, 'family-A')
    study_b = _confirm(world, others, read_pin, 'family-B')
    seen_b = _outcome_units(world, _access(world, read_pin, pairs, authority=study_b.id), read_pin)
    assert not seen_b & {p[1] for p in mine} and {p[1] for p in others} <= seen_b
    with pytest.raises(PlatformError) as caught:                         # another family cannot consume them
        _confirm(world, mine, read_pin, 'family-C')
    assert caught.value.code in ('confirmation_population_exposed', 'reserve_access_refused')
    for purpose in ('monitoring_outcome', 'outcome_disclosure', 'discovery_selection', 'confirmation'):
        with pytest.raises(PlatformError) as caught:                     # authority is access-only
            _access(world, read_pin, pairs, authority=study_a.id, purpose=purpose)
        assert caught.value.code == 'authority_scope'
    monitoring = _access(world, read_pin, pairs, purpose='monitoring_outcome')
    assert not _outcome_units(world, monitoring, read_pin) & {p[1] for p in mine}
    with pytest.raises(PlatformError) as caught:                         # development roles still refuse
        _access(world, read_pin, pairs, purpose='discovery_selection')
    assert caught.value.code == 'reserve_access_refused'
    disclosure = _access(world, read_pin, pairs, purpose='outcome_disclosure')
    with pytest.raises(PlatformError) as caught:                         # only confirmation-class uses grant
        _access(world, read_pin, pairs, authority=disclosure.id)
    assert caught.value.code == 'authority_scope'
    access = _access(world, read_pin, pairs)
    with pytest.raises(PlatformError) as caught:                         # an access read never grants
        _access(world, read_pin, pairs, authority=access.id)
    assert caught.value.code == 'authority_scope'


def test_authority_never_reaches_beyond_the_studys_snapshot(platform, world):
    read_pin, pairs = world.pairs()
    mine, _ = _split(world, pairs)
    study = _confirm(world, mine, read_pin, 'family-A')
    world.publish(['late-entity'], tag='late')
    later_pin, later_pairs = world.pairs()
    assert later_pin.k > read_pin.k
    with pytest.raises(PlatformError) as caught:
        _access(world, later_pin, later_pairs, authority=study.id)
    assert caught.value.code == 'authority_snapshot'
    _access(world, read_pin, pairs, authority=study.id)                  # within the snapshot: admitted


def test_retries_and_scheduled_looks_keep_the_original_authorization(platform, world):
    read_pin, pairs = world.pairs()
    mine, _ = _split(world, pairs)
    initial = _confirm(world, mine, read_pin, 'family-A', request_id='initial', study_id='study-A', alpha=0.04,
                       total_alpha=0.05, metadata={'restatement_schedule': [LOOK]})
    retried = _confirm(world, mine, read_pin, 'family-A', request_id='initial', study_id='study-A', alpha=0.04,
                       total_alpha=0.05, metadata={'restatement_schedule': [LOOK]})
    assert retried.reused and retried.id == initial.id
    reused = _confirm(world, mine, read_pin, 'family-A', request_id='other-attempt', study_id='study-A', alpha=0.04,
                      total_alpha=0.05, metadata={'restatement_schedule': [LOOK]})
    assert reused.reused and reused.id == initial.id                     # same family and population
    look = _confirm(world, mine, read_pin, 'family-A', request_id='look', study_id='study-A', alpha=0.01,
                    total_alpha=0.05, population_digest='look-snapshot',
                    metadata={'predeclared_look': LOOK, 'look_id': 'april', 'initial_use_id': initial.id})
    assert not look.reused and look.id != initial.id                    # spent by its own family: allowed
    for authority in (initial.id, look.id):
        assert {p[1] for p in mine} <= _outcome_units(world, _access(world, read_pin, pairs, authority=authority),
                                                       read_pin)
    status = reserves.status(platform.db, platform.scope, world.reserve_id)
    assert status['spent'] == len(mine)                                  # the look spent nothing new


def test_interrupted_study_keeps_its_units_spent_and_retry_keeps_access(platform, world):
    read_pin, pairs = world.pairs()
    mine, _ = _split(world, pairs)
    lease = lease_for(platform, kind='confirm')
    study = world.reserve(lease, 'confirmation', mine, read_pin, family_digest='family-A', consume_reserve=True,
                          request_id='interrupted')
    worker_lease = lease_for(platform, kind='worker')
    worker = world.reserve(worker_lease, 'selection_access', pairs, read_pin, authority=study.id)
    with platform.db.transaction() as conn:                              # both attempts die
        conn.execute("UPDATE jobs SET lease_expires_at = now() - interval '1 second' WHERE id = ANY(%s)",
                     ([lease.job_id, worker_lease.job_id],))
    Controller(platform.db).run_once()
    with pytest.raises(PlatformError) as caught:
        governed.resolve(platform.db, platform.store, worker, read_pin, kinds=['outcome'])
    assert caught.value.code == 'reservation_owner'                      # the dead worker lost access
    with platform.db.connect() as conn:
        assert conn.execute('SELECT state FROM evidence_uses WHERE id = %s', (study.id,)).fetchone()['state'] == 'reserved'
    status = reserves.status(platform.db, platform.scope, world.reserve_id)
    assert status['spent'] == len(mine)                                  # freshness is not restored
    with pytest.raises(PlatformError):
        _confirm(world, mine, read_pin, 'family-B')
    again = _confirm(world, mine, read_pin, 'family-A', request_id='interrupted')
    assert again.reused and again.id == study.id                         # the retry resumes the same study
    assert {p[1] for p in mine} <= _outcome_units(world, _access(world, read_pin, pairs, authority=again.id), read_pin)


# ConfidenceGuard worker plumbing ------------------------------------------------------------------

def _cg_workspace(platform, monkeypatch, tmp_path):
    from pathlib import Path
    from test_cg3_on_platform import _cg3_helpers
    monkeypatch.setenv('NUMEK_PLATFORM_DSN', platform.db.dsn)
    helpers = _cg3_helpers()
    tmp_path = Path(tmp_path).resolve()
    ws = helpers.workspace(tmp_path)
    ws.ingest(helpers.batch(tmp_path))
    return helpers, ws, tmp_path


def _ingest_more(helpers, ws, tmp_path):
    from pathlib import Path
    extra = helpers.batch(tmp_path, 'more', count=14)
    path = Path(extra['evaluation']['sources'][0]['path'])
    rows = path.read_text().splitlines()
    path.write_text('\n'.join([rows[0]] + [','.join([str(100 + int(r.split(',')[0]))] + r.split(',')[1:])
                                           for r in rows[1:]]) + '\n')
    ws.ingest(extra)


def test_worker_reads_inherit_study_authority_only_within_its_scope(platform, monkeypatch, tmp_path):
    from confidenceguard import EvaluationError
    from confidenceguard.evidence_use import EvidenceUseLedger
    from confidenceguard.history_storage import Catalog
    from confidenceguard.platform_catalog import _WORKER_GOVERNANCE, study_authority
    helpers, ws, tmp_path = _cg_workspace(platform, monkeypatch, tmp_path)
    ws.evidence_tracking(True)
    hexes = [f'{i:064x}' for i in range(1, 4)]
    study = EvidenceUseLedger(ws).record('confirmation', events=hexes, units=hexes, population_digest='p',
                                         family_digest='family-A', study_id='s', alpha=0.05, total_alpha=0.05)
    disclosure = EvidenceUseLedger(ws).record('outcome_disclosure', events=hexes, units=hexes, population_digest='q')
    k = ws.status()['catalog_sequence']
    root = str(ws.catalog.root)
    try:
        with study_authority(study):
            worker = Catalog(ws.path).ensure_governance(namespace='events', k=k, purpose_label='historical_selection')
        assert worker.governance['auto'] and worker.governance['authority'] == study['evidence_use_id']
        with platform.db.connect() as conn:
            row = conn.execute('SELECT kind, metadata FROM evidence_uses WHERE id = %s',
                               (worker.governance['reservation']['id'],)).fetchone()
            exposed = conn.execute('SELECT count(*) AS n FROM exposure_registry WHERE last_use_id = %s',
                                   (worker.governance['reservation']['id'],)).fetchone()['n']
        assert row['kind'] == 'access' and row['metadata']['authority_use_id'] == study['evidence_use_id']
        assert exposed == 0                                              # access is never exposure accounting
        assert list(worker.iter_facts('outcome'))                       # governed outcome read works
        _WORKER_GOVERNANCE.pop(root, None)
        with study_authority(disclosure):                                # a disclosure receipt confers nothing
            plain = Catalog(ws.path).ensure_governance(namespace='events', k=k, purpose_label='historical_selection')
        assert plain.governance['authority'] is None
        _WORKER_GOVERNANCE.pop(root, None)
        forged = {**disclosure, 'evidence_kind': 'confirmation'}         # and the ledger refuses a mislabelled one
        with study_authority(forged), pytest.raises(EvaluationError) as caught:
            Catalog(ws.path).ensure_governance(namespace='events', k=k, purpose_label='historical_selection')
        assert caught.value.code == 'authority_scope'                    # only confirmation-class uses grant
        _ingest_more(helpers, ws, tmp_path)                              # K advances past the study snapshot
        _WORKER_GOVERNANCE.pop(root, None)
        with study_authority(study), pytest.raises(EvaluationError) as caught:
            Catalog(ws.path).ensure_governance(namespace='events', k=k + 1, purpose_label='historical_selection')
        assert caught.value.code == 'authority_snapshot'
    finally:
        _WORKER_GOVERNANCE.pop(root, None)


def test_handed_in_reservations_are_never_widened_to_a_later_snapshot(platform, monkeypatch, tmp_path):
    from confidenceguard import EvaluationError
    from confidenceguard.history_storage import Catalog
    helpers, ws, tmp_path = _cg_workspace(platform, monkeypatch, tmp_path)
    k = ws.status()['catalog_sequence']
    lease, governance = ws.catalog.reserve_history(namespace='events', k=k, purpose_label='historical_analysis')
    try:
        _ingest_more(helpers, ws, tmp_path)
        frozen = Catalog(ws.path).governed(governance)
        assert len(list(frozen.iter_facts('prediction', sequence=k))) == 12   # within the frozen snapshot
        for kind in ('prediction', 'outcome', None):                    # no plain-reader fallback, no renewal
            with pytest.raises(EvaluationError) as caught:
                list(frozen.iter_facts(kind))
            assert caught.value.code == 'reservation_snapshot'
        assert frozen.governance is governance
    finally:
        ws.catalog.finish_attempt(lease)
