# p7: sjf_nohint

- id: p7
- config: sjf_nohint
- generation: 6
- status: accepted
- builds_on: p3
- changed_from_previous: p3 plus: a HIGH thread without a run-time hint counts as 8 µs long instead of 0, both in its turn (deadline plus 8 times its run time) and in the 20 µs urgency test; threads that carry a run-time hint are ranked exactly as in p3
- commit: d0ae8e4

## What it does
Like sjf_guard, each core runs helper threads first, then HIGH, NORMAL and LOW threads. Among HIGH threads a short request normally goes ahead of a long one, and a request that must start within 20 µs to make its deadline goes first. The only change is for a HIGH request whose expected run time the server left blank, such as w7's 30 µs replica syncs. sjf_guard counted the blank as zero, so these requests ran ahead of every waiting lookup and put; sjf_nohint counts it as 8 µs, so a sync now lets lookups and puts that arrive shortly after it go first, but still runs ahead of the long queries. Requests that carry a run-time hint are ranked exactly as before, so every earlier workload gets the same decisions.

## Why (hypothesis)
results/gen6/report.md, section 3: on w7 the champion's get p99 is 139.0 µs, and 96.0 µs of that is runqueue wait (w5: 43.3 of 98.5). sjf_guard ranks a HIGH thread by its turn, the deadline plus 8 times its run-time hint. Counted from the moment a thread becomes ready, the turns are sync +100 µs, put +108, get +116 and query +236. So syncs, 9.3% of core time in 30 µs jobs, run ahead of the gets and puts queued with them; put runqueue-wait p99 rose from 37.7 to 94.6 µs and put deadline-met fell from 98.84% (w5) to 95.87%.

This is the report's hypothesis 1. With a blank counted as 8 µs, a sync's turn is +164: a get goes ahead of any sync that became ready up to 48 µs before it, and a put up to 56 µs, which gives gets, puts and queries back w5's order (sjf_guard had get p99 98.5 there). A sync still goes ahead of every query unless the query became ready more than 72 µs earlier, when the query is nearly lost. sjf_timed showed what syncs cost once gets go ahead of them: only 5 µs of get p99 (96.5 on w7 against 91.5 on w5). Expected: w7 get p99 about 100–115 µs; the threshold is 129.0.

Protecting every kind with a deadline (the gen5 lesson): compared with sjf_guard, only syncs move, and they move later against every other kind, so puts and queries can only gain at first order. The second-order risk is the urgency window: syncs now wait longer, so more reach it at 72–92 µs of waiting; under sjf_timed, whose sync window was similar, query deadline-met did not move. The same window caps how long a sync can wait, which protects rule 3 (sync p99 limit 180.6).

Why not learn the sync's length: syncs really take about 34 µs, which would put them behind queries that became ready up to 136 µs after them and break the sync cap. Why not rank gets ahead of puts: p5 and p6 did, and puts paid each time.

Other workloads: every HIGH kind in w1–w6 carries a run-time hint, so every pick there is p3's. w0 has no HIGH threads.

## Cost
- **Syncs pay:** sync wait p99 from 60.8 to about 75–95 µs and sync p99 from 144.5 to about 150–170 (limit 180.6). Syncs have no client deadline.
- **Gets still wait** for puts (flushes included), as on w5, and for a sync already running (no preemption).
- **Per pick:** p3's work plus one test per queued HIGH thread for a missing hint; at most one clock read, only when two HIGH threads are queued; no per-core state.
- **A tuned constant:** 8 µs fits these hints (1–2 µs short kinds, 17 µs queries); an unhinted kind that is really short would be ranked a little behind gets.

## Needs
Outside the policy region, for the owner (as in p2–p6): preemption (a get cannot pass a running 30 µs sync); packets waiting on a busy core (about 43 µs of the champion's get p99 is outside the runqueue); hint-aware stealing (30.2% of hinted threads are stolen).

## Prediction (from the policy agent)

| Workload | Metric | Expected direction | Rough size |
|---|---|---|---|
| w7 | get p99 at 380k (score) | down | 139.0 to about 100–115 µs (threshold ≤ 129.0) |
| w7 | get runqueue-wait p99 at 380k | down | 96.0 to about 45–60 µs |
| w7 | put deadline met % / put p99 | up / down | 95.87 to about 97–98.5 (floor 94.87); 140.0 to about 105–125 µs (limit 175.0) |
| w7 | query deadline met % / query p99 | flat | 83.72 to about 83.3–84.5 (floor 82.73); 217.5 to about 210–225 µs |
| w7 | sync p99 / sync wait p99 | up | 144.5 to about 150–170 µs (limit 180.6); 60.8 to about 75–95 µs |
| w7 | batch / scan p99, scans answered | flat | 297 / 320 within ±5%; 100% |
| w1–w6 | score | unchanged (identical picks) | 51 / 51 / 55 / 94 / 98.5 / 143 within noise |
| w5, w6 | put and query deadline met % | unchanged | within noise of sjf_guard |
| w0 | p99 at 300k / sustained throughput | flat | about 69.5 µs (limit 73.7); within 0.3% |

## Results
Accepted in generation 6 (judge.py, results/gen6/) against the champion p3
sjf_guard. The first verdict was a rejection on w5 rule 6 (query deadline-met
86.50% against sjf_guard's 88.05% from gen 4), although both policies make
identical decisions there. A paired confirmation, the two policies alternated
on w5 in one session, gave 86.92% against 86.81%: the gap was drift between
sessions, and the judge accepted.

| Workload | sjf_guard | sjf_nohint | Change | Notes |
|---|---|---|---|---|
| w7 | get p99 139.0 µs | 116.5 µs | −16.2% | predicted 100–115; get runqueue-wait p99 96.1 → 61.8 µs (predicted 45–60) |
| w7 | put p99 / met | 140.0 µs / 95.87% | 117.5 µs / 97.98% | puts gain, as predicted; put wait p99 94.6 → 45.5 µs |
| w7 | query p99 / met | 217.5 µs / 83.72% | 219.5 µs / 83.28% | flat, as predicted |
| w7 | sync p99 / wait p99 | 144.5 / 60.8 µs | 174.5 / 91.9 µs | +20.8% (limit 25%); syncs pay, as predicted |
| w5 (paired) | get p99 100.5 µs | 100.0 µs | −0.5% | identical decisions; query met 86.81 vs 86.92% |
| w6 | 143.0 µs | 140.5 µs | −1.7% | identical decisions |
| w4b | 94.0 µs | 94.0 µs | 0% | |
| w1, w2, w3 | 51.0 / 51.0 / 55.0 µs | 53.0 / 54.0 / 57.5 µs | +3.9 to +5.9% | identical decisions; within the 10% rule, so drift of this size is normal |
| w0 | p99 at 300k 69.5 µs | 70.5 µs | +1.4% | sustained throughput −0.76% |

The prediction held on every line: an unhinted HIGH kind counted as 8 µs
lets gets and puts pass syncs, and only syncs pay. sjf_timed still has the
lower get tail on w7 (96.5 µs) but costs puts 2 points of deadline-met.
