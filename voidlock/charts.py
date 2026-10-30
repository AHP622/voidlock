"""Charts as a small vector scene (rectangles, lines, polylines, circles, text). The same scene is drawn as inline SVG in the
HTML report and with QPainter in the PDF and in the app (charts_qt.py), so every chart looks the same everywhere.
No Qt in here."""
import html
import math
from datetime import date, datetime

from . import i18n

LIGHT = dict(text="#334155", muted="#64748b", grid="#e2e8f0", axis="#94a3b8", goal="#a855f7", avg="#0e7490", ma="#6d28d9",
             accent="#0e7490", accent2="#7c9cd6", exam="#d97706", good="#16a34a", bad="#dc2626", area="#0e749022", panel="#ffffff")


def digits(s, fa):
    return str(s).translate(i18n.FA_DIGITS) if fa else str(s)


def fmt_int(n, fa):
    s = f"{int(round(n)):,}"
    return digits(s.replace(",", "\u066c" if fa else ","), fa)


def nice_ticks(lo, hi, n=5):
    """Round tick values covering [lo, hi]."""
    if hi <= lo:
        hi = lo + 1
    raw = (hi - lo) / max(1, n - 1)
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)
    start = math.floor(lo / step) * step
    ticks, v = [], start
    while v < hi + step * 0.999:
        ticks.append(round(v, 6))
        v += step
        if len(ticks) > 12:
            break
    return ticks


class Scene:
    def __init__(self, w, h):
        self.w, self.h, self.items = w, h, []

    def rect(self, x, y, w, h, fill, rx=0, title=None, stroke=None):
        self.items.append(("rect", x, y, w, h, fill, rx, title, stroke))

    def line(self, x1, y1, x2, y2, stroke, width=1.0, dash=None):
        self.items.append(("line", x1, y1, x2, y2, stroke, width, dash))

    def poly(self, pts, stroke, width=2.0, dash=None):
        self.items.append(("poly", list(pts), stroke, width, dash))

    def polygon(self, pts, fill, title=None):
        self.items.append(("polygon", list(pts), fill, title))

    def circle(self, cx, cy, r, fill, stroke=None, title=None):
        self.items.append(("circle", cx, cy, r, fill, stroke, title))

    def text(self, x, y, s, size=11, fill="#334155", anchor="middle", bold=False):
        self.items.append(("text", x, y, str(s), size, fill, anchor, bold))

    def add(self, other, dx=0.0, dy=0.0):
        """Copy the items of another scene, moved by (dx, dy)."""
        for it in other.items:
            k = it[0]
            if k == "rect":
                self.items.append((k, it[1] + dx, it[2] + dy) + it[3:])
            elif k == "line":
                self.items.append((k, it[1] + dx, it[2] + dy, it[3] + dx, it[4] + dy) + it[5:])
            elif k in ("poly", "polygon"):
                self.items.append((k, [(x + dx, y + dy) for x, y in it[1]]) + it[2:])
            elif k == "circle":
                self.items.append((k, it[1] + dx, it[2] + dy) + it[3:])
            elif k == "text":
                self.items.append((k, it[1] + dx, it[2] + dy) + it[3:])

    # ---- SVG backend
    def to_svg(self, label="", rtl=False):
        # In SVG, text-anchor start / end follow the element's direction: in a right-to-left page "start" is the RIGHT edge.
        # The scene uses geometric meaning (start = text begins at x and runs to the right), so swap them for rtl.
        flip = {"start": "end", "end": "start", "middle": "middle"} if rtl else {"start": "start", "end": "end", "middle": "middle"}
        out = [f'<svg viewBox="0 0 {self.w:.0f} {self.h:.0f}" direction="{"rtl" if rtl else "ltr"}" role="img" aria-label="{html.escape(label)}">']
        for it in self.items:
            k = it[0]
            if k == "rect":
                _, x, y, w, h, fill, rx, title, stroke = it
                st = f' stroke="{stroke}"' if stroke else ""
                body = f"<title>{html.escape(title)}</title>" if title else ""
                out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{max(w, 0):.1f}" height="{max(h, 0):.1f}" rx="{rx}" fill="{fill}"{st}>{body}</rect>')
            elif k == "line":
                _, x1, y1, x2, y2, stroke, width, dash = it
                d = f' stroke-dasharray="{dash}"' if dash else ""
                out.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{stroke}" stroke-width="{width}"{d}/>')
            elif k == "poly":
                _, pts, stroke, width, dash = it
                d = f' stroke-dasharray="{dash}"' if dash else ""
                out.append('<polyline fill="none" stroke="%s" stroke-width="%s" stroke-linejoin="round" stroke-linecap="round"%s points="%s"/>'
                           % (stroke, width, d, " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)))
            elif k == "polygon":
                _, pts, fill, title = it
                body = f"<title>{html.escape(title)}</title>" if title else ""
                out.append(f'<polygon fill="{fill}" points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in pts)}">{body}</polygon>')
            elif k == "circle":
                _, cx, cy, r, fill, stroke, title = it
                st = f' stroke="{stroke}" stroke-width="2"' if stroke else ""
                body = f"<title>{html.escape(title)}</title>" if title else ""
                out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="{fill}"{st}>{body}</circle>')
            elif k == "text":
                _, x, y, s, size, fill, anchor, bold = it
                w = ' font-weight="700"' if bold else ""
                out.append(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" text-anchor="{flip.get(anchor, anchor)}"{w}>{html.escape(s)}</text>')
        out.append("</svg>")
        return "".join(out)


def _legend(sc, entries, y, w, rtl, pal, size=11):
    """Flowing legend. entries: [(kind, color, text)] kind: dot | line | dash | tri. Returns the height used."""
    x = w - 8 if rtl else 8
    row_h, cur_y = 18, y
    for kind, color, text in entries:
        tw = len(text) * size * 0.7 + 38
        if (rtl and x - tw < 8) or (not rtl and x + tw > w - 8):
            x = w - 8 if rtl else 8
            cur_y += row_h
        s = -1 if rtl else 1
        ix = x + (-6 if rtl else 6)
        if kind == "dot":
            sc.circle(ix, cur_y + 7, 5, color)
        elif kind in ("line", "dash"):
            sc.line(ix - 7 * s * -1 if False else ix - 8, cur_y + 7, ix + 8, cur_y + 7, color, 2.4, "4 3" if kind == "dash" else None)
        elif kind == "tri":
            sc.polygon([(ix - 5, cur_y + 11), (ix + 5, cur_y + 11), (ix, cur_y + 2)], color)
        sc.text(ix + (-14 if rtl else 14), cur_y + 11, text, size, pal["text"], "end" if rtl else "start")
        x += s * tw
    return cur_y - y + row_h


def titled(scene, title, fa, pal=LIGHT, size=14):
    """The chart with its heading drawn above it, in ONE picture: a heading and its chart can then never be split across two
    PDF pages."""
    head = 28
    sc = Scene(scene.w, scene.h + head)
    sc.text(scene.w - 4 if fa else 4, 18, title, size, "#0e5a72", "end" if fa else "start", True)
    sc.add(scene, 0, head)
    return sc


# ------------------------------------------------------------------ study charts
def _bars(R):
    """Bars of the main chart: one per day (periods up to 62 days) or one per month."""
    lang = R["lang"]
    fa = lang == "fa"
    from . import report
    colors = {r["name"].strip().casefold(): r["color"] for r in R["subjects"]}
    order = {r["name"].strip().casefold(): i for i, r in enumerate(R["subjects"])}
    bars = []
    if R["daily_rows"]:
        for x in R["days"]:
            d = x["date"]
            jd = i18n.to_jalali(datetime(d.year, d.month, d.day)) if fa else (d.year, d.month, d.day)
            parts = sorted(((n, colors.get(n.strip().casefold(), "#8A8F9C"), v) for n, v in x["parts"]),
                           key=lambda p: order.get(p[0].strip().casefold(), 99))
            first = jd[2] == 1
            lab = digits(jd[2], fa) + ((" " + i18n.FA_MONTHS[jd[1] - 1]) if (fa and first) else "")
            bars.append({"label": lab, "sec": x["sec"], "parts": parts, "exam": x["exam"], "tip": report.fmt_date(d, lang, weekday=True)})
        return "day", bars
    by = {}
    for x in R["days"]:
        k = report.month_key(x["date"], lang)
        m = by.setdefault(k, {})
        for n, v in x["parts"]:
            m[n] = m.get(n, 0) + v
    for m in R["monthly"]:
        parts = sorted(((n, colors.get(n.strip().casefold(), "#8A8F9C"), v) for n, v in by.get(m["key"], {}).items()),
                       key=lambda p: order.get(p[0].strip().casefold(), 99))
        y, mo = m["key"]
        lab = i18n.FA_MONTHS[mo - 1] if fa else date(y, mo, 1).strftime("%b")
        bars.append({"label": lab, "sec": m["sec"], "parts": parts, "exam": [], "tip": report.month_label(m["key"], lang)})
    return "month", bars


def study_chart(R, pal=LIGHT, w=760):
    """Stacked column chart of the study time (by subject) with hour gridlines, goal line, average line, 7-day moving average
    and exam markers."""
    from . import report
    lang = R["lang"]
    fa = lang == "fa"
    t = report.STR[lang]
    mode, bars = _bars(R)
    if not bars:
        return Scene(w, 10)
    ml, mr, mt, mb = (12, 50, 18, 30) if fa else (50, 12, 18, 30)
    h_plot = 230
    pw, ph = w - ml - mr, h_plot - mt - mb
    goal = R["goal_sec"] if mode == "day" else 0
    ymax_sec = max(max(b["sec"] for b in bars), goal or 0, 3600)
    ticks = nice_ticks(0, ymax_sec / 3600, 5)
    ymax = ticks[-1] * 3600
    n = len(bars)
    slot = pw / n
    bw = max(3.0, min(30.0 if mode == "day" else 64.0, slot * 0.7))
    sc = Scene(w, h_plot)
    axis_x = (w - mr + 6) if fa else (ml - 6)
    anchor = "start" if fa else "end"
    for tv in ticks:
        y = mt + ph - ph * (tv * 3600 / ymax)
        sc.line(ml, y, w - mr, y, pal["grid"], 1)
        sc.text(axis_x, y + 3.5, digits(f"{tv:g}", fa), 10.5, pal["muted"], anchor)
    sc.text(axis_x, mt - 6, t["h"], 10.5, pal["muted"], anchor)

    def cx(i):
        return (ml + pw - (i + 0.5) * slot) if fa else (ml + (i + 0.5) * slot)

    step = (1 if n <= 16 else (2 if n <= 31 else 7)) if mode == "day" else 1
    for i, b in enumerate(bars):
        x0 = cx(i) - bw / 2
        base = mt + ph
        if b["sec"] > 0:
            tip = f"{b['tip']} · {report.fmt_dur(b['sec'], lang)}"
            used = 0.0
            if b["parts"]:
                for nm, color, v in b["parts"]:
                    hh = ph * v / ymax
                    sc.rect(x0, base - used - hh, bw, hh, color, 0, f"{tip}\n{nm}: {report.fmt_dur(v, lang)}")
                    used += hh
            else:
                hh = ph * b["sec"] / ymax
                sc.rect(x0, base - hh, bw, hh, pal["accent"], 2, tip)
        if i % step == 0 or b["label"].count(" "):
            sc.text(cx(i), h_plot - 12, b["label"], 10, pal["muted"])
        if b["exam"]:
            ytop = mt + 2
            sc.line(cx(i), ytop + 8, cx(i), mt + ph, pal["exam"], 1, "2 3")
            sc.polygon([(cx(i) - 5, ytop), (cx(i) + 5, ytop), (cx(i), ytop + 9)], pal["exam"], f"{t['exam']}: {', '.join(b['exam'])}")
    s = R["summary"]
    if goal:
        gy = mt + ph - ph * goal / ymax
        sc.line(ml, gy, w - mr, gy, pal["goal"], 1.4, "6 4")
    if mode == "day" and s["avg_active"]:
        ay = mt + ph - ph * s["avg_active"] / ymax
        sc.line(ml, ay, w - mr, ay, pal["avg"], 1.2, "1 4")
    if mode == "day" and n >= 10:
        pts = []
        for i in range(n):
            win = bars[max(0, i - 6): i + 1]
            pts.append((cx(i), mt + ph - ph * (sum(b["sec"] for b in win) / len(win)) / ymax))
        sc.poly(pts, pal["ma"], 2.2)
    # legend
    ent = [("dot", r["color"], r["name"] + (f" ({t['deleted']})" if r["ghost"] else "")) for r in R["subjects"][:8] if r["sec"]]
    if goal:
        ent.append(("dash", pal["goal"], t["goal"]))
    if mode == "day" and s["avg_active"]:
        ent.append(("dash", pal["avg"], t["avg_line"]))
    if mode == "day" and n >= 10:
        ent.append(("line", pal["ma"], t["ma7"]))
    if any(b["exam"] for b in bars):
        ent.append(("tri", pal["exam"], t["legend_exam"]))
    used = _legend(sc, ent, h_plot + 2, w, fa, pal)
    sc.h = h_plot + 2 + used
    return sc


def weekday_chart(R, pal=LIGHT, w=380, h=200):
    """Average study time per weekday (all days of that weekday in the period, empty ones included)."""
    from . import report
    lang = R["lang"]
    fa = lang == "fa"
    ws = R.get("week_start", 5)
    order = [(ws + k) % 7 for k in range(7)]
    tot = {k: 0 for k in range(7)}
    cnt = {k: 0 for k in range(7)}
    for x in R["days"]:
        wd = x["date"].weekday()
        tot[wd] += x["sec"]
        cnt[wd] += 1
    avg = [tot[k] / cnt[k] if cnt[k] else 0 for k in order]
    sc = Scene(w, h)
    mt, mb = 22, 28
    ph = h - mt - mb
    mx = max(avg + [1])
    slot = (w - 16) / 7
    bw = min(34, slot * 0.7)
    best = max(range(7), key=lambda i: avg[i]) if any(avg) else -1
    for i, v in enumerate(avg):
        cx = (w - 8 - (i + 0.5) * slot) if fa else (8 + (i + 0.5) * slot)
        hh = ph * v / mx
        sc.rect(cx - bw / 2, mt + ph - hh, bw, hh, pal["accent"] if i == best else pal["accent2"], 3,
                f"{i18n.FA_DAYS[order[i]] if fa else date(2024, 1, 1 + order[i]).strftime('%A')}: {report.fmt_dur(v, lang)}")
        if v > 0:
            sc.text(cx, mt + ph - hh - 5, digits(f"{v / 3600:.1f}", fa), 10, pal["text"])
        name = i18n.FA_DAYS[order[i]] if fa else date(2024, 1, 1 + order[i]).strftime("%a")
        sc.text(cx, h - 9, name, 10, pal["muted"])
    sc.line(8, mt + ph, w - 8, mt + ph, pal["axis"], 1)
    return sc


# ------------------------------------------------------------------ progress (line) charts
def line_chart(spec, pal=LIGHT, w=760, h=260, rtl=False, fa=None):
    """spec: {labels:[...], series:[{name,color,values:[v|None], width, markers, value_labels}], invert:bool, trend:bool, unit}.
    The first label is the oldest point; for right-to-left reports it is drawn at the right."""
    fa = rtl if fa is None else fa
    labels, series = spec["labels"], spec["series"]
    invert = bool(spec.get("invert"))
    vals = [v for s in series for v in s["values"] if v is not None]
    ml, mr, mt, mb = (30, 58, 24, 34) if rtl else (58, 30, 24, 34)
    sc = Scene(w, h)
    if not vals:
        return sc
    lo, hi = min(vals), max(vals)
    pad = (hi - lo) * 0.12 or max(1.0, abs(hi) * 0.05)
    ticks = nice_ticks(lo - pad, hi + pad, 5)
    ylo, yhi = ticks[0], ticks[-1]
    pw, ph = w - ml - mr, h - mt - mb
    n = len(labels)
    axis_x = (w - mr + 6) if rtl else (ml - 6)
    anchor = "start" if rtl else "end"

    def py(v):
        f = (v - ylo) / (yhi - ylo or 1)
        return mt + (ph * f if invert else ph * (1 - f))

    def px(i):
        if n == 1:
            return ml + pw / 2
        f = i / (n - 1)
        return (ml + pw - f * pw) if rtl else (ml + f * pw)

    fmt = spec.get("fmt") or (lambda v: fmt_int(v, fa))
    for tv in ticks:
        sc.line(ml, py(tv), w - mr, py(tv), pal["grid"], 1)
        sc.text(axis_x, py(tv) + 3.5, fmt(tv), 10.5, pal["muted"], anchor)
    if spec.get("unit"):
        sc.text(axis_x, mt - 8, spec["unit"], 10.5, pal["muted"], anchor)
    step = 1 if n <= 7 else math.ceil(n / 7)
    for i, lab in enumerate(labels):
        if i % step == 0:
            sc.text(px(i), h - 12, lab, 10, pal["muted"])
    single = len(series) == 1
    for s in series:
        pts = [(px(i), py(v)) for i, v in enumerate(s["values"]) if v is not None]
        if not pts:
            continue
        if single and len(pts) > 1 and not spec.get("no_area"):
            base = py(ylo) if not invert else py(yhi)
            sc.polygon([(pts[0][0], base)] + pts + [(pts[-1][0], base)], pal["area"])
        if len(pts) > 1:
            sc.poly(pts, s["color"], s.get("width", 2.6))
        # trend (least squares) for a single series
        real = [(i, v) for i, v in enumerate(s["values"]) if v is not None]
        if single and spec.get("trend", True) and len(real) >= 3:
            xs, ys = [p[0] for p in real], [p[1] for p in real]
            mx_, my_ = sum(xs) / len(xs), sum(ys) / len(ys)
            den = sum((x - mx_) ** 2 for x in xs) or 1
            sl = sum((x - mx_) * (y - my_) for x, y in zip(xs, ys)) / den
            a0, a1 = my_ + sl * (xs[0] - mx_), my_ + sl * (xs[-1] - mx_)
            sc.poly([(px(xs[0]), py(a0)), (px(xs[-1]), py(a1))], pal["goal"], 1.6, "6 4")
        best_i = None
        if single and real:
            best_i = (min if invert else max)(real, key=lambda p: p[1])[0]
        for i, v in enumerate(s["values"]):
            if v is None:
                continue
            tip = f"{labels[i]}: {fmt(v)}" if not spec.get("tips") else spec["tips"][i]
            sc.circle(px(i), py(v), 5.5 if i == best_i else 4, s["color"], "#ffffff", tip)
            if single and (s.get("value_labels", True)) and n <= 14:
                sc.text(px(i), py(v) - 9, fmt(v), 10, pal["text"], "middle", i == best_i)
    if not single:
        ent = [("line", s["color"], s["name"]) for s in series]
        used = _legend(sc, ent, h + 2, w, rtl, pal)
        sc.h = h + 2 + used
    return sc
