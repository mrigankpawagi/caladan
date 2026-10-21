# Generation 13: six cores, chosen from three proposals

## What happened

1. **Three workload proposals** (prompt v1.3, each assigned an untouched
   dimension), probed with `probe.py` (fifo and the champion, one repeat):

   | Proposal | Probed load | fifo get p99 | sjf_upper get p99 | Its get wait p99 | Share in runqueue |
   |---|---|---|---|---|---|
   | w14a exponential service, honest hints | 90k | 269 µs | 127 µs | 18.2 µs | 14% |
   | w14b six cores | 75k | 774 µs | 239 µs | 157.6 µs | 66% |
   | w14c memory-bandwidth antagonist, load 0.9 | 100k | 680 µs | 217 µs | 130.4 µs | 60% |

   w14b became **w14** (w13 on 6 cores, same load per core). Gate: PASS at
   75k; fifo 804.0 µs, champion sjf_upper 247.5.
2. **Report** (measurement agent): every mean stayed flat, but the gets'
   runqueue-wait p99 grew 33% over w13; about 160 µs of the 166 µs is a
   matter of order. Top hypothesis: stop urgent queries passing waiting gets.
3. **Policy p14 sjf_ratio** (policy agent): one condition added to p13's
   rescue check: at a time unit above 1, an urgent HIGH thread passes the
   chosen one only if it is at most 3 times as long. **Accepted** on every
   workload without a paired confirmation: w14 −17.4% (204.5 µs), w13
   −15.3%, w11 −8.4%, w12 −7.5%, and no kind with a deadline lost anything.

## Findings

- **On a fresh, realistic mix the champion already works.** On w14a,
  exponential service times with honest hints, a workload no policy was
  designed against, sjf_upper cut fifo's get p99 by 53% and left only 14% of
  its tail in the runqueue. That is a data point against overfitting: the
  hint-aware ordering generalizes to a mix outside the family it was tuned on,
  and is near what ordering can do there.
- **The antagonist did nothing measurable.** At light load w14c matched w13
  (get p99 26 µs); at 100k it was within 4% of w13. The IOKernel isolates the
  server's guaranteed spinning cores from a best-effort neighbour, as in the
  gen 5 test.
- **Fewer cores stretch the tail, not the means.** HIGH wait and queue depth
  were flat from 8 to 6 cores; the get wait p99 grew 33% and steals fell.
- **p14 is the simplest accepted change in a while,** and its gain cost no
  other kind: get wait p99 on w13 halved (125.4 → 60.0 µs).

## Orchestrator changes this generation

- `probe.py` and `run.py --probe` (proposal probes), workload prompt v1.3
  (untouched dimensions, real-workload inspiration), and a step-down to
  lower levels when a proposal's two busiest levels are overloaded.
- **This Mac went to sleep** (closed lid, on battery) one second after the
  last measurement of p14's evaluation, from 16:09 to 16:38. The data was
  complete, but the teardown never reached the nodes and an IOKernel and
  server were left running until cleaned up by hand; every experiment's setup
  kills leftovers anyway. Experiment commands now run under `caffeinate`,
  which only helps while the Mac is on power with the lid open.

## Open requests for the owner

Unchanged (the owner has asked to stay inside the policy region for now).

## Node time

About 45 minutes: proposal probes (8 min), w14's matrix (10 min), and p14's
evaluation (about 27 min, of which 17 were the Mac asleep).
