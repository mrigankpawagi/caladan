#!/usr/bin/env python3
"""Analysis for the v2 study (DESIGN-v2.md): SLO-load, the paired decision
rule, price, mean waits against predictions, per-request time split, and
the W1 knee.

  ./v2.py <workload> <session> [--variant V]   tables.md + plots for one workload
  ./v2.py --knee w1-overhead <session>        the W1 capacity table
  ./v2.py --scorecard <session>               the ladder scorecard (all workloads)

Definitions (fixed in DESIGN-v2.md before the runs):
- ratio(rho) = max over scored kinds of p99 / SLO (inf if the level failed)
- SLO-load = the first grid point where ratio > 1, interpolated linearly in
  ratio from the point before; ">= top" if it never exceeds 1; "< bottom" if
  the first point already does
- a difference between two configurations counts if, in every repeat, the
  paired ratio of their values lies beyond +-5% on the same side
"""

import argparse
import csv
import json
import math
import os
import statistics
import sys
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze  # noqa: E402  (predictions)

LADDER = ["stock", "fifo", "prio", "prio_edf", "hinted", "edf"]
COLORS = {"stock": "#52514e", "fifo": "#898781", "prio": "#2a78d6", "prio_edf": "#1baf7a",
          "hinted": "#6250d6", "edf": "#eb6834"}
MARKERS = {"stock": "*", "fifo": "o", "prio": "s", "prio_edf": "D", "hinted": "P", "edf": "^"}
THRESH = 0.05


def order(configs):
    """Ladder order, each policy followed by its +rx variant."""
    def key(c):
        base, _, extra = c.partition("+")
        return (LADDER.index(base) if base in LADDER else 99, extra)
    return sorted(configs, key=key)


def style(c):
    base, _, extra = c.partition("+")
    return COLORS.get(base, "#52514e"), MARKERS.get(base, "o"), "--" if extra else "-"


def fnum(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x


def load_session(wid, session, variant=None):
    d = os.path.join(HERE, "results", wid, session)
    meta = json.load(open(os.path.join(d, "meta.json")))
    rows = [r for r in csv.DictReader(open(os.path.join(d, "summary.csv")))
            if variant is None or r.get("variant") == variant]
    segs = []
    if os.path.exists(os.path.join(d, "segments.csv")):
        segs = [r for r in csv.DictReader(open(os.path.join(d, "segments.csv")))
                if variant is None or r.get("variant") == variant]
    ctr = []
    if os.path.exists(os.path.join(d, "counters.csv")):
        ctr = [r for r in csv.DictReader(open(os.path.join(d, "counters.csv")))
               if variant is None or r.get("variant") == variant]
    spec = dict(meta["workload"])
    return d, meta, spec, rows, segs, ctr


def slo_load(points, grid):
    """points: {rho: ratio}. Returns (value, censor) with censor in
    {"", ">=", "<"}."""
    prev = None
    for rho in grid:
        r = points.get(rho, math.inf)
        if r > 1:
            if prev is None:
                return grid[0], "<"
            r0 = points[prev]
            if math.isinf(r):
                return prev, ""
            return prev + (1 - r0) / (r - r0) * (rho - prev), ""
        prev = rho
    return grid[-1], ">="


def paired(a, b):
    """Decision rule: 'higher'/'lower' if every paired ratio a/b is beyond
    +-THRESH on the same side; 'tie' only if every ratio is within +-THRESH;
    otherwise 'inconclusive'. a, b: {repeat: value}."""
    ratios = [a[r] / b[r] for r in a if r in b and b[r] and a[r] is not None
              and not math.isinf(a[r]) and not math.isinf(b[r])]
    if not ratios:
        return "n/a", []
    if all(x > 1 + THRESH for x in ratios):
        return "higher", ratios
    if all(x < 1 - THRESH for x in ratios):
        return "lower", ratios
    if all(abs(x - 1) <= THRESH for x in ratios):
        return "tie", ratios
    return "inconclusive", ratios


def compare(c1, c2, sload, top_ratio):
    """c1 against c2 on SLO-load by the paired rule; when both are censored
    at the top of the grid (or the SLO-load comparison cannot clear the
    threshold because one is censored there), the tie-break compares the
    scored kinds' worst p99/SLO at the top load (lower is better), under the
    same rule. Returns (verdict, basis, ratios); verdict is 'better',
    'worse', 'tie' or 'inconclusive'."""
    a, b = sload.get(c1, {}), sload.get(c2, {})
    cens = lambda per: all(cz == ">=" for _, cz in per.values()) if per else False
    if not (cens(a) and cens(b)):
        v, rr = paired({k: x for k, (x, _) in a.items()}, {k: x for k, (x, _) in b.items()})
        if v in ("higher", "lower") or not (cens(a) or cens(b)):
            return {"higher": "better", "lower": "worse"}.get(v, v), "SLO-load", rr
    v, rr = paired(top_ratio.get(c1, {}), top_ratio.get(c2, {}))
    return {"higher": "worse", "lower": "better"}.get(v, v), "p99/SLO at top load", rr


def analyze_workload(wid, session, variant=None):
    d, meta, spec, rows, segs, ctr = load_session(wid, session, variant)
    if variant:
        spec = dict(spec, **spec.get("variants", {}).get(variant, {}))
    cal = meta["calibration"]
    kinds = {k["name"]: k for k in spec["kinds"]}
    scored = [n for n, k in kinds.items() if k.get("scored")]
    price = [n for n, k in kinds.items() if not k.get("scored")]
    grid = sorted(set(float(r["rho"]) for r in rows if r["rho"]))
    configs = order(set(r["policy"] for r in rows))
    reps = sorted(set(int(r["repeat"]) for r in rows))

    p99 = defaultdict(dict)      # (config, kind, rho) -> {repeat: p99}
    mean = defaultdict(dict)
    p0 = defaultdict(dict)
    for r in rows:
        if not r["rho"] or not r["group"].startswith("kind:"):
            if r["group"] == "all" and int(r.get("failed") or 0) and r["rho"]:
                for n in kinds:  # a failed level fails every kind
                    p99[(r["policy"], n, float(r["rho"]))][int(r["repeat"])] = math.inf
            continue
        n = r["group"][5:]
        key = (r["policy"], n, float(r["rho"]))
        v = fnum(r["p99"])
        p99[key][int(r["repeat"])] = math.inf if v is None else v
        mean[key][int(r["repeat"])] = fnum(r["mean"])
        p0[key][int(r["repeat"])] = fnum(r["p0"])

    def med(dct):
        xs = [x for x in dct.values() if x is not None]
        return statistics.median(xs) if xs else None

    # SLO-load per config and repeat
    sload = {}
    for c in configs:
        per = {}
        for rep in reps:
            pts = {}
            for rho in grid:
                vals = [p99[(c, n, rho)].get(rep) for n in scored]
                if any(v is None for v in vals):
                    continue
                pts[rho] = max(v / kinds[n]["slo_us"] for n, v in zip(scored, vals))
            if pts:
                per[rep] = slo_load(pts, grid)
        sload[c] = per

    out = ["# %s%s, session %s" % (wid, " (%s)" % variant if variant else "", session), "",
           spec.get("title", ""), "",
           "Scored kinds: %s (SLO %s). Price: %s. %d repeats; configurations in ladder order."
           % (", ".join(scored), ", ".join("%s %d us" % (n, kinds[n]["slo_us"]) for n in scored),
              ", ".join(price) or "none", len(reps)), ""]

    top = grid[-1]
    top_ratio = {}
    for c in configs:
        per = {}
        for rep in reps:
            vals = [p99[(c, n, top)].get(rep) for n in scored]
            if all(v is not None for v in vals):
                per[rep] = max(v / kinds[n]["slo_us"] for n, v in zip(scored, vals))
        top_ratio[c] = per
    out += ["## SLO-load", "",
            "Highest rho at which every scored kind's p99 <= its SLO, per repeat (>= means it "
            "never crossed within the grid). Compared by the paired rule; when the SLO-load "
            "cannot decide because of the grid top, by the worst scored p99/SLO at rho %.2f."
            % top, "",
            "| config | SLO-load (median) | per repeat | worst p99/SLO at top | vs fifo | "
            "vs the rung below |", "|---|---|---|---|---|---|"]
    for c in configs:
        per = sload[c]
        if not per:
            continue
        vals = [v for v, _ in per.values()]
        cens = set(cz for _, cz in per.values())
        m = statistics.median(vals)
        def verdict_vs(other):
            if c == other or other not in sload:
                return ""
            v, basis, rr = compare(c, other, sload, top_ratio)
            return "%s on %s (%s)" % (v, basis, ", ".join("%.2f" % x for x in rr))
        base, _, extra = c.partition("+")
        below = (base + "") if extra else (LADDER[LADDER.index(base) - 1]
                                          if base in LADDER and LADDER.index(base) > 1 else "")
        tr = top_ratio.get(c, {})
        out.append("| %s | %s%.2f | %s | %s | %s | %s |" % (
            c, ">=" if cens == {">="} else ("<" if cens == {"<"} else ""), m,
            ", ".join("%s%.2f" % (cz, v) for v, cz in (per[k] for k in sorted(per))),
            "%.2f" % statistics.median(tr.values()) if tr else "-",
            verdict_vs("fifo"), (verdict_vs(below) if below and base != "edf" else
                                 verdict_vs("prio_edf") if base == "edf" else "")))
    out.append("")

    for rho in [x for x in grid if x >= 0.8]:
        out += ["## rho = %.2f" % rho, "",
                "p99 per kind (median of repeats), its ratio to the SLO, mean wait (mean minus "
                "min latency) and the predicted mean wait (pooled / per core).", ""]
        pred = analyze.predictions(spec, cal, rho)
        predc = analyze.predictions(spec, cal, rho, pooled=False)
        hdr = "| config | " + " | ".join("%s p99 | %s wait (pred)" % (n, n) for n in kinds) + " |"
        out += [hdr, "|" + "---|" * (hdr.count("|") - 1)]
        for c in configs:
            cells = []
            for n in kinds:
                k = (c, n, rho)
                pv = med(p99[k])
                wv = [mean[k][r] - p0[k][r] for r in mean[k]
                      if mean[k][r] is not None and p0[k].get(r) is not None]
                base = c.split("+")[0]
                pr = pred.get(base, {}).get(n)
                pc = predc.get(base, {}).get(n)
                slo = kinds[n].get("slo_us")
                cells.append("%s%s | %s (%s)" % (
                    "-" if pv is None else ("inf" if math.isinf(pv) else "%.0f" % pv),
                    " (%.2f)" % (pv / slo) if pv is not None and slo and not math.isinf(pv) else "",
                    "%.1f" % statistics.median(wv) if wv else "-",
                    "%.1f/%.0f" % (pr, pc) if pr is not None else "-"))
            out.append("| %s | %s |" % (c, " | ".join(cells)))
        out.append("")
        if price and "fifo" in configs:
            out += ["Price at rho %.2f: unscored kinds' p99 against fifo (paired)." % rho, ""]
            for c in configs:
                if c == "fifo":
                    continue
                for n in price:
                    v, rr = paired(p99[(c, n, rho)], p99[("fifo", n, rho)])
                    if rr:
                        out.append("- %s, %s: %s (%s)" % (c, n, v, ", ".join("%.2f" % x for x in rr)))
            out.append("")

    # per-request split at the top load
    if segs:
        top = grid[-1]
        out += ["## Where the time goes at rho = %.2f (us; mean over repeats)" % top, "",
                "lag = client send minus schedule; in = send to server enqueue (delivery and "
                "RX-queue wait, plus classification); rq = runqueue; svc = handler; out = reply "
                "path; thread stolen = the handler ran on another kthread than the one that "
                "queued it; packet stolen = the packet was processed by another kthread than the "
                "owner of its RX queue.", ""]
        out += ["| config | kind | part | lag | in | rq | svc | out | thread stolen % | "
                "packet stolen % |", "|---|---|---|---|---|---|---|---|---|---|"]
        acc = defaultdict(list)
        for s in segs:
            if s["rho"] and abs(float(s["rho"]) - top) < 1e-9:
                acc[(s["policy"], s["group"][5:], s["part"])].append(s)
        for c in configs:
            for n in kinds:
                for part in ("mean", "tail99"):
                    xs = acc.get((c, n, part))
                    if not xs:
                        continue
                    f = lambda k: statistics.mean(float(x[k]) for x in xs)
                    out.append("| %s | %s | %s | %.1f | %.1f | %.1f | %.1f | %.1f | %.0f | %s |" % (
                        c, n, part, f("lag"), f("in"), f("rq"), f("svc"), f("out"), f("stolen"),
                        "%.0f" % f("pktstolen") if "pktstolen" in xs[0] else "-"))
        out.append("")
    if ctr and any(c.get("antagonist_rate") for c in ctr):
        out += ["## Batch job's work rate (units/s, median of repeats)", "",
                "| config | " + " | ".join("%.2f" % g for g in grid) + " |",
                "|---|" + "---|" * len(grid)]
        ar = defaultdict(list)
        for r in ctr:
            if r.get("antagonist_rate"):
                ar[(r["policy"], float(r["rho"]))].append(float(r["antagonist_rate"]))
        for c in configs:
            out.append("| %s | %s |" % (c, " | ".join(
                "%.0f" % statistics.median(ar[(c, g)]) if ar.get((c, g)) else "-" for g in grid)))
        out.append("")

    name = "%s-%s%s" % (wid, session, "-" + variant if variant else "")
    open(os.path.join(d, "tables%s.md" % ("-" + variant if variant else "")), "w").write(
        "\n".join(out) + "\n")
    plot_workload(name, spec, kinds, scored, configs, grid, p99, sload, segs)
    return {"sload": sload, "configs": configs, "scored": scored}


def setup_axes(ax):
    ax.set_facecolor("#fcfcfb")
    ax.grid(axis="y", color="#e1e0d9", linewidth=0.6)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)


def plot_workload(name, spec, kinds, scored, configs, grid, p99, sload, segs):
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9,
                         "axes.edgecolor": "#c3c2b7", "axes.labelcolor": "#52514e",
                         "xtick.color": "#898781", "ytick.color": "#898781",
                         "svg.fonttype": "none"})
    names = list(kinds)
    fig, axes = plt.subplots(1, len(names) + 1, figsize=(3.3 * (len(names) + 1), 3.6))
    fig.patch.set_facecolor("#fcfcfb")
    for ax, n in zip(axes, names):
        setup_axes(ax)
        slo = kinds[n]["slo_us"]
        for c in configs:
            ys = []
            for g in grid:
                vals = [v for v in p99[(c, n, g)].values()]
                ys.append(statistics.median(vals) / slo if vals else None)
            pts = [(g, y) for g, y in zip(grid, ys) if y is not None and not math.isinf(y)]
            col, mk, ls = style(c)
            ax.plot([p[0] for p in pts], [p[1] for p in pts], color=col, marker=mk,
                    linestyle=ls, linewidth=1.8, markersize=4.5, markeredgecolor="#fcfcfb",
                    label=c)
        ax.axhline(1, color="#898781", linestyle=(0, (4, 3)), linewidth=1)
        ax.set_title("%s p99 / SLO (%d us)%s" % (n, slo, "" if n in scored else ", price"),
                     fontsize=9.5, loc="left", color="#0b0b0b")
        ax.set_xlabel("offered load (rho)")
        ax.set_ylim(bottom=0)
    ax = axes[-1]
    setup_axes(ax)
    xs, labels = [], []
    for i, c in enumerate(configs):
        per = sload.get(c)
        if not per:
            continue
        vals = sorted(v for v, _ in per.values())
        col, _, ls = style(c)
        m = statistics.median(vals)
        ax.bar(i, m, color=col, width=0.7, hatch="//" if ls == "--" else None,
               edgecolor="#fcfcfb", linewidth=1)
        ax.plot([i, i], [vals[0], vals[-1]], color="#0b0b0b", linewidth=1)
        ge = all(cz == ">=" for _, cz in per.values())
        ax.annotate((">=%.2f" if ge else "%.2f") % m, (i, m), xytext=(0, 3),
                    textcoords="offset points", ha="center", fontsize=7.5, color="#0b0b0b")
        xs.append(i)
        labels.append(c)
    ax.set_xticks(xs, labels, rotation=45, ha="right")
    ax.set_ylim(min(grid) - 0.05, max(grid) + 0.08)
    ax.set_title("SLO-load (higher is better)", fontsize=9.5, loc="left", color="#0b0b0b")
    h, lab = axes[0].get_legend_handles_labels()
    fig.legend(h, lab, loc="upper center", ncol=min(len(lab), 10), frameon=False, fontsize=8.5,
               bbox_to_anchor=(0.5, 1.06))
    fig.suptitle("%s: %s" % (name, spec.get("title", "")), x=0.01, ha="left", y=1.14,
                 fontsize=10.5, color="#0b0b0b")
    fig.tight_layout()
    os.makedirs(os.path.join(HERE, "plots"), exist_ok=True)
    for ext, kw in (("svg", {}), ("png", {"dpi": 150})):
        fig.savefig(os.path.join(HERE, "plots", "v2-%s.%s" % (name, ext)),
                    facecolor=fig.get_facecolor(), bbox_inches="tight", **kw)
    plt.close(fig)


def knee(wid, session, bound=70.0):
    d, meta, spec, rows, segs, ctr = load_session(wid, session)
    configs = order(set(r["policy"] for r in rows))
    ok = defaultdict(dict)  # (config, rps) -> {repeat: pass}
    goodput = defaultdict(list)
    for r in rows:
        if r["group"] != "all":
            continue
        rps, rep = int(r["load_rps"]), int(r["repeat"])
        p = fnum(r.get("p99"))
        drops = fnum(r.get("dropped")) or 0
        good = not int(r.get("failed") or 0) and p is not None and not math.isinf(p) \
            and p <= bound and drops == 0
        ok[(r["policy"], rps)][rep] = good
        goodput[(r["policy"], rps)].append(fnum(r.get("resp_rps")) or 0)
    grid = sorted(set(int(r["load_rps"]) for r in rows))
    out = ["# %s, session %s: capacity (knee)" % (wid, session), "",
           "Capacity = highest offered load at which every repeat has zero drops and p99 <= "
           "%d us; a fresh server for every level. Each cell: repeats passing / run." % bound, "",
           "| config | capacity | vs fifo | " + " | ".join("%.2fM" % (g / 1e6) for g in grid)
           + " |", "|---|---|---|" + "---|" * len(grid)]
    caps = {}
    for c in configs:
        cap = None
        for g in grid:
            v = ok.get((c, g), {})
            if v and all(v.values()):
                cap = g
            else:
                break
        caps[c] = cap
    for c in configs:
        cells = []
        for g in grid:
            v = ok.get((c, g), {})
            cells.append("%d/%d" % (sum(v.values()), len(v)) if v else "-")
        rel = ("%+.1f%%" % ((caps[c] - caps["fifo"]) / caps["fifo"] * 100)
               if caps.get(c) and caps.get("fifo") else "-")
        out.append("| %s | %s | %s | %s |" % (c, "%.2fM" % (caps[c] / 1e6) if caps[c] else
                                               "< %.2fM" % (grid[0] / 1e6), rel, " | ".join(cells)))
    open(os.path.join(d, "knee.md"), "w").write("\n".join(out) + "\n")
    print("\n".join(out))
    return caps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("args", nargs="+")
    ap.add_argument("--variant")
    ap.add_argument("--knee", action="store_true")
    a = ap.parse_args()
    if a.knee:
        knee(*a.args)
        return
    res = analyze_workload(a.args[0], a.args[1], a.variant)
    d = os.path.join(HERE, "results", a.args[0], a.args[1])
    print(open(os.path.join(d, "tables%s.md" % ("-" + a.variant if a.variant else ""))).read())


if __name__ == "__main__":
    main()
