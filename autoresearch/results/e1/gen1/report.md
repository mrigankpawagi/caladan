# Gen 1 measurement report: w2 fan-out leaf, fifo vs prio

Session 20261023-003837, 3 repeats, medians (min-max), µs.

## 1. Headline, 202,000 req/s

| Policy | read p99 / p99.9 (×800) | subreq p99 / p99.9 (×130) | health | export | rebuild | resp/s |
|---|---|---|---|---|---|---|
| fifo | 184 (180-193) / 349 (334-352), ×0.23 / ×0.44 | 187 (182-195) / 341 (334-348), ×1.44 / ×2.62 | 144 (144-151) / 296 (290-325) | 183 (181-197) / 341 | 186 (183-188) / 333 | 201056 (199937-201230) |
| prio | 179 (170-182) / 327 (305-336), ×0.22 / ×0.41 | 176 (172-181) / 326 (308-328), ×1.35 / ×2.51 | 139 (134-144) / 284 (267-293) | 248 (239-248) / 545 | 253 (251-263) / 535 | 200771 (200413-201228) |

Subreq deadline-met: 97.01% fifo, 97.26% prio.

## 2. Is it real
Subreq p99 −6%, ranges separated by 1 µs (181 vs 182): real, barely. Read, health: inside the spread. Subreq p99.9 −4%: below the rule. Export/rebuild +35%/+36% p99, +60% p99.9: real, by design. At 191k the subreq gap (139 vs 133) overlaps; nothing is real below the headline.

## 3. Where the time goes (prio, subreq p99 176)
- Own service 37; light-load floor ~12 (p99 49 at 56k, min 43).
- Run-queue wait ~94 (86-103): QWait99 from the client. Fifo: 109 (104-110).
- Remainder ~33: before the thread is ready (packet waits for the running fetch and the softirq thread; wait_us_softirq 0.09 → 1.2 µs from 56k to 202k). No ordering reaches it.

Split of the 94 by work share within HIGH: ~61 other subreqs, ~33 reads, <1 health. Prio removed exactly the background share (10.5% of work): QWait99 109 → 94, p99 −11. **Only ~33 µs of a tail subreq is reads ahead of it**; an all-subreq-first order would still leave ~143 (×1.10).

Reads' slack: 621 µs to the deadline, but **9 µs by the rule** (5% of 179) and 16 at p99.9. Asymmetry: 3,300 subreqs/s miss; 600 reads/s define the read p99. A pass moves one subreq down and one read up, and the read (older) lands above the subreq's old latency, so the read p99 band fills ~2× faster than the subreq's empties.

Counters: mean depth 1.20 (choice in ≤20% of picks); 27%/26% of hinted picks were stolen threads (steal path ignores hints); fifo inversion rate 1.0%; late-at-pick 0.39% vs 3.0% client misses (8× undercount).

## 4. Costs
Export/rebuild still answer 99.8%/99.6% of offered, 0 dropped. sched_share 11.0% vs 11.1% (policy cost not measurable); program share 89% → capacity ~227k. cpu_cores 7.99 is spinning, uninformative. Health: 1 µs work, 139/144 p99 — 95% waiting; p99.9 noisy (27 samples/level).

## 5. Anomalies and checks
No failed or saturated levels, 0 drops, adherence 99.86 (99.85-99.87) at every level (client artifact), rq_overflow ≤1. **p99.9 floor**: at 56k (QWait99 0.8) fetch p99.9 is 197-202 and p99.99 240; w0/w1 at 100k show 155-168. ~0.1-0.2% of requests spend ~150 µs outside the queue at any load; subreq deadline-met is 99.81% at 56k, the ceiling for any policy. Author's expectations: fifo fetch p99 predicted 210-260, measured 187 (≈3 fetches ahead, not 4-7); prio predicted 135-175, measured 176-179 (less gain); export/rebuild predicted 300-450/450-800, measured 248/253 (less harm). Ratios ×1.44, ×0.23, health ~40 lower, headline 202k: as predicted.

## 6. Hypotheses (mechanisms)
1. **Rationed rescue pass.** A subreq runs ahead of older reads only when the service hints of the threads ahead show it would otherwise miss, and only past reads still young enough that one more fetch leaves them in the body of the read distribution; otherwise oldest-first. Gains: subreqs that land in a freshly formed queue. Pays: young reads, one fetch each, outside their tail. Only mechanism whose cost can stay inside the 9 µs.
2. **Subreq-first within HIGH (deadline order).** Gains subreq up to ~33 µs; pays reads ~37-74 at the tail (+20-40%). Expected to fail the rule; worth one measurement to put the price on record.
3. **Shortest hinted service first among HIGH** (health ahead of fetches): health gains ~100 µs, fetches pay ≤1 µs. Free rider on 1 or 2, not an improvement by rule.

## 7. Lessons
- Workload: the loose kind's spendable slack is 5% of its p99 (~9 µs), not its deadline gap (621); it needs a mix where the two kinds' tails differ, and expect prio to move only the background share (10% here).
- Policy: a tail subreq has ~33 µs of reads ahead, 61 of subreqs, 82 outside the queue; 26% of hinted threads are stolen before any local order applies.
- Measurement: QWait99 is the wait distribution's p99, not the p99 request's wait; the 200 µs p99.9 floor at 0.25 load needs a source (client timer, NIC, IOKernel) before p99.9 comparisons mean anything.
