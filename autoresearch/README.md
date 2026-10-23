# autoresearch: evolving per-thread scheduling policies for Caladan

This directory runs a research loop. Each **generation**, one agent proposes a
harder **workload**, the existing **policies** are measured on it, a second
agent turns the numbers into a **bottleneck report**, and a third agent proposes
a new policy aimed at that bottleneck, which is then measured on every workload
so far. Everything is recorded as small git commits tagged with the
generation, so any number can be traced back to the exact workload, policy,
and code that produced it.

The human owner watches one generation at a time and decides whether to
continue.

## The question

Caladan schedules the threads inside an application in the order they became
ready (first in, first out). Our fork lets an application attach optional
**hints** to a thread: a priority class (HIGH, NORMAL, LOW), a deadline, and an
expected service time. A **policy** decides which ready thread a core runs
next, using whatever hints are present. Which policies help which workloads,
and what do they cost? Only scheduling *inside* an application changes; the
IOKernel, which decides how many cores each application gets, is untouched.

## Words used here

- **Request kind**: a type of request the client sends (e.g. `short`, `long`).
  The client only says which kind a request is; the **server** decides each
  kind's hint, as a real service would.
- **Workload**: a traffic mix (kinds, their service times and shares), the
  server's kind-to-hint map, the server's cores, the load levels to try, and
  optionally an antagonist (a best-effort process competing for the server's
  cores and caches). One JSON file in `workloads/`.
- **Policy**: one `choose_<name>` function in the scheduling policy region of
  `runtime/sched.c`, plus a card in `policies/`. Selected per run by name.
- **Mode**: `hints` (the server applies its hint map) or `ignore` (the server
  applies no hints; same binary, same traffic).
- **Build**: `hints` (our fork) or `stock` (hint support compiled out, i.e.
  Caladan as published). Only used for the overhead check. `hints-nostats` is
  the hints build with the per-pick measurement counters switched off
  (`run.py --sched-stats off`); experiments normally keep them on.
- **Headline load**: the busiest load level at which the baseline (fifo,
  hints mode, hints build) answers at least 99% of requests, keeps client
  schedule adherence at least 99%, and keeps overall median latency within
  1.5x of its value at the lightest load. In other words, as busy as the server gets
  before it is overloaded.
- **Score**: the workload's chosen kind and percentile (e.g. `short` p99) at
  the headline load, median over repeats. Lower is better.
- **p99**: the latency 99% of requests beat (tail latency).

## Who does what

- **Workload agent, policy agent, measurement agent**: propose workloads,
  write policies, and write reports, from the prompts in `prompts/`. They reply
  with text; they do not edit files.
- **Orchestrator** (Claude Code, driven by the owner): runs the generation
  protocol, saves and commits agent outputs, reviews policy code, runs
  experiments, and checks reports against the raw data. Between generations it
  also fixes the loop's own infrastructure when that is really needed (for
  example, measurement overhead that would distort results), in separate
  commits explained in the next generation's notes. It never changes the
  IOKernel and never writes policies itself.
- **Owner**: watches each generation and decides whether to continue.

## One generation

| Step | Who | Output | Commit message |
|---|---|---|---|
| 1. Propose harder workloads (from gen 13: two or three agents, each assigned an untouched difficulty dimension) | workload agents (`prompts/workload_agent.md`) | proposals in `results/genN/proposals/` | (with the chosen workload) |
| 1b. Probe the proposals and keep the one whose champion spends the largest share of its tail in the runqueue | orchestrator, `probe.py` | `results/genN/probe/` (local) | `autoresearch gen N: workload wN <slug>` |
| 2. Gate it: baseline not trivially overloaded, a FIFO penalty exists, the best policy leaves headroom | orchestrator, `run.py` | results in `results/genN/` | (with step 3) |
| 3. Measure every policy on the new workload, hints and ignore | `run.py` | `results/genN/summary.csv`, `counters.csv` | `autoresearch gen N: results for wN` |
| 4. Bottleneck report | measurement agent | `results/genN/report.md` | `autoresearch gen N: measurement report` |
| 5. Propose a policy | policy agent | code in the policy region + `policies/pM-*.md` | `autoresearch gen N: policy pM <name>` |
| 6. Measure it on every workload, plus the overhead check on w0 | `run.py` | more rows in `results/genN/` | `autoresearch gen N: results for pM` |
| 7. Leaderboard, prompt lessons, notes | orchestrator, `summarize.py` | `LEADERBOARD.md`, prompt "Lessons" lines, `results/genN/notes.md` | `autoresearch gen N: leaderboard and lessons` |

The gate and the acceptance decision are computed by `judge.py` (`./judge.py
gate --workload wN`, `./judge.py accept --policy <name>`), which prints the
numbers behind each verdict; the orchestrator records its output in the
generation's notes. The policy to beat is the **champion**: the most recently
accepted policy, or `prio` until one is accepted (`./judge.py champion`).

Acceptance rules for a new policy (also in the policy agent's prompt): the new
workload's score improves by at least 10% or 10 µs over the current best; no
earlier workload gets more than 10% worse; NORMAL p99 at the headline load
rises at most 25%; LOW still completes at least 90% of its requests below
saturation; on w0 (no hints) p99 one level below the headline load stays
within the noise band and the throughput sustained when overloaded within 1%;
and any
other kind with a deadline loses at most 1 percentage point of its
deadline-met rate. From generation 19, also: on every earlier workload the
champion wins (below), the new policy must win too. A rejected policy stays in
the tree with `status: rejected`.

**Winning a workload, and the end of the loop.** The loop ends no later than
generation 25, with a champion that wins every workload (the owner's goal,
set in generation 19). Since generation 20 (the owner's choice, after the
first definition proved to conflict with rule 2) a policy *wins* a workload if
no other policy *dominates* it at the headline load: is better beyond noise on
something (score more than 6% lower, or some kind's deadline-met more than 1
point higher) and worse beyond noise on nothing. `./judge.py wins` prints the
table for the champion. The first definition (be within 1 point of the best
deadline-met of any policy, then within noise of the best such policy's
score) made prio's query deadline-met the bar on w4b–w12; matching it meant
behaving like prio there and doubling get p99, which rule 2 forbids, and four
mechanisms tested on the nodes gained at most about 0.5 point within the rules.
Plan: generation 19 added w20 and re-measured the eight workloads the champion
lost, with their bar-setting policies, in one session (cross-session drift is
about 6% of p99 and 1.5 points of deadline-met): the losses on w5–w10 and w12
(query deadline-met 1.9–4.4 points below prio's) and w17 (prio 6.9% faster)
are real, and w14's was drift. Generations 20–25 add no workloads: each is a
convergence generation, with a measurement report on the losses, a policy
aimed at them, and `./eval_policy.sh <gen> <policy> converge`, which
re-measures the bar-setters of every lost workload in the same session and
judges with `--converge` (rule 1 becomes "wins more workloads than the
champion"; rules 2–7 apply to every workload). The last generation ends with a
single-session confirmation of the final policy against fifo, prio and each
workload's best deadline-keeper.

Two practices from the convergence generations. **Stale rivals:** the best of
many measurements from older sessions is a lucky draw, so before a win table
is trusted, `./judge.py rivals --before <gen>` lists each workload's decisive
rivals not measured in the current session, and they are re-measured (with the
champion) until the list is empty; the first two rounds turned w1–w3, w11 and
w13 back into wins. **Policy probes:** where the policy agent's model is
uncertain, it submits up to three variants as thin wrappers over one
implementation (one table row each), and the orchestrator runs each variant
and the champion at the headline of the targeted and at-risk workloads (2
repeats, about 30 minutes) before a full evaluation of the best one.

To save node time, a new policy is judged on *older* workloads at their
headline load only (`run.py --levels <load>`), or the headline and the two
levels below it for workloads with a LOW kind (rule 4 checks the measured
levels up to the headline); w0 runs the level below its headline and its top
level; the newest workload gets the full sweep (`eval_policy.sh` does all of
this).
Headline loads come from fifo's full sweeps, which every workload has.

**Paired confirmation.** On older workloads the champion's numbers were
measured in an earlier session, and some quantities drift between sessions
more than the rules allow: in gen 6, a policy whose decisions on w5 are
identical to the champion's measured 86.5% query deadline-met against the
champion's 88.1% from gen 4, while repeats inside one session agree within
about 0.3 points. So when the judge rejects a policy whose score on the
newest workload did improve enough (rule 1), `eval_policy.sh` re-measures the
policy and the champion back to back on every failing workload at the same
levels (`run.py --paired`, runs labelled p1, p2, ... and alternating between
the two policies; the full sweep for the newest workload), and the judge
decides those workloads from the paired runs alone. A policy that misses
rule 1 is rejected without confirmation.

Nothing is ever overwritten. Workloads, policies, and results only accumulate;
a broken workload gets a new revised file. The only regenerated file is
`LEADERBOARD.md`, and its history is in git.

## Files

```
README.md            this file
LEADERBOARD.md       generated summary: policies, scores per workload, curves
plots/               generated SVG plots shown in LEADERBOARD.md
calibration.json     gen 0 measurements: fake-work speed, noise band, timings, budget
run.py               runs experiments on the two nodes (see ./run.py --help)
summarize.py         builds LEADERBOARD.md, plots/, and results/genN/tables.md
probe.py             quick probes of workload proposals (results/genN/probe/)
lib/plots.py         the plots (plain SVG, no plotting library)
judge.py             gate and acceptance decisions, and the current champion
eval_policy.sh       judge a new policy on every scored workload (reduced sweeps), then judge.py
lib/                 spec validation, ssh helpers, output parsing
nodes.json.example   node settings; copy to nodes.json (ignored by git)
workloads/           one JSON file per workload, plus README.md (format)
policies/            one card per policy, plus README.md (format, code contract)
prompts/             the three agent prompts and CHANGELOG.md
results/genN/        report.md and notes.md (committed); summary.csv, counters.csv,
                     meta/*.json, raw/*/rps*.out, ledger.json (node time used) and
                     tables.md stay on the machine that ran them (git-ignored)
```

## Running

Prerequisites: two CloudLab nodes with ConnectX-4 or newer NICs (the
experiments so far used xl170 nodes with Ubuntu 22.04), the fork cloned in
`~/caladan` on both, and one full build (see the top-level README). Then:

```
cp nodes.json.example nodes.json         # edit hostnames
./run.py --gen 1 --workload workloads/w1-short-high-vs-long.json \
         --policy fifo,prio --mode hints,ignore
./summarize.py --gen 1
```

`run.py` refuses to run if the code under test has uncommitted changes or is
not pushed: the server checks out and builds exactly that commit, and every
result records its sha.

## Tracing a number back

Every row in `results/genN/summary.csv` has a `run_id`
(`<workload>__<policy>__<mode>__<build>__r<repeat>`). Its
`results/genN/meta/<run_id>.json` records the code sha, the workload file and
its hash, the nodes, and timings. The workload and policy cards name the
generation and commit that introduced them.

The measurement data (CSVs, run metadata, raw client output, tables and
ledgers) is not in git, to keep the repository and its pull requests
reviewable; it lives in `results/` on the machine that ran the loop, and
`summarize.py` and `judge.py` need it there. History was rewritten on
2026-10-21 to remove it from earlier commits; run metadata from before then
records the old commit hashes.

## Budget

Measured in generation 0 (details in `calibration.json`): one experiment of six
load levels takes 56 s of node time, a rebuild after a policy change 34 s, and
repeats differ by up to about 6%. A generation therefore costs about
(2N + 4) x 112 s + 126 s: 13 minutes for generation 1, growing by about 4
minutes per generation as workloads and policies accumulate. The cap is **25
minutes of node time per generation**; beyond it, the orchestrator trims in
this order: re-measure only baseline and accepted policies on the new workload,
drop the two lightest load levels on older workloads, and use one repeat for
policies more than 15% behind the best. `results/genN/ledger.json` records the
node time actually used. An 8-hour CloudLab slot fits about 10 generations.

In practice later generations used 25–35 minutes, mostly for the reduced
evaluation over a growing suite and for paired confirmations. From gen 13 the
proposal probes add about 3 minutes per proposal. The cap is a guide, not a
stopping rule: the owner asked the loop to keep running without one.
