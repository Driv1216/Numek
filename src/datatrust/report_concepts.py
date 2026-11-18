"""Per-report concept manifests for "Understand this report": which concepts a report uses, where each is placed, its
wording for the report's methodology and its example. The catalogue data lives in report_catalogue (re-exported here)."""
from datatrust.report_catalogue import (  # noqa: F401
    CATALOGUE, CATALOGUE_VERSION, CONCEPTS, DEPTHS, FINDING_CONCEPTS, Concept, ConceptVariant, catalogue_bytes, concepts_for,
)


# ——— Per-report concept manifest ———
# Sections in document order, with the concepts each declares. A declaration whose condition is false for this report
# (no guardrail, no candidate codes, ...) is skipped, so the manifest only names concepts the report actually uses.
SECTION_TITLES = {'summary': 'Summary', 'actions': 'Priority actions', 'overview': 'Dataset overview', 'target': 'Target',
                  'missingness': 'Missingness', 'features': 'Duplicates and features', 'numeric': 'Numeric evidence',
                  'relationships': 'Target relationships', 'context': 'Context and declarations',
                  'methodology': 'Scoring, methods and limitations', 'scoring': 'Score explanation',
                  'appendix': 'Technical appendix', 'coverage_inputs': 'Annotation or input coverage',
                  'task': 'Task-specific evidence', 'overlap': 'Overlap and schema', 'populations': 'Feature populations',
                  'advanced': 'Targets, constraints and segments', 'declarations': 'Declarations', 'chronology': 'Chronology',
                  'continuity': 'Continuity and history', 'behavior': 'Behavioral investigation',
                  'availability': 'Availability and outcome maturity', 'evaluation': 'Chronological evaluation',
                  # M6 text
                  'integrity': 'Corpus integrity', 'duplication': 'Duplication and passages', 'tokens': 'Tokens and annotations',
                  'conversations': 'Conversations', 'retrieval': 'Retrieval and provenance',
                  'comparisons': 'Comparisons and model evidence', 'methods': 'Methods and coverage',
                  # M7 images
                  'inventory': 'Inventory', 'decode': 'Decode and representations', 'visual': 'Visual evidence',
                  'annotations': 'Annotation integrity', 'composition': 'Dataset composition', 'duplicates': 'Duplication candidates',
                  'comparison': 'Split and version comparisons', 'coverage': 'Methods and coverage',
                  # M9 cross-representation
                  'identities': 'Source logical identities', 'associations': 'Identity and association integrity',
                  'cross_context': 'Declared entity, version and timing context', 'reconciliation': 'Reconciliation and conflicting evidence',
                  'separation': 'Cross-source contamination', 'models': 'Optional semantic investigations',
                  'limitations': 'Coverage and limitations'}
CORE = {'temporal': ('no_score', 'priority', 'review_evidence', 'window_effects'),
        'text': ('no_score', 'review_evidence', 'bounded_search', 'protected_evidence', 'protected_evidence_disclosed'),
        'image': ('no_score', 'review_evidence', 'duplicate_candidate', 'protected_evidence', 'protected_evidence_disclosed'),
        'cross': ('no_score', 'priority', 'reconciliation_outcomes', 'protected_evidence', 'protected_evidence_disclosed'),
        'm3': ('no_score', 'priority', 'review_evidence', 'coverage'),
        'm4': ('no_score', 'priority', 'review_evidence', 'split_overlap'),
        'classification': ('reliability_score', 'guardrail', 'priority', 'review_evidence'),
        'regression': ('no_score', 'priority', 'review_evidence', 'coverage'),
        'unlabeled': ('no_score', 'priority', 'review_evidence', 'coverage')}


def _structured_sections(family, value, view):
    """M3 and M4: concepts follow what the report actually contains."""
    p = value.get('profile') or {}
    complete = bool(view.get('complete_tables'))
    appendix = ['print_profile'] + (['screen_only'] if complete and view.get('qa', {}).get('print_profile') != 'complete' else []) + ['coverage']
    if family == 'm3':
        task = []
        if view.get('multilabel_summary'):
            task += ['label_cardinality', 'jaccard']
        if view.get('regression_summary'):
            task += ['central_span'] + (['output_correlation'] if (view['regression_summary'].get('output_dependencies')) else [])
        if view.get('readiness_summary'):
            task += ['quantitative_eligibility', 'scale_ratio'] + (['anomaly_candidates'] if (value.get('task') or {}).get('kind') == 'anomaly_detection' else [])
        coverage = ['annotation_expectation', 'annotation_coverage'] if view.get('annotation_rows') else (['quantitative_eligibility'] if view.get('readiness_summary') else [])
        features = ['duplicates'] + (['repeated_inputs'] if view.get('repetition') else []) + (['cohort_contrast'] if view.get('cohort_availability') else [])
        context = value.get('contextual') or {}
        context_concepts = (['suggested_codes'] if context.get('candidates') else []) + (['bounded_search'] if (context.get('dependency_search') or {}).get('unsearched_features') else [])
        return [('summary', ['no_score']), ('actions', ['priority', 'review_evidence']), ('coverage_inputs', coverage), ('task', task),
                ('features', features), ('context', context_concepts),
                ('methodology', ['coverage', 'bounded_search', 'review_thresholds']), ('appendix', appendix)]
    tables = view.get('tables') or {}
    comparison = bool(tables.get('overlap') or tables.get('schema') or tables.get('effects'))
    populations = (['missingness_change', 'total_variation', 'cdf_distance', 'wasserstein'] if tables.get('effects') else []) + ['missingness']
    return [('summary', ['no_score']), ('actions', ['priority', 'review_evidence']),
            ('overlap', ['split_overlap', 'schema_change'] if comparison else []), ('populations', populations),
            ('advanced', ['affected_rows'] if tables.get('advanced') else []),
            ('methodology', ['coverage', 'bounded_search', 'significance', 'review_thresholds']), ('appendix', appendix)]


def _temporal_sections(value, view):
    present = {topic['id']: bool(topic['rows'] or topic['charts']) for topic in view.get('topics') or []}
    checks = {record.get('check_id') for record in value.get('evidence') or []}
    def when(concept, *ids):
        return [concept] if checks & set(ids) else []
    windows = when('windows', 'behavior_windows') + when('window_effects', 'behavior_windows')
    effects = (['total_variation', 'cdf_distance', 'wasserstein'] if 'behavior_windows' in checks else [])
    declared = {'declarations': ['clock'], 'chronology': ['clock'], 'continuity': when('schedule_continuity', 'continuity'),
                'behavior': windows + when('runs', 'runs', 'runs_and_volatility') + when('volatility', 'volatility', 'runs_and_volatility')
                            + when('seasonality', 'seasonality') + effects,
                'availability': when('availability_timing', 'availability', 'availability_unknown', 'past_observation')
                                + when('revisions', 'revision_history', 'selected_revision_timing') + when('maturity', 'outcome_maturity'),
                'evaluation': when('folds', 'evaluation')}
    sections = [('summary', ['no_score']), ('actions', ['priority', 'review_evidence'])]
    sections += [(topic, concepts if present.get(topic) else []) for topic, concepts in declared.items()]
    appendix = ['print_profile'] + (['screen_only'] if view.get('complete_tables') and view.get('profile') != 'complete' else [])
    return sections + [('methodology', ['coverage', 'bounded_search']), ('appendix', appendix)]


def _modality_sections(family, value, view):
    """M6 text, M7 images and M9 cross-representation (Stage 6): concepts are declared where their evidence appears."""
    evidence = value.get('evidence') or []
    families = {e.get('family') for e in evidence}
    policy = ((value.get('profile') or {}).get('disclosure') or {}).get('policy')
    protected = 'protected_evidence' if policy in (None, 'references_only') else 'protected_evidence_disclosed'
    bounded = any(e.get('scope') == 'bounded' for e in evidence)
    present = {s.get('id'): bool(s.get('records') or s.get('blocks')) for s in view.get('sections') or []}
    def when(concept, *names):
        return [concept] if families & set(names) else []
    if family == 'text':
        declared = {'integrity': when('framed_records', 'invalidity', 'corpus'),
                    'duplication': when('grapheme_jaccard', 'near_duplicates') + when('verified_candidates', 'near_duplicates')
                                   + when('shared_passages', 'passages'),
                    'comparisons': when('semantic_neighbours', 'semantic_similarity') + when('language_id', 'language'),
                    'methods': ['coverage'] + (['bounded_search'] if bounded else []) + [protected]}
        order = ('integrity', 'duplication', 'tokens', 'conversations', 'retrieval', 'comparisons', 'methods')
        present['methods'] = True   # coverage, execution and the protected-evidence note always render there
        head = [('summary', ['no_score']), ('actions', ['review_evidence'])]
    elif family == 'image':
        exact = [f for f in families if str(f).startswith('exact_duplicates')]
        declared = {'annotations': when('coordinate_frames', 'annotations', 'annotation_disagreement'),
                    'duplicates': (['exact_representations'] if exact else []) + when('perceptual_signature', 'near_duplicates')
                                  + when('hamming_distance', 'near_duplicates') + when('duplicate_candidate', 'near_duplicates', 'embeddings'),
                    'coverage': ['coverage'] + (['bounded_search'] if bounded else []) + [protected]}
        order = ('inventory', 'decode', 'visual', 'annotations', 'composition', 'duplicates', 'comparison', 'coverage')
        head = [('summary', ['no_score']), ('actions', ['review_evidence'])]
    else:
        conflicting = any((e.get('data') or {}).get('conflicting_evidence') for e in evidence if e.get('family') == 'reconciliation')
        declared = {'identities': ['logical_identity'], 'associations': ['association_cardinality'],
                    'reconciliation': ['reconciliation_outcomes'] + (['competing_evidence'] if conflicting else []),
                    'separation': ['separation'], 'models': ['model_candidates', 'abstention']}
        order = ('identities', 'associations', 'cross_context', 'reconciliation', 'separation', 'models')
        head = [('summary', ['no_score']), ('actions', ['priority', 'review_evidence'])]
    sections = head + [(sid, declared.get(sid, []) if present.get(sid) else []) for sid in order]
    if family == 'cross':
        sections.append(('limitations', ['coverage'] + (['bounded_search'] if bounded else []) + [protected]))
    appendix = ['print_profile'] + (['screen_only'] if view.get('complete_tables') and view.get('profile') != 'complete' else [])
    return sections + [('appendix', appendix)]


def _sections(family, value, view):
    if family in ('text', 'image', 'cross'):
        return _modality_sections(family, value, view)
    if family == 'temporal':
        return _temporal_sections(value, view)
    if family in ('m3', 'm4'):
        return _structured_sections(family, value, view)
    p = value.get('profile') or {}
    scores = (value.get('scoring') or {}).get('values') if (value.get('scoring') or {}).get('status') == 'computed' else None
    guardrails = bool((scores or {}).get('guardrails'))
    context = value.get('contextual') or {}
    unsearched = bool((context.get('dependency_search') or {}).get('unsearched_features'))
    findings = [f for f in value.get('findings') or [] if f.get('code') != 'no_major_issues']
    finding_concepts = [c for f in findings for c in FINDING_CONCEPTS.get(f.get('code'), ())]
    columns = view.get('columns') or {}
    field_concepts = [f['concept'] for u in columns.values() for f in u['fields'] if f.get('concept')]
    summarised = any(r['type'] == 'summary' for u in columns.values() for r in u['rows'])
    screen = any(u.get('print_hidden') for u in columns.values())
    appendix = (['print_profile'] + [c for c in ('missingness', 'iqr_outliers', 'quartiles', 'cardinality') if c in field_concepts]
                + (['summarised_rows'] if summarised else []) + (['screen_only'] if screen else [])
                + (['not_assessable'] if 'col-assessability' in columns else []) + ['coverage'])
    context_concepts = (['suggested_codes'] if context.get('candidates') else []) + (['bounded_search'] if unsearched else [])
    actions = ['priority', 'review_evidence'] + finding_concepts
    if family == 'classification':
        return [('summary', ['reliability_score', 'evidence_score'] + (['guardrail'] if guardrails else []) + ['risk_band']),
                ('actions', actions),
                ('target', ['target', 'class_imbalance', 'majority_baseline'] + (['missing_labels'] if p.get('target_missing_count') else [])),
                ('missingness', ['missingness']),
                ('features', ['duplicates', 'conflicting_labels', 'leakage_name_review']),
                ('context', context_concepts),
                ('methodology', ['sub_scores'] + (['guardrail'] if guardrails else [])),
                ('scoring', ['feature_usability', 'review_thresholds']),
                ('appendix', appendix)]
    regression = (p.get('regression') or {})
    if family == 'regression':
        return [('summary', ['no_score', 'target']),
                ('actions', actions),
                ('overview', ['declared_constraints'] if (regression.get('constraints') or {}).get('rules') else []),
                ('target', ['quartiles', 'iqr_outliers', 'non_finite']),
                ('relationships', ['target_relationship', 'bounded_search']),
                ('missingness', ['missingness', 'duplicates']),
                ('context', context_concepts),
                ('methodology', ['coverage', 'review_thresholds']),
                ('appendix', appendix)]
    return [('summary', ['no_score']),
            ('actions', actions),
            ('missingness', ['missingness']),
            ('features', ['duplicates', 'cardinality', 'near_constant']),
            ('numeric', ['quartiles', 'iqr_outliers', 'non_finite']),
            ('context', context_concepts),
            ('methodology', ['coverage', 'review_thresholds']),
            ('appendix', appendix)]


def build_manifest(family, value, view):
    """The concepts this report uses, where each is placed, its wording for this methodology and its example. Built
    from the projection before rendering; templates render exactly these placements and guide entries."""
    from datatrust.report_context import Example, build
    methodology = value.get('methodology_id')
    findings = [f for f in value.get('findings') or [] if f.get('code') != 'no_major_issues']
    tied = {c for f in findings for c in FINDING_CONCEPTS.get(f.get('code'), ())}
    sections, placements, order, seen_first = [], [], [], set()
    for section, declared in _sections(family, value, view):
        ids = [c for c in dict.fromkeys(declared) if c in CATALOGUE and family in CATALOGUE[c].families]
        entries = []
        for cid in ids:
            first = cid not in seen_first
            seen_first.add(cid)
            if first:
                order.append(cid)
            entry = {'concept': cid, 'section': section, 'anchor': f'term-{section}-{cid}', 'first': first,
                     'term': CATALOGUE[cid].term}
            placements.append(entry)
            entries.append(entry)
        sections.append({'id': section, 'title': SECTION_TITLES[section], 'placements': entries,
                         'has_first': any(e['first'] for e in entries)})
    first_anchor = {p['concept']: p['anchor'] for p in placements if p['first']}
    first_section = {p['concept']: p['section'] for p in placements if p['first']}
    concepts = []
    for cid in order:
        entry = CATALOGUE[cid].resolved(methodology)
        example = build(CATALOGUE[cid].example_builder, value, view)
        entry.update({'anchor': first_anchor[cid], 'section': first_section[cid],
                      'section_title': SECTION_TITLES[first_section[cid]], 'tied_to_finding': cid in tied,
                      'example': ({'text': example.text, 'values': example.values} if isinstance(example, Example)
                                  else {'unavailable': example.reason} if example else None)})
        concepts.append(entry)
    core = [c for c in CORE.get(family, ()) if c in first_anchor]
    return {'family': family, 'catalogue': CATALOGUE_VERSION, 'methodology_id': methodology, 'sections': sections,
            'placements': placements, 'concepts': concepts, 'core': core,
            'by_id': {c['id']: c for c in concepts}, 'section': {s['id']: s for s in sections}}
