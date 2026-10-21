# Generation 14: large values that carry a lookup's hints

## What happened

1. **Three workload proposals**, probed against the champion sjf_ratio:

   | Proposal | Probed load | fifo get p99 | sjf_ratio get p99 | Its get wait p99 | Share in runqueue |
   |---|---|---|---|---|---|
   | w15a 48 connections on 4 cores | 48.75k | 727 µs | 170 µs | 48.0 µs | 28% |
   | w15b 1% of lookups 100 times longer, same hints | 73.75k | 812 µs | 322 µs | 241 µs | 75% |
   | w15c lookup-heavy mix at 90% load | 104.5k | 548 µs | 147 µs | 39.1 µs | 27% |

   w15b became **w15**. Gate: PASS at 73.75k; fifo 812.5 µs, champion
   sjf_ratio 341.0 (204.5 on w14).
2. **Report** (measurement agent): a large lookup re-queued after each 100 µs
   time slice keeps the lookups' label and its early deadline, so it runs
   again at once ahead of the ordinary lookups (its median only 55.5 µs over
   its own run). The label is not visibly inflated. Top hypothesis: place a
   re-queued thread behind short waiting threads with its label.
3. **Policy p15 sjf_overrun** (policy agent): a HIGH thread readied again
   after more than 150 µs of total run time (read from the thread's
   `total_cycles`, which the runtime resets when the thread is created and
   adds to on every switch) runs after waiting threads with the same label
   and is never rescued. **Accepted** on every workload: w15 −23.5% (261.0
   µs), get wait p99 264.8 → 188.7 µs, get p99.9 739.5 → 502.5; the large
   lookups themselves did not pay (−1.7%).

## Findings

- **Connections only matter through how they hash to cores.** The 48-
  connection proposal left little to fix; the gen 15 workload agent traced
  this to the NIC's flow hash, which splits consecutive ports evenly over 4
  or 8 cores but not over 6.
- **The champion handles a lookup-heavy mix at 90% load** with only 27% of
  its tail in the runqueue.
- **p15 is the second small, targeted policy in a row** (after p14) to be
  accepted without cost to other kinds. Both were found from the
  measurements (who passes whom, and why) rather than by tuning constants.

## Orchestrator notes

- Background experiments ran under `caffeinate`; no stalls this generation.

## Open requests for the owner

Unchanged (staying inside the policy region).

## Node time

About 40 minutes: probes (8 min), w15's matrix (10 min), p15's evaluation
(22 min).
