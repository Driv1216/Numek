"""S10: facts routed to their opportunity's partition (migration 0014).

Predictions and context are stored in the partition of their opportunity (route = identity[0]); every other kind
in its own key's partition. The tests cover:
- the route of each kind, the partition it lands in, and the database CHECK on the rule;
- duplicates, conflicts and forks still detected for routed kinds;
- a purged identity refused even when its old row routes by key (facts deleted before migration);
- reads by route equal reads by the old opportunity and target filters;
- the capture side: a prediction's opportunity key comes from its identity, never its payload.
"""
import psycopg
import pytest

from helpers import lease_for, publish_records, record
from numek_platform.errors import PlatformError
from numek_platform.evidence.maintenance import purge_facts
from numek_platform.evidence.reader import pin, release, resolve


def _window(n=6):
    """n opportunities with one prediction, one context and one outcome each (CG3 identity shapes)."""
    out = []
    for i in range(n):
        target = ['ns', f'e{i}', 'v1', 't']
        target_key = record('outcome', target, {})['key']
        opp = record('opportunity', [target, 'o'], {'target_key': target_key})
        out.append({'opportunity': opp, 'target_key': target_key,
                    'prediction': record('prediction', [opp['key'], 'variant', 'slot', 'single'], {'p': i}),
                    'context': record('context', [opp['key']], {'values': {'x': i}}),
                    'outcome': record('outcome', target, {'value': i % 2})})
    return out


def _publish_window(platform, window):
    opps = [w['opportunity'] for w in window]
    publish_records(platform, opps, opportunity_keys=[o['key'] for o in opps],
                    target_keys=[w['target_key'] for w in window])
    linked = [w[k] for w in window for k in ('prediction', 'context')]
    publish_records(platform, linked, opportunity_keys=[w['opportunity']['key'] for w in window for _ in (0, 1)])
    outcomes = [w['outcome'] for w in window]
    publish_records(platform, outcomes, target_keys=[o['key'] for o in outcomes])


def test_routed_kinds_share_their_opportunitys_partition(platform):
    window = _window()
    _publish_window(platform, window)
    with platform.db.connect() as conn:
        rows = {(r['kind'], bytes(r['key']).hex()): r for r in conn.execute(
            'SELECT kind, key, route, opportunity_key, tableoid::regclass::text AS part FROM fact_index '
            'WHERE catalog_id = %s', (platform.catalog_id,)).fetchall()}
    for w in window:
        opp = rows[('opportunity', w['opportunity']['key'])]
        assert bytes(opp['route']).hex() == w['opportunity']['key']
        for kind in ('prediction', 'context'):
            row = rows[(kind, w[kind]['key'])]
            assert bytes(row['route']).hex() == w['opportunity']['key'] and row['part'] == opp['part']
        outcome = rows[('outcome', w['outcome']['key'])]
        assert bytes(outcome['route']).hex() == w['outcome']['key'] == w['target_key']
    # The database refuses any other route for a fact.
    with platform.db.connect() as conn, pytest.raises(psycopg.errors.CheckViolation):
        conn.execute("UPDATE fact_index SET route = key WHERE catalog_id = %s AND kind = 'prediction'", (platform.catalog_id,))


def test_duplicates_conflicts_and_forks_hold_for_routed_kinds(platform):
    window = _window(2)
    _publish_window(platform, window)
    opp_key = window[0]['opportunity']['key']
    prediction = window[0]['prediction']
    again, _, _ = publish_records(platform, [prediction], opportunity_keys=[opp_key])
    assert (again.new_facts, again.duplicate_occurrences) == (0, 1)
    changed = record('prediction', [opp_key, 'variant', 'slot', 'single'], {'p': 99})       # same identity+revision
    with pytest.raises(PlatformError) as caught:
        publish_records(platform, [changed], opportunity_keys=[opp_key])
    assert caught.value.code == 'fact_conflict'
    corrected = record('prediction', [opp_key, 'variant', 'slot', 'single'], {'p': 1}, revision='r2',
                       predecessor=prediction['fact_digest'])
    assert publish_records(platform, [corrected], opportunity_keys=[opp_key])[0].new_facts == 1
    fork = record('prediction', [opp_key, 'variant', 'slot', 'single'], {'p': 2}, revision='r3',
                  predecessor=prediction['fact_digest'])
    with pytest.raises(PlatformError) as caught:
        publish_records(platform, [fork], opportunity_keys=[opp_key])
    assert caught.value.code == 'correction_fork'


def test_purged_identity_is_refused_whatever_its_old_route(platform):
    # A fact whose bytes were deleted before migration 0014 has no opportunity key and routes by its own key.
    window = _window(1)
    opp_key = window[0]['opportunity']['key']
    prediction = window[0]['prediction']
    _, _, lease = publish_records(platform, [prediction])                                  # routed by key
    purge_facts(platform.db, platform.scope, lease, platform.catalog_id, [('prediction', prediction['key'], 'initial')],
                request_id='purge-routing', reason='subject request')
    with pytest.raises(PlatformError) as caught:                                          # now routed by opportunity
        publish_records(platform, [prediction], opportunity_keys=[opp_key])
    assert caught.value.code == 'historical_evidence_unavailable'


def test_reads_by_route_equal_the_opportunity_and_target_filters(platform):
    window = _window(8)
    _publish_window(platform, window)
    publish_records(platform, [record('prediction', ['f' * 64, 'v', 's', 'a'], {'other': 1})],
                    opportunity_keys=['f' * 64])                                          # another opportunity's
    chosen = window[:5]
    opp_keys = [w['opportunity']['key'] for w in chosen]
    targets = [w['target_key'] for w in chosen]
    read_pin = pin(platform.db, platform.scope, platform.catalog_id, holder='routing-test')
    try:
        def ids(locators):
            return sorted((l.kind, l.key, l.revision) for l in locators)
        for kind in ('prediction', 'context'):
            old = resolve(platform.db, read_pin, kinds=[kind], opportunity_keys=opp_keys, access='maintenance')
            new = resolve(platform.db, read_pin, kinds=[kind], routes=opp_keys + opp_keys[:2], access='maintenance')
            assert ids(new) == ids(old) and len(old) == 5
        old = resolve(platform.db, read_pin, kinds=['opportunity'], keys=opp_keys, access='maintenance')
        assert ids(resolve(platform.db, read_pin, kinds=['opportunity'], routes=opp_keys, access='maintenance')) == ids(old)
        old = resolve(platform.db, read_pin, kinds=['outcome'], target_keys=targets, access='maintenance')
        assert ids(resolve(platform.db, read_pin, kinds=['outcome'], routes=targets, access='maintenance')) == ids(old)
        assert len(old) == 5
        assert resolve(platform.db, read_pin, kinds=['prediction'], routes=opp_keys, access='maintenance', _count=True) == 5
    finally:
        release(platform.db, read_pin)


def test_capture_takes_the_prediction_opportunity_from_its_identity():
    from numek_platform.evidence.publish import FactRow
    from confidenceguard.contracts import EvaluationError
    from confidenceguard.platform_catalog import PlatformCatalog, identity_route
    opp_key = 'a' * 64
    fact = record('prediction', [opp_key, 'v', 's', 'single'], {'namespace': 'ns', 'opportunity_key': opp_key})
    entry = {'kind': 'prediction', 'key': fact['key'], 'revision': 'initial'}
    row = PlatformCatalog._row(None, FactRow, entry, fact, fact['fact_digest'], None, 'byte_range', 0, 1, {})
    assert row.opportunity_key == opp_key == identity_route('prediction', fact['key'], fact['identity'])
    assert identity_route('context', 'c' * 64, [opp_key]) == opp_key
    assert identity_route('outcome', 'd' * 64, ['ns', 'e', 'v', 't']) == 'd' * 64
    assert identity_route('prediction', 'e' * 64, ['not-a-key', 'v']) == 'e' * 64
    tampered = record('prediction', [opp_key, 'v', 's', 'single'], {'namespace': 'ns', 'opportunity_key': 'b' * 64})
    with pytest.raises(EvaluationError) as caught:
        PlatformCatalog._row(None, FactRow, entry, tampered, tampered['fact_digest'], None, 'byte_range', 0, 1, {})
    assert caught.value.code == 'capture_changed'
