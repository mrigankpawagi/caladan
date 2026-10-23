# p9: sjf_pair

- id: p9
- config: sjf_pair
- generation: 8
- status: accepted
- builds_on: p8
- changed_from_previous: p8 plus: each core learns run times per pair of run-time hint and coarse deadline (whether the deadline is more than 250 µs after the thread became ready) instead of per run-time hint alone, so kinds that share a hint but not a deadline class keep separate estimates; order, caps, slack and timing unchanged
- commit: b666cb1

## What it does
Like sjf_capped, each core runs helper threads first, then HIGH, NORMAL and LOW threads. Among HIGH threads it puts shorter requests first and learns from its own timings how long requests really take. sjf_capped keeps one learned length per run-time hint, so two kinds that share a hint have their run times averaged together. sjf_pair also asks how far off a request's deadline is: requests whose deadline is more than 250 µs away when they join the queue are learned apart from requests with the same hint and a nearer deadline. On w9 this keeps the 2 µs lookups' learned length short, while the 30 µs multigets, which borrowed the lookups' hint but carry a 300 µs deadline, get their own long estimate; on every earlier workload no request has so distant a deadline, so sjf_pair makes exactly sjf_capped's choices.

## Why (hypothesis)
results/gen8/report.md, sections 3 and 6 (hypothesis 1). On w9 the champion's get p99 rose from 83.0 (w8) to 95.0 µs. Over the same step, get runqueue-wait p99 rose from 25.4 to 40.9 µs, while the part outside the runqueue stayed about the same (57.6 → 54.1 µs). The cause is the shared "2 µs" label. About one run in four with that hint is a 34 µs multiget, so the learned length of gets rises toward the 14 µs cap. That moves gets back toward the puts' and syncs' turn of +204 µs: +212 at the cap, and about a quarter of that penalty in practice.

Only multigets carry a 300 µs deadline. Every other HIGH kind in w1–w9 has 200 µs or less. So a key of (hint, deadline more than 250 µs after ready) separates exactly the two w9 kinds that share a hint and changes nothing anywhere else.
- **Measurement fits.** The server sets the deadline at classification, just before the thread is readied. Deadline minus ready time is therefore about 299 µs for a multiget, at most 100 µs for the 100 µs kinds, and at most 200 µs for w2's queries. 250 sits halfway.
- **Slots fit.** w9 needs 4 keys ('2 µs tight', '1 µs', '17 µs', '2 µs relaxed') of the 5 slots. LOW scans are never timed. The flag uses the key's spare top bit, so no new state slot is used.

With gets learned at about 6 µs, the turns counted from becoming ready are:

| Kind | Turn |
|---|---|
| gets | +148 µs |
| puts and syncs ('1 µs' label, capped at 13 µs) | +204 µs |
| queries (about 21 µs) | +268 µs |
| multigets (learned about 34 µs, capped at 14 µs) | +412 µs |

That is w8's order with multigets last.

Multigets' place relative to queries is deliberately left as now. They count 14 µs, under the queries' 21 µs, so a query that is already too late still waits for queued multigets, as under the champion. Report section 4 shows that pushing multigets back behind late queries leaves only 3% of p99 and 0.2 points of deadline-met margin. One small side effect: under the champion the shared label usually sat below 13 µs, so too-late puts and syncs also waited for multigets. At 14 µs they no longer do.

Expected on w9: get runqueue-wait p99 back to w8's level (about 25 µs). The report notes this already matches at 290k: 5.7 against 5.45 µs. That gives get p99 about 78–88 µs against the 85.5 threshold. The margin is thin, because the 30 µs multigets that cannot be passed while running (no preemption) stay in the part outside the runqueue.

## Cost
- **Multigets** count at the 14 µs cap instead of somewhat below it. Too-late puts and syncs stop waiting for them, so multiget p99 may rise slightly (limit 311.3 µs, deadline-met floor 98.81%). Their order against gets and queries is unchanged.
- **Puts and queries on w9** see w8's order: gets pass them more often. On w8 that cost puts and queries nothing under p8 (97.13% and 83.49% deadline-met).
- **Rare mislabel:** a thread handed back by the IOKernel (thread_cede) is re-queued with the oldest queued thread's ready time. On a deep queue this can mark a 100 µs thread as relaxed. With 8 guaranteed spinning kthreads in every workload this should be negligible.
- **Per pick:** one subtraction and comparison per HIGH thread priced, and one at each timed pick. The clock is still read at most once. Without HIGH threads the path is p8's.
- **Limits:** five (hint, deadline-class) pairs per core; a sixth falls back to hint plus 4 µs. The 250 µs split is tuned to these workloads (deadlines of 60, 100, 200 and 300 µs). Kinds that share both hint and deadline (w8's syncs and puts) are still learned together.

## Needs
Unchanged from p8, for the owner: preemption (a get cannot pass a running 30 µs multiget or sync); packet processing while hinted threads wait (about 54 µs of the get p99 is outside the runqueue); a learning key the server sets per kind; and counters for each core's learned lengths and how often the cap binds.

## Prediction (from the policy agent)

| Workload | Metric | Expected direction | Rough size |
|---|---|---|---|
| w9 | get p99 at 370k (score) | down | 95.0 → about 78–88 µs (threshold ≤ 85.5) |
| w9 | get runqueue-wait p99 at 370k | down | 40.9 → about 22–32 µs (w8 level 25.4) |
| w9 | get p99 at 320k / 345k | down | 77.5 / 88.5 → about 68–75 / 75–83 µs |
| w9 | put deadline met % / put p99 | flat to slightly up / flat | 97.02 → 96.8–97.8 (floor 96.02); 130.5 → 115–140 µs (limit 163.1) |
| w9 | query deadline met % / query p99 | flat / flat | 83.81 → 83.3–84.5 (floor 82.81); 252.0 → 235–265 µs (limit 315.0) |
| w9 | multiget deadline met % / multiget p99 | flat / flat to slightly up | 99.81 → 99.5–99.9 (floor 98.81); 249.0 → 240–275 µs (limit 311.3) |
| w9 | sync p99 | flat | 157.0 → 145–165 µs (limit 196.3) |
| w9 | batch / scan p99, scans answered | flat | 326.0 / 347.5 within ±5%; 100% |
| w8 | get p99 at 380k and all kinds | same decisions as p8 | 83.0 within session drift (limit 91.3) |
| w7 / w6 / w5 / w4b / w3 / w2 / w1 | score and deadline-met | same decisions as p8 | within session drift (no deadline over 200 µs) |
| w0 | p99 one level below the headline / sustained throughput | flat (p8's path) | within noise; within 0.5% |

## Results
Accepted in generation 8 (judge.py, results/gen8/) against the champion p8
sjf_capped, after a paired confirmation. The first verdict rejected p9 on
rule 6: query deadline-met on w8 (82.33% vs 83.49%), where p9 makes p8's
decisions, and on w9 (82.70% vs 83.81%), against champion runs from earlier
sessions. Re-measured alternately in one session, queries matched on both,
and the judge accepted.

| Workload | sjf_capped | sjf_pair | Change | Notes |
|---|---|---|---|---|
| w9 (paired) | get p99 99.0 µs | 86.0 µs | −13.1% | predicted 78–88; get wait p99 42.95 → 25.7 µs (predicted 22–32) |
| w9 (paired) | query met / put met | 82.52% / 96.69% | 82.52% / 96.75% | flat |
| w9 (paired) | multiget p99 / met | 254.0 µs / 99.74% | 265.5 µs / 99.67% | +4.5%, as predicted (slightly up) |
| w9 (first pass) | get p99 95.0 µs | 85.5 µs | −10.0% | exactly at the threshold |
| w8 (paired) | get p99 84.5 µs | 84.5 µs | 0% | identical decisions |
| w1–w7 | | | −0.6 to +6.6% | identical decisions; w3 scan p99 +22.1% (limit 25%) is drift between sessions |
| w0 | p99 at 300k 69.5 µs | 72.0 µs | +3.6% | sustained throughput −0.70% |

The prediction held: learned apart, multigets no longer inflate the gets'
length, and get runqueue wait returns to the w8 floor of about 25 µs.
