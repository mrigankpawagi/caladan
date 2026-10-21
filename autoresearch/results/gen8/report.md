# Generation 8: measurement report

## 1. Headline

These are the w9 results at the headline load of 370k req/s. The score is get p99 in µs: the median of two repeats, with the range in brackets. The other columns are p99 in µs.

| Policy | Score | vs fifo | put | query | sync | multiget | batch | scan | Throughput |
|---|---|---|---|---|---|---|---|---|---|
| fifo | 210.5 (207–214) | 0% | 217.5 | 229.5 | 244.5 | 244.5 | 231.0 | 231.0 | 368,415 |
| prio | 188.0 (185–191) | −11% | 196.0 | 207.5 | 224.5 | 224.5 | 316.5 | 341.0 | 369,096 |
| sjf_nohint | 142.0 (139–145) | −33% | 129.5 | 215.5 | 155.5 | 301.5 | 317.5 | 340.5 | 368,564 |
| **sjf_capped** (champion) | 95.0 (94–96) | −55% | 130.5 | 252.0 | 157.0 | 249.0 | 326.0 | 347.5 | 368,591 |
| fifo / ignore | 213.5 (213–214) | +1% | 221.0 | 232.5 | 247.0 | 246.0 | 232.0 | 231.5 | 368,330 |

Multigets share the gets' 2 µs run-time hint. Adding them raised the champion's get p99 from 83.0 (w8) to 95.0. At the same core time, fifo (210.5 → 210.5) and sjf_nohint (145.0 → 142.0) repeated their w8 values.

## 2. Is it real?

- **Repeats agree.** The widest spread is 4.2% (sjf_nohint, 139 and 145), inside the 6% noise band.
- **Real:** the champion against sjf_nohint (−33%) and against fifo (−55%).
- **Noise:** fifo against fifo/ignore (1.4%).
- **Across sessions (w8 → w9):** fifo did not move and sjf_nohint moved −2.1%, so drift is small here. The champion's +12.0 µs (+14.5%) and its get runqueue-wait p99 rise (25.4 → 40.9 µs) are both well beyond that drift.

## 3. Where the gets' time goes (sjf_capped, 370k)

- **Latency:** get p50 is 18.0 µs and p99 is 95.0, against 11.0 and 14.0 at 100k.
- **Runqueue wait:** p99 40.9 µs, so about 54.1 µs of the p99 is spent outside the runqueue (57.6 on w8). Of that, about 14 µs is network plus service (the light-load p99), and about 40 µs is the request waiting on a busy core before its thread exists.
- **Counters:**
  - mean HIGH wait 15.40 µs (w8: 14.15);
  - queue depth 1.96 (1.91);
  - inversions 0;
  - late at pick 2.67% of deadline picks, while gets miss 0.67% at the client;
  - steals 29.0% (28.9%);
  - hinted overflow 116 of about 887k HIGH picks.

**Why the champion lost less than predicted.** The prediction assumed the shared "2 µs" learned length sits at its 14 µs cap. The turn is the deadline plus 8 times the length. At the cap, gets get a turn of +212 against +204 for "1 µs" threads. That ranks gets 8 µs behind puts and syncs, exactly where sjf_nohint ranks them, and sjf_nohint's get wait p99 is 96.25 µs. The champion's is 40.9.

| Load | Champion w9 | Champion w8 | sjf_nohint w9 |
|---|---|---|---|
| 290k | 5.7 | 5.45 | 38.4 |
| 320k | 28.6 | 8.9 | 46.8 |
| 345k | 38.7 | 23.2 | 86.0 |
| 370k | 40.9 | 25.4 | 96.25 |

(Get runqueue-wait p99 in µs; w8 values are at the matching loads 300k to 380k.)

At 345k–370k the champion pays only about a quarter of the at-cap penalty. So the label is usually below the cap.

The timer explains this. I inferred it from the code; no counter shows the learned lengths.
- A run is timed only when the pick leaves at least 2 threads queued.
- The sample is kept only if the newest queued thread is still there at the core's next pick.
- Multigets have the latest turn of any HIGH kind (+348 to +412, against +268 for queries). So they run mostly after the backlog drains, from short queues. Their wait p50 is 4.7 µs against 0.5 for gets.
- A 34 µs run also leaves more time for the marked thread to be stolen than a 6 µs run does.

The estimator moves up 1/16 and down 1/64 of the gap. With 1 multiget in 4 samples (its traffic share) it would settle near 22 µs. It reaches the 14 µs cap at 1 in 11, and stays near 10 µs at about 1 in 25.

**Conclusion:** the gets' tail is mostly outside the runqueue (about 54 µs). Queueing behind a partly inflated shared label adds about 15 µs over the w8 floor of about 25 µs.

## 4. Costs

- **Puts and syncs** match sjf_nohint: put p99 130.5 µs and 97.02% deadline-met (sjf_nohint 129.5 µs, 96.94%); sync p99 157.0 vs 155.5.
- **Batch and scans:** batch +41% and scan +50% against fifo; NORMAL wait 37.38 vs 22.10 µs.
- **CPU and drops:** 7.99 cores; zero drops.

**Queries: p99 252.0 µs against sjf_nohint's 215.5.**
- **Where it shows:** query runqueue-wait p99 is 195.6 against 159.25 µs. The gap appears from 345k (201.5 vs 180.0).
- **Why:** under p8's too-late rule, a HIGH thread with under 9 µs of slack waits for any shorter thread. Queries count about 21 µs and become too late after about 70 µs of waiting. Multigets count at most 14 µs (the shared label). So a late query also waits for every queued 30 µs multiget, which otherwise ranks 80 µs or more behind it.
- **Why w8 didn't show it:** every shorter kind already ranked ahead of queries there, and query p99 was 225.0 under the champion against 225.5 under sjf_nohint.
- **Multigets gain the mirror image:** multiget p99 249.0 vs 301.5 µs and runqueue-wait p99 168.8 vs 227.1 µs.
- **Deadline-met is unchanged** (83.81 vs 83.60%), because only queries that are already lost wait.

**Does it threaten rule 3?** No. The limit is 1.25 × 252.0 = 315.0 µs. The real risk is to multigets. A policy that pushes them back behind late queries moves them toward sjf_nohint's 301.5 µs and 99.02%. The limits are 311.3 µs and 98.81%, so the margins would be only 3% and 0.2 points.

## 5. Anomalies

- **Clean runs:** 10 runs, one code sha (dbbe26c), no failed or saturated levels, adherence at least 99.78%. Kind and class rows agree within 2 req/s.
- **Prediction misses:**
  - champion get p99 95.0 (predicted 125–150);
  - champion get wait p99 40.9 (predicted 80–110);
  - prio 188.0 (predicted 170–180);
  - champion multiget deadline-met 99.81% (predicted 97–99.5).
- **Predictions that held:** fifo, sjf_nohint, put and sync wait as on w8 (82.0 and 82.05 µs), and get p99 of 14.0 µs at 100k under every policy.

## 6. Hypotheses for the policy agent

**Thresholds on w9:**
- get p99 at most 85.5 µs;
- deadline-met at least 96.02% (put), 82.81% (query), 98.81% (multiget);
- p99 at most 163.1 µs (put), 315.0 (query), 196.3 (sync), 311.3 (multiget), 407.5 (batch), 434.4 (scan);
- on w8, get p99 at most 91.3 µs.

1. **Learn one length per pair of run-time hint and coarse deadline.**
   - Evidence: only w9, among w1–w9, has one hint value with two deadlines (2 µs: 100 and 300 µs). So the change decides exactly as p8 does elsewhere. It needs 4 keys, within the 5 slots.
   - Expected effect: gets are learned at about 6 µs (turn +148) and multigets at about 34, capped to 14 (+412). That is w8's order.
   - Prediction: get wait p99 about 25 µs. At 290k it already matches w8 (5.7 vs 5.45), so the extra 30 µs runs add little. Get p99 is then about 80 µs (78–88): enough, but only just.
   - Use one split (for example, a deadline more than 200 µs after ready). The gap shrinks by however long a request waited before its thread existed.
   - Queries stay as now, since multigets still count 14 µs, less than 21.
2. **A cheaper variant: do not time HIGH threads whose deadline is more than 200 µs after they become ready.**
   - Gain: the same get gain, with no extra slot.
   - Risk: multigets then count about 6 µs, below the "1 µs" label's 13. Too-late puts and syncs would then also wait for 30 µs multigets. Watch put p99 (130.5 µs now, limit 163.1).
3. **Outside the policy region.**
   - Evidence: the part outside the runqueue is 42–54 µs under every policy (fifo 42.1, sjf_nohint 45.8, champion 54.1). Runs of 30 µs that cannot be passed are now about 20% of core time (3.0 of 14.9 µs per request), against about 11% on w8.
   - Needed hooks: preemption; processing packets while hinted threads wait; and a learning key the server sets per kind.

## 7. Lessons

workload: On w9, giving a 30 µs kind the gets' run-time hint but a 300 µs deadline raised the champion's get p99 only from 83.0 to 95.0 µs (predicted 125–150), because a kind that ranks last runs mostly from short queues, which the per-core timer skips, so a mixed label hurts most when its long members rank level with its short ones (w8's syncs and puts), not behind them.
policy: On w9 the champion's get runqueue-wait p99 rose from 25.4 to 40.9 µs while 54 µs of its 95.0 µs get p99 lies outside the runqueue, so learning lengths per run-time hint and coarse deadline can win back only about 15 µs, just enough for the 85.5 µs threshold, and too-late queries now wait for multigets counted at 14 µs (query p99 252.0 vs 215.5 under sjf_nohint, deadline-met unchanged).
