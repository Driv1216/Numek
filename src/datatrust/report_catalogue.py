"""The DataTrust concept catalogue data ("Understand this report"), versioned.

Concepts define terms; guidance (finding_guidance_v1) explains findings and options. Neither duplicates the other:
concept text never prescribes an action. Text is plain and autoescaped when rendered; nothing here is Markup.

A concept's wording can vary by methodology (variants keyed by methodology_id) where the method itself differs, for
example the IQR outlier denominator. A change of meaning bumps the concept's version; the catalogue entries a workflow
uses are part of that workflow's presentation identity (report_identity).

Stage 3 covers the tabular reports (classification, regression, unlabeled profiling) and the evidence vocabulary every
report uses. Later stages add their workflows' concepts.

This module is data. It is deliberately not a module dependency of any report's presentation identity: each family's
identity covers only the entries it uses (catalogue_bytes), so a concept added or reworded for one workflow never
changes another workflow's identity.
"""
import json
from dataclasses import asdict, dataclass, field
from typing import Optional

CATALOGUE_VERSION = 'report_concepts_v1'
DEPTHS = ('definition', 'contextual', 'interpretive')
TABULAR = frozenset({'classification', 'regression', 'unlabeled'})
STRUCTURED = TABULAR | {'m3', 'm4', 'temporal'}   # tabular, annotation, comparison and temporal reports
TEMPORAL = frozenset({'temporal'})
M5_REF = 'M5 temporal reliability methodology'
M3 = frozenset({'m3'})
M4 = frozenset({'m4'})
CLASSIFICATION = frozenset({'classification'})
REGRESSION = frozenset({'regression'})
UNSCORED = frozenset({'regression', 'unlabeled'})
LEGACY = 'classification_legacy_2026_08_13'
TEXT = frozenset({'text'})
IMAGE = frozenset({'image'})
CROSS = frozenset({'cross'})
MODALITY = TEXT | IMAGE | CROSS
REPR_REF = 'M6–M7 representation-specific methodology'
M9_REF = 'M9 cross-representation methodology'
TEXT_ID, IMAGE_ID, CROSS_ID = 'text_reliability_v1', 'image_reliability_v1', 'cross_representation_reliability_v1'


@dataclass(frozen=True)
class ConceptVariant:
    definition: Optional[str] = None
    means: Optional[str] = None
    does_not_mean: Optional[str] = None
    methodology_ref: Optional[str] = None


@dataclass(frozen=True)
class Concept:
    id: str
    version: int
    term: str
    depth: str
    definition: str
    families: frozenset
    methodology_ref: str
    means: Optional[str] = None
    does_not_mean: Optional[str] = None
    example_builder: Optional[str] = None
    aliases: tuple = ()
    variants: dict = field(default_factory=dict)
    related: tuple = ()

    def __post_init__(self):
        if self.depth not in DEPTHS:
            raise ValueError(f'{self.id}: unknown depth {self.depth}')
        if self.depth == 'interpretive' and not (self.means and self.does_not_mean):
            raise ValueError(f'{self.id}: an interpretive concept states what it means and what it does not establish.')

    def resolved(self, methodology_id):
        """The concept as one methodology words it."""
        variant = self.variants.get(methodology_id) or ConceptVariant()
        return {'id': self.id, 'version': self.version, 'term': self.term, 'depth': self.depth,
                'definition': variant.definition or self.definition, 'means': variant.means or self.means,
                'does_not_mean': variant.does_not_mean or self.does_not_mean,
                'methodology_ref': variant.methodology_ref or self.methodology_ref, 'related': list(self.related)}


SCORES = 'Classification Scores (Unchanged)'
EVIDENCE_ONLY = 'Evidence-Only Diagnostics'
PARSING = 'Parsing Fidelity, Execution, and Coverage'
UNLABELED_POLICY = 'Unlabeled CSV Profiling Policy'
REGRESSION_POLICY = 'Single-Target Regression Policy — `tabular_regression_v1`'
RELATIONSHIPS = 'Regression relationships and bounded execution'
READING = 'Reading Reports: Presentation, Explanations, and Context Layers'

_RETAINED = ConceptVariant(definition='What the PDF prints of the complete retained evidence. “Focused” prints the summary views; '
                           '“complete” also prints every retained entry they abbreviate. The HTML report always lists every '
                           'retained entry.')
_NO_SCORE_BY_MEANING = ConceptVariant(
    definition='This workflow has no validated way to combine its evidence into one number, so it reports evidence, '
               'with each finding labelled by what it means (a deterministic fact, an observation or a candidate), '
               'without a score.', methodology_ref=REPR_REF)
_FINITE_IQR = ConceptVariant(
    definition='The interquartile range (IQR) is Q3 minus Q1, the spread of the middle half of the finite values. A value '
               'more than 1.5 × IQR below Q1 or above Q3 is counted as outside the fences. The share uses finite values '
               'only, and the check needs at least four finite values and a non-zero IQR.',
    methodology_ref=UNLABELED_POLICY)

CONCEPTS = (
    # ——— score and policy (classification) ———
    Concept('reliability_score', 1, 'Reliability score', 'interpretive',
            'A number from 0 to 100 that summarises five transparent sub-scores, then is capped by any guardrail a severe '
            'finding triggers. Higher means fewer of the measured risks were found.',
            CLASSIFICATION, SCORES,
            means='How the measured risks compare under this methodology’s heuristic rules; the score path shows how it was reached.',
            does_not_mean='It is not a probability that a model will work, and not a validated cut-off or certification.',
            example_builder='reliability_score', related=('evidence_score', 'guardrail', 'sub_scores')),
    Concept('evidence_score', 1, 'Evidence score', 'contextual',
            'The average of the five sub-scores before any guardrail cap is applied.',
            CLASSIFICATION, EVIDENCE_ONLY, example_builder='evidence_score', related=('reliability_score', 'guardrail')),
    Concept('sub_scores', 1, 'Sub-scores', 'contextual',
            'Five scores from 0 to 100 for completeness, uniqueness, target balance, feature usability and name-based '
            'leakage risk. Each is computed by a stated formula from the evidence in this report.',
            CLASSIFICATION, SCORES, example_builder='lowest_sub_score', related=('reliability_score',)),
    Concept('guardrail', 1, 'Guardrail (score cap)', 'interpretive',
            'A rule that caps the final score when a severe problem is present, so a serious finding cannot sit beside a '
            'reassuring average. Strong leakage, one target class or no features cap it at 49; other severe problems at 69.',
            CLASSIFICATION, EVIDENCE_ONLY,
            means='At least one severe condition was present, and the final score is limited until it is reviewed.',
            does_not_mean='The cap does not measure how severe the problem is beyond triggering the rule.',
            example_builder='guardrail', related=('reliability_score',)),
    Concept('risk_band', 1, 'Risk band', 'definition',
            'A label for the final score: Low from 85, Moderate from 70, Elevated from 50, and High below 50.',
            CLASSIFICATION, EVIDENCE_ONLY, related=('reliability_score',)),
    Concept('feature_usability', 1, 'Feature usability', 'contextual',
            'A sub-score that subtracts points for columns that are mostly missing, constant or nearly constant, high '
            'cardinality, or heavy in IQR outliers, averaged over the feature columns.',
            CLASSIFICATION, SCORES, example_builder='feature_usability', related=('sub_scores', 'iqr_outliers')),
    Concept('review_thresholds', 1, 'Review thresholds', 'definition',
            'The fixed rules that decide when evidence becomes a finding or a penalty. They are heuristic review settings, '
            'not validated cut-offs.', STRUCTURED, READING),
    # ——— target ———
    Concept('target', 1, 'Target', 'definition',
            'The column chosen as the outcome a model would predict. DataTrust never chooses it; it was selected explicitly.',
            frozenset({'classification', 'regression'}), 'Classification Target Guidance',
            variants={'tabular_regression_v1': ConceptVariant(methodology_ref=REGRESSION_POLICY)}),
    Concept('class_imbalance', 1, 'Class imbalance', 'contextual',
            'One target class makes up much more of the labelled rows than the others. The report flags it when the '
            'largest class reaches 75% of labelled rows.',
            CLASSIFICATION, SCORES, example_builder='class_imbalance', related=('majority_baseline',)),
    Concept('majority_baseline', 1, 'Majority-class baseline', 'contextual',
            'The accuracy a model would get by always predicting the most common class. It is context for reading '
            'accuracy, not a measure of any model.',
            CLASSIFICATION, EVIDENCE_ONLY, example_builder='majority_baseline', related=('class_imbalance',)),
    Concept('missing_labels', 1, 'Missing target labels', 'definition',
            'Rows with no value in the target column. They are counted separately and left out of class shares.',
            CLASSIFICATION, SCORES),
    # ——— structure ———
    Concept('missingness', 1, 'Missing values', 'contextual',
            'Cells with no recorded value. The report counts them per column, per row and across the whole dataset; '
            'which tokens count as missing follows the parsing policy shown in the technical appendix.',
            TABULAR | {'m3', 'm4'}, SCORES, example_builder='missingness',
            variants={'unlabeled_csv_profile_v1': ConceptVariant(methodology_ref=UNLABELED_POLICY),
                      'tabular_regression_v1': ConceptVariant(methodology_ref=REGRESSION_POLICY)}),
    Concept('duplicates', 1, 'Repeated rows', 'contextual',
            'Rows identical to an earlier row in every parsed column, missing values included. The first row of each '
            'group is not counted as a repeat.', TABULAR | {'m3', 'm4'}, EVIDENCE_ONLY, example_builder='duplicates'),
    Concept('conflicting_labels', 1, 'Conflicting labels', 'interpretive',
            'Groups of rows with identical recorded features but more than one target label.',
            CLASSIFICATION, EVIDENCE_ONLY,
            means='The recorded features alone cannot tell these rows apart, yet their labels differ.',
            does_not_mean='It is not proof of a labelling error: repeated entities, changes over time or a missing '
                          'distinguishing column can explain it.', example_builder='conflicting_labels'),
    Concept('cardinality', 1, 'High cardinality', 'contextual',
            'A non-numeric column with many distinct values: at least 20 values and at least 80% of rows distinct. '
            'Identifiers and free text often look like this.', TABULAR | {'m3', 'm4'}, SCORES, example_builder='high_cardinality'),
    Concept('near_constant', 1, 'Constant and near-constant values', 'contextual',
            'A constant column has one observed value. A near-constant column has one value in at least 95% of rows.',
            TABULAR | {'m3', 'm4'}, SCORES, example_builder='near_constant'),
    # ——— distributions ———
    Concept('quartiles', 1, 'Q1, median and Q3', 'definition',
            'The values below which a quarter, half and three quarters of the observations fall.',
            TABULAR | {'m3', 'm4'}, EVIDENCE_ONLY, related=('iqr_outliers',)),
    Concept('iqr_outliers', 1, 'Values outside the IQR fences', 'interpretive',
            'The interquartile range (IQR) is Q3 minus Q1, the spread of the middle half of the values. A value more than '
            '1.5 × IQR below Q1 or above Q3 is counted as outside the fences. Under this methodology the share is of all '
            'rows, and non-finite values count as outside.',
            TABULAR | {'m3', 'm4'}, SCORES,
            means='The column has unusually many extreme values relative to its middle half; they deserve a look.',
            does_not_mean='An outlier is not an error. Skewed, heavy-tailed or rare legitimate values fall outside the fences too.',
            example_builder='iqr_outliers', related=('quartiles',),
            variants={'unlabeled_csv_profile_v1': _FINITE_IQR,
                      'tabular_regression_v1': ConceptVariant(definition=_FINITE_IQR.definition, methodology_ref=REGRESSION_POLICY)}),
    Concept('non_finite', 1, 'Non-finite values', 'definition',
            'Numeric values that are infinite or not a number. They are counted separately from missing values.',
            TABULAR | {'m3', 'm4'}, EVIDENCE_ONLY),
    # ——— leakage ———
    Concept('leakage_name_review', 1, 'Name-based leakage review', 'interpretive',
            'A check of column names for words suggesting the column records the outcome itself or something known only '
            'after it. Strong candidates lower the score; review-only names do not.',
            CLASSIFICATION, SCORES,
            means='A column name suggests information that may not exist when a prediction would be made.',
            does_not_mean='Names are only a cue. A clean review does not rule out leakage, and a flagged name is not proof of it.',
            example_builder='leakage_review'),
    # ——— regression ———
    Concept('target_relationship', 1, 'Target relationship', 'interpretive',
            'An exact arithmetic link between the target and input columns found by a bounded search: a copy, an affine '
            'transform, or a sum of two columns, verified on every overlapping row.',
            REGRESSION, RELATIONSHIPS,
            means='The target can be computed from these inputs on the verified rows.',
            does_not_mean='It does not show the input is available at prediction time, or that a model uses it. Unsearched '
                          'pairs remain unknown.', example_builder='target_relationship'),
    Concept('declared_constraints', 1, 'Declared constraints', 'contextual',
            'Rules you supplied for the target, such as a range, integer values or non-negative values. Violations are '
            'counted; no value is removed.', REGRESSION, REGRESSION_POLICY, example_builder='declared_constraints'),
    Concept('no_score', 1, 'No score for this report', 'definition',
            'This workflow has no validated way to combine its evidence into one number, so it reports evidence and review '
            'priorities without a score.', UNSCORED | {'m3', 'm4', 'temporal'} | MODALITY, UNLABELED_POLICY,
            variants={'tabular_regression_v1': ConceptVariant(methodology_ref=REGRESSION_POLICY),
                      TEXT_ID: _NO_SCORE_BY_MEANING, IMAGE_ID: _NO_SCORE_BY_MEANING,
                      CROSS_ID: ConceptVariant(methodology_ref=M9_REF)}),
    # ——— M3: annotations, multilabel, multi-output, readiness ———
    Concept('annotation_expectation', 1, 'Annotation expectation and observation', 'interpretive',
            'Each label cell is described on separate axes: whether a label was expected (expected, optional or unknown), '
            'what was observed (well-formed, absent or invalid), and any declared status such as intentional absence.',
            M3, 'M3 Annotation Semantics And Coverage',
            means='Missing labels are counted as gaps only where a label was expected.',
            does_not_mean='An expected label being present does not show it is correct; validity is declared, not verified.'),
    Concept('annotation_coverage', 1, 'Observed and expected coverage', 'contextual',
            'Observed coverage is supplied labels over all rows. Expected coverage is supplied expected labels over the '
            'resolved expected requirements, shown beside the rows whose expectation is unknown.',
            M3, 'M3 Annotation Semantics And Coverage'),
    Concept('label_cardinality', 1, 'Label cardinality and density', 'contextual',
            'Cardinality is the mean number of positive labels per complete label vector; density is that mean divided by '
            'the number of declared labels. Partial vectors give only lower and upper bounds.',
            M3, 'M3 Multilabel Indicators'),
    Concept('jaccard', 1, 'Jaccard overlap of two labels', 'contextual',
            'Among rows where both labels are known, the share positive for both out of those positive for at least one. '
            'Each label pair uses its own jointly observed rows.', M3, 'M3 Multilabel Indicators'),
    Concept('output_correlation', 1, 'Correlation between outputs (Pearson)', 'interpretive',
            'A measure from −1 to 1 of how closely two numeric outputs move together on rows where both are finite. It '
            'needs at least 20 finite pairs and five distinct values per output.',
            M3, 'M3 Multi-output Numerical Evidence',
            means='The two outputs rise and fall together (or oppositely) on the paired rows.',
            does_not_mean='It does not show that one output causes the other or that either can be dropped.'),
    Concept('central_span', 1, 'Central 90% span and Bowley skewness', 'definition',
            'The central 90% span is the 95th percentile minus the 5th. Bowley skewness compares the distances from the '
            'median to Q1 and Q3: zero is symmetric, positive leans to high values.', M3 | REGRESSION, 'M3 Multi-output Numerical Evidence'),
    Concept('quantitative_eligibility', 1, 'Quantitative eligibility', 'interpretive',
            'Whether a selected input enters numeric summaries for clustering or anomaly readiness. Declared quantitative '
            'fields enter; declared categories and identifiers never do; undeclared numeric fields enter as an assumption.',
            M3, 'M3 Conditional Unsupervised Readiness',
            means='The field is summarised as a measurement under the stated assumption.',
            does_not_mean='Numeric storage alone does not make a field a measurement; no data is transformed.'),
    Concept('scale_ratio', 1, 'Scale ratio', 'contextual',
            'The largest interquartile range among eligible quantitative inputs divided by the smallest. Ratios of 10 or '
            'more prompt a review when the method is scale-sensitive.', M3, 'M3 Conditional Unsupervised Readiness'),
    Concept('anomaly_candidates', 1, 'Marginal extreme candidates', 'interpretive',
            'Rows with at least one eligible input outside its 1.5 × IQR fences, counted for anomaly readiness.',
            M3, 'M3 Conditional Unsupervised Readiness',
            means='These rows hold at least one extreme value on a single input.',
            does_not_mean='They are not established anomalies, and rare or extreme rows can be legitimate.'),
    Concept('cohort_contrast', 1, 'Annotation population contrast', 'interpretive',
            'A comparison of an input between rows with and without annotations, by median and IQR for measurements or by '
            'total variation for categories (half the summed absolute differences in category shares).',
            M3, 'M3 Annotation Semantics And Coverage',
            means='The labelled and unlabelled rows differ on this input within this file.',
            does_not_mean='It does not establish why labels are missing, representativeness or a deployment shift.'),
    Concept('repeated_inputs', 1, 'Repeated-input disagreement', 'interpretive',
            'Rows with identical selected inputs whose observed labels or outputs differ.',
            M3 | REGRESSION, 'M3 Multilabel Indicators',
            means='The selected inputs alone cannot separate these rows, yet their labels or outputs differ.',
            does_not_mean='It does not prove a labelling error; repetition can be legitimate.'),
    # ——— M4: comparisons and advanced analysis ———
    Concept('split_overlap', 1, 'Overlap between sources', 'interpretive',
            'Records, feature vectors or declared keys that appear in two sources, counted as shared distinct groups, '
            'participating rows on each side and multiset intersections.', M4, 'M4 comparative and advanced methods',
            means='The same recorded values occur in both sources under the stated definition.',
            does_not_mean='Overlap is not proof of leakage, and zero overlap holds only for the definitions that completed.'),
    Concept('schema_change', 1, 'Schema change', 'definition',
            'Fields added or removed between versions, and changes of role, storage type or declared meaning.',
            M4, 'M4 comparative and advanced methods'),
    Concept('missingness_change', 1, 'Missingness change (percentage points)', 'definition',
            'The current share of missing values minus the reference share, in percentage points, per field.',
            M4, 'M4 comparative and advanced methods'),
    Concept('total_variation', 1, 'Total variation (categories)', 'contextual',
            'Half the sum of absolute differences between two sources’ category shares over all categories seen in '
            'either: 0 means identical shares, 1 means no shared categories. Review starts at 0.10.',
            M4 | TEMPORAL, 'M4 comparative and advanced methods'),
    Concept('cdf_distance', 1, 'Empirical CDF distance', 'contextual',
            'The largest vertical gap between two sources’ cumulative distributions of a numeric field, from 0 to 1. '
            'Review starts at 0.10.', M4 | TEMPORAL, 'M4 comparative and advanced methods'),
    Concept('wasserstein', 1, 'Wasserstein-1 distance', 'interpretive',
            'The area between two cumulative distributions: roughly how far, in the field’s own units, values shift '
            'between one distribution and the other.', M4 | TEMPORAL, 'M4 comparative and advanced methods',
            means='How large the shift is in the original units.',
            does_not_mean='It is not standardised across fields; compare it with the field’s spread, not across fields.'),
    Concept('significance', 1, 'Statistical significance (optional tests)', 'interpretive',
            'Optional tests run only for explicitly independent rows; their p-values are adjusted for the number of tests '
            'with the Benjamini–Hochberg procedure.', M4, 'M4 comparative and advanced methods',
            means='The difference is unlikely to be sampling noise alone, under the test’s assumptions.',
            does_not_mean='Significance says nothing about size; it never creates or raises a finding’s priority.'),
    Concept('affected_rows', 1, 'Affected-row union', 'definition',
            'The number of distinct rows touched by any record of a finding, each row counted once.', M4,
            'M4 comparative and advanced methods'),
    # ——— M5: temporal reliability ———
    Concept('clock', 1, 'Clock and time zone', 'definition',
            'How each timestamp is read: an instant with a known offset or time zone, a calendar date, or a local time '
            'whose zone is not known. Ambiguous or missing local times around daylight-saving changes are counted, not guessed.',
            TEMPORAL, M5_REF),
    Concept('schedule_continuity', 1, 'Expected schedule and continuity', 'interpretive',
            'With a declared schedule, the time slots each entity is expected to fill; continuity counts the slots that hold '
            'an observation and those that are absent.', TEMPORAL, M5_REF,
            means='Absent slots, supplied missing values and periods outside the declared activity are counted separately.',
            does_not_mean='An absent observation alone does not prove an outage or a collection failure.'),
    Concept('windows', 1, 'Investigation windows', 'definition',
            'The time range divided into equal-span windows (twelve by default, empty windows kept), each compared with a '
            'reference window, the first by default.', TEMPORAL, M5_REF),
    Concept('window_effects', 1, 'Window effects', 'interpretive',
            'Differences between a window and the reference: the change in missing share, total variation for categories, '
            'and CDF distance and Wasserstein-1 for measurements. A window needs 100 supported values to be compared.',
            TEMPORAL, M5_REF,
            means='This window’s values differ from the reference beyond the configured investigation settings.',
            does_not_mean='The settings are investigation defaults, not defect criteria; a difference is not drift detection or a cause.', example_builder='window_effects'),
    Concept('runs', 1, 'Equal-value runs', 'contextual',
            'Consecutive observations of a measurement with exactly the same value, within one entity. Runs break at missing '
            'or invalid values and lifecycle boundaries.', TEMPORAL, M5_REF),
    Concept('volatility', 1, 'Consecutive-difference dispersion', 'contextual',
            'How much successive values of a measurement change, compared between windows.', TEMPORAL, M5_REF),
    Concept('seasonality', 1, 'Declared seasonality', 'definition',
            'Summaries by a declared cycle, such as hour of day, weekday or month, using the clock rules shown in the '
            'declarations.', TEMPORAL, M5_REF),
    Concept('availability_timing', 1, 'Feature availability at prediction time', 'interpretive',
            'Whether a feature’s value existed by the prediction time, judged from the timing rules you declared. Features '
            'without a rule stay unknown.', TEMPORAL, M5_REF,
            means='Under the declared rules, the value was or was not available when a prediction would be made.',
            does_not_mean='It does not show what a pipeline actually used.'),
    Concept('revisions', 1, 'Revisions and as-of values', 'interpretive',
            'Later versions of the same observation, linked by observation keys. An as-of value is the version known at a '
            'given time.', TEMPORAL, M5_REF,
            means='Values changed after first recording; analysis that uses the final version may see information that '
                  'was not known earlier.',
            does_not_mean='A revision is not an error; only the linked keys and recorded times are used.'),
    Concept('maturity', 1, 'Outcome maturity', 'interpretive',
            'Whether an outcome had become known by the time it would be used: unavailable at the training cutoff, missing '
            'but already due, not yet due, or unknown.', TEMPORAL, M5_REF,
            means='Some outcomes could not have been known when the data would have been used for training.',
            does_not_mean='A not-yet-due outcome is expected, not a defect.'),
    Concept('folds', 1, 'Chronological evaluation folds', 'contextual',
            'The training and evaluation periods you supplied, checked for time order, separation of groups or entities, '
            'overlap, horizons, gaps and available lookback.', TEMPORAL, M5_REF),
    # ——— evidence vocabulary (every report) ———
    Concept('priority', 1, 'Priority (High, Moderate, Low)', 'definition',
            'How soon a finding deserves review under this methodology’s rules. It orders the work; it is not a measured '
            'size of harm.', STRUCTURED | CROSS, READING),
    Concept('review_evidence', 1, 'Findings are review evidence', 'interpretive',
            'Each finding reports what the data shows under a stated rule, with its evidence.',
            STRUCTURED | MODALITY, READING,
            means='Something in the data meets a rule that experience says is worth checking.',
            does_not_mean='A finding does not prove a defect, a cause, or that any change is needed; nothing was changed in the data.'),
    Concept('coverage', 1, 'Coverage', 'interpretive',
            'Which checks ran, which were not applicable, blocked or failed, and which searches stopped at a limit.',
            STRUCTURED | MODALITY, PARSING,
            means='The conclusions apply to the checks and scopes that completed.',
            does_not_mean='It is not a percentage of reliability, and a check that did not run concludes nothing.'),
    Concept('not_assessable', 1, 'Not assessable', 'contextual',
            'A check that could not produce a result for a column, with the recorded reason, for example too few finite '
            'values or an interquartile range of zero.', STRUCTURED, PARSING, example_builder='not_assessable'),
    Concept('bounded_search', 1, 'Bounded search', 'interpretive',
            'A search that examined candidates only up to configured limits on pairs, features or work.',
            STRUCTURED | MODALITY, PARSING,
            means='Within the searched scope, the reported results are complete.',
            does_not_mean='Finding nothing in a bounded search does not show that nothing exists beyond it.'),
    Concept('suggested_codes', 1, 'Suggested codes (not applied)', 'definition',
            'Values that often stand for missing or special cases, such as “unknown” or -1, found by a fixed rule set. '
            'They are suggestions only; nothing is applied unless you declare it.', TABULAR, READING),
    Concept('print_profile', 1, 'Print profile', 'definition',
            'What the PDF prints of detailed per-column evidence. “Focused” prints every finding and flagged column and '
            'summarises the rest; “complete” prints every row. The HTML report always lists every row.', STRUCTURED | MODALITY, READING,
            variants={TEXT_ID: _RETAINED, IMAGE_ID: _RETAINED, CROSS_ID: _RETAINED}),
    Concept('summarised_rows', 1, 'Summarised rows', 'definition',
            'Rows the PDF shows as a summary: how many, with the smallest and largest stored values and the column that '
            'has each, or counts per value. Every row is in the HTML report and analysis.json.', STRUCTURED, READING),
    Concept('screen_only', 1, 'Listed on screen', 'definition',
            'A table the HTML report shows in full but this print profile does not print, because its values are printed '
            'elsewhere or summarised. The disclosure under it says where every row is.', STRUCTURED | MODALITY, READING),
    # ——— M6, M7, M9: shared evidence vocabulary ———
    Concept('protected_evidence', 1, 'Protected evidence', 'definition',
            'Source text, images, values and file locations are kept out of this report and its JSON. They carry opaque '
            'references instead; resolving one needs the private local manifest and the original, unchanged sources.',
            MODALITY, REPR_REF, variants={CROSS_ID: ConceptVariant(methodology_ref=M9_REF)}),
    # The same term for an export whose recorded disclosure policy includes explicitly chosen examples.
    Concept('protected_evidence_disclosed', 1, 'Protected evidence', 'definition',
            'Source text, images, values and file locations stay out of this report and its JSON, except the examples '
            'chosen for disclosure, shown in their own section. Everything else carries opaque references; resolving one '
            'needs the private local manifest and the original, unchanged sources.',
            MODALITY, REPR_REF, variants={CROSS_ID: ConceptVariant(methodology_ref=M9_REF)}),
    # ——— M6 text ———
    Concept('framed_records', 1, 'Framed records and invalidity', 'definition',
            'Every record read from the sources is counted. Malformed lines and invalid items stay counted, with their '
            'locations, rather than being dropped; usable neighbouring items are kept.', TEXT, REPR_REF),
    Concept('grapheme_jaccard', 1, 'Five-grapheme Jaccard similarity', 'interpretive',
            'Two texts are compared as sets of overlapping five-character pieces (graphemes): shared pieces divided by all '
            'distinct pieces. A pair at 0.80 or above is a review candidate.', TEXT, REPR_REF,
            means='The two texts share most of their character sequences.',
            does_not_mean='Similarity is not transitive, and it does not show copying, contamination or that either text is wrong.', example_builder='grapheme_jaccard'),
    Concept('verified_candidates', 1, 'Candidate versus verified pair', 'definition',
            'A fast hashing index (MinHash) only proposes candidate pairs. Each candidate is then checked by counting its '
            'actual shared pieces, so a hash collision cannot create a reported pair.', TEXT, REPR_REF),
    Concept('shared_passages', 1, 'Shared literal passages', 'interpretive',
            'Literal passages found through winnowed fingerprints and verified in the text, including a passage contained '
            'in a longer document whose overall similarity is low.', TEXT, REPR_REF,
            means='The same character sequence occurs in both places.',
            does_not_mean='Shared templates, prompts and related chunks can be legitimate; a passage alone does not establish contamination.', example_builder='shared_passages'),
    Concept('semantic_neighbours', 1, 'Semantic neighbours (cosine)', 'interpretive',
            'An optional local embedding model turns text windows into vectors; cosine similarity ranks the closest windows.',
            TEXT, REPR_REF,
            means='The windows are close in the model’s representation.',
            does_not_mean='Segment similarity does not establish that two documents are equivalent or say the same thing.'),
    Concept('language_id', 1, 'Language identification', 'definition',
            'An optional local detector assigns a language from a declared set to bounded source windows. Its margins are '
            'not calibrated probabilities.', TEXT, REPR_REF),
    # ——— M7 images ———
    Concept('exact_representations', 1, 'Exact bytes, raster and oriented pixels', 'definition',
            'Three separate equality checks: identical file bytes, identical decoded pixels in the native format, and '
            'identical pixels after applying the recorded orientation. A re-encoded copy can match on pixels but not bytes.',
            IMAGE, REPR_REF),
    Concept('perceptual_signature', 1, 'Perceptual signature', 'definition',
            'A 64-bit fingerprint of the coarse brightness pattern of each eligible decoded image (a DCT signature). '
            'Signatures are compared by Hamming distance.', IMAGE, REPR_REF, related=('hamming_distance',)),
    Concept('hamming_distance', 1, 'Hamming distance', 'definition',
            'The number of bits that differ between two 64-bit signatures; 0 means identical signatures. The search checks '
            'distances up to six.', IMAGE, REPR_REF, example_builder='hamming_distance'),
    Concept('duplicate_candidate', 1, 'Duplicate candidate', 'interpretive',
            'A pair of images whose perceptual signatures, or optional model embeddings, are close enough to inspect.',
            IMAGE, REPR_REF,
            means='The images look alike under this method.',
            does_not_mean='Similarity alone proves neither leakage nor an incorrect label; plain or low-detail images can look alike.', example_builder='duplicate_candidate'),
    Concept('coordinate_frames', 1, 'Coordinate frames and taxonomy', 'definition',
            'Annotations are compared only when their coordinate frame (encoded, oriented or explicitly mapped) and their '
            'category meanings are known to be compatible; otherwise the comparison is reported as blocked.', IMAGE, REPR_REF),
    # ——— M9 cross-representation ———
    Concept('logical_identity', 1, 'Logical identity', 'definition',
            'The declared key that says which records describe the same thing across sources. Keys are typed: the text “7” '
            'and the number 7 differ unless a normalised view is declared.', CROSS, M9_REF, example_builder='logical_identity'),
    Concept('association_cardinality', 1, 'Association cardinality', 'definition',
            'The declared rule for how many records may link on each side, such as one-to-one or one-to-many. Repeated '
            'keys, missing endpoints and required gaps are counted separately.', CROSS, M9_REF),
    Concept('reconciliation_outcomes', 1, 'Reconciliation outcomes', 'interpretive',
            'Under each declared rule, a record agrees, disagrees, has conflicting supplied evidence, or cannot be resolved.',
            CROSS, M9_REF,
            means='The supplied values compare as stated under the declared conventions and tolerance.',
            does_not_mean='Agreement is with the declared evidence only; a declared authority is a comparison policy, not external truth.', example_builder='reconciliation_outcomes'),
    Concept('competing_evidence', 1, 'Conflicting supplied evidence', 'interpretive',
            'More than one eligible source supplies a different value for the same fact. Every eligible value is kept.',
            CROSS, M9_REF,
            means='The sources disagree about this fact.',
            does_not_mean='It does not say which value is correct.'),
    Concept('separation', 1, 'Cross-source separation', 'interpretive',
            'A declared requirement that sources share no entity, group, text or image. Exact overlaps are counted once '
            'per record on each side.', CROSS, M9_REF,
            means='An exact overlap violates the declared requirement.',
            does_not_mean='Similar-image candidates do not establish a violation, and a bounded search cannot establish absence.'),
    Concept('model_candidates', 1, 'Model candidates', 'interpretive',
            'Optional local models score whether retrieved evidence supports or contradicts a claim, or whether an image '
            'and its text belong together, within a narrow qualified profile.', CROSS, M9_REF,
            means='The model’s scores met the qualified thresholds for this profile.',
            does_not_mean='Raw scores are not probabilities, and a neutral result or missed retrieval never shows a claim is false.'),
    Concept('abstention', 1, 'Abstention', 'definition',
            'The model gives no judgment when a claim, language, length or evidence falls outside its qualified profile. '
            'Abstentions are counted, never treated as agreement.', CROSS, M9_REF),
)

CATALOGUE = {c.id: c for c in CONCEPTS}
if len(CATALOGUE) != len(CONCEPTS):
    raise ValueError('Concept ids repeat.')

# Recorded finding codes and the concepts their cards and index rows use.
FINDING_CONCEPTS = {
    'target_imbalance': ('class_imbalance', 'majority_baseline'),
    'numeric_outlier_concentration': ('iqr_outliers',),
    'leakage_review_prompts': ('leakage_name_review',),
    'possible_target_leakage': ('leakage_name_review',),
    'severe_feature_missingness': ('missingness',),
    'feature_missingness': ('missingness',),
    'column_missingness': ('missingness',),
    'high_missingness': ('missingness',),
    'fully_missing_columns': ('missingness',),
    'dataset_missingness': ('missingness',),
    'widespread_row_missingness': ('missingness',),
    'duplicate_records': ('duplicates',),
    'conflicting_target_labels': ('conflicting_labels',),
    'constant_fields': ('near_constant',),
    'near_constant_fields': ('near_constant',),
    'high_cardinality_categoricals': ('cardinality',),
    'missing_target_labels': ('missing_labels',),
    'regression_relationships_unknown': ('target_relationship',),
    'regression_relationships_unavailable_at_prediction': ('target_relationship',),
    'regression_declared_constraints': ('declared_constraints',),
    'regression_target_extremes': ('iqr_outliers',),
    'regression_missing_targets': ('missingness',),
    'regression_nonfinite_targets': ('non_finite',),
}


def concepts_for(family):
    return [c for c in CONCEPTS if family in c.families]


def catalogue_bytes(family):
    """Canonical bytes of the entries a family uses, for its presentation identity. The families field is left out,
    so extending a concept to another workflow does not change this family's identity; its wording does."""
    entries = [{k: v for k, v in asdict(c).items() if k != 'families'} | {'variants': {k: asdict(v) for k, v in sorted(c.variants.items())}}
               for c in concepts_for(family)]
    used = {c.id for c in concepts_for(family)}
    findings = {code: ids for code, ids in sorted(FINDING_CONCEPTS.items()) if set(ids) & used}
    return json.dumps({'version': CATALOGUE_VERSION, 'concepts': entries, 'finding_concepts': findings},
                      sort_keys=True, ensure_ascii=True).encode()


