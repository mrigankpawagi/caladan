# p10: sjf_mixed

- id: p10
- config: sjf_mixed
- generation: 9
- status: accepted
- builds_on: p9
- changed_from_previous: p9 plus: when two capped labels are ranked against their measurements (the one whose learned run time is longer has the smaller cap, so it counts shorter), both count one shared length, 4 µs below the smaller cap (on w10, gets with multigets and puts with syncs both count 9 µs instead of 14 and 13); every other length, and order, slack, rescue, timing and learning keys, unchanged
- commit: 635c52d

## What it does
Like sjf_pair, each core runs helper threads first, then HIGH, NORMAL and LOW threads. Among HIGH threads it runs shorter requests first. It learns from its own timings how long requests with each label really take, and a label may count at most 8 µs more than its hint plus 4 µs. On w10 two labels hit that limit: lookups share theirs with 30 µs multigets, and puts share theirs with 30 µs syncs. Because the lookups' hint is 1 µs larger, lookups count as longer even though they measured shorter, so they wait behind puts and syncs. sjf_mixed notices when two capped labels are ranked against what was measured. It then counts both at one shared length, 4 µs below the smaller limit (9 µs on w10), so lookups and puts take turns by deadline instead of one always giving way to the other, and both move a little further ahead of the long queries. When no two capped labels are in the wrong order, as on every earlier workload, it makes exactly sjf_pair's choices.

## Why (hypothesis)
results/gen9/report.md, sections 3 and 6 (hypotheses 1 and 2).
- **The problem.** On w10 the champion's get runqueue-wait p99 rose from 23.6 to 87.2 µs, and the whole 58 µs rise is runqueue wait.
  - The gets' label, capped at 14 µs, gets a turn of +212 µs. The puts' label, capped at 13 µs, gets +204, so gets go behind puts and syncs.
  - After 77 µs of waiting a get counts as too late and then also gives way to the shorter "1 µs" label.
  - What was measured says the reverse: the "2 µs" label averages about 13 µs (the learned estimate is about 22) and the "1 µs" label about 18 (estimate about 27). The caps, not the measurements, invert the order.

**Why one shared length, not just a reversed order.** I checked the hypotheses with an offline model: 8 cores; per-core queues fed by 16 hashed flows; packets held while their core is busy; stealing; w10's mix and bursts. The model calls the real choose functions with simulated clocks. It reproduces the champion's runqueue-wait p99 at 345k fairly well:

| Kind | Model (µs) | Measured (µs) |
|---|---|---|
| get | 98.8 | 87.2 |
| put | 58.0 | 57.9 |
| sync | 58.8 | 61.4 |
| multiget | 99.0 | 87.9 |

It overstates query and batch waits. Gets and puts trade waiting almost one for one:

| Variant (model, 345k) | Get p99 | Put p99 | Put met (points) | Sync p99 | Query met (points) |
|---|---|---|---|---|---|
| Hypothesis 1: gets' label 3 µs below the puts' | −33% | +39% | −1.2 | +31% | 0 |
| Gets' label 1 µs below, too-late rule narrowed (hypothesis 2) | −22% | +25% | −1.0 | +21% | 0 |
| Both labels at the smaller cap (13 µs) | −15% | +18% | −0.66 | +14% | −0.1 |
| **Both labels 4 µs below it (9 µs): this policy** | **−23%** | **+7%** | **−0.24** | **+6%** | **−0.47** |

Why each part matters:
- **Reversing the order only moves the waiting.** Whichever mixed label counts shorter wins at every too-late comparison. Its 30 µs members, multigets or syncs, then land on the other label.
- **An equal length removes that swap.** Neither label gives way to the other, and gets and puts take turns by deadline.
- **Lowering both by 4 µs moves some waiting onto queries.** Their turn becomes +172 µs against the queries' +268. During bursts HIGH work alone exceeds capacity, so part of the waiting moves to queries. Queries have room under the rules: p99 213 against a 266.3 limit, deadline-met 87.47% against an 86.47% floor.
- **Why 4 µs.** The model shows a step between 3 and 4 µs. A 3 µs drop gives get −17%, put met −0.50, query met −0.09. A 5 µs drop changes nothing more.

**Decisions on w1–w9 stay p9's.**
- Only one pair of labels is capped on w9: "1 µs" (cap 13, about 27 learned) and the relaxed "2 µs" multigets (cap 14, about 34 learned). Their caps follow their measurements. On w5–w8 only one label is capped, and on w1–w4b none.
- I checked this in the model by calling p9 and p10 on every queue state (lockstep):

| Workload | Picks that differ |
|---|---|
| w0–w8 | 0 (0.13–0.9 M picks each) |
| w9 | 104–146 of 0.4–1.3 M, all in the first 0.07–0.48 s, none after |
| w10 | 5.4% |

  The w9 differences come while the multigets' estimate climbs from its floor to 34 µs. That ends inside the 1 s rampup.
- On w10 the inversion is detected in about 97% of pricing calls. The rest is warmup and moments when estimate noise reverses the two labels, and then p9's lengths apply.

**State fits.** No new state. The rule reads the existing learned estimates and the caps derived from each slot's key. w10 needs 3 slots and w9 needs 4, as in p9.

Expected on w10 at 345k: get runqueue-wait p99 about 55–70 µs and get p99 about 105–118 µs (threshold ≤ 123.7). Gets still wait for multigets queued before them (no hint separates them). About 50 µs of the get tail stays outside the runqueue.

## Cost
- **Queries are the main risk.** Gets, puts, syncs and multigets now pass them more often. Model: −0.47 points of deadline-met at 345k (floor −1.0), p99 flat.
- **Puts and syncs** now share turns with gets and with 30 µs multigets. Model: put p99 +7%, put deadline-met −0.24 points, sync p99 +6%.
- **Multigets gain** (model −19% p99). Batch and scans are unaffected because the change is inside HIGH.
- **Per pick:**
  - Only when two HIGH threads are queued: one pass over the 5 learning slots. If two or more labels are capped, 25 pair checks follow.
  - The clock is still read at most once. No new state.
  - Without HIGH threads (w0) the path is p9's.
- **Limits:**
  - The 4 µs drop is tuned in a model and sits near a step: 3 µs gave a smaller gain.
  - Kinds that share both hint and deadline are still learned together; this only stops the caps from ranking such labels backwards.
  - A noisy moment that reverses the two estimates falls back to p9's lengths.

## Needs
Unchanged from p9, for the owner:
- a learning key the server sets per kind (the only way to separate gets from multigets);
- preemption (a running 30 µs multiget or sync cannot be passed);
- packet processing while hinted threads wait;
- counters for each core's learned lengths, how often the cap binds, and how often this rule applies.

## Prediction (from the policy agent)

| Workload | Metric | Expected direction | Rough size |
|---|---|---|---|
| w10 | get p99 at 345k (score) | down | 137.5 → about 105–118 µs (threshold ≤ 123.7) |
| w10 | get runqueue-wait p99 at 345k | down | 87.2 → about 55–70 µs |
| w10 | get p99 at 370k / 320k | down | 162.5 → 115–135 µs; 110.0 → 90–100 µs |
| w10 | put p99 / deadline met % at 345k | up slightly / down slightly | 113.0 → 115–128 µs (limit 141.3); 98.23 → 97.8–98.2 (floor 97.23) |
| w10 | sync p99 at 345k | up slightly | 136.5 → 140–152 µs (limit 170.6) |
| w10 | query deadline met % / p99 at 345k (main risk) | down slightly / flat | 87.47 → 86.7–87.3 (floor 86.47); 213.0 → 205–225 µs (limit 266.3) |
| w10 | multiget p99 / deadline met % | down / flat | 173.5 → 140–160 µs (limit 216.9); 99.96 → ≥ 99.9 (floor 98.96) |
| w10 | batch / scan p99 | flat | 268.5 / 288.0 within ±5% (limits 335.6 / 360.0) |
| w9 | get p99 at 370k and every kind | same decisions as p9 after warmup | 85.5 within session drift (limit 94.1) |
| w8 / w7 / w6 / w5 / w4b / w3 / w2 / w1 | score and deadline-met | same decisions as p9 | within session drift (w8 limit 93.0) |
| w0 | p99 one level below the headline / sustained throughput | flat (p9's path, no HIGH threads) | within noise; within 1% |

## Results
Accepted in generation 9 (judge.py, results/gen9/) against the champion p9
sjf_pair, on every rule and every workload, without a paired confirmation.

| Workload | sjf_pair | sjf_mixed | Change | Notes |
|---|---|---|---|---|
| w10 | get p99 137.5 µs | 114.5 µs | −16.7% | predicted 105–118; at 370k 162.5 → 135.0 |
| w10 | put p99 / met | 113.0 µs / 98.23% | 123.0 µs / 97.39% | +8.8%, −0.84 points (predicted 115–128, 97.8–98.2); close to the 1-point limit |
| w10 | sync / multiget p99 | 136.5 / 173.5 µs | 148.5 / 148.5 µs | +8.8% / −14.4% |
| w10 | query met / p99 | 87.47% / 213.0 µs | 87.06% / 209.5 µs | −0.41 points (predicted 86.7–87.3) |
| w10 | runqueue-wait p99 get / put / sync / multiget | 87.2 / 57.9 / 61.4 / 87.9 µs | 81.1 / 80.3 / 80.2 / 80.1 µs | the four kinds now wait alike |
| w1–w9 | | | −3.5 to +3.7% | identical decisions (after warmup on w9) |
| w0 | p99 at 300k 72.0 µs | 71.0 µs | −1.4% | sustained throughput −0.18% |

The model's prediction held on the score, queries and multigets; puts paid
more than predicted (0.84 points against 0.24). Sharing one length evens
the waiting out across the two mixed labels instead of removing it: get
wait p99 fell only 6 µs, while get p99 fell 23 µs because fewer gets reach
the too-late regime.
