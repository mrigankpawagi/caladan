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

    out += ["## Mean-wait check (pre-registered)", "",
            "dwait = growth of the kind's mean latency over rho %.2f, net of the change in "
            "its handler time, paired by repeat; predicted = pred(rho) - pred(%.2f) pooled / "
            "per core." % (grid[0], grid[0]), ""]
    out += delta_wait_table(wid, session, variant)
    out.append("")
    name = "%s-%s%s" % (wid, session, "-" + variant if variant else "")
    open(os.path.join(d, "tables%s.md" % ("-" + variant if variant else "")), "w").write(
        "\n".join(out) + "\n")
    plot_workload(name, spec, kinds, scored, configs, grid, p99, sload, segs)
    return {"sload": sload, "configs": configs, "scored": scored, "top_ratio": top_ratio}


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


def delta_wait_table(wid, session, variant=None):
    """The pre-registered mean-wait check (DESIGN-v2.md, amendments):
    measured dwait(rho) = [mean(rho) - mean(0.5)] - [handler(rho) - handler(0.5)]
    per kind, paired within each repeat (median over repeats), against the
    predicted pred(rho) - pred(0.5). Pass: within [pooled, per-core] for
    priority orders; within +-25% of pooled for fifo."""
    d, meta, spec, rows, segs, ctr = load_session(wid, session, variant)
    if variant:
        spec = dict(spec, **spec.get("variants", {}).get(variant, {}))
    cal = meta["calibration"]
    grid = sorted(set(float(r["rho"]) for r in rows if r["rho"]))
    base_rho = grid[0]
    mean = {}
    for r in rows:
        if r["rho"] and r["group"].startswith("kind:") and fnum(r["mean"]) is not None:
            mean[(r["policy"], r["group"][5:], float(r["rho"]), int(r["repeat"]))] = fnum(r["mean"])
    svc = {}
    for x in segs:
        if x["rho"] and x["part"] == "mean":
            svc[(x["policy"], x["group"][5:], float(x["rho"]), int(x["repeat"]))] = float(x["svc"])
    configs = order(set(r["policy"] for r in rows))
    kinds = [k["name"] for k in spec["kinds"]]
    out = ["| config | rho | " + " | ".join("%s dwait meas (pooled / per core) ok" % k
                                            for k in kinds) + " |",
           "|---|---|" + "---|" * len(kinds)]
    verdicts = []
    for c in configs:
        base = c.split("+")[0]
        for rho in [g for g in grid if g >= 0.8]:
            p1, p0 = analyze.predictions(spec, cal, rho), analyze.predictions(spec, cal, base_rho)
            c1 = analyze.predictions(spec, cal, rho, pooled=False)
            c0 = analyze.predictions(spec, cal, base_rho, pooled=False)
            cells = []
            for n in kinds:
                ds = []
                for rep in range(5):
                    k1, k0 = (c, n, rho, rep), (c, n, base_rho, rep)
                    if k1 in mean and k0 in mean and k1 in svc and k0 in svc:
                        ds.append((mean[k1] - mean[k0]) - (svc[k1] - svc[k0]))
                if not ds or base not in p1:
                    cells.append("-")
                    continue
                m = statistics.median(ds)
                lo = p1[base][n] - p0[base][n]
                hi = c1[base][n] - c0[base][n]
                fifo_like = base in ("fifo", "stock") or any(
                    "fifo" in g and base in g for g in CONSTRUCTION_TIES.get(wid, []))
                if fifo_like:
                    ok = abs(m - lo) <= 0.25 * lo
                else:
                    ok = min(lo, hi) <= m <= max(lo, hi)
                if "+" not in c:
                    verdicts.append(ok)
                cells.append("%.1f (%.1f / %.0f) %s" % (m, lo, hi, "yes" if ok else "NO"))
            out.append("| %s | %.2f | %s |" % (c, rho, " | ".join(cells)))
    out.append("")
    out.append("Pre-registered check passes in %d of %d cells (policies without +rx)."
               % (sum(verdicts), len(verdicts)))
    return out


WORKLOAD_ORDER = [("w2b-hol-class", "W2b class"), ("w3-deadlines", "W3 deadline"),
                  ("w2a-hol-service", "W2a size"), ("w4-wrong-hints", "W4 wrong size"),
                  ("w6-mixed-hints", "W6 all hints")]
# cells where the ladder makes two configurations identical by construction
# (DESIGN-v2.md): workload -> groups of policies that must tie
CONSTRUCTION_TIES = {
    "w2b-hol-class": [["prio", "prio_edf", "hinted"], ["fifo", "edf"]],
    "w3-deadlines": [["fifo", "prio"], ["prio_edf", "hinted", "edf"]],
    "w2a-hol-service": [["fifo", "prio", "prio_edf", "edf"]],
    "w4-wrong-hints": [["fifo", "prio", "prio_edf", "edf"]],
    "w6-mixed-hints": [["prio_edf", "hinted"]],
}


def scorecard(session):
    """SLO-load of every configuration on every workload, ladder order."""
    res = {}
    for wid, _ in WORKLOAD_ORDER:
        try:
            res[wid] = analyze_workload(wid, session)
        except FileNotFoundError:
            pass
    configs = order(set(c for r in res.values() for c in r["configs"]))
    lines = ["# Ladder scorecard, session %s" % session, "",
             "SLO-load (median of repeats; >= means it never crossed within the grid, followed "
             "by the pre-registered tie-break in brackets: the worst scored p99/SLO at rho 0.9, "
             "lower is better). Workloads ordered by the information they need. Cells marked = "
             "must tie with the others marked = in the same column by construction.", "",
             "| config | " + " | ".join(lab for wid, lab in WORKLOAD_ORDER if wid in res) + " |",
             "|---|" + "---|" * len(res)]
    fig, ax = plt.subplots(figsize=(1.8 * len(res) + 2.2, 0.55 * len(configs) + 1.6))
    fig.patch.set_facecolor("#fcfcfb")
    ax.set_facecolor("#fcfcfb")
    cols = [wid for wid, _ in WORKLOAD_ORDER if wid in res]
    import matplotlib.colors as mcolors
    cmap = mcolors.LinearSegmentedColormap.from_list("seq", ["#f0efec", "#86b6ef", "#2a78d6",
                                                             "#184f95"])
    for i, c in enumerate(configs):
        cells = []
        for j, wid in enumerate(cols):
            per = res[wid]["sload"].get(c)
            if not per:
                cells.append("-")
                continue
            m = statistics.median(v for v, _ in per.values())
            ge = all(cz == ">=" for _, cz in per.values())
            tie = any(c.split("+")[0] in g and "+" not in c
                      for g in CONSTRUCTION_TIES.get(wid, []))
            tr = res[wid]["top_ratio"].get(c, {})
            txt = "%s%.2f%s" % (">=" if ge else "", m, " =" if tie else "")
            if ge and tr:  # the pre-registered tie-break inside censored cells
                txt += "\n(%.2f)" % statistics.median(tr.values())
            cells.append(txt)
            shade = min(max((m - 0.7) / 0.2, 0.0), 1.0)  # floats: an int indexes the colormap
            ax.add_patch(plt.Rectangle((j, i), 0.96, 0.9, color=cmap(shade)))
            ax.text(j + 0.48, i + 0.45, txt, ha="center", va="center", fontsize=8,
                    color="#ffffff" if shade > 0.55 else "#0b0b0b")
        lines.append("| %s | %s |" % (c, " | ".join(cells)))
    ax.set_xlim(0, len(cols))
    ax.set_ylim(len(configs), 0)
    ax.set_xticks([j + 0.48 for j in range(len(cols))],
                  [lab for wid, lab in WORKLOAD_ORDER if wid in res], fontsize=8.5)
    ax.xaxis.tick_top()
    ax.set_yticks([i + 0.45 for i in range(len(configs))], configs, fontsize=8.5)
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.tick_params(length=0)
    ax.set_title("SLO-load: highest load meeting every scored SLO (higher is better; "
                 "= marks a tie by construction;\nin brackets for >=0.90: worst scored "
                 "p99/SLO at rho 0.9, lower is better)", fontsize=9.5, loc="left", pad=28,
                 color="#0b0b0b")
    fig.tight_layout()
    for ext, kw in (("svg", {}), ("png", {"dpi": 150})):
        fig.savefig(os.path.join(HERE, "plots", "v2-scorecard-%s.%s" % (session, ext)),
                    facecolor=fig.get_facecolor(), bbox_inches="tight", **kw)
    out = os.path.join(HERE, "results", "scorecard-%s.md" % session)
    open(out, "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))


def timesplit(wid, session, kind, variant=None):
    """Where the scored kind's time goes at the top load: mean and slowest 1%,
    per configuration (client lag, which is negative, is left out)."""
    d, meta, spec, rows, segs, ctr = load_session(wid, session, variant)
    grid = sorted(set(float(r["rho"]) for r in rows if r["rho"]))
    top = grid[-1]
    acc = defaultdict(list)
    for x in segs:
        if x["rho"] and abs(float(x["rho"]) - top) < 1e-9 and x["group"] == "kind:" + kind:
            acc[(x["policy"], x["part"])].append(x)
    configs = order(set(c for c, _ in acc))
    parts = [("in", "send to enqueue (delivery, RX queue)", "#eb6834"),
             ("rq", "runqueue", "#2a78d6"), ("svc", "handler", "#c3c2b7"),
             ("out", "reply path", "#898781")]
    fig, axes = plt.subplots(1, 2, figsize=(10, 0.42 * len(configs) + 1.6), sharey=True)
    fig.patch.set_facecolor("#fcfcfb")
    for ax, part, title in zip(axes, ("mean", "tail99"), ("mean request", "slowest 1%")):
        setup_axes(ax)
        ax.grid(axis="x", color="#e1e0d9", linewidth=0.6)
        ax.grid(axis="y", visible=False)
        for i, c in enumerate(configs):
            xs = acc.get((c, part))
            if not xs:
                continue
            left = 0
            for k, lab, col in parts:
                v = statistics.mean(float(x[k]) for x in xs)
                ax.barh(i, v, left=left, color=col, height=0.7, edgecolor="#fcfcfb",
                        linewidth=1, label=lab if i == 0 else None)
                left += v
            ax.annotate("%.0f" % left, (left, i), xytext=(3, 0), textcoords="offset points",
                        va="center", fontsize=7.5, color="#0b0b0b")
        ax.set_yticks(range(len(configs)), configs)
        ax.set_title("%s: %s" % (kind, title), fontsize=9.5, loc="left", color="#0b0b0b")
        ax.set_xlabel("us")
    axes[0].invert_yaxis()  # shared axis: once, so the ladder reads top-down
    h, lab = axes[0].get_legend_handles_labels()
    fig.legend(h, lab, loc="upper center", ncol=4, frameon=False, fontsize=8.5,
               bbox_to_anchor=(0.5, 1.04))
    fig.suptitle("%s at rho %.2f: where %s requests spend their time" % (wid, top, kind),
                 x=0.01, ha="left", y=1.1, fontsize=10.5, color="#0b0b0b")
    fig.tight_layout()
    name = "v2-%s-%s%s-split" % (wid, session, "-" + variant if variant else "")
    for ext, kw in (("svg", {}), ("png", {"dpi": 150})):
        fig.savefig(os.path.join(HERE, "plots", name + "." + ext),
                    facecolor=fig.get_facecolor(), bbox_inches="tight", **kw)
    plt.close(fig)


def aa_noise(session):
    """Configurations identical by construction, used as A/A tests: the spread
    of their medians per metric (max/min - 1), per workload and load."""
    out = ["| workload | identical configs | rho | scored p99 spread | price p99 spread |",
           "|---|---|---|---|---|"]
    for wid, _ in WORKLOAD_ORDER:
        try:
            d, meta, spec, rows, segs, ctr = load_session(wid, session)
        except FileNotFoundError:
            continue
        kinds = {k["name"]: k for k in spec["kinds"]}
        for group in CONSTRUCTION_TIES.get(wid, []):
            for rho in ("0.8", "0.9"):
                def spread(names):
                    vals = []
                    for c in group:
                        xs = [fnum(r["p99"]) for r in rows if r["policy"] == c and r["rho"] == rho
                              and r["group"] in ["kind:" + n for n in names]]
                        xs = [x for x in xs if x is not None and not math.isinf(x)]
                        if xs:
                            vals.append(statistics.median(xs))
                    return "%.1f%%" % ((max(vals) / min(vals) - 1) * 100) if len(vals) > 1 else "-"
                sc = [n for n, k in kinds.items() if k.get("scored")]
                pr = [n for n, k in kinds.items() if not k.get("scored")]
                out.append("| %s | %s | %s | %s | %s |" % (
                    wid, ", ".join(group), rho, spread(sc), spread(pr) if pr else "-"))
    return out


def knee_brackets(wid, session, bound=70.0):
    """Stage-2 levels: a 10k grid strictly inside each configuration's
    stage-1 bracket (last level passing in every repeat, first failing)."""
    d, meta, spec, rows, segs, ctr = load_session(wid, session)
    grid = sorted(set(int(r["load_rps"]) for r in rows))
    ok = defaultdict(dict)
    for r in rows:
        if r["group"] != "all":
            continue
        p = fnum(r.get("p99"))
        good = not int(r.get("failed") or 0) and p is not None and not math.isinf(p) \
            and p <= bound and (fnum(r.get("dropped")) or 0) == 0
        ok[(r["policy"], int(r["load_rps"]))][int(r["repeat"])] = good
    out = {}
    for c in order(set(r["policy"] for r in rows)):
        last = None
        for g in grid:
            v = ok.get((c, g), {})
            if v and all(v.values()):
                last = g
            else:
                break
        if last is None or last == grid[-1]:
            out[c] = []
            continue
        nxt = grid[grid.index(last) + 1]
        out[c] = list(range(last + 10000, nxt, 10000))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("args", nargs="+")
    ap.add_argument("--variant")
    ap.add_argument("--knee", action="store_true")
    ap.add_argument("--brackets", action="store_true")
    ap.add_argument("--scorecard", action="store_true")
    ap.add_argument("--split", help="kind for the time-split figure")
    a = ap.parse_args()
    if a.knee:
        knee(*a.args)
        return
    if a.brackets:
        print(json.dumps(knee_brackets(*a.args)))
        return
    if a.scorecard:
        scorecard(a.args[0])
        print("\n".join(aa_noise(a.args[0])))
        return
    if a.split:
        timesplit(a.args[0], a.args[1], a.split, a.variant)
        return
    res = analyze_workload(a.args[0], a.args[1], a.variant)
    d = os.path.join(HERE, "results", a.args[0], a.args[1])
    print(open(os.path.join(d, "tables%s.md" % ("-" + a.variant if a.variant else ""))).read())


if __name__ == "__main__":
    main()
