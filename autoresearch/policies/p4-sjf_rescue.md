# p4: sjf_rescue

- id: p4
- config: sjf_rescue
- generation: 3
- status: rejected
- builds_on: p3
- changed_from_previous: p3 with two changes among HIGH threads: one with less than 13 µs to spare before it must start (p3: less than 0) counts as too late to save, so it is never urgent and waits for any shorter HIGH thread; and p3's fixed 20 µs urgency guard is replaced by a check against the thread p3's order would run: the savable HIGH thread with the least time to spare runs first only if waiting for that thread (its expected run time plus 4 µs) would leave it less than 13 µs
- commit: fd9a57e

## What it does
Like sjf_guard, each core runs helper threads first, then HIGH, NORMAL and LOW threads. Among HIGH threads a short request normally goes ahead of a long one. What changes is how the core treats a HIGH request that is close to its deadline. A request with less than 13 µs to spare is treated as already lost, because about that much of every request's time is spent outside the queue (network and runtime), so the client will see it miss anyway; it now waits for any shorter request instead of holding one up. A request that can still make it goes ahead of the core's normal choice only if waiting for that choice would make it too late, so a lookup still slips in front of a query with a few microseconds to spare, but not in front of one it would push past its deadline.

## Why (hypothesis)
Section 3 of results/gen3/report.md finds that during bursts gets lose time queueing behind other HIGH work and behind the thread already running. Inversions are 0, and stealing and overflow are not the cause. The addendum shows the same picture on w4b at 380k: sjf_guard get p99 94.0 µs, query deadline met 87.15%. Two parts of p3 make a get wait behind queries that gain nothing from it:

1. **The urgent window is mostly lost queries (report hypothesis 2).** p3 calls a query urgent when it has 0–20 µs of slack, and it runs the one closest to 0 first. A query takes 29.5 µs at light load for 17 µs of work, so about 13 µs is spent outside the queue. In a burst the packet also waits for the request already running before the runtime reads it (helper wait 4.56 µs mean at 380k, up to a query's ~21 µs). A query picked with less than 13 µs of slack therefore misses at the client whatever happens. On w4b only 1.77% of deadline picks are already late at the server, yet 12.85% of queries miss at the client. So the urgent rule spends core time, and the gets' waiting time, on queries that are already lost, and meanwhile the next query slides into the window.
2. **Old queries still go first.** p3's turn order (deadline plus 8× run time) runs a query ahead of a get when the query became ready more than 120 µs earlier. Such a query is already lost, and these queries exist in the worst bursts (query p99 194 µs), which is where the get tail is made.

p4 does both of the report's hypotheses:
- A thread with less than 13 µs of slack is lost: never urgent, and behind any shorter thread.
- A get passes a savable query whenever the query keeps at least 13 µs after the get runs (19 µs before it). A get then waits only for a query that can still be saved and cannot spare about 6 µs, besides the request already running.

The same check means a savable query with less than 34 µs of slack runs before a lost query of the same length, so fewer queries are dragged down behind lost ones. Expected result: get p99 at 380k falls from 94 to about 65–80 µs (acceptance needs 84.6 or less). Query deadline-met stays flat or rises; the floor is 86.15%.

Other workloads:
- **w1, w2:** HIGH queue waits are short (0.50 and 2.82 µs mean). A short or get must wait over 45 µs, or a w2 query over 170 µs, to count as lost, which is beyond p99, so the order is p3's.
- **w3:** the same deadlines without bursts. Queries over 70 µs of waiting are rare (query p99 103 µs), so get p99 stays flat or improves slightly.
- **w0:** no HIGH threads, so this is p3's code path and the clock is never read.

## Cost
- **Lost queries wait longer.** They now yield to gets and to savable queries, so query p99 may rise a little (194 to at most about 225 µs; the limit is 242.5), and late-at-pick rises.
- **Gets still wait for a savable query.** When a query has less than 19 µs to spare, a get waits for it (about 21 µs).
- **Batch and scan are unaffected:** the HIGH work and the class order are the same.
- **Per pick:** as in p3, the clock is read at most once and only when two HIGH threads are queued. Each HIGH thread adds a few additions and comparisons, and one more candidate is tracked.
- **Hints are trusted.** A long HIGH thread that is already lost can be passed by shorter HIGH threads for as long as they keep the core busy; here gets use about 6% of core time.
- **Tuned to this setup.** The 13 µs and 4 µs constants are measured here (light-load latency and calibration.json) and would need re-measuring elsewhere.

## Needs
These limits are outside the policy region, for the owner to decide:
1. **No preemption** (as in p2 and p3). A get that arrives while a query runs still waits for it, and so does the packet that carries the get.
2. **Per-request arrival time.** The 13 µs threshold is a constant because the runtime does not record when a request's packet arrived. Recording that time when the packet is received would let the policy count the time each request has already spent before its thread became ready, instead of an estimate.
3. **Counters (report section 6.3).** Queue wait per kind, and a count of picks where the rescue check overrode the short-first choice. Together they would test this hypothesis directly.

## Prediction (from the policy agent)

| Workload | Metric | Expected direction | Rough size |
|---|---|---|---|
| w4b | get p99 at 380k (score) | down | 94.0 to about 65–80 µs (−15 to −30%; acceptance needs ≤ 84.6) |
| w4b | query deadline met % at 380k | flat to up | 87.15 to about 87–90 (rule 6 floor 86.15) |
| w4b | query p99 at 380k | flat to up | 194 to about 190–225 µs (limit 242.5) |
| w4b | batch p99 / scan p99 at 380k | flat | 285.5 / 306 within ±10% |
| w4b | late at pick at 380k | up | 1.77% to about 2–3.5% |
| w3 | get p99 at 400k | flat to slightly down | 55 to about 51–56 µs (limit 60.5) |
| w2 | get / query / batch p99 at 400k | flat | 51 / 101 / 140 within ±6% |
| w1 | short / long p99 at 400k | flat | 51 / 111 within ±6% |
| w0 | req p99 at 300k, throughput at 450k | flat | same code path as p3 for unhinted threads |

## Results
Rejected in generation 3 (judge.py, results/gen3/) against the champion p3
sjf_guard, on rule 1 only: the newest workload must improve by at least 10%
or 10 µs.

| Workload | Score (sjf_guard) | Score (sjf_rescue) | Change | Other kinds |
|---|---|---|---|---|
| w4b | get p99 94.0 µs (94/94) | 86.5 µs (86/87) | −8.0% (−7.5 µs) | query deadline met 87.91% vs 87.15%; batch, scan −2% |
| w3 | get p99 55.0 µs | 52.5 µs | −4.5% | query met 99.04% vs 98.94% |
| w2 | get p99 51.0 µs | 52.5 µs | +2.9% (noise) | query met 99.62% vs 99.75% |
| w1 | short p99 51.0 µs | 51.5 µs | +1.0% | |
| w0 | p99 at 300k 69.5 µs | 69.0 µs | overhead ok | |

The improvement on w4b is real (repeats do not overlap) and nothing got worse,
but it is smaller than predicted (65–80 µs). The rule stands; a later policy
may build on this one.
