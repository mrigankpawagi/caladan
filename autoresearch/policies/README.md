# Scheduling policies

A policy decides which ready thread a core runs next, inside one application
(the IOKernel's allocation of cores to applications is never changed). Every
policy is a small `choose_<name>` function in the **scheduling policy region**
of `runtime/sched.c` plus one row in the `sched_policies[]` table, and a card
in this directory. All policies stay compiled in and are selected per run with
the runtime config line `runtime_sched_policy <name>`, so any generation can
re-measure any earlier policy without old code. Rejected policies stay too,
with `status: rejected`: their numbers are still evidence.

## Card format

The header lines are parsed by `summarize.py`; keep the `- key: value` form.

```
# pN: <name>

- id: pN
- config: <name used in runtime_sched_policy>
- generation: <generation that introduced it>
- status: baseline | accepted | rejected | candidate
- builds_on: <id of the policy it modifies>
- changed_from_previous: <one line: exactly what differs from builds_on>
- commit: <sha of the commit that added the code>

## What it does
Two to five plain-English sentences.

## Why (hypothesis)
Which bottleneck in which report it targets, and what should change.

## Cost
Who pays (which class or workload), and the extra work per pick.

## Results
Pointer to results/genN/ and the leaderboard line; filled in after evaluation.
```

## Contract for the code (also at the top of the policy region)

- Called with the core's runqueue lock held and preemption disabled.
- Sees the `n` ready threads, oldest first, through `sched_rq_at(k, i)`.
- Returns the index of the thread to run; the shared code removes it.
- Must not block, allocate, take locks, or change the runqueue; O(n) time.
- May read any thread field (`prio_class`, `ready_tsc`, `deadline_tsc`,
  `service_tsc`), call `rdtsc()`, and use `k->policy_state[]`.
- Should run runtime helper threads (`THREAD_PRIO_SOFTIRQ`) first: they
  process packets and timers for everyone.
