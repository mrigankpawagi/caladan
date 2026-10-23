"""SVG plots for LEADERBOARD.md (stdlib only, no plotting library).

Each plot is a standalone SVG with its own light and dark colors (it follows
the viewer's color scheme), a title, a legend or direct labels, and a
<title> tooltip on every mark. Colors follow the policy, never its rank: the
baselines fifo and prio are gray and dashed, and every other policy keeps the
categorical slot it was given in card-id order (see Colors). The palette is
the dataviz skill's validated default (8 slots, adjacent CVD separation >= 8.4
in both modes); past eight policies, the oldest rejected one is drawn gray and
dotted instead.
"""

import math
from xml.sax.saxutils import escape

SERIES_LIGHT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300",
                "#6250d6", "#e34948"]
SERIES_DARK = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300",
               "#9085e9", "#e66767"]
FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'


def _style():
    light = {"surface": "#fcfcfb", "ink": "#0b0b0b", "ink2": "#52514e", "muted": "#898781",
             "grid": "#e1e0d9", "axis": "#c3c2b7", "mid": "#f0efec", "neg": "#2a78d6",
             "pos": "#e34948", "base0": "#898781", "base1": "#52514e"}
    dark = {"surface": "#1a1a19", "ink": "#f0efec", "ink2": "#c3c2b7", "muted": "#898781",
            "grid": "#2c2c2a", "axis": "#383835", "mid": "#383835", "neg": "#3987e5",
            "pos": "#e66767", "base0": "#898781", "base1": "#c3c2b7"}
    var = lambda d, s: "".join("--%s:%s;" % kv for kv in d.items()) + "".join(
        "--s%d:%s;" % (i + 1, c) for i, c in enumerate(s))
    css = [
        "svg{%s}" % var(light, SERIES_LIGHT),
        "@media (prefers-color-scheme: dark){svg{%s}}" % var(dark, SERIES_DARK),
        "text{font-family:%s;font-size:12px;fill:var(--ink2)}" % FONT,
        ".bg{fill:var(--surface)}",
        ".title{font-size:15px;font-weight:600;fill:var(--ink)}",
        ".sub{font-size:12px;fill:var(--muted)}",
        ".tick{font-size:11px;fill:var(--muted);font-variant-numeric:tabular-nums}",
        ".lab{font-size:12px;fill:var(--ink2)}",
        ".val{font-size:11px;fill:var(--ink);font-variant-numeric:tabular-nums}",
        ".valb{font-size:11px;font-weight:700;fill:var(--ink);font-variant-numeric:tabular-nums}",
        ".best{fill:none;stroke:var(--ink);stroke-width:2}",
        ".grid{stroke:var(--grid);stroke-width:1}",
        ".axis{stroke:var(--axis);stroke-width:1}",
        ".ref{stroke:var(--muted);stroke-width:1;stroke-dasharray:4 3}",
        ".mid{fill:var(--mid)}", ".neg{fill:var(--neg)}", ".pos{fill:var(--pos)}",
        ".ring{stroke:var(--surface);stroke-width:2}",
    ]
    for i in range(len(SERIES_LIGHT)):
        css.append(".s%d{stroke:var(--s%d)}.f%d{fill:var(--s%d)}" % (i + 1, i + 1, i + 1, i + 1))
    css.append(".s-b0{stroke:var(--base0)}.f-b0{fill:var(--base0)}")
    css.append(".s-b1{stroke:var(--base1)}.f-b1{fill:var(--base1)}")
    css.append(".s-fold{stroke:var(--muted)}.f-fold{fill:var(--muted)}")
    return "<style>%s</style>" % "".join(css)


def _doc(w, h, title, body):
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" '
            'role="img" aria-label="%s">%s<rect class="bg" width="%d" height="%d" rx="8"/>%s</svg>\n'
            % (w, h, w, h, escape(title, {'"': "&quot;"}), _style(), w, h, "".join(body)))


def _t(x, y, s, cls="lab", anchor="start", extra=""):
    return '<text class="%s" x="%.1f" y="%.1f" text-anchor="%s"%s>%s</text>' % (
        cls, x, y, anchor, extra, escape(str(s)))


def _nice_ticks(hi, n=5):
    """Round tick values from 0 to at least hi."""
    if hi <= 0:
        return [0, 1]
    raw = hi / n
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)
    top = step * math.ceil(hi / step)
    return [round(i * step, 6) for i in range(int(round(top / step)) + 1)]


def _num(v):
    return ("%d" % v) if float(v).is_integer() else ("%g" % v)


def _klabel(load):
    return "%gk" % (load / 1000.0)


class Colors:
    """Fixed color per policy: baselines gray and dashed; the others take the
    categorical slots in card-id order. When a ninth policy arrives, the
    oldest rejected policy that holds a slot gives it up, or else the oldest
    accepted policy that is no longer the champion, and is drawn gray and
    dotted ("folded"); so the newest policies and the champion always have a
    color, and every policy that keeps a slot keeps its color."""

    def __init__(self, cards):
        self.cls = {"fifo": "b0", "prio": "b1"}
        num = lambda c: int(str(c.get("id", "p999"))[1:] or 999)
        others = sorted((c for n, c in cards.items() if n not in self.cls), key=num)
        acc = [c for c in others if c.get("status") == "accepted"]
        champ = max(acc, key=lambda c: (int(c.get("generation", 0)), num(c)))["config"] \
            if acc else None
        free = [str(i + 1) for i in range(len(SERIES_LIGHT))]
        holders = []
        for c in others:
            if not free:
                victim = next((h for h in holders if h.get("status") == "rejected"), None) \
                    or next((h for h in holders if h["config"] != champ), None)
                if victim is None:
                    self.cls[c["config"]] = "fold"
                    continue
                holders.remove(victim)
                free.append(self.cls[victim["config"]])
                self.cls[victim["config"]] = "fold"
            self.cls[c["config"]] = free.pop(0)
            holders.append(c)

    def stroke(self, policy):
        c = self.cls.get(policy, "fold")
        return "s" + c if c[0].isdigit() else "s-" + c

    def fill(self, policy):
        c = self.cls.get(policy, "fold")
        return "f" + c if c[0].isdigit() else "f-" + c

    def dash(self, policy):
        """SVG dash pattern: dashed baselines, dotted folded policies."""
        c = self.cls.get(policy, "fold")
        return "" if c[0].isdigit() else ("2 3" if c == "fold" else "6 4")


def _legend(x, y, w, items, colors):
    """One or more rows of swatch + name; returns (svg parts, height used)."""
    parts, cx, cy = [], x, y
    for name in items:
        width = 26 + 7 * len(name)
        if cx + width > x + w and cx > x:
            cx, cy = x, cy + 18
        dash = (' stroke-dasharray="%s"' % colors.dash(name)) if colors.dash(name) else ""
        parts.append('<line class="%s" x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" '
                     'stroke-width="2" stroke-linecap="round"%s/>' % (
                         colors.stroke(name), cx, cy - 4, cx + 16, cy - 4, dash))
        parts.append(_t(cx + 21, cy, name))
        cx += width
    return parts, cy - y + 18


def load_curves(title, subtitle, series, headline, colors, ylabel):
    """series: [(policy, [(load, value), ...])] -> SVG. One line per policy,
    score against offered load; values above the axis top are drawn at the
    top edge with a triangle and their value."""
    W, H, L, R = 720, 400, 60, 24
    pts_all = [v for _, pts in series for _, v in pts if v is not None and math.isfinite(v)]
    loads = sorted({l for _, pts in series for l, _ in pts})
    if not pts_all or len(loads) < 2:
        return None
    at_head = [v for _, pts in series for l, v in pts
               if l == headline and v is not None and math.isfinite(v)]
    cap = 2.5 * max(at_head) if at_head else max(pts_all)
    ymax_data = max([v for v in pts_all if v <= cap] or [cap])
    ticks = _nice_ticks(ymax_data * 1.05)
    ymax = ticks[-1]
    body = [_t(L, 26, title, "title"), _t(L, 44, subtitle, "sub")]
    leg, lh = _legend(L, 66, W - L - R, [p for p, _ in series], colors)
    body += leg
    T, B = 66 + lh + 8, H - 46
    x0, x1 = loads[0], loads[-1]
    X = lambda l: L + (l - x0) / float(x1 - x0) * (W - L - R)
    Y = lambda v: B - min(v, ymax) / float(ymax) * (B - T)
    for tv in ticks:
        body.append('<line class="grid" x1="%d" y1="%.1f" x2="%d" y2="%.1f"/>' % (
            L, Y(tv), W - R, Y(tv)))
        body.append(_t(L - 8, Y(tv) + 4, _num(tv), "tick", "end"))
    body.append('<line class="axis" x1="%d" y1="%d" x2="%d" y2="%d"/>' % (L, B, W - R, B))
    last_x = -1e9
    for l in loads:
        if X(l) - last_x >= 34:
            body.append(_t(X(l), B + 16, _klabel(l), "tick", "middle"))
            last_x = X(l)
    body.append(_t((L + W - R) / 2, H - 10, "offered load (requests per second)", "sub",
                   "middle"))
    body.append(_t(14, (T + B) / 2, ylabel, "sub", "middle",
                   ' transform="rotate(-90 14 %.1f)"' % ((T + B) / 2)))
    if any(v > ymax for _, pts in series for _, v in pts if v is not None):
        body.append(_t(W - R, T - 6, "▲ off the scale (overloaded)", "tick", "end"))
    if headline and x0 <= headline <= x1:
        body.append('<line class="ref" x1="%.1f" y1="%d" x2="%.1f" y2="%d"/>' % (
            X(headline), T, X(headline), B))
        body.append(_t(X(headline) - 4, T + 12, "headline load", "tick", "end"))
    for policy, pts in series:
        pts = [(l, v) for l, v in sorted(pts) if v is not None and math.isfinite(v)]
        if not pts:
            continue
        dash = (' stroke-dasharray="%s"' % colors.dash(policy)) if colors.dash(policy) else ""
        d = " ".join("%s%.1f %.1f" % ("M" if i == 0 else "L", X(l), Y(v))
                     for i, (l, v) in enumerate(pts))
        body.append('<path class="%s" d="%s" fill="none" stroke-width="2" '
                    'stroke-linejoin="round" stroke-linecap="round"%s/>' % (
                        colors.stroke(policy), d, dash))
        for l, v in pts:
            tip = "<title>%s at %s: %s µs</title>" % (escape(policy), _klabel(l), _num(v))
            if v > ymax:
                x, y = X(l), T
                body.append('<path class="%s ring" d="M%.1f %.1f l5 9 h-10 z">%s</path>' % (
                    colors.fill(policy), x, y - 2, tip))
            else:
                body.append('<circle class="%s ring" cx="%.1f" cy="%.1f" r="4">%s</circle>' % (
                    colors.fill(policy), X(l), Y(v), tip))
    return _doc(W, H, title, body)


def score_map(title, subtitle, rows, cols, cell, row_note, col_note=None, footer="",
              key=None, best_label="best in its column", cell_note=""):
    """Heatmap: rows = policies, cols = workloads, cell(r, c) -> None or
    {"pct": change from fifo in %, "text": printed value, "best": outline it,
    "mark": suffix it with an asterisk}. Fill is diverging on pct: blue =
    better (lower latency) than fifo, red = worse, gray = no change.
    col_note(c), if given, is printed under each column's label (the
    workload's score kind)."""
    CW, CH, LW, TOP = 62, 28, 230, (106 if col_note else 92)
    W = LW + CW * len(cols) + 24
    H = TOP + CH * len(rows) + (66 if footer else 50)
    body = [_t(16, 26, title, "title"), _t(16, 44, subtitle, "sub")]
    # color key
    kx = 16
    for frac, lab in key or ((-1, "−60% or better than fifo"), (-0.5, "−30%"),
                             (0, "same as fifo"), (0.5, "+30%"), (1, "+60% or worse")):
        body.append('<rect class="mid" x="%d" y="54" width="14" height="14" rx="3"/>' % kx)
        if frac:
            body.append('<rect class="%s" x="%d" y="54" width="14" height="14" rx="3" '
                        'fill-opacity="%.2f"/>' % ("neg" if frac < 0 else "pos", kx,
                                                  0.85 * abs(frac)))
        body.append(_t(kx + 19, 65, lab, "tick"))
        kx += 34 + 6 * len(lab)
    body.append('<rect class="best" x="%d" y="54" width="14" height="14" rx="3"/>' % kx)
    body.append(_t(kx + 19, 65, best_label, "tick"))
    for j, c in enumerate(cols):
        if col_note:
            body.append(_t(LW + CW * j + CW / 2, TOP - 22, c, "lab", "middle"))
            body.append(_t(LW + CW * j + CW / 2, TOP - 8, col_note(c), "tick", "middle"))
        else:
            body.append(_t(LW + CW * j + CW / 2, TOP - 8, c, "lab", "middle"))
    for i, r in enumerate(rows):
        y = TOP + CH * i
        body.append(_t(LW - 10, y + CH / 2 + 4, r + row_note(r), "lab", "end"))
        for j, c in enumerate(cols):
            x = LW + CW * j
            d = cell(r, c)
            if d is None:
                body.append(_t(x + CW / 2, y + CH / 2 + 4, "–", "tick", "middle"))
                continue
            v = d["pct"]
            op = min(abs(v) / 60.0, 1.0) * 0.85
            tip = "<title>%s on %s: %s (%+.0f%% vs fifo)%s</title>" % (
                escape(r), escape(c), escape(d["text"]), v,
                ", dominated" if d.get("mark") else "")
            body.append('<rect class="mid" x="%d" y="%d" width="%d" height="%d" rx="4">%s'
                        '</rect>' % (x + 1, y + 1, CW - 2, CH - 2, tip))
            if abs(v) >= 0.5:
                body.append('<rect class="%s" x="%d" y="%d" width="%d" height="%d" rx="4" '
                            'fill-opacity="%.2f">%s</rect>' % (
                                "neg" if v < 0 else "pos", x + 1, y + 1, CW - 2, CH - 2, op,
                                tip))
            if d.get("best"):
                body.append('<rect class="best" x="%.1f" y="%.1f" width="%d" height="%d" '
                            'rx="4"/>' % (x + 2, y + 2, CW - 4, CH - 4))
            body.append(_t(x + CW / 2, y + CH / 2 + 4, d["text"] + ("*" if d.get("mark") else ""),
                           "valb" if d.get("best") else "val", "middle"))
    body.append(_t(16, H - (32 if footer else 16), cell_note or "Each cell: the p99 latency "
                   "(µs) of the workload's score kind; the fill shows its change from fifo's. "
                   "Lower is better.", "sub"))
    if footer:
        body.append(_t(16, H - 14, footer, "sub"))
    return _doc(W, H, title, body)


def generations(title, subtitle, bars, colors, threshold):
    """bars: [(label, policy, value % or None, verdict, note)] -> SVG bar chart
    of each candidate's change against the champion it faced; a reference
    line marks the acceptance threshold."""
    W, H, L, R, T, B = 720, 396, 60, 24, 86, 316
    W = max(W, L + R + 80 * len(bars))  # room for each bar's labels
    vals = [b[2] for b in bars if b[2] is not None] + [threshold, 0]
    lo, hi = min(vals), max(vals)
    lo_t = -_nice_ticks(-lo * 1.1)[-1] if lo < 0 else 0
    hi_t = _nice_ticks(hi * 1.1)[-1] if hi > 0 else 0
    step = _nice_ticks(max(hi_t - lo_t, 1))[1]
    ticks = [lo_t + k * step for k in range(int(round((hi_t - lo_t) / step)) + 1)]
    Y = lambda v: T + (hi_t - v) / float(hi_t - lo_t) * (B - T)
    body = [_t(L, 26, title, "title"), _t(L, 44, subtitle, "sub"),
            '<line class="ref" x1="%d" y1="62" x2="%d" y2="62"/>' % (L, L + 18),
            _t(L + 24, 66, "acceptance threshold: the score must improve by at least "
               "%d%% (or 10 µs)" % -threshold, "tick")]
    for tv in ticks:
        body.append('<line class="grid" x1="%d" y1="%.1f" x2="%d" y2="%.1f"/>' % (
            L, Y(tv), W - R, Y(tv)))
        body.append(_t(L - 8, Y(tv) + 4, ("%+d%%" % tv if tv else "0").replace("-", "−"),
                       "tick", "end"))
    body.append('<line class="axis" x1="%d" y1="%.1f" x2="%d" y2="%.1f"/>' % (
        L, Y(0), W - R, Y(0)))
    body.append('<line class="ref" x1="%d" y1="%.1f" x2="%d" y2="%.1f"/>' % (
        L, Y(threshold), W - R, Y(threshold)))
    slot = (W - L - R) / float(len(bars))
    bw = min(36, slot * 0.5)
    for i, (label, policy, v, verdict, note) in enumerate(bars):
        cx = L + slot * (i + 0.5)
        body.append(_t(cx, B + 18, label, "lab", "middle"))
        body.append(_t(cx, B + 34, verdict, "tick", "middle"))
        body.append(_t(cx, B + 48, note, "tick", "middle"))
        if v is None:
            body.append(_t(cx, Y(0) - 8, "pending" if verdict == "candidate" else "not run",
                           "tick", "middle"))
            continue
        y0, y1 = Y(0), Y(v)
        top, h = min(y0, y1), max(abs(y1 - y0), 1)
        tip = "<title>%s: %+.1f%% vs the champion it faced</title>" % (escape(label), v)
        # rounded end away from the baseline, square end on it
        r = min(4, h / 2)
        if v < 0:
            d = ("M%.1f %.1f h%.1f v%.1f q0 %.1f -%.1f %.1f h-%.1f q-%.1f 0 -%.1f -%.1f z" % (
                cx - bw / 2, top, bw, h - r, r, r, r, bw - 2 * r, r, r, r))
        else:
            d = ("M%.1f %.1f v-%.1f q0 -%.1f %.1f -%.1f h%.1f q%.1f 0 %.1f %.1f v%.1f z" % (
                cx - bw / 2, top + h, h - r, r, r, r, bw - 2 * r, r, r, r, h - r))
        body.append('<path class="%s" d="%s">%s</path>' % (colors.fill(policy), d, tip))
        ty = y1 + (14 if v < 0 else -6)
        body.append(_t(cx, ty, ("%+.0f%%" % v).replace("-", "−"), "val", "middle"))
    body.append(_t(L - 48, (T + B) / 2, "change vs champion", "sub", "middle",
                   ' transform="rotate(-90 %d %.1f)"' % (L - 48, (T + B) / 2)))
    return _doc(W, H, title, body)


def wait_split(title, subtitle, rows, colors, unit_label):
    """rows: [(policy, p99, wait p99)] -> horizontal bars, one per policy: the
    light bar is the kind's p99 latency, the solid bar inside it is its
    runqueue-wait p99 (the part a policy can change); the gap between them
    is time outside the runqueue."""
    W, L, R, T, RH = 720, 130, 120, 92, 30
    H = T + RH * len(rows) + 48
    hi = max(max(p, w) for _, p, w in rows)
    ticks = _nice_ticks(hi * 1.02)
    X = lambda v: L + v / float(ticks[-1]) * (W - L - R)
    body = [_t(16, 26, title, "title"), _t(16, 44, subtitle, "sub")]
    # key
    body.append('<rect class="f-b0" x="16" y="56" width="22" height="12" rx="3" '
                'fill-opacity="0.35"/>')
    body.append(_t(44, 66, unit_label + " latency", "tick"))
    kx = 52 + 7 * len(unit_label + " latency")
    body.append('<rect class="f-b0" x="%d" y="56" width="22" height="12" rx="3"/>' % kx)
    body.append(_t(kx + 28, 66, "of which runqueue wait p99 (what a policy can change)",
                   "tick"))
    B = T + RH * len(rows)
    for tv in ticks:
        body.append('<line class="grid" x1="%.1f" y1="%d" x2="%.1f" y2="%d"/>' % (
            X(tv), T - 6, X(tv), B))
        body.append(_t(X(tv), B + 16, _num(tv), "tick", "middle"))
    body.append(_t((L + W - R) / 2, B + 34, "microseconds", "sub", "middle"))
    for i, (policy, p, w) in enumerate(rows):
        y = T + RH * i
        body.append(_t(L - 10, y + RH / 2 + 4, policy, "lab", "end"))
        tip = "<title>%s: %s p99 %s µs, runqueue wait p99 %s µs</title>" % (
            escape(policy), escape(unit_label), _num(round(p, 1)), _num(round(w, 1)))
        body.append('<rect class="%s" x="%d" y="%.1f" width="%.1f" height="%d" rx="4" '
                    'fill-opacity="0.35">%s</rect>' % (colors.fill(policy), L, y + 5,
                                                        max(X(p) - L, 1), RH - 10, tip))
        body.append('<rect class="%s ring" x="%d" y="%.1f" width="%.1f" height="%d" rx="4">'
                    '%s</rect>' % (colors.fill(policy), L, y + 9, max(X(min(w, p)) - L, 1),
                                   RH - 18, tip))
        body.append(_t(X(p) + 6, y + RH / 2 + 4, "%s (wait %s)" % (
            _num(round(p)), _num(round(w))), "val"))
    return _doc(W, H, title, body)
