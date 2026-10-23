# Generation 15: measurement report

## 1. Headline (w16, 155k, p99 in µs, median of 2 repeats; the champion has 1)

| Policy | point (score) | vs fifo | fanout p99 / met % | health | export | rebuild | Resp/s |
|---|---|---|---|---|---|---|---|
| fifo | 649.0 | 0% | 683.0 / 86.14 | 636.0 | 686.0 | 682.5 | 154,135 |
| fifo ignore | 625.5 | −3.6% | 659.0 / 86.69 | 622.0 | 659.5 | 663.5 | 153,888 |
| **prio** | **305.0** | −53.0% | 340.5 / 98.27 | 302.5 | 1089 | 1465 | 153,582 |
| edf_high | 683.5 | +5.3% | 301.0 / 98.99 | 804.0 | 1082 | 1479 | 153,632 |
| sjf_guard | 520.5 | −19.8% | 321.0 / 98.64 | 636.5 | 1102 | 1468 | 153,583 |
| sjf_overrun (champion) | 483.0 | −25.6% | 298.0 / 99.07 | 606.0 | 1126 | 1517 | 153,347 |

This is the first workload since w4 that is not a key-value variant. Plain priority classes win on the score. Every policy that looks at deadlines meets more fanout deadlines.

## 2. Is it real?

- The noise band is 6%. Repeats agree within 4 µs (prio 307/303, sjf_guard 520/521, edf 684/683).
- The champion's second repeat was lost. Its probe run 9 minutes earlier gave 487 and 99.09%, so 483.0 holds.
- prio beats the champion by 36.9%, which is real. The champion beats sjf_guard by 7.2%, just outside the band.
- Fanout deadline-met repeats agree within 0.10 points. So the champion against edf_high (+0.08 points) is noise; against sjf_guard (+0.43) and prio (+0.80) the difference is real.
- fifo ignoring hints against fifo with hints (−3.6%) is noise.

## 3. Where the points' time goes

| At 155k | prio | champion | edf_high |
|---|---|---|---|
| How long after a point a fanout can still go first | 0 | 236 µs | 500 µs |
| point p50 / p90 / p99 / p99.9 | 35.0 / 140 / 305.0 / 462 | 37.0 / 276 / 483.0 / 558 | 36.5 / 274.5 / 683.5 / 868.5 |
| point queue-wait p99 (share of p99) | 255.8 (84%) | 426.7 (88%) | 628.2 (92%) |
| p99 minus wait p99 | 49.2 | 56.3 | 55.3 |
| fanout queue-wait p99 | 258.6 | 212.0 | 210.8 |

- **The policy's choice of order sets the points' wait.** The point p50 at 55k is 17.0 under every policy.
- **Why the champion waits 236 µs.** Its turn for a point is 800 + 8×8 = 864 µs after the point becomes ready. A fanout's turn is 300 + 8×41 = 628 µs. So any fanout readied up to 236 µs after a point runs first.
  - Rough count: 155k × 0.4 ÷ 6 cores is about 10 fanouts per ms per core. That is about 2.4 fanouts, roughly 100 µs of work, inside the window, and about twice that in a burst.
- **Why prio does best for points.** prio runs HIGH threads oldest first, so a point never waits for a younger fanout.
- **Points' own deadline never pushes them forward.** Points met 800 µs in at least 99.73% of cases under every policy (100.00% under prio and the champion).
- **The champion's edge over sjf_guard comes from its too-late rule.** A fanout with under 13 µs to spare waits for shorter threads. This shows in the fanout p99.9: 763 under the champion against 481 under sjf_guard.
- **Other counters under the champion:**
  - mean HIGH wait 36.83 µs (prio 25.99), queue depth 2.95, no inversions;
  - 17.3% of hinted threads stolen, 357 hinted and 433 total overflows;
  - 91 time-slice yields per run;
  - late at pick 0.23% of HIGH picks, which is about 0.40% of fanouts, against 0.93% of fanouts late at the client.

**Conclusion:** queueing behind younger fanouts that the policy deliberately puts first.

## 4. Costs and thresholds (new policy against the champion)

| Rule | Champion | Limit | Room |
|---|---|---|---|
| point p99 (90%) | 483.0 | ≤ 434.7 | must drop 48.3 (prio is at 305.0) |
| fanout / health p99 | 298.0 / 606.0 | 372.5 / 757.5 | +74.5 / +151.5 |
| export / rebuild p99 | 1126 / 1517 | 1407.5 / 1896.3 | +281.5 / +379.3 |
| fanout / health met | 99.07 / 100.00 | 98.07 / 99.00 | 1.0 point each; prio would leave only 0.20 on fanouts |

- Against fifo, the champion pays export +64% and rebuild +122%.
- Health checks wait last among HIGH threads: their turn is 1008 µs, so their p99 is 606.0 against prio's 302.5.
- Every policy used 5.98–5.99 cores.

## 5. Anomalies

- **The Mac slept during the champion's second repeat.** It started at 17:44:37 and failed after 1116 s with "server hp075 not responding". It left no rows and an empty raw folder.
- **No other run looks truncated or failed:**
  - all have 6 levels and took 55.5–56.2 s;
  - 0 drops, adherence 99.83–99.87%, and no failed or saturated level;
  - every raw file ends with `CLIENT_EXIT=0`;
  - the two runs after the wake (fifo ignore) match fifo with hints within noise.
- The adherence warning appears at every level. calibration.json says that is normal.
- **Hints reached the scheduler.** Kinds match classes: class high 107,177 against 107,176 for the three HIGH kinds; normal and low equal export and rebuild exactly.

## 6. The other two proposals (probe, champion, one repeat)

- **w16a, large values over 48 connections (73.75k):** get p99 237 against fifo's 738. Wait p99 160.9, 68% of the tail.
- **w16b, large values at 90% load (81k):** get p99 228 against fifo's 623. Wait p99 157.5, 69% of the tail.
- w16c (now w16) had 88% of its tail in the queue (429.3 of 487), the most room for a scheduling policy.

## 7. Hypotheses

1. **Let a short HIGH thread pass a longer one that can afford the wait.**
   - Idea: if the chosen thread is at least 3 times longer and would keep enough slack after one short request, run the short one first.
   - Evidence: point wait p99 tracks the window (0, 236, 500 µs gives 255.8, 426.7, 628.2). A point costs a fanout only about 8 µs; a fanout costs a point about 41.
   - Risk: if the core's time unit is above 1, p14's 3× ratio rule would stop urgent fanouts (about 5 times a point's length) from being rescued past points.
   - Counter request: each core's unit and learned length per label.
2. **Cap the relative deadline used for ordering at about 400 µs, keeping real deadlines for the rescue and too-late rules.**
   - Point turn 464 against fanout 628, so a fanout goes first only after waiting 164 µs. Its wait p99 is 212.
   - This should land between prio and the champion. Check w11–w15, where multigets are due in 1200 µs.
3. **Outside the policy region.** 49–58 µs of point p99 is outside the queue under every policy. Preempting a running 41 µs thread, or stealing with hints in view (17.3% are stolen), is needed below that.

## 8. Lessons

workload: On w16, where the longer HIGH kind has the tighter deadline, plain priority classes gave the best score (point p99 305.0 against the champion's 483.0) while every deadline-aware policy met more fanout deadlines (98.99–99.07% against 98.27%), so a conflict between deadlines and lengths separates policies by how far they let the tight-deadline kind jump ahead.
policy: Point queue-wait p99 on w16 follows how long after a point a fanout may still run first (0, 236 and 500 µs give 255.8, 426.7 and 628.2 µs under prio, the champion and edf_high), and a point costs a fanout only about 8 µs, so let short HIGH threads pass a longer one that keeps enough slack while guarding the fanouts' 1.0 point of deadline-met room.
