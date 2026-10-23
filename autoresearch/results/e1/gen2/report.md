# Gen 2 report: w3 search leaf, fifo vs prio

Session 20261023-010732, 3 repeats, medians (min–max), µs. Gate: PASS at 299k (`judge.py gate --workload w3`).

## 1. Headline, 299,000 req/s

| Policy | suggest p99 / p99.9 (×60) | search p99 / p99.9 (×200) | index | merge | resp/s |
|---|---|---|---|---|---|
| fifo | 135 (135–138) / 292 (290–292), ×2.25 / ×4.87 | 167 (167–167) / 320 (317–320), ×0.83 / ×1.60 | 148 (146–151) / 303 | 165 (164–170) / 320 | 297647 (297509–297983) |
| prio | 130 (119–135) / 257 (247–290), ×2.17 / ×4.28 | 161 (152–168) / 283 (280–320), ×0.81 / ×1.42 | 208 (182–208) / 428 | 235 (210–248) / 468 | 298064 (297708–298370) |

Suggest deadline-met 92.65% fifo, 93.04% prio (99.84% at 83k).

## 2. Is it real
Suggest −3.7%, search −3.6%, p99.9 −12%: ranges overlap, not real. Real: QWait99 86.4 (86.3–86.9) → 81.9 (76.6–84.6); index +40%, merge +42%. At 282k suggest 96 (95–98) → 91 (90–92), real by 1 µs. Prio's repeats spread 12% (r1 best on every kind, r3 worst, a per-run shift); fifo's 2%.

## 3. Where the time goes (prio, suggest p99 130)
Own run 6; light-load remainder ~12 (p99 18 at 83k); **run-queue wait ~82** (QWait99: the per-request server wait stamped in the reply; its distribution's p99, not the p99 request's wait; fifo 86); **~30 outside the queue** (the running request the packet waits for before a softirq creates the thread, ≤37 for a search), which no order reaches. A search splits the same way: 161 = 37 + 12 + 81 + 31. Both HIGH kinds share one oldest-first queue.

By HIGH work share (13/87%) the 82 is ~11 behind suggestions and **~71 behind searches**; fifo's 86 is 61/9/5/11 (search/suggest/index/merge). Prio should have removed ~16 (background is 18.2% of work) and removed 4.5: fifo's inversion rate is 1.7% of picks (mean depth 1.25, background rarely ahead of HIGH in the ring), 26–28% of hinted threads are stolen (the steal path ignores the order), 63% of softirqs run on another core.

**Floor.** No preemption: a suggestion arriving during a search waits ≤37, and searches hold 63% of core time, so the p99 carries a full one: 18 + 37 ≈ 55–60, ×1.0 of its budget (w1 prio short: 52 behind a 17 µs blocker). In play: 130 → ~60.

**Searches' slack.** 39 to the deadline, but 8.0 by the rule (5% of 161; "worse" also needs min above 168): the rule binds first. p99.9 283 is ×1.42 already. Unconditional suggestion-first: one suggestion per 67 µs per core (14.9k/s), 6–7 each, so a search waiting W absorbs ~0.10 W ≈ 8–9 at W = 81, +5–6%: on the line (author: 7–10%). One pass per search costs 6–7 (+4%).

## 4. Costs
Index/merge mean wait at pick 6.8 → 10.4, 6.7 → 11.7; all answered, 0 dropped. sched_share 11.6% for both (includes spinning); program share 88.3%, 23.7 µs per request (model 24.1; load 0.885 of ~338k). pick_scanned/pick 1.25; sched_pop_next calls the policy only when n > 1 (≤25% of picks).

## 5. Anomalies and checks
0 drops, no failed or saturated level, adherence 99.85–99.87 everywhere (client artifact). The headline is the top level swept (p50 45 vs 44 at 83k), not a knee. p99.9 floor: suggest 124 at 83k with QWait99 0.8 (~0.15% miss 60 at any load). late_at_pick 1.09%/0.88% vs client HIGH misses 3.8%/3.5%: 3.5–4× undercount. rq_overflow ≤31 of 1.7M picks.

Author: suggest/search inside every predicted range for both policies (fifo 135/167, prio 130/161); index 208 above 150–180, merge 235 below 250–400; prio kept 0.95–0.97 of fifo's excess, not 0.85–0.9.

Gen 1 lessons: (a) mean HIGH wait 5.9 vs p99 82 (14×; exponential would be 4.6×): the tail is rare bursts of ≥2 searches on one core; the summary cannot say whether their head is young, but a pass here costs the passed thread 6, not 37, so it need not be confined to fresh queues. (b) prio scans every multi-thread pick at fifo's sched_share within 0.2 points: no support for a 5–9% scan-and-clock cost.

## 6. Hypotheses
1. **Suggestion ahead of searches, each search passed at most once.** Shorter-hinted thread first within the chosen class unless the search ahead was already passed (k->policy_state keeps the ready_tsc of the youngest passed search; only younger ones may be passed; no clock read). Gains: suggestions, up to ~71 of 82. Pays: searches 6–7 once each; index/merge untouched. Risk: tail searches are already passed and the pick is prio's.
2. **Shortest hinted run time first within HIGH**, unrationed (deadline order here). Gains: suggestions to ~60. Pays: searches ~10% of their wait (+5–6%): on the line; prices the trade.
3. **Pass bounded by the passed search's hinted finish** (deadline minus run times ahead minus 30 unseen). Spends deadline slack (39 at p99, 0 at p99.9) the rule does not grant; expect a p99.9 regression.

## 7. Lessons
- Workload: the tight budget (60) equals the non-preemptive floor (18 + 37); set it above the floor so ×1.0 is reachable.
- Policy: price a pass by what the passed thread absorbs (6 here, 37 on w2); bound passes per thread, not queue age; ready_tsc order needs no clock.
- Measurement: prio's 12% repeat spread (fifo 2%) decides verdicts; a candidate's max must beat prio's min in the eval session.

Sources: /Users/mpawagi/caladan/autoresearch/results/e1/gen2/summary.csv and counters.csv; RtStats in results/e1/gen2/raw/w3__{fifo,prio}__hints__hints__r{1,2,3}/rps299000.out; /Users/mpawagi/caladan/runtime/sched.c (policy region 186–329, sched_count_pick 372–397, sched_pop_next 408–430); /Users/mpawagi/caladan/apps/loadgen/src/main.rs (GroupResult.waits: server runqueue wait, 100 ns units). Read-only; nothing modified or run on the nodes.
