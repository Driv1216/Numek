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
from datatrust.ingestion import inspect_unlabeled_dataset, inspect_regression_dataset, inspect_regression_target, load_dataset, source_digest, source_signature
from datatrust.annotations import effective_policy, annotation_coverage, feature_semantics, specification_fingerprint
from datatrust.contracts import AnnotationOptions, AnnotationSpec, FeatureOptions, MultilabelOptions
from datatrust.pdf import PDFRenderError, render_pdf_report
from datatrust.profiler import inspect_classification_target, inspect_csv_dataset
from datatrust.renderer import ArtifactCollisionError, write_report_artifacts, _regression_inspection_notice


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


def create_app(workspace: Path, max_upload_mib: float = 100, analysis_config=None, data_roots=None) -> Flask:
    analysis_config = analysis_config or AnalysisConfig()
    if not isinstance(analysis_config, AnalysisConfig):
        raise ValueError("analysis_config must be AnalysisConfig.")
    app = Flask(__name__, template_folder="templates")
    app.jinja_env.filters["regression_inspection_notice"] = _regression_inspection_notice
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

    def owned(job, kind):
        identity = job.get("artifacts", {}).get(kind)
        if not identity:
            return False
        path = identity["path"]
        return (not path.is_symlink() and path.is_file() and source_signature(path) == identity["signature"]
                and source_digest(path) == identity["sha256"])

    def remember(job, artifacts):
        for kind in ("html", "pdf", "json"):
            location = getattr(artifacts, f"{kind}_path")
            if location:
                path = Path(location)
                job.setdefault("artifacts", {})[kind] = {"path": path, "sha256": source_digest(path), "signature": source_signature(path)}
                job[f"{'report' if kind == 'html' else kind}_path"] = path

    def invalidate(job):
        # Verify the entire set before touching anything. Filenames do not prove ownership.
        for kind, identity in job.get("artifacts", {}).items():
            if identity["path"].exists() or identity["path"].is_symlink():
                if not owned(job, kind):
                    raise ArtifactCollisionError(f"Unrecognized job artifact at {identity['path']}; it was left untouched.")
        for identity in job.get("artifacts", {}).values():
            identity["path"].unlink(missing_ok=True)
        for key in ("artifacts", "report_path", "pdf_path", "json_path", "summary", "analysis_result", "pdf_html_digest"):
            job.pop(key, None)

    m3_modes = {'annotation_classification','annotation_regression','multilabel_classification','clustering','anomaly_detection','role_profile'}
    kind_for = {'annotation_classification':'classification','annotation_regression':'regression','role_profile':'dataset_profile'}

    def populate_m3_forms(job):
        config = job['config']; annotation = config.annotations
        job.update(
            annotation_status_json=json.dumps(asdict(annotation.default)['status_values']) if annotation else None,
            per_target_annotation_json=json.dumps({k:asdict(v) for k,v in annotation.per_target.items()}) if annotation else None,
            expectations_json=json.dumps({k:asdict(v) for k,v in config.regression.expectations_by_target.items()}) if config.regression else None,
            availability_json=json.dumps(config.regression.feature_availability) if config.regression else None,
            multilabel_json=json.dumps(asdict(config.multilabel)) if config.multilabel else None,
        )

    def configure_m3(job):
        if request.method == 'POST':
            try:
                columns=job['inspection']['columns']
                roles={c:request.form.get('role_'+c,'feature') for c in columns}
                if any(r not in {'feature','target','metadata','group','ignored'} for r in roles.values()): raise ValueError('Invalid column role.')
                targets=tuple(c for c in columns if roles[c]=='target')
                kind=kind_for.get(job['mode'],job['mode'])
                annotation=None
                if targets:
                    default=AnnotationSpec(request.form.get('annotation_expectation','unknown'),request.form.get('status_column') or None,json.loads(request.form.get('status_values','null')))
                    annotation=AnnotationOptions(default,json.loads(request.form.get('per_target_annotations','{}')))
                    status_columns={spec.status_column for spec in [default,*annotation.per_target.values()] if spec.status_column}
                    for c in status_columns:
                        if c in roles and roles[c]=='feature': roles[c]='metadata'
                features=tuple(c for c in columns if roles[c]=='feature')
                task=TaskSpec(kind,targets=targets,feature_columns=features,metadata_columns=tuple(c for c in columns if roles[c]=='metadata'),group_columns=tuple(c for c in columns if roles[c]=='group'))
                semantics={c:request.form.get('semantic_'+c) for c in features if request.form.get('semantic_'+c,'undeclared')!='undeclared'}
                sensitivity={'unknown':None,'true':True,'false':False}.get(request.form.get('scale_sensitive','unknown'))
                parsing=CsvParseOptions(request.form.get('encoding','utf-8'),request.form.get('missing_policy','pandas_default'),json.loads(request.form.get('na_values','[]')),json.loads(request.form.get('column_types','{}')))
                regression = None
                if kind == 'regression':
                    base = job['config'].regression or RegressionOptions()
                    declarations = RegressionOptions.from_dict({'expectations_by_target':json.loads(request.form.get('expectations_by_target','{}')),'feature_availability':json.loads(request.form.get('feature_availability','{}'))})
                    regression = replace(base, expectations_by_target=declarations.expectations_by_target,
                                         feature_availability=declarations.feature_availability)
                    if declarations.expectations_by_target and len(targets)>1:
                        regression = replace(regression, expectations=declarations.expectations)
                config=replace(job['config'],parsing=parsing,annotations=annotation,features=FeatureOptions(semantics,sensitivity),
                               regression=regression,
                               multilabel=AnalysisConfig.from_dict({'multilabel':json.loads(request.form.get('multilabel_options','{}'))}).multilabel if kind=='multilabel_classification' else None)
                audit=DataTrust.from_spec(DatasetSpec(job['dataset_path'],dataset_name=request.form.get('dataset_name'),purpose=request.form.get('purpose')),task,config)
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
                invalidate(job)
                job.update(task_spec=task,config=config,target_info=info,dataset_name=audit.dataset_name,purpose=audit.purpose,
                           annotation_status_json=json.dumps(asdict(annotation.default)['status_values']) if annotation else None,
                           per_target_annotation_json=json.dumps({k:asdict(v) for k,v in annotation.per_target.items()}) if annotation else None,
                           expectations_json=json.dumps({k:asdict(v) for k,v in config.regression.expectations_by_target.items()}) if config.regression else None,
                           availability_json=json.dumps(config.regression.feature_availability) if config.regression else None,
                           multilabel_json=json.dumps(asdict(config.multilabel)) if config.multilabel else None)
                return redirect(url_for('confirm'))
            except (ValueError,FileNotFoundError) as exc:
                job.pop('target_info',None);flash(str(exc),'error');return redirect(url_for('configure'))
        return render_template('m3_ui.html',stage='configure',job=job)

    def audit_for(job):
        config = job.get("config", analysis_config)
        if job["mode"] == "classification":
            config = replace(config, parsing=CsvParseOptions())
        return DataTrust.from_spec(DatasetSpec(str(job["dataset_path"]), dataset_name=job.get("dataset_name"),
            purpose=job.get("purpose"), source_filename=job["source_filename"]),
            job.get("task_spec") or TaskSpec("dataset_profile" if job["mode"] == "unlabeled" else job["mode"], job.get("target")), config)

    @app.get("/")
    def index():
        return render_template("ui.html", stage="upload", max_upload_mib=max_upload_mib)

    @app.post("/upload")
    def upload():
        mode = request.form.get("mode", "classification")
        if mode not in {"classification", "unlabeled", "regression"} | m3_modes:
            abort(400, description="Choose classification, regression, or unlabeled profiling.")
        uploaded = request.files.get("dataset")
        if uploaded is None or not uploaded.filename:
            flash("Choose a CSV file to continue.", "error")
            return redirect(url_for("index"))

        source_filename = _source_filename(uploaded.filename)
        if not source_filename.lower().endswith(".csv"):
            flash("DataTrust accepts .csv files only.", "error")
            return redirect(url_for("index"))

        store.remove(session.pop("job_id", None))
        job = store.create(uploaded, source_filename)
        job.update(mode=mode, config=analysis_config)
        if mode in m3_modes:
            populate_m3_forms(job)
        if analysis_config.regression is not None and mode not in {"regression","annotation_regression"}:
            store.remove(job["id"])
            flash("Regression options require regression mode.", "error")
            return redirect(url_for("index"))
        try:
            job["inspection"] = (inspect_csv_dataset(job["dataset_path"], preview_rows=10) if mode == "classification"
                else (inspect_regression_dataset if mode == "regression" else inspect_unlabeled_dataset)(DatasetSpec(job["dataset_path"]), job["config"]))
            job["file_size"] = job["dataset_path"].stat().st_size
        except (FileNotFoundError, ValueError) as exc:
            store.remove(job["id"])
            flash(str(exc), "error")
            return redirect(url_for("index"))

        session["job_id"] = job["id"]
        return redirect(url_for("configure"))

    @app.route("/configure", methods=["GET", "POST"])
    def configure():
        job = require_job()
        if not job:
            return redirect(url_for("index"))

        if job["mode"] in m3_modes:
            return configure_m3(job)

        if request.method == "POST":
            target = request.form.get("target", "") if job["mode"] != "unlabeled" else None
            dataset_name = request.form.get("dataset_name", "")
            purpose = request.form.get("purpose", "")
            if job["mode"] != "unlabeled" and target not in job["inspection"]["columns"] and request.form.get("action") != "preview":
                flash("Choose a target column from the uploaded dataset.", "error")
                return redirect(url_for("configure"))
            try:
                if job["mode"] != "classification":
                    if job["mode"] == "unlabeled" and request.form.get("target"):
                        raise ValueError("Unlabeled dataset profiling does not accept a target.")
                    parsing = CsvParseOptions(encoding=request.form.get("encoding", job["config"].parsing.encoding),
                        missing_policy=request.form.get("missing_policy", job["config"].parsing.missing_policy),
                        na_values=json.loads(request.form.get("na_values", json.dumps(job["config"].parsing.na_values))),
                        column_types=json.loads(request.form.get("column_types", json.dumps(job["config"].parsing.column_types))))
                    updated_config = replace(job["config"], parsing=parsing)
                    if job["mode"] == "regression":
                        existing = job["config"].regression or RegressionOptions()
                        def optional_number(name, default):
                            if name not in request.form:
                                return default
                            text = request.form[name]
                            return float(text) if text.strip() else None
                        def optional_flag(name, default):
                            return True if request.form.get(name) else None if request.form.get("regression_options_submitted") else default
                        expectations = TargetExpectations(kind=request.form.get("target_kind", existing.expectations.kind),
                            minimum=optional_number("target_minimum", existing.expectations.minimum), maximum=optional_number("target_maximum", existing.expectations.maximum),
                            units=request.form.get("target_units", existing.expectations.units or "").strip() or None,
                            nonnegative=optional_flag("target_nonnegative", existing.expectations.nonnegative),
                            integer_required=optional_flag("target_integer", existing.expectations.integer_required))
                        availability = {c:request.form.get("availability_"+c, existing.feature_availability.get(c, "unknown")) for c in job["inspection"]["columns"] if c != target}
                        availability = {c:v for c,v in availability.items() if v != "unknown"}
                        updated_config = replace(updated_config, regression=RegressionOptions(expectations, availability, existing.relation_limits))
                    inspection = (inspect_regression_dataset if job["mode"] == "regression" else inspect_unlabeled_dataset)(DatasetSpec(job["dataset_path"]), updated_config)
                else:
                    updated_config = replace(job["config"], parsing=CsvParseOptions())
                    inspection = dict(job["inspection"])
                    handle = load_dataset(DatasetSpec(job["dataset_path"]), TaskSpec("classification", target),
                        updated_config, updated_config.limits or ExecutionLimits(), lambda stage: None, preview_rows=10)
                    inspection.update(parsing=handle.parsing, parsing_warnings=handle.parsing_warnings,
                                      limits=asdict(updated_config.limits or ExecutionLimits()))
                audit = DataTrust.from_spec(DatasetSpec(job["dataset_path"], dataset_name=dataset_name, purpose=purpose),
                    TaskSpec("dataset_profile" if job["mode"] == "unlabeled" else job["mode"], target or (inspection["columns"][0] if job["mode"] == "regression" and request.form.get("action") == "preview" else target)), updated_config)
                target_info = (inspect_classification_target(job["dataset_path"], target) if job["mode"] == "classification" else
                    inspect_regression_target(DatasetSpec(job["dataset_path"]), target, updated_config) if job["mode"] == "regression" and request.form.get("action") != "preview" else None)
                invalidate(job)
            except (FileNotFoundError, ValueError) as exc:
                flash(str(exc), "error")
                return redirect(url_for("configure"))

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
            if request.form.get("action") == "preview":
                if job["mode"] == "regression":
                    job.pop("target_info", None)
                return redirect(url_for("configure"))
            return redirect(url_for("confirm"))

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
        if "target_info" not in job:
            flash("Confirm the target before generating the report.", "error")
            return redirect(url_for("configure"))
        if (
            job["mode"] in {"classification", "regression"}
            and job["target_info"]["suitability"]["requires_override"]
            and request.form.get("advanced_target_ack") != "confirmed"
        ):
            flash(
                "Confirm that you still want to use this advanced choice as the prediction outcome.",
                "error",
            )
            return redirect(url_for("confirm"))
        try:
            if job['mode'] in m3_modes:
                info=job['target_info']
                if request.form.get('representation_ack')!='confirmed': raise ValueError('Confirm the representation assumptions before generating the report.')
                if source_digest(job['dataset_path'])!=info['source_sha256'] or specification_fingerprint(job['task_spec'],job['config'],job['inspection']['columns'])!=info['specification_fingerprint']:
                    job.pop('target_info',None)
                    raise ValueError('Source or effective configuration changed since confirmation; review again.')
            if job["mode"] == "regression" and source_digest(job["dataset_path"]) != job["target_info"]["source_sha256"]:
                job.pop("target_info", None)
                raise ValueError("Source changed since regression confirmation; review the target again.")
            invalidate(job)
            report_path = job["directory"] / "report.html"
            audit = audit_for(job)
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
            if job['mode'] in m3_modes:
                if typed.parsing['source_sha256']!=job['target_info']['source_sha256'] or typed.parsing['fingerprint']!=job['target_info']['parsing_fingerprint']:
                    job.pop('target_info',None)
                    raise ValueError('Source/parsing changed since confirmation; no report was published.')
            artifacts = write_report_artifacts(typed, report_path, json_path=job["directory"] / "analysis.json", legacy_html=typed.methodology_id == "classification_legacy_2026_08_13")
            remember(job, artifacts)
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
                remember(job, exc.artifacts)
            flash(str(exc), "error")
            return redirect(url_for("confirm"))
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

        pdf_path = job["directory"] / "report.pdf"
        if not (owned(job, "pdf") and job.get("pdf_html_digest") == job["artifacts"]["html"]["sha256"]):
            try:
                artifacts = write_report_artifacts(job["analysis_result"], pdf_path, format="pdf",
                    html_path=job["report_path"], pdf_converter=render_pdf_report, legacy_html=job["analysis_result"].methodology_id == "classification_legacy_2026_08_13")
                remember(job, artifacts)
                job["pdf_html_digest"] = job["artifacts"]["html"]["sha256"]
            except (PDFRenderError, ValueError) as exc:
                flash(str(exc), "error")
                return redirect(url_for("result"))
        job["pdf_path"] = pdf_path

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
    return app


def run_ui(port: int = 8000, max_upload_mib: float = 100, open_browser: bool = True, analysis_config=None, data_roots=None) -> None:
    """Run the single-user loopback UI and clean its temporary workspace."""
    with tempfile.TemporaryDirectory(prefix="datatrust-ui-") as temporary_root:
        app = create_app(Path(temporary_root), max_upload_mib=max_upload_mib, analysis_config=analysis_config, data_roots=data_roots)
        url = f"http://127.0.0.1:{port}/"
        if open_browser:
            timer = threading.Timer(0.6, webbrowser.open, args=(url,))
            timer.daemon = True
            timer.start()
        try:
            app.run(
                host="127.0.0.1",
                port=port,
                debug=False,
                use_reloader=False,
                threaded=False,
            )
        finally:
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
