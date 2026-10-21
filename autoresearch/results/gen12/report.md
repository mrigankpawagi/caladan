# Generation 12: measurement report

(Written in parallel with the gen 12 policy agent to fit the node lease; the
policy agent worked from the gate numbers instead.)

## 1. Headline (w13, 100k, p99 in µs, median of 2 repeats)

| Policy | get (score) | vs fifo | put | query | sync | multiget | batch | scan | lease | Resp/s |
|---|---|---|---|---|---|---|---|---|---|---|
| fifo | 657.0 | 0% | 785.5 | 732.5 | 1062 | 1074 | 731.0 | 730.5 | 647.5 | 99,292 |
| sjf_mixed | 267.5 | −59% | 380.0 | 861.0 | 484.5 | 839.5 | 1106 | 1177 | 132.5 | 99,620 |
| **sjf_scale** | **259.0** | −61% | 362.0 | 853.0 | 468.5 | 819.5 | 1086 | 1150 | 132.5 | 99,388 |

The only change from w12 is that queries are due in 300 µs instead of 400. With that, the champion falls back to p10's level: get p99 was 184.0 on w12 and is 259.0 here.

## 2. Is it real?

- **sjf_scale and sjf_mixed decide the same way.** The get p99 difference is −3.2%, inside the 6% noise band. 47 of the 48 kind×load p99 cells agree within 6%. The one exception is leases at 35k (16 vs 19 µs).
- **The fall from w12 is real.** gen 11 and gen 12 ran about 45 minutes apart. Over that gap fifo moved −2.8%, while sjf_scale moved +41%.
- **Repeats:** 256/262 for sjf_scale and 260/275 for sjf_mixed.

## 3. Where the gets' time goes (sjf_scale, 100k)

**The prediction checks out: the unit is 1.**
- Shares of answered latency-critical (HIGH) requests, by deadline:
  - leases at 100 µs: 12.2%;
  - queries at 300 µs: 49.5%;
  - gets, puts and syncs at 400 µs: 32.8%;
  - multigets at 1200 µs: 5.5%.
- So 61.7% of fresh requests are due in 300 µs or less, and the median is 300 µs, below the 350 µs cut-off. That gives unit 1.
- Requests re-queued after a time-slice yield have shorter deadlines and add to that share. There are 17,075 yields per run, 6.5% of HIGH picks.
- **The behaviour matches unit 1.** The gets' wait p99 is 0.75 of the puts' (sjf_mixed 0.71). Under unit 4 on w12 it was 0.38.
- **Caveat:** there is no per-core unit counter, so this is inferred from these numbers, not read directly.

**Get latency and its parts:**
- p50 30.5 and p99 259.0, against 17.5 and 24.5 at 35k.
- Runqueue wait p99 is 178.1, 69% of the p99. About 81 µs is spent outside the runqueue.
- Counters: mean HIGH wait 42.88 µs, queue depth 2.06, inversions 0, late at pick 3.05% (1.62% on w12), get deadline-met 99.87%, steals 25.9%, hinted overflow 2.

**Splitting the 178.1 µs of wait:**
- **Floor, at most 84.5 µs:** p12's value on w12.
- **Lost unit-4 lead, about 70 µs.**
- **About 24 µs from the tighter query deadline.** Under sjf_mixed, get wait p99 went from 161.8 on w12 to 185.7 here, and p99 rose 13%. Queries now turn urgent earlier and pass gets.

**Conclusion: queueing.**

## 4. Costs (sjf_scale against fifo)

- **Gains:** put −54%, sync −56%, multiget −24%, lease −80%.
- **Losses:** query +16%, batch +49%, scan +57%.
- Query deadline-met is 84.72% against fifo's 82.30%.
- NORMAL wait is 127.74 against 76.52 µs. CPU use is 7.98 cores.

## 5. Anomalies

- No failed or saturated levels.
- class:high counts 81,606 requests against 81,603 for the HIGH kinds, so hints reached the scheduler.
- fifo pushes up to 157 threads past the 32-slot queue at 110k.
- Time-slice yields at 100k are about the same for all three policies: 16.2k–17.4k per run.

## 6. Hypotheses

**Thresholds at 100k on w13:**
- Score: get p99 ≤ 249.0 (10 µs better) or ≤ 233.1 (10% better).
- p99 limits: put 452.5, query 1066.3, sync 585.6, multiget 1024.4, batch 1357.5, scan 1437.5, lease 165.6.
- Deadline-met floors: put 98.41%, query 83.72%, multiget 99.00%, lease 94.17%.

**Older workloads:** score on w12 ≤ 202.4 and on w11 ≤ 197.5.

1. **A unit per label, from that label's own deadline.** Evidence: the wait ratio went from 0.38 to 0.75. Predicted get p99 about 195–215; the query urgency cost above remains. The multigets' 1200 µs label must be checked on w9–w12.
2. **One median, taken only over labels with short run-time hints, leaving queries out.** On w13 that median is 400 µs, so unit 4. On w12 that unit kept leases first. w1–w10 must still give unit 1.
3. **Outside the policy region:** keep a thread's ready time across a time-slice yield. That targets the 81 µs outside the runqueue and the 17k yields per run.

## 7. Lessons

workload: Cutting the queries' deadline to 300 µs pinned sjf_scale's unit at 1 as designed (47 of 48 cells within 6% of sjf_mixed, get/put wait ratio 0.75 vs 0.38 on w12), but the tighter deadline alone also added about 24 µs to the gets' wait p99 (sjf_mixed 161.8 → 185.7, fifo −2.8%), so changing a deadline to test the unit also shifts urgency order.
policy: A per-core unit taken from one median follows whichever deadline holds half the HIGH picks (queries at 300 µs, 49.5%, on w13), so take the unit per label or from the short-hinted labels only, keep leases first, and budget about 24 µs of get wait that earlier-urgent queries will still take.
