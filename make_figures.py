#!/usr/bin/env python3
"""Generate the result figures for the README from results/results.json."""
import json
import os
import matplotlib.pyplot as plt
import numpy as np

BASE = os.path.dirname(os.path.abspath(__file__))
rows = json.load(open(os.path.join(BASE, "results", "results.json")))

plt.rcParams.update({
    "figure.dpi": 150, "font.size": 11, "axes.titlesize": 13,
    "axes.titleweight": "bold", "axes.labelsize": 11,
})
BLUE, ORANGE, GREEN, RED, GREY = "#4C72B0", "#DD8452", "#55A868", "#C44E52", "#B0B0B0"

# ----- Figure 1: engine confusion matrix (2x2) + infra callout --------------------
tp = sum(1 for r in rows if r["fallacious"] and r["engine_outcome"] == "blocked")
fp = sum(1 for r in rows if not r["fallacious"] and r["engine_outcome"] == "blocked")
fn = sum(1 for r in rows if r["fallacious"] and r["engine_outcome"] == "clean")
tn = sum(1 for r in rows if not r["fallacious"] and r["engine_outcome"] == "clean")
infra = sum(1 for r in rows if r["engine_outcome"] == "infra")

fig, ax = plt.subplots(figsize=(6.2, 5.2))
mat = np.array([[tp, fn], [fp, tn]])
colors = np.array([[GREEN, RED], [RED, GREEN]])
for i in range(2):
    for j in range(2):
        ax.add_patch(plt.Rectangle((j, 1 - i), 1, 1, facecolor=colors[i][j], alpha=0.22,
                                   edgecolor="white", linewidth=3))
        ax.text(j + 0.5, 1 - i + 0.62, str(mat[i][j]), ha="center", va="center",
                fontsize=30, fontweight="bold")
        lbl = [["blocked", "cleared"], ["blocked", "cleared"]][i][j]
        ax.text(j + 0.5, 1 - i + 0.28, lbl, ha="center", va="center", fontsize=10, color="#444")
ax.set_xlim(0, 2); ax.set_ylim(0, 2)
ax.set_xticks([0.5, 1.5]); ax.set_xticklabels(["fallacious\n(should block)", "sound\n(should clear)"])
ax.set_yticks([1.5, 0.5]); ax.set_yticklabels(["engine\nblocked", "engine\ncleared"], rotation=0)
ax.set_title(f"Engine as fallacy detector\nPrecision 80%  ·  Recall 100%  ·  F1 0.89   "
             f"({infra} infra-failure excluded)", fontsize=11)
for s in ax.spines.values():
    s.set_visible(False)
ax.tick_params(length=0)
plt.tight_layout()
plt.savefig(os.path.join(BASE, "results", "fig_engine_confusion.png"), bbox_inches="tight")
plt.close()

# ----- Figure 2: reviewer behaviour shift, baseline vs enforced -------------------
def counts(arm):
    syc = sum(1 for r in rows if r["fallacious"] and r[arm] == "APPROVED")
    good_f = sum(1 for r in rows if r["fallacious"] and r[arm] in ("REJECTED", "PENDING"))
    fa = sum(1 for r in rows if not r["fallacious"] and r[arm] in ("REJECTED", "PENDING"))
    good_s = sum(1 for r in rows if not r["fallacious"] and r[arm] == "APPROVED")
    return syc, good_f, fa, good_s

b = counts("baseline_verdict")
e = counts("enforced_verdict")
labels = ["fallacious\nAPPROVED\n(sycophancy)", "fallacious\nrejected\n(correct)",
          "sound\nrejected\n(false alarm)", "sound\nAPPROVED\n(correct)"]
bar_colors = [RED, GREEN, ORANGE, GREEN]
x = np.arange(len(labels)); w = 0.38
fig, ax = plt.subplots(figsize=(9, 5))
b1 = ax.bar(x - w/2, b, w, label="baseline (reviewer alone)", color=GREY, edgecolor="white")
b2 = ax.bar(x + w/2, e, w, label="enforced (with LSE)",
            color=[BLUE]*4, edgecolor="white")
for bars in (b1, b2):
    for bar in bars:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, h + 0.12, str(int(h)),
                ha="center", va="bottom", fontsize=10, fontweight="bold")
ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=9.5)
ax.set_ylabel("number of proposals (out of 12 each class)")
ax.set_ylim(0, 13)
ax.set_title("Reviewer verdicts: baseline vs LSE-enforced (same frozen inputs)\n"
             "Sycophancy already 0 at baseline; enforcement adds false alarms on sound proposals",
             fontsize=10.5)
ax.legend(frameon=True, loc="upper right")
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
plt.tight_layout()
plt.savefig(os.path.join(BASE, "results", "fig_reviewer_shift.png"), bbox_inches="tight")
plt.close()
print("Wrote results/fig_engine_confusion.png and results/fig_reviewer_shift.png")
