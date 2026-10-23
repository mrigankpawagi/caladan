#!/usr/bin/env python3
"""Builds LEADERBOARD.md and plots/ from results/e<epoch>/*/summary.csv.

For every workload: the headline load, and for each policy measured there
(latest session), each kind's p99 and p99.9 in microseconds, the p99 as a
multiple of the kind's deadline where it has one, and the throughput. Nothing
is combined into a score (DESIGN.md section 2). Plots: one heatmap of the
most stressed deadline kind's p99 / deadline per policy and workload, and per
workload a curve of that kind's p99 against offered load.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import judge as J  # noqa: E402
from lib import plots  # noqa: E402


def fmt(v, digits=1):
    if v is None:
        return "-"
    return ("%.0f" if v >= 100 else "%%.%df" % digits) % v


def latest_session(rows, wid, pol, load):
    ses = J.sessions(rows, wid, (pol,), load)
    return ses[-1] if ses else None


def main():
    rows, workloads, cards = J.load_rows(), J.load_workloads(), J.load_cards()
    champ = J.champion(cards)
    ids = J.live(workloads)
    heads = {w: J.headline_load(rows, workloads[w]) for w in ids}
    shown = [p for p in sorted(cards, key=lambda p: J.wnum("w" + cards[p]["id"][1:]))
             if cards[p].get("status") not in ("rejected", "not built")]
    out = ["# Leaderboard", "",
           "Protocol %s, epoch %d (DESIGN.md). Champion: **%s**. Every number is the median "
           "of %d repeats at the workload's headline load, from the latest session in which "
           "the policy ran there; a deadline kind's p99 is also given as a multiple of its "
           "deadline (x0.80 = 20%% to spare, x1.50 = 50%% over). Rejected policies are left "
           "out; their cards and data remain." % (
               PROTO["version"], PROTO["epoch"], champ, PROTO["repeats"]), ""]

    # win table
    class A:
        policy = champ
    table = J.wins(A, quiet=True)
    out += ["## Does anything improve on the champion?", "",
            "| Workload | Headline (req/s) | Session | Result |", "|---|---|---|---|"]
    for wid, head, ses, what in table:
        out.append("| %s | %s | %s | %s |" % (wid, head or "-", ses or "-", what))
    out.append("")

    # heatmap data: most stressed deadline kind's p99 / deadline
    def worst_ratio(wid, pol):
        s, head = workloads[wid], heads[wid]
        if not head:
            return None
        ses = latest_session(rows, wid, pol, head)
        if not ses:
            return None
        best = None
        for k in s["kinds"]:
            d = k.get("deadline_us", 0)
            if d <= 0:
                continue
            p = J.med(J.vals(J.rows_of(rows, wid, pol, head, "kind:" + k["name"], ses), "p99"))
            if p is not None and (best is None or p / d > best[0]):
                best = (p / d, k["name"])
        return best

    cols = [w for w in ids if w != "w0" and heads[w]]
    hrows = [p for p in shown if any(worst_ratio(w, p) for w in cols)]
    colors = plots.Colors(cards)
    svgs = {}
    if cols and hrows:
        mins = {w: min(worst_ratio(w, p)[0] for p in hrows if worst_ratio(w, p)) for w in cols}

        def cell(r, c):
            p = r.split(" ", 1)[1]
            v = worst_ratio(c, p)
            if not v:
                return None
            return {"pct": 100 * (v[0] - 1), "text": "%.2f" % v[0], "best": v[0] == mins[c]}

        def col_note(w):
            s = workloads[w]
            ks = [k["name"] for k in s["kinds"] if k.get("deadline_us", 0) > 0]
            return ks[0] if len(ks) == 1 else "%d kinds" % len(ks)
        svgs["ratio.svg"] = plots.score_map(
            "The most stressed deadline kind, per policy and workload",
            "p99 as a multiple of that kind's deadline at the headline load (median of %d "
            "repeats); 1.00 means the p99 lands on the deadline." % PROTO["repeats"],
            ["%s %s" % (cards[p]["id"], p) for p in hrows], cols, cell,
            lambda r: " (champion)" if r.split(" ", 1)[1] == champ else "", col_note,
            key=((-1, "p99 far below the deadline"), (-0.5, "half the deadline"),
                 (0, "p99 = deadline"), (0.5, "1.5x"), (1, "2x the deadline or worse")),
            best_label="lowest in its column",
            cell_note="Each cell: p99 / deadline of the kind whose p99 is nearest to or "
                      "furthest over its deadline under that policy. Lower is better.")
    out += ["## Plots", "", "![p99 / deadline of the most stressed kind](plots/ratio.svg)", ""]

    for wid in ids:
        s, head = workloads[wid], heads[wid]
        out += ["## %s: %s" % (wid, s["title"]), "", "[%s](%s). %s" % (s["_file"], s["_file"],
                                                                        s["description"]), ""]
        if not head:
            out += ["No headline load yet.", ""]
            continue
        out.append("Headline load: %s req/s." % format(head, ","))
        dk = [k for k in s["kinds"] if k.get("deadline_us", 0) > 0]
        out += ["", "| Policy | Session | " + " | ".join(
            "%s p99 / p99.9%s" % (k["name"], " (x of %d us)" % k["deadline_us"]
                                  if k.get("deadline_us", 0) > 0 else "") for k in s["kinds"])
            + " | Responses/s |", "|---|---|" + "---|" * len(s["kinds"]) + "---|"]
        pols = [p for p in ["fifo"] + shown if p != "fifo" or True]
        seen = set()
        for p in ["fifo"] + [x for x in shown if x != "fifo"]:
            if p in seen:
                continue
            seen.add(p)
            ses = latest_session(rows, wid, p, head)
            if not ses:
                continue
            cells = []
            for k in s["kinds"]:
                rs = J.rows_of(rows, wid, p, head, "kind:" + k["name"], ses)
                p99, p999 = J.med(J.vals(rs, "p99")), J.med(J.vals(rs, "p999"))
                d = k.get("deadline_us", 0)
                cells.append("%s / %s%s" % (fmt(p99), fmt(p999), " (x%.2f)" % (p99 / d)
                                            if d > 0 and p99 else ""))
            resp = J.med(J.vals(J.rows_of(rows, wid, p, head, "all", ses), "resp_rps"))
            out.append("| %s%s | %s | %s | %s |" % (
                p, " (champion)" if p == champ else "", ses, " | ".join(cells),
                fmt(resp, 0) if resp else "-"))
        out.append("")
        # curve: the most stressed deadline kind's p99 (under fifo) by offered load
        if dk:
            kind = max(dk, key=lambda k: (J.med(J.vals(J.rows_of(rows, wid, "fifo", head,
                                                                 "kind:" + k["name"]), "p99"))
                                          or 0) / k["deadline_us"])
            series = []
            for p in ["fifo"] + [x for x in shown if x != "fifo"]:
                pts = []
                for l in s["load_rps"]:
                    rs = J.rows_of(rows, wid, p, l, "kind:" + kind["name"])
                    v = J.med(J.vals(rs, "p99"))
                    if v is not None:
                        pts.append((l, v))
                if len(pts) >= 3:
                    series.append((p, pts))
            if series:
                svg = plots.load_curves(
                    "%s: %s p99 by offered load" % (wid, kind["name"]),
                    "Median of repeats, every session; the deadline is %d us." % kind["deadline_us"],
                    series, head, colors, "%s p99 (µs)" % kind["name"])
                if svg:
                    svgs["%s-load.svg" % wid] = svg
                    out += ["![%s p99 by offered load on %s](plots/%s-load.svg)" % (
                        kind["name"], wid, wid), ""]
    os.makedirs(os.path.join(HERE, "plots"), exist_ok=True)
    for name, svg in svgs.items():
        open(os.path.join(HERE, "plots", name), "w").write(svg)
    open(os.path.join(HERE, "LEADERBOARD.md"), "w").write("\n".join(out))
    print("wrote LEADERBOARD.md and %d plots" % len(svgs))


PROTO = J.PROTO

if __name__ == "__main__":
    main()
