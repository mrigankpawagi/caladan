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
import random
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from lib import parse  # noqa: E402
from lib.remote import Node, RemoteError, copy_between, parallel  # noqa: E402

KILL = ("pkill -9 -x loadgen; pkill -9 -x loadgen-study; pkill -9 -x stress; "
        "sudo pkill -9 iokerneld; sleep 1; true")
CLIENT_BIN = "apps/loadgen-study"
POLICIES = ["fifo", "prio", "prio_edf", "hinted", "edf"]
STOCK = "stock"  # pseudo-policy: fifo on a build with hints compiled out


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


def runtime_config(ip, cfg, kthreads, policy=None, stats=False, guaranteed=None,
                   spinning=None, prio="lc"):
    lines = ["host_addr %s" % ip, "host_netmask %s" % cfg["netmask"],
             "host_gateway %s" % cfg["gateway"], "runtime_kthreads %d" % kthreads,
             "runtime_guaranteed_kthreads %d" % (kthreads if guaranteed is None else guaranteed),
             "runtime_spinning_kthreads %d" % (kthreads if spinning is None else spinning),
             "runtime_priority %s" % prio]
    if policy and policy != STOCK:
        # "<policy>[+rx][+q<us>]": the policy, plus packets before the
        # runqueue and/or a different quantum. ("+steal", hint-aware
        # stealing, was tested in W5 at 677952d and removed: no effect.)
        base, *extras = policy.split("+")
        lines.append("runtime_sched_policy %s" % base)
        for extra in extras:
            if extra == "rx":
                lines.append("runtime_sched_softirq_first 1")
            elif extra.startswith("q") and extra[1:].isdigit():
                lines.append("runtime_quantum_us %s" % extra[1:])
            else:
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
            "make -C apps/netbench -j20 stress > /tmp/study_make_nb.log 2>&1; "
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


def ensure_stock_build(cfg, server, sha):
    """Builds `sha` with hints compiled out in a second checkout on the
    server, so stock runs can be interleaved with the others."""
    repo = cfg["repo_stock"]
    want = "%s stock" % sha
    if server.run("cat %s/.study_build 2>/dev/null" % repo, check=False).strip() == want:
        return
    log("building %s (stock) on server in %s" % (sha[:10], repo))
    server.run(
        "set -e; [ -d %s ] || git clone -q %s %s; cd %s; git fetch -q origin; "
        "git checkout -q -f --detach %s; "
        "sed -i 's/^CONFIG_THREAD_HINTS=.*/CONFIG_THREAD_HINTS=n/' build/config; "
        "[ -d deps/pcm/build ] || (cp -r %s/deps %s/ && cp -r %s/rdma-core %s/ && "
        "cp -r %s/dpdk %s/); "
        "make clean > /dev/null 2>&1; make -j20 > /tmp/study_make_stock.log 2>&1; "
        "make -C bindings/cc -j20 > /dev/null 2>&1; "
        "cd apps/loadgen && touch build.rs src/main.rs; "
        "env %s cargo build --release > /tmp/study_cargo_stock.log 2>&1; "
        "echo '%s' > %s/.study_build" % (repo, cfg["repo"], repo, repo, sha, cfg["repo"], repo,
                                         cfg["repo"], repo, cfg["repo"], repo,
                                         cfg["cargo_env"], want, repo), timeout=3600)


def pin_frequency(node):
    """Fixes the CPU clock (performance governor, no turbo); returns what it
    reads back, for the session record."""
    node.run("for c in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do "
             "echo performance | sudo tee $c > /dev/null; done; "
             "echo 1 | sudo tee /sys/devices/system/cpu/intel_pstate/no_turbo > /dev/null",
             check=False)
    return node.run("cat /sys/devices/system/cpu/cpu2/cpufreq/scaling_governor "
                    "/sys/devices/system/cpu/intel_pstate/no_turbo; "
                    "grep MHz /proc/cpuinfo | sort | uniq -c", check=False).strip()


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


def handler_us(spec, cal):
    """Mean handler time per request, from the in-place calibration (the
    handler start-to-end time measured at light load for each service time)."""
    tot = sum(k["weight"] for k in spec["kinds"])
    try:
        return sum(k["weight"] * cal["handler_us"][str(k["service_us"])]
                   for k in spec["kinds"]) / tot
    except KeyError as e:
        sys.exit("calibration.json has no handler time for service %s us" % e)


def load_levels(spec, cal):
    """Offered loads in requests/s: given directly (rps), or as utilisation
    rho = rate x mean handler time / cores, with the handler time measured in
    place (calibration.json) and cores = rho_kthreads (default: the server's
    kthreads). The same offered rate is used for every policy."""
    if "rps" in spec:
        return [(r, None) for r in spec["rps"]]
    k = spec.get("rho_kthreads", spec["server_kthreads"])
    cap = k / handler_us(spec, cal) * 1e6
    return [(int(round(rho * cap, -2)), rho) for rho in spec["rho"]]


def setup(cfg, server, client, spec, policy, mode, stats, cal):
    repo = cfg["repo"]
    if policy == STOCK:
        repo, mode, stats = cfg["repo_stock"], "ignore", False
    parallel(lambda n: start_iokernel(n, cfg), hosts(server, client))
    server.put(runtime_config(cfg["server"]["ip"], cfg, spec["server_kthreads"], policy, stats,
                              spec.get("guaranteed_kthreads"), spec.get("spinning_kthreads")),
               "/tmp/study_server.config")
    client.put(runtime_config(cfg["client"]["ip"], cfg, spec.get("client_kthreads", cfg["client_kthreads"])),
               "/tmp/study_client.config")
    hints = "--ignore-hints" if mode == "ignore" else (
        "--hintmap %s" % hintmap_arg(spec) if hintmap_arg(spec) else "")
    server.bg("cd %s && exec ./apps/loadgen/target/release/loadgen %s:%d "
              "--config /tmp/study_server.config --mode spawner-server --transport udp "
              "--fakework %s %s" % (repo, cfg["server"]["ip"], cfg["port"], cal["fakework"],
                                    hints), "/tmp/study_server.log")
    server.wait_for("/tmp/study_server.log", "^hints:", 30,
                    fail_pattern="panicked|bad config|Aborted|unknown runtime")
    ant = spec.get("antagonist")
    if ant:
        # a best-effort batch job on the cores the server does not hold
        server.put(runtime_config(cfg["antagonist_ip"], cfg, ant["kthreads"], None, False, 0, 0,
                                  "be"), "/tmp/study_ant.config")
        server.bg("cd %s && exec ./apps/netbench/stress /tmp/study_ant.config %d %d %s"
                  % (cfg["repo"], ant["threads"], ant["n"], ant["spec"]), "/tmp/study_ant.log")
        server.wait_for("/tmp/study_ant.log", r"\| <[56]> [0-9.]+$", 30,
                        fail_pattern="failed|Abort")


def antagonist_rate(server, seconds):
    """Mean work rate the batch job logged over the last `seconds` seconds."""
    out = server.run("tail -n %d /tmp/study_ant.log" % seconds, check=False)
    vals = [float(m) for m in re.findall(r"\| <[56]> ([0-9.]+)$", out, re.M)]
    return sum(vals) / len(vals) if vals else None


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
    keep = ("Group,", "all,", "class:", "kind:", "RtStats:", "Means:", "Segments:", "WARNING",
            "Aborting",
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
    run_id = "%s__%s__r%d" % (policy, spec.get("variant", "base"), repeat)
    raw_dir = os.path.join(out_dir, "raw", run_id)
    os.makedirs(raw_dir, exist_ok=True)
    summary, counters, segments = [], [], []
    fresh = spec.get("fresh_per_level", False)
    stats = args.stats == "on" and policy != STOCK

    def one_level(rps, rho):
        base = {"workload": spec["id"], "variant": spec.get("variant", "base"),
                "policy": policy, "stats": int(stats), "repeat": repeat,
                "load_rps": rps, "rho": rho if rho is not None else ""}
        out = run_level(cfg, client, spec, rps, cal)
        with open(os.path.join(raw_dir, "rps%d.out" % rps), "w") as f:
            f.write(keep_lines(out))
        rows, rt, flags = parse.parse_level(out)
        for r in rows:
            summary.append(dict(base, **{f: r.get(f) for f in parse.ROW_FIELDS + ["mean"]},
                                client_saturated=int(flags["client_saturated"]),
                                failed=int(flags["failed"])))
        if not rows:  # record failures as rows, never drop them
            summary.append(dict(base, group="all", client_saturated=int(flags["client_saturated"]),
                                failed=1))
        for sg in parse.parse_segments(out):
            segments.append(dict(base, **sg))
        if rt or spec.get("antagonist"):
            row = dict(base, **rt)
            if spec.get("antagonist"):
                row["antagonist_rate"] = antagonist_rate(server, spec.get("duration_s", 4))
            counters.append(row)
        allrow = next((r for r in rows if r["group"] == "all"), None)
        log("  %-30s %8d rps  %s" % (run_id, rps, "FAILED" if flags["failed"] or not allrow else
            "p50=%s p99=%s" % (allrow["p50"], allrow["p99"])))
        return not (flags["client_saturated"] or flags["failed"])

    levels = load_levels(spec, cal)
    try:
        if fresh:
            # a fresh server for every level: overload at one level cannot
            # carry over into the next (knee searches)
            for rps, rho in levels:
                try:
                    setup(cfg, server, client, spec, policy, args.mode, stats, cal)
                    one_level(rps, rho)
                finally:
                    parallel(lambda n: n.run(KILL, timeout=60, check=False),
                             hosts(server, client))
        else:
            setup(cfg, server, client, spec, policy, args.mode, stats, cal)
            for rps, rho in levels:
                if not one_level(rps, rho):
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
    append_csv(os.path.join(out_dir, "segments.csv"), segments)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workload")
    ap.add_argument("--policy", help="comma-separated (default: the workload's list)")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--mode", default="hints", choices=["hints", "ignore"])
    ap.add_argument("--variant", help="apply this entry of the workload's variants")
    ap.add_argument("--rps", help="comma-separated offered loads replacing the workload's "
                    "(e.g. a W1 stage-2 refinement inside a bracket)")
    ap.add_argument("--stats", default="off", choices=["on", "off"],
                    help="runtime_sched_stats: per-pick counters (they cost a scan per "
                    "pick, so measurement runs leave them off; timing comes from Segments)")
    ap.add_argument("--session", help="session id (default: now)")
    ap.add_argument("--nodes", default=os.path.join(HERE, "nodes.json"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    spec = json.load(open(args.workload))
    if args.variant:
        spec = dict(spec, **spec["variants"][args.variant], variant=args.variant)
    spec.pop("variants", None)
    if args.rps:
        spec["rps"] = [int(x) for x in args.rps.split(",")]
        spec.pop("rho", None)
    cal = json.load(open(os.path.join(HERE, "calibration.json")))
    cfg = json.load(open(args.nodes))
    policies = args.policy.split(",") if args.policy else spec.get("policies", POLICIES)
    session = args.session or time.strftime("%Y%m%d-%H%M%S")
    levels = load_levels(spec, cal)
    # every repeat runs every policy once, in an order shuffled per repeat
    # (seeded by the session, so it is reproducible and recorded)
    plan = []
    for r in range(args.repeats):
        order = list(policies)
        random.Random("%s-%s-%d" % (session, spec.get("variant", ""), r)).shuffle(order)
        plan += [(r, p) for p in order]
    log("%s: %d runs x %d levels %s; kinds %s; hintmap %s" % (
        spec["id"], len(plan), len(levels), [l[0] for l in levels],
        kinds_arg(spec, cal["iters_per_us"]), hintmap_arg(spec) or "-"))
    if args.dry_run:
        return
    sha = code_sha()
    out_dir = os.path.join(HERE, "results", spec["id"], session)
    os.makedirs(out_dir, exist_ok=True)
    server, client = Node("server", cfg["server"]["ssh"]), Node("client", cfg["client"]["ssh"])
    ensure_build(cfg, server, client, sha, "hints")
    if STOCK in policies:
        ensure_stock_build(cfg, server, sha)
    clock = pin_frequency(server)
    meta_path = os.path.join(out_dir, "meta.json")
    meta = json.load(open(meta_path)) if os.path.exists(meta_path) else {"runs": []}
    meta.update({"workload": spec, "calibration": cal, "session": session,
                 "nodes": {"server": cfg["server"]["ssh"], "client": cfg["client"]["ssh"]}})
    meta["runs"].append({"code_sha": sha, "mode": args.mode, "variant": args.variant,
                         "stats": args.stats, "policies": policies, "repeats": args.repeats,
                         "order": [p for _, p in plan], "clock": clock,
                         "started": time.strftime("%Y-%m-%dT%H:%M:%S")})
    for repeat, policy in plan:
        experiment(args, cfg, server, client, spec, policy, repeat, out_dir, cal)
    meta["runs"][-1]["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    json.dump(meta, open(meta_path, "w"), indent=1)
    log("done: %s" % os.path.relpath(out_dir, HERE))


if __name__ == "__main__":
    main()
