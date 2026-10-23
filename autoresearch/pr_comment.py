#!/usr/bin/env python3
"""Prints the Markdown of a generation's PR comment, built from the data.

  ./pr_comment.py --gen N --workload wK --sha <record commit> [--verdict file] [--notes file]

The comment has the newest workload's headline table (every policy measured
there in its latest session: each kind's p99 / p99.9, the p99 as a multiple of
the deadline, throughput), the judge's verdict if given, the two plots at the
record commit, and the orchestrator's notes. Numbers come from judge.py's
readers, never typed by hand.
"""

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import judge as J  # noqa: E402

RAW = "https://raw.githubusercontent.com/mrigankpawagi/caladan/%s/autoresearch/plots/%s"


def fmt(v):
    if v is None:
        return "-"
    return "%.0f" % v if v >= 100 else "%.1f" % v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gen", type=int, required=True)
    ap.add_argument("--workload", required=True)
    ap.add_argument("--sha", required=True)
    ap.add_argument("--verdict", help="file with judge.py's output")
    ap.add_argument("--notes", help="file with the orchestrator's notes (Markdown)")
    args = ap.parse_args()
    rows, workloads, cards = J.load_rows(), J.load_workloads(), J.load_cards()
    s, champ = workloads[args.workload], J.champion(cards)
    head = J.headline_load(rows, s)
    out = ["## Generation %d: %s (%s)" % (args.gen, args.workload, s["title"]), "",
           s["description"], ""]
    if head:
        out += ["Headline load %s req/s (%d repeats; range in brackets; a deadline kind's "
                "p99 also as a multiple of its deadline)." % (format(head, ","),
                                                             J.PROTO["repeats"]), "",
                "| Policy | Session | " + " | ".join(
                    "%s p99 / p99.9%s" % (k["name"], " (×%d µs)" % k["deadline_us"]
                                          if k.get("deadline_us", 0) > 0 else "")
                    for k in s["kinds"]) + " | Resp/s |",
                "|---|---|" + "---|" * len(s["kinds"]) + "---|"]
        pols = sorted({r["policy"] for r in rows if r["workload"] == args.workload},
                      key=lambda p: (p != "fifo", p != "prio", cards.get(p, {}).get("id", "")))
        for p in pols:
            ses = J.sessions(rows, args.workload, (p,), head)
            if not ses:
                continue
            cells = []
            for k in s["kinds"]:
                rs = J.rows_of(rows, args.workload, p, head, "kind:" + k["name"], ses[-1])
                p99s, p999 = J.vals(rs, "p99"), J.med(J.vals(rs, "p999"))
                d = k.get("deadline_us", 0)
                cells.append("%s [%s–%s] / %s%s" % (
                    fmt(J.med(p99s)), fmt(min(p99s)), fmt(max(p99s)), fmt(p999),
                    " (×%.2f)" % (J.med(p99s) / d) if d > 0 and p99s else "") if p99s else "-")
            resp = J.med(J.vals(J.rows_of(rows, args.workload, p, head, "all", ses[-1]),
                                "resp_rps"))
            out.append("| %s%s | %s | %s | %s |" % (
                p, " (champion)" if p == champ else "", ses[-1], " | ".join(cells),
                format(int(resp), ",") if resp else "-"))
        out.append("")
    if args.verdict:
        out += ["<details><summary>Judge</summary>", "", "```",
                open(args.verdict).read().rstrip(), "```", "", "</details>", ""]
    if args.notes:
        out += [open(args.notes).read().rstrip(), ""]
    out += ["![p99 / deadline of the most stressed kind, per policy and workload](%s)" % (
        RAW % (args.sha, "ratio.svg")), ""]
    if os.path.exists(os.path.join(HERE, "plots", "%s-load.svg" % args.workload)):
        out += ["![%s: p99 by offered load](%s)" % (
            args.workload, RAW % (args.sha, "%s-load.svg" % args.workload)), ""]
    out += ["Data: `autoresearch/results/e%d/gen%d/` at %s. "
            "🤖 Generated with [Claude Code](https://claude.com/claude-code)" % (
                J.PROTO["epoch"], args.gen, args.sha[:10])]
    print("\n".join(out))


if __name__ == "__main__":
    main()
