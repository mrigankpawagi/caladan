# p3: sjf_guard

- id: p3
- config: sjf_guard
- generation: 2
- status: candidate
- builds_on: p2
- changed_from_previous: p2 plus: among HIGH threads, one that must start within 20 µs to finish by its deadline runs first (most urgent first; a thread that can no longer finish in time is not urgent), and the others run in order of deadline plus 8 times their expected run time instead of deadline alone
- commit: (filled by orchestrator)

## What it does
Like edf_high, each core runs runtime helper threads first, then HIGH, then NORMAL, then LOW, and NORMAL and LOW threads keep their oldest-first order. Inside HIGH, the core now also uses each request's expected run time, so a short request normally goes ahead of a long one. Each HIGH thread's turn is its deadline pushed back by eight times its expected run time, which lets a 2 µs lookup pass a 17 µs query that arrived up to 120 µs before it, but no earlier. The exception is a HIGH thread that will miss its deadline unless it starts within the next 20 µs: it runs first, the most urgent one first. A thread that can no longer finish on time does not count as urgent. It keeps its normal turn, so it does not hold up requests that can still make their deadlines.

## Why (hypothesis)
Section 3 of results/gen2/report.md shows that on w3 gets wait behind older queries of their own class. Both kinds gain about 77 µs at p99 over their light-load medians, inversions are 0, and the mean HIGH queue wait (3.81 µs) is enough to explain the tail. With one shared deadline, deadline order is arrival order, so only the run-time hint can tell a get from a query. The traffic is the same as w2's, where edf_high let gets pass nearly every query and get p99 fell to 53 µs. Ordering by deadline plus eight times run time does the same on w3: a get passes any query that arrived up to 120 µs before it. So get p99 at 400k should fall from 87.5 µs to about 53–65 µs; acceptance needs 78.75 µs or less.

The risk is the queries' new 100 µs deadline. On w2 the same passing raised query p99 from 103.5 to 111.5 µs. At that shape about 1.5% of queries would take more than 100 µs, against 1.16% now. The urgent rule is the report's hypothesis 1 with its 20 µs guard: about 13 µs of a query's deadline is spent outside the run queue, plus one get of about 5.7 µs. Under it, a query close to the edge is no longer passed. Threads that can no longer finish on time are left out of the urgent rule because they miss anyway; at least the 0.36% of HIGH picks that are late at pick are such threads. Running them first would only delay gets and other queries.

Hypothesis 2 in the report has its sign backwards. Ordering by deadline minus a multiple of run time (latest start time) puts the long query first, so short requests need their run time to push their turn later, not earlier.

Other workloads:
- **w2:** almost unchanged. Gets already passed queries up to 140 µs older and now pass queries up to 260 µs older, and a query becomes urgent only after waiting 163 µs.
- **w1:** one HIGH kind, so the order is p2's. The only exception is a short request that can still make its deadline going before one that cannot, which is beyond p99 (zero late at pick there).
- **w0:** no HIGH threads. Every pick is p2's and the clock is never read.

## Cost
Queries give way to gets, which use about 6% of core time. Query p99 should change by a few µs, and query deadline-met should fall by at most a few tenths of a point; the limit is 1 point. Batch and scan wait behind the same amount of HIGH work as under edf_high, so their p99 should stay near 147 and 158.5 µs, and scans still finish. A get that meets an urgent query waits for it (about 21 µs). That should affect about 1% of gets, which is why the prediction is 53–65 µs rather than 53.

Each pick reads the clock at most once (about 20 cycles), and only when at least two HIGH threads are queued. It also does a few additions and comparisons per HIGH thread.

The run-time hint is trusted. A long request that claims to be short goes ahead of real short ones, but only past threads due within eight times the claimed difference. A HIGH thread without a run-time hint counts as zero-length in the same bounded way.

Under sustained overload, a thread that can no longer make its deadline may wait a long time, because threads that can still make theirs keep passing it. This is deliberate, since it protects requests that can still be saved, and is not expected at or below the headline load. At 440k, query p99 may rise while query deadline-met rises too.

## Needs
These limits are outside the policy region, for the owner to decide (as in p2):
1. **No preemption.** A get that arrives while a query or scan is running still waits up to about 21 µs. w1 and w2 both stopped near 52 µs for this reason, so w3 cannot go much below that from inside the policy.
2. **Hint-blind stealing.** On w3 at 400k, 26% of hinted threads are stolen, and stealing takes the oldest half of a queue whatever its hints. A steal filter that prefers short or urgent HIGH threads could cut the tail further.

## Prediction (from the policy agent)

| Workload | Metric | Expected direction | Rough size |
|---|---|---|---|
| w3 | get p99 at 400k (score) | down | 87.5 to about 53–65 µs (−25 to −40%; acceptance needs ≤ 78.75) |
| w3 | query p99 at 400k | flat to slightly up | 107 to about 104–115 µs (limit 133.75) |
| w3 | query deadline met % at 400k | flat to slightly down | 98.84 to about 98.5–98.9 (rule 6 floor 97.84) |
| w3 | get deadline met % at 400k | up | 99.22 to 99.5 or more |
| w3 | batch p99 / scan p99 at 400k | flat | 147 / 158.5 within ±10% (limits 183.75 / 198) |
| w3 | scan answered | unchanged | 100% at every level |
| w3 | wait_us_high at 400k | slightly down | 3.81 to about 3.1–3.6 µs |
| w3 | inversion_rate / late at pick | unchanged / flat | 0 / 0.36% to about 0.3–0.5% |
| w3 | get p99 at 440k (unscored) | down | 288.5 to about 100–180 µs; query p99 there may rise |
| w2 | get p99 at 400k | flat | 53 within ±6% (limit 58.3) |
| w2 | query p99 / batch p99 / query met at 400k | flat | 111.5 / 160 / 99.69% within noise (limits 139.4 / 200 / 98.69) |
| w1 | short p99 / long p99 at 400k | flat | 52 / 115 within ±6% (limits 57.2 / 143.75) |
| w0 | req p99 and throughput at 350k | flat | 188.5 within 6% (limit 199.8); throughput within 0.2% |

## Results
(filled after evaluation)
