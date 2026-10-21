# Generation 0: calibration and baselines

## What was run

14 experiments, 13 minutes of node time, no errors (two xl170 nodes, code
5786466): w1 x {fifo, prio} x {hints applied, hints ignored}, w0 x {fifo,
prio} on the hint-enabled build, and w0 x fifo on stock Caladan (hint support
compiled out), each repeated twice; plus a fake-work calibration.

## Findings

1. **The priority hint works on w1.** At the headline load (400k req/s),
   `prio` with hints cuts the short requests' p99 from 95.5 to 52.5 µs (−45%)
   and raises their deadline-met rate from 97.3% to 99.4%. The long requests
   are unaffected (p99 about 116 µs either way). The short requests' mean wait
   in a core's queue drops from 4.5 to 0.5 µs, so the gain is exactly the
   queueing behind long requests that FIFO imposes.
2. **The controls agree.** `prio` with hints ignored (95 µs) and `fifo` with
   hints applied (95.5 µs) match `fifo` with hints ignored (91 µs) within
   noise: the improvement comes only from the scheduler acting on the hint.
3. **Noise band: about 6%.** Repeats of the same experiment differ by up to
   6% at the headline load (fifo on w1: 90 vs 101 µs).
4. **The hint-enabled build costs a little near saturation, even with no
   hints.** On w0, p99 at 300k req/s is 71–73 µs in all four hint-build
   repeats versus 67 µs in both stock repeats, and the median at 350k is
   37 vs 35 µs; lighter loads are identical. `fifo` and `prio` cost the same,
   so it is not the policy's queue scan. The per-pick measurement counters are
   the main suspect.
5. **Capacity.** One fake-work iteration is about 0.01 µs, so w1's short
   requests do about 1.7 µs of work and the long ones 17 µs, and each request
   costs about 4 µs more in the runtime and network stack. With 8 cores, w0
   saturates between 350k and 400k req/s and w1 between 400k and 450k.
6. **Budget.** 56 s per experiment, 34 s per rebuild: about 13 minutes of
   node time for generation 1 and a 25-minute cap per generation
   (README.md, calibration.json).

## Open items for generation 1

- Decide whether to make the per-pick counters switchable, to separate
  measurement cost from mechanism cost (finding 4). This changes runtime code
  outside the policy region, so it needs the owner's approval.
- The workload agent's first harder workload should keep a FIFO penalty
  while leaving `prio` room to improve: `prio` already brings short p99 at
  400k to about half of fifo, and its HIGH queue wait is down to 0.5 µs.

## Addendum: overhead follow-up (between gen 0 and gen 1)

Finding 4 above blamed the per-pick counters. To test that, the counters
were made switchable (`runtime_sched_stats`, commit 810cfbf) and w0 was
re-run in one session, fifo, two repeats per condition:

| Condition | 300k p99 (µs) | 350k median (µs) | Saturated throughput |
|---|---|---|---|
| hint build, counters on (`hints`, r3–r4) | 72 / 72 | 37 / 37 | 375k / 375k |
| hint build, counters off (`hints-nostats`) | 70 / 72 | 37 / 37 | 376k / 376k |
| counters off, hints ignored | 70 / 70 | 37 / 37 | 376k / 377k |
| stock Caladan (r3–r4) | 67 / 68 | 35 / 35 | 379k / 380k |

The counters are **not** the cause: switching them off changes nothing
measurable, and neither does the hints mode. The remaining cost, about 1% of
saturated throughput and 2 µs of median latency near saturation, belongs to the
hint build's general pick mechanism (an indirect policy call and the code that
closes the gap in the queue, in place of stock Caladan's one-line pop). Every
policy shares it, so policy comparisons are unaffected, and experiments keep
the counters on. Not chased further for now (not needed for the loop); a
possible later fix is an inlined fast path for a queue of one thread.

Also fixed: re-running an experiment within a generation reused its run id
and overwrote the earlier run's files. The originals were restored from git
and the new runs renumbered r3–r4 (commit "never reuse a run id").
