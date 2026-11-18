"""Shared presentation helpers for the M3, M4, M5, M6, M7 and M9 reports (Report Experience Stages 4–6). Presentation only.

Their topic tables are V1 summary views capped by the historical display limits recorded with the result
(PresentationLimits); those limits keep their meaning (plan G.5). For every capped table this module adds:
- a disclosure worded by the shared contract ("Summary view: 20 of 412 rows shown (historical display limit) · ...");
- a V2 complete table in the appendix, listed in full on screen and printed in the complete print profile;
- in the focused profile, a printed table of the rows beyond the limit that a recorded finding refers to, grouped and
  budgeted by report_print_v1 (plan R1/R2, acceptance gate 2), so no finding's evidence is left out of print.
"""
import re

from datatrust.report_layout import Field, Record, Signal, Unit, disclosure, plan_print, plan_screen, render_unit


def slug(text):
    return re.sub(r'[^a-z0-9]+', '-', str(text).lower()).strip('-')[:60] or 'table'


def labelled(v):
    """Nested recorded values as labelled text ("format: csv · role: dataset"), never as raw JSON. Nothing is dropped:
    empty values read "none", unset values "not set"."""
    if v is None:
        return 'not set'
    if isinstance(v, bool):
        return 'yes' if v else 'no'
    if isinstance(v, float):
        return format(v, '.7g')
    if isinstance(v, dict):
        return ' · '.join(f"{str(k).replace('_', ' ')}: {labelled(x)}" for k, x in v.items()) or 'none'
    if isinstance(v, (list, tuple)):
        parts = [labelled(x) for x in v]
        return ('; '.join(f'({x})' for x in parts) if any(isinstance(x, dict) for x in v) else ', '.join(parts)) or 'none'
    return str(v)


# Every opaque reference kind the M6, M7 and M9 analyses define (their `opaque(kind, ...)` helpers and hashed record
# ids). Each resolves only through the private manifest and the unchanged sources.
REFERENCE_KINDS = ('annotation', 'category', 'evidence', 'field', 'group_key', 'image', 'item', 'label', 'model_token_id',
                   'role', 'split', 'token')
REFERENCE = re.compile(r'\b(?:' + '|'.join(REFERENCE_KINDS) + r')_[0-9a-f]{16,}\b')


def has_references(value):
    """Whether a recorded value carries opaque references whose source content is held in the private manifest (V4)."""
    return bool(REFERENCE.search(labelled(value)))


def finding_signal(finding, scope=''):
    """The recorded finding a row is evidence for, as a print signal: grouped only with rows of the same severity,
    scope, finding code and evidence type (R2a); labelled with the finding's own title."""
    # Workflows without finding codes (M5) are keyed by the finding's recorded title, so distinct findings never merge.
    code = str(finding.get('code') or finding.get('family') or finding.get('title') or finding.get('id') or 'finding')
    return Signal(code, finding.get('severity') or finding.get('priority'), str(scope or ''), code,
                  str(finding.get('evidence_type') or finding.get('meaning') or ''), label=finding.get('title'))


def _kind(values):
    numbers = [v for v in values if v is not None]
    return 'quantity' if numbers and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in numbers) else 'text'


def capped_tables(tables, profile_name, *, limit_label='historical display limit', protected=False, section_label='Complete tables',
                  referenced=None):
    """({table key: disclosure text}, [rendered complete units]) for tables whose rows were capped. limit_label names
    the bound in the disclosure; protected marks rows whose source content is held only in the private manifest (V4).

    A table may carry `signals`, aligned with `all_rows`: the finding signal of each row, or None. When `referenced`
    (a dict) is given, it receives, per table key, a rendered unit of the rows beyond the summary view that a finding
    refers to, printed in the focused profile. The complete profile prints every row in the complete table instead, so
    no row is printed twice (R5)."""
    disclosures, complete, seen = {}, [], set()
    for table in tables:
        rows, shown = table.get('all_rows') or [], len(table.get('rows') or [])
        if len(rows) <= shown:
            continue
        uid = 'complete-' + slug(table.get('topic') or table['title'])
        while uid in seen:
            uid += '-2'
        seen.add(uid)
        columns = list(table['columns'])
        fields = tuple(Field(f'c{i}', label, 'text') for i, label in enumerate(columns[1:]))
        records = tuple(Record(f'{uid}:{n}', str(row[0]), {f'c{i}': row[i + 1] for i in range(len(columns) - 1)}, n,
                               table.get('pointer') or '/profile', protected=table.get('protected', protected)) for n, row in enumerate(rows))
        label = f'“{section_label}: {table["title"]}”'
        summary = Unit(uid + '-summary', table['title'], 'V1', fields, records, noun=table.get('noun') or 'rows', pointer=table.get('pointer') or '',
                       html_anchor=uid, html_label=label, screen_limit=shown, limit_label=limit_label)
        record = disclosure(summary, plan_screen(summary), plan_print(summary, profile_name))
        detail = Unit(uid, table['title'], 'V2', fields, records, noun=table.get('noun') or 'rows', pointer=table.get('pointer') or '',
                      html_anchor=uid, html_label=label, printed=profile_name == 'complete')
        printed_rows = table.get('print_rows')
        if printed_rows is not None and printed_rows != shown:   # a summary view whose print shows fewer rows than the screen
            record['text'] += f' · print shows the first {printed_rows:,}'
        disclosures[table.get('topic') or table['title']] = record['text']
        complete.append(render_unit(detail, plan_screen(detail), plan_print(detail, profile_name), entity_label=columns[0]))
        signals = table.get('signals') or []
        in_print = table.get('print_rows', shown)
        extra = [(n, rows[n], signals[n]) for n in range(in_print, len(rows)) if n < len(signals) and signals[n] is not None]
        if referenced is not None and extra and profile_name != 'complete':
            rid = uid.replace('complete-', 'referenced-', 1)
            kinds = tuple(Field(f'c{i}', label, _kind([row[i + 1] for _, row, _ in extra])) for i, label in enumerate(columns[1:]))
            chosen = tuple(Record(f'{rid}:{n}', str(row[0]), {f'c{i}': row[i + 1] for i in range(len(columns) - 1)}, n,
                                  table.get('pointer') or '/profile', signal=signal, protected=table.get('protected', protected))
                           for n, row, signal in extra)
            unit = Unit(rid, f'{table["title"]}: rows referenced by findings beyond the summary view', 'V2', kinds, chosen,
                        noun=table.get('noun') or 'rows', pointer=table.get('pointer') or '', html_anchor=uid, html_label=label)
            referenced[table.get('topic') or table['title']] = render_unit(unit, plan_screen(unit), plan_print(unit, profile_name),
                                                                          entity_label=columns[0], own_anchor=True)
    return disclosures, complete


def finding_index(findings):
    """Every finding, in recorded order, with its priority and scope: the index never applies a display limit."""
    out = []
    for i, f in enumerate(findings or []):
        if not isinstance(f, dict) or f.get('code') == 'no_major_issues':
            continue
        scope = f.get('scope') or f.get('population') or ''
        count = f.get('affected_count')
        effect = (f'{count:,} affected' if isinstance(count, int) else '') + (f' · {scope}' if scope and not isinstance(scope, dict) else '')
        out.append({'anchor': f'finding-{i}', 'index': i, 'title': f.get('title'), 'severity': f.get('severity') or f.get('priority'),
                    'effect': effect.strip(' ·') or str(f.get('evidence_type') or '').replace('_', ' ')})
    return out
