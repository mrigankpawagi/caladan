# Generation 3: measurement report

## 1. Headline

The headline load for w4 is 380k req/s nominal, which is its top level. The score is `get` p99 in µs, the median of two repeats with the range in brackets. "Met" is the share answered within 100 µs.

| Policy / mode | Score | vs fifo | query p99 | batch p99 | scan p99 | get / query met % | Throughput |
|---|---|---|---|---|---|---|---|
| fifo / hints | 167.0 (165–169) | 0% | 187.0 | 186.5 | 186.5 | 94.15 / 90.66 | 370,546 |
| prio / hints | 139.5 (138–141) | −16% | 158.5 | 234.5 | 252.5 | 96.07 / 92.91 | 370,401 |
| edf_high / hints | 140.5 (135–146) | −16% | 160.0 | 239.0 | 255.5 | 96.09 / 92.87 | 370,474 |
| sjf_guard / hints (champion) | 86.0 (85–87) | −49% | 161.5 | 241.5 | 258.0 | 99.73 / 92.40 | 370,372 |
| fifo / ignore | 163.0 (161–165) | −2% | 182.5 | 183.0 | 183.0 | 94.40 / 90.98 | 371,346 |

Bursts raise the champion's get p99 from 55.0 (w3 at 400k) to 86.0, at a lower load. It still beats edf_high by 39%, close to its 37% lead on w3.

## 2. Is it real?

- **Real:** sjf_guard (85–87) against every other policy (135–169) is far beyond the 6% noise band.
- **Noise:** prio vs edf_high (1%), fifo hints vs ignore (2.4%), and query p99 across the three priority policies (158.5–161.5).
- **Small but consistent:** query met for sjf_guard is 0.47 points below edf_high. The repeats do not overlap (92.23/92.57 vs 92.60/93.14).
- **Repeat spread:** the largest is 8% (edf_high 135/146), under the 15% re-run rule.

## 3. Where the get's time goes (sjf_guard, 380k)

- **Latency:** get p50 is 14 µs (11 at 100k) and p99 is 86. On w3, sjf_guard had 30.5 at 350k and 55.0 at 400k. So bursts add about 31–55 µs at p99. That is 1.5–2.5 query run times, at about 21 µs each.
- **Queue wait:** the mean HIGH wait is 8.59 µs (0.29 at 100k). If queries wait at least as long as under edf_high (10.20), the mean get wait is at most 3.8 µs. So the get tail comes from rare moments, which means the bursts.
- **Depth:** 1.55. Little's law says waiting threads = arrival rate × mean wait. That gives about 0.5 waiting threads per core, less than half the backlog the workload's model implies.
- **Other counters:** inversions are 0. Overflow is 57 threads out of about 891k HIGH picks. Steals are 27% (fifo 32%).
- **Deadlines:** late at pick is 0.85%, yet 7.6% of queries miss at the client. So about 5% of HIGH picks are queries picked before their deadline that still miss (0.4% at 300k).

**The workload hypothesis is only partly supported.**
- **For:** these near-late queries are the ones the urgent rule promotes. Between 300k and 380k they grow from 0.4% to 5% of HIGH picks, while get p99 grows from 47 to 86.
- **Against the strong form:** edf_high already makes a get wait behind every older query. If urgent queries were the main blocker, sjf_guard's lead over edf_high would shrink as load rises. Instead it grows: the get p99 ratio is 0.72, 0.66, 0.64 and 0.61 from 300k to 380k.
- **Not measurable yet:** no counter separates waits behind urgent queries from other waits.

**Conclusion:** gets lose time queueing behind other HIGH work during bursts, plus waiting for the thread already running. Stealing and overflow are not the cause.

## 4. Costs

- **Queries:** p99 is 161.5 (edf_high 160.0). Query met is 0.47 points below edf_high and 1.74 above fifo.
- **Batch and scan:** batch p99 is 29% above fifo and scan p99 38% above. NORMAL wait is 20.19 vs 12.88 µs and LOW wait 22.74 vs 12.99. Prio and edf_high pay about the same.
- **Drops and CPU:** there are zero drops at every level. Every run uses 7.98 cores, because the cores spin.

## 5. Anomalies

- **Clean runs:** no failed or saturated levels, one code version (31c94fd), and adherence of at least 99.77%. Kind and class rows match (class:high 296,047 = get 73,943 + query 222,104).
- **New: client sends below nominal.** With bursts, the client sends 2.5–6.3% fewer requests than the nominal rate. That is 93.7k at 100k and 370.5k at 380k; on w3 it was within 0.6%. It affects every policy equally.
- **Model overshot:** the workload's corrected predictions were 118–123 µs for sjf_guard and 220–225 for fifo. Measured: 86 and 167.
- **Built-in check passes:** get p99 at 100k is 13.0–14.0 µs, as on w3.

## 6. Hypotheses for the policy agent

To be accepted, a policy needs get p99 at or below 77.4 µs and query met at or above 91.40%. Slack is how long a thread can still wait and still finish on time.

1. **Let a get pass an urgent query that can spare the time.**
   - **Rule:** run a short HIGH thread first when the most urgent query's slack exceeds that thread's expected run time.
   - **Evidence:** the 31–55 µs burst penalty and the 5% near-late queries.
   - **Why first:** it tests the workload hypothesis directly. Each pass costs a query about 6 µs.
2. **Stop promoting queries that will miss anyway.**
   - **Rule:** count a query as hopeless once its slack falls below the time it still needs outside the queue, not below zero. At light load about 13 µs of a query's 30 µs is not run time.
   - **Evidence:** 5% of HIGH picks are on time at pick yet miss at the client.
3. **Changes outside the policy region.**
   - **Counters:** queue wait per kind, and a count of picks where the urgent rule overrode short-first order. Together they would show whether hypothesis 1 or 2 is right.
   - **Preemption:** still the limit on the floor; w1–w3 stopped at 51–55 µs.

## 7. Lessons

workload: w4's bursts hurt less than modeled (about 0.5 threads waiting per core; sjf_guard get p99 86 µs vs a predicted 118–123), and the client sends 2.5–6.3% below nominal under bursts, so size backlogs from measured depth and sent rate.
policy: On w4 sjf_guard's lead over edf_high grows with load (39% at the headline), so urgent queries are at most part of the get's 31–55 µs burst penalty; let gets pass urgent queries with slack to spare, or stop promoting queries that will miss anyway, keeping query met at or above 91.40%.
