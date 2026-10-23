# Generation 16: reads only 2.5 times shorter than sub-requests

## What happened

1. **Three workload proposals**, probed against the champion sjf_afford:

   | Proposal | Probed load | fifo score p99 | Champion score p99 | Its wait p99 | Share in runqueue |
   |---|---|---|---|---|---|
   | w17a the leaf at 90% peak load | 170k | 323 µs | 301 µs | 248.4 µs | 83% |
   | w17b a search shard (new service) | 136k | 405 µs | 251 µs | 180.2 µs | 72% |
   | w17c reads 2.5 times shorter, 90% load | 159k | 305 µs | 373 µs | 309.4 µs | 83% |

   w17c became **w17**. It sits just outside p16's one-third length ratio, so
   the champion's pass never fired for reads and it fell behind fifo. Gate:
   PASS at 159k; read p99 fifo 310.5, prio 209.5, champion 364.0 µs.
2. **Report** (measurement agent): with 1000 µs bursts oldest-first already
   meets 99.76% of sub-request deadlines, so the deadline order bought
   sub-requests 20.5 µs of wait and cost reads 150 µs. Top hypothesis: a pass
   guarded by slack and cost, not a fixed ratio, safest for a passer that
   arrived first.
3. **Policy p17 sjf_older** (policy agent): the shortest waiting HIGH thread
   may also pass when it is only shorter, if it became ready before the
   chosen thread and the chosen one has not run yet; p16's slack guard still
   applies. **Accepted** after a paired confirmation on w4b and w9 (query
   deadline-met drift where p17 decides as p16): w17 −35.7% (234.0 µs),
   sub-requests −0.03 points.

## Findings

- **A trap on a fixed constant was answered with a principled rule.** w17
  was built to sit just outside p16's one-third ratio. The fix did not move
  the constant; it added a case stated in cost and arrival order.
- **Short bursts change the deadline trade-off.** With 1000 µs bursts, plain
  oldest-first met sub-request deadlines almost as well as deadline order, so
  the case for running tight-deadline work first depends on how deep bursts
  are.

## Orchestrator notes

- No sleep this generation; all runs complete.

## Node time

About 40 minutes: probes (8 min), w17's matrix (10 min), p17's evaluation
with paired confirmation on two workloads (22 min).
