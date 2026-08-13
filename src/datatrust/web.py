import hmac
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

from datatrust import DataTrust
from datatrust.pdf import PDFRenderError, render_pdf_report
from datatrust.profiler import inspect_classification_target, inspect_csv_dataset
from datatrust.renderer import write_html_report


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


def create_app(workspace: Path, max_upload_mib: float = 100) -> Flask:
    app = Flask(__name__, template_folder="templates")
    app.secret_key = secrets.token_bytes(32)
    app.config.update(
        MAX_CONTENT_LENGTH=int(max_upload_mib * 1024 * 1024),
        MAX_UPLOAD_MIB=max_upload_mib,
    )
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

    @app.get("/")
    def index():
        return render_template("ui.html", stage="upload", max_upload_mib=max_upload_mib)

    @app.post("/upload")
    def upload():
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
        try:
            job["inspection"] = inspect_csv_dataset(job["dataset_path"], preview_rows=10)
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

        if request.method == "POST":
            target = request.form.get("target", "")
            dataset_name = request.form.get("dataset_name", "")
            purpose = request.form.get("purpose", "")
            if target not in job["inspection"]["columns"]:
                flash("Choose a target column from the uploaded dataset.", "error")
                return redirect(url_for("configure"))
            try:
                audit = DataTrust(
                    str(job["dataset_path"]),
                    target=target,
                    dataset_name=dataset_name,
                    purpose=purpose,
                )
                target_info = inspect_classification_target(job["dataset_path"], target)
            except (FileNotFoundError, ValueError) as exc:
                flash(str(exc), "error")
                return redirect(url_for("configure"))

            job.update(
                {
                    "target": target,
                    "dataset_name": audit.dataset_name,
                    "purpose": audit.purpose,
                    "target_info": target_info,
                }
            )
            return redirect(url_for("confirm"))

        return render_template("ui.html", stage="configure", job=job)

    @app.get("/confirm")
    def confirm():
        job = require_job()
        if not job:
            return redirect(url_for("index"))
        if "target_info" not in job:
            return redirect(url_for("configure"))
        return render_template("ui.html", stage="confirm", job=job)

    @app.post("/generate")
    def generate():
        job = require_job()
        if not job:
            return redirect(url_for("index"))
        if "target_info" not in job:
            flash("Confirm the target before generating the report.", "error")
            return redirect(url_for("configure"))
        if (
            job["target_info"]["suitability"]["requires_override"]
            and request.form.get("advanced_target_ack") != "confirmed"
        ):
            flash(
                "Confirm that you still want to use this advanced choice as the prediction outcome.",
                "error",
            )
            return redirect(url_for("confirm"))
        try:
            report_path = job["directory"] / "report.html"
            audit = DataTrust(
                str(job["dataset_path"]),
                target=job["target"],
                dataset_name=job["dataset_name"],
                purpose=job["purpose"],
                source_filename=job["source_filename"],
            )
            result = audit.analyze()
            write_html_report(result, str(report_path))
            job.update(
                {
                    "report_path": report_path,
                    "summary": _result_summary(result),
                }
            )
        except (FileNotFoundError, ValueError) as exc:
            flash(str(exc), "error")
            return redirect(url_for("confirm"))
        return redirect(url_for("result"))

    @app.get("/result")
    def result():
        job = require_job()
        if not job:
            return redirect(url_for("index"))
        if not job.get("report_path", Path()).is_file():
            return redirect(url_for("confirm"))
        if "summary" not in job:
            return redirect(url_for("confirm"))
        return render_template("ui.html", stage="result", job=job)

    @app.get("/report")
    def report():
        job = require_job()
        if not job or not job.get("report_path", Path()).is_file():
            abort(404)
        return send_file(job["report_path"], mimetype="text/html")

    @app.get("/download")
    def download():
        job = require_job()
        if not job or not job.get("report_path", Path()).is_file():
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
        if not job or not job.get("report_path", Path()).is_file():
            abort(404)

        pdf_path = job["directory"] / "report.pdf"
        if not pdf_path.is_file():
            try:
                render_pdf_report(job["report_path"], pdf_path)
            except PDFRenderError as exc:
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

    return app


def run_ui(port: int = 8000, max_upload_mib: float = 100, open_browser: bool = True) -> None:
    """Run the single-user loopback UI and clean its temporary workspace."""
    with tempfile.TemporaryDirectory(prefix="datatrust-ui-") as temporary_root:
        app = create_app(Path(temporary_root), max_upload_mib=max_upload_mib)
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
