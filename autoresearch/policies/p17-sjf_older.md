# p17: sjf_older

- id: p17
- config: sjf_older
- generation: 16
- status: candidate
- builds_on: p16
- changed_from_previous: p16 plus: the shortest waiting HIGH thread may also pass the order's choice when it is only shorter, not a third as long, if it became ready before the chosen thread and the chosen thread has not run yet; p16's other guards still apply (due at least twice as late within p9's split, and the chosen thread keeps 40% of its relative deadline as slack). On w17 reads now pass the fanouts that arrived after them; on w1–w16 decisions are p16's.
- commit: 4f21993

## What it does
Like sjf_afford, each core runs helper threads first, then HIGH, NORMAL and LOW threads. It orders HIGH threads by deadline and length, and lets a much shorter request with a much looser deadline go ahead of the chosen one when that one can spare the time. sjf_older also lets a request that is only somewhat shorter go ahead, but only if it was already waiting when the chosen one arrived. Oldest-first would have run it first anyway. On w17 a document read no longer waits behind fan-out sub-requests that arrived after it while they still have 120 µs to spare; a sub-request with little slack left still runs first. On the earlier workloads a shorter, earlier request due twice as late does not occur, so nothing changes there.

## Why (hypothesis)
- **The bottleneck (gen 16 report §3):** 81.5% of the read p99 is runqueue wait (296.6 of 364.0 µs). The order gives a read its turn about 300 µs after a fanout's, so any fanout readied up to 300 µs after a read runs first. p16's pass needs a third of the length, and reads are only 2.5 times shorter. Read wait p99 follows that window: 146.2 under prio (window 0) against 296.6 under the champion.
- **The rule (report hypothesis 2, with hypothesis 1's test that the passer is shorter):** an earlier passer is a fixed amount of work, the reads queued when the fanout arrived, not a stream of later ones. p16's 120 µs reserve still applies. The new branch has no length ratio; it is stated in cost (shorter) and arrival order, under p16's slack guard.
- **Why not hypothesis 1 alone (any shorter passer):** in the model it cuts reads 65–70%, but fanout p99 rises 21–22% (limit 25%) and fanout wait p99 reaches 178–185 µs, at the report's 181 µs bound. The earlier-passer version gets about half the read gain for half the fanout cost.
- **Why the chosen thread must not have run yet:** a thread re-queued after a time slice gets a new ready time, so it looks younger than everything waiting and its deadline minus ready time understates its window (gen 10/11 lessons). Without this condition the model changed 0.1–0.2% of picks on w11–w15.
- **Offline check** (gen 15's model with the current region, lockstep against sjf_afford, calibrated so prio matches measured w17 within 1%): differing picks none on w1–w10, w12, w15, w16 (about 30M picks); w11 0.002–0.003%, w13 3 of 560k, w14 6 of 368k, all multigets while a core's unit was briefly 8 or more. w17 at 159k, 8 seeds: read p99 388 → 253 µs (−35%), fanout p99 +9%, deadline-met 99.92 → 99.89; heavier calibrations read −31% and −25%.

## Cost
- **Fanouts:** they wait for reads queued before them until they get within 120 µs plus a read's length of their deadline. Model at 159k: fanout p99 +9 to +11% (limit +25%), fanout wait p99 132 → 153–158 µs, deadline-met −0.03 to −0.08 points.
- **Reads that arrive after a fanout** still wait for it, so read p99 stays above prio's in the model (253 against 209).
- **Per-pick work:** at most two more comparisons after the scan. No extra clock read and no new state.

## Prediction (from the policy agent, against sjf_afford)

| Workload | Metric (headline load unless noted) | Expected vs sjf_afford |
|---|---|---|
| w17 (159k) | read p99 (score) | −25% to −35% (364.0 → about 235–275 µs; limit 327.6) |
| w17 | read runqueue-wait p99 | 296.6 → about 175–215 µs |
| w17 | fanout p99 | +8% to +12% (219.0 → about 235–245; limit 273.8) |
| w17 | fanout deadline-met | 0 to −0.15 points (limit 98.85) |
| w17 | health p99 | within noise (107.0; limit 133.8) |
| w16, w1–w15, w0 | every metric | unchanged within noise (p16's decisions) |

## Results
(filled after evaluation)
