"""Before/after preprocessing assessment (M4 versions preset "before_after").

Four kinds of statement are kept apart:
  declared    the transformations you list; DataTrust never performs one
  observed    what differs between the two files: counts, schema, missingness, target coverage, remaining risks
  lineage     record-level retention, only when identity keys make it verifiable
  pipeline    actual model or pipeline use, which DataTrust never observes and never infers
Counts always reconcile arithmetically; without identity keys the record-level explanation is stated as unavailable.
Fewer findings or a higher score afterwards does not establish improvement.
"""
from __future__ import annotations

from datatrust.m4_diagnostics import NUMERIC

ROW_KINDS = {"drop_rows", "filter", "deduplicate", "resample"}
SHARE_REVIEW_POINTS = 2.0
NOT_IMPROVEMENT = ("Fewer findings or a higher score after preprocessing does not establish improvement; this assessment shows what "
                   "changed in the data. No model performance is measured and no transformation was performed.")


def _q(con, sql, params=()):
    return con.execute(sql, params).fetchall()


def _missing(con, r, column):
    c = r.col(column)
    nonfinite = f"count(*) FILTER (WHERE {c} IS NOT NULL AND NOT isfinite({c}))" if r.types[column] in NUMERIC else "0"
    missing, bad = _q(con, f"SELECT count(*) FILTER (WHERE {c} IS NULL), {nonfinite} FROM {r.table}")[0]
    return int(missing), int(bad)


def _classes(con, r, column):
    c = r.col(column)
    rows = _q(con, f"SELECT CAST({c} AS VARCHAR) v, count(*) n FROM {r.table} WHERE {c} IS NOT NULL GROUP BY 1 ORDER BY 2 DESC, 1")
    return {str(v): int(n) for v, n in rows}


def _key(r, logical):
    cols = [r.alignment[l] for l in logical]
    expression = " || chr(31) || ".join(f"CAST({r.col(c)} AS VARCHAR)" for c in cols)
    complete = " AND ".join(f"{r.col(c)} IS NOT NULL" for c in cols)
    return expression, complete


def _lineage(con, before, after, key, target):
    kb, cb = _key(before, key)
    ka, ca = _key(after, key)
    tb = f", CAST({before.col(before.alignment[target])} AS VARCHAR)" if target else ", NULL"
    ta = f", CAST({after.col(after.alignment[target])} AS VARCHAR)" if target else ", NULL"
    con.execute(f"CREATE OR REPLACE TEMP TABLE ba_before AS SELECT {kb} k{tb} t FROM {before.table} WHERE {cb}")
    con.execute(f"CREATE OR REPLACE TEMP TABLE ba_after AS SELECT {ka} k{ta} t FROM {after.table} WHERE {ca}")
    stats = {}
    for name in ("before", "after"):
        _, distinct, dup_rows = _q(con, f"SELECT count(*), count(DISTINCT k), coalesce(sum(n) FILTER (WHERE n > 1), 0) FROM (SELECT k, count(*) n FROM ba_{name} GROUP BY k)")[0]
        stats[name] = {"rows_with_complete_key": int(_q(con, f"SELECT count(*) FROM ba_{name}")[0][0]), "distinct_identities": int(distinct), "rows_in_repeated_identities": int(dup_rows)}
    retained, dropped, added = (int(_q(con, sql)[0][0]) for sql in (
        "SELECT count(*) FROM (SELECT DISTINCT k FROM ba_before) b WHERE k IN (SELECT k FROM ba_after)",
        "SELECT count(*) FROM (SELECT DISTINCT k FROM ba_before) b WHERE k NOT IN (SELECT k FROM ba_after)",
        "SELECT count(*) FROM (SELECT DISTINCT k FROM ba_after) a WHERE k NOT IN (SELECT k FROM ba_before)"))
    record = {"key": list(key), "before": stats["before"], "after": stats["after"],
              "identities": {"retained": retained, "dropped": dropped, "added": added},
              "identity_reconciliation": f"{stats['before']['distinct_identities']} − {dropped} + {added} = {stats['after']['distinct_identities']}",
              "identity_reconciles": stats["before"]["distinct_identities"] - dropped + added == stats["after"]["distinct_identities"]}
    unique = not stats["before"]["rows_in_repeated_identities"] and not stats["after"]["rows_in_repeated_identities"]
    complete = stats["before"]["rows_with_complete_key"] == before.rows and stats["after"]["rows_with_complete_key"] == after.rows
    record["row_level"] = unique and complete
    record["row_level_reason"] = None if record["row_level"] else (
        "Some identities repeat within a file, so rows are not one-to-one with identities." if not unique else "Some rows have incomplete keys and cannot be traced.")
    if target and record["row_level"]:
        by = lambda sql: {str(v): int(n) for v, n in _q(con, sql)}
        record["by_class"] = {
            "dropped": by("SELECT coalesce(t, '(missing)'), count(*) FROM ba_before WHERE k NOT IN (SELECT k FROM ba_after) GROUP BY 1 ORDER BY 1"),
            "added": by("SELECT coalesce(t, '(missing)'), count(*) FROM ba_after WHERE k NOT IN (SELECT k FROM ba_before) GROUP BY 1 ORDER BY 1"),
            "label_changed": int(_q(con, "SELECT count(*) FROM ba_before b JOIN ba_after a USING (k) WHERE b.t IS DISTINCT FROM a.t")[0][0]),
        }
    con.execute("DROP TABLE IF EXISTS ba_before"); con.execute("DROP TABLE IF EXISTS ba_after")
    return record


def assess(e, spec, relations):
    """Measure the before/after differences and record them as evidence and findings. Returns the measurement."""
    before = next(r for r in relations if r.role == "reference")
    after = next(r for r in relations if r.role == "current")
    con = e.work.con
    ab, aa = before.alignment, after.alignment
    scope = f"{before.id}:{after.id}"
    declared = [{"kind": t.kind, "columns": list(t.columns), "outputs": list(t.outputs), "description": t.description} for t in spec.transformations]

    added = sorted(set(aa) - set(ab)); removed = sorted(set(ab) - set(aa))
    retyped = sorted(l for l in set(ab) & set(aa) if before.types[ab[l]] != after.types[aa[l]])
    covers = lambda kinds, column, field="columns": any(t.kind in kinds and column in getattr(t, field) for t in spec.transformations)
    undeclared = ([{"change": "removed", "column": c} for c in removed if not covers({"drop_columns", "encode", "rename"}, c)]
                  + [{"change": "added", "column": c} for c in added if not covers({"encode", "rename", "transform", "other"}, c, "outputs")]
                  + [{"change": "retyped", "column": c} for c in retyped if not covers({"transform", "encode", "impute", "cap", "other"}, c)])
    # An observed encoding pattern: a removed column whose name prefixes several added columns.
    encodings = [{"column": c, "outputs": [x for x in added if x.startswith(c + "_") or x.startswith(c + "=")]} for c in removed]
    encodings = [x for x in encodings if len(x["outputs"]) >= 2]

    missingness = []
    for logical in sorted(set(ab) & set(aa)):
        mb, nb = _missing(con, before, ab[logical]); ma, na = _missing(con, after, aa[logical])
        if mb or ma or nb or na:
            missingness.append({"column": logical, "before_missing": mb, "after_missing": ma, "before_non_finite": nb, "after_non_finite": na})
    imputed = [{"column": c, "still_missing": next((m["after_missing"] for m in missingness if m["column"] == c), 0)}
               for t in spec.transformations if t.kind == "impute" for c in t.columns if c in aa]

    targets = [t for t in before.task.target_names if t in ab and t in aa]
    target = targets[0] if targets else None
    coverage = None
    if target:
        cb, ca = _classes(con, before, ab[target]), _classes(con, after, aa[target])
        mb, _ = _missing(con, before, ab[target]); ma, _ = _missing(con, after, aa[target])
        share = lambda counts, k: round(100 * counts.get(k, 0) / sum(counts.values()), 2) if counts else 0.0
        labels = sorted(set(cb) | set(ca), key=lambda k: (-cb.get(k, 0), k))[:20]
        coverage = {"target": target, "before_missing": mb, "after_missing": ma,
                    "classes": [{"class": k, "before": cb.get(k, 0), "after": ca.get(k, 0), "before_share": share(cb, k), "after_share": share(ca, k),
                                 "share_change_points": round(share(ca, k) - share(cb, k), 2)} for k in labels],
                    "classes_omitted": max(0, len(set(cb) | set(ca)) - len(labels))}

    key = next((k for k in spec.identity_keys if set(k) <= set(ab) & set(aa)), None)
    lineage = _lineage(con, before, after, key, target) if key else None
    rows = {"before": before.rows, "after": after.rows, "difference": after.rows - before.rows,
            "reconciliation": f"{before.rows} {'+' if after.rows >= before.rows else '−'} {abs(after.rows - before.rows)} = {after.rows}"}
    if lineage and lineage["row_level"]:
        rows["explained"] = before.rows - lineage["identities"]["dropped"] + lineage["identities"]["added"] == after.rows
        rows["explanation"] = f"{before.rows} − {lineage['identities']['dropped']} dropped + {lineage['identities']['added']} added = {after.rows}"
    else:
        rows["explained"] = None
        rows["explanation"] = ("Record-level lineage requires identity keys that are complete and unique in both files; only aggregate counts are compared."
                               if not lineage else lineage["row_level_reason"])
    if coverage:
        rows["by_class_difference"] = {c["class"]: c["after"] - c["before"] for c in coverage["classes"]}
        rows["missing_target_difference"] = coverage["after_missing"] - coverage["before_missing"]

    not_observed = []
    for t in spec.transformations:
        if t.kind == "drop_columns" and set(t.columns) & set(aa):
            not_observed.append({"kind": t.kind, "columns": sorted(set(t.columns) & set(aa)), "reason": "still present after"})
        elif t.kind in ROW_KINDS and t.kind != "resample" and after.rows >= before.rows:
            not_observed.append({"kind": t.kind, "columns": list(t.columns), "reason": "the row count did not fall"})
        elif t.kind == "impute":
            for c in t.columns:
                m = next((x for x in missingness if x["column"] == c), None)
                if c not in aa or (m and m["before_missing"] and m["after_missing"] >= m["before_missing"]):
                    not_observed.append({"kind": t.kind, "columns": [c], "reason": "absent after" if c not in aa else "missing values did not fall"})
        elif t.kind in {"rename", "encode"} and t.outputs and not set(t.outputs) & set(aa):
            not_observed.append({"kind": t.kind, "columns": list(t.columns), "reason": "declared outputs are absent after"})

    titles = lambda scope_id: {f["title"] for f in e.findings if f.get("scope") == scope_id}
    tb, ta = titles(before.id), titles(after.id)
    risks = {"still_present": sorted(tb & ta), "new": sorted(ta - tb), "no_longer_flagged": sorted(tb - ta),
             "meaning": "Findings are compared by kind on each file; a finding no longer flagged may reflect lost rows or columns rather than repair."}

    value = {"declared_transformations": declared,
             "observed": {"rows": rows, "columns": {"before": len(ab), "after": len(aa), "added": added, "removed": removed, "retyped": retyped},
                          "undeclared_changes": undeclared, "observed_encoding_patterns": encodings, "missingness": missingness,
                          "target_coverage": coverage, "declared_but_not_observed": not_observed,
                          "declared_imputation_remaining": [x for x in imputed if x["still_missing"]]},
             "lineage": lineage or {"available": False, "reason": rows["explanation"]},
             "remaining_risks": risks,
             "pipeline_use": "Not observed: DataTrust does not see your pipeline or model. Columns present in the After file are the only demonstrated survivors.",
             "statement": NOT_IMPROVEMENT}
    ident = e.add(scope, "before_after", value, columns=sorted(set(ab) | set(aa)), population="both files as parsed; lineage only through declared identity keys",
                  denominator=before.rows, affected=abs(after.rows - before.rows))
    limitation = "Describes data differences only; it does not establish improvement or model performance."
    if not_observed:
        e.finding(ident, "Declared transformations are not reflected in the data", "Moderate", scope=scope, count=len(not_observed),
                  action="Check that the After file is the output of the declared steps, or correct the declaration.", limitations=limitation)
    if undeclared or encodings:
        e.finding(ident, "Changes between before and after were not declared", "Moderate", scope=scope, count=len(undeclared),
                  action="Declare each change, or confirm it was intended; undeclared changes are unexplained.", limitations=limitation)
    if value["observed"]["declared_imputation_remaining"]:
        e.finding(ident, "Declared imputation left missing values", "Moderate", scope=scope,
                  count=sum(x["still_missing"] for x in value["observed"]["declared_imputation_remaining"]),
                  action="Review the imputation step; columns declared imputed still contain missing values.", limitations=limitation)
    if coverage and any(abs(c["share_change_points"]) >= SHARE_REVIEW_POINTS for c in coverage["classes"]):
        e.finding(ident, "Target class shares changed during preprocessing", "Moderate", scope=scope,
                  action="Confirm the change in class shares is intended; filtering and deduplication can shift who is represented.", limitations=limitation)
    if rows["difference"] and rows["explained"] is not True:
        e.finding(ident, "Row changes are not explained by identity evidence", "Low", scope=scope, count=abs(rows["difference"]), denominator=before.rows,
                  action="Declare complete, unique identity keys to trace which rows were dropped or added.", limitations=limitation)
    return value
