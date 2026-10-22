# Generation 19: measurement report

## 1. Headline (w20, 108k, µs, median of 2 repeats)

| Policy | search p99 (score) | vs fifo | suggest p99 / met % | health | index | merge | Resp/s |
|---|---|---|---|---|---|---|---|
| fifo | 643.0 | 0% | 608.0 / 83.85 | 595.0 | 633.0 | 631.5 | 107,009 |
| fifo ignore | 626.5 | −2.6% | 592.0 / 84.48 | 582.0 | 616.0 | 613.5 | 106,451 |
| prio | **325.5** | −49.4% | 290.5 / 98.08 | 279.5 | 1054 | 1526 | 106,410 |
| sjf_share | 401.0 | −37.6% | 128.0 / 99.975 | 97.5 | 1084 | 1541 | 107,275 |
| sjf_tier (champion) | 406.5 | −36.8% | 129.5 / 99.96 | 98.0 | 1104 | 1602 | 106,660 |

w20 is a new service. A search costs four times a suggestion and is due four times later. Every hinted policy met 100% of search deadlines.

## 2. Is it real?
- Score repeats: champion 400/413, sjf_share 399/403, prio 325/326, fifo 642/644.
- **Real:** the champion against fifo, prio against the champion (−19.9%), and prio's suggestion deadline-met (97.99/98.17 against 99.96/99.96).
- **Within the 6% noise band:** the champion against sjf_share (+1.4%) and fifo ignore against fifo.

## 3. Where the searches' time goes (champion)
- Search p50 is 81 µs (57 at 40k) and p99 406.5 (82 at 40k).
- Queue-wait p99 is 311.9 µs, 77% of the p99. The other 94.6 µs is spent outside the queue (fifo 95.4, prio 90.0): the search's own 48 µs, the network, and waiting behind a running 41 µs index update or merge.
- **No pass reaches a search, confirmed.**
  - p16's and p17's passes need the passer shorter. p18's and p19's allow at most 1.5 times as long, and a search is 4 times a suggestion.
  - p18 and p19 differ only in that pass, and they agree within noise on every kind: search wait p99 308.6 vs 311.9, suggest p99 128.0 vs 129.5, health 97.5 vs 98.0, mean HIGH wait 15.4 vs 15.7.
  - The rescue never fires either: the search p99 is far below 1000 µs, and 0.002–0.003% of deadline threads were late at pick.
- **Turn times** (deadline plus 8 times length): search 1384 µs after it is ready, health 1008, suggestion 346. So suggestions readied up to 1038 µs after a search run first. In practice the champion runs every suggestion first.
- **Splitting the 311.9 µs:**
  - Under oldest-first (prio), searches wait 235.5 µs at p99 and suggestions 233.9. That is the backlog already ahead of a search when it arrives.
  - The remaining 76.4 µs is time behind younger suggestions; health checks are about 1% of HIGH work.
  - Check: during a burst, suggestions use about 22% of a core, so a 236 µs wait collects about 68 µs of younger suggestion work.
- **What the threshold needs:** reaching 365.9 means a queue-wait p99 of about 271 µs, so at least 41 of those 76 µs must go.
- Other counters: queue depth 2.71, no inversions, 12% of hinted threads stolen, no overflow.

## 4. Suggestion slack and costs
- The champion's suggest p99 is 129.5 µs, 120.5 before the deadline. 74.4 µs of it is spent outside the queue: suggestion cost is exponential, so 1% run longer than 55 µs under the same 12 µs hint.
- Under the rules, suggestion deadline-met may fall 0.96 points, but suggest p99 may rise only 32.4 µs (to 161.9).
- **Mixing toward oldest-first fails.** On a straight line from the champion to prio, each µs of search p99 costs 1.99 µs of suggest p99, 2.24 µs of health p99 and 0.023 points.
  - At 365.9, suggest p99 would be about 210 and deadline-met about 99.02.
  - The p99 cap binds first. A policy must spend at most 0.8 µs of suggest p99 per µs of search p99.
- Every policy used 3.99 cores, and all merges were answered.

## 5. Anomalies
- None in the 10 runs: 0 drops, adherence 99.85–99.88%, kind and class counts equal.
- Workload predictions that missed: suggest p99 (129.5 against 90–115), health (98 against 50–70), and the share of the tail spent in the queue (0.77 against 0.78–0.83).

## 6. Hypotheses
1. **Let a much longer thread pass, charging the passed thread a whole time slice.**
   - The rule: the oldest waiting HIGH thread (not overrun, within p9's split) that is more than 1.5 times as long passes under p19's cut and share test (on w20, once a search has waited at least 4 times as long as the suggestion).
   - The guard: the suggestion must keep 40% of its window after a full 100 µs time slice plus its own length.
   - So a suggestion can be passed only until it has waited 38 µs, and pays for at most one search (48 µs).
   - Charging a slice rather than the hinted length keeps out w15's long lookups (hinted as 8 µs gets) and every passed thread with a 60–100 µs window (w2's gets, the leases on w12–w15). Multigets stay outside the split. w16–w19 have no longer kind due later, so their passes are unchanged. Confirm in lockstep that no picks differ on w1–w19.
   - Prediction: search p99 350–385, suggest p99 140–160. Both margins are thin.
2. If suggest p99 rises above about 150 in the model, also require the search to have used at least 10% of its window (100 µs).
3. **Outside the policy region:** the 94.6 µs outside the queue needs preemption of running index updates and merges.
   - Counter requests: passes per pair of kinds.
   - Also each core's time unit, to confirm that 1000 µs is within p9's split (1125 µs at unit 8, per p16's card).

## 7. Limits for a new policy

| Rule | Champion | Limit |
|---|---|---|
| w20 search p99 | 406.5 | ≤ 365.9 |
| suggest / health p99 | 129.5 / 98.0 | ≤ 161.9 / 122.5 |
| index / merge p99 | 1104 / 1602 | ≤ 1379 / 2003 |
| suggest / search / health met | 99.96 / 100 / 100 | ≥ 98.96 / 99.0 / 99.0 |
| w19 point p99, mid / fanout met | 413.5, 99.945 / 99.89 | ≤ 454.9, ≥ 98.945 / 98.89 |
| w18 point p99, fanout met | 454.5, 99.625 | ≤ 500.0, ≥ 98.625 |
| w17 point p99, fanout met | 227.0, 99.81 | ≤ 249.7, ≥ 98.81 |
| w16 point p99, fanout met | 240.5, 98.51 | ≤ 264.5, ≥ 97.51 |

w18's fanouts (p99 264.0, 36 µs under their deadline) must not move. A w18 read is only 1.1 times a fanout, so hypothesis 1 never applies there.

## 8. Other proposals (probe, one repeat each)
- **w20b** (frontend fetch cost exponential around the 45 µs hint): at 76k, the champion's point p99 is 688 against fifo's 690, with 77% of it queue wait.
  - At 28k the point p99 is already 225 µs (w19: 77.5), from run time alone.
  - 3.6% of fetches run past p15's 150 µs mark, more than the 1% the p99 counts. Time-slice preemptions were 3863, against 65 on w19.
  - Per p15's card, such threads go behind waiting threads of the same label, and p17–p19's passes need a thread that has not run yet. So the tail likely sits where no pass reaches.
- **w20a** (2 guaranteed and 2 burstable cores next to a cache antagonist): at 71k, point p99 is 383 against fifo's 508 (−24.6%), with 71% of it queue wait.
  - Fanout deadline-met rises from 92.92% to 99.91%.
  - The server used 2.09 cores at 28k and 3.10 at 71k.

## 9. Lessons
workload: A score kind four times as long as the tight kind (w20) made p18 and p19 decide alike (401.0 vs 406.5 µs), and making the score kind's cost vary (w20b) left the champion level with fifo (688 vs 690), because 3.6% of fetches run past the 150 µs overrun mark, so put varying cost on a kind that is not scored.
policy: On w20 the champion runs every suggestion first, and the search wait p99 of 311.9 µs is 235.5 of backlog plus 76.4 behind younger suggestions, so the next pass must let a four-times-longer search go first while charging the suggestion a full 100 µs slice and keeping 40% of its window, because the suggestions' +25% p99 cap (161.9 µs) binds before their 1-point deadline rule.
measurement: Placing the rule limits on the straight line from the champion to oldest-first, per µs of score, showed which limit binds (on w20 the suggestion p99 cap allows 16 µs of search gain and the deadline rule 41), so report the binding limit and how much better than that line a policy must do.
