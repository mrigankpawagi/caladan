#!/usr/bin/env python3
"""Held-out test of the post-hoc two-stage explanation (design review, round 3).

The send->enqueue stage is taken to be FIFO and the same under every
policy. Two functional forms were tried, both fitted on W2b only (all
policies without +rx, every load) and both reported, so the better one's
error is optimistic:
  - linear in the per-core residual work R = rho E[S^2] / 2E[S]
  - the Pollaczek-Khinchine wait shape R / (1 - rho)
Only W3 has a different service mix; W2a, W4, W6 and W5's 2- and 6-core
variants share W2b's mix, and the forms ignore the core count, so for those
the "prediction" is W2b's own measurement: they test whether the stage
depends on policy and on core count, not the form.

import csv
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SESSION = sys.argv[1] if len(sys.argv) > 1 else "v2"


def points(wid, variant=None):
    d = os.path.join(HERE, "results", wid, SESSION)
    meta = json.load(open(os.path.join(d, "meta.json")))
    spec = dict(meta["workload"])
    if variant:
        spec.update(spec.get("variants", {}).get(variant, {}))
    cal = meta["calibration"]
    tot = sum(k["weight"] for k in spec["kinds"])
    s = [cal["handler_us"][str(k["service_us"])] for k in spec["kinds"]]
    p = [k["weight"] / tot for k in spec["kinds"]]
    es = sum(a * b for a, b in zip(p, s))
    es2 = sum(a * b * b for a, b in zip(p, s))
    acc = {}
    for r in csv.DictReader(open(os.path.join(d, "segments.csv"))):
        if (variant and r.get("variant") != variant) or r["part"] != "mean":
            continue
        if "+" in r["policy"] or not r["rho"]:
            continue
        acc.setdefault(float(r["rho"]), []).append(float(r["in"]))
    k = spec.get("rho_kthreads", spec["server_kthreads"])
    return [(FORM(rho, es, es2, k), statistics.mean(v), rho) for rho, v in sorted(acc.items())]


# the two forms tested, both fitted on W2b only: the per-core residual work
# R = rho E[S^2] / 2E[S], and the Pollaczek-Khinchine FIFO wait R / (1 - rho)
FORMS = {"residual R": lambda rho, es, es2, k: rho * es2 / (2 * es),
         "P-K wait R/(1-rho)": lambda rho, es, es2, k: rho * es2 / (2 * es) / (1 - rho)}
for FNAME, FORM in FORMS.items():
  print("\n## form: in = a + b x %s" % FNAME)
  train = points("w2b-hol-class")
  n = len(train)
  mx = sum(x for x, _, _ in train) / n
  my = sum(y for _, y, _ in train) / n
  b = sum((x - mx) * (y - my) for x, y, _ in train) / sum((x - mx) ** 2 for x, _, _ in train)
  a = my - b * mx
  print("fit on W2b: in = %.2f + %.3f x" % (a, b))
  print("| held-out | rho | x | predicted in | measured in | error |")
  print("|---|---|---|---|---|---|")
  errs = []
  for wid, var in [("w3-deadlines", None), ("w6-mixed-hints", None), ("w2a-hol-service", None),
                   ("w4-wrong-hints", None), ("w5-cores", "cores2"), ("w5-cores", "cores6")]:
      for x, y, rho in points(wid, var):
          pred = a + b * x
          errs.append((pred - y) / y)
          print("| %s%s | %.2f | %.1f | %.1f | %.1f | %+.0f%% |" % (
              wid, " " + var if var else "", rho, x, pred, y, 100 * (pred - y) / y))
  print("\nheld-out points: %d, median |error| %.0f%%, max |error| %.0f%%" % (
      len(errs), 100 * statistics.median(abs(e) for e in errs), 100 * max(abs(e) for e in errs)))
