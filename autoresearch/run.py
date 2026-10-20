#!/usr/bin/env python3
"""Runs autoresearch experiments on the two CloudLab nodes.

One experiment = one workload x one policy x one mode (hints applied or
ignored) x one repeat. For each, run.py restarts the IOKernel on both nodes,
starts the loadgen server (and an antagonist if the workload has one) with the
policy selected in its runtime config, sweeps the workload's load levels with
one client invocation per level, tears everything down, and appends the
results to results/gen<N>/.

Examples:
  ./run.py --gen 1 --workload workloads/w1-short-high-vs-long.json \
           --policy fifo,prio --mode hints
  ./run.py --gen 0 --workload workloads/w0-single-normal.json \
           --policy fifo --mode ignore --build stock

Nodes come from nodes.json (copy nodes.json.example). The code under test is
the committed HEAD, which must be pushed: the server node checks it out and
builds it, then the client node receives the same loadgen binary.
"""

import argparse
import csv
import hashlib
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from lib import parse, spec as specs  # noqa: E402
from lib.remote import Node, RemoteError, copy_between, parallel  # noqa: E402

KILL = ("pkill -9 -x loadgen; pkill -9 -x loadgen-ar; pkill -9 -x stress; "
        "sudo pkill -9 iokerneld; sleep 1; true")
CLIENT_BIN = "apps/loadgen-ar"
SUMMARY_FIELDS = (["gen", "run_id", "workload", "policy", "mode", "build", "repeat",
                   "load_rps"] + parse.ROW_FIELDS + ["client_saturated", "failed"])
COUNTER_FIELDS = (["gen", "run_id", "workload", "policy", "mode", "build", "repeat",
                   "load_rps"] +
                  ["picks_" + c for c in parse.CLASSES] +
                  ["wait_us_" + c for c in parse.CLASSES] +
                  ["picks_total", "mean_depth", "inversion_rate", "late_at_pick_rate",
                   "hinted_stolen", "hinted_stolen_rate", "hinted_overflow",
                   "rq_overflow", "reschedules", "cpu_cores", "sched_share"])


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def git(*args):
    return subprocess.run(["git", "-C", HERE] + list(args), capture_output=True,
                          text=True, check=True).stdout.strip()


CODE_DIRS = ["../runtime", "../inc", "../apps", "../bindings", "../iokernel", "../build",
             "../base", "../net", "../shim", "../ksched", "../Makefile"]


def code_sha():
    """The code under test: the latest commit that touched code, which must be
    clean and pushed. Commits that only add results, cards, or prompts do not
    change it, so they do not trigger rebuilds on the nodes."""
    dirty = git("status", "--porcelain", "--", *CODE_DIRS)
    if dirty:
        sys.exit("refusing to run: uncommitted changes to code under test:\n" + dirty)
    sha = git("log", "-1", "--format=%H", "--", *CODE_DIRS)
    git("fetch", "-q", "origin")
    if not git("branch", "-r", "--contains", sha):
        sys.exit("refusing to run: %s is not pushed to origin" % sha[:10])
    return sha


def runtime_config(ip, cfg, kthreads, guaranteed, spinning, prio, policy=None,
                   stats=False):
    lines = ["host_addr %s" % ip, "host_netmask %s" % cfg["netmask"],
             "host_gateway %s" % cfg["gateway"], "runtime_kthreads %d" % kthreads,
             "runtime_guaranteed_kthreads %d" % guaranteed,
             "runtime_spinning_kthreads %d" % spinning, "runtime_priority %s" % prio]
    if policy:
        lines.append("runtime_sched_policy %s" % policy)
    if stats:
        lines.append("runtime_sched_stats 1")
    return "\n".join(lines) + "\n"


def ensure_build(cfg, server, client, sha, build):
    """Makes sure the server has `sha` built in the given flavor and the client
    has the matching loadgen binary. Returns seconds spent building."""
    t0 = time.time()
    repo = cfg["repo"]
    want = "%s %s" % (sha, build)
    have = server.run("cat %s/.ar_build 2>/dev/null" % repo, check=False).strip()
    if have != want:
        log("building %s (%s) on server" % (sha[:10], build))
        flag = "y" if build == "hints" else "n"
        server.run(
            "set -e; cd %s; git fetch -q origin; git checkout -q -f --detach %s; "
            "sed -i 's/^CONFIG_THREAD_HINTS=.*/CONFIG_THREAD_HINTS=%s/' build/config; "
            "make -j20 > /tmp/ar_make.log 2>&1; "
            "make -C bindings/cc -j20 > /tmp/ar_make_cc.log 2>&1; "
            "make -C apps/netbench -j20 stress > /tmp/ar_make_nb.log 2>&1; "
            "cd apps/loadgen && env %s cargo build --release > /tmp/ar_cargo.log 2>&1; "
            "echo '%s' > %s/.ar_build" % (repo, sha, flag, cfg["cargo_env"], want, repo),
            timeout=1800)
    have = client.run("cat %s/%s.build 2>/dev/null" % (repo, CLIENT_BIN), check=False).strip()
    if have != want:
        log("copying loadgen to client")
        copy_between(server, "%s/apps/loadgen/target/release/loadgen" % repo,
                     client, "%s/%s" % (repo, CLIENT_BIN))
        client.run("echo '%s' > %s/%s.build" % (want, repo, CLIENT_BIN))
    return time.time() - t0


def start_iokernel(node, cfg):
    node.run(KILL, timeout=60, check=False)
    node.bg("cd %s && exec sudo ./iokerneld %s nicpci %s" % (
        cfg["repo"], cfg["iokernel_args"], cfg["nic_pci"]), "/tmp/ar_iok.log")
    node.wait_for("/tmp/ar_iok.log", "running dataplane", 60,
                  fail_pattern="PANIC|panic|Error|failed")


def setup(cfg, server, client, spec, policy, mode, stats):
    """Starts IOKernels, the server, and the antagonist for one experiment."""
    repo, srv = cfg["repo"], spec["server"]
    parallel(lambda n: start_iokernel(n, cfg), [server, client])
    server.put(runtime_config(cfg["server"]["ip"], cfg, srv["kthreads"],
                              srv["guaranteed_kthreads"], srv["spinning_kthreads"],
                              "lc", policy, stats), "/tmp/ar_server.config")
    ccfg = cfg["client_runtime"]
    client.put(runtime_config(cfg["client"]["ip"], cfg, ccfg["kthreads"],
                              ccfg["kthreads"], ccfg["kthreads"], "lc"),
               "/tmp/ar_client.config")
    hint_args = ("--ignore-hints" if mode == "ignore"
                 else "--hintmap %s" % specs.hintmap_arg(spec))
    server.bg("cd %s && exec ./apps/loadgen/target/release/loadgen %s:%d "
              "--config /tmp/ar_server.config --mode spawner-server --transport udp "
              "--fakework %s %s" % (repo, cfg["server"]["ip"], cfg["port"],
                                    srv["fakework"], hint_args), "/tmp/ar_server.log")
    server.wait_for("/tmp/ar_server.log", "^hints:", 30,
                    fail_pattern="panicked|bad config|Aborted")
    ant = spec.get("antagonist")
    if ant:
        server.put(runtime_config(cfg["antagonist_ip"], cfg, ant["kthreads"], 0, 0, "be"),
                   "/tmp/ar_antagonist.config")
        server.bg("cd %s && exec ./apps/netbench/stress /tmp/ar_antagonist.config %d %d %s"
                  % (repo, ant["threads"], ant["n"], ant["spec"]), "/tmp/ar_antagonist.log")
        time.sleep(3)
        if not server.run("pgrep -x stress", check=False).strip():
            raise RemoteError("antagonist did not start:\n" +
                              server.run("tail -10 /tmp/ar_antagonist.log", check=False))


def run_level(cfg, client, spec, rps):
    """Runs one client invocation at one load level; returns its output."""
    cli = spec["client"]
    timeout = cli["rampup_s"] + cli["duration_s"] + 30
    mpps = "%.6f" % (rps / 1e6)
    cmd = ("cd %s && timeout %d ./%s %s:%d --config /tmp/ar_client.config "
           "--mode runtime-client --transport udp --mpps %s --start_mpps %s --samples 1 "
           "--runtime %d --rampup %d --conns %d --discard_pct %s --kinds '%s' "
           "--groups both --runtime_stat %s 2>&1; echo \"CLIENT_EXIT=$?\""
           % (cfg["repo"], timeout, CLIENT_BIN, cfg["server"]["ip"], cfg["port"], mpps,
              mpps, cli["duration_s"], cli["rampup_s"], cli["conns"], cli["discard_pct"],
              specs.kinds_arg(spec),
              "--burst %s" % specs.burst_arg(spec) if spec.get("burst") else ""))
    return client.run(cmd, timeout=timeout + 30, check=False)


def levels_for(args, spec):
    """The workload's load levels, or the subset given with --levels (values
    not in the workload are rejected, so results stay comparable)."""
    if not args.levels:
        return spec["load_rps"]
    want = [int(x) for x in args.levels.split(",")]
    bad = [x for x in want if x not in spec["load_rps"]]
    if bad:
        sys.exit("--levels %s not in %s's load_rps %s" % (bad, spec["id"], spec["load_rps"]))
    return [x for x in spec["load_rps"] if x in want]


def keep_lines(text):
    """Drops the runtime's log noise, keeping result rows and warnings."""
    keep = ("Group,", "all,", "class:", "kind:", "RtStats:", "WARNING", "Aborting",
            "CLIENT_EXIT=", "Receive thread", "thread '")
    return "\n".join(l for l in text.splitlines() if l.startswith(keep)) + "\n"


def append_csv(path, fields, rows):
    new = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerows(rows)


def experiment(args, cfg, server, client, spec, spec_path, policy, mode, repeat, sha):
    wid = spec["id"]
    run_id = "%s__%s__%s__%s__r%d" % (wid, policy, mode, args.label, repeat)
    gen_dir = os.path.join(HERE, "results", "gen%d" % args.gen)
    raw_dir = os.path.join(gen_dir, "raw", run_id)
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(os.path.join(gen_dir, "meta"), exist_ok=True)
    meta = {"run_id": run_id, "gen": args.gen, "workload": wid, "workload_file":
            os.path.relpath(spec_path, HERE), "workload_sha256":
            hashlib.sha256(open(spec_path, "rb").read()).hexdigest()[:16],
            "policy": policy, "mode": mode, "build": args.label, "repeat": repeat,
            "sched_stats": args.sched_stats,
            "code_sha": sha, "nodes": {"server": server.ssh, "client": client.ssh},
            "started": time.strftime("%Y-%m-%dT%H:%M:%S"), "levels": []}
    t0 = time.time()
    summary, counters = [], []
    try:
        setup(cfg, server, client, spec, policy, mode, args.sched_stats == "on")
        meta["setup_s"] = round(time.time() - t0, 1)
        for rps in levels_for(args, spec):
            t1 = time.time()
            out = run_level(cfg, client, spec, rps)
            with open(os.path.join(raw_dir, "rps%d.out" % rps), "w") as f:
                f.write(keep_lines(out))
            rows, rt, flags = parse.parse_level(out)
            base = {"gen": args.gen, "run_id": run_id, "workload": wid, "policy": policy,
                    "mode": mode, "build": args.label, "repeat": repeat, "load_rps": rps}
            for r in rows:
                summary.append(dict(base, **r, **{k: int(v) for k, v in flags.items()
                                                  if k in ("client_saturated", "failed")}))
            if rt:
                counters.append(dict(base, **parse.derive_counters(rt)))
            allrow = next((r for r in rows if r["group"] == "all"), None)
            meta["levels"].append({"load_rps": rps, "seconds": round(time.time() - t1, 1),
                                   **flags})
            log("  %-36s %7d rps  %s" % (run_id, rps, "FAILED" if flags["failed"] else
                "p99=%s score(%s %s)=%s" % (
                    allrow["p99"] if allrow else "?", spec["score"]["kind"],
                    spec["score"]["percentile"],
                    next((r[spec["score"]["percentile"]] for r in rows if r["group"] ==
                          "kind:" + spec["score"]["kind"]), "?"))))
            if flags["client_saturated"] or flags["failed"]:
                log("  stopping sweep: %s" % ("client saturated" if
                                              flags["client_saturated"] else "level failed"))
                with open(os.path.join(raw_dir, "server.log"), "w") as f:
                    f.write(server.run("tail -50 /tmp/ar_server.log", check=False))
                break
    except (RemoteError, subprocess.TimeoutExpired) as e:
        meta["error"] = str(e)[-2000:]
        log("  ERROR: %s" % str(e).splitlines()[0])
    finally:
        parallel(lambda n: n.run(KILL, timeout=60, check=False), [server, client])
    meta["seconds"] = round(time.time() - t0, 1)
    meta["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    with open(os.path.join(gen_dir, "meta", run_id + ".json"), "w") as f:
        json.dump(meta, f, indent=1)
    append_csv(os.path.join(gen_dir, "summary.csv"), SUMMARY_FIELDS, summary)
    append_csv(os.path.join(gen_dir, "counters.csv"), COUNTER_FIELDS, counters)
    ledger_path = os.path.join(gen_dir, "ledger.json")
    ledger = json.load(open(ledger_path)) if os.path.exists(ledger_path) else {"runs": []}
    ledger["runs"].append({"run_id": run_id, "seconds": meta["seconds"],
                           "error": "error" in meta})
    ledger["node_seconds"] = round(sum(r["seconds"] for r in ledger["runs"]), 1)
    json.dump(ledger, open(ledger_path, "w"), indent=1)
    return meta


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gen", type=int, required=True, help="generation number")
    ap.add_argument("--workload", required=True, action="append",
                    help="workload spec file (repeatable)")
    ap.add_argument("--policy", required=True, help="comma-separated policy names")
    ap.add_argument("--mode", default="hints", help="comma-separated: hints,ignore")
    ap.add_argument("--build", default="hints", choices=["hints", "stock"],
                    help="hints = CONFIG_THREAD_HINTS=y, stock = n (fifo/ignore only)")
    ap.add_argument("--sched-stats", default="on", choices=["on", "off"],
                    help="per-pick runtime statistics (default on); with off, results "
                         "are labelled build 'hints-nostats'")
    ap.add_argument("--repeats", type=int, help="override the workload's repeat count")
    ap.add_argument("--levels", help="comma-separated subset of the workload's load_rps "
                    "to run (e.g. only the headline load when judging a policy on an "
                    "older workload)")
    ap.add_argument("--nodes", default=os.path.join(HERE, "nodes.json"))
    ap.add_argument("--dry-run", action="store_true", help="validate and print the plan")
    args = ap.parse_args()

    cfg = json.load(open(args.nodes))
    args.label = args.build + ("-nostats" if args.sched_stats == "off" and
                               args.build == "hints" else "")
    policies = args.policy.split(",")
    modes = args.mode.split(",")
    if args.build == "stock" and (policies != ["fifo"] or modes != ["ignore"]):
        sys.exit("a stock build only supports --policy fifo --mode ignore")
    loaded = [(p, specs.load(p)) for p in args.workload]
    meta_dir = os.path.join(HERE, "results", "gen%d" % args.gen, "meta")

    def first_repeat(wid, pol, mode):
        """Repeat numbers continue from earlier runs in this generation, so a
        re-run never overwrites an earlier run's files."""
        prefix = "%s__%s__%s__%s__r" % (wid, pol, mode, args.label)
        done = [int(f[len(prefix):-5]) for f in (os.listdir(meta_dir)
                if os.path.isdir(meta_dir) else []) if f.startswith(prefix)]
        return max(done, default=0) + 1

    plan = []
    for path, s in loaded:
        for pol in policies:
            for mode in modes:
                r0 = first_repeat(s["id"], pol, mode)
                n = args.repeats or s.get("repeats", 1)
                plan += [(path, s, pol, mode, r) for r in range(r0, r0 + n)]
    for path, s, pol, mode, r in plan:
        log("plan: %s %s %s r%d (%d levels)" % (s["id"], pol, mode, r,
                                                 len(levels_for(args, s))))
    if args.dry_run:
        for _, s, *_ in plan[:1]:
            print("kinds:  ", specs.kinds_arg(s))
            print("hintmap:", specs.hintmap_arg(s))
        return

    sha = code_sha()
    server = Node("server", cfg["server"]["ssh"])
    client = Node("client", cfg["client"]["ssh"])
    build_s = ensure_build(cfg, server, client, sha, args.build)
    if build_s > 5:
        log("build took %.0f s" % build_s)
    t0 = time.time()
    for path, s, pol, mode, r in plan:
        experiment(args, cfg, server, client, s, path, pol, mode, r, sha)
    log("done: %d experiments in %.0f s (+%.0f s build)" % (len(plan), time.time() - t0,
                                                            build_s))


if __name__ == "__main__":
    main()
