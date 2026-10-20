# Generation 1: measurement report

## 1. Headline

w2 at its headline load, 400k req/s. Score: `get` p99 in µs (the latency 99% of gets beat), median of two repeats.

| Workload | Policy / mode | Score | vs fifo | query p99 | batch p99 | Throughput (req/s) |
|---|---|---|---|---|---|---|
| w2 | fifo / hints | 100.5 | 0% | 120.0 | 119.5 | 398,318 |
| w2 | prio / hints | 84.5 | −16% | 103.5 | 144.5 | 398,061 |
| w2 | fifo / ignore | 92.0 | −8% | 114.0 | 114.5 | 398,961 |

With gets and queries both HIGH, prio's gain shrinks from −45% on w1 to −16% here. 440k fails the new 1.5x rule (fifo median 45.5 µs against a limit of 44.25), though it would have passed the old 2x rule.

## 2. Is it real?

- prio vs fifo/hints: the repeats (80, 89 vs 99, 102) do not overlap, and the gap is outside the 6% band.
- fifo with hints and fifo with hints ignored run threads in the same order, yet they differ by 8.5% (99–102 vs 91–93). Against fifo/ignore, prio is only −8%. Treat about 9% as w2's real noise floor.
- Batch +21% (139–150 vs 115–124) is real. prio's two repeats differ by 11%, under the 15% re-run rule.

## 3. Where the get's time goes (prio, 400k)

- p50 (median) 14 µs, p99 84.5; at 100k the p50 is 11.
- Get and query gain the same extra delay over their light-load medians: 73.5 µs at p99. Under fifo it is 89.5 for get, 90 for query and 89.5 for batch. Gets wait in the same line as queries.
- Mean HIGH queue wait is 3.64 µs (0.32 at 100k; fifo 4.61). If the slowest 10% of HIGH threads had spent their extra ~22 µs (p90 minus the light-load p50) in the queue, the mean would rise by at least 2.2 µs. It rose 3.3. Unlike w1, queueing alone can explain the whole tail.
- Mean depth 1.22. Inversions 0 (fifo 1.98%).
- Late at pick: 0.23% of deadline-carrying threads. Client deadline misses: 0.73% (gets 2.18%).
- Steals 24% (fifo 29%). Overflow 53 threads, against about 958k HIGH picks.

Conclusion: gets queue behind older HIGH queries, because prio runs HIGH threads oldest first.

## 4. Costs

Batch p99 rose 21% and NORMAL wait went from 4.59 to 7.06 µs. At 440k, batch p99 went from 289 to 513.5. Throughput stayed within 0.2%. CPU was 7.99 cores in every run because the cores spin, so CPU cannot separate policies. w2 has no LOW kind.

## 5. Anomalies

- No errors and no failed or saturated levels. All runs used code 82c4fe9.
- Kind and class rows match (class:high 318,491 vs get + query 318,490), so hints reached the scheduler.
- fifo on w2 reproduces fifo on w1 (100.5 vs 95.5), as the workload predicted.
- At 440k, which is not scored, the fifo/ignore repeats differ by 20% (274, 330). prio also pushed 2.3x more hinted threads past the queue than fifo (4,340 vs 1,866) and stole less (30% vs 38%). Both are unexplained.
- Ignore mode reports inversions (at most 0.0017%) although no hints are applied.

## 6. Hypotheses for the policy agent

1. **Earliest deadline first within HIGH.** Earliest deadline first (EDF) runs the thread whose deadline (queue time plus the deadline hint) comes soonest. Break ties oldest first and keep HIGH ahead of NORMAL. Evidence: get and query show the same tail delay, inversions are already zero, and the queue wait is large enough to hold the tail. Under EDF a get passes any query queued less than 140 µs before it, which is nearly all of them (query p99 is 103.5). Gets would then run ahead of all 17 µs work, as with prio on w1. There, at the same mix and load, the short p99 was 52.5 µs; acceptance needs 76 or less. Queries may drift toward w1's long p99 (116.5), still inside their 200 µs deadline. Shortest expected service first (2 vs 17 µs hints) can starve queries; EDF limits how long a query can be passed to 140 µs.
2. **Protect batch if the 25% NORMAL budget binds.** Evidence: batch p99 is +21% at 400k and +78% at 440k, while queries have time to spare (99.74% met their deadline). Idea: give NORMAL threads an implied deadline of queue time + 200 µs in the same EDF order. Queries and batch then run in arrival order, as under fifo.
3. **A floor outside the queue.** Evidence: on w1, prio left a 52.5 µs p99 with only 0.51 µs of queue wait. Here two-thirds of deadline misses were not late at pick, and 24% of HIGH threads are stolen. Idea: check that cores which steal threads also follow the policy's order. Below about 50 µs only a hook outside the policy region helps, for example letting an arriving get interrupt a running query.

## 7. Lessons

workload: w2 works as intended (under prio, get and query p99 are both 73.5 µs above their light-load medians, with zero inversions), so next stress what deadline order cannot fix (a LOW kind, bursts, or wrong service hints), and keep the top load near the headline, where repeats agree.
policy: On w2 the get tail is queueing behind older HIGH queries (inversions 0, HIGH wait 3.64 µs), so order HIGH by earliest deadline, watch batch p99 (already +21% under prio), and expect about 52 µs at best, w1's floor that only a hook outside the policy region can beat.
