from io import BytesIO
from pathlib import Path

import pandas as pd
from click.testing import CliRunner
from pypdf import PdfReader

from datatrust import DataTrust
from datatrust.cli import main
from datatrust.pdf import PDFRenderError
from datatrust.web import create_app


def _token(client):
    client.get("/")
    with client.session_transaction() as state:
        return state["form_token"]


def _csv_bytes(data: dict) -> BytesIO:
    return BytesIO(pd.DataFrame(data).to_csv(index=False).encode("utf-8"))


def test_complete_local_ui_flow_download_and_cleanup(tmp_path, monkeypatch):
    app = create_app(tmp_path / "jobs", max_upload_mib=1)
    app.config.update(TESTING=True)
    client = app.test_client()
    token = _token(client)

    upload = client.post(
        "/upload",
        data={
            "form_token": token,
            "dataset": (_csv_bytes({"note": ["<script>x</script>", "safe"], "label": [0, 1]}), "demo.csv"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert upload.status_code == 200
    assert b"Configure the analysis" in upload.data
    assert b"&lt;script&gt;x&lt;/script&gt;" in upload.data

    configured = client.post(
        "/configure",
        data={
            "form_token": token,
            "target": "label",
            "dataset_name": "<b>Demo</b>",
            "purpose": "Check <script>labels</script>",
        },
        follow_redirects=True,
    )
    assert b"Detected task: Binary classification" in configured.data

    original_analyze = DataTrust.analyze
    analyze_calls = 0

    def counted_analyze(audit):
        nonlocal analyze_calls
        analyze_calls += 1
        return original_analyze(audit)

    monkeypatch.setattr(DataTrust, "analyze", counted_analyze)
    generated = client.post(
        "/generate", data={"form_token": token}, follow_redirects=True
    )
    assert generated.status_code == 200
    assert analyze_calls == 1
    assert b"Dataset reliability overview" in generated.data
    assert b"What this means" in generated.data
    assert b"Recommended next action" in generated.data
    assert b"Download PDF" in generated.data
    assert b"View full report" in generated.data
    assert b"Print / Save as PDF" not in generated.data
    assert b"Download HTML" not in generated.data
    assert b"<iframe" not in generated.data
    assert b"2. Priority Actions" not in generated.data
    assert b"&lt;b&gt;Demo&lt;/b&gt;" in generated.data
    assert b"No guardrail changed the evidence score" in generated.data

    report = client.get("/report")
    assert report.status_code == 200
    assert b"2. Priority Actions" in report.data
    assert b"&lt;b&gt;Demo&lt;/b&gt;" in report.data
    assert b"Source: demo.csv" in report.data
    assert b"No guardrail changed the evidence score" in report.data
    assert str(tmp_path).encode() not in report.data

    download = client.get("/download")
    assert download.status_code == 200
    assert "attachment" in download.headers["Content-Disposition"]
    assert download.headers["Content-Disposition"].endswith("-reliability-report.html")
    assert "<" not in download.headers["Content-Disposition"]

    pdf_download = client.get("/download/pdf")
    assert pdf_download.status_code == 200
    assert pdf_download.mimetype == "application/pdf"
    assert pdf_download.data.startswith(b"%PDF")
    assert "attachment" in pdf_download.headers["Content-Disposition"]
    assert pdf_download.headers["Content-Disposition"].endswith(
        "-reliability-report.pdf"
    )
    pdf = PdfReader(BytesIO(pdf_download.data))
    pdf_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    assert len(pdf.pages) > 0
    assert "DataTrust Reliability Report" in pdf_text
    assert "1. Decision Summary" in pdf_text
    assert "8. Technical Appendix" in pdf_text

    def unexpected_render(*_args, **_kwargs):
        raise AssertionError("cached PDF should be reused")

    monkeypatch.setattr("datatrust.web.render_pdf_report", unexpected_render)
    cached_pdf = client.get("/download/pdf")
    assert cached_pdf.status_code == 200
    assert cached_pdf.data == pdf_download.data

    with client.session_transaction() as state:
        job_id = state["job_id"]
    store = app.extensions["datatrust_job_store"]
    job_directory = store.get(job_id)["directory"]
    assert job_directory.exists()

    response = client.post("/new", data={"form_token": token}, follow_redirects=True)
    assert b"Generate a reliability report" in response.data
    assert not job_directory.exists()


def test_pdf_failure_is_actionable_and_html_report_survives(tmp_path, monkeypatch):
    app = create_app(tmp_path / "jobs", max_upload_mib=1)
    app.config.update(TESTING=True)
    client = app.test_client()
    token = _token(client)

    client.post(
        "/upload",
        data={
            "form_token": token,
            "dataset": (_csv_bytes({"x": [1, 2], "label": [0, 1]}), "demo.csv"),
        },
        content_type="multipart/form-data",
    )
    client.post(
        "/configure",
        data={
            "form_token": token,
            "target": "label",
            "dataset_name": "PDF Demo",
            "purpose": "",
        },
    )
    client.post("/generate", data={"form_token": token})

    def fail_pdf(*_args, **_kwargs):
        raise PDFRenderError(
            "PDF generation is unavailable. The HTML report is still available."
        )

    monkeypatch.setattr("datatrust.web.render_pdf_report", fail_pdf)
    failed = client.get("/download/pdf", follow_redirects=True)
    assert failed.status_code == 200
    assert b"PDF generation is unavailable" in failed.data
    assert b"Dataset reliability overview" in failed.data
    assert client.get("/report").status_code == 200


def test_pdf_download_requires_an_active_report(tmp_path):
    app = create_app(tmp_path / "jobs", max_upload_mib=1)
    app.config.update(TESTING=True)
    client = app.test_client()
    _token(client)

    assert client.get("/download/pdf").status_code == 404


def test_result_overview_uses_top_three_existing_risks(tmp_path):
    app = create_app(tmp_path / "jobs", max_upload_mib=1)
    app.config.update(TESTING=True)
    client = app.test_client()
    token = _token(client)

    client.post(
        "/upload",
        data={
            "form_token": token,
            "dataset": (
                BytesIO(Path("examples/loan_data.csv").read_bytes()),
                "loan_data.csv",
            ),
        },
        content_type="multipart/form-data",
    )
    client.post(
        "/configure",
        data={
            "form_token": token,
            "target": "default",
            "dataset_name": "Loan Review",
            "purpose": "",
        },
    )
    result = client.post(
        "/generate", data={"form_token": token}, follow_redirects=True
    )

    assert b"Possible target leakage" in result.data
    assert b"High-cardinality categoricals" in result.data
    assert b"Numeric outlier concentration" in result.data
    assert b"Leakage review prompts" not in result.data
    assert b"Validation performance may look much better" in result.data
    assert b"Completeness" not in result.data
    assert b"Rows with missing features" not in result.data


def test_ui_reports_invalid_extension_empty_csv_and_invalid_target(tmp_path):
    app = create_app(tmp_path / "jobs", max_upload_mib=1)
    app.config.update(TESTING=True)
    client = app.test_client()
    token = _token(client)

    invalid = client.post(
        "/upload",
        data={"form_token": token, "dataset": (BytesIO(b"a,b\n1,2\n"), "data.txt")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert b"accepts .csv files only" in invalid.data

    empty = client.post(
        "/upload",
        data={"form_token": token, "dataset": (BytesIO(b""), "empty.csv")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert b"Dataset is empty" in empty.data

    client.post(
        "/upload",
        data={"form_token": token, "dataset": (_csv_bytes({"x": [1, 2], "label": [0, 1]}), "ok.csv")},
        content_type="multipart/form-data",
    )
    invalid_target = client.post(
        "/configure",
        data={"form_token": token, "target": "missing", "dataset_name": "", "purpose": ""},
        follow_redirects=True,
    )
    assert b"Choose a target column" in invalid_target.data


def test_ui_handles_missing_labels_stale_jobs_upload_limit_and_bad_token(tmp_path):
    app = create_app(tmp_path / "jobs", max_upload_mib=0.001)
    app.config.update(TESTING=True)
    client = app.test_client()
    token = _token(client)

    too_large = client.post(
        "/upload",
        data={"form_token": token, "dataset": (BytesIO(b"x" * 3000), "large.csv")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert too_large.status_code == 413
    assert b"exceeds the 0.001 MiB" in too_large.data

    stale = client.get("/configure", follow_redirects=True)
    assert b"no longer available" in stale.data

    bad_token = client.post("/new", data={"form_token": "wrong"})
    assert bad_token.status_code == 400
    assert b"form session expired" in bad_token.data


def test_ui_rejects_target_without_usable_labels_and_long_metadata(tmp_path):
    app = create_app(tmp_path / "jobs", max_upload_mib=1)
    app.config.update(TESTING=True)
    client = app.test_client()
    token = _token(client)
    client.post(
        "/upload",
        data={
            "form_token": token,
            "dataset": (_csv_bytes({"x": [1, 2], "label": [None, None]}), "labels.csv"),
        },
        content_type="multipart/form-data",
    )

    no_labels = client.post(
        "/configure",
        data={"form_token": token, "target": "label", "dataset_name": "", "purpose": ""},
        follow_redirects=True,
    )
    assert b"has no usable labels" in no_labels.data

    long_name = client.post(
        "/configure",
        data={"form_token": token, "target": "x", "dataset_name": "a" * 121, "purpose": ""},
        follow_redirects=True,
    )
    assert b"Dataset name must be 120 characters or fewer" in long_name.data


def test_ui_cli_options_call_runner_without_blocking(monkeypatch):
    captured = {}

    def fake_run_ui(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr("datatrust.cli.run_ui", fake_run_ui)
    result = CliRunner().invoke(
        main, ["ui", "--port", "8123", "--max-upload-mib", "12.5", "--no-open"]
    )

    assert result.exit_code == 0
    assert "http://127.0.0.1:8123/" in result.output
    assert captured == {"port": 8123, "max_upload_mib": 12.5, "open_browser": False}


def test_configure_groups_ambiguous_targets_without_preselection(tmp_path):
    app = create_app(tmp_path / "jobs", max_upload_mib=1)
    app.config.update(TESTING=True)
    client = app.test_client()
    token = _token(client)
    data = {
        "customer_id": range(20),
        "risk_score": ["low", "high"] * 10,
        "risk_grade": ["a", "b", "c", "a", "b"] * 4,
        "approved": [0, 1] * 10,
        "defaulted_90d": [0, 1] * 10,
        "previous_outcome": ["yes", "no"] * 10,
    }

    configured = client.post(
        "/upload",
        data={
            "form_token": token,
            "dataset": (_csv_bytes(data), "ambiguous.csv"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert b"Outcome-word candidates" in configured.data
    assert b"Other small-set candidates" in configured.data
    assert b"Advanced choices (1)" in configured.data
    assert configured.data.index(b'value="approved"') < configured.data.index(
        b'value="risk_grade"'
    )
    assert configured.data.index(b'value="defaulted_90d"') < configured.data.index(
        b'value="risk_grade"'
    )
    assert b"Its name suggests an outcome" in configured.data
    assert b"small-outcome guidance limit" not in configured.data
    assert b"checked" not in configured.data


def test_advanced_target_requires_server_enforced_acknowledgement(tmp_path):
    app = create_app(tmp_path / "jobs", max_upload_mib=1)
    app.config.update(TESTING=True)
    client = app.test_client()
    token = _token(client)

    client.post(
        "/upload",
        data={
            "form_token": token,
            "dataset": (
                _csv_bytes({"customer_id": range(20), "label": [0, 1] * 10}),
                "advanced.csv",
            ),
        },
        content_type="multipart/form-data",
    )
    confirmation = client.post(
        "/configure",
        data={
            "form_token": token,
            "target": "customer_id",
            "dataset_name": "",
            "purpose": "",
        },
        follow_redirects=True,
    )
    assert b"Detected task: Multiclass classification" in confirmation.data
    assert b"Review this outcome choice" in confirmation.data
    assert b"20 distinct values across 20 labeled rows (100.0% distinct)" in confirmation.data
    assert b"I still want to use" in confirmation.data
    assert b"as the prediction outcome" in confirmation.data

    rejected = client.post(
        "/generate", data={"form_token": token}, follow_redirects=True
    )
    assert b"still want to use this advanced choice as the prediction outcome" in rejected.data
    assert client.get("/report").status_code == 404

    accepted = client.post(
        "/generate",
        data={"form_token": token, "advanced_target_ack": "confirmed"},
        follow_redirects=True,
    )
    assert b"Dataset reliability overview" in accepted.data
    assert client.get("/report").status_code == 200


def test_report_name_defaults_to_original_upload_filename(tmp_path):
    app = create_app(tmp_path / "jobs", max_upload_mib=1)
    app.config.update(TESTING=True)
    client = app.test_client()
    token = _token(client)

    client.post(
        "/upload",
        data={
            "form_token": token,
            "dataset": (_csv_bytes({"feature": [1, 2], "label": [0, 1]}), "Original Name.csv"),
        },
        content_type="multipart/form-data",
    )
    client.post(
        "/configure",
        data={"form_token": token, "target": "label", "dataset_name": "", "purpose": ""},
    )
    client.post("/generate", data={"form_token": token})

    report = client.get("/report")
    assert b"<h1>Original Name</h1>" in report.data
    assert b"<h1>dataset</h1>" not in report.data


def test_confirm_displays_automatically_detected_binary_task(tmp_path):
    app = create_app(tmp_path / "jobs", max_upload_mib=1)
    app.config.update(TESTING=True)
    client = app.test_client()
    token = _token(client)

    client.post(
        "/upload",
        data={
            "form_token": token,
            "dataset": (_csv_bytes({"feature": [1, 2, 3, 4], "label": [0, 1, 0, 1]}), "binary.csv"),
        },
        content_type="multipart/form-data",
    )
    confirmation = client.post(
        "/configure",
        data={"form_token": token, "target": "label", "dataset_name": "", "purpose": ""},
        follow_redirects=True,
    )

    assert b"Detected task: Binary classification" in confirmation.data
    assert b"2 observed target classes" in confirmation.data


def test_confirm_displays_single_class_with_singular_grammar(tmp_path):
    app = create_app(tmp_path / "jobs", max_upload_mib=1)
    app.config.update(TESTING=True)
    client = app.test_client()
    token = _token(client)
    client.post(
        "/upload",
        data={"form_token": token, "dataset": (_csv_bytes({"feature": [1, 2, 3], "label": [1, 1, 1]}), "single.csv")},
        content_type="multipart/form-data",
    )
    confirmation = client.post(
        "/configure",
        data={"form_token": token, "target": "label", "dataset_name": "", "purpose": ""},
        follow_redirects=True,
    )

    assert b"Detected task: Single-class classification" in confirmation.data
    assert b"Based on 1 observed target class." in confirmation.data
    assert b"class(es)" not in confirmation.data
