"""Real per-column distributions and an age x hours density grid from the pinned
Adult CSV, for the round-three concepts. Writes only inside the lab."""
import json
from pathlib import Path
import numpy as np
import pandas as pd

LAB = Path(__file__).resolve().parents[1]
df = pd.read_csv(LAB.parent / "validation/data/prepared/adult.csv")
target = "annual_income_over_50k"
cols = []
for c in df.columns:
    s = df[c]
    item = {"name": c, "missing": int(s.isna().sum())}
    if pd.api.types.is_numeric_dtype(s):
        v = s.dropna().to_numpy()
        lo, hi = float(v.min()), float(v.max())
        counts, edges = np.histogram(v, bins=24, range=(lo, hi))
        item |= {"kind": "numeric", "min": lo, "max": hi, "bins": counts.tolist(), "edges": [round(float(e), 2) for e in edges]}
    else:
        vc = s.value_counts(dropna=True)
        top = vc.head(8)
        item |= {"kind": "categorical", "top": [[str(k), int(n)] for k, n in top.items()], "other": int(vc.iloc[8:].sum()), "distinct": int(vc.size)}
    cols.append(item)

age_edges = np.arange(17, 92, 2)      # 37 bins of 2 years
hour_edges = np.arange(1, 105, 4)     # 26 bins of 4 hours, through 100
H, _, _ = np.histogram2d(df["age"], df["hours_per_week"], bins=[age_edges, hour_edges])
Hh, _, _ = np.histogram2d(df.loc[df[target] == ">50K", "age"], df.loc[df[target] == ">50K", "hours_per_week"], bins=[age_edges, hour_edges])
out = {"columns": cols, "grid": {"age_edges": age_edges.tolist(), "hour_edges": hour_edges.tolist(), "counts": H.astype(int).tolist(), "high": Hh.astype(int).tolist()}}
(LAB / "src/shared/distributions.json").write_text(json.dumps(out))
peak = np.unravel_index(H.argmax(), H.shape)
print("peak", age_edges[peak[0]], hour_edges[peak[1]], int(H.max()), "total", int(H.sum()))
