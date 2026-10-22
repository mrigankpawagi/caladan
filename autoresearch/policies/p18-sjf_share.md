# p18: sjf_share

- id: p18
- config: sjf_share
- generation: 17
- status: candidate
- builds_on: p17
- changed_from_previous: p17 plus: when p17's shortest waiting HIGH thread does not pass, the oldest waiting HIGH thread (not overrun) may pass the order's choice if it became ready first and the chosen thread has not run yet, it is due at least twice as late within p9's split, it is at most half again as long, the chosen thread keeps 30% of its relative deadline as slack after it, and it has already used at least as large a share of its own deadline window as the chosen thread will have used after waiting for it; on w18 frontend reads pass fanouts that arrived after them, and on w1–w17 decisions are p17's (42 of 35M picks differ in the model)
- commit: (filled by orchestrator)

## What it does
Like sjf_older, each core runs helper threads first, then HIGH, NORMAL and LOW threads. It orders HIGH threads by deadline and length, and lets a shorter request go ahead of the chosen one when the chosen one can spare the time. sjf_share adds one case for two requests of about the same size. The request that has waited longest may go first if it arrived before the chosen one and has already used a larger share of its own time budget than the chosen one would after waiting for it. The chosen one must still keep 30% of its budget to spare. On w18 a frontend document fetch (800 µs budget) no longer waits behind every fan-out fetch (300 µs budget) that arrived after it while those still have time. On the earlier workloads such a pair either does not occur or p17's rule already handles it, so decisions do not change.

## Why (hypothesis)
- **The bottleneck (gen 17 report §3):** 82% of the read p99 is runqueue wait (482.4 of 589.0 µs). The order gives a read its turn 1168 µs after it is ready and a fanout its turn at 636 µs, so any fanout readied up to about 530 µs after a read runs first. p16's and p17's passes consider only the shortest waiting thread, which is a health check or a fanout, so no pass fires for reads. The champion equals fifo (589 vs 574.5).
- **The rule (report hypothesis 1):** a second candidate, the oldest waiting HIGH thread, under p17's arrival-order and not-yet-run conditions and p16's twice-as-late-within-the-split condition. The cost guard is that the passer is at most half again as long: a w18 read is 1.1 times a fanout; gets against leases on w13–w15 (3.5×) and queries against gets on w2 (8×) stay excluded.
- **The share condition (stated in deadlines and cost, not a ratio, per the gen 15 and gen 16 lessons):** the passer must already have used at least as large a share of its window as the chosen thread will have used after waiting for it. In the model, the plain oldest pass at p16's 40% reserve cut reads −15% but raised fanout p99 +33% (limit +25%). With the share condition, reads gain about three times as much per µs of fanout wait spent.
- **The reserve:** 30% of 300 µs is 90 µs, so a fanout can be passed only until it has waited about 122 µs, the champion's measured fanout queue-wait p99 (126.8).
- **Offline check** (gen 16 model with the current region and w18; it overstates measured read p99 by 10–11% for fifo, prio and the champion alike and matches fanout wait p99): lockstep against sjf_older, 42 of 35.0M picks differ over w1–w16 (none on w1–w10, w14, w15); on w17 57–106 of 1.3–1.5M, read p99 253 → 255. w18 at 76k: read p99 −12.5% and −11.6% under two overheads; −13.5% to −15% at 72k–74k.

## Cost
- **Fanouts on w18:** they wait for reads that came first until they have waited about 120 µs. Model: fanout p99 +15–16% (limit +25%), queue-wait p99 127 → 153–157, deadline-met −0.05 to −0.07 points.
- **Health checks on w18** gain (model 106 → 84 µs).
- **Per-pick work:** one comparison per HIGH thread to track the oldest; when p17's pass does not fire, a few comparisons and two divisions after the scan. No extra clock read and no new state.
- **Risk:** the margin on the score is thin (model −11.6% to −12.5% against a 10% threshold).

## Prediction (from the policy agent, against sjf_older)

| Workload | Metric (headline load unless noted) | Expected vs sjf_older |
|---|---|---|
| w18 (76k) | read p99 (score) | −10% to −15% (589.0 → about 500–530 µs; limit 530.1) |
| w18 | read runqueue-wait p99 | 482.4 → about 400–430 µs |
| w18 | fanout p99 | +12% to +18% (216.0 → about 240–255; limit 270.0) |
| w18 | fanout deadline-met | −0.03 to −0.10 points (limit 98.86) |
| w18 | health p99 | −10% to −25% (126.0; limit 157.5) |
| w17, w16, w1–w15, w0 | every metric | within noise (p17's decisions) |

## Results
(filled after evaluation)
