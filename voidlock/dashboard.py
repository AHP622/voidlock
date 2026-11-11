"""Numbers for the Overview dashboard. No Qt here, so it can be tested without a display (tests/dashboard_test.py).

Everything is derived from ONE pass over the last days (`daily`), so the page can refresh without walking the history many times."""
from datetime import date, datetime, timedelta

from . import classes as classes_mod

STREAK_MIN_SEC = 600            # a day counts for the streak from 10 minutes (as the old Overview did)
LOOKBACK = 21                   # extra days before the chart range: moving average + "last week" comparisons


def daily(study, today, days, extra_today=0):
    """{date: seconds} for the last `days` days plus LOOKBACK days before them. Today includes the running timer
    (study.day_sec) and `extra_today` (an unsaved focus session in progress)."""
    out = {}
    d = today - timedelta(days=days - 1 + LOOKBACK)
    while d <= today:
        out[d] = study.day_sec(d, True)
        d += timedelta(days=1)
    out[today] = out.get(today, 0) + int(extra_today)
    return out


def moving_average(values, n=7):
    """Trailing average; None until a full window exists (so the line starts where it is honest)."""
    out = []
    for i in range(len(values)):
        out.append(sum(values[i - n + 1:i + 1]) / n if i >= n - 1 else None)
    return out


def streak_at(secs, d, min_sec=STREAK_MIN_SEC):
    """The same rule as StudyLog.streak, on an already computed {date: seconds} (a day that is not over yet may be empty)."""
    if secs.get(d, 0) < min_sec:
        d -= timedelta(days=1)
    n = 0
    while secs.get(d, 0) >= min_sec and n < 1000:
        n += 1
        d -= timedelta(days=1)
    return n


def pct_change(now_v, base):
    """Whole-number percent change, or None when there is nothing to compare with."""
    if not base or base <= 0:
        return None
    return int(round((now_v - base) / base * 100))


def _focus_by_day(history):
    out = {}
    for r in history or []:
        try:
            d = datetime.fromtimestamp(float(r["start"])).date()
            out[d] = out.get(d, 0) + int(r.get("focus_sec", 0))
        except (KeyError, TypeError, ValueError, OSError):
            continue
    return out


def _last(d_map, today, n, shift=0):
    return [d_map.get(today - timedelta(days=shift + n - 1 - i), 0) for i in range(n)]


def kpis(secs, history, points, today):
    """The four cards: {key: {value, change, spark}}. `change` is a percent, a count or None, as noted per key."""
    t = secs.get(today, 0)
    prev7 = _last(secs, today, 7, shift=1)
    base = sum(prev7) / 7.0
    focus = _focus_by_day(history)
    f_now, f_prev = sum(_last(focus, today, 7)), sum(_last(focus, today, 7, shift=7))
    ledger = list((points.d.get("ledger") if points is not None else None) or [])
    earned = sum(int(e.get("pts", 0)) for e in ledger if e.get("date") == today.isoformat() and int(e.get("pts", 0)) > 0)
    bal = points.balance if points is not None else 0
    pts_spark = []
    for i in range(7):                                    # balance at the end of each of the last 7 days
        day = today - timedelta(days=6 - i)
        after = sum(int(e.get("pts", 0)) for e in ledger if str(e.get("date", "")) > day.isoformat())
        pts_spark.append(bal - after)
    return {
        "today": {"value": t, "change": pct_change(t, base), "spark": _last(secs, today, 7)},
        "streak": {"value": streak_at(secs, today), "change": streak_at(secs, today) - streak_at(secs, today - timedelta(days=7)),
                   "spark": [streak_at(secs, today - timedelta(days=6 - i)) for i in range(7)]},
        "focus": {"value": f_now, "change": pct_change(f_now, f_prev), "spark": _last(focus, today, 7)},
        "points": {"value": bal, "change": earned, "spark": pts_spark},
    }


def chart(secs, today, days, goal_sec, exam_dates=()):
    """Bars of the main chart: [{date, sec, exam}], the 7-day average aligned with them, and the y-axis top in hours."""
    full_days = [today - timedelta(days=days - 1 + LOOKBACK - i) for i in range(days + LOOKBACK)]
    full_days = [d for d in full_days if d in secs] or [today]
    ma_all = dict(zip(full_days, moving_average([secs[d] for d in full_days])))
    exams = {str(x) for x in exam_dates}
    bars = []
    for i in range(days):
        d = today - timedelta(days=days - 1 - i)
        bars.append({"date": d, "sec": secs.get(d, 0), "exam": d.isoformat() in exams, "ma": ma_all.get(d)})
    top_sec = max([b["sec"] for b in bars] + [goal_sec, 3600] + [b["ma"] or 0 for b in bars])
    step = 1
    for st in (1, 2, 3, 4, 5, 6, 8, 10, 12):
        if top_sec / 3600.0 / st <= 4:
            step = st
            break
    top_h = max(1, -(-top_sec // 3600))                   # ceil
    top_h = -(-top_h // step) * step
    return {"bars": bars, "top_h": top_h, "step_h": step, "goal_sec": goal_sec}


def share(study, today, days, keep=5):
    """Subject share of the study time of the last `days` days: ([(name, color, sec)], total). Small ones become 'others'."""
    tot = {}
    d = today - timedelta(days=days - 1)
    while d <= today:
        for s, v in study.day_subject_times(d):
            if v > 0:
                key = str(s["name"]).strip().casefold()
                slot = tot.setdefault(key, [s["name"], s.get("color") or "#8A8F9C", 0])
                slot[2] += v
        d += timedelta(days=1)
    rows = sorted(tot.values(), key=lambda r: -r[2])
    total = sum(r[2] for r in rows)
    if len(rows) > keep + 1:
        other = sum(r[2] for r in rows[keep:])
        rows = rows[:keep] + [["", "#8A8F9C", other]]      # the page labels the unnamed row "Others"
    return [tuple(r) for r in rows], total


def donut_arcs(values, gap=0.8, start=90.0):
    """[(start_deg, span_deg)] for a donut, Qt angle convention (0 = 3 o'clock, counter-clockwise positive): the first segment
    begins at 12 o'clock and the rest follow clockwise (negative spans), touching each other except for a hairline `gap`.
    A segment too small to show gets None."""
    tot = float(sum(values))
    out, ang = [], float(start)
    for v in values:
        span = 360.0 * v / tot if tot > 0 else 0.0
        out.append((ang - gap / 2.0, -(span - gap)) if span > gap else None)
        ang -= span
    return out


def recent_sessions(history, n=3):
    """Newest first: [{subject, start (datetime), focus_sec, planned_min, status}]."""
    out = []
    for r in history or []:
        try:
            out.append({"subject": str(r.get("subject") or ""), "start": datetime.fromtimestamp(float(r["start"])), "focus_sec": int(r.get("focus_sec", 0)),
                        "planned_min": int(r.get("planned_min", 0)), "status": str(r.get("status") or "")})
        except (KeyError, TypeError, ValueError, OSError):
            continue
    out.sort(key=lambda x: x["start"], reverse=True)
    return out[:n]


def upcoming(study, class_list, now, hours_text=""):
    """What is coming: the next exam, the running/next class and the lock-hours line. [{kind, title, when, when_dt, minutes_left}]."""
    items = []
    e, dd = study.next_exam(now.date())
    if e:
        items.append({"kind": "exam", "title": e["name"], "date": e["date"], "days": dd})
    st, c, s, en = classes_mod.current_or_next(class_list or [], now)
    if st:
        items.append({"kind": "class_now" if st == "now" else "class", "title": c.get("name") or "", "start": s, "end": en,
                      "minutes": max(0, int((s - now).total_seconds() // 60)) if st == "next" else max(0, int((en - now).total_seconds() // 60)),
                      "place": c.get("place") or ""})
    if hours_text:
        items.append({"kind": "hours", "title": hours_text})
    return items


# ------------------------------------------------------------------ texts (both languages here, so the page needs no catalog entries)
def _fa():
    from . import i18n
    return i18n.is_fa()


def _dg(s):
    from . import i18n
    return i18n.digits(str(s)) if _fa() else str(s)


def tx(en, fa):
    """English or Persian text; Persian digits are applied to the Persian text."""
    return _dg(fa) if _fa() else en


def fmt_dur(sec):
    sec = max(0, int(sec))
    h, m = divmod(sec // 60, 60)
    if _fa():
        return _dg(f"{h} س {m:02d} د") if h else _dg(f"{m} د")
    return f"{h}h {m:02d}m" if h else f"{m}m"


def greeting(hour):
    if 5 <= hour < 12:
        return tx("Good morning", "صبح بخیر")
    if 12 <= hour < 16:
        return tx("Good afternoon", "ظهر بخیر")
    if 16 <= hour < 20:
        return tx("Good evening", "عصر بخیر")
    return tx("Good night", "شب بخیر")


def change_text(kind, change):
    """(text, tone) for the line under a card's number. tone: up | down | flat | none."""
    if kind == "points":
        if change and change > 0:
            return tx(f"+{change} today", f"{change}+ امروز"), "up"
        return tx("none earned today yet", "امروز هنوز امتیازی نگرفته‌اید"), "none"
    if change is None:
        return "", "none"
    ref = {"today": (tx("vs 7-day avg", "نسبت به میانگین ۷ روز")), "streak": tx("vs last week", "نسبت به هفته‌ی قبل"),
           "focus": tx("vs last week", "نسبت به هفته‌ی قبل")}[kind]
    unit = "" if kind == "streak" else "%"
    if change > 0:
        return f"▲ {_dg(change)}{unit if not _fa() else ('٪' if unit else '')} {ref}", "up"
    if change < 0:
        return f"▼ {_dg(abs(change))}{unit if not _fa() else ('٪' if unit else '')} {ref}", "down"
    return tx(f"no change {ref}", f"بدون تغییر {ref}"), "flat"
