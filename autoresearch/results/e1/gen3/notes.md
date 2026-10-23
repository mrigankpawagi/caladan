# Generation 3 (loop 2): w4, the storage node, and p4 afford

## What happened
1. **Workload w4** (storage node, base cell): 37 µs reads due in 130 µs beside
   10 µs appends due in 300 µs, with flushes and compaction steps as a third
   of the work. Gate at 240k: reads ×1.45 under fifo, ×1.20 under prio, ×1.25
   under the champion passonce, whose shortest-first pass helps the appends
   (127 → 102) and seemed to charge the reads. Its first gate found no
   headline load because the client answers 98.99% of the *offered* load at
   the lightest level; the delivery check is now against what the client
   sent (protocol 2.0.1), and no earlier headline changed.
2. **Report:** a tail read under prio waits 75.5 µs in the run queue, 62
   behind other reads and 13 behind appends; it has no slack by budget and
   8 µs by the rule, while the appends have 170–200 by budget and 5 by the
   rule. The report concluded that a pass must be priced against the passed
   thread's remaining slack, and that under the rules no candidate could be
   accepted on w4: passonce's 25 µs append gain is protected by the 5%
   no-regression rule, and the reads' 7 µs is under the 5% improvement line.
3. **Policy p4 afford** (passonce's pass only when every passed thread keeps
   its hinted slack; one reused constant). **Rejected:** on w4 the reads
   stayed where they were (165 vs 164 in one session) while the appends
   returned toward prio's tail (+20%); on w3 the suggestions' far tail got
   worse. w2, w1, w0 unchanged.

## What this says
- **The 7 µs was drift.** Measured in one session, passonce's pass costs the
  tail reads nothing: the report's attribution came from comparing prio
  (one session) with passonce (another, 43 minutes later). A 4% difference
  between sessions is ordinary here, which is exactly why the judge only
  compares within one session. Reports must say so too.
- **Slack-priced passes refuse the deep queues**, which is where the far
  tail lives, so they cost p99.9 on w3 for no gain anywhere.
- **The rule question stands, in a cleaner form.** Any policy that stops
  letting appends pass reads on w4 is rejected, because the appends' p99
  (×0.35 of their budget) may not rise 5% against passonce, even though the
  reads gain nothing from the change either way. The rule protects a gain
  the budget says is worthless; whether that matters is a question for the
  owner at the epoch review.
- passonce holds: it is still the champion, and on w4 it is within noise of
  prio on reads with far better appends.

## Orchestrator notes
- w5 (key-value, two budgets) and w6 (RPC leaf, 1 ms waves) passed their
  gates with fifo, prio and passonce during this generation; a first burst
  draft for the key-value family was set aside because with one HIGH kind
  bursts leave an in-region policy no decision.
- Node time: gate 7 min plus 3.5 for the champion, evaluation 26 min.
