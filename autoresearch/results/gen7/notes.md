# Generation 7: syncs labelled as puts

## What happened

0. **p5 re-check** (orchestrator, before the workload): sjf_guard and
   sjf_learn alternated on a full w5 sweep. At 390k sjf_learn's get p99 was
   84.5 µs against 102.5 (−17.6%), with query deadline-met 86.83% against
   86.75% and puts equal. p5's gen 4 rejection was drift between sessions.
   The record stands as decided; p5's card has a "Re-check" section.
1. **Workload w8** (workload agent): w7 with one change in the server's hint
   map: syncs carry the puts' 1 µs run-time hint instead of a blank one, so
   syncs and puts have identical hints. Gate: PASS at 380k. fifo get p99
   210.5 µs; champion sjf_nohint 145.0 (116.5 on w7), because syncs ranked as
   1 µs puts run ahead of gets again (get wait p99 61.8 → 97.3 µs).
2. **Report** (measurement agent): per-hint learning (sjf_learn 89.5 µs,
   sjf_timed 96.5) separates gets from the mixed "1 µs" label but costs puts
   11–14 points of deadline-met: syncs inflate the shared estimate to the
   queries' level. On w5, where only puts carry that hint, it cost nothing.
   Top hypothesis: cap how far a learned length may rise above its hint.
3. **Policy p8 sjf_capped** (policy agent): p5's rules and timing, with
   learned lengths allowed below the hint (as in p6) but at most 8 µs above
   p5's starting value, a 17 µs length for a HIGH thread without a run-time
   hint, and slack measured with the same length. **Accepted**, improving on
   every workload: w8 −42.8% (83.0 µs), w7 −27.9%, w6 −42.3%, w5 −19.5%,
   w4b −12.8%; every deadline-carrying kind held or gained.

## Orchestrator changes this generation

- **Bug: the evaluation skipped older workloads.** The paired-confirmation
  rewrite of `eval_policy.sh` (gen 6) read its plan with a `while read` loop
  whose `run.py` calls also read stdin; their ssh sessions swallowed the
  rest of the plan after w0. p8's first evaluation therefore measured only
  w8 and w0, and the judge printed ACCEPT, because a missing older workload
  counted as a pass. Both are fixed: `run.py` gets no stdin in the loops, and
  missing data now fails a policy. w1–w7 were then measured for p8 and the
  verdict was re-derived from complete data. Gen 6's evaluation used the
  older script and was complete (its judge output lists every workload).
- **Plots in the leaderboard** (owner's request): a score map of every policy
  on every workload, each candidate against the champion it faced, and a
  latency-by-load curve per workload, written by `summarize.py` to `plots/`.

## Observations to keep

- **The learned-length idea was right twice.** p5 (gen 4) was a real win
  rejected by drift; p8 is p5 with its two flaws fixed (a floor that ranked
  w6's gets too long, and no limit on how long a mixed label may grow).
- **The policy region is near its limit for gets.** Get runqueue-wait p99 is
  about 25 µs on w5–w8 under p8, and get p99 about 81–84 µs everywhere. The
  remaining 55–60 µs is outside the runqueue: packets waiting on a busy core
  and running syncs that cannot be passed. Further large gains need the
  owner's hooks (preemption, packet processing while hinted threads wait).
- **Tuned constants.** p8's 8 µs cap and 17 µs blank length fit these
  workloads' hint values (2, 1, 17 µs); a workload with different scales
  could break them, which is a natural next test.

## Open requests for the owner

Unchanged: preemption; hint-aware stealing; packet processing on every
reschedule while hinted threads wait; exact run times from the scheduler;
learned-cost counters. New from p8's card: a learning key separate from the
run-time hint, so kinds that share a hint value can be learned apart.

## Node time

About 27 minutes, above the 25-minute cap: the p5 re-check (4 min), w8's
matrix (11 min), and p8's evaluation (11 min, including the re-run of the
older workloads after the bug).
