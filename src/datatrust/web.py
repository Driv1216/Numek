import hashlib
import hmac
import json
import secrets
import shutil
import tempfile
import threading
import uuid
import webbrowser
from pathlib import Path

from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from werkzeug.utils import secure_filename

from dataclasses import asdict, replace
from datatrust import AnalysisConfig, CsvParseOptions, DataTrust, DatasetSpec, ExecutionLimits, TaskSpec, RegressionOptions, TargetExpectations
from datatrust.ingestion import resolve_delimiter, inspect_unlabeled_dataset, inspect_regression_dataset, inspect_regression_target, load_dataset, source_digest, source_signature
from datatrust.annotations import effective_policy, annotation_coverage, feature_semantics, specification_fingerprint
from datatrust.contracts import AnnotationOptions, AnnotationSpec, ContextOptions, FeatureOptions, MultilabelOptions
from datatrust.pdf import PDFRenderError, render_pdf_report
from datatrust.profiler import inspect_classification_target, inspect_csv_dataset
from datatrust.renderer import ArtifactCollisionError, write_report_artifacts, _regression_inspection_notice, _report_filters


class JobStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.jobs = {}

    def create(self, upload, source_filename: str) -> dict:
        job_id = uuid.uuid4().hex
        job_dir = self.root / job_id
        job_dir.mkdir()
        dataset_path = job_dir / "dataset.csv"
        upload.save(dataset_path)
        job = {
            "id": job_id,
            "directory": job_dir,
            "dataset_path": dataset_path,
            "source_filename": source_filename,
        }
        self.jobs[job_id] = job
        return job

    def get(self, job_id):
        if not job_id:
            return None
        return self.jobs.get(job_id)

    def remove(self, job_id) -> None:
        job = self.jobs.pop(job_id, None)
        if job:
            shutil.rmtree(job["directory"], ignore_errors=True)

    def cleanup(self) -> None:
        for job_id in list(self.jobs):
            self.remove(job_id)


M3_MODES = {'annotation_classification','annotation_regression','multilabel_classification','clustering','anomaly_detection','role_profile'}


class WorkflowError(Exception):
    """A correctable core-flow problem. The classic UI flashes it and returns to `back`; the JSON API reports it."""

    def __init__(self, message: str, back: str):
        super().__init__(message)
        self.back = back


# Core-flow steps shared by the classic form routes and the JSON API (datatrust.api_web). `form` is any
# mapping with the classic form's field names and string values: request.form, or the API's JSON body.

def artifact_owned(job, kind):
    identity = job.get("artifacts", {}).get(kind)
    if not identity:
        return False
    path = identity["path"]
    return (not path.is_symlink() and path.is_file() and source_signature(path) == identity["signature"]
            and source_digest(path) == identity["sha256"])


def remember_artifacts(job, artifacts):
    for kind in ("html", "pdf", "json"):
        location = getattr(artifacts, f"{kind}_path")
        if location:
            path = Path(location)
            job.setdefault("artifacts", {})[kind] = {"path": path, "sha256": source_digest(path), "signature": source_signature(path)}
            job[f"{'report' if kind == 'html' else kind}_path"] = path


def core_pdf(job):
    """The canonical PDF of a completed core job, rendered from its canonical HTML once per HTML digest."""
    pdf_path = job["directory"] / "report.pdf"
    if not (artifact_owned(job, "pdf") and job.get("pdf_html_digest") == job["artifacts"]["html"]["sha256"]):
        artifacts = write_report_artifacts(job["analysis_result"], pdf_path, format="pdf",
            html_path=job["report_path"], pdf_converter=render_pdf_report, legacy_html=job["analysis_result"].methodology_id == "classification_legacy_2026_08_13")
        remember_artifacts(job, artifacts)
        job["pdf_html_digest"] = job["artifacts"]["html"]["sha256"]
    job["pdf_path"] = pdf_path
    return pdf_path


def invalidate_artifacts(job):
    # Verify the entire set before touching anything. Filenames do not prove ownership.
    for kind, identity in job.get("artifacts", {}).items():
        if identity["path"].exists() or identity["path"].is_symlink():
            if not artifact_owned(job, kind):
                raise ArtifactCollisionError(f"Unrecognized job artifact at {identity['path']}; it was left untouched.")
    for identity in job.get("artifacts", {}).values():
        identity["path"].unlink(missing_ok=True)
    for key in ("artifacts", "report_path", "pdf_path", "json_path", "summary", "analysis_result", "pdf_html_digest"):
        job.pop(key, None)


def populate_m3_forms(job):
    config = job['config']; annotation = config.annotations
    job.update(
        annotation_status_json=json.dumps(asdict(annotation.default)['status_values']) if annotation else None,
        per_target_annotation_json=json.dumps({k:asdict(v) for k,v in annotation.per_target.items()}) if annotation else None,
        expectations_json=json.dumps({k:asdict(v) for k,v in config.regression.expectations_by_target.items()}) if config.regression else None,
        availability_json=json.dumps(config.regression.feature_availability) if config.regression else None,
        multilabel_json=json.dumps(asdict(config.multilabel)) if config.multilabel else None,
    )


DELIMITER_CHOICES = {"auto", ",", ";", "\t", "|"}


def with_delimiter(config, delimiter):
    return replace(config, parsing=replace(config.parsing, delimiter=delimiter))


def core_parsing(job):
    """Classification keeps its pinned parse defaults; only the declared separator is carried."""
    return CsvParseOptions(delimiter=job["config"].parsing.delimiter) if job["mode"] == "classification" else job["config"].parsing


def inspect_upload(job):
    return (inspect_csv_dataset(job["dataset_path"], preview_rows=10, options=core_parsing(job)) if job["mode"] == "classification"
        else (inspect_regression_dataset if job["mode"] == "regression" else inspect_unlabeled_dataset)(DatasetSpec(job["dataset_path"]), job["config"]))


def start_job(store, analysis_config, mode, uploaded, delimiter=","):
    """Upload: replace this session's job with a new one and inspect the CSV. `delimiter` is a separator, or "auto"
    to detect one (see ingestion.detect_delimiter). An ambiguous file is refused until a separator is chosen."""
    if mode not in {"classification", "unlabeled", "regression"} | M3_MODES:
        abort(400, description="Choose classification, regression, or unlabeled profiling.")
    if delimiter not in DELIMITER_CHOICES:
        raise WorkflowError("Choose a comma, semicolon, tab or vertical bar separator.", "index")
    if uploaded is None or not uploaded.filename:
        raise WorkflowError("Choose a CSV file to continue.", "index")

    source_filename = _source_filename(uploaded.filename)
    if not source_filename.lower().endswith(".csv"):
        raise WorkflowError("DataTrust accepts .csv files only.", "index")

    store.remove(session.pop("job_id", None))
    job = store.create(uploaded, source_filename)
    try:
        chosen = resolve_delimiter(job["dataset_path"], delimiter)
    except ValueError as exc:
        store.remove(job["id"])
        raise WorkflowError(str(exc), "index") from exc
    job.update(mode=mode, config=with_delimiter(analysis_config, chosen), delimiter_detected=delimiter == "auto" and chosen != ",")
    if mode in M3_MODES:
        populate_m3_forms(job)
    if analysis_config.regression is not None and mode not in {"regression","annotation_regression"}:
        store.remove(job["id"])
        raise WorkflowError("Regression options require regression mode.", "index")
    try:
        job["inspection"] = inspect_upload(job)
        job["file_size"] = job["dataset_path"].stat().st_size
    except (FileNotFoundError, ValueError) as exc:
        store.remove(job["id"])
        raise WorkflowError(str(exc), "index") from exc

    session["job_id"] = job["id"]
    return job


def set_delimiter(job, delimiter):
    """Read the uploaded file again with another separator. Declarations made for the old columns are cleared."""
    if delimiter not in DELIMITER_CHOICES - {"auto"}:
        raise WorkflowError("Choose a comma, semicolon, tab or vertical bar separator.", "configure")
    previous = (job["config"], job.get("delimiter_detected"))
    job.update(config=with_delimiter(job["config"], delimiter), delimiter_detected=False)
    try:
        inspection = inspect_upload(job)
    except (FileNotFoundError, ValueError) as exc:
        job["config"], job["delimiter_detected"] = previous
        raise WorkflowError(str(exc), "configure") from exc
    for key in ("target", "target_info", "task_spec", "summary", "result"):
        job.pop(key, None)
    invalidate_artifacts(job)
    job["inspection"] = inspection
    if job["mode"] in M3_MODES:
        populate_m3_forms(job)
    return job


def context_fingerprint(context):
    """The confirmation seal of the declared context (context_v1); None when nothing is declared."""
    if context is None:
        return None
    return hashlib.sha256(json.dumps(context.to_dict(), sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def apply_context(job, form):
    """Read the optional `context` field (context_v1 JSON). A change invalidates the confirmation and every artifact.
    Forms without the field (the classic pages, older clients) keep the job's context unchanged."""
    if "context" not in form:
        return
    raw = form.get("context")
    context = None
    if raw not in (None, "", "null", "{}"):
        try:
            context = ContextOptions.from_dict(json.loads(raw) if isinstance(raw, str) else raw)
        except (ValueError, TypeError) as exc:
            raise WorkflowError(f"Context declarations are invalid: {exc}", "configure") from exc
        columns = set(job["inspection"]["columns"])
        unknown = sorted(set(context.columns) - columns) + sorted(d.applies_when["column"] for d in context.columns.values() if d.applies_when and d.applies_when["column"] not in columns)
        if unknown:
            raise WorkflowError("Context declares columns the file does not have: " + ", ".join(unknown) + ".", "configure")
    if context_fingerprint(context) != context_fingerprint(job["config"].context):
        invalidate_artifacts(job)
        for key in ("summary", "result", "target_info"):
            job.pop(key, None)
    try:
        job["config"] = replace(job["config"], context=context)
    except ValueError as exc:
        raise WorkflowError(str(exc), "configure") from exc
    job["context_seal"] = context_fingerprint(context)


def configure_core(job, form):
    """Configure for classification, regression and unlabeled jobs. Returns the next stage: configure or confirm."""
    apply_context(job, form)
    target = form.get("target", "") if job["mode"] != "unlabeled" else None
    dataset_name = form.get("dataset_name", "")
    purpose = form.get("purpose", "")
    if job["mode"] != "unlabeled" and target not in job["inspection"]["columns"] and form.get("action") != "preview":
        raise WorkflowError("Choose a target column from the uploaded dataset.", "configure")
    try:
        if job["mode"] != "classification":
            if job["mode"] == "unlabeled" and form.get("target"):
                raise ValueError("Unlabeled dataset profiling does not accept a target.")
            parsing = CsvParseOptions(delimiter=job["config"].parsing.delimiter, encoding=form.get("encoding", job["config"].parsing.encoding),
                missing_policy=form.get("missing_policy", job["config"].parsing.missing_policy),
                na_values=json.loads(form.get("na_values", json.dumps(job["config"].parsing.na_values))),
                column_types=json.loads(form.get("column_types", json.dumps(job["config"].parsing.column_types))))
            updated_config = replace(job["config"], parsing=parsing)
            if job["mode"] == "regression":
                existing = job["config"].regression or RegressionOptions()
                def optional_number(name, default):
                    if name not in form:
                        return default
                    text = form[name]
                    return float(text) if text.strip() else None
                def optional_flag(name, default):
                    return True if form.get(name) else None if form.get("regression_options_submitted") else default
                expectations = TargetExpectations(kind=form.get("target_kind", existing.expectations.kind),
                    minimum=optional_number("target_minimum", existing.expectations.minimum), maximum=optional_number("target_maximum", existing.expectations.maximum),
                    units=form.get("target_units", existing.expectations.units or "").strip() or None,
                    nonnegative=optional_flag("target_nonnegative", existing.expectations.nonnegative),
                    integer_required=optional_flag("target_integer", existing.expectations.integer_required))
                availability = {c:form.get("availability_"+c, existing.feature_availability.get(c, "unknown")) for c in job["inspection"]["columns"] if c != target}
                availability = {c:v for c,v in availability.items() if v != "unknown"}
                updated_config = replace(updated_config, regression=RegressionOptions(expectations, availability, existing.relation_limits))
            inspection = (inspect_regression_dataset if job["mode"] == "regression" else inspect_unlabeled_dataset)(DatasetSpec(job["dataset_path"]), updated_config)
        else:
            updated_config = replace(job["config"], parsing=core_parsing(job))
            inspection = dict(job["inspection"])
            handle = load_dataset(DatasetSpec(job["dataset_path"]), TaskSpec("classification", target),
                updated_config, updated_config.limits or ExecutionLimits(), lambda stage: None, preview_rows=10)
            inspection.update(parsing=handle.parsing, parsing_warnings=handle.parsing_warnings,
                              limits=asdict(updated_config.limits or ExecutionLimits()))
        audit = DataTrust.from_spec(DatasetSpec(job["dataset_path"], dataset_name=dataset_name, purpose=purpose),
            TaskSpec("dataset_profile" if job["mode"] == "unlabeled" else job["mode"], target or (inspection["columns"][0] if job["mode"] == "regression" and form.get("action") == "preview" else target)), updated_config)
        target_info = (inspect_classification_target(job["dataset_path"], target, options=core_parsing(job)) if job["mode"] == "classification" else
            inspect_regression_target(DatasetSpec(job["dataset_path"]), target, updated_config) if job["mode"] == "regression" and form.get("action") != "preview" else None)
        invalidate_artifacts(job)
    except (FileNotFoundError, ValueError) as exc:
        raise WorkflowError(str(exc), "configure") from exc

    job.update(
        {
            "target": target,
            "dataset_name": audit.dataset_name,
            "purpose": audit.purpose,
            "target_info": target_info,
            "config": updated_config,
            "inspection": inspection,
        }
    )
    if form.get("action") == "preview":
        if job["mode"] == "regression":
            job.pop("target_info", None)
        return "configure"
    return "confirm"


KIND_FOR = {'annotation_classification':'classification','annotation_regression':'regression','role_profile':'dataset_profile'}


def configure_m3(job, form):
    """Configure for the six M3 modes: column roles, semantics and annotation declarations. Returns confirm."""
    apply_context(job, form)
    try:
        columns=job['inspection']['columns']
        roles={c:form.get('role_'+c,'feature') for c in columns}
        if any(r not in {'feature','target','metadata','group','ignored'} for r in roles.values()): raise ValueError('Invalid column role.')
        targets=tuple(c for c in columns if roles[c]=='target')
        kind=KIND_FOR.get(job['mode'],job['mode'])
        annotation=None
        if targets:
            default=AnnotationSpec(form.get('annotation_expectation','unknown'),form.get('status_column') or None,json.loads(form.get('status_values','null')))
            annotation=AnnotationOptions(default,json.loads(form.get('per_target_annotations','{}')))
            status_columns={spec.status_column for spec in [default,*annotation.per_target.values()] if spec.status_column}
            for c in status_columns:
                if c in roles and roles[c]=='feature': roles[c]='metadata'
        features=tuple(c for c in columns if roles[c]=='feature')
        task=TaskSpec(kind,targets=targets,feature_columns=features,metadata_columns=tuple(c for c in columns if roles[c]=='metadata'),group_columns=tuple(c for c in columns if roles[c]=='group'))
        semantics={c:form.get('semantic_'+c) for c in features if form.get('semantic_'+c,'undeclared')!='undeclared'}
        sensitivity={'unknown':None,'true':True,'false':False}.get(form.get('scale_sensitive','unknown'))
        parsing=CsvParseOptions(form.get('encoding','utf-8'),form.get('missing_policy','pandas_default'),json.loads(form.get('na_values','[]')),json.loads(form.get('column_types','{}')),delimiter=job['config'].parsing.delimiter)
        regression = None
        if kind == 'regression':
            base = job['config'].regression or RegressionOptions()
            declarations = RegressionOptions.from_dict({'expectations_by_target':json.loads(form.get('expectations_by_target','{}')),'feature_availability':json.loads(form.get('feature_availability','{}'))})
            regression = replace(base, expectations_by_target=declarations.expectations_by_target,
                                 feature_availability=declarations.feature_availability)
            if declarations.expectations_by_target and len(targets)>1:
                regression = replace(regression, expectations=declarations.expectations)
        config=replace(job['config'],parsing=parsing,annotations=annotation,features=FeatureOptions(semantics,sensitivity),
                       regression=regression,
                       multilabel=AnalysisConfig.from_dict({'multilabel':json.loads(form.get('multilabel_options','{}'))}).multilabel if kind=='multilabel_classification' else None)
        audit=DataTrust.from_spec(DatasetSpec(job['dataset_path'],dataset_name=form.get('dataset_name'),purpose=form.get('purpose')),task,config)
        prepared={}
        def resolve(columns):
            et,ec,rr,mm=effective_policy(columns,task,config);prepared.update(task=et,config=ec,roles=rr,method=mm)
            return et,ec,config.limits or (ExecutionLimits() if et.kind=='classification' and not mm else ExecutionLimits.unlabeled_defaults())
        handle=load_dataset(DatasetSpec(job['dataset_path']),task,config,config.limits or ExecutionLimits.unlabeled_defaults(),lambda stage:None,prepare=resolve)
        rr=prepared['roles'];sem=feature_semantics(handle.data,rr['features'],config.features)
        cov=annotation_coverage(handle.data,task,config.annotations,rr['groups'])[0] if targets else None
        if kind=='multilabel_classification':
            from datatrust.multilabel import validate_options
            validate_options(targets,config.multilabel)
        info={'rows':len(handle.data),'roles':rr,'annotations':cov,'methodology':prepared['method'] or ('classification_legacy_2026_08_13' if kind=='classification' else 'tabular_regression_v1' if kind=='regression' else 'unlabeled_csv_profile_v1'),
              'source_sha256':handle.source['sha256'],'parsing_fingerprint':handle.parsing['fingerprint'],'specification_fingerprint':specification_fingerprint(task,config,columns),
              'assumed_quantitative_count':sum(s['semantic_type']=='assumed_quantitative' for s in sem),'ambiguous_count':sum(s['semantic_type']=='ambiguous_code' for s in sem)}
        invalidate_artifacts(job)
        job.update(task_spec=task,config=config,target_info=info,dataset_name=audit.dataset_name,purpose=audit.purpose,
                   annotation_status_json=json.dumps(asdict(annotation.default)['status_values']) if annotation else None,
                   per_target_annotation_json=json.dumps({k:asdict(v) for k,v in annotation.per_target.items()}) if annotation else None,
                   expectations_json=json.dumps({k:asdict(v) for k,v in config.regression.expectations_by_target.items()}) if config.regression else None,
                   availability_json=json.dumps(config.regression.feature_availability) if config.regression else None,
                   multilabel_json=json.dumps(asdict(config.multilabel)) if config.multilabel else None)
    except (ValueError,FileNotFoundError) as exc:
        job.pop('target_info',None)
        raise WorkflowError(str(exc), "configure") from exc
    return "confirm"


def audit_for(job, analysis_config):
    config = job.get("config", analysis_config)
    if job["mode"] == "classification":
        config = replace(config, parsing=CsvParseOptions(delimiter=config.parsing.delimiter))
    return DataTrust.from_spec(DatasetSpec(str(job["dataset_path"]), dataset_name=job.get("dataset_name"),
        purpose=job.get("purpose"), source_filename=job["source_filename"]),
        job.get("task_spec") or TaskSpec("dataset_profile" if job["mode"] == "unlabeled" else job["mode"], job.get("target")), config)


def generate_report(job, form, analysis_config):
    """Generate: run the confirmed analysis and write the canonical HTML and JSON artifacts."""
    if "target_info" not in job:
        raise WorkflowError("Confirm the target before generating the report.", "configure")
    if (
        job["mode"] in {"classification", "regression"}
        and job["target_info"]["suitability"]["requires_override"]
        and form.get("advanced_target_ack") != "confirmed"
    ):
        raise WorkflowError(
            "Confirm that you still want to use this advanced choice as the prediction outcome.",
            "confirm",
        )
    if job.get("context_seal") != context_fingerprint(job["config"].context):
        job.pop("target_info", None)
        raise WorkflowError("The declared context changed since confirmation; review the selection again.", "configure")
    try:
        if job['mode'] in M3_MODES:
            info=job['target_info']
            if form.get('representation_ack')!='confirmed': raise ValueError('Confirm the representation assumptions before generating the report.')
            if source_digest(job['dataset_path'])!=info['source_sha256'] or specification_fingerprint(job['task_spec'],job['config'],job['inspection']['columns'])!=info['specification_fingerprint']:
                job.pop('target_info',None)
                raise ValueError('Source or effective configuration changed since confirmation; review again.')
        if job["mode"] == "regression" and source_digest(job["dataset_path"]) != job["target_info"]["source_sha256"]:
            job.pop("target_info", None)
            raise ValueError("Source changed since regression confirmation; review the target again.")
        invalidate_artifacts(job)
        report_path = job["directory"] / "report.html"
        audit = audit_for(job, analysis_config)
        if job["mode"] == "classification":
            result = audit.analyze()
            typed = audit._last_result
            summary = _result_summary(result)
        else:
            typed = audit.analyze_result()
            summary = _result_summary(typed.to_legacy_dict()) if typed.methodology_id == "classification_legacy_2026_08_13" else {"dataset_name": typed.context["dataset_name"], "source_filename": typed.context["source_filename"],
                "overall_assessment": typed.narrative["overall_assessment"], "principal_evidence_summary": typed.narrative["principal_evidence_summary"],
                "recommended_action": typed.narrative["recommended_action"], "risks": typed.findings[:3]}
            if job["mode"] == "regression":
                if (typed.parsing["source_sha256"] != job["target_info"]["source_sha256"] or
                        typed.parsing["fingerprint"] != job["target_info"]["parsing_fingerprint"]):
                    raise ValueError("Source changed since regression confirmation; no report was published.")
                summary.update(target=typed.task.target, target_statistics=typed.profile["regression"]["target_statistics"], scoring=typed.scoring)
        if job['mode'] in M3_MODES:
            if typed.parsing['source_sha256']!=job['target_info']['source_sha256'] or typed.parsing['fingerprint']!=job['target_info']['parsing_fingerprint']:
                job.pop('target_info',None)
                raise ValueError('Source/parsing changed since confirmation; no report was published.')
        artifacts = write_report_artifacts(typed, report_path, json_path=job["directory"] / "analysis.json", legacy_html=typed.methodology_id == "classification_legacy_2026_08_13")
        remember_artifacts(job, artifacts)
        summary.update(parsing_warnings=typed.parsing_warnings, execution=typed.execution, coverage=typed.coverage, scoring=typed.scoring)
        job.update(
            {
                "report_path": report_path,
                "summary": summary,
                "analysis_result": typed,
            }
        )
    except (FileNotFoundError, ValueError) as exc:
        if getattr(exc, "artifacts", None):
            remember_artifacts(job, exc.artifacts)
        raise WorkflowError(str(exc), "confirm") from exc


def create_app(workspace: Path, max_upload_mib: float = 100, analysis_config=None, data_roots=None, history=None, launch_token=None,
               classic_ui: bool = True, confidenceguard_workspace=None, confidenceguard_launch_token=None) -> Flask:
    analysis_config = analysis_config or AnalysisConfig()
    if not isinstance(analysis_config, AnalysisConfig):
        raise ValueError("analysis_config must be AnalysisConfig.")
    app = Flask(__name__, template_folder="templates")
    app.jinja_env.filters["regression_inspection_notice"] = _regression_inspection_notice
    _report_filters(app.jinja_env)  # report templates rendered in pages (the temporal investigate view) share the report filters
    app.secret_key = secrets.token_bytes(32)
    app.config.update(
        MAX_CONTENT_LENGTH=int(max_upload_mib * 1024 * 1024),
        MAX_UPLOAD_MIB=max_upload_mib,
    )
    app.extensions["datatrust_worker_lock"] = threading.Lock()
    store = JobStore(Path(workspace))
    app.extensions["datatrust_job_store"] = store

    @app.before_request
    def protect_posts():
        # ConfidenceGuard and the DataTrust app API own their versioned JSON CSRF
        # protocols. Existing form workflows retain their original token behavior.
        if request.blueprint in {'confidenceguard_api', 'datatrust_api'}:
            return None
        token = session.setdefault("form_token", secrets.token_urlsafe(24))
        if request.method == "POST" and not hmac.compare_digest(
            str(request.form.get("form_token", "")), token
        ):
            abort(400, description="The form session expired. Reload the page and try again.")

    @app.context_processor
    def form_context():
        return {"form_token": session.get("form_token", "")}

    def current_job():
        return store.get(session.get("job_id"))

    def require_job():
        job = current_job()
        if not job:
            flash("That analysis session is no longer available. Upload the CSV again.", "error")
            return None
        return job

    owned, remember, invalidate = artifact_owned, remember_artifacts, invalidate_artifacts
    m3_modes = M3_MODES

    def configure_m3_route(job):
        if request.method == 'POST':
            try:
                return redirect(url_for(configure_m3(job, request.form)))
            except WorkflowError as exc:
                flash(str(exc),'error');return redirect(url_for(exc.back))
        return render_template('m3_ui.html',stage='configure',job=job)

    @app.get("/")
    def index():
        return render_template("ui.html", stage="upload", max_upload_mib=max_upload_mib)

    @app.post("/upload")
    def upload():
        try:
            start_job(store, analysis_config, request.form.get("mode", "classification"), request.files.get("dataset"))
        except WorkflowError as exc:
            flash(str(exc), "error")
            return redirect(url_for(exc.back))
        return redirect(url_for("configure"))

    @app.route("/configure", methods=["GET", "POST"])
    def configure():
        job = require_job()
        if not job:
            return redirect(url_for("index"))

        if job["mode"] in m3_modes:
            return configure_m3_route(job)

        if request.method == "POST":
            try:
                next_stage = configure_core(job, request.form)
            except WorkflowError as exc:
                flash(str(exc), "error")
                return redirect(url_for(exc.back))
            return redirect(url_for(next_stage))

        return render_template("ui.html", stage="configure", job=job)

    @app.get("/confirm")
    def confirm():
        job = require_job()
        if not job:
            return redirect(url_for("index"))
        if "target_info" not in job:
            return redirect(url_for("configure"))
        return render_template("m3_ui.html" if job["mode"] in m3_modes else "ui.html", stage="confirm", job=job)

    @app.post("/generate")
    def generate():
        job = require_job()
        if not job:
            return redirect(url_for("index"))
        try:
            generate_report(job, request.form, analysis_config)
        except WorkflowError as exc:
            flash(str(exc), "error")
            return redirect(url_for(exc.back))
        return redirect(url_for("result"))

    @app.get("/result")
    def result():
        job = require_job()
        if not job:
            return redirect(url_for("index"))
        if not owned(job, "html"):
            return redirect(url_for("confirm"))
        if "summary" not in job:
            return redirect(url_for("confirm"))
        return render_template("m3_ui.html" if job["mode"] in m3_modes else "ui.html", stage="result", job=job)

    @app.get("/report")
    def report():
        job = require_job()
        if not job or not owned(job, "html"):
            abort(404)
        return send_file(job["report_path"], mimetype="text/html")

    @app.get("/download")
    def download():
        job = require_job()
        if not job or not owned(job, "html"):
            abort(404)
        stem = secure_filename(job.get("dataset_name") or Path(job["source_filename"]).stem)
        return send_file(
            job["report_path"],
            mimetype="text/html",
            as_attachment=True,
            download_name=f"{stem or 'datatrust'}-reliability-report.html",
        )

    @app.get("/download/pdf")
    def download_pdf():
        job = require_job()
        if not job or not owned(job, "html"):
            abort(404)

        try:
            pdf_path = core_pdf(job)
        except (PDFRenderError, ValueError) as exc:
            flash(str(exc), "error")
            return redirect(url_for("result"))

        stem = secure_filename(job.get("dataset_name") or Path(job["source_filename"]).stem)
        return send_file(
            pdf_path,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=f"{stem or 'datatrust'}-reliability-report.pdf",
        )

    @app.get("/download/json")
    def download_json():
        job = require_job()
        if not job or not owned(job, "json"):
            abort(404)
        return send_file(job["json_path"], mimetype="application/json", as_attachment=True, download_name="datatrust-analysis.json")

    @app.post("/new")
    def new_analysis():
        store.remove(session.pop("job_id", None))
        return redirect(url_for("index"))

    @app.errorhandler(413)
    def too_large(_error):
        flash(f"CSV exceeds the {max_upload_mib:g} MiB local UI limit.", "error")
        return render_template(
            "ui.html", stage="upload", max_upload_mib=max_upload_mib
        ), 413

    @app.errorhandler(400)
    def bad_request(error):
        return render_template(
            "ui.html", stage="error", error_message=getattr(error, "description", str(error))
        ), 400

    @app.errorhandler(MemoryError)
    def allocation_failed(_error):
        flash("The dataset could not be analyzed with available memory. Try a smaller input or tighter limits.", "error")
        job = current_job()
        return redirect(url_for("confirm" if job and "target_info" in job else "index"))

    from datatrust.m4_web import register
    register(app, workspace, data_roots or (Path.cwd(),), analysis_config)
    from datatrust.temporal_web import register as register_temporal
    register_temporal(app,workspace,data_roots or (Path.cwd(),))
    from datatrust.text_web import register as register_text
    register_text(app,workspace,data_roots or (Path.cwd(),))
    from datatrust.image_web import register as register_images
    register_images(app,workspace,data_roots or (Path.cwd(),))
    from datatrust.cross_web import register as register_cross
    register_cross(app,workspace,data_roots or (Path.cwd(),))
    classic_endpoints = set(app.view_functions) - {"static"}  # the classic pages, before the app API and ConfidenceGuard
    from datatrust.api_web import register as register_app_api
    register_app_api(app, analysis_config, max_upload_mib, history=history, launch_token=launch_token)
    from confidenceguard.transport import register as register_confidenceguard
    register_confidenceguard(app,workspace,data_roots or (Path.cwd(),),persistent_workspace=confidenceguard_workspace,launch_token=confidenceguard_launch_token)
    if not classic_ui:
        retire_classic_pages(app, classic_endpoints)
    return app


CLASSIC_TO_APP = (("/m4", "/app/m4/sources"), ("/temporal", "/app/temporal/sources"), ("/text", "/app/text/sources"),
                  ("/images", "/app/images/sources"), ("/cross-representation", "/app/cross/sources"))


def retire_classic_pages(app, endpoints):
    """Serve the DataTrust app in place of the classic pages: their GETs lead to the matching app page, their
    form posts no longer exist. Only the classic DataTrust endpoints are affected; the app API, the app itself
    and ConfidenceGuard keep their routes, guards and sessions unchanged."""
    def app_only():
        if request.endpoint not in endpoints:
            return None
        if request.method in {"GET", "HEAD"}:
            return redirect(next((to for prefix, to in CLASSIC_TO_APP if request.path == prefix or request.path.startswith(prefix + "/")), "/app/"))
        abort(404)
    app.before_request(app_only)  # after the form-token check, so a post without its token is refused exactly as before


def run_ui(port: int = 8000, max_upload_mib: float = 100, open_browser: bool = True, analysis_config=None, data_roots=None,
           history_dir=None, history_enabled: bool = True) -> None:
    """Run the single-user loopback UI and clean its temporary workspace.

    The DataTrust app is the interface: `/` leads to it and the classic pages are not served. It opens through
    a one-time launch link that unlocks saved analyses for that browser. History
    keeps verified copies of canonical artifacts only; the temporary workspace is still removed on exit."""
    from datatrust.history import History, default_history_dir
    history = History(history_dir or default_history_dir()) if history_enabled else None
    launch_token = secrets.token_urlsafe(32)
    with tempfile.TemporaryDirectory(prefix="datatrust-ui-") as temporary_root:
        app = create_app(Path(temporary_root), max_upload_mib=max_upload_mib, analysis_config=analysis_config, data_roots=data_roots,
                         history=history, launch_token=launch_token, classic_ui=False)
        url = f"http://127.0.0.1:{port}/app/?launch={launch_token}"
        if open_browser:
            timer = threading.Timer(0.6, webbrowser.open, args=(url,))
            timer.daemon = True
            timer.start()
        else:
            print(f"Open the DataTrust app (this link works once): {url}", flush=True)
        try:
            app.run(
                host="127.0.0.1",
                port=port,
                debug=False,
                use_reloader=False,
                threaded=False,
            )
        finally:
            try:
                app.extensions['datatrust_history_sweep']()
            except Exception:
                app.logger.warning("Saved analyses could not be updated before shutdown.")
            app.extensions['confidenceguard_store'].cleanup()
            app.extensions['datatrust_m6_store'].cleanup()
            app.extensions['datatrust_m9_store'].cleanup()
            app.extensions['datatrust_m5_store'].cleanup()
            app.extensions['datatrust_m4_store'].cleanup()
            app.extensions["datatrust_job_store"].cleanup()


def _source_filename(filename: str) -> str:
    normalized = str(filename).replace("\\", "/")
    return Path(normalized).name[:255] or "dataset.csv"


def _result_summary(result: dict) -> dict:
    risks = [
        {
            "title": item["title"],
            "severity": item["severity"],
            "finding": item["finding"],
        }
        for item in result["risks"][:3]
    ]
    narrative = result["narrative"]
    return {
        "dataset_name": result["context"]["dataset_name"],
        "source_filename": result["context"]["source_filename"],
        "target": result["profile"]["target"],
        "overall": result["scores"]["overall"],
        "risk_level": result["scores"]["risk_level"],
        "recommended_action": result["scores"]["recommended_action"],
        "overall_assessment": narrative["overall_assessment"],
        "score_explanation": narrative["score_explanation"],
        "principal_evidence_summary": narrative["principal_evidence_summary"],
        "what_this_means": narrative["principal_evidence_summary"],
        "risks": risks,
    }
