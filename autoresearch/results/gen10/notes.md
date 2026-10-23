# Generation 10: four times the time scale

## What happened

1. **Workload w11** (workload agent): w9 with every time multiplied by four:
   work, run-time hints (8/4/68 µs), deadlines (400/1200 µs) and the burst
   period. Gate: PASS with a headline load of 90k, not the predicted 103k:
   long requests run at about 83 fake-work iterations per µs, not the
   calibrated 99.6, and 103k–109k overload every policy. Champion sjf_mixed:
   get p99 242.0 µs against fifo's 679.0.
2. **Report** (measurement agent): against fifo the champion is fine (−64%),
   but its gets lost their lead over puts and syncs: get runqueue-wait p99 is
   1.7 times w9's scaled by four. The fixed 50 µs sample drop hides the 145 µs
   syncs and flushes, the 8 µs cap would limit the gets' lead, and the 250 µs
   split no longer separates gets from multigets. Top hypothesis: scale those
   constants by one workload-wide time unit, equal to 1 on w1–w10.
3. **Policy p11 sjf_unit** (policy agent): each core reads a time unit from
   the tightest relative deadline of the HIGH threads it runs and scales the
   constants by it. **Rejected on rule 1**: w11 get p99 259.0 µs against
   242.0 (+7.0%; predicted 140–190). Every w11 kind came within about 2% of
   the champion's numbers, so p11 decided like p10: the unit evidently did
   not reach 4 on the real system, although the agent's offline model
   reached it. Champion stays p10.

## Why the model and the system disagreed (not verified)

The deadline is set at classification as an absolute time (microtime() plus
the relative deadline), and the ready time is stamped each time a thread is
made runnable. For a freshly queued handler, deadline minus ready time is
the relative deadline. Two effects outside the model would keep the unit
low: a handler readied a second time (after blocking) gets a new ready
time, so the difference understates its relative deadline, and p11 takes
the tightest value it sees at once; or the unit flaps, and each change
clears the learning table, which leaves lengths at hint plus 4 µs and also
ranks puts ahead of gets. No counter reports the unit or how often the table
is cleared, so neither is confirmed. This is the first time an offline model
built by an agent predicted a large gain that the nodes did not show.

## Orchestrator changes this generation

- The gen 11 workload agent ran during p11's evaluation, as before. Because
  of the node lease, the gen 11 workload (w12) was committed and measured
  before these notes; the order of commits reflects that.

## Observations to keep

- **Scale problems are real and unsolved.** On w11 the champion's gets wait
  1.7 times longer than at the original scale. A scale-robust policy needs a
  unit that survives re-readied threads, or per-kind scaling from each
  thread's own hints.
- **Counters are now the bottleneck.** The last four reports inferred learned
  lengths, and this one could not check the time unit. A counter for each
  core's learned lengths and unit would have caught p11's problem in one run.

## Open requests for the owner

Unchanged: preemption; hint-aware stealing; packet processing on every
reschedule while hinted threads wait; exact run times from the scheduler;
a learning key set by the server per kind. Raised in priority: counters
for each core's learned lengths, time unit, cap binding, and dropped
samples.

## Node time

About 26 minutes: w11's matrix (10 min) and p11's evaluation (16 min).
