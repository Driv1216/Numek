"""Run the frozen WS3 benchmark (validation/ws3/benchmark.json) and write validation/ws3/results/.

Cases are generated deterministically from the base datasets. Expected outcomes were fixed before evaluation. Numeric
checks use independent pandas calculations, never the DataTrust reducers under test. Results report detections,
misses, false flags, abstentions and oracle agreement separately; nothing unassessed counts as a correct negative.

Usage: python validation/ws3/run_benchmark.py
"""
import hashlib
import json
import sys
import tempfile
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def frame(name, bases):
    import pandas as pd
    return pd.read_csv(ROOT / bases[name])


def mutate(case, df):
    import numpy as np
    rng = np.random.default_rng(7)
    op, a, t = case["op"], case["args"], case["target"]
    df = df.copy()
    if op in {"copy_target", "head_with_copy"}:
        if op == "head_with_copy":
            df = df.head(a["rows"]).copy()
        df[a["name"]] = df[t]
    elif op == "encode_target":
        df[a["name"]] = (df[t].astype(str) == a["positive"]).astype(int)
    elif op == "proxy_categories":
        df[a["name"]] = df[t].astype(str) + "_" + (np.arange(len(df)) % a["splits"]).astype(str)
    elif op == "separator":
        positive = df[t].astype(str) == a["positive"]
        df[a["name"]] = np.where(positive, rng.uniform(50, 100, len(df)), rng.uniform(0, 49, len(df))).round(3)
    elif op == "noisy_copy":
        values = df[t].astype(str).to_numpy().copy()
        classes = sorted(set(values))
        flip = rng.random(len(values)) < a["noise"]
        values[flip] = [classes[1] if v == classes[0] else classes[0] for v in values[flip]]
        df[a["name"]] = values
    elif op == "independent_categories":
        df[a["name"]] = rng.choice(["ok", "late", "closed"], len(df))
    elif op == "row_identifier":
        df[a["name"]] = ["C" + str(i) for i in range(len(df))]
    elif op == "inside_range_code":
        values = rng.integers(-5, 6, len(df))
        values[rng.random(len(df)) < 0.2] = a["code"]
        df[a["name"]] = values
    elif op == "outside_code":
        values = rng.integers(1, 120, len(df))
        values[: max(1, int(round(a["share"] * len(df))))] = a["code"]
        df[a["name"]] = values
    return df


def before_after_frames(case, bases):
    import pandas as pd
    op, a = case["op"], case["args"]
    if case["family"] == "german":
        before = frame("german", bases)
        before.insert(0, "id", range(len(before)))
        before.loc[before.index % 50 == 0, "age"] = None
    else:
        before = frame("bank", bases).head(a.get("rows", 5000)).copy()
    if op == "ba_filter_drop_impute":
        after = before[before.credit_amount < 10000].drop(columns=["telephone"]).copy()
        after["age"] = after["age"].fillna(after["age"].median())
    elif op == "ba_dedup":
        before = pd.concat([before, before.sample(a["duplicates"], random_state=7)], ignore_index=True)
        after = before.drop_duplicates()
    elif op == "ba_drop_column":
        after = before.drop(columns=[a["column"]])
    elif op == "ba_partial_impute":
        after = before.copy()
        missing = after.index[after[a["column"]].isna()]
        after.loc[missing[: len(missing) // 2], a["column"]] = after[a["column"]].median()
    elif op == "ba_one_hot":
        after = pd.get_dummies(before, columns=[a["column"]], prefix=a["column"], dtype=int)
    else:
        after = before.copy()
    return before, after


def run_core(case, df, tmp):
    from datatrust import AnalysisConfig, DataTrust, DatasetSpec, TaskSpec
    path = tmp / f"{case['id']}.csv"
    df.to_csv(path, index=False)
    config = AnalysisConfig(context=case["context"]) if case.get("context") else None
    return DataTrust.from_spec(DatasetSpec(str(path)), TaskSpec("classification", target=case["target"]), config).analyze_result().to_dict()["contextual"]


def oracle_declaration(case, df, ctx):
    import pandas as pd
    if case["expected"]["oracle"] == "pdays_applicable":
        applicable = (df.previous > 0) & (df.pdays != -1) & df.pdays.notna()
        values = df.pdays[applicable].astype(float)
        q1, q3 = values.quantile(0.25), values.quantile(0.75)
        outside = int(((values < q1 - 1.5 * (q3 - q1)) | (values > q3 + 1.5 * (q3 - q1))).sum())
        present = int(((df.previous <= 0) & (df.pdays != -1)).sum())
        absent = int(((df.previous > 0) & (df.pdays == -1)).sum())
        got = ctx["interpreted"]["pdays"]
        ex = got["condition"]["exceptions"]
        expected = {"applicable_rows": int(applicable.sum()), "outside": outside, "present": present, "absent": absent}
        observed = {"applicable_rows": got["applicable_rows"], "outside": got["applicable_numeric"]["outlier_count"],
                    "present": ex["value_present_where_declared_not_to_apply"], "absent": ex["not_applicable_code_where_condition_holds"]}
    else:
        column = "previous_campaign_outcome"
        expected = {"absent": int(((df.previous > 0) & (df[column].astype(str) == "unknown")).sum()),
                    "present": int(((df.previous <= 0) & (df[column].astype(str) != "unknown") & df[column].notna()).sum())}
        ex = ctx["interpreted"][column]["condition"]["exceptions"]
        observed = {"absent": ex["not_applicable_code_where_condition_holds"], "present": ex["value_present_where_declared_not_to_apply"]}
    return expected, observed


def oracle_before_after(case, before, after, measurement):
    target = case["target"]
    rows = measurement["observed"]["rows"]
    cb, ca = before[target].astype(str).value_counts(), after[target].astype(str).value_counts()
    expected = {"difference": len(after) - len(before), "by_class": {k: int(ca.get(k, 0) - cb.get(k, 0)) for k in set(cb.index) | set(ca.index)}}
    observed = {"difference": rows["difference"], "by_class": rows.get("by_class_difference")}
    if case["expected"].get("oracle") == "lineage":
        dropped = before[~before.id.isin(after.id)]
        expected.update(dropped=len(dropped), added=int((~after.id.isin(before.id)).sum()), dropped_by_class=dropped[target].astype(str).value_counts().to_dict(), explained=True)
        lin = measurement["lineage"]
        observed.update(dropped=lin["identities"]["dropped"], added=lin["identities"]["added"], dropped_by_class=lin["by_class"]["dropped"], explained=rows["explained"])
    elif case["expected"].get("oracle") == "aggregate":
        expected["explained"] = None
        observed["explained"] = rows["explained"]
    return expected, observed


def run_before_after(case, bases, tmp):
    from datatrust import ComparisonSpec, DatasetInput, DatasetSpec, TaskSpec
    from datatrust.m4_worker import compare
    before, after = before_after_frames(case, bases)
    paths = [tmp / f"{case['id']}-{n}.csv" for n in ("before", "after")]
    before.to_csv(paths[0], index=False); after.to_csv(paths[1], index=False)
    task = TaskSpec("classification", case["target"])
    spec = ComparisonSpec("versions", (DatasetInput("source1", "reference", DatasetSpec(str(paths[0])), task), DatasetInput("source2", "current", DatasetSpec(str(paths[1])), task)),
                          identity_keys=(("id",),) if case["args"].get("keys") else (), preset="before_after", transformations=tuple(case.get("transformations", ())))
    result = compare(spec)
    measurement = next(v for k, v in result.coverage["measurements"].items() if k.endswith(".before_after"))
    titles = {f["title"] for f in result.findings if f.get("scope") == "source1:source2"}
    return before, after, measurement, titles


def evaluate(case, bases, tmp):
    kind, expected = case["kind"], case["expected"]
    record = {"id": case["id"], "family": case["family"], "kind": kind, "class": case["class"], "expected": expected}
    if kind == "before_after":
        before, after, measurement, titles = run_before_after(case, bases, tmp)
        checks = []
        if expected.get("oracle"):
            want, got = oracle_before_after(case, before, after, measurement)
            record["oracle"] = {"expected": want, "observed": got}
            checks.append(want == got)
        checks += [t in titles for t in expected.get("titles", [])] + [t not in titles for t in expected.get("titles_absent", [])]
        if "encodings" in expected:
            found = [x["column"] for x in measurement["observed"]["observed_encoding_patterns"]]
            checks.append(set(expected["encodings"]) <= set(found))
        record["observed"] = {"titles": sorted(titles)}
        record["passed"] = all(checks)
        record["outcome"] = "agrees" if record["passed"] else "disagrees"
        return record
    df = mutate(case, frame(case["family"], bases))
    ctx = run_core(case, df, tmp)
    codes = [f["code"] for f in ctx["findings"]]
    search = ctx.get("dependency_search", {})
    record["observed"] = {"flagged": search.get("flagged", []), "status": search.get("status"), "unsearched": len(search.get("unsearched_features", [])), "codes": codes}
    checks = []
    if kind == "dependency":
        if "status" in expected:
            checks.append(search.get("status") == expected["status"])
            record["outcome"] = "abstained" if search.get("status") == "not_assessable" else "assessed"
        else:
            flagged = set(search.get("flagged", []))
            want = set(expected["flagged"])
            checks.append(flagged == want)
            if case["class"] in {"positive", "expected_miss"}:
                record["outcome"] = "detected" if flagged & {case["args"]["name"]} else "missed"
            else:
                record["outcome"] = "clean" if not flagged else "false_flag"
    elif kind == "availability":
        checks += [c in codes for c in expected.get("codes", [])] + [c not in codes for c in expected.get("absent_codes", [])]
        if "columns" in expected:
            checks.append(any(set(expected["columns"]) <= set(f["columns"]) for f in ctx["findings"] if f["code"] in expected["codes"]))
        record["outcome"] = "agrees" if all(checks) else "disagrees"
    elif kind == "candidates":
        found = {(c["column"], c["value"]) for c in ctx["candidates"]}
        columns = {c["column"] for c in ctx["candidates"]}
        checks += [tuple(x) in found for x in expected.get("candidates", [])] + [c not in columns for c in expected.get("no_candidate_columns", [])]
        record["observed"]["candidates"] = sorted([list(x) for x in found], key=str)
        record["outcome"] = ("abstained" if case["class"] == "abstention" else "agrees") if all(checks) else "disagrees"
    elif kind == "declaration":
        if expected.get("oracle"):
            want, got = oracle_declaration(case, df, ctx)
            record["oracle"] = {"expected": want, "observed": got}
            checks.append(want == got)
        checks += [c in codes for c in expected.get("codes", [])]
        record["outcome"] = "agrees" if all(checks) else "disagrees"
    record["passed"] = all(checks)
    return record


def summarise(records):
    by = lambda outcome, cls=None: [r["id"] for r in records if r.get("outcome") == outcome and (cls is None or r["class"] == cls)]
    dep = [r for r in records if r["kind"] == "dependency"]
    positives = [r for r in dep if r["class"] == "positive"]
    negatives = [r for r in dep if r["class"] == "negative"]
    return {
        "cases": len(records), "passed": sum(r["passed"] for r in records), "failed": [r["id"] for r in records if not r["passed"]],
        "dependency": {"positives": len(positives), "detected": by("detected", "positive"), "missed": by("missed", "positive"),
                       "negatives": len(negatives), "false_flags": by("false_flag", "negative"), "clean": by("clean", "negative"),
                       "expected_misses": {r["id"]: r["outcome"] for r in dep if r["class"] == "expected_miss"},
                       "abstained": by("abstained"), "unsearched_features_total": sum(r["observed"].get("unsearched", 0) for r in dep)},
        "families": sorted({r["family"] for r in records}),
        "note": "Families are mutations of three base datasets; they are not independent samples. Results establish behaviour on these "
                "constructed cases only, not external validity.",
    }


def main():
    warnings.simplefilter("ignore")
    sys.path[:0] = [str(ROOT / "src")]
    definition = ROOT / "validation/ws3/benchmark.json"
    spec = json.loads(definition.read_text())
    out = ROOT / "validation/ws3/results"
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        records = [evaluate(case, spec["bases"], Path(tmp)) for case in spec["cases"]]
    result = {"benchmark": spec["benchmark"], "definition_sha256": hashlib.sha256(definition.read_bytes()).hexdigest(), "summary": summarise(records), "cases": records}
    (out / "results.json").write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str) + "\n")
    s = result["summary"]; d = s["dependency"]
    lines = [f"# WS3 benchmark results ({spec['benchmark']})", "", f"Definition sha256 `{result['definition_sha256']}`, frozen before evaluation.", "",
             f"- Cases: {s['cases']}; agreeing with their frozen expectation: {s['passed']}; disagreeing: {', '.join(s['failed']) or 'none'}.",
             f"- Dependency search, positives: {len(d['detected'])} of {d['positives']} detected; missed: {', '.join(d['missed']) or 'none'}.",
             f"- Dependency search, negatives: {len(d['false_flags'])} false flags of {d['negatives']}; {', '.join(d['false_flags']) or 'none'}.",
             f"- Expected misses (true leaks the gates cannot detect): " + ", ".join(f"{k} {v}" for k, v in d["expected_misses"].items()) + ".",
             f"- Abstentions: {', '.join(d['abstained']) or 'none'}. Unsearched features across dependency cases: {d['unsearched_features_total']}.",
             "", s["note"], "", "| Case | Family | Kind | Class | Outcome | Agrees |", "|---|---|---|---|---|---|"]
    lines += [f"| {r['id']} | {r['family']} | {r['kind']} | {r['class']} | {r.get('outcome')} | {'yes' if r['passed'] else 'no'} |" for r in records]
    (out / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:9]))
    return 0 if s["passed"] == s["cases"] else 1


if __name__ == "__main__":
    sys.exit(main())
