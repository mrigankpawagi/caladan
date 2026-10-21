# Generation 4: measurement report

## 1. Headline

w5 is measured at its headline load of 390k req/s, which is its top level and about 86% of estimated capacity (w4b's 380k was also about 86%). The score is get p99 in µs, the median of 2 repeats with the range in brackets.

| Policy | Score | vs fifo | put p99 | query p99 | batch p99 | scan p99 | Throughput |
|---|---|---|---|---|---|---|---|
| fifo | 192.0 (188–196) | 0% | 199.0 | 210.0 | 210.0 | 209.5 | 388,930 |
| prio | 159.0 (158–160) | −17% | 167.0 | 177.5 | 271.0 | 292.5 | 388,709 |
| edf_high | 161.5 (159–164) | −16% | 170.0 | 181.0 | 272.0 | 295.5 | 389,016 |
| **sjf_guard** (champion) | 98.5 (98–99) | −49% | 103.5 | 187.0 | 270.5 | 291.5 | 387,884 |
| sjf_rescue (rejected) | 94.0 (94–94) | −51% | 98.5 | 198.0 | 286.5 | 311.5 | 389,346 |
| fifo / ignore | 193.0 (191–195) | +1% | 201.0 | 212.0 | 212.5 | 210.5 | 388,682 |

Adding puts with a hidden 30 µs flush raised the champion's get p99 only from 94.0 (w4b) to 98.5 µs.

## 2. Is it real?

- **Real:** both sjf policies against all the others (94–98.5 vs 159–193).
- **Noise (under 6%):** sjf_guard on w5 vs w4b (+4.8%), prio vs edf_high (1.6%), fifo hints vs ignore (0.5%), and sjf_rescue vs sjf_guard (−4.6%). The last is consistent, though: its repeats do not overlap (94/94 vs 98/99).
- **Beyond noise:** sjf_rescue's own rise from w4b (86.5 to 94.0, +8.7%).
- **Repeat spread:** the largest is fifo's 188/196 (4%). Per-kind wait p99 for gets agrees within 1 µs between repeats.

## 3. Where the get's time goes

"Wait" below is runqueue wait: the time from a handler thread being queued until it starts. Each cell is latency p99 / wait p99 µs, with wait's share of latency in brackets. The two percentiles need not come from the same requests, so each share is only approximate.

| Policy | get | put | query |
|---|---|---|---|
| fifo | 192 / 148.0 (77%) | 199 / 148.6 (75%) | 210 / 147.9 (70%) |
| prio | 159 / 119.7 (75%) | 167 / 118.9 (71%) | 177.5 / 118.1 (67%) |
| edf_high | 161.5 / 120.3 (74%) | 170 / 120.1 (71%) | 181 / 120.6 (67%) |
| sjf_guard | 98.5 / 43.3 (44%) | 103.5 / 37.7 (36%) | 187 / 129.4 (69%) |
| sjf_rescue | 94.0 / 40.2 (43%) | 98.5 / 36.8 (37%) | 198 / 143.4 (72%) |

Median wait is 0.4–0.7 µs for every kind and policy.

**Champion (sjf_guard), gets at 390k:**
- **Latency:** p50 is 16 µs (11 at 100k) and p99 is 98.5.
- **Queue wait:** wait p99 is 43.3 µs, about 44% of the get's p99. At 300k it is only 9.3 of 55.5. The remaining ~55 µs is outside the runqueue: the packet waiting for a busy core, plus network and service. That matches the 51–55 µs floor seen on w1–w3.
- **Other counters:**
  - Mean HIGH wait is 11.51 µs (0.30 at 100k), and queue depth is 1.78.
  - Inversions are 0.
  - Late at pick is 1.50%, while 0.91% of gets miss at the client.
  - Steals are 28.4% (fifo 34.7%).
  - Overflow is 90 hinted threads out of about 934k HIGH picks.

**Does trusting the put's 1 µs hint hurt gets?** Visibly, but only a little.
- Under both sjf policies puts wait less than gets: 37.7 vs 43.3 µs under sjf_guard and 36.8 vs 40.2 under sjf_rescue. The gap is 3–12 µs from 340k to 390k. Under prio, edf_high and fifo the two kinds wait the same, within 1 µs.
- Puts, which sjf_guard ranks ahead of nearly all HIGH work, still wait 37.7 µs at p99. So ranking puts behind gets could save at most about the 6 µs gap.

**Conclusion:** the get tail is about 45% queueing during bursts, of which puts going first are a small part, and about 55% time outside the runqueue. Stealing and overflow are not the cause.

## 4. Costs

- **Queries:** sjf_guard's query p99 is 187 vs 181 under edf_high (noise). Query deadline met is 88.05% vs 88.73% under edf_high, and the repeats do not overlap. fifo gives 85.67%. sjf_rescue lowers it to 87.22%.
- **Batch and scan:** p99 is +29% and +39% over fifo, the same as prio and edf_high. NORMAL wait is 27.57 vs 17.83 µs and LOW wait 31.17 vs 17.87.
- **Drops and CPU:** zero drops, and 7.98 cores used everywhere.

## 5. Anomalies

- **Clean runs:** no failed or saturated levels, one code version (65e0924), adherence of at least 99.78%, and zero drops. Kind and class rows match (class:high 310,078 = get+put+query 310,077).
- **Built-in checks pass:** fifo's get p99 is 192, against 189 on w4b. Every policy's get p99 at 100k is 14.0 µs.
- **The intended mechanism is mostly absent:** the champion lost only 4.5 µs, which is within noise.
- **sjf_rescue now lowers query met** (−0.83 points). On w4b it raised it (+0.76). It also overflows more (336 hinted threads), though that is still only 0.04%.

## 6. Hypotheses for the policy agent

To be accepted, a policy needs get p99 ≤ 88.65 µs, query met ≥ 87.05% and put met ≥ 97.84%.

1. **Rank HIGH work by learned run time per hint, together with sjf_rescue's lost-thread rule.**
   - **Evidence:** the 3–12 µs get–put wait gap, and sjf_rescue already reaches 94.0.
   - **Expected gain:** a few µs, so it is borderline.
2. **Hint-aware stealing (a hook outside the policy region).** An idle core would steal the shortest HIGH threads first.
   - **Evidence:** even puts wait 37.7 µs at p99. The urgency rule does not explain this, because sjf_rescue changes it by less than 1 µs. Steals are 28%.
3. **Preemption or recorded packet arrival time (outside the policy region).** The ~55 µs outside the runqueue is 83% of the get's p99 at 300k.
   - **Also needed:** a counter that splits runqueue wait into waiting behind the running thread and waiting behind queued threads.

## 7. Lessons

workload: On w5 the hidden 30 µs put flushes raised sjf_guard's get p99 only from 94.0 (w4b) to 98.5 µs, within noise, because even puts, which sjf_guard ranks near the front, wait 37.7 µs at p99, so check the per-kind runqueue-wait gaps (here 3–12 µs) before building a workload on an ordering mistake.
policy: On w5 at 390k get runqueue wait p99 is 43.3 of 98.5 µs and puts wait 5.6 µs less than gets, so re-ranking puts by learned run time saves only a few µs, and reaching 88.65 µs also requires cutting the ~37 µs that even first-ranked HIGH threads wait or the ~55 µs spent outside the runqueue.
