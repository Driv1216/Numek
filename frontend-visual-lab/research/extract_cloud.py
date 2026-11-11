"""Packs three numeric Adult columns and the label into a compact asset for the
Trace concept's point cloud. Reads the pinned prepared CSV; writes only inside the lab.

Byte layout per row: age, hours_per_week, education_years, label (0 = <=50K, 1 = >50K).
"""
import base64
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "validation/data/prepared/adult.csv"
OUT = Path(__file__).resolve().parents[1] / "src/shared/adult-cloud.json"

buf = bytearray()
with SRC.open() as f:
    for r in csv.DictReader(f):
        buf += bytes([int(r["age"]), int(r["hours_per_week"]), int(r["education_years"]),
                      1 if r["annual_income_over_50k"].strip() == ">50K" else 0])
OUT.write_text(json.dumps({"source": "validation/data/prepared/adult.csv", "rows": len(buf) // 4,
                           "layout": ["age", "hours_per_week", "education_years", "label"],
                           "data": base64.b64encode(bytes(buf)).decode()}))
print(len(buf) // 4, "rows", OUT.stat().st_size, "bytes")
