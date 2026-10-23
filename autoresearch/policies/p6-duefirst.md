# p6: duefirst

- id: p6
- config: duefirst
- generation: 5
- status: candidate
- builds_on: p3
- changed_from_previous: Where passonce would run the oldest thread of the chosen class, the earliest-due class-mate runs instead if every class-mate ahead of it has the same hinted run time and is due later (unbounded, no state); passonce's shortest-first pass, its once-bound and its mark are unchanged and keep precedence; a thread never passes a class-mate of a different or unknown run time by deadline.
- commit: 749981a

## What it does
Each core runs helper threads first and then the highest class present,
exactly as prio. Inside that class passonce's one pass is kept whole: a
deadline-carrying thread strictly shorter than every class-mate ahead runs
first, each passed thread paying at most once (the per-core ready-time
mark). New: wherever passonce would then run the oldest thread of the
class, a younger class-mate takes that turn if every class-mate ahead of
it has the same hinted run time and is due later; among several, the
earliest due, and among equal deadlines the oldest. Nothing younger can
jump a thread of another cost, so a thread of another cost (w6's health
checks) waits for exactly the work it waited for under prio. No clock is
read, no constant exists, and no state is written by the exchange.
The pick is passonce's wherever equal-cost class-mates share one budget
(w3, w4, w5, w1) or carry no hints (w0).

## Why (hypothesis)
Gen 5 report, w6 at 202k under passonce: a tail sub-request (p99 283,
x2.18 of 130) waits 204 us in the run queue, 72 behind reads due in 800
(their p99 283 = x0.35, 500 unused) and 132 behind other sub-requests; the
read directly ahead of it is itself a tail read, ~12 us behind it in
latency, so any pass that helps the sub-requests' tail charges the reads'
tail 37 against the 14 the rule allows, and the report concludes that no
order inside the class can be accepted on w6 (or w2, allowance 9). This
candidate is therefore evidence, not a likely accept: it implements the
order the deadline hints name among equal-cost threads, whole and
unrationed (a once-bound would leave a late-wave sub-request behind an
already-passed prefix and measure a muddled middle: gain 0-15, cost
20-37), so that one session per workload puts the full trade on record:
what the deadline order buys the sub-requests on w6 and w2 (p99, p99.9,
deadline-met) and what it costs the reads, with every other workload
identical to the champion by construction. It also tests the workload
author's busy-phase argument: sub-requests alone are 79% of busy-phase
capacity, so with reads deferred the core clears them during the wave and
a late-wave sub-request waits only for other sub-requests (150-200).
Which order wins when cost and deadline disagree is decided by cost: an
exchange between unequal costs is not neutral, and on w4 a deadline
override would stop appends (10 us, due 300) passing reads (37, due 130),
costing the appends 20-25% (afford measured 104 -> 125) for no measurable
read gain (165 vs 164), or, if it let the earlier-due longer thread pass,
charge appends 37 per pass to gain reads 10-13: both rejected by the rule.
On w5 cost and deadline agree (2 us due 60 before 21 us due 100), so an
override changes nothing at the first pass; only an unbounded one would
also pass the stale prefix (absorb's lookups 54 -> 51, ranges +0.7
expected). With cost winning, w4 and w5 are passonce's exactly.

## Cost
Who pays: on w6 and w2 the frontend reads, at their tail (+20 to +50% p99
on w6, +20 to +45% on w2) and far tail, because every sub-request arriving
while a read waits takes its turn, so a late-wave read inherits the wave's
backlog and is passed again by the drain's sub-requests; reads still meet
800 us (100%). Health checks: nothing, by construction. Export and
rebuild: nothing, HIGH stays work-conserving. w3, w4, w5, w1, w0: nothing,
the decisions are passonce's (offline: 0 differing picks in 350k). Per
pick: passonce's single scan plus one compare of service_tsc against the
head's and, while equal, one deadline compare (same cache line); no clock,
no second scan, no store on the exchange. Dilution of the measurement: a
health check (5.3% of HIGH arrivals) sits in the prefix of 15-24% of
deep-backlog sub-requests and shields the reads ahead of it until it runs,
so those sub-requests keep part of passonce's wait; expected to pull the
sub-request p99 up by ~10-20 us against the pure deadline order.

## Expectations (from the policy agent, against passonce, one session per workload, 3 repeats)

| Workload, load | Kind | Direction | Rough size | Reason |
|---|---|---|---|---|
| w6, 202k | subreq p99 | down | 283 (280–286) → ~180–240 (−15 to −35%) | At the p99 ~1.9 reads (72 µs) sit directly ahead; the deadline order removes every unshielded one (floor 211 by removal alone), and the sub-request-only queue is shorter than the mixed one because the core serves a sub-request whenever one is queued (79% of busy-phase capacity, 41% in the drain), so up to ~2 more sub-requests have been served ahead of a late-wave arrival (the author's 150–200). Against: health shields in 15–24% of deep backlogs; ~30 outside the queue and the running thread (≤37) untouched. Judge: better needs median < 269 and every repeat < 280: expected. |
| w6, 202k | subreq p99.9 | down | 406 (402–413) → ~270–340 | Deepest waves keep a sub-request-only backlog; p99.9 floor 189–193 at 56k. |
| w6, 202k | subreq p50 / p90 / deadline-met | same / down / up | 67 / 166 / 81.1% → 66–67 / 120–150 / 86–93% | p90 is 3 fetches ahead, ~1 of them a read now deferred; a sub-request meets 130 with ≲50 µs of queue wait: drain-phase ones (31%) now wait for the running thread only, busy-phase ones when ≤1 sub-request is ahead. |
| w6, 202k | read p99 | up, **worse** | 283 (282–286) → ~340–420 (+20 to +50%, 60–140 µs) | No once-bound: a late-wave read inherits the wave's backlog (~110 µs of work) and is then passed by the drain's sub-requests (41% of capacity), stretching its wait ~1/(1−0.41) ≈ 1.7× (QWait ~190–310); the author's argument gives 380–450. The rule allows +14 (median > 297 and min > 286 is "worse"): expected by 45–125 µs over the line, because the read directly ahead of a tail sub-request is a tail read and the deadline order grants every such pass. |
| w6, 202k | read p99.9 / deadline-met | up / same | 407 (399–409) → ~500–650 / 100% | Same mechanism, deeper waves; still under 800. |
| w6, 202k | read p50 / p90 | same / up | 67 / 166 → 67–70 / 180–220 | An early-wave read with nothing queued still runs at once; the p90 read is mid-wave, now passed by 1–2 sub-requests. |
| w6, 202k | health p99 / p99.9 | same | 248 (246–252) / 377 ± noise | By construction: nothing younger jumps a thread of another cost, so a health check waits for the HIGH work older than it, as under passonce. |
| w6, 202k | export, rebuild p99 / p99.9 | same | 426 (413–434) / 634, 436 (427–454) / 635 ± noise | HIGH stays work-conserving; NORMAL/LOW run at the same instants; no clock, no extra scan. Risk: p99.9 of 8–12k samples moved 6–7% between identical policies in gen 4 (p5 on w4), so a noise verdict either way is possible. |
| w6, 202k | throughput | same | 201k | Work-conserving reorder. |
| w6, 191k (swept) | subreq / read p99 | down / up | 247 → ~170–215; 247 → ~280–340 | Same shape, shallower waves (2.5 queued per core). |
| **w6 verdict** | | | **subreq better, read worse → FAIL** | A deadline kind regresses by far more than 5% with ranges apart. |
| w2, 202k | subreq p99 / p99.9 / met | down / down slightly / up | 166 (163–175) → ~135–150 (−10 to −19%); 306 → 270–300; 98.5 → 99.0–99.5% | Gen 1: ~33 of a tail sub-request's 94 µs queue wait is reads ahead; removing them gives ~143 (×1.10), slightly less with the shorter sub-request-only queue. Better needs median < 158 and every repeat < 163: likely. |
| w2, 202k | read p99 / p99.9 | up, **worse** | 166 → ~195–240 (+20 to +45%); 307 → 380–450 | A tail read is passed by every sub-request arriving during its wait (one per 72 µs per core, 37 each: ~0.5 of its wait, compounding to ~2×); the rule allows 9. |
| w2, 202k | health, export, rebuild | same | 134 / 272, 230 / 500, 241 / 473 ± noise | Same construction as on w6; same p99.9 noise caveat. |
| **w2 verdict** | | | **read worse → FAIL** | Regression on an earlier workload. |
| w3 299k, w4 240k, w5 400k, w1 400k | every kind, p99 and p99.9 | same | 90 / 150 / 182 / 210; 156 / 97 / 203 / 239; 54 / 86 / 127; 51 / 109 ± noise | Decisions identical to passonce's by construction: equal-cost class-mates are one kind under one budget (6/60 and 37/200; 37/130 and 10/300; 2/60 and 21/100; 2/60), so the older is always due earlier and the exchange never fires; NORMAL/LOW carry no deadlines; passonce's candidate test, once-bound and mark are the same code. One extra compare per scanned thread, unmeasurable (gen 2 lesson b). Offline: 0 differing picks in 350k. Judge: same, with the p99.9 noise caveat on w4's flush/compact (p5). |
| w0 | req p99 at 300k, throughput at 450k | within the rule | ≈ fifo's 69–73 ± noise; within 1% | No hints: service and deadline zero, cost 0 from the head, no candidate: index 0 = passonce = prio = fifo. |

## Results
(filled after evaluation)
