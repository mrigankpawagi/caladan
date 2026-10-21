# Generation 6: measurement report

## 1. Headline

w7 at its headline load of 380k req/s. The score is get p99 in µs, the median of 2 repeats, with the range in brackets. The other latency columns are p99 in µs.

| Policy | Score | vs fifo | put | query | sync | batch | scan | Throughput |
|---|---|---|---|---|---|---|---|---|
| fifo | 200.5 (195–206) | 0% | 206.0 | 219.0 | 234.5 | 218.0 | 219.5 | 378,520 |
| prio | 181.0 (179–183) | −10% | 186.5 | 200.0 | 214.5 | 301.0 | 325.5 | 378,763 |
| edf_high | 180.5 (177–184) | −10% | 187.5 | 199.5 | 215.0 | 295.0 | 319.5 | 378,182 |
| **sjf_guard** (champion) | 139.0 (137–141) | −31% | 140.0 | 217.5 | 144.5 | 297.0 | 320.0 | 378,856 |
| sjf_timed (rejected) | 96.5 (95–98) | −52% | 171.5 | 225.0 | 155.0 | 310.5 | 333.5 | 378,490 |
| fifo / ignore | 197.5 (197–198) | −1% | 204.0 | 217.0 | 233.0 | 213.5 | 217.0 | 378,408 |

The unhinted syncs raised the champion's get p99 from 98.5 µs on w5 to 139.0.

## 2. Is it real?

- **Real:** sjf_guard vs fifo (−31%); sjf_timed vs sjf_guard (−31%; repeats 95/98 vs 137/141); sjf_timed's loss of put deadline-met (93.30/93.71% vs 95.92/95.82%).
- **Noise (under the 6% band):** prio vs edf_high (0.3%); fifo vs fifo/ignore (1.5%); query deadline-met, sjf_guard vs sjf_timed (83.72 vs 83.66%).
- **Checks pass:** every policy's get p99 at 100k is 14.0 µs. The widest repeat spread is fifo's, 5.5%.

## 3. Where each kind waits (380k)

Each cell is p99 in µs / runqueue-wait p99 in µs / deadline met %.

| Kind | fifo | sjf_guard | sjf_timed |
|---|---|---|---|
| get | 200.5 / 159.0 / 88.92 | 139.0 / 96.0 / 96.28 | 96.5 / 31.1 / 99.26 |
| put | 206.0 / 156.9 / 87.50 | 140.0 / 94.6 / 95.87 | 171.5 / 106.6 / 93.50 |
| query | 219.0 / 158.4 / 83.85 | 217.5 / 161.4 / 83.72 | 225.0 / 167.1 / 83.66 |
| sync | 234.5 / 157.0 / – | 144.5 / 60.8 / – | 155.0 / 83.7 / – |

**The champion's gets:** p50 18.0 µs and p99 139.0 (11.0 and 14.0 at 100k); queue wait 96.0 µs of the 139.0 p99 (w5: 43.3 of 98.5); mean HIGH wait 14.96 µs (w5: 11.51); depth 1.87; inversions 0; late at pick 2.49% of HIGH picks while 3.72% of gets miss at the client; steals 30.2%; hinted overflow 70 of about 912k HIGH picks.

**Why:** a HIGH thread's *turn* in sjf_guard's order, counted from when it became ready, is the deadline plus 8 times the run-time hint, and a missing hint counts as zero. The order is therefore sync (+100 µs), put (+108), get (+116), query (+236), and syncs wait least (60.8 µs). Compared with w5, this raised get wait p99 from 43.3 to 96.0 µs and put wait p99 from 37.7 to 94.6 µs. Put deadline-met fell from 98.84% to 95.87%.

**Conclusion:** gets lose their time queueing behind syncs that sjf_guard ranks first. Stealing and overflow are not the cause.

**sjf_timed:** gets move to the front (wait p99 31.1 µs), syncs come next (83.7), and puts fall behind both (106.6). Its learned put lengths of 12–16 µs, inflated by the flushes, give puts a turn of +196 to +228 µs instead of +108. Puts lose 2.37 points of deadline-met here, after 1.69 on w5 and 1.40 on w6. Syncs cost gets little once gets run first: sjf_timed's get p99 is 96.5 µs here, only 5 µs above its 91.5 on w5.

## 4. Costs

- **Champion vs fifo:** batch p99 36% higher and scan p99 46% higher; NORMAL wait 33.10 vs 19.95 µs. Syncs gain the most (144.5 vs 234.5 µs).
- **Queries:** the champion's query deadline-met (83.72%) matches fifo's (83.85%) and is 2.8 points below prio's (86.51%), because every short kind passes queries.
- **Drops and CPU:** zero drops; 7.98 cores used everywhere.

## 5. Anomalies

- **Clean runs:** no failed or saturated levels, one code sha (ff0143a), adherence at least 99.76%. The class:high row equals get + put + query + sync within 1 req/s.
- **Repeats that disagree:** fifo on hinted overflow (460 vs 27) and on p99.9 (357 vs 294 µs); sjf_timed on batch p99 (323 vs 298 µs, 8%).
- **Prediction missed:** the champion's get wait p99 (96.0 µs) is above w7's predicted 65–90. Its get p99 (139.0) falls inside the predicted 120–145.

## 6. Hypotheses for the policy agent

**Thresholds on w7 (against sjf_guard at 380k):**
- **Score:** get p99 at most 129.0 µs (the 10 µs rule; 10% would mean 125.1).
- **Rule 6:** put deadline-met at least 94.87% and query deadline-met at least 82.73%. Syncs have no client deadline.
- **Rule 3:** p99 at most 175.0 µs for put, 271.9 for query, 180.6 for sync, 371.3 for batch and 400.0 for scan.
- **Rule 4:** scans answer at least 90% of requests at every level.

**Other workloads (w0–w7, w4 superseded):** rule 2 limits on get p99: w1 and w2 56.1 µs, w3 60.5, w4b 103.4, w5 108.35, w6 157.3. Rule 6 floors: on w5 put ≥ 97.84% and query ≥ 87.05%; on w6 put ≥ 97.26% and query ≥ 86.08%. w0 (rule 5): p99 at 300k at most 73.7 µs.

1. **An order that protects both puts and queries likely exists: sjf_guard's order with syncs moved between the short kinds and queries.** Evidence: on w5, sjf_guard's order (puts, then gets, then queries) gave get wait p99 43.3 µs and put deadline-met 98.84%; under sjf_timed, gets run ahead of syncs and sync p99 rose only 10.5 µs, to 155.0 (limit 180.6). Idea: count a missing run-time hint as about 8 µs, giving syncs a turn of +164 µs, between gets (+116) and queries (+236). No kind in w1–w6 lacks a run-time hint, so picks there stay sjf_guard's. Do not use the learned length (about 34 µs: syncs behind every query, over the 180.6 limit).
2. **If the policy learns run times, let learning only lower a hint.** Raising put lengths cost puts on three workloads; lowering the stale get hint is what won w6 (get wait p99 from 78.8 to 27.4 µs). Idea: use the smaller of the learned run time and the hint.
3. **Time outside the runqueue (outside the policy region).** About 65 µs of sjf_timed's get p99 is spent outside the runqueue; a running sync cannot be passed; 30.2% of hinted threads are stolen. Idea: preemption, packet processing at every reschedule, or hint-aware stealing.

## 7. Lessons

workload: On w7 an unhinted 30 µs HIGH kind that sjf_guard ranks first raised get and put runqueue-wait p99 from 43.3 and 37.7 µs (w5) to 96.0 and 94.6 while fifo's get p99 moved 4%, so a missing run-time hint is a clean lever that hurts every short deadline kind at once.
policy: sjf_timed's flush-inflated put length has now cost puts 1.4–2.4 points of deadline-met on w5, w6 and w7, so keep hinted kinds at their hint (learning may only lower it) and give an unhinted HIGH thread a length that ranks it after gets and puts but before queries (about 8 µs, not its learned 34 µs).
