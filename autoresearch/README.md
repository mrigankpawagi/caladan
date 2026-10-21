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
| 1. Propose a harder workload | workload agent (`prompts/workload_agent.md`) | `workloads/wN-*.json` | `autoresearch gen N: workload wN <slug>` |
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
deadline-met rate. A rejected policy stays in the tree with `status: rejected`.

To save node time, a new policy is judged on *older* workloads at their
headline load only (`run.py --levels <load>`), or the headline and the two
levels below it for workloads with a LOW kind (rule 4 checks the measured
levels up to the headline); w0 runs the level below its headline and its top
level; the newest workload gets the full sweep (`eval_policy.sh` does all of
this).
Headline loads come from fifo's full sweeps, which every workload has.

Nothing is ever overwritten. Workloads, policies, and results only accumulate;
a broken workload gets a new revised file. The only regenerated file is
`LEADERBOARD.md`, and its history is in git.

## Files

```
README.md            this file
LEADERBOARD.md       generated summary: policies, scores per workload, curves
calibration.json     gen 0 measurements: fake-work speed, noise band, timings, budget
run.py               runs experiments on the two nodes (see ./run.py --help)
summarize.py         builds LEADERBOARD.md and results/genN/tables.md
judge.py             gate and acceptance decisions, and the current champion
eval_policy.sh       judge a new policy on every scored workload (reduced sweeps), then judge.py
lib/                 spec validation, ssh helpers, output parsing
nodes.json.example   node settings; copy to nodes.json (ignored by git)
workloads/           one JSON file per workload, plus README.md (format)
policies/            one card per policy, plus README.md (format, code contract)
prompts/             the three agent prompts and CHANGELOG.md
results/genN/        summary.csv, counters.csv, meta/*.json, raw/*/rps*.out,
                     ledger.json (node time used), tables.md, report.md, notes.md
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
