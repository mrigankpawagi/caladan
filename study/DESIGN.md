# Scheduling hints in Caladan: study design

This study replaces the autoresearch loops (#5, #6). It answers the five
review comments on #5 one step at a time. Each step makes a prediction from
service times **before** anything runs, then checks it on the nodes.

## The five questions

| # | Question (from the review) | Answered by |
|---|---|---|
| Q1 | Is the cost of making scheduling decisions counted? | Step 2 (cycles per pick), W1 (end to end) |
| Q2 | How do policies interact with Caladan's load balancing across cores, and do they scale? | W5, Step 6 |
| Q3 | Are the policies explainable? | Every policy is one textbook rule; see below |
| Q4 | A handful of workloads explained by service times and expectations | W1–W5, each with a written prediction |
| Q5 | One best policy that is cheap to run and simple to understand | Step 7, chosen from the matrix |

## Policies

Each policy is one rule from the scheduling literature. Every policy runs
runtime helper threads (packets, timers) first, then applies its rule to the
local core's runqueue. No policy has a tuned constant.

| Policy | Rule | Known property |
|---|---|---|
| `fifo` | oldest ready thread first (stock Caladan) | baseline |
| `prio` | highest class first, oldest first within a class (#2) | Cobham's formula gives each class's mean wait |
| `sjf` | smallest hinted service time first; unknown counts as longest | minimises mean wait among non-preemptive orders |
| `edf` | earliest hinted deadline first; no deadline counts as latest | meets every deadline whenever any order does (Jackson's rule, all jobs present) |

At most one combination is added, and only if a step shows that no single
rule is enough. For example, class first and then EDF within a class.

**Complexity budget.** Each policy uses a single O(n) scan, has no state across
picks, and fits in 30 lines.

## Workloads

Service times below are in µs of handler work. Step 3 calibrates them
against the fakework loop on the nodes. Each prediction uses an approximation
that treats each core as one server; it is meant to give the order and rough
size of the effect, and the measured p99 is reported next to it.

- **ρ** is the utilisation.
- **R = λ·E[S²]/2** is the mean remaining work of the request already
  running.

Non-preemptive priority (Cobham's formula):
- the high class waits on average R / (1 − ρ_high);
- the low class waits on average R / ((1 − ρ_high)(1 − ρ)).

Under fifo, every request waits R / (1 − ρ) on average.

### W1: overhead (Q1)

- **Traffic:** one kind, zero work, no hints. A second run sets hints on
  every request.
- **Prediction:** runqueues stay 1–2 deep, so a pick scans almost nothing.
  Every policy's maximum throughput and p99 are within 5% of fifo.
- **What would change the plan:** a gap over 5%. Any policy with such a gap
  is too expensive for Q5.

### W2: head-of-line blocking (Q4)

- **Traffic:** 80% short requests (5 µs), 20% long requests (50 µs).
  - **2a:** hints give only the service time.
  - **2b:** hints give only the class (short = HIGH).
- **Prediction at ρ = 0.8:** E[S] = 14 µs and R = 14.9 µs.
  - Under fifo, everyone waits about 74 µs on average.
  - If short requests go first, they wait about 19 µs (3.9× less), and long
    ones about 96 µs (+30%).
  - In 2a, `sjf` gets the gain and `prio` behaves like fifo. In 2b it is the
    other way round.
  - `edf` behaves like fifo in both, because there are no deadlines.
  - The short requests' remaining wait is the long request already running,
    which no non-preemptive order removes.
- **The point:** a policy can only use the hint the application gives it.

### W3: equal work, different deadlines (Q4)

- **Traffic:** every request takes 10 µs.
  - 20% have a 50 µs deadline.
  - 80% have a 500 µs deadline.
  - Both kinds are HIGH, so `prio` cannot tell them apart.
- **Prediction at ρ = 0.8:**
  - The mean wait is fixed at about 20 µs under every order, because all
    requests are the same size (Kleinrock's conservation law). Reordering
    only moves waiting from one kind to the other.
  - Under fifo, the tight kind's p99 goes past 50 µs and misses its deadline.
  - Under `edf`, it waits only behind other tight requests and the one already
    running, so it meets its deadline. The loose kind's p99 rises but stays far
    inside 500 µs.
  - `sjf` and `prio` behave like fifo.
- **Score:** the share of requests that miss their deadline, measured at the
  client, and p99 ÷ deadline for each kind.

### W4: wrong hints (Q4, robustness)

- **Traffic:** W2a, but 10% of long requests claim to be short.
- **Prediction:**
  - The short requests now share their class with mislabelled long requests,
    so the short load goes from 0.23 to 0.29. Their mean wait rises only
    slightly (19.3 → 21 µs).
  - Their p99 rises more, because sometimes a 50 µs request runs right
    before them.
  - `sjf` degrades smoothly towards fifo and never becomes worse than fifo.

### W5: uneven load across cores (Q2)

- **Traffic:** W2b or W3 over few connections, so flow steering gives each
  core uneven arrivals. Run with 2, 4 and 8 kthreads.
- **How Caladan balances load today:**
  - An idle core steals the **oldest half** of a busy core's queue, by ready
    time, ignoring hints (`steal_work`, `merge_runqueues`).
  - The IOKernel grants cores based on the oldest thread's queueing delay,
    which also ignores hints.
- **Prediction:**
  - An urgent request that arrives on a busy core is young, so stealing leaves
    it behind.
  - It waits for that core's running request to finish (up to 50 µs in W2)
    even while another core is idle.
  - Per-core policies cannot fix this. The extra wait shows up as hinted
    threads that wait while some core is idle.
- **Step 6** then tests one change, and only that change: a stealing core
  takes the thread its own policy would pick first, instead of the oldest
  half.
  - Prediction: the urgent kind's p99 drops by about the long request's
    service time.
  - Nothing else changes, because stealing still happens only when a core is
    idle.

## Method

- **Testbed:** two CloudLab Utah nodes: E5-2640 v4 (10 cores), ConnectX-4 Lx.
  The server runs on node0 with the IOKernel and 4 kthreads unless stated
  otherwise; the client runs on node1.
- **Repeats and drift:** each comparison runs at least 3 repeats, with every
  policy interleaved in one session. fifo is re-run each session so drift
  between sessions shows up.
- **Threshold:** a difference counts only if it is beyond 5%.
- **Preemption:** Caladan preempts a thread that runs past its quantum
  (`runtime_quantum_us`, 100 µs) while others wait. Every service time here
  is well below that, so a running request finishes before anything else
  runs, and the non-preemptive formulas apply.
- **What is measured:** client-side latency per kind (p50, p99, p99.9),
  deadline misses, and throughput. Server counters are used only after
  checking them against the client's numbers.
- **What is reported:** p99 and p99 ÷ deadline per kind at each load, plus the
  cycles per pick.

## Steps

Each step is one commit with its own result. I stop for review after each
step.

1. This note.
2. A cycle counter around the pick and a microbenchmark of pick cost against
   runqueue depth, for each policy (Q1).
3. Node setup, calibration of µs to fakework iterations, and a noise check
   (fifo, 3 repeats, twice).
4. W1, then W2, W3, W4, one per step: each run against its prediction.
5. W5: measure how stealing treats urgent threads.
6. Hint-aware stealing, as one isolated change.
7. Choose the best policy and write a short report for the review.
