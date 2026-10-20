# p2: edf_high

- id: p2
- config: edf_high
- generation: 1
- status: accepted
- builds_on: p1
- changed_from_previous: p1 plus: among HIGH threads, run the one whose deadline comes first (oldest first on ties; a HIGH thread without a deadline counts as due 1 ms after it became ready)
- commit: 7281afd

## What it does
Like prio, each core runs runtime helper threads first, then HIGH, then NORMAL, then LOW. The change is inside the HIGH class. Instead of the HIGH thread that has waited longest, the core runs the one whose deadline is soonest. So a quick lookup due in 60 µs goes ahead of a long query due in 200 µs, even if the query arrived first. A HIGH thread with no deadline counts as due 1 ms after it became ready, so it cannot be passed forever. NORMAL and LOW threads, including every unhinted one, keep prio's oldest-first order.

## Why (hypothesis)
Section 3 of results/gen1/report.md shows that on w2 under prio, gets and queries both gain the same 73.5 µs of extra p99 delay over their light-load medians. Inversions are 0, and the HIGH queue wait (3.64 µs mean) is enough to explain the whole tail. So gets wait behind older queries of their own class. With deadline order, a get passes any query queued less than 140 µs before it. That is nearly all of them (query p99 is 103.5 µs), so w2's get behaves like w1's short request. Get p99 at 400k should approach prio's 52.5 µs floor on w1; acceptance needs 76 µs or less. On w1 every HIGH thread has the same 60 µs deadline, so deadline order is arrival order and nothing changes. On w0 no thread is HIGH, so every pick is the same as prio's.

## Cost
Queries now give way to gets, which use only about 6% of core time. Query p99 should rise by a few µs, well inside its 200 µs deadline and the 25% budget, and no get can pass a query that was queued more than 140 µs earlier. Batch waits behind the same amount of HIGH work as under prio, so batch p99 should stay near prio's 144.5 µs, which is already 21% above fifo. Each pick costs one extra comparison per queued thread, plus a deadline comparison for each HIGH thread, and no clock read. Under overload, threads already past their deadline still go first, so a flood of late HIGH work could delay HIGH work that is still on time. That is the usual weakness of deadline order and is not expected on these workloads. The deadline is the one set when the hint was applied. A long-lived thread that keeps an old request's deadline would jump the HIGH queue; this cannot happen with the per-request UDP threads used here.

## Needs
These two limits are outside the policy region and are for the owner to decide:
1. **No preemption.** A get that arrives while a query is running still waits up to about 21 µs for it to finish. On w1 this kind of delay left prio at 52.5 µs p99 with only 0.51 µs of mean queue wait. Going lower needs a hook that lets a thread with an early deadline interrupt a running long thread.
2. **Hint-blind stealing.** Work stealing takes the oldest half of a busy core's queue without looking at hints. The stealing core does order what it took by this policy. A steal filter that prefers early-deadline threads could still help the 24% of HIGH threads that are stolen.

## Prediction (from the policy agent)

| Workload | Metric | Expected direction | Rough size |
|---|---|---|---|
| w2 | get p99 at 400k (score) | down | 84.5 to about 55–65 µs (−25 to −35%; acceptance needs 76 or less) |
| w2 | get deadline met % at 400k | up | 97.8 to 99.3 or more |
| w2 | query p99 at 400k | slightly up | 103.5 to about 105–112 µs (+2 to +8%; limit 129) |
| w2 | batch p99 at 400k | flat | 144.5 µs within noise (±10%; limit 180) |
| w2 | wait_us_high at 400k | flat to slightly down | 3.64 to about 3.0–3.6 µs |
| w2 | inversion_rate | unchanged | 0 |
| w2 | late at pick at 400k | down | 0.23% to about 0.1% |
| w2 | get p99 at 440k (unscored) | down | 252 to about 100–150 µs; query p99 there rises |
| w1 | short p99 at 400k | flat | 52.5 µs within ±6% (limit 57.75) |
| w1 | long p99 at 400k | flat | 116.5 µs within noise |
| w0 | req p99 and throughput at 350k | flat | 178.5 µs within 6%; throughput within 0.2% |

## Results
Accepted in generation 1 (judge.py, results/gen1/, commit 2f1080c), against
the champion p1 prio, two repeats each at each workload's headline load:

| Workload | Score (prio) | Score (edf_high) | Change | Other kinds |
|---|---|---|---|---|
| w2 | get p99 84.5 µs | 53.0 µs | −37% | query p99 +7.7%, batch p99 +10.7% |
| w1 | short p99 52.5 µs | 52.0 µs | −1% (unchanged, as predicted) | long p99 −1.3% |
| w0 | req p99 178.5 µs | 188.5 µs | +5.6% (inside the 6% band; repeats 181, 196) | throughput equal |

The prediction (55–65 µs on w2) held, slightly better. At 440k, past the
headline load, get p99 is 98 µs against prio's 252. The HIGH queue wait barely
moved (3.12 vs 3.64 µs mean): the gain is in *which* HIGH thread waits.
