# Workload specs

Each workload is one JSON file, `wN-<slug>.json`, never edited after its
generation is committed. A broken or superseded workload gets a new file
(`w3b-...`) and the old one is marked `"status": "superseded"`.

The client only chooses *which kind* each request is. The server maps each
kind to scheduling hints (`hint`), exactly as a real application would decide
that, say, cache lookups are latency-critical and scans are not.

| Field | Meaning |
|---|---|
| `id`, `slug`, `generation` | `w3`, `bimodal-burst`, the generation that introduced it |
| `title`, `description` | one line, and a plain-English paragraph |
| `changed_from_previous` | what is harder than the workload it builds on |
| `difficulty` | the knobs the workload agent turns (see prompts/workload_agent.md) |
| `server.kthreads`, `guaranteed_kthreads`, `spinning_kthreads` | server runtime cores; guaranteed must be even |
| `server.fakework` | the work each request does per iteration, e.g. `stridedmem:1024:7` (see apps/loadgen/src/fakework.rs) |
| `client.conns`, `duration_s`, `rampup_s`, `discard_pct` | client connections, seconds measured per load level, seconds of ramp-up, % of requests discarded as warm-up |
| `kinds[].name`, `service`, `weight` | request kind, its work in iterations (`constant:N`, `exponential:MEAN`, `bimodal:P:A:B`, `zero`), and its share of traffic |
| `kinds[].deadline_us` | client-side deadline used only for the DeadlineMet column (0 = none) |
| `kinds[].hint` | what the server tells the scheduler: `class` (normal/high/low), `deadline_us` (relative), `service_us` (expected run time) |
| `load_rps` | ascending offered loads to sweep, requests per second |
| `score.kind`, `score.percentile` | the request kind whose tail latency the policies compete on, and which percentile |
| `burst` | optional bursty arrivals: `{"period_us", "duty", "factor"}`. In every period the first `duty` fraction of the time runs at `factor` times the rate of the rest; the average rate is still the level's `load_rps`, and all connections burst together. The busy-phase rate (`load_rps × factor / (duty × factor + 1 − duty)`) must stay at or below 700k req/s |
| `antagonist` | optional best-effort interfering process on the server: `{"threads", "n", "spec", "kthreads"}` for apps/netbench/stress (e.g. `cacheantagonist:4090880`) |
| `repeats` | how many times each experiment is repeated (medians are reported) |
| `notes` | anything else, e.g. how the capacity estimate was computed |

run.py rejects unknown fields, so a workload that needs a new feature (bursts,
TCP, more clients) needs a tooling commit first.
