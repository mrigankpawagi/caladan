# Study design, version 2 (pre-registered)

This note was committed **before** any v2 measurement run. It revises
[DESIGN.md](DESIGN.md) after three independent reviews of #4 and #7. Everything below (metrics,
SLOs, load grid, decision rule, predictions) is fixed now. Any later change is
listed in the report with its reason. Version 1's results stay in the record
as written. The report says which v1 claims were wrong and why.

## What changed, and why

| v1 problem (found in review) | v2 change |
|---|---|
| `hinted` equalled the single rules by construction on W2a/W2b/W3/W4, and `sjf` was the same algorithm as `prio` (hints are per request kind) | The policies are a **ladder**. Each reads one more hint, and each rung only breaks ties the rung below leaves. `sjf` is dropped. The tie cells are predicted below as ties, and are never counted as wins. |
| `hinted` cost about 2× a single rule, which failed v1's own 5% cost rule | Each thread's hints are packed once into a **64-bit sort key**. Every policy compares a prefix of it, so all cost the same. |
| W6's metric was switched relative to W3, and `edf` tied `hinted` on misses | **One metric, fixed in advance (SLO-load).** W6 is redesigned so that class and deadline genuinely conflict. |
| W1 "capacity" was goodput during collapse | **Knee search**: a fresh server per level, 10 s levels, a 40 k grid, and the stock build interleaved in the same session |
| The wait split was a residual, and its attribution was asserted | **Per-request timestamps** on one shared TSC: client send, server enqueue, handler start and end, client receive, plus the queueing and running kthreads |
| Pooled predictions were added after the v1 runs; ρ was nominal; the clock floated (schedutil, turbo) | Predictions are below, committed before the runs. ρ uses the **in-place handler times**. The **clock is pinned** at 2.4 GHz with no turbo. |
| Q2 never exercised core counts or the IOKernel's core allocation | **W5**: 2, 4 and 6 cores, plus 2 guaranteed and 2 burstable cores next to a best-effort batch job |
| `softirq_first` acted only in the slow path; the v1 W5-quantum explanation was wrong (`thread_yield` does process packets) | `softirq_first` now also acts on the fast path, but only while the ring has room. `+rx` is a second factor on W2b, W3 and W6. |

## Policies: a ladder plus one foil

Each thread's key is `class (2 bits) | deadline in µs (42) | service time in µs (20)`. A missing hint sorts last.

| policy | compares | reads |
|---|---|---|
| `fifo` | nothing (earliest ring slot) | no hint (stock order) |
| `prio` | class | importance |
| `prio_edf` | class, then deadline | + urgency |
| `hinted` | class, then deadline, then size | + size |
| `edf` (foil) | deadline only | urgency, not importance |

`stock` is fifo on a build with hints compiled out; it appears only in W1. `+rx` turns on `runtime_sched_softirq_first`, which processes arrived packets before the runqueue.

## Testbed and calibration

- **Node.** One CloudLab xl170 (hp070). The server and the client share it through the IOKernel's loopback. With `ias noht`, they get 8 cores (2–9) with no shared hyperthreads.
- **Clock.** Pinned at 2.4 GHz: performance governor, turbo off. The TSC is invariant on a single socket, so client and server timestamps are directly comparable.
- **Work loop.** The sqrt loop does 318.99 iterations per µs (three calibrations agree within 0.003%).
- **Handler times.** Measured in place (session `cal`): 1.22, 5.225, 10.235 and 50.26 µs for nominal 1, 5, 10 and 50 µs.
- **Load.** ρ = offered rate × mean handler time / cores. The offered rate at each level is the same for every policy.
- **Busy fraction.** Packet processing runs on the server cores too, so the busy fraction exceeds ρ: at ρ = 0.95, program time is 97.5% of kthread time. The grid therefore stops at 0.9.
- **Client headroom.** The client keeps up with every planned rate. Its lag stays at −4 µs (sends slightly early) even with 2 client threads at 400 k req/s.

## Metric

**SLO-load.** For each policy: the highest ρ at which every *scored* kind's p99 is at or below its SLO, interpolated linearly on p99/SLO between grid points. A result above the top of the grid is reported as "≥ 0.9".

**SLOs.**
- Where a kind has a deadline, its SLO is that deadline.
- Otherwise its SLO is the largest service time plus 10× the kind's own (short 5 µs: 100 µs; long 50 µs: 550 µs).

**Scored kinds.** The HIGH kinds where the workload uses classes; otherwise every kind. The unscored kinds are the **price**, reported as their p99 against fifo's at ρ = 0.85 and 0.9.

**Secondary measures.**
- Mean waits per kind, against the predictions below.
- The per-request time split (mean, and the mean over the slowest 1%).
- The share of handlers stolen.

**Cost.**
- **W1 knee:** the highest offered load at which every repeat has zero drops and p99 ≤ 70 µs. That is 10× the 7 µs p99 at light load in v1.
- **Per-pick cycles:** pickbench, and one stats-on session.

**Grid and repeats.**
- ρ ∈ {0.5, 0.6, 0.7, 0.8, 0.85, 0.9}, 3 repeats.
- Every repeat runs every configuration once, in a seeded, recorded shuffled order. Failed levels are recorded as rows.

**Decision rule.** A difference between two configurations counts only if all three paired ratios agree, each taken within one repeat, and each lies beyond ±5% on the same side. Otherwise the two are reported as a tie. The v1 noise check measured ≤ 2% at ρ ≤ 0.8 and 3.4% at 0.9.

## Workloads and pre-registered predictions

Mean waits predicted at ρ = 0.9, from `analyze.predictions()` with the handler times above. Each pair is pooled M/G/4 / per-core M/G/1. v1 measured the truth between the two, close to pooled for fifo and in between for priority orders.

### W2b: class only

- **Traffic:** short requests 5 µs, HIGH, 80%; long requests 50 µs, NORMAL. Scored: short (SLO 100 µs).
- **Ladder:** `prio` = `prio_edf` = `hinted` by construction (no deadlines, no sizes). `edf` = `fifo` (no deadlines).
- **SLO-load:** `fifo` = `edf` ≈ 0.75–0.85 < `prio`-family ≥ 0.9.
- **Mean waits:**

| policy | short | long |
|---|---|---|
| fifo | 36.5 / 167 | 36.5 / 167 |
| prio-family | 5.0 / 23 | 49.6 / 227 |

- **Price:** long p99 +10–30% over fifo.

### W3: deadline within a class

- **Traffic:** 10 µs, all HIGH. Tight: due in 50 µs, 20%. Loose: due in 500 µs. Both scored.
- **Ladder:** `fifo` = `prio` (one class). `prio_edf` = `hinted` = `edf` (equal sizes, and a single class means class adds nothing).
- **SLO-load:** `fifo`/`prio` ≈ 0.8–0.85 < `prio_edf`/`hinted`/`edf` ≈ 0.85–0.9. With `+rx`, the deadline-aware rules reach ≥ 0.9.
- **Mean waits:**

| policy | tight | loose |
|---|---|---|
| fifo/prio | 10.1 / 46 | 10.1 / 46 |
| deadline-aware | 1.2 / 6 | 12.3 / 56 |

- **Conservation:** the traffic-weighted mean wait is the same for every policy within 5%.

### W2a: size only

- **Traffic:** short 5 µs and long 50 µs, both NORMAL, no deadlines. Both scored (SLOs 100 and 550 µs).
- **Ladder:** only `hinted` separates. `fifo` = `prio` = `prio_edf` = `edf`.
- **SLO-load:** the four tie ≈ 0.75–0.85 < `hinted` ≥ 0.9.
- **Mean waits:** short 36.5 → 5.0 (pooled) under `hinted`.

### W4: wrong sizes

- **Traffic:** W2a, but 10% of long requests claim 5 µs ("liar").
- **Ladder:** as W2a.
- **Prediction:** `hinted` keeps most of its W2a gain. Short-request mean wait is 5.4 µs pooled (5.0 in W2a). Its SLO-load stays ≥ 0.9, or falls by at most one grid step. It never drops below fifo.

### W6: every hint given; class and deadline disagree

- **Traffic:**
  - tight: 5 µs, HIGH, due in 50 µs, 20%;
  - loose: 5 µs, HIGH, due in 200 µs, 60%;
  - bulk: 50 µs, NORMAL, due in 150 µs, 20%.

  Scored: tight and loose. Price: bulk.
- **Ladder and predictions:**
  - **`prio`** separates HIGH from bulk but not tight from loose, so tight misses.
  - **`prio_edf`** adds that separation.
  - **`hinted` = `prio_edf`:** the null rung. Once every thread has a deadline, size never decides. This is predicted as a tie.
  - **`edf`** runs bulk (due 150 µs) before loose (due 200 µs), so loose waits behind 50 µs bulk runs.
- **SLO-load:** `fifo` < `prio` < `prio_edf` = `hinted`; `edf` < `prio_edf`.
- **Mean waits:**

| policy | tight | loose | bulk |
|---|---|---|---|
| prio | 5.0 / 23 | 5.0 / 23 | 49.6 / 227 |
| prio_edf = hinted | 3.9 / 18 | 5.3 / 24 | 49.6 / 227 |
| edf, as a fixed order | 3.9 / 18 | up to 122 / 559 | 13.1 / 60 |

- **The `edf` loose value is an upper bound.** Real EDF lets a loose request that has waited more than 50 µs pass a newly arrived bulk request.

### W5: cores and the IOKernel (Q2)

- **Traffic:** W2b's traffic. Policies: `fifo`, `prio`, `hinted`, `hinted+rx`.
- **Variants, same ρ:** 2, 4 and 6 cores.
  - **Prediction:** fifo's short-request wait falls as cores grow (pooling).
  - The *absolute* gain of ordering shrinks with more cores, while `hinted`'s short wait approaches the floor set by the job already running on its own core.
  - The share of handlers stolen rises with more cores.
- **Variant `burst`:** 2 guaranteed + 2 burstable cores, a 2-thread client, and a 6-thread best-effort batch job. ρ is relative to 4 cores.
  - **Prediction:** under `prio`/`hinted`, the oldest queued thread is a bypassed NORMAL long request. So the IOKernel's congestion signal (the oldest thread's age) is higher.
  - The server therefore takes more cores, and the batch job's work rate is ≥ 5% lower than under `fifo` at ρ ≥ 0.6.
  - The short-request gain is preserved.

### W1: cost

- **Traffic:** 1 µs requests on 2 cores. Every thread carries identical hints, so every pick scans the full ring.
- **Prediction:**
  - **Knee order:** `stock` > `fifo` (−2 to −4%, the cost of carrying hints).
  - **Sort-key policies:** `prio` = `prio_edf` = `hinted` = `edf` within 1% of each other (v1: `hinted` cost 2× the others), each within 5% of `fifo`.
  - **`hinted+rx`** has the lowest knee, because packets are processed eagerly.
- **pickbench:** all key-based policies within 15% of each other at every depth.

### The `+rx` factor (W2b, W3, W6)

- **Prediction:**
  - Hint-aware policies' scored p99 drops 20–45% (v1: 24–43%).
  - `fifo+rx` changes by no more than ±10%.
  - **The policy × rx interaction:** the gap between hint-aware policies and `fifo` widens with rx on.
  - The per-request split shows the send→enqueue segment shrinking under rx.

## What would falsify the story

- A higher rung beating a lower one in a cell predicted as a tie, beyond the decision rule. That would point to a bug in the key or the harness.
- `hinted` ≠ `prio_edf` on W6.
- The key-based policies differing in cost by more than 5% on W1.
- `+rx` hurting a hint-aware policy's scored kinds.

## Amendments before the first v2 run (after the methods review of this note)

1. **W1 knee resolution.**
   - Stage 1 is the 40 k grid above, 2 repeats.
   - Stage 2: for each configuration, a 10 k grid (about 0.8%) strictly inside the stage-1 bracket (last passing level, first failing level), 2 repeats, same session.
   - The capacity is the highest level that passes in every repeat of both stages.
   - **Rule:** knee differences of one 10 k step or less are ties.
   - The W1 predictions are restated in those terms:
     - `stock` above `fifo` by more than one step;
     - the four key-based policies within one step of each other;
     - each key-based policy within 5% of `fifo`.
2. **"Mean wait", as compared with the predictions,** is defined as the growth of queueing over ρ = 0.5:
   - measured Δwait(ρ) = [client mean latency(ρ) − client mean latency(0.5)] − [handler time(ρ) − handler time(0.5)], per kind, with the handler time taken from the Segments split;
   - the prediction it is compared with is pred(ρ) − pred(0.5).

   The per-request split is reported next to it.

**Stated now, to be repeated in the report:**
- **Packet processing is outside ρ.** The busy fraction (program time / kthread time) is recorded per run. Predictions are also computed at the measured busy fraction, as a secondary check.
- **send→enqueue is "network + RX queue".** It mixes IOKernel transit and receive-queue wait, because there is no zero-work control. Its growth is attributed to `schedule()`'s order only through the `+rx` contrast.
- **W6 was redesigned after seeing v1's results** (deadlines 150/200, so that `edf`'s fixed order disagrees with class). It is a pre-registered prediction, not a blind workload.
- **`enqueue_tsc` resets whenever a thread is readied again.** With a 100 µs quantum and handlers under 60 µs, the handlers here are readied once.
- **SLO-load is censored at ≥ 0.9.** The top rungs of W2a, W2b and W4 are expected to tie on it by design. The gradient on those workloads is read from the mean waits and the price, not from SLO-load.
- **The client sends up to 5 µs early** (`MIN_TIMER_SLEEP`). Latency is measured from the actual send.

## Second amendments before the first v2 run (after the design review of this note)

1. **W6 parameters changed.**
   - **New values:** tight HIGH due 100 µs (SLO 100); loose HIGH due 300 µs (SLO 300); bulk NORMAL due 100 µs.
   - **Reason 1:** a 50 µs SLO for tight is below what any non-preemptive order can reach. A 50 µs bulk job may already be running on the request's own core, so the floor is 50 + 5 µs.
   - **Reason 2:** the 150/200 µs pair left `edf` only a 50 µs window to put bulk ahead of loose. The new 100/300 µs pair keeps v1's 200 µs window.
   - **Pre-registered W6 outcome on SLO-load:** `prio` = `prio_edf` = `hinted` ≥ 0.9, `edf` ≈ 0.85 (failing on loose), `fifo` ≈ 0.75.
   - **Mean waits** (pooled / per core) are recomputed with these deadlines by `analyze.predictions()` and printed in the report's tables.
   - **The urgency rung (`prio_edf` over `prio`) is carried by W3.** In W6, tight's tail is set by the bulk job on its own core, not by loose requests queued ahead of it.
2. **`hinted` = `prio_edf` on W6 is a construction check, not a prediction.** Every thread there has a deadline, so size never decides, except between deadlines that tie at µs granularity.
3. **The decision rule, completed.**
   - SLO-load is computed per repeat, at the first grid point where the worst scored p99/SLO exceeds 1.
   - A difference counts if all three paired ratios lie beyond ±5% on the same side.
   - A **tie** needs all three within ±5%; any other mix is reported as **inconclusive**.
   - **Tie-break:** when both SLO-loads are censored at ≥ 0.9, or one is censored and the ratio cannot clear 5%, the configurations are compared by the worst scored p99/SLO at ρ = 0.9 under the same paired rule.
4. **The mean-wait check.** The measured Δwait passes if:
   - it lies within [pooled, per-core] for the priority orders;
   - it is within ±25% of the pooled value for `fifo`.
5. **W5 changes.**
   - **Client:** every variant uses 2 client threads (2 were validated at 400 k req/s).
   - **qdelay:** `runtime_qdelay_us 10` is set explicitly. It is the runtime's default (`runtime/ioqueues.c`), so the IOKernel already used queueing delay, not the standing-queue test.
   - **Exploratory:** `hinted+rx` in `burst` is exploratory. `+rx` moves delay from the RX-queue term of the congestion signal to the runqueue term, so its direction is not predicted.
6. **Steals are counted at both levels.**
   - Each request now records the kthread whose RX queue it arrived on.
   - The time split reports **packet stolen** (processed by another kthread than the RX queue's owner) and **thread stolen** (run by another kthread than the one that queued it) separately.

## Third amendment (2026-11-19), after the first v2 burst runs; burst only

**What happened in the first burst runs.**
- In the first v2 runs of W5 `burst`, one server instance swept all six load levels.
- Many levels collapsed: the burstable cores were never granted, the server stayed at 2.0 cores and its threads never parked. The collapses were not monotone in load.
- The batch job's work rate was lost to a CSV-header bug in the harness (fixed in `run.py`).

**The diagnostic.**
- `results/w5-cores/diag`: fifo, ρ = 0.7, a fresh server for each of 6 runs, IOKernel `stats` on.
- **No collapse in 6 of 6.** The server used 3.1 cores, about 55 k batch-job preemptions per run, and the batch job did about 1.70 M work units/s.
- So the collapses came from state carried over between levels within one server instance, not from the load level.

**Change.**
- `burst` now runs a **fresh server per level**, like W1.
- The **prediction is unchanged:** at ρ ≥ 0.6, the batch job's work rate is at least 5% lower under `prio`/`hinted` than under `fifo`, and the short-request gain is preserved.
- `hinted+rx` stays exploratory.
- The first burst runs stay in the record (session `v2`), reported as invalid for the batch-rate question.
