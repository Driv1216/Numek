"""interpretation_v1: the one deterministic interpretation of a completed result, shared by the dashboards (through the
presentation companion) and, from Stage 6D, the canonical reports.

It is presentation, not analysis. It reads only what the result records (fields, the recorded `finding_guidance_v1`
block and the methodology identity), and it never creates, removes, re-ranks or recomputes findings or values. Every
number in a summary sentence is a recorded value or a count of recorded items, and each sentence lists the facts it
rests on as JSON pointers so the text can be traced back (`resolve_fact`). Results saved before guidance existed get no
guidance here: nothing is back-filled.

Sections:
- summary: per-workflow sentences, in the order a reader needs them.
- findings: the recorded guidance for each finding, keyed by the same reference the guidance block records.
- more_conclusive: declarations the user could supply that would let the analysis conclude more, derived from recorded
  unknowns (a fixed table, `UNKNOWN_RESOLUTION`, that maps every catalogue unknown to a declaration or to none) and from
  recorded configuration (no evaluation intent, no schedule, no models selected, ...).
- clean: for a result with no finding, what was completed, which thresholds were not met and what is not established.
- states: the fixed vocabulary for result states.
"""
import re

from datatrust.guidance import NARRATIVE_ONLY, PLACEHOLDERS

VERSION = 'interpretation_v1'

STATES = [
    {'state': 'no_finding', 'label': 'No finding', 'meaning': 'The check ran on its population and no review threshold was met.'},
    {'state': 'not_applicable', 'label': 'Not applicable', 'meaning': 'The check does not apply to this data or task.'},
    {'state': 'not_requested', 'label': 'Not requested', 'meaning': 'An optional check or declaration was left off in the configuration.'},
    {'state': 'not_assessed', 'label': 'Not assessed', 'meaning': 'The check applied but did not run on this population.'},
    {'state': 'insufficient_evidence', 'label': 'Insufficient evidence', 'meaning': 'Too little support to measure; the value is shown as unavailable, never as zero.'},
    {'state': 'bounded', 'label': 'Bounded', 'meaning': 'A search stopped at a planned limit; what it did not examine is not a negative result.'},
    {'state': 'blocked_or_failed', 'label': 'Blocked or failed', 'meaning': 'A precondition excluded the check, or it failed or was interrupted; nothing is concluded on its scope.'},
    {'state': 'confirmed_violation', 'label': 'Confirmed violation', 'meaning': 'The data breaks a requirement you declared or a deterministic rule.'},
]

# Declarations a user can supply, with what each one makes possible. The key is what the dashboard links to configure.
DECLARATIONS = {
    'prediction_point': ('Prediction point and feature availability',
                         'Relationships and dependencies on the target are then judged as available or unavailable at prediction time, instead of leaving leakage unverified.'),
    'code_meanings': ('Meanings of the suggested placeholder and sentinel codes',
                      'Missing-value and extreme-value checks are then recomputed on the population your declarations make applicable.'),
    'target_expectations': ('Target meaning, units and plausible range',
                            'Values outside the declared range or type are then reported as declared violations rather than left as review candidates.'),
    'annotation_expectation': ('Annotation expectations (partially labelled data)',
                               'Absent labels can then be told apart as expected gaps, optional, or intentionally unlabelled.'),
    'semantic_types': ('Meaning of ambiguous columns (quantitative, categorical or identifier)',
                       'Integer codes and identifiers are then excluded from quantitative evidence instead of being assumed numeric.'),
    'scale_sensitivity': ('Whether your method is sensitive to feature scales',
                          'The scale review then applies, or is set aside, according to the method you will use.'),
    'evaluation_intent': ('What must not be shared between splits',
                          'Overlap on the declared keys is then reported as a violation of your requirement rather than as an observation.'),
    'identity_keys': ('Identity keys',
                      'Rows can then be traced across files, so overlap, lineage and row changes are measured per record instead of by counts.'),
    'transformations': ('The transformations your pipeline applied',
                        'Observed changes are then reconciled against what you declared: declared but not observed, and undeclared changes.'),
    'schedule': ('An expected observation schedule',
                 'Continuity is then assessed: absent expected records are counted instead of left unassessed.'),
    'models': ('Optional model-assisted investigations',
               'Model-assisted candidates are added to the evidence. They are review candidates and never produce findings on their own.'),
    'dependency_search': ('The opt-in dependency search (regression_dependency_v1)',
                          'Features that determine the target as a lookup, a binned copy or a monotone mapping are then searched; the standard search covers exact copies, linear rescalings and sums of two columns only.'),
    'quality_expectations': ('Declared image quality rules',
                             'Images breaking a declared minimum size, contrast or exposure rule are then reported as declared violations.'),
}
ORDER = list(DECLARATIONS)

# Every unknown a guidance catalogue entry or method can record, mapped to the declaration that would resolve it, or to
# None when no declaration can (it needs domain review or is outside DataTrust's scope). First match wins; the test suite
# requires every recorded unknown to match exactly one row.
UNKNOWN_RESOLUTION = [
    # readiness v2 (Stage 6C): neither can be resolved by a declaration
    (r'^Why values are missing is not established; complete rows may not represent', None),
    (r'^Correlation in this file does not establish that the features are interchangeable', None),
    (r'^A name check cannot establish when values become available', 'prediction_point'),
    (r'^Availability of the related inputs was not declared', 'prediction_point'),
    (r'^Checks follow your declarations; undeclared features were not assessed for availability', 'prediction_point'),
    (r'^Leakage was checked by column name only', 'prediction_point'),
    (r'^Leakage was checked by column name and by a bounded target-dependency search .*no prediction point was declared', 'prediction_point'),
    (r'^Leakage was checked by column name and by a bounded target-dependency search .*availability is as you declared', None),
    (r'^Prediction-time availability is known only for features you declared', 'prediction_point'),
    (r'^' + re.escape(PLACEHOLDERS), 'code_meanings'),
    (r'^\d+ possible placeholder or sentinel codes were suggested but none was declared', 'code_meanings'),
    (r'^Placeholder and sentinel codes were interpreted only where you declared them', None),
    (r'^Why values are missing, and whether text placeholders', 'code_meanings'),
    (r'^Whether absent targets are pending, inapplicable or lost was not declared', 'annotation_expectation'),
    (r'^Whether a scale-sensitive method will be used was not declared', 'scale_sensitivity'),
    (r'^The semantic type of these columns was not assessed', 'semantic_types'),
    (r'^Record-level lineage was not available', 'identity_keys'),
    (r'^How the After file was produced was not observed', 'transformations'),
    # No declaration resolves these: they need domain review, or are outside what DataTrust observes.
    (r'^Actual model use of these inputs was not observed', None),
    (r'^Candidates come from a bounded search', None),
    (r'^DataTrust checks your declaration', None),
    (r'^DataTrust records your availability declaration', None),
    (r'^Dependence is measured within the bounded pairs searched', None),
    (r'^Excluded records were not assessed by content checks', None),
    (r'^Matches to later revisions are investigation candidates', None),
    (r'^No minimum sample size is validated by DataTrust', None),
    (r'^Overlap is checked on the declared keys and selected inputs only', None),
    (r'^Passage candidates are bounded', None),
    (r'^Records with unresolved clocks were not assessed', None),
    (r'^Semantic equivalence of renamed columns was not assessed', None),
    (r'^The cause of ', None),
    (r"^The deployment population's class shares", None),
    (r'^The origin of non-finite values was not assessed', None),
    (r'^The search covers its stated methods and bounds only', None),
    (r'^This finding kind has no specific guidance', None),
    (r'^Topology and semantic correctness of valid annotations', None),
    (r'^Whether (duplicate content|extreme values|missing outcomes|other outcomes|rare values|repeated rows|runs|shared inputs|the difference|valid annotations)', None),
    (r'^Which (duplicate|label|measurement|side)', None),
    (r'^Why (histories|records|values concentrate|values are missing beyond)', None),
]


def resolution(line):
    """The declaration that would resolve a recorded unknown: a key, None (no declaration resolves it), or KeyError when
    the line is not in the table (a test failure, never a silent default)."""
    for pattern, key in UNKNOWN_RESOLUTION:
        if re.search(pattern, line):
            return key
    raise KeyError(line)


# ——— Facts: every number in a sentence is a recorded value or a count of recorded items ———

def _at(value, pointer):
    node = value
    for part in [p for p in pointer.split('/') if p][:64]:
        part = part.replace('~1', '/').replace('~0', '~')
        node = node[int(part)] if isinstance(node, list) else node[part]
    return node


def _findings(value):
    return [f for f in value.get('findings') or [] if isinstance(f, dict) and f.get('code') not in NARRATIVE_ONLY]


def _rank(f):
    return str(f.get('severity') or f.get('priority') or f.get('meaning') or '')


def resolve_fact(value, fact):
    """Recompute a fact from the recorded result: the value at a pointer, the length of a recorded list, or the number of
    recorded findings with a given rank."""
    if fact['derived'] == 'value':
        return _at(value, fact['pointer'])
    if fact['derived'] == 'count':
        node = _at(value, fact['pointer'])
        return len(_findings(value)) if fact['pointer'] == '/findings' else len(node)
    if fact['derived'].startswith('rank:'):
        return sum(1 for f in _findings(value) if _rank(f).lower() == fact['derived'][5:].lower())
    if fact['derived'].startswith('where:'):
        # Items of the list at the pointer matching every condition (`field=value`, or a bare `field` for truthy).
        items = _findings(value) if fact['pointer'] == '/findings' else _at(value, fact['pointer'])
        conditions = [c.split('=', 1) for c in fact['derived'][6:].split('&')]
        return sum(1 for item in items if all((str(item.get(c[0])) == c[1]) if len(c) == 2 else bool(item.get(c[0])) for c in conditions))
    if fact['derived'].startswith('state:'):
        # Entries of the mapping at the pointer whose state (a plain value, or its `state` field) equals the given one.
        node = _at(value, fact['pointer'])
        return sum(1 for v in node.values() if (v if isinstance(v, str) else (v or {}).get('state')) == fact['derived'][6:])
    if fact['derived'].startswith('sum:'):
        return sum(int(_at(value, p) or 0) for p in fact['derived'][4:].split(','))
    raise ValueError(fact['derived'])


def _fact(value, pointer, derived='value'):
    fact = {'pointer': pointer, 'derived': derived}
    fact['value'] = resolve_fact(value, fact)
    return fact


def _n(v):
    return f'{v:,}' if isinstance(v, int) and not isinstance(v, bool) else str(v)


def _s(text, *facts):
    return {'text': text, 'facts': list(facts)}


def _plural(k, one, many=None):
    return f'{_n(k)} {one if k == 1 else (many or one + "s")}'


def _finding_sentence(value):
    fs = _findings(value)
    if not fs:
        return _s('No finding met its review threshold within the completed checks.', _fact(value, '/findings', 'count'))
    ranks = []
    for label in ('High', 'Moderate', 'Low'):
        k = sum(1 for f in fs if _rank(f).lower() == label.lower())
        if k:
            ranks.append((f'{_n(k)} {label.lower()}', _fact(value, '/findings', f'rank:{label}')))
    meanings = {}
    for f in fs:
        if not (f.get('severity') or f.get('priority')) and f.get('meaning'):
            meanings[f['meaning']] = meanings.get(f['meaning'], 0) + 1
    for m, k in meanings.items():
        ranks.append((f'{_n(k)} {m.replace("_", " ")}', _fact(value, '/findings', f'rank:{m}')))
    text = f'{_plural(len(fs), "finding")} call{"s" if len(fs) == 1 else ""} for review' + (f' ({", ".join(r for r, _ in ranks)})' if ranks else '') + '.'
    return _s(text, _fact(value, '/findings', 'count'), *(f for _, f in ranks))


def _availability_sentence(value):
    ctx = value.get('contextual') or {}
    if ctx.get('status') != 'completed':
        return None
    declared = (ctx.get('prediction') or {}).get('declared')
    if not declared:
        return _s('No prediction point was declared, so whether each feature is known at prediction time was not verified; leakage evidence is limited to column names and the bounded dependency search.',
                  _fact(value, '/contextual/prediction/declared'))
    availability = ctx.get('availability') or {}
    states = {}
    for state in availability.values():
        key = state if isinstance(state, str) else (state or {}).get('state', 'unknown')
        states[key] = states.get(key, 0) + 1
    parts = ', '.join(f'{_n(k)} {s.replace("_", " ")}' for s, k in sorted(states.items()))
    return _s(f'A prediction point was declared; feature availability is as you declared it{f" ({parts})" if parts else ""}.', _fact(value, '/contextual/prediction/declared'),
              *(_fact(value, '/contextual/availability', f'state:{s}') for s in sorted(states)))


# ——— Per-workflow summaries ———

def _summary_classification(value):
    v = (value.get('scoring') or {}).get('values') or {}
    out = []
    if v.get('overall') is not None:
        out.append(_s(f'Reliability score {v["overall"]} ({v.get("risk_level")}): a review-policy score, not a probability.',
                      _fact(value, '/scoring/values/overall'), _fact(value, '/scoring/values/risk_level')))
        caps = [(i, g) for i, g in enumerate(v.get('guardrails') or [])]
        if caps:
            i, g = min(caps, key=lambda x: x[1]['cap'])
            out.append(_s(f'The score is capped at {g["cap"]} by the {str(g.get("code", "")).replace("_", " ")} guardrail.', _fact(value, f'/scoring/values/guardrails/{i}/cap')))
    out.append(_finding_sentence(value))
    a = _availability_sentence(value)
    if a:
        out.append(a)
    return out


def _summary_regression(value):
    reg = (value.get('profile') or {}).get('regression') or {}
    t = reg.get('target_statistics') or {}
    out = []
    if t.get('finite_count') is not None and t.get('row_count') is not None:
        out.append(_s(f'{_n(t["finite_count"])} of {_n(t["row_count"])} target values are finite.',
                      _fact(value, '/profile/regression/target_statistics/finite_count'), _fact(value, '/profile/regression/target_statistics/row_count')))
    rels = [(i, r) for i, r in enumerate(reg.get('relationships') or []) if r.get('fully_verified')]
    if rels:
        unknown = [r for _, r in rels if r.get('availability') == 'unknown']
        exprs = '; '.join(str(r.get('expression')) for _, r in rels[:3])
        facts = [_fact(value, '/profile/regression/relationships', 'where:fully_verified')]
        if unknown:
            facts.append(_fact(value, '/profile/regression/relationships', 'where:fully_verified&availability=unknown'))
        out.append(_s(f'{_plural(len(rels), "input relationship")} reproduce{"s" if len(rels) == 1 else ""} the target ({exprs})'
                      + (f'; availability of {_plural(len(unknown), "relationship")} at prediction time is unknown, so it may be leakage or a legitimate rule.' if unknown else '.'),
                      *facts))
    dep = reg.get('dependency_search')
    if isinstance(dep, dict) and dep.get('status') != 'not_assessable':
        k = len(dep.get('flags') or [])
        out.append(_s(f'The dependency search (regression_dependency_v1) checked {_plural(len(dep.get("checks") or []), "feature")}; '
                      + (f'{_plural(k, "feature")} {"determines" if k == 1 else "determine"} the target within its searched families.' if k else
                         'none determines the target within its searched families and gates.')
                      + (' The search was bounded; unsearched features are named in the evidence.' if dep.get('status') == 'bounded' else ''),
                      _fact(value, '/profile/regression/dependency_search/checks', 'count'),
                      _fact(value, '/profile/regression/dependency_search/flags', 'count')))
    out.append(_finding_sentence(value))
    a = _availability_sentence(value)
    if a:
        out.append(a)
    return out


def _summary_profile(value):
    p = value.get('profile') or {}
    out = []
    if p.get('row_count') is not None and p.get('column_count') is not None:
        out.append(_s(f'{_n(p["row_count"])} rows and {_n(p["column_count"])} columns were profiled.', _fact(value, '/profile/row_count'), _fact(value, '/profile/column_count')))
    out.append(_finding_sentence(value))
    readiness = p.get('readiness')
    if readiness is not None:
        coverage = readiness.get('complete_case_coverage') or {}
        if coverage.get('status') == 'completed':
            out.append(_s(f'{_n(coverage["complete_rows"])} of {_n(coverage["rows"])} rows have every quantitative feature finite; '
                          'a distance-based method would drop or impute the rest.' if coverage['complete_rows'] < coverage['rows'] else
                          f'All {_n(coverage["rows"])} rows have every quantitative feature finite.',
                          _fact(value, '/profile/readiness/complete_case_coverage/complete_rows'), _fact(value, '/profile/readiness/complete_case_coverage/rows')))
        redundancy = readiness.get('redundant_quantitative_features') or {}
        if 'pairs' in redundancy:
            k = len(redundancy['pairs'])
            out.append(_s((f'{_plural(k, "pair")} of quantitative features {"carries" if k == 1 else "carry"} nearly the same information, so distances weight that dimension more than once; this may be intended.'
                           if k else 'No pair of quantitative features carries nearly the same information within the searched pairs.')
                          + (' The pair search was bounded.' if redundancy.get('status') == 'bounded' else ''),
                          _fact(value, '/profile/readiness/redundant_quantitative_features/pairs', 'count')))
        out.append(_s('No model was fitted and no readiness verdict is given; the evidence describes prerequisites for distance-based methods.'))
    return out


def _summary_m4(value):
    comparison = value.get('comparison') or {}
    out = [_finding_sentence(value)]
    if comparison.get('mode') == 'splits':
        violated = [f for f in _findings(value) if f.get('evidence_type') == 'declared_violation']
        if comparison.get('evaluation_intent', 'unknown') == 'unknown':
            out.append(_s('No evaluation intent was declared, so overlap between splits is reported as an observation, not as a violation.', _fact(value, '/comparison/evaluation_intent')))
        else:
            out.append(_s(f'Declared intent: {comparison["evaluation_intent"].replace("_", " ")}; {_plural(len(violated), "declared requirement")} violated.',
                          _fact(value, '/comparison/evaluation_intent'), _fact(value, '/findings', 'where:evidence_type=declared_violation')))
    elif comparison.get('preset') == 'before_after':
        out.append(_s('Fewer findings after preprocessing do not establish improvement; the comparison shows what changed in the data.', _fact(value, '/comparison/preset')))
    elif comparison:
        out.append(_s('A changed distribution is not necessarily worse; per-column comparisons cannot establish the absence of a joint shift.', _fact(value, '/comparison/mode')))
    measurements = (value.get('coverage') or {}).get('measurements') or {}
    # Source-pair scopes only ('a:b.material_changes'); segment-level records stay in the evidence with their own scope.
    for key in sorted(k for k in measurements if k.endswith('.material_changes') and k.count(':') == 1):
        changes = measurements[key].get('changes') or []
        if changes:
            shown = ', '.join(f'{"missing values" if c["measure"] == "missingness" else "non-finite values"} in {c["column"]}' for c in changes[:3]) + (', …' if len(changes) > 3 else '')
            pointer = '/coverage/measurements/' + key.replace('~', '~0').replace('/', '~1') + '/changes'
            out.append(_s(f'{_plural(len(changes), "material decrease")} ({shown}). A decrease is a material change, not a defect: '
                          'imputation, back-fill, a changed collection process or row filtering can cause it.', _fact(value, pointer, 'count')))
    return out


def _summary_temporal(value):
    fs = _findings(value)
    violations = sum(1 for f in fs if f.get('evidence_type') == 'declared_violation')
    candidates = len(fs) - violations
    out = [_s(f'{_plural(violations, "declared violation")} and {_plural(candidates, "investigation candidate")}.',
              _fact(value, '/findings', 'where:evidence_type=declared_violation'), _fact(value, '/findings', 'where:evidence_type=investigation_candidate'))]
    if candidates:
        out.append(_s('Investigation candidates meet configured investigation settings; they are not validated defect criteria.'))
    return out


def _summary_evidence(value, noun):
    fs = _findings(value)
    out = [_finding_sentence(value)]
    if not fs:
        out.append(_s(f'The completed {noun} checks found nothing to review; bounded searches did not examine everything (see coverage).'))
    return out


def _summary_cross(value):
    out = []
    rules = [(i, e) for i, e in enumerate(value.get('evidence') or []) if e.get('family') == 'reconciliation']
    assessed = [(i, e) for i, e in rules if int(e['data'].get('records') or 0) > int(e['data'].get('unassessed') or 0)]
    if assessed:
        agree = sum(int(e['data'].get('satisfied') or 0) for _, e in assessed)
        total = sum(int(e['data'].get('records') or 0) for _, e in assessed)
        out.append(_s(f'{_n(agree)} of {_n(total)} assessed record checks agree with their documents.',
                      {'pointer': '/evidence', 'derived': 'sum:' + ','.join(f'/evidence/{i}/data/satisfied' for i, e in assessed if 'satisfied' in e['data']), 'value': agree},
                      {'pointer': '/evidence', 'derived': 'sum:' + ','.join(f'/evidence/{i}/data/records' for i, _ in assessed), 'value': total}))
    out.append(_finding_sentence(value))
    return out


SUMMARIES = {'classification': _summary_classification, 'regression': _summary_regression, 'unlabeled': _summary_profile, 'm3': _summary_profile,
             'm4': _summary_m4, 'temporal': _summary_temporal, 'text': lambda v: _summary_evidence(v, 'text'), 'image': lambda v: _summary_evidence(v, 'image'),
             'cross': _summary_cross}


# ——— More conclusive, clean ———

def _structural(value, family):
    """Declarations the recorded configuration shows were not supplied."""
    keys = []
    ctx = value.get('contextual') or {}
    if ctx.get('status') == 'completed':
        if not (ctx.get('prediction') or {}).get('declared'):
            keys.append(('prediction_point', '/contextual/prediction/declared'))
        if ctx.get('candidates') and not any((d or {}).get('placeholders') or (d or {}).get('sentinels') for d in (ctx.get('declarations') or {}).values()):
            keys.append(('code_meanings', '/contextual/candidates'))
    profile = value.get('profile') or {}
    reg = profile.get('regression') or {}
    expectations = reg.get('expectations') or {}
    if reg and expectations.get('kind') in (None, 'unspecified') and expectations.get('minimum') is None and expectations.get('maximum') is None:
        keys.append(('target_expectations', '/profile/regression/expectations'))
    if reg.get('target_statistics') and 'dependency_search' not in reg:
        keys.append(('dependency_search', '/profile/regression/target_statistics'))
    features = ((profile.get('declarations') or {}).get('features') or {})
    if profile.get('readiness') is not None and features.get('scale_sensitive') is None:
        keys.append(('scale_sensitivity', '/profile/declarations/features/scale_sensitive'))
    comparison = value.get('comparison') or {}
    if family == 'm4' and comparison:
        if comparison.get('mode') == 'splits' and comparison.get('evaluation_intent', 'unknown') == 'unknown':
            keys.append(('evaluation_intent', '/comparison/evaluation_intent'))
        if not comparison.get('identity_keys'):
            keys.append(('identity_keys', '/comparison/identity_keys'))
        if comparison.get('preset') == 'before_after' and not comparison.get('transformations'):
            keys.append(('transformations', '/comparison/transformations'))
    if family == 'temporal':
        for i, e in enumerate(value.get('evidence') or []):
            if e.get('check_id') == 'continuity' and (e.get('data') or {}).get('schedule') == 'none':
                keys.append(('schedule', f'/evidence/{i}/data/schedule'))
                break
    families = {e.get('family') for e in value.get('evidence') or []}
    if family == 'text' and 'semantic_similarity' not in families and 'language' not in families:
        keys.append(('models', '/evidence'))
    if family == 'image' and 'quality_expectations' not in families:
        keys.append(('quality_expectations', '/evidence'))
    if family == 'cross':
        selected = (value.get('coverage') or {}).get('model_selected') or {}
        if not any(int(v or 0) for v in selected.values()):
            keys.append(('models', '/coverage/model_selected'))
    return keys


def _more_conclusive(value, family, unknowns):
    entries = {}
    for key, pointer in _structural(value, family):
        entries.setdefault(key, {'key': key, 'label': DECLARATIONS[key][0], 'why': DECLARATIONS[key][1], 'resolves': [], 'pointer': pointer})
    for line in unknowns:
        try:
            key = resolution(line)
        except KeyError:
            continue  # recorded by an older or newer catalogue: shown under "not established", never guessed
        if key:
            entries.setdefault(key, {'key': key, 'label': DECLARATIONS[key][0], 'why': DECLARATIONS[key][1], 'resolves': [], 'pointer': '/guidance/scope/unknowns'})
            if line not in entries[key]['resolves']:
                entries[key]['resolves'].append(line)
    return [entries[k] for k in ORDER if k in entries]


def _clean(value, guidance):
    checks = [c for c in value.get('checks') or [] if isinstance(c, dict)]
    def status(c, k):
        v = c.get(k)
        return v.get('value') if isinstance(v, dict) else v
    completed = [c for c in checks if status(c, 'applicability') in (None, 'applicable') and status(c, 'execution') in (None, 'completed')]
    return {'checks_completed': len(completed), 'checks_recorded': len(checks),
            'thresholds': [p for p in (guidance or {}).get('policy') or [] if p.get('rule') != 'Score'],
            'not_established': list((guidance or {}).get('scope', {}).get('unknowns') or [])}


def interpret(value, family=None):
    """The interpretation of a completed result (dict), for the presentation family that renders it."""
    if family is None:
        from datatrust.report_identity import family_of
        family = family_of(value)
    guidance = value.get('guidance') if isinstance(value.get('guidance'), dict) else None
    unknowns = list(((guidance or {}).get('scope') or {}).get('unknowns') or [])
    # A result saved before guidance existed recorded no unknowns: nothing is derived from them.
    summary = SUMMARIES.get(family, lambda v: [_finding_sentence(v)])(value)
    findings = {ref: {**item, 'ref': ref} for ref, item in ((guidance or {}).get('items') or {}).items()}
    return {
        'version': VERSION, 'family': family, 'guidance_recorded': guidance is not None,
        'summary': summary, 'findings': findings,
        'more_conclusive': _more_conclusive(value, family, unknowns),
        'clean': _clean(value, guidance) if not _findings(value) else None,
        'states': STATES,
    }
