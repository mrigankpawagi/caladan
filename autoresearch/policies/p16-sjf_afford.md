# p16: sjf_afford

- id: p16
- config: sjf_afford
- generation: 15
- status: accepted
- builds_on: p15
- changed_from_previous: p15 plus: after the order has chosen a HIGH thread, the shortest waiting HIGH thread (not overrun) runs first instead if it is at most a third as long (p14's ratio), due at least twice as late relative to when each became ready but within p9's deadline split, and the chosen thread would still keep 40% of its relative deadline as slack after it (on w16 points and health checks pass fanouts that have time to spare); on w1–w15 no such thread exists outside rare multiget cases, so decisions are p15's
- commit: bb79c96

## What it does
Like sjf_overrun, each core runs helper threads first, then HIGH, NORMAL and LOW threads, and orders HIGH threads by deadline and length. Sometimes that order picks a long request only because its deadline is tighter, while a much shorter request with a much looser deadline waits. sjf_afford then runs the short request first, as long as the long one would still have plenty of time left afterwards (40% of its deadline window). On w16, a cheap point read no longer waits behind a fan-out sub-request that has time to spare, and the sub-request loses only about 10 µs. On the earlier workloads, shorter requests are never due much later than longer ones, apart from multigets that only look short, which are excluded, so nothing changes there.

## Why (hypothesis)
- **The bottleneck (gen 15 report §3, hypothesis 1):** 88% of the point p99 is runqueue wait (426.7 of 483.0 µs). That wait tracks how long after a point a fanout may still run first: 0, 236 and 500 µs give 255.8, 426.7 and 628.2 µs. A point costs a fanout about 10 µs; a fanout costs a point about 40.
- **Why the champion cannot fix it:** the ordinary order ranks a fresh fanout (300 + 8×40) ahead of a point (800 + 8×10), so the conflict is in the order itself.
- **The guard:** the rule spends a fanout's slack only while it keeps 120 µs of its 300; once a waiting fanout gets within 120 µs, p15's order (and its rescue) runs it first again. A 100 µs guard gave points −49% but fanouts −0.66 points of deadline-met in the model, and −0.93 under a heavier calibration.
- **The exclusions:** *due at least twice as late* is the deadline–length conflict itself (on w1–w15 shorter kinds have equal or tighter deadlines, except multigets); *within p9's split* keeps out multigets, which carry the lookups' short hint but run about 130 µs; lengths are learned lengths, as in p14.
- **Offline check** (gen 14 model with the current region; w16 with 48 connections; calibrated so prio matches the measured w16 numbers within 4%): 0 differing picks from p15 on w1–w13 (about 3.0M picks); 0.01–0.04% on w14 and w15, all while a core's unit briefly reached 8 or more, with their kinds at noise level. w16 at 155k, 8 seeds: point p99 503 → 360, fanout p99 278 → 317, fanout deadline-met 99.31 → 98.75, health 627 → 270, export and rebuild ±1%. Across calibrations: point −23% to −49%, fanout deadline-met −0.35 to −0.56 points.

## Cost
- **Fanouts:** they wait for points and health checks until their slack nears 120 µs. Model at 155k: fanout p99 +8% to +14% (limit +25%) and deadline-met −0.35 to −0.56 points (limit 1.0).
- **Per-pick work:** one comparison per HIGH thread to track the shortest, plus one check after the scan. No extra clock read and no new state.
- **Risk:** the rule relies on a w16 core's time unit being at least 7 (the model gives 8; the upper-quartile rule should put it at 8, where the split is 1125 µs), so that the points' 800 µs deadline stays within p9's split. At a unit of 5 or less p16 behaves exactly like p15 on w16.

## Prediction (from the policy agent, against sjf_overrun)

| Workload | Metric (headline load unless noted) | Expected vs sjf_overrun |
|---|---|---|
| w16 (155k) | point p99 (score) | −17% to −32% (483.0 → about 330–400 µs; limit 437.4 after the champion's restored repeat) |
| w16 | point runqueue-wait p99 | 426.7 → about 280–360 µs |
| w16 | fanout p99 | +5% to +17% (298.0 → about 315–350; limit 372.5) |
| w16 | fanout deadline-met | −0.3 to −0.7 points (99.07 → about 98.4–98.8; limit 98.07) |
| w16 | health p99 | −45% to −60% (606 → about 250–330) |
| w16 | export / rebuild p99 | within ±4% |
| w1–w13 | every metric | unchanged within noise (decisions are p15's) |
| w14, w15 | get p99, deadline-met | within noise |
| w0 | p99 and saturated throughput | unchanged (no HIGH threads) |

## Results
Accepted in generation 15 (judge.py, results/gen15/) against the champion
p15 sjf_overrun, on every rule and every workload, without a paired
confirmation.

| Workload | sjf_overrun | sjf_afford | Change | Notes |
|---|---|---|---|---|
| w16 | point p99 486.0 µs | 255.0 µs | −47.5% | predicted −17 to −32%; better than prio (305.0) |
| w16 | fanout p99 / met | 299.0 µs / 99.04% | 321.5 µs / 98.53% | +7.5% / −0.51 points (predicted +5 to +17%, −0.3 to −0.7) |
| w16 | health p99 | 608.5 µs | 178.0 µs | −70.7% (predicted −45 to −60%) |
| w15 | get p99 261.0 µs | 262.5 µs | +0.6% | bigget p99 +16.5% (limit 25%): a 1%-of-lookups kind, few samples at p99 |
| w14 | 197.5 µs | 192.5 µs | −2.5% | |
| w1–w13 | | | within noise | p15's decisions |

On the first workload outside the key-value family, the champion line had
fallen behind plain priority classes; one guarded rule (a much shorter,
much later-due request may pass when the chosen one keeps 40% of its
deadline window as slack) put it ahead of prio on the score while keeping
more of the fanouts' deadlines than prio does.
