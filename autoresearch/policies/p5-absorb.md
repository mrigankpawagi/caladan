# p5: absorb

- id: p5
- config: absorb
- generation: 4
- status: rejected
- builds_on: p3
- changed_from_previous: passonce's first pass per thread is kept unconditional; a prefix whose head has already been passed may be passed again while the passers' run times absorbed in that episode, the new one included, stay within 25% of the least hinted run time among the passed threads; policy_state[1] carries the absorbed total, the mark in policy_state[0] is passonce's.
- commit: 996f3e6

## What it does
Each core runs helper threads first and then the highest class present,
oldest first, exactly as prio. Within that class passonce's pass is allowed:
a thread with a deadline whose hinted run time is shorter than that of every
class-mate ahead of it runs first, and each passed thread pays the passer's
run time. passonce let a thread pay at most once. Here a thread absorbs one
pass unconditionally and further passes only while everything it has
absorbed during its stay at the head of its class, the new pass included,
stays within a quarter of its own hinted run time; a thread without a hinted
run time has no quarter and is passed once. The core keeps passonce's mark
(the ready time of the youngest thread passed) and one more word, the run
time absorbed by the passed prefix since a pass last opened on a never-passed
head; every thread of the prefix is charged the whole of it, which can only
refuse more than the rule, never admit more. The quarter is measured
against the shortest hinted run time among the threads the candidate would
pass. No clock is read.

One constant: POLICY_ABSORB_PCT = 25, in percent of the passed thread's
hinted run time. The cap is a share of the passed thread's own cost so that
it scales with that thread and not with the passers' share of the traffic
(what an unconditional shorter-first order charges: lookups are 2.4% of
core time on w5, suggestions 11% on w3, appends 12% on w4). 25 is the
middle of the band in which the cap changes nothing where the once-bound was
measured as right and admits a second pass where its refusal was measured as
the whole residue: two suggestions cost a search 12 of 37 (32%, w3) and two
appends cost a read 20 of 37 (54%, w4), both refused; two lookups cost a
range read 4 of 21 (19%, w5), admitted. 25 sits a factor 1.3 from either
edge of 19-32. This is a fixed ratio of the kind loop 1 warns about: a
passer at an eighth of the thread it passes or less gets a second pass, one
at a sixth or more does not, and a workload built with a cheap passer that
is a large share of the traffic would charge the passed kind up to a quarter
of its run time per episode (bounded, unlike a waiver, but near the 5% line
of a p99 that is about four run times).

## Why (hypothesis)
Gen 4 report, w5 at 400k under passonce: the lookups' p99 (56, x0.93 of
60) carries 13-21 us of run-queue wait whose only reorderable part is the
once-bound's residue: a lookup arriving behind a range read that an earlier
lookup already passed waits the full 21 us to save that range read 2 us.
The floor where the queue wait vanishes is 46 (380k), about 45-50 at 400k.
Range reads (86, x0.86) cannot be moved by any order and may rise 4.3 us by
the rule; an unconditional lookup-first order would cost them +0.7 expected
and +2-4 worst. The report's honest view is that only a rule off on w3 and
w4 by construction can be accepted. The rule here is identical to passonce
on w3 and w4 with their hints (see Cost) and on w5 admits the second lookup
of an episode: refusals move from the second lookup of an episode to the
third. With one lookup per 100 us per core and episodes of 21-60 us (one
or two passed range reads draining, extended once by the second pass),
that is a 4-7x rarer event; under passonce refusals sit at the p99 boundary
(QWait99 13-21, less than one range read), so after the change the p99 is
the bulk's, as at 380k. Expected lookup p99 47-52, every repeat below
passonce's lowest. A range read absorbs at most two lookups (4 us) per
episode instead of one; at its p99 it waits ~28 us and sees 0.28 lookups on
average, so two arrive with probability ~3%: +0.1 expected, +2 worst.

## Cost
Who pays: on w5 the range reads, +0.1 us expected and at most +2 at p99
(two lookups instead of one), +0.7 expected and +2 worst at p99.9 (deeper
queues, ~130 us waits, P(two lookups) ~0.37). Long requests: nothing, HIGH
stays work-conserving. w3 and w4: nothing, the decisions are passonce's. On
w3 the quarter of the prefix's least run time is 9.25 us (a search) or 1.5
(a suggestion in the prefix) and the absorbed total after any first pass is
at least 6, so 6 + 6 = 12 > 9.25 refuses; it would admit only with
suggestions hinted at 4.6 us or less or searches at 48 or more. On w4 the
quarter is 9.25 and a second append is 20: never, until reads are hinted at
80 us or more. The mark update is passonce's in both cases (a never-passed
head writes the passed thread's ready time), so the state evolves
identically and the stolen-thread caveat is passonce's. w2, w1, w0: no
candidate ever forms (reads and subreqs both hint 37; health has no
deadline; one HIGH kind on w1; no hints on w0), so the code after the
candidate test never runs and neither word is written. Per pick: passonce's
single scan plus one MIN per thread of the chosen class (same cache line as
prio_class); where passonce refuses, one multiply and compare; one extra
store on a pass; no clock read, no second scan. Gen 2 lesson (b): such
costs were never measurable (sched_share identical within 0.2 points).

## Expectations (from the policy agent, against passonce, one session per workload, 3 repeats)

| Workload, load | Kind | Direction | Rough size | Reason |
|---|---|---|---|---|
| w5, 400k | lookup p99 | down | 56 (56–59) → 47–52 (−8 to −16%) | Refusals move from the 2nd to the 3rd lookup of an episode, 4–7× rarer, below the p99; the p99 becomes the bulk's wait as at 380k (46 with QWait99 5.2) plus ~25 outside. Judge: better needs median ≤ 53 and every repeat below passonce's lowest (56 in gen 4). Risk: lands at 52–55 if 2-lookup episodes are longer than estimated or passonce's session value comes in low (its r2 had QWait99 13 and still 56); the "outside" 25 is inferred, not measured. |
| w5, 400k | lookup p99.9 | same or slightly down | 163 (148–170) → 150–165 | The far tail is the ~150 µs outside-the-queue floor (103–117 at 100k), not the queue. |
| w5, 400k | lookup p50 / p90 / deadline met | same / same or down / up | 13 / 26 / 99.2% → 13 / 24–26 / 99.3–99.5% | Body lookups already pass; the 2nd-of-episode ones join them. |
| w5, 400k | range p99 | same | 86 (86–91) → 86–88 | At most two lookups per episode (4 µs) instead of one; two arrive during a 28 µs wait with P ≈ 0.03. Worse needs median > 90.3 and min > 91: out of reach. |
| w5, 400k | range p99.9 | same | 210 (206–213) → 210–213 | Deeper queues: +0.7 expected, +2 worst; worse needs > 220 and min > 213. |
| w5, 400k | range p50 / p90 | same | 32 / 49 | Unchanged shapes. |
| w5, 400k | long p99 / p99.9 | same | 131 (128–149) / 363 ± noise | HIGH stays work-conserving, NORMAL runs at the same instants; no clock read. Only risk: this kind's own 16% spread; worse needs median > 137.6 and min > 149 from noise alone. |
| w5, 400k | throughput | same | 399k | Work-conserving reorder. |
| w5, 380k and below (swept, not judged) | lookup / range / long | same | 46 / 73 / 97 | QWait99 is already 5.2: no stale prefix at the p99, nothing in play. |
| w4, 240k | read, append, flush, compact (p99, p99.9) | same | 164 / 104 / 213 / 259 ± noise (passonce's eval-session ranges 158–173, 100–110) | Decisions identical: a second append costs a read 20 of 37 = 54% > 25%, so the quarter clause never admits; the first pass is passonce's. Code differs by one MIN per scanned HIGH thread and one compare where passonce refuses. Judge: same on every kind. |
| w3, 299k | suggest, search, index, merge (p99, p99.9) | same | 104 / 167 / 213 / 243 ± noise | Decisions identical: a second suggestion costs a search 12 of 37 = 32% > 25%; an episode's absorbed total is ≥ 6 after any first pass. Judge: same. (afford's p99.9 failure came from refusing deep queues; nothing is refused here that passonce admits.) |
| w2, 202k | read, subreq, health, export, rebuild | same | 177 / 179 / 143 / 250 / 256 ± noise | No candidate ever forms (37 vs 37; health has no deadline; NORMAL/LOW without deadlines): the code after `!cand` never runs, no state written. Judge: same. |
| w1, 400k | short, long | same | 52 / 115 | One HIGH kind: nothing strictly shorter; NORMAL has no deadlines. No candidate. |
| w0 | req p99 at 300k, throughput at 450k | within the rule | p99 ≈ fifo's 71–73 ± noise; throughput within 1% | No hints: service and deadline zero, no candidate, index 0 = passonce = prio = fifo. |

## Results
Rejected in generation 4 (judge.py accept, results/e1/gen4/), against
passonce in one session per workload, 3 repeats, interleaved.

| Workload | Kind | passonce p99 (range) | absorb p99 (range) | Verdict |
|---|---|---|---|---|
| w5 (400k) | lookup (×60 µs) | 54 (54–55), ×0.90 | 51 (51–52), ×0.85 | **better** (−5.6%, ranges apart) |
| w5 | range (×100 µs) | 86 (83–86) | 83 (83–85) | same |
| w5 | long | 127 (121–129) | 122 (118–125) | same |
| w4 (240k) | read / append | 156 / 97 | 152 / 95 | same / same |
| w4 | flush p99 / p99.9 | 203 / 401 (390–412) | 206 / 430 (423–454) | same / **p99.9 worse** (+7%) |
| w4 | compact p99 / p99.9 | 239 / 481 (472–482) | 235 / 508 (504–515) | same / **p99.9 worse** (+6%) |
| w3, w2, w1 | every kind | | | same |
| w0 | req p99 at 300k, throughput at 450k | fifo 69 / 377.0k | 69 / 374.5k | ok |

The expectation on w5 held: the lookups cleared the line, the range reads
and the long requests did not move. The rejection comes from the p99.9 of
w4's two background kinds. On w4 the two policies make identical decisions
by arithmetic (a second append would cost a read 54% of its run time
against the 25% cap, and the first pass and the mark update are
passonce's), so those two p99.9 values, the 32nd and 97th slowest requests
of each run, moved for a reason other than the policy. The rule stands as
written; the judging of p99.9 on kinds without a deadline is on the list
for the epoch review.
