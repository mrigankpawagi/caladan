# Autoresearch, second loop

An automated loop in which agents propose harder workloads and better
intra-process scheduling policies for Caladan's runtime, judged by fixed rules
on measurements from two CloudLab nodes. The rules are in **DESIGN.md**; read
that first. The first loop (PR #5, branch `autoresearch`) is kept as it was.

| File | What |
|---|---|
| `DESIGN.md` | the contract: metrics, comparison and acceptance rules, the coverage grid, the protocol, who sees what |
| `protocol.json` | the numbers the tools read: epoch, repeats, change threshold, budget |
| `run.py` | one experiment on the nodes; policies alternate repeat by repeat; every row carries the session id |
| `judge.py` | gate, accept, wins, plan, champion |
| `eval_policy.sh` | candidate against champion on every workload, then the verdict |
| `apply_policy.py` | static review of a policy proposal and insertion into the policy region |
| `summarize.py` | `LEADERBOARD.md` and `plots/` |
| `workloads/` | one spec per workload (see `workloads/README.md`) |
| `policies/` | one card per policy (see `policies/README.md`) |
| `prompts/` | the three agents' instructions and the lessons carried over from the first loop |
| `results/e<epoch>/gen<N>/` | `summary.csv`, `counters.csv`, `report.md`, `notes.md` (raw output stays local) |

Nodes: copy `nodes.json.example` to `nodes.json`. Runs need the committed
HEAD pushed; the server node builds it.
