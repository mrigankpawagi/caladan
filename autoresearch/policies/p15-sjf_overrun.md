# p15: sjf_overrun

- id: p15
- config: sjf_overrun
- generation: 14
- status: accepted
- builds_on: p14
- changed_from_previous: p14 plus: a HIGH thread readied again after more than 150 µs of total run time (so yielded at the 100 µs time slice at least twice; on w15 only the large lookups) runs after every waiting HIGH thread with the same label that has not run that long, and is never rescued ahead of the order's choice; against every other thread its place is p14's; no HIGH thread on w1–w14 runs that long, so there every decision is p14's
- commit: ddc13c9

## What it does
Like sjf_ratio, each core runs helper threads first, then HIGH, NORMAL and LOW threads, and among HIGH threads it runs short requests first. The system pauses any request that has run for 100 µs while others wait, and puts it back in the queue. sjf_overrun spots a request that comes back after more than 150 µs of running, using the run time the runtime already records for every thread. Such a request is clearly far longer than its label says. It now lets the waiting requests with the same label run first (on w15, the ordinary lookups queued behind a large lookup), and it can no longer jump the queue as urgent. It keeps its place against every other kind, so it still runs ahead of queries and other longer work. On the earlier workloads no HIGH request runs that long, so nothing changes.

## Why (hypothesis)
- **Where the gets' tail is:** the gen 14 report finds all of the gets' p99 rise from w14 (+136.5 µs) in runqueue wait (+143.5 µs at p99), with the p90 nearly flat. A large lookup's median is only 55.5 µs above its 825 µs run, so after each time slice it runs again almost at once (report §3, mechanism 1; hypothesis 1).
- **Why it runs again at once:** it comes back with the lookups' label and its original deadline, so it ties with the ordinary lookups on length and wins on deadline, even once it is too late.
- **How it is recognised:** on a time-slice yield the runtime puts the thread at the tail of the queue and gives it a new ready time. Its class, deadline and run-time hint are unchanged, and its accumulated run time (`total_cycles`, reset to 0 when the thread is created and added to on every switch; orchestrator checked) grows by the slice before the next pick. Ready time cannot serve here: a re-queued large lookup and a fresh query both show about 300 µs to their deadline (gen 10 and gen 11 lessons).
- **Why 150 µs:** a slice is 100–110 µs. Syncs, flushes and multigets (about 145 µs) come back at most once, with about 100 µs run. A large lookup comes back at about 200, 300, … µs, so 7 of its 8 returns are caught.
- **Why the first return is left alone:** at its first return a large lookup looks exactly like a sync or flush remnant. In the model, a 60 µs threshold raised sync p99 by 25% and cost multigets 0.2 points of deadline-met.
- **Why the same label, not the same length:** the report gives bigget only 25% of p99 room, and demoting it behind all fresh HIGH work cost +70–98% in simulation. Tying on equal length also caught puts and syncs, which share the lookups' learned length on some cores, and cost bigget +21% in the model. Tying on the same label costs it +5–6%.
- **Why no rescue:** at its second and third returns a large lookup still shows 70–170 µs of slack against its label. The rescue would jump it straight back ahead of the lookup that won the tie.
- **Offline check** (gen 13's model with each thread's run time added: the real policy region, 6 cores, 100 µs slice, bursts, stealing; it under-reads the real waits, so only relative changes count):
  - **Lockstep:** 0 of about 2.1M picks differ from p14 on w14, w13, w12, w10, w9, w5 and w2, because no thread there ever counts as overrun. On w15 0.23% of picks differ, and 98.8% of those are picks where p14 would have run the overrun thread.
  - **w15 at the headline load, two overhead settings, 16 seeds:** get p99 −13.6% and −17.2%.
  - **Other kinds on w15:** bigget +6.0% and +4.6%. Put, sync, query, multiget and lease p99 within ±1.5%, and their deadline-met within ±0.06 points.

## Cost
- **Large lookups:** from their second return they wait for the ordinary lookups queued on their core, about 8 µs each. Model: +5–6% p99, against 25% of room.
- **Per-pick work:** one comparison of the recorded run time per HIGH thread, and two label lookups only when exactly one of two compared threads has overrun. No extra clock read and no new state.
- **Limits:** a long-lived HIGH thread that sleeps and wakes builds up run time over its whole life and would count as overrun; the servers here create one thread per request.

## Prediction (from the policy agent, against sjf_ratio)

| Workload | Metric (headline load unless noted) | Expected vs sjf_ratio |
|---|---|---|
| w15 (73.75k) | get p99 | −10% to −18% (341.0 → about 280–305 µs; limit 306.9) |
| w15 | get runqueue-wait p99 | 264.8 → about 200–235 µs |
| w15 | bigget p99 | +3% to +12% (1282 → about 1320–1440; limit 1602.5) |
| w15 | put / sync / query / multiget / lease p99 | within ±5% |
| w15 | query / lease / put / multiget deadline-met | within ±0.3 points (room 1.0 each) |
| w11–w14 | every kind | identical decisions (no HIGH thread reaches 150 µs); noise only |
| w1–w10, w0 | every kind | identical decisions; noise only |

## Results
Accepted in generation 14 (judge.py, results/gen14/) against the champion
p14 sjf_ratio, on every rule and every workload, without a paired
confirmation.

| Workload | sjf_ratio | sjf_overrun | Change | Notes |
|---|---|---|---|---|
| w15 | get p99 341.0 µs | 261.0 µs | −23.5% | predicted −10 to −18% (280–305) |
| w15 | bigget p99 | 1282 µs | 1261 µs | −1.7% | predicted +3 to +12%; it did not pay |
| w15 | put / sync / query p99 | 417.5 / 546.0 / 1144 µs | 408.0 / 563.5 / 1132 µs | −2.3% / +3.2% / −1.0% |
| w15 | query / lease / put met | 85.50 / 95.31 / 98.88% | 85.12 / 95.37 / 98.94% | within 0.4 points |
| w14 / w13 | 204.5 / 176.5 µs | 197.5 / 185.5 µs | −3.4% / +5.1% | identical decisions; drift |
| w1–w12 | | | within noise | identical decisions |

Recognising a request by the run time the runtime records, rather than by
its hint or ready time, stopped re-queued large lookups from cutting ahead
of ordinary lookups at no visible cost to the large lookups themselves.
