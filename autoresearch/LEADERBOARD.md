# Leaderboard

Protocol 2.0, epoch 1 (DESIGN.md). Champion: **passonce**. Every number is the median of 3 repeats at the workload's headline load, from the latest session in which the policy ran there; a deadline kind's p99 is also given as a multiple of its deadline (x0.80 = 20% to spare, x1.50 = 50% over). Rejected policies are left out; their cards and data remain.

## Does anything improve on the champion?

| Workload | Headline (req/s) | Session | Result |
|---|---|---|---|
| w1 | 400000 | 20261023-021054 | HELD against prio |
| w2 | 202000 | 20261023-021319 | HELD against prio |
| w3 | 299000 | 20261023-021542 | HELD against prio |

## Plots

![p99 / deadline of the most stressed kind](plots/ratio.svg)

## w0: One request kind, no hints: overhead check

[workloads/w0-single-normal.json](workloads/w0-single-normal.json). Every request is the same long kind and gets no hints. No policy can help here, so any difference between policies, or between the hint-enabled build and stock Caladan, is pure overhead of the scheduling machinery. Every new policy is checked against this workload.

Headline load: 350,000 req/s.

| Policy | Session | req p99 / p99.9 | Responses/s |
|---|---|---|---|
| fifo | 20261023-003528 | - / - | - |

## w1: Short latency-critical requests behind long ones

[workloads/w1-short-high-vs-long.json](workloads/w1-short-high-vs-long.json). 20% of requests are short and latency-critical; the server marks them HIGH with a 60 us deadline. The other 80% are about ten times longer and stay NORMAL. Under FIFO a short request that arrives behind long ones waits for them, so its tail latency is set by the long requests. This is the simplest case where a priority hint should help.

Headline load: 400,000 req/s.

| Policy | Session | short p99 / p99.9 (x of 60 us) | long p99 / p99.9 | Responses/s |
|---|---|---|---|---|
| fifo | 20261023-002655 | 93.0 / 257 (x1.55) | 113 / 284 | 398527 |
| prio | 20261023-021054 | 53.0 / 133 (x0.88) | 116 / 308 | 398656 |
| passonce (champion) | 20261023-021054 | 53.0 / 129 (x0.88) | 118 / 296 | 398295 |

![short p99 by offered load on w1](plots/w1-load.svg)

## w2: A fan-out leaf serving the same fetch under two budgets

[workloads/w2-fanout-leaf-two-budgets.json](workloads/w2-fanout-leaf-two-budgets.json). A leaf server in a fan-out RPC tree serves one document fetch to two callers. The frontend calls it directly with most of the page budget left (due in 800 us). An aggregator sends the same fetch to every leaf and must wait for the slowest, so it passes down a tight remaining budget (due in 130 us). Both fetches do the same work (about 37 us) and both are latency-critical, so neither class nor length separates them; only the propagated budget does. The server also answers load-balancer health checks (high class, tiny, no deadline) and runs export steps (normal) and index-rebuild steps (low) chunked to a fetch's size. At 0.85-0.9 of capacity, first-come-first-served queueing alone pushes the fetches' p99 past the aggregator's budget while the frontend's budget stays comfortably met. The question for a policy is whether it can meet the aggregator's budget without raising the frontend reads' tail.

Headline load: 202,000 req/s.

| Policy | Session | read p99 / p99.9 (x of 800 us) | subreq p99 / p99.9 (x of 130 us) | health p99 / p99.9 | export p99 / p99.9 | rebuild p99 / p99.9 | Responses/s |
|---|---|---|---|---|---|---|---|
| fifo | 20261023-003837 | 184 / 349 (x0.23) | 187 / 341 (x1.44) | 144 / 296 | 183 / 341 | 186 / 333 | 201056 |
| prio | 20261023-021319 | 179 / 320 (x0.22) | 179 / 318 (x1.38) | 136 / 275 | 248 / 488 | 249 / 515 | 200676 |
| passonce (champion) | 20261023-021319 | 183 / 343 (x0.23) | 180 / 336 (x1.38) | 145 / 300 | 255 / 553 | 259 / 534 | 200784 |

![subreq p99 by offered load on w2](plots/w2-load.svg)

## w3: A search leaf: type-ahead suggestions beside full searches

[workloads/w3-search-leaf-suggest-vs-search.json](workloads/w3-search-leaf-suggest-vs-search.json). A search leaf serves two user-facing kinds that differ in both cost and budget. Type-ahead suggestions arrive on keystrokes, cost about 6 us and are due in 60 us, because a suggestion is useless once the next keystroke arrives. Full searches from the results page cost six times more (about 37 us) and are due in 200 us. Both are latency-critical, so the class hint does not separate them; only the budget and the expected run time do. The leaf also applies index updates (normal) and runs background segment merges (low), both chunked to steps below the runtime's time slice. At 0.85-0.9 of capacity, first-come-first-served queueing pushes the suggestions' p99 to about twice their budget while the searches stay within theirs, with little to spare at the top level. The question for a policy is whether it can run suggestions ahead of queued searches without raising the searches' tail.

Headline load: 299,000 req/s.

| Policy | Session | suggest p99 / p99.9 (x of 60 us) | search p99 / p99.9 (x of 200 us) | index p99 / p99.9 | merge p99 / p99.9 | Responses/s |
|---|---|---|---|---|---|---|
| fifo | 20261023-010732 | 135 / 292 (x2.25) | 167 / 320 (x0.83) | 148 / 303 | 165 / 320 | 297647 |
| prio | 20261023-021542 | 129 / 275 (x2.15) | 161 / 301 (x0.81) | 203 / 475 | 233 / 528 | 297580 |
| passonce (champion) | 20261023-021542 | 98.0 / 228 (x1.63) | 162 / 294 (x0.81) | 200 / 424 | 232 / 511 | 298138 |

![suggest p99 by offered load on w3](plots/w3-load.svg)
