"""Governance before access: reservations, ported overlap rules, sealed reserves, governed reads."""
import uuid
from decimal import Decimal

import pytest

from helpers import lease_for, publish_records, record
from numek_platform.canonical import digest
from numek_platform.errors import PlatformError
from numek_platform.evidence.maintenance import purge_facts
from numek_platform.evidence.reader import pin, read, resolve
from numek_platform.execution.controller import Controller
from numek_platform.governance import ledger, reader as governed, reserve as reserves
from numek_platform.secrets import FileSecretStore

NS = 'ns'


class World:
    def __init__(self, platform, n=200, *, fraction=Decimal('0.10'), policy='exclude', with_reserve=True):
        self.platform = platform
        self.secrets = FileSecretStore(platform.root / 'secrets')
        self.reserve_id = None
        if with_reserve:
            self.reserve_id = reserves.create_reserve(platform.db, self.secrets, platform.scope, platform.catalog_id, NS,
                                                      actor='test', fraction=fraction, covariate_policy=policy)
        self.entities = [f'customer-{i}' for i in range(n)]
        self.publish(self.entities)

    def publish(self, entities, tag='w'):
        records, events, units, lexical = [], [], [], []
        for entity in entities:
            event = f'{tag}-{entity}'
            e_hash, u_hash = digest([NS, event]), digest([NS, entity])
            for kind, identity, payload in (('opportunity', [NS, event], {'entity': entity}),
                                            ('outcome', [NS, event, 'v1', 'default'], {'value': 1})):
                records.append(record(kind, identity, payload))
                events.append(e_hash)
                units.append(u_hash)
            lexical.append((u_hash, entity))

        def register(conn, _publication_id, k):
            reserves.register_entities(conn, self.secrets, self.platform.scope, self.platform.catalog_id, NS, lexical, k)

        return publish_records(self.platform, records, event_hashes=events, entity_hashes=units, exposure_lock=True,
                               after_head=register)[0]

    def reserve_units(self):
        with self.platform.db.connect() as conn:
            return {bytes(r['unit_hash']).hex() for r in conn.execute(
                "SELECT unit_hash FROM entity_registry WHERE catalog_id = %s AND reserve_state = 'reserve'",
                (self.platform.catalog_id,))}

    def pairs(self, lease=None):
        read_pin = pin(self.platform.db, self.platform.scope, self.platform.catalog_id,
                       **({'lease': lease} if lease else {'holder': 'test'}))
        return read_pin, governed.membership_from_index(self.platform.db, read_pin)

    def reserve(self, lease, purpose, members, read_pin, **kwargs):
        return ledger.reserve(self.platform.db, self.platform.store, self.platform.scope, lease, self.platform.catalog_id,
                              purpose=purpose, members=members, read_k=read_pin.k,
                              population_digest=kwargs.pop('population_digest', digest(sorted(members))), **kwargs)


@pytest.fixture
def world(platform):
    return World(platform)


def test_plain_reads_never_expose_outcomes_or_reserve_rows(platform, world):
    read_pin = pin(platform.db, platform.scope, platform.catalog_id, holder='t')
    with pytest.raises(PlatformError) as caught:
        resolve(platform.db, read_pin, kinds=['outcome'])
    assert caught.value.code == 'reservation_required'
    visible = resolve(platform.db, read_pin, kinds=['opportunity'])
    assert len(visible) == 200 - len(world.reserve_units())
    assert all(l.entity_hash not in world.reserve_units() for l in visible)
    assert all(l.kind != 'outcome' for l in resolve(platform.db, read_pin))


def test_reservation_precedes_access_and_is_consumed_with_the_result(platform, world):
    lease = lease_for(platform, kind='monitoring')
    read_pin, pairs = world.pairs(lease)
    res = world.reserve(lease, 'monitoring_outcome', pairs, read_pin)
    assert res.withheld_reserve_units == len(world.reserve_units()) > 0
    result = governed.resolve(platform.db, platform.store, res, read_pin, kinds=['outcome'])
    outcomes = [r for _, r in read(platform.store, result.locators)]
    assert len(outcomes) == 200 - len(world.reserve_units()) and result.withheld == len(world.reserve_units())
    receipt = publish_records(platform, [record('context', [NS, 'window-measurement'], {'n': len(outcomes)})],
                              lease=lease, reservations=[res])[0]
    assert receipt.new_facts == 1
    with platform.db.connect() as conn:
        assert conn.execute('SELECT state FROM evidence_uses WHERE id = %s', (res.id,)).fetchone()['state'] == 'consumed'


def test_crashed_attempt_keeps_exposure_and_loses_access(platform, world):
    lease = lease_for(platform, kind='monitoring')
    read_pin, pairs = world.pairs(lease)
    res = world.reserve(lease, 'monitoring_outcome', pairs, read_pin)
    with platform.db.transaction() as conn:
        conn.execute("UPDATE jobs SET lease_expires_at = now() - interval '1 second' WHERE id = %s", (lease.job_id,))
    Controller(platform.db).run_once()
    with pytest.raises(PlatformError) as caught:
        governed.resolve(platform.db, platform.store, res, read_pin, kinds=['outcome'])
    assert caught.value.code == 'reservation_owner'
    with platform.db.connect() as conn:
        assert conn.execute('SELECT state FROM evidence_uses WHERE id = %s', (res.id,)).fetchone()['state'] == 'reserved'
        exposed = conn.execute("SELECT count(*) AS n FROM exposure_registry WHERE catalog_id = %s AND outcome_exposed "
                               "AND member_kind = 'unit'", (platform.catalog_id,)).fetchone()['n']
    assert exposed == 200 - len(world.reserve_units())


def test_monitoring_exposure_blocks_confirmation_but_the_reserve_stays_fresh(platform, world):
    lease = lease_for(platform, kind='monitoring')
    read_pin, pairs = world.pairs(lease)
    world.reserve(lease, 'monitoring_outcome', pairs, read_pin)
    reserve_units = world.reserve_units()
    ordinary = [p for p in pairs if p[1] not in reserve_units][:20]
    sealed = [p for p in pairs if p[1] in reserve_units]
    study = lease_for(platform, kind='confirm')
    with pytest.raises(PlatformError) as caught:
        world.reserve(study, 'confirmation', ordinary, read_pin, family_digest='family-A')
    assert caught.value.code == 'confirmation_population_exposed'
    with pytest.raises(PlatformError) as caught:
        world.reserve(study, 'confirmation', sealed, read_pin, family_digest='family-A')
    assert caught.value.code == 'reserve_access_refused'          # consumption must be explicit
    first = world.reserve(study, 'confirmation', sealed, read_pin, family_digest='family-A', consume_reserve=True)
    assert first.reserve_consumed_units == len(sealed)
    got = governed.resolve(platform.db, platform.store, first, read_pin, kinds=['outcome'])
    assert len(got.locators) == len(sealed)
    status = reserves.status(platform.db, platform.scope, world.reserve_id)
    assert status['spent'] == len(sealed) and status['fresh_reserve'] == 0
    retry = lease_for(platform, kind='confirm-retry')
    again = world.reserve(retry, 'confirmation', sealed, read_pin, family_digest='family-A', consume_reserve=True)
    assert again.reused and again.id == first.id                   # same family and population: ported reuse
    other = lease_for(platform, kind='confirm-other')
    with pytest.raises(PlatformError):
        world.reserve(other, 'confirmation', sealed, read_pin, family_digest='family-B', consume_reserve=True)


def test_development_roles_refuse_reserve_entities(platform, world):
    lease = lease_for(platform, kind='fit')
    read_pin, pairs = world.pairs(lease)
    with pytest.raises(PlatformError) as caught:
        world.reserve(lease, 'fit_F', pairs, read_pin)
    assert caught.value.code == 'reserve_access_refused'
    ordinary = [p for p in pairs if p[1] not in world.reserve_units()]
    res = world.reserve(lease, 'fit_F', ordinary, read_pin)
    with platform.db.connect() as conn:
        flags = conn.execute("SELECT bool_and(development_use) AS d, bool_and(outcome_exposed) AS o FROM exposure_registry "
                             "WHERE catalog_id = %s AND last_use_id = %s", (platform.catalog_id, res.id)).fetchone()
    assert flags['d'] and flags['o']


@pytest.mark.parametrize('policy', ['exclude', 'inspect'])
def test_covariate_policy_governs_reserve_inputs(platform, policy):
    world = World(platform, policy=policy)
    lease = lease_for(platform, kind='inspect')
    read_pin, pairs = world.pairs(lease)
    res = world.reserve(lease, 'covariate_inspection', pairs, read_pin)
    rows = governed.resolve(platform.db, platform.store, res, read_pin, kinds=['opportunity']).locators
    outcomes = governed.resolve(platform.db, platform.store, res, read_pin, kinds=['outcome']).locators
    assert outcomes == []                                           # covariate reservations never open outcomes
    if policy == 'exclude':
        assert res.withheld_reserve_units == len(world.reserve_units()) and len(rows) == 200 - len(world.reserve_units())
    else:
        assert res.withheld_reserve_units == 0 and len(rows) == 200


def test_reserve_assignment_is_stable_versioned_and_starts_after_creation(platform):
    secrets = FileSecretStore(platform.root / 'secrets')
    before = World(platform, n=50, with_reserve=False)
    with platform.db.connect() as conn:
        assert {r['reserve_state'] for r in conn.execute('SELECT reserve_state FROM entity_registry')} == {'pre_reserve'}
    reserve_id = reserves.create_reserve(platform.db, secrets, platform.scope, platform.catalog_id, NS, actor='test')
    before.secrets = secrets
    before.publish([f'new-{i}' for i in range(2000)], tag='n')
    counts = reserves.status(platform.db, platform.scope, reserve_id)['counts']
    assert counts['pre_reserve'] == 50 and 140 <= counts['reserve'] <= 260      # 10% of 2000, ±4.5 sd
    with platform.db.connect() as conn:
        snapshot = {bytes(r['unit_hash']): r['reserve_state'] for r in conn.execute('SELECT * FROM entity_registry')}
    reserves.rotate_secret(platform.db, secrets, platform.scope, reserve_id, actor='test')
    reserves.change_fraction(platform.db, secrets, platform.scope, reserve_id, '0.25', actor='test')
    before.publish([f'new-{i}' for i in range(2000)], tag='again')           # same entities seen again
    with platform.db.connect() as conn:
        after = {bytes(r['unit_hash']): r['reserve_state'] for r in conn.execute('SELECT * FROM entity_registry')}
    assert after == snapshot                                                   # never reassigned
    assert [v['version'] for v in reserves.status(platform.db, platform.scope, reserve_id)['versions']] == [1, 2, 3]


def test_reallocation_refuses_exposed_entities_and_release_keeps_history(platform, world):
    lease = lease_for(platform, kind='monitoring')
    read_pin, pairs = world.pairs(lease)
    exposed_unit = next(u for _, u in pairs if u not in world.reserve_units())
    world.reserve(lease, 'monitoring_outcome', [p for p in pairs if p[1] == exposed_unit], read_pin)
    fresh = world.publish(['fresh-entity'], tag='f')
    assert fresh.new_facts == 2
    fresh_unit = digest([NS, 'fresh-entity'])
    with platform.db.connect() as conn:
        initial = conn.execute('SELECT reserve_state FROM entity_registry WHERE unit_hash = %s',
                               (bytes.fromhex(fresh_unit),)).fetchone()['reserve_state']
    moved, refused = reserves.reallocate_into_reserve(platform.db, platform.scope, world.reserve_id,
                                                      [exposed_unit, fresh_unit], reason='grow reserve', actor='test')
    with platform.db.connect() as conn:
        final = conn.execute('SELECT reserve_state FROM entity_registry WHERE unit_hash = %s',
                             (bytes.fromhex(fresh_unit),)).fetchone()['reserve_state']
    assert exposed_unit in refused and exposed_unit not in moved          # exposure can never be undone
    if initial == 'non_reserve':                                          # unexposed and undeveloped: eligible
        assert moved == [fresh_unit] and final == 'reserve'
    else:                                                                 # randomly assigned to the reserve already
        assert fresh_unit in refused and final == 'reserve'
    some = sorted(world.reserve_units())[:2]
    assert reserves.release(platform.db, platform.scope, world.reserve_id, some, reason='policy change', actor='test') == 2


def test_tracking_and_continuity_gaps_require_current_declarations(platform, world):
    lease = lease_for(platform, kind='confirm')
    read_pin, pairs = world.pairs(lease)
    sealed = [p for p in pairs if p[1] in world.reserve_units()][:5]
    status = ledger.set_tracking(platform.db, platform.scope, platform.catalog_id, False)
    assert status['continuity'] == 'incomplete'
    with pytest.raises(PlatformError) as caught:
        world.reserve(lease, 'confirmation', sealed, read_pin, consume_reserve=True)
    assert caught.value.code == 'exposure_tracking_disabled'
    token = ledger.set_tracking(platform.db, platform.scope, platform.catalog_id, True)['continuity_token']
    with pytest.raises(PlatformError) as caught:
        world.reserve(lease, 'confirmation', sealed, read_pin, consume_reserve=True)
    assert caught.value.code == 'exposure_history_gap_requires_current_declaration'
    res = world.reserve(lease, 'confirmation', sealed, read_pin, consume_reserve=True,
                        metadata={'exposure_history_token': token})
    assert res.reserve_consumed_units == 5


def test_study_error_budget_is_enforced(platform, world):
    read_pin, pairs = world.pairs()
    sealed = sorted(p for p in pairs if p[1] in world.reserve_units())
    first = world.reserve(lease_for(platform), 'confirmation', sealed[:3], read_pin, consume_reserve=True,
                          family_digest='f1', study_id='study', alpha='0.03', total_alpha='0.05')
    assert first.reserve_consumed_units == 3
    with pytest.raises(PlatformError) as caught:
        world.reserve(lease_for(platform), 'confirmation', sealed[3:6], read_pin, consume_reserve=True,
                      family_digest='f2', study_id='study', alpha='0.03', total_alpha='0.05')
    assert caught.value.code == 'study_alpha_exhausted'


def test_exposure_history_survives_purge(platform, world):
    lease = lease_for(platform, kind='monitoring')
    read_pin, pairs = world.pairs(lease)
    ordinary = [p for p in pairs if p[1] not in world.reserve_units()][:5]
    world.reserve(lease, 'monitoring_outcome', ordinary, read_pin)
    with platform.db.connect() as conn:
        outcome_keys = [bytes(r['key']).hex() for r in conn.execute(
            "SELECT key FROM fact_index WHERE catalog_id = %s AND kind = 'outcome' AND event_hash = ANY(%s)",
            (platform.catalog_id, [bytes.fromhex(e) for e, _ in ordinary]))]
    purge_facts(platform.db, platform.scope, lease, platform.catalog_id, [('outcome', k, 'initial') for k in outcome_keys],
                request_id='purge', reason='retention')
    later_pin, _ = world.pairs()
    with pytest.raises(PlatformError) as caught:
        world.reserve(lease_for(platform), 'confirmation', ordinary, later_pin, family_digest='f')
    assert caught.value.code == 'confirmation_population_exposed'


def test_reservation_idempotency_and_ownership(platform, world):
    lease = lease_for(platform, kind='m')
    read_pin, pairs = world.pairs(lease)
    ordinary = [p for p in pairs if p[1] not in world.reserve_units()][:4]
    res = world.reserve(lease, 'monitoring_outcome', ordinary, read_pin, request_id='window-1')
    retry = lease_for(platform, kind='m2')
    rebound = world.reserve(retry, 'monitoring_outcome', ordinary, read_pin, request_id='window-1')
    assert rebound.id == res.id and rebound.fence == retry.fence and rebound.job_id == retry.job_id
    with pytest.raises(PlatformError) as caught:
        world.reserve(retry, 'monitoring_outcome', ordinary[:2], read_pin, request_id='window-1')
    assert caught.value.code == 'idempotency_conflict'
    with pytest.raises(PlatformError) as caught:
        publish_records(platform, [record('context', [NS, 'x'], {})], lease=lease_for(platform), reservations=[rebound])
    assert caught.value.code == 'reservation_owner'
    assert uuid.UUID(str(rebound.catalog_id)) == platform.catalog_id
