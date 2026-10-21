# p5: sjf_learn

- id: p5
- config: sjf_learn
- generation: 4
- status: rejected
- builds_on: p4
- changed_from_previous: p4 plus: each core learns, for each run-time hint value, how long its HIGH threads really run (timed between consecutive picks, leaning toward the long runs), and uses the larger of that and p4's hint plus 4 µs as a HIGH thread's length, both for ordering and for the rescue check
- commit: 103c554

## What it does
Like sjf_rescue, each core runs helper threads first, then HIGH, NORMAL and LOW threads. Among HIGH threads a short request normally goes first, and sjf_rescue's rules still apply to requests near their deadline. The change is where a HIGH request's length comes from. Each core now times the requests it runs and remembers how long requests with each run-time hint really take. A kind whose hint is honest keeps exactly sjf_rescue's order. A kind that runs longer than its hint says, like puts that sometimes flush, is ranked by how long it was seen to take: on w5 lookups (about 6 µs) now go ahead of puts (seen at roughly 10–15 µs), and puts still go ahead of queries (about 21 µs).

## Why (hypothesis)
Section 3 of results/gen4/report.md puts the champion's get p99 at 98.5 µs, with a runqueue-wait p99 of 43.3 µs against 37.7 µs for puts. It concludes that ranking puts behind gets could save at most the ~6 µs gap, because puts wait 37.7 µs even when ranked first. That bound does not hold. Among puts the older one goes first, so a put waits behind every older put on its core, flushes included. A get waits behind all of those and more: under sjf_guard and sjf_rescue a get waits for every put that became ready before it or up to 8 µs after it. The put's own wait therefore says nothing about how long a get would wait if gets went first. Three observations say the get's wait tail is mostly one hidden flush:
1. Under sjf_guard, get wait p99 jumps from 9.3 µs at 300k to 35.4 at 340k and then stays at 35–43 µs up to 390k (sjf_rescue: 32.5–40.2). That plateau is one 30 µs flush plus about 4 µs of overhead and a few µs more. It is not a multiple of a 21 µs query.
2. sjf_rescue's much narrower rescue window changed get wait p99 by only 3 µs (43.3 to 40.2). So queries promoted near their deadline do not set it.
3. w4b is the same bursty workload without puts. There sjf_rescue reached 86.5 µs.

The hint cannot tell a flushing put from a quick one, but timing can. p5 times each hinted HIGH run from its pick to the core's next pick. It keeps the sample only if a thread that pick left queued is still queued, which proves nothing else ran in between. Each sample updates a per-core estimate for that hint value. The estimate rises quickly on long runs and falls slowly on short ones, because long runs are more often lost to work stealing before they can be timed; a plain average would be biased low. Puts should settle at roughly 10–15 µs, between gets and queries, which stay at p4's hint plus 4 µs because they do not run longer than that.

With gets no longer behind flushes, w5 should look like w4b under sjf_rescue: get wait p99 15–28 µs and get p99 at 390k 83–90 µs. Acceptance needs 88.65 or less, so this is borderline. If the bar is missed, the rest is outside the policy region (Needs 2). Query deadline-met is the other risk (sjf_rescue had 87.22%, floor 87.05%); the rescue check now charges a put its learned cost, which should recover part of it.

Other workloads have no kind that runs longer than its hint plus 4 µs, so every decision is p4's. w0 has no HIGH threads, so nothing is timed and the code path is p4's.

## Cost
- **Puts** now wait for gets and, near their limit, for queries the rescue check protects. Put p99 should rise from 98.5 (p4) to about 100–115 µs; put deadline-met from 99.1% to about 98.5–99%.
- **Batch and scan** sit behind the same HIGH work as under p4, so they stay flat.
- **Per pick:** the clock is read on most picks that run a HIGH thread (p4 read it only when two HIGH threads were queued), still at most once; one extra pass over the queue when a timed pick is pending; a five-entry table lookup per HIGH thread. Without hints, two extra tests and nothing else.
- **Limits of the learning:** five hint values per core; only picks that leave two or more threads queued are timed; learning is per hint value, so kinds sharing a hint share an estimate; if too few flush runs are timed, the policy falls back to p4's order.

## Needs
These are outside the policy region, for the owner to decide:
1. **Exact run times.** The scheduler already measures how long each thread ran when it stops. Handing that to the policy, or calling the policy on every pick, would replace inference from consecutive picks.
2. **Packets wait on a busy core.** A core reads newly arrived packets only when its runqueue is empty or the 50 µs watchdog fires, and idle cores steal queued threads before packet work. In a burst a get's packet can sit up to about 50 µs before its thread exists, and that time does not count against the server's deadline. This is likely most of the ~55 µs outside the runqueue in report section 3, and of the 51–55 µs floor on w1–w3. Checking for packets at every reschedule while hinted threads are queued, or a shorter watchdog, would attack it directly. (Found by reading the scheduler, not measured.)
3. **No preemption** (as in p2–p4).
4. **Counters:** picks where the learned cost changed the choice, and each core's learned run time per hint value at the end of a run.

## Prediction (from the policy agent)

| Workload | Metric | Expected direction | Rough size |
|---|---|---|---|
| w5 | get p99 at 390k (score) | down | 98.5 (p3) / 94.0 (p4) to about 83–90 µs; acceptance needs ≤ 88.65 (borderline) |
| w5 | get runqueue-wait p99 at 390k | down | 43.3 (p3) / 40.2 (p4) to about 15–28 µs |
| w5 | put p99 / put deadline met | up / slightly down | 98.5 to 100–115 µs; 99.1 to 98.5–99.1% |
| w5 | query deadline met at 390k | flat to up vs p4 | 87.22 to 87.3–88.0% (floor 87.05; main risk) |
| w4b, w3, w2, w1 | score | same as p4 | 86.5 / 52.5 / 52.5 / 51.5 µs |
| w0 | p99 at 300k / throughput at 450k | flat | p4's code path |

## Results
Rejected in generation 4 (judge.py, results/gen4/) against the champion p3
sjf_guard, on rule 6 only (another kind with a deadline may lose at most 1
point of deadline-met).

| Workload | sjf_guard | sjf_learn | Change | Notes |
|---|---|---|---|---|
| w5 | get p99 98.5 µs | 85.0 µs (85/85) | −13.7% | get runqueue-wait p99 43.3 → 25.2 µs (predicted 15–28); **query deadline met 88.05% → 86.55% (−1.5 points)**; put met 98.84 → 98.57% |
| w4b | 94.0 µs | 86.0 µs | −8.5% | query met 87.15 → 86.72% |
| w3 | 55.0 µs | 55.0 µs | 0% | |
| w2 | 51.0 µs | 54.0 µs | +5.9% | batch p99 +17% (limit 25%) |
| w1 | 51.0 µs | 53.0 µs | +3.9% | |
| w0 | p99 at 300k 69.5 µs | 72.5 µs | +4.3% | sustained throughput −0.93% (limit 1%) |

The learning works: lookups no longer wait behind flushing puts, and the get
tail on w5 dropped as predicted. The price was paid by queries, which lost
1.5 points of deadline-met, as the card flagged as its main risk.
