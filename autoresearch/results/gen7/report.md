# Generation 7: measurement report

## 1. Headline

These are the w8 results at its headline load of 380k req/s. The score is get p99 in µs: the median of 2 repeats, with the range in brackets. The other latency columns are p99 in µs.

| Policy | Score | vs fifo | put | query | sync | batch | scan | Throughput |
|---|---|---|---|---|---|---|---|---|
| fifo | 210.5 (205–216) | 0% | 217.5 | 229.5 | 244.0 | 227.5 | 230.0 | 378,694 |
| prio | 175.5 (173–178) | −17% | 184.0 | 195.0 | 210.0 | 294.5 | 319.0 | 378,770 |
| **sjf_nohint** (champion) | 145.0 (143–147) | −31% | 133.5 | 225.5 | 159.5 | 311.5 | 333.5 | 378,708 |
| sjf_learn (p5, rejected) | 89.5 (89–90) | −57% | 252.0 | 209.5 | 283.5 | 319.5 | 348.5 | 379,184 |
| sjf_timed (p6, rejected) | 96.5 (96–97) | −54% | 196.0 | 206.5 | 221.0 | 300.0 | 320.5 | 378,940 |
| fifo / ignore | 205.0 (201–209) | −3% | 211.5 | 224.5 | 239.5 | 225.0 | 224.0 | 378,416 |

Giving syncs the puts' 1 µs hint raised the champion's get p99 from 116.5 µs on w7 (measured in the gen 6 session) to 145.0. sjf_guard was not measured. Every HIGH kind now has a run-time hint, so it would decide exactly as sjf_nohint does.

## 2. Is it real?

- **Real** (same session, repeats do not overlap, beyond the 6% band):
  - champion vs fifo (−31%);
  - sjf_learn and sjf_timed vs the champion (−38%, −33%);
  - sjf_learn vs sjf_timed (−7%; repeats 89/90 vs 96/97);
  - the learners' put deadline-met (82.77/82.82% and 85.84/85.58%, vs the champion's 96.75/96.63%).
- **Noise:** fifo vs fifo/ignore (2.6%).
- **Across sessions:** fifo, fifo/ignore and prio never read run-time hints, so they make the same decisions on w7 and w8. Between the two sessions their scores moved +5.0%, +3.8% and −3.0%, and fifo's query deadline-met moved −1.4 points. That is the drift band.
  - The champion's +24% score change and its get wait p99 change (61.8 → 97.3 µs) are far outside it.
  - Its put deadline-met change (97.98 → 96.69%) is within it.
- **Check:** every policy's get p99 at 100k is 13–14 µs.

## 3. Where the favored kind's time goes (380k)

Each cell is p99 in µs / runqueue-wait p99 in µs / deadline met %.

| Kind | sjf_nohint, w7 (gen 6) | sjf_nohint, w8 | sjf_learn, w8 | sjf_timed, w8 |
|---|---|---|---|---|
| get | 116.5 / 61.8 / 98.28 | 145.0 / 97.3 / 95.79 | 89.5 / 25.8 / 99.71 | 96.5 / 40.3 / 99.36 |
| put | 117.5 / 45.5 / 97.98 | 133.5 / 89.0 / 96.69 | 252.0 / 203.8 / 82.79 | 196.0 / 152.2 / 85.71 |
| query | 219.5 / 164.5 / 83.28 | 225.5 / 169.1 / 82.94 | 209.5 / 152.2 / 86.20 | 206.5 / 152.1 / 86.30 |
| sync | 174.5 / 91.9 / – | 159.5 / 88.5 / – | 283.5 / 206.1 / – | 221.0 / 148.1 / – |

**The champion's gets.** Get p50 is 19.0 µs and p99 is 145.0 µs (11.0 and 14.0 at 100k).
- **Queue wait vs latency:** runqueue wait is 97.3 µs of the p99. The rest (p99 minus wait p99) is 47.7 µs, against 54.7 on w7. So the whole 28.5 µs rise is queueing.
- **Counters (w7 value in brackets):**
  - mean HIGH wait 15.54 µs (14.66);
  - queue depth 1.91 (1.93);
  - inversions 0;
  - late at pick 2.75% of deadline picks (2.61%), while 4.21% of gets miss at the client (1.72%);
  - steals 29.6% (29.1%);
  - hinted overflow 230 of about 910k HIGH picks.

**Why.** The champion ranks a HIGH thread by its *turn*: the thread's deadline plus 8 times its run-time length, counted from when it became ready.
- On w7 a sync had a blank run-time hint. The champion counts a blank as 8 µs, which gave syncs a turn of +164, behind gets (+116).
- On w8 the sync's 1 µs hint gives it the puts' turn (+108), ahead of gets. The 8 µs default no longer applies.
- Syncs and puts now wait alike (88.5 vs 89.0 µs).
- The champion on w8 reproduces sjf_guard on w7 (get 139.0 / 96.0, put 140.0 / 94.6).

**Conclusion:** the champion's gets queue behind 30 µs syncs that are ranked as 1 µs puts; stealing and overflow are not the cause.

**Why the learners cut the get tail.** Both learning policies learn one length per run-time hint value.
- Gets' 2 µs hint is honest, so their learned length stays short.
- The "1 µs" label now averages about 17.6 µs per request, because a third of those requests are 30 µs syncs (from the w8 notes).
- So gets run ahead of puts and syncs. Get wait p99 falls to 25.8 µs (sjf_learn) and 40.3 µs (sjf_timed), as low as sjf_learn's 25.0 on w5.
- sjf_learn's 7 µs edge over sjf_timed fits p4's narrower rescue rule against p3's 20 µs urgency window. The two families showed the same gap on w4b (86.5 vs 94.0).

**Why puts pay on w8 but not on w5.** Requests with the same hint value share one learned length.
- **On w5** only puts carry "1 µs". They average about 9.4 µs, which gives a turn near +175: behind gets but well ahead of queries (+268 at 21 µs). In the paired runs puts lost nothing:
  - wait p99 39.6 vs 38.6 µs;
  - deadline met 98.66 vs 98.65%;
  - p99 106.0 vs 106.5 µs.
- **On w8** syncs nearly double that average (turn about +241). The learned estimate also leans toward long runs. So puts end up level with queries or behind them.
  - Under sjf_timed, put wait p99 equals the queries' (152.2 vs 152.1 µs).
  - Under sjf_learn it is higher (203.8 µs). The likely reason is p4's rule, which gives up on a thread with under 13 µs to spare. An inflated length makes puts reach that point sooner.
- **Even the median put now waits:** put wait p50 is 3.9 and 3.6 µs (champion 0.5), and put p50 is 39.0 µs (champion 22.0).
- **The loss grows with load:** sjf_learn's puts trail the champion by 1.4, 4.6, 8.5 and 13.9 points of deadline-met at 300k, 330k, 355k and 380k.

## 4. Costs

- **Learners vs champion:**
  - Put deadline-met falls 13.9 points (sjf_learn) and 11.0 points (sjf_timed), below even fifo's 86.27%.
  - Put p99 rises 89% and 47%; sync p99 rises 78% and 39%.
  - Queries gain: deadline-met 86.20% and 86.30%, vs 82.94%. Overall deadline-met rises from 87.34% to 88.44% and 88.83%. The misses move from queries and gets onto puts.
  - Batch and scan p99 stay within ±5%.
- **Champion vs fifo:** batch p99 +37%, scan p99 +45%; NORMAL wait 34.59 vs 20.96 µs.
- **CPU and drops:** 7.98 cores everywhere; zero drops; scans answered 100%.

## 5. Anomalies

- **Clean runs:** no failed or saturated levels. All runs used one code sha (7f53df7), adherence was at least 99.78%, and kind and class rows agree within 3 req/s.
- **Predictions in the w8 notes that missed:**
  - champion get p99 145.0 (predicted 125–140);
  - champion get wait p99 97.3 (predicted 85–96);
  - champion sync wait p99 88.5 (predicted 55–70). Syncs tie with puts instead of going ahead of them.
  - For the learners: gets −33 to −38% (predicted −9 to −11%), and puts −11 to −14 points (predicted about −2).
- **Repeats:** fifo's score spread is 5.3%. The champion's hinted overflow is 39 in one repeat and 420 in the other, under 0.05% of picks either way.
- **w5 paired rows:** sjf_guard measured 102.5 µs, 4% above its gen 4 value. That is drift.

## 6. Hypotheses for the policy agent

**Thresholds on w8** (against sjf_nohint at 380k):
- score at most 135.0 µs;
- deadline-met at least 95.69% for puts and 81.94% for queries;
- p99 at most 166.9 µs (put), 281.9 (query), 199.4 (sync), 389.4 (batch), 416.9 (scan).

Both learners fail on put deadline-met, put p99 and sync p99. On w7 a new policy needs get p99 of at most 128.2 µs and put deadline-met of at least 96.98%.

1. **Let a learned length rise only a bounded amount above its hint.**
   - Evidence: on w5 the "1 µs" estimate sat between gets and queries, and puts lost 0.0 points while gets gained 18 µs. On w8 syncs pushed it to the queries' level, and puts lost 11–14 points.
   - Idea: use p6's two-way learning, capped at the hint plus about 8 µs. Two-way learning keeps the w6 win, where a stale hint must come down. "1 µs" requests would then rank as 9 µs long (turn +172): behind gets and ahead of queries, whose learned length (about 21 µs) is under their own cap.
   - Risk: on w7, capped puts (+172) would fall just behind syncs with a blank hint (+164). The default length for a blank hint should therefore be above the cap.
2. **p4's rescue rule is worth about 7 µs for gets, but only with capped lengths.**
   - Evidence: get wait p99 is 25.8 µs under sjf_learn vs 40.3 under sjf_timed, but put wait p99 is 51.6 µs worse.
   - Idea: test the cap on p3's 20 µs urgency window first.
3. **No policy can tell syncs from puts; the fix lies outside the policy region.**
   - Evidence: under every hint-reading policy, syncs and puts wait alike (88.5/89.0, 148.1/152.2, 206.1/203.8 µs).
   - Idea for the owner: give each kind a learning key that is separate from its hint.
   - Also: roughly 64 µs of sjf_learn's get p99 is spent outside the runqueue. That includes waiting for a running 30 µs sync, which cannot be passed (no preemption).

## 7. Lessons

workload: On w8, giving 30 µs syncs the puts' exact 1 µs hint raised the champion's get runqueue-wait p99 from 61.8 µs (w7) to 97.3 and made syncs and puts wait alike under every hint-reading policy, so folding a long kind into a short kind's hint value defeats both fixed rankings and per-hint learning.
policy: Per-hint learning cut w8's get p99 from 145.0 to 89.5–96.5 µs but cost puts 11–14 points of deadline-met because syncs inflate the shared '1 µs' estimate to the queries' level, while on w5, where only puts carry that hint, it cost them nothing (98.66 vs 98.65%), so cap how far a learned length may rise above its hint (about 8 µs) to move mixed labels behind gets but keep them ahead of queries.
