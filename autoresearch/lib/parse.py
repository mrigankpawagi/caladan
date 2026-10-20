"""Parsing loadgen client output (grouped rows and the RtStats line)."""

ROW_FIELDS = ["group", "dist", "sent_rps", "resp_rps", "dropped", "adherence",
              "p0", "p50", "p90", "p99", "p999", "p9999", "max", "deadline_met",
              "qwait_p50", "qwait_p99"]
CLASSES = ("normal", "high", "low", "softirq")


def _num(v):
    v = v.strip()
    if v in ("-", ""):
        return None
    if v.lower() in ("inf", "infinity"):
        return float("inf")
    return float(v.rstrip("%"))


def parse_level(text):
    """Parses one client invocation's output.

    Returns (rows, rtstats, flags): rows is a list of dicts with ROW_FIELDS,
    rtstats maps counter names to their change during the step, and flags notes
    saturation warnings and failures.
    """
    rows, rtstats = [], {}
    flags = {"client_saturated": False, "adherence_warning": False,
             "tcp_full": False, "failed": False}
    for line in text.splitlines():
        if line.startswith("RtStats: "):
            for kv in line[len("RtStats: "):].split():
                k, _, v = kv.partition("=")
                rtstats[k] = int(v)
        elif line.startswith(("all, ", "class:", "kind:")):
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 14:
                flags["failed"] = True  # loadgen's short row: almost no responses
                continue
            row = {"group": parts[0], "dist": parts[1]}
            # rows from clients without queue-wait columns have 14 fields
            ncols = 16 if len(parts) >= 18 else 14
            for name, v in zip(ROW_FIELDS[2:ncols], parts[2:ncols]):
                row[name] = _num(v)
            rows.append(row)
        elif "Aborting: schedule adherance is low" in line:
            flags["client_saturated"] = True
        elif "WARNING: Schedule adherance is low" in line:
            flags["adherence_warning"] = True
        elif "TCP send buffer was full" in line:
            flags["tcp_full"] = True
    if not any(r["group"] == "all" for r in rows):
        flags["failed"] = True
    return rows, rtstats, flags


def derive_counters(rt):
    """Turns raw counter deltas into the hint-aware metrics reports use."""
    out = {}
    cpu_us = rt.get("cycles_per_us") or 1
    picks_total = 0
    for c in CLASSES:
        picks = rt.get("pick_" + c, 0)
        picks_total += picks
        out["picks_" + c] = picks
        out["wait_us_" + c] = (rt.get("wait_cycles_" + c, 0) / picks / cpu_us) if picks else None
    out["picks_total"] = picks_total
    out["mean_depth"] = rt.get("pick_scanned", 0) / picks_total if picks_total else None
    out["inversion_rate"] = rt.get("pick_inversions", 0) / picks_total if picks_total else None
    pd = rt.get("pick_deadline", 0)
    out["late_at_pick_rate"] = rt.get("deadline_miss_at_pick", 0) / pd if pd else None
    hinted = rt.get("pick_high", 0) + rt.get("pick_low", 0)
    out["hinted_stolen"] = rt.get("hinted_stolen", 0)
    out["hinted_stolen_rate"] = rt.get("hinted_stolen", 0) / hinted if hinted else None
    out["hinted_overflow"] = rt.get("hinted_overflow", 0)
    out["rq_overflow"] = rt.get("rq_overflow", 0)
    out["reschedules"] = rt.get("reschedules", 0)
    tsc = rt.get("tsc", 0)
    busy = rt.get("program_cycles", 0) + rt.get("sched_cycles", 0)
    out["cpu_cores"] = busy / tsc if tsc else None
    out["sched_share"] = rt.get("sched_cycles", 0) / busy if busy else None
    return out
