# Generation 11: two time scales at once

## What happened

1. **Workload w12** (workload agent): w11 plus a HIGH lease kind on the
   original time scale (10% of traffic, 2 µs of work, 100 µs deadline), so
   the server runs requests on two time scales. Load levels were sized from
   w11's measured light-load medians, and the headline landed where planned,
   at 100k. Champion sjf_mixed: get p99 236.5 µs against fifo's 676.0.
2. **Report** (measurement agent): the leases change nothing for the w11
   kinds; the champion's gets still lose about 66 µs of lead to puts and
   syncs. Top hypothesis: read the time unit from the deadline most HIGH
   work carries, not the tightest.
3. **Policy p12 sjf_scale** (policy agent): p10 plus a per-core time unit
   from the running median of HIGH relative deadlines. The agent found why
   p11 failed by reading the code and the raw counters: the IOKernel's 100 µs
   time slice makes long requests yield, and they are queued again with a
   new ready time (17,241 preemptions per run at w12's headline, against
   about 100 on w10), which pinned p11's minimum low. **Accepted** on every
   workload: w12 −22.2% (184.0 µs), w11 −25.8% (179.5 µs), w1–w10
   unchanged. sjf_scale is the new champion.

## Orchestrator changes this generation

- Checked the policy agent's diagnosis against the raw RtStats before
  building: `preemptions=17241` at w12 100k under sjf_unit, 63–115 on w10.
- Ran the gen 12 workload agent while closing this generation, to use the
  rest of the node lease.

## Observations to keep

- **A diagnosis from the code beat a model.** The offline model behind p10
  and p11 had no time slice; the gen 11 agent found it in the runtime's
  configuration and the counters, and its fix held on the nodes.
- **The scale problem is solved for these workloads.** Under p12 the gets'
  runqueue-wait p99 on w11 and w12 is about 84 µs, near the four-times
  version of w9's floor. The remaining tail is time slices and running long
  requests, outside the policy region.
- **Lineage of accepted policies:** edf_high → sjf_guard → sjf_nohint →
  sjf_capped → sjf_pair → sjf_mixed → sjf_scale, each one rule on top of
  the last, each kept by the rules from hurting another deadline kind.

## Open requests for the owner

- **Counters (top priority):** each core's time unit and median, learned
  length per label, table clears, and time-slice yields of hinted threads.
- **The time slice and hints:** a way to keep a thread's original ready time
  across a time-slice yield, or to tell a re-queued thread from a fresh one.
- Unchanged: preemption by hint; hint-aware stealing; packet processing
  while hinted threads wait; a learning key the server sets per kind.

## Node time

About 25 minutes: w12's matrix (10 min) and p12's evaluation (15 min).
