# Gen 3 report: w4 storage node, fifo / prio / passonce

S1 = session 20261023-013951 (fifo, prio interleaved); S2 = 20261023-022241 (passonce alone, 43 min later). 3 repeats, medians (min–max), µs. Gate PASS at 240k. prio↔passonce comparisons are cross-session.

## 1. Headline, 240,000 req/s

| Policy | read p99 / p99.9 (×130) | append p99 / p99.9 (×300) | flush | compact | resp/s |
|---|---|---|---|---|---|
| fifo S1 | 188 (182–189) / 360 (316–373), ×1.45 / ×2.77 | 159 (156–160) / 331 (300–342), ×0.53 / ×1.10 | 189 (181–189) / 357 | 201 (195–202) / 369 | 239325 (238823–239355) |
| prio S1 | 156 (152–156) / 278 (272–284), ×1.20 / ×2.14 | 127 (126–127) / 249 (249–249), ×0.42 / ×0.83 | 213 (207–216) / 429 | 248 (246–255) / 509 | 239028 (238562–239071) |
| passonce S2 | 163 (162–163) / 288 (283–292), ×1.25 / ×2.22 | 102 (101–102) / 212 (212–219), ×0.34 / ×0.71 | 224 (209–225) / 448 | 255 (248–257) / 517 | 238943 (238898–239370) |

Read deadline-met 97.04 / 98.10 / 97.68% (ranges apart); append 99.85 / 99.97 / 99.98.

## 2. Is it real
S1, prio vs fifo: real on every kind (read −17%, append −20%, flush +13%, compact +23%; p99.9 likewise). passonce vs prio (cross-session): append −20%, real by any spread; read +4.5% with ranges apart (162–163 vs 152–156) but under the 5% line; p99.9 +3.6%; flush +5% and compact +3% overlap. Spreads: read 2.6% prio, 0.6% passonce, 3.8% fifo; appends 1%; flush 4–8%; nothing like w3's 12%. At 226k the same shape: read 122 (122–124) → 128 (125–130), ×0.94 → ×0.98; append 95 → 78.

## 3. Where the time goes
QWait99 (the wait distribution's p99) is identical for both HIGH kinds under oldest-first: fifo 105.0 / 102.3, prio 75.5 / 75.3 (read / append). The two tails are the same queues; only run times set the exchange rate.

Read p99 under prio: 156 = 37 own + 12 light-load (p99 49 at 67k) + 75.5 run-queue + ~31 outside the queue (the running request the packet waits for, up to 49 for a compaction step; 63% of softirqs run on another core). fifo 188 = 37+12+105+34; passonce 163 = 37+12+83.7+30. The ~30 no order reaches.

prio's 75.5 by HIGH work share (reads 83%, appends 17%): ~62 behind other reads, ~13 behind appends (1.3 × 10 µs). fifo's 105 splits 60/13/6/26 read/append/flush/compact; prio removed 29.5 = 28% (background is 31% of the work; on w3 it removed a quarter of that share). passonce adds ~8: the once-bound pass costs a read at most one append (10); measured +7 at p99, +10 at p99.9, so ~70% of tail reads are passed once. Appends' wait 75.3 → 47.6: one read plus a stale prefix instead of two.

Slack. Reads: none by budget (×1.20 / ×1.25); by the rule 7.8 (prio) or 8.2 (passonce) at p99, 14 at p99.9; passonce spent 7 of it. Appends: 173–198 by budget at p99, 51–88 at p99.9; by the rule 6.4 (prio) / 5.1 (passonce). A read passing one append saves 10 and charges that append 37, seven times the rule's allowance. The reads' reorderable part is ≤ ~20 (13 appends ahead + 7 charge): the floor by ordering is ~143 (×1.10); no in-region order meets the budget at 240k.

Gen 1–2 lesson applied: passonce prices the pass right (10, once) and it is still unaffordable, because the passed kind has zero budget slack and the passer has 170 it cannot use. When the shorter kind has the looser budget, a per-thread bound is not enough: the pass must be priced against the passed thread's remaining slack (deadline − waited − class work ahead − own run − passer − unseen), which is what distinguishes w3's searches (39 at p99) from w4's reads (none).

## 4. Costs
Flush p99 189 → 213 → 224, compact 201 → 248 → 255 (p99.9 357/429/448, 369/509/517); mean wait at pick normal 7.6 → 10.2 → 10.6, low 7.7 → 11.9 → 12.6. All answered, 0 dropped. sched_share 11.3 / 11.5 / 11.2%; program 29.5 µs/req for all three (author's model 30.0): capacity ~271k, load 0.885. 1.23 threads scanned per pick, mean depth 1.22.

## 5. Anomalies and checks
0 drops, no failed or saturated level, adherence 99.84–99.86 everywhere (client artifact). Headline: fifo answers 100% of sent, median 47 vs 45 at 67k. Inversions fifo 2.06% of picks, prio/passonce 0. Hinted threads stolen 27/25/24% (steal path ignores order). rq_overflow ≤7. Late-at-pick 0.38/0.15/0.19% of deadline picks vs client HIGH misses 1.74/1.08/1.31%: 5–7× undercount, same direction. p99.9 floor: read 195 at 67k. Skeptic: passonce's +7 on reads is cross-session, 0.5 points under the rule, and was never judged against prio on w4 in one session; deadline-met says +450 read misses/s bought −8 append misses/s.

Author: fifo inside every band (188/159/189/201 vs 175–195/150–170/175–195/190–210; 226k likewise). prio: read 156 at the bottom of 155–175; append 127 below 135–150; flush 213 and compact 248 below 230–290 and 280–450 (less harm, as on w2). The unconditional shortest-first forecast (appends 60–70, reads +5–10%) was softened by the once-bound: 102 and +4.5%.

## 6. Hypotheses
Rule first: against passonce's 102 the appends may rise 5; all three below hand them 10–25 back, and the reads' recovery (−7, −4.3%) is under the 5% line. None is acceptable on w4 as the rule stands; ranked by what they establish.
1. **Affordable pass.** passonce's pass fires only if every thread it would pass keeps its hinted slack (deadline − waited − class work ahead − own − passer − unseen). w4: a read behind another read has 16 − waited, so tail reads are never passed; reads −7, appends keep their body gain (p90 56 → 47), p99 back toward 127. w3: a search behind one search keeps 90 − waited, so the p99 gain holds; p99.9 at risk. Clock and one constant only when a candidate exists.
2. **Need-gated pass.** Fires only if the passer would otherwise miss (waited + work ahead + own + unseen > deadline). w3 always (73 > 60 behind one search), w4 never (114 < 300): w3 = passonce, w4 = prio. Simplest; passer-side only, so a tight long kind would still be charged.
3. **Charge-back.** A read past its slack passes appends ahead of it: reads −10 to −13 (~150), appends +37 per pass at their tail. Rejected by rule; prices the other direction.

## 7. Lessons
- Workload: with cost and budget aligned, the tight kind is 83% of its own queue and ordering can move ≤ 13% of its wait; a cell where the cheap loose kind carries more of the work gives a policy something to trade.
- Policy: the pass needs the passed thread's remaining slack, not only the passer's run time and a once-bound; w4 is the counterexample.
- Measurement: the 5% rule locked in 25 µs on a kind at ×0.34, bought with 7 µs from a kind at ×1.20; only the leaderboard's ×deadline column shows it. Gate the champion on a new workload with prio in one session before a candidate is judged against it.

Sources: /Users/mpawagi/caladan/autoresearch/results/e1/gen3/summary.csv and counters.csv; RtStats in /Users/mpawagi/caladan/autoresearch/results/e1/gen3/raw/w4__{fifo,prio,passonce}__hints__hints__r{1,2,3}/rps{226000,240000}.out; /Users/mpawagi/caladan/runtime/sched.c (policy region 186–401, sched_count_pick 444–469); /Users/mpawagi/caladan/autoresearch/workloads/w4-storage-node-reads-vs-appends.json; /Users/mpawagi/caladan/autoresearch/policies/p3-passonce.md. Read-only; nothing modified or run on the nodes. Length by `wc -w` is about 1150 with the table and ranges, the same density as the gen 1 and gen 2 reports (790 and 915).
