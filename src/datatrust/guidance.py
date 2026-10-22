"""Evidence-grounded guidance for every finding: finding_guidance_v1.

For each finding a result records, guidance states what was observed (only values the canonical result already
holds, with their populations and denominators), the possible impact, what to investigate first, conditional
options with their prerequisites, when to avoid them and how to verify their consequences, and what the run did
not assess. It never prescribes a pipeline, ranks options as optimal, or implies analysis that did not run.

The block is computed once, when a result is produced, and stored on the result (``result.guidance``), so JSON,
HTML, PDF and saved views carry the same text and reloaded results keep their exact bytes. Results produced
before this version carry no block.
"""
from __future__ import annotations

VERSION = "finding_guidance_v1"


def _option(option, prerequisites, avoid_when, verify):
    return {"option": option, "prerequisites": prerequisites, "avoid_when": avoid_when, "verify": verify}


NO_DATA_CHANGE = "Not applicable: this changes no data."

# ——— The catalogue: one entry per kind of finding. Wording is conditional where the evidence differs. ———

CATALOGUE = {
    "missing_values": {
        "impact": ["Rows with gaps may be dropped or filled by later tools without notice, changing who is represented.",
                   "If missingness depends on the outcome or on a group, both deletion and imputation can bias results."],
        "investigate": ["Which columns and rows carry the gaps, and whether they share a source, period or group.",
                        "Whether a gap means 'not collected', 'not applicable' or 'zero', which the file alone cannot say."],
        "options": [
            _option("Keep gaps and use methods that accept missing values", "The downstream method handles missing values natively.",
                    "The method silently drops or zero-fills them.", "Confirm the row count and class shares that reach the method equal those analysed here."),
            _option("Impute values", "The meaning of a gap is known and imputation fits it (for example, values missing at random within groups).",
                    "Gaps are structural ('not applicable') or concentrated in one outcome or group; or the imputer is fitted on data that includes evaluation rows.",
                    "Fit the imputer on training rows only; add a was-missing indicator; compare results with and without imputation on the same split."),
            _option("Drop affected rows or columns", "The affected share is small and unrelated to the outcome.",
                    "Gaps concentrate in one class or group, or a column is mostly empty but informative when present.",
                    "Report how many rows, and which class and group shares, remain after dropping."),
        ],
        "unknowns": ["Why values are missing, and whether text placeholders such as 'unknown' stand for missing values, was not assessed."],
    },
    "missing_targets": {
        "impact": ["Rows without a target cannot be used for supervised training or evaluation and were excluded from target calculations.",
                   "If unlabeled rows differ from labeled ones, results describe only the labeled population."],
        "investigate": ["Why the target is absent: pending, not applicable, or lost.", "Whether unlabeled rows differ in their feature distributions from labeled rows."],
        "options": [
            _option("Exclude unlabeled rows from supervised use and say so", "None.", "The unlabeled rows are the population the model will serve.",
                    "Compare feature distributions of labeled and unlabeled rows and report any difference."),
            _option("Obtain the missing labels", "The labels exist upstream or can be collected.", "Labels would be produced by a model or rule derived from the same features.",
                    "Re-run this analysis once labels are added and compare target shares."),
        ],
        "unknowns": ["Whether absent targets are pending, inapplicable or lost was not declared."],
    },
    "duplicates": {
        "impact": ["Identical rows give repeated cases more weight.",
                   "If copies land on both sides of a train/test split, evaluation can look better than it will be on new data."],
        "investigate": ["Whether repetition reflects genuine repeated events (the same values recurring legitimately) or copying.",
                        "Whether an identifier or timestamp exists that would make repeated rows distinct."],
        "options": [
            _option("Keep repeated rows but split by group", "An identifier or the full row can define groups.", "Groups cannot be defined.",
                    "Confirm that no group appears in more than one split."),
            _option("Remove exact copies", "Repetition is confirmed to be copying, not repeated events.",
                    "Rows are legitimate repeated observations; removing them changes the represented frequencies.",
                    "Report row counts and class shares before and after; re-run this analysis on the result."),
        ],
        "unknowns": ["Whether repeated rows are legitimate repeated events or copies was not assessed."],
    },
    "label_conflicts": {
        "impact": ["Identical recorded inputs with different outcomes limit how well any model can fit those cases.",
                   "Conflicts may reflect omitted context, outcomes that are genuinely random, or annotation differences."],
        "investigate": ["A sample of conflicting groups: what distinguishes them that the file does not record.",
                        "Whether conflicts concentrate in one source, annotator or period."],
        "options": [
            _option("Keep all rows and treat the variation as real", "The variation is plausible for the outcome.", "One label is known to be wrong.",
                    "Report the conflicting share alongside model results."),
            _option("Adjudicate labels", "A reviewer or reference can decide the correct label.", "No reliable reference exists; majority voting would invent certainty.",
                    "Record changed labels and re-run this analysis."),
            _option("Add the missing context as features", "The distinguishing information exists and is available at prediction time.",
                    "The added information is only known after the outcome.", "Re-check repeated-input conflicts with the added features."),
        ],
        "unknowns": ["Which label, if any, is correct was not assessed."],
    },
    "class_imbalance": {
        "impact": ["Accuracy can look high while the minority class is mostly missed.",
                   "Default decision thresholds and probability outputs may suit the majority class."],
        "investigate": ["Whether the observed class shares match the population the model will serve.",
                        "How many minority rows each later split will contain."],
        "options": [
            _option("Use class-sensitive evaluation", "None.", NO_DATA_CHANGE,
                    "Report per-class precision and recall, precision–recall curves and the confusion matrix at the chosen threshold, on a held-out split."),
            _option("Choose class weights or a decision threshold", "The relative cost of each error type is known or can be stated.",
                    "Calibrated probabilities are the deliverable and will not be recalibrated afterwards.",
                    "Compare per-class metrics and calibration before and after, on the same split."),
            _option("Resample the training data", "Rows are independent, and resampling happens inside training folds only.",
                    "Rows are grouped or time-ordered so resampled copies would cross splits; or resampling would precede the train/test split.",
                    "Check minority-class metrics on untouched validation data; confirm no resampled row appears in evaluation."),
            _option("Collect more minority examples", "More examples can be obtained from the same population.", "New examples come from a different population.",
                    "Re-run this analysis and compare class shares and feature distributions by source."),
        ],
        "unknowns": ["The deployment population's class shares and the cost of each error type were not supplied."],
    },
    "single_class": {
        "impact": ["With one observed class or a constant target, there is no variation to learn or evaluate."],
        "investigate": ["Whether the file is a filtered subset, and whether other outcomes exist upstream."],
        "options": [
            _option("Recover the excluded outcomes", "The full population is available.", "The task genuinely has a single outcome.", "Re-run this analysis and confirm two or more outcomes."),
            _option("Reframe the task", "The question can be posed without a varying target (for example, profiling or anomaly review).", "A supervised model is still required.",
                    "Run the matching DataTrust mode for the reframed task."),
        ],
        "unknowns": ["Whether other outcomes exist outside this file was not assessed."],
    },
    "limited_support": {
        "impact": ["Few observations, or values too close to numerical precision, make summary statistics and later evaluation unstable."],
        "investigate": ["How many observations each class, label or output has, and whether more exist."],
        "options": [
            _option("Report uncertainty alongside every metric", "None.", NO_DATA_CHANGE, "Give confidence intervals or per-split counts with each metric."),
            _option("Merge rare categories or outputs", "The merged categories mean the same thing for the task.", "The rare category is the one that matters.",
                    "Report category counts before and after merging."),
            _option("Collect more data", "More observations can be obtained.", "New data comes from a different population.", "Re-run this analysis on the larger file."),
        ],
        "unknowns": ["No minimum sample size is validated by DataTrust; the review gates are internal."],
    },
    "name_leakage": {
        "impact": ["A feature that is recorded after the outcome, or derived from it, makes evaluation optimistic and fails at prediction time."],
        "investigate": ["For each named column, when its value is recorded relative to the outcome.",
                        "How each column is produced: collected before the decision, or written back afterwards."],
        "options": [
            _option("Keep the column after confirming availability", "Its value is known at the prediction point.", "Its value is set or updated after the outcome.",
                    "Document the availability decision; compare a model with and without the column on a time-ordered split."),
            _option("Exclude the column", "Its value is recorded after the outcome or derived from it.", "It is available at prediction time and the name match was coincidental.",
                    "Re-run this analysis without it and record the change."),
        ],
        "unknowns": ["A name check cannot establish when values become available; columns with neutral names were not assessed for availability."],
    },
    "declared_unavailable": {
        "impact": ["Inputs you declared unavailable at prediction time would make evaluation optimistic if used."],
        "investigate": ["Whether these inputs are present in the feature set any downstream model will use."],
        "options": [
            _option("Exclude the declared inputs from training and evaluation", "None.", "The declaration was wrong; correct it and re-run instead.",
                    "Confirm the final feature list omits them."),
        ],
        "unknowns": ["Actual model use of these inputs was not observed; the declaration is yours."],
    },
    "target_relationship": {
        "impact": ["A target reproducible from inputs means those inputs carry the answer; if they are not available at prediction time, evaluation is invalid."],
        "investigate": ["How the related inputs are produced, and whether they are known before the outcome."],
        "options": [
            _option("Exclude the related inputs", "They are recorded after, or derived from, the outcome.", "They are legitimate, available predictors.",
                    "Re-run this analysis; the relationship finding should no longer apply."),
            _option("Keep them with a documented availability decision", "They are available at prediction time.", "Availability is uncertain.",
                    "Validate on a time-ordered split that reflects the real prediction point."),
        ],
        "unknowns": ["The search covers its stated methods and bounds only; relationships outside them were not searched."],
    },
    "target_relationship_unknown": {
        "impact": ["A target reproducible from inputs whose availability is unknown may be leakage or a legitimate deterministic rule."],
        "investigate": ["Declare each related input's availability, then re-run."],
        "options": [
            _option("Declare availability and re-run", "You know when each input becomes available.", NO_DATA_CHANGE,
                    "The re-run classifies the relationship as available or unavailable at prediction time."),
        ],
        "unknowns": ["Availability of the related inputs was not declared."],
    },
    "constant_features": {
        "impact": ["A column with one value (or nearly one) carries little or no information for most methods, and rare values may be noise or important exceptions."],
        "investigate": ["Whether the rare values are meaningful exceptions, errors, or a coding of missing values."],
        "options": [
            _option("Exclude constant columns", "The column has exactly one value in every population that matters.", "The data is a subset and other subsets vary.",
                    "Confirm the column is constant in every split."),
            _option("Keep near-constant columns", "The rare values carry meaning for the outcome.", "The rare values are errors or placeholders.",
                    "Check how the rare values relate to the target before deciding."),
        ],
        "unknowns": ["Whether rare values are meaningful was not assessed."],
    },
    "high_cardinality": {
        "impact": ["Columns with many distinct values may be identifiers or free text; one-hot encoding them inflates dimensionality and can memorise rows."],
        "investigate": ["Whether each column is an identifier, free text or a category with many levels."],
        "options": [
            _option("Exclude identifiers from features", "The column identifies records rather than describing them.", "Its values carry meaning (for example, a product code).",
                    "Use identifiers for grouping splits instead, and confirm no group crosses splits."),
            _option("Group rare levels or use target-free encodings", "The column is a genuine category.", "Encoders are fitted on data that includes evaluation rows (target encoding leaks).",
                    "Fit encoders on training rows only; compare validation metrics."),
        ],
        "unknowns": ["The semantic type of these columns was not assessed."],
    },
    "outliers": {
        "impact": ["Values outside the 1.5 × IQR fences can dominate scale-sensitive methods and summary statistics.",
                   "They may be legitimate tails, unit or entry errors, or sentinel codes."],
        "investigate": ["The extreme values themselves: are they plausible for the field's meaning and unit?",
                        "Whether a single code (for example −1 or 999) accounts for many of them."],
        "options": [
            _option("Keep the values and use robust methods or transforms", "The values are legitimate.", "They are confirmed errors or sentinel codes.",
                    "Compare model behaviour with and without the transform on the same split."),
            _option("Cap (winsorise) the values", "Extremes are legitimate but over-influential, and the cap is chosen from training rows only.",
                    "Tails carry the signal you care about (for example, fraud amounts); or the cap uses evaluation data.",
                    "Report how many values change and compare metrics on tail cases specifically."),
            _option("Correct or remove values", "They are confirmed errors from source records.", "They are legitimate rare observations.",
                    "Re-run this analysis and record which rows changed."),
        ],
        "unknowns": ["Whether extreme values are legitimate was not assessed; an IQR flag does not establish an error."],
    },
    "concentration": {
        "impact": ["Many targets at one value or boundary can indicate censoring, default values or a genuinely concentrated outcome."],
        "investigate": ["Whether the common value is a floor, ceiling, default or placeholder."],
        "options": [
            _option("Model the concentration explicitly", "The concentrated value is a real outcome (for example, zero counts).", "It is a placeholder.",
                    "Check residuals at the concentrated value separately."),
            _option("Treat the value as censored or missing", "It is a measurement limit or placeholder.", "It is a real outcome.",
                    "Re-run this analysis with the value declared missing and compare the target distribution."),
        ],
        "unknowns": ["Why values concentrate was not assessed."],
    },
    "non_finite": {
        "impact": ["Infinity values break many calculations or are silently dropped."],
        "investigate": ["Whether infinities come from division by zero or are used as codes."],
        "options": [
            _option("Recompute at the source", "The originating calculation is known.", "Infinity is a deliberate code with a documented meaning.",
                    "Re-run this analysis; the non-finite count should be zero."),
            _option("Declare them missing", "They represent 'undefined'.", "They carry a distinct meaning.", "Compare counts before and after."),
        ],
        "unknowns": ["The origin of non-finite values was not assessed."],
    },
    "scale": {
        "impact": ["Inputs on very different scales let distance- and gradient-based methods weight some inputs far more than others."],
        "investigate": ["Each input's unit and range, and whether the method you plan is scale-sensitive."],
        "options": [
            _option("Standardise or normalise inputs", "The planned method is scale-sensitive.", "The method is scale-invariant (for example, tree models), or scaling is fitted on evaluation rows.",
                    "Fit the scaler on training rows only; compare results."),
        ],
        "unknowns": ["Whether a scale-sensitive method will be used was not declared."],
    },
    "declared_constraints": {
        "impact": ["Values that violate requirements you declared contradict the intended definition of the data."],
        "investigate": ["The violating values against the declaration: is the value wrong, or the requirement?"],
        "options": [
            _option("Correct values at the source", "The requirement is right and the values are errors.", "The requirement was mis-specified.",
                    "Re-run this analysis; violations should be zero."),
            _option("Revise the declaration", "The requirement was too strict.", "The values are genuinely invalid.", "Re-run with the revised declaration."),
        ],
        "unknowns": ["DataTrust checks your declaration; it does not independently verify it."],
    },
    "annotation_validity": {
        "impact": ["Invalid or contradictory annotations are excluded from annotation evidence, reducing coverage."],
        "investigate": ["The encodings and status tokens actually supplied, against the declared mapping."],
        "options": [
            _option("Fix the encodings or the status mapping", "The intended value is clear.", "The intended value is ambiguous.", "Re-run this analysis; invalid counts should fall."),
        ],
        "unknowns": ["Whether valid annotations are correct was not assessed."],
    },
    "no_features": {
        "impact": ["Without feature columns, no input-to-target analysis is possible."],
        "investigate": ["Whether feature columns were excluded by the role declarations or are absent from the file."],
        "options": [_option("Declare feature columns or supply them", "Inputs exist.", "None.", "Re-run this analysis.")],
        "unknowns": [],
    },
}

# ——— M4 comparisons ———
CATALOGUE["missingness_structure"] = {
    "impact": ["Missingness that concentrates in some features or co-occurs across them can reflect a collection process that differs by group or period."],
    "investigate": ["The retained missingness patterns and which rows share them."],
    "options": [
        _option("Model missingness explicitly (indicator features)", "Missingness is informative and its pattern is known at prediction time.",
                "Missingness is caused by the outcome itself.", "Compare results with and without indicators on the same split."),
        _option("Impute within groups", "The pattern is tied to a known group.", "The grouping is only known after the outcome.", "Compare group-level distributions before and after."),
    ],
    "unknowns": ["The cause of the missingness pattern was not assessed."],
}
CATALOGUE["input_dependence"] = {
    "impact": ["Strongly dependent inputs can make coefficients unstable and hide which input matters."],
    "investigate": ["Whether the dependent inputs measure the same thing, or one is derived from another."],
    "options": [
        _option("Keep one representative input", "The inputs are redundant for the task.", "Each carries distinct information you need.", "Compare validation metrics with each choice."),
        _option("Keep both and use regularisation", "Interpretation of individual coefficients is not required.", "You need per-input explanations.", "Check coefficient stability across folds."),
    ],
    "unknowns": ["Dependence is measured within the bounded pairs searched; other pairs were not assessed."],
}
CATALOGUE["split_separation"] = {
    "impact": ["Records or groups shared across evaluation sources make evaluation optimistic."],
    "investigate": ["The shared identities or groups, and how the split was produced."],
    "options": [
        _option("Rebuild the split by group or identity", "A grouping key exists.", "None.", "Re-run this comparison; the separation finding should no longer apply."),
    ],
    "unknowns": ["Overlap is checked on the declared keys and selected inputs only."],
}
CATALOGUE["split_overlap"] = {
    "impact": ["Evaluation rows that share selected input vectors with other sources may be near-copies, which inflates measured performance."],
    "investigate": ["Whether shared input vectors are the same entities or legitimately identical cases."],
    "options": [
        _option("Remove or regroup shared rows across splits", "Shared rows are the same entities.", "Identical inputs are legitimately common (for example, small categorical spaces).",
                "Re-run this comparison and report the remaining overlap."),
    ],
    "unknowns": ["Whether shared inputs are the same entities was not assessed."],
}
CATALOGUE["schema_change"] = {
    "impact": ["Changed columns or representations between sources break pipelines or silently change meaning."],
    "investigate": ["Each changed column: renamed, retyped, re-encoded or new."],
    "options": [
        _option("Align schemas before use", "The mapping between versions is known.", "Columns changed meaning, not just name.", "Re-run this comparison after alignment."),
    ],
    "unknowns": ["Semantic equivalence of renamed columns was not assessed."],
}
CATALOGUE["population_shift"] = {
    "impact": ["Sources whose supported populations differ may not represent each other; models may not transfer."],
    "investigate": ["Which populations differ and whether the difference is expected (time, region, sampling)."],
    "options": [
        _option("Evaluate per population", "Populations can be identified.", NO_DATA_CHANGE, "Report metrics for each source separately."),
        _option("Reweight or stratify", "The target population's composition is known.", "It is not known.", "Compare reweighted and unweighted results."),
    ],
    "unknowns": ["Whether the difference matters for your use was not assessed."],
}
# ——— M5 temporal ———
CATALOGUE["temporal_schedule"] = {
    "impact": ["Absent records against a declared schedule leave gaps that windowed features and evaluation may silently fill or skip."],
    "investigate": ["When and where records are absent, and whether collection stopped or values were not recorded."],
    "options": [
        _option("Treat absences as missing observations", "The schedule is correct.", "The schedule was mis-declared.", "Re-run with the absences declared; check affected windows."),
        _option("Correct the declared schedule", "Collection really follows another cadence.", "The absences are real.", "Re-run this audit."),
    ],
    "unknowns": ["Why records are absent was not assessed."],
}
CATALOGUE["temporal_uniqueness"] = {
    "impact": ["Repeated timestamps for an entity break the assumption of one value per time point."],
    "investigate": ["Whether duplicates are revisions, copies or simultaneous measurements."],
    "options": [
        _option("Resolve duplicates by a documented rule", "A rule exists (latest revision, source priority).", "The rule uses information unavailable at prediction time.",
                "Re-run this audit; uniqueness violations should be zero."),
    ],
    "unknowns": ["Which duplicate is correct was not assessed."],
}
CATALOGUE["temporal_history"] = {
    "impact": ["Histories shorter than the declared lookback produce windows with fewer observations than features assume."],
    "investigate": ["Which entities have short histories and whether they are new or truncated."],
    "options": [
        _option("Restrict to entities with full history", "Short histories are rare.", "New entities are part of the deployment population.", "Report how many entities remain."),
        _option("Mark incomplete windows", "Models can use an indicator.", "None.", "Compare metrics for complete and incomplete windows."),
    ],
    "unknowns": ["Why histories are short was not assessed."],
}
CATALOGUE["simultaneous_disagreement"] = {
    "impact": ["Disagreeing measurements at the same time point make the true value uncertain."],
    "investigate": ["Which sources disagree and whether one is authoritative."],
    "options": [
        _option("Choose a source by documented priority", "One source is authoritative.", "Priority depends on information known only later.", "Re-run this audit."),
    ],
    "unknowns": ["Which measurement is correct was not assessed."],
}
CATALOGUE["clock_resolution"] = {
    "impact": ["Unresolved clock values cannot be ordered, so availability and window checks exclude them."],
    "investigate": ["The unresolved values and the declared clock format or time zone."],
    "options": [_option("Correct the clock declaration or the values", "The intended format is known.", "None.", "Re-run this audit; unresolved counts should fall.")],
    "unknowns": ["Records with unresolved clocks were not assessed by time-dependent checks."],
}
CATALOGUE["temporal_order"] = {
    "impact": ["Backward steps in source order can indicate merged files, corrections, or clock problems."],
    "investigate": ["Where order reverses and whether the file was concatenated."],
    "options": [_option("Sort by the declared clock before use", "The clock is trustworthy.", "Order itself carries meaning (for example, arrival order).", "Re-run this audit.")],
    "unknowns": ["The cause of the reversals was not assessed."],
}
CATALOGUE["behavior_change"] = {
    "impact": ["Changes in level, dispersion or window behaviour can reflect real change, collection changes or instrumentation issues; models trained across them may not transfer."],
    "investigate": ["What changed around the flagged windows: process, instrument, definition or population."],
    "options": [
        _option("Evaluate on the most recent period", "The latest period represents deployment.", NO_DATA_CHANGE, "Report metrics per period."),
        _option("Mark or exclude the affected periods", "The change is a known artifact.", "The change is real behaviour the model must learn.", "Compare models with and without the periods."),
    ],
    "unknowns": ["The cause of the change was not assessed; these are investigation candidates."],
}
CATALOGUE["flat_runs"] = {
    "impact": ["Long runs of identical values can indicate stuck sensors, forward-filled gaps or legitimately stable states."],
    "investigate": ["Whether the runs coincide with known outages or fills."],
    "options": [_option("Declare suspected fills as missing", "Fills are confirmed.", "Stability is real.", "Re-run this audit and compare.")],
    "unknowns": ["Whether runs are genuine was not assessed."],
}
CATALOGUE["availability_violation"] = {
    "impact": ["Values that become available after the declared cutoff would make evaluation optimistic if used at that cutoff."],
    "investigate": ["The affected features and records, against the declared availability rule."],
    "options": [
        _option("Use only values available at each cutoff (as-of joins)", "Availability times are recorded.", "None.", "Re-run this audit; violations should be zero."),
        _option("Correct the declaration", "The availability rule was mis-declared.", "Values really arrive late.", "Re-run this audit."),
    ],
    "unknowns": ["Checks follow your declarations; undeclared features were not assessed for availability."],
}
CATALOGUE["revision_mismatch"] = {
    "impact": ["Selected values that match later revisions rather than what was known at the time leak future corrections into training."],
    "investigate": ["How the selected values were produced and whether a point-in-time history exists."],
    "options": [_option("Rebuild features from point-in-time revisions", "A revision history exists.", "None.", "Re-run this audit; mismatches should fall.")],
    "unknowns": ["Matches to later revisions are investigation candidates, not proof of leakage."],
}
CATALOGUE["outcome_maturity"] = {
    "impact": ["Outcomes that are due but missing may be unrecorded events; treating them as negatives biases the target."],
    "investigate": ["Whether due outcomes are delayed in recording or truly absent."],
    "options": [
        _option("Exclude immature outcomes", "Outcomes are delayed rather than absent.", "Absence means the event did not happen and is recorded as such.", "Report how many rows remain."),
    ],
    "unknowns": ["Whether missing outcomes are delayed or absent was not assessed."],
}
CATALOGUE["fold_violation"] = {
    "impact": ["A fold that violates its declared temporal requirements uses future information or overlapping periods in evaluation."],
    "investigate": ["The fold boundaries against the declared requirements."],
    "options": [_option("Rebuild folds by time", "Fold rules are declared.", "None.", "Re-run this audit; the violation should no longer apply.")],
    "unknowns": [],
}
# ——— M6 text, M7 images, M9 records ↔ documents ———
CATALOGUE["record_validity"] = {
    "impact": ["Invalid or undecodable records are excluded from content checks, reducing coverage."],
    "investigate": ["The retained invalidity witnesses and the mapping or decoder involved."],
    "options": [_option("Repair the source record or mapping", "The intended content is known.", "None.", "Re-run this audit; invalid counts should fall.")],
    "unknowns": ["Excluded records were not assessed by content checks."],
}
CATALOGUE["identities"] = {
    "impact": ["Missing or repeated logical identities make joins, splits and de-duplication unreliable."],
    "investigate": ["Which identities repeat or are missing, and in which source."],
    "options": [_option("Repair identities before joins or splits", "The correct identity is known.", "None.", "Re-run this audit; identity findings should no longer apply.")],
    "unknowns": [],
}
CATALOGUE["content_duplicates"] = {
    "impact": ["Exact duplicates across splits inflate evaluation; within a split they over-weight repeated content."],
    "investigate": ["Whether duplicates are legitimate shared content (templates, boilerplate) or copies, and which splits they span."],
    "options": [
        _option("Keep duplicates within one split", "Duplicates are legitimate.", "None.", "Confirm no duplicate group spans splits."),
        _option("Remove copies", "Copying is confirmed.", "Content is legitimately shared.", "Report counts before and after; re-run this audit."),
    ],
    "unknowns": ["Whether duplicate content is legitimate was not assessed."],
}
CATALOGUE["near_duplicates"] = {
    "impact": ["Near-duplicates across splits can inflate evaluation much like exact copies."],
    "investigate": ["Shared and differing content in the retained candidates; templates and document families need context."],
    "options": [_option("Group near-duplicates for splitting", "Candidates are confirmed near-copies.", "Similarity reflects a shared template only.",
                        "Confirm no confirmed group spans splits.")],
    "unknowns": ["Candidates come from a bounded search; unsearched pairs were not assessed."],
}
CATALOGUE["passage_overlap"] = {
    "impact": ["Passages reused across sources or splits can expose evaluation content during training."],
    "investigate": ["The original passage spans and their provenance."],
    "options": [_option("Exclude or regroup overlapping passages", "Overlap is confirmed.", "Quotation is legitimate and expected.", "Re-run this audit.")],
    "unknowns": ["Passage candidates are bounded; unsearched spans were not assessed."],
}
CATALOGUE["conversations"] = {
    "impact": ["Conversations that break declared order, role or completion rules may train or evaluate on malformed dialogue."],
    "investigate": ["The retained witnesses against the declared requirements."],
    "options": [_option("Repair or exclude malformed conversations", "The intended structure is known.", "None.", "Re-run this audit.")],
    "unknowns": [],
}
CATALOGUE["retrieval"] = {
    "impact": ["Unresolved references or conflicting judgments make retrieval evaluation unreliable."],
    "investigate": ["The unresolved references and conflicting judgments."],
    "options": [_option("Repair references and adjudicate judgments", "Correct targets are known.", "None.", "Re-run this audit.")],
    "unknowns": [],
}
CATALOGUE["image_annotations"] = {
    "impact": ["Annotations outside image bounds, with invalid geometry or classes, corrupt training targets."],
    "investigate": ["The retained annotation witnesses against the image and the declared schema."],
    "options": [_option("Correct or exclude invalid annotations", "The intended annotation is clear.", "None.", "Re-run this audit.")],
    "unknowns": ["Topology and semantic correctness of valid annotations were not assessed."],
}
CATALOGUE["quality_expectations"] = {
    "impact": ["Images that violate the quality expectations you declared may not suit the task."],
    "investigate": ["The violating images against the declared expectation."],
    "options": [_option("Exclude or replace violating images", "The expectation is right.", "The expectation was too strict.", "Re-run this audit.")],
    "unknowns": ["DataTrust checks your declaration; it does not judge image suitability itself."],
}
CATALOGUE["relationships"] = {
    "impact": ["Records and documents that fail to associate as declared leave records unsupported or documents unused."],
    "investigate": ["The retained association failures and the declared keys."],
    "options": [_option("Repair keys or the association declaration", "The correct association is known.", "None.", "Re-run this audit.")],
    "unknowns": [],
}
CATALOGUE["context"] = {
    "impact": ["Entity, version or timing context that does not line up means a record may be compared with the wrong document."],
    "investigate": ["The unresolved context comparisons."],
    "options": [_option("Declare the missing context and re-run", "Context exists.", "None.", "Re-run this audit.")],
    "unknowns": [],
}
CATALOGUE["reconciliation"] = {
    "impact": ["Discrepancies or conflicting evidence between records and documents mean one of them may be wrong, or the rule may be."],
    "investigate": ["The review targets: which value each side states, and which source is authoritative."],
    "options": [
        _option("Correct the record or the document", "The authoritative source is known.", "Authority is unclear; review instead.", "Re-run this audit."),
        _option("Revise the reconciliation rule", "The rule mis-states the relationship.", "The data is wrong.", "Re-run with the revised rule."),
    ],
    "unknowns": ["Which side is correct was not assessed; conflicting evidence is retained, not resolved."],
}
# ——— Contextual findings (context_v1) ———
CATALOGUE["deterministic_predictor"] = {
    "impact": ["A feature that alone determines the target leaves a model little to learn; if the availability declaration is wrong, it is leakage."],
    "investigate": ["How the feature is produced, and whether the relationship holds in data from other periods or sources."],
    "options": [
        _option("Keep the feature with a documented decision", "It is produced before the prediction point.", "Its value is set or revised after the outcome.",
                "Validate on a time-ordered or source-held-out split that reflects real use."),
        _option("Exclude it and model the remaining signal", "The deterministic rule is already known and does not need learning.", "The rule is exactly the decision you need to automate.",
                "Compare models with and without it on the same split."),
    ],
    "unknowns": ["DataTrust records your availability declaration; it cannot observe when the value became known."],
}
CATALOGUE["condition_exceptions"] = {
    "impact": ["Rows that contradict a declared structure are treated inconsistently by any rule or feature built on that structure."],
    "investigate": ["The listed row references: is the declaration incomplete, or are the records wrong?"],
    "options": [
        _option("Correct the records at the source", "The declared structure is right.", "The declaration is incomplete.", "Re-run; the exception counts should be zero."),
        _option("Revise the declaration", "The exceptions are legitimate cases the declaration missed.", "They are errors.", "Re-run with the revised declaration."),
    ],
    "unknowns": ["Which side is right was not assessed."],
}
CATALOGUE["declared_missing"] = {
    "impact": ["Codes you declared as missing were counted as ordinary values by the parser, so missingness-aware methods do not see them."],
    "investigate": ["Whether the declared-missing rows differ from the rest in other columns or in the target."],
    "options": [
        _option("Convert the declared codes to missing in your pipeline", "The declaration is right for every row.", "The same code also carries a real value in some rows.",
                "Compare row counts and class shares before and after; a before/after comparison can confirm it."),
        _option("Keep the code as its own category", "Absence is informative and known at prediction time.", "The model would learn a collection artifact.",
                "Check how the code relates to the target before deciding."),
    ],
    "unknowns": ["Why values are missing beyond your declaration was not assessed."],
}
CATALOGUE["declaration_typo"] = {
    "impact": ["A declaration that matches nothing has no effect, so the interpretation you intended was not applied."],
    "investigate": ["The exact parsed spelling and type of the code in this column."],
    "options": [_option("Correct the declared value", "The intended code exists under another spelling.", "None.", "Re-run; the declared value should now match rows.")],
    "unknowns": [],
}
# ——— Before/after preprocessing (M4 preset) ———
_VERIFY_AGAIN = "Re-run the before/after assessment on the corrected files."
CATALOGUE["preprocessing_declaration_gap"] = {
    "impact": ["The After file may not be the output of the steps you declared, so conclusions about those steps do not hold."],
    "investigate": ["Which declared step left no trace, and whether the right After file was supplied."],
    "options": [_option("Supply the actual output or correct the declaration", "The intended steps are known.", "None.", _VERIFY_AGAIN)],
    "unknowns": ["How the After file was produced was not observed."],
}
CATALOGUE["preprocessing_undeclared"] = {
    "impact": ["Undeclared changes are unexplained: they may be intended, or side effects of a step that changed more than planned."],
    "investigate": ["Each undeclared change and the step that could have caused it."],
    "options": [_option("Declare the change or undo it", "You know which step caused it.", "None.", _VERIFY_AGAIN)],
    "unknowns": ["The cause of undeclared changes was not observed."],
}
CATALOGUE["preprocessing_incomplete_imputation"] = {
    "impact": ["Columns declared imputed still contain missing values, which later steps may drop or fill differently."],
    "investigate": ["Which rows still have gaps and why the imputation skipped them."],
    "options": [_option("Fix the imputation step", "The gaps should have been filled.", "Gaps were left on purpose (for example, structural absence).", _VERIFY_AGAIN)],
    "unknowns": [],
}
CATALOGUE["preprocessing_target_shift"] = {
    "impact": ["Preprocessing changed who is represented: a model trained afterwards learns different class shares than the source population."],
    "investigate": ["Which step removed or added rows of each class (lineage shows this when identity keys are declared)."],
    "options": [
        _option("Keep the change and document it", "The shift is intended (for example, removing invalid records).", "The deployment population keeps the original shares.",
                "Evaluate on data with the deployment population's shares."),
        _option("Revise the filtering or deduplication step", "The shift is a side effect.", "None.", _VERIFY_AGAIN),
    ],
    "unknowns": ["The deployment population's class shares were not supplied."],
}
CATALOGUE["preprocessing_unreconciled"] = {
    "impact": ["Without identity evidence, which records were removed or added cannot be traced; only the aggregate difference is known."],
    "investigate": ["Whether a stable identifier exists in both files."],
    "options": [_option("Declare complete, unique identity keys", "A stable identifier exists.", "Identifiers change between the files.", _VERIFY_AGAIN)],
    "unknowns": ["Record-level lineage was not available."],
}
CATALOGUE["generic_review"] = {
    "impact": ["See the finding's canonical text for its possible impact."],
    "investigate": ["The retained evidence and the applicable declaration."],
    "options": [_option("Review the evidence before changing data", "None.", NO_DATA_CHANGE, "Re-run this analysis after any change.")],
    "unknowns": ["This finding kind has no specific guidance in finding_guidance_v1."],
}

# ——— Which catalogue entry applies to each finding ———

CODE_KEY = {
    **dict.fromkeys(("fully_missing_columns", "column_missingness", "dataset_missingness", "widespread_row_missingness", "high_missingness",
                     "severe_feature_missingness"), "missing_values"),
    **dict.fromkeys(("missing_target_labels", "regression_missing_targets", "expected_annotation_gaps_high", "expected_annotation_gaps_moderate"), "missing_targets"),
    "duplicate_records": "duplicates",
    **dict.fromkeys(("conflicting_target_labels", "regression_repeated_input_variation", "observed_annotation_disagreement"), "label_conflicts"),
    "target_imbalance": "class_imbalance",
    **dict.fromkeys(("single_target_class", "constant_observed_class", "constant_observed_labels", "regression_constant_target", "constant_numerical_outputs"), "single_class"),
    **dict.fromkeys(("limited_label_support", "regression_limited_observations", "limited_finite_outputs", "limited_numerical_evidence", "regression_precision_review"), "limited_support"),
    **dict.fromkeys(("possible_target_leakage", "leakage_review_prompts", "regression_name_review"), "name_leakage"),
    **dict.fromkeys(("regression_declared_availability", "declared_input_unavailability"), "declared_unavailable"),
    **dict.fromkeys(("regression_relationships_unavailable_at_prediction", "input_target_relationships_unavailable_at_prediction"), "target_relationship"),
    **dict.fromkeys(("regression_relationships_unknown", "input_target_relationships_unknown"), "target_relationship_unknown"),
    **dict.fromkeys(("constant_fields", "near_constant_fields"), "constant_features"),
    "high_cardinality_categoricals": "high_cardinality",
    **dict.fromkeys(("numeric_outlier_concentration", "output_extreme_candidates", "regression_target_extremes"), "outliers"),
    **dict.fromkeys(("regression_target_concentration", "output_concentration"), "concentration"),
    **dict.fromkeys(("non_finite_values", "regression_nonfinite_targets"), "non_finite"),
    "conditional_scale_review": "scale",
    **dict.fromkeys(("regression_declared_constraints", "numerical_target_constraints", "multilabel_declared_constraints"), "declared_constraints"),
    **dict.fromkeys(("invalid_annotations", "annotation_declaration_conflicts", "unresolved_annotation_metadata"), "annotation_validity"),
    **dict.fromkeys(("no_feature_columns", "regression_no_features"), "no_features"),
    # context_v1
    "declared_unavailable_feature": "declared_unavailable", "target_dependency_unavailable": "target_relationship",
    "dependency_availability_unknown": "target_relationship_unknown", "deterministic_predictor_declared_available": "deterministic_predictor",
    "declared_condition_exceptions": "condition_exceptions", "declared_missing_population": "declared_missing",
    "applicable_population_outliers": "outliers", "declared_value_not_observed": "declaration_typo",
}
NARRATIVE_ONLY = frozenset({"no_major_issues"})

TITLE_KEY = {
    # M4 single-source structure (titles of the shared unlabeled finding builder)
    "Fully missing columns": "missing_values", "Substantial column missingness": "missing_values", "Dataset-wide missingness": "missing_values",
    "Widespread row missingness": "missing_values", "Exact repeated records": "duplicates", "Observed constant fields": "constant_features",
    "Near-constant fields": "constant_features", "High-cardinality text or categories": "high_cardinality", "Non-finite numeric values": "non_finite",
    "IQR review candidates": "outliers",
    # M4 annotations and dependence
    "Declared expected annotations are unavailable": "missing_targets", "Supplied annotations have invalid values": "annotation_validity",
    "Annotation status contradicts supplied values": "annotation_validity", "Repeated inputs have different observed annotations": "label_conflicts",
    "A declared dataset requirement is violated": "declared_constraints", "A declared label-vector requirement is violated": "declared_constraints",
    "An output is reproducible from selected inputs": "target_relationship_unknown", "Quantitative feature scales differ substantially": "scale",
    "Selected features have concentrated or associated missingness": "missingness_structure", "Strong dependence between selected inputs warrants review": "input_dependence",
    # M4 comparisons
    "Declared evaluation separation is violated": "split_separation", "Evaluation sources share informative selected inputs": "split_overlap",
    "Validation and test share selected inputs": "split_overlap", "Selected schema or representation changed": "schema_change",
    "Supported input or annotation populations differ": "population_shift",
    # M5
    "Declared observation schedule has absent records": "temporal_schedule", "Some declared collection opportunities have no supplied events": "temporal_schedule",
    "Declared temporal uniqueness is violated": "temporal_uniqueness", "Observed histories are shorter than the declared lookback": "temporal_history",
    "No eligible feature revision in declared complete history": "temporal_history", "Simultaneous measurements disagree": "simultaneous_disagreement",
    "Some declared clock values remain unresolved": "clock_resolution", "Source order contains backward temporal steps": "temporal_order",
    "Consecutive-difference dispersion changed": "behavior_change", "Window effects meet configured investigation settings": "behavior_change",
    "Within-series window effects merit investigation": "behavior_change", "Contiguous equal-value runs merit investigation": "flat_runs",
    "Bound features become available after their cutoffs": "availability_violation", "Declared past-observation features have future observation times": "availability_violation",
    "Identified selected revisions were unavailable at cutoff": "availability_violation", "Training outcomes were unavailable at the declared fit cutoff": "availability_violation",
    "Selected feature state disagrees with supplied revision history": "revision_mismatch", "Selected values resemble later revisions": "revision_mismatch",
    "Some missing outcomes are already due under the declared rule": "outcome_maturity", "Supplied fold violates declared temporal requirements": "fold_violation",
    # M4 before/after preset
    "Declared transformations are not reflected in the data": "preprocessing_declaration_gap", "Changes between before and after were not declared": "preprocessing_undeclared",
    "Declared imputation left missing values": "preprocessing_incomplete_imputation", "Target class shares changed during preprocessing": "preprocessing_target_shift",
    "Row changes are not explained by identity evidence": "preprocessing_unreconciled",
}

FAMILY_KEY = {
    # M6 text
    "invalidity": "record_validity", "identities": "identities", "annotation_disagreement": "label_conflicts", "conversations": "conversations",
    "retrieval": "retrieval", "exact_duplicates": "content_duplicates", "near_duplicates": "near_duplicates", "passages": "passage_overlap",
    # M7 images
    "decode": "record_validity", "annotations": "image_annotations", "logical_identity": "identities", "quality_expectations": "quality_expectations",
    "exact_duplicates_bytes": "content_duplicates", "exact_duplicates_native": "content_duplicates", "exact_duplicates_oriented": "content_duplicates",
    "split_requirements": "split_separation",
    # M9 records ↔ documents
    "relationships": "relationships", "context": "context", "reconciliation": "reconciliation", "separation": "split_separation",
}


def catalogue_key(finding):
    """The catalogue entry for a finding, by its code (core and M3), family (M6, M7, M9) or title (M4, M5)."""
    if finding.get("code"):
        return CODE_KEY.get(finding["code"], "generic_review")
    if finding.get("family"):
        return FAMILY_KEY.get(finding["family"], "generic_review")
    return TITLE_KEY.get(finding.get("title"), "generic_review")


# ——— Observed facts: values the result already records, never derived numbers ———

def _n(value):
    if isinstance(value, bool) or value is None:
        return str(value)
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        return f"{value:,.0f}" if value.is_integer() and abs(value) >= 1000 else f"{value:g}" if abs(value) < 1e6 else f"{value:,.0f}"
    return str(value)


def _cp(count, singular, plural=None):
    """A count with its correctly inflected noun ("1 group", "2 groups"), in the report's number format."""
    from datatrust.wording import pluralize
    return f"{_n(count)} {pluralize(count if isinstance(count, int) else 2, singular, plural)}"


def _columns(profile, names):
    by = {c["name"]: c for c in profile.get("columns", []) if isinstance(c, dict) and "name" in c}
    return [by[n] for n in names if n in by]


def _structured(evidence, limit=6):
    rows = evidence if isinstance(evidence, list) else [evidence]
    lines = []
    for row in rows[:limit]:
        if isinstance(row, dict):
            lines.append("; ".join(f"{k.replace('_', ' ')} {_n(v) if not isinstance(v, (dict, list)) else _flat(v)}" for k, v in row.items()))
        else:
            lines.append(str(row))
    if len(rows) > limit:
        lines.append(f"{_cp(len(rows) - limit, 'more entry', 'more entries')} in the canonical evidence.")
    return lines


def _flat(value):
    if isinstance(value, dict):
        return ", ".join(f"{k.replace('_', ' ')} {_flat(v)}" for k, v in value.items())
    if isinstance(value, list):
        return ", ".join(_flat(v) for v in value[:8])
    return _n(value)


def _core_observed(finding, value, legacy):
    code, profile = finding["code"], value.get("profile", {})
    rows = profile.get("row_count")
    if code == "target_imbalance":
        classes = profile.get("target_distribution") or []
        shown = "; ".join(f"{c['label']} {_n(c['count'])} ({c['percentage']}%)" for c in classes[:8])
        more = f"; {_cp(len(classes) - 8, 'more class', 'more classes')}" if len(classes) > 8 else ""
        return [f"Classes among {_cp(profile.get('labeled_row_count'), 'labelled row')}: {shown}{more}.",
                f"Majority-class baseline {profile.get('majority_class_baseline')}%; majority : minority {profile.get('majority_to_minority_ratio')} : 1."]
    if code == "numeric_outlier_concentration":
        lines = []
        affected = [c for c in profile.get("columns", []) if isinstance(c.get("outlier_rate"), (int, float)) and c["outlier_rate"] >= 5 and c.get("role", "feature") == "feature"]
        for c in affected:
            s = c.get("numeric_summary") or {}
            denominator = f"{_n(rows)} rows" if legacy else f"{_n(c.get('outlier_denominator'))} finite values"
            detail = f"; q1 {_n(s.get('q1'))}, q3 {_n(s.get('q3'))}, min {_n(s.get('min'))}, max {_n(s.get('max'))}" if s else ""
            signs = f"; {_n(s['negative_count'])} negative, {_n(s['zero_count'])} zero" if s.get("negative_count") is not None else ""
            lines.append(f"{c['name']}: {_n(c['outlier_count'])} of {denominator} ({c['outlier_rate']}%) outside the 1.5 × IQR fences{detail}{signs}.")
        if legacy and affected:
            lines.append("Under this policy the denominator is all rows, and non-finite values count as outside the fences.")
        zero = [c["name"] for c in profile.get("columns", []) if (c.get("numeric_summary") or {}).get("q1") is not None and c["numeric_summary"]["q1"] == c["numeric_summary"]["q3"] and c.get("role", "feature") == "feature"]
        if zero:
            lines.append(f"IQR is zero for {', '.join(zero)} (q1 equals q3), so the fences cannot separate values; "
                         + ("the recorded rate of 0 there means 'not assessable', not 'no outliers'." if legacy else "no rate was computed for them."))
        return lines or [str(finding.get("evidence", ""))]
    if code in {"fully_missing_columns", "column_missingness", "high_missingness", "severe_feature_missingness", "dataset_missingness", "widespread_row_missingness"}:
        cols = sorted((c for c in profile.get("columns", []) if c.get("missing_count")), key=lambda c: -c["missing_count"])
        lines = [f"{c['name']}: {_n(c['missing_count'])} of {_n(rows)} rows missing ({c['missing_rate']}%)." for c in cols[:8]]
        if len(cols) > 8:
            lines.append(f"{_cp(len(cols) - 8, 'more column')} with missing values in the canonical profile.")
        lines.append(f"{_cp(profile.get('missing_cells'), 'missing cell')} ({profile.get('missing_rate')}% of cells); {_cp(profile.get('missing_feature_row_count'), 'row')} with at least one missing feature ({profile.get('missing_feature_row_rate')}%).")
        return lines
    if code == "duplicate_records":
        return [f"{_n(profile.get('duplicate_rows'))} of {_cp(rows, 'row')} {'repeats' if profile.get('duplicate_rows') == 1 else 'repeat'} an earlier row ({profile.get('duplicate_rate')}%), in {_cp(profile.get('duplicate_group_count'), 'group')}; largest group {_cp(profile.get('largest_duplicate_group_size'), 'row')}."]
    if code == "conflicting_target_labels":
        return [f"{_cp(profile.get('conflicting_label_group_count'), 'feature-identical group')} ({_cp(profile.get('conflicting_label_row_count'), 'row')}) with more than one non-missing label."]
    if code in {"constant_fields", "near_constant_fields"}:
        names = finding.get("affected_columns") or [c["name"] for c in profile.get("columns", []) if c.get("constant" if code == "constant_fields" else "near_constant") and c.get("role", "feature") == "feature"]
        return [f"{c['name']}: {_cp(c['unique_count'], 'distinct value')}; most common '{c.get('top_value')}' in {c.get('top_value_rate')}% of rows." for c in _columns(profile, names)] or [str(finding.get("evidence", ""))]
    if code == "high_cardinality_categoricals":
        names = finding.get("affected_columns") or [c["name"] for c in profile.get("columns", []) if c.get("high_cardinality")]
        return [f"{c['name']}: {_cp(c['unique_count'], 'distinct value')} ({c.get('unique_rate')}% of rows)." for c in _columns(profile, names)] or [str(finding.get("evidence", ""))]
    if code in {"possible_target_leakage", "leakage_review_prompts"}:
        return [f"{d.get('column')}: {'strong candidate' if d.get('classification') == 'strong' else 'review only'}; {d.get('reason')}" for d in profile.get("leakage_details", [])] or [str(finding.get("evidence", ""))]
    if code == "missing_target_labels":
        return [f"{_n(profile.get('target_missing_count'))} of {_cp(rows, 'row')} without a target label ({profile.get('target_missing_rate')}%)."]
    evidence = finding.get("evidence")
    lines = _structured(evidence) if isinstance(evidence, (list, dict)) else [str(evidence)] if evidence else []
    if finding.get("affected_count") is not None and isinstance(evidence, (list, dict)):
        lines.append(f"Affected: {_n(finding['affected_count'])}.")
    return lines or [str(finding.get("finding", ""))]


def _pointer(value, pointer):
    """The dict a JSON pointer names in the result (M4 measurements), or an empty dict."""
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        return {}
    node = value
    for part in pointer[1:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        if isinstance(node, dict) and part in node:
            node = node[part]
        elif isinstance(node, list) and part.isdigit() and int(part) < len(node):
            node = node[int(part)]
        else:
            return {}
    return node if isinstance(node, dict) else {}


def _record_facts(value, finding):
    """Scalar facts from the evidence records a finding references (M4 to M9): population, scope, denominators and
    up to five recorded measurements. Only values the record holds."""
    refs = set(finding.get("evidence_refs") or []) | ({finding["id"]} if finding.get("id") else set())
    lines = []
    for record in value.get("evidence") or []:
        if not isinstance(record, dict) or record.get("id") not in refs:
            continue
        head = [f"{k.replace('_', ' ')} {_n(record[k])}" for k in ("population", "scope", "denominator", "affected_count")
                if record.get(k) not in (None, "", [], {})]
        data = record.get("data") if isinstance(record.get("data"), dict) else _pointer(value, (record.get("measurement_refs") or [None])[0])
        facts = [f"{k.replace('_', ' ')} {_n(v)}" for k, v in data.items() if isinstance(v, (int, float, str)) and not isinstance(v, bool) and v != "" and len(str(v)) <= 80][:5]
        if head or facts:
            lines.append(f"Evidence {record['id']}: " + "; ".join(head + facts) + ".")
    return lines[:3]


def _other_observed(finding, value):
    lines = []
    if finding.get("finding"):
        lines.append(str(finding["finding"]))
    if finding.get("affected_count") is not None:
        lines.append(f"{_n(finding['affected_count'])}" + (f" of {_n(finding['denominator'])}" if finding.get("denominator") is not None else "") + f" in scope {finding.get('scope')}.")
    if finding.get("count") is not None:
        lines.append(f"{_n(finding['count'])} in family {finding.get('family')} ({str(finding.get('meaning', '')).replace('_', ' ')})." if finding.get("family") else f"{_n(finding['count'])}.")
    if isinstance(finding.get("counts"), dict):
        counts = {k: v for k, v in finding["counts"].items() if isinstance(v, (int, float)) and v}
        if counts:
            lines.append("Counts: " + ", ".join(f"{k.replace('_', ' ')} {_n(v)}" for k, v in counts.items()) + (f"; population {finding.get('population')}." if finding.get("population") else "."))
    if finding.get("measurement"):
        lines.append(f"Measurement {finding['measurement']}" + (f" in {', '.join(map(str, finding.get('source_ids') or []))}." if finding.get("source_ids") else "."))
    refs = finding.get("references") or []
    if refs:
        lines.append(f"{_cp(len(refs), 'retained reference')} for local inspection.")
    lines += _record_facts(value, finding)
    return lines or [str(finding.get("title", ""))]


def _ref(finding, index):
    return str(finding.get("code") if finding.get("code") and not finding.get("id") else finding.get("id") or finding.get("code") or f"finding_{index + 1}")


# ——— Scope, scoring explanation and policy ———

def _status(check, key):
    v = check.get(key)
    return v.get("value") if isinstance(v, dict) else v


PLACEHOLDERS = "Whether text values such as 'unknown' or numeric codes such as -1 stand for missing or special values was not assessed."
METHOD_UNKNOWNS = {
    "classification_legacy_2026_08_13": [PLACEHOLDERS, "Leakage was checked by column name only; when each feature becomes available relative to the outcome was not verified."],
    "tabular_regression_v1": [PLACEHOLDERS, "Prediction-time availability is known only for features you declared; the relationship search is bounded to its stated methods."],
    "unlabeled_csv_profile_v1": [PLACEHOLDERS],
}


def _scope(value, items):
    not_completed, seen = [], set()
    for c in value.get("checks") or []:
        if not isinstance(c, dict):
            continue
        applicability, execution = _status(c, "applicability"), _status(c, "execution")
        name = c.get("check_id") or c.get("family") or c.get("id")
        if applicability == "blocked":
            state = "excluded"
        elif execution in {"failed", "skipped"}:
            state = "failed" if execution == "failed" else "interrupted"
        elif applicability == "applicable" and execution == "not_run":
            state = "not assessed"
        else:
            continue
        key = (name, c.get("scope"), state)
        if key in seen:
            continue
        seen.add(key)
        not_completed.append({"check": name, "scope": c.get("scope"), "state": state, "reason": c.get("reason")})
    method = METHOD_UNKNOWNS.get(value.get("methodology_id"), [PLACEHOLDERS] if str(value.get("methodology_id", "")).startswith("tabular_") else [])
    contextual = value.get("contextual") or {}
    if contextual.get("status") == "completed":
        declared = [n for n, d in (contextual.get("declarations") or {}).items() if d.get("placeholders") or d.get("sentinels")]
        replaced = []
        for line in method:
            if line == PLACEHOLDERS:
                line = (f"Placeholder and sentinel codes were interpreted only where you declared them ({', '.join(declared)}); other values were taken as recorded."
                        if declared else f"{len(contextual.get('candidates') or [])} possible placeholder or sentinel codes were suggested but none was declared, so none was interpreted.")
            elif line.startswith("Leakage was checked by column name only") and contextual.get("dependency_search", {}).get("status") in {"completed", "bounded"}:
                search = contextual["dependency_search"]
                line = (f"Leakage was checked by column name and by a bounded target-dependency search ({len(search['checks'])} features checked"
                        + (f", {len(search['unsearched_features'])} unsearched" if search["unsearched_features"] else "") + "); "
                        + ("availability is as you declared it for the prediction point." if contextual.get("prediction", {}).get("declared") else "no prediction point was declared, so availability was not verified."))
            replaced.append(line)
        method = replaced
    unknowns = list(dict.fromkeys([*method, *(u for item in items.values() for u in item["unknowns"])]))
    findings = [f for f in value.get("findings") or [] if f.get("code") not in NARRATIVE_ONLY]
    priorities = [str(f.get("severity") or f.get("priority") or "").capitalize() for f in findings]
    counts = ", ".join(f"{priorities.count(p)} {p.lower()}" for p in ("High", "Moderate", "Low") if priorities.count(p))
    status = (value.get("execution") or {}).get("status", "completed")
    conclusion = (f"Within the completed checks, {len(findings)} finding{'s' if len(findings) != 1 else ''} call{'s' if len(findings) == 1 else ''} for review"
                  + (f" ({counts})" if counts else "") + "." if findings else "Within the completed checks, no finding met its review threshold.")
    if any(c["state"] != "excluded" for c in not_completed) or status == "partial":
        conclusion += " Some checks did not complete; their scope is listed and was not concluded on."
    if any(c["state"] == "excluded" for c in not_completed):
        conclusion += " Some scopes were excluded by a method's preconditions and are listed."
    context_findings = len((value.get("contextual") or {}).get("findings") or [])
    if context_findings:
        conclusion += f" {context_findings} contextual finding{'s' if context_findings != 1 else ''} from your declarations and the dependency search {'are' if context_findings != 1 else 'is'} listed separately; {'they do' if context_findings != 1 else 'it does'} not change any score."
    conclusion += " This is review evidence for the stated scope; it does not establish model performance, semantic correctness or prediction-time availability."
    return {"execution": status, "not_completed": not_completed[:50], "not_completed_total": len(not_completed), "unknowns": unknowns, "conclusion": conclusion}


RULE_LABELS = {
    "missing_rate_100": "column entirely missing", "missing_rate_50": "≥ 50% missing", "missing_rate_25": "≥ 25% missing", "constant": "constant",
    "near_constant": "near-constant (top value ≥ 95%)", "high_cardinality": "high cardinality (≥ 80% unique, ≥ 20 values)",
    "iqr_rate_10": "≥ 10% outside IQR fences", "iqr_rate_5": "≥ 5% outside IQR fences",
}


def _scoring(value):
    scoring = value.get("scoring") or {}
    values = scoring.get("values") if scoring.get("status") == "computed" else None
    if not values or "sub_scores" not in values:
        return None
    from datatrust.scoring import feature_usability_contributions
    contributions = feature_usability_contributions(value["profile"]["columns"])
    raw = sum(points for _, rules in contributions for _, points in rules)
    caps = [g["cap"] for g in values.get("guardrails", [])]
    governing = min(caps) if caps else None
    return {
        "evidence_score": {"sub_scores": values["sub_scores"], "mean": values["evidence_score"], "method": "Mean of the five sub-scores, rounded to two decimals."},
        "guardrails": [{**g, "governing": g["cap"] == governing} for g in values.get("guardrails", [])],
        "overall": values["overall"],
        "overall_method": "The evidence score, capped by the lowest triggered guardrail." if caps else "The evidence score; no guardrail was triggered.",
        "feature_usability": {
            "contributors": [{"column": name, "rules": [{"rule": RULE_LABELS[r], "points": p} for r, p in rules]} for name, rules in contributions if rules],
            "feature_count": len(contributions), "raw_points": raw,
            "method": "100 minus (raw points ÷ feature count), clamped to 0–100 and rounded to two decimals.",
            "sub_score": values["sub_scores"].get("feature_usability"),
        },
    }


POLICY = {
    "classification_legacy_2026_08_13": [
        {"rule": "Target imbalance finding", "threshold": "Majority class ≥ 75% of labelled rows (High from 90%)", "effect": "Finding; target-balance sub-score falls as the majority share exceeds an even split."},
        {"rule": "Column missingness penalty", "threshold": "≥ 25% / ≥ 50% / 100% missing", "effect": "10 / 20 / 30 feature-usability points."},
        {"rule": "Constant / near-constant penalty", "threshold": "One value / top value ≥ 95%", "effect": "12 / 8 points."},
        {"rule": "High-cardinality penalty", "threshold": "Non-numeric, ≥ 80% unique and ≥ 20 values", "effect": "8 points."},
        {"rule": "IQR outlier penalty", "threshold": "≥ 5% / ≥ 10% of rows outside 1.5 × IQR fences (non-finite counted)", "effect": "4 / 8 points; finding from 5%."},
        {"rule": "Dataset missingness finding", "threshold": "≥ 10% of cells (High from 25%)", "effect": "Finding; completeness sub-score is 100 minus the missing-cell rate."},
        {"rule": "Duplicate finding", "threshold": "≥ 2% repeated rows (High from 10%)", "effect": "Finding; uniqueness sub-score is 100 minus the duplicate rate."},
        {"rule": "Guardrail: critical sub-score", "threshold": "Any sub-score ≤ 50", "effect": "Overall capped at 69."},
        {"rule": "Guardrails: severe missingness or duplicates; missing labels", "threshold": "Feature ≥ 50% missing; cells ≥ 25% missing; duplicates ≥ 10%; any missing label", "effect": "Overall capped at 69."},
        {"rule": "Guardrails: strong leakage name, one class, no features", "threshold": "Any", "effect": "Overall capped at 49."},
        {"rule": "Risk level", "threshold": "≥ 85 Low · ≥ 70 Moderate · ≥ 50 Elevated · below High", "effect": "Label only."},
        {"rule": "Leakage check", "threshold": "Column names matching outcome-like terms", "effect": "Name-based only; strong candidates cost 40 points (+15 each further, at most 85)."},
    ],
    "tabular_regression_v1": [
        {"rule": "IQR review candidates", "threshold": "≥ 5% of finite values outside 1.5 × IQR fences", "effect": "Finding (evidence only; no score)."},
        {"rule": "Column missingness", "threshold": "≥ 25% missing (High from 50%); cells ≥ 10%; rows with a gap ≥ 25%", "effect": "Findings (evidence only)."},
        {"rule": "Duplicates", "threshold": "Any repeated row (Moderate from 2%, High from 10%)", "effect": "Finding (evidence only)."},
        {"rule": "Relationship search", "threshold": "Declared support and coverage requirements", "effect": "Findings by declared availability; bounded search."},
        {"rule": "Score", "threshold": "None", "effect": "No validated score is defined for regression."},
    ],
    "unlabeled_csv_profile_v1": [
        {"rule": "IQR review candidates", "threshold": "≥ 5% of finite values outside 1.5 × IQR fences", "effect": "Finding (evidence only)."},
        {"rule": "Column missingness", "threshold": "≥ 25% missing (High from 50%); cells ≥ 10%; rows with a gap ≥ 25%", "effect": "Findings (evidence only)."},
        {"rule": "Duplicates", "threshold": "Any repeated row (Moderate from 2%, High from 10%)", "effect": "Finding (evidence only)."},
        {"rule": "Near-constant / high cardinality", "threshold": "Top value ≥ 95% / ≥ 80% unique and ≥ 20 values", "effect": "Findings (evidence only)."},
        {"rule": "Score", "threshold": "None", "effect": "No validated score is defined for unlabeled profiling."},
    ],
}


def build_guidance(result):
    """The guidance block for a just-produced result (any workflow)."""
    value = result.to_dict()
    legacy = value.get("methodology_id") == "classification_legacy_2026_08_13"
    items = {}
    for i, finding in enumerate(value.get("findings") or []):
        if not isinstance(finding, dict) or finding.get("code") in NARRATIVE_ONLY:
            continue
        key = catalogue_key(finding)
        entry = CATALOGUE[key]
        observed = _core_observed(finding, value, legacy) if finding.get("code") else _other_observed(finding, value)
        items[_ref(finding, i)] = {"catalogue": key, "title": finding.get("title") or str(finding.get("family", "")).replace("_", " "),
                                   "observed": [o for o in observed if o], "impact": entry["impact"], "investigate": entry["investigate"],
                                   "options": entry["options"], "unknowns": entry["unknowns"]}
    for finding in (value.get("contextual") or {}).get("findings") or []:
        key = CODE_KEY.get(finding["code"], "generic_review")
        entry = CATALOGUE[key]
        ref = f"context.{finding['code']}." + "+".join(finding.get("columns") or [])
        items[ref] = {"catalogue": key, "title": finding["title"], "context": True, "observed": [finding["finding"], finding["evidence"]],
                      "impact": entry["impact"], "investigate": entry["investigate"], "options": entry["options"], "unknowns": entry["unknowns"]}
    block = {"version": VERSION, "items": items, "scope": _scope(value, items)}
    scoring = _scoring(value)
    if scoring:
        block["scoring"] = scoring
    if value.get("methodology_id") in POLICY:
        block["policy"] = POLICY[value["methodology_id"]]
    return block


def attach_guidance(result):
    """Compute the block once, when the result is produced; reloaded results keep whatever they recorded."""
    object.__setattr__(result, "guidance", build_guidance(result))
    return result

