# Generation 6: a HIGH kind with no run-time hint

## What happened

1. **Workload w7** (workload agent): w5 plus a HIGH "sync" kind, 30 µs
   replica syncs arriving in bursts, whose run-time hint the server leaves
   blank. Gate: PASS at 380k. fifo's get p99 is 200.5 µs; the champion
   sjf_guard's is 139.0 (98.5 on w5), because it counts a blank run time as
   zero and runs syncs ahead of every waiting get and put. Get and put
   runqueue-wait p99 rose from 43.3 and 37.7 µs on w5 to 96.0 and 94.6.
2. **Report** (measurement agent): the new cost is queueing behind syncs.
   The rejected sjf_timed gets the best get tail (96.5 µs) by learning the
   sync's length, but its flush-inflated put length costs puts 2.4 points of
   deadline-met.
3. **Policy p7 sjf_nohint** (policy agent): sjf_guard with one change: a HIGH
   thread without a run-time hint counts as 8 µs long. Threads with a hint
   are ranked exactly as before, so w1–w6 see identical decisions.
   **Accepted** after a paired confirmation: w7 get p99 116.5 µs (−16.2%),
   put deadline-met 95.87 → 97.98%, query flat, sync p99 +20.8% (limit
   25%). Every line of the policy agent's prediction held. sjf_nohint is
   the new champion, the first since gen 2.

## The paired confirmation

The first verdict rejected p7 on w5 rule 6: query deadline-met 86.50% against
the champion's 88.05%. But on w5 the two policies make identical decisions,
and the champion's numbers were from gen 4, more than two hours earlier.
Repeats inside one session agree within about 0.3 points; across sessions
the same decisions measured:

| w5 query deadline-met at 390k | Repeats | Session |
|---|---|---|
| sjf_guard | 88.18 / 87.92% | gen 4, 20:47 |
| sjf_learn (rejected p5) | 86.51 / 86.59% | gen 4, 21:18 |
| sjf_timed (rejected p6) | 87.38 / 87.22% | gen 5, 22:07 |
| sjf_nohint | 86.49 / 86.51% | gen 6, 23:01 |
| sjf_guard, paired | 86.81% (median of 2) | gen 6, 23:11 |
| sjf_nohint, paired | 86.92% (median of 2) | gen 6, 23:11 |

Rule 6 allows 1 point, so drift alone could reject a policy. The two
policies were re-measured alternately in one session, and the judge decided
w5 from those runs. The same drift explains p7's +3.9 to +5.9% on w1–w3 with
identical decisions, within rule 2's 10%.

**p5's rejection is now in doubt.** sjf_learn was rejected on w5 rule 6
alone, against sjf_guard runs taken 30 minutes earlier: 86.55% against
88.05%. Its 86.55% matches what sjf_guard measures today. Gen 7 starts with
a paired re-check of sjf_learn against sjf_guard on w5; history stays as
recorded, and the result goes on p5's card.

## Orchestrator changes this generation

- **Older LOW workloads trimmed** to their top three levels in the reduced
  evaluation (saves about 3 minutes per policy).
- **Paired confirmation** (README, "Paired confirmation"): when a policy
  passes rule 1 but fails elsewhere, `eval_policy.sh` re-measures it and the
  champion alternately on each failing workload and judges again.
  `run.py --paired` labels these runs p1, p2, ...; the judge decides a
  workload from paired runs when both policies have them in one generation.
- **The judge lists every failing workload.** Each workload is now checked
  on its own; before, a failure hid later ones.

## Observations to keep

- **Hints that are present but incomplete need a default.** A blank run-time
  hint meant zero to sjf_guard, the most urgent possible length. A neutral
  default restored the order without learning anything.
- **The trade-off pattern of p4–p6 broke.** p7 gained for gets and puts, and
  only syncs, which have no deadline, paid. The rules allow a kind without a
  deadline to pay up to 25% of p99.
- sjf_timed still has the lowest get tail on w7 (96.5 µs). Learning lengths
  helps when it is limited to lowering them; raising a hinted kind's length
  cost puts every time.

## Open requests for the owner

Unchanged: preemption (a get cannot pass a running 30 µs sync); hint-aware
stealing; packet processing on every reschedule while hinted threads wait;
exact run times from the scheduler; learned-cost counters.

## Node time

About 23 minutes: w7's matrix, p7's reduced evaluation, and the 2.5-minute
paired confirmation.
