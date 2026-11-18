#!/usr/bin/env python3
"""Plots pickbench results: cycles per pick by runqueue depth, per policy."""
import csv
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
COLORS = {"fifo": "#898781", "prio": "#2a78d6", "sjf": "#eb6834", "edf": "#1baf7a"}
MARKERS = {"fifo": "o", "prio": "s", "sjf": "^", "edf": "D"}
src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "results-hp070.csv")
rows = list(csv.DictReader(open(src)))
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": "#c3c2b7",
                     "axes.labelcolor": "#52514e", "xtick.color": "#898781",
                     "ytick.color": "#898781", "svg.fonttype": "none"})
fig, axes = plt.subplots(1, 2, figsize=(8, 3.2), sharey=True)
fig.patch.set_facecolor("#fcfcfb")
for ax, case, title in zip(axes, ["hot", "cold"], ["threads in cache", "threads flushed from cache"]):
    ax.set_facecolor("#fcfcfb")
    ax.grid(axis="y", color="#e1e0d9", linewidth=0.6)
    ax.spines[["top", "right"]].set_visible(False)
    for pol in ["fifo", "prio", "sjf", "edf"]:
        pts = [(int(r["depth"]), int(r["median_cycles"])) for r in rows
               if r["policy"] == pol and r["case"] == case]
        ax.plot([p[0] for p in pts], [p[1] for p in pts], color=COLORS[pol], marker=MARKERS[pol],
                markersize=5, linewidth=2, markeredgecolor="#fcfcfb", label=pol)
        if pol != "sjf":  # sjf and edf cost the same and overlap; label them once
            ax.annotate("sjf, edf" if pol == "edf" else pol, pts[-1], xytext=(4, 0),
                        textcoords="offset points", va="center", fontsize=8, color="#52514e")
    ax.set_xscale("log", base=2)
    ax.set_xticks([2, 4, 8, 16, 32], ["2", "4", "8", "16", "32"])
    ax.set_xlim(1.7, 60)
    ax.set_title(title, fontsize=10, loc="left", color="#0b0b0b")
    ax.set_xlabel("runqueue depth (threads)")
axes[0].set_ylabel("cycles per pick (median)")
axes[0].set_ylim(bottom=0)
h, l = axes[0].get_legend_handles_labels()
fig.legend(h, l, loc="upper center", ncol=4, frameon=False, bbox_to_anchor=(0.5, 1.04))
fig.tight_layout(rect=(0, 0, 1, 0.93))
out = os.path.join(HERE, "..", "plots", "pickbench.svg")
os.makedirs(os.path.dirname(out), exist_ok=True)
fig.savefig(out, facecolor=fig.get_facecolor(), bbox_inches="tight")
fig.savefig(out[:-4] + ".png", dpi=150, facecolor=fig.get_facecolor(), bbox_inches="tight")
print(out)
