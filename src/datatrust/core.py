import re
import time
import pandas as pd
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path

from datatrust.contracts import (
    AnalysisConfig, AnalysisError, AnalysisResult, Applicability, CheckOutcome,
    CsvParseOptions, DatasetSpec, EvidenceRecord, ExecutionLimits, ExecutionStatus, TaskSpec, RegressionOptions,
)
from datatrust.ingestion import load_dataset, verify_source
from datatrust.profiler import (
    exact_duplicate_evidence, finite_numeric_evidence,
    profile_classification_frame, profile_unlabeled_frame, profile_tabular_frame,
)
from datatrust.renderer import write_html_report
from datatrust.risks import build_findings, build_unlabeled_findings, build_regression_findings
from datatrust.narrative import build_narrative, build_unlabeled_narrative, build_regression_narrative
from datatrust.regression import (validate_target, target_evidence, constraint_evidence,
                                  relationship_evidence, repeated_input_evidence, ACTION_SUPPORT)
from datatrust.scoring import score_profile


class DataTrust:
    """Generate local dataset reliability reports."""

    @staticmethod
    def audit_temporal(spec, config=None, **kwargs):
        from datatrust.temporal import audit_temporal
        return audit_temporal(spec, config, **kwargs)

    @staticmethod
    def compare(spec, config=None):
        from datatrust.m4_worker import compare
        return compare(spec, config)

    def __init__(
        self,
        dataset_path: str,
        target: str,
        task: str = "classification",
        *,
        dataset_name: str = None,
        purpose: str = None,
        source_filename: str = None,
    ):
        self._config = AnalysisConfig()
        self._specification_based = False
        self._last_result = None
        self.dataset_path = Path(dataset_path)
        self.target = target
        self.task = task
        self.dataset_name = _clean_context_value(
            dataset_name, "Dataset name", maximum_length=120
        )
        self.purpose = _clean_context_value(purpose, "Purpose", maximum_length=1000)
        cleaned_source = _clean_context_value(
            source_filename, "Source filename", maximum_length=255
        )
        self.source_filename = (
            Path(cleaned_source.replace("\\", "/")).name if cleaned_source else None
        )

    @classmethod
    def from_spec(cls, dataset: DatasetSpec, task: TaskSpec, config=None):
        if not isinstance(dataset, DatasetSpec) or not isinstance(task, TaskSpec):
            raise ValueError("from_spec requires DatasetSpec and TaskSpec.")
        if config is not None and not isinstance(config, AnalysisConfig):
            raise ValueError("config must be AnalysisConfig.")
        audit = cls(str(dataset.path), task.target,
                    "unlabeled" if task.kind == "dataset_profile" else task.kind,
                    dataset_name=dataset.dataset_name, purpose=dataset.purpose,
                    source_filename=dataset.source_filename)
        audit._task_spec = task
        audit._config = config or AnalysisConfig()
        audit._specification_based = True
        return audit

    def _specs(self):
        if hasattr(self, "_task_spec"):
            return DatasetSpec(str(self.dataset_path), dataset_name=self.dataset_name, purpose=self.purpose, source_filename=self.source_filename), self._task_spec
        if self.task not in {"classification", "unlabeled", "dataset_profile", "regression"}:
            raise ValueError("DataTrust supports classification, regression, and unlabeled profiling.")
        return (DatasetSpec(str(self.dataset_path), dataset_name=self.dataset_name,
                            purpose=self.purpose, source_filename=self.source_filename),
                TaskSpec("dataset_profile" if self.task in {"unlabeled", "dataset_profile"} else self.task, self.target))

    def analyze_result(self) -> AnalysisResult:
        dataset, task = self._specs()
        self._last_result = run_analysis(dataset, task, self._config)
        return self._last_result

    def analyze(self) -> dict:
        """Fresh analysis; classification retains its exact six-key projection."""
        result = self.analyze_result()
        return result.to_legacy_dict() if result.methodology_id == "classification_legacy_2026_08_13" else result.to_dict()

    def generate_report(self, output_path: str, *, format="html", html_path=None) -> str:
        if format == "html" and self.task == "classification" and not self._specification_based:
            if html_path is not None:
                raise ValueError("html_path is only supported for PDF output.")
            from datatrust.renderer import protect_source
            protect_source(self.dataset_path, [output_path])
            return write_html_report(self.analyze(), output_path)
        result = self.analyze_result()
        return result.generate_report(output_path, format=format, html_path=html_path)

    def generate_artifacts(self, output_path, *, format="html", html_path=None, json_path=None):
        return self.analyze_result().generate_artifacts(output_path, format=format,
                                                       html_path=html_path, json_path=json_path)


def run_analysis(dataset: DatasetSpec, task: TaskSpec, config=None) -> AnalysisResult:
    """The single local analysis path; interpretation policies remain explicit."""
    config = config or AnalysisConfig()
    if config.advanced is not None or config.execution is not None and config.execution.backend == 'duckdb_local':
        from datatrust.m4_worker import analyze_scalable
        return analyze_scalable(dataset, task, config)
    from datatrust.numerical import feature_evidence
    if config.regression is not None and task.kind != "regression":
        raise ValueError("Regression options require task='regression'.")
    start = time.monotonic()
    limits = config.limits or (ExecutionLimits() if task.kind == "classification" else ExecutionLimits.unlabeled_defaults())

    def checkpoint(stage):
        if limits.max_seconds is not None and time.monotonic() - start > limits.max_seconds:
            raise AnalysisError(f"Cooperative elapsed-time safeguard reached after {stage}; individual operations are not interruptible.", code="resource_limit", stage=stage)

    from datatrust.annotations import effective_policy
    def prepare(columns):
        nonlocal task, config, limits, roles, m3_method
        task, config, roles, m3_method = effective_policy(columns, task, config)
        if task.kind == "multilabel_classification":
            from datatrust.multilabel import validate_options
            validate_options(task.target_names, config.multilabel)
        if m3_method and config.limits is None:
            limits = ExecutionLimits.unlabeled_defaults()
        if not m3_method and task.kind == "classification" and config.parsing != CsvParseOptions():
            raise ValueError("Non-default classification parsing is outside M1; legacy defaults are preserved.")
        return task, config, limits
    roles = None; m3_method = None
    handle = load_dataset(dataset, task, config, limits, checkpoint, prepare=prepare)
    checkpoint("basic profiling")
    if m3_method:
        if not handle.data.index.equals(pd.RangeIndex(len(handle.data))):
            raise ValueError("CSV produced an implicit index; repair mismatched record/header widths before profiling.")
        profile = profile_tabular_frame(handle.data, Path(dataset.path), resolved_roles=roles['columns'])
        profile.update(task=task.kind, roles=roles)
        profile['missing_feature_cells'] = sum(c['missing_count'] for c in profile['columns'] if c['role']=='feature')
        profile['missing_feature_cell_rate'] = 100*profile['missing_feature_cells']/(profile['row_count']*profile['feature_count']) if profile['feature_count'] else 0
        profile['presentation_limits'] = asdict(config.presentation)
    elif task.kind == "classification":
        profile = profile_classification_frame(handle.data, Path(dataset.path), task.target)
    elif task.kind == "regression":
        options = config.regression or RegressionOptions()
        validate_target(handle.data, task.target, options)
        profile = profile_tabular_frame(handle.data, Path(dataset.path), task.target)
        profile.update(target=task.target, task="regression")
        profile["missing_feature_cells"] = sum(c["missing_count"] for c in profile["columns"] if c["role"] == "feature")
        profile["missing_feature_cell_rate"] = 100 * profile["missing_feature_cells"] / (profile["row_count"] * profile["feature_count"]) if profile["feature_count"] else 0
        profile["regression"] = {"expectations": asdict(options.expectations), "declaration_source": "user_declared",
            "feature_availability": options.feature_availability, "target_statistics": None, "constraints": None,
            "relationships": [], "relationship_groups": [], "search": None, "repeated_inputs": None, "name_candidates": []}
    else:
        profile = profile_unlabeled_frame(handle.data, Path(dataset.path))
    checks = []
    evidence = []

    def record(check_id, refs, population, denominator=None, affected_count=None,
               columns=None, rows=None, method="deterministic", scope="dataset", thresholds=None):
        evidence_id = f"{check_id}.{len(evidence)}"
        record = EvidenceRecord(evidence_id, check_id, refs, population, denominator,
                                affected_count, columns or [], rows or [], method, thresholds or {})
        evidence.append(record)
        checks.append(CheckOutcome(check_id, scope=scope, evidence_refs=[evidence_id]))
        return evidence_id

    record("schema", ["/parsing/header_mapping", "/profile/row_count", "/profile/column_count"], "parsed records", profile["row_count"])
    record("missingness", ["/profile/missing_cells", "/profile/missing_rate", "/profile/missing_feature_row_rate"],
           "all parsed cells", profile["row_count"] * profile["column_count"], profile["missing_cells"])
    record("column_variation", ["/profile/columns"], "all parsed columns", profile["column_count"])
    record("categorical_cardinality", ["/profile/columns"], "nonnumeric parsed columns", profile["non_numeric_feature_count"])
    if task.kind == "regression" or m3_method:
        record("feature_missingness", ["/profile/missing_feature_cells", "/profile/missing_feature_cell_rate", "/profile/missing_feature_row_rate"], "parsed feature cells", profile["row_count"] * profile["feature_count"], profile["missing_feature_cells"])

    def row_ref(ordinal):
        return {"source_sha256": handle.source["sha256"], "parsing_fingerprint": handle.parsing["fingerprint"], "parsed_row": ordinal}

    def optional(check_id, operation, scope="dataset"):
        try:
            checkpoint(check_id)
            return operation()
        except MemoryError:
            raise
        except AnalysisError as exc:
            if exc.code != "resource_limit":
                raise
            checks.append(CheckOutcome(check_id, execution=ExecutionStatus.SKIPPED, scope=scope, reason=str(exc)))
        except Exception as exc:
            checks.append(CheckOutcome(check_id, execution=ExecutionStatus.FAILED, scope=scope,
                                       reason=f"{type(exc).__name__}: check failed; no conclusion was generated."))
        return None

    if task.kind in {"dataset_profile", "regression"} or m3_method:
        duplicates = optional("exact_duplicates", lambda: exact_duplicate_evidence(handle.data))
        if duplicates is not None:
            profile.update(duplicates)
            record("exact_duplicates", ["/profile/duplicate_rows", "/profile/duplicate_group_count", "/profile/rows_in_duplicate_groups"],
                   "all parsed rows", profile["row_count"], profile["duplicate_rows"],
                   rows=[row_ref(i) for i in profile["duplicate_row_examples"]])
        for index, column in enumerate(profile["columns"]):
            if not column["is_numeric"] or column["role"] != "feature":
                continue
            column["outlier_count"] = column["outlier_rate"] = None
            numeric = optional("numeric_summary", lambda c=column: (feature_evidence if m3_method else finite_numeric_evidence)(handle.data[c["name"]]), column["name"])
            if numeric is not None:
                column.update(numeric)
                record("numeric_summary", [f"/profile/columns/{index}/numeric_summary", f"/profile/columns/{index}/finite_count"],
                       "finite values; zero/negative/non-finite rates use total rows", profile["row_count"],
                       columns=[column["name"]], scope=column["name"], method="finite_descriptive")
                if numeric["outlier_unavailable_reason"]:
                    checks.append(CheckOutcome("numeric_outliers", Applicability.BLOCKED, ExecutionStatus.NOT_RUN,
                                               scope=column["name"], reason=numeric["outlier_unavailable_reason"]))
                else:
                    record("numeric_outliers", [f"/profile/columns/{index}/outlier_count", f"/profile/columns/{index}/outlier_rate"],
                           "finite numeric observations", numeric["finite_count"], numeric["outlier_count"],
                           columns=[column["name"]], scope=column["name"], method="finite_1.5_iqr", thresholds={"review_rate": 5})
                    checks[-1].exclusions = [{"missing_values": column["missing_count"], "non_finite_values": numeric["numeric_summary"]["non_finite_count"]}]
            else:
                checks.append(CheckOutcome("numeric_outliers", Applicability.BLOCKED, ExecutionStatus.NOT_RUN,
                                           scope=column["name"], reason="numeric evidence unavailable"))
        if m3_method:
            from datatrust.m3 import analyze_tasks
            findings, narrative, scores = analyze_tasks(handle.data,task,config,roles,profile,checks,record,optional,checkpoint)
            method = m3_method
        elif task.kind == "regression":
            r = profile["regression"]
            prefix = "/profile/regression/"
            r["target_statistics"] = optional("regression_target", lambda: target_evidence(handle.data[task.target], options.expectations), task.target)
            if r["target_statistics"] is not None:
                record("regression_target", [prefix+"target_statistics"], "finite targets; coverage uses all parsed rows", profile["row_count"], columns=[task.target], method="finite_regression_distribution", scope=task.target)
                t = r["target_statistics"]
                for name in ("sample_std", "extremes", "bowley_skewness", "histogram", "rounding"):
                    reason = t["unavailable_statistics"].get(name)
                    if name == "rounding" and t[name] and t[name]["status"] == "blocked":
                        reason = t[name].get("reason", "floating_resolution")
                    if reason:
                        checks.append(CheckOutcome("regression_"+name, Applicability.BLOCKED, ExecutionStatus.NOT_RUN, scope=task.target, reason=reason))
                    else:
                        record("regression_"+name, [prefix+"target_statistics/"+name], "finite targets", t["finite_count"], columns=[task.target], scope=task.target)
            r["constraints"] = optional("regression_constraints", lambda: constraint_evidence(handle.data[task.target], options.expectations), task.target)
            if r["constraints"] is not None:
                if r["constraints"]["rules"]:
                    record("regression_constraints", [prefix+"constraints"], "finite targets", r["constraints"]["denominator"], r["constraints"]["violation_union_count"], columns=[task.target], scope=task.target)
                else:
                    checks.append(CheckOutcome("regression_constraints", Applicability.NOT_APPLICABLE, ExecutionStatus.NOT_RUN, reason="No numerical constraints declared."))
            relations = optional("regression_relationships", lambda: relationship_evidence(handle.data, task.target, options, checkpoint))
            if relations is not None:
                r.update(relations)
                record("regression_relationships", [prefix+"search"], "eligible numerical features; explicitly bounded candidate search", method="bounded_arithmetic_identities", thresholds=ACTION_SUPPORT)
                if r["search"].get("failure"):
                    failure = r["search"]["failure"]
                    checks.append(CheckOutcome("regression_relationships", execution=ExecutionStatus.SKIPPED if failure["reason_category"] == "execution_interruption" else ExecutionStatus.FAILED, reason=failure["reason"]))
                record("regression_names", [prefix+"name_candidates"], "feature names; contextual cues only", profile["feature_count"])
                for i, relation in enumerate(r["relationships"]):
                    relation["evidence_refs"] = [record("regression_relationship", [prefix+f"relationships/{i}"], "finite overlapping targets and participating features", relation["overlap_count"], columns=relation["columns"], method=relation["method"], scope=relation["id"], thresholds=ACTION_SUPPORT)]
                for i, group in enumerate(r["relationship_groups"]):
                    group["evidence_refs"] = [record("regression_relationship_group", [prefix+f"relationship_groups/{i}"], "verified relationship support scopes", columns=group["columns"], scope=group["id"])]
                    group["evidence_refs"] += [ref for relation in r["relationships"] if relation["id"] in group["relationship_ids"] for ref in relation["evidence_refs"]]
            r["repeated_inputs"] = optional("regression_repeated_inputs", lambda: repeated_input_evidence(handle.data, task.target)) if profile["feature_count"] else None
            if r["repeated_inputs"] is not None:
                record("regression_repeated_inputs", [prefix+"repeated_inputs"], "finite targets grouped by exact feature values", r["repeated_inputs"]["denominator"], r["repeated_inputs"]["varying_rows"])
            elif not profile["feature_count"]:
                checks.append(CheckOutcome("regression_repeated_inputs", Applicability.NOT_APPLICABLE, ExecutionStatus.NOT_RUN, reason="No feature columns."))
            record("regression_availability", [prefix+"feature_availability"], "user-declared feature context", profile["feature_count"])

            def attach_rows(value):
                if isinstance(value, dict):
                    if "row_ordinals" in value:
                        value["row_refs"] = [row_ref(i) for i in value.pop("row_ordinals")]
                    for child in value.values():
                        attach_rows(child)
                elif isinstance(value, list):
                    for child in value:
                        attach_rows(child)
            attach_rows(r)
            for e in evidence:
                for pointer in e.measurement_refs:
                    if pointer.startswith(prefix):
                        node = profile["regression"]
                        for part in pointer[len(prefix):].split("/"):
                            node = node[int(part)] if isinstance(node, list) else node[part]
                        if isinstance(node, dict):
                            e.row_refs = node.get("row_refs", [])
            for check_id in ("classification_target", "label_conflicts", "target_leakage", "classification_scoring"):
                checks.append(CheckOutcome(check_id, Applicability.NOT_APPLICABLE, ExecutionStatus.NOT_RUN, reason="Regression uses numerical target evidence and no classification scores."))
            scores = {"status": "not_defined", "values": None, "reason": "No validated scoring policy is defined for regression reliability."}
            findings = build_regression_findings(profile)
            narrative = build_regression_narrative(profile, findings)
            method = "tabular_regression_v1"
        else:
            for check_id in ("classification_target", "label_conflicts", "target_leakage", "classification_scoring"):
                checks.append(CheckOutcome(check_id, Applicability.NOT_APPLICABLE, ExecutionStatus.NOT_RUN, reason="No target selected; general dataset profiling."))
            scores = {"status": "not_defined", "values": None,
                      "reason": "No validated scoring policy is defined for unlabeled profiling."}
            findings = build_unlabeled_findings(profile)
            narrative = build_unlabeled_narrative(profile, findings)
            method = "unlabeled_csv_profile_v1"
    else:
        record("exact_duplicates", ["/profile/duplicate_rows", "/profile/duplicate_group_count"], "all parsed rows", profile["row_count"], profile["duplicate_rows"])
        record("classification_target", ["/profile/target_distribution", "/profile/class_balance"], "labeled rows", profile["labeled_row_count"])
        record("label_conflicts", ["/profile/conflicting_label_group_count", "/profile/conflicting_label_row_count"], "labeled rows", profile["labeled_row_count"])
        record("target_leakage", ["/profile/leakage_details"], "feature column names", profile["feature_count"], method="legacy_name_heuristic")
        if profile["numeric_feature_count"]:
            record("numeric_summary", ["/profile/columns"], "finite descriptive values; legacy outliers include non-finite values", profile["row_count"], method="legacy_numeric_policy")
            record("numeric_outliers", ["/profile/columns"], "total rows", profile["row_count"], method="legacy_1.5_iqr")
        scores = {"status": "computed", "values": score_profile(profile), "reason": None}
        record("classification_scoring", ["/scoring/values"], "legacy classification policy", method="legacy_five_scores_and_guardrails")
        findings = build_findings(profile, scores["values"])
        narrative = build_narrative(profile, scores["values"], findings[:3], findings)
        method = "classification_legacy_2026_08_13"
    if not profile["numeric_feature_count"]:
        for check_id in ("numeric_summary", "numeric_outliers"):
            checks.append(CheckOutcome(check_id, Applicability.NOT_APPLICABLE, ExecutionStatus.NOT_RUN, reason="No numeric input columns."))
    if profile["non_numeric_feature_count"] == 0:
        cardinality = next(c for c in checks if c.check_id == "categorical_cardinality")
        cardinality.applicability = Applicability.NOT_APPLICABLE
        cardinality.execution = ExecutionStatus.NOT_RUN
        cardinality.reason = "No nonnumeric input columns."
    record("parsing_fidelity", ["/parsing/fidelity_inspection", "/parsing_warnings"], "bounded source prefix",
           handle.parsing["fidelity_inspection"]["comparable_cells"], method="bounded_source_token_comparison")
    if not handle.parsing["fidelity_inspection"]["alignment_confirmed"]:
        checks[-1].applicability = Applicability.BLOCKED
        checks[-1].execution = ExecutionStatus.NOT_RUN
        checks[-1].reason = "Token alignment unavailable; interpretation review limitations are disclosed separately."
    # Do not mix snapshots even if the source changed while optional checks ran.
    verify_source(dataset.path, handle.source)
    if task.kind == "classification" and not m3_method:
        checkpoint("analysis")
    else:
        try:
            checkpoint("analysis")
        except AnalysisError as exc:
            checks.append(CheckOutcome("execution_budget", execution=ExecutionStatus.SKIPPED, reason=str(exc)))
    partial = any(c.execution in {ExecutionStatus.FAILED, ExecutionStatus.SKIPPED} for c in checks)
    groups = {}
    for check in checks:
        groups.setdefault(check.check_id, []).append(check)
    complete_groups = [name for name, outcomes in groups.items()
                       if any(c.applicability == Applicability.APPLICABLE for c in outcomes)
                       and all(c.execution == ExecutionStatus.COMPLETED for c in outcomes if c.applicability == Applicability.APPLICABLE)]
    coverage = {"completed_applicable_groups": complete_groups,
                "completed_applicable_checks": sum(c.applicability == Applicability.APPLICABLE and c.execution == ExecutionStatus.COMPLETED for c in checks),
                "unavailable_checks": [asdict(c) for c in checks if c.execution != ExecutionStatus.COMPLETED],
                "unsupported_capabilities": ["semantic typing", "missingness patterns", "split/reference comparisons", "model performance", "non-tabular modalities"],
                "meaning": "Coverage describes these checks, not a percentage of universal reliability."}
    context = {"dataset_name": _clean_context_value(dataset.dataset_name, "Dataset name", 120) or _humanize_fallback_name(Path(dataset.source_filename or str(dataset.path)).stem),
               "purpose": _clean_context_value(dataset.purpose, "Purpose", 1000),
               "source_filename": Path((dataset.source_filename or Path(dataset.path).name).replace("\\", "/")).name}
    if task.kind != "classification" or m3_method:
        refs = {item.check_id: [] for item in evidence}
        for item in evidence:
            refs[item.check_id].append(item.id)
        for finding in findings:
            if "measurement_paths" in finding:
                paths = finding.pop("measurement_paths")
                finding["evidence_refs"] = [e.id for e in evidence if set(e.measurement_refs).intersection(paths)]
                for index, group in enumerate(profile.get("regression", {}).get("relationship_groups", [])):
                    if f"/profile/regression/relationship_groups/{index}" in paths:
                        finding["evidence_refs"] = list(dict.fromkeys(finding["evidence_refs"] + group["evidence_refs"]))
            else:
                finding["evidence_refs"] = refs.get(finding.pop("check_id"), [])
    if task.kind == "regression" and not m3_method:
        search = profile["regression"]["search"]
        coverage["relationship_search"] = search or {"status": "unavailable", "meaning": "No relationship conclusion is available."}
    if m3_method:
        coverage['unsupported_capabilities'] = ['semantic label correctness', 'general split/reference comparisons', 'model performance', 'non-tabular modalities', 'clustering quality', 'anomaly correctness']
        def attach_m3_rows(value):
            if isinstance(value, dict):
                if 'examples' in value and isinstance(value['examples'],dict) and set(value['examples'])=={'invalid','expected_gaps','unresolved_metadata','inconsistencies'}:
                    value['row_refs_by_reason']={reason:[row_ref(i) for i in ordinals] for reason,ordinals in value.pop('examples').items()}
                if 'row_ordinals' in value: value['row_refs'] = [row_ref(i) for i in value.pop('row_ordinals')]
                for child in value.values(): attach_m3_rows(child)
            elif isinstance(value,list):
                for child in value: attach_m3_rows(child)
        attach_m3_rows(profile)
    return AnalysisResult(replace(dataset, path=str(Path(dataset.path).resolve())), task, profile, {**handle.parsing, "source_sha256": handle.source["sha256"]},
                          handle.parsing_warnings, checks, evidence, findings, narrative, context, coverage, scores,
                          {"status": "partial" if partial else "completed", "backend": "pandas_in_memory", "materialization": "in_memory",
                           "source_bytes": handle.source["bytes"], "analyzed_rows": profile["row_count"], "analyzed_columns": profile["column_count"],
                           "frame_bytes": handle.frame_bytes, "elapsed_seconds": round(time.monotonic() - start, 6), "limits": asdict(limits),
                           "enforcement": "Source/header preflight, bounded row read, post-load frame measurement, cooperative stage deadlines; no hard memory or execution guarantee."},
                          datetime.now(timezone.utc).isoformat(), method, schema_version="1.2" if m3_method else "1.1" if task.kind == "regression" else "1.0")


def _clean_context_value(value, label: str, maximum_length: int):
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned:
        return None
    if len(cleaned) > maximum_length:
        raise ValueError(f"{label} must be {maximum_length} characters or fewer.")
    return cleaned


def _humanize_fallback_name(value: str) -> str:
    """Turn a filename stem into a readable title without changing custom names."""
    chunks = [chunk for chunk in re.split(r"[_\-\s]+", str(value)) if chunk]
    words = []
    for chunk in chunks:
        if re.match(r"^[a-z][A-Z]", chunk):
            parts = [chunk]
        else:
            separated = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", chunk)
            separated = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", separated)
            parts = separated.split()
        for part in parts:
            words.append(part.capitalize() if part.islower() else part)
    return " ".join(words) or str(value)
