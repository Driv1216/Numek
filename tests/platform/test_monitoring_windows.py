"""CG7 S5b closure gate (plan M.1, H.2): window-pruned selection equals full-history selection restricted to
the window.

The history deliberately contains:
- event-time corrections that move opportunities forward and backward between windows;
- outcome revisions that are late, out of order, withdrawn and chronologically inconsistent;
- outcomes that arrive before their predictions;
- malformed event clocks;
- retry attempts;
- repeated entities;
- two catalog snapshots and two maturity policies.

For every window, the pruned and full selections must agree exactly on the selected rows, the
selected-fact digest, every measurement and the window coverage. The only excluded field is the
whole-history ``unlocated_opportunities`` count.
"""
import csv
import json

import pytest

from confidenceguard import LongitudinalSpec, ReliabilityWorkspace
from confidenceguard.history_contracts import WorkspaceConfig
from confidenceguard.operations.monitoring import windows

NS = 'events'
WINDOWS = [{'id': 'jan', 'start': '2026-01-01T00:00:00Z', 'end': '2026-02-01T00:00:00Z'},
           {'id': 'feb', 'start': '2026-02-01T00:00:00Z', 'end': '2026-03-01T00:00:00Z'},
           {'id': 'mar', 'start': '2026-03-01T00:00:00Z', 'end': '2026-04-01T00:00:00Z'}]
TICK = lambda iso: int(__import__('datetime').datetime.fromisoformat(iso.replace('Z', '+00:00')).timestamp()) * 10**9


def _write(path, fields, records):
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        writer.writerows(records)


def _batch(path, *, attempt_column=False):
    evaluation = {'task': {'kind': 'binary_classification', 'outcome_definition': 'Observed event', 'classes': ['0', '1'],
                           'positive_class': '1'},
                  'sources': [{'id': 'p', 'path': str(path)}],
                  'runs': [{'id': 'base', 'source': 'p', 'model': {'id': 'risk', 'version': '1'}, 'key_columns': ['id'],
                            'entity_columns': ['entity'], 'prediction_at': {'column': 'when'},
                            'probabilities': {'positive_column': 'p'},
                            'decision': {'rule': 'probability_threshold', 'threshold': .5}, 'role': 'production'}],
                  'outcomes': {'source': 'p', 'column': 'y', 'key_columns': ['id'], 'available_at': {'column': 'available'},
                               'due_at': {'column': 'due'}}}
    binding = {'run': 'base', 'features': {'group': 'categorical'}}
    if attempt_column:
        binding['attempt_column'] = 'attempt'
    return {'namespace': NS, 'outcome_definition_version': 'outcome-v1', 'bindings': [binding], 'evaluation': evaluation}


def _rows(ids, *, attempt=None):
    out = []
    for i in ids:
        month = 1 + (i % 3)
        day = 1 + (i * 7) % 27
        when = f'2026-{month:02d}-{day:02d}T{(i * 5) % 24:02d}:00:00Z' if i % 23 != 5 else 'not-a-time'
        row = {'id': str(i), 'entity': f'entity-{i % 17}', 'when': when, 'y': str((i * 3) % 2),
               'p': f'{((i * 37) % 100) / 100:.2f}', 'available': f'2026-{min(month + 1, 4):02d}-{(i % 20) + 1:02d}T00:00:00Z',
               'due': f'2026-{month:02d}-28T00:00:00Z', 'group': 'a' if i % 3 else 'b'}
        if attempt is not None:
            row['attempt'] = attempt
        out.append(row)
    return out


@pytest.fixture(scope='module')
def history(tmp_path_factory):
    root = tmp_path_factory.mktemp('windows')
    ws = ReliabilityWorkspace.initialize(root / 'workspace', WorkspaceConfig(saving=True, free_disk_bytes=1))
    fields = ['id', 'entity', 'when', 'y', 'p', 'available', 'due', 'group']
    # Outcomes before predictions: revisions for 200-205 arrive first.
    early = root / 'early.csv'
    _write(early, ['id', 'y', 'rev', 'ord', 'available', 'status'],
           [{'id': str(i), 'y': str(i % 2), 'rev': 'r1', 'ord': '1', 'available': '2026-02-15T00:00:00Z', 'status': 'observed'}
            for i in range(200, 206)])
    ws.update_outcomes({'source': {'id': 'early', 'path': str(early)}, 'namespace': NS, 'outcome_definition_version': 'outcome-v1',
                        'event_columns': ['id'], 'column': 'y', 'revision_column': 'rev', 'order_column': 'ord',
                        'available_at': {'column': 'available'}, 'status_column': 'status'})
    first = root / 'first.csv'
    _write(first, fields, _rows(range(0, 90)))
    ws.ingest(_batch(first))
    middle_k = ws.status()['catalog_sequence']
    late = root / 'late.csv'
    _write(late, fields, _rows(list(range(90, 120)) + list(range(200, 206))))
    ws.ingest(_batch(late))
    retry = root / 'retry.csv'
    _write(retry, fields + ['attempt'], _rows(range(0, 9), attempt='retry'))
    ws.ingest(_batch(retry, attempt_column=True))
    # Outcome revisions: late, out of order (order 2 available before order 1), withdrawn.
    updates = root / 'updates.csv'
    _write(updates, ['id', 'y', 'rev', 'ord', 'available', 'status'], [
        {'id': '10', 'y': '1', 'rev': 'r1', 'ord': '1', 'available': '2026-04-20T00:00:00Z', 'status': 'observed'},
        {'id': '11', 'y': '0', 'rev': 'r2', 'ord': '2', 'available': '2026-02-02T00:00:00Z', 'status': 'observed'},
        {'id': '11', 'y': '1', 'rev': 'r1', 'ord': '1', 'available': '2026-03-05T00:00:00Z', 'status': 'observed'},
        {'id': '12', 'y': '0', 'rev': 'r1', 'ord': '1', 'available': '2026-02-20T00:00:00Z', 'status': 'withdrawn'},
        {'id': '13', 'y': '1', 'rev': 'r1', 'ord': '1', 'available': '2026-01-15T00:00:00Z', 'status': 'final'}])
    ws.update_outcomes({'source': {'id': 'o', 'path': str(updates)}, 'namespace': NS, 'outcome_definition_version': 'outcome-v1',
                        'event_columns': ['id'], 'column': 'y', 'revision_column': 'rev', 'order_column': 'ord',
                        'available_at': {'column': 'available'}, 'status_column': 'status'})
    # Corrections: move a January opportunity into February, a February one into March, a March one into January.
    opportunities = {f['key']: f for f in ws.catalog.iter_facts('opportunity')}
    by_month = {}
    for fact in opportunities.values():
        tick = fact['payload']['time']['tick']
        if tick is not None:
            by_month.setdefault(__import__('datetime').datetime.fromtimestamp(int(tick) // 10**9, __import__('datetime').timezone.utc).month, []).append(fact)
    moves = [(sorted(by_month[1], key=lambda f: f['key'])[0], TICK('2026-02-11T00:00:00Z'), 'valid'),
             (sorted(by_month[2], key=lambda f: f['key'])[0], TICK('2026-03-12T00:00:00Z'), 'valid'),
             (sorted(by_month[3], key=lambda f: f['key'])[0], TICK('2026-01-20T00:00:00Z'), 'valid')]
    for fact, tick, state in moves:
        ws.correct({'kind': 'opportunity', 'key': fact['key'], 'revision': 'corrected', 'predecessor': fact['fact_digest'],
                    'authority': 'supplied', 'available_at': '2026-03-03T00:00:00Z', 'reason': 'Correct event time',
                    'changes': {'time': {'state': state, 'tick': None if tick is None else str(tick)}}})
    return ws, middle_k, ws.status()['catalog_sequence']


def _spec(ws, window, k, **changes):
    variant = ws.models()[0]['id']
    value = {'namespace': NS, 'variants': [variant], 'as_of': '2026-04-25T00:00:00Z', 'windows': [window],
             'features': {'group': 'categorical'}, 'catalog_sequence': k,
             'cohorts': [{'id': 'population', 'column': 'group', 'categories': ['a', 'b']}]}
    value.update(changes)
    return LongitudinalSpec.from_dict(value)


def _evaluate(ws, spec, k, *, pruned):
    """One governed window evaluation: window-scoped reservation (pruned) or whole-namespace reservation (full)."""
    from confidenceguard.platform_catalog import process_scope
    window = spec.windows[0]
    if pruned:
        lease, governance = windows.reserve_window(ws.catalog, namespace=NS, k=k, ticks=(TICK(window.start), TICK(window.end)))
    else:
        lease, governance = ws.catalog.reserve_history(namespace=NS, k=k, purpose_label='equivalence_reference')
    try:
        with process_scope():
            return windows.evaluate_window(str(ws.path), spec, k, spec.as_of, governance, pruned=pruned)
    finally:
        ws.catalog.finish_attempt(lease)


def _evaluate_full(ws, spec, k):
    return _evaluate(ws, spec, k, pruned=False)


def _normal(value):
    return json.loads(json.dumps(value, sort_keys=True, default=str))


@pytest.mark.parametrize('maturity', ['mature_as_of', 'equal_followup'])
@pytest.mark.parametrize('snapshot', ['middle', 'latest'])
def test_window_pruned_selection_equals_full_history_selection(history, maturity, snapshot):
    ws, middle_k, latest_k = history
    k = middle_k if snapshot == 'middle' else latest_k
    extra = {'maturity': maturity, **({'followup_ns': str(20 * 86400 * 10**9)} if maturity == 'equal_followup' else {})}
    compared = 0
    for window in WINDOWS:
        spec = _spec(ws, window, k, **extra)
        pruned = _evaluate(ws, spec, k, pruned=True)
        full = _evaluate_full(ws, spec, k)
        assert pruned['variants'].keys() == full['variants'].keys()
        for variant, a in pruned['variants'].items():
            b = full['variants'][variant]
            assert a['selected_digest'] == b['selected_digest']
            assert _normal(a['units']) == _normal(b['units'])
            assert _normal(a['measurements']) == _normal(b['measurements'])
            ca, cb = dict(a['coverage']), dict(b['coverage'])
            ca.pop('unlocated_opportunities'), cb.pop('unlocated_opportunities')
            assert _normal(ca) == _normal(cb)
            compared += len(a['units'])
        # Incremental: a window reads only its own opportunities' facts.
        assert pruned['materialization']['materialized_records'] < full['materialization']['materialized_records']
    assert compared > 60


def test_history_exercises_the_hard_cases(history):
    """Guards the gate itself: the fixture must contain what the docstring claims."""
    ws, _middle, k = history
    spec = _spec(ws, WINDOWS[1], k)
    result = _evaluate_full(ws, spec, k)
    coverage = next(iter(result['variants'].values()))['coverage']
    states = coverage['outcome_states']
    assert coverage['ambiguous_predictions'] > 0                                   # retry attempts
    assert coverage['unlocated_opportunities'] > 0                                 # malformed clocks
    assert any(s in states for s in ('outcome_withdrawn', 'inconsistent_revision_chronology', 'immature_outcome'))
    corrected = [f for f in ws.catalog.iter_facts('opportunity') if f['revision'] == 'corrected']
    assert len(corrected) == 3
    for fact in corrected:                                       # each moved opportunity is selected at its new time
        tick = int(fact['payload']['time']['tick'])
        window = next(w for w in WINDOWS if TICK(w['start']) <= tick < TICK(w['end']))
        units = next(iter(_evaluate_full(ws, _spec(ws, window, k), k)['variants'].values()))['units']
        assert [u['history_tick'] for u in units if u['history_opportunity'] == fact['key']] == [tick]


def test_window_reservation_is_window_scoped(history):
    ws, _middle, k = history
    from numek_platform.governance import ledger
    lease, governance = windows.reserve_window(ws.catalog, namespace=NS, k=k,
                                               ticks=(TICK(WINDOWS[0]['start']), TICK(WINDOWS[0]['end'])))
    ws.catalog.finish_attempt(lease)
    whole_lease, whole = ws.catalog.reserve_history(namespace=NS, k=k, purpose_label='comparison', purpose='monitoring_outcome')
    ws.catalog.finish_attempt(whole_lease)
    with ws.catalog.db.connect() as conn:
        rows = {str(r['id']): r for r in conn.execute(
            'SELECT id, purpose, metadata, event_count FROM evidence_uses WHERE id = ANY(%s)',
            ([governance['reservation']['id'], whole['reservation']['id']],)).fetchall()}
    window_row, whole_row = rows[governance['reservation']['id']], rows[whole['reservation']['id']]
    assert window_row['purpose'] == 'monitoring_outcome'
    assert 0 < window_row['event_count'] < whole_row['event_count']


def test_gate_rejects_naive_pruning(history, monkeypatch):
    """Mutation check: loading only the revisions that lie in the window (not complete chains) is wrong,
    because an opportunity corrected out of the window would keep its stale revision; the gate must see it."""
    from confidenceguard.platform_catalog import PlatformCatalog
    ws, _middle, k = history
    window = WINDOWS[0]
    lower, upper = TICK(window['start']), TICK(window['end'])
    original = PlatformCatalog.iter_facts

    def naive(self, kind=None, **kwargs):
        for fact in original(self, kind, **kwargs):
            tick = (fact.get('payload') or {}).get('time', {}).get('tick')
            if kind == 'opportunity' and kwargs.get('keys') is not None and not (tick and lower <= int(tick) < upper):
                continue
            yield fact

    full = _evaluate_full(ws, _spec(ws, window, k), k)
    monkeypatch.setattr(PlatformCatalog, 'iter_facts', naive)
    wrong = _evaluate(ws, _spec(ws, window, k), k, pruned=True)
    variant = next(iter(full['variants']))
    assert wrong['variants'][variant]['selected_digest'] != full['variants'][variant]['selected_digest']
