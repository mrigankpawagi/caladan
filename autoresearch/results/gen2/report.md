# Generation 2: measurement report

## 1. Headline

These numbers are for w3 at its headline load of 400k req/s. The score is `get` p99 in µs, the median of two repeats. "Query met" is the share of queries answered within their 100 µs deadline.

| Workload | Policy / mode | Score | vs fifo | query p99 | batch p99 | scan p99 | Query met % | Throughput |
|---|---|---|---|---|---|---|---|---|
| w3 | fifo / hints | 94.5 | 0% | 114.5 | 113.5 | 114.0 | 98.64 | 398,628 |
| w3 | prio / hints | 84.0 | −11% | 103.0 | 139.5 | 154.5 | 98.94 | 398,618 |
| w3 | edf_high / hints (champion) | 87.5 | −7% | 107.0 | 147.0 | 158.5 | 98.84 | 398,082 |
| w3 | fifo / ignore | 89.5 | −5% | 109.5 | 108.5 | 111.0 | 98.77 | 398,781 |

With one shared deadline, edf_high goes from 53.0 on w2 to 87.5 here and matches prio, as w3 predicted.

## 2. Is it real?

- edf_high vs prio: 87–88 vs 81–87, a 4% gap, inside the 6% band. On w3 they behave as the same policy.
- Every policy is within 6% of fifo/ignore (88–91). fifo/hints and fifo/ignore schedule alike yet differ by 5.6%, as in gen1. No policy clearly helps gets.
- These differences are real: batch +23–30% and scan +36–39% over fifo (repeats 146/148 and 155/162), and query p99 −7 to −10%.
- The largest spread between repeats is 7% (prio 81/87), under the 15% re-run rule.

## 3. Where the get's time goes (edf_high, 400k)

- Get p50 is 14 µs (11 at 100k) and p99 is 87.5. Gets and queries both gain about 77 µs at p99 over their light-load medians. Under prio both gain 73; under fifo 83.5 and 84.5. They wait in one line.
- Mean HIGH queue wait is 3.81 µs (0.31 at 100k). The slowest 10% of HIGH requests gain at least 22 µs: the 90th-percentile latency (p90) minus the light-load median, for both kinds. That alone adds at least 2.2 µs to the mean; it rose 3.5. Queueing can explain the tail.
- Queue depth is 1.22, inversions 0, steals 26%, and overflow 152 threads out of about 958k HIGH picks.
- Late at pick is 0.36%, but 1.16% of queries and 0.78% of gets miss at the client, and 0.15% miss even at 100k.
- The same traffic on w2 had depth 1.23 and HIGH wait 3.12 µs, but get p99 was 53.

Conclusion: gets queue behind older queries. The only difference from w2 is which HIGH thread waits.

## 4. Costs

- **Batch:** p99 +29.5% vs fifo; NORMAL wait 6.96 vs 4.62 µs.
- **Scan:** p99 +39%, p99.9 476.5 vs 287, LOW wait 7.71 vs 4.63 µs. Its median moves only 1 µs.
- **Scan completion:** scans answered 100% at every level, 440k included, with zero drops in every run. The 90% rule is far from binding.
- **CPU:** 7.99 cores in every run, because the cores spin, so CPU cannot separate policies.

## 5. Anomalies

- No errors and no failed or saturated levels. Adherence is at least 99.85%. All runs used code 561241d.
- Kind and class rows match, so hints reached the scheduler: class:high 318,670 vs get + query 318,669; class:low equals scan and class:normal equals batch.
- fifo reproduces w2 as w3 predicted (94.5 vs 100.5).
- edf_high should match prio, but in both repeats it has a worse query p99 (107/107 vs 100/106) and more overflow (192/113 vs 36/23). The gap is small and unexplained.

## 6. Hypotheses for the policy agent

To be accepted, a policy needs get p99 ≤ 78.75 µs. The 25% rule allows query p99 up to 133.75, which is past the 100 µs deadline, so it does not protect queries. Aim to keep query met at or above 98.84%.

1. **Shortest expected run time first within HIGH, with a slack guard.** Slack is deadline − now − service_tsc.
   - **Rule:** if the least-slack HIGH thread has less than a guard G of slack left, run it. Otherwise run the HIGH thread with the smallest service_tsc.
   - **Evidence:** on w2, edf_high let gets pass nearly every query: get p99 fell to 53, but query p99 rose to 111.5 vs prio's 103.5. That +8 µs is above p90 (52 vs 51.5), exactly where w3 queries cross 100 µs.
   - **Sizing G:** a query takes 30 µs at light load for 17 µs of work, so about 13 µs of its client deadline is not run time. G ≈ 20 µs (those 13 µs plus one get of about 5.7 µs) is a starting point.
   - **Why it fits:** late at pick (0.36%) is well below query misses (1.16%), so most late queries still had some time left when picked but not enough; the guard targets those.
   - **Cost:** one clock read per pick.
2. **Clock-free: order HIGH by latest start time, deadline − k × service_tsc.**
   - **Rule:** k = 1 gives gets a 15 µs head start over queries; k = 4 gives 60 µs.
   - **Evidence:** HIGH wait of 3.81 µs and depth of 1.22 suggest most queries in the queue arrived recently, so a modest head start may cover most passes.
   - **Other workloads:** gets still go first on w2; w1 and w0 are unchanged.
3. **Leave class order and LOW alone; the remaining floor is outside the policy region.**
   - **Scans:** reordering inside HIGH leaves the same HIGH work ahead of each scan, so scan p99 should stay near 158.5 (limit 198).
   - **Floor:** w1 and w2 both stopped at about 52 µs. Going lower needs a hook outside the policy region: preempting a running query or scan, or hint-aware stealing (26% of hinted threads are stolen).

## 7. Lessons

workload: w3 works as intended (edf_high 87.5 µs equals prio 84.0 within noise, and gets and queries both gain about 77 µs at p99), but scans answer 100% even at 440k, so a later workload should make the LOW rule or inaccurate run-time hints bind.
policy: On w3 gets queue behind older queries with the same deadline (inversions 0, HIGH wait 3.81 µs), so let the run-time hint order HIGH work but guard each query's slack, keeping query deadline met at or above edf_high's 98.84% while aiming for w2's 53 µs.
