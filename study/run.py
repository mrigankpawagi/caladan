#!/usr/bin/env python3
"""Runs one study workload on the two CloudLab nodes.

For each repeat, every listed policy is run once, in an order rotated per
repeat, so drift over the session affects all policies alike. One run starts
both IOKernels and the server with the policy, sweeps the workload's load
levels from low to high, and tears everything down.

  ./run.py workloads/w2a.json                     # all policies, 3 repeats
  ./run.py workloads/w1.json --policy fifo --build stock --mode ignore
  ./run.py workloads/w2a.json --dry-run           # print the plan

Results go to results/<workload>/<session>/: summary.csv (one row per run,
level and group), counters.csv (server counters per run and level), raw/
(the client's result lines), and meta.json (code sha, nodes, settings).

The server node builds the pushed commit under test; the client receives the
same loadgen binary.
"""

import argparse
import csv
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from lib import parse  # noqa: E402
from lib.remote import Node, RemoteError, copy_between, parallel  # noqa: E402

KILL = "pkill -9 -x loadgen; pkill -9 -x loadgen-study; sudo pkill -9 iokerneld; sleep 1; true"
CLIENT_BIN = "apps/loadgen-study"
POLICIES = ["fifo", "prio", "sjf", "edf", "hinted"]


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def git(*args):
    return subprocess.check_output(["git", "-C", HERE] + list(args), text=True).strip()


def code_sha():
    """The commit under test: HEAD, which must be clean in code and pushed."""
    if git("status", "--porcelain", "--", "../runtime", "../apps/loadgen", "../bindings",
           "../inc", "../iokernel"):
        sys.exit("uncommitted changes to code under test; commit and push first")
    sha = git("rev-parse", "HEAD")
    if not git("branch", "-r", "--contains", sha):
        sys.exit("HEAD %s is not pushed" % sha[:10])
    return sha


def runtime_config(ip, cfg, kthreads, policy=None, stats=False):
    lines = ["host_addr %s" % ip, "host_netmask %s" % cfg["netmask"],
             "host_gateway %s" % cfg["gateway"], "runtime_kthreads %d" % kthreads,
             "runtime_guaranteed_kthreads %d" % kthreads,
             "runtime_spinning_kthreads %d" % kthreads, "runtime_priority lc"]
    if policy:
        # "<policy>+steal": the policy plus hint-aware stealing
        base, _, extra = policy.partition("+")
        lines.append("runtime_sched_policy %s" % base)
        if extra == "steal":
            lines.append("runtime_sched_steal policy")
        elif extra:
            sys.exit("unknown policy option '+%s'" % extra)
    if stats:
        lines.append("runtime_sched_stats 1")
    return "\n".join(lines) + "\n"


def ensure_build(cfg, server, client, sha, build):
    """Builds `sha` on the server (hints or stock) and copies loadgen to the
    client, unless already done."""
    repo, want = cfg["repo"], "%s %s" % (sha, build)
    if server.run("cat %s/.study_build 2>/dev/null" % repo, check=False).strip() != want:
        log("building %s (%s) on server" % (sha[:10], build))
        server.run(
            "set -e; cd %s; git fetch -q origin; git checkout -q -f --detach %s; "
            "sed -i 's/^CONFIG_THREAD_HINTS=.*/CONFIG_THREAD_HINTS=%s/' build/config; "
            "make clean > /dev/null 2>&1; make -j20 > /tmp/study_make.log 2>&1; "
            "make -C bindings/cc -j20 > /tmp/study_make_cc.log 2>&1; "
            "cd apps/loadgen && touch build.rs src/main.rs; "
            "env %s cargo build --release > /tmp/study_cargo.log 2>&1; "
            "echo '%s' > %s/.study_build" % (repo, sha, "y" if build == "hints" else "n",
                                             cfg["cargo_env"], want, repo), timeout=1800)
    if client.run("cat %s/%s.build 2>/dev/null" % (repo, CLIENT_BIN), check=False).strip() != want:
        log("copying loadgen to client")
        if server.ssh == client.ssh:
            client.run("cp %s/apps/loadgen/target/release/loadgen %s/%s" % (repo, repo, CLIENT_BIN))
        else:
            copy_between(server, "%s/apps/loadgen/target/release/loadgen" % repo,
                         client, "%s/%s" % (repo, CLIENT_BIN))
        client.run("echo '%s' > %s/%s.build" % (want, repo, CLIENT_BIN))


def hosts(server, client):
    """The distinct machines: one if the client shares the server's node
    (the IOKernel then loops packets between the two runtimes)."""
    return [server] if server.ssh == client.ssh else [server, client]


def start_iokernel(node, cfg):
    node.run(KILL, timeout=60, check=False)
    node.bg("cd %s && exec sudo ./iokerneld %s nicpci %s" % (
        cfg["repo"], cfg["iokernel_args"], cfg["nic_pci"]), "/tmp/study_iok.log")
    node.wait_for("/tmp/study_iok.log", "running dataplane", 60,
                  fail_pattern="PANIC|panic|Error|failed")


def kinds_arg(spec, iters_per_us):
    """loadgen --kinds: name/distribution/weight/deadline, work in iterations."""
    out = []
    for k in spec["kinds"]:
        dist = k.get("dist", "constant")
        work = int(round(k["service_us"] * iters_per_us))
        d = "zero" if k["service_us"] == 0 else "%s:%d" % (dist, work)
        out.append("%s/%s/%s/%d" % (k["name"], d, k["weight"], k.get("deadline_us", 0)))
    return ",".join(out)


def hintmap_arg(spec):
    """loadgen --hintmap: kind index = class:deadline_us:service_us."""
    return ",".join("%d=%s" % (i, k["hint"]) for i, k in enumerate(spec["kinds"])
                    if k.get("hint"))


def mean_service_us(spec):
    tot = sum(k["weight"] for k in spec["kinds"])
    return sum(k["weight"] * k["service_us"] for k in spec["kinds"]) / tot


def load_levels(spec, cal):
    """Offered loads in requests/s. A workload gives either rps directly or
    utilisations rho, converted with the measured per-request overhead:
    capacity = kthreads / (mean service + overhead)."""
    if "rps" in spec:
        return [(r, None) for r in spec["rps"]]
    per_req = mean_service_us(spec) + cal["overhead_us"]
    cap = spec["server_kthreads"] / per_req * 1e6
    return [(int(round(rho * cap, -2)), rho) for rho in spec["rho"]]


def setup(cfg, server, client, spec, policy, mode, stats, cal):
    repo = cfg["repo"]
    parallel(lambda n: start_iokernel(n, cfg), hosts(server, client))
    server.put(runtime_config(cfg["server"]["ip"], cfg, spec["server_kthreads"], policy, stats),
               "/tmp/study_server.config")
    client.put(runtime_config(cfg["client"]["ip"], cfg, cfg["client_kthreads"]),
               "/tmp/study_client.config")
    hints = "--ignore-hints" if mode == "ignore" else (
        "--hintmap %s" % hintmap_arg(spec) if hintmap_arg(spec) else "")
    server.bg("cd %s && exec ./apps/loadgen/target/release/loadgen %s:%d "
              "--config /tmp/study_server.config --mode spawner-server --transport udp "
              "--fakework %s %s" % (repo, cfg["server"]["ip"], cfg["port"], cal["fakework"],
                                    hints), "/tmp/study_server.log")
    server.wait_for("/tmp/study_server.log", "^hints:", 30,
                    fail_pattern="panicked|bad config|Aborted|unknown runtime")


def run_level(cfg, client, spec, rps, cal):
    dur, ramp = spec.get("duration_s", 4), spec.get("rampup_s", 1)
    timeout = dur + ramp + 30
    mpps = "%.6f" % (rps / 1e6)
    cmd = ("cd %s && timeout %d ./%s %s:%d --config /tmp/study_client.config "
           "--mode runtime-client --transport udp --mpps %s --start_mpps %s --samples 1 "
           "--runtime %d --rampup %d --conns %d --discard_pct 10 --kinds '%s' "
           "--groups both --runtime_stat 2>&1; echo \"CLIENT_EXIT=$?\""
           % (cfg["repo"], timeout, CLIENT_BIN, cfg["server"]["ip"], cfg["port"], mpps, mpps,
              dur, ramp, spec["conns"], kinds_arg(spec, cal["iters_per_us"])))
    return client.run(cmd, timeout=timeout + 30, check=False)


def keep_lines(text):
    keep = ("Group,", "all,", "class:", "kind:", "RtStats:", "Means:", "WARNING", "Aborting",
            "CLIENT_EXIT=", "thread '")
    return "\n".join(l for l in text.splitlines() if l.startswith(keep)) + "\n"


def append_csv(path, rows):
    if not rows:
        return
    new = not os.path.exists(path)
    fields = list(rows[0].keys())
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerows(rows)


def experiment(args, cfg, server, client, spec, policy, repeat, out_dir, cal):
    run_id = "%s__%s__%s__r%d" % (policy, args.mode, args.build, repeat)
    raw_dir = os.path.join(out_dir, "raw", run_id)
    os.makedirs(raw_dir, exist_ok=True)
    summary, counters = [], []
    try:
        setup(cfg, server, client, spec, policy, args.mode, args.stats == "on", cal)
        for rps, rho in load_levels(spec, cal):
            out = run_level(cfg, client, spec, rps, cal)
            with open(os.path.join(raw_dir, "rps%d.out" % rps), "w") as f:
                f.write(keep_lines(out))
            rows, rt, flags = parse.parse_level(out)
            base = {"workload": spec["id"], "policy": policy, "mode": args.mode,
                    "build": args.build, "stats": args.stats, "repeat": repeat,
                    "load_rps": rps, "rho": rho if rho is not None else ""}
            for r in rows:
                summary.append(dict(base, **{f: r.get(f) for f in parse.ROW_FIELDS + ["mean"]},
                                    client_saturated=int(flags["client_saturated"]),
                                    failed=int(flags["failed"])))
            if rt:
                counters.append(dict(base, **rt))
            allrow = next((r for r in rows if r["group"] == "all"), None)
            log("  %-28s %7d rps  %s" % (run_id, rps, "FAILED" if flags["failed"] else
                "p50=%s p99=%s" % (allrow["p50"], allrow["p99"])))
            if flags["client_saturated"] or flags["failed"]:
                log("  stopping sweep")
                break
    except (RemoteError, subprocess.TimeoutExpired) as e:
        log("  ERROR: %s" % str(e).splitlines()[0])
        with open(os.path.join(raw_dir, "error.txt"), "w") as f:
            f.write(str(e))
    finally:
        parallel(lambda n: n.run(KILL, timeout=60, check=False), hosts(server, client))
    append_csv(os.path.join(out_dir, "summary.csv"), summary)
    append_csv(os.path.join(out_dir, "counters.csv"), counters)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workload")
    ap.add_argument("--policy", help="comma-separated (default: the workload's list)")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--mode", default="hints", choices=["hints", "ignore"])
    ap.add_argument("--build", default="hints", choices=["hints", "stock"])
    ap.add_argument("--stats", default="on", choices=["on", "off"],
                    help="runtime_sched_stats: per-pick counters (cost a little)")
    ap.add_argument("--session", help="session id (default: now)")
    ap.add_argument("--nodes", default=os.path.join(HERE, "nodes.json"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    spec = json.load(open(args.workload))
    cal = json.load(open(os.path.join(HERE, "calibration.json")))
    cfg = json.load(open(args.nodes))
    policies = args.policy.split(",") if args.policy else spec.get("policies", POLICIES)
    if args.build == "stock" and (policies != ["fifo"] or args.mode != "ignore"):
        sys.exit("a stock build runs only fifo with --mode ignore")
    session = args.session or time.strftime("%Y%m%d-%H%M%S")
    levels = load_levels(spec, cal)
    plan = [(r, p) for r in range(args.repeats)
            for p in policies[r % len(policies):] + policies[:r % len(policies)]]
    log("%s: %d runs x %d levels %s; kinds %s; hintmap %s" % (
        spec["id"], len(plan), len(levels), [l[0] for l in levels],
        kinds_arg(spec, cal["iters_per_us"]), hintmap_arg(spec) or "-"))
    if args.dry_run:
        return
    sha = code_sha()
    out_dir = os.path.join(HERE, "results", spec["id"], session)
    os.makedirs(out_dir, exist_ok=True)
    server, client = Node("server", cfg["server"]["ssh"]), Node("client", cfg["client"]["ssh"])
    ensure_build(cfg, server, client, sha, args.build)
    meta_path = os.path.join(out_dir, "meta.json")
    meta = json.load(open(meta_path)) if os.path.exists(meta_path) else {"runs": []}
    meta.update({"workload": spec, "calibration": cal, "session": session,
                 "nodes": {"server": cfg["server"]["ssh"], "client": cfg["client"]["ssh"]}})
    meta["runs"].append({"code_sha": sha, "mode": args.mode, "build": args.build,
                         "stats": args.stats, "policies": policies, "repeats": args.repeats,
                         "started": time.strftime("%Y-%m-%dT%H:%M:%S")})
    for repeat, policy in plan:
        experiment(args, cfg, server, client, spec, policy, repeat, out_dir, cal)
    meta["runs"][-1]["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    json.dump(meta, open(meta_path, "w"), indent=1)
    log("done: %s" % os.path.relpath(out_dir, HERE))


if __name__ == "__main__":
    main()
