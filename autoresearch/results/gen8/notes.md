# Generation 8: multigets that borrow the lookups' hint

## What happened

1. **Workload w9** (workload agent): w8 plus a HIGH multiget kind (5% of
   traffic, 30 µs of work) that carries the gets' 2 µs run-time hint but a
   300 µs deadline. Gate: PASS at 370k. fifo get p99 210.5 µs; champion
   sjf_capped 95.0 (83.0 on w8), get wait p99 25.4 → 40.9 µs. The agent
   predicted 125–150 µs; the champion was hurt less.
2. **Report** (measurement agent): multigets rank last, so they run mostly
   from short queues, which the per-core timer skips; the shared "2 µs"
   estimate rises only partway to its cap. About 54 µs of the get p99 is
   outside the runqueue. Top hypothesis: learn per pair of run-time hint
   and coarse deadline.
3. **Policy p9 sjf_pair** (policy agent): p8 with one change: the learning
   key is the run-time hint plus one bit, set when the deadline is more than
   250 µs after the thread became ready. On w1–w8 no deadline is that far,
   so p9 decides exactly as p8. **Accepted** after a paired confirmation:
   w9 get p99 99.0 → 86.0 µs (−13.1%), get wait p99 back to 25.7 µs.

## The paired confirmation, second use

The first verdict was a rejection on rule 6, queries losing 1.1 points of
deadline-met on w8 and w9. On w8 the two policies make identical decisions,
so that gap could only be drift between sessions. `eval_policy.sh` then
re-measured both policies alternately on w8 (headline levels) and w9 (full
sweep): queries matched within 0.1 point on both, and the w9 gain held
(−13.1% paired, −10.0% in the first pass). This is the rule working as
intended, with no manual step.

Drift between sessions also reached rule 3's margin on an older workload:
w3 scan p99 +22.1% (limit 25%) with identical decisions. A paired
confirmation would catch a failure there too, since it covers every
failing workload.

## Orchestrator changes this generation

- The gen 9 workload agent was started while p9 was being evaluated, to use
  the node lease (it ends at 08:46 UTC); it was told to design against both
  p8 and p9, which differ only on w9.
- A background command that changed directory before running `run.py`
  failed to find the script; commands now use absolute paths.

## Observations to keep

- **Mixed labels hurt in proportion to how often the long members are
  timed.** On w8 syncs ranked level with puts and inflated the shared
  estimate fully; on w9 multigets ranked last and inflated it partly.
- **The get floor holds.** Under the best policy, get runqueue-wait p99 is
  about 25 µs on w5–w9, and get p99 about 81–86 µs. The rest of the tail is
  outside the runqueue.
- **Tuned constants accumulate.** p9 adds a 250 µs split to p8's 8 µs cap and
  17 µs blank length; each fits the current workloads' scales.

## Open requests for the owner

Unchanged: preemption; hint-aware stealing; packet processing on every
reschedule while hinted threads wait; exact run times from the scheduler;
learned-cost counters; a learning key set by the server per kind.

## Node time

About 33 minutes: w9's matrix (10 min), p9's evaluation (17 min), and the
paired confirmation (6 min, full w9 sweep plus w8). The confirmation is the
main overrun; it is part of the protocol now.
