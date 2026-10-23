# Leaderboard

Protocol 2.0, epoch 1 (DESIGN.md). Champion: **passonce**. Every number is the median of 3 repeats at the workload's headline load, from the latest session in which the policy ran there; a deadline kind's p99 is also given as a multiple of its deadline (x0.80 = 20% to spare, x1.50 = 50% over). Rejected policies are left out; their cards and data remain.

## Does anything improve on the champion?

| Workload | Headline (req/s) | Session | Result |
|---|---|---|---|
| w1 | 400000 | 20261023-044335 | HELD against duefirst |
| w2 | 202000 | 20261023-044556 | HELD against duefirst |
| w3 | 299000 | 20261023-044815 | HELD against duefirst |
| w4 | 240000 | 20261023-045038 | HELD against duefirst |
| w5 | 400000 | 20261023-045258 | HELD against duefirst |
| w6 | 202000 | 20261023-045517 | HELD against duefirst |

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
| passonce (champion) | 20261023-044335 | 52.0 / 128 (x0.87) | 121 / 308 | 398708 |

![short p99 by offered load on w1](plots/w1-load.svg)

## w2: A fan-out leaf serving the same fetch under two budgets

[workloads/w2-fanout-leaf-two-budgets.json](workloads/w2-fanout-leaf-two-budgets.json). A leaf server in a fan-out RPC tree serves one document fetch to two callers. The frontend calls it directly with most of the page budget left (due in 800 us). An aggregator sends the same fetch to every leaf and must wait for the slowest, so it passes down a tight remaining budget (due in 130 us). Both fetches do the same work (about 37 us) and both are latency-critical, so neither class nor length separates them; only the propagated budget does. The server also answers load-balancer health checks (high class, tiny, no deadline) and runs export steps (normal) and index-rebuild steps (low) chunked to a fetch's size. At 0.85-0.9 of capacity, first-come-first-served queueing alone pushes the fetches' p99 past the aggregator's budget while the frontend's budget stays comfortably met. The question for a policy is whether it can meet the aggregator's budget without raising the frontend reads' tail.

Headline load: 202,000 req/s.

| Policy | Session | read p99 / p99.9 (x of 800 us) | subreq p99 / p99.9 (x of 130 us) | health p99 / p99.9 | export p99 / p99.9 | rebuild p99 / p99.9 | Responses/s |
|---|---|---|---|---|---|---|---|
| fifo | 20261023-003837 | 184 / 349 (x0.23) | 187 / 341 (x1.44) | 144 / 296 | 183 / 341 | 186 / 333 | 201056 |
| prio | 20261023-021319 | 179 / 320 (x0.22) | 179 / 318 (x1.38) | 136 / 275 | 248 / 488 | 249 / 515 | 200676 |
| passonce (champion) | 20261023-044556 | 171 / 312 (x0.21) | 172 / 312 (x1.32) | 136 / 286 | 233 / 487 | 238 / 517 | 200705 |

![subreq p99 by offered load on w2](plots/w2-load.svg)

## w3: A search leaf: type-ahead suggestions beside full searches

[workloads/w3-search-leaf-suggest-vs-search.json](workloads/w3-search-leaf-suggest-vs-search.json). A search leaf serves two user-facing kinds that differ in both cost and budget. Type-ahead suggestions arrive on keystrokes, cost about 6 us and are due in 60 us, because a suggestion is useless once the next keystroke arrives. Full searches from the results page cost six times more (about 37 us) and are due in 200 us. Both are latency-critical, so the class hint does not separate them; only the budget and the expected run time do. The leaf also applies index updates (normal) and runs background segment merges (low), both chunked to steps below the runtime's time slice. At 0.85-0.9 of capacity, first-come-first-served queueing pushes the suggestions' p99 to about twice their budget while the searches stay within theirs, with little to spare at the top level. The question for a policy is whether it can run suggestions ahead of queued searches without raising the searches' tail.

Headline load: 299,000 req/s.

| Policy | Session | suggest p99 / p99.9 (x of 60 us) | search p99 / p99.9 (x of 200 us) | index p99 / p99.9 | merge p99 / p99.9 | Responses/s |
|---|---|---|---|---|---|---|
| fifo | 20261023-010732 | 135 / 292 (x2.25) | 167 / 320 (x0.83) | 148 / 303 | 165 / 320 | 297647 |
| prio | 20261023-021542 | 129 / 275 (x2.15) | 161 / 301 (x0.81) | 203 / 475 | 233 / 528 | 297580 |
| passonce (champion) | 20261023-044815 | 92.0 / 230 (x1.53) | 155 / 304 (x0.78) | 187 / 434 | 214 / 496 | 298154 |

![suggest p99 by offered load on w3](plots/w3-load.svg)

## w4: A storage node: expensive tight-budget reads beside cheap loose-budget appends, with flushes and compactions behind

[workloads/w4-storage-node-reads-vs-appends.json](workloads/w4-storage-node-reads-vs-appends.json). A replica of a log-structured storage node serves two client-facing kinds. Point reads consult the memtable and several on-disk tables, cost about 37 us and are due in 130 us, because they sit on the page-render path with most of the page budget already spent upstream. Log appends only write the commit log and the memtable, cost about 10 us and are due in 300 us, because a write's end-to-end time is dominated by durability and replication and the client tolerates more of it. Both are latency-critical, so the class hint does not separate them; the expected run time and the budget do, and they point the same way: the costlier kind is the one with less time. The node also flushes memtables to disk (normal) and compacts tables (low), chunked to steps below the runtime's time slice; together they are about a third of the work, the share compaction takes in a log-structured store. At 0.85-0.9 of capacity, first-come-first-served queueing pushes the reads' p99 past their budget while the appends stay far inside theirs. The question for a policy is whether the appends' cheapness and slack can be used at all: running appends ahead of reads costs the reads, and running reads ahead of appends gains them little.

Headline load: 240,000 req/s.

| Policy | Session | read p99 / p99.9 (x of 130 us) | append p99 / p99.9 (x of 300 us) | flush p99 / p99.9 | compact p99 / p99.9 | Responses/s |
|---|---|---|---|---|---|---|
| fifo | 20261023-013951 | 188 / 360 (x1.45) | 159 / 331 (x0.53) | 189 / 357 | 201 / 369 | 239325 |
| prio | 20261023-013951 | 156 / 278 (x1.20) | 127 / 249 (x0.42) | 213 / 429 | 248 / 509 | 239028 |
| passonce (champion) | 20261023-045038 | 154 / 285 (x1.18) | 97.0 / 215 (x0.32) | 209 / 427 | 243 / 500 | 238738 |

![read p99 by offered load on w4](plots/w4-load.svg)

## w5: Key-value lookups and range reads under two budgets, behind long requests

[workloads/w5-lookups-ranges-two-budgets.json](workloads/w5-lookups-ranges-two-budgets.json). w1's key-value server with its second user-facing read. Point lookups (20% of requests, about 2 us) are HIGH and due in 60 us, as in w1. Range reads (30%), which return the first entries of a key's list and cost ten lookups' work (about 21 us), are HIGH too and due in 100 us: more time than a lookup, but not ten times more. The remaining 50% are w1's long NORMAL requests, still the bulk of the work. Under first-come-first-served both reads queue behind the long requests and miss their budgets at the top level. A priority order skips the long requests, but inside HIGH it runs the oldest thread first, so a lookup still waits behind the range reads that arrived before it, which now carry over a third of the work. The two HIGH kinds differ in both cost and budget: running lookups ahead of queued range reads saves each lookup about 21 us per range passed and costs each range read 2-3 us, and the budgets say when a range read can no longer afford it. The question for a policy is how much of the lookups' queueing inside HIGH it can recover without raising the range reads' tail.

Headline load: 400,000 req/s.

| Policy | Session | lookup p99 / p99.9 (x of 60 us) | range p99 / p99.9 (x of 100 us) | long p99 / p99.9 | Responses/s |
|---|---|---|---|---|---|
| fifo | 20261023-022546 | 99.0 / 272 (x1.65) | 119 / 289 (x1.19) | 121 / 292 | 398536 |
| prio | 20261023-022546 | 70.0 / 176 (x1.17) | 89.0 / 208 (x0.89) | 146 / 367 | 398781 |
| passonce (champion) | 20261023-045258 | 54.0 / 158 (x0.90) | 84.0 / 206 (x0.84) | 123 / 360 | 398826 |

![lookup p99 by offered load on w5](plots/w5-load.svg)

## w6: A fan-out leaf serving the same fetch under two budgets, with requests arriving in 1 ms waves

[workloads/w6-fanout-leaf-short-bursts.json](workloads/w6-fanout-leaf-short-bursts.json). w2's leaf server in a fan-out RPC tree, now with bursty arrivals. One document fetch (about 37 us) is served to two callers: the frontend, which calls it directly with most of the page budget left (due in 800 us), and an aggregator that sends the same fetch to every leaf and must wait for the slowest, so it passes down a tight remaining budget (due in 130 us). Both are latency-critical and cost the same, so only the propagated budget separates them; health checks (high, tiny, no deadline), export steps (normal) and index-rebuild steps (low) share the server. The traffic now comes in waves: for the first quarter of every millisecond the client sends at 1.6 times the average rate and at 0.8 times for the rest, so at the two busiest levels every core ends each wave with about three fetches queued and spends roughly half of every millisecond working off a backlog. Under first-come-first-served a sub-request that arrives late in a wave waits behind that backlog and misses its budget by more than twice; the frontend reads wait exactly as long but keep three fifths of theirs. The order inside the HIGH class is now a decision with a price: running the aggregator's fetches ahead of queued frontend fetches moves each wave's backlog from the sub-requests' tail onto the reads' tail, one fetch at a time, and the no-regression rule allows the reads' tail to move by far less than one fetch. The question for a policy is how much of the sub-requests' burst penalty it can recover inside that allowance.

Headline load: 202,000 req/s.

| Policy | Session | read p99 / p99.9 (x of 800 us) | subreq p99 / p99.9 (x of 130 us) | health p99 / p99.9 | export p99 / p99.9 | rebuild p99 / p99.9 | Responses/s |
|---|---|---|---|---|---|---|---|
| fifo | 20261023-024717 | 296 / 429 (x0.37) | 296 / 425 (x2.28) | 254 / 384 | 293 / 419 | 299 / 429 | 200937 |
| prio | 20261023-024717 | 280 / 395 (x0.35) | 279 / 396 (x2.15) | 245 / 370 | 419 / 600 | 433 / 609 | 201107 |
| passonce (champion) | 20261023-045517 | 276 / 401 (x0.34) | 276 / 400 (x2.12) | 237 / 358 | 415 / 610 | 422 / 642 | 201153 |

![subreq p99 by offered load on w6](plots/w6-load.svg)
