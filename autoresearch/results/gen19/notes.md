# Generation 19: a search leaf, and a new goal

## What happened

1. **Three workload proposals**, probed against the champion sjf_tier:

   | Proposal | Probed load | fifo score p99 | Champion score p99 | Its wait p99 | Share in runqueue |
   |---|---|---|---|---|---|
   | w20a w19 on 2 guaranteed + 2 burstable cores next to a cache antagonist | 71k | 508 µs | 383 µs | 273.3 µs | 71% |
   | w20b w19 with frontend fetches of exponential cost around the 45 µs hint | 76k | 690 µs | 688 µs | 531.3 µs | 77% |
   | w20c a search leaf: searches four times a type-ahead suggestion | 108k | 639 µs | 409 µs | 317.1 µs | 78% |

   w20c became **w20**, a new service: full searches (48 µs, due in 1000 µs,
   the score) and type-ahead suggestions (exponential, mean 12 µs, due in
   250 µs). Both length and deadline favour suggestions, and every pass needs
   the passer at most half again as long, so a search never passes. Gate:
   PASS at 108k; search p99 fifo 643.0, prio 325.5 (suggest deadline-met
   98.08%), champion 406.5 µs. w20b came within a point: there the champion
   was no better than fifo.
2. **Report** (measurement agent): the search queue-wait p99 is 235.5 µs of
   backlog plus 76.4 behind younger suggestions; the suggestions' +25% p99
   cap binds before their deadline rule.
3. **Policy p20 sjf_slice** (policy agent): a much longer, later-due thread
   may pass if the chosen one keeps 40% of its window after a full 100 µs
   slice. The agent's own model predicted only −2% to −5%. **Rejected** on
   rule 1, decided from w20 alone: search p99 −1.8% (399.0 µs).

## The owner's new goal, and what it showed

The owner asked for at most 25 generations, ending with a policy that
**always wins**. They chose this definition: on every workload the policy is a
deadline-keeper, meaning every kind with a deadline meets within 1 point of
the best deadline-met any policy reached there. Its score must also be within
the noise band of the best other deadline-keeper. New tooling:
`judge.py wins`, acceptance rule 7 (keep every win), and convergence
generations (`eval_policy.sh ... converge`, `judge.py accept --converge`).

The first table gave the champion 11 wins of 20. The orchestrator then
re-measured the eight lost workloads in one session, with each workload's
bar-setting policies:

| Workload | Result | Why |
|---|---|---|
| w1–w4b, w11, w13–w16, w18–w20 | win | w14's loss was drift between sessions |
| w5–w10, w12 | loss | query deadline-met 86.9 / 86.9 / 82.7 / 82.7 / 82.3 / 87.5 / 91.7%, against the best 89.1 / 88.8 / 86.9 / 87.0 / 84.9 / 91.3 / 93.6% (prio, except edf_high on w7 and the rejected p6 sjf_timed on w8, whose get p99 was 96.5 µs) |
| w17 | loss | prio 209.0 µs against 223.5 µs, keeping deadlines |

The per-generation rule 6 allowed each policy to give up to 1 point of
deadline-met against the previous champion. On the key-value workloads,
query deadline-met fell that way, 2–4.4 points below the best, while the get
score halved.

## Orchestrator notes

- No workloads are added from generation 20; generations 20–25 aim at the
  eight losses.
- No sleep this generation; all runs complete.

## Node time

About 60 minutes: probes (5 min), w20's matrix (10 min), the
re-measurement of eight workloads (30 min), and p20 on w20 (4 min).
