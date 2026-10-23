# Generation 5 (loop 2): w6, the fan-out leaf in 1 ms waves, and p6 duefirst

## What happened
1. **Workload w6** (RPC leaf, bursts: short): w2 with 1 ms waves. Gate at
   202k (fifo, prio, passonce interleaved): sub-requests ×2.28 / ×2.15 / ×2.18
   of their 130 µs budget, reads ×0.35–0.37 of 800 µs. The champion decides as
   prio here, since both fetches hint 37 µs.
2. **Report:** a tail sub-request waits 204 µs in the run queue, 72 behind
   reads and 132 behind other sub-requests; the read directly ahead of it is
   itself a tail read, so any pass that helps the sub-requests' p99 charges
   the reads' p99 a full fetch against the 14 µs the rule allows. No order
   inside the class can be accepted on w6 or w2 as the rules stand.
3. **Policy p6 duefirst** (no constants, no state): among class-mates of
   equal hinted run time, the earlier-due one takes the turn; passonce's
   pass is unchanged where costs differ. Measured as evidence of the
   deadline order's price. **Rejected, as predicted:** sub-requests −17% on
   w6 and −15% on w2, reads +26% and +22%; w1, w3, w4, w5 identical.

## What this says
- **The deadline order works and the rule forbids it.** On w2 and w6 it
  takes the sub-requests from ×1.32 to ×1.13 and from ×2.12 to ×1.76 of their
  budget, while the reads move from ×0.21 to ×0.26 and from ×0.34 to ×0.43 of
  theirs. Every request still meets far more of its budget than before on
  the kind that was missing it. The no-regression rule counts the reads'
  +22–26% as a regression regardless of budget.
- This is the third generation whose verdict was decided by protecting a
  kind far inside its budget (w4's appends in gen 3; w4's background p99.9
  in gen 4 was noise). The rule, not the policies, is the limit now.

## Orchestrator notes
- The evaluation's last step crashed: I had copied w10's spec into
  workloads/ for its gate check at the moment eval_policy.sh planned its
  runs, and removed it before run.py reached it. All of w0–w6 had been
  measured; the verdict comes from `judge.py accept --policy duefirst
  --newest w6` on those rows. Lesson: never touch workloads/ while an
  evaluation is running.
- Gated and ready, not yet committed: w7 (search leaf, exponential-cost
  suggestions), w8 (storage node, stale append hint), w9 (key-value in
  waves), w10 (search leaf in waves). The w11 draft (three budgets) was cut
  off by the session limit.
- Node time: gate 9 min, evaluation 21 min.
