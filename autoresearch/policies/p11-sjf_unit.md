# p11: sjf_unit

- id: p11
- config: sjf_unit
- generation: 10
- status: rejected
- builds_on: p10
- changed_from_previous: p10 plus: each core reads a time unit from the tightest relative deadline of the HIGH threads it runs (nearest multiple of 100 µs, at least 1; it takes the last learning slot, leaving four), multiplies the 250 µs deadline split and the 50 µs drop-limit allowance by it, and grows the 8 µs cap allowance, the 17 µs blank length and the 4 µs shared-length drop by half a step per unit; per-request cost, too-late line, order, slack, rescue and timing unchanged (unit 1 on w1–w10, so p10's decisions; 4 on w11, where the cap allowance is 20 µs)
- commit: b9b2fc8

## What it does
Like sjf_mixed, each core runs helper threads first, then HIGH, NORMAL and LOW threads. Among HIGH threads it runs shorter requests first, using run times it learns per label. sjf_mixed's learning rules used fixed microsecond limits tuned to 100 µs deadlines. sjf_unit reads the time scale from the deadlines it sees: the tightest one, in units of 100 µs. It stretches its limits by that unit. On w1–w10 the unit is 1, so it decides exactly as sjf_mixed. On w11 the unit is 4, so it again sees that the "4 µs" label hides 120 µs syncs and flushes, ranks that label behind lookups, and learns multigets apart from lookups.

## Why (hypothesis)
results/gen10/report.md, sections 3 and 6 (hypothesis 1).

**The problem.** On w11 the champion's get runqueue-wait p99 is 162 µs, 1.7 times w9's scaled by four. Three fixed constants cause it:
- The 50 µs drop limit discards every 145 µs sync and flush, so the "4 µs" label learns only quick puts (about 6 µs) and ranks ahead of gets (about 10 µs).
- The 8 µs cap would hold the gets' lead to 48 µs even with those samples kept.
- The 250 µs split no longer separates 400 µs gets from 1200 µs multigets.

**The fix.** With the unit at 4:
- The drop limit becomes 216 µs, so syncs and flushes count again.
- The split becomes 1000 µs, so gets (400) and multigets (1200) get separate labels.
- The cap allowance becomes 20 µs.

The resulting lengths, in µs:

| Label | Learned | Cap | Counts |
|---|---|---|---|
| gets | ~10 | 32 | 10 |
| puts and syncs | ~100 | 28 | 28 |
| queries | ~83 | 92 | 83 |
| multigets | ~140 | 32 | 32 |

Turns: gets +480 µs, puts and syncs +624, queries +1064, multigets +1456. That is w9's order: gets first, then puts and syncs, then queries; multigets count short but their 1200 µs deadline puts them last. Their caps follow their measurements, so p10's shared-length rule stays off.

**Model.** I reused the gen 9 offline model, which calls the real choose functions, and added w11: 4 ms burst period, with long requests at 83 or 90 iterations per µs to bracket the report's measured speed. At 90k it reproduces the champion fairly well:

| Quantity | Model p10 (µs) | Measured p10 (µs) |
|---|---|---|
| get p99 | 217–249 | 242.0 |
| get runqueue-wait p99 | 141–155 | 162.2 |
| multiget p99 | 776–829 | 833.0 |
| put p99 | 216–254 | 342.0 |

It understates puts and syncs.

Model at 90k, 4 seeds; ranges are the two speeds (90 / 83 iterations per µs):

| Kind | p10 | p11 | Change |
|---|---|---|---|
| get p99 | 217 / 249 | 119 / 139 | −45% / −44% |
| get runqueue-wait p99 | 141 / 155 | 9 / 12 | |
| put p99 | 216 / 254 | 235 / 272 | +9% / +7% |
| put deadline-met | | | −0.07 / −0.08 points |
| sync p99 | | | +5% / +3% |
| query p99 | | | −8% / −2% |
| query deadline-met | | | +0.3 / +0.9 points |
| multiget p99 | 776 / 829 | 899 / 946 | +16% / +14% |
| multiget deadline-met | | | ≥ 99.90% |
| batch, scan | | | flat |

**Why half steps for the length allowances.** Scaling the 8 µs cap allowance fully (32 µs) gives the same get p99 (−45%), but multigets count 44 µs and fall 96 µs further behind queries. Multiget p99 then rises +21–23%, against a 25% limit.
- Half steps (20 µs) cut that rise to +14–16%.
- Smaller allowances leave the queries' cap too close to their 83 µs. Unscaled (12 µs) caps queries at 80 µs, which triggers p10's shared length for queries and puts, and the model breaks down: get p99 1143 µs.

The drop limit and the split must scale fully: 145 µs runs must stay under the drop limit, and the split must fall between 400 and 1200 µs.

**Decisions on w1–w10 stay p10's.**
- The tightest HIGH deadline there is 60 or 100 µs, so the unit is 1, and every unit-1 constant equals p10's.
- Lockstep check in the model (p10 called on every queue state p11 saw), on w0–w10 at their headline loads and at 320k–450k: 0 differing picks of 0.03–0.36 M per run.
- On w2 the unit is briefly 2 at startup (when the first deadline seen is a query's 200 µs), then settles at 1. No decision differed.
- The unit changes about once per core per run, at startup. It never toggled afterwards in any run.

**State fits.** One word (slot 7) holds the unit and the tightest relative deadline; the learning table keeps slots 3–6. Labels needed: w1 1, w2–w4b 2, w5–w8 and w10 3, w9 and w11 4.

## Cost
- **Multigets are the main risk.** They now count 32 µs instead of sharing the gets' 10 µs label, so they wait behind more queries. Model: p99 +14–16% (limit +25%), deadline-met ≥ 99.9%.
- **Puts and syncs** now let gets go first. Model: put p99 +7–9%, put deadline-met −0.1 point, sync p99 +3–5%.
- **Queries** gain slightly. Batch and scans are unaffected (the change is inside HIGH).
- **Per pick:**
  - Each pick that runs a HIGH thread does one division to update the unit.
  - Pricing is unchanged: one pass over four learning slots.
  - The clock is still read at most once.
  - Without HIGH threads (w0) it is p10's path plus one branch.
- **Limits:**
  - The unit is a whole number from the tightest deadline, so a workload whose tightest deadline is 150–250 µs gets unit 2.
  - The half-step allowance was tuned in the model.
  - One thread readied long after its deadline was set can lower the unit on its core. The table is then cleared and relearned, and looser deadlines raise the unit back within a few hundred picks.

## Needs
Unchanged from p10, for the owner:
- a learning key the server sets per kind;
- preemption (a running 145 µs sync, flush or multiget cannot be passed);
- packet processing while hinted threads wait;
- counters for each core's learned lengths, its time unit, how often the cap binds, and how often the shared-length rule applies.

## Prediction (from the policy agent)

| Workload | Metric | Expected direction | Rough size |
|---|---|---|---|
| w11 | get p99 at 90k (score) | down | 242.0 → about 140–190 µs (threshold ≤ 217.8); model 119–139 |
| w11 | get runqueue-wait p99 at 90k | down | 162.2 → about 10–60 µs |
| w11 | get p99 at 97k / 103k | down | 293.0 / 376.0 → about 150–220 / 170–260 µs |
| w11 | put p99 / deadline-met at 90k | up slightly / flat | 342.0 → 350–390 µs (limit 427.5); 99.56 → 99.3–99.6% (floor 98.56) |
| w11 | sync p99 at 90k | up slightly | 461.5 → 470–500 µs (limit 576.9) |
| w11 | multiget p99 / deadline-met at 90k (main risk) | up / flat | 833.0 → 930–990 µs (limit 1041.3); 100.00 → ≥ 99.8% (floor 99.00) |
| w11 | query p99 / deadline-met at 90k | flat to down / flat to up | 850.5 → 780–870 µs (limit 1063.1); 91.28 → 91.3–92.3% (floor 90.28) |
| w11 | batch / scan p99, scans answered | flat | 1084 / 1160 within ±5% (limits 1355 / 1450); 100% |
| w10 / w9 / w8 / w7 / w6 / w5 / w4b / w3 / w2 / w1 | score, deadline-met and every kind | same decisions as p10 (lockstep: 0 differing picks) | within session drift |
| w0 | p99 one level below the headline / sustained throughput | flat (p10's path, no HIGH threads) | within noise; within 1% |

## Results
Rejected in generation 10 (judge.py, results/gen10/) on rule 1 against the
champion p10 sjf_mixed: the w11 score did not improve.

| Workload | sjf_mixed | sjf_unit | Change | Notes |
|---|---|---|---|---|
| w11 | get p99 242.0 µs | 259.0 µs | +7.0% | predicted 140–190 (model 119–139) |
| w11 | put / query / sync / multiget p99 | 342.0 / 850.5 / 461.5 / 833.0 µs | 342.5 / 842.0 / 453.5 / 851.5 µs | all within 2.2% |
| w11 | put / query / multiget met | 99.56 / 91.28 / 100.00% | 99.55 / 91.20 / 99.99% | unchanged |
| w1–w10 | | | −2.7 to +4.6% | p10's decisions, as intended |
| w0 | p99 at 300k 71.0 µs | 72.0 µs | +1.4% | sustained throughput +0.08% |

On w11 every kind came within about 2% of sjf_mixed, so sjf_unit decided
like p10 there: the time unit evidently did not reach 4 on the real system,
although the offline model, which calls the same code, reached it on every
core. The cause is not verified (no counter reports the unit). Two
candidates, both outside the model: a handler thread readied a second time
gets a new ready time, so deadline minus ready time understates its relative
deadline and the tightest-deadline rule pins the unit low; or the unit
changes often and each change clears the learning table, leaving lengths at
hint plus 4 µs, which also ranks puts ahead of gets. A counter for each
core's unit would settle it.
