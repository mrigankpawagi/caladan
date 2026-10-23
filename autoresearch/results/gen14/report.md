# Generation 14: measurement report

## 1. Headline (w15, 73.75k, p99 in µs, median of 2 repeats)

| Policy | get (score) | vs fifo | bigget | put | query | sync | multiget | batch | scan | lease | Resp/s |
|---|---|---|---|---|---|---|---|---|---|---|---|
| fifo | 812.5 | 0% | 2498 | 953.5 | 890.0 | 1296 | 1270 | 892.5 | 910.5 | 789.0 | 73,226 |
| fifo ignore | 786.0 | −3% | 2362 | 936.5 | 869.0 | 1298 | 1294 | 862.0 | 862.0 | 792.0 | 73,318 |
| prio | 661.5 | −19% | 2500 | 783.5 | 734.0 | 1132 | 1164 | 1418 | 1556 | 659.5 | 73,110 |
| sjf_upper | 385.0 | −53% | 1418 | 445.0 | 1139 | 591.5 | 1084 | 1518 | 1578 | 129.5 | 73,220 |
| **sjf_ratio** | **341.0** | −58% | 1282 | 417.5 | 1144 | 546.0 | 1050 | 1508 | 1592 | 127.5 | 73,551 |

Compared with w14 at the same load per core, fifo (+1%) and prio (flat) did not move. The two length-ranking policies rose: sjf_ratio by 67% (204.5 to 341.0) and sjf_upper by 56%.

## 2. Is it real?

- The repeats agree: sjf_ratio 354/328, sjf_upper 392/378, fifo 775/850.
- sjf_ratio beats sjf_upper by 11.4%, above the 6% noise band, and the repeat ranges do not overlap.
- fifo with hints against fifo ignoring them (−3%) is noise.
- The +67% from w14 crosses sessions, but it is far above the ~6% drift between sessions. This session's probe gave 322 and 812.

## 3. Where the gets' time goes (sjf_ratio)

| | w14, 75k | w15, 73.75k |
|---|---|---|
| get p50 / p90 / p99 / p99.9 | 33.5 / 97.5 / 204.5 / 342.5 | 36.0 / 108.5 / 341.0 / 739.5 |
| get runqueue-wait p99 (share of p99) | 121.3 (59%) | 264.8 (78%) |
| p99 minus wait p99 | 83.2 | 76.2 |
| mean HIGH wait, depth | 45.67, 2.16 | 48.68, 2.19 |
| late at pick, steals, hinted overflow | 3.26%, 21.2%, 2 | 4.08%, 21.8%, 41 |
| time-slice yields per HIGH pick | 7.0% | 7.8% |

There are no inversions. The get p50 at 26k is 17.0 on both workloads.

- **Only the tail grew.** The p90 rose 11 µs; the p99 rose 136.5 and the p99.9 397. All of the p99 rise is runqueue wait (+143.5). The same rise appears at 66.5k (wait p99 41.2 to 180.9 µs) while the p90 rose 7 µs.
- **Mechanism 1 is supported: re-queued large lookups keep an early turn.**
  - Under sjf_ratio, a large lookup's median is only 55.5 µs above its light-load 825.0. Under fifo it is 200.5 above. So after each 100 µs slice it is picked again almost at once.
  - The gets' p99.9 (739.5) is about one large lookup's run.
  - Large lookups use about 1.3% of core time (92/s × ~0.83 ms over 6 cores; an estimate). 0.69% of gets now miss 400 µs, against 0.02% on w14.
- **Mechanism 2 is not visible: the lookup label growing past the puts' cap.** If puts and syncs now ran ahead of gets, their waits would fall. Instead their wait p99 rose 6.6% and 3.9% (276.7 to 295.0, 281.0 to 291.9), in line with the +6.6% mean HIGH wait. Counter request: each core's learned length per label, to settle this.

**Conclusion:** queueing, behind a large lookup that holds its core through its re-queues.

## 4. Costs and thresholds

Against fifo, sjf_ratio pays query +29%, batch +69% and scan +75%. Query and lease deadline-met rise (85.50 vs 81.05, 95.31 vs 65.69). Every policy used 5.99 cores.

| Rule (vs sjf_ratio) | Champion | Limit | Room |
|---|---|---|---|
| get p99 (90%) | 341.0 | ≤ 306.9 | must drop 34.1 (judge.py also accepts −10 µs, i.e. 331.0, but that is inside the repeat spread) |
| bigget / put / sync p99 | 1282 / 417.5 / 546.0 | 1602.5 / 521.9 / 682.5 | +320.5 / +104.4 / +136.5 |
| query / multiget p99 | 1144 / 1050 | 1430 / 1312.5 | +286 / +262.5 |
| batch / scan / lease p99 | 1508 / 1592 / 127.5 | 1885 / 1990 / 159.4 | +377 / +398 / +31.9 |
| deadline-met: query / lease / put / multiget | 85.50 / 95.31 / 98.88 / 99.66 | −1 point | 1.0 point each |

Earlier workloads cap w14 at 225.0 and w13 at 194.2. The tightest limit is the bigget rule. The workload agent's oracle, which demotes re-queued large lookups, cost them +70–80% in simulation, which would fail it.

## 5. Anomalies

- No level failed or saturated.
- class:high counts 60,234 requests against 60,231 for the HIGH kinds, so hints reached the scheduler.
- Yields rose 10% under sjf_ratio (14.0k to 15.4k per run) but only 5% under fifo.
- **Prediction misses:** sjf_ratio 341.0 against 270–330, and its wait p99 264.8 against 190–240; the runqueue share was 0.78 against 0.70–0.75.
- **Prediction hits:** fifo, sjf_upper, bigget, yields and the light-load numbers all fell inside their predicted ranges.

## 6. Probe: the other two proposals (sjf_ratio, one repeat)

- **w15a (48 connections, 4 cores, 48.75k):** get p99 170 against fifo's 727; wait p99 48.0 (28% of the tail). 50k failed the headline rule (fifo median 137 against a limit of 135).
- **w15c (lookup-heavy, 90% load, 104.5k):** get p99 147 against fifo's 548; wait p99 39.1 (27%).
- On both, about 120 µs of the tail is outside the runqueue, out of reach of the policy region.

## 7. Hypotheses

1. **Put a re-queued thread behind short waiting HIGH threads only.** Evidence: the bigget median is +55.5 µs, the get p99.9 is 739.5 and the p90 is flat. The workload notes say a ready time far past the thread's deadline start marks a re-queue. Budget: about 40 µs per re-queue (+320 µs over 7–8 slices), enough for queued gets and leases but not for queries.
2. **Stop learning from picks that end in a time-slice yield.** This is cheap insurance against mechanism 2, which is unconfirmed (puts did not gain).
3. **Outside the policy region:** stealing gets that are queued behind a long-running thread (steals 21.8%). The ~76 µs outside the runqueue is unchanged.

## 8. Lessons

workload: Adding 1% of lookups 100 times longer with the same hints left fifo and prio flat (get p99 812.5 vs 804, 661.5 vs 662) but added about 140 µs of runqueue wait to the gets' p99 under both length-ranking policies from 66.5k up, with the p90 up only 7–11 µs, so a rare hidden long request hurts only the policies that trust its label, and only in the tail.
policy: On w15 the large lookups hurt gets by holding their core through each re-queue (bigget median only 55.5 µs over its run, get p99.9 739.5 µs), not by inflating the lookup label (put and sync wait p99 rose 4–7% instead of falling), and bigget has only 320 µs (25%) of p99 room, so demote a re-queued lookup behind short waiting threads, not to the back of the queue.
