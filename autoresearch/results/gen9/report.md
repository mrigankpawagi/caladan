# Generation 9: measurement report

## 1. Headline

These are the w10 results at the headline load of 345k req/s. The score is get p99 in µs: the median of two repeats, with the range in brackets. The other columns are p99 in µs.

| Policy | Score | vs fifo | put | query | sync | multiget | batch | scan | Throughput |
|---|---|---|---|---|---|---|---|---|---|
| fifo | 182.5 (180–185) | 0% | 188.5 | 202.0 | 218.0 | 215.0 | 202.0 | 203.0 | 344,058 |
| prio | 161.0 (160–162) | −12% | 167.5 | 181.0 | 197.0 | 198.0 | 265.0 | 283.0 | 343,934 |
| sjf_capped | 138.0 (135–141) | −24% | 112.0 | 212.0 | 134.0 | 176.0 | 271.5 | 289.0 | 343,604 |
| **sjf_pair** (champion) | 137.5 (135–140) | −25% | 113.0 | 213.0 | 136.5 | 173.5 | 268.5 | 288.0 | 343,490 |
| fifo / ignore | 173.5 (171–176) | −5% | 180.0 | 192.5 | 205.5 | 207.5 | 192.5 | 192.0 | 343,620 |

On w10, multigets carry exactly the gets' hints. At 345k this raised the champion's get p99 from 79.5 µs on w9 to 137.5.

## 2. Is it real?

- **Repeats agree.** The widest spread is 4.3% (sjf_capped, 135 and 141), inside the 6% noise band.
- **Real differences:** the champion against fifo (−25%) and against prio (−15%).
- **Noise:**
  - sjf_pair against sjf_capped (0.4%). Their decisions are identical because no deadline is now more than 250 µs away.
  - fifo against fifo/ignore (5.2%). This is inside the band, although their repeat ranges do not overlap.
- **Across sessions (w9 to w10, both at 345k):** fifo and prio make the same decisions on both workloads, yet moved +7.7% (169.5 → 182.5) and +4.2%. The champion's +58 µs (+73%) and its get runqueue-wait p99 rise from 23.6 to 87.2 µs are far beyond that drift.

## 3. Where the gets' time goes (sjf_pair, 345k)

- **Latency:** get p50 is 15.5 µs and p99 is 137.5, against 11.0 and 14.0 at 100k.
- **Runqueue wait:** p99 87.2 µs, so about 50 µs of the p99 is spent outside the runqueue (55.9 on w9). About 14 µs of that is network plus service. The rest is the packet waiting on a busy core before its thread exists. The whole 58 µs rise is runqueue wait.
- **Counters:**
  - mean HIGH wait 11.69 µs;
  - queue depth 1.62;
  - inversions 0;
  - late at pick 1.86% of HIGH picks, while 3.00% of gets miss at the client (w9: about 0.2%);
  - steals 29.8%;
  - hinted overflow 118 of about 826k HIGH picks.

**The order is inverted.** Runqueue-wait p99 in µs at 345k, sjf_pair:

| Kind | w9 | w10 |
|---|---|---|
| get | 23.6 | 87.2 |
| multiget | 154.1 | 87.9 |
| put | 54.0 | 57.9 |
| sync | 50.9 | 61.4 |

- Gets and multigets now wait the same, and puts and syncs wait less than gets.
- A thread's turn is its deadline plus 8 times its length. If the gets' "2 µs" label is at its 14 µs cap, gets are due 212 µs after becoming ready, against 204 µs for the "1 µs" label (puts and syncs, capped at 13 µs).
- That is sjf_nohint's order on w9, where gets also ranked 8 µs behind puts. Its get wait p99 at 345k was 86.0, against 87.2 here.

**The too-late rule makes it worse.** With a length of 14 µs, a get counts as too late (less than 9 µs to spare) after 100 − 14 − 9 = 77 µs of waiting. From then on it waits for every queued shorter thread, and the 13 µs label is now shorter. The p99 get waited 87.2 µs, so it is in this regime. On w9 a get was too late only after about 85 µs, and no label was shorter.

No counter shows the learned lengths, so the cap is inferred, not measured.

**Conclusion:** queueing. Gets now rank behind puts and syncs and level with 30 µs multigets. About 50 µs of the tail lies outside the runqueue.

## 4. Costs

- **Against fifo:**
  - Puts, syncs and multigets all gain: p99 113.0, 136.5 and 173.5 against 188.5, 218.0 and 215.0.
  - Queries are close: p99 +5%, deadline-met 87.47% against 87.78%.
  - Batch +33% and scans +42%. NORMAL wait is 24.71 against 15.39 µs.
- **Against w9 at the same load:**
  - Puts and syncs are unchanged: put p99 113.0 against 114.5, put deadline-met 98.23% against 98.08%, sync p99 136.5 against 135.5.
  - Multigets took the gets' place: p99 173.5 against 229.0.
- **CPU and drops:** 7.98 cores, zero drops.

## 5. Anomalies

- **The headline load moved.** It fell to 345k (w9: 370k) because fifo's light-load median went from 30.0 to 29.0 µs. That made 370k's 45.0 µs 1.55 times the light-load value, over the 1.5 limit. Compare w9 and w10 at equal load.
- **Clean runs:** 10 runs, one sha (b666cb1), no failed or saturated levels, adherence at least 99.77%. Kind and class rows agree within 3 req/s.
- **Overflow repeats disagree:** sjf_pair's hinted overflow at 345k was 1 in one repeat and 234 in the other, both under 0.03% of HIGH picks.
- **The champion was hurt more than the workload agent predicted.** At 370k:

| Quantity | Predicted | Measured |
|---|---|---|
| get p99 | 125–155 | 162.5 |
| get runqueue-wait p99 | 85–110 | 119.7 |
| put runqueue-wait p99 | 55–75 | 81.5 |
| multiget p99 | 150–190 | 199.5 |

The likely extra cause is gets queueing behind earlier multigets at the same turn. sjf_nohint on w9, which had the same 8 µs order but multigets last, measured 96.25 µs of get wait.

- **Predictions that held:**
  - fifo, prio and fifo/ignore repeated w9 within drift (+6.2%, +4.5%, +2.8%);
  - sjf_capped and sjf_pair decided alike;
  - query p99 was 256.0 (predicted 235–265);
  - put deadline-met was 97.05% (predicted 97–97.8);
  - get p99 at 100k was 14.0 under every policy.

## 6. Hypotheses for the policy agent

**Thresholds on w10 at 345k:**
- get p99 at most 123.7 µs;
- p99 at most 141.3 µs (put), 266.3 (query), 170.6 (sync), 216.9 (multiget), 335.6 (batch), 360.0 (scan);
- deadline-met at least 97.23% (put), 86.47% (query), 98.96% (multiget);
- on older workloads, get p99 at most 94.1 µs on w9 and 93.0 on w8.

Gets and multigets carry identical hints, so no policy can separate them. Each get will still wait for multigets queued before it, and w9's floor (79.5 µs at 345k) is out of reach. What remains to win is the gets' place against puts and syncs.

1. **Keep capped labels in their measured order.**
   - Evidence: the wait inversion in section 3.
   - Idea: never let a label count longer than a label whose measured average is longer. For example, keep a plain average per label next to the current estimate (which leans toward long runs), and when both labels are capped, rank the one with the lower average a clear few µs ahead.
   - By the workload agent's arithmetic, the "2 µs" label averages about 13 µs and the "1 µs" label about 18. On w1–w9 no capped label averages less than one that counts shorter, so decisions there should not change.
   - Expected: get wait p99 about 40–60 µs and get p99 about 90–110 µs.
   - Main risk: puts and syncs now also wait for multigets, about 1.5 of the 14.9 µs of work per request. Watch put p99 (113.0) and deadline-met (98.23%).
2. **Narrow the too-late rule.**
   - Evidence: get wait p99 is 87.2 µs, past the 77 µs line, and 3.00% of gets miss their deadline.
   - Idea: a too-late thread yields only to threads that are shorter by at least 2–3 µs, not by 1.
   - This gains less than hypothesis 1, because gets still rank 8 µs behind puts by turn.
3. **Outside the policy region.**
   - Evidence: about 50 µs of the get p99 is outside the runqueue (fifo about 44).
   - Needed hooks: a learning key the server sets per kind (the only way left to tell gets from multigets); preemption, since a 30 µs multiget now runs at the gets' own turn and cannot be passed; and packet processing while hinted threads wait.
   - Counters to request: each core's learned length per label, how often the cap binds, and how many picks the too-late rule decides.

## 7. Lessons

workload: On w10, giving multigets the gets' whole hint entry raised the champion's get runqueue-wait p99 at 345k from 23.6 to 87.2 µs, now equal to the multigets' 87.9, and hurt more than predicted at 370k (get p99 162.5 vs 125–155) because gets also queue behind 30 µs multigets at the same turn; the headline also fell to 345k because fifo's light-load median moved by 1 µs, so state predictions at both loads.
policy: On w10 the gets' label, capped at 14 µs, ranks 8 µs behind the puts' label, capped at 13 µs, and gets count as too late after 77 µs and then yield to that label, so ordering capped labels by their measured average (about 13 vs 18 µs) can recover part of the 58 µs loss, while about 50 µs of the 137.5 µs get p99 stays outside the runqueue and gets still wait for multigets no hint can separate.
