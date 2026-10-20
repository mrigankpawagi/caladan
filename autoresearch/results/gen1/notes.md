# Generation 1: two latency-critical kinds in one class

## What happened

1. **Workload w2** (workload agent): 20% quick lookups (HIGH, 60 µs
   deadline), 60% queries ten times longer (HIGH, 200 µs deadline), 20% batch
   (NORMAL). Same service-time mix as w1, so fifo reproduces w1's curve.
2. **Gate** (judge.py): PASS at the headline load of 400k req/s. fifo's get
   p99 is 100.5 µs (7.2x its light-load value) and prio only reaches 84.5 µs
   (−16%), against −45% on w1: once lookups share HIGH with queries, strict
   priority cannot tell them apart.
3. **Report** (measurement agent): lookups queue behind older HIGH queries;
   zero inversions, HIGH queue wait 3.64 µs, and get and query p99 rise by the
   same 73.5 µs. Top hypothesis: earliest deadline first within HIGH.
4. **Policy p2 edf_high** (policy agent): prio, but among HIGH threads the one
   whose deadline comes first runs first. **Accepted**: w2 get p99 53.0 µs
   (−37% vs prio, both repeats 53), w1 unchanged, w0 within noise. Query and
   batch p99 rose 8% and 11%, inside the 25% budget. edf_high is the new
   champion.

## Orchestrator fixes this generation (outside the agents' work)

- **Headline load rule tightened** from "median within 2x of light load" to
  1.5x (commit c5778f8). At 440k, where the 2x rule landed, fifo with hints
  applied and fifo with hints ignored, which schedule identically, differed by
  11%, so the 10% acceptance threshold would not have been reliable. Gen 0's
  headline loads are unchanged.
- **judge.py** (gate and acceptance rules as code) and **apply_policy.py**
  (static review and insertion of agent policies) added, so decisions are
  reproducible while the owner is away.

## Observations to keep

- fifo with hints applied scores a few percent worse than fifo with hints
  ignored on both w1 (95.5 vs 91) and w2 (100.5 vs 92). They schedule the same
  way; the difference is the small per-request cost of the classifier and the
  hint bookkeeping, amplified near saturation. It does not affect policy
  comparisons, which all apply hints.
- w0 under edf_high: +5.6%, close to the edge of the 6% band (repeats 181
  and 196 µs). Watch it in later generations.

## Open requests for the owner (not built)

The policy agent asked for two hooks outside the policy region, which only the
owner can approve: (1) letting an early-deadline thread preempt a running long
thread, the likely floor of about 52 µs on w1 and w2; (2) a hint-aware filter
for work stealing (24% of HIGH threads are stolen).

## Node time

ledger.json: about 12.5 minutes (12 experiments), under the 25-minute cap.
