"""Parsing loadgen client output: per-group rows and the server's RtStats."""

ROW_FIELDS = ["group", "dist", "sent_rps", "resp_rps", "dropped", "adherence",
              "p0", "p50", "p90", "p99", "p999", "p9999", "max", "deadline_met"]
MEAN_FIELD = "mean"  # mean latency of answered requests (the Means: line)


def _num(v):
    v = v.strip()
    if v in ("-", ""):
        return None
    if v.lower() in ("inf", "infinity"):
        return float("inf")
    return float(v.rstrip("%"))


def parse_level(text):
    """Parses one client invocation's output.

    Returns (rows, rtstats, flags). rows: dicts with ROW_FIELDS, one per group
    ("all", "class:<c>", "kind:<k>"). rtstats: server counter deltas over the
    measured interval. flags: client saturation and failures.
    """
    rows, rtstats, means = [], {}, {}
    flags = {"client_saturated": False, "failed": False}
    for line in text.splitlines():
        if line.startswith("RtStats: "):
            for kv in line[len("RtStats: "):].split():
                k, _, v = kv.partition("=")
                try:
                    rtstats[k] = int(v)
                except ValueError:
                    pass
        elif line.startswith("Means: "):
            for kv in line[len("Means: "):].split():
                k, _, v = kv.partition("=")
                means[k] = float(v)
        elif line.startswith(("all, ", "class:", "kind:")):
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 14:
                flags["failed"] = True  # loadgen's short row: almost no responses
                continue
            row = {"group": parts[0], "dist": parts[1]}
            for name, v in zip(ROW_FIELDS[2:], parts[2:14]):
                row[name] = _num(v)
            rows.append(row)
        elif "Aborting: schedule adherance is low" in line:
            flags["client_saturated"] = True
    for r in rows:
        r["mean"] = means.get(r["group"])
    if not any(r["group"] == "all" for r in rows):
        flags["failed"] = True
    return rows, rtstats, flags
