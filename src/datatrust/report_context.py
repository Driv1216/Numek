"""Contextual examples for concepts ("In this report: ..."), built only from the completed result.

Each builder returns Example(text, values) or Unavailable(reason):
- every value quoted in the text is stored in the result at the JSON pointer that keys it in `values`; no number is
  derived (fences are never recomputed from rounded quartiles, shares never re-divided);
- the entity chosen is deterministic: the most significant by the recorded measure, ties broken by source order;
- an example never discloses more than the report already shows: tabular reports print every value used here.
"""
from dataclasses import dataclass, field

from datatrust.report_layout import format_value


@dataclass(frozen=True)
class Example:
    text: str
    values: dict = field(default_factory=dict)   # JSON pointer -> stored value


@dataclass(frozen=True)
class Unavailable:
    reason: str


def _columns(value):
    return list(enumerate((value.get('profile') or {}).get('columns') or []))


def _fv(v):
    return format_value(v)


def _best(value, key, minimum=0, roles=('feature',)):
    """The column with the largest recorded value of key (above minimum), source order breaking ties."""
    best = None
    for i, c in _columns(value):
        v = c.get(key)
        if not isinstance(v, (int, float)) or isinstance(v, bool) or v <= minimum:
            continue
        if roles and c.get('role') not in roles and not (c.get('role') in (None, 'column')):
            continue
        if best is None or v > best[1].get(key):
            best = (i, c)
    return best


def iqr_outliers(value, view=None):
    found = _best(value, 'outlier_count')
    if not found:
        return Unavailable('No column has values outside the fences in this report.')
    i, c = found
    s = c.get('numeric_summary') or {}
    base = f'/profile/columns/{i}'
    unit = 'rows' if value.get('methodology_id') == 'classification_legacy_2026_08_13' else 'finite values'
    values = {f'{base}/name': c['name'], f'{base}/outlier_count': c['outlier_count'], f'{base}/outlier_rate': c['outlier_rate']}
    text = f"{c['name']}: {_fv(c['outlier_count'])} {unit} ({_fv(c['outlier_rate'])}%) are outside the fences"
    if s.get('q1') is not None and s.get('q3') is not None:
        values.update({f'{base}/numeric_summary/q1': s['q1'], f'{base}/numeric_summary/q3': s['q3']})
        text += f", with Q1 {_fv(s['q1'])} and Q3 {_fv(s['q3'])}"
    return Example(text + '.', values)


def missingness(value, view=None):
    found = _best(value, 'missing_rate', roles=('feature', 'target'))
    if not found:
        return Unavailable('No column has missing values in this report.')
    i, c = found
    base = f'/profile/columns/{i}'
    rows = (value.get('profile') or {}).get('row_count')
    return Example(f"{c['name']}: {_fv(c['missing_count'])} of {_fv(rows)} rows missing ({_fv(c['missing_rate'])}%).",
                   {f'{base}/name': c['name'], f'{base}/missing_count': c['missing_count'], '/profile/row_count': rows,
                    f'{base}/missing_rate': c['missing_rate']})


def duplicates(value, view=None):
    p = value.get('profile') or {}
    if p.get('duplicate_rows') is None:
        return Unavailable('Duplicate rows were not recorded for this analysis.')
    return Example(f"{_fv(p['duplicate_rows'])} rows repeat an earlier row ({_fv(p.get('duplicate_rate'))}% of rows).",
                   {'/profile/duplicate_rows': p['duplicate_rows'], '/profile/duplicate_rate': p.get('duplicate_rate')})


def class_imbalance(value, view=None):
    p = value.get('profile') or {}
    classes = p.get('target_distribution') or []
    if not classes or p.get('majority_to_minority_ratio') is None:
        return Unavailable('The target has fewer than two observed classes.')
    top = classes[0]
    return Example(f"The largest class, {top['label']}, is {_fv(top['percentage'])}% of labelled rows; majority to minority is "
                   f"{_fv(p['majority_to_minority_ratio'])} : 1.",
                   {'/profile/target_distribution/0/label': top['label'], '/profile/target_distribution/0/percentage': top['percentage'],
                    '/profile/majority_to_minority_ratio': p['majority_to_minority_ratio']})


def majority_baseline(value, view=None):
    p = value.get('profile') or {}
    if p.get('majority_class_baseline') is None:
        return Unavailable('No labelled rows were available for a baseline.')
    return Example(f"Always predicting the largest class here would be right for {_fv(p['majority_class_baseline'])}% of labelled rows.",
                   {'/profile/majority_class_baseline': p['majority_class_baseline']})


def _scores(value):
    scoring = value.get('scoring') or {}
    return scoring.get('values') if scoring.get('status') == 'computed' else None


def reliability_score(value, view=None):
    s = _scores(value)
    if not s:
        return Unavailable('No score was computed for this analysis.')
    return Example(f"This report’s final score is {_fv(s['overall'])}, in the {s['risk_level']} risk band.",
                   {'/scoring/values/overall': s['overall'], '/scoring/values/risk_level': s['risk_level']})


def evidence_score(value, view=None):
    s = _scores(value)
    if not s:
        return Unavailable('No score was computed for this analysis.')
    return Example(f"Here the evidence score is {_fv(s['evidence_score'])} and the final score after guardrails is {_fv(s['overall'])}.",
                   {'/scoring/values/evidence_score': s['evidence_score'], '/scoring/values/overall': s['overall']})


def lowest_sub_score(value, view=None):
    s = _scores(value)
    if not s or not s.get('sub_scores'):
        return Unavailable('No sub-scores were computed for this analysis.')
    name, score = min(s['sub_scores'].items(), key=lambda item: (item[1], item[0]))
    label = name.replace('_', ' ')
    return Example(f"The lowest sub-score here is {label}, at {_fv(score)}.", {f'/scoring/values/sub_scores/{name}': score})


def guardrail(value, view=None):
    s = _scores(value)
    rails = (s or {}).get('guardrails') or []
    if not rails:
        return Unavailable('No guardrail was triggered in this report.')
    index, rail = min(enumerate(rails), key=lambda item: (item[1]['cap'], item[0]))
    return Example(f"Here a guardrail caps the score at {_fv(rail['cap'])}: {rail['explanation']}",
                   {f'/scoring/values/guardrails/{index}/cap': rail['cap'], f'/scoring/values/guardrails/{index}/explanation': rail['explanation']})


def feature_usability(value, view=None):
    fu = (((value.get('guidance') or {}).get('scoring') or {}).get('feature_usability')) or {}
    if fu.get('raw_points') is None:
        return Unavailable('The feature-usability breakdown was not recorded by the version that produced this analysis.')
    return Example(f"Here {_fv(fu['raw_points'])} penalty points across {_fv(fu['feature_count'])} feature columns give a "
                   f"sub-score of {_fv(fu['sub_score'])}.",
                   {'/guidance/scoring/feature_usability/raw_points': fu['raw_points'],
                    '/guidance/scoring/feature_usability/feature_count': fu['feature_count'],
                    '/guidance/scoring/feature_usability/sub_score': fu['sub_score']})


def conflicting_labels(value, view=None):
    p = value.get('profile') or {}
    if p.get('conflicting_label_group_count') is None:
        return Unavailable('Label conflicts were not assessed.')
    return Example(f"{_fv(p['conflicting_label_group_count'])} such groups were found, covering {_fv(p.get('conflicting_label_row_count'))} labelled rows.",
                   {'/profile/conflicting_label_group_count': p['conflicting_label_group_count'],
                    '/profile/conflicting_label_row_count': p.get('conflicting_label_row_count')})


def _first_flag(value, flag):
    for i, c in _columns(value):
        if c.get(flag):
            return i, c
    return None


def high_cardinality(value, view=None):
    found = _first_flag(value, 'high_cardinality')
    if not found:
        return Unavailable('No column met the high-cardinality rule in this report.')
    i, c = found
    base = f'/profile/columns/{i}'
    return Example(f"{c['name']}: {_fv(c['unique_count'])} distinct values ({_fv(c['unique_rate'])}% of rows).",
                   {f'{base}/name': c['name'], f'{base}/unique_count': c['unique_count'], f'{base}/unique_rate': c['unique_rate']})


def near_constant(value, view=None):
    found = _first_flag(value, 'constant') or _first_flag(value, 'near_constant')
    if not found:
        return Unavailable('No column was constant or near-constant in this report.')
    i, c = found
    base = f'/profile/columns/{i}'
    return Example(f"{c['name']}: its most common value fills {_fv(c['top_value_rate'])}% of rows.",
                   {f'{base}/name': c['name'], f'{base}/top_value_rate': c['top_value_rate']})


def leakage_review(value, view=None):
    details = (value.get('profile') or {}).get('leakage_details') or []
    if not details:
        return Unavailable('No column name matched the leakage rules in this report.')
    d = details[0]
    kind = 'a strong candidate' if d.get('classification') == 'strong' else 'review only'
    return Example(f"{d['column']} was flagged as {kind}.",
                   {'/profile/leakage_details/0/column': d['column'], '/profile/leakage_details/0/classification': d.get('classification')})


def target_relationship(value, view=None):
    groups = (((value.get('profile') or {}).get('regression') or {}).get('relationship_groups')) or []
    if not groups:
        return Unavailable('No relationship was verified in the searched scope.')
    return Example(f"Here: {groups[0]['expression']}.", {'/profile/regression/relationship_groups/0/expression': groups[0]['expression']})


def declared_constraints(value, view=None):
    constraints = (((value.get('profile') or {}).get('regression') or {}).get('constraints'))
    if not constraints or not constraints.get('rules'):
        return Unavailable('No constraint was declared for this analysis.')
    return Example(f"Here {_fv(constraints['violation_union_count'])} finite targets violate at least one declared rule.",
                   {'/profile/regression/constraints/violation_union_count': constraints['violation_union_count']})


def not_assessable(value, view=None):
    from datatrust.report_format import _report_label
    names = {c.get('name') for _, c in _columns(value)}
    for i, check in enumerate(value.get('checks') or []):
        if check.get('scope') in names and check.get('reason') and check.get('applicability') != 'applicable':
            return Example(f"{check['scope']}: {str(check['check_id']).replace('_', ' ')} was not run ({_report_label(check['reason'])}).",
                           {f'/checks/{i}/scope': check['scope'], f'/checks/{i}/reason': check['reason']})
    return Unavailable('Every applicable column check completed in this report.')


def _first_evidence(value, family, condition=lambda data: True):
    """(index, data) of the first evidence record of a family (M6, M7, M9 `family`; M5 `check_id`), in recorded order."""
    for i, e in enumerate(value.get('evidence') or []):
        if (e.get('family') or e.get('check_id')) == family and isinstance(e.get('data'), dict) and condition(e['data']):
            return i, e['data']
    return None


def window_effects(value, view=None):
    found = _first_evidence(value, 'behavior_windows', lambda d: any(c.get('distribution_review') for c in d.get('comparisons') or []))
    if not found:
        return Unavailable('No window comparison met the configured investigation settings in this report.')
    i, d = found
    j, c = next((j, c) for j, c in enumerate(d['comparisons']) if c.get('distribution_review'))
    base = f'/evidence/{i}/data/comparisons/{j}'
    values = {f'/evidence/{i}/data/measurement': d.get('measurement'), f'{base}/reference_window': c['reference_window'],
              f'{base}/comparison_window': c['comparison_window']}
    parts = []
    for key, label in (('total_variation', 'total variation'), ('cdf_distance', 'CDF distance'), ('wasserstein_1', 'Wasserstein-1')):
        if c.get(key) is not None:
            values[f'{base}/{key}'] = c[key]
            parts.append(f'{label} {_fv(c[key])}')
    return Example(f"{d.get('measurement')}: window {c['comparison_window']} against window {c['reference_window']} has "
                   + ', '.join(parts) + ', which meets the investigation settings.', values)


def grapheme_jaccard(value, view=None):
    found = _first_evidence(value, 'near_duplicates', lambda d: 'threshold' in d)
    if not found:
        return Unavailable('The near-duplicate search did not run for this report.')
    i, d = found
    base = f'/evidence/{i}/data'
    return Example(f"Pairs at {_fv(d['threshold'])} or above qualify; this search found {_fv(d['qualifying_pairs'])} qualifying "
                   f"pairs and {_fv(d['subthreshold_candidates'])} verified candidates below the threshold.",
                   {f'{base}/threshold': d['threshold'], f'{base}/qualifying_pairs': d['qualifying_pairs'],
                    f'{base}/subthreshold_candidates': d['subthreshold_candidates']})


def shared_passages(value, view=None):
    found = _first_evidence(value, 'passages', lambda d: 'verified_passage_matches' in d)
    if not found:
        return Unavailable('The passage search did not run for this report.')
    i, d = found
    base = f'/evidence/{i}/data'
    return Example(f"{_fv(d['verified_passage_matches'])} verified passage matches of at least {_fv(d['minimum_graphemes'])} graphemes.",
                   {f'{base}/verified_passage_matches': d['verified_passage_matches'], f'{base}/minimum_graphemes': d['minimum_graphemes']})


def hamming_distance(value, view=None):
    found = _first_evidence(value, 'near_duplicates', lambda d: 'radius' in d)
    if not found:
        return Unavailable('The perceptual search did not run for this report.')
    i, d = found
    base = f'/evidence/{i}/data'
    return Example(f"This search used radius {_fv(d['radius'])} and found {_fv(d['qualifying_raster_pairs'])} qualifying image pairs.",
                   {f'{base}/radius': d['radius'], f'{base}/qualifying_raster_pairs': d['qualifying_raster_pairs']})


def duplicate_candidate(value, view=None):
    found = _first_evidence(value, 'near_duplicates', lambda d: d.get('examples'))
    if not found:
        return Unavailable('No duplicate candidate was retained in this report.')
    i, d = found
    pair = d['examples'][0]
    base = f'/evidence/{i}/data/examples/0'
    return Example(f"{pair['left']} and {pair['right']} are a candidate pair at Hamming distance {_fv(pair['hamming_distance'])}.",
                   {f'{base}/left': pair['left'], f'{base}/right': pair['right'], f'{base}/hamming_distance': pair['hamming_distance']})


def reconciliation_outcomes(value, view=None):
    found = _first_evidence(value, 'reconciliation', lambda d: 'satisfied' in d)
    if not found:
        return Unavailable('No deterministic reconciliation rule ran in this report.')
    i, d = found
    base = f'/evidence/{i}/data'
    keys = [k for k in ('records', 'satisfied', 'violated', 'conflicting_evidence', 'inconclusive') if k in d]
    words = {'satisfied': 'agree', 'violated': 'disagree', 'conflicting_evidence': 'have conflicting supplied evidence',
             'inconclusive': 'cannot be resolved'}
    text = f"Of {_fv(d['records'])} records, " + ', '.join(f"{_fv(d[k])} {words[k]}" for k in keys if k != 'records') + '.'
    return Example(text, {f'{base}/{k}': d[k] for k in keys})


def logical_identity(value, view=None):
    found = _first_evidence(value, 'identities', lambda d: 'records' in d)
    if not found:
        return Unavailable('No source declared a logical identity in this report.')
    i, d = found
    base = f'/evidence/{i}/data'
    return Example(f"The first source has {_fv(d['records'])} records: {_fv(d['invalid_keys_total'])} without a usable identity and "
                   f"{_fv(d['cardinality_violations'])} repeated identity groups.",
                   {f'{base}/records': d['records'], f'{base}/invalid_keys_total': d['invalid_keys_total'],
                    f'{base}/cardinality_violations': d['cardinality_violations']})


BUILDERS = {name: fn for name, fn in globals().items() if callable(fn) and not name.startswith('_')
            and name not in {'Example', 'Unavailable', 'dataclass', 'field', 'format_value'}}


def build(name, value, view=None):
    if not name:
        return None
    return BUILDERS[name](value, view)
