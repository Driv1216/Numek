"""Which analyses fit an uploaded CSV ("Start from a CSV"; Guided Analysis Stage 4a).

Advisory and deterministic: built only from the input inspection (input_inspection_v1). It never ranks, never preselects
and never gates: every analysis stays choosable, including those listed as unlikely to be useful. Each entry names the
inspection rules behind it.
"""
from datatrust.target_guidance import regression_target_groups

STATES = ("can_run", "needs_input", "unlikely")


def _with(inspection, rule):
    return [c["name"] for c in inspection["columns"] if any(s["rule"] == rule for s in c["suggestions"])]


def _names(names, limit=3):
    shown = ", ".join(names[:limit])
    return shown + (f" and {len(names) - limit:,} more" if len(names) > limit else "")


def applicable_analyses(inspection):
    """One entry per analysis that runs on a single CSV, plus the multi-source workflows a CSV can lead to."""
    small = sorted(set(_with(inspection, "R-CAT-1")) | set(_with(inspection, "R-BIN-1")), key=[c["name"] for c in inspection["columns"]].index)
    groups = regression_target_groups(inspection)
    numeric = [o["name"] for o in groups["options"] if o["group"] in {"outcome_word", "numeric"}]
    ids = set(_with(inspection, "R-ID-1")) | set(_with(inspection, "R-ID-2"))
    quantitative = [c for c in _with(inspection, "R-NUM-1") if c not in ids]  # identifiers carry no distance
    indicators = inspection["table"][0]["columns"] if inspection["table"] else []
    status = _with(inspection, "R-STATUS-1")
    clocks = _with(inspection, "R-TIME-1") + _with(inspection, "R-TIME-2")
    text = _with(inspection, "R-TEXT-1")
    n = lambda k, one, many: f"{k:,} {one if k == 1 else many}"
    out = [
        ("unlabeled", "can_run", "No prediction target is needed; every column is profiled.", []),
        ("role_profile", "can_run", "You choose which columns are features, metadata or ignored.", []),
        ("classification", *(("can_run", f"{n(len(small), 'column has', 'columns have')} a small set of values ({_names(small)}); you choose which is the outcome.")
                              if small else ("unlikely", "No column has a small set of values to predict.")), ["R-CAT-1", "R-BIN-1"]),
        ("regression", *(("can_run", f"{n(len(numeric), 'numeric column has', 'numeric columns have')} many values ({_names(numeric)}); you choose which is the outcome.")
                          if numeric else ("unlikely", f"No numeric column has more than {groups['ceiling']} distinct values.")), ["R-NUM-1"]),
        ("multioutput", *(("can_run", f"{n(len(numeric), 'numeric column', 'numeric columns')} with many values; you choose two or more outcomes.")
                           if len(numeric) >= 2 else ("unlikely", "Fewer than two numeric columns have many values.")), ["R-NUM-1"]),
        ("multilabel_classification", *(("can_run", f"{n(len(indicators), 'yes/no column', 'yes/no columns')} ({_names(indicators)}); a fit only if they are labels, one per label.")
                                          if len(indicators) >= 2 else ("unlikely", "Fewer than two yes/no indicator columns.")), ["R-MULTI-1"]),
        ("annotation_classification", *(("can_run", f"{_names(status)} {'looks' if len(status) == 1 else 'look'} like a labelling status; you declare which labels are expected.")
                                         if status else ("can_run", "For a category outcome whose labels may be incomplete; you declare which labels are expected.") if small
                                         else ("unlikely", "No column has a small set of values to predict.")), ["R-STATUS-1", "R-CAT-1", "R-BIN-1"]),
        ("annotation_regression", "can_run" if numeric else "unlikely",
         "For a numerical outcome whose values may be incomplete." if numeric else "No numeric column has many values.", ["R-NUM-1"]),
        ("clustering", *(("can_run", f"{n(len(quantitative), 'numeric column', 'numeric columns')} (not identifiers) could describe each row.") if len(quantitative) >= 2
                         else ("unlikely", "Fewer than two numeric columns to measure distance with.")), ["R-NUM-1"]),
        ("anomaly_detection", *(("can_run", f"{n(len(quantitative), 'numeric column', 'numeric columns')} (not identifiers) could describe each row.") if len(quantitative) >= 2
                                else ("unlikely", "Fewer than two numeric columns to measure distance with.")), ["R-NUM-1"]),
        ("temporal", *(("needs_input", f"{_names(clocks)} may hold times; you confirm the observation clock, in the Data over time workflow (upload the file there).")
                       if clocks else ("unlikely", "No column parses as an ISO date or time, or as epoch numbers.")), ["R-TIME-1", "R-TIME-2"]),
        ("comparison", "needs_input", "Needs a second file (or a third): training and evaluation splits, or two versions.", []),
        ("text", *(("needs_input", f"{_names(text)} {'holds' if len(text) == 1 else 'hold'} free text; the Text workflow reads CSV or JSONL (upload the file there).")
                   if text else ("unlikely", "No column holds free text.")), ["R-TEXT-1"]),
    ]
    return [{"analysis": a, "state": s, "reason": r, "rules": rules} for a, s, r, rules in out]
