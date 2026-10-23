# Generation 5: measurement report

## 1. Headline

w6 at its headline load of 390k req/s, the same as w5. The score is get p99 in µs: the median of 2 repeats, with the range in brackets.

| Policy | Score | vs fifo | put p99 | query p99 | batch p99 | scan p99 | Throughput |
|---|---|---|---|---|---|---|---|
| fifo | 197.5 (194–201) | 0% | 203.5 | 216.0 | 217.0 | 216.0 | 388,338 |
| prio | 161.0 (160–162) | −18% | 169.0 | 181.5 | 275.0 | 297.5 | 388,711 |
| edf_high | 165.5 (163–168) | −16% | 173.5 | 185.0 | 281.0 | 307.0 | 389,080 |
| **sjf_guard** (champion) | 143.0 (142–144) | −28% | 112.5 | 198.5 | 292.0 | 314.5 | 389,367 |
| sjf_learn (rejected) | 200.0 (200–200) | +1% | 104.5 | 193.0 | 280.0 | 301.5 | 388,788 |
| fifo / ignore | 192.5 (188–197) | −3% | 201.5 | 212.0 | 213.0 | 211.0 | 388,973 |

The stale 20 µs get hint raised the champion's get p99 from 98.5 µs (w5) to 143.0, and sjf_learn's from 85.0 to 200.0.

## 2. Is it real?

- **Built-in check passes.** The policies that ignore the run-time hint reproduce w5 within the 6% noise band: fifo +2.9%, prio +1.3%, edf_high +2.5%, fifo/ignore −0.3%.
- **Real:** sjf_guard from w5 to w6 (+45%; repeats 142/144 vs 98/99), sjf_learn (+135%), and sjf_guard vs prio (−11%; the repeats do not overlap).
- **Noise:** sjf_learn vs fifo on score (+1.3%), and prio vs edf_high (2.8%).
- **But not noise:** sjf_learn's get wait p99 is higher than fifo's (165.0/165.5 vs 153.6/151.0).
- **Repeat spread:** the largest is fifo/ignore, 188/197.

## 3. Where the get's time goes

Each cell is get latency p99 / runqueue-wait p99, in µs, with wait's approximate share in brackets.

| Policy | w5 | w6 |
|---|---|---|
| fifo | 192 / 148.0 | 197.5 / 152.3 |
| prio | 159 / 119.7 | 161 / 119.7 |
| sjf_guard | 98.5 / 43.3 (44%) | 143 / 78.8 (55%) |
| sjf_learn | 85 / 25.2 | 200 / 165.2 (83%) |

**Champion at 390k:**
- **Latency:** p50 is 23 µs (11 at 100k) and p99 is 143 (14 at 100k).
- **Most of the rise is queueing:** p99 rose 44.5 µs, of which 35.5 is runqueue wait. Time outside the runqueue grew from 55.2 to 64.2 µs.
- **Gets now routinely wait:** get wait p50 is 2.5 µs (0.5 on w5; puts 0.4, queries 0.7).
- **The wait tail stops just under 80 µs:** wait p99 is 62.6, 70.5, 75.1 and 78.8 µs from 300k to 390k.
  - sjf_guard's turn is the deadline plus 8× the hint, so a get now runs after every query that arrived before it or up to 24 µs after it.
  - Its urgency rule runs a thread first if it must start within 20 µs. With a 20 µs hint, that catches a get between 60 and 80 µs of waiting, if its deadline clock starts when it is queued. The plateau fits that window.
- **Other counters:**
  - Mean HIGH wait is 15.11 µs (11.51 on w5), and queue depth is 1.84.
  - Inversions are 0.
  - Late at pick is 1.80%, while 10.66% of gets miss at the client.
  - Steals are 32.3% (28.4% on w5).
  - Hinted overflow is 190 of about 937k HIGH picks.

**Conclusion:** the new cost is queueing behind queries that the stale hint ranks first. Stealing and overflow are not the cause.

**Why sjf_learn is worse than fifo.** Two rules on its card combine:
1. A HIGH thread's length is the larger of its learned run time and its hint plus 4 µs. Learning can only raise a length, so gets count as 24 µs, longer than queries (21).
2. It inherits sjf_rescue's "lost" rule: a thread with less than 13 µs to spare before it must start waits behind any shorter HIGH thread. A 24 µs get becomes lost about 63 µs in (100 − 24 − 13). From then on it waits behind every query and put, newer ones included, until the burst drains.

The numbers follow this. sjf_learn's get wait p99 stays near sjf_guard's while bursts are mild (56.0 and 66.7 µs at 300k and 340k), then runs away (120.8 at 365k, 165.2 at 390k, against fifo's 152.3). Under sjf_guard a get past 80 µs keeps its turn. sjf_learn's gets meet their deadline slightly more often (90.22% vs 89.34%), because it gives up only on gets that are already lost.

## 4. Costs (champion, w6 vs w5)

- **Queries:** p99 198.5 vs 187.0 µs. Deadline met 87.08% vs 88.05% (edf_high 87.73%, fifo 84.84%).
- **Puts:** p99 112.5 vs 103.5 µs. Deadline met 98.26% vs 98.84%.
- **Batch and scan:** +35% and +46% over fifo, as under prio and edf_high. NORMAL wait is 30.29 vs 18.72 µs.
- **Drops and CPU:** zero drops, and 7.98 cores used everywhere.

## 5. Anomalies

- **Clean runs:** no failed or saturated levels, one code version (11aeffa), adherence of at least 99.76%. Kind and class rows match within 2 req/s.
- **The champion only wins at the top level.** At 300k its gets do worse than fifo's: p99 95.5 vs 83.0 µs (prio 77.0), wait p99 62.6 vs 47.5. It beats prio only at 390k; at 365k the gap (133.5 vs 137.0) is noise.

## 6. Hypotheses for the policy agent

**Thresholds on w6** (against sjf_guard):
- Score: get p99 ≤ 133.0 µs. The 10 µs rule is the looser one here; 10% would mean 128.7.
- Rule 6: query deadline met ≥ 86.08% and put deadline met ≥ 97.26%.
- Rule 3: put, query, batch and scan p99 ≤ 140.6, 248.1, 365.0 and 393.1 µs.
- Rule 4: scans answer at least 90% at every level.

The policy is judged on w0–w6 (w4 is superseded). On w5, query deadline met must also stay ≥ 87.05%, the floor p5 missed.

1. **Let learned run times lower a hint, not only raise it.**
   - **Evidence:** the hint is the only change from w5. There, ranking by learned run time cut get wait p99 from 43.3 to 25.2 µs. Ranking gets by their observed run time restores the w5 order, under which sjf_guard scored 98.5.
   - **Idea:** use the learned length in both directions. Keep sjf_guard's urgency rule rather than the lost rule, which cost 1.5 query points on w5.
2. **A lost thread keeps its place.**
   - **Evidence:** get wait p99 is 165.2 µs under sjf_learn vs 78.8 under sjf_guard.
   - **Idea:** if building on p4 or p5, never make a lost thread yield to threads that became ready after it.
3. **Time outside the runqueue (outside the policy region).**
   - **Evidence:** 64.2 µs of the champion's p99, up 9 µs from w5.
   - **Idea:** process packets at every reschedule while hinted threads wait, or preemption.

## 7. Lessons

workload: On w6 the too-long get hint raised the champion's get p99 from 98.5 to 143.0 µs (get wait p99 43.3 to 78.8), while policies that ignore the hint moved less than 3%, so a hint error that ranks the scored kind behind the bulk kind is a clean, reproducible lever that shows up in runqueue wait.
policy: On w6 sjf_learn rates gets at 24 µs (it takes the larger of learned time and hint plus 4) and its lost rule then puts them behind every newer query (get wait p99 165.2 µs vs fifo's 152.3), so learned run times must be able to lower a hint, and a lost thread must keep its place instead of yielding to newer work.
