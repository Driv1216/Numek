from io import BytesIO

import pandas as pd
from click.testing import CliRunner

from datatrust.cli import main
from datatrust.web import create_app


def _token(client):
    client.get("/")
    with client.session_transaction() as state:
        return state["form_token"]


def _csv_bytes(data: dict) -> BytesIO:
    return BytesIO(pd.DataFrame(data).to_csv(index=False).encode("utf-8"))


def test_complete_local_ui_flow_download_and_cleanup(tmp_path):
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
    assert b"Detected binary classification" in configured.data

    generated = client.post(
        "/generate", data={"form_token": token}, follow_redirects=True
    )
    assert generated.status_code == 200
    assert b"Report ready" in generated.data
    assert b"Print / Save as PDF" in generated.data

    report = client.get("/report")
    assert report.status_code == 200
    assert b"2. Prioritized Action Plan" in report.data
    assert b"&lt;b&gt;Demo&lt;/b&gt;" in report.data
    assert b"Source: demo.csv" in report.data
    assert str(tmp_path).encode() not in report.data

    download = client.get("/download")
    assert download.status_code == 200
    assert "attachment" in download.headers["Content-Disposition"]
    assert download.headers["Content-Disposition"].endswith("-reliability-report.html")
    assert "<" not in download.headers["Content-Disposition"]

    with client.session_transaction() as state:
        job_id = state["job_id"]
    store = app.extensions["datatrust_job_store"]
    job_directory = store.get(job_id)["directory"]
    assert job_directory.exists()

    response = client.post("/new", data={"form_token": token}, follow_redirects=True)
    assert b"Generate a reliability report" in response.data
    assert not job_directory.exists()


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
