# Generation 20: the first convergence generation

## What happened

1. **Same-session re-measurements.** Two more rounds of re-measuring
   decisive rivals (`judge.py rivals`) on top of generation 19's. The best of
   many measurements from older sessions was a lucky draw: once re-measured,
   w1–w3, w11 and w13 were wins again.
2. **Loss report** (measurement agent): on w4b–w12 queries miss more
   deadlines under the champion than under prio. The order lets younger gets
   and puts, and 30 µs syncs hidden under short labels, run ahead of queries.
   p4's rescue, with a 13 µs margin measured at light load, fires late. On
   w17 prio is 6.9% faster.
3. **Policy p21 sjf_early** (policy agent), with variants sjf_early30 and
   sjf_early_w: an earlier, guarded query rescue. A paired probe on the nodes
   showed no query deadline-met change beyond ±0.6 point and gets 5–6% slower.
   sjf_early_w's full convergence evaluation: **rejected** (11 wins, like the
   champion; it gained w12 and lost w11).
4. **Policy p22 sjf_age** (policy agent, generation 21's slot, drafted in
   parallel): aging. Its own model predicted no new wins, and it was **not
   built** after the definition change below.

## The win definition changed

The first definition required being within 1 point of the best deadline-met
any policy reached, then within noise of the best such policy's score. That
made prio's query deadline-met the bar on w4b–w12. Matching it meant
behaving like prio there, which doubles get p99 (81 → about 156 µs on w5),
and rule 2 allows +10%. Two more facts:
- The four mechanisms tried on the nodes (later, earlier and guarded rescues,
  aging) gained at most about 0.5 point within the rules.
- The measured scheduler share ruled out the policy's own cost per pick as
  the cause.

The owner chose a new definition: a policy wins a workload if **no other
policy dominates it**. Dominating means being better beyond noise on
something (score more than 6% lower, or a kind's deadline-met more than 1
point higher) and worse beyond noise on nothing.

| Definition | sjf_tier wins | Losses |
|---|---|---|
| Best of deadline-keepers (gen 19, same session) | 11 of 20 | w4b–w10, w12 (query deadline-met), w17 |
| Never dominated (from gen 20) | **19 of 20** | w17: prio 208.0 against 227.0 µs, fanout deadline-met within noise (99.78 against 99.82) |

## What is left

- **w17:** a pass inside the region that lets points go ahead of fanouts as
  prio does, without letting a queued health check hide them. The gen 20
  report's hypothesis 3 is a smaller reserve for p17's older-passer pass.
- **A single-session final confirmation** of the final policy against every
  policy that could dominate it, with more repeats. The 19 wins mix sessions
  from the last few hours, and a few margins are within noise.

## Node time

About 2 hours 10 minutes: three rounds of re-measurement (about 75 min),
the p21 probe (26 min), and sjf_early_w's convergence evaluation (about
65 min).
