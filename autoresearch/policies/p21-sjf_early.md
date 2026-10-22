# p21: sjf_early (with variants sjf_early30 and sjf_early_w)

- id: p21
- config: sjf_early (variants: sjf_early30, sjf_early_w)
- generation: 20
- status: candidate
- builds_on: p19
- changed_from_previous: p19 plus: at a time unit of 1 (w1-w10), when p4's rescue check does not fire, the HIGH thread with the least slack still runs first if waiting for the chosen thread, priced at that label's uncapped learned length, would leave it with less than 18 us of slack (22 us margin instead of 13), and the chosen thread keeps 60% of its window after it; give-up rule unchanged; decisions on w1 and w11-w20 are p19's (0 differing picks in the model)
- commit: (filled by orchestrator)

## What it does
Like sjf_tier, each core runs helper threads first, then HIGH, NORMAL and LOW threads, and orders HIGH threads by deadline and length, so short lookups usually go ahead of long queries. A query that is about to run out of time can jump ahead (the "rescue"), but so far that happened only when the query was already lost, because the rule assumed a request spends 13 µs outside the queue, while at full load it spends 34-41 µs. sjf_early lets the rescue happen a little earlier, using the full measured length of the request it would wait for (a "1 µs" put label that really holds 30 µs flushes counts as long as it is). The earlier rescue happens only if the request that gets passed still keeps 60% of its time budget afterwards. It applies only on workloads whose deadlines are around 100 µs (time unit 1); everywhere else the policy decides exactly as sjf_tier.

## Variants (first convergence generation)
The policy agent's model understates the champion-versus-prio query deadline-met gap by 2.4–3.7 times, so the constants are settled by a short paired probe on the nodes before a full evaluation. All three variants share one implementation, choose_sjf_early_k(margin, keep, any_unit):

| Config | Margin | Kept by the passed thread | Units | One-line difference |
|---|---|---|---|---|
| sjf_early | 22 µs | 60% | 1 only | as described above |
| sjf_early30 | 30 µs | 40% | 1 only | the same rescue, earlier and cheaper to grant (the report's bolder form) |
| sjf_early_w | 22 µs | 70% | every unit | also above unit 1, where a thread is never rescued past one due later and p14's ratio rule does not bar the rescue; on w12 a query may pass a get but never a lease |

Share of picks that differ from sjf_tier on won workloads (lockstep model): sjf_early w2 0.24%, w3 2.1%, w4b 1.0%; sjf_early30 w2 1.2%, w3 3.6%, w4b 1.7%, w12–w15 1–2 picks per run at startup; sjf_early_w w3 2.1%, w4b 1.0%, w11 1.0%, w13–w15 about 0; none on w1 or w16–w20.

## Why (hypothesis)
- **Report (gen 20), sections 1–3:** on w5–w10 queries lose 1.2–3.4 points of deadline-met to prio. p4's rescue fires only after 57–70 µs of waiting, while a query that has waited past about 60–66 µs already misses at the client. The report's hypothesis 1 is to rescue earlier, priced at the chosen thread's real length.
- **The offline model rejects the unguarded form.** In the gen 19 model, recalibrated with a client-side delay outside the queue, hypothesis 1 with a 30 µs margin gains queries +0.6 points on w5 but costs puts:
  - put deadline-met 98.66 → 96.93 (rule 6)
  - put p99 +45% (rule 3)
  - get p99 +11% (rule 2)
  Every rescued 21 µs query delays the puts and gets queued behind it, and they share the same 100 µs deadline.
- **The guard:** rescue earlier only when the passed thread keeps 60% of its window (p16's reserve idea), with a 22 µs margin. In the model this keeps puts within about 0.8 points and gets within +8%.
- **Calibration and bias:**
  - What it reproduces on w5: tier get 16/53/80 µs (measured 16/52/81), put p99 and deadline-met (105 µs, 98.66% against 106.5, 98.60%), and query queue-wait p99 (tier 143 against 145.6; prio 121 against 115.6).
  - Bias: it gets the tier-versus-prio query deadline-met gap too small (w5 0.6 against 2.2 points; w8 1.7 against 4.15), so its query gains are likely 2.4–3.7 times too small in absolute terms.
- **Lockstep against sjf_tier:** 0 differing picks on w1 and w11–w20 (unit above 1). Differing picks: w2 0.24%, w4b 1.0%, w5 1.2%, w3 2.1%.

## Cost
- Puts and gets on w5–w10 wait behind more rescued queries. Model:
  - put deadline-met −0.3 to −0.8 points, put p99 +5% to +12%
  - get p99 +1% to +3%, and +8% on w10
- w3: get p99 +3.5% in the model (sjf_early30: +10.5%, likely a rule-7 loss).
- w10 stays a loss: its puts have only 0.04 points of room (model −0.5).
- sjf_early_w on w12 (model): query +0.2 points, get p99 +6.7%; it reaches w12's +0.87 only if the nodes show about 4 times the model's gain. w15's large lookups rose 14% in one 3-seed run of that setting; watch them.
- Per pick: at most one extra slot scan (5 entries) and two comparisons, only when p4's rescue does not fire; no extra clock read, no new state.

## Prediction (from the policy agent, against sjf_tier; model numbers, query gains likely 2.4–3.7 times larger on the nodes)

| Workload | Metric | Expected |
|---|---|---|
| w5 | query deadline-met (needs 88.09) / get p99 / put deadline-met | about 0 to +0.3 points (model −0.1) / +1% / −0.3 points; stays a loss |
| w6 | query deadline-met (needs 87.82) | about 0 to +0.3 points (as w5); stays a loss |
| w7 | query deadline-met (needs 85.91) / sync p99 | +0.5 to +1.5 points / +5% to +10%; stays a loss |
| w8 | query deadline-met (needs 86.03) / put deadline-met / get p99 | +0.5 to +1.7 points (model +0.47) / −0.8 points (floor 95.97, tight) / +2% to +5%; stays a loss |
| w9 | query deadline-met (needs 83.86) / put deadline-met / put p99 | +0.45 to +1.5 points (model +0.45) / −0.7 points / +11%; possible win only if the nodes show about 3 times the model's gain |
| w10 | query deadline-met / put deadline-met | +0.6 to +2 points / −0.5 points (below the 97.38 floor); stays a loss |
| w12 | every metric | unchanged (unit 4: p19's decisions); stays a loss |
| w17 | point p99 | unchanged (p19's decisions); stays a loss within noise |
| w3 (won, at risk) | get p99 / query deadline-met | +2% to +4% / about 0; rule-7 risk if w3 is already near the 6% band in gen 20's re-measurement |
| w4b (won, at risk) | get p99 / query deadline-met | +1% to +3% / about 0 to +0.3 points |
| w2 (won) | get p99 | within noise (0.24% of picks differ) |
| w1, w11, w13–w16, w18–w20 (won), w0 | every metric | identical decisions; within noise |

## Results
(filled after evaluation)
