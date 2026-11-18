"""Projection of completed tabular results (classification, regression, unlabeled profiling) for the shared report layout.

Presentation only. Every unit is built from the completed result dict; nothing is analysed or recomputed. A column's
signals come only from what the analysis recorded:
- classification: the recorded feature-usability contributor rules (guidance block), the recorded severe-missingness
  list and leakage details, and the per-column flag fields;
- regression and unlabeled profiling: each finding's evidence references and the affected columns those evidence
  records name, cross-checked against the per-column flag fields where a finding is about a flag.
Print treatment then follows report_layout (report_print_v1): signal tables by family, evidence-appropriate summaries
for columns without signals, and the complete column table on screen (printed in the complete profile).
"""
import re
from collections import OrderedDict

from datatrust.report_layout import (
    Field, Record, Signal, Unit, group_checks, humanise, plan_print, plan_screen, render_unit,
)

POINTER = '/profile/columns'
APPENDIX = 'ev-columns'

F = {
    'role': Field('role', 'Role', 'category'),
    'dtype': Field('dtype', 'Type', 'category'),
    'non_null': Field('non_null', 'Non-null', 'quantity'),
    'missing': Field('missing', 'Missing', 'quantity', 'missingness'),
    'missing_pct': Field('missing_pct', 'Missing %', 'quantity', 'missingness'),
    'unique': Field('unique', 'Distinct', 'quantity', 'cardinality'),
    'unique_pct': Field('unique_pct', 'Distinct %', 'quantity', 'cardinality'),
    'top_value': Field('top_value', 'Most common value', 'text'),
    'top_share': Field('top_share', 'Top share %', 'quantity'),
    'outliers': Field('outliers', 'Outside IQR fences', 'quantity', 'iqr_outliers'),
    'outlier_pct': Field('outlier_pct', 'Outside fences %', 'quantity', 'iqr_outliers'),
    'min': Field('min', 'Min', 'quantity'), 'q1': Field('q1', 'Q1', 'quantity', 'quartiles'),
    'median': Field('median', 'Median', 'quantity', 'quartiles'), 'q3': Field('q3', 'Q3', 'quantity', 'quartiles'),
    'max': Field('max', 'Max', 'quantity'), 'zero': Field('zero', 'Zero', 'quantity'),
    'negative': Field('negative', 'Negative', 'quantity'), 'non_finite': Field('non_finite', 'Non-finite', 'quantity'),
    'finite': Field('finite', 'Finite', 'quantity'),
    'missing_cell': Field('missing_cell', 'Missing', 'quantity', 'missingness'),
    'unique_cell': Field('unique_cell', 'Distinct', 'quantity', 'cardinality'),
    'outlier_cell': Field('outlier_cell', 'Outside IQR fences', 'quantity', 'iqr_outliers'),
    'flags': Field('flags', 'Flags', 'text'),
}

# (family, heading, fields, measure used for significance order)
FAMILIES = (
    ('missingness', 'Missing values', ('missing', 'missing_pct'), 'missing_pct'),
    ('outliers', 'Values outside the 1.5 × IQR fences', ('outliers', 'outlier_pct', 'q1', 'q3', 'min', 'max', 'zero', 'negative'), 'outlier_pct'),
    ('variation', 'Constant and near-constant values', ('unique', 'top_value', 'top_share'), 'top_share'),
    ('cardinality', 'High cardinality', ('unique', 'unique_pct'), 'unique_pct'),
    ('nonfinite', 'Non-finite values', ('non_finite', 'finite'), 'non_finite'),
    ('other', 'Other column findings', ('missing_pct', 'unique', 'top_share', 'outlier_pct'), None),
)
FAMILY = {f[0]: f for f in FAMILIES}
CHECK_FAMILY = {'missingness': 'missingness', 'numeric_outliers': 'outliers', 'column_variation': 'variation',
                'categorical_cardinality': 'cardinality', 'numeric_summary': 'nonfinite'}
FLAG_FOR_CODE = {'constant_fields': 'constant', 'near_constant_fields': 'near_constant',
                 'high_cardinality_categoricals': 'high_cardinality'}
RULE_FAMILY = {'missing_rate_100': 'missingness', 'missing_rate_50': 'missingness', 'missing_rate_25': 'missingness',
               'constant': 'variation', 'near_constant': 'variation', 'high_cardinality': 'cardinality',
               'iqr_rate_10': 'outliers', 'iqr_rate_5': 'outliers'}
RULE_FINDING = {'missing_rate_100': 'severe_feature_missingness', 'missing_rate_50': 'severe_feature_missingness',
                'constant': 'constant_fields', 'near_constant': 'near_constant_fields',
                'high_cardinality': 'high_cardinality_categoricals', 'iqr_rate_10': 'numeric_outlier_concentration',
                'iqr_rate_5': 'numeric_outlier_concentration'}
ITEM_FAMILY = {'numeric_outlier_concentration': 'outliers', 'constant_fields': 'variation', 'near_constant_fields': 'variation',
               'high_cardinality_categoricals': 'cardinality', 'fully_missing_columns': 'missingness',
               'column_missingness': 'missingness', 'high_missingness': 'missingness', 'severe_feature_missingness': 'missingness',
               'possible_target_leakage': 'leakage', 'leakage_review_prompts': 'leakage'}


def _pct(count, rate):
    if count is None:
        return None
    return f'{count:,} ({rate}%)' if rate is not None else f'{count:,}'


def column_values(c):
    s = c.get('numeric_summary') or {}
    if c.get('top_value_hidden'):
        top = 'Withheld (high cardinality)'
    elif c.get('top_value_is_missing'):
        top = '(missing)'
    else:
        top = None if c.get('top_value') is None else str(c.get('top_value'))
    flags = [label for key, label in (('constant', 'Constant'), ('near_constant', 'Near constant'),
                                      ('high_cardinality', 'High cardinality')) if c.get(key)]
    return {'role': c.get('role'), 'dtype': c.get('dtype'), 'non_null': c.get('non_null_count'),
            'missing': c.get('missing_count'), 'missing_pct': c.get('missing_rate'),
            'unique': c.get('unique_count'), 'unique_pct': c.get('unique_rate'), 'top_value': top,
            'top_share': c.get('top_value_rate'), 'outliers': c.get('outlier_count'), 'outlier_pct': c.get('outlier_rate'),
            'min': s.get('min'), 'q1': s.get('q1'), 'median': s.get('median'), 'q3': s.get('q3'), 'max': s.get('max'),
            'zero': s.get('zero_count'), 'negative': s.get('negative_count'), 'non_finite': s.get('non_finite_count'),
            'finite': c.get('finite_count'),
            'missing_cell': _pct(c.get('missing_count'), c.get('missing_rate')),
            'unique_cell': _pct(c.get('unique_count'), c.get('unique_rate')),
            'outlier_cell': _pct(c.get('outlier_count'), c.get('outlier_rate')) if c.get('outlier_count') is not None else None,
            'flags': ' · '.join(flags) or None}


def _measure(values, family):
    key = FAMILY[family][3]
    value = values.get(key) if key else None
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def classification_signals(value, columns):
    """{(family, column): Signal} from the recorded contributor rules, severe-missingness list and flag fields."""
    from datatrust.guidance import RULE_LABELS
    by_label = {label: rule for rule, label in RULE_LABELS.items()}
    findings = {f.get('code'): f for f in value.get('findings', [])}
    signals = {}
    def add(family, column, rule, label):
        finding = findings.get(RULE_FINDING.get(rule))
        signal = Signal(finding.get('code') if finding else rule, finding.get('severity') if finding else None, '', rule,
                        'finding' if finding else 'scoring rule', _measure(columns[column], family), None,
                        (finding.get('title') + ' · ' + label) if finding else label)
        current = signals.get((family, column))
        if current is None or signal.rank < current.rank:
            signals[(family, column)] = signal
    contributors = (((value.get('guidance') or {}).get('scoring') or {}).get('feature_usability') or {}).get('contributors')
    if contributors is not None:
        for entry in contributors:
            if entry.get('column') not in columns:
                continue
            for rule in entry.get('rules', []):
                rule_id = by_label.get(rule.get('rule'))
                if rule_id in RULE_FAMILY:
                    add(RULE_FAMILY[rule_id], entry['column'], rule_id, rule['rule'])
    else:   # results recorded before the guidance block: the flag fields alone
        for name, values in columns.items():
            for flag, rule in (('constant', 'constant'), ('near_constant', 'near_constant'), ('high_cardinality', 'high_cardinality')):
                if values['_flags'].get(flag):
                    add(RULE_FAMILY[rule], name, rule, RULE_LABELS[rule])
    for name in (value.get('profile') or {}).get('severe_missing_columns') or []:
        if name in columns and ('missingness', name) not in signals:
            add('missingness', name, 'missing_rate_50', RULE_LABELS['missing_rate_50'])
    return signals


def evidence_signals(value, columns):
    """{(family, column): Signal} from each finding's evidence references and the columns those records name."""
    evidence = {e.get('id'): e for e in value.get('evidence', []) if isinstance(e, dict)}
    signals = {}
    for finding in value.get('findings', []):
        refs = finding.get('evidence_refs') or []
        for ref in refs if isinstance(refs, list) else [refs]:
            record = evidence.get(ref)
            if not record:
                continue
            family = CHECK_FAMILY.get(record.get('check_id'), 'other')
            flag = FLAG_FOR_CODE.get(finding.get('code'))
            named = record.get('affected_columns') or []
            if not named and flag:   # flag findings whose evidence record names no columns: the recorded flag fields
                regression = (value.get('task') or {}).get('kind') == 'regression'
                named = [n for n, v in columns.items() if v['_flags'].get(flag) and not (regression and v['role'] == 'target')]
            for column in named:
                if column not in columns or (flag and not columns[column]['_flags'].get(flag)):
                    continue
                thresholds = record.get('thresholds') or {}
                trigger = ' '.join([str(record.get('method') or '')] + [f'{k} {v}' for k, v in sorted(thresholds.items())]).strip()
                signal = Signal(finding.get('code', ''), finding.get('severity'), '', trigger,
                                str(finding.get('evidence_type') or ''), _measure(columns[column], family), None,
                                finding.get('title'))
                current = signals.get((family, column))
                if current is None or signal.rank < current.rank:
                    signals[(family, column)] = signal
    return signals


def column_units(value, profile_name):
    """Signal tables, the summary of columns without signals, the complete table and the numeric detail table."""
    columns_list = (value.get('profile') or {}).get('columns') or []
    columns = OrderedDict()
    for c in columns_list:
        values = column_values(c)
        values['_flags'] = {k: bool(c.get(k)) for k in ('constant', 'near_constant', 'high_cardinality')}
        columns[c['name']] = values
    legacy = value.get('methodology_id') == 'classification_legacy_2026_08_13'
    signals = classification_signals(value, columns) if legacy else evidence_signals(value, columns)
    order = {name: i for i, name in enumerate(columns)}
    complete = profile_name == 'complete'
    units = []
    signalled = {column for _, column in signals}
    for family, heading, keys, _ in FAMILIES:
        members = [(column, s) for (fam, column), s in signals.items() if fam == family]
        if not members:
            continue
        fields = tuple(F[k] for k in keys)
        records = tuple(Record(f'{family}:{column}', column, {k: columns[column][k] for k in keys}, order[column],
                               f'{POINTER}/{order[column]}', s) for column, s in sorted(members, key=lambda m: order[m[0]]))
        units.append(Unit(f'col-{family}', heading, 'V2', fields, records, noun='columns', pointer=POINTER,
                          html_anchor=f'ev-col-{family}', html_label=f'“{heading}”', printed=not complete))
    quiet = [name for name in columns if name not in signalled]
    if quiet:
        keys = ('non_null', 'missing_pct', 'unique', 'top_share', 'outlier_pct')
        records = tuple(Record(f'quiet:{name}', name, {k: columns[name][k] for k in keys}, order[name], f'{POINTER}/{order[name]}',
                               None, (str(columns[name]['role']), str(columns[name]['dtype']))) for name in quiet)
        units.append(Unit('col-quiet', 'Columns without findings or flags', 'V2', tuple(F[k] for k in keys), records,
                          noun='columns', pointer=POINTER, html_anchor=APPENDIX, html_label='“All columns”',
                          printed=not complete))
    assess = assessability(value, columns_list)
    if assess:
        records = tuple(Record(f'assess:{name}', name, {'reason': text}, order[name], f'{POINTER}/{order[name]}',
                               Signal('not_assessable', None, '', checks, 'not assessable', None, text, 'Not assessable for this column'))
                        for name, (text, checks) in assess.items() if name in order)
        units.append(Unit('col-assessability', 'Checks not assessable for a column', 'V2', (Field('reason', 'Recorded reason', 'text'),),
                          records, noun='columns', pointer='/checks', html_anchor='ev-col-assessability',
                          html_label='“Checks not assessable for a column”'))
    keys = ('role', 'dtype', 'non_null', 'missing_cell', 'unique_cell', 'top_value', 'top_share', 'outlier_cell', 'flags')
    every = tuple(Record(f'all:{name}', name, {k: v[k] for k in keys}, order[name], f'{POINTER}/{order[name]}')
                  for name, v in columns.items())
    units.append(Unit('col-all', 'All columns', 'V2', tuple(F[k] for k in keys), every, noun='columns', pointer=POINTER,
                      html_anchor=APPENDIX, html_label='“All columns”', printed=complete))
    keys = ('min', 'q1', 'median', 'q3', 'max', 'zero', 'negative', 'non_finite') + (() if legacy else ('finite',))
    numeric = tuple(Record(f'num:{c["name"]}', c['name'], {k: columns[c['name']][k] for k in keys}, order[c['name']],
                           f'{POINTER}/{order[c["name"]]}/numeric_summary')
                    for c in columns_list if c.get('is_numeric') and (not legacy or c.get('role') == 'feature'))
    if numeric:
        units.append(Unit('col-numeric', 'Numeric summaries', 'V2', tuple(F[k] for k in keys), numeric, noun='numeric columns',
                          pointer=POINTER, html_anchor='ev-col-numeric', html_label='“Numeric summaries”', printed=complete))
    return units, signals, columns


def assessability(value, columns_list):
    """{column: (reasons, check ids)} for per-column checks that were blocked, failed or not run, and numeric summaries
    with no finite observation: recorded states, worded for display."""
    from datatrust.report_format import _report_label
    names = {c['name'] for c in columns_list}
    reasons = OrderedDict()
    for c in columns_list:
        if c.get('is_numeric') and c.get('numeric_summary') is not None and c.get('finite_count') == 0:
            reasons.setdefault(c['name'], []).append(('numeric_summary', 'Summary unavailable: no finite observations.'))
    for check in value.get('checks') or []:
        scope = check.get('scope')
        if scope not in names or (check.get('applicability') == 'applicable' and check.get('execution') == 'completed'):
            continue
        label = str(check.get('check_id', '')).replace('_', ' ').capitalize()
        state = ' / '.join(_report_label(x) for x in (check.get('applicability'), check.get('execution')) if x)
        detail = f'{label} {state}' + (f': {_report_label(check["reason"])}' if check.get('reason') else '') + '.'
        reasons.setdefault(scope, []).append((check.get('check_id'), detail))
    return OrderedDict((name, (' '.join(t for _, t in items), ' '.join(sorted(c for c, _ in items))))
                       for name, items in reasons.items())


def entity_prefix(line, names):
    """The column a recorded observation line is about ("name: ..."), the longest matching name, or None. Each
    ": " in the line is a candidate boundary, so names that themselves contain ": " still match."""
    found, start = None, 0
    while (position := line.find(': ', start)) >= 0:
        if line[:position] in names:
            found = line[:position]
        start = position + 1
    return found


def guidance_observed(value, plans_by_unit, columns, profile_name):
    """Per guidance item: the observation lines printed as text, and the per-column lines whose facts are already
    printed for that column (R5), which become a screen table with a disclosure."""
    items = ((value.get('guidance') or {}).get('items') or {})
    complete = profile_name == 'complete'
    in_print = {}   # entities a family's print plan shows, individually or inside a summary of stored values
    for unit_id, (unit, _, printed) in plans_by_unit.items():
        entity = {r.key: r.entity for r in unit.records}
        in_print[unit_id] = {r.entity for r in printed.individual} | {entity[k] for s in printed.summaries for k in s.record_keys}
    leakage = {d.get('column') for d in (value.get('profile') or {}).get('leakage_details') or []}
    out = {}
    for key, item in items.items():
        family = ITEM_FAMILY.get(item.get('catalogue')) or ITEM_FAMILY.get(key)
        lines, moved = [], []
        for index, line in enumerate(item.get('observed') or []):
            name = entity_prefix(line, columns)
            covered = False
            if name and family:
                if family == 'leakage':
                    covered = name in leakage
                elif complete:
                    covered = True
                else:
                    covered = name in in_print.get(f'col-{family}', set())
            (moved if covered else lines).append((index, name, line))
        unit = None
        if moved:
            where = ('the leakage-name review table' if family == 'leakage' else
                     'the “All columns” and “Numeric summaries” tables' if complete else
                     f'the “{FAMILY[family][1]}” table (individually or in its summary)')
            records = tuple(Record(f'obs:{key}:{i}', name, {'observation': line}, i, f'/guidance/items/{key}/observed/{i}')
                            for i, name, line in moved)
            u = Unit('obs-' + re.sub(r'[^A-Za-z0-9]+', '-', key).strip('-'), None, 'V2', (Field('observation', 'Observation', 'text'),), records,
                     noun='observations', pointer=f'/guidance/items/{key}/observed', printed=False)
            text = (f'{len(moved):,} per-column observations repeat values printed in {where}; all are listed here on screen '
                    f'and in analysis.json → /guidance/items/{key}/observed.')
            unit = render_unit(u, plan_screen(u), plan_print(u, profile_name), entity_label='Column', disclosure_text_override=text,
                               name=f'{humanise(key)} observations')
        out[key] = {'lines': [line for _, _, line in lines], 'moved': unit}
    return out


def contributors_unit(value, profile_name):
    from datatrust.guidance import RULE_LABELS
    by_label = {label: rule for rule, label in RULE_LABELS.items()}
    contributors = (((value.get('guidance') or {}).get('scoring') or {}).get('feature_usability') or {}).get('contributors')
    if not contributors:
        return None
    names = [c['name'] for c in (value.get('profile') or {}).get('columns') or []]
    order = {name: i for i, name in enumerate(names)}
    records = []
    for entry in contributors:
        for rule in entry.get('rules', []):
            rule_id = by_label.get(rule.get('rule'), rule.get('rule'))
            records.append(Record(f'{entry["column"]}:{rule_id}', entry['column'], {'points': rule.get('points')},
                                  order.get(entry['column'], len(order)), f'/guidance/scoring/feature_usability/contributors',
                                  Signal(rule_id, None, '', rule_id, 'scoring rule', rule.get('points'), None, rule.get('rule'))))
    unit = Unit('contributors', None, 'V2', (Field('points', 'Points', 'quantity'),), tuple(records), noun='column rules',
                pointer='/guidance/scoring/feature_usability/contributors', table_kind='register-portrait')
    return render_unit(unit, plan_screen(unit), plan_print(unit, profile_name), entity_label='Column',
                       name='feature-usability contributors')


def checks_view(value, profile_name):
    checks = value.get('checks') or []
    grouped = group_checks(checks)
    detail = None
    if len(grouped) < len(checks):
        from datatrust.report_format import _report_label, _report_value
        def reason(c):   # the legacy ledger's "Reason / exclusions" wording
            text = _report_label(c['reason']) if c.get('reason') else ''
            if c.get('exclusions'):
                text += ('; ' if text else '') + 'Exclusions: ' + _report_value(c['exclusions'])
            return text or 'No exclusions'
        fields = (Field('scope', 'Scope', 'scope'), Field('applicability', 'Applicable', 'category'),
                  Field('execution', 'Execution', 'category'), Field('reason', 'Reason / exclusions', 'text'))
        records = tuple(Record(f'check:{i}', _report_label(c.get('check_id', '')),
                               {'scope': c.get('scope'), 'applicability': _report_label(c.get('applicability')),
                                'execution': _report_label(c.get('execution')), 'reason': reason(c)}, i, f'/checks/{i}')
                        for i, c in enumerate(checks))
        unit = Unit('checks', None, 'V2', fields, records, noun='checks', pointer='/checks', printed=profile_name == 'complete')
        detail = render_unit(unit, plan_screen(unit), plan_print(unit, profile_name), entity_label='Check', name='the check ledger')
    return {'grouped': grouped, 'detail': detail, 'total': len(checks)}


def candidates_view(value, profile_name):
    candidates = ((value.get('contextual') or {}).get('candidates')) or []
    if not candidates:
        return None
    fields = (Field('rows', 'Rows', 'quantity'), Field('rate', 'Rate %', 'quantity'), Field('rule', 'Rule', 'category'))
    records = tuple(Record(f'cand:{i}', f'{c.get("column")} = {c.get("value")}', {'rows': c.get('rows'), 'rate': c.get('rate'),
                                                                               'rule': c.get('rule')}, i, f'/contextual/candidates/{i}',
                           Signal('suggested_code', None, '', str(c.get('kind') or ''), 'suggestion, not applied', c.get('rows'),
                                  None, 'Suggested code (not applied) · ' + str(c.get('kind') or '').replace('_', ' ')))
                    for i, c in enumerate(candidates))
    unit = Unit('candidates', None, 'V2', fields, records, noun='suggested codes', pointer='/contextual/candidates',
                table_kind='register-portrait')
    return render_unit(unit, plan_screen(unit), plan_print(unit, profile_name), entity_label='Column = value', name='suggested codes')


def unsearched_view(value, profile_name):
    names = (((value.get('contextual') or {}).get('dependency_search') or {}).get('unsearched_features')) or []
    if not names:
        return None
    records = tuple(Record(f'uns:{i}', n, {}, i, f'/contextual/dependency_search/unsearched_features/{i}') for i, n in enumerate(names))
    unit = Unit('unsearched', None, 'V2', (), records, noun='features', pointer='/contextual/dependency_search/unsearched_features',
                printed=profile_name == 'complete')
    shown = names if len(names) <= 3 else None
    text = (f'{len(names):,} features were not searched within the limits (from {names[0]} to {names[-1]} in source order); '
            'all are listed here on screen and in analysis.json → /contextual/dependency_search/unsearched_features.')
    rendered = render_unit(unit, plan_screen(unit), plan_print(unit, profile_name), entity_label='Feature', name='unsearched features',
                           disclosure_text_override=text)
    return {'count': len(names), 'names': shown, 'unit': None if shown else rendered}


def headers_view(value, profile_name):
    mapping = (value.get('parsing') or {}).get('header_mapping') or []
    if not mapping:
        return None
    dtypes = (value.get('parsing') or {}).get('dtypes') or {}
    fields = (Field('position', 'Position', 'quantity'), Field('original', 'Original header', 'text'),
              Field('type', 'Inferred type', 'category'))
    records = []
    for i, h in enumerate(mapping):
        renamed = (h.get('original') or '') != (h.get('resolved') or '')
        records.append(Record(f'hdr:{i}', str(h.get('resolved') or 'unavailable'),
                              {'position': h.get('position'), 'original': h.get('original') or 'Empty header',
                               'type': dtypes.get(h.get('resolved'), 'unavailable')}, i, f'/parsing/header_mapping/{i}',
                              Signal('renamed_header', None, '', 'header resolution', 'parsed name differs from the source',
                                     None, None, 'Resolved name differs from the source header') if renamed else None,
                              ('kept as parsed',)))
    unit = Unit('headers', None, 'V2', fields, tuple(records), noun='headers', pointer='/parsing/header_mapping')
    return render_unit(unit, plan_screen(unit), plan_print(unit, profile_name), entity_label='Resolved column', name='resolved source headers')


def evidence_view(value, profile_name):
    evidence = value.get('evidence') or []
    if not evidence:
        return None
    fields = (Field('population', 'Population', 'category'), Field('denominator', 'Denominator', 'quantity'),
              Field('method', 'Method', 'category'), Field('measurements', 'Measurements', 'text'),
              Field('rows', 'Bounded parsed-row references', 'text'))
    records = tuple(Record(f'ev:{i}', str(e.get('id')), {'population': e.get('population'), 'denominator': e.get('denominator'),
                                                        'method': str(e.get('method') or '').replace('_', ' '),
                                                        'measurements': ', '.join(e.get('measurement_refs') or []),
                                                        'rows': ', '.join(str(r.get('parsed_row')) for r in e.get('row_refs') or []) or None},
                           i, f'/evidence/{i}') for i, e in enumerate(evidence))
    unit = Unit('evidence', None, 'V2', fields, records, noun='evidence records', pointer='/evidence',
                printed=profile_name == 'complete')
    return render_unit(unit, plan_screen(unit), plan_print(unit, profile_name), entity_label='Evidence ID', name='evidence references')


def availability_view(value, profile_name):
    """Regression: user-declared feature availability. Declared features print; undeclared ones are counted."""
    from datatrust.report_format import _report_label
    regression = (value.get('profile') or {}).get('regression') or {}
    declared = regression.get('feature_availability') or {}
    features = [c['name'] for c in (value.get('profile') or {}).get('columns') or [] if c.get('role') == 'feature']
    if not features:
        return None
    records = []
    for i, name in enumerate(features):
        state = declared.get(name, 'unknown')
        signal = (Signal('declared_availability', None, '', str(state), 'user declaration', None, None,
                         'Declared ' + _report_label(state)) if name in declared else None)
        records.append(Record(f'avail:{name}', name, {'availability': _report_label(state)}, i,
                              f'/profile/regression/feature_availability', signal, ('undeclared',)))
    unit = Unit('availability', None, 'V2', (Field('availability', 'User-declared availability', 'category'),), tuple(records),
                noun='features', pointer='/profile/regression/feature_availability', table_kind='register-portrait')
    return render_unit(unit, plan_screen(unit), plan_print(unit, profile_name), entity_label='Feature', name='declared feature availability')


def search_view(value, profile_name):
    """Regression: the relationship-search ledger, grouped by method and status."""
    from datatrust.report_format import _report_label
    search = ((value.get('profile') or {}).get('regression') or {}).get('search') or {}
    candidates = search.get('candidates') or []
    if not candidates:
        return None
    fields = (Field('status', 'Status', 'category'), Field('reason', 'Reason', 'category'),
              Field('screened', 'Screened rows', 'quantity'), Field('verified', 'Verified rows', 'quantity'))
    records = tuple(Record(f'cand:{i}', f'{_report_label(c.get("method"))} · {", ".join(c.get("columns") or [])}',
                           {'status': _report_label(c.get('status')), 'reason': _report_label(c.get('reason_category')) if c.get('reason_category') else None,
                            'screened': c.get('screened_rows'), 'verified': c.get('verified_rows')}, i,
                           f'/profile/regression/search/candidates/{i}', None, (_report_label(c.get('method')), _report_label(c.get('status'))))
                    for i, c in enumerate(candidates))
    unit = Unit('search', None, 'V2', fields, records, noun='candidates', pointer='/profile/regression/search/candidates')
    return render_unit(unit, plan_screen(unit), plan_print(unit, profile_name), entity_label='Method · columns', name='the relationship search ledger')


def missingness_chart(value, limit=15):
    """Up to fifteen columns with missing values, most missing first: the chart convention of the classification
    report, applied to every tabular report. The rest are counted, with where they are."""
    columns = [c for c in (value.get('profile') or {}).get('columns') or [] if c.get('missing_count') and c.get('role') != 'target']
    columns.sort(key=lambda c: (-c['missing_rate'], c['name']))
    return {'bars': columns[:limit], 'more': max(0, len(columns) - limit), 'total': len(columns)}


def target_chart(distribution, limit=20):
    """The classification report's class chart, unchanged: up to twenty classes, then one bar for the rest."""
    visible = [dict(item) for item in distribution[:limit]]
    remainder = distribution[limit:]
    if remainder:
        visible.append({"label": f"Other ({len(remainder)} classes)", "count": sum(item["count"] for item in remainder),
                        "percentage": round(sum(item["percentage"] for item in remainder), 2)})
    return visible


def finding_index(value):
    out = []
    for i, f in enumerate(value.get('findings') or []):
        if f.get('code') == 'no_major_issues':
            continue
        out.append({'anchor': f'finding-{i}', 'title': f.get('title'), 'severity': f.get('severity'),
                    'effect': f.get('score_effect') or str(f.get('evidence_type') or '').replace('_', ' ')})
    return out


def report_view(result, profile_name='focused'):
    """Everything the tabular report templates lay out, from the completed result only."""
    value = result if isinstance(result, dict) else result.to_dict()
    units, signals, columns = column_units(value, profile_name)
    plans = OrderedDict((u.unit_id, (u, plan_screen(u), plan_print(u, profile_name))) for u in units)
    # Columns without findings point to "All columns", which owns that anchor.
    rendered = OrderedDict((uid, render_unit(u, s, p, entity_label='Column', own_anchor=uid == 'col-quiet'))
                           for uid, (u, s, p) in plans.items())
    view = {
        'profile': profile_name,
        'findings': finding_index(value),
        'columns': rendered,
        'column_order': list(rendered),
        'signalled_columns': len({c for _, c in signals}),
        'total_columns': len(columns),
        'observed': guidance_observed(value, plans, columns, profile_name),
        'contributors': contributors_unit(value, profile_name),
        'checks': checks_view(value, profile_name),
        'candidates': candidates_view(value, profile_name),
        'unsearched': unsearched_view(value, profile_name),
        'headers': headers_view(value, profile_name),
        'evidence': evidence_view(value, profile_name),
        'availability': availability_view(value, profile_name),
        'search': search_view(value, profile_name),
        'missingness_chart': missingness_chart(value),
        'target_chart': target_chart((value.get('profile') or {}).get('target_distribution') or []),
    }
    from datatrust.report_layout import accounting
    view['qa'] = {'print_profile': profile_name, 'accounting': [accounting(u, p) for u, _, p in plans.values()]
                  + [accounting(u, s) for u, s, _ in plans.values()]}
    return view
