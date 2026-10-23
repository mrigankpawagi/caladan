# Leaderboard

Protocol 2.0, epoch 1 (DESIGN.md). Champion: **passonce**. Every number is the median of 3 repeats at the workload's headline load, from the latest session in which the policy ran there; a deadline kind's p99 is also given as a multiple of its deadline (x0.80 = 20% to spare, x1.50 = 50% over). Rejected policies are left out; their cards and data remain.

## Does anything improve on the champion?

| Workload | Headline (req/s) | Session | Result |
|---|---|---|---|
| w1 | 400000 | 20261023-030204 | HELD against afford |
| w2 | 202000 | 20261023-030427 | HELD against afford |
| w3 | 299000 | 20261023-030650 | HELD against afford |
| w4 | 240000 | 20261023-030912 | HELD against afford |

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
| passonce (champion) | 20261023-030204 | 52.0 / 132 (x0.87) | 115 / 295 | 398046 |

![short p99 by offered load on w1](plots/w1-load.svg)

## w2: A fan-out leaf serving the same fetch under two budgets

[workloads/w2-fanout-leaf-two-budgets.json](workloads/w2-fanout-leaf-two-budgets.json). A leaf server in a fan-out RPC tree serves one document fetch to two callers. The frontend calls it directly with most of the page budget left (due in 800 us). An aggregator sends the same fetch to every leaf and must wait for the slowest, so it passes down a tight remaining budget (due in 130 us). Both fetches do the same work (about 37 us) and both are latency-critical, so neither class nor length separates them; only the propagated budget does. The server also answers load-balancer health checks (high class, tiny, no deadline) and runs export steps (normal) and index-rebuild steps (low) chunked to a fetch's size. At 0.85-0.9 of capacity, first-come-first-served queueing alone pushes the fetches' p99 past the aggregator's budget while the frontend's budget stays comfortably met. The question for a policy is whether it can meet the aggregator's budget without raising the frontend reads' tail.

Headline load: 202,000 req/s.

| Policy | Session | read p99 / p99.9 (x of 800 us) | subreq p99 / p99.9 (x of 130 us) | health p99 / p99.9 | export p99 / p99.9 | rebuild p99 / p99.9 | Responses/s |
|---|---|---|---|---|---|---|---|
| fifo | 20261023-003837 | 184 / 349 (x0.23) | 187 / 341 (x1.44) | 144 / 296 | 183 / 341 | 186 / 333 | 201056 |
| prio | 20261023-021319 | 179 / 320 (x0.22) | 179 / 318 (x1.38) | 136 / 275 | 248 / 488 | 249 / 515 | 200676 |
| passonce (champion) | 20261023-030427 | 177 / 322 (x0.22) | 179 / 332 (x1.38) | 143 / 301 | 250 / 500 | 256 / 552 | 201316 |

![subreq p99 by offered load on w2](plots/w2-load.svg)

## w3: A search leaf: type-ahead suggestions beside full searches

[workloads/w3-search-leaf-suggest-vs-search.json](workloads/w3-search-leaf-suggest-vs-search.json). A search leaf serves two user-facing kinds that differ in both cost and budget. Type-ahead suggestions arrive on keystrokes, cost about 6 us and are due in 60 us, because a suggestion is useless once the next keystroke arrives. Full searches from the results page cost six times more (about 37 us) and are due in 200 us. Both are latency-critical, so the class hint does not separate them; only the budget and the expected run time do. The leaf also applies index updates (normal) and runs background segment merges (low), both chunked to steps below the runtime's time slice. At 0.85-0.9 of capacity, first-come-first-served queueing pushes the suggestions' p99 to about twice their budget while the searches stay within theirs, with little to spare at the top level. The question for a policy is whether it can run suggestions ahead of queued searches without raising the searches' tail.

Headline load: 299,000 req/s.

| Policy | Session | suggest p99 / p99.9 (x of 60 us) | search p99 / p99.9 (x of 200 us) | index p99 / p99.9 | merge p99 / p99.9 | Responses/s |
|---|---|---|---|---|---|---|
| fifo | 20261023-010732 | 135 / 292 (x2.25) | 167 / 320 (x0.83) | 148 / 303 | 165 / 320 | 297647 |
| prio | 20261023-021542 | 129 / 275 (x2.15) | 161 / 301 (x0.81) | 203 / 475 | 233 / 528 | 297580 |
| passonce (champion) | 20261023-030650 | 104 / 236 (x1.73) | 167 / 303 (x0.83) | 213 / 463 | 243 / 518 | 298305 |

![suggest p99 by offered load on w3](plots/w3-load.svg)

## w4: A storage node: expensive tight-budget reads beside cheap loose-budget appends, with flushes and compactions behind

[workloads/w4-storage-node-reads-vs-appends.json](workloads/w4-storage-node-reads-vs-appends.json). A replica of a log-structured storage node serves two client-facing kinds. Point reads consult the memtable and several on-disk tables, cost about 37 us and are due in 130 us, because they sit on the page-render path with most of the page budget already spent upstream. Log appends only write the commit log and the memtable, cost about 10 us and are due in 300 us, because a write's end-to-end time is dominated by durability and replication and the client tolerates more of it. Both are latency-critical, so the class hint does not separate them; the expected run time and the budget do, and they point the same way: the costlier kind is the one with less time. The node also flushes memtables to disk (normal) and compacts tables (low), chunked to steps below the runtime's time slice; together they are about a third of the work, the share compaction takes in a log-structured store. At 0.85-0.9 of capacity, first-come-first-served queueing pushes the reads' p99 past their budget while the appends stay far inside theirs. The question for a policy is whether the appends' cheapness and slack can be used at all: running appends ahead of reads costs the reads, and running reads ahead of appends gains them little.

Headline load: 240,000 req/s.

| Policy | Session | read p99 / p99.9 (x of 130 us) | append p99 / p99.9 (x of 300 us) | flush p99 / p99.9 | compact p99 / p99.9 | Responses/s |
|---|---|---|---|---|---|---|
| fifo | 20261023-013951 | 188 / 360 (x1.45) | 159 / 331 (x0.53) | 189 / 357 | 201 / 369 | 239325 |
| prio | 20261023-013951 | 156 / 278 (x1.20) | 127 / 249 (x0.42) | 213 / 429 | 248 / 509 | 239028 |
| passonce (champion) | 20261023-030912 | 164 / 286 (x1.26) | 104 / 223 (x0.35) | 213 / 412 | 259 / 511 | 239048 |

![read p99 by offered load on w4](plots/w4-load.svg)
