# Generation 15: a new service, where deadlines and lengths conflict

## What happened

1. **Three workload proposals**, probed against the champion sjf_overrun:

   | Proposal | Probed load | fifo score p99 | Champion score p99 | Its wait p99 | Share in runqueue |
   |---|---|---|---|---|---|
   | w16a large values over 48 connections | 73.75k | 738 µs | 237 µs | 160.9 µs | 68% |
   | w16b large values at 90% load | 81k | 623 µs | 228 µs | 157.5 µs | 69% |
   | w16c an RPC leaf service (new) | 155k | 624 µs | 487 µs | 429.3 µs | 88% |

   w16c became **w16**: a leaf of a fan-out RPC tree with cheap frontend
   reads (8 µs, due in 800 µs; the score), fan-out sub-requests (41 µs, due
   in 300 µs), health checks and background work, honest hints, 48
   connections. It is the first workload outside the key-value family since
   w4. Gate: PASS at 155k.
2. **A counter-example to the policy line.** On w16 plain priority classes
   gave the best read p99 (305.0 µs) and every deadline-aware policy did
   worse (edf_high 683.5, sjf_guard 520.5, the champion 486.0), because the
   deadline-plus-length order lets any sub-request readied up to 236 µs after
   a read run first. The deadline-aware policies met more sub-request
   deadlines (99.04% against prio's 98.27%).
3. **Policy p16 sjf_afford** (policy agent): after the order chooses a HIGH
   thread, the shortest waiting HIGH thread runs first if it is at most a
   third as long, due at least twice as late (within p9's split), and the
   chosen thread keeps 40% of its deadline window as slack. **Accepted** on
   every workload: w16 read p99 486.0 → 255.0 µs (−47.5%, now better than
   prio), health −70.7%, sub-request deadline-met −0.51 points.

## Findings

- **Out-of-family tests matter.** A new service exposed an assumption the
  key-value family never tested (shorter kinds have tighter deadlines), and
  fixing it took one guarded rule; w1–w15 were unaffected.
- **The champion now beats prio on both axes on w16**: read p99 255.0 against
  305.0, and sub-request deadline-met 98.53% against 98.27%.

## Orchestrator notes

- **The Mac slept** (closed lid, on battery) from 17:44, during w16's matrix.
  The champion's second repeat failed with no rows; it was re-run (r3: 489.0
  against r1's 483.0) and committed separately. Every other run was complete.
- A gen 16 proposal (reads 2.5 times shorter than sub-requests) is built to
  sit just outside p16's one-third ratio; the probe decides whether it leaves
  the most headroom.

## Open requests for the owner

Unchanged (staying inside the policy region).

## Node time

About 50 minutes: probes (8 min), w16's matrix (12 min plus 19 min asleep),
the champion's re-run (1 min), and p16's evaluation (24 min).
