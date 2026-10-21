# p12: sjf_scale

- id: p12
- config: sjf_scale
- generation: 11
- status: candidate
- builds_on: p10
- changed_from_previous: p10 plus: each core keeps a time unit from the median relative deadline of the HIGH threads it runs (1 below 350 µs, else that median in 100 µs, rounded; stored beside the pending pick's key, so all five learning slots stay), multiplies the 50 µs drop-limit allowance by it, and grows the 250 µs deadline split, the 8 µs cap allowance, the 17 µs blank length and the 4 µs shared-length drop by half a step per unit (p11's scaling, but with the split also in half steps and the unit from the median, not the tightest deadline); order, slack, rescue, timing and learning keys otherwise unchanged (unit 1 on w1–w10, so p10's decisions; 4 on w11 and w12)
- commit: (filled by orchestrator)

## What it does
Like sjf_mixed, each core runs helper threads first, then HIGH, NORMAL and LOW threads. Among HIGH threads it runs shorter requests first, using run times it learns per label. sjf_mixed's learning rules use fixed microsecond limits tuned to 100 µs deadlines. sjf_scale reads each core's time scale from the deadline that most of its HIGH work carries (a running median), not from the tightest one. On w1–w10 that median is at most 200 µs, the scale stays 1, and it decides exactly as sjf_mixed. On w11 and w12 the median is 400 µs. The scale becomes 4, so lookups again count shorter than puts and syncs, and multigets are learned apart from lookups. Leases keep running first.

## Why (hypothesis)
results/gen11/report.md, sections 3 and 6 (hypothesis 1), and results/gen10/notes.md ("why the model and the system disagreed").

**Why p11 failed, now located.**
- The runtime's default time slice is 100 µs (`cfg_quantum_us = 100`).
- When a request runs past 100 µs while other work waits, the IOKernel's slicer makes it yield. It is queued again with a new ready time.
- The server's raw counters show about 17,000 preemptions per run at w12 100k (16,904 at w11 90k under sjf_unit), against about 45 on w10. (Orchestrator check: `preemptions=17241` in results/gen11/raw/w12__sjf_unit__hints__hints__r1/rps100000.out; 63–115 on w10 at 290k–370k.)
- Each re-queued 145 µs sync, flush or multiget shows a relative deadline about 100 µs shorter or more. p11 took the tightest value at once, so its unit fell to 1 or 2 and every change cleared the learning table.
- Fresh handler threads are classified just before their first ready (UDP spawner), so for them deadline minus ready time is exact to about 1 µs.

**The fix: a median.**
- Re-queued threads and leases are a minority of HIGH picks on w12: leases about 12%, re-queued long requests about 7%. About 75% carry 400 µs.
- A median that moves 2 µs per pick therefore sits at about 400 µs and stays there. On w11 it is the same without leases.
- On w1–w10 the median is 60–200 µs, below the 350 µs threshold, so the unit is never anything but 1 and never changes.

**Lengths at unit 4 on w12.** Drop limit: '4 µs' label 216 µs, '8 µs' 224. Split 625 µs. Cap allowance 20 µs.

| Label | Kinds | Learned | Cap | Counts | Turn (deadline + 8 × length) |
|---|---|---|---|---|---|
| '2 µs' near | leases | ~3–5 µs | 26 | ~4 | +130 µs, first |
| '8 µs' | gets | ~10–15 µs | 32 | ~10–15 | +480–520 µs |
| '4 µs' | puts, syncs, flushes | ~90 µs | 28 | 28 | +624 µs |
| '68 µs' | queries | ~83 µs | 92 | 83 | +1064 µs |
| '8 µs' relaxed | multigets | ~120–145 µs | 32 | 32 | +1456 µs |

- **Gets** may pick up a few re-queued multiget remnants of about 40 µs; that is why their learned range goes up to about 15 µs.
- **Puts, syncs and flushes:** with yields, these are timed as a ~100 µs slice plus a ~40 µs remainder.
- **Queries** are not capped.
- **Multigets:** fresh ones, and remainders readied within about 475 µs, stay in their own label because of the half-step split. With p11's full split (1000 µs), most remainders would join the gets' label (offline: gets 26 µs instead of 15).
- **Shared-length rule stays off:** the two capped labels follow their measurements.

**Expected effect.**
- Gets lead puts and syncs by about 100 µs, against roughly a tie or a deficit today (report: get wait is 0.79 of put wait).
- This removes part of the ~66 µs "lost lead"; the ~95 µs floor of running long requests remains.

**Checks done offline** (scratchpad p12/drv.c, which compiles the real region with this code):
- Lockstep against choose_sjf_mixed on w9-like and w2-like streams: 0 differing picks out of 400k each, unit 1.
- On a w12-like stream with simulated yields: the unit settles at 4 (median ~400 µs) and the five labels above form.
- Not done: the full queueing model, so the w12 numbers below are reasoned, not simulated.

## Cost
- **Multigets are the main risk.** They count 32 µs and turn last, so they wait behind more queries. p11's model put this at +14–16% p99 for w11 (limit +25%). Deadline-met should stay at or above 99.9% (1200 µs deadline).
- **Puts and syncs** now let gets go first: p99 up about 5–15%, put deadline-met down at most a few tenths of a point.
- **Leases** keep the earliest turn. Their tail is outside the runqueue, so they should be flat.
- **Queries, batch and scans:** about flat. The change is inside HIGH, and the queries' position against gets and puts is unchanged.
- **Per pick:**
  - Each HIGH pick does one median step. When the median is at least 350 µs, it also does one division.
  - Pricing is one pass over five slots, as in p10. The clock is still read at most once.
  - With no HIGH threads (w0), it is p10's path plus reading one word.
- **Limits:**
  - A workload whose HIGH work is split evenly between two deadlines gets a unit from whichever holds the median.
  - The half-step allowances come from p11's model.
  - Time-sliced requests are still learned as pieces (~100 µs plus ~40 µs), not as whole runs.

## Needs
For the owner:
- **Counters (raised in priority again):**
  - each core's unit and median;
  - learned length per label;
  - table clears;
  - time-slice yields of hinted threads.
- **A way to tell a re-queued thread from a fresh one, or to keep the original ready time across a yield.** The time slice now shapes the learning on w11/w12.
- **Unchanged:** preemption by hint, hint-aware stealing, packet processing while hinted threads wait, and a per-kind learning key.

## Prediction (from the policy agent)

| Workload | Metric | Expected direction | Rough size |
|---|---|---|---|
| w12 | get p99 at 100k (score) | down | 236.5 → about 170–205 µs (threshold ≤ 212.8) |
| w12 | get runqueue-wait p99 at 100k | down | 161.8 → about 95–130 µs |
| w12 | get p99 at 105k / 110k | down | 282.0 / 327.5 → about 200–250 / 240–300 µs |
| w12 | put p99 / deadline-met at 100k | up / flat to slightly down | 348.5 → 360–410 µs (limit 435.6); 99.51 → 99.2–99.5% (floor 98.51) |
| w12 | sync p99 at 100k | up | 450.5 → 460–520 µs (limit 563.1) |
| w12 | multiget p99 / deadline-met at 100k (main risk) | up / flat | 857.0 → 900–1000 µs (limit 1071.3); 100.00 → ≥ 99.9% (floor 99.00) |
| w12 | query p99 / deadline-met at 100k | flat | 866.0 → 820–900 µs (limit 1082.5); 90.81 → 90.3–91.5% (floor 89.81) |
| w12 | lease p99 / deadline-met at 100k | flat | 131.5 → 125–140 µs (limit 164.4); 94.89 → 94.3–95.5% (floor 93.89) |
| w12 | batch / scan p99 | flat | 1102 / 1177 within ±5% (limits 1377.5 / 1471.3) |
| w11 | get p99 at 90k | down | 242.0 → about 170–215 µs (limit 266.2); other kinds as on w12 |
| w10 / w9 / w8 / w7 / w6 / w5 / w4b / w3 / w2 / w1 | score, deadline-met and every kind | same decisions as p10 (unit stays 1; lockstep: 0 differing picks) | within session drift |
| w0 | p99 one level below the headline / sustained throughput | flat (no HIGH threads: p10's path plus one word read) | within noise; within 1% |

## Results
(filled after evaluation)
