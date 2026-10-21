# p6: sjf_timed

- id: p6
- config: sjf_timed
- generation: 5
- status: rejected
- builds_on: p3
- changed_from_previous: p3 plus: a HIGH thread's expected run time is the run time this core has measured for threads with the same run-time hint (p5's timing and estimate, without p5's floor, so it can end up below the hint as well as above it; the hint plus 4 µs until measured), used both in the thread's turn (deadline plus 8 times the run time) and in the 20 µs urgency test
- commit: 23c4704

## What it does
Like sjf_guard, each core runs helper threads first, then HIGH, NORMAL and LOW threads. Among HIGH threads a short request normally goes ahead of a long one, and a request that must start within 20 µs to make its deadline goes first. The change is where a HIGH request's length comes from. Each core times the requests it runs, remembers how long requests with each run-time hint really take, and uses that instead of the hint, whether it is shorter or longer. Lookups that the server still calls 20 µs jobs, but that finish in a few microseconds, go ahead of queries again; puts, whose occasional flushes make them slower than their 1 µs hint, go after lookups; and a request that is already too late keeps its usual place instead of being pushed behind newer work.

## Why (hypothesis)
results/gen5/report.md, sections 1 and 3: on w6 the stale 20 µs lookup hint raised the champion's get p99 from 98.5 µs (w5) to 143.0. Get runqueue-wait p99 went from 43.3 to 78.8 µs, and the report puts 35.5 of the 44.5 µs rise down to queueing. The cause is ordering: sjf_guard's turn is the deadline plus 8 times the hint, so a lookup runs after every query that arrived before it or up to 24 µs after it, escaping only through the urgency window after 60–80 µs of waiting.

p6 follows the report's hypotheses 1 and 2: lengths come from observed run times in both directions, and p4's too-late rule is not used. Once a core has timed a few hundred runs, a hint value is only a label for its own estimate. The only difference between w6 and w5 is the lookups' hint value, so p6 makes the same decisions on both. Expected lengths: a few µs for lookups, about 19–21 µs for queries, about 12–16 µs for puts (the estimate leans toward the 30 µs flushes). Expected: w6 get p99 about 85–100 µs against the 133.0 threshold, get wait p99 about 25–45 µs.

Why not build on p5: on w6 its max(learned, hint + 4) rated lookups at 24 µs and its lost rule then put late lookups behind every newer query (get wait p99 165.2 µs vs fifo's 152.3); on w5 it cost queries 1.5 points of deadline-met. p6 keeps p3's urgency rule and none of p4's rules, so on w5 each change either takes work away from queries or leaves it unchanged; query deadline-met should stay near 88.05% (floor 87.05%), and on w6 rise from 87.08%.

On w1–w4b the hints are honest, so every kind measures at roughly its hint plus 1–4 µs and picks are p3's except near a boundary. On w0 there are no HIGH threads, so nothing is timed and the clock is never read.

## Cost
- **Puts pay:** they now go after lookups and pass fewer queries (expected put p99 on w5 105–125 µs, limit 129.4; put deadline-met ≥ 98.2%, floor 97.84).
- **Lookups gain less than under p5 on w5** (85.0): they still wait for urgent queries and puts.
- **Batch and scan are flat.**
- **Per pick:** the same as p5 (at most one clock read; one extra queue pass when a timed pick is pending; a five-entry table lookup per HIGH thread; on w0 one extra test).
- **Learning limits:** five hint values per core; only picks that leave two or more threads queued are timed; kinds sharing a hint share an estimate; estimates move 1/16 up toward longer runs and 1/64 down, so on w6 a core needs about 15 timed lookup runs to rank them ahead of queries and about 150 to settle.
- **What it trusts:** the hint is only a label now; a kind with bimodal run time is ranked near its long runs.

## Needs
Outside the policy region, for the owner: exact run times from the scheduler; packets waiting on a busy core (64.2 µs of the champion's get p99 on w6 is outside the runqueue); preemption; counters for each core's learned run times.

## Prediction (from the policy agent)

| Workload | Metric | Expected direction | Rough size |
|---|---|---|---|
| w6 | get p99 at 390k (score) | down | 143.0 to about 85–100 µs (threshold ≤ 133.0) |
| w6 | get runqueue-wait p99 at 390k | down | 78.8 to about 25–45 µs |
| w6 | query deadline met % at 390k | flat to up | 87.08 to about 87.3–88.5 (floor 86.08) |
| w6 | put p99 / put deadline met % | flat to up / flat | 112.5 to 100–125 µs (limit 140.6); 98.26 to 98.0–98.8 (floor 97.26) |
| w5 | get p99 at 390k | down | 98.5 to about 85–97 µs (limit 108.35) |
| w5 | query deadline met % at 390k | flat | 88.05 to about 87.5–88.5 (floor 87.05; the main risk) |
| w5 | put p99 / put deadline met % | up / slightly down | 103.5 to 105–125 µs (limit 129.4); 98.84 to 98.2–98.8 (floor 97.84) |
| w4b | get p99 / query deadline met % at 380k | flat | 94.0 within ±6% (limit 103.4); 87.15 ± 0.7 (floor 86.15) |
| w3 / w2 / w1 | score at 400k | flat | 55 / 51 / 51 within ±6% |
| w0 | p99 at 300k / sustained throughput at 450k | flat | p3's path plus one test per pick |

## Results
Rejected in generation 5 (judge.py, results/gen5/) against the champion p3
sjf_guard, on rules 3 and 6, both for puts.

| Workload | sjf_guard | sjf_timed | Change | Notes |
|---|---|---|---|---|
| w6 | get p99 143.0 µs | 92.0 µs (92/92) | −35.7% | get wait p99 78.8 → 27.4 µs; query met 87.08 → 87.43%; **put met 98.26 → 96.86% (−1.4 points)** |
| w5 | get p99 98.5 µs | 91.5 µs | −7.1% | query met 88.05 → 87.30% (held); **put p99 103.5 → 134.0 µs (+29.5%), put met 98.84 → 97.15% (−1.7 points)** |
| w4b | 94.0 µs | 92.5 µs | −1.6% | query met 87.62% |
| w3 / w2 / w1 | 55.0 / 51.0 / 51.0 µs | 55.5 / 52.5 / 51.5 µs | within noise | |
| w0 | p99 at 300k 69.5 µs | 69.0 µs | overhead ok | |

Learning in both directions did what the card predicted: on w6 lookups are
ranked by their real run time again and the stale hint costs them nothing
(92 µs on both w5 and w6), and queries were protected this time. The cost
moved to puts: ranked by their flush-inflated learned run time (about 12–16
µs), they now wait behind lookups and fewer of them pass queries, and they
lose more than the 1 point of deadline-met rule 6 allows.
