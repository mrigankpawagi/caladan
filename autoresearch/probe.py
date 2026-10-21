#!/usr/bin/env python3
"""Quick probes of several workload proposals; reports which leaves the most
for a policy to win.

  ./probe.py --gen 13 proposal1.json proposal2.json ...

Each proposal is copied to results/gen<N>/proposals/ with its id suffixed by a
letter (w14a, w14b, ...), then measured once (one repeat) with fifo and the
champion at its lightest level and its two busiest levels (run.py --probe;
results go to results/gen<N>/probe/, which summarize.py and judge.py ignore).

For each proposal it prints, at the busiest probed level that passes the
headline rule (README), fifo's and the champion's score and the champion's
runqueue-wait p99 for the score kind, as microseconds and as a share of its
p99. A policy can only shorten runqueue wait, so the proposal whose champion
spends the largest share of its tail in the runqueue is the one with the most
for a policy to win (the floor itself cannot be measured without counters,
so the share is a proxy). The orchestrator picks one, commits it under the
original id, and runs the full matrix on it; the probe numbers are recorded
in the generation's notes.
"""

import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import judge as J  # noqa: E402
import summarize as S  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gen", type=int, required=True)
    ap.add_argument("--champion", help="default: judge.py's champion")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("proposals", nargs="+")
    args = ap.parse_args()
    champ = args.champion or J.champion(S.load_cards())
    gdir = os.path.join(HERE, "results", "gen%d" % args.gen)
    pdir = os.path.join(gdir, "proposals")
    os.makedirs(pdir, exist_ok=True)

    probed = []
    for i, path in enumerate(args.proposals):
        s = json.load(open(path))
        pid = s["id"] + "abcdefghij"[i]
        s["id"] = pid
        dst = os.path.join(pdir, "%s-%s.json" % (pid, s["slug"]))
        with open(dst, "w") as f:
            json.dump(s, f, indent=2)
            f.write("\n")
        loads = s["load_rps"]
        levels = sorted({loads[0]} | set(loads[-2:]))
        probed.append((pid, s, levels))
        cmd = [os.path.join(HERE, "run.py"), "--gen", str(args.gen), "--workload", dst,
               "--policy", "fifo," + champ, "--levels", ",".join(map(str, levels)),
               "--repeats", "1", "--probe"] + (["--dry-run"] if args.dry_run else [])
        print("probe %s: %s" % (pid, " ".join(cmd[1:])), flush=True)
        subprocess.run(cmd, check=True, stdin=subprocess.DEVNULL)
    if args.dry_run:
        return

    rows = S.load_rows(os.path.join("probe", "summary.csv"))
    rows = [r for r in rows if int(r["gen"]) == args.gen]
    idx = S.index(rows)
    print("\nchampion: %s" % champ)
    print("%-6s %-9s %-10s %-10s %-14s %s" % ("id", "level", "fifo", "champion",
                                              "champ wait p99", "wait share"))
    best = None
    for pid, s, levels in probed:
        kind, pc = "kind:" + s["score"]["kind"], s["score"]["percentile"]
        head = S.headline_load(idx, pid, levels)
        if not head or head == levels[0]:
            print("%-6s no usable level (fifo overloaded above the lightest)" % pid)
            continue
        f, _ = S.metric(idx, pid, ("fifo", "hints", "hints"), head, kind, pc)
        c, _ = S.metric(idx, pid, (champ, "hints", "hints"), head, kind, pc)
        w, _ = S.metric(idx, pid, (champ, "hints", "hints"), head, kind, "qwait_p99")
        share = w / c if (w is not None and c) else None
        print("%-6s %-9d %-10s %-10s %-14s %s" % (
            pid, head, S.fmt(f), S.fmt(c), S.fmt(w),
            "%.0f%%" % (100 * share) if share is not None else "-"))
        if share is not None and (best is None or share > best[0]):
            best = (share, pid)
    if best:
        print("\nlargest share of the champion's tail in the runqueue: %s" % best[1])


if __name__ == "__main__":
    main()
