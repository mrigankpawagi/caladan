# Generation 1 (loop 2): w2, the fan-out leaf, and p2 rescue

## What happened
1. **Workload w2** (RPC fan-out leaf, base cell): one 37 µs fetch served to
   the frontend (due in 800 µs) and to an aggregator (due in 130 µs), plus
   health checks, exports and rebuilds; 8 cores, 16 connections, no bursts.
   Gate passed at 202k req/s: sub-request p99 ×1.44 of its budget under fifo,
   ×1.35 under prio; reads ×0.23. The author's expectations held in the ratios
   and the headline; fifo's absolute p99 came in lower (187 against 210–260).
2. **Report:** of a tail sub-request's 176 µs under prio, about 94 µs is
   run-queue wait (61 behind other sub-requests, 33 behind reads, under 1
   behind health checks) and about 33 µs is spent before the thread is ready.
   prio removed exactly the background share. The reads' spendable slack by
   the 5% rule is about 9 µs of p99, not the 621 µs to their deadline.
3. **Policy p2 rescue** (72 lines, one constant): prio plus a rationed pass
   inside the chosen class for a thread the hints say will miss, allowed only
   while the passed thread has waited less than one run time. **Rejected:**
   sub-request p99 unchanged (181 vs 175), reads +5.1%, exports +8.7%,
   rebuilds +5.1%, all with ranges apart; w1 and w0 unchanged.

## What this says
- The sub-requests' tail is made of persistent queues, not freshly formed
  ones, so a pass that only fires in fresh queues misses the tail by
  construction. Any pass that reaches the tail has to pass reads that are
  already old, which the 5% rule on reads forbids at this mix. On w2 the
  rule and the workload leave a deadline-aware policy almost no room: the
  tight kind is 55% of the traffic and the loose kind's tail is the same
  queue.
- The extra scan and clock read per pick may be what the background kinds
  paid (+5–9%); the policy ran it on every pick with a deadline present.
  A policy should cost nothing on the picks it does not change.

## Orchestrator notes
- The w3 proposal (search leaf, generation 2) needed one revision: its first
  mix made the median request a 6 µs suggestion, so the headline rule tripped
  at 0.7 load before any budget was missed. The revised mix passed its gate.
- Node time: gate 7 min, evaluation 15 min including a build.
