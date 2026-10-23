# Gen 4 report: w5 lookups and range reads, fifo / prio / passonce

Session 20261023-022546 (all three interleaved, 3 repeats); every comparison below is within it. Medians (min–max), µs. Gate PASS at 400k. Decomposition convention as gen 2–3: p99 = own run + 12 light-load remainder + QWait99 + outside the queue.

## 1. Headline, 400,000 req/s

| Policy | lookup p99 / p99.9 (×60) | range p99 / p99.9 (×100) | long p99 / p99.9 | resp/s |
|---|---|---|---|---|
| fifo | 99 (94–104) / 272 (270–289), ×1.65 / ×4.5 | 119 (116–124) / 289 (277–314), ×1.19 / ×2.9 | 121 (118–124) / 292 (286–309) | 398536 (398226–398718) |
| prio | 70 (68–71) / 176 (176–186), ×1.17 / ×2.9 | 89 (87–89) / 208 (206–210), ×0.89 / ×2.1 | 146 (135–146) / 367 (351–387) | 398781 (398772–398845) |
| passonce | 56 (56–59) / 163 (148–170), ×0.93 / ×2.7 | 86 (86–91) / 210 (206–213), ×0.86 / ×2.1 | 131 (128–149) / 363 (361–398) | 399032 (398604–399176) |

Deadline-met: lookups 97.19 / 98.46 / 99.21%, ranges 98.55 / 99.40 / 99.48%. Deadline capacity (every deadline kind p99 ≤ budget): fifo 350k, prio 380k, passonce 400k.

## 2. Is it real
prio vs fifo: all three kinds, ranges apart (lookups −29%, ranges −25%, long +21%). passonce vs prio: lookups −20% real (56–59 vs 68–71), p99.9 −7% real (≤170 vs ≥176); ranges −3% same; long −10% **same** (128–149 vs 135–146 overlap). At 380k passonce lookups 46 (46–46) vs prio 53 (52–54): real; ranges/long same. Per-run shift: passonce r1 is its worst on every kind (59/91/149; lookup QWait99 21.1 vs 13.1/17.0), prio r3 its best (68/87/135). Spreads: lookups 3–10%, ranges 2–7%, long 5–16%.

## 3. Where the time goes
Lookup: passonce 56 = 2 + 12 + 17 (13.1–21.1) + ~25; prio 70 = 2 + 12 + 30.8 (28–30.8) + 25; fifo 99 = 2 + 12 + 63.5 + 21. Range: 86 = 21 + 12 + 28.2 (27.4–31) + 25; prio 89 = 21 + 12 + 32.3 + 24; fifo 119 = 21 + 12 + 63.2 + 23. Long: 131 = 21 + 12 + 69.4 (67.6–85.9) + 29; prio 146 = 21 + 12 + 84.5 (73.5–86.1) + 28; fifo 121 = 21 + 12 + 63.9 + 24. The ~25 outside the queue is the running 21 µs request the packet waits for before a softirq (63% run on another core) creates the thread, plus reply; no order reaches it; it is 15 at 350k, 27 at 380k.

Split by work share: fifo's 63.5 is 39 behind long, 23 behind ranges, 1.5 behind lookups; prio's 30.8 is ~29 behind range reads, ~2 behind lookups (inversions 0, NORMAL never ahead). passonce removed 14 of the 29. The residual 17 is less than one range read, so a lookup stuck behind an already-passed range read (once-bound stale prefix, 21 + 2) is rarer than 1%; the p99 is partial waits (lookups ahead at 2 each, batch softirq, the rare stale prefix) and its 13–21 spread is the widest in the session.

**Floor.** Where the queue wait vanishes the lookup p99 is 46 at 380k (QWait99 5.2) and 32 at 350k (3.0); at 400k with ~25 outside: about 45–50, below the author's 52–60 (w1's 52 carried a 33 µs outside part, another session). In play: 6–11 µs, all of it the once-bound's residue.

**Rule room.** Lookups: better needs median ≤ 53 and every repeat < 56. Ranges: worse needs median > 90 and min > 91; budget leaves 14. An unconditional lookup-first order charges a tail range read the lookups arriving during its ~28 µs wait: lookups are 2.4% of core time, so +0.7 expected, +2–4 worst, inside 4.3. Ranges cannot gain: their 28 is one range read plus ≤2 of lookups; same kind, same hints, so "below 82" is out of any order's reach.

**Long requests** pay vs fifo: +25 (prio, +21%) / +10 (passonce, +8%, 128 vs 124 apart), p99.9 +25% both; NORMAL mean wait at pick 4.7 → 6.5 → 6.1; all answered. prio's 146 vs passonce's 131 is not established (overlap; HIGH is work-conserving under both, so NORMAL runs at the same instants; counters agree, 6.50 (6.23–6.51) vs 6.08 (6.00–6.48)).

## 4. Costs
sched_share 11.71 / 11.72 / 11.75%; program 7.05 cores, 17.6–17.7 µs/req (author 18.0) → capacity ~454k, load 0.88; scanned per pick 1.23, mean depth 1.23; hinted stolen 28.6 / 17.1 / 15.4%; rq_overflow ≤156 of 2.28M picks; cpu_cores 7.99 (spinning).

## 5. Anomalies and checks
0 drops, no failed or saturated level, adherence 99.85–99.86 everywhere (client artifact). Headline: fifo median 31 vs 30 at 100k, 100% of sent. late_at_pick 0.76 / 0.15 / 0.074% vs client HIGH misses 2.0 / 0.98 / 0.63%: 2.6–8× undercount. p99.9 floor at 100k: lookups 103–117, ranges 154–175 (~0.15% miss at any load). Author: fifo lookups 99 at the top of 90–98, ranges/long 1–3 above 108–118, lookup p99.9 272 above 250–265; prio lookups 70, ranges 89 inside their bands, long 146 above 120–130, HIGH QWait99 31 vs 25 predicted, outside 25 vs 33; the "shortest-first within HIGH" forecast (lookups 52–60, ranges +1–3) is what passonce measured (56, −3); 380k inside every band. Skeptic: the 6–11 µs in play is two repeats' spread of QWait99; a 3 µs win needs all three candidate repeats under 56; the outside-the-queue 25 is inferred, not measured; QWait99 is the wait distribution's p99, not the tail request's wait.

## 6. Hypotheses
1. **Unrationed pass for a cheap passer.** The once-bound is waived when the passer's hinted run time is a small fraction of the passed thread's (2 of 21 here); lookups then pass the stale prefix. Gains lookups (wait 17 → 3–5, p99 toward 45–50). Pays ranges +0.7 expected, +2–4 worst. w1–w4 decisions unchanged by construction if the fraction sits below w3's 6/37 and w4's 10/37: a fixed ratio, which loop 1 warns invites a workload built just outside it.
2. **Absorbed-time bound.** A thread is passed while the run times it has absorbed total less than a fraction of its own. Same gain and price on w5, but any fraction admitting two lookups (≥0.2 of 21) admits a second suggestion on w3 (expected +7 of 8 allowed) and must still admit one append on w4 (0.27): on the line on both.
3. **Earliest deadline within HIGH.** On w5 ≈ unconditional (a lookup passes any range read readied <40 µs before it); on w3 unconditional (searches +8–9, at the line); on w4 appends (300) never pass reads (130) and lose 25 µs: rejected by the rule. Prices the deadline-order trade only.

Honest view: no in-region policy can move the range reads; the lookups can clear the line on w5, but only a rule that stays off on w3 and w4 by construction can be accepted. The generation's candidate is judged on w5 lookups alone, with w3 and w4 as the whole risk.

## 7. Lessons
- Workload: with the passer at 2.4% of core time the passed kind's rule-slack (4.3) exceeds the unconditional price (0.7); the w3/w4 conflict did not appear. Raise the passer's share or cut its budget next.
- Policy: the once-bound's residue is the stale prefix: 6–11 µs of lookup p99 here, priced at 0.7 expected; the deciding quantity is the passer's cost relative to the passed thread's.
- Measurement: lookups' QWait99 spreads 13–21 and one repeat shifted every kind; take the floor from the level where the queue wait vanishes (380k: 46), not from another session.

Sources: /Users/mpawagi/caladan/autoresearch/results/e1/gen4/summary.csv and counters.csv; RtStats in /Users/mpawagi/caladan/autoresearch/results/e1/gen4/raw/w5__{fifo,prio,passonce}__hints__hints__r{1,2,3}/rps400000.out; /Users/mpawagi/caladan/runtime/sched.c (policy region 186–522); /Users/mpawagi/caladan/autoresearch/workloads/w5-lookups-ranges-two-budgets.json; /Users/mpawagi/caladan/autoresearch/policies/p3-passonce.md, p4-afford.md. Read-only; nothing modified or run on the nodes.
