"""input_inspection_v1: a bounded, deterministic look at an uploaded table, for guiding configuration only.

Advisory. It is never written into analysis JSON, specifications, fingerprints or history; the analysis run keeps its
own authoritative read. Every item carries one class:
- observed: a count or value read from the inspected rows ("17,379 rows; 869 distinct values");
- structural: a deterministic property of the inspected rows ("parses as an ISO date in all 17,379 inspected values");
- suggestion: a heuristic with a named rule and its reason ("possible identifier, R-ID-1: id-like name, unique in the
  inspected rows"). Suggestions are never applied; the user confirms each one;
- unknown: what inspection cannot establish (business meaning, availability at prediction time).

Budgets are enforceable (`InspectionBudget`): source bytes and rows decide whether the whole file is inspected; columns
beyond the profiling limit are listed by name only; the file is read in chunks into per-column accumulators whose
distinct-value tracking is capped, so memory stays bounded; and a deadline stops the pass between chunks. When a
budget is exceeded the first rows are inspected and the coverage says exactly what was and was not seen. Statements
that need the whole file (unique, constant) are never made from a partial pass.

Parsing: the pass uses the same pandas arguments as the analysis (`ingestion.csv_read_kwargs`) under one parse profile.
CSV-first discovery runs under the provisional profile (detected separator, defaults), which equals every core
workflow's default; the confirmed workflow reuses the cached inspection when its parse fingerprint is unchanged.
"""
import hashlib
import json
import math
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

VERSION = 'input_inspection_v1'
MIB = 1024 * 1024


@dataclass(frozen=True)
class InspectionBudget:
    full_bytes: int = 64 * MIB          # whole-file inspection only up to this size
    full_rows: int = 500_000            # and this many data rows
    fallback_rows: int = 50_000         # otherwise the first rows, at most
    profiled_columns: int = 500         # detailed accumulators; later columns are listed by name and type only
    listed_columns: int = 2_000         # columns beyond this are counted, not listed
    chunk_rows: int = 50_000
    distinct_cap: int = 10_000          # per-column distinct values tracked exactly up to this many
    unique_tracked: int = 16            # columns whose exact uniqueness is tracked across chunks (64-bit hashes)
    deadline_seconds: float = 4.0


ID_TOKENS = {'id', 'ids', 'uuid', 'guid', 'key', 'index', 'identifier'}
STATUS_VOCAB = {'labeled', 'labelled', 'unlabeled', 'unlabelled', 'pending', 'skipped', 'uncertain', 'reviewed', 'annotated',
                'observed', 'missing', 'unknown', 'intentionally_unlabeled', 'not_applicable', 'rejected', 'accepted', 'in_review'}
BINARY_SETS = [{0, 1}, {True, False}, {'yes', 'no'}, {'true', 'false'}, {'y', 'n'}, {'0', '1'}]
UNKNOWNS = [
    'What each column means for your task is not established by its name, type or values.',
    'Whether a column is known at prediction time cannot be inspected; it is a declaration only you can make.',
    'A suggestion is a structural hint with a stated rule, not a recommendation of what to analyse.',
]

# The rule catalogue, as shown in the app (the Input Inspection Boundary in docs/ARCHITECTURE.md).
RULES = {
    'R-ID-1': 'Possible identifier: an identifier-like name and a different value in every inspected row.',
    'R-ID-2': 'A different value in every inspected row, in a whole-number or text column (no identifier-like name).',
    'R-TIME-1': 'Parses as a date or time in at least 99% of non-missing inspected values (ISO 8601 only; no locale guessing).',
    'R-TIME-2': 'Whole numbers in the range of epoch seconds or milliseconds; a time only if you confirm the unit.',
    'R-BIN-1': 'Exactly two values that read as a yes/no indicator (0/1, true/false, yes/no).',
    'R-MULTI-1': 'Two or more yes/no columns. If they are labels, one column per label, the multilabel analysis applies; if they are features, it does not.',
    'R-CAT-1': 'A small set of distinct values.',
    'R-NUM-1': 'Numeric, finite and not constant.',
    'R-TEXT-1': 'Free text: at least half of the values are 40 or more characters, or five or more words.',
    'R-STATUS-1': 'Values from an annotation-status vocabulary (labeled, pending, skipped, ...): possibly a labelling status column.',
    'R-ENTITY-1': 'Where times repeat in the inspected rows, a column whose values make each (value, time) pair unique: possibly an entity, one series per value.',
    'R-KEY-1': 'Present in every source and a different value in every inspected row of each: possibly an identity key.',
    'R-MAP-1': 'Names that differ only in letter case, spaces, hyphens or underscores across sources: possibly the same column.',
}


def profile_fingerprint(options):
    """The parse fingerprint an inspection was made under; equal fingerprints parse identically."""
    from datatrust.ingestion import parsing_options_dict
    return hashlib.sha256(json.dumps(parsing_options_dict(options), sort_keys=True, default=str).encode()).hexdigest()


def _tokens(name):
    spaced = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', str(name))
    return {t for t in re.split(r'[^A-Za-z0-9]+', spaced.lower()) if t}


class _Column:
    __slots__ = ('name', 'dtype', 'non_null', 'missing', 'distinct', 'capped', 'numeric', 'integral', 'finite', 'minimum', 'maximum',
                 'long_text', 'text_values', 'time_parsed', 'time_tested', 'hashes', 'unique_so_far')

    def __init__(self, name):
        self.name, self.dtype = name, None
        self.non_null = self.missing = 0
        self.distinct, self.capped = set(), False
        self.numeric, self.integral, self.finite = None, True, 0
        self.minimum = self.maximum = None
        self.long_text = self.text_values = 0
        self.time_parsed = self.time_tested = 0
        self.hashes, self.unique_so_far = None, True


def _update(col, series, budget, track_unique):
    present = series.dropna()
    col.dtype = col.dtype or str(series.dtype)
    col.non_null += int(len(present))
    col.missing += int(len(series) - len(present))
    numeric = pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series)
    col.numeric = numeric if col.numeric is None else (col.numeric and numeric)
    if not col.capped:
        for v in present.unique()[: budget.distinct_cap + 1]:
            col.distinct.add(v.item() if hasattr(v, 'item') else v)
            if len(col.distinct) > budget.distinct_cap:
                col.capped = True
                col.distinct = set()
                break
    if numeric and len(present):
        values = present.to_numpy(dtype=float)
        finite = values[np.isfinite(values)]
        col.finite += int(len(finite))
        if len(finite):
            lo, hi = float(finite.min()), float(finite.max())
            col.minimum = lo if col.minimum is None else min(col.minimum, lo)
            col.maximum = hi if col.maximum is None else max(col.maximum, hi)
            col.integral = col.integral and bool(np.all(np.mod(finite, 1) == 0))
    elif len(present) and (series.dtype == object or pd.api.types.is_string_dtype(series)):
        text = present.astype(str)
        col.text_values += int(len(text))
        col.long_text += int(((text.str.len() >= 40) | (text.str.count(r'\s+') >= 4)).sum())
        sample = text.iloc[:2000]
        parsed = pd.to_datetime(sample, format='ISO8601', errors='coerce', utc=True)
        col.time_tested += int(len(sample))
        col.time_parsed += int(parsed.notna().sum())
    if track_unique and col.unique_so_far:
        hashes = pd.util.hash_pandas_object(present, index=False).to_numpy()
        col.hashes = hashes if col.hashes is None else np.concatenate([col.hashes, hashes])
        if len(np.unique(col.hashes)) != len(col.hashes):
            col.unique_so_far, col.hashes = False, None


def _finish(col, rows, complete, ceiling):
    n = lambda v: f'{v:,}'
    scope = 'in every row' if complete else 'in the inspected rows'
    observed = {'non_missing': col.non_null, 'missing': col.missing, 'distinct': None if col.capped else len(col.distinct), 'distinct_capped': col.capped,
                'minimum': col.minimum, 'maximum': col.maximum}
    structural, suggestions = [], []
    distinct = None if col.capped else len(col.distinct)
    unique = col.unique_so_far and col.missing == 0 and col.non_null > 1
    if unique:
        structural.append(f'A different value {scope} ({n(col.non_null)} values).')
        named = bool(_tokens(col.name) & ID_TOKENS)
        if named or not (col.numeric and not col.integral):  # a fractional measurement is often unique; that is not an identifier
            rule = 'R-ID-1' if named else 'R-ID-2'
            suggestions.append({'rule': rule, 'role': 'identifier', 'text': RULES[rule]})
    if distinct == 1:
        structural.append(f'One value {scope}.')
    values = col.distinct if not col.capped else set()
    lowered = {str(v).strip().lower() for v in values}
    if distinct == 2 and any(values == s or lowered == {str(x) for x in s} for s in BINARY_SETS):
        suggestions.append({'rule': 'R-BIN-1', 'role': 'indicator', 'text': RULES['R-BIN-1']})
    if col.time_tested and col.time_parsed >= 0.99 * col.time_tested:
        structural.append(f'Parses as an ISO 8601 date or time in {n(col.time_parsed)} of {n(col.time_tested)} tested values.')
        suggestions.append({'rule': 'R-TIME-1', 'role': 'clock', 'text': RULES['R-TIME-1']})
    if col.numeric and col.integral and col.minimum is not None and (1e9 <= col.minimum and col.maximum <= 4.2e9 or 1e12 <= col.minimum and col.maximum <= 4.2e12):
        suggestions.append({'rule': 'R-TIME-2', 'role': 'clock', 'text': RULES['R-TIME-2']})
    if col.numeric and col.finite and col.minimum is not None and col.minimum < col.maximum:
        suggestions.append({'rule': 'R-NUM-1', 'role': 'numeric', 'text': RULES['R-NUM-1']})
    if distinct is not None and 2 <= distinct <= ceiling and not unique:
        suggestions.append({'rule': 'R-CAT-1', 'role': 'category', 'text': RULES['R-CAT-1']})
    if col.text_values and col.long_text * 2 >= col.text_values:
        suggestions.append({'rule': 'R-TEXT-1', 'role': 'text', 'text': RULES['R-TEXT-1']})
    if values and distinct <= 10 and lowered and sum(1 for v in lowered if v in STATUS_VOCAB) * 2 >= len(lowered):
        suggestions.append({'rule': 'R-STATUS-1', 'role': 'annotation_status', 'text': RULES['R-STATUS-1']})
    return {'name': col.name, 'dtype': col.dtype, 'observed': observed, 'structural': structural, 'suggestions': suggestions}


def inspect_table(path, options, budget=InspectionBudget(), *, frame=None, frame_complete=True, clock=time.monotonic):
    """Inspect a CSV under the given parse options (CsvParseOptions). `frame`, when the caller already parsed the whole
    file with the same options, is profiled instead of reading again; `frame_complete=False` says it holds only the
    first rows (a bounded Parquet read), so the coverage says so."""
    from datatrust.ingestion import apply_column_types, csv_read_kwargs
    path = Path(path)
    size = path.stat().st_size
    started = clock()
    full = size <= budget.full_bytes
    header = list(frame.columns) if frame is not None else list(pd.read_csv(path, nrows=0, **csv_read_kwargs(options)).columns)
    listed = [str(c) for c in header[: budget.listed_columns]]
    profiled = header[: budget.profiled_columns]
    cols = [_Column(str(c)) for c in profiled]
    numeric_overrides = [n for n, kind in (options.column_types.items() if options else []) if kind == 'numeric' and n in profiled]
    limit = budget.full_rows if full else budget.fallback_rows
    chunks = iter([frame[profiled]] if frame is not None else pd.read_csv(path, usecols=profiled, chunksize=budget.chunk_rows, **csv_read_kwargs(options)))
    tracked, rows, stopped = None, 0, None
    for chunk in chunks:
        if frame is None:
            for name in numeric_overrides:  # the same refusal as the analysis read (ingestion.apply_column_types)
                try:
                    chunk[name] = pd.to_numeric(chunk[name], errors='raise')
                except (ValueError, TypeError) as exc:
                    raise ValueError(f"Column '{name}' contains invalid numeric values; no values were coerced to missing.") from exc
        truncated = rows + len(chunk) > limit
        if truncated:
            chunk = chunk.iloc[: limit - rows]
        if tracked is None:  # chosen once, on the first chunk: identifier-named columns first, then columns unique within it
            named = [i for i, c in enumerate(cols) if _tokens(c.name) & ID_TOKENS]
            local = [i for i, c in enumerate(cols) if i not in named and chunk.iloc[:, i].nunique(dropna=False) == len(chunk)]
            tracked = set((named + local)[: budget.unique_tracked])
        for i, col in enumerate(cols):
            _update(col, chunk.iloc[:, i], budget, i in tracked)
        rows += len(chunk)
        if truncated or rows >= limit:
            more = truncated or next(chunks, None) is not None
            if more:
                stopped = 'rows' if full else 'bytes'
            break
        if clock() - started > budget.deadline_seconds:
            more = next(chunks, None) is not None
            stopped = 'time' if more else None
            break
    tracked = tracked or set()
    if frame is not None and not frame_complete:
        stopped = 'rows'
    for i, col in enumerate(cols):
        if i not in tracked:
            col.unique_so_far = False
    complete = stopped is None
    ceiling = min(20, max(2, rows // 2))
    columns = [_finish(c, rows, complete, ceiling) for c in cols]
    columns += [{'name': str(c), 'dtype': None, 'observed': None, 'structural': [], 'suggestions': [], 'not_profiled': True} for c in header[len(profiled): budget.listed_columns]]
    indicators = [c['name'] for c in columns if any(s['rule'] == 'R-BIN-1' for s in c['suggestions'])]
    table = [{'rule': 'R-MULTI-1', 'columns': indicators, 'text': RULES['R-MULTI-1']}] if len(indicators) >= 2 else []
    statement = (f'Inspected all {rows:,} rows.' if complete else
                 {'bytes': f'The file is larger than {budget.full_bytes // MIB} MiB: inspected the first {rows:,} rows only; suggestions describe those rows.',
                  'rows': f'Inspected the first {rows:,} rows only (the inspection limit); suggestions describe those rows.',
                  'time': f'Stopped after {rows:,} rows at the {budget.deadline_seconds:g}-second inspection limit; suggestions describe those rows.'}[stopped])
    if len(header) > len(profiled):
        statement += f' Columns {len(profiled) + 1:,}–{len(header):,} were listed, not profiled.'
    return {
        'version': VERSION, 'profile': {'fingerprint': profile_fingerprint(options) if options else None, 'delimiter': options.delimiter if options else None},
        'coverage': {'complete': complete, 'stopped': stopped, 'rows_inspected': rows, 'bytes': size, 'columns_total': len(header),
                     'columns_profiled': len(profiled), 'columns_listed': len(listed), 'statement': statement},
        'columns': columns, 'table': table, 'rules': RULES, 'unknowns': UNKNOWNS, 'budget': asdict(budget),
    }


# ——— Multi-source inspection (Guided Analysis Stage 5) ———————————————————————————————————————————————————————————————

# Sources added to comparison and temporal workflows may be large data-root files; they always get the bounded head.
SOURCE_BUDGET = InspectionBudget(full_bytes=8 * MIB, full_rows=20_000, fallback_rows=20_000)


def inspect_source(path, fmt='csv', delimiter=',', budget=SOURCE_BUDGET, clock=time.monotonic):
    """Inspect a CSV or Parquet source under the provisional profile. Parquet reads the schema from metadata and the
    first row batch; a first batch beyond the budget is never read whole."""
    from datatrust import CsvParseOptions
    if fmt != 'parquet':
        return inspect_table(path, CsvParseOptions(delimiter=delimiter), budget, clock=clock)
    import pyarrow.parquet as pq
    handle = pq.ParquetFile(path)
    total = handle.metadata.num_rows
    batch = next(handle.iter_batches(batch_size=budget.fallback_rows), None)
    frame = batch.to_pandas() if batch is not None else handle.schema_arrow.empty_table().to_pandas()
    out = inspect_table(path, None, budget, frame=frame, frame_complete=len(frame) >= total, clock=clock)
    if len(frame) < total:
        out['coverage']['statement'] = f'Inspected the first {len(frame):,} of {total:,} rows (the inspection limit); suggestions describe those rows.'
    return out


def identity_key_candidates(inspections):
    """R-KEY-1: columns present in every source and unique in each source's inspected rows. `inspections` maps a
    source id to its inspection; failed inspections are skipped and named."""
    usable = {k: v for k, v in inspections.items() if v and 'columns' in v}
    if len(usable) < 2:
        return []
    unique = [{c['name'] for c in v['columns'] if any(s['role'] == 'identifier' for s in c['suggestions'])} for v in usable.values()]
    order = [c['name'] for c in next(iter(usable.values()))['columns']]
    shared = set.intersection(*unique)
    return [{'columns': [c], 'rule': 'R-KEY-1', 'text': RULES['R-KEY-1']} for c in order if c in shared]


def _norm(name):
    return re.sub(r'[\s_\-]+', '', str(name)).lower()


def name_mapping_candidates(headers):
    """R-MAP-1: for each later source, its columns whose normalised name matches a different spelling in the first
    source. `headers` maps source ids to header lists, in source order."""
    items = list(headers.items())
    if len(items) < 2:
        return []
    first = {_norm(h): h for h in items[0][1]}
    exact = set(items[0][1])
    out = []
    for sid, names in items[1:]:
        for h in names:
            match = first.get(_norm(h))
            if match is not None and match != h and h not in exact:
                out.append({'source': sid, 'column': h, 'aligned': match, 'rule': 'R-MAP-1', 'text': RULES['R-MAP-1']})
    return out


_UNITS = [(86400 * 7, 'week'), (86400, 'day'), (3600, 'hour'), (60, 'minute'), (1, 'second')]


def _spacing_label(seconds):
    for size, unit in _UNITS:
        if seconds >= size and seconds % size == 0:
            k = int(seconds // size)
            return f'{k} {unit}' + ('s' if k != 1 else '')
    return f'{seconds:g} seconds'


def time_structure(path, inspection, fmt='csv', delimiter=',', limit=8):
    """Clock, entity and spacing observations for a temporal source, from its inspected rows only (one bounded read of
    the clock and candidate columns). Never applied: the user confirms each one."""
    if not inspection or 'columns' not in inspection:
        return None
    rows = inspection['coverage']['rows_inspected']
    cols = inspection['columns']
    clocks = [c['name'] for c in cols if any(s['rule'] in {'R-TIME-1', 'R-TIME-2'} for s in c['suggestions'])][:3]
    ids = {c['name'] for c in cols if any(s['role'] == 'identifier' for s in c['suggestions'])}
    small = lambda c: any(s['rule'] in {'R-CAT-1', 'R-BIN-1'} for s in c['suggestions'])
    measurements = [{'column': c['name'], 'type': 'categorical' if small(c) else 'quantitative'} for c in cols
                    if any(s['rule'] == 'R-NUM-1' for s in c['suggestions']) and c['name'] not in ids and c['name'] not in clocks]
    candidates = [c['name'] for c in cols if c['name'] not in clocks and c.get('observed') and c['observed']['distinct'] is not None
                  and 2 <= c['observed']['distinct'] <= max(2, rows // 2) and not any(s['rule'] == 'R-NUM-1' and c['name'] not in ids for s in c['suggestions'])][:limit]
    out = {'clocks': [], 'entities': [], 'measurements': measurements, 'statement': None}
    if not clocks:
        return out
    wanted = clocks + candidates
    if fmt == 'parquet':
        import pyarrow.parquet as pq
        batch = next(pq.ParquetFile(path).iter_batches(batch_size=max(rows, 1), columns=wanted), None)
        frame = batch.to_pandas() if batch is not None else pd.DataFrame(columns=wanted)
    else:
        frame = pd.read_csv(path, usecols=wanted, nrows=rows, sep=delimiter, dtype=str, keep_default_na=True)
    for name in clocks:
        raw = frame[name].dropna()
        numeric = pd.to_numeric(raw, errors='coerce')
        epoch = numeric.notna().all() and len(raw) > 0
        if epoch:
            unit = 'ms' if numeric.min() >= 1e12 else 's'
            parsed = pd.to_datetime(numeric, unit=unit, utc=True, errors='coerce')
            kind, encoding = 'instant', 'epoch'
        else:
            text = raw.astype(str)
            parsed = pd.to_datetime(text, format='ISO8601', errors='coerce', utc=True)
            date_only = bool(text.str.fullmatch(r'\d{4}-\d{2}-\d{2}').all())
            offset = bool(text.str.contains(r'(?:Z|[+-]\d{2}:?\d{2})$', regex=True).all())
            kind = 'civil_date' if date_only else 'instant' if offset else 'local_datetime'
            encoding, unit = 'iso', None
        valid = parsed.dropna()
        repeats = len(valid) - valid.nunique()
        spacing = None
        unique_times = valid.drop_duplicates().sort_values()
        if len(unique_times) >= 3:
            gaps = unique_times.diff().dropna().dt.total_seconds()
            mode = float(gaps.mode().iloc[0])
            share = float((gaps == mode).mean())
            if mode > 0:
                spacing = {'seconds': mode, 'nanoseconds': int(mode * 1e9), 'label': _spacing_label(mode), 'share': round(share * 100, 1),
                           'first': (unique_times.iloc[0].date().isoformat() if kind == 'civil_date' else unique_times.iloc[0].tz_localize(None).isoformat() if kind == 'local_datetime' else unique_times.iloc[0].isoformat()), 'text': f'Most common spacing in the inspected rows: {_spacing_label(mode)} ({round(share * 100, 1)}% of consecutive distinct times). An observation, never applied as a schedule.'}
        out['clocks'].append({'column': name, 'kind': kind, 'encoding': encoding, 'epoch_unit': unit if encoding == 'epoch' else None,
                              'naive': kind == 'local_datetime', 'repeats': int(repeats), 'spacing': spacing,
                              'rule': 'R-TIME-2' if encoding == 'epoch' else 'R-TIME-1'})
        if repeats and not out['entities']:
            times = parsed.reindex(frame.index)
            for cand in candidates:
                pair = pd.DataFrame({'t': times, 'e': frame[cand]}).dropna()
                if len(pair) and pair.duplicated().sum() <= 0.01 * repeats:
                    out['entities'].append({'column': cand, 'clock': name, 'rule': 'R-ENTITY-1', 'distinct': int(frame[cand].nunique()), 'per_time': round(len(valid) / max(valid.nunique(), 1), 2),
                                            'text': f'Times in {name} repeat {repeats:,} times in the inspected rows; each ({cand}, {name}) pair is unique. Possibly one series per {cand}.'})
    # closest first: one series per value means as many values as each time repeats
    out['entities'].sort(key=lambda e: abs(e['distinct'] - e['per_time']))
    if out['clocks'] and not any(c['repeats'] for c in out['clocks']):
        out['statement'] = 'Within the inspected rows each time appears once, so whether the file holds one series or several is not established by the inspection.' + ('' if inspection['coverage']['complete'] else ' A file sorted by series may show only its first series in the inspected rows.')
    return out


# ——— Record discovery for text, image manifests and records (Guided Analysis Stage 5b) ————————————————————————————————

RULES.update({
    'R-SPLIT-1': 'At most ten distinct values, including a conventional split name (train, test, validation, dev, eval): possibly a split column.',
    'R-PATH-1': 'Text values ending in an image file extension: possibly the image path column.',
    'R-LIST-1': 'A list of short values in every record where present: possibly several labels per record.',
    'R-BOX-1': 'A list of objects carrying four-number boxes: possibly the object annotations; the box ranges are reported, not interpreted.',
})
SPLIT_WORDS = {'train', 'training', 'test', 'testing', 'validation', 'valid', 'val', 'dev', 'eval', 'evaluation', 'holdout'}
IMAGE_EXT = ('.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tif', '.tiff', '.webp')
BOX_KEYS = ('bbox', 'box', 'bounding_box', 'xyxy', 'xywh')


def _pointer(parts):
    return '/' + '/'.join(str(p).replace('~', '~0').replace('/', '~1') for p in parts)


def _walk(record, parts=(), depth=0):
    """(selector parts, value) pairs: top-level keys and, one level down, keys of nested objects."""
    for key, value in record.items():
        here = parts + (key,)
        yield here, value
        if isinstance(value, dict) and depth == 0:
            yield from _walk(value, here, 1)


def _kind(value):
    if value is None:
        return 'null'
    if isinstance(value, bool):
        return 'boolean'
    if isinstance(value, (int, float)):
        return 'number'
    if isinstance(value, str):
        return 'text'
    if isinstance(value, list):
        return 'list_of_objects' if value and all(isinstance(x, dict) for x in value) else 'list'
    return 'object'


def discover_selectors(records, examined=None):
    """Selector discovery over framed records (dicts), bounded by the caller. Each selector: its JSON Pointer (or plain
    name at the top level), presence and type counts, and rule-based suggestions. Advisory only."""
    records = [r for r in records if isinstance(r, dict)]
    stats = {}
    for record in records:
        for parts, value in _walk(record):
            s = stats.setdefault(parts, {'present': 0, 'kinds': {}, 'values': [], 'long': 0, 'texts': 0, 'lists': 0, 'short_lists': 0, 'boxes': []})
            s['present'] += 1
            kind = _kind(value)
            s['kinds'][kind] = s['kinds'].get(kind, 0) + 1
            if kind in {'text', 'number', 'boolean'}:
                s['values'].append(value)
            if kind == 'text':
                s['texts'] += 1
                s['long'] += len(value) >= 40 or len(value.split()) >= 5
            if kind == 'list':
                s['lists'] += 1
                s['short_lists'] += all(isinstance(x, (str, int)) and len(str(x)) <= 40 for x in value)
            if kind == 'list_of_objects':
                for item in value[:50]:
                    box = next((item[k] for k in BOX_KEYS if k in item), None)
                    if isinstance(box, list) and len(box) == 4 and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in box):
                        s['boxes'].append(box)
    n = len(records)
    out = []
    for parts, s in stats.items():
        name = parts[0] if len(parts) == 1 else _pointer(parts)
        values = s['values']
        distinct = len(set(map(str, values)))
        lowered = {str(v).strip().lower() for v in values}
        suggestions = []
        if s['texts'] and s['long'] * 2 >= s['texts']:
            suggestions.append({'rule': 'R-TEXT-1', 'role': 'content'})
        is_path = bool(s['texts']) and all(str(v).lower().endswith(IMAGE_EXT) for v in values if isinstance(v, str))
        if values and s['present'] == n and distinct == len(values) and n > 1 and s['texts'] + s['kinds'].get('number', 0) == len(values) and not (s['texts'] and s['long'] * 2 >= s['texts']) and not is_path:
            suggestions.append({'rule': 'R-ID-1' if _tokens(parts[-1]) & ID_TOKENS else 'R-ID-2', 'role': 'identifier'})
        if values and distinct <= 10 and lowered & SPLIT_WORDS:
            suggestions.append({'rule': 'R-SPLIT-1', 'role': 'split'})
        elif values and 2 <= distinct <= min(20, max(2, n // 2)) and not any(x['role'] == 'content' for x in suggestions):
            suggestions.append({'rule': 'R-CAT-1', 'role': 'label'})
        if is_path:
            suggestions.append({'rule': 'R-PATH-1', 'role': 'path'})
        if s['lists'] and s['short_lists'] == s['lists']:
            suggestions.append({'rule': 'R-LIST-1', 'role': 'labels'})
        if s['boxes']:
            suggestions.append({'rule': 'R-BOX-1', 'role': 'objects'})
        for x in suggestions:
            x['text'] = RULES[x['rule']]
        out.append({'selector': name, 'present': s['present'], 'kinds': s['kinds'], 'distinct': distinct if values else None,
                    'suggestions': suggestions, 'boxes': box_evidence(s['boxes']) if s['boxes'] else None})
    return {'version': VERSION, 'records_examined': n, 'statement': f'Examined the first {n:,} records{"" if examined is None else f" of at least {examined:,}"}; suggestions describe those records.',
            'selectors': out}


def box_evidence(boxes):
    """What four-number boxes allow, from their ranges only. Never chooses the format."""
    n = len(boxes)
    unit = sum(all(0 <= v <= 1 for v in b) for b in boxes)
    ordered = sum(b[2] > b[0] and b[3] > b[1] for b in boxes)
    consistent = []
    if unit == n:
        consistent.append('normalized_cxcywh')
    if ordered == n:
        consistent.append('xyxy')
    consistent.append('xywh')
    text = (f'In {unit:,} of {n:,} examined boxes every value lies between 0 and 1. ' if unit else '') + \
           f'In {ordered:,} of {n:,} the third value exceeds the first and the fourth exceeds the second. ' + \
           ('That rules out xyxy (corner coordinates). ' if ordered < n else '') + \
           f'Consistent with: {", ".join(consistent)}. Width-height boxes fit any of these ranges, so the format is not established by the values.'
    return {'examined': n, 'unit_range': unit, 'ordered': ordered, 'consistent': consistent, 'text': text}
