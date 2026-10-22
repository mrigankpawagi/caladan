#!/usr/bin/env python3
"""Builds LEADERBOARD.md and per-generation tables from autoresearch results.

  ./summarize.py              rewrite LEADERBOARD.md and plots/*.svg from all
                              generations
  ./summarize.py --gen 3      also write results/gen3/tables.md, the detailed
                              per-load tables the measurement agent reads

Definitions (also in README.md):
  headline load  highest load level at which the baseline (fifo, hints
                 applied, hint-enabled build) answers >= 99% of requests,
                 keeps client schedule adherence >= 99%, and keeps the overall
                 median latency within 1.5x of its value at the lightest load,
                 i.e. the busiest level that is not in overload
  score          the workload's score kind and percentile (e.g. short p99) at
                 the headline load, median over repeats; lower is better
"""

import argparse
import csv
import glob
import json
import math
import os
import re
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from lib import spec as specs  # noqa: E402
from lib import plots  # noqa: E402

BASELINE = ("fifo", "hints", "hints")
# headline load: overall median at most this multiple of its lightest-load value
MEDIAN_LIMIT = 1.5


def fnum(v):
    if v in (None, "", "None"):
        return None
    return float(v)


def med(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def fmt(v, digits=1):
    if v is None:
        return "-"
    if v == float("inf"):
        return "inf"
    if abs(v) >= 1000:
        return "%d" % round(v)
    return ("%." + str(digits) + "f") % v


def load_rows(name):
    rows = []
    for path in sorted(glob.glob(os.path.join(HERE, "results", "gen*", name))):
        with open(path) as f:
            rows.extend(csv.DictReader(f))
    return rows


def load_cards():
    cards = {}
    for path in sorted(glob.glob(os.path.join(HERE, "policies", "p*.md"))):
        card = {"file": os.path.relpath(path, HERE)}
        for line in open(path):
            m = re.match(r"^- (\w+): (.*)$", line.strip())
            if m:
                card[m.group(1)] = m.group(2).strip()
        if "config" in card:
            cards[card["config"]] = card
            # variants probed under one card (generation 20 on) share its id
            # and status
            for v in filter(None, (x.strip() for x in card.get("variants", "").split(","))):
                cards[v] = dict(card, config=v, variant_of=card["config"])
    return cards


def load_workloads():
    out = {}
    for path in sorted(glob.glob(os.path.join(HERE, "workloads", "w*.json"))):
        s = specs.load(path)
        s["_file"] = os.path.relpath(path, HERE)
        out[s["id"]] = s
    return out


def latest(rows):
    """Keeps, for each (workload, policy, mode, build), only the latest generation."""
    newest = {}
    for r in rows:
        key = (r["workload"], r["policy"], r["mode"], r["build"])
        newest[key] = max(newest.get(key, -1), int(r["gen"]))
    return [r for r in rows if int(r["gen"]) ==
            newest[(r["workload"], r["policy"], r["mode"], r["build"])]]


def sweeps(rows, min_levels=3):
    """Like latest(), for load curves: for each (workload, policy, mode, build),
    the latest generation that measured at least min_levels loads, else the
    latest generation, so that a re-measurement at the headline alone (the
    convergence generations) does not hide an earlier full sweep."""
    levels = {}
    for r in rows:
        k = (r["workload"], r["policy"], r["mode"], r["build"])
        levels.setdefault((k, int(r["gen"])), set()).add(r["load_rps"])
    pick = {}
    for (k, g), ls in levels.items():
        pick[k] = max(pick.get(k, (False, -1)), (len(ls) >= min_levels, g))
    return [r for r in rows if int(r["gen"]) ==
            pick[(r["workload"], r["policy"], r["mode"], r["build"])][1]]


def index(rows, metric_rows=True):
    """(workload, policy, mode, build, load, group) -> list of rows over repeats."""
    idx = {}
    for r in rows:
        if metric_rows and r.get("failed") == "1":
            continue
        key = (r["workload"], r["policy"], r["mode"], r["build"], int(r["load_rps"]),
               r.get("group", ""))
        idx.setdefault(key, []).append(r)
    return idx


def headline_load(idx, wid, loads):
    """The busiest load level the baseline handles without overload."""
    base = [(l, idx.get((wid,) + BASELINE + (l, "all"), [])) for l in loads]
    base = [(l, rs) for l, rs in base if rs]
    if not base:
        return None
    p50_low = med([fnum(r["p50"]) for r in base[0][1]])
    best = None
    for l, rs in base:
        ok = (med([fnum(r["resp_rps"]) / max(fnum(r["sent_rps"]), 1) for r in rs]) >= 0.99
              and med([fnum(r["adherence"]) for r in rs]) >= 99.0
              and med([fnum(r["p50"]) for r in rs]) <= MEDIAN_LIMIT * p50_low)
        if ok:
            best = l
    return best


def metric(idx, wid, combo, load, group, field):
    rs = idx.get((wid,) + combo + (load, group), [])
    # rows from before a column existed (e.g. qwait_p99 before gen 4) count as missing
    return med([fnum(r.get(field)) for r in rs]), len(rs)


def spread(idx, wid, combo, load, group, field):
    vals = [fnum(r[field]) for r in idx.get((wid,) + combo + (load, group), [])]
    vals = [v for v in vals if v is not None]
    return (min(vals), max(vals)) if len(vals) > 1 else None


def leaderboard(rows, crows, cards, workloads):
    sidx = index(sweeps(rows))
    rows, crows = latest(rows), latest(crows)
    idx, cidx = index(rows), index(crows, metric_rows=False)
    combos = sorted({(r["policy"], r["mode"], r["build"]) for r in rows},
                    key=lambda c: (c[2] != "hints", c[1] != "hints", c[0]))
    out = ["# Leaderboard", "",
           "Generated by `summarize.py` from `results/gen*/`; do not edit by hand.",
           "Scores are the workload's score kind and percentile at its headline load "
           "(see README.md), median over repeats, in microseconds; lower is better.",
           "Mode `ignore` means the server did not apply hints; build `stock` is "
           "Caladan with hint support compiled out.", ""]

    out += ["## Policies", "", "| Policy | Config name | Gen | Status | Changed from previous |",
            "|---|---|---|---|---|"]
    for name, c in sorted(cards.items(), key=lambda kv: kv[1].get("id", "")):
        out.append("| [%s](%s) | `%s` | %s | %s | %s |" % (
            c.get("id", "?"), c["file"], name, c.get("generation", "?"),
            c.get("status", "?"), c.get("changed_from_previous", "")))
    out.append("")

    svgs = make_plots(idx, cards, workloads, sidx)
    out += ["## Progress", "",
            "![Score of every policy on every workload, as change from fifo]"
            "(plots/scores.svg)", "",
            "![Each candidate against the champion it faced](plots/generations.svg)", ""]

    superseded = [w for w, s in sorted(workloads.items()) if s.get("status") == "superseded"]
    for wid, s in sorted(workloads.items(), key=lambda kv: wnum(kv[0])):
        if not any(r["workload"] == wid for r in rows) or wid in superseded:
            continue
        sk, sp = s["score"]["kind"], s["score"]["percentile"]
        loads = s["load_rps"]
        head = headline_load(idx, wid, loads)
        out += ["## %s: %s" % (wid, s["title"]), "",
                "[%s](%s). %s" % (s["_file"], s["_file"], s["description"]), "",
                "Score: `%s` %s. Headline load: %s req/s." % (
                    sk, sp, "{:,}".format(head) if head else "not determined "
                    "(no baseline fifo/hints data)"), ""]
        if "%s-load.svg" % wid in svgs:
            out += ["![%s %s by offered load on %s](plots/%s-load.svg)" % (sk, sp, wid, wid),
                    ""]
        if "%s-wait.svg" % wid in svgs:
            out += ["![%s %s and its runqueue wait at the headline load on %s]"
                    "(plots/%s-wait.svg)" % (sk, sp, wid, wid), ""]
        if head:
            others = [k["name"] for k in s["kinds"] if k["name"] != sk]
            hdr = ("| Policy | Mode | Build | Score (%s %s) | vs fifo | %s deadline met %% | "
                   % (sk, sp, sk) + "".join("%s p99 | " % o for o in others) +
                   "Throughput (req/s) | HIGH wait (µs) | NORMAL wait (µs) | Repeats | Gen |")
            out += [hdr, "|" + "---|" * (hdr.count("|") - 1)]
            base_score, _ = metric(idx, wid, BASELINE, head, "kind:" + sk, sp)
            scored = []
            for combo in combos:
                sc, n = metric(idx, wid, combo, head, "kind:" + sk, sp)
                if n == 0:
                    continue
                scored.append((sc, combo))
                dl, _ = metric(idx, wid, combo, head, "kind:" + sk, "deadline_met")
                oth = [metric(idx, wid, combo, head, "kind:" + o, "p99")[0] for o in others]
                thr, _ = metric(idx, wid, combo, head, "all", "resp_rps")
                wh, _ = metric(cidx, wid, combo, head, "", "wait_us_high")
                wn, _ = metric(cidx, wid, combo, head, "", "wait_us_normal")
                sprd = spread(idx, wid, combo, head, "kind:" + sk, sp)
                gen = max(int(r["gen"]) for r in rows if r["workload"] == wid and
                          (r["policy"], r["mode"], r["build"]) == combo)
                rel = ("%+.0f%%" % (100 * (sc / base_score - 1))
                       if sc is not None and base_score and sc != float("inf") else "-")
                score_cell = fmt(sc) + (" (%s–%s)" % (fmt(sprd[0]), fmt(sprd[1]))
                                        if sprd else "")
                cells = ([(cards.get(combo[0], {}).get("id", "") + " " + combo[0]).strip(),
                          combo[1], combo[2], score_cell, rel, fmt(dl, 2)] +
                         [fmt(v) for v in oth] +
                         [fmt(thr), fmt(wh, 2), fmt(wn, 2), str(n), str(gen)])
                out.append("| " + " | ".join(cells) + " |")
            best = min((x for x in scored if x[1][1] == "hints" and x[0] is not None),
                       default=None)
            if best:
                out += ["", "Best with hints applied: **%s** (%s µs)." % (
                    best[1][0], fmt(best[0]))]
            out.append("")
        # score by load level
        hdr = "| Policy | Mode | Build | " + " | ".join("{:,}".format(l) for l in loads) + " |"
        out += ["%s %s by offered load (req/s):" % (sk, sp), "", hdr,
                "|" + "---|" * (len(loads) + 3)]
        for combo in combos:
            vals = [metric(idx, wid, combo, l, "kind:" + sk, sp) for l in loads]
            if not any(n for _, n in vals):
                continue
            out.append("| %s | %s | %s | %s |" % (combo + (" | ".join(
                fmt(v) if n else "" for v, n in vals),)))
        out.append("")
    if superseded:
        out += ["Superseded workloads (kept with their results, not scored): " +
                ", ".join(superseded) + ".", ""]
    return "\n".join(out) + "\n", svgs


def wnum(wid):
    """Workload ids in numeric order: w2 < w4 < w4b < w10."""
    return (int(wid[1:].rstrip("abcdefghij")), wid)


def card_num(c):
    return int(str(c.get("id", "p999"))[1:] or 999)


def make_plots(idx, cards, workloads, sidx=None):
    """The leaderboard's plots, as {file name: SVG text}; load curves come from
    sidx (see sweeps()) when given."""
    sidx = sidx or idx
    colors = plots.Colors(cards)
    combo = lambda p: (p, "hints", "hints")
    live = sorted((w for w, s in workloads.items() if s.get("status") != "superseded"),
                  key=wnum)
    heads = {w: headline_load(idx, w, workloads[w]["load_rps"]) for w in live}

    def score(policy, wid):
        s, head = workloads[wid], heads[wid]
        if not head:
            return None
        v, n = metric(idx, wid, combo(policy), head, "kind:" + s["score"]["kind"],
                      s["score"]["percentile"])
        return v if n and v is not None and math.isfinite(v) else None

    acc = [c for c in cards.values() if c.get("status") == "accepted"]
    champ = max(acc, key=lambda c: (int(c.get("generation", 0)), c.get("id")))["config"] \
        if acc else "prio"
    svgs = {}

    # every policy on every scored workload, as change from fifo
    # every kept policy on every workload, in µs: the score at the headline
    # load (w0: one level below it, where the overhead rule measures every
    # policy); rejected and unbuilt policies are left out
    def level(wid):
        h = heads[wid]
        if wid == "w0" and h:
            return max([l for l in workloads[wid]["load_rps"] if l < h], default=h)
        return h

    def at(policy, wid, group, field):
        l = level(wid)
        if not l:
            return None
        v, n = metric(idx, wid, combo(policy), l, group, field)
        return v if n and v is not None and math.isfinite(v) else None

    def val(policy, wid):
        s = workloads[wid]
        return at(policy, wid, "kind:" + s["score"]["kind"], s["score"]["percentile"])

    def dominated(policy, wid):
        """Another policy measured here is better beyond noise on something
        (p99 more than 6% lower, or a kind's deadline-met more than 1 point
        higher) and worse beyond noise on nothing (judge.py's win rule)."""
        allp = sorted({k[1] for k in idx if k[0] == wid and k[2:4] == ("hints", "hints")})
        sc = {p: val(p, wid) for p in allp}
        sc = {p: v for p, v in sc.items() if v is not None}
        if policy not in sc:
            return False
        kinds = [k["name"] for k in workloads[wid]["kinds"] if k.get("deadline_us", 0) > 0]
        met = {(p, k): at(p, wid, "kind:" + k, "deadline_met") for p in sc for k in kinds}
        for q in sc:
            if q == policy:
                continue
            pairs = [(met[(q, k)], met[(policy, k)]) for k in kinds
                     if met[(q, k)] is not None and met[(policy, k)] is not None]
            worse = sc[q] > 1.06 * sc[policy] or any(a < b - 1.0 for a, b in pairs)
            better = sc[q] * 1.06 < sc[policy] or any(a > b + 1.0 for a, b in pairs)
            if better and not worse:
                return True
        return False

    keep_rows = ["fifo"] + [c["config"] for c in sorted(cards.values(), key=card_num)
                            if c["config"] != "fifo"
                            and c.get("status") not in ("rejected", "not built")]
    cols = [w for w in live if val("fifo", w)]
    rows = [p for p in keep_rows if any(val(p, w) for w in cols)]
    best = {}
    for w in cols:
        vs = [val(p, w) for p in rows]
        vs = [v for v in vs if v is not None]
        if vs:
            best[w] = min(vs)

    def fmt_us(v):
        return "%.0f" % v if v >= 1000 or v == int(v) else "%.1f" % v

    def cell(p, w):
        a, b = val(p, w), val("fifo", w)
        if not a or not b:
            return None
        return {"pct": 100 * (a / b - 1), "text": fmt_us(a), "best": best.get(w) == a,
                "mark": dominated(p, w)}

    def note(p):
        st = cards.get(p, {}).get("status", "")
        return " (champion)" if p == champ else (" (%s)" % st if st in (
            "candidate", "baseline") else "")

    def kind_note(w):
        k = workloads[w]["score"]["kind"]
        return "%s @%dk" % (k, level(w) // 1000) if w == "w0" else k
    if cols and rows:
        svgs["scores.svg"] = plots.score_map(
            "Every policy on every workload",
            "p99 latency (µs) of each workload's latency-critical kind (named under its id) at "
            "its headline load, median of 2 repeats; rejected policies left out.",
            ["%s %s" % (cards[p]["id"], p) for p in rows], cols,
            lambda r, c: cell(r.split(" ", 1)[1], c),
            lambda r: note(r.split(" ", 1)[1]), kind_note,
            "Outlined: the lowest p99 in the column. * = dominated: another policy is faster "
            "beyond noise or meets more deadlines (over 1 point) without being worse at either.")

    # each candidate against the champion it faced, on its generation's newest workload
    bars = []
    for c in sorted((c for c in cards.values() if c.get("status") not in ("baseline", "not built")
                     and not c.get("variant_of")), key=card_num):
        g = int(c.get("generation", 0))
        before = [x for x in acc if int(x.get("generation", 0)) < g]
        faced = max(before, key=lambda x: (int(x.get("generation", 0)), x.get("id")))[
            "config"] if before else "prio"
        ws = [w for w in live if int(workloads[w].get("generation", 0)) <= g]
        if not ws:
            continue
        wid = ws[-1]
        a, b = score(c["config"], wid), score(faced, wid)
        v = 100 * (a / b - 1) if a and b else None
        bars.append(("%s" % c["id"], c["config"], v, c.get("status", ""),
                     "%s vs %s" % (wid, cards.get(faced, {}).get("id", faced))))
    if bars:
        svgs["generations.svg"] = plots.generations(
            "Each candidate against the champion it faced",
            "Score on the workload that was newest in the candidate's generation, "
            "from the latest measurements.", bars, colors, -10)

    # score kind against offered load, per workload
    order = sorted({p for (w, p, m, b, l, g) in idx if m == "hints" and b == "hints"},
                   key=lambda p: (p != "fifo", p != "prio", card_num(cards.get(p, {}))))
    for wid in live:
        s = workloads[wid]
        sk, sp = s["score"]["kind"], s["score"]["percentile"]
        series = []
        for p in order:
            pts = []
            for l in s["load_rps"]:
                v, n = metric(sidx, wid, combo(p), l, "kind:" + sk, sp)
                if n and v is not None:
                    pts.append((l, v))
            if len(pts) >= 3:
                series.append((p, pts))
        svg = plots.load_curves(
            "%s: %s %s by offered load" % (wid, sk, sp),
            "Median of repeats; policies measured at three or more loads.",
            series, heads.get(wid), colors, "%s %s (µs)" % (sk, sp))
        if svg:
            svgs["%s-load.svg" % wid] = svg
        # score kind's p99 and its runqueue-wait p99 at the headline load
        head = heads.get(wid)
        wrows = []
        for p in order:
            if not head:
                break
            v, n = metric(idx, wid, combo(p), head, "kind:" + sk, sp)
            w, _ = metric(idx, wid, combo(p), head, "kind:" + sk, "qwait_p99")
            if n and v is not None and w is not None and math.isfinite(v):
                wrows.append((p, v, w))
        if wid != "w0" and len(wrows) >= 2:
            svgs["%s-wait.svg" % wid] = plots.wait_split(
                "%s: where the %s tail is spent, at %s" % (wid, sk, plots._klabel(head)),
                "Median of repeats at the headline load; runqueue wait is measured per "
                "request by the server (from gen 4).", wrows, colors, "%s %s" % (sk, sp))
    return svgs


def gen_tables(gen, rows, crows, workloads):
    rows = [r for r in rows if int(r["gen"]) == gen]
    crows = [r for r in crows if int(r["gen"]) == gen]
    idx, cidx = index(rows), index(crows, metric_rows=False)
    out = ["# Generation %d: measurement tables" % gen, "",
           "Generated by `summarize.py --gen %d`. Latencies in µs, medians over repeats; "
           "counters are from the server runtime (see README.md for definitions)." % gen, ""]
    for wid in sorted({r["workload"] for r in rows}):
        s = workloads[wid]
        loads = s["load_rps"]
        groups = ["all"] + ["kind:" + k["name"] for k in s["kinds"]]
        combos = sorted({(r["policy"], r["mode"], r["build"]) for r in rows
                         if r["workload"] == wid})
        out += ["## %s: %s" % (wid, s["title"]), ""]
        for combo in combos:
            out += ["### %s / %s / %s" % combo, "",
                    "| Load | Group | Resp/s | p50 | p90 | p99 | p99.9 | Deadline met % | "
                    "Queue wait p50 | Queue wait p99 |",
                    "|---|---|---|---|---|---|---|---|---|---|"]
            for l in loads:
                for g in groups:
                    rs = idx.get((wid,) + combo + (l, g))
                    if not rs:
                        continue
                    m = lambda f: med([fnum(r.get(f)) for r in rs])  # noqa: E731
                    out.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
                        "{:,}".format(l), g, fmt(m("resp_rps")), fmt(m("p50")),
                        fmt(m("p90")), fmt(m("p99")), fmt(m("p999")),
                        fmt(m("deadline_met"), 2), fmt(m("qwait_p50")), fmt(m("qwait_p99"))))
            out += ["", "| Load | Wait HIGH | Wait NORMAL | Wait LOW | Wait helper | "
                    "Mean depth | Inversion rate | Late at pick | HIGH/LOW stolen rate | "
                    "Hinted overflow | Overflow | CPU cores |",
                    "|---|---|---|---|---|---|---|---|---|---|---|---|"]
            for l in loads:
                rs = cidx.get((wid,) + combo + (l, ""))
                if not rs:
                    continue
                m = lambda f: med([fnum(r[f]) for r in rs])  # noqa: E731
                out.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
                    "{:,}".format(l), fmt(m("wait_us_high"), 2), fmt(m("wait_us_normal"), 2),
                    fmt(m("wait_us_low"), 2), fmt(m("wait_us_softirq"), 2),
                    fmt(m("mean_depth"), 2), fmt(m("inversion_rate"), 4),
                    fmt(m("late_at_pick_rate"), 4), fmt(m("hinted_stolen_rate"), 3),
                    fmt(m("hinted_overflow"), 0), fmt(m("rq_overflow"), 0),
                    fmt(m("cpu_cores"), 2)))
            out.append("")
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gen", type=int, help="also write results/gen<N>/tables.md")
    args = ap.parse_args()
    rows, crows = load_rows("summary.csv"), load_rows("counters.csv")
    cards, workloads = load_cards(), load_workloads()
    text, svgs = leaderboard(rows, crows, cards, workloads)
    with open(os.path.join(HERE, "LEADERBOARD.md"), "w") as f:
        f.write(text)
    os.makedirs(os.path.join(HERE, "plots"), exist_ok=True)
    for name, svg in svgs.items():
        with open(os.path.join(HERE, "plots", name), "w") as f:
            f.write(svg)
    print("wrote LEADERBOARD.md and %d plots" % len(svgs))
    if args.gen is not None:
        path = os.path.join(HERE, "results", "gen%d" % args.gen, "tables.md")
        with open(path, "w") as f:
            f.write(gen_tables(args.gen, rows, crows, workloads))
        print("wrote", os.path.relpath(path, HERE))


if __name__ == "__main__":
    main()
