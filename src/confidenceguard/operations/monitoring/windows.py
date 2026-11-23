"""CG7 monitoring windows (plan G.1, H.2, H.6).

Windows are half-open event-time intervals ``[anchor + i*length, anchor + (i+1)*length)`` in ns ticks.

**Selection is exact and incremental.**
- A window evaluation loads only the opportunities with any revision in the window, with their
  complete revision chains, predictions, context, samples and outcomes. It does this through
  ``load_history(..., window_ticks=...)``.
- It then runs the unchanged CG3 ``select_history`` / ``HistoryStore``.
- The selected population equals the full-history selection restricted to the window. The
  equivalence gate is ``tests/platform/test_monitoring_windows.py``.
- Cost scales with the window, not with history.

**Governance before access.** The window's reservation (purpose ``monitoring_outcome``) covers
exactly the opportunities with any revision in the window. It is committed before any outcome read.
"""
import base64

from ...contracts import EvaluationError, digest
from ...history_contracts import instant

UNIT_COLUMNS = ('ordinal', 'event_key', 'entity_key', 'history_tick', 'history_opportunity', 'history_target',
                'outcome_valid', 'outcome_reason', 'y', 'y_num', 'decision', 'state', 'confidence', 'ptrue', 'brier',
                'point', 'cg_role', 'probs', 'prob_valid')


def window_ticks(anchor, length_ns, index):
    start = instant(anchor) + int(index) * int(length_ns)
    return start, start + int(length_ns)


def window_index(anchor, length_ns, tick):
    return (int(tick) - instant(anchor)) // int(length_ns)


def iso(tick):
    from datetime import datetime, timezone
    seconds, ns = divmod(int(tick), 10**9)
    value = datetime.fromtimestamp(seconds, tz=timezone.utc)
    if ns:
        return value.strftime('%Y-%m-%dT%H:%M:%S.') + f'{ns:09d}'.rstrip('0') + 'Z'
    return value.strftime('%Y-%m-%dT%H:%M:%SZ')


def window_id(anchor, length_ns, index):
    return f'w{int(index):06d}' if index >= 0 else f'wm{-int(index):06d}'


def evaluate_window(root, spec, sequence, effective_as_of, governance=None, *, pruned=True, cohort_scopes=True,
                    export_relation=False, reference=None, progress=None):
    """Select and measure one window (``spec.windows == (window,)``) at K = ``sequence``.

    Returns a plain dict per variant with:
    - ``measurements``: CG1/CG2/CG3 window measures, using the same reducers as CG3 longitudinal;
    - ``coverage``: the CG3 window coverage;
    - ``selected_digest``;
    - ``units``: the selected rows, for detector units and estimators.
    """
    from ... import compat
    from ...history_selection import HistoryStore, context_links, load_history, select_history
    from ...longitudinal import _evaluate
    if len(spec.windows) != 1:
        raise EvaluationError('A window evaluation selects exactly one window.', 'monitoring_window')
    window = spec.windows[0]
    ticks = (instant(window.start), instant(window.end)) if pruned else None
    work = compat.workspace(spec.config, 256 * 1024**2, progress)
    try:
        variants, scan = load_history(work, root, spec, sequence, governance, window_ticks=ticks)
        cutoff = select_history(work, spec, effective_as_of)
        context_links(work, root, sequence, spec.max_scan_records)
        out = {}
        for variant, metadata in sorted(variants.items()):
            store = HistoryStore(work, spec, variant, metadata, window, cutoff)
            store.metadata = metadata
            store.calibration_edges = spec.calibration_edges
            _evaluate(store, distributions_enabled=True)
            if cohort_scopes:
                for index, cohort in enumerate(spec.cohorts):
                    groups = work.con.execute(f'SELECT DISTINCT g{index} FROM {store.table} ORDER BY 1').fetchall()
                    for group, in groups:
                        if group in {'unretained', 'unresolved'}:
                            continue
                        from ...analytics import literal
                        _evaluate(store, f'cohort_{index}/{group}', f'g{index}={literal(group)}')
            normalized = {name for name, _type in metadata['normalized_columns']}
            present = [c for c in UNIT_COLUMNS if c in normalized or c in _HISTORY_COLUMNS]
            present += [f'g{i}' for i in range(len(spec.cohorts))]
            units = [dict(zip(present, row)) for row in work.con.execute(
                f'SELECT {",".join(chr(34) + c + chr(34) for c in present)} FROM {store.table} ORDER BY ordinal').fetchall()]
            contexts = dict(work.con.execute(f'SELECT ordinal, history_context FROM {store.table}').fetchall())
            import json
            for unit in units:
                if unit.get('history_tick') is not None:
                    unit['history_tick'] = int(unit['history_tick'])
                context = json.loads(contexts.get(unit['ordinal']) or '{}')
                unit['features'] = {name: context.get(name) for name in spec.features}
            coverage = dict(store.coverage)
            out[variant] = {'measurements': store.evidence.measurements, 'coverage': coverage,
                            'selected_digest': store.selected_digest, 'units': units,
                            'task': metadata['task'], 'cutoff': int(cutoff)}
            if export_relation:
                out[variant]['relation'] = base64.b64encode(_parquet(work.con, store.table)).decode()   # JSON-safe
                out[variant]['metadata'] = {k: metadata[k] for k in ('task', 'run', 'signature', 'outcome_definition_version',
                                                                     'normalized_columns') if k in metadata}
            if reference is not None and variant in reference:
                from .measures import drift_against_reference
                out[variant]['drift'] = drift_against_reference(work, spec, store, reference[variant])
        return {'variants': out, 'materialization': scan, 'window': window.to_dict(), 'catalog_sequence': int(sequence),
                'pruned': bool(pruned)}
    finally:
        work.close()


def _parquet(con, table):
    import io
    import pyarrow.parquet as pq
    relation = con.execute(f'SELECT * FROM {table} ORDER BY ordinal')
    arrow = relation.fetch_arrow_table() if hasattr(relation, 'fetch_arrow_table') else relation.arrow()
    buffer = io.BytesIO()
    pq.write_table(arrow, buffer, compression='zstd')
    return buffer.getvalue()


_HISTORY_COLUMNS = {'ordinal', 'event_key', 'y', 'y_num', 'outcome_valid', 'outcome_reason', 'ptrue', 'brier', 'history_fact',
                    'history_opportunity', 'history_target', 'history_tick', 'history_context', 'cg_role'}


def reserve_window(catalog, *, namespace, k, ticks, purpose='monitoring_outcome', metadata=None):
    """Commit the window's reservation (identity and clock membership only) before any outcome read."""
    return catalog.reserve_history(namespace=namespace, k=k, purpose_label=purpose, purpose=purpose, tick_range=ticks,
                                   metadata={'window': [str(ticks[0]), str(ticks[1])], **(metadata or {})})


def selection_digest(result):
    """Digest of a window selection (population and selected facts), independent of timings."""
    return digest({variant: {'selected': v['selected_digest'], 'units': len(v['units'])}
                   for variant, v in result['variants'].items()})
