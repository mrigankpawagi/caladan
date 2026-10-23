# Generation 18: three budgets for the same fetch

## What happened

1. **Three workload proposals**, probed against the champion sjf_share:

   | Proposal | Probed load | fifo score p99 | Champion score p99 | Its wait p99 | Share in runqueue |
   |---|---|---|---|---|---|
   | w19a w18 on 2 guaranteed + 2 burstable cores next to a cache antagonist | 70k | 471 µs | 432 µs | 316.3 µs | 73% |
   | w19b a replicated storage node (new service) | 98k | 540 µs | 241 µs | 152.7 µs | 63% |
   | w19c the same fetch with three budgets, 128 connections | 76k | 544 µs | 503 µs | 405.0 µs | 81% |

   w19c became **w19**. The same 41–45 µs fetch arrives from the frontend
   (due in 800 µs), a mid-tier ranker (450 µs) and a fan-out aggregator
   (300 µs). p18's equal-cost pass needs the passer due twice as late, so
   frontend fetches never passed mid-tier ones. Gate: PASS at 76k; point p99
   fifo 551.5, prio 340.0 (fanout deadline-met 98.35%), champion 483.0 µs.
2. **Report** (measurement agent): the points' 388.6 µs queue-wait p99 is
   about 254 µs of backlog that oldest-first also has, 90 behind younger
   mids and 45 behind younger fanouts. 128 connections left steals and depth
   unchanged and pushed only about 0.1% of HIGH threads into overflow. Top
   hypothesis: state the due-later cut as the chosen thread's reserve plus
   both lengths.
3. **Policy p19 sjf_tier** (policy agent): the equal-cost pass now needs the
   passer due later by more than the chosen thread's 30% reserve plus both
   lengths, compares both threads' used share of their windows at the same
   moment, and takes the oldest thread that qualifies, found in a second
   scan. **Accepted** without a paired confirmation: w19 −14.4% (413.5 µs),
   mids +16.3% and fanouts +13.2% p99 with no deadline-met lost; w18 −8.3%,
   with its fanouts at +12.6% p99 and −0.21 points.

## Findings

- **A ratio became a sum.** p16 and p18 asked for a passer "due at least
  twice as late". p19 asks for "due later by more than what the passed
  thread must keep, plus both run times", which needs no constant for how
  far apart the tiers are and still keeps mids from passing fanouts.
- **The antagonist leaves more in the runqueue when the server has fewer
  guaranteed cores.** On 4 cores (2 guaranteed) 73% of the champion's tail
  was runqueue wait, against 49% on 6 guaranteed cores in gen 17. Requests
  queue even at light load while parked cores are won back (point wait p99
  41 µs at 28k against 0.7 without the antagonist).
- **More connections did not even out the cores.** 128 connections instead
  of 48 left steals at 14% and depth at 2.07; only overflow appeared.

## Orchestrator notes

- No sleep this generation; all runs complete.
- Gen 19's three proposals were drafted during p19's evaluation: w19 on
  burstable cores next to the cache antagonist, frontend fetches whose cost
  varies with document size around the 45 µs hint (the first per-request
  wrong hint in the RPC family), and a search leaf where full searches cost
  four times a type-ahead suggestion.

## Node time

About 45 minutes: probes (5 min), w19's matrix (10 min), p19's evaluation
(27 min, no paired confirmation).
