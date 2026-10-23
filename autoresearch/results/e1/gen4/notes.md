# Generation 4 (loop 2): w5, lookups and range reads, and p5 absorb

## What happened
1. **Workload w5** (key-value, deadline spread: two budgets): w1 plus 21 µs
   range reads due in 100 µs beside the 2 µs lookups due in 60 µs, with the
   long NORMAL requests still 61% of the work. Gate at 400k, fifo, prio and
   the champion interleaved in one session: lookups ×1.65 / ×1.17 / ×0.93 of
   their budget under fifo / prio / passonce, range reads ×1.19 / ×0.89 /
   ×0.86. The champion brings both inside their budgets.
2. **Report:** a tail lookup under passonce waits about 17 µs in the run
   queue, less than one range read: the once-bound's residue, a lookup stuck
   behind a range read that an earlier lookup already passed. The floor is
   about 45–50 µs. The range reads cannot be moved by any order.
3. **Policy p5 absorb** (passonce plus a second pass while the passers
   absorbed stay within 25% of the passed thread's run time): on w5 the
   lookups improved as predicted (54 → 51, ×0.90 → ×0.85, ranges apart) with
   range reads and long requests unchanged; w3, w2, w1, w0 unchanged;
   **rejected** because w4's flush and compact p99.9 rose 6–7% with ranges
   apart, on a workload where the two policies make identical decisions.

## What this says
- The improvement on w5 is real and small, as the report said it would be:
  the lookups' remaining 51 µs is the running request and the packet wait.
- **The p99.9 rule on background kinds decided this generation on noise.**
  The flush p99.9 is the 32nd slowest of about 32,000 requests per run; it
  moved 7% between two policies that cannot differ on that workload. The
  verdict stands as written, and the rule is on the epoch review list:
  judge p99.9 for kinds with a deadline only, or widen its threshold.
- absorb's 25% is a fixed ratio, declared as such in its card; two lookups
  cost a range read 19%, two suggestions a search 32%, two appends a read
  54%, so the band is real but a workload built just outside it would find
  it.

## Orchestrator notes
- w6 (RPC leaf in 1 ms waves), w7 (search leaf, exponential suggestions),
  w8 (storage node, one append in seven hiding a 73 µs log roll under a
  10 µs hint) passed their gates during this generation. On w8 the stale
  hint costs the champion: reads ×1.47 against prio's ×1.31.
- Node time: gate 9 min (three policies), evaluation 25 min.
