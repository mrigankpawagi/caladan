# Generation 2 (loop 2): w3, the search leaf, and p3 passonce

## What happened
1. **Workload w3** (search leaf, base cell): 6 µs type-ahead suggestions due
   in 60 µs beside 37 µs searches due in 200 µs, with index updates (normal)
   and segment merges (low); 8 cores, 16 connections, no bursts. Its first
   version failed the headline rule at 0.7 load, because the median request
   was a suggestion whose median doubles by 0.8 load; the mix was revised once
   (40/45/7/8) so the median request is a search. Gate at 299k: suggestions
   ×2.25 of their budget under fifo, ×2.17 under prio; searches ×0.83 / ×0.81.
2. **Report:** a tail suggestion under prio waits about 82 µs in the run
   queue, 71 of it behind searches; about 30 µs is outside the queue, and the
   floor without preemption is about 55–60 µs. The searches may rise about
   8 µs under the 5% rule; an unconditional suggestion-first order would cost
   them 5–6%. prio's own repeats spread 12% on this workload (fifo's 2%).
3. **Policy p3 passonce** (40-line function, no constants, no clock read):
   prio plus one pass inside the chosen class for the shortest
   deadline-carrying thread, each passed thread paying at most once, tracked
   by a per-core ready-time mark. **Accepted:** suggestions' p99 129 → 98 µs
   (×2.15 → ×1.63), p99.9 better, searches +1 µs (same), index and merge
   same; w2, w1, w0 unchanged. The new champion.

## What this says
- Generation 1's lesson paid off: price a pass by what the passed thread
  absorbs (6 µs here), and bound passes per thread rather than by the age of
  the queue. The one-pass bound kept the searches' cost under the rule's
  threshold, and the suggestions' far tail improved too.
- The policy costs nothing on picks it does not change: w0 and w2 are
  within noise, unlike p2's extra scan and clock read.
- The remaining suggestion tail (98 µs, ×1.63) is one search ahead plus the
  ~30 µs outside the queue; the floor is about 55–60.

## Orchestrator notes
- The storage-node cell (w4) was gated with fifo and prio while this
  generation ran, and needed a clarification of the headline rule (2.0.1):
  delivery is checked against what the client sent, since the client misses
  about 0.15% of its send slots. The headlines of w0–w3 did not change.
- A first draft of the key-value family's burst step was set aside: with one
  HIGH kind, bursts leave no decision to an in-region policy. The family's
  next cell is instead a second budget (range reads), drafted as w5.
- Node time: gate 7 min (plus the failed first version's 7), evaluation
  18 min including a build.
