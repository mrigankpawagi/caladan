# Generation 9: multigets labelled exactly as lookups

## What happened

1. **Workload w10** (workload agent): w9 with the multigets' hint changed to
   the gets' entire entry (high, 100 µs deadline, 2 µs run time), so no hint
   field separates them. Gate: PASS. The headline fell to 345k this session
   (fifo's light-load median moved by 1 µs). Champion sjf_pair: get p99 137.5
   µs at 345k (79.5 on w9), 162.5 at 370k; get runqueue-wait p99 23.6 →
   87.2 µs.
2. **Report** (measurement agent): the gets' label now reaches its 14 µs
   cap, 1 µs above the puts' 13 µs cap, so gets rank 8 µs behind puts and
   syncs, and too-late gets yield to them. The measurements rank the labels
   the other way (about 13 against 18 µs). Top hypothesis: keep capped
   labels in their measured order.
3. **Policy p10 sjf_mixed** (policy agent): p9 plus one rule: when two capped
   labels rank against their measurements, both count one shared length,
   4 µs below the smaller cap. The agent tuned this in an offline model that
   calls the real choose functions and reproduced the champion's waits.
   **Accepted** on every rule without a paired confirmation: w10 −16.7%
   (114.5 µs); put deadline-met −0.84 points, near the limit.

## Orchestrator changes this generation

- **Plot colors past eight policies:** p10 is the ninth non-baseline policy.
  The oldest rejected policy (p4) now gives up its color and is drawn gray
  and dotted, and p10 takes the freed slot. Every other policy keeps its
  color.
- The gen 10 workload agent ran while p10 was being evaluated, as in gen 8.

## Observations to keep

- **Sharing evens out waiting rather than removing it.** Under p10, gets,
  puts, syncs and multigets all have runqueue-wait p99 of about 80 µs on
  w10. With identical hints for gets and multigets, the policy region can
  only choose who waits; a per-kind key from the server would let it do
  better.
- **The constants keep accumulating.** p10 adds a 4 µs drop to p8's 8 µs cap,
  the 17 µs blank length and p9's 250 µs split. The gen 10 workload tests
  whether they generalise by scaling every time by four.

## Open requests for the owner

Unchanged: preemption; hint-aware stealing; packet processing on every
reschedule while hinted threads wait; exact run times from the scheduler;
a learning key set by the server per kind; counters for learned lengths,
cap binding, and the too-late and shared-length rules.

## Node time

About 24 minutes: w10's matrix (10 min) and p10's evaluation (14 min).
