#!/usr/bin/env python3
"""One-page scorecard of the final session (s2): every policy on every
workload at rho = 0.9, one panel per question, lower is better everywhere.

  ./scorecard.py [session]

Writes plots/scorecard-<session>.{svg,png} and prints the same numbers as a
markdown table (median of repeats).
"""

import csv
import os
import statistics
import sys
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
POLS = ["fifo", "prio", "sjf", "edf", "hinted", "hinted+rx"]
COLORS = {"fifo": "#898781", "prio": "#2a78d6", "sjf": "#eb6834", "edf": "#1baf7a",
          "hinted": "#6250d6", "hinted+rx": "#008300"}

# (title, workload, group, metric): metric is a column of summary.csv, or
# "miss" = 100 - deadline_met, or "capacity_loss" for W1
PANELS = [
    ("W2a short p99 (us)\nservice-time hints", "w2a-hol-service", "kind:short", "p99"),
    ("W2b short p99 (us)\nclass hints", "w2b-hol-class", "kind:short", "p99"),
    ("W3 tight: % missing 50 us\ndeadline hints", "w3-deadlines", "kind:tight", "miss"),
    ("W4 short p99 (us)\n10% wrong hints", "w4-wrong-hints", "kind:short", "p99"),
    ("W6 tight: % missing 50 us\nclass and deadline disagree", "w6-mixed-hints", "kind:tight", "miss"),
    ("W6 loose p99 (us)\nclass and deadline disagree", "w6-mixed-hints", "kind:loose", "p99"),
    ("the price: W2b long p99 (us)", "w2b-hol-class", "kind:long", "p99"),
    ("W1 capacity lost vs fifo (%)\n1 us requests, full queues", "w1-overhead", "all", "capacity_loss"),
]


def load(wid, session):
    rows = list(csv.DictReader(open(os.path.join(HERE, "results", wid, session, "summary.csv"))))
    return [r for r in rows if r["mode"] == "hints" and r["build"] == "hints"]


def value(rows, pol, group, metric):
    if metric == "capacity_loss":
        top = max(int(r["load_rps"]) for r in rows)
        cap = lambda p: statistics.median(float(r["resp_rps"]) for r in rows if r["policy"] == p
                                          and r["group"] == "all" and int(r["load_rps"]) == top)
        return (cap("fifo") - cap(pol)) / cap("fifo") * 100
    xs = [float(r["deadline_met"]) if metric == "miss" else float(r[metric]) for r in rows
          if r["policy"] == pol and r["group"] == group and r["rho"] == "0.9"]
    v = statistics.median(xs)
    return 100 - v if metric == "miss" else v


def main():
    session = sys.argv[1] if len(sys.argv) > 1 else "s2"
    cache, vals = {}, defaultdict(dict)
    for title, wid, group, metric in PANELS:
        rows = cache.setdefault(wid, load(wid, session))
        for pol in POLS:
            vals[title][pol] = value(rows, pol, group, metric)

    print("| policy | " + " | ".join(t.split("\n")[0] for t, *_ in PANELS) + " |")
    print("|---|" + "---|" * len(PANELS))
    for pol in POLS:
        print("| %s | " % pol + " | ".join(
            ("%.2f" if PANELS[i][3] in ("miss", "capacity_loss") else "%.0f") % vals[t][pol]
            for i, (t, *_) in enumerate(PANELS)) + " |")

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8.5,
                         "axes.edgecolor": "#c3c2b7", "xtick.color": "#52514e",
                         "ytick.color": "#898781"})
    fig, axes = plt.subplots(2, 4, figsize=(12.5, 6.2))
    fig.patch.set_facecolor("#fcfcfb")
    for ax, (title, wid, group, metric) in zip(axes.flat, PANELS):
        ax.set_facecolor("#fcfcfb")
        ax.grid(axis="y", color="#e1e0d9", linewidth=0.6)
        ax.set_axisbelow(True)
        ax.spines[["top", "right"]].set_visible(False)
        v = [vals[title][p] for p in POLS]
        ax.bar(range(len(POLS)), v, width=0.72, color=[COLORS[p] for p in POLS],
               edgecolor="#fcfcfb", linewidth=1)
        best = min(v)
        for i, x in enumerate(v):
            fmt = "%.1f" if metric in ("miss", "capacity_loss") else "%.0f"
            ax.annotate(fmt % x, (i, x), xytext=(0, 2), textcoords="offset points", ha="center",
                        fontsize=7.5, color="#0b0b0b",
                        fontweight="bold" if x == best else "normal")
        ax.set_xticks(range(len(POLS)), POLS, rotation=40, ha="right")
        ax.set_title(title, fontsize=9, loc="left", color="#0b0b0b")
        ax.set_ylim(0, max(v) * 1.18 if max(v) > 0 else 1)
    fig.suptitle("Every policy on every workload at rho = 0.9 (final session %s, median of 3); "
                 "lower is better in every panel" % session, x=0.01, ha="left", fontsize=11,
                 color="#0b0b0b")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    for ext, kw in (("svg", {}), ("png", {"dpi": 150})):
        fig.savefig(os.path.join(HERE, "plots", "scorecard-%s.%s" % (session, ext)),
                    facecolor=fig.get_facecolor(), bbox_inches="tight", **kw)


if __name__ == "__main__":
    main()
