# Generation 4: hints that lie

## What happened

1. **Workload w5** (workload agent): w4b plus "put" requests, HIGH with a
   1 µs run-time hint that hides a 30 µs flush 15% of the time. The first
   workload with inaccurate hints. Gate: PASS at 390k; fifo 192, prio 159,
   edf_high 161.5, champion sjf_guard 98.5 µs (rejected sjf_rescue: 94).
2. **Report** (measurement agent, the first with per-kind runqueue wait): the
   champion's get tail is about 45% runqueue wait during bursts and 55% time
   outside the runqueue; it concluded that ranking puts behind gets could save
   only a few µs.
3. **Policy p5 sjf_learn** (policy agent): each core learns how long threads
   with each hint value really run and ranks them by that. The agent argued
   the report's bound was wrong, and the data agreed: w5 get p99 85.0 µs
   (−13.7%) and get runqueue-wait p99 25 µs (from 43). **Rejected** on rule 6:
   queries lost 1.5 points of deadline-met (88.05% → 86.55%, limit 1).
   sjf_guard stays champion.

## Orchestrator changes this generation

- **Per-request runqueue wait** (commits "report each request's server queue
  wait", "parse and tabulate per-kind queue wait"): the server measures how
  long each request's handler thread waited before starting and returns it in
  the reply; result rows and tables now carry per-kind wait percentiles. On
  w3 it showed that the lookups' tail under the champion is not queueing
  (wait p99 6 µs of 57 µs latency), confirming the floor the agents attributed
  to time before the thread exists.
- The workload agent stalled while this laptop slept; it was asked to finish
  and did.

## Observations to keep

- Two policies in a row (p4, p5) found real gains that the acceptance rules
  rejected: p4 on the 10% threshold, p5 on protecting queries' deadlines. The
  rules are unchanged. The next policy could combine p5's learning with a
  guard for queries.
- The policy agent found, by reading the scheduler, that a busy core reads new
  packets only when its runqueue empties or a 50 µs watchdog fires. That would
  explain most of the time requests spend before their thread exists, and no
  policy inside the region can change it.

## Open requests for the owner

Preemption; a hint-aware work-stealing filter; packet processing on every
reschedule while hinted threads are queued (or a shorter watchdog); exact
per-thread run times handed to the policy; per-request packet arrival time.

## Node time

About 20 minutes (12 experiments on w5, then p5's reduced evaluation).
