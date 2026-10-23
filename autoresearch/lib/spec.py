"""Workload specs: loading, validation, and translation into loadgen arguments.

A workload spec (workloads/wN-<slug>.json) is the single source of truth for an
experiment's traffic and server setup. run.py derives the client's --kinds, the
server's --hintmap and --fakework, the runtime configs, and the antagonist
command from it. See workloads/README.md for the field reference.
"""

import json
import re

CLASSES = ("normal", "high", "low")
PERCENTILES = {"p50": "p50", "p90": "p90", "p99": "p99", "p999": "p999", "p9999": "p9999"}
_DIST = re.compile(
    r"^(zero|constant:\d+|exponential:\d+(\.\d+)?|bimodal:0?\.\d+:\d+:\d+)$")
_NAME = re.compile(r"^[a-z][a-z0-9_]{0,23}$")
_TOP_FIELDS = {
    "id", "slug", "generation", "title", "description", "changed_from_previous",
    "difficulty", "server", "client", "kinds", "load_rps", "family", "cell",
    "antagonist", "notes", "status", "burst",
}
# highest instantaneous send rate the client is trusted with (req/s)
CLIENT_PEAK_RPS = 700000


class SpecError(ValueError):
    pass


def _need(cond, msg):
    if not cond:
        raise SpecError(msg)


def load(path):
    """Loads and validates a workload spec; returns it as a dict."""
    with open(path) as f:
        spec = json.load(f)
    validate(spec)
    return spec


def validate(spec):
    unknown = set(spec) - _TOP_FIELDS
    _need(not unknown, "unknown top-level fields: %s (run.py would ignore them; "
          "extend run.py first)" % sorted(unknown))
    for key in ("id", "slug", "generation", "title", "description", "server",
                "client", "kinds", "load_rps", "family", "cell"):
        _need(key in spec, "missing field '%s'" % key)
    _need(re.match(r"^w\d+[a-z]?$", spec["id"]), "id must look like w3 or w3b")

    srv = spec["server"]
    for key in ("kthreads", "guaranteed_kthreads", "spinning_kthreads", "fakework"):
        _need(key in srv, "server.%s missing" % key)
    _need(1 <= srv["kthreads"] <= 16, "server.kthreads must be 1..16")
    _need(srv["guaranteed_kthreads"] % 2 == 0,
          "server.guaranteed_kthreads must be even (hyperthread pairs)")
    _need(srv["guaranteed_kthreads"] <= srv["kthreads"], "guaranteed > kthreads")
    _need(srv["spinning_kthreads"] <= srv["kthreads"], "spinning > kthreads")

    cli = spec["client"]
    for key in ("conns", "duration_s", "rampup_s", "discard_pct"):
        _need(key in cli, "client.%s missing" % key)
    _need(1 <= cli["duration_s"] <= 30, "client.duration_s must be 1..30")

    kinds = spec["kinds"]
    _need(1 <= len(kinds) <= 16, "need 1..16 kinds")
    names = set()
    for k in kinds:
        _need(_NAME.match(k.get("name", "")), "bad kind name %r" % k.get("name"))
        _need(k["name"] not in names, "duplicate kind %s" % k["name"])
        names.add(k["name"])
        _need(_DIST.match(k.get("service", "")),
              "kind %s: service must be zero, constant:N, exponential:M, or "
              "bimodal:p:a:b (in work iterations)" % k["name"])
        _need(k.get("weight", 0) > 0, "kind %s: weight must be > 0" % k["name"])
        _need(k.get("deadline_us", 0) >= 0, "kind %s: deadline_us >= 0" % k["name"])
        h = k.get("hint", {})
        _need(h.get("class", "normal") in CLASSES,
              "kind %s: hint.class must be one of %s" % (k["name"], CLASSES))
        for f in ("deadline_us", "service_us"):
            _need(h.get(f, 0) >= 0, "kind %s: hint.%s >= 0" % (k["name"], f))

    loads = spec["load_rps"]
    _need(loads and all(isinstance(x, int) and x > 0 for x in loads),
          "load_rps must be positive integers")
    _need(loads == sorted(loads), "load_rps must be ascending")

    b = spec.get("burst")
    if b:
        for key in ("period_us", "duty", "factor"):
            _need(key in b, "burst.%s missing" % key)
        _need(b["period_us"] >= 10, "burst.period_us must be >= 10")
        _need(0 < b["duty"] < 1, "burst.duty must be between 0 and 1")
        _need(b["factor"] >= 1, "burst.factor must be >= 1")
        peak = max(loads) * burst_peak_multiplier(spec)
        _need(peak <= CLIENT_PEAK_RPS, "busy-phase rate at the top load would be %d req/s, "
              "above the client's %d; lower factor, duty, or load_rps" % (peak, CLIENT_PEAK_RPS))

    ant = spec.get("antagonist")
    if ant:
        for key in ("threads", "n", "spec", "kthreads"):
            _need(key in ant, "antagonist.%s missing" % key)


def burst_peak_multiplier(spec):
    """Busy-phase rate relative to the average rate (1.0 without bursts)."""
    b = spec.get("burst")
    if not b:
        return 1.0
    return b["factor"] / (b["duty"] * b["factor"] + 1 - b["duty"])


def burst_arg(spec):
    """The client's --burst value, or None."""
    b = spec.get("burst")
    return "%d:%s:%s" % (b["period_us"], b["duty"], b["factor"]) if b else None


def kinds_arg(spec):
    """The client's --kinds value."""
    return ",".join("%s/%s/%s/%d" % (k["name"], k["service"], k["weight"],
                                     k.get("deadline_us", 0))
                    for k in spec["kinds"])


def hintmap_arg(spec):
    """The server's --hintmap value (kind index -> hints)."""
    out = []
    for i, k in enumerate(spec["kinds"]):
        h = k.get("hint", {})
        out.append("%d=%s:%d:%d" % (i, h.get("class", "normal"),
                                    h.get("deadline_us", 0), h.get("service_us", 0)))
    return ",".join(out)
