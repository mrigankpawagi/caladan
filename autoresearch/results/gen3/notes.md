# Generation 3: bursts

## What happened

1. **Workload w4** (workload agent): w3's traffic and hints arriving in bursts
   (every 1000 µs, 250 µs at 1.6x the average rate), the first workload to use
   the new burst support. Gate: PASS at 380k req/s; sjf_guard 86 µs vs about
   140 for prio and edf_high and 167 for fifo.
2. **Report** (measurement agent): bursts add 31–55 µs to the champion's get
   p99; the urgent-query hypothesis is only partly supported. It also found
   that the client sent 2.5–6.3% below the nominal rate under bursts.
3. **Client bug fixed, w4 superseded by w4b.** The burst generator scaled each
   arrival gap by the rate of the phase it started in; it now uses exact time
   rescaling (client sends 99.1–99.9% of nominal). w4b is the same workload
   re-measured: gate PASS at 380k; fifo 189, prio 169.5, edf_high 165.5,
   sjf_guard 94 µs. The report got an orchestrator addendum with these numbers.
4. **Policy p4 sjf_rescue** (policy agent): treat HIGH requests with less than
   13 µs of slack as already lost, and let a get pass an urgent query when the
   query can spare the time. **Rejected** on rule 1: w4b get p99 86.5 vs 94.0
   µs (−8%, real but below the 10% threshold); w3 −4.5%, w1 and w2 within
   noise, w0 overhead fine. sjf_guard stays champion.

## Orchestrator changes this generation

- **w0 overhead rule** now uses p99 one level below the headline and the
  throughput sustained when overloaded (w0's headline point drifted 150–196 µs
  across runs). Past verdicts unchanged.
- **`run.py --levels`**: older workloads are judged at their headline load
  only (w0 at its two overhead levels; workloads with a LOW kind, and the
  newest, get full sweeps). Cuts policy evaluation on older workloads from 56 s
  to about 20 s per experiment.
- **Burst generator fixed** (above); **judge.py** fixed so w0's overhead rule
  does not need headline data; leaderboard and judge skip superseded workloads.

## Observations to keep

- Under bursts queries miss their 100 µs deadline about 13% of the time under
  every priority policy: the burst backlog, not order within HIGH, dominates
  query latency. The remaining get tail is waiting behind running requests.
- The 10% acceptance threshold now binds on real but incremental gains
  (sjf_rescue −8% with non-overlapping repeats). Not changed: moving the
  threshold after seeing a result would bias the loop.

## Open requests for the owner

Preemption of a running long request by an urgent one (every policy agent so
far); a hint-aware work-stealing filter; recording each request's packet
arrival time in the runtime (p4), so policies can account for time spent
before the thread was queued; per-kind queue-wait counters and a counter for
picks where an urgency rule overrode the normal order.

## Node time

About 26 minutes (w4, then w4b after the client fix, and p4's evaluation),
slightly over the 25-minute cap because of the re-run; the reduced evaluation
kept the rest small.
