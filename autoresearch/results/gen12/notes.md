# Generation 12: tight queries pull the median down

## What happened

1. **Workload w13** (workload agent): w12 with the queries' deadline cut
   from 400 to 300 µs. Queries are about half of the HIGH picks, so p12's
   median deadline is 300 µs, below its 350 µs threshold, and its unit falls
   to 1. Gate: PASS at 100k. Champion sjf_scale: get p99 259.0 µs (184.0 on
   w12), close to sjf_mixed's 267.5, as designed.
2. **Report** (measurement agent): unit 1 confirmed indirectly (47 of 48
   cells within 6% of sjf_mixed). The tighter query deadline alone also
   costs gets about 24 µs of wait, because queries turn urgent earlier.
3. **Policy p13 sjf_upper** (policy agent): p12 with the unit read from an
   upper quartile of the deadlines, with hysteresis. **Accepted** after a
   paired confirmation: w13 −19.5% (208.5 µs); syncs +20.9% p99 (limit 25%),
   puts −0.52 points. The first verdict's rule-6 failures on w6, w7, w9 and
   w10, where p13 decides as p12, were drift between sessions.

## Shortcuts taken to fit the node lease (ends 08:46 UTC)

- **Fewer policies in the matrix:** w13 was measured with fifo, sjf_mixed
  and sjf_scale only; prio and fifo ignoring hints were skipped.
- **Report in parallel:** the measurement report was written in parallel
  with the policy agent. The policy agent worked from the gate numbers. Its
  hypothesis matched the report's second hypothesis.
- **Workload agents overlapped evaluations**, as in gens 8–11.

## Observations to keep

- **Each fix to the unit invites a workload that breaks it.** tightest
  deadline (p11), median (p12), upper quartile (p13). A unit per label, from
  that label's own deadline, is the next step the reports keep pointing to.
- **Puts and syncs pay more each time.** On w13 sync p99 rose 20.9%, close
  to the 25% limit. The next policy will have little room there.
- **Paired confirmation is now routine.** It decided four workloads this
  generation, every one a drift-caused rule-6 failure where decisions were
  identical.

## Open requests for the owner

- **Counters (top priority):** each core's time unit and estimate, learned
  length per label, table clears, time-slice yields of hinted threads.
- **Time slice:** keep a thread's original ready time across a time-slice
  yield, or mark re-queued threads.
- Unchanged: preemption by hint; hint-aware stealing; packet processing
  while hinted threads wait; a learning key the server sets per kind.

## Node time

About 33 minutes: w13's reduced matrix (6 min), p13's evaluation (18 min)
and the paired confirmation on four workloads (9 min).
