# p3: passonce

- id: p3
- config: passonce
- generation: 2
- status: accepted
- builds_on: p1
- changed_from_previous: Inside the class prio chose, the shortest-hinted thread that carries a deadline runs ahead of the longer threads of its class, but only while the oldest of them has never been passed; the core remembers the ready time of the youngest thread it let something pass, so each thread is passed at most once.
- commit: db98ae0

## What it does
Each core runs helper threads first and then the highest class present,
oldest first, exactly as prio. Within that class one pass is allowed: a
thread with a deadline whose hinted run time is shorter than that of every
thread of its class ahead of it runs first. The price to each passed thread
is the passer's run time (6 us on w3), and a thread pays it at most once:
the core keeps the ready time of the youngest thread it has let something
pass, and because the queue is kept in ready-time order (the steal path
merges by ready time), every thread at or before that mark has already been
passed, so a pass is allowed only while the oldest thread of the class is
younger than the mark. No clock is read and there are no constants. A
thread never passes its own kind or a shorter one, so passes cannot
cascade. Without deadlines, with one hinted run time per class, or when the
shorter kind has no deadline, no pass can trigger and every pick is prio's.

## Why (hypothesis)
Gen 2 report, w3 at 299k under prio: a tail suggestion (p99 130, x2.17 of
60) waits ~82 us in the run queue, ~71 of it behind two searches; ~30 us is
outside the queue and no order reaches it. The searches (p99 161, x0.81)
may rise by 8 us by the rule, an unconditional suggestion-first order would
cost them 8-9 (on the line), and one pass costs a search 6-7. Gen 1's
lesson: price a pass by what the passed thread absorbs and bound passes per
thread, not by queue age. Bounding each search to one pass keeps every
search within 6 us of its prio latency, so its p99 can rise by at most 6
and in expectation by 3-4, since a tail search is passed only if a
suggestion arrives while it sits in a never-passed prefix (about half to
two thirds of them). A suggestion is passed by nothing, so its queue wait
never exceeds prio's; at prio's p99 (two searches ahead) it passes both
when it is the first suggestion to arrive since they queued (about 60% of
cases, e^(-30/67)), and otherwise waits only for the stale prefix left by
the previous pass, about one search for a two-deep queue, before passing
the rest. The wait at the new p99 should therefore be about one search
(37-55) instead of two: p99 roughly 85-105. Risk: if stale prefixes are
longer than estimated (persistent three-deep queues), the p99 lands at
105-120 and the improvement is inside prio's 12% spread; the searches are
safe either way.

## Cost
Searches on w3 pay: each absorbs at most one suggestion (6 us) per stay in
a core's queue; a search stolen after being passed can rarely be passed
once more on the thief (26% of hinted threads are stolen, and both cores
must see a suggestion arrive during its stay), and one older than the
thief's mark is treated as already passed (conservative). Index and merge
are untouched: the order inside HIGH is work-conserving, so the HIGH queue
empties at the same moments. Per pick: prio's single scan plus two field
loads and compares per thread of the chosen class (same cache line as
prio_class), one compare of the class head's ready time against the mark
when a candidate exists, and one store on a pass. No clock read, no second
scan; the mark is never written on w0, w1 or w2.

## Expectations (from the policy agent, against prio, one session, 3 repeats)

| Workload, load | Kind | Direction | Rough size | Reason |
|---|---|---|---|---|
| w3, 299k | suggest p99 | down | 130 (119–135) → ~85–105 (−20 to −35%) | At prio's p99 two searches (71 of 82 µs) are ahead. A suggestion is passed by nothing, so it never waits longer than under prio; it passes both searches when fresh (~60%), else waits only the stale prefix (~one search) then passes the rest. All three repeats should sit below prio's lowest (119), since the gap exceeds prio's 12% spread. |
| w3, 299k | suggest p99.9 | same or down | 257 (247–290) → 220–260 | Deeper queues: a blocked suggestion waits at most the passed prefix (≤ what prio made it wait); the ~200 µs outside-the-queue floor is untouched. |
| w3, 299k | suggest p50 / p90 / deadline met | same / slightly down / up | 19 / 51→45–51 / 93%→96–98% | At the p90 the wait is a running search, not the queue; suggestions behind one fresh search now pass it. |
| w3, 299k | search p99 | up, inside the rule | 161 (152–168) → 163–167 (+1 to +4%) | At most one 6 µs pass per search; a tail search is passed with probability ~0.5–0.7, so mean +3–4, max +6 < 8. "Worse" needs a median above 169 and a min above prio's max; neither expected. |
| w3, 299k | search p99.9 / p50 | same or slightly up | 283 (280–320) → 283–290; 49 → 49–50 | +6 at most per search. |
| w3, 299k | index, merge p99 / p99.9 | same | 208 / 235 ± noise (prio's own ranges 182–208, 210–248) | HIGH stays work-conserving; NORMAL/LOW run at the same instants; no clock read, no extra scan. |
| w3, 299k | throughput | same | 298k | Work-conserving reorder. |
| w3, 282k | suggest / search p99 | down / same | 91 → 70–85; 123 → 123–127 | Same mechanism, shallower queues. Lower levels within noise. |
| w2, 202k | read, subreq, health, export, rebuild | same | identical to prio within noise | Decisions are prio's by construction: read and subreq have equal hinted run times (37), health has no deadline, export/rebuild have no deadlines; no candidate ever forms and the mark is never written. The code differs only by two loads and compares per scanned thread, unmeasurable per gen 2 lesson (b). |
| w1, 400k | short, long | same | 52 / 116 | One HIGH kind: no class-mate is strictly shorter; NORMAL has no deadlines. Decisions are prio's. |
| w0 | req p99 at 300k, throughput at 450k | within the rule | p99 ≈ fifo's 71 ± noise; throughput within 1% | No hints: service and deadline are zero, no candidate, index 0 = prio = fifo. |

## Results
Accepted in generation 2 (judge.py accept, results/e1/gen2/), against prio
in one session per workload, 3 repeats, interleaved.

| Workload | Kind | prio p99 (range) | passonce p99 (range) | Verdict |
|---|---|---|---|---|
| w3 (299k) | suggest (×60 µs) | 129 (127–133), ×2.15 | 98 (98–100), ×1.63 | better (−24%); p99.9 better too |
| w3 | search (×200 µs) | 161 (161–165) | 162 (161–167) | same |
| w3 | index / merge | 203 / 233 | 200 / 232 | same / same |
| w2 (202k) | read, subreq, health, export, rebuild | 179 / 179 / 136 / 248 / 249 | 183 / 180 / 145 / 255 / 259 | all same (ranges overlap) |
| w1 (400k) | short / long | 53 / 116 | 53 / 118 | same / same |
| w0 | req p99 at 300k, throughput at 450k | fifo 73 / 373.6k | 73 / 372.0k | ok |

The expectation held: the suggestions' p99 landed in the predicted 85–105
band, every repeat below prio's lowest, and the searches paid nothing
measurable (+1 µs, inside their range). The far tail of the suggestions
improved as well. On w2, w1 and w0 the decisions are prio's by construction
and the numbers agree.
