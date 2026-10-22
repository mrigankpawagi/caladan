# p20: sjf_slice

- id: p20
- config: sjf_slice
- generation: 19
- status: candidate
- builds_on: p19
- changed_from_previous: p19 plus: in the second scan, a waiting HIGH thread more than half again as long as the chosen one may also pass it, under p19's deadline cut, if the chosen thread keeps 40% of its window as slack after a whole 100 µs time slice and the passer has already used at least as large a share of its window as the chosen thread will have after waiting for it (p18's share test); on w20 searches pass fresh suggestions, and on w1–w19 decisions are p19's (6 of about 30M picks differ in the model, on w11 and w12)
- commit: (filled by orchestrator)

## What it does
Like sjf_tier, each core runs helper threads first, then HIGH, NORMAL and LOW threads. It orders HIGH threads by deadline and length, and lets an earlier request go first when the chosen one can spare the time. Until now, that earlier request had to be at most half again as long. sjf_slice also lets a much longer request go first. To allow it, the chosen request must still have 40% of its budget left after waiting a full time slice (100 µs), and the longer request must already have used a larger share of its own budget than the chosen one will have after waiting for it. On w20 a search that has waited a long time can now run before a suggestion that has only just arrived. A request with a budget under about 170 µs is never passed this way.

## Why (hypothesis)
- **The bottleneck (gen 19 report, sections 3 and 6):** search queue-wait p99 is 311.9 of 406.5 µs. About 76 µs of that is time behind younger suggestions. No pass reaches a search, because it is 4 times as long as a suggestion.
- **Why charge a slice (report hypothesis 1):** a passer can hold the core for at most one time slice before the IOKernel takes it back, even if its label understates its length. That rules out every chosen thread with a window under about 170 µs: w1–w10, w2's gets, the leases on w12–w15, and w15's hidden long lookups. On w16–w19 no longer kind is due later.
- **Why p18's share test and not p19's:** the suggestion p99 cap (+32.4 µs) binds before its deadline rule. In the model, p19's test ("has used as much as the chosen one has now") gave search p99 −3.2% but suggest p99 +38 µs, over the cap. p18's test ("as much as the chosen one will have after waiting") passes only searches that have waited at least about 190 µs. It gave −2.6% (108k) and −2.9% (104k) with suggest p99 +12 to +15 µs. That is about 1 µs of suggestion p99 per µs of search, still above the report's 0.8 limit.
- **Model:** the gen 17–19 queueing model with the real region compiled in and w20's mix (4 seed sets × 6 seeds).
  - At 108k: champion search p99 443, prio 359.
  - Measured, these are 406.5 and 325.5, so the model overstates search p99 by about 9%. It also understates suggest p99 by about 30 µs, because suggestion run times have a long tail.
  - Lockstep against sjf_tier:
    - w1–w10 and w13–w19: 0 differing picks.
    - w11 and w12: 6 of about 3M.
    - w20: about 1.2% of picks, all searches passing suggestions.
- **Honest limit:** the model puts −10% on w20 out of reach for any rule where a search passes a suggestion within the suggestion p99 cap.
  - Each pass costs a suggestion a whole 48 µs search and saves the search about one suggestion's run.
  - With no share test and no reserve at all, search reaches only −13%, at suggest p99 250.
  - Varying the slice charge (0/48/100 µs), the reserve (20–55%) and a minimum search wait (10–30%, report hypothesis 2) never gave better than −7% with suggest within +30 µs.
  - So this card is evidence on the report's top hypothesis, not a likely win. The remaining 95 µs outside the queue (report section 3, hypothesis 3) needs preemption of running index updates and merges, outside the region.
- **The w5–w10 losses (not attempted):** there the champion keeps the best get score but meets 2–3.6 points fewer query deadlines than prio and edf_high.
  - Every kind has a 100 µs window, so the gets and puts that the order runs first push older 17 µs queries past their deadlines. p4's rescue fires only when less than about 13 µs of slack is left, which is often too late.
  - Turning these into wins would take a rescue stated in backlog rather than a fixed margin: an older query runs first once its slack falls below the learned cost of the shorter HIGH work queued ahead of it.
  - That would cost gets some p99. The get score would have to stay within 6% of the best deadline-keeper, and query met would have to come within 1 point of prio and edf_high.
  - It should be built and checked in the model against w5–w10's measured query met before proposing.

## Cost
- **Who pays:** w20's suggestions. Each pass delays one fresh suggestion by one search, about 48 µs. About 1.5% of suggestions are passed.
- **Expected effect:** in the model, suggest p99 rises 12–15 µs and deadline-met stays at 100%. Health, index and merge are unchanged within 1%.
- **Elsewhere:** every other workload's decisions are p19's. w0 takes the same path, with no extra work.
- **Per-pick work:** at most one more inline check per HIGH thread in the second scan, which runs only when the chosen HIGH thread has a deadline and has not run yet. The clock is still read at most once per pick.

## Prediction (from the policy agent, against sjf_tier)

| Workload | Metric | Expected |
|---|---|---|
| w20 108k (headline) | search p99 | −2% to −5% (about 385–400 µs). Very likely misses the 365.9 threshold. |
| w20 104k | search p99 | −2% to −4% |
| w20 108k | suggest p99 / deadline-met | +10 to +20 µs (about 140–150, under the 161.9 cap) / at least 99.9% |
| w20 108k | health, index, merge p99 | unchanged (±2 µs, ±1%) |
| w20 40k | all kinds | identical |
| w20 108k | search queue-wait p99 | −8 to −15 µs (from 311.9) |
| w1–w19 | score and deadline-met | unchanged within noise (decisions are p19's in the model) |
| w0 | p99 and saturated throughput | unchanged (no HIGH threads, same path) |
| Rule 7 | the 11 wins | all kept (w20 search stays at or below sjf_share's 401) |

## Results
(filled after evaluation)
