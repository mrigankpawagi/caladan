# Autoresearch, second loop: design

Protocol version 2.0, epoch 1. This file is the contract. Nothing below changes
mid-epoch; a change bumps the version, starts a new epoch, re-measures the
leaderboard, and is recorded in the changelog at the end.

## 1. Goal

Find one intra-process scheduling policy for Caladan's runtime that, using the
per-thread hints (priority class, deadline, expected service time), gives the
best tail latency to latency-critical requests on every workload in the suite
without hurting the rest, and show it with measurements a reader already
trusts. The IOKernel is never changed. Policies live in the scheduling policy
region of `runtime/sched.c` and nowhere else.

## 2. What is measured

Every run reports, per request kind, from the client's own timing:

| Metric | Unit | Role |
|---|---|---|
| p50, p99, p99.9 latency | µs | p99 decides; p50 and p99.9 are reported |
| p99 / deadline, p99.9 / deadline | ratio | for kinds that carry a deadline hint: the tail as a fraction of what the application asked for. A deadline is a hint, not a promise, so this normalizes kinds and workloads; it is not a pass/fail |
| throughput | responses/s | must equal the offered load at the headline; the capacity (the highest load level at which every deadline kind has p99 ≤ deadline) is reported per policy |

Nothing is combined into a score. A comparison is made kind by kind.

Each number is the median of 3 repeats, with the min–max range kept. Runs
that compare policies interleave them repeat by repeat in one session (one
`run.py` invocation), and the judge only compares rows from the same session.

**Headline load** of a workload: the highest offered load at which fifo
answers at least 99% of the requests the client sent and fifo's overall median
latency is at most 1.5× its median at the lightest level (not saturated). Decisions are made at the
headline load; the newest workload is swept at every level.

## 3. How two policies are compared

On one workload, in one session, policy A **improves on** B if
- at least one kind with a deadline has a p99 lower by more than 5%, and
- no kind (deadline or not) has a p99 higher by more than 5%,

where "by more than 5%" means the medians differ by more than 5% and the
two sets of 3 repeats do not overlap. p99.9 is reported next to p99 and must
not rise by more than 5% either. A does **not regress** from B if only the
second condition holds.

## 4. Acceptance of a policy

A candidate replaces the champion when, measured against the champion in
one session:
1. it improves on the champion on the newest workload;
2. it does not regress on any earlier workload;
3. on w0 (no hints) its p99 is within 5% of fifo's and its throughput under
   overload within 1%;
4. low-priority kinds still answer at least 90% of their requests below
   saturation.

The cumulative change of every kind against fifo, including background kinds
that priority policies slow down by design, is always shown in the
leaderboard so that slow erosion stays visible, and the owner reviews it at
every epoch end.

Rejected policies keep their card and code (status `rejected`), but are left
out of the leaderboard's plots.

## 5. Workloads

A workload fixes the request kinds (work, share of traffic, deadline, hint),
the server (cores), the client (connections, bursts, antagonist) and the load
levels. The workload agent proposes traffic; it does not choose what is
measured.

**Coverage grid.** Each generation's workload fills an empty cell: one
service family × one difficulty step not yet taken in that family. Families
are filled breadth first, at most 6 workloads per family.

| Family (real-world shape) | Base cell |
|---|---|
| key-value store: lookups, writes, range queries | w1 |
| RPC fan-out leaf: frontend reads and sub-requests with propagated budgets | |
| search leaf: full searches and type-ahead suggestions | |
| storage node: reads, appends, flushes, compactions | |

Difficulty steps: load (0.8 → 0.9 of capacity); bursts (none → short → long);
service-time spread (constant → exponential → bimodal); hint accuracy (honest
→ stale → missing → mislabeled); deadline spread (one budget → two → three);
cores (8 → 4); connections (16 → 48 → 128); antagonist (none → cache job on
burstable cores).

**Gate** for a proposed workload, measured with fifo, prio and the champion:
it has a headline load above the lightest level; under fifo at least one
deadline kind has p99 above its deadline; under the champion at least one
deadline kind has p99 above 0.8× its deadline. Otherwise the proposal is
revised once with the numbers attached.

## 6. Policies

- Code only in the policy region: one `choose_<name>` function, optional
  static helpers, one table row. No allocation, locks or blocking; the scan is
  bounded by the queue; the clock is read at most once per pick.
- The card states the rule as a principle in one sentence before any constant
  appears, and names every constant with its unit and why that value.
- **Complexity budget:** the champion's code (its function plus the helpers
  it uses) is at most 300 lines and 8 named constants. A proposal over budget
  must retire something.
- **Ablation at each epoch end:** every rule the champion carries is switched
  off in turn and re-measured; a rule that changes no workload beyond noise
  is removed.
- No offline model or simulator. Predictions in a card are stated as
  expectations with reasons, not model output.

## 7. One generation

| Step | Who | Output |
|---|---|---|
| 1. Propose a workload for the next empty grid cell | workload agent | `workloads/wN-*.json` |
| 2. Gate: fifo, prio, champion, 3 repeats, full sweep | orchestrator, `run.py` | `results/e1/genN/summary.csv` |
| 3. Report: where the latency-critical kinds' time goes, with numbers | measurement agent | `results/e1/genN/report.md` |
| 4. Propose a policy | policy agent | region code + `policies/pM-*.md` |
| 5. Evaluate: champion vs candidate interleaved, every workload at its headline (the newest swept), 3 repeats | orchestrator, `eval_policy.sh` | rows in `results/e1/genN/` |
| 6. Judge | `judge.py` | verdict in the generation's notes |
| 7. Record: leaderboard, notes, lessons, one PR comment | orchestrator | `LEADERBOARD.md`, `results/e1/genN/notes.md` |

Agents receive the design, the data and the reports. They never receive a
numeric target to hit.

An epoch is 5 generations. It ends with the ablation (§6), a re-measurement
of fifo, prio and the champion on every workload in one session, and the
owner's review.

## 8. Actors and what each one sees

| Actor | Sees | Produces | Must not |
|---|---|---|---|
| owner | PR comments, leaderboard, notes | goals, rule changes, reviews | — |
| orchestrator (Claude) | everything | prompts, runs, commits, notes, PR comments | change rules mid-epoch; hand agents targets; accept a claim without the numbers |
| workload agent | design, leaderboard, reports, the grid | one workload spec | choose metrics; tune to one constant of the champion |
| measurement agent | design, data, counters, cards | the report | propose policies |
| policy agent | design, region code, cards, reports, leaderboard | code + card | touch code outside the region; exceed the budget |
| judge (`judge.py`) | `summary.csv` | verdicts, the leaderboard's win table | — |
| the nodes | — | the only ground truth | — |

## 9. What goes in git

Per generation: the workload spec, the policy code and card, `summary.csv`
and `counters.csv` (a few hundred rows), `report.md`, `notes.md`, and the
leaderboard with its plots regenerated once in the record commit (marked as
generated so reviews collapse them). Raw client output, run metadata and logs
stay local. Every row carries the code commit and the session id.

The first loop (PR #5, branch `autoresearch`) stays as it was; its lessons
are summarized for the agents in `prompts/lessons-from-loop-1.md`.

## Changelog

- 2.0 (2026-10-23): first version of the second loop.
- 2.0.1 (2026-10-23, generation 3's gate): the headline rule's delivery
  check is against the requests the client sent, not the offered load; the
  client misses about 0.15% of its send slots at every load, which put w4's
  lightest level at 98.99% of the offered load. The headline loads of w0–w3
  are unchanged, so the epoch continues.
