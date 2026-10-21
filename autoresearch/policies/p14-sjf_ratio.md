# p14: sjf_ratio

- id: p14
- config: sjf_ratio
- generation: 13
- status: candidate
- builds_on: p13
- changed_from_previous: p13 plus: when the core's time unit is above 1, p4's rescue check lets an urgent HIGH thread run ahead of the chosen one only if its learned length is at most 3 times the chosen one's (urgent 68 µs queries no longer pass 7 µs gets or 2 µs leases, but still pass puts, syncs and multigets); at unit 1 (w1–w10) every decision is p13's; order, lengths, slack, unit, timing and learning unchanged
- commit: (filled by orchestrator)

## What it does
Like sjf_upper, each core runs helper threads first, then HIGH, NORMAL and LOW threads, and among HIGH threads it runs short requests first. A request close to missing its deadline may still jump the queue. sjf_ratio allows that jump only when the waiting request is not much shorter than the one jumping. On w14, a 68 µs query about to miss its deadline no longer runs ahead of a 7 µs lookup or a 2 µs lease renewal. The lookup runs first and costs the query only a few microseconds. The query may still jump ahead of puts, syncs and multigets. On the older workloads that use the small time scale (w1–w10), nothing changes.

## Why (hypothesis)
- **Where the gets' tail is:** in the gen 13 report, all of the +39 µs in get p99 from w13 to w14 is runqueue wait (166.3 µs at p99). The roughly 81 µs outside the runqueue is flat. Leases, which run first, wait only 5.5 µs, so most of the gets' wait is a matter of order (report hypothesis 1).
- **Urgent queries are what passes gets:** w12 and w13 differ only in the queries' deadline (400 to 300 µs), and both run at unit 4. Between them, the champion's get wait p99 rose from 84.5 to 125.4 µs.
  - Under the p13 order, a query never passes a get by turn: it would need about 400 µs more waiting, and it is too late after about 220 µs.
  - It passes only through the rescue, when it has 9–20 µs of slack left. Each such pass costs the waiting get the query's full ~72 µs.
  - On 6 cores more queries cross that window (query wait p99 +27%).
- **Why it costs queries little:** a query denied the rescue waits only for the get (~11 µs), and it still has slack (about −1 to +9 µs).
- **Why the cut-off is 3 times:** in learned lengths, query to get is about 6–7 and query to lease about 18, while query to the capped put/sync label is about 2.6 and to multigets about 2.3. So only the intended pairs change.
- **Why it is off at unit 1:** on w1–w10 the query-to-get ratio is about 3.5–4, close to the cut-off, and those workloads have 1-point margins. With the rule off there, the decisions are p13's exactly.
- **The time slice:** the rule compares learned label lengths, not ready times, so threads re-queued after the 100 µs time slice do not affect it.
- **Offline check** (scratchpad p14/sim.c: the real policy region, 6 cores, 100 µs time slice, bursts, stealing). The model under-reads the real waits, so only relative changes count.
  - **Lockstep:** 0 of about 0.5M picks differ from p13 on w9, w10, w5 and w2; on w14, 0.4% differ.
  - **w14 get p99:** −14% to −21% across three overhead settings (get wait p99 85→40, 108→49, 118→65 µs).
  - **w13 and w12 get p99:** −15% and −13%.
  - **Other kinds (w14, w13, w12):** query deadline-met −0.05 to +0.4 points; put deadline-met +0.07 to +0.12 points; sync p99 −3% to −8%; lease deadline-met +0.2 points.

## Cost
- **Queries:** those that reach the urgent window while a get or lease waits now wait one short request longer. A few may then miss. Expected −0.5 to +0.3 points of query deadline-met against 1 point of room.
- **Puts and syncs:** urgent puts and syncs no longer pass leases. That is about 4 µs each, and it is rare.
- **Per-pick work:** one more saved length and one multiply-and-compare per pick with two or more HIGH threads. No extra clock read and no new state.

## Prediction (from the policy agent, against sjf_upper)

| Workload | Metric (headline load) | Expected vs sjf_upper |
|---|---|---|
| w14 (75k) | get p99 | −11% to −21% (247.5 → about 195–220 µs; limit 222.8) |
| w14 | get runqueue-wait p99 | 166.3 → about 110–140 µs |
| w14 | query deadline-met / p99 | −0.5 to +0.3 points (85.72; room 1.0) / ±5% |
| w14 | lease deadline-met / p99 | flat to +0.3 points (95.09) / flat (132) |
| w14 | put deadline-met / put p99 | flat to +0.2 points (98.92) / −0% to −5% (408) |
| w14 | sync p99 | −0% to −8% (560.5) |
| w14 | multiget, batch, scan p99 | within ±5% |
| w13 (100k) | get p99 | −8% to −18% (208.5 → about 170–195 µs; limit 229.4) |
| w13 | query / put deadline-met | −0.5 to +0.3 / flat to +0.2 points |
| w11, w12 | get p99 | −3% to −12% (unit 4, same mechanism; w11 has no leases) |
| w1–w10 | all kinds | identical decisions (unit 1); noise only, paired confirmation if drift |
| w0 | p99 one level below headline, overloaded throughput | identical path (no HIGH threads); noise only |

## Results
(filled after evaluation)
