#!/usr/bin/env python3
"""Applies the generation protocol's decision rules to the measured results.

  ./judge.py gate --workload w2       is the new workload worth keeping?
  ./judge.py accept --policy edf      does the new policy beat the champion?
  ./judge.py champion                 which policy is the current champion?

The champion is the accepted policy with the highest generation, or the best
baseline policy (prio) if none has been accepted yet. Rules (README.md):

gate:   (1) the baseline (fifo with hints) has a headline load above the
            lightest level, i.e. the workload is not overloaded everywhere;
        (2) a FIFO penalty exists: fifo's score at the headline load is at
            least 1.5x its score at the lightest load;
        (3) headroom remains: the champion's score at the headline load is at
            least 1.3x its own score at the lightest load, or its deadline-met
            rate there is below 99%.
accept: (1) the newest workload's score improves on the champion's by at
            least 10% or 10 us;
        (2) no earlier workload (other than w0) is more than 10% worse;
        (3) other kinds' p99 at the headline load rise at most 25%;
        (4) LOW-hinted kinds answer at least 90% of their requests at every
            level up to the headline load;
        (5) on w0, p99 at the headline load is within the noise band of the
            champion's and throughput within 1%.
Exit status 0 means pass, 1 means fail; the numbers are always printed.
"""

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import summarize as S  # noqa: E402

NOISE = 0.06


def data():
    rows = S.latest(S.load_rows("summary.csv"))
    return S.index(rows), S.load_cards(), S.load_workloads()


def champion(cards):
    acc = [c for c in cards.values() if c.get("status") == "accepted"]
    if acc:
        return max(acc, key=lambda c: (int(c.get("generation", 0)), c.get("id")))["config"]
    return "prio"


def score(idx, s, policy, load):
    v, n = S.metric(idx, s["id"], (policy, "hints", "hints"), load,
                    "kind:" + s["score"]["kind"], s["score"]["percentile"])
    return v if n else None


def gate(args):
    idx, cards, workloads = data()
    s = workloads[args.workload]
    loads, champ = s["load_rps"], champion(cards)
    head = S.headline_load(idx, s["id"], loads)
    ok = True
    print("workload %s, champion %s, headline load %s" % (s["id"], champ, head))
    if not head or head == loads[0]:
        print("FAIL (1): no headline load above the lightest level (overloaded everywhere "
              "or no fifo data)")
        return 1
    f_lo, f_hi = score(idx, s, "fifo", loads[0]), score(idx, s, "fifo", head)
    c_lo, c_hi = score(idx, s, champ, loads[0]), score(idx, s, champ, head)
    dl, _ = S.metric(idx, s["id"], (champ, "hints", "hints"), head,
                     "kind:" + s["score"]["kind"], "deadline_met")
    print("fifo score: %s at %d, %s at headline" % (S.fmt(f_lo), loads[0], S.fmt(f_hi)))
    print("%s score: %s at %d, %s at headline, deadline met %s%%" % (
        champ, S.fmt(c_lo), loads[0], S.fmt(c_hi), S.fmt(dl, 2)))
    if None in (f_lo, f_hi, c_lo, c_hi):
        print("FAIL: missing measurements (need fifo and %s with hints)" % champ)
        return 1
    if f_hi < 1.5 * f_lo:
        print("FAIL (2): no FIFO penalty (%.2fx < 1.5x)" % (f_hi / f_lo)); ok = False
    else:
        print("pass (2): FIFO penalty %.2fx" % (f_hi / f_lo))
    if c_hi < 1.3 * c_lo and (dl is None or dl >= 99.0):
        print("FAIL (3): %s already near its unloaded score (%.2fx) and meets deadlines"
              % (champ, c_hi / c_lo)); ok = False
    else:
        print("pass (3): headroom (%s at %.2fx its unloaded score)" % (champ, c_hi / c_lo))
    print("GATE", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def accept(args):
    idx, cards, workloads = data()
    new, champ = args.policy, args.against or champion(cards)
    ids = sorted(workloads, key=lambda w: (int(w[1:].rstrip("abcdefghij")), w))
    newest = args.newest or [w for w in ids if workloads[w].get("status") != "superseded"][-1]
    ok = True
    print("policy %s vs champion %s; newest workload %s" % (new, champ, newest))
    for wid in ids:
        s = workloads[wid]
        head = S.headline_load(idx, wid, s["load_rps"])
        if not head:
            continue
        a, b = score(idx, s, new, head), score(idx, s, champ, head)
        if a is None or b is None:
            print("  %s: missing data (%s=%s, %s=%s)" % (wid, new, a, champ, b))
            if wid == newest or wid == "w0":
                ok = False
            continue
        rel = a / b - 1 if b else 0
        if wid == "w0":
            ta, _ = S.metric(idx, wid, (new, "hints", "hints"), head, "all", "resp_rps")
            tb, _ = S.metric(idx, wid, (champ, "hints", "hints"), head, "all", "resp_rps")
            good = rel <= NOISE and ta >= 0.99 * tb
            print("  %s (overhead): p99 %s vs %s (%+.1f%%), throughput %s vs %s -> %s" % (
                wid, S.fmt(a), S.fmt(b), 100 * rel, S.fmt(ta), S.fmt(tb),
                "ok" if good else "FAIL (5)"))
        elif wid == newest:
            good = a <= 0.9 * b or b - a >= 10
            print("  %s (newest): score %s vs %s (%+.1f%%) -> %s" % (
                wid, S.fmt(a), S.fmt(b), 100 * rel, "ok" if good else "FAIL (1)"))
        else:
            good = a <= 1.10 * b
            print("  %s: score %s vs %s (%+.1f%%) -> %s" % (
                wid, S.fmt(a), S.fmt(b), 100 * rel, "ok" if good else "FAIL (2)"))
        ok &= good
        for k in s["kinds"]:
            if k["name"] == s["score"]["kind"] or wid == "w0":
                continue
            pa, _ = S.metric(idx, wid, (new, "hints", "hints"), head, "kind:" + k["name"], "p99")
            pb, _ = S.metric(idx, wid, (champ, "hints", "hints"), head, "kind:" + k["name"], "p99")
            if pa is not None and pb:
                good = pa <= 1.25 * pb
                print("    %s p99 %s vs %s (%+.1f%%) -> %s" % (
                    k["name"], S.fmt(pa), S.fmt(pb), 100 * (pa / pb - 1),
                    "ok" if good else "FAIL (3)"))
                ok &= good
            if k.get("hint", {}).get("class") == "low":
                for l in [x for x in s["load_rps"] if x <= head]:
                    rs = idx.get((wid, new, "hints", "hints", l, "kind:" + k["name"]), [])
                    frac = S.med([S.fnum(r["resp_rps"]) / max(S.fnum(r["sent_rps"]), 1)
                                  for r in rs])
                    if frac is not None and frac < 0.9:
                        print("    %s answered %.1f%% at %d -> FAIL (4)" % (k["name"],
                                                                         100 * frac, l))
                        ok = False
    print("ACCEPT" if ok else "REJECT")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gate"); g.add_argument("--workload", required=True)
    a = sub.add_parser("accept"); a.add_argument("--policy", required=True)
    a.add_argument("--against", help="compare with this policy instead of the champion")
    a.add_argument("--newest", help="the newest workload id (default: highest id)")
    sub.add_parser("champion")
    args = ap.parse_args()
    if args.cmd == "champion":
        print(champion(data()[1]))
        return 0
    return gate(args) if args.cmd == "gate" else accept(args)


if __name__ == "__main__":
    sys.exit(main())
