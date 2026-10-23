# Generation 2: one shared deadline, plus a LOW kind

## What happened

1. **Workload w3** (workload agent): w2's traffic, but lookups and queries
   share one 100 µs deadline, and half of batch becomes a LOW "scan" kind. With
   one deadline, deadline order is arrival order, so only the expected run-time
   hint can tell lookups from queries.
2. **Gate**: PASS at 400k req/s. fifo 94.5 µs, prio 84.0, champion edf_high
   87.5: edf_high fell back to prio exactly as predicted (it was 53 on w2).
3. **Report**: gets queue behind older queries (inversions 0, HIGH wait 3.81
   µs, both kinds gain about 77 µs at p99); scans answer 100% everywhere.
   Hypothesis: shortest expected run time first within HIGH, with a slack guard
   so queries keep their 100 µs deadline.
4. **Policy p3 sjf_guard** (policy agent): among HIGH threads, an "urgent" one
   (must start within 20 µs to make its deadline, and still can) runs first;
   otherwise order by deadline plus 8x expected run time. **Accepted**: w3 get
   p99 55.0 µs (−37% vs edf_high), and it is at least as good on w1, w2 and on
   every other kind; query deadline-met 98.94% vs 98.84%. New champion.

## Orchestrator changes this generation

- **Bursts** (owner's suggestion): loadgen `--burst period_us:duty:factor` and
  a workload `burst` field (commits "loadgen: bursty arrivals", "optional burst
  field"). A check at 300k req/s on w1 (period 1000 µs, duty 0.25, factor 3)
  raised short p99 under fifo from 30 to 121 µs. The workload prompt is now
  v1.2 with a burst ladder.
- **Acceptance rule 6**: other kinds with a deadline may lose at most 1
  percentage point of deadline-met (the 25% p99 rule alone would have allowed
  w3's queries past their deadline). Retroactively it does not change gen 1.

## Observations to keep

- **w0 drifts more than the 6% band.** w0 has no hints, so all policies
  schedule it identically, yet its headline score has ranged 150–196 µs across
  runs (sjf_guard 163 vs edf_high 188.5 this generation). Its headline point
  (350k, median 1.23x light load) is close to saturation. If rule 5 ever
  rejects a policy on w0 alone, check this before believing it.
- Every hinted workload now sits at 51–55 µs, the floor the agents attribute to
  waiting behind an already-running long request. Further gains from inside
  the policy region may need harder workloads (bursts, wrong hints) or the
  owner's hooks.

## Open requests for the owner (unchanged)

Preemption of a running long thread by an urgent one; a hint-aware
work-stealing filter (26% of hinted threads are stolen on w3).

## Node time

About 17 minutes (18 experiments), under the 25-minute cap.
