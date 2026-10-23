#!/usr/bin/env python3
"""Applies DESIGN.md's rules to the measured results (results/e<epoch>/).

  ./judge.py gate --workload w2        is the proposed workload worth keeping?
  ./judge.py accept --policy sjf       does the candidate replace the champion?
  ./judge.py wins [--policy p]         on which workloads does nothing improve on it?
  ./judge.py champion                  the current champion
  ./judge.py plan                      what eval_policy.sh must run

Every number is the median of the repeats, with the min-max range. "A is
better than B on a kind" means A's median p99 is lower by more than
protocol.json's change_pct and the two ranges do not overlap; "worse" is the
mirror image. The judge only compares rows from one session (one run.py
invocation, in which the compared policies alternated), never across sessions.

Headline load: the highest offered load at which fifo delivers at least 99% of
it, the client's adherence is at least 99%, and fifo's overall median latency is
at most 1.5x its median at the lightest level.
"""

import argparse
import csv
import glob
import json
import os
import re
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from lib import spec as specs  # noqa: E402

PROTO = json.load(open(os.path.join(HERE, "protocol.json")))
PCT = PROTO["change_pct"] / 100.0
RESULTS = os.path.join(HERE, "results", "e%d" % PROTO["epoch"])


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def med(xs):
    return statistics.median(xs) if xs else None


def wnum(wid):
    return (int(wid[1:].rstrip("abcdefghij")), wid)


def load_rows(gen=None):
    pat = "gen%d" % gen if gen is not None else "gen*"
    rows = []
    for f in sorted(glob.glob(os.path.join(RESULTS, pat, "summary.csv"))):
        for r in csv.DictReader(open(f)):
            if r.get("failed") == "1" or r.get("mode") != "hints":
                continue
            rows.append(r)
    return rows


def load_workloads():
    out = {}
    for path in sorted(glob.glob(os.path.join(HERE, "workloads", "w*.json"))):
        s = specs.load(path)
        s["_file"] = os.path.relpath(path, HERE)
        out[s["id"]] = s
    return out


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
    return cards


def champion(cards):
    acc = [c for c in cards.values() if c.get("status") == "accepted"]
    if acc:
        return max(acc, key=lambda c: (int(c.get("generation", 0)), c.get("id")))["config"]
    return "prio"


def live(workloads):
    return sorted((w for w, s in workloads.items() if s.get("status") != "superseded"),
                  key=wnum)


def rows_of(rows, wid, pol, load, group, session=None, build="hints"):
    return [r for r in rows if r["workload"] == wid and r["policy"] == pol
            and int(r["load_rps"]) == load and r["group"] == group and r["build"] == build
            and (session is None or r["session"] == session)]


def vals(rs, field):
    return [v for v in (num(r.get(field)) for r in rs) if v is not None]


def headline_load(rows, s):
    base, head = None, None
    for l in s["load_rps"]:
        rs = rows_of(rows, s["id"], "fifo", l, "all")
        if not rs:
            break
        resp, adh, p50 = (med(vals(rs, f)) for f in ("resp_rps", "adherence", "p50"))
        if base is None:
            base = p50
        if resp >= 0.99 * l and adh >= 99 and p50 <= 1.5 * base:
            head = l
        else:
            break
    return head


def sessions(rows, wid, pols, load):
    """Sessions in which every policy in pols has rows at load, newest last."""
    have = {}
    for r in rows:
        if r["workload"] == wid and int(r["load_rps"]) == load and r["group"] == "all" \
                and r["policy"] in pols:
            have.setdefault(r["session"], set()).add(r["policy"])
    return sorted(s for s, ps in have.items() if ps >= set(pols))


def better(va, vb):
    """A's p99s are lower than B's beyond noise."""
    return bool(va and vb) and med(va) < (1 - PCT) * med(vb) and max(va) < min(vb)


def worse(va, vb):
    return bool(va and vb) and med(va) > (1 + PCT) * med(vb) and min(va) > max(vb)


def compare(rows, s, load, a, b, session):
    """Per kind: (name, deadline_us, p99s of a, p99s of b, verdict on p99, verdict on
    p99.9), where a verdict is 'better', 'worse' or 'same'."""
    out = []
    for k in s["kinds"]:
        ra = rows_of(rows, s["id"], a, load, "kind:" + k["name"], session)
        rb = rows_of(rows, s["id"], b, load, "kind:" + k["name"], session)
        v = {}
        for f in ("p99", "p999"):
            xa, xb = vals(ra, f), vals(rb, f)
            v[f] = "better" if better(xa, xb) else "worse" if worse(xa, xb) else "same"
        out.append((k["name"], k.get("deadline_us", 0), vals(ra, "p99"), vals(rb, "p99"),
                    v["p99"], v["p999"]))
    return out


def fmt(xs):
    if not xs:
        return "-"
    return "%g (%g-%g)" % (med(xs), min(xs), max(xs)) if len(xs) > 1 else "%g" % xs[0]


def improves(cmp):
    """A improves on B: some deadline kind better, no kind worse (p99 or p99.9)."""
    return any(d and v == "better" for _, d, _, _, v, _ in cmp) and not regresses(cmp)


def regresses(cmp):
    return any(v == "worse" or v9 == "worse" for _, _, _, _, v, v9 in cmp)


def gate(args):
    rows, workloads, cards = load_rows(), load_workloads(), load_cards()
    s, champ = workloads[args.workload], champion(cards)
    head = headline_load(rows, s)
    print("workload %s, champion %s, headline load %s" % (s["id"], champ, head))
    if not head or head == s["load_rps"][0]:
        print("FAIL (1): no headline load above the lightest level")
        return 1
    ok = True
    for pol, factor, rule in (("fifo", 1.0, "2"), (champ, 0.8, "3")):
        over = []
        for k in s["kinds"]:
            d = k.get("deadline_us", 0)
            if d <= 0:
                continue
            p99 = med(vals(rows_of(rows, s["id"], pol, head, "kind:" + k["name"]), "p99"))
            if p99 is None:
                print("FAIL: no %s rows for %s at %d" % (pol, k["name"], head))
                return 1
            print("  %s %s p99 %g = %.2f x deadline" % (pol, k["name"], p99, p99 / d))
            if p99 > factor * d:
                over.append(k["name"])
        if over:
            print("pass (%s): under %s, %s above %.1fx the deadline" % (
                rule, pol, ", ".join(over), factor))
        else:
            print("FAIL (%s): under %s no deadline kind is above %.1fx its deadline" % (
                rule, pol, factor))
            ok = False
    print("GATE", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def accept(args):
    rows, workloads, cards = load_rows(), load_workloads(), load_cards()
    new, champ = args.policy, args.against or champion(cards)
    ids = live(workloads)
    newest = args.newest or [w for w in ids if w != "w0"][-1]
    ok = True
    print("policy %s vs champion %s; newest workload %s; %d repeats, change > %d%%" % (
        new, champ, newest, PROTO["repeats"], PROTO["change_pct"]))
    for wid in ids:
        s = workloads[wid]
        head = headline_load(rows, s)
        if not head:
            print("  %s: no headline load -> FAIL" % wid)
            ok = False
            continue
        if wid == "w0":
            # overhead: against fifo, one level below the headline and at the top
            below = max([l for l in s["load_rps"] if l < head], default=head)
            top = s["load_rps"][-1]
            ses = sessions(rows, wid, (new, "fifo"), below)
            if not ses:
                print("  w0: no session with %s and fifo -> FAIL" % new)
                ok = False
                continue
            pa = vals(rows_of(rows, wid, new, below, "all", ses[-1]), "p99")
            pb = vals(rows_of(rows, wid, "fifo", below, "all", ses[-1]), "p99")
            ta = vals(rows_of(rows, wid, new, top, "all", ses[-1]), "resp_rps")
            tb = vals(rows_of(rows, wid, "fifo", top, "all", ses[-1]), "resp_rps")
            good = (pa and pb and med(pa) <= (1 + PCT) * med(pb)
                    and ta and tb and med(ta) >= 0.99 * med(tb))
            print("  w0 (overhead, session %s): p99 at %d %s vs fifo %s; throughput at %d %s "
                  "vs %s -> %s" % (ses[-1], below, fmt(pa), fmt(pb), top, fmt(ta), fmt(tb),
                                  "ok" if good else "FAIL (3)"))
            ok &= bool(good)
            continue
        ses = sessions(rows, wid, (new, champ), head)
        if not ses:
            print("  %s: no session with both %s and %s at %d -> FAIL" % (wid, new, champ, head))
            ok = False
            continue
        cmp = compare(rows, s, head, new, champ, ses[-1])
        verdict = improves(cmp) if wid == newest else not regresses(cmp)
        print("  %s%s (session %s, %d req/s): %s" % (
            wid, " (newest)" if wid == newest else "", ses[-1], head,
            "ok" if verdict else "FAIL (%s)" % ("1" if wid == newest else "2")))
        for name, d, xa, xb, v, v9 in cmp:
            print("    %-10s p99 %s vs %s %s-> %s%s" % (
                name, fmt(xa), fmt(xb), ("(x%.2f vs x%.2f of %d us) " % (
                    med(xa) / d, med(xb) / d, d)) if d and xa and xb else "", v,
                "" if v9 == "same" else ", p99.9 %s" % v9))
        ok &= verdict
        for k in s["kinds"]:
            if k.get("hint", {}).get("class") != "low":
                continue
            for l in [x for x in s["load_rps"] if x <= head]:
                rs = rows_of(rows, wid, new, l, "kind:" + k["name"], ses[-1])
                frac = med([num(r["resp_rps"]) / max(num(r["sent_rps"]), 1) for r in rs])
                if frac is not None and frac < 0.9:
                    print("    %s answered %.1f%% at %d -> FAIL (4)" % (k["name"], 100 * frac, l))
                    ok = False
    print("ACCEPT" if ok else "REJECT")
    return 0 if ok else 1


def wins(args, quiet=False):
    """A policy holds a workload if, in the latest session where it ran at the
    headline load, no other policy improves on it (DESIGN.md section 3)."""
    rows, workloads, cards = load_rows(), load_workloads(), load_cards()
    pol = args.policy or champion(cards)
    held, lost, table = [], [], []
    for wid in live(workloads):
        s = workloads[wid]
        if wid == "w0":
            continue
        head = headline_load(rows, s)
        ses = sessions(rows, wid, (pol,), head) if head else []
        if not ses:
            table.append((wid, head, None, "no data"))
            lost.append(wid)
            continue
        others = sorted({r["policy"] for r in rows if r["workload"] == wid
                         and r["session"] == ses[-1] and r["policy"] != pol})
        beats = [o for o in others if improves(compare(rows, s, head, o, pol, ses[-1]))]
        table.append((wid, head, ses[-1], "HELD against %s" % ", ".join(others) if not beats
                      else "IMPROVED ON by %s" % ", ".join(beats)))
        (lost if beats else held).append(wid)
    if not quiet:
        for wid, head, ses, what in table:
            print("%-4s %8s %16s  %s" % (wid, head or "-", ses or "-", what))
        print("%s holds %d of %d workloads%s" % (pol, len(held), len(held) + len(lost),
                                                  ("; not held: " + " ".join(lost)) if lost else ""))
    return table


def plan(args):
    """One line per workload for eval_policy.sh: <id> <file> <levels> <with>,
    where <with> is 'fifo' for w0 and 'champion' otherwise."""
    rows, workloads = load_rows(), load_workloads()
    ids = live(workloads)
    newest = [w for w in ids if w != "w0"][-1]
    for wid in ids:
        s = workloads[wid]
        head = headline_load(rows, s)
        if not head:
            continue
        if wid == "w0":
            below = max([l for l in s["load_rps"] if l < head], default=head)
            print(wid, s["_file"], "%d,%d" % (below, s["load_rps"][-1]), "fifo")
        elif wid == newest:
            print(wid, s["_file"], ",".join(str(l) for l in s["load_rps"]), "champion")
        else:
            print(wid, s["_file"], str(head), "champion")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gate"); g.add_argument("--workload", required=True)
    a = sub.add_parser("accept"); a.add_argument("--policy", required=True)
    a.add_argument("--against", help="compare with this policy instead of the champion")
    a.add_argument("--newest", help="the newest workload id (default: highest id)")
    w = sub.add_parser("wins"); w.add_argument("--policy")
    sub.add_parser("champion")
    sub.add_parser("plan")
    args = ap.parse_args()
    if args.cmd == "champion":
        print(champion(load_cards()))
        return 0
    if args.cmd == "wins":
        return 0 if all("HELD" in t[3] for t in wins(args)) else 1
    return {"gate": gate, "accept": accept, "plan": plan}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
