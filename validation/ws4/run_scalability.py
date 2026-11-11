"""WS4 scalability qualification: isolated, progressively escalated workloads with explicit caps.

Each workload runs in its own process. The parent polls the whole process tree (including M4 workers) and stops
it at the memory or time cap; a group escalates to its next size only when the previous size completed. Results
describe this machine only: no capacity guarantee, no extrapolation, no backend switching.

Usage:
  python validation/ws4/run_scalability.py --data DIR [--only GROUP ...]
Results: validation/ws4/results/<workload>.json and validation/ws4/results/summary.json
"""
import argparse
import functools
import json
import os
import platform
import resource
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "validation/ws4/results"
GIB = 1024 ** 3
MEMORY_CAP = 12 * GIB          # of 16 GiB on the qualification machine; the tree is stopped above this
DEFAULT_SECONDS = 1800         # an upper bound, not a target

# Frozen before any run. Sizes escalate within a group; the group stops at its first non-completion.
GROUPS = {
    "core_classification_tall": [{"rows": n, "cols": 10, "repeats": 3 if n == 1_000_000 else 1} for n in (1_000_000, 5_000_000, 10_000_000)],
    "core_unlabeled_tall_default_limits": [{"rows": n, "cols": 10} for n in (1_000_000, 5_000_000)],
    "core_classification_wide": [{"rows": 5000, "cols": c} for c in (200, 1000, 5000)],
    "core_classification_high_cardinality": [{"rows": 1_000_000}],
    "core_long_records": [{"variant": "megabyte_fields"}, {"variant": "embedded_newlines"}],
    "malformed_near_eof": [{"bytes": GIB, "path": "core"}, {"bytes": GIB, "path": "m4"}],
    "m4_advanced_tall": [{"rows": n} for n in (1_000_000, 5_000_000, 10_000_000)],
    "m4_long_record": [{"record_mib": 7}, {"record_mib": 9}],
    "m4_splits_identity": [{"rows": n} for n in (1_000_000, 5_000_000)],
    "m4_before_after_keys": [{"rows": n} for n in (1_000_000, 5_000_000)],
    "app_core_overhead": [{"rows": 1_000_000}, {"oversize_mib": 150}],
    # Added after the frozen run (post hoc, labelled as such): M4's 10M-row source limit refused the 1 GiB file before its
    # last record was reached, so M4's own discovery of a malformed final record is measured below that limit.
    "post_hoc_malformed_near_eof_m4_under_row_limit": [{"bytes": 380 * 1024 ** 2, "path": "m4"}],
}
# A refusal by a declared safeguard is a correct, completed outcome for these workloads.
REFUSAL_EXPECTED = {("core_unlabeled_tall_default_limits", 1), ("malformed_near_eof", 0), ("malformed_near_eof", 1), ("m4_long_record", 1), ("app_core_overhead", 1),
                    ("post_hoc_malformed_near_eof_m4_under_row_limit", 0)}


# ——— Data generation (deterministic; chunked so memory stays small) ———

def tall_csv(path, rows, cols=10, key=False, shift=0):
    import numpy as np
    if path.exists():
        return path
    rng = np.random.default_rng(1 + shift)
    tmp = path.with_suffix(".partial")
    with tmp.open("w") as f:
        names = (["id"] if key else []) + [f"n{i}" for i in range(cols - 4)] + ["c0", "c1", "c2", "y"]
        f.write(",".join(names) + "\n")
        for start in range(0, rows, 500_000):
            n = min(500_000, rows - start)
            parts = []
            if key:
                parts.append(np.char.add("k", np.arange(start + shift, start + shift + n).astype(str)))
            for _ in range(cols - 4):
                parts.append(np.round(rng.normal(size=n), 3).astype(str))
            for k in range(3):
                parts.append(rng.choice(np.array(list("abcdefgh")[: 3 + k * 2]), n))
            parts.append(rng.choice(np.array(["yes", "no"]), n, p=[0.12, 0.88]))
            f.write("\n".join(",".join(row) for row in zip(*parts)) + "\n")
    tmp.rename(path)
    return path


def wide_csv(path, rows, cols):
    import numpy as np
    if path.exists():
        return path
    rng = np.random.default_rng(2)
    import pandas as pd
    frame = pd.DataFrame(np.round(rng.normal(size=(rows, cols - 10)), 3), columns=[f"f{i}" for i in range(cols - 10)])
    for k in range(9):
        frame[f"k{k}"] = rng.choice(list("xyz"), rows)
    frame["y"] = rng.choice(["yes", "no"], rows)
    frame.to_csv(path, index=False)
    return path


def high_cardinality_csv(path, rows):
    import numpy as np
    if path.exists():
        return path
    rng = np.random.default_rng(3)
    with path.open("w") as f:
        f.write("id,note,category,amount,y\n")
        for start in range(0, rows, 250_000):
            n = min(250_000, rows - start)
            ids = np.char.add("u", np.arange(start, start + n).astype(str))
            notes = np.char.add("visit note ", rng.integers(0, 10**9, n).astype(str))
            cats = np.char.add("c", rng.integers(0, 100_000, n).astype(str))
            amounts = np.round(rng.lognormal(size=n), 2).astype(str)
            ys = rng.choice(np.array(["a", "b", "c"]), n)
            f.write("\n".join(",".join(r) for r in zip(ids, notes, cats, amounts, ys)) + "\n")
    return path


def long_csv(path, variant):
    if path.exists():
        return path
    with path.open("w") as f:
        f.write("id,text,amount,y\n")
        for i in range(5000 if variant == "megabyte_fields" else 200_000):
            if variant == "megabyte_fields":
                text = ("x" * 1_048_576) if i % 1000 == 0 else f"short {i}"
            else:
                text = f'"line one {i}\nline two\nline three"'
            f.write(f"{i},{text},{i % 97},{'yes' if i % 7 == 0 else 'no'}\n")
    return path


def malformed_csv(path, size):
    """About `size` bytes of valid records, then one record with a missing field at the very end."""
    if path.exists():
        return path
    row = "1234567,alpha,0.125,beta,gamma-delta,yes\n"
    with path.open("w") as f:
        f.write("id,a,b,c,d,y\n")
        block = row * 100_000
        written = 0
        while written < size:
            f.write(block); written += len(block)
        f.write("7654321,alpha,0.5,beta,yes\n")
    return path


def long_record_csv(path, mib):
    if path.exists():
        return path
    with path.open("w") as f:
        f.write("id,text,y\n")
        for i in range(2000):
            f.write(f"{i},{'z' * (mib * 1024 * 1024) if i == 1000 else 'short'},{'yes' if i % 5 else 'no'}\n")
    return path


# ——— The child: one workload, with stage timings ———

def instrument():
    import datatrust.contextual as ctx
    import datatrust.guidance as gd
    import datatrust.ingestion as ing
    stages = {}
    def wrap(module, name, label):
        f = getattr(module, name)
        @functools.wraps(f)
        def w(*a, **k):
            t = time.perf_counter()
            try:
                return f(*a, **k)
            finally:
                stages[label] = round(stages.get(label, 0) + time.perf_counter() - t, 3)
        setattr(module, name, w)
    wrap(ing, "source_digest", "ingest_digest"); wrap(ing, "validate_csv_structure", "ingest_structure_check"); wrap(ing, "read_csv", "ingest_parse")
    wrap(ctx, "build", "analysis_contextual"); wrap(gd, "build_guidance", "analysis_guidance")
    return stages


def exports(result, legacy, out_dir, pdf=True):
    from datatrust.renderer import write_report_artifacts
    record = {}
    t = time.perf_counter(); text = result.json_text(); record["serialise_json_s"] = round(time.perf_counter() - t, 3); record["json_bytes"] = len(text.encode())
    from datatrust.renderer import render_analysis_result
    t = time.perf_counter(); html = render_analysis_result(result); record["export_html_s"] = round(time.perf_counter() - t, 3); record["html_bytes"] = len(html.encode())
    if pdf:
        t = time.perf_counter()
        artifacts = write_report_artifacts(result, out_dir / "report.pdf", format="pdf", legacy_html=legacy)
        record["export_pdf_s"] = round(time.perf_counter() - t, 3)
        from pypdf import PdfReader
        record["pdf_pages"] = len(PdfReader(artifacts.pdf_path).pages); record["pdf_bytes"] = Path(artifacts.pdf_path).stat().st_size
    return record


REFUSAL_CLOCK = {}


def child(group, index, data):
    import warnings
    warnings.simplefilter("ignore")
    sys.path[:0] = [str(ROOT / "src")]
    from datatrust import (AnalysisConfig, ComparisonSpec, DataTrust, DatasetInput, DatasetSpec, ExecutionLimits, TaskSpec)
    from datatrust.contracts import AnalysisError
    params = GROUPS[group][index]
    record = {"group": group, "params": params}
    data = Path(data)
    out = Path(tempfile.mkdtemp(prefix="ws4-out-"))
    try:
        if group.startswith("core_") or group == "malformed_near_eof" and params["path"] == "core":
            stages = instrument()
            if group == "core_classification_tall":
                path, task, config = tall_csv(data / f"tall_{params['rows']}.csv", params["rows"]), TaskSpec("classification", target="y"), None
            elif group == "core_unlabeled_tall_default_limits":
                path, task, config = tall_csv(data / f"tall_{params['rows']}.csv", params["rows"]), TaskSpec("dataset_profile"), None
            elif group == "core_classification_wide":
                path, task, config = wide_csv(data / f"wide_{params['cols']}.csv", params["rows"], params["cols"]), TaskSpec("classification", target="y"), None
            elif group == "core_classification_high_cardinality":
                path, task, config = high_cardinality_csv(data / "highcard.csv", params["rows"]), TaskSpec("classification", target="y"), None
            elif group == "core_long_records":
                path, task, config = long_csv(data / f"long_{params['variant']}.csv", params["variant"]), TaskSpec("classification", target="y"), None
            else:
                path, task, config = malformed_csv(data / "malformed_1gib.csv", params["bytes"]), TaskSpec("classification", target="y"), None
            record["source_bytes"] = path.stat().st_size
            started = time.perf_counter(); REFUSAL_CLOCK["start"] = started
            result = DataTrust.from_spec(DatasetSpec(str(path)), task, config).analyze_result()
            record["analysis_s"] = round(time.perf_counter() - started, 3)
            record.update(stages=stages, execution={k: result.execution.get(k) for k in ("status", "analyzed_rows", "analyzed_columns", "frame_bytes", "backend")})
            record.update(exports(result, result.methodology_id == "classification_legacy_2026_08_13", out))
            record["dependency_search"] = {k: (result.contextual.get("dependency_search") or {}).get(k) for k in ("status",)}
            record["outcome"] = "completed"
        elif group == "app_core_overhead":
            record.update(app_overhead(params, data))
        else:
            record.update(m4_workload(group, params, data))
    except AnalysisError as exc:
        record.update(outcome="refused", code=exc.code, stage=exc.stage, message=str(exc)[:300])
        if "start" in REFUSAL_CLOCK:
            record["time_to_refusal_s"] = round(time.perf_counter() - REFUSAL_CLOCK["start"], 3)
    except ValueError as exc:
        record.update(outcome="refused", code="value_error", message=str(exc)[:300])
    except MemoryError:
        record.update(outcome="failed", code="memory_error", message="MemoryError raised inside the process.")
    record["child_max_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss  # bytes on macOS
    record["children_max_rss_bytes"] = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    return record


def m4_workload(group, params, data):
    from datatrust import ComparisonSpec, DatasetInput, DatasetSpec, TaskSpec
    from datatrust.m4_worker import analyze_scalable, compare
    task = TaskSpec("classification", targets=("y",))
    started = time.perf_counter()
    if group == "m4_advanced_tall":
        path = tall_csv(data / f"tall_{params['rows']}.csv", params["rows"])
        from datatrust.contracts import AnalysisConfig as AC
        from datatrust.m4_contracts import AdvancedTabularOptions, ExecutionOptions
        result = analyze_scalable(DatasetSpec(str(path)), task, AC(execution=ExecutionOptions(), advanced=AdvancedTabularOptions()))
        source_bytes = path.stat().st_size
    elif group in {"malformed_near_eof", "post_hoc_malformed_near_eof_m4_under_row_limit"}:
        path = malformed_csv(data / ("malformed_1gib.csv" if group == "malformed_near_eof" else "malformed_380mib.csv"), params["bytes"])
        from datatrust.contracts import AnalysisConfig as AC
        from datatrust.m4_contracts import AdvancedTabularOptions, ExecutionOptions
        source_bytes = path.stat().st_size
        REFUSAL_CLOCK["start"] = time.perf_counter()
        result = analyze_scalable(DatasetSpec(str(path)), task, AC(execution=ExecutionOptions(), advanced=AdvancedTabularOptions()))
    elif group == "m4_long_record":
        path = long_record_csv(data / f"long_record_{params['record_mib']}.csv", params["record_mib"])
        from datatrust.contracts import AnalysisConfig as AC
        from datatrust.m4_contracts import AdvancedTabularOptions, ExecutionOptions
        source_bytes = path.stat().st_size
        result = analyze_scalable(DatasetSpec(str(path)), TaskSpec("dataset_profile"), AC(execution=ExecutionOptions(), advanced=AdvancedTabularOptions()))
    else:
        rows = params["rows"]
        before = tall_csv(data / f"keyed_{rows}_a.csv", rows, key=True)
        after = tall_csv(data / f"keyed_{rows}_b.csv", rows, key=True, shift=rows // 10)
        source_bytes = before.stat().st_size + after.stat().st_size
        if group == "m4_splits_identity":
            spec = ComparisonSpec("splits", (DatasetInput("train", "train", DatasetSpec(str(before)), task), DatasetInput("test", "test", DatasetSpec(str(after)), task)),
                                  identity_keys=(("id",),), evaluation_intent="entity_disjoint")
        else:
            spec = ComparisonSpec("versions", (DatasetInput("before", "reference", DatasetSpec(str(before)), task), DatasetInput("after", "current", DatasetSpec(str(after)), task)),
                                  identity_keys=(("id",),), preset="before_after", transformations=({"kind": "filter", "description": "rolling window"},))
        result = compare(spec)
    record = {"outcome": "completed", "analysis_s": round(time.perf_counter() - started, 3), "source_bytes": source_bytes,
              "execution": {k: result.execution.get(k) for k in ("status", "duration_seconds", "peak_worker_rss_bytes", "peak_workspace_bytes", "peak_spill_bytes", "serialized_bytes")}}
    out = Path(tempfile.mkdtemp(prefix="ws4-m4-"))
    record.update(exports(result, False, out, pdf=True))
    if group == "m4_before_after_keys":
        m = next(v for k, v in result.coverage["measurements"].items() if k.endswith(".before_after"))
        record["reconciles"] = m["observed"]["rows"]["explained"]
    return record


def app_overhead(params, data):
    import io
    from datatrust.history import History
    from datatrust.web import create_app
    API = "/api/datatrust/v1"
    work = Path(tempfile.mkdtemp(prefix="ws4-app-"))
    app = create_app(work / "ui", history=History(work / "history"), launch_token="t"); app.testing = True
    c = app.test_client(); c.get("/app/?launch=t")
    h = {"X-CSRF-Token": c.get(f"{API}/session").json["data"]["csrf_token"]}
    c.post(f"{API}/history/choice", json={"saving": "on"}, headers=h)
    record = {}
    if "oversize_mib" in params:
        blob = b"a,b\n" + b"1,2\n" * (params["oversize_mib"] * 1024 * 1024 // 4)
        t = time.perf_counter()
        r = c.post(f"{API}/core/jobs", data={"mode": "classification", "dataset": (io.BytesIO(blob), "big.csv")}, headers=h, content_type="multipart/form-data")
        record.update(outcome="refused" if r.status_code == 413 else "completed", status_code=r.status_code, refusal_s=round(time.perf_counter() - t, 3), code="upload_limit")
        return record
    path = tall_csv(data / f"tall_{params['rows']}.csv", params["rows"])
    timings = {}
    t = time.perf_counter()
    r = c.post(f"{API}/core/jobs", data={"mode": "classification", "dataset": (path.open("rb"), "tall.csv")}, headers=h, content_type="multipart/form-data")
    timings["upload_and_inspect_s"] = round(time.perf_counter() - t, 3)
    t = time.perf_counter(); c.get(f"{API}/core/job/context"); timings["context_suggestions_s"] = round(time.perf_counter() - t, 3)
    t = time.perf_counter(); c.post(f"{API}/core/job/configure", json={"target": "y", "dataset_name": "Tall"}, headers=h); timings["configure_s"] = round(time.perf_counter() - t, 3)
    t = time.perf_counter(); g = c.post(f"{API}/core/job/generate", json={}, headers=h); timings["generate_and_save_s"] = round(time.perf_counter() - t, 3)
    t = time.perf_counter(); c.get(f"{API}/core/job/download/pdf"); timings["pdf_on_demand_s"] = round(time.perf_counter() - t, 3)
    record.update(outcome="completed" if g.status_code == 200 and r.status_code == 201 else "failed", upload_status=r.status_code, generate_status=g.status_code,
                  saved=(g.json or {}).get("data", {}).get("history", {}).get("saved"), timings=timings, source_bytes=path.stat().st_size)
    app.extensions["datatrust_job_store"].cleanup(); app.extensions["confidenceguard_store"].cleanup()
    return record


# ——— The parent: isolation, caps, escalation ———

def tree_rss(proc):
    import psutil
    try:
        procs = [proc] + proc.children(recursive=True)
    except psutil.NoSuchProcess:
        return 0
    total = 0
    for p in procs:
        try:
            total += p.memory_info().rss
        except psutil.Error:
            pass
    return total


def run_one(group, index, data, seconds):
    import psutil
    out = Path(tempfile.mkstemp(prefix="ws4-", suffix=".json")[1])
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    started = time.monotonic()
    p = subprocess.Popen([sys.executable, "-B", __file__, "--child", group, str(index), "--data", str(data), "--out", str(out)], env=env, cwd=ROOT,
                         stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    proc = psutil.Process(p.pid); peak = 0; stopped = None
    while p.poll() is None:
        peak = max(peak, tree_rss(proc))
        if peak > MEMORY_CAP:
            stopped = "memory_cap"
        elif time.monotonic() - started > seconds:
            stopped = "time_cap"
        if stopped:
            for q in [proc] + proc.children(recursive=True):
                try:
                    q.kill()
                except psutil.Error:
                    pass
            break
        time.sleep(0.25)
    p.wait()
    elapsed = round(time.monotonic() - started, 2)
    stderr = p.stderr.read().decode(errors="replace")[-2000:] if p.stderr else ""
    if stopped:
        record = {"group": group, "params": GROUPS[group][index], "outcome": f"stopped_at_{stopped}"}
    else:
        try:
            record = json.loads(out.read_text())
        except (OSError, ValueError):
            record = {"group": group, "params": GROUPS[group][index], "outcome": "crashed", "exit_code": p.returncode, "stderr_tail": stderr}
    out.unlink(missing_ok=True)
    record.update(wall_s=elapsed, peak_tree_rss_bytes=peak, caps={"memory_bytes": MEMORY_CAP, "seconds": seconds})
    return record


def environment():
    import duckdb, pandas, psutil, weasyprint
    return {"python": platform.python_version(), "platform": platform.platform(), "machine": platform.machine(), "cpus": os.cpu_count(),
            "physical_memory": psutil.virtual_memory().total, "pandas": pandas.__version__, "duckdb": duckdb.__version__, "weasyprint": weasyprint.__version__,
            "capacity_guarantee": False}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True); ap.add_argument("--only", nargs="*"); ap.add_argument("--child", nargs=2); ap.add_argument("--out")
    a = ap.parse_args()
    if a.child:
        record = child(a.child[0], int(a.child[1]), a.data)
        Path(a.out).write_text(json.dumps(record, default=str))
        return 0
    Path(a.data).mkdir(parents=True, exist_ok=True); RESULTS.mkdir(parents=True, exist_ok=True)
    summary_path = RESULTS / "summary.json"
    summary = json.loads(summary_path.read_text()) if summary_path.exists() else {"environment": environment(), "groups": {}}
    summary["environment"] = environment()
    for group, sizes in GROUPS.items():
        if a.only and group not in a.only:
            continue
        runs = []
        for index, params in enumerate(sizes):
            repeats = params.get("repeats", 1)
            attempts = [run_one(group, index, a.data, DEFAULT_SECONDS) for _ in range(repeats)]
            record = attempts[0]
            if repeats > 1:
                walls = sorted(x["wall_s"] for x in attempts)
                record = {**sorted(attempts, key=lambda x: x["wall_s"])[repeats // 2], "repeats": repeats, "wall_s_all": walls}
            expected_refusal = (group, index) in REFUSAL_EXPECTED
            record["expected_refusal"] = expected_refusal
            runs.append(record)
            (RESULTS / f"{group}-{index}.json").write_text(json.dumps(record, indent=2, default=str) + "\n")
            print(group, index, record.get("outcome"), record.get("code", ""), record.get("wall_s"), f"{record.get('peak_tree_rss_bytes', 0) / GIB:.2f} GiB", flush=True)
            if record.get("outcome") != "completed" and not expected_refusal:
                print(f"  early stop: {group} does not escalate past {params}", flush=True)
                break
        summary["groups"][group] = runs
        summary_path.write_text(json.dumps(summary, indent=2, default=str) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
