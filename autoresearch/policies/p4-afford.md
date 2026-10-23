# p4: afford

- id: p4
- config: afford
- generation: 3
- status: rejected
- builds_on: p3
- changed_from_previous: passonce's pass fires only if every thread it would pass that carries a deadline would still, by the hints, finish with the unseen time to spare after absorbing the passer's run time (deadline − now − hinted work of its class through it − passer's run time − 30 µs unseen ≥ 0); the once-bound and the mark are unchanged.
- commit: 8b8ed04

## What it does
Each core runs helper threads first and then the highest class present,
oldest first, exactly as prio. Within that class passonce's one pass is
allowed: a thread with a deadline whose hinted run time is shorter than
that of every class-mate ahead of it runs first, each passed thread paying
the passer's run time at most once (the per-core ready-time mark). New: the
pass is priced against each passed thread's remaining slack. For every
class-mate it would pass that carries a deadline, the deadline minus the
time already waited (the hint clock), minus the hinted run time of the
class ahead of it and its own, minus the passer's run time, minus the 30 µs
the hint clock does not see must not have run out; otherwise the pick is
prio's. Threads without a deadline have no slack to keep and never refuse.
The clock is read once, and only when a candidate exists and the once-bound
permits the pass.

One constant: POLICY_UNSEEN_US = 30 µs (reused from p2), the latency the
hint clock does not see: the clock starts when the handler thread gets its
hints, after the packet has waited for the request the core was running,
and stops before the reply. The gen 3 report measures the part outside the
queue at ~31 µs at the tail of w4 (156 = 37 + 12 + 75.5 + ~31), ~31 on w3
and ~33 on w2; with the 12 µs light-load floor the tail's unseen total is
42–45, at light load 12. 30 is the report's figure and sits between; a
thread within ~13 µs of the line can be mispriced by at most that much.
Every other quantity is the requests' own: deadlines, waits, hinted run
times.

## Why (hypothesis)
Gen 3 report, w4 at 240k: passonce's pass is priced right (10 µs, once) and
is still unaffordable, because the passed kind (reads, ×1.20 of 130, no
slack by budget, 8 by the rule) pays 7 µs at its p99 so that the passing
kind (appends, ×0.34 of 300, 170–200 to spare) gains 25. The report's
finding is that the pass must be priced against the passed thread's
remaining slack, which separates w3's searches (39 µs to spare at the tail;
behind one search they keep 90 − waited) from w4's reads (a read behind
another read keeps 16 − waited; a tail read has waited 75). With that
price, a tail read is never passed (reads give back their 7 µs: ≈ prio's
156), appends keep the body gain (p90 56 → 47) from passing one fresh read
and give back their tail gain (p99 back toward prio's 127); on w3 passes of
one to three searches survive, four-deep queues refuse, so the suggestions'
p99 gain holds and their p99.9 is at risk. The expected verdict on w4 is a
rejection as the rules stand: −4.3% on the reads is under the 5% line and
the appends' rise counts as a regression against passonce's 102. The rule
is measured because that result is the evidence about the rule itself: it
is the principled pricing, and the 5% rule has locked in 25 µs on a kind at
×0.34 bought with 7 from a kind at ×1.20.

## Cost
Who pays: on w4 the appends, at their tail (+13 to +23% p99, back toward
prio's 127) and far tail; on w3 nothing expected at p99, the suggestions'
p99.9 (queues four searches deep) possibly. Per pick: passonce's single
scan plus one add and one subtract-and-min per thread of the chosen class
(same cache line as prio_class), and one rdtsc only when a candidate exists
and the once-bound allows the pass; no second scan, no state beyond
passonce's mark. On w0, w1 and w2 no candidate ever forms, so no clock is
read and the decisions are passonce's (prio's) by construction.

## Expectations (from the policy agent, against passonce, one session, 3 repeats)

| Workload, load | Kind | Direction | Rough size | Reason |
|---|---|---|---|---|
| w4, 240k | read p99 | down, under the line | 163 (162–163) → 156–160 (−2 to −4%) | Tail reads have waited > 53 at the head or > 16 behind another read: never passed. Not all 7 µs return: some tail reads were passed while young (second of two reads, within 16 µs). Judge: same (better needs < 155 and max < 162). |
| w4, 240k | read p99.9 | down slightly | 288 → 278–286 | Same mechanism; prio's 278 is the floor. same. |
| w4, 240k | read p50 / p90 | same / down slightly | 50 / 86 → 49–50 / 83–85 | Body reads behind one fresh read are still passed once. |
| w4, 240k | append p99 | up | 102 (101–102) → 115–125 (+13 to +23%) | The tail append sits behind two reads (second must have waited < 16) or one read in a persistent queue (> 53): mostly refused; prio's 127 is the ceiling. Judge: worse (median > 107 and min > 102 both expected). |
| w4, 240k | append p99.9 | up | 212 → 230–250 | Deeper queues refuse more; prio's 249 is the ceiling. Likely worse. |
| w4, 240k | append p50 / p90 | same / up slightly | 22 / 47 → 22–23 / 48–52 | The body case is one fresh read ahead (waited < 53), still passed; prio's p90 is 56. |
| w4, 240k | flush, compact p99 / p99.9 | same | 224 / 448, 255 / 517 ± noise (passonce ranges 209–225, 248–257) | Class order untouched; HIGH stays work-conserving; one clock read only on candidate picks. |
| w4, 240k | throughput, deadline met | same / reads up, appends down | 239k; reads 97.7 → ~98.0%, appends 99.98 → ~99.97% | Work-conserving reorder. |
| w4, 226k (swept, not judged) | read / append p99 | down / up | 128 → 123–126; 78 → 85–95 | Same shape, shallower queues (prio 122–124 / 95). |
| **w4 verdict** | | | **FAIL (1) → REJECT** | No deadline kind better (reads −4% at most) and appends worse; the overall verdict is REJECT whatever w1–w3 show. |
| w3, 299k | suggest p99 | same, small drift up possible | 98 (98–100) → 98–104 | At the p99 two searches are ahead; the second keeps 90 − waited − 6q, nearly always positive (searches' QWait99 is 82 at pick, less at the suggestion's arrival); three deep keeps 53 − waited, mostly. Worse would need > 103 and min > 100: unlikely. |
| w3, 299k | suggest p99.9 | up | 228 (226–248) → 230–255 | Four-deep queues refuse (16 − waited), three-deep refuse part of the time: the far tail waits the whole prefix. The main risk of a FAIL (2): worse needs median > 239 and all three repeats above 248. |
| w3, 299k | suggest p50 / p90 | same | 18 / 42 → 18 / 42–43 | Body passes (one search ahead) keep 127 − waited. |
| w3, 299k | search p99 | same or down slightly | 162 (161–167) → 159–163 | Searches that cannot afford the 6 µs are the ones no longer charged. |
| w3, 299k | search p99.9 | same or down | 294 (292–318) → 285–296 | Deep-queue searches, already past their budget, are no longer charged. |
| w3, 299k | index, merge p99 / p99.9 | same | 200 / 424, 232 / 511 ± noise | NORMAL/LOW run at the same instants. |
| w3, 299k | throughput | same | 298k | Work-conserving. |
| w2, 202k | read, subreq, health, export, rebuild | same | 183 / 180 / 145 / 255 / 259 ± noise | Decisions identical to passonce's (= prio's): read and subreq both hint 37 µs so no class-mate is strictly shorter, health carries no deadline, export/rebuild are NORMAL/LOW without deadlines; the candidate test is passonce's code unchanged and the affordability code sits after the `!cand` return, so it never runs and no clock is read. The only difference per scanned thread is an add and a min, unmeasurable (gen 2 lesson b). |
| w1, 400k | short, long | same | 53 / 118 | One HIGH kind, NORMAL without deadlines: no candidate ever; same argument. |
| w0 | req p99 at 300k, throughput at 450k | within the rule | p99 ≈ fifo's 71–73 ± noise; throughput within 1% (372–374k) | No hints: no candidate, index 0 = passonce = prio = fifo. |

## Results
Rejected in generation 3 (judge.py accept, results/e1/gen3/), against
passonce in one session per workload, 3 repeats, interleaved.

| Workload | Kind | passonce p99 (range) | afford p99 (range) | Verdict |
|---|---|---|---|---|
| w4 (240k) | read (×130 µs) | 164 (158–173), ×1.26 | 165 (162–165), ×1.27 | same |
| w4 | append (×300 µs) | 104 (100–110), ×0.35 | 125 (124–127), ×0.42 | worse (+20%); p99.9 worse |
| w4 | flush / compact | 213 / 259 | 229 / 266 | same / same |
| w3 (299k) | suggest (×60 µs) | 104 (99–104) | 99 (96–105) | same; **p99.9 worse** |
| w3 | search, index, merge | 167 / 213 / 243 | 161 / 198 / 227 | same |
| w2, w1 | every kind | | | same |
| w0 | req p99 at 300k, throughput at 450k | fifo 72 / 373.8k | 73 / 371.7k | ok |

Two expectations failed. The reads on w4 did not recover at all (165 vs
164 in one session): the 7 µs that the gen 3 report attributed to
passonce's pass was drift between that report's two sessions, not the
pass. And on w3 the suggestions' far tail got worse, because the
slack-priced pass refuses passes in queues three or four searches deep,
exactly where the far tail sits. Pricing a pass against the passed
thread's hinted slack therefore gave nothing back and took something
away; passonce's once-bound alone was the better rule.
