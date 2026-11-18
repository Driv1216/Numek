"""The shared evidence-presentation contract for every DataTrust report (Report Experience plan, section G).

Presentation only: nothing here computes evidence. Workflow projections describe what they render as units of records
taken from the completed result; this module decides, deterministically, how each record is treated in each medium and
accounts for every one of them.

Three separate dimensions (G.1):
- coverage: what the analysis computed, bounded or skipped. It comes from the result and is carried on a unit as
  qualifiers; it is never added to the counts below;
- treatment, per unit and medium: a record is shown individually, grouped into a summary, or referenced (counted, with
  a location only);
- location, a set: html_summary (V1), html_detail (V2), pdf, json (V3), protected (V4).

Print profiles (report_print_v1):
- complete: every record printed individually;
- focused: R2a groups records only when they share severity, scope, trigger and interpretation; R2b prints members in
  significance order, always prints every member whose recorded detail differs in meaning, and summarises repetitive
  members once the group's page guideline is reached; R3 prints signal-free groups individually when that costs no more
  space than their summary; R4 summaries use only stored values, in a form suited to each field.
"""
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Optional

from datatrust.report_identity import PRINT_POLICY_VERSION

PROFILES = ('focused', 'complete')
SEVERITY_RANK = {'High': 0, 'Moderate': 1, 'Low': 2}
NO_FINDING_RANK = 3                  # an analysis flag without a finding ranks below Low
VIEWS = ('V1', 'V2')                 # V1 summary view (may carry a historical display limit); V2 detailed evidence view
FIELD_KINDS = ('quantity', 'category', 'scope', 'identity', 'text')
SUMMARY_ROWS = 3                     # a range summary occupies two range rows and a count line (R3 space-neutral rule)
DEFAULT_GROUP_PAGES = 1              # R2b guideline: about one printed page of repetitive members per group
# Table rows that fit one printed page with the shared print styles (_report_shell.html): medians measured on
# 2026-11-17 by validation/report_experience/spikes/rows_per_page.py (names of 10-49 characters; results in
# spikes/results/rows_per_page_shell.json) and frozen here as part of report_print_v1. They size the R2b guideline,
# which is a guideline: distinct members always print, and a page holds fewer rows when names wrap.
ROWS_PER_PAGE = {'evidence-portrait': 33, 'evidence-landscape': 24, 'register-portrait': 33}


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    kind: str = 'quantity'
    concept: Optional[str] = None

    def __post_init__(self):
        if self.kind not in FIELD_KINDS:
            raise ValueError(f'Unknown field kind: {self.kind}')


@dataclass(frozen=True)
class Signal:
    """Why a record matters, exactly as the analysis recorded it. Nothing here is inferred by presentation."""
    code: str                       # finding code, flag name, or blocked/failed state
    severity: Optional[str] = None  # recorded severity or priority; None for a flag without a finding
    scope: str = ''                 # source, split pair, measurement, target or population
    trigger: str = ''               # rule, declaration, threshold rule or method that produced it
    interpretation: str = ''        # recorded meaning or evidence type
    measure: Optional[float] = None  # the triggering measure, for significance order
    detail: Optional[str] = None    # recorded free-text detail; members whose detail differs are never merged
    label: Optional[str] = None     # display wording for the group heading; not part of the grouping key

    @property
    def rank(self):
        return SEVERITY_RANK.get(self.severity, NO_FINDING_RANK)

    @property
    def key(self):
        """R2a: records group only when every element of this key is equal."""
        return (self.rank, self.scope, self.code, self.trigger, self.interpretation)


@dataclass(frozen=True)
class Record:
    key: str                         # stable within the unit (an evidence id, or pointer#index)
    entity: str                      # display identity
    values: dict
    order: int                       # source order
    pointer: str                     # JSON pointer of this record in the canonical result
    signal: Optional[Signal] = None  # the signal this unit presents it for
    group: tuple = ()                # R3 grouping key for signal-free records, e.g. (role, storage type)
    protected: bool = False          # its source content is held only in a protected manifest (V4)


@dataclass(frozen=True)
class Unit:
    unit_id: str
    title: str
    view: str
    fields: tuple
    records: tuple
    noun: str = 'records'
    pointer: str = ''                # JSON pointer of the collection
    html_anchor: str = ''            # where the V2 detailed view of these records is
    html_label: str = ''             # how a disclosure names that place, e.g. "Technical evidence §B.2"
    coverage: tuple = ()             # coverage qualifiers recorded by the analysis (G.1, I4)
    screen_limit: Optional[int] = None  # a historical display limit (PresentationLimits); V1 units only
    table_kind: str = 'evidence-landscape'
    printed: bool = True             # False: a V2 detail view that this print profile does not print (all referenced)
    limit_label: str = 'historical display limit'  # how a V1 disclosure names its bound; M6, M7 and M9 keep their
                                                    # existing summary selections, which are not PresentationLimits

    def __post_init__(self):
        if self.view not in VIEWS:
            raise ValueError(f'Unknown view: {self.view}')
        if self.screen_limit is not None and self.view != 'V1':
            raise ValueError('Only a V1 summary view carries a historical display limit.')
        keys = [r.key for r in self.records]
        if len(keys) != len(set(keys)):
            raise ValueError(f'Record keys repeat within unit {self.unit_id}.')


@dataclass(frozen=True)
class Summary:
    """R4: an evidence-appropriate summary of grouped records. Every number in it is a stored value or a count."""
    group_key: tuple
    kind: str                        # 'signal-remainder' | 'signal-free'
    count: int
    record_keys: tuple
    fields: tuple                    # (field key, summary dict)


@dataclass(frozen=True)
class GroupPlan:
    key: tuple
    signal: Optional[Signal]
    total: int
    entities: int
    individual: tuple                # records printed individually, in significance order
    summary: Optional[Summary]


@dataclass(frozen=True)
class Plan:
    unit_id: str
    medium: str                      # 'screen' | 'print'
    profile: str
    individual: tuple                # records
    summaries: tuple                 # Summary
    referenced: tuple                # records
    groups: tuple = ()               # GroupPlan, signal groups in key order (R1: every group appears)

    def treatment(self):
        out = {r.key: 'individual' for r in self.individual}
        out.update({key: 'grouped' for s in self.summaries for key in s.record_keys})
        out.update({r.key: 'referenced' for r in self.referenced})
        return out


def significance(record):
    signal = record.signal
    measure = signal.measure if signal and signal.measure is not None else None
    return (signal.rank if signal else NO_FINDING_RANK, measure is None, -(measure or 0), record.order, record.key)


def summarise(records, fields, group_key, kind):
    """R4: count, plus per field a summary suited to its kind, built only from stored values."""
    out = []
    ordered = sorted(records, key=lambda r: (r.order, r.key))
    for f in fields:
        present = [(r.values.get(f.key), r) for r in ordered if r.values.get(f.key) is not None]
        if f.kind == 'quantity':
            numbers = [(v, r) for v, r in present if isinstance(v, (int, float)) and not isinstance(v, bool)]
            if numbers:
                low = min(numbers, key=lambda item: (item[0], item[1].order))
                high = max(numbers, key=lambda item: (item[0], -item[1].order))
                summary = {'kind': 'range', 'min': low[0], 'min_entity': low[1].entity, 'max': high[0],
                           'max_entity': high[1].entity, 'with_value': len(numbers)}
            else:
                summary = {'kind': 'range', 'min': None, 'max': None, 'with_value': 0}
            summary['without_value'] = len(ordered) - summary['with_value']
        elif f.kind in ('category', 'scope'):
            tally = Counter(str(v) for v, _ in present)
            summary = {'kind': 'tally' if f.kind == 'category' else 'scopes',
                       'counts': sorted(tally.items(), key=lambda item: (-item[1], item[0])),
                       'without_value': len(ordered) - len(present)}
        elif f.kind == 'identity':
            ranked = sorted(records, key=significance)
            summary = {'kind': 'identity', 'first': ranked[0].entity, 'last': ranked[-1].entity}
        else:
            summary = {'kind': 'distinct', 'distinct': len({str(v) for v, _ in present})}
        out.append((f.key, summary))
    return Summary(group_key, kind, len(records), tuple(r.key for r in ordered), tuple(out))


def capacity(unit, group_pages=DEFAULT_GROUP_PAGES):
    return group_pages * ROWS_PER_PAGE.get(unit.table_kind, ROWS_PER_PAGE['evidence-landscape'])


def plan_print(unit, profile='focused', group_pages=DEFAULT_GROUP_PAGES):
    """How every record of a unit is treated in print."""
    if profile not in PROFILES:
        raise ValueError(f'Unknown print profile: {profile}')
    if unit.view == 'V1':
        return _plan_limited(unit, 'print', profile)
    if not unit.printed:
        plan = Plan(unit.unit_id, 'print', profile, (), (), tuple(unit.records))
        check_partition(unit, plan)
        return plan
    signal_records = [r for r in unit.records if r.signal is not None]
    free_records = [r for r in unit.records if r.signal is None]
    groups = defaultdict(list)
    for record in signal_records:
        groups[record.signal.key].append(record)
    individual, summaries, group_plans = [], [], []
    limit = capacity(unit, group_pages)
    for key in sorted(groups):
        members = sorted(groups[key], key=significance)
        if profile == 'complete':
            chosen, rest = members, []
        else:
            seen, distinct, repetitive = set(), [], []
            for record in members:
                detail = record.signal.detail
                if detail is not None and detail not in seen:
                    seen.add(detail)
                    distinct.append(record)
                else:
                    repetitive.append(record)
            budget = max(0, limit - len(distinct))
            kept = set(r.key for r in distinct) | set(r.key for r in repetitive[:budget])
            chosen = [r for r in members if r.key in kept]
            rest = [r for r in members if r.key not in kept]
        summary = summarise(rest, unit.fields, key, 'signal-remainder') if rest else None
        individual += chosen
        if summary:
            summaries.append(summary)
        group_plans.append(GroupPlan(key, members[0].signal, len(members), len({m.entity for m in members}),
                                     tuple(chosen), summary))
    free_groups = defaultdict(list)
    for record in free_records:
        free_groups[record.group].append(record)
    for key in sorted(free_groups, key=lambda k: tuple(str(x) for x in k)):
        members = sorted(free_groups[key], key=lambda r: (r.order, r.key))
        if profile == 'complete' or len(members) <= SUMMARY_ROWS:
            individual += members
        else:
            summaries.append(summarise(members, unit.fields, key, 'signal-free'))
    plan = Plan(unit.unit_id, 'print', profile, tuple(individual), tuple(summaries), (), tuple(group_plans))
    check_partition(unit, plan)
    return plan


def plan_screen(unit):
    """How every record of a unit is treated on screen: V2 shows all records; V1 keeps its historical limit."""
    if unit.view == 'V1':
        return _plan_limited(unit, 'screen', None)
    plan = Plan(unit.unit_id, 'screen', None, tuple(unit.records), (), ())
    check_partition(unit, plan)
    return plan


def _plan_limited(unit, medium, profile):
    """A V1 summary view keeps its historical meaning in both media: the first screen_limit records in the unit's own
    order are shown; the rest are referenced (counted, with where to find them), never silently dropped."""
    limit = len(unit.records) if unit.screen_limit is None else unit.screen_limit
    plan = Plan(unit.unit_id, medium, profile, tuple(unit.records[:limit]), (), tuple(unit.records[limit:]))
    check_partition(unit, plan)
    return plan


class AccountingError(AssertionError):
    """A presentation plan broke an accounting invariant."""


def check_partition(unit, plan):
    """I1: individual, grouped and referenced records are disjoint and together are exactly the unit's records."""
    individual = [r.key for r in plan.individual]
    grouped = [k for s in plan.summaries for k in s.record_keys]
    referenced = [r.key for r in plan.referenced]
    every = individual + grouped + referenced
    if len(every) != len(set(every)):
        raise AccountingError(f'{unit.unit_id} {plan.medium}: a record is counted under more than one treatment.')
    if set(every) != {r.key for r in unit.records}:
        raise AccountingError(f'{unit.unit_id} {plan.medium}: treatments do not cover exactly the unit\'s records.')


def accounting(unit, plan):
    """The accounting record for one unit in one medium (data island and QA)."""
    grouped = sum(s.count for s in plan.summaries)
    return {'unit_id': unit.unit_id, 'view': unit.view, 'medium': plan.medium, 'profile': plan.profile,
            'total': len(unit.records), 'individual': len(plan.individual), 'grouped': grouped,
            'referenced': len(plan.referenced), 'groups': len(plan.groups), 'coverage': list(unit.coverage)}


def locations(units, plans):
    """I2: the location set of every record key, per unit, from the plans actually rendered."""
    out = defaultdict(set)
    by_unit = defaultdict(list)
    for plan in plans:
        by_unit[plan.unit_id].append(plan)
    for unit in units:
        for record in unit.records:
            places = out[(unit.unit_id, record.key)]
            places.add('json')
            if record.protected:
                places.add('protected')
        for plan in by_unit[unit.unit_id]:
            shown = plan.treatment()
            for key, treatment in shown.items():
                if treatment == 'referenced':
                    continue
                if plan.medium == 'print':
                    out[(unit.unit_id, key)].add('pdf')
                elif unit.view == 'V1':
                    out[(unit.unit_id, key)].add('html_summary')
                elif treatment == 'individual':
                    out[(unit.unit_id, key)].add('html_detail')
    return dict(out)


def distinct_records(units):
    """I3: a cross-unit total counts distinct record keys (by pointer), never the sum of unit counts."""
    return len({r.pointer or r.key for unit in units for r in unit.records})


def disclosure(unit, screen, printed=None):
    """I5: the disclosure for a unit with grouped or referenced records, or None. It names the view, what is shown
    individually and what is summarised, exactly where the rest is, and any analytical bound as coverage."""
    plans = [p for p in (screen, printed) if p is not None]
    if not any(p.summaries or p.referenced for p in plans):
        return None
    where = []
    if unit.view == 'V1' and unit.html_anchor:
        where.append({'location': 'html_detail', 'anchor': unit.html_anchor, 'label': unit.html_label or unit.html_anchor})
    elif unit.view == 'V2' and unit.html_anchor and printed is not None:
        where.append({'location': 'html_detail', 'anchor': unit.html_anchor, 'label': unit.html_label or unit.html_anchor})
    if unit.pointer:
        where.append({'location': 'json', 'pointer': unit.pointer})
    if any(r.protected for r in unit.records):
        where.append({'location': 'protected'})
    record = {'unit_id': unit.unit_id, 'view': unit.view, 'noun': unit.noun, 'computed': len(unit.records),
              'screen': accounting(unit, screen), 'print': accounting(unit, printed) if printed else None,
              'where': where, 'coverage': list(unit.coverage), 'policy': PRINT_POLICY_VERSION, 'limit_label': unit.limit_label}
    record['text'] = disclosure_text(record)
    return record


def disclosure_text(record):
    """Deterministic wording for a disclosure record (I5)."""
    noun, total = record['noun'], record['computed']
    places = []
    for place in record['where']:
        if place['location'] == 'html_detail':
            places.append(f"{place['label']} in this HTML file")
        elif place['location'] == 'json':
            places.append(f"analysis.json → {place['pointer']}")
        else:
            places.append('source content: protected, local resolution only')
    where = ' and '.join(p for p in places if not p.startswith('source')) or 'analysis.json'
    protected = [p for p in places if p.startswith('source')]
    parts = []
    if record['view'] == 'V1':
        shown = record['screen']['individual']
        bound = record.get('limit_label') or 'historical display limit'
        if shown:
            parts.append(f'Summary view: {shown:,} of {counted(total, noun)} shown ({bound}) · all {total:,}: {where}')
        else:   # the summary states counts or a sentence instead of listing entries
            parts.append(f'Summary view: counts only, no {noun} listed ({bound}) · all {counted(total, noun)}: {where}')
    else:
        printed = record['print']
        if printed and printed['individual'] == 0 and printed['grouped'] == 0:
            parts.append(f"Detailed view, not printed in this profile: {'the' if total == 1 else 'all'} {counted(total, noun)} "
                         f"{'is' if total == 1 else 'are'} listed in {where}")
        elif printed and (printed['grouped'] or printed['referenced']):
            parts.append(f"Detailed view, print: {counted(total, noun)} computed · {printed['individual']:,} printed individually · "
                         + (f"{printed['grouped']:,} summarised below · " if printed['grouped'] else '')
                         + (f"{printed['referenced']:,} not printed · " if printed['referenced'] else '')
                         + f"every row: {where}")
    parts += protected
    parts += [f'Coverage: {c}' for c in record['coverage']]
    return ' · '.join(parts)


def group_checks(checks):
    """Repeated check-ledger entries aggregated by (check, applicability, execution, reason); moved unchanged from the
    M3 projection so every workflow groups its ledger the same way. Accepts check objects or dicts."""
    def get(check, name):
        return check.get(name) if isinstance(check, dict) else getattr(check, name)
    def plain(value):
        return str(getattr(value, 'value', value))
    groups = defaultdict(list)
    for check in checks:
        groups[(get(check, 'check_id'), plain(get(check, 'applicability')), plain(get(check, 'execution')),
                get(check, 'reason'))].append(get(check, 'scope'))
    rows = []
    for (check, applicability, execution, reason), scopes in groups.items():
        unique = list(dict.fromkeys(scopes))
        summary = ', '.join(unique[:3]) + (' ...' if len(unique) > 3 else '')
        rows.append([check.replace('_', ' '), f'{len(scopes)} checks; {len(unique)} scopes: ' + summary, applicability,
                     execution, reason or 'Completed within declared scope'])
    return rows


@dataclass(frozen=True)
class FindingRef:
    """A finding as the finding index presents it: workflow adapters fill it from recorded fields only."""
    key: str
    title: str
    severity: Optional[str]
    pointer: str
    order: int
    scope: str = ''
    trigger: str = ''
    interpretation: str = ''
    count: Optional[int] = None
    measure: Optional[float] = None
    refs: tuple = ()


INDEX_FIELDS = (Field('title', 'Finding', 'text'), Field('count', 'Affected', 'quantity'),
                Field('scope', 'Scope', 'scope'))


def finding_unit(findings, unit_id='finding-index', pointer='/findings', noun='findings'):
    """The finding index (R1): one V2 unit whose signal groups are the distinct findings. A finding's title is its
    recorded detail, so findings that read differently are never merged into one summary."""
    records = tuple(Record(f.key, f.title, {'title': f.title, 'count': f.count, 'scope': f.scope}, f.order, f.pointer,
                           Signal(f.trigger or f.title, f.severity, f.scope, f.trigger, f.interpretation, f.measure, f.title))
                    for f in findings)
    return Unit(unit_id, 'Findings', 'V2', INDEX_FIELDS, records, noun=noun, pointer=pointer, table_kind='register-portrait')


def format_value(value):
    """Display a stored value without changing it: counts get separators, other numbers six significant digits."""
    if value is None:
        return 'Unavailable'
    if isinstance(value, bool):
        return 'Yes' if value else 'No'
    if isinstance(value, int):
        return f'{value:,}'
    if isinstance(value, float):
        return format(value, ',.6g') if abs(value) >= 1000 else format(value, '.6g')
    return str(value)


def counted(count, noun):
    """A count with its noun in the right number: the unit nouns are plural phrases ("columns", "column rules")."""
    if count == 1 and noun.endswith('s'):
        noun = noun[:-1]
    return f'{count:,} {noun}'


def humanise(code):
    return str(code).replace('_', ' ').strip().capitalize()


def group_label(group, noun):
    signal = group.signal
    parts = [signal.severity or 'Flag', signal.label or humanise(signal.code)]
    if signal.scope:
        parts.append(signal.scope)
    if signal.interpretation:
        parts.append(humanise(signal.interpretation).lower())
    count = counted(group.total, noun) + (f' ({group.entities:,} distinct)' if group.entities != group.total else '')
    return ' · '.join(parts) + f' — {count}'


def summary_cells(summary, fields):
    by_key = dict(summary.fields)
    cells = []
    for f in fields:
        s = by_key[f.key]
        if s['kind'] == 'range':
            if s['with_value']:
                text = (f"{format_value(s['min'])} ({s['min_entity']}) to {format_value(s['max'])} ({s['max_entity']})"
                        if s['min'] != s['max'] else f"{format_value(s['min'])} for all")
            else:
                text = 'Unavailable'
            if s['without_value'] and s['with_value']:
                text += f"; unavailable for {s['without_value']:,}"
        elif s['kind'] in ('tally', 'scopes'):
            text = ' · '.join(f'{value}: {count:,}' for value, count in s['counts']) or 'Unavailable'
        elif s['kind'] == 'identity':
            text = s['first'] if s['first'] == s['last'] else f"{s['first']} … {s['last']}"
        else:
            text = f"{s['distinct']:,} distinct values"
        cells.append(text)
    return cells


def anchor(unit, record, position=None):
    """Index-based row anchor (plan F.5): the record's position within its unit, so a column that appears under
    several rules of one unit still gets one id per row. Never built from a column name."""
    if position is None:
        position = {r.key: i for i, r in enumerate(unit.records)}
    return f'ev-{unit.unit_id}-{position[record.key]}'


def render_unit(unit, screen, printed=None, *, entity_label='Name', json_hint=None, disclosure_text_override=None, name=None,
                own_anchor=False):
    """Lay a unit out for the shared evidence macro. Printed rows (or, without a print plan, the screen rows) become
    ordinary HTML; when the screen shows records that print does not show individually, every screen record also goes
    into a data island the report script draws in pages."""
    plan = printed or screen
    position = {r.key: i for i, r in enumerate(unit.records)}
    fields = [{'key': f.key, 'label': f.label, 'numeric': f.kind == 'quantity', 'concept': f.concept} for f in unit.fields]
    def row(record):
        return {'type': 'record', 'entity': record.entity, 'anchor': anchor(unit, record, position),
                'cells': [format_value(record.values.get(f.key)) for f in unit.fields]}
    rows = []
    shown = {r.key for r in plan.individual}
    grouped_free = [s for s in plan.summaries if s.kind == 'signal-free']
    for group in plan.groups:
        rows.append({'type': 'group', 'label': group_label(group, unit.noun)})
        rows += [row(r) for r in group.individual]
        if group.summary:
            rows.append({'type': 'summary', 'label': f'{counted(group.summary.count, unit.noun).replace(" ", " more ", 1)}, summarised',
                         'cells': summary_cells(group.summary, unit.fields)})
    in_groups = {r.key for g in plan.groups for r in g.individual}
    rows += [row(r) for r in plan.individual if r.key not in in_groups and r.key in shown]
    for summary in grouped_free:
        label = ' · '.join(str(x) for x in summary.group_key) or unit.noun
        rows.append({'type': 'summary', 'label': f'{counted(summary.count, unit.noun)} without findings ({label}), summarised',
                     'cells': summary_cells(summary, unit.fields)})
    screen_only = printed is not None and {r.key for r in screen.individual} - {r.key for r in printed.individual}
    island = None
    if screen_only:
        island = {'noun': unit.noun, 'numeric': [f.kind == 'quantity' for f in unit.fields],
                  'rows': [{'entity': r.entity, 'anchor': anchor(unit, r, position),
                                               'cells': [format_value(r.values.get(f.key)) for f in unit.fields]}
                                              for r in screen.individual]}
    record = disclosure(unit, screen, printed)
    table_id = f'dt-{unit.unit_id}'
    # A unit's element id is the place its disclosures point to, unless that place is another unit (own_anchor): a
    # summary or signal table that points to the complete table keeps an id of its own, so no id repeats.
    return {'anchor': table_id + '-unit' if own_anchor or not unit.html_anchor else unit.html_anchor, 'table_id': table_id, 'title': unit.title,
            'name': unit.title or name,   # the accessible name of the table's search and paging controls
            'entity_label': entity_label, 'fields': fields, 'rows': rows, 'island': island,
            'filterable': unit.view == 'V2' and len(unit.records) > 1, 'screen_total': f'{len(screen.individual):,}',
            'print_hidden': printed is not None and not printed.individual and not printed.summaries,
            'noun': unit.noun, 'json_hint': json_hint or (f'analysis.json → {unit.pointer}' if unit.pointer else 'analysis.json'),
            'disclosure': (disclosure_text_override or record['text']) if record else None, 'disclosure_record': record,
            'coverage': [f'Coverage: {c}' for c in unit.coverage] if not record else []}
