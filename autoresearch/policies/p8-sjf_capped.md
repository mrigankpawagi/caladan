# p8: sjf_capped

- id: p8
- config: sjf_capped
- generation: 7
- status: candidate
- builds_on: p5
- changed_from_previous: p5 plus: a HIGH thread's length is the run time learned for its run-time hint without p5's floor (so it can fall below the hint, as in p6) and at most 8 µs above p5's starting value of hint plus 4 µs; a HIGH thread without a run-time hint counts as 17 µs (p5: 4 µs); and the too-late rule and rescue check measure slack with that length, too late meaning less than 9 µs to spare (p5: slack from the hint, less than 13 µs)
- commit: dbbe26c

## What it does
Like sjf_learn, each core runs helper threads first, then HIGH, NORMAL and LOW threads. Among HIGH threads the shorter request normally goes first, a request that can no longer make its deadline steps aside for shorter ones, and one about to become too late is let in just in time. Each core also times the requests it runs and learns how long requests with each run-time hint really take. What changes is how far the core trusts those timings. It accepts that a kind is quicker than its hint, so w6's lookups labelled 20 µs count as the 6 µs they take. But it lets a kind count as at most 8 µs slower than sjf_learn's starting guess, so w8's "1 µs" label, shared by quick puts and 30 µs syncs, ranks as 13 µs: behind lookups and still ahead of queries. A request with no run-time hint, like w7's syncs, counts as 17 µs, just behind that, and each request's time to spare is measured with the same length it is ranked by.

## Why (hypothesis)
results/gen7/report.md, sections 1, 3 and 6: on w8 the champion's get p99 is 145.0 µs, and 97.3 µs of that is runqueue wait. Syncs carry the puts' 1 µs hint, so sjf_nohint ranks them with puts, ahead of gets. No rule that reads only hints can tell a sync from a put. The two learners rank the shared label by its learned run time (about 18 µs on average, more with the estimator that leans toward long runs). That cut get p99 to 89.5 and 96.5 µs but put puts level with or behind queries, and put deadline-met fell 11–14 points.

p8 is the report's hypothesis 1, run on p5's rules. With learned lengths of about 6 µs for gets, 13 µs for the capped "1 µs" label, 17 µs for a blank hint and about 21 µs for queries, the turns counted from becoming ready (100 µs deadline) are +148, +204, +236 and +268. So:
- A get goes ahead of any "1 µs" thread that became ready less than 56 µs before it. Under the champion it goes ahead of almost none.
- The "1 µs" threads keep their place ahead of queries. A query passes them only in its rescue window (57–70 µs of waiting), and after 70 µs a query is too late and waits for them.
- Gets pass queries readied up to 120 µs earlier, the same margin as the champion's.

**Why p5's rules rather than the champion's (and against hypothesis 2's order).** On w5, sjf_learn and sjf_timed used the same learned put length.
- Under p3's rules (sjf_timed), put runqueue-wait p99 was 83.8 µs and put deadline-met 97.15%.
- Under p4's rules (sjf_learn), they were 40.0 µs and 98.57%. In gen 7's paired runs sjf_learn's puts matched sjf_guard's: 98.66% against 98.65%.
- The mechanism: under p3, a query that is already too late keeps its turn and passes a put whose length was raised. Under p4 it waits for the shorter put. So a raised length is only safe with p4's rule.
- The same rule is worth about 7 µs to gets: w8 get wait p99 25.8 against 40.3 µs; w4b 86.5 against 94.0.
- The gen 7 paired re-check shows p5 itself would have been accepted in gen 4.

**The other three changes.**
- **No floor.** p5's floor rated w6's gets (hint 20) at 24 µs, longer than queries, and its too-late rule then held late gets behind newer queries (get p99 200 µs). sjf_timed's two-way learning fixed w6 (92 µs). With correct lengths, a late get waits only for shorter threads, and none are shorter. The gen 5 lesson's failure came from the wrong length, not from the yielding.
- **Blank hint counts as 17 µs.** p5 prices a thread without a run-time hint at 4 µs, ahead of gets. The champion's 8 µs would now sit ahead of the 13 µs puts. At 17 µs, w7 keeps the order gets, puts, syncs, queries: puts pass a sync that became ready up to 32 µs before them, and syncs pass queries up to 32 µs older.
- **Slack from the length.** Under p5 a "1 µs" thread counts as savable until 86 µs of waiting, and in its last 6 µs it goes ahead of gets. With its 13 µs length it is too late after 78 µs, so a fresh get waits only for "1 µs" threads that have waited 56–78 µs. The 9 µs line is p4's 13 µs minus the 4 µs that p4 added to every hint, which a learned length already contains. For a kind that runs in its hint plus 4 µs, the test is p4's.

**Expected on w8.** Get p99 about 95–115 µs (threshold 135.0), with get wait p99 about 30–55 µs. Puts now wait for gets (about 5% of core time) and are given up on 8 µs sooner. In exchange they lose fewer turns to queries: the champion runs urgent queries (63–83 µs of waiting) ahead of them, while p8 runs only queries in their rescue window (57–70 µs) and makes queries past 70 µs wait for them. On w5 that balance cost puts nothing. Expected put deadline-met 96.0–97.5% (floor 95.69).

**Other workloads.**
- **w5 and w6:** like sjf_learn on w5, with puts capped at 13 µs instead of about 12–17, so gets gain slightly less (about 85–95 µs). On w6 the result is the same once the lookups' length has been learned down.
- **w7:** gets about 90–110 µs (limit 128.2).
- **w1–w4b:** hints are honest and lengths land within a µs or two of hint plus 4, so decisions are about sjf_learn's and sjf_rescue's (w4b about 86–90 µs against the champion's 94).
- **w0:** no HIGH threads, so this is p4's path and the clock is never read.

## Cost
- **Puts and syncs on w8** wait for gets that become ready up to 56 µs after them. They count as too late after 78 µs of waiting (p5: 86) and then wait only for gets.
- **Puts on w7 are the main risk.** Blank syncs at 17 µs pass puts that became ready more than 32 µs after them, against 56 µs under the champion. Put deadline-met floor there is 96.98%.
- **Queries** that are too late (over 70 µs of waiting) step aside for every shorter kind, now including syncs. Query p99 may rise (limits 281.9 µs on w8 and 274.4 on w7). Deadline-met should hold, because only queries that are already lost wait.
- **Syncs on w7** now wait behind queries that are 32 µs older or more and still savable. Sync p99 may rise to about 175–205 µs (limit 218.1).
- **Per pick:** the same as p5. The clock is read at most once. There is one extra queue pass when a timed pick is pending, and a five-entry table lookup per HIGH thread. Without HIGH threads the only addition is one test.
- **Tuned constants:** the 8 µs cap, the 17 µs blank length and the 9 µs too-late line fit these hints (2 and 17 µs kinds, about 4 µs per-request overhead) and would need re-measuring elsewhere.
- **Learning limits as in p5:** five hint values per core; kinds sharing a hint share one estimate. The cap limits what a mixed label costs; it does not separate syncs from puts.

## Needs
These are outside the policy region, for the owner:
1. **A learning key separate from the run-time hint** (report hypothesis 3), so syncs can be learned as 34 µs while puts stay short.
2. **Preemption:** a get cannot pass a running 30 µs sync.
3. **Packets waiting on a busy core:** about 48 µs of the champion's get p99 is spent outside the runqueue.
4. **Counters:** each core's learned length per hint value, and how often the cap binds.

## Prediction (from the policy agent)

| Workload | Metric | Expected direction | Rough size |
|---|---|---|---|
| w8 | get p99 at 380k (score) | down | 145.0 → about 95–115 µs (threshold ≤ 135.0) |
| w8 | get runqueue-wait p99 | down | 97.3 → about 30–55 µs |
| w8 | put deadline met % / put p99 | flat | 96.69 → 96.0–97.5 (floor 95.69); 133.5 → 115–150 µs (limit 166.9) |
| w8 | query deadline met % / query p99 | flat to up / flat to up | 82.94 → 82.5–85.5 (floor 81.94); 225.5 → 215–250 µs (limit 281.9) |
| w8 | sync p99 | flat to up | 159.5 → 150–185 µs (limit 199.4) |
| w8 | batch / scan p99, scans answered | flat | 311.5 / 333.5 within ±5%; 100% |
| w7 | get p99 at 380k | down | 116.5 → 90–110 µs (limit 128.2) |
| w7 | put deadline met % | flat to slightly down (main risk) | 97.98 → 97.2–98.2 (floor 96.98) |
| w7 | sync p99 / query deadline met % | up / flat | 174.5 → 175–205 µs (limit 218.1); 83.28 → 82.8–84.5 |
| w6 | get p99 at 390k | down | 140.5 → 85–100 µs (like sjf_timed's 92) |
| w6 | put / query deadline met % | flat | 98.50 / 87.46 within ±0.6 |
| w5 | get p99 at 390k | down | 100.0 → 85–95 µs |
| w5 | put / query deadline met % | flat | 98.75 / 86.92 within ±0.5 |
| w4b | get p99 at 380k / query met % | down / flat | 94.0 → 85–90 µs; 87.14 within ±0.8 |
| w3 / w2 / w1 | score at 400k | flat to slightly down | 57.5 / 54.0 / 53.0 → 52–57 / 51–55 / 51–54 µs |
| w0 | p99 at 300k / sustained throughput at 450k | flat | 70.5 within 6% (≤ 74.7); within 0.5% |

## Results
(filled after evaluation)
