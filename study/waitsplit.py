#!/usr/bin/env python3
"""Where a request's wait happens: in the runqueue, or before its thread
exists.

  ./waitsplit.py w5-even s1 short high

For one request kind that is alone in its class (W2b and W5: short requests
are the only HIGH ones), splits the client-measured mean wait (mean latency
minus the kind's minimum latency) into
  - runqueue: the server's mean runqueue wait for that class
    (wait_cycles_<class> / pick_<class>, runtime_sched_stats counters)
  - before the thread exists: the rest, i.e. the packet waiting to be
    processed while its core runs another request, plus delivery jitter
Medians over repeats; one stacked bar per policy and load level.
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


def main():
    wid, session, kind, cls = sys.argv[1:5]
    d = os.path.join(HERE, "results", wid, session)
    cyc = 2394.0  # TSC cycles per us on the server node
    client, rq = defaultdict(list), defaultdict(list)
    for r in csv.DictReader(open(os.path.join(d, "summary.csv"))):
        if r["group"] == "kind:" + kind and r["mean"] not in ("", "None"):
            client[(r["policy"], float(r["rho"]))].append(float(r["mean"]) - float(r["p0"]))
    for r in csv.DictReader(open(os.path.join(d, "counters.csv"))):
        cyc = float(r.get("cycles_per_us") or cyc)
        picks = int(r["pick_" + cls])
        if picks:
            rq[(r["policy"], float(r["rho"]))].append(int(r["wait_cycles_" + cls]) / picks / cyc)
    pols = []
    for p, _ in client:
        if p not in pols:
            pols.append(p)
    rhos = sorted(set(k[1] for k in client))
    rows = []
    print("| policy | rho | client wait | runqueue | before the thread exists |")
    print("|---|---|---|---|---|")
    for rho in rhos:
        for p in pols:
            c, q = statistics.median(client[(p, rho)]), statistics.median(rq[(p, rho)])
            rows.append((p, rho, c, q))
            print("| %s | %.1f | %.1f | %.1f | %.1f |" % (p, rho, c, q, c - q))

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9,
                         "axes.edgecolor": "#c3c2b7", "axes.labelcolor": "#52514e",
                         "xtick.color": "#52514e", "ytick.color": "#898781"})
    fig, ax = plt.subplots(figsize=(1.2 + 0.55 * len(rows), 3.6))
    fig.patch.set_facecolor("#fcfcfb")
    ax.set_facecolor("#fcfcfb")
    ax.grid(axis="y", color="#e1e0d9", linewidth=0.6)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    x, labels, xi = [], [], 0.0
    for i, (p, rho, c, q) in enumerate(rows):
        if i and rows[i - 1][1] != rho:
            xi += 0.6
        x.append(xi)
        labels.append(p)
        xi += 1
    ax.bar(x, [r[3] for r in rows], width=0.7, color="#2a78d6", label="in the runqueue",
           edgecolor="#fcfcfb", linewidth=1)
    ax.bar(x, [r[2] - r[3] for r in rows], bottom=[r[3] for r in rows], width=0.7,
           color="#eb6834", label="before the thread exists", edgecolor="#fcfcfb", linewidth=1)
    for xx, r in zip(x, rows):
        ax.annotate("%.0f" % r[2], (xx, r[2]), xytext=(0, 2), textcoords="offset points",
                    ha="center", fontsize=8, color="#0b0b0b")
    ax.set_xticks(x, labels, rotation=40, ha="right")
    for rho in rhos:
        xs = [xx for xx, r in zip(x, rows) if r[1] == rho]
        ax.annotate("rho = %.1f" % rho, ((xs[0] + xs[-1]) / 2, 1.0), xycoords=("data", "axes fraction"),
                    ha="center", fontsize=9, color="#52514e")
    ax.set_ylabel("mean wait of %s requests (us)" % kind)
    ax.legend(frameon=False, loc="upper left", bbox_to_anchor=(0, 1.2), ncol=2)
    fig.suptitle("%s: where %s requests wait" % (wid, kind), x=0.02, ha="left", y=1.06,
                 fontsize=11, color="#0b0b0b")
    fig.tight_layout()
    for ext, kw in (("svg", {}), ("png", {"dpi": 150})):
        fig.savefig(os.path.join(HERE, "plots", "%s-%s-waitsplit.%s" % (wid, session, ext)),
                    facecolor=fig.get_facecolor(), bbox_inches="tight", **kw)


if __name__ == "__main__":
    main()
