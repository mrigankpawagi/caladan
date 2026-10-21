# Generation 13: measurement report

## 1. Headline (w14, 75k, p99 in µs, median of 2 repeats)

| Policy | get (score) | vs fifo | put | query | sync | multiget | batch | scan | lease | Resp/s |
|---|---|---|---|---|---|---|---|---|---|---|
| fifo | 804.0 | 0% | 919.0 | 871.5 | 1273 | 1288 | 868.5 | 856.5 | 785.5 | 74,726 |
| fifo ignore | 799.0 | −1% | 922.5 | 877.5 | 1287 | 1301 | 868.0 | 884.0 | 785.0 | 74,704 |
| prio | 662.0 | −18% | 793.0 | 727.5 | 1118 | 1110 | 1366 | 1494 | 651.5 | 74,319 |
| sjf_scale | 357.5 | −56% | 377.0 | 1062 | 482.5 | 1002 | 1419 | 1537 | 132.0 | 74,356 |
| **sjf_upper** | **247.5** | −69% | 408.0 | 1074 | 560.5 | 1050 | 1431 | 1548 | 132.0 | 74,445 |

w14 is w13 on 6 cores instead of 8, with the same load per core. Against w13 at 100k, the champion went from 208.5 to 247.5 µs (+18.7%) and fifo from 657 to 804 µs (+22.4%).

## 2. Is it real?

- The repeats agree: sjf_upper 247/248, sjf_scale 348/367, fifo 797/811.
- The champion beats sjf_scale by 30.8% (19.5% on w13), so that gap is real. fifo with hints against fifo ignoring them (−0.6%) is noise.
- w13 and w14 were measured in different sessions. A gap of 19–22% is far above the roughly 6% drift seen between sessions. The probe's w14b run in this session gave 239 and 774, within 4% of the main runs.

## 3. Where the gets' time goes (sjf_upper)

| | w13, 100k | w14, 75k |
|---|---|---|
| get p50 / p90 / p99 | 31.5 / 99.0 / 208.5 | 34.0 / 100.0 / 247.5 |
| get runqueue-wait p99 | 125.4 | 166.3 |
| p99 minus wait p99 | 83.1 | 81.2 |
| mean HIGH wait, depth | 45.20, 2.12 | 45.74, 2.15 |
| late at pick, steals | 3.32%, 26.2% | 3.16%, 21.0% |
| time-slice yields per HIGH pick | 6.6% | 7.1% |

There are no inversions, the gets' deadline-met is 99.91%, and hinted overflow is 2. The get p50 at the lightest load is 17.0 on both workloads.

**What changed.** The averages did not move; only the tail of waiting grew.
- All of the +39 µs in get p99 is runqueue wait (+40.9 µs, +33%). The part outside the runqueue is flat.
- Steals fell, since there are fewer neighbouring cores to take a queued request.
- The puts' and syncs' wait p99 stayed flat (288.9 against 284.6; 284.0 against 294.6). Queries rose 27% and multigets 23%.
- So gets lost part of their lead over puts: their ratio of wait p99 went from 0.44 to 0.58.

**What a policy could still remove.**
- Leases, which the champion runs first, wait 5.5 µs at p99. So up to about 160 µs of the gets' 166.3 µs is a matter of order.
- The roughly 81 µs outside the runqueue is out of reach of the policy region.
- To pass, a policy must cut the get wait p99 by about 25 µs, to about 141.

**Conclusion:** queueing, about two thirds of the tail.

## 4. Costs and thresholds

- **Against fifo:** put −56%, sync −56%, multiget −18%, lease −83%; query +23%, batch +65%, scan +81%. Deadline-met: queries 85.72% against 80.84%, leases 95.09% against 65.28%. NORMAL wait 153.78 against 86.71 µs. Every policy used 5.99 cores.
- **Against sjf_scale:** put +8.2%, sync +16.2%, put deadline-met −0.33 points.

| Rule (vs sjf_upper) | Champion | Limit | Room |
|---|---|---|---|
| get p99 (90%) | 247.5 | ≤ 222.8 | must drop 24.8 µs |
| sync / put p99 | 560.5 / 408.0 | 700.6 / 510.0 | +140 / +102 µs |
| query / multiget p99 | 1074 / 1050 | 1342.5 / 1312.5 | +268 / +262 |
| batch / scan / lease p99 | 1431 / 1548 / 132.0 | 1788.8 / 1935.0 / 165.0 | +358 / +387 / +33 |
| deadline-met: query / lease / put / multiget | 85.72 / 95.09 / 98.92 / 99.67 | −1 point each | 1.0 point |

- The 10 µs rule would allow 237.5 µs instead. On w13 the score must stay at or below 229.4.
- The limits reset against sjf_upper, but syncs have already paid +16.2% (w14) and +20.9% (w13) over sjf_scale.
- The tightest rooms are the one point of query and lease deadline-met, and the leases' 33 µs.

## 5. Anomalies

- No level failed or saturated. class:high counts 61,080 requests against 61,078 for the HIGH kinds, so hints reached the scheduler.
- At the lightest load the get p99 is 37.5 µs, against 26.5 on w13. fifo shows the same (40.5 against 25.0), and leases too (30–33 against 18–20). Runqueue wait p99 is 0.7 there, so the extra 11–15 µs is outside the runqueue and hits every policy. The workload agent predicted about 25.
- **Prediction misses:** steals fell instead of rising; put and sync p99 were flat (−0.7% / −1.1%) instead of +5–15%; fifo came in at 804, above 680–760.
- **Prediction hits:** get p99, wait p99 and runqueue share (0.67) all fell inside their predicted ranges.
- fifo pushes 151 threads past the 32-slot queue, against 2–5 on w13.

## 6. Probe: the other two proposals

- **w14a (exponential service, honest hints), at 90k:**
  - get p99 is 269 (fifo) against 127 (sjf_upper). The champion's get wait p99 is 18.2, so only 14% of its tail is in the runqueue.
  - Puts (118 / 7.9) and leases (114 / 3.3) look the same.
  - The tail is service time and time before the handler thread exists, so ordering has little left to remove.
  - 95k and 100k failed the headline rule.
- **w14c (memory-bandwidth antagonist):**
  - At 35k the get p99 is 26 for both policies, as on w13.
  - At 100k, fifo gives 680 and sjf_upper 217 (wait 130.4), within 4% of w13. There is no measurable effect.
  - 110k and 115k were overloaded (fifo overall median 190 and 261 µs).
  - No counter confirms the antagonist's bandwidth.

## 7. Hypotheses

1. **Stop urgent queries from passing waiting gets.** A HIGH thread is "urgent" when it has under 20 µs to spare. Queries reach that after about 197 µs of waiting. Their wait p99 is 939 and 14.3% of them miss, so many cross that window, and each one that jumps ahead costs a waiting get 68 µs. The gen 12 estimate of this cost was about 24 µs. Idea: an urgent query first lets one get (7–12 µs) run if the get fits inside its slack. This resembles p4's rescue check (rejected in gen 3). It would spend query deadline-met (1 point of room).
2. **Move gets closer to the leases' rank.** A first-ranked kind waits 5.5 µs at p99, and gets are only about 1.7% of core time. This spends lease deadline-met (1 point of room) and some sync p99.
3. **Outside the policy region:** packet processing while hinted threads wait, hint-aware stealing, and marking time-slice remnants (14.1k yields per run). Even leases spend 126 of their 132 µs outside the runqueue. Counter request for the owner: the label of each pick made while a get waits, to split the 166 µs among urgent queries, time-slice remnants and leases.

## 8. Lessons

workload: Moving to fewer cores at the same load per core left every mean unchanged (HIGH wait 45.7 vs 45.2 µs, depth 2.15 vs 2.12) but grew the champion's get wait p99 by 33% (125.4 → 166.3 µs) and cut steals (21.0% vs 26.2%) while puts and syncs stayed flat, so a core-count change stretches the tail rather than reordering it, and the predicted shifts in steals and puts and syncs were wrong.
policy: On w14 the gets keep about 81 µs outside the runqueue, as on w13, while a first-ranked kind waits only 5.5 µs at p99, so the 25 µs a new policy needs must come from what passes gets in the runqueue (urgent queries, time-slice remnants), with only one point of query and lease deadline-met to spend.
