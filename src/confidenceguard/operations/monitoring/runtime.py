"""The CG7 monitoring cycle: window evaluations, detector advance, estimators, rules and signals (H.4, H.6).

Each confirmed definition has two phases:
- **close**: once a window is closed (by producer watermark or after the allowed lateness), the window
  gets outcome-free measures, drift against the frozen reference, the original estimator records,
  rules, and the outcome-free detectors.
- **maturity**: once its outcomes have matured (window end + maturity horizon + lateness), the window
  gets matured measures, matched estimator accountability, rules, and the outcome detectors.

**One window phase is one transaction.** It holds, in order:
1. the fence;
2. the exposure lock;
3. the packet object;
4. consumption of the window's reservation;
5. the evaluation row;
6. for every detector:
   - a unique segment;
   - a state update guarded by the previous state version and by window contiguity;
7. the admitted units;
8. signals and estimates.

A replay therefore never applies a window twice, never skips one, and never creates a result without
its evidence-use record.

**Late publications.** A window whose facts changed after its evaluation gets a new evaluation
*revision*, which is a new measurement version. The old version is kept. Its new units never enter a
running detector; they are counted as late exclusions.
"""
import time
import uuid

from psycopg.types.json import Jsonb

from ...contracts import EvaluationError, digest
from ...history_contracts import instant
from . import definitions, eprocess, estimators, measures, packets, references, units as unit_rules, windows
from . import context as deployment_context

MAX_WINDOWS_PER_CYCLE = 64
MAX_REVISIONS_PER_CYCLE = 32


def _due(definition, phase, index):
    start, end = windows.window_ticks(definition['start'], definition['window_ns'], index)
    lateness = int(definition['allowed_lateness_ns'])
    if phase == 'close':
        return end + lateness, start, end
    return end + definitions.maturity_ns(definition) + lateness, start, end


def _closed(installation, sources, start, end, definition, now_tick):
    from .. import ingest
    if not sources:
        return now_tick >= end + int(definition['allowed_lateness_ns']), 'assumed_complete_after_lateness'
    standings = [ingest.window_closure(installation, s, start, end, allowed_lateness_ns=int(definition['allowed_lateness_ns']),
                                       now_tick=now_tick) for s in sources]
    if all(s['closed'] for s in standings):
        kinds = {s['standing'] for s in standings}
        return True, 'producer_declared_complete' if kinds == {'producer_declared_complete'} else 'assumed_complete_after_lateness'
    return False, 'open'


def cycle(installation, deployment_id, *, now_tick=None):
    """Advance one deployment's confirmed definition up to ``now``. Returns a summary."""
    now_tick = time.time_ns() if now_tick is None else int(now_tick)
    current = definitions.confirmed(installation, deployment_id)
    if current is None:
        return {'deployment': deployment_id, 'state': 'no_confirmed_definition'}
    ctx = deployment_context.deployment(installation, deployment_id)
    definition = current['spec']
    reference = references.load(installation, current['reference_id'])
    summary = {'deployment': deployment_id, 'version': current['version'], 'evaluated': [], 'revisions': [], 'signals': 0}
    for phase in ('close', 'maturity'):
        last = _last_index(installation, deployment_id, current['version'], phase)
        index = 0 if last is None else last + 1
        done = 0
        while done < MAX_WINDOWS_PER_CYCLE:
            due, start, end = _due(definition, phase, index)
            if due > now_tick:
                break
            closed, closure = _closed(installation, ctx['sources'], start, end, definition, now_tick)
            if phase == 'close' and not closed:
                break
            if phase == 'maturity' and _last_index(installation, deployment_id, current['version'], 'close') is None:
                break
            if phase == 'maturity':
                close_last = _last_index(installation, deployment_id, current['version'], 'close')
                if close_last is None or close_last < index:
                    break
            outcome = evaluate(installation, ctx, current, reference, phase, index, closure=closure,
                               as_of_tick=min(due, now_tick))
            summary['evaluated'].append({'phase': phase, 'window': index, 'units': outcome['units'],
                                         'alarms': outcome['alarms'], 'claims': outcome['claims']})
            summary['signals'] += outcome['signals']
            index += 1
            done += 1
        summary['revisions'] += revise(installation, ctx, current, reference, phase, now_tick)
    from . import health
    summary['health'] = health.record(installation, deployment_id, now_tick=now_tick)
    return summary


def _last_index(installation, deployment_id, version, phase):
    with installation.db.connect() as conn:
        row = conn.execute('SELECT max(window_index) AS m FROM ops_window_evaluations WHERE org_id = %s AND deployment_id = %s '
                           'AND definition_version = %s AND phase = %s',
                           (installation.scope.org_id, deployment_id, version, phase)).fetchone()
    return row['m']


def _select(installation, ctx, definition, reference, phase, index, as_of_tick, *, drift=True):
    """Reserve the window (governance before access), then select and measure it in an isolated phase."""
    from ...execution_context import ctx as run_ctx
    ws = ctx['workspace']
    start, end = windows.window_ticks(definition['start'], definition['window_ns'], index)
    k = ws.catalog.head()                      # the head row only (status() counts every fact: cost grows with history)
    as_of = windows.iso(as_of_tick)
    spec = references.longitudinal_spec(definition, ctx['namespace'], windows.iso(start), windows.iso(end), k, as_of,
                                        window_id=windows.window_id(definition['start'], definition['window_ns'], index))
    purpose = 'monitoring_outcome' if phase == 'close' else 'detector'
    lease, governance = windows.reserve_window(ws.catalog, namespace=ctx['namespace'], k=k, ticks=(start, end), purpose=purpose,
                                               metadata={'deployment': ctx['deployment']['id'], 'phase': phase,
                                                         'window': int(index)})
    try:
        relation = {definition['variant']: references.relation(installation, reference)} if drift and phase == 'close' else None
        result = run_ctx.run(_evaluate_window, (str(ws.path), spec, k, as_of, governance, relation), spec.config).data
    except BaseException:
        ws.catalog.finish_attempt(lease, failed=True)
        raise
    return lease, governance, result, k, as_of, (start, end)


def _evaluate_window(root, spec, k, as_of, governance, relation, progress=None):
    from ...result import Inspection
    return Inspection(windows.evaluate_window(root, spec, k, as_of, governance, reference=relation, progress=progress),
                      {'status': 'completed', 'peak_workspace_bytes': 0})


def _compact(namespace, units, task=None):
    """Packet form of selected units: hashes instead of lexical keys (minimized), plus what detectors read."""
    from .estimators import _implied
    out = []
    for u in units:
        out.append({'event': digest([namespace, u['event_key']]), 'entity': unit_rules.entity_hash(namespace, u).hex(),
                    'tick': u.get('history_tick'), 'state': u.get('state'), 'decision': u.get('decision'), 'y': u.get('y'),
                    'outcome_valid': u.get('outcome_valid'), 'outcome_reason': u.get('outcome_reason'),
                    'brier': u.get('brier'), 'confidence': u.get('confidence'), 'group': u.get('g0'),
                    'regions': u.get('regions') or {},
                    'implied_error': None if task is None else _implied('implied_issued_error', u, task)})
    return out


def evaluate(installation, ctx, current, reference, phase, index, *, closure, as_of_tick):
    definition = current['spec']
    version = current['version']
    deployment_id = ctx['deployment']['id']
    scope = installation.scope
    namespace = ctx['namespace']
    lease, governance, result, k, as_of, (start, end) = _select(installation, ctx, definition, reference, phase, index,
                                                                as_of_tick)
    from ..intelligence import regions as region_rules
    variant = result['variants'].get(definition['variant'])
    selected_units = region_rules.annotate([] if variant is None else variant['units'], definition.get('regions'))
    task = reference['packet']['metadata']['task']
    classes = len(task.get('classes') or [0, 1])
    measure_map = {} if variant is None else measures.flat(variant['measurements'])
    drift = [] if variant is None else variant.get('drift') or []
    secret = references.order_secret(installation, deployment_id)
    with installation.db.connect() as conn:
        detectors = [dict(r) for r in conn.execute(
            'SELECT * FROM ops_detectors WHERE org_id = %s AND deployment_id = %s AND definition_version = %s AND phase = %s '
            'ORDER BY detector_id', (scope.org_id, deployment_id, version, phase)).fetchall()]
    updates, alarms_total, claims_total, signals = [], 0, 0, []
    ref_inclusion = reference['packet']['inclusion'].get('label_availability_rate')
    labelled = sum(1 for u in selected_units if u.get('outcome_valid'))
    horizon = definitions.maturity_ns(definition)
    cutoff = None if variant is None else variant['cutoff']
    elapsed = [u for u in selected_units if u.get('history_tick') is not None and cutoff is not None
               and u['history_tick'] + horizon <= cutoff]
    window_inclusion = labelled / len(elapsed) if elapsed else None
    invalid_rate = (sum(1 for u in selected_units if u.get('outcome_reason') in unit_rules.INVALID_OUTCOME_REASONS)
                    / len(selected_units)) if selected_units else None
    overlap = references.entity_overlap(reference['packet'], namespace, selected_units)
    for det in detectors:
        plan = det['plan']
        if index < plan.get('first_window', 0):
            continue
        comparability = _comparability(definition, reference['packet'], phase, det, window_inclusion, invalid_rate, overlap)
        shifted = comparability['shifted']
        seen_entities, seen_events = _seen(installation, deployment_id, version, det['detector_id'], namespace, selected_units)
        values, entities, events, excluded = unit_rules.stream(
            selected_units, statistic=plan['statistic'], design=definition['unit_design'], namespace=namespace,
            secret=secret, seen_entities=seen_entities, seen_events=seen_events, classes=classes, params=plan.get('params'))
        first_unit = int(det['state'].get('units', 0)) + 1
        if det['kind'] == 'sm1':
            kernel = eprocess.EDetector.from_state(det['state'])
            found = kernel.update(values)
            state = kernel.state()
            alarms_total += len(found)
            standing = {'formal': 'F', 'descriptive': 'P', 'insufficient_power': 'P'}[det['standing']]
            for alarm in found:
                signals.append(_alarm_signal(det, plan, alarm, index, standing, comparability))
        else:
            kernel = eprocess.RecoveryTest.from_state(det['state'])
            before = kernel.claimed_at
            kernel.update(values)
            state = kernel.state()
            found = []
            if before is None and kernel.claimed_at is not None:
                claims_total += 1
                found = [{'claimed_at_unit': kernel.claimed_at, 'upper': kernel.upper()}]
                signals.append(_claim_signal(det, plan, kernel, index, comparability))
            elif kernel.claimed_at is None and kernel.units >= int(plan.get('horizon_units') or 10**18):
                signals.append({'source': 'recovery', 'source_id': det['detector_id'],
                                'standing': 'F' if det['standing'] == 'formal' else 'P', 'severity': 'info',
                                'kind': 'recovery_not_established', 'dedupe': f"{det['detector_id']}:not_established",
                                'payload': {'units': kernel.units, 'upper': kernel.upper(), 'theta': plan['theta'],
                                            'condition': plan.get('condition_id')}})
        updates.append({'detector': det, 'state': state, 'values': len(values), 'entities': entities, 'events': events,
                        'excluded': excluded, 'alarms': found, 'first_unit': first_unit})
    for item in measures.evaluate_rules([r for r in definition.get('rules', []) if r.get('phase', 'close') == phase],
                                        measure_map, drift if phase == 'close' else (),
                                        drift_thresholds=definition.get('drift_thresholds')):
        signals.append({**item, 'source': 'rule', 'dedupe': f"{item['source_id']}:{index}:{phase}"})
    if phase == 'close' and not selected_units:
        signals.append({'source': 'health', 'source_id': 'empty_window', 'standing': 'D', 'severity': 'high',
                        'kind': 'empty_window', 'dedupe': f'empty_window:{index}',
                        'payload': {'window': index, 'start': windows.iso(start), 'end': windows.iso(end), 'closure': closure,
                                    'detail': 'No selected units in a closed window: not monitored, not healthy.'}})
    estimates, matches = [], []
    if variant is not None and phase == 'close':
        for name in definition.get('estimators', []):
            record, hashes = estimators.estimate(name, selected_units, task, reference['packet'], namespace)
            record.update(window=index, catalog_sequence=k, as_of=as_of)
            estimates.append((name, record, hashes))
    if variant is not None and phase == 'maturity':
        with installation.db.connect() as conn:
            prior = [dict(r) for r in conn.execute(
                'SELECT id, estimator, record FROM ops_estimates WHERE org_id = %s AND deployment_id = %s AND definition_version = %s '
                'AND window_index = %s AND matched IS NULL', (scope.org_id, deployment_id, version, index)).fetchall()]
        for row in prior:
            hashes = _population_hashes(installation, row)
            matches.append((row['id'], estimators.matched(row['estimator'], hashes, selected_units, task, reference['packet'],
                                                           namespace)))
    packet = {'deployment': deployment_id, 'version': version, 'phase': phase, 'window': index, 'start': start, 'end': end,
              'closure': closure, 'catalog_sequence': k, 'as_of': as_of, 'evidence_use': governance['reservation']['id'],
              'variant': definition['variant'], 'measurements': [] if variant is None else variant['measurements'],
              'coverage': None if variant is None else variant['coverage'], 'drift': drift,
              'selected_digest': None if variant is None else variant['selected_digest'],
              'units': _compact(namespace, selected_units, task), 'estimates': [e[1] for e in estimates],
              'estimate_populations': {e[0]: e[2] for e in estimates},
              'label_availability_rate': window_inclusion, 'reference_label_availability_rate': ref_inclusion,
              'invalid_outcome_rate': invalid_rate, 'reference_entity_overlap': overlap,
              'reference_invalid_outcome_rate': reference['packet']['inclusion'].get('invalid_outcome_rate'),
              'region_shares': region_rules.shares(selected_units, definition.get('regions'))}
    ref = packets.stage(installation, lease, ctx['catalog_id'], packets.encode(packet))
    evaluation_id = uuid.uuid4()
    selection = digest({'selected': packet['selected_digest'], 'units': len(selected_units)})

    def write(conn):
        conn.execute('''INSERT INTO ops_window_evaluations(org_id, id, deployment_id, definition_version, window_index, revision,
                            phase, start_tick, end_tick, closure, catalog_sequence, as_of, selection_digest, units,
                            packet_object, packet_digest, evidence_use_id)
                        VALUES (%s, %s, %s, %s, %s, 1, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)''',
                     (scope.org_id, evaluation_id, deployment_id, version, index, phase, start, end, closure, k, as_of,
                      selection, len(selected_units), ref.id, packets.packet_digest(packet), governance['reservation']['id']))
        for update in updates:
            _apply(conn, scope, deployment_id, version, index, evaluation_id, update)
        for name, record, _hashes in estimates:
            conn.execute('''INSERT INTO ops_estimates(org_id, id, deployment_id, definition_version, estimator, window_index,
                                evaluation_id, population_digest, population, value, record)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)''',
                         (scope.org_id, uuid.uuid4(), deployment_id, version, name, index, evaluation_id,
                          record['population_digest'], record['population'], record['value'], Jsonb(record)))
        for estimate_id, match in matches:
            conn.execute('UPDATE ops_estimates SET matched = %s, matched_evaluation_id = %s, matched_at = clock_timestamp() '
                         'WHERE org_id = %s AND id = %s AND matched IS NULL',
                         (Jsonb(match), evaluation_id, scope.org_id, estimate_id))
        for signal in signals:
            _signal(conn, scope, deployment_id, version, index, signal)
    packets.publish(installation, lease, ctx['catalog_id'], [ref], [governance['reservation']['id']], write)
    return {'units': len(selected_units), 'alarms': alarms_total, 'claims': claims_total, 'signals': len(signals),
            'evaluation': str(evaluation_id)}


def _population_hashes(installation, row):
    """The estimate's original population (event hashes) from its window's close packet."""
    with installation.db.connect() as conn:
        ev = conn.execute('SELECT e.packet_object FROM ops_estimates s JOIN ops_window_evaluations e ON e.id = s.evaluation_id '
                          'WHERE s.org_id = %s AND s.id = %s', (installation.scope.org_id, row['id'])).fetchone()
    packet = packets.read(installation, ev['packet_object'])
    hashes = packet['estimate_populations'][row['estimator']]
    if digest(hashes) != row['record']['population_digest']:
        raise EvaluationError('Estimate population differs from its record.', 'evidence_changed')
    return hashes


def _seen(installation, deployment_id, version, detector_id, namespace, units_):
    entities = [unit_rules.entity_hash(namespace, u) for u in units_]
    events = [unit_rules.event_hash(namespace, u) for u in units_]
    with installation.db.connect() as conn:
        rows = conn.execute('SELECT kind, hash FROM ops_detector_units WHERE org_id = %s AND deployment_id = %s '
                            'AND definition_version = %s AND detector_id = %s AND hash = ANY(%s)',
                            (installation.scope.org_id, deployment_id, version, detector_id, entities + events)).fetchall()
    return ({bytes(r['hash']) for r in rows if r['kind'] == 'entity'}, {bytes(r['hash']) for r in rows if r['kind'] == 'event'})


def _apply(conn, scope, deployment_id, version, index, evaluation_id, update):
    det = update['detector']
    row = conn.execute('SELECT state_version, cursor_window FROM ops_detectors WHERE org_id = %s AND deployment_id = %s '
                       'AND definition_version = %s AND detector_id = %s FOR UPDATE',
                       (scope.org_id, deployment_id, version, det['detector_id'])).fetchone()
    first = det['plan'].get('first_window', 0)
    expected_cursor = None if index == first else index - 1
    if row['state_version'] != det['state_version'] or row['cursor_window'] != expected_cursor:
        raise EvaluationError('Detector state moved or a window would be skipped; the cycle retries.', 'detector_conflict')
    new_version = det['state_version'] + 1
    conn.execute('''INSERT INTO ops_detector_segments(org_id, deployment_id, definition_version, detector_id, window_index,
                        evaluation_id, state_version, first_unit, units, excluded, alarms)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)''',
                 (scope.org_id, deployment_id, version, det['detector_id'], index, evaluation_id, new_version,
                  update['first_unit'], update['values'], Jsonb(update['excluded']), Jsonb(update['alarms'])))
    conn.execute('''UPDATE ops_detectors SET state = %s, state_version = %s, cursor_window = %s, units = units + %s,
                        alarms = alarms + %s, updated_at = clock_timestamp()
                    WHERE org_id = %s AND deployment_id = %s AND definition_version = %s AND detector_id = %s
                          AND state_version = %s''',
                 (Jsonb(update['state']), new_version, index, update['values'],
                  len(update['alarms']) if det['kind'] == 'sm1' else 0, scope.org_id, deployment_id, version,
                  det['detector_id'], det['state_version']))
    rows = [(scope.org_id, deployment_id, version, det['detector_id'], 'entity', h, index) for h in update['entities']]
    rows += [(scope.org_id, deployment_id, version, det['detector_id'], 'event', h, index) for h in update['events']]
    if rows:
        with conn.cursor().copy('COPY ops_detector_units (org_id, deployment_id, definition_version, detector_id, kind, hash, '
                                'window_index) FROM STDIN') as copy:
            for value in rows:
                copy.write_row(value)


def _comparability(definition, reference_packet, phase, det, window_inclusion, invalid_rate, overlap=None):
    """R2.4 comparability of the included population with the reference, for one detector and window.

    Compared rates (``shifted`` lists those beyond the declared tolerance):
    - label availability among units whose follow-up elapsed (outcome detectors; ``inclusion_tolerance``, default 0.1);
    - invalid-outcome rate (outcome detectors; the same tolerance);
    - late exclusion: units published after their window was processed, over all units this detector has seen. The
      reference has none by construction (``late_tolerance``, default 0.01, plan G.3).
    Entity-first thinning is recorded with the detector's exclusions but not compared: the stream accumulates repeat
    entities over months while the reference covers one period, so their thinning rates differ by design.
    The reference/stream entity overlap is measured and shown; independence remains a declared assumption.
    """
    tolerance = float(definition.get('inclusion_tolerance', 0.1))
    late_tolerance = float(definition.get('late_tolerance', 0.01))
    inclusion = reference_packet.get('inclusion') or {}
    rates, limits = {}, {}
    if phase == 'maturity':
        if window_inclusion is not None and inclusion.get('label_availability_rate') is not None:
            rates['label_availability'] = (window_inclusion, inclusion['label_availability_rate'])
            limits['label_availability'] = tolerance
        if invalid_rate is not None and inclusion.get('invalid_outcome_rate') is not None:
            rates['invalid_outcome'] = (invalid_rate, inclusion['invalid_outcome_rate'])
            limits['invalid_outcome'] = tolerance
    seen = int(det.get('units') or 0) + int(det.get('late_excluded') or 0)
    if seen:
        rates['late_exclusion'] = (int(det.get('late_excluded') or 0) / seen, 0.0)
        limits['late_exclusion'] = late_tolerance
    shifted = sorted(k for k, (window, ref) in rates.items() if abs(window - ref) > limits[k])
    return {'shifted': shifted, 'rates': {k: {'window': w, 'reference': r, 'tolerance': limits[k]} for k, (w, r) in rates.items()},
            'reference_entity_overlap': overlap}


def _population_note(comparability):
    if comparability['shifted']:
        return ('formal for the included population; population definition has shifted relative to reference ('
                + ', '.join(comparability['shifted']) + ')')
    return 'included population comparable to reference'


def _assumptions(comparability):
    overlap = comparability.get('reference_entity_overlap')
    independence = 'reference independent of the monitored stream'
    if overlap is not None:
        independence += f" (measured entity overlap with the reference: {overlap['shared']} of {overlap['entities']} window entities)"
    return ['conditional risk of included units given the observed past', 'no unmodelled common shocks', independence]


def _alarm_signal(det, plan, alarm, index, standing, comparability):
    wording = (f"The matured observed-label sequence since the detector start is inconsistent (expected false alarms <= "
               f"alpha per included unit, alpha = {plan['alpha']:.3g}) with per-unit conditional {plan['statistic']} risk "
               f"never exceeding {plan['m0']:.4g}. Risk exceeded that level at some point after approximately unit "
               f"{alarm['onset']}.")
    rates = comparability['rates']
    payload = {'detector': det['detector_id'], 'statistic': plan['statistic'], 'unit': alarm['unit'], 'onset_unit': alarm['onset'],
               'log_statistic': alarm['log_statistic'], 'm0': plan['m0'], 'alpha': plan['alpha'], 'standing': det['standing'],
               'reasons': plan.get('reasons', []), 'added_after_observation': plan.get('added_after_observation', False),
               'wording': wording if standing == 'F' else 'Descriptive alarm (no probability statement): ' + wording,
               'not_established': ['average risk over the period', 'cause', 'a probability that degradation occurred',
                                   'anything about unlabelled, immature, reserve-held or late-excluded units'],
               'assumptions': _assumptions(comparability),
               'population': _population_note(comparability), 'comparability': comparability,
               'label_availability_rate': (rates.get('label_availability') or {}).get('window'),
               'reference_label_availability_rate': (rates.get('label_availability') or {}).get('reference')}
    return {'source': 'detector', 'source_id': det['detector_id'], 'standing': standing,
            'severity': 'high' if standing == 'F' else 'medium', 'kind': 'sequential_alarm',
            'dedupe': f"{det['detector_id']}:alarm:{alarm['unit']}", 'payload': payload}


def _claim_signal(det, plan, kernel, index, comparability):
    """An SM2 claim. Formal only when the test was admitted formally (R2.5); a descriptive claim is never recovery."""
    claim = plan['claim']
    formal = det['standing'] == 'formal'
    wording = (f"Post-start risk on matured observed labels is below {plan['theta']:.4g} (error <= {plan['error_bound']:.3g})."
               if claim == 'R2' else
               f"Post-start risk is not worse than the reference by more than {plan['delta']} (error <= {plan['error_bound']:.3g}).")
    if not formal:
        wording = ('Descriptive recovery indication (no error statement; not recovery evidence; reasons: '
                   + ', '.join(plan.get('reasons') or ['not_formally_admitted']) + '): ' + wording)
        kind = 'descriptive_recovery_indication'
    else:
        kind = 'threshold_recovery_established' if claim == 'R2' else 'reference_noninferiority_established'
    return {'source': 'recovery', 'source_id': det['detector_id'], 'standing': 'F' if formal else 'P', 'severity': 'info',
            'kind': kind, 'dedupe': f"{det['detector_id']}:claim",
            'payload': {'claim': claim, 'theta': plan['theta'], 'units': kernel.units, 'claimed_at_unit': kernel.claimed_at,
                        'upper': kernel.upper(), 'wording': wording, 'interpretation': plan['interpretation'],
                        'condition': plan.get('condition_id'), 'standing': det['standing'], 'reasons': plan.get('reasons', []),
                        'population': _population_note(comparability), 'comparability': comparability,
                        'assumptions': _assumptions(comparability)}}


def _signal(conn, scope, deployment_id, version, index, signal):
    conn.execute('''INSERT INTO ops_signals(org_id, id, deployment_id, definition_version, source, source_id, window_index,
                        standing, severity, payload, dedupe_key)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (org_id, dedupe_key) DO NOTHING''',
                 (scope.org_id, uuid.uuid4(), deployment_id, version, signal['source'], signal['source_id'], index,
                  signal['standing'], signal['severity'], Jsonb({'kind': signal.get('kind'), **signal['payload']}),
                  f"{deployment_id}:{version}:{signal['dedupe']}"))


def revise(installation, ctx, current, reference, phase, now_tick):
    """New revisions for evaluated windows whose facts changed after their latest evaluation (late publications).

    Incremental: the facts published since the last scan (the revision cursor, at least the earliest
    latest-evaluation K) are joined to the opportunities of evaluated windows; a window is late when its newest
    linked publication is after its own K. Facts for windows not yet evaluated (a bulk catch-up) are not scanned
    against history: they are first evaluations. Every fact is scanned once: the cursor moves to the catalog head read at the
    start of the scan, and only when every late window found was revised in this cycle (otherwise the next cycle
    rescans from the old cursor, and windows already revised carry their new K).
    """
    definition, version = current['spec'], current['version']
    scope = installation.scope
    deployment_id = ctx['deployment']['id']
    start = instant(definition['start'])
    length = int(definition['window_ns'])
    # Outcome arrivals are maturation, not lateness, for outcome-free (close) measures.
    kinds = "AND x.kind <> 'outcome'" if phase == 'close' else ''
    with installation.db.connect() as conn:
        latest = {int(r['window_index']): dict(r) for r in conn.execute(
            '''SELECT DISTINCT ON (window_index) window_index, revision, catalog_sequence, start_tick, end_tick, closure
               FROM ops_window_evaluations WHERE org_id = %s AND deployment_id = %s AND definition_version = %s AND phase = %s
               ORDER BY window_index, revision DESC''', (scope.org_id, deployment_id, version, phase)).fetchall()}
        if not latest:
            return []
        head = conn.execute('SELECT head FROM catalog_heads WHERE org_id = %s AND catalog_id = %s',
                            (scope.org_id, ctx['catalog_id'])).fetchone()['head']
        cursor = conn.execute('SELECT checked_sequence FROM ops_revision_cursors WHERE org_id = %s AND deployment_id = %s '
                              'AND definition_version = %s AND phase = %s', (scope.org_id, deployment_id, version, phase)).fetchone()
        floor = min(r['catalog_sequence'] for r in latest.values())
        if cursor is not None:
            floor = max(floor, int(cursor['checked_sequence']))
        # Only opportunities inside evaluated windows can make a window late; facts for windows not yet evaluated
        # (a bulk catch-up) are first evaluations, not revisions.
        low = min(int(r['start_tick']) for r in latest.values())
        high = max(int(r['end_tick']) for r in latest.values())
        # A window is late when a fact linked to one of its opportunities (the opportunity itself, a fact carrying its
        # opportunity key, or an outcome for its target) was published after the window's latest evaluation K.
        # Driven from the new facts by index probes, so the cost follows what was published since the cursor,
        # never the history. An opportunity fact's opportunity_key is its own key, and predictions and context
        # carry their opportunity's key: that link is a probe on the partition key. Outcomes link by target.
        # Each probe is a LATERAL subquery with its conditions inside (OFFSET 0 keeps it unflattened). A plain join
        # lets the planner scan every opportunity in the evaluated range once and filter it against every new fact,
        # which is quadratic after a bulk catch-up (millions of new facts). Keys are deduplicated before probing.
        # Close measures are outcome-free, so outcomes are not linked for them.
        outcome_link = '' if phase == 'close' else '''
                            UNION ALL
                            SELECT o.event_tick, n.sequence FROM (SELECT target_key, max(sequence) AS sequence FROM new
                                                                  WHERE kind = 'outcome' GROUP BY target_key) n
                            CROSS JOIN LATERAL (SELECT o0.event_tick FROM fact_index o0
                                                WHERE o0.catalog_id = %(c)s AND o0.target_key = n.target_key
                                                  AND o0.kind = 'opportunity' OFFSET 0) o'''
        from numek_platform.db import point_lookups
        with conn.transaction(), point_lookups(conn):
            linked = conn.execute(
                f'''WITH new AS MATERIALIZED (SELECT x.kind, x.opportunity_key, x.target_key, px.sequence FROM fact_index x
                                   JOIN publications px ON px.id = x.publication_id
                                   WHERE x.catalog_id = %(c)s AND px.sequence > %(floor)s AND px.sequence <= %(head)s {kinds}),
                        links AS (
                            SELECT o.event_tick, n.sequence FROM (SELECT opportunity_key, max(sequence) AS sequence FROM new
                                                                  WHERE opportunity_key IS NOT NULL GROUP BY opportunity_key) n
                            CROSS JOIN LATERAL (SELECT o0.event_tick FROM fact_index o0
                                                WHERE o0.catalog_id = %(c)s AND o0.kind = 'opportunity'
                                                  AND o0.route = n.opportunity_key AND o0.key = n.opportunity_key OFFSET 0) o
                            {outcome_link})
                   SELECT floor((event_tick - %(start)s)::numeric / %(length)s) AS window_index, max(sequence) AS newest
                   FROM links WHERE event_tick >= %(low)s AND event_tick < %(high)s GROUP BY 1''',
                {'c': ctx['catalog_id'], 'floor': floor, 'head': head, 'low': max(low, start), 'high': high,
                 'start': start, 'length': length}).fetchall()
        newest = {int(r['window_index']): int(r['newest']) for r in linked}
        late = [latest[index] for index in sorted(set(newest) & set(latest))
                if newest[index] > int(latest[index]['catalog_sequence'])]
    revised = [_revision(installation, ctx, current, reference, phase, row, now_tick) for row in late[:MAX_REVISIONS_PER_CYCLE]]
    if len(late) <= MAX_REVISIONS_PER_CYCLE:
        with installation.db.transaction() as conn:
            conn.execute('''INSERT INTO ops_revision_cursors(org_id, deployment_id, definition_version, phase, checked_sequence)
                            VALUES (%s, %s, %s, %s, %s)
                            ON CONFLICT (org_id, deployment_id, definition_version, phase) DO UPDATE
                            SET checked_sequence = greatest(ops_revision_cursors.checked_sequence, EXCLUDED.checked_sequence),
                                updated_at = clock_timestamp()''', (scope.org_id, deployment_id, version, phase, head))
    return revised


def _revision(installation, ctx, current, reference, phase, row, now_tick):
    definition, version = current['spec'], current['version']
    scope = installation.scope
    deployment_id = ctx['deployment']['id']
    namespace = ctx['namespace']
    index = int(row['window_index'])
    due, _start, _end = _due(definition, phase, index)
    lease, governance, result, k, as_of, (start, end) = _select(installation, ctx, definition, reference, phase, index,
                                                                min(due, now_tick), drift=False)
    from ..intelligence import regions as region_rules
    variant = result['variants'].get(definition['variant'])
    selected_units = region_rules.annotate([] if variant is None else variant['units'], definition.get('regions'))
    with installation.db.connect() as conn:
        detectors = [dict(r) for r in conn.execute(
            'SELECT detector_id, plan FROM ops_detectors WHERE org_id = %s AND deployment_id = %s AND definition_version = %s '
            'AND phase = %s AND cursor_window >= %s', (scope.org_id, deployment_id, version, phase, index)).fetchall()]
    late_counts = {}
    secret = references.order_secret(installation, deployment_id)
    classes = len(reference['packet']['metadata']['task'].get('classes') or [0, 1])
    for det in detectors:
        seen_entities, seen_events = _seen(installation, deployment_id, version, det['detector_id'], namespace, selected_units)
        values, _e, _v, _x = unit_rules.stream(selected_units, statistic=det['plan']['statistic'],
                                               design=definition['unit_design'], namespace=namespace, secret=secret,
                                               seen_entities=seen_entities, seen_events=seen_events, classes=classes,
                                               params=det['plan'].get('params'))
        late_counts[det['detector_id']] = len(values)
    packet = {'deployment': deployment_id, 'version': version, 'phase': phase, 'window': index, 'revision_of': row['revision'],
              'catalog_sequence': k, 'as_of': as_of, 'evidence_use': governance['reservation']['id'],
              'measurements': [] if variant is None else variant['measurements'],
              'coverage': None if variant is None else variant['coverage'],
              'selected_digest': None if variant is None else variant['selected_digest'],
              'units': _compact(namespace, selected_units), 'late_units_excluded_from_detectors': late_counts,
              'note': 'Window revision (late publications): a new measurement version; detector inputs are unchanged.'}
    ref = packets.stage(installation, lease, ctx['catalog_id'], packets.encode(packet))
    evaluation_id = uuid.uuid4()

    def write(conn):
        conn.execute('''INSERT INTO ops_window_evaluations(org_id, id, deployment_id, definition_version, window_index, revision,
                            phase, start_tick, end_tick, closure, catalog_sequence, as_of, selection_digest, units,
                            packet_object, packet_digest, evidence_use_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)''',
                     (scope.org_id, evaluation_id, deployment_id, version, index, row['revision'] + 1, phase, start, end,
                      row['closure'], k, as_of, digest({'selected': packet['selected_digest'], 'units': len(selected_units)}),
                      len(selected_units), ref.id, packets.packet_digest(packet), governance['reservation']['id']))
        for detector_id, count in late_counts.items():
            if count:
                conn.execute('UPDATE ops_detectors SET late_excluded = late_excluded + %s WHERE org_id = %s AND deployment_id = %s '
                             'AND definition_version = %s AND detector_id = %s',
                             (count, scope.org_id, deployment_id, version, detector_id))
    packets.publish(installation, lease, ctx['catalog_id'], [ref], [governance['reservation']['id']], write)
    return {'phase': phase, 'window': index, 'revision': row['revision'] + 1, 'late_units': late_counts}


def cycle_job(job_ctx, payload):
    """Worker-host entry point (``ops_monitoring_cycle``)."""
    from numek_platform.installation import Installation
    installation = Installation(payload['installation'])
    from ...execution_context import InProcessContext, using
    with using(InProcessContext(deadline=job_ctx.deadline)):
        return monitor_once(installation, payload['deployment'], now_tick=payload.get('now_tick'))


def monitor_once(installation, deployment_id, *, now_tick=None):
    """Monitoring cycle, then the operations step (signals → conditions → incidents) at the same time."""
    from datetime import datetime, timezone
    from ..incidents import engine
    now_tick = time.time_ns() if now_tick is None else int(now_tick)
    summary = cycle(installation, deployment_id, now_tick=now_tick)
    summary['operations'] = engine.operate(installation, deployment_id, now=datetime.fromtimestamp(now_tick / 1e9, tz=timezone.utc))
    return summary
