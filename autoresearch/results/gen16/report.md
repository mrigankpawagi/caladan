# Generation 16: measurement report

## 1. Headline (w17, 159k, p99 in µs, median of 2 repeats)

| Policy | read p99 (score) | vs fifo | fanout p99 / met % | health | export | rebuild | Resp/s |
|---|---|---|---|---|---|---|---|
| fifo | 310.5 | 0% | 336.0 / 98.27 | 294.0 | 337.5 | 333.0 | 157,598 |
| fifo ignore | 307.5 | −1.0% | 330.5 / 98.38 | 289.5 | 330.5 | 332.5 | 157,700 |
| **prio** | **209.5** | −32.5% | 235.0 / 99.76 | 196.5 | 488.5 | 620.5 | 157,693 |
| sjf_overrun | 375.5 | +20.9% | 219.0 / 99.84 | 375.5 | 521.0 | 664.0 | 157,601 |
| sjf_afford (champion) | 364.0 | +17.2% | 219.0 / 99.85 | 107.0 | 502.0 | 651.0 | 157,445 |

Reads now cost 16 µs instead of 8. The champion lets a request pass only if it is at most a third as long as the chosen one, so reads no longer pass, and the champion falls behind both fifo and prio.

## 2. Is it real?

- The noise band is 6%. Read p99 repeats agree within 6 µs (champion 361/367, prio 209/210).
- prio beats the champion by 42.4%, which is real. Champion against sjf_overrun is −3.1%, which is noise: the pass rule never fires for reads.
- Health checks still pass: 107.0 against 375.5 under sjf_overrun. They are due in 1000 µs, so due times that late are allowed through. For reads, only the length ratio blocks.
- Fanout deadline-met repeats differ by 0.06–0.09 points. prio's −0.085 points against the champion is noise.

## 3. Where the reads' time goes (champion, 159k)

- Reads' p50 goes from 25.0 at 53k to 46.0; p99 from 36.0 to 364.0.
- Queue-wait p99 is 296.6, which is 81.5% of p99. Only 67.4 µs is spent outside the queue (prio 63.3, fifo 61.9).
- Other counters:
  - mean HIGH wait 17.98 µs, queue depth 1.70, no inversions;
  - 17.2–17.5% of hinted threads stolen, 0–16 overflows per run;
  - 122–125 time-slice yields per run.
- **The order puts younger fanouts first.** A read's turn comes 800 + 8×16 = 928 µs after it becomes ready, a fanout's 300 + 8×41 = 628 µs. So any fanout readied up to about 300 µs after a read runs first (on w16 this window was 236 µs).
  - Read wait p99 follows that window: 146.2 under prio (window 0), 296.6 under the champion, 306.2 under sjf_overrun.

**Why prio now costs fanouts only about 0.1 point**

- Under prio, all three HIGH kinds wait alike (wait p99 146.2–147.8). Fanout p99 is 235.0, 65 µs inside the 300 µs deadline.
- On w16, prio's fanout wait p99 was 258.6 and p99 340.5, past the deadline, which cost 0.8 points.
- On w17, bursts come every 1000 µs instead of 4000, and each builds a quarter of w16's backlog. So oldest-first already gets fanouts in on time.
- The deadline order buys fanouts only 20.5 µs of wait p99 (146.7 → 126.2) and 16 µs of p99. It costs reads 150.4 µs of wait p99.
- About 45% of fanout misses were already late when picked: 97–162 per run were late at pick, against about 210–380 client misses.

**Conclusion:** the reads wait in the queue behind younger fanouts that the policy deliberately runs first.

## 4. Costs and thresholds

Against fifo, the champion pays export +49% and rebuild +95%; every rebuild request is still answered. Every policy uses 5.99 cores.

| Rule (new policy vs champion) | Champion | Limit | prio |
|---|---|---|---|
| w17 read p99 | 364.0 | ≤ 327.6 | 209.5 |
| fanout / health p99 | 219.0 / 107.0 | 273.8 / 133.8 | 235.0 / 196.5 (fails) |
| export / rebuild p99 | 502.0 / 651.0 | 627.5 / 813.8 | 488.5 / 620.5 |
| fanout met | 99.85 | ≥ 98.85 | 99.76 |
| w16 point p99 | 255.0 | ≤ 280.5 | 305.0 (fails) |
| w16 fanout p99 / met | 321.5 / 98.53 | 401.9 / 97.53 | – |
| w15 get / bigget p99 | 262.5 / 1468 | 288.8 / 1835 | – |

- judge.py also accepts a gain of 10 µs (≤ 354.0), but that is within noise; aim at 327.6.
- Fanout p99 sits about 93 µs above its queue-wait p99 under both the champion and prio. To stay within +25%, fanout queue-wait p99 must stay below about 181 µs.
- Plain prio fails on health checks, so health checks must keep passing under any new rule.

## 5. Anomalies

None found:
- 10 runs, each with 6 levels, taking 57–63 s;
- 0 drops, adherence 99.78–99.89%, CLIENT_EXIT=0 everywhere;
- kinds match classes (HIGH 110,286 against 110,285).

The workload's predictions held. The exception is fifo's read p99, 310.5 against a predicted 330–440.

## 6. The other proposals (probe, champion, 1 repeat)

- **w17a, w16 at 90% peak load (170k):** champion read p99 301 against fifo's 323 (−7%). 83% of the tail is runqueue wait (248.4). The pass rule fires, but its 100 µs reserve binds in every burst.
- **w17b, search shard (136k):** the 140k level fails the median rule (78 against 49). Hit p99 251 against fifo's 405; 72% of the tail is runqueue wait (180.2).
- **w17c, now w17:** 83% of its tail was runqueue wait (309.4 of 373), a near tie with w17a.

## 7. Hypotheses

1. **A pass guarded by cost and slack, with no ratio.** The shortest waiting HIGH thread passes if it is shorter than the chosen thread, due at least twice as late, and within the deadline split. The chosen thread must keep 40% of its deadline as slack (time to spare) after the passer runs.
   - **w17:** a fanout can be passed until it has waited about 123 µs (300 − 41 − 16 − 120). Its wait p99 is 126.2, so reads would pass nearly every fanout.
   - **Prediction:** read p99 100–210, fanout deadline-met −0.2 to −0.8 points.
   - **Risk:** fanout p99, limit 273.8.
   - **w16:** decisions unchanged. Reads (8 µs) and health checks already pass, and a fanout is never the shortest.
   - **w9–w15:** the "twice as late, within the split" condition already excludes nearly every pair. Leases are shorter but due sooner, queries against gets differ by only 1.33×, and multigets are longer. p16's offline check found no differing picks on w1–w13 and 0.01–0.04% on w14–w15; verify again offline.
2. **The same rule, but only for a passer that became ready before the chosen thread.** This is prio's read-against-fanout order.
   - **Prediction:** read p99 about 210, fanout p99 about 235, deadline-met about 99.76, health about 107.
   - This leaves room under every rule.
3. **Outside the policy region.** 62–67 µs of read p99 is outside the queue under every policy. Getting below that needs preemption of a running fanout or stealing that sees hints.
   - **Counter requests:** passes per pair of request kinds, and each core's learned lengths.

## 8. Lessons

workload: On w17 the 1000 µs bursts left so little HIGH backlog that oldest-first met 99.76% of fanout deadlines (prio fanout p99 235.0 of 300 µs, against 340.5 with w16's 4000 µs bursts), so a workload built on a conflict between deadlines and lengths should first check prio's p99 for the tight-deadline kind to confirm that ignoring deadlines actually costs that kind.
policy: On w17 the deadline order bought fanouts only 20.5 µs of queue-wait p99 and 0.085 points of deadline-met over prio while costing reads 150 µs, and only the fixed one-third ratio kept 16 µs reads from passing, so state the pass as the chosen thread keeping its slack after the passer (safest when the passer became ready first) and keep fanout queue-wait p99 under about 181 µs.
