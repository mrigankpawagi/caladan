# p22: sjf_age (with variants sjf_age_mix and sjf_age_all)

- id: p22
- config: sjf_age (variants: sjf_age_mix, sjf_age_all)
- generation: 21
- status: not built
- builds_on: p19
- changed_from_previous: p19 plus: at a time unit of 1 (w1-w10), when p4's rescue does not fire and the order's choice is a HIGH thread with no run-time hint, the oldest waiting HIGH thread (deadline, not overrun, not too late) that became ready before it and has waited 20 us runs instead, if the choice keeps 40% of its window after it; variants hold back more threads (sjf_age_mix: labels hiding long work; sjf_age_all: every younger thread)
- commit: none (code kept in the orchestrator's scratchpad only)

## What it proposed
Aging for queries on the key-value workloads: once a request has waited 20 µs, a younger request whose run time the server cannot predict no longer jumps ahead of it. The variants widen who is held back, to measure how many points of query deadline-met each µs of get p99 buys.

## Why it was not built
The policy agent's own model, calibrated on the generation 19–20 same-session data, predicted no loss turned into a win: sjf_age changes decisions only on w7 (+1.0 to +1.3 points of query deadline-met against the 3.2 needed), and the variants trade gets or puts for queries beyond rules 2 and 6 (sjf_age_all: get p99 +22% to +48% for +0.3 to +0.8 points). While it was being written, the owner changed the win definition (generation 20): the query deadline-met gaps to prio on w4b–w12 no longer count as losses, and the champion now wins all of those workloads. The agent also proposed, and the orchestrator checked, that the gap to prio was the policy's own cost per pick; the measured scheduler share refutes it (sjf_tier 16.7% against prio's 16.8% on w5).
