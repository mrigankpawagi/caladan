# p2: rescue

- id: p2
- config: rescue
- generation: 1
- status: candidate
- builds_on: p1
- changed_from_previous: Inside the class prio chose, a younger thread due earlier than everything of its class ahead of it runs first when the hints say it would otherwise miss its deadline, but only while the oldest thread has waited less than the run time it would be asked to absorb.
- commit: af7c648

## What it does
Each core runs helper threads first and then the highest priority class, oldest
first, exactly as prio. Within that class one pass is allowed: a thread that is
due earlier than every thread of the class ahead of it may run first if the run
times of those threads, its own run time and the 30 µs the hints cannot see add
up to more than the time it has left, and if the oldest thread has waited less
than the passing thread's run time. That last condition means the queue formed
within the last request's run, the pass at most doubles the passed thread's
wait, and no thread is passed twice. A thread never passes one of its own kind,
so rescues cannot cascade, and without deadlines, or with one deadline window
per class, the pick is prio's.

One constant: `POLICY_UNSEEN_US` = 30 µs, the latency the hint clock cannot
see (the packet's wait before its handler thread exists, plus the reply); the
gen 1 report puts it at 12 µs at light load and 45 µs at the tail of w2 at
202k, and 30 sits between. Every other threshold is a quantity of the requests
themselves: the passer's slack, the hinted run times of the threads ahead, and
the head's age against the passer's run time.

## Why (hypothesis)
Gen 1 report, w2 at 202k req/s under prio: a tail sub-request (p99 176, ×1.35)
waits ~94 µs in the queue, ~33 µs of it behind frontend reads due in 800 µs,
and the read p99 (179) may rise by at most ~9 µs by the rule. Reads already at
their tail are older than the sub-request behind them, so an unrationed pass
fills the read p99 band faster than it empties the sub-request's. Reads that
have waited less than one fetch can absorb one more fetch and stay in the body
of their latency (at most ~156 µs even with the tail's unseen time), and they
are the heads of freshly formed queues, where the report says the rescuable
tail sub-requests sit (bursts of three or more fetches within one run). The
sub-request p99 should fall by about one fetch for those, with reads' p99 and
p99.9 unmoved; tail sub-requests in persistent queues are left to prio.

## Cost
Frontend reads and health checks pay: a few hundred to a thousand per second
(1–2% of reads) absorb one fetch (37 µs) in the body of their latency, so the
read p50 and p90 may rise by a few microseconds; the read p99 should not. Per
pick, when some thread carries a deadline and the chosen class is not helper,
one clock read and a second scan of the chosen class reading three fields per
thread (n ≤ 32); no state, no learning. Export and rebuild are untouched.

## Expectations (from the policy agent, against prio)

| Workload, load | Kind | Direction | Rough size | Reason |
|---|---|---|---|---|
| w2, 202k | subreq p99 | down | 176 → ~160–167 (−5 to −9%) | Tail sub-requests that arrive in a freshly formed queue with two fetches ahead run first and save one fetch (37 µs). Risk: if persistent queues hold most of the tail, the gain sits inside the 172–181 range and the policy is rejected for no improvement, not for regression. |
| w2, 202k | subreq p99.9 | same or slightly down | 326 → 300–326 | The far tail is persistent queues and the ~200 µs floor outside the queue. |
| w2, 202k | read p99 / p99.9 | same | 179 / 327 ± noise | A passed read has waited < 37 µs and lands at ≤ ~156 µs; no read is passed twice. |
| w2, 202k | read p50 / p90 | same / slightly up | p90 90 → 90–93 | 1–2% of reads gain 37 µs inside the body. |
| w2, 202k | health, export, rebuild p99 | same | ± noise | Class order is prio's; the pass reorders only inside HIGH. |
| w2, ≤191k | all kinds | same | within noise | Queues are rare; few rescues trigger. |
| w1, 400k | short, long | same | 52 / 117 | One window and one run time in HIGH: condition (a) never holds; long has no deadline. |
| w0 | req p99, throughput | same as fifo within the rule | — | No deadlines: prio's index after prio's scan plus one field read per thread. |

## Results
(filled after evaluation)
