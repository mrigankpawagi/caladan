# Generation 17: measurement report

## 1. Headline (w18, 76k, p99 in µs, median of 2 repeats)

| Policy | read p99 (score) | vs fifo | fanout p99 / met % | health | export | rebuild | Resp/s |
|---|---|---|---|---|---|---|---|
| fifo | 574.5 | 0% | 571.0 / 90.09 | 527.5 | 570.0 | 573.0 | 74,933 |
| fifo ignore | 567.5 | −1.2% | 564.5 / 89.78 | 519.5 | 561.5 | 566.0 | 74,998 |
| **prio** | **346.5** | −39.7% | 344.5 / 98.15 | 297.5 | 1044 | 1395 | 75,077 |
| sjf_afford | 601.0 | +4.6% | 213.5 / 99.86 | 131.5 | 1113 | 1446 | 75,260 |
| sjf_older (champion) | 589.0 | +2.5% | 216.0 / 99.85 | 126.0 | 1088 | 1427 | 75,056 |

A read now costs 1.1 times a fanout, so no pass fires for reads, and the champion does no better than fifo.

## 2. Is it real?
- The noise band is 6%. Read p99 repeats: champion 583/595, sjf_afford 597/605, prio 345/348, fifo 565/584.
- Champion vs sjf_afford (−2.0%) and vs fifo (+2.5%) are noise. prio vs champion (−41%) is real.
- Fanout deadline-met repeats agree within 0.05 points (champion 99.88/99.83, prio 98.15/98.14).

## 3. Where the reads' time goes (champion, 76k)
- Read p50 is 71.0 (54.0 at 28k). Read p99 is 589.0 (77.0 at 28k).
- Queue-wait p99 is 482.4, 82% of p99. 106.6 µs is spent outside the queue (prio 88.6, fifo 93.6).
- Reads wait as long as under fifo (480.9). Fanouts wait 126.8 instead of 476.6. Under prio both wait about 258.
- Mean HIGH wait 23.3 µs, depth 2.12, no inversions, 14.3% stolen, no overflow. HIGH threads late at pick: 0.04%, against 0.12% missed at the client.
- **Why neither pass fires.** A read's turn comes 800 + 8×46 = 1168 µs after it is ready, a fanout's 636 µs, so fanouts readied up to 532 µs later go first. p16's pass needs a passer a third as long, and p17's needs a shorter one. Both also look only at the shortest waiting HIGH thread, which here is a health check or a fanout, never a read. Health checks do pass (126.0 vs prio's 297.5). sjf_afford and the champion differ by at most 4% on every HIGH kind, so their decisions match.

**Conclusion:** reads queue behind younger fanouts that the order runs first.

## 4. Costs and thresholds
- Against fifo, the champion costs exports +91% and rebuilds +149%. Every request is answered, and every policy uses 3.99 cores.
- **Fanout slack** (time to spare before the deadline). Fanout p99 sits 86–89 µs above its queue-wait p99. The +25% cap (270.0) lets fanout wait p99 rise only from 126.8 to about 181 µs: 54 µs, about one read (46 µs) per tail fanout. The deadline alone would allow about 211.
- From the champion to prio, read p99 fell 242.5 µs, fanout p99 rose 128.5 µs, and fanouts lost 1.7 points of deadline-met: about 1.9 µs per µs. On a straight line, the −59 µs target costs about 31 µs of fanout p99 (to about 247) and 0.4 points (to about 99.45).

| Rule (vs champion) | Champion | Limit |
|---|---|---|
| w18 read p99 | 589.0 | ≤ 530.1 (10 µs rule: 579.0, within noise) |
| fanout / health p99 | 216.0 / 126.0 | 270.0 / 157.5 |
| export / rebuild p99 | 1088 / 1427 | 1360 / 1784 |
| fanout met | 99.85 | ≥ 98.86 |
| w17 / w16 read p99 | 234.0 / 261.0 | ≤ 257.4 / 287.1 |

prio fails on fanout p99 (by 74.5), health (by 140) and fanout deadline-met (by 0.71 points).

## 5. Anomalies
None:
- 10 runs, 57–62 s each; 0 drops; adherence 99.84–99.88%; no failed levels.
- Kinds match classes within 1 request.
- The workload's predictions held, except prio's fanout deadline-met (98.15 against 98.3–98.9) and the reads' runqueue share (0.82 against 0.85–0.9).

## 6. The other proposals (probe, champion vs fifo)
- **w18a, cache antagonist:**
  - This is the first antagonist that took cores from the server: it used 2.34 of 6 at 55k and 4.2–4.8 at busy levels.
  - Champion read p99 is 144 vs fifo's 444 at 136k (−68%), and 252 vs 606 at 150k.
  - Only 49% of it is runqueue wait at 136k (70.6 µs), and 75% at 150k.
  - At 55k, read p99 is 65–77 against 27–28 on w16, with queue wait p99 16.9: the tail comes from slower or parked cores.
  - First real overflow: 39–64 hinted overflows at 143–150k.
- **w18b, search shard:** hit p99 237 vs fifo's 411 at 136k (−42%), 69% runqueue wait. fifo's median is 72 against a limit of 73.5.

## 7. Hypotheses
1. **An older pass at equal cost.**
   - Keep the shortest-thread candidate so health checks still pass. Add the oldest waiting HIGH thread as a second candidate.
   - It passes if it became ready first, the chosen thread has not run, it is due at least twice as late within the split, it is at most about 1.25 times as long, and the chosen thread keeps p16's 120 µs reserve afterwards.
   - A fanout can then be passed until it has waited 300 − 42 − 46 − 120 = 92 µs.
   - Prediction: read p99 −10% to −17%, with fanout p99 nearing the 270 cap.
   - w16 and w17 should not change, because reads there are already shorter. Check w1–w15 offline.
2. **The same rule with a 150 µs reserve (a 62 µs window), if the model puts fanout wait p99 above about 170.** The workload's own model gave fanouts a 118 µs window (run first at 140 µs slack) and cost fanout p99 +39%. Keep the window at 92 µs or less.
3. **Outside the policy region.** 106.6 µs of read p99 is spent outside the queue (89 even under prio). A read waits for a running 41 µs export or rebuild, and those are 30% of requests. Fixing that needs preemption or work stealing that sees hints. **Counter requests:** passes per pair of kinds.

## 8. Lessons
workload: The cache-antagonist probe w18a was the first to take server cores (2.3 of 6 at light load, about 4.6 when busy), yet the champion left only 49% of its read p99 in the runqueue and already beat fifo by 68%, so propose antagonist workloads as targets for hooks outside the policy region, not for a new policy.
policy: When two HIGH kinds cost the same, p16's and p17's passes never fire because they consider only the shortest waiting thread and require it to be shorter, so a pass at equal cost must consider the oldest waiting thread and spend only the tight kind's measured headroom (on w18, fanout queue-wait p99 from 126.8 to about 181 µs, roughly one 46 µs read per fanout).
