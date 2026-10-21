# Generation 10: measurement report

## 1. Headline

These are the w11 results at the headline load of 90k req/s. The score is get p99 in µs: the median of two repeats, with the range in brackets. The other columns are p99 in µs.

| Policy | Score | vs fifo | put | query | sync | multiget | batch | scan | Throughput |
|---|---|---|---|---|---|---|---|---|---|
| fifo | 679.0 (673–685) | 0% | 808.0 | 738.0 | 1080 | 1104 | 742.0 | 736.0 | 89,502 |
| prio | 551.0 (546–556) | −19% | 704.0 | 620.0 | 941.5 | 929.5 | 1010 | 1106 | 89,524 |
| sjf_pair | 238.0 (225–251) | −65% | 338.5 | 827.0 | 454.0 | 834.0 | 1058 | 1135 | 89,414 |
| **sjf_mixed** (champion) | 242.0 (235–249) | −64% | 342.0 | 850.5 | 461.5 | 833.0 | 1084 | 1160 | 89,746 |
| fifo / ignore | 652.0 (646–658) | −4% | 787.5 | 726.5 | 1070 | 1086 | 722.5 | 724.5 | 89,680 |

w11 is w9 with every time multiplied by four. Measured against fifo, the champion did not suffer: it is −64% here, against −53% on w9 at the matching load (see section 5). What got worse is the gets' runqueue wait, measured against the champion's own w9 numbers scaled by four (section 3).

## 2. Is it real?

- **Real differences:** the champion against fifo (−64%) and against prio (−56%).
- **Noise (under the 6% band):**
  - sjf_mixed against sjf_pair (1.7%). They make the same decisions here, because fewer than two labels are capped (section 3).
  - fifo against fifo/ignore (4.0%).
- **Repeats:** sjf_pair's two repeats differ by 11% (225 and 251). That is outside the 6% band but under the 15% third-run rule. Every other policy's repeats are within 6%.
- **Comparison with w9:** this uses gen 8 and 9 runs, so it is across sessions (drift up to about 6%). The 1.7× ratio below is far beyond that.

## 3. Where the gets' time goes (sjf_mixed, 90k)

- **Latency:** get p50 is 31.5 µs and p99 is 242.0, against 17.0 and 22.5 at 30k.
- **Runqueue wait:** p99 162.2 µs, or 67% of the p99.
- **Counters:**
  - mean HIGH wait 49.24 µs;
  - queue depth 2.04;
  - inversions 0;
  - late at pick 2.06% of deadline picks, mostly queries (8.72% of queries miss, 0.09% of gets);
  - steals 28.7% (w9: 28.1%);
  - overflow 0.

**Only the gets lost ground against w9 scaled by four.** fifo's get p99 at 90k is 679.0 µs, which is four times its w9 value at 345k (4 × 169.5 = 678). So the comparison point is w9 at 345k. Runqueue-wait p99 in µs:

| Kind | w9 345k × 4 | w11 90k | Ratio |
|---|---|---|---|
| get | 95.6 | 162.2 | 1.70 |
| put | 221.6 | 196.4 | 0.89 |
| sync | 229.6 | 200.6 | 0.87 |
| multiget | 631 | 600.0 | 0.95 |
| query | 620 | 715.8 | 1.15 |

The gets lost their lead over puts and syncs:
- A thread's **turn** is its deadline plus 8 times its expected length. Gets' runqueue wait divided by puts' was 0.44 on w9, when gets' turn came 56 µs before puts'. It is 0.83 here, and 1.00 under prio, which does not order HIGH threads at all.
- So among gets, puts and syncs the order is now close to oldest-first.

**Which fixed constants bind.** A **label** is the learning key: the run-time hint, plus whether the deadline is more than 250 µs away. On w11 there are three labels, all on the far side of that split: "4 µs" (puts and syncs), "8 µs" (gets and multigets) and "68 µs" (queries). Run lengths are taken from fifo's medians at 30k: syncs, flushes and multigets about 145 µs, queries about 82, gets about 10, quick puts about 6.
- **Drop limit (twice the floor plus 50 µs) binds.** The limits are 66 µs for "4 µs" and 74 for "8 µs", against 145 µs runs. The "4 µs" label never sees the 43% of its requests that are long, so it learns about 6 µs against the gets' 10. That puts the gets' turn about 24–30 µs *behind* puts'.
- **Cap (floor plus 8 µs) does not bind for gets now.** It may bind for queries: the cap is 80 µs and they measure about 83. That is only one capped label, so p10's shared-length rule stays off.
  - Even with long samples kept, the cap would hold the gets' lead to 8 × (16 − 10) = 48 µs, or 12% of the deadline. On w9 the lead was 56% of the deadline.
- **Split (250 µs) binds structurally.** Both 400 and 1200 µs deadlines are past it, so gets and multigets share one label. This is harmless only because the drop limit throws away the multigets' samples.
- **Not binding:**
  - the too-late line (9 µs of slack): a get reaches it only after about 381 µs of waiting;
  - the blank length (17 µs) and the mixed-rule drop (4 µs).

No counter reports learned lengths or dropped samples, so these lengths are inferred, not measured.

**Conclusion: queueing.** Of the 162 µs of runqueue wait, about 95 is the four-times floor: 82–145 µs runs that no ordering can pass. About 67 is the lost lead. About 80 µs of the p99 lies outside the runqueue. Part of that is packets waiting for a busy core: mean helper wait is 41.4 µs, about 12 times w9's 3.5, not 4 times. fifo shows the same growth (13 times), so this is the runtime, not the policy.

## 4. Costs (sjf_mixed against fifo, 90k)

- **Gains:**
  - put −58%, sync −57%, multiget −25%;
  - put deadline-met 99.56% against 91.12%.
- **Losses:**
  - query p99 +15% (850.5), although query deadline-met rises from 89.70% to 91.28%;
  - against prio, query p99 is +37% and query deadline-met is 1.9 points lower;
  - batch +46% and scan +58%;
  - NORMAL wait 133.95 against 79.53 µs, LOW 149.65 against 79.34.
- **CPU and drops:** 7.98 cores, zero drops.

## 5. Anomalies

- **The headline is 90k, not the predicted 103k.** fifo's overall median is 128.5 µs at 90k and 164.0 at 97k, against a limit of 136.5 (1.5 × 91.0).
  - Long requests run at about 83 iterations per µs on both w9 and w11, not the calibrated 99.6. Query p50 minus put p50 is 19.0 µs on w9 and 77.0 on w11, a ratio of 4.05.
  - Matching 90k on w11 to 345k on w9 implies about 1 µs of non-work core time per request, not the 4 µs the workload agent assumed.
  - So 103k corresponds to about 395k on w9, and 109k keeps about 99% of the cores busy.
- **Predictions at 103k:**

| Quantity | Predicted | Measured |
|---|---|---|
| champion get runqueue-wait p99 | 220–320 | 288.4 |
| champion get p99 | 330–430 | 376.0 |
| get deadline-met | 96–98% | 99.30% |
| put runqueue-wait p99 | 150–200 | 287.2 |
| sync runqueue-wait p99 | 150–200 | 287.6 |
| fifo get p99 | 550–620 | 1052 |

  The first two held; the last four missed.
- **109k is unusable.**
  - Overflow ranges from 70k to 363k threads.
  - Repeats disagree: sjf_pair get p99 is 10,589 against 2,335.
  - sjf_mixed degrades most: get p99 14–18 ms, against 3.4–5.0 ms for fifo.
- **Clean runs:**
  - one sha (635c52d), no failed or saturated levels;
  - class rows match kind rows (class:high 71,648 against 71,647);
  - the client's adherence warning appears at every level, as on w10, with adherence at least 99.83%.

## 6. Hypotheses for the policy agent

**Thresholds on w11 at 90k:**
- get p99 at most 217.8 µs;
- p99 at most 427.5 µs (put), 1063.1 (query), 576.9 (sync), 1041.3 (multiget), 1355.0 (batch), 1450.0 (scan);
- deadline-met at least 98.56% (put), 90.28% (query), 99.00% (multiget).

1. **Scale the drop limit, the cap and the split together by one workload-wide time unit.**
   - The unit is the tightest HIGH relative deadline the core has seen, divided by 100 µs, and never below 1. It starts unset. It needs one stored word, which fits: w9 uses 4 of the 5 learning slots.
   - Keep the 4 µs per-request cost and the 13 µs late line fixed. The per-request overhead did not scale: light-load get p50 is 17.0 µs here against 11.0 on w9.
   - On w11 the unit is 4. The limits become a 216 µs drop limit, a 32 µs cap allowance and a 1000 µs split. The labels then count: puts and syncs 40 µs, gets 10, multigets 44, queries about 83 (under a cap of 104).
   - The turns become gets +480, puts and syncs +720, queries +1064, multigets +1552. Gets lead puts by 240 µs; w9 scaled by four gives 224.
   - **w1–w10 are unchanged by construction:** the unit is 1 there (the tightest deadlines are 60 or 100 µs). Verify this with the lockstep model used for p10.
   - **Risk if only the drop limit is scaled:** the labels would measure about 110 (puts), 87 (gets with multigets) and 83 µs (queries), and all three would be capped. They would be in the wrong order, so p10's rule would count all three at 12 µs. That reduces HIGH ordering to deadlines, as under prio (get p99 551.0).
   - **Predicted:**
     - get runqueue-wait p99 about 95–120 µs and get p99 about 180–205;
     - put and sync p99 +0–10% (w9 → w10: put wait 54.0 → 57.9);
     - multiget p99 +0–10%, with deadline-met at least 99.9%.
2. **A variant without stored state: scale per thread.**
   - Scale each thread by its own deadline, and key labels by hint plus a power-of-two bucket of the deadline.
   - This is simpler but not neutral on older workloads. On w9 the multigets' cap would go from 14 to 30 µs and their turn from +412 to +540, so w9 (multiget p99 233.5) must be judged again.
3. **Outside the policy region.**
   - Evidence: about 80 µs of the get p99, the four-times floor of about 95 µs, and helper wait growing about 12 times.
   - Needed hooks: preemption, packet processing on every reschedule, and hint-aware stealing.
   - Counters to request: learned length per label per core, dropped samples per label, and how often the cap binds.

## 7. Lessons

workload: On w11, light-load medians show long requests running at about 83 iterations per µs on both w9 and w11 and imply only about 1 µs of non-work core time per request, so 90k already matched w9's 345k (fifo get p99 679.0 against 4 × 169.5) and 103k–109k overloaded every policy; size load levels from the parent workload's measured light-load medians, not from the 4 µs allowance.
policy: On w11 the fixed 50 µs drop limit hides the 145 µs syncs, flushes and multigets from their labels, the fixed 8 µs cap would hold the gets' lead to 48 µs even without that, and the fixed 250 µs split no longer separates gets from multigets, so all three must scale together by a workload-wide unit equal to 1 on w1–w10 (which keeps those decisions identical), because scaling the drop limit alone would let p10's shared-length rule count puts, gets and likely queries all at 12 µs.
