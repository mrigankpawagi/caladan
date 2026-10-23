# p19: sjf_tier

- id: p19
- config: sjf_tier
- generation: 18
- status: accepted
- builds_on: p18
- changed_from_previous: p18 plus: in the equal-cost pass, the passer must be due later than the chosen thread by more than the chosen thread's 30% reserve plus both lengths (instead of at least twice as late), must have used at least as large a share of its window as the chosen thread has so far (instead of as large as it will have after waiting), and is the oldest waiting HIGH thread (not overrun) that meets the conditions, found in a second scan (instead of the oldest waiting HIGH thread); on w19 frontend fetches pass mid-tier and fan-out fetches that arrived after them, mids never pass fanouts, and on w1–w17 decisions are p18's (at most 0.017% of picks differ in the model)
- commit: 610f8f5

## What it does
Like sjf_share, each core runs helper threads first, then HIGH, NORMAL and LOW threads. It orders HIGH threads by deadline and length, and lets a request that came first go ahead of the chosen one when both cost about the same and the chosen one can spare the time. sjf_tier changes when that is allowed. The earlier request may go first if its deadline is later than the chosen one's by more than the chosen one's reserve (30% of its budget) plus both run times, and it has already used at least as large a share of its own budget as the chosen one has. On w19 a frontend fetch (800 µs budget) can now go ahead of mid-tier fetches (450 µs) as well as fan-out fetches (300 µs) that arrived after it, while a mid-tier fetch still never goes ahead of a fan-out fetch. If the request that has waited longest does not qualify, the policy looks at the next oldest one, so a mid-tier fetch that may not pass no longer hides an older frontend fetch that may.

## Why (hypothesis)
- **The bottleneck (gen 18 report, section 3):** queue wait is 388.6 of the 483 µs point p99. About 254 µs of it is backlog that oldest-first also has, about 90 µs is spent behind younger mids and about 45 µs behind younger fanouts. p18's pass needs the passer due at least twice as late (800 / 450 = 1.78), so points never pass mids, and they pass a fresh fanout only after waiting 123 µs.
- **The cut (report hypothesis 1, stated in deadlines and cost):** "due later by more than the chosen thread's reserve plus both lengths."
  - Point over mid: 350 > 135 + 88, so it passes.
  - Point over fanout: 500 > 90 + 88, so it passes.
  - Mid over fanout: 150 < 90 + 88, so it does not pass (28 µs of margin).
  - In the model this alone gives −4% to −7%: points still wait for mids that are waiting too, because the share test charges the passer's whole run time to the chosen thread.
- **The share test, now against now:** "who has used more of their window?" is asked of both threads at the same moment. What the passer costs is charged only through the 30% reserve the chosen thread must keep. The reserve stops passes once a fanout has waited about 122 µs and a mid about 227 µs. Together with the cut this gives −10% to −14% in the model; the change of share test alone gives −4%.
- **The candidate (report hypothesis 2):** the oldest thread that meets the conditions, not just the oldest thread. When the oldest is a mid that may not pass a fanout, an older-than-the-fanout point can still go. This adds about 2 points in the model. Wherever p18's oldest candidate already passes it is chosen again, so p18's passes are kept.
- **Offline check:** the gen 17 model with the current region, w19 added (4 cores, 128 connections, bursts) and the final code compiled in.
  - Calibration on w19: champion point p99 is 495/511 µs in the model (measured 483), mid 305/311 (measured 300.5) and fanout 184/190. The model understates fanout p99 by 9–12% (measured 208.5).
  - Lockstep against sjf_share: 0 differing picks on w1–w10. On w11–w17, 14–129 of 0.33–0.98M (at most 0.017%). On w18, 5.8% differ: reads pass fresh fanouts sooner.
- **w19 at 76k (model, 6 seeds, two overheads):**
  - Point p99 495 → 425 (−14.1%) and 511 → 450 (−11.9%).
  - Point queue-wait p99 417 → 349 and 434 → 372.
  - At 70k–74k, −14% to −18%.

## Cost
- **Mids on w19:** frontend fetches now go ahead of them until a mid has waited about 227 µs.
  - Model: mid p99 +13% to +15% (305 → 346, 311 → 357), so measured about 340–345 against a limit of 375.6.
  - Deadline-met −0.01 to −0.05 points.
- **Fanouts on w19:** points pass fresh fanouts sooner (no 123 µs wait first), still only until a fanout has waited about 122 µs.
  - Model: fanout p99 +12% to +13% (184 → 206, 190 → 214). Scaled by the model's underestimate, measured about 233–236 against a limit of 260.6.
  - Deadline-met −0.02 to −0.04 points (limit 98.905).
- **Fanouts on w18:** model fanout p99 221 → 241 (+9%) and deadline-met −0.09 points; reads 538 → 519 (−3.5%).
- **Health checks gain** (w19 model: 83 → 59 µs).
- **Exports and rebuilds:** unchanged.
- **Per-pick work:** the scan no longer tracks the oldest thread. When p17's pass does not fire and the chosen HIGH thread has a deadline and has not run, a second scan over the ring skips threads not older than the chosen one or the current candidate. For each remaining HIGH thread it does one length lookup and at most a few comparisons and two divisions. No extra clock read and no new state.
- **Risk:** the score margin is moderate (model −12% to −14% against a 10% threshold). For p18 on w18 the model underpredicted the measured gain (−12% predicted, −15.9% measured).

## Prediction (from the policy agent, against sjf_share)

| Workload | Metric (headline load unless noted) | Expected vs sjf_share |
|---|---|---|
| w19 (76k) | point p99 (score) | −11% to −15% (483 → about 410–430 µs; limit 434.7) |
| w19 | point queue-wait p99 | 388.6 → about 320–345 µs |
| w19 | mid p99 / deadline-met | +12% to +16% (300.5 → about 335–350; limit 375.6) / −0.01 to −0.05 points |
| w19 | fanout p99 / deadline-met | +11% to +14% (208.5 → about 230–240; limit 260.6) / −0.02 to −0.05 points |
| w19 | health p99 | −20% to −30% (108.5 → about 75–85) |
| w19 | export / rebuild p99 | within noise |
| w19 (56k–74k) | point p99 | −14% to −18% |
| w18 (76k) | read p99 | −2% to −5% (495.5 → about 470–485; limit 545.1) |
| w18 | fanout p99 / deadline-met | +7% to +10% (234.5 → about 250–258) / −0.05 to −0.10 points (limit 98.83) |
| w17 / w16 | point p99, fanout deadline-met | within noise (w17 model −3%; at most 0.017% of picks differ) |
| w1–w15, w0 | every metric | within noise (p18's decisions; w0 has no HIGH threads, so p4's path is unchanged) |

## Results
Accepted in generation 18 (judge.py, results/gen18/) against the champion
p18 sjf_share, with no paired confirmation needed.

| Workload | Metric | sjf_share | sjf_tier | Change | Notes |
|---|---|---|---|---|---|
| w19 (76k) | point p99 (score) | 483.0 µs | 413.5 µs | −14.4% | predicted −11 to −15% (410–430) |
| w19 | point queue-wait p99 | 388.6 µs | 308.8 µs | −20.5% | predicted 320–345 |
| w19 | mid p99 / met | 300.5 µs / 99.955% | 349.5 µs / 99.945% | +16.3% / −0.01 points | predicted 335–350; limit 375.6 |
| w19 | fanout p99 / met | 208.5 µs / 99.905% | 236.0 µs / 99.89% | +13.2% / −0.02 points | predicted 230–240; limit 260.6 |
| w19 | health p99 | 108.5 µs | 96.5 µs | −11.1% | predicted 75–85 (missed) |
| w18 (76k) | read p99 | 495.5 µs | 454.5 µs | −8.3% | predicted −2 to −5% |
| w18 | fanout p99 / met | 234.5 µs / 99.83% | 264.0 µs / 99.625% | +12.6% / −0.21 points | predicted +7 to +10% / −0.05 to −0.10 (cost above prediction) |
| w17 / w16 | read p99 | 222.5 / 241.0 µs | 227.0 / 240.5 µs | +2.0% / −0.2% | within noise |
| w1–w15, w0 | | | | within noise | largest +4.9% (w14) |

The score and the mids landed as predicted; the restated cut also helped
w18 more than the model said, and charged w18's fanouts more. Fanouts on
w18 now sit at 264 µs p99 and 99.62% met.
