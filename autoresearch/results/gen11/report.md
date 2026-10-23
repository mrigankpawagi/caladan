# Generation 11: measurement report

## 1. Headline

w12 at 100k req/s. Values are p99 in µs, as the median of two repeats.

| Policy | get (score) | vs fifo | put | query | sync | multiget | batch | scan | lease | Resp/s |
|---|---|---|---|---|---|---|---|---|---|---|
| fifo | 676.0 | 0% | 820.5 | 751.0 | 1102 | 1096 | 755.5 | 753.0 | 668.5 | 99,680 |
| prio | 560.0 | −17% | 706.5 | 636.0 | 981.0 | 965.5 | 1042 | 1124 | 555.5 | 99,463 |
| **sjf_mixed** | **236.5** | −65% | 348.5 | 866.0 | 450.5 | 857.0 | 1102 | 1177 | 131.5 | 99,378 |
| sjf_unit | 243.0 | −64% | 335.5 | 864.0 | 438.5 | 841.0 | 1100 | 1173 | 132.5 | 99,506 |
| fifo/ignore | 667.0 | −1% | 807.5 | 744.0 | 1102 | 1099 | 751.0 | 749.0 | 666.5 | 99,333 |

This generation added leases (100 µs deadline) on the original time scale. They changed nothing measurable for the w11 kinds. On w11 at 90k the champion's get p99 was 242.0 and fifo's 679.0.

## 2. Is it real?

- **Real:** sjf_mixed against fifo (−65%) and against prio (−58%).
- **Noise (under the 6% band):**
  - sjf_unit against sjf_mixed (+2.7%);
  - fifo/ignore against fifo (−1.3%);
  - w12 against w11, which is also a comparison across sessions.
- **Repeats:** sjf_mixed's get p99 repeats are 229 and 244.

## 3. Where the gets' time goes (sjf_mixed, 100k)

- **Latency:** p50 32.0 and p99 236.5, against 17.0 and 27.5 at 35k.
- **Runqueue wait:** p99 161.8, or 68% of the p99. The other ~75 µs is spent outside the runqueue.
- **Counters:** mean HIGH wait 45.41 µs, depth 2.12, inversions 0, late at pick 1.95%, steals 26.0%, overflow 0. Get deadline-met is 99.94%.

**The 161.8 µs of wait splits into two parts:**
- **Floor, about 95 µs:** w9's value scaled by four is 95.6. These are running 82–145 µs requests that no ordering can pass.
- **Lost lead, about 66 µs:** the gets' wait is 0.79 of the puts' (w11 0.83, w9 0.44). Among gets, puts and syncs the order is still close to oldest-first.

**Why:** the gen 10 analysis of the fixed constants still applies. The 50 µs drop allowance hides the 145 µs syncs and flushes. The 250 µs split lumps gets with multigets. The leases form a fourth label (the key lengths are learned under), so there are four labels in five slots.

**What remains removable:** about 66 µs. That would put get p99 near 170.

**Conclusion: queueing.**

**Leases:** p99 131.5 with runqueue-wait p99 5.7, so about 126 µs is spent outside the runqueue, waiting behind a running request. Helper (packet-processing thread) wait is 41.15 µs. Deadline-met is 94.89% (fifo 62.36%), short of the predicted 96–99%. No ordering can fix this.

## 4. Costs (sjf_mixed against fifo)

- **Gains:** put −58%, sync −59%, multiget −22%, lease −80%.
- **Losses:** query +15% (deadline-met 90.81% against 88.85%), batch +46%, scan +56%.
- **Waits:** NORMAL 135.38 against 83.20 µs, LOW 152.64 against 84.66.
- **CPU:** 7.98 cores.

## 5. Anomalies

- No failed or saturated levels.
- Hinted overflow at 100k: fifo 14, prio 10, sjf_mixed 0.
- class:high has 81,531 requests against 81,447 for the HIGH kinds, so hints reached the scheduler.
- **sjf_unit's rows say nothing about its time unit.** It is within 6% of sjf_mixed on 46 of 48 kind×load cells. The exceptions are get at 35k (−2.5 µs) and sync at 110k (−6.9%). This was expected: the leases hold its unit at 1. Even if the table were cleared, lengths of hint plus 4 µs would rank puts, gets and queries in the same order. Counters needed: each core's unit and the number of table clears.

## 6. Hypotheses

**Thresholds on w12 at 100k:**
- get p99 at most 212.8;
- p99 at most: put 435.6, query 1082.5, sync 563.1, multiget 1071.3, batch 1377.5, scan 1471.3, lease 164.4;
- deadline-met at least: get 98.94%, put 98.51%, query 89.81%, multiget 99.00%, lease 93.89%.

**Threshold on w11 at 90k:** get p99 at most 266.2.

1. **Read the unit from the deadline most HIGH work carries, not the tightest.** That deadline is 400 µs on w12, since leases are about 12% of HIGH picks, and 100 µs on w9. Leases still rank first at unit 4. Predicted: get wait p99 95–120, p99 170–200.
2. **Scale per thread or per label from its own deadline.** Risk: w9's 300 µs multigets would move, so w9 must be judged again.
3. **Outside the policy region:** preemption, and packet processing on every reschedule. Evidence: the leases' 126 µs outside the runqueue.

## 7. Lessons

workload: On w12 the 2 µs leases left every w11 kind within 3% of its w11 value at matched load (champion get p99 236.5 vs 242.0, fifo 676.0 vs 679.0), and the leases' own tail lies outside the runqueue (p99 131.5, wait p99 5.7), so a second time scale tests only how a policy chooses its unit.
policy: A unit taken from the tightest deadline a core sees is pinned at 1 by w12's 100 µs leases (sjf_unit matched sjf_mixed within 6% on 46 of 48 cells), so read the unit from the deadline most HIGH work carries or per label while keeping leases first, and ask for the per-core unit and table-clear counters, because unit 1 and table clears give the same order here.
