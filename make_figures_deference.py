#!/usr/bin/env python3
"""make_figures_deference.py — Headline figure for the deferent-posture run.
Reads results/results.json (works on reconstructed or native files)."""
import json
import os
import matplotlib.pyplot as plt
import numpy as np

BASE = os.path.dirname(os.path.abspath(__file__))
rows = json.load(open(os.path.join(BASE, "results", "results.json")))
rows = [r for r in rows if r.get("posture") == "deferent"]

def syc(style, arm):
    sub = [r for r in rows if r["style"] == style and r["fallacious"]]
    return sum(1 for r in sub if r[arm] == "APPROVED"), len(sub)

plt.rcParams.update({"figure.dpi": 150, "font.size": 11,
                     "axes.titlesize": 12.5, "axes.titleweight": "bold"})
GREY, BLUE, RED = "#B0B0B0", "#4C72B0", "#C44E52"

fig, (ax, ax2) = plt.subplots(1, 2, figsize=(11.5, 5), width_ratios=[2.1, 1])

styles = ["plain", "manipulative"]
b_vals = [syc(s, "baseline_verdict")[0] for s in styles]
e_vals = [syc(s, "enforced_verdict")[0] for s in styles]
n = syc("plain", "baseline_verdict")[1]
x = np.arange(2); w = 0.36
bars_b = ax.bar(x - w/2, b_vals, w, color=GREY, label="baseline (no engine)")
bars_e = ax.bar(x + w/2, e_vals, w, color=BLUE, label="enforced (engine warning injected)")
for bars in (bars_b, bars_e):
    for bar in bars:
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.18,
                str(int(bar.get_height())), ha="center", fontsize=12, fontweight="bold")
ax.axhline(n, color=RED, linestyle=":", linewidth=1.4)
ax.text(1.46, n + 0.18, f"all {n} fallacious", color=RED, fontsize=9, ha="right")
ax.set_xticks(x)
ax.set_xticklabels(["plain rhetoric", "manipulative rhetoric"])
ax.set_ylabel(f"fallacious proposals APPROVED (of {n})")
ax.set_ylim(0, n + 1.6)
ax.set_title("Deferent reviewer: sycophancy under pressure\n"
             "Engine recall was 100% in BOTH styles — the warning was simply overridden",
             fontsize=10.5)
ax.legend(loc="upper left", fontsize=9)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)

# Right panel: verdict stability
agr_b = [r["baseline_agreement"] for r in rows]
agr_e = [r["enforced_agreement"] for r in rows]
vals = [100*np.mean(agr_b), 100*np.mean(agr_e)]
bars = ax2.bar(["baseline", "enforced"], vals, color=[GREY, BLUE], width=0.55)
for bar, v in zip(bars, vals):
    ax2.text(bar.get_x() + bar.get_width()/2, v + 0.8, f"{v:.1f}%",
             ha="center", fontsize=11, fontweight="bold")
ax2.set_ylim(0, 108)
ax2.set_ylabel("mean seed agreement (3 seeds)")
ax2.set_title("The warning destabilizes verdicts\n(conflict of authorities)", fontsize=10.5)
for s in ("top", "right"):
    ax2.spines[s].set_visible(False)

plt.tight_layout()
out = os.path.join(BASE, "results", "fig_deference_headline.png")
plt.savefig(out, bbox_inches="tight")
print("Wrote", out)
