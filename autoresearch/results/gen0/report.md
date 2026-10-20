# Generation 0: measurement report

## 1. Headline

Headline load: 400k req/s (w1), 350k (w0). Score: `short` p99 (w1) or `req` p99 (w0), µs, median of two repeats; p99 is the latency 99% of requests beat.

| Workload | Policy / mode / build | Score | vs fifo | Other kind p99 | Throughput (req/s) |
|---|---|---|---|---|---|
| w1 | fifo / hints / hints | 95.5 | 0% | long 116.0 | 399,039 |
| w1 | prio / hints / hints | 52.5 | −45% | long 116.5 | 399,079 |
| w1 | fifo / ignore / hints | 91.0 | −5% | long 109.5 | 399,132 |
| w1 | prio / ignore / hints | 95.0 | −1% | long 114.5 | 398,462 |
| w0 | fifo / hints / hints | 178.5 | 0% | - | 348,728 |
| w0 | prio / hints / hints | 178.5 | 0% | - | 348,376 |
| w0 | fifo / ignore / stock | 169.0 | −5% | - | 349,120 |

No new policy this generation: acting on the priority hint nearly halves w1's short tail; prio's queue scan costs nothing measurable on w0.

## 2. Is it real?

The noise band (calibration.json) is 6%. prio's −45% is far outside it, and its repeats agree (52, 53 µs). The controls (−5%, −1%) and stock's −5% on w0 are within noise.

## 3. Where the short requests' time goes (prio, w1, 400k)

- p50 13 µs, p99 52.5; at 100k, p50 11, p99 14.
- Mean queue wait 0.51 µs (0.30 at 100k). Had the slowest 1% spent their extra ~38 µs queued, the mean would have risen at least 0.38 µs; it rose 0.21. So queueing is at most about half the tail.
- Mean depth 1.23: little is left to reorder.
- Inversions 0 (fifo 2.75%).
- Late at pick 0.00% (fifo 1.02%), yet 0.60% missed the 60 µs client deadline: the misses arise outside the queue.
- Steals 9.6% (fifo 28.4%). Overflow: 49 threads in 2.28 million picks.

Conclusion: most likely stuck behind a running long request (about 21 µs of core time each, calibration.json), which prio never interrupts; short service is only about 1.7 µs.

## 4. Costs

At 400k prio raised long p99 0.4% and NORMAL wait from 4.49 to 4.66 µs; throughput was unchanged. CPU was 7.99 cores in every run (all 8 cores spin, polling rather than sleeping), so it cannot separate policies. At 450k, past the headline load, long p99 rises from 691.5 to 850 µs (+23%).

## 5. Anomalies

- No errors or failed levels; all 14 runs used code 5786466. Overloaded levels: w0 at 400k and 450k (373–381k req/s answered); w1 at 450k (median 76 vs 29.5 µs).
- Kind and class rows match in hints mode: hints reached the scheduler.
- Repeats differ by at most 12% at the headline loads; at 450k (not scored) by up to 22%, three of four configurations past the 15% re-run rule.
- Build overhead (open item): on w0 the hint build is slower in every repeat: p99 at 300k 71–73 vs 67 µs, saturated throughput 373–376k vs 379–381k req/s. fifo and prio match, so the per-pick counters, not the scan, are the suspect.
- Past saturation prio is worse than fifo even without hints (w1 short p99 at 450k: 888–1080 vs 523–586 µs), possibly because it runs helper threads (runtime packet and timer threads) first; untested.

## 6. Hypotheses

1. **The tail is outside the queue** (wait 0.51 vs p99 52.5 µs, depth 1.23, zero late at pick). Reordering cannot help further on w1. Hook outside the policy region: let a newly ready HIGH thread interrupt a running NORMAL one, or reserve a core for HIGH.
2. **HIGH threads will compete with each other.** prio runs them oldest first, ignoring deadline and service hints; at 450k HIGH wait is already 12.3 µs, depth 5.17, late at pick 3.5%. Policy: earliest deadline first within a class. Workload: latency-critical kinds with different deadlines or service times, or HIGH bursts.
3. **Other classes need protection.** At 450k prio adds 23% to long p99 and 70.7k threads overflowed the 32-slot queue; no workload has LOW, so the LOW acceptance rule is untested. Policy: aging (promote after a bounded wait). Workload: add a LOW kind.

## 7. Lessons

workload: prio already removes w1's queueing penalty (HIGH wait 0.51 µs, short p99 95.5 to 52.5 µs), so the next workload should make latency-critical requests compete with each other at the headline load, via kinds with different deadlines or service times, bursts, or a LOW kind.
policy: On w1 the remaining short tail is not queue wait (0.51 µs mean vs 52.5 µs p99, zero late at pick), so target ordering among HIGH threads by deadline or service hint, or propose a hook outside the policy region that stops HIGH work waiting behind a running long request.
