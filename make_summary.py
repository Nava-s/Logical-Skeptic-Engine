#!/usr/bin/env python3
"""make_summary.py — Writes results/results_summary.csv from a results.json.

Usage:
  python make_summary.py                       # reads results/results.json
  python make_summary.py path/to/results.json  # explicit input
Handles both legacy rows (no style/posture/seeds) and full factorial rows.
"""
import csv
import json
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE, "results", "results.json")
dst = os.path.join(BASE, "results", "results_summary.csv")

with open(src, "r", encoding="utf-8") as f:
    rows = json.load(f)

FIELDS = ["use_case", "proposal", "fallacious", "style", "posture", "seeds",
          "baseline_verdict", "baseline_agreement",
          "enforced_verdict", "enforced_agreement", "engine_outcome"]

with open(dst, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(FIELDS)
    for r in rows:
        w.writerow([
            r.get("use_case"), r.get("proposal"), r.get("fallacious"),
            r.get("style", ""), r.get("posture", ""), r.get("seeds", ""),
            r.get("baseline_verdict"),
            round(r["baseline_agreement"], 2) if r.get("baseline_agreement") is not None else "",
            r.get("enforced_verdict"),
            round(r["enforced_agreement"], 2) if r.get("enforced_agreement") is not None else "",
            r.get("engine_outcome"),
        ])

print(f"Wrote {dst} ({len(rows)} rows from {src})")
