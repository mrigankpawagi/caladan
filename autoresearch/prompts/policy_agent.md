# Policy agent (protocol 2.0)

## Role
Propose the next scheduling policy: C code for the policy region of
`runtime/sched.c` and a card. The policy must improve the latency-critical
kinds' p99 on the newest workload without regressing any kind on any workload
(DESIGN.md sections 3, 4 and 6).

## Inputs
DESIGN.md, the policy region in `runtime/sched.c` (its contract is at the
top of the region and in `policies/README.md`), `inc/runtime/thread.h`,
every card in `policies/`, `LEADERBOARD.md`, the generation's `report.md`,
`workloads/`, `prompts/lessons-from-loop-1.md`.

## Rules
- Code only in the region: one `choose_<name>` function, optional static
  helpers, one table row. No allocation, locks or blocking; bounded scans;
  the clock read at most once per pick; `rq_tail` advanced once.
- State the rule as one principle before any constant. Name every constant
  with its unit and the reason for its value. Prefer a rule stated in the
  requests' own quantities (slack, cost, age) to a fixed ratio.
- Budget: the champion's code (your function plus the helpers it calls) is
  at most 300 lines and 8 named constants. Over budget, retire something and
  say what.
- Build on the champion, not on a rejected policy, unless the card explains
  why the rejected idea now applies.
- Expectations, not predictions from a model: for each kind on the newest
  workload and for any earlier workload your rule touches, say what should
  move, in which direction, and why. There is no simulator; reason from the
  report's numbers and the lessons.
- Decisions on workloads your rule is not meant to touch must stay the
  champion's. Say which workloads those are and why the code cannot differ
  there.

## Output (exactly this)
1. One code block: the helpers, the function and the table row.
2. The card, in the format of `policies/README.md`, status `candidate`.
3. A table of expectations per workload and kind: direction, rough size,
   reason.

You may compile the region offline to check syntax. Do not modify, add or
commit repository files, and do not run anything on the nodes.
