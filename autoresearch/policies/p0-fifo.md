# p0: fifo

- id: p0
- config: fifo
- generation: 0
- status: baseline
- builds_on: none
- changed_from_previous: Stock Caladan order: always run the thread that became ready first; hints are ignored.
- commit: 2ce9967

## What it does
Each core runs its ready threads strictly in the order they became ready,
whatever their hints say. This is exactly what Caladan does without any of our
changes, so it is the baseline every other policy is compared against.

## Why (hypothesis)
Not a hypothesis: a reference point. A request that becomes ready behind slower
ones must wait for all of them, which is the cost the other policies try to cut.

## Cost
None beyond stock Caladan, apart from the measurement counters in the
hint-enabled build (checked by workload w0 against the stock build).

## Results
See LEADERBOARD.md (every workload) and results/gen0/.
