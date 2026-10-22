# Generation 20: measurement report (convergence): why the champion loses 8 workloads

Data: the generation 19 re-measurement (one session, 2 repeats). Query deadline-met repeats agree within 0.1–0.9 points. Every gap below is larger than that, so the losses are real. One exception: w17 is inside the 6% noise band.

## 1. What a win needs, workload by workload

"Floor" means the best deadline-met any policy reached, minus 1 point. The get limit is the champion's get p99 plus 10% (rule 2).

| Workload | Query deadline-met, champion → needed | Gain needed | Get p99, now → limit | Put deadline-met, champion / floor | Other limits |
|---|---|---|---|---|---|
| w5 | 86.88 → 88.09 | +1.21 | 81.0 → 89.1 | 98.60 / 98.07 | put p99 ≤ 133 |
| w6 | 86.88 → 87.82 | +0.94 | 81.0 → 89.1 | 98.66 / 97.87 | |
| w7 | 82.68 → 85.91 | +3.23 | 84.5 → 93.0 | 98.34 / 97.38 | sync p99 ≤ 207 |
| w8 | 82.66 → 86.03 | +3.37 | 86.0 → 94.6 | 96.77 / 95.97 | sync p99 ≤ 192 |
| w9 | 82.34 → 83.86 | +1.52 | 86.5 → 95.2 | 96.47 / 96.00 | multiget floor 98.88 |
| w10 | 87.48 → 90.27 | +2.79 | 113.5 → 124.9 | 97.42 / **97.38** | puts have only 0.04 points of room |
| w12 | 91.69 → 92.56 | +0.87 | 174.5 → 192.0 | 99.36 / 98.61 | lease 95.11 / floor 94.22 |
| w17 | point p99 223.5 → **≤221.5** | −2 µs | | fanout 99.85 / floor 98.87 | health p99 ≤ 127.5 |

Puts have at most 1 point of room on every workload, so the queries' gain cannot come from puts.

## 2. Why queries miss under the champion but not under prio

- **Which threads run ahead.** All HIGH kinds share a 100 µs deadline. The champion ranks a thread by its deadline plus 8 times its length. A query counts as about 21 µs, a get as 6, and the put/sync label is capped at 13. So a query runs after any get unless the query was ready 120 µs earlier, and after any put or sync unless it was ready 64 µs earlier (32 µs for w7's unhinted syncs, which count as 17). Prio runs only older HIGH threads ahead of a query.
- **Queue wait.** On w5 the query queue-wait p99 is 145.6 µs under the champion against 115.6 under prio. Query p90 latency is 111 against 103.5.
- **Late at pick is not the gap.** "Late at pick" means the thread was already past its server-side deadline when picked. On w5 that is 1.79–1.90% of deadline picks under the champion and 1.88–1.90% under prio. Even if every one were a query, that is at most 2.7% of queries, against 13.1% of queries that miss at the client. So at least 80% of misses are picked before the server's deadline but finish late. The server's deadline clock starts only when the hint is applied (apps/loadgen/src/hintmap.rs), so it misses the time before that.
- **p4's rescue fires too late.** A query is rescued only when its slack is between 9 µs and 9 µs plus the chosen thread's length. That means after 64–70 µs of waiting when the chosen thread is a get, or 57–70 µs when it is a put or sync.
  - At the headline load, a query's median time outside the queue is 34–41 µs (w5: p50 38 µs, queue-wait p50 1 µs). So a query that has waited past about 60–66 µs already misses at the client.
  - The 13 µs margin was measured at light load. As a result, rescues fire at or after the point of no return, and queries waiting 40–60 µs get no help.
  - On w12 rescues never help queries: p14's ratio rule bars a query (about 72 µs) from going ahead of gets or leases (6–12 µs).
- **Time-slice re-queues do not matter.** w5–w10 have 42–157 per 3-second run, against about 0.9M HIGH picks. w12 has about 17k for every policy, prio included.
- **The gap tracks hidden long work.** Each point of query deadline-met lost tracks the HIGH work per request allowed ahead of queries.
  - Lost per µs per request: about 1.2 points on w5–w8 and 0.7 on w9–w10.
  - Work allowed ahead: about 1.8 µs per request on w5/w6, 3.5 on w7–w9, 5.2 on w10.
  - The extra work on w7–w10 is 30 µs syncs, and on w10 also multigets, hidden under short labels.

**What sjf_timed did on w8.**
- It learned that the shared "1 µs" label (puts and syncs) really averages about 18 µs and used that uncapped. A put or sync then passed only queries that arrived less than 24 µs before it (the champion: 64 µs). It also used p3's 20 µs urgency guard.
- Gains: query deadline-met +4.4 points (87.03%), query queue-wait p99 154 against 181.
- Costs: puts lost 10.5 points (86.31%), sync p99 rose 46% (223.5 µs), and get p99 rose 13% (97.5 µs; no give-up rule). It fails rules 2, 3 and 6.
- Its gain per µs per request moved was 1.66 points, against 1.2 for prio's wholesale order. Targeting queries at risk is cheaper than reordering whole kinds.

**w17.**
- Point queue-wait p99 is 143.8 µs under prio against 167.6 under the champion. Fanout queue-wait p99 is the same under both (about 144).
- p17's pass lets an older point go ahead of a fanout only while the fanout keeps 120 µs (40% of its 300 µs budget). That holds until the fanout has waited about 115 µs, and in the worst 1–2% of bursts fanouts wait longer, so points wait behind them.
- A queued health check, being the shortest thread, also hides the point from that pass.
- Prio shows that oldest-first between points and fanouts costs fanouts only 0.05 points (99.80 against 99.85).
- A pass inside the region can recover the 2 µs the win needs. That is less than the champion's own repeat spread (219/228).

## 3. Hypotheses (ranked)

1. **Rescue priced at the chosen thread's real length.** In the rescue check, use the label's uncapped learned length (34 µs for a sync or flush) and a margin of about 30 µs. Keep the 13 µs give-up rule. Honest get labels behave as now.
   - Targets w7–w10 (2.15–3.85 µs per request of hidden long work), plus w5 and w9.
   - Risk: puts on w10.
2. **Earlier rescue, only when affordable.** Raise the rescue trigger to about 30 µs, but only when the chosen thread keeps p16's 40% reserve. On w12, relax the ratio rule for this case.
   - Targets w5, w6, w12, which need about 1 point.
   - Get queue-wait p99 may rise by at most about 8 µs.
3. **w17: lower p17's older-passer reserve to 15–20%,** and let the second scan consider the oldest point even when a health check is the shortest thread.
   - Expected point p99 about 209–215 µs.
   - Check w16 and w18–w20, which must keep their wins.

Counters requested: per-kind late at pick, rescue and give-up counts, and pass counts per branch.

## 4. Lessons

workload: On the key-value workloads, a query loses about 1 point of deadline-met per µs per request of HIGH work allowed ahead of it, and 30 µs jobs hidden under short labels are most of that work on w7–w10.
policy: p4's 13 µs margin was measured at light load. At the headline load a query spends 34–41 µs outside the queue, so rescues fire after the query is already lost. Move the rescue earlier and price it at the chosen thread's real length.
measurement: The server's late-at-pick counter covers at most 20% of client misses, because the server's deadline starts when the hint is applied. Compare policies by client deadline-met together with per-kind queue wait, not by late at pick.
