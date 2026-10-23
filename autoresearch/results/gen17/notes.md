# Generation 17: the same fetch with two budgets

## What happened

1. **Three workload proposals**, probed against the champion sjf_older:

   | Proposal | Probed load | fifo score p99 | Champion score p99 | Its wait p99 | Share in runqueue |
   |---|---|---|---|---|---|
   | w18a the leaf next to a cache-thrashing batch job | 136k | 444 µs | 144 µs | 70.6 µs | 49% |
   | w18b a search shard at its usable peak | 136k | 411 µs | 237 µs | 162.7 µs | 69% |
   | w18c the same fetch with two budgets, 4 cores | 76k | 557 µs | 581 µs | 477.9 µs | 82% |

   w18c became **w18**. Frontend reads (45 µs, due in 800 µs) and fan-out
   reads of the same document (41 µs, due in 300 µs) cost about the same, so
   no pass of the champion fired for reads and it did no better than fifo.
   Gate: PASS at 76k; read p99 fifo 574.5, prio 346.5, champion 589.0 µs.
2. **Report** (measurement agent): 82% of the read p99 is runqueue wait
   behind younger fanouts; p16's and p17's passes look only at the shortest
   waiting thread, which is never a read. Top hypothesis: a pass at equal
   cost for the oldest waiting thread, spending only the fanouts' measured
   headroom.
3. **Policy p18 sjf_share** (policy agent): when p17's pass does not fire,
   the oldest waiting HIGH thread may go first if it arrived first, is due at
   least twice as late, is at most half again as long, the chosen thread
   keeps 30% of its window, and the passer has already used at least as
   large a share of its window as the chosen one will have. **Accepted**
   without a paired confirmation: w18 −15.9% (495.5 µs), fanout p99 +8.6%,
   fanout deadline-met −0.02 points, health −14.7%; w16 −7.7%, w17 −4.9%.

## Findings

- **The first antagonist that competes.** w18a's cache antagonist ran on
  best-effort cores and took server cores away (2.3 of 6 at light load, about
  4.6 when busy), unlike gen 13's memory-bandwidth antagonist next to
  spinning cores. But the champion already beat fifo by 68% there and only
  49% of its tail was in the runqueue: most of what an antagonist adds is
  outside the policy's reach (parked cores, slower shared cores), so it is a
  target for hooks the owner has not approved, not for a new policy.
- **Equal cost needs a different question.** Earlier passes asked "is the
  other request shorter?". At equal cost the useful question was "who has
  used more of their own window?", and stating it that way kept the
  fanouts' cost under a third of the 25% limit.

## Orchestrator notes

- No sleep this generation; all runs complete.
- Gen 18's three proposals (a burstable-core antagonist version of w18, a
  replicated storage node, and three budgets for the same fetch over 128
  connections) are being probed against p18.

## Node time

About 45 minutes: probes (9 min), w18's matrix (10 min), p18's evaluation
(26 min, no paired confirmation).
