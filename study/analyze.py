#!/usr/bin/env python3
"""Tables, predictions and plots for one workload session.

  ./analyze.py w2a-hol-service s1

Reads results/<workload>/<session>/summary.csv and writes, next to it:
  tables.md   per load level and request kind: median over repeats of the
              mean latency, the mean wait, p50, p99, p99.9 and deadline-met,
              the spread of p99 across repeats, and the textbook prediction
  plots/<workload>-<session>.svg   mean wait and p99 by load, one panel per kind

"Wait" is the time a request spends before running: its mean latency minus
the smallest latency seen for its kind in that run (network round trip plus
service time, with no queueing).

Predictions use the textbook formulas from DESIGN.md, applied to the pooled
k-core queue (work stealing approximately pools the cores):
  - FIFO: Allen-Cunneen, Wq = ErlangC(k, a) / (k mu - lambda) * (1 + Cs^2) / 2
  - priority to a class (non-preemptive): Cobham's split of the same residual
    term, W_1 = W0 / (1 - rho_1), W_2 = W0 / ((1 - rho_1)(1 - rho)), with
    W0 = Wq_fifo * (1 - rho), so that the formulas agree with FIFO's
For all-equal service times FIFO, SJF and EDF move waiting but cannot change
the mean (Kleinrock's conservation law).
"""

import csv
import json
import math
import os
import statistics
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
POLICY_ORDER = ["stock", "fifo (no hints)", "fifo", "prio", "sjf", "edf", "hinted",
                "prio+steal", "hinted+steal", "fifo+q25", "prio+q25", "fifo+q10", "prio+q10", "fifo+rx", "prio+rx", "hinted+rx"]
# reference categorical palette, fixed order; fifo is the neutral baseline
COLORS = {"stock": "#52514e", "fifo (no hints)": "#eda100", "fifo": "#898781",
          "prio": "#2a78d6", "sjf": "#eb6834", "edf": "#1baf7a", "hinted": "#6250d6",
          "prio+steal": "#e87ba4", "hinted+steal": "#008300",
          "fifo+q25": "#c3c2b7", "prio+q25": "#86b6ef", "fifo+q10": "#52514e", "prio+q10": "#184f95",
          "fifo+rx": "#52514e", "prio+rx": "#e87ba4", "hinted+rx": "#008300"}
MARKERS = {"stock": "*", "fifo (no hints)": "h", "fifo": "o", "prio": "s", "sjf": "^",
           "edf": "D", "hinted": "P", "prio+steal": "v", "hinted+steal": "X",
           "fifo+q25": "o", "prio+q25": "s", "fifo+q10": "o", "prio+q10": "s",
           "fifo+rx": "h", "prio+rx": "v", "hinted+rx": "X"}


def erlang_c(k, a):
    """Probability of waiting in M/M/k with offered load a = lambda / mu."""
    s = sum(a ** n / math.factorial(n) for n in range(k))
    t = a ** k / math.factorial(k) * k / (k - a)
    return t / (s + t)


def predictions(spec, cal, rho, pooled=True):
    """Predicted mean wait (us) per policy and kind at utilisation rho
    (rho = rate x mean handler time / cores), or {} without rho.

    With hints set per request kind, every policy is a fixed ordering of the
    kinds (kinds that tie are served FIFO among themselves), so each is a
    non-preemptive priority queue: Cobham's split of the FIFO residual term.
    pooled=True treats the cores as one M/G/k queue (Allen-Cunneen);
    pooled=False treats each core as its own M/G/1 queue with no stealing.
    Handler times are the in-place measurements in calibration.json."""
    if rho is None or not rho:
        return {}
    k = spec.get("rho_kthreads", spec["server_kthreads"])
    kinds = spec["kinds"]
    tot = sum(x["weight"] for x in kinds)
    s = [cal["handler_us"][str(x["service_us"])] for x in kinds]
    p = [x["weight"] / tot for x in kinds]
    es = sum(pi * si for pi, si in zip(p, s))
    es2 = sum(pi * si * si for pi, si in zip(p, s))
    cs2 = es2 / es ** 2 - 1
    lam = rho * k / es
    if pooled:
        wq = erlang_c(k, lam * es) / (k / es - lam) * (1 + cs2) / 2
    else:
        wq = (lam / k) * es2 / 2 / (1 - rho)
    w0 = wq * (1 - rho)

    def order_by(keyfn):
        res, sigma_prev = {}, 0.0
        for v in sorted(set(keyfn(x) for x in kinds)):
            members = [i for i, x in enumerate(kinds) if keyfn(x) == v]
            sigma = sigma_prev + sum(lam * p[i] * s[i] for i in members) / k
            for i in members:
                res[kinds[i]["name"]] = w0 / ((1 - sigma_prev) * (1 - sigma))
            sigma_prev = sigma
        return res

    def field(x, i):
        f = (x.get("hint") or "").split(":")
        v = f[i] if len(f) > i else ""
        return float(v) if v not in ("", "0") else math.inf

    rank = {"high": 1, "normal": 2, "low": 3}
    cls = lambda x: rank.get((x.get("hint") or "normal").split(":")[0], 2)
    return {"fifo": {x["name"]: wq for x in kinds},
            "prio": order_by(cls),
            "prio_edf": order_by(lambda x: (cls(x), field(x, 1))),
            "hinted": order_by(lambda x: (cls(x), field(x, 1), field(x, 2))),
            "edf": order_by(lambda x: field(x, 1)),
            "stock": {x["name"]: wq for x in kinds}}


def load(path):
    rows = list(csv.DictReader(open(path)))
    for r in rows:
        for f in ("load_rps", "repeat"):
            r[f] = int(r[f])
        for f in ("mean", "p0", "p50", "p99", "p999", "deadline_met", "resp_rps", "sent_rps"):
            v = r.get(f)
            r[f] = float(v) if v not in (None, "", "None") else None
        r["rho"] = float(r["rho"]) if r.get("rho") else None
        if r.get("build") == "stock":
            r["policy"] = "stock"
        elif r.get("mode") == "ignore":
            r["policy"] = r["policy"] + " (no hints)"
    return rows


def med(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def fmt(v, nd=0):
    if v is None:
        return "-"
    if v == float("inf"):
        return "inf"
    return ("%%.%df" % nd) % v


def main():
    wid, session = sys.argv[1], sys.argv[2]
    d = os.path.join(HERE, "results", wid, session)
    rows = load(os.path.join(d, "summary.csv"))
    meta = json.load(open(os.path.join(d, "meta.json")))
    spec, cal = meta["workload"], meta["calibration"]
    pols = [p for p in POLICY_ORDER if any(r["policy"] == p for r in rows)]
    pols += sorted(set(r["policy"] for r in rows) - set(pols))
    loads = sorted(set(r["load_rps"] for r in rows))
    rho_of = {r["load_rps"]: r["rho"] for r in rows}
    groups = ["kind:" + k["name"] for k in spec["kinds"]] + (["all"] if len(spec["kinds"]) > 1 else [])
    if len(spec["kinds"]) == 1:
        groups = ["all"]
    deadline = {"kind:" + k["name"]: k.get("deadline_us", 0) for k in spec["kinds"]}

    # cell[(policy, load, group)] = list of per-repeat rows
    cell = defaultdict(list)
    for r in rows:
        cell[(r["policy"], r["load_rps"], r["group"])].append(r)

    def stat(pol, load_, g, f):
        return med([r[f] for r in cell[(pol, load_, g)]])

    def wait(pol, load_, g):
        if g == "all" and len(spec["kinds"]) > 1:
            return None  # kinds differ in minimum latency; a pooled wait means nothing
        xs = [r["mean"] - r["p0"] for r in cell[(pol, load_, g)]
              if r["mean"] is not None and r["p0"] is not None]
        return med(xs)

    def spread(pol, load_, g):
        xs = [r["p99"] for r in cell[(pol, load_, g)] if r["p99"] not in (None, float("inf"))]
        if len(xs) < 2:
            return None
        return (max(xs) - min(xs)) / statistics.median(xs) * 100

    reps = max(r["repeat"] for r in rows) + 1
    out = ["# %s, session %s" % (wid, session), "",
           spec.get("title", ""), "",
           "Median of %d repeats per cell. *wait* = mean latency minus the kind's minimum "
           "latency; *pred* = predicted mean wait with the cores pooled into one queue, *pred/core* = with each core its own queue and no stealing (see analyze.py). *p99 spread* = "
           "(max - min) / median of p99 across repeats." % reps, ""]
    for load_ in loads:
        rho = rho_of[load_]
        pred = predictions(spec, cal, rho)
        predc = predictions(spec, cal, rho, pooled=False)
        out.append("## %d req/s%s" % (load_, " (rho = %.2f)" % rho if rho else ""))
        out.append("")
        for g in groups:
            name = g.split(":", 1)[-1]
            dl = deadline.get(g, 0)
            hdr = "| %s | wait | pred | pred/core | mean | p50 | p99 | p99.9 | p99 spread |%s" % (
                name, " met %d us |" % dl if dl else "")
            out += [hdr, "|" + "---|" * (hdr.count("|") - 1)]
            for pol in pols:
                if not cell[(pol, load_, g)]:
                    continue
                pv = pred.get(pol.split("+")[0], {}).get(name) if g != "all" else None
                pc = predc.get(pol.split("+")[0], {}).get(name) if g != "all" else None
                line = "| %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
                    pol, fmt(wait(pol, load_, g), 1), fmt(pv, 1), fmt(pc, 1),
                    fmt(stat(pol, load_, g, "mean"), 1), fmt(stat(pol, load_, g, "p50")),
                    fmt(stat(pol, load_, g, "p99")), fmt(stat(pol, load_, g, "p999")),
                    fmt(spread(pol, load_, g)) + "%" if spread(pol, load_, g) is not None else "-")
                if dl:
                    line += " %s |" % fmt(stat(pol, load_, g, "deadline_met"), 2)
                out.append(line)
            out.append("")
    open(os.path.join(d, "tables.md"), "w").write("\n".join(out) + "\n")

    # plots: row 1 mean wait, row 2 p99, one column per kind
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9,
                         "axes.edgecolor": "#c3c2b7", "axes.labelcolor": "#52514e",
                         "xtick.color": "#898781", "ytick.color": "#898781",
                         "axes.titlecolor": "#0b0b0b", "svg.fonttype": "none"})
    if not all(rho_of[l] for l in loads):
        return capacity_plot(wid, session, spec, pols, loads, stat, cell, out)
    kg = [g for g in groups if g != "all"] or ["all"]
    fig, axes = plt.subplots(2, len(kg), figsize=(3.4 * len(kg) + 0.6, 5.4), squeeze=False)
    fig.patch.set_facecolor("#fcfcfb")
    xs_of = lambda: [rho_of[l] if rho_of[l] else l / 1e6 for l in loads]
    xlabel = "offered load (rho)" if all(rho_of[l] for l in loads) else "offered load (M req/s)"
    for c, g in enumerate(kg):
        for rr, (metric, label) in enumerate([("wait", "mean wait (us)"), ("p99", "p99 latency (us)")]):
            ax = axes[rr][c]
            ax.set_facecolor("#fcfcfb")
            ax.grid(axis="y", color="#e1e0d9", linewidth=0.6)
            ax.spines[["top", "right"]].set_visible(False)
            for pol in pols:
                ys = [wait(pol, l, g) if metric == "wait" else stat(pol, l, g, "p99") for l in loads]
                pts = [(x, y) for x, y in zip(xs_of(), ys) if y is not None and y != float("inf")]
                if not pts:
                    continue
                ax.plot([p[0] for p in pts], [p[1] for p in pts], color=COLORS.get(pol, "#52514e"),
                        marker=MARKERS.get(pol, "o"), markersize=5, linewidth=2,
                        markeredgecolor="#fcfcfb", markeredgewidth=1, label=pol)
            if metric == "wait" and g != "all":
                for pol in pols:
                    pv = [(rho_of[l], predictions(spec, cal, rho_of[l])
                           .get(pol.split("+")[0], {}).get(g.split(":", 1)[-1])) for l in loads]
                    pv = [p for p in pv if p[0] and p[1] is not None]
                    if pv and "+" not in pol:
                        ax.plot([p[0] for p in pv], [p[1] for p in pv], color=COLORS.get(pol),
                                linewidth=1, linestyle=(0, (3, 2)))
            if metric == "p99" and deadline.get(g):
                ax.axhline(deadline[g], color="#898781", linestyle=(0, (4, 3)), linewidth=1)
                ax.annotate("deadline", (ax.get_xlim()[0], deadline[g]), color="#898781",
                            fontsize=8, va="bottom")
            ax.set_ylim(bottom=0)
            if rr == 0:
                ax.set_title(g.split(":", 1)[-1] + " requests", fontsize=10, loc="left")
            if c == 0:
                ax.set_ylabel(label)
            if rr == 1:
                ax.set_xlabel(xlabel)
    h, lab = axes[0][0].get_legend_handles_labels()
    fig.legend(h, lab, loc="upper center", ncol=len(lab), frameon=False, fontsize=9,
               bbox_to_anchor=(0.5, 1.0))
    if all(rho_of[l] for l in loads):
        fig.text(0.99, 0.955, "dashed: predicted mean wait", ha="right", fontsize=8,
                 color="#898781")
    fig.suptitle("%s: %s" % (wid, spec.get("title", "")), y=1.06, fontsize=11, x=0.02,
                 ha="left", color="#0b0b0b")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    os.makedirs(os.path.join(HERE, "plots"), exist_ok=True)
    for ext, kw in (("svg", {}), ("png", {"dpi": 150})):
        fig.savefig(os.path.join(HERE, "plots", "%s-%s.%s" % (wid, session, ext)),
                    facecolor=fig.get_facecolor(), bbox_inches="tight", **kw)
    print("\n".join(out))


def capacity_plot(wid, session, spec, pols, loads, stat, cell, out):
    """For fixed-rate workloads (W1): p99 while every configuration keeps up,
    and capacity, the throughput achieved at the highest offered load."""
    import matplotlib.pyplot as plt
    ok = [l for l in loads if all(stat(p, l, "all", "p99") not in (None, float("inf"))
                                   for p in pols)]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(9, 3.4), gridspec_kw={"width_ratios": [1.1, 1]})
    fig.patch.set_facecolor("#fcfcfb")
    for ax in (a1, a2):
        ax.set_facecolor("#fcfcfb")
        ax.spines[["top", "right"]].set_visible(False)
    a1.grid(axis="y", color="#e1e0d9", linewidth=0.6)
    for pol in pols:
        a1.plot([l / 1e6 for l in ok], [stat(pol, l, "all", "p99") for l in ok],
                color=COLORS.get(pol, "#52514e"), marker=MARKERS.get(pol, "o"), markersize=5,
                linewidth=2, markeredgecolor="#fcfcfb", label=pol)
    a1.set_ylim(bottom=0)
    a1.set_xlabel("offered load (M req/s)")
    a1.set_ylabel("p99 latency (us)")
    a1.set_title("p99 while every configuration keeps up", fontsize=10, loc="left")
    top = max(loads)
    caps = [(pol, med([r["resp_rps"] for r in cell[(pol, top, "all")]])) for pol in pols]
    base = caps[0][1]
    a2.grid(axis="x", color="#e1e0d9", linewidth=0.6)
    for i, (pol, c) in enumerate(caps):
        a2.barh(i, c / 1e6, height=0.6, color=COLORS.get(pol, "#52514e"))
        a2.annotate("%.3f M  (%+.1f%%)" % (c / 1e6, (c - base) / base * 100) if i else
                    "%.3f M" % (c / 1e6), (c / 1e6, i), xytext=(4, 0),
                    textcoords="offset points", va="center", fontsize=8, color="#0b0b0b")
    a2.set_yticks(range(len(caps)), [p for p, _ in caps])
    a2.invert_yaxis()
    a2.set_xlim(0, base / 1e6 * 1.45)
    a2.set_xlabel("capacity (M req/s, achieved at %.1f M offered)" % (top / 1e6))
    a2.set_title("capacity, relative to %s" % caps[0][0], fontsize=10, loc="left")
    h, lab = a1.get_legend_handles_labels()
    fig.legend(h, lab, loc="upper center", ncol=len(lab), frameon=False, fontsize=9,
               bbox_to_anchor=(0.5, 1.02))
    fig.suptitle("%s: %s" % (wid, spec.get("title", "")), y=1.1, fontsize=11, x=0.02,
                 ha="left", color="#0b0b0b")
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    for ext, kw in (("svg", {}), ("png", {"dpi": 150})):
        fig.savefig(os.path.join(HERE, "plots", "%s-%s.%s" % (wid, session, ext)),
                    facecolor=fig.get_facecolor(), bbox_inches="tight", **kw)
    print("\n".join(out))


if __name__ == "__main__":
    main()
