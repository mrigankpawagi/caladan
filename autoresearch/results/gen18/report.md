# Generation 18: measurement report

## 1. Headline (w19, 76k, p99 in µs, median of 2 repeats)

| Policy | point p99 (score) | vs fifo | mid p99 / met % | fanout p99 / met % | health | export | rebuild | Resp/s |
|---|---|---|---|---|---|---|---|---|
| fifo | 551.5 | 0% | 559.5 / 97.21 | 549.5 / 90.72 | 510.0 | 555.5 | 559.0 | 74,202 |
| fifo ignore | 544.0 | −1.4% | 535.0 / 97.69 | 534.0 / 91.50 | 494.5 | 538.5 | 532.5 | 74,256 |
| prio | **340.0** | −38.3% | 336.5 / 99.85 | 333.0 / 98.35 | 287.0 | 1048 | 1366 | 74,830 |
| sjf_older | 562.0 | +1.9% | 269.5 / 99.96 | 171.0 / 99.94 | 128.0 | 1047 | 1372 | 74,647 |
| sjf_share (champion) | 483.0 | −12.4% | 300.5 / 99.96 | 208.5 / 99.91 | 108.5 | 1021 | 1370 | 74,182 |

On w19, half of w18's fanouts are replaced by mid-tier fetches. Points cannot pass these. The champion still beats fifo by 12%, and prio is 30% below the champion.

## 2. Is it real?
- The noise band is 6%. Score repeats: champion 480/486, sjf_older 554/570, prio 333/347, fifo 546/557.
- Real: the champion against sjf_older (−14.1%) and against fifo (−12.4%).
- Noise: sjf_older against fifo (+1.9%), fifo ignore against fifo (−1.4%), and the champion against its w18 score from another session (−2.5%).
- The champion's fanout queue-wait p99 repeats disagree (124.4 vs 93.6), but its fanout p99 repeats agree (211 vs 206).

## 3. Where the points' time goes (champion, 76k)
- Point p50 is 69 (54 at 28k). Point p99 is 483 (77 at 28k).
- Queue wait p99 is 388.6, 80% of the p99. The other 94.4 µs is spent outside the queue (fifo 89.7, prio 85.6): waiting behind a running 41 µs export or rebuild, the fetch itself, and the network.
- Queue-wait p99 by kind: mid 211.9, fanout 109.0, health 45.7.
- **Turn times.** The order gives a point its turn 1168 µs after it is ready, a mid 786 µs, a fanout 636 µs. So mids readied up to 382 µs after a point run first, and fanouts up to 532 µs after.
- **What p18's pass allows.** A point can pass a fresh fanout only once it has waited 800/300 × 46 = 123 µs. It never passes a mid, because 800/450 = 1.78 is below the required 2.
- **Splitting the wait** (an estimate, assuming mids and fanouts arrive at equal rates with equal lengths):
  - Oldest-first (prio) gives points 254.5 µs of queue-wait p99. This is the backlog already ahead of a point when it arrives.
  - sjf_older adds 214.5 µs from younger threads run first. Split by turn window, that is about 90 µs behind mids (382/914) and 125 µs behind fanouts.
  - The champion's 80.3 µs cut (468.9 → 388.6) can only have come from fanouts.
  - So the 388.6 µs is about 254 of backlog, 90 behind younger mids and 45 behind younger fanouts.
- Other counters: mean depth 2.07, no inversions. HIGH threads late at pick: 0.02–0.03%, against 0.06% of points missed at the client. Steals: 14.3% of hinted picks. Hinted overflow: 152 and 69 threads, at most 0.1% of HIGH picks.

**Conclusion:** points queue behind younger mids that no pass reaches, and behind younger fanouts during a point's first 123 µs of waiting.

## 4. What 128 connections changed (vs w18, champion at 76k)
- Steals 14.2/14.4% vs 14.5/14.6%. The workload predicted 8–12%.
- Softirqs stolen 66,070 vs 66,024. Mean depth 2.07/2.06 vs 2.05/2.08. HIGH mean wait 22.3 vs 22.9 µs.
- Overflow is the only change: 69–152 hinted threads beyond the 32-slot queue, against 0–1 on w18. Across all policies it is 61–295.
- fifo point p99 is 551.5 vs 574.5 on w18, within noise.

## 5. Costs and thresholds
- Against sjf_older, the champion costs mids +11.5% p99 and fanouts +21.9% p99 (−0.03 points of deadline-met). Health improves by 15.2%.
- Against fifo: exports +84%, rebuilds +145%. Every request is answered, and every policy uses 3.99 cores.

| Rule | Champion | Limit |
|---|---|---|
| w19 point p99 | 483.0 | ≤ 434.7 (needs −48.3; the 10 µs rule's 473.0 is within noise) |
| mid / fanout / health p99 | 300.5 / 208.5 / 108.5 | ≤ 375.6 / 260.6 / 135.6 |
| export / rebuild p99 | 1021 / 1370 | ≤ 1276 / 1712 |
| point / mid / fanout met | 99.94 / 99.955 / 99.905 | ≥ 98.94 / 98.955 / 98.905 |
| w18 / w17 / w16 point p99 | 495.5 / 222.5 / 241.0 | ≤ 545.1 / 244.8 / 265.1 |
| w18 / w17 / w16 fanout met | 99.83 / 99.86 / 98.565 | ≥ 98.83 / 98.86 / 97.565 |

- **Why oldest-first is out.** prio misses fanout deadline-met by 0.56 points (98.35 against 98.905) and fanout p99 by 72.4 µs.
- **Margins on a straight line from the champion to prio** (each µs of point p99 costs fanouts 0.87 µs of p99 and 0.011 points of deadline-met): reaching 434.7 would leave fanout p99 at about 250.6 (10 µs of margin) and fanout deadline-met at about 99.38 (0.47 points). Fanouts are where the policy has no room.

## 6. Anomalies
- None in the runs: 10 runs of 57.7–60.1 s, 0 drops, adherence 99.83–99.89%, kind and class counts match within 2.
- Predictions that missed: mid p99 300.5 (predicted 180–260), champion 483 (predicted 500–600), and the steal and overflow predictions in §4.

## 7. The other proposals (probe, champion vs fifo, 1 repeat)
- **w19a** (2 guaranteed + 2 burstable cores next to a cache antagonist):
  - At 70k, point p99 is 432 vs 471 (−8%). 316.3 µs of it is runqueue wait (73%), against w18a's 49% on 6 cores.
  - The server used 2.09 cores at 28k and 3.05 at 70k.
  - At 28k, point p99 is already 114, with a 41 µs wait p99 (w18 at 28k: 79 and 0.7). With the burstable cores parked, requests queue even at light load.
  - Fanout deadline-met: 94.30 under fifo, 99.88 under the champion.
- **w19b** (replicated storage node):
  - At 98k, read p99 is 241 vs 540 (−55%). 152.7 µs of it is runqueue wait (63%).
  - Compaction p99 is 1240 vs fifo's 609. Append deadline-met rises from 92.92 to 99.98.

## 8. Hypotheses
1. **Let points pass mids, but not mids pass fanouts.**
   - Change the share pass's "due twice as late" cut to: due later by more than the chosen thread's 30% reserve plus both lengths.
   - Point over mid: 350 ≥ 135+88, passes. Point over fanout: 500 ≥ 90+88, passes. Mid over fanout: 150 < 174, does not pass. Threads with the same deadline never pass, so w1–w15 should keep their decisions; check offline.
   - A point would pass a fresh mid after waiting 82 µs. A mid can be passed until it has waited 227 µs (its wait p99 is now 211.9).
   - Target: the roughly 90 µs points spend behind mids. Fanouts pay what they pay under p18.
2. **Consider the thread that has used the largest share of its own deadline window as the pass candidate, not the oldest one.**
   - Mid wait p99 (211.9) is above 123 µs. So an older mid is often the oldest waiting thread when a point becomes eligible to pass, and it hides the point.
   - **Counter requests:** passes per pair of kinds, and rejected candidates by kind.
3. **Outside the policy region.** 94.4 µs of point p99 is spent outside the queue (85.6 even under prio), and 0.1% of HIGH threads overflow the queue. Fixing these needs preemption of running exports and rebuilds, or a larger queue that sees hints.

## 9. Lessons
workload: Moving w18's load from 48 to 128 connections left steals (14.3% vs 14.6%) and depth (2.07) unchanged and only pushed about 0.1% of HIGH threads past the 32-slot queue, so propose more connections to test overflow, not to even out cores.
policy: On w19 a point's 389 µs tail wait is about 254 µs of backlog that oldest-first also has, 90 behind younger mids and 45 behind younger fanouts, so the next pass must reach mids under a cut stated in deadlines and cost (due later by more than the chosen thread's reserve plus both lengths) that keeps mids from passing fanouts, the kind with only 10 µs of p99 margin.
measurement: Without a per-pair pass counter, splitting a kind's queue wait among the kinds that run ahead of it worked from three measured policies (oldest-first as the backlog floor, the order without passes, and the champion) together with the order's turn windows.
