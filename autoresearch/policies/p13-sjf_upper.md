# p13: sjf_upper

- id: p13
- config: sjf_upper
- generation: 12
- status: candidate
- builds_on: p12
- changed_from_previous: p12 plus: the per-core deadline estimate steps 3× further up than down, so it tracks the upper quartile of HIGH relative deadlines instead of the median, and a unit above 1 is kept until that estimate is a whole 100 µs away from it; the 350 µs threshold, the scaled constants, and the order, slack, rescue, timing and learning are p12's (unit 4 on w11–w13, 1 on w1–w10)
- commit: 12cb1b2

## What it does
Like sjf_scale, each core runs helper threads first, then HIGH, NORMAL and LOW threads. Among HIGH threads it runs shorter requests first, using run times it learns per label and measured on a time scale it reads from the deadlines it sees. sjf_scale reads that scale from the deadline carried by the middle of its HIGH work. sjf_upper reads it from the deadline carried by the longer-deadline quarter, and it does not switch scale on a brief dip. On w13, half the HIGH work is 300 µs queries, but lookups, puts and syncs carry 400 µs. The scale is therefore 4, as on w12: slow syncs and flushes no longer hide behind the puts' short hint, and lookups again run ahead of them. Leases keep running first.

## Why (hypothesis)
- **Why sjf_scale loses on w13:** in the gen 12 gate at 100k, sjf_scale matches sjf_mixed (get p99 259.0 vs 267.5 µs, get runqueue-wait p99 178.1 vs 185.7). That is p10's state, as the w13 spec predicts: queries are 49% of fresh HIGH picks at 300 µs, so the median is 300 µs and the unit is 1.
- **What the same order gave on w12:** gen 11, w12 at 100k: get p99 184 against sjf_mixed's 236.5, and get wait p99 84.5 against 161.8.
- **Why the new estimate lands at 400 µs:** on w13 about 39% of HIGH picks carry at least 400 µs. These are gets, puts, syncs and multigets, plus multiget remnants requeued after the 100 µs time slice. About 10% carry 1000 µs or more. An upper-quartile estimate sits where 25% lie above, so it settles at the 400 µs mass and the unit is 4.
- **Tolerance of requeued threads (gen 11 lesson):** requeued sync, flush and multiget remnants only add short values, and they are about 6% of picks. With 61% of picks short, a median-style estimate could slip, so a unit above 1 is held until the estimate leaves 300–500 µs. The queries' 300 µs mass pushes the estimate up below that range, so a table clear in a run is very unlikely.
- **w1–w10:** every deadline is at most 300 µs and the estimate never passes the largest value seen, so the unit is always 1 and the decisions equal p12's (and p10's).
- **w11, w12:** the estimate is 400 µs and the unit 4, so the decisions equal p12's after start-up.
- **Offline check (scratchpad p13/drv.c, the real region plus this code, lockstep against sjf_scale):**
  - w9-like and w2-like streams: 0 of 400k picks differ.
  - w11-like stream: 0 differ.
  - w12-like stream: 0.5% differ, during start-up.
  - w13-like stream: unit 4, and p12's w12 labels form.

## Cost
- **Same per-pick work as p12:** one estimate step and at most one division per HIGH pick.
- **On w13, the costs are p12's w12 trade:**
  - syncs' p99 rises about 5–10%;
  - puts lose about 0.2 points of deadline-met;
  - multigets are about flat.
- **Queries:** the 300 µs deadline makes them urgent sooner; their order against gets and puts is unchanged.

## Prediction (from the policy agent)

| Workload | Metric (100k unless noted) | Expected vs sjf_scale |
|---|---|---|
| w13 | get p99 | −20 to −30% (259 → about 185–210 µs) |
| w13 | get runqueue-wait p99 | 178 → about 85–110 µs |
| w13 | sync p99 | +5–12% (limit 585.6) |
| w13 | put p99 / deadline-met | +0–8% / −0.1 to −0.4 points (limit 98.41) |
| w13 | query p99 / deadline-met | −2 to −5% / flat to +1 point (limit 83.72) |
| w13 | multiget p99 / deadline-met | ±3% / ≥ 99.9% |
| w13 | lease p99 / deadline-met | flat (about 130 µs / about 95%) |
| w11, w12 | get p99 | equal within noise (same unit 4) |
| w1–w10, w0 | all | identical decisions (unit 1, or no HIGH threads); noise only |

## Results
(filled after evaluation)
