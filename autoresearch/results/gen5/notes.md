# Generation 5: a stale hint

## What happened

1. **Workload w6** (workload agent): w5 with one change in the server's hint
   map: lookups carry a stale 20 µs run-time hint although they take about
   2 µs. The built-in check held (fifo, prio, edf_high, which never read
   run-time hints, reproduced w5 within 3%). Gate: PASS at 390k; champion
   sjf_guard 143 µs (98.5 on w5), its lookups' runqueue-wait p99 79 µs (43
   on w5); rejected sjf_learn 200 µs, worse than fifo.
2. **Report** (measurement agent): the new cost is queueing behind queries
   the stale hint ranks first; sjf_learn fails because learning could only
   raise a length and its lost rule sent late lookups behind newer work.
3. **Policy p6 sjf_timed** (policy agent): p3's order and urgency rule with
   each HIGH thread's length learned per hint value in both directions, and
   no lost rule. **Rejected** on rules 3 and 6: w6 get p99 92 µs (−36%), get
   wait p99 27 µs, queries protected on w5 and w6; but puts lost 1.4–1.7
   points of deadline-met and put p99 rose 29.5% on w5. sjf_guard stays
   champion.

## Orchestrator changes this generation

- `eval_policy.sh`: one command for the reduced policy evaluation, choosing
  full, headline-only, and overhead levels from the workload directory.
- The antagonist path in run.py was tested (cache antagonist with w1): it
  runs, and the IOKernel largely isolates the latency-critical server from it.

## Observations to keep

- **Three rejections in a row (p4, p5, p6) share a pattern**: each found a
  real gain for lookups and paid for it with another deadline-carrying kind
  (p4: threshold only; p5: queries; p6: puts). Inside the policy region,
  without preemption and at fixed capacity, ordering moves waiting time
  between latency-critical kinds rather than removing it. The rules,
  unchanged, now protect every kind with a deadline, which is the intended
  research question: can hints help one kind without hurting others?
- On w6 the champion only beats prio at the top load; at 300k its gets do
  worse than fifo's (95.5 vs 83 µs), because the stale hint ranks them last.

## Open requests for the owner

Unchanged: preemption; hint-aware stealing; packet processing on every
reschedule while hinted threads wait (64 µs of the champion's get p99 on w6
is outside the runqueue); exact run times from the scheduler; counters for
learned run times.

## Node time

About 23 minutes (12 experiments on w6, then p6's evaluation).
