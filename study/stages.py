#!/usr/bin/env python3
"""Two checks reported in REPORT.md, from the v2 data:

1. The pre-registered secondary check (DESIGN-v2.md, first amendment):
   fifo's measured wait growth over rho 0.5 against the pooled M/G/k
   prediction computed at the measured busy fraction (program time / kthread
   time from the RtStats counters) instead of the nominal rho. All fifo
   cells: five workloads x rho 0.8, 0.85, 0.9.

2. Post hoc: the runqueue stage. For a favoured kind under a priority order,
   its wait growth minus the growth of its send->enqueue segment (the stage
   every policy shares), against the priority model's bracket (pooled / per
   core) at the measured busy fraction.

  ./stages.py [session]   -> results/stages-<session>.md
"""
import csv
import json
import os
import statistics as st
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze  # noqa: E402

SESSION = sys.argv[1] if len(sys.argv) > 1 else "v2"


def load(wid, pol):
    d = os.path.join(HERE, "results", wid, SESSION)
    meta = json.load(open(os.path.join(d, "meta.json")))
    spec, cal = meta["workload"], meta["calibration"]
    k = spec["server_kthreads"]
    busy = defaultdict(list)
    for r in csv.DictReader(open(os.path.join(d, "counters.csv"))):
        if r["policy"] == pol and r.get("tsc"):
            busy[float(r["rho"])].append(int(r["program_cycles"]) / (int(r["tsc"]) * k))
    mean, svc, inn = {}, {}, {}
    for r in csv.DictReader(open(os.path.join(d, "summary.csv"))):
        if r["policy"] == pol and r["group"].startswith("kind:") and r["mean"]:
            mean[(float(r["rho"]), r["group"][5:], int(r["repeat"]))] = float(r["mean"])
    for r in csv.DictReader(open(os.path.join(d, "segments.csv"))):
        if r["policy"] == pol and r["part"] == "mean":
            key = (float(r["rho"]), r["group"][5:], int(r["repeat"]))
            svc[key], inn[key] = float(r["svc"]), float(r["in"])
    return spec, cal, busy, mean, svc, inn


def dwait(mean, svc, rho, kn, base=0.5, minus=None):
    xs = []
    for rp in range(5):
        a, b = (rho, kn, rp), (base, kn, rp)
        if a in mean and b in mean and a in svc and b in svc:
            v = (mean[a] - mean[b]) - (svc[a] - svc[b])
            if minus is not None:
                v -= minus[a] - minus[b]
            xs.append(v)
    return st.median(xs) if xs else None


out = ["# Two checks from the v2 data (stages.py, session %s)" % SESSION, "",
       "## 1. Pre-registered secondary check: fifo against the pooled prediction at the "
       "measured busy fraction", "",
       "| workload | kind | rho | busy | measured dwait (us) | pooled at rho | pooled at busy |",
       "|---|---|---|---|---|---|---|"]
for wid in ["w2b-hol-class", "w3-deadlines", "w6-mixed-hints", "w2a-hol-service",
            "w4-wrong-hints"]:
    spec, cal, busy, mean, svc, inn = load(wid, "fifo")
    kn = spec["kinds"][0]["name"]
    b0 = st.median(busy[0.5])
    for rho in (0.8, 0.85, 0.9):
        bf = st.median(busy[rho])
        m = dwait(mean, svc, rho, kn)
        nom = analyze.predictions(spec, cal, rho)["fifo"][kn] - \
            analyze.predictions(spec, cal, 0.5)["fifo"][kn]
        bus = analyze.predictions(spec, cal, bf)["fifo"][kn] - \
            analyze.predictions(spec, cal, b0)["fifo"][kn]
        out.append("| %s | %s | %.2f | %.3f | %.1f | %.1f (%+.0f%%) | %.1f (%+.0f%%) |" % (
            wid, kn, rho, bf, m, nom, 100 * (nom - m) / m, bus, 100 * (bus - m) / m))

out += ["", "## 2. Post hoc: the runqueue stage of favoured kinds at rho 0.9", "",
        "dwait minus the growth of send->enqueue (the stage every policy shares), against the "
        "priority model at the measured busy fraction (pooled / per core).", "",
        "| workload | policy | kind | busy | dwait | minus send->enqueue growth | "
        "predicted pooled | predicted per core | inside |", "|---|---|---|---|---|---|---|---|---|"]
for wid, pol, kinds in [("w2b-hol-class", "prio", ["short"]),
                        ("w3-deadlines", "prio_edf", ["tight"]),
                        ("w6-mixed-hints", "prio_edf", ["tight", "loose"])]:
    spec, cal, busy, mean, svc, inn = load(wid, pol)
    bf, b0 = st.median(busy[0.9]), st.median(busy[0.5])
    P, P0 = analyze.predictions(spec, cal, bf), analyze.predictions(spec, cal, b0)
    C = analyze.predictions(spec, cal, bf, pooled=False)
    C0 = analyze.predictions(spec, cal, b0, pooled=False)
    for kn in kinds:
        d = dwait(mean, svc, 0.9, kn)
        q = dwait(mean, svc, 0.9, kn, minus=inn)
        lo, hi = P[pol][kn] - P0[pol][kn], C[pol][kn] - C0[pol][kn]
        out.append("| %s | %s | %s | %.3f | %.1f | %.1f | %.1f | %.1f | %s |" % (
            wid, pol, kn, bf, d, q, lo, hi, "yes" if lo <= q <= hi else "no"))
path = os.path.join(HERE, "results", "stages-%s.md" % SESSION)
open(path, "w").write("\n".join(out) + "\n")
print("\n".join(out))
