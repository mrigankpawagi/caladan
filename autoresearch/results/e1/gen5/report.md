# Gen 5 report: w6 fan-out leaf in 1 ms waves, fifo / prio / passonce

Session 20261023-024717 (all three interleaved, 3 repeats); every comparison is within it. Medians (min–max), µs. Gate PASS at 202k. Decomposition as gen 2–4: p99 = own run + 12 light-load (p99 49 at 56k) + QWait99 + outside the queue.

## 1. Headline, 202,000 req/s

| Policy | read p99 / p99.9 (×800) | subreq p99 / p99.9 (×130) | health | export | rebuild | resp/s |
|---|---|---|---|---|---|---|
| fifo | 296 (285–300) / 429 (390–433), ×0.37 / ×0.54 | 296 (287–299) / 425 (395–433), ×2.28 / ×3.27 | 254 (252–262) / 384 | 293 (290–297) / 419 | 299 (287–302) / 429 | 200937 (200673–201069) |
| prio | 280 (273–300) / 395 (387–462), ×0.35 / ×0.49 | 279 (275–302) / 396 (393–471), ×2.15 / ×3.05 | 245 (240–264) / 370 | 419 (407–457) / 600 | 433 (427–475) / 609 | 201107 (201094–201247) |
| passonce | 283 (282–286) / 407 (399–409), ×0.35 / ×0.51 | 283 (280–286) / 406 (402–413), ×2.18 / ×3.12 | 248 (246–252) / 377 | 426 (413–434) / 634 | 436 (427–454) / 635 | 201099 (201002–201244) |

Subreq deadline-met 79.9 / 81.5 / 81.1%; reads 100%.

## 2. Is it real
passonce vs fifo: subreq −4.4% with ranges apart by 1 µs (286 vs 287), under the 5% line; reads −4.4%, overlap. prio vs fifo: −5.7% but prio r1 (302/300, export 457, p99.9 462–471) overlaps fifo: a per-run shift; prio's spread 10%, fifo 4%, passonce 2%. passonce = prio on every kind (inversions 0 for both; decisions identical by construction). Real: export +43/+45%, rebuild +45/+46% p99, p99.9 +42–51%. At 191k nothing among HIGH (fifo 253 (247–265), prio 240 (236–249), passonce 247 (235–247)).

## 3. Where the time goes (passonce, subreq p99 283)
283 = 37 own + 12 + **QWait99 204 (197–207)** + ~30 outside. fifo 296 = 37+12+218 (209–220)+29; prio 279 = 37+12+194 (191–221)+36. w2 without waves (gen 1, prio): 176 = 37+12+94+33. The waves added ~110 of run-queue wait and 0–3 outside: the outside part did **not** grow (mean softirq wait rose 1.2 → 9.4, the tail's outside part did not).

Split of 204 by HIGH work share (reads 35%, subreq 65%, health 0.2%): **~72 behind reads** (1.9 fetches), ~132 behind other sub-requests (3.6), <1 health; the running background step costs 14–24 (fifo 218 → 194–204, the 10.5% background share). 5.5 fetches at the p99 (author: 4–5, reads 50–65).

Depth: mean ring depth at pick 1.67 (1.64–1.69) vs 1.20 on w2 (1.44 at 191k, 1.30 at 180k). Little: mean HIGH wait 27.0 (26.6–27.6) × 22.6k HIGH/s per core = **0.61 queued HIGH per core** on average (0.16 on w2). The author's "3–5 deep for 640 of 1000 µs" is the wave's tail, not the typical state: p50 +22 over light load (0.6 fetch), p90 166 (3 fetches), p99 5.5. Hinted threads stolen 34% (26% on w2).

Sub-request-first: moves ≤72 directly (floor 211, ×1.62), more if the sub-request-only queue drains as the author argues (150–200). What it charges: the read directly ahead of a p99 sub-request arrived ~25 µs earlier (busy-phase 40k/s per core) and finishes one fetch earlier, so its latency is the sub-request's −12: a ~p98.5 read. One pass (+37) lands it at ~308, above the read p99 (283); the rule allows **+14** (and every repeat above 286). Read tail 605/s, subreq tail 1,106/s: the read band fills faster than the subreq band empties (gen 1). Reads that end below the tail after +37 sit below ~246 (p96): early-wave reads, ahead of sub-requests at ≤258, below the subreq p99. Once-bound: each read is passed by the first sub-request behind it, so a late-wave sub-request meets a passed prefix; where the bound fires at the tail it charges 37 against 14 (w3: 6 against 8 fit; w4: 10 against 8 did not). **Honest answer: no order takes the sub-request p99 down 5% while every pass lands below the read tail**: to run before any read ahead, a tail sub-request runs before the read directly ahead, which is a tail read. w2 (allowance 9) would regress the same way.

## 4. Costs
Export/rebuild mean wait at pick 29 → 50 / 52.5; all answered, 0 dropped. sched_share 11.16 / 11.17 / 11.11% (policy cost unmeasurable); program 35.2 µs/req, 88.7% → capacity ~227k, load 0.89; cpu_cores 7.99 (spinning).

## 5. Anomalies and checks
0 drops, no failed or saturated level, adherence 99.87–99.89 (client artifact). **Headline margin:** fifo overall median 67 (66–67) vs 45 at 56k = 1.49× of the 1.5× limit (author 56–62); 1 µs of drift moves the headline to 191k, where the gate still holds (fifo ×1.95, passonce ×1.90). late_at_pick 2.8% of deadline picks vs client 12.2% of deadline requests missed: 4.4× undercount. rq_overflow 32 in one passonce run (author: never near full). p99.9 floor 189–193 at 56k. Author: fifo inside every band (p99 290–340, p99.9 400–480, health 250–300, met 78–85%); prio inside (265–320; export 400–520) except rebuild 433 below 450–600; HIGH tail 0.94 of fifo's (0.92–0.95); passonce = prio as predicted. Skeptic: QWait99 is the wait distribution's p99, not the tail request's wait; the wave/drain split and the −12 argument are inferred from arrival spacing, not measured per request.

## 6. Hypotheses (all tie-breaks on equal hints: w1, w3, w4, w5, w0 identical by construction, no equal-hint pair with different deadlines)
1. **Deadline tie-break, once per thread**: inside passonce's candidate test, among equal hinted run times the earlier-due thread passes, each passed thread once (the mark). Gains early-wave sub-requests (p90, deadline-met), p99 −0 to −15. Pays wave reads +37 once: read p99 +20–37 on w6 and w2. Expected worse; prices the trade under the once-bound.
2. **Same, passing only reads that have waited under one fetch** (clock read only on a candidate): passed reads end ≤~140, in the body. Gains sub-request body/deadline-met; p99 same; reads' p50/p90 a few µs. Expected "same" everywhere; risk: p2's unexplained +5% reads, +5–9% background on w2 with this freshness.
3. **Unconditional deadline order within HIGH**: the full trade (sub-requests toward 150–210, reads +35–60%; w4 appends lose 25). Rejected by rule; measures the author's busy-phase argument.

None is acceptable on w6 as the rule stands.

## 7. Lessons
- Workload: waves moved only the run-queue part (94 → 204) and left outside ~30; with equal costs the exchange rate is 1:1 and the allowance 0.4 fetch; the headline sits at 1.49 of 1.5.
- Policy: the read ahead of a tail sub-request is ~12 µs behind it in latency; a pass that helps the tail charges the tail; the once-bound protects nothing when the pass costs 37 against 14.
- Measurement: counters give the mean backlog (0.6) not the wave profile; prio's r1 shift (10%) vs passonce 2%: a candidate's max must beat 280; late_at_pick undercounts 4.4×.

Sources: /Users/mpawagi/caladan/autoresearch/results/e1/gen5/summary.csv, counters.csv; RtStats in /Users/mpawagi/caladan/autoresearch/results/e1/gen5/raw/w6__{fifo,prio,passonce}__hints__hints__r{1,2,3}/rps{202000,191000,56000}.out; /Users/mpawagi/caladan/autoresearch/results/e1/gen1/summary.csv (w2, session 20261023-003837); /Users/mpawagi/caladan/runtime/sched.c (policy region 186–634, sched_count_pick); /Users/mpawagi/caladan/autoresearch/workloads/w6-fanout-leaf-short-bursts.json; /Users/mpawagi/caladan/autoresearch/policies/p3-passonce.md. Read-only; nothing modified or run on the nodes. About 950 words with the table and ranges, the density of gen 2–4's reports.
