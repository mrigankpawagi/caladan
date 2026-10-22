#!/usr/bin/env python3
"""Applies the generation protocol's decision rules to the measured results.

  ./judge.py gate --workload w2       is the new workload worth keeping?
  ./judge.py accept --policy edf      does the new policy beat the champion?
  ./judge.py champion                 which policy is the current champion?
  ./judge.py wins [--policy p]        on which workloads does it win?

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
        (5) on w0 (no hints), p99 one level below the headline load is within
            the noise band of the champion's, and the throughput sustained at
            the top (overloaded) level is within 1% of the champion's; w0's
            headline point itself drifts too much (150-196 us across runs) to
            detect overhead;
        (6) other kinds that have a deadline lose at most 1 percentage point
            of deadline-met at the headline load (so a policy cannot win by
            sacrificing another kind's deadline);
        (7) on every earlier workload the champion wins (see wins below), the
            new policy wins too, so wins are never traded away and small
            losses cannot add up over generations.
wins:   a policy wins a workload if, at the headline load, it keeps every
        kind with a deadline within 1 point of the best deadline-met any
        policy reached there (it is a deadline-keeper) and its score is within
        the noise band of the best score of any other deadline-keeper. The
        loop must end (by generation 25) with a champion that wins every
        workload.
A workload on which both the policy and the champion have paired runs
(run.py --paired) in the same generation is decided from those runs alone
(paired confirmation, README.md). A rejection prints a FAILED_ON line naming
the failing workloads, the newest workload, the champion, and whether rule 1
passed, which eval_policy.sh reads to start the confirmation.
Exit status 0 means pass, 1 means fail; the numbers are always printed.
"""

import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import summarize as S  # noqa: E402

NOISE = 0.06


PAIRED = re.compile(r"__p\d+$")


def data():
    rows = S.latest(S.load_rows("summary.csv"))
    return S.index(rows), S.load_cards(), S.load_workloads()


def paired_index(new, champ, wid):
    """Rows of a paired confirmation (run.py --paired) of new against champ on
    wid, from the latest generation that has paired runs of both, else None."""
    # every generation, not only the latest: a later re-run of either policy
    # must not hide the pairing
    rows = [r for r in S.load_rows("summary.csv")
            if r["workload"] == wid and PAIRED.search(r["run_id"])]
    gens = [{r["gen"] for r in rows if r["policy"] == p} for p in (new, champ)]
    common = gens[0] & gens[1]
    if not common:
        return None
    g = max(common, key=int)
    return S.index([r for r in rows if r["gen"] == g and r["policy"] in (new, champ)])


def champion(cards):
    acc = [c for c in cards.values() if c.get("status") == "accepted"]
    if acc:
        return max(acc, key=lambda c: (int(c.get("generation", 0)), c.get("id")))["config"]
    return "prio"


def score(idx, s, policy, load):
    v, n = S.metric(idx, s["id"], (policy, "hints", "hints"), load,
                    "kind:" + s["score"]["kind"], s["score"]["percentile"])
    return v if n else None


def standing(idx, s, head):
    """Every policy measured with hints at the headline load of workload s:
    (scores, deadline-keepers, best deadline-met per kind, deadline-met per
    (policy, kind)). A policy without a deadline-met value for a kind is not
    judged on that kind."""
    wid = s["id"]
    pols = sorted({k[1] for k in idx if k[0] == wid and k[2:5] == ("hints", "hints", head)})
    sc = {p: score(idx, s, p, head) for p in pols}
    sc = {p: v for p, v in sc.items() if v is not None}
    met = {}
    for k in s["kinds"]:
        if k.get("deadline_us", 0) > 0:
            for p in sc:
                v, _ = S.metric(idx, wid, (p, "hints", "hints"), head, "kind:" + k["name"],
                                "deadline_met")
                if v is not None:
                    met[(p, k["name"])] = v
    best = {}
    for (p, kn), v in met.items():
        best[kn] = max(best.get(kn, v), v)
    keep = [p for p in sc if all(met.get((p, kn), b) >= b - 1.0 for kn, b in best.items())]
    return sc, keep, best, met


def wins_on(idx, s, head, pol, exclude=()):
    """(win, best other deadline-keeper, its score) for pol on workload s,
    ignoring the policies in exclude."""
    sc, keep, _, _ = standing(idx, s, head)
    if pol not in sc:
        return None, None, None
    rivals = [p for p in keep if p != pol and p not in exclude]
    bp = min(rivals, key=sc.get) if rivals else None
    win = pol in keep and (bp is None or sc[pol] <= (1 + NOISE) * sc[bp])
    return win, bp, sc.get(bp)


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
    failed = []
    score_ok = [True]  # rule 1 on the newest workload
    print("policy %s vs champion %s; newest workload %s" % (new, champ, newest))
    def check(wid):
        s = workloads[wid]
        ok = True
        widx = idx
        head = S.headline_load(idx, wid, s["load_rps"])
        if not head:
            return ok
        pidx = paired_index(new, champ, wid)
        if pidx and all(any(k[1] == p for k in pidx) for p in (new, champ)):
            widx = pidx
            print("  %s: decided from the paired confirmation runs" % wid)
        a, b = score(widx, s, new, head), score(widx, s, champ, head)
        if wid != "w0" and (a is None or b is None):
            # a workload without data is a failure, never a silent pass
            print("  %s: missing data (%s=%s, %s=%s) -> FAIL" % (wid, new, a, champ, b))
            return False
        rel = a / b - 1 if (a is not None and b) else 0
        if wid == "w0":
            loads = s["load_rps"]
            below = max([l for l in loads if l < head], default=head)
            pa, _ = S.metric(widx, wid, (new, "hints", "hints"), below, "all", "p99")
            pb, _ = S.metric(widx, wid, (champ, "hints", "hints"), below, "all", "p99")
            ta, _ = S.metric(widx, wid, (new, "hints", "hints"), loads[-1], "all", "resp_rps")
            tb, _ = S.metric(widx, wid, (champ, "hints", "hints"), loads[-1], "all", "resp_rps")
            if None in (pa, pb, ta, tb):
                print("  %s (overhead): missing data" % wid)
                ok = False
                return ok
            good = pa <= (1 + NOISE) * pb and ta >= 0.99 * tb
            print("  %s (overhead): p99 at %d %s vs %s (%+.1f%%), sustained throughput at "
                  "%d %s vs %s (%+.2f%%) -> %s" % (
                      wid, below, S.fmt(pa), S.fmt(pb), 100 * (pa / pb - 1), loads[-1],
                      S.fmt(ta), S.fmt(tb), 100 * (ta / tb - 1), "ok" if good else "FAIL (5)"))
        elif wid == newest:
            good = a <= 0.9 * b or b - a >= 10
            score_ok[0] = good
            print("  %s (newest): score %s vs %s (%+.1f%%) -> %s" % (
                wid, S.fmt(a), S.fmt(b), 100 * rel, "ok" if good else "FAIL (1)"))
        else:
            good = a <= 1.10 * b
            print("  %s: score %s vs %s (%+.1f%%) -> %s" % (
                wid, S.fmt(a), S.fmt(b), 100 * rel, "ok" if good else "FAIL (2)"))
            # rule 7: the champion's win (over every other policy but the new
            # one) must be kept; from paired runs, against the champion alone
            cw, _, _ = wins_on(idx, s, head, champ, exclude=(new,))
            if cw:
                nw, bp, bs = wins_on(widx, s, head, new)
                print("    win kept: %s (best other deadline-keeper %s %s) -> %s" % (
                    "yes" if nw else "no", bp, S.fmt(bs), "ok" if nw else "FAIL (7)"))
                good = good and bool(nw)
        ok &= good
        for k in s["kinds"]:
            if k["name"] == s["score"]["kind"] or wid == "w0":
                continue
            pa, _ = S.metric(widx, wid, (new, "hints", "hints"), head, "kind:" + k["name"], "p99")
            pb, _ = S.metric(widx, wid, (champ, "hints", "hints"), head, "kind:" + k["name"], "p99")
            if pa is not None and pb:
                good = pa <= 1.25 * pb
                print("    %s p99 %s vs %s (%+.1f%%) -> %s" % (
                    k["name"], S.fmt(pa), S.fmt(pb), 100 * (pa / pb - 1),
                    "ok" if good else "FAIL (3)"))
                ok &= good
            if k.get("deadline_us", 0) > 0:
                da, _ = S.metric(widx, wid, (new, "hints", "hints"), head, "kind:" + k["name"],
                                 "deadline_met")
                db, _ = S.metric(widx, wid, (champ, "hints", "hints"), head,
                                 "kind:" + k["name"], "deadline_met")
                if da is not None and db is not None:
                    good = da >= db - 1.0
                    print("    %s deadline met %.2f%% vs %.2f%% -> %s" % (
                        k["name"], da, db, "ok" if good else "FAIL (6)"))
                    ok &= good
            if k.get("hint", {}).get("class") == "low":
                for l in [x for x in s["load_rps"] if x <= head]:
                    rs = widx.get((wid, new, "hints", "hints", l, "kind:" + k["name"]), [])
                    frac = S.med([S.fnum(r["resp_rps"]) / max(S.fnum(r["sent_rps"]), 1)
                                  for r in rs])
                    if frac is not None and frac < 0.9:
                        print("    %s answered %.1f%% at %d -> FAIL (4)" % (k["name"],
                                                                         100 * frac, l))
                        ok = False
        return ok

    for wid in ids:
        if workloads[wid].get("status") == "superseded":
            continue
        if not check(wid):
            ok = False
            failed.append(wid)
    if failed:
        # machine-readable, for eval_policy.sh's paired confirmation
        print("FAILED_ON: %s NEWEST: %s CHAMPION: %s SCORE: %s" % (
            " ".join(failed), newest, champ, "ok" if score_ok[0] else "fail"))
    print("ACCEPT" if ok else "REJECT")
    return 0 if ok else 1


def wins(args):
    idx, cards, workloads = data()
    pol = args.policy or champion(cards)
    ids = sorted(workloads, key=lambda w: (int(w[1:].rstrip("abcdefghij")), w))
    won, lost = [], []
    print("%-5s %8s %9s  %-28s %7s  %s" % ("wl", "headline", pol, "best other deadline-keeper",
                                          "gap", "result"))
    for wid in ids:
        s = workloads[wid]
        if wid == "w0" or s.get("status") == "superseded":
            continue
        head = S.headline_load(idx, wid, s["load_rps"])
        if not head:
            continue
        sc, keep, best, met = standing(idx, s, head)
        win, bp, bs = wins_on(idx, s, head, pol)
        if win is None:
            print("%-5s %8d %9s  no data" % (wid, head, "-"))
            lost.append(wid)
            continue
        gap = "%+.1f%%" % (100 * (sc[pol] / bs - 1)) if bs else "-"
        why = ""
        if pol not in keep:
            why = " (not a deadline-keeper: %s)" % ", ".join(
                "%s %.2f vs best %.2f" % (kn, met[(pol, kn)], b) for kn, b in best.items()
                if met.get((pol, kn), b) < b - 1.0)
        # faster policies left out for missing deadlines, for the record
        out = ["%s %s" % (p, S.fmt(sc[p])) for p in sorted(sc, key=sc.get)
               if p not in keep and sc[p] < sc[pol]]
        print("%-5s %8d %9s  %-28s %7s  %s%s%s" % (
            wid, head, S.fmt(sc[pol]), "%s %s" % (bp, S.fmt(bs)) if bp else "-", gap,
            "WIN" if win else "LOSS", why,
            ("  [faster but misses deadlines: %s]" % ", ".join(out)) if out else ""))
        (won if win else lost).append(wid)
    print("%s wins %d of %d workloads%s" % (pol, len(won), len(won) + len(lost),
                                            ("; losses: " + " ".join(lost)) if lost else ""))
    return 0 if not lost else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gate"); g.add_argument("--workload", required=True)
    a = sub.add_parser("accept"); a.add_argument("--policy", required=True)
    a.add_argument("--against", help="compare with this policy instead of the champion")
    a.add_argument("--newest", help="the newest workload id (default: highest id)")
    sub.add_parser("champion")
    w = sub.add_parser("wins"); w.add_argument("--policy", help="default: the champion")
    args = ap.parse_args()
    if args.cmd == "champion":
        print(champion(data()[1]))
        return 0
    if args.cmd == "wins":
        return wins(args)
    return gate(args) if args.cmd == "gate" else accept(args)


if __name__ == "__main__":
    sys.exit(main())
