"""Study report for an advisor or parents: data collection, a single-file HTML page (CSS inside, right-to-left Persian or
left-to-right English, printable) and CSV. No Qt in here (the PDF is drawn in report_pdf.py from the same data).

What counts as "study" is the Study Timer's own definition: subject timer + manual entries. Focus sessions (Start on the
Overview) are listed in their own table and are NOT added to the total, so nothing is counted twice."""
import csv
import html
import io
from datetime import date, datetime, timedelta

from . import __version__, charts, i18n

MAX_DAILY_ROWS = 62          # longer periods get a month-by-month table instead of one row per day
STREAK_MIN_SEC = 600         # a day counts for the streak with at least 10 minutes

STR = {
    "fa": {
        "title": "گزارش مطالعه", "student": "نام", "period": "بازه", "generated": "تاریخ تهیه", "app": "تهیه‌شده با VOIDLOCK",
        "summary": "خلاصه", "total": "مجموع مطالعه", "active_days": "روزهای مطالعه", "of_days": "از {n} روز",
        "avg_active": "میانگین هر روز مطالعه", "avg_cal": "میانگین کل روزها", "best": "بهترین روز", "tests": "تست‌های حل‌شده",
        "words": "لغت‌های یادگرفته‌شده", "streak": "طولانی‌ترین روزهای پیاپی", "goal_days": "روزهای رسیدن به هدف",
        "sessions": "جلسه‌های تمرکز", "sessions_time": "زمان جلسه‌های تمرکز",
        "subjects": "جمع هر درس", "subject": "درس", "time": "زمان", "share": "سهم", "deleted": "حذف‌شده",
        "daily": "جدول روزانه", "monthly": "جدول ماهانه", "date": "تاریخ", "weekday": "روز", "month": "ماه", "days": "روزها",
        "sessions_title": "جدول جلسه‌های تمرکز", "when": "زمان شروع", "planned": "برنامه‌ریزی‌شده", "focused": "تمرکز واقعی",
        "status": "وضعیت", "blocked": "برنامه‌ی بسته‌شده", "exams": "آزمون‌ها", "exam": "آزمون", "no_data": "در این بازه داده‌ای ثبت نشده است.",
        "note": "زمان مطالعه = تایمر درس‌ها + زمان ثبت‌شده‌ی دستی. جلسه‌های تمرکز جدا فهرست شده‌اند و به مجموع اضافه نشده‌اند.",
        "print": "چاپ", "chart_daily": "مطالعه‌ی روزانه", "chart_monthly": "مطالعه‌ی ماهانه", "chart_subjects": "سهم درس‌ها", "goal": "هدف روزانه",
        "none": "—", "h": "ساعت", "m": "دقیقه", "and": "و", "of": "از", "legend_goal": "رسیدن به هدف", "legend_below": "کمتر از هدف", "legend_exam": "روز آزمون", "goal_line": "خط چین: هدف روزانه",
 "avg_line": "میانگین روزهای مطالعه", "ma7": "میانگین ۷ روزه", "weekday_chart": "میانگین مطالعه در هر روز هفته",
        "schedule_title": "برنامه‌ی هفتگی کلاس‌ها و مطالعه", "kind_class": "کلاس", "kind_session": "جلسه‌ی مطالعه", "place": "مکان / معلم",
        "week_class_h": "ساعت کلاس در هفته", "week_session_h": "ساعت مطالعه‌ی برنامه‌ریزی‌شده در هفته", "no_schedule": "هنوز برنامه‌ای ثبت نشده است.",
        "results_title": "نتایج آزمون‌ها و روند تراز", "taraz": "تراز", "taraz_total": "تراز کل", "rank": "رتبه کل", "pct": "درصد",
        "exam_name": "آزمون", "delta": "تغییر", "best_taraz": "بهترین تراز", "avg_taraz": "میانگین تراز", "latest": "آخرین آزمون",
        "best_rank": "بهترین رتبه", "first_to_last": "تغییر تراز از اولین تا آخرین آزمون", "exams_taken": "آزمون‌های ثبت‌شده",
        "chart_taraz": "روند تراز کل", "chart_rank": "روند رتبه کل (پایین‌تر = بهتر)", "chart_subj": "روند تراز هر درس", "trend": "روند",
        "strong": "قوی‌ترین درس‌ها", "weak": "نیازمند تلاش بیشتر", "improved": "بیشترین پیشرفت", "declined": "بیشترین افت", "no_results": "هنوز نتیجه‌ای ثبت نشده است.",
        "pct_avg": "میانگین درصد", "note_l": "یادداشت", "subject_matrix": "تراز و درصد هر درس در هر آزمون", "up": "▲", "down": "▼", "same": "=",
        "results_upto": "همه‌ی نتایج تا پایان بازه", "delta_taraz": "تغییر تراز", "delta_rank": "تغییر رتبه", "kind": "نوع", "min_l": "دقیقه", "latest_vs_prev": "نسبت به آزمون قبل",
        "st_completed": "کامل", "st_ended": "پایان دستی", "st_emergency": "خروج اضطراری", "st_recovered": "بازیابی‌شده",
        "csv_minutes": "دقیقه", "gdate": "تاریخ میلادی", "jdate": "تاریخ شمسی", "tests_short": "تست", "words_short": "لغت",
        "total_min": "مجموع (دقیقه)", "key": "مورد", "value": "مقدار", "start_gdate": "شروع (میلادی)", "end_gdate": "پایان (میلادی)",
        "planned_min": "برنامه‌ریزی (دقیقه)", "focus_min": "تمرکز (دقیقه)", "kind_daily": "روزانه", "avg_short": "میانگین",
    },
    "en": {
        "title": "Study report", "student": "Name", "period": "Period", "generated": "Created", "app": "Created with VOIDLOCK",
        "summary": "Summary", "total": "Total study time", "active_days": "Days studied", "of_days": "of {n} days",
        "avg_active": "Average per study day", "avg_cal": "Average per day (all days)", "best": "Best day", "tests": "Tests solved",
        "words": "Words learned", "streak": "Longest streak (days)", "goal_days": "Days the goal was reached",
        "sessions": "Focus sessions", "sessions_time": "Focus-session time",
        "subjects": "Time per subject", "subject": "Subject", "time": "Time", "share": "Share", "deleted": "deleted",
        "daily": "Daily table", "monthly": "Monthly table", "date": "Date", "weekday": "Day", "month": "Month", "days": "Days",
        "sessions_title": "Focus sessions", "when": "Started", "planned": "Planned", "focused": "Focused",
        "status": "Status", "blocked": "Programs closed", "exams": "Exams", "exam": "Exam", "no_data": "Nothing was recorded in this period.",
        "note": "Study time = subject timer + manually added time. Focus sessions are listed separately and are not added to the total.",
        "print": "Print", "chart_daily": "Study per day", "chart_monthly": "Study per month", "chart_subjects": "Share of subjects", "goal": "Daily goal",
        "none": "-", "h": "h", "m": "min", "and": "", "of": "of", "legend_goal": "goal reached", "legend_below": "below goal", "legend_exam": "exam day", "goal_line": "dashed line: daily goal",
 "avg_line": "average of study days", "ma7": "7-day average", "weekday_chart": "Average study per weekday",
        "schedule_title": "Weekly timetable: classes and study", "kind_class": "Class", "kind_session": "Study session", "place": "Place / teacher",
        "week_class_h": "Class hours per week", "week_session_h": "Planned study hours per week", "no_schedule": "Nothing is scheduled yet.",
        "results_title": "Exam results and taraz progress", "taraz": "Taraz", "taraz_total": "Total taraz", "rank": "Overall rank", "pct": "Percent",
        "exam_name": "Exam", "delta": "Change", "best_taraz": "Best taraz", "avg_taraz": "Average taraz", "latest": "Latest exam",
        "best_rank": "Best rank", "first_to_last": "Taraz change, first to latest exam", "exams_taken": "Exams with results",
        "chart_taraz": "Total taraz trend", "chart_rank": "Overall rank trend (lower is better)", "chart_subj": "Taraz per subject", "trend": "trend",
        "strong": "Strongest subjects", "weak": "Needs more work", "improved": "Most improved", "declined": "Biggest drop", "no_results": "No results recorded yet.",
        "pct_avg": "Average percent", "note_l": "Note", "subject_matrix": "Taraz and percent per subject and exam", "up": "▲", "down": "▼", "same": "=",
        "results_upto": "all results up to the end of the period", "delta_taraz": "Taraz change", "delta_rank": "Rank change", "kind": "Type", "min_l": "min", "latest_vs_prev": "vs the previous exam",
        "st_completed": "Completed", "st_ended": "Ended by hand", "st_emergency": "Emergency exit", "st_recovered": "Recovered",
        "csv_minutes": "minutes", "gdate": "Gregorian date", "jdate": "Jalali date", "tests_short": "tests", "words_short": "words",
        "total_min": "Total (minutes)", "key": "Item", "value": "Value", "start_gdate": "Start", "end_gdate": "End",
        "planned_min": "Planned (min)", "focus_min": "Focused (min)", "kind_daily": "Daily", "avg_short": "Average",
    },
}


# ------------------------------------------------------------------ formatting (independent of the app's language)
def _digits(s, lang):
    return str(s).translate(i18n.FA_DIGITS) if lang == "fa" else str(s)


def fmt_dur(sec, lang):
    sec = max(0, int(sec))
    h, m = divmod(sec // 60, 60)
    t = STR[lang]
    if lang == "fa":
        if h and m:
            return _digits(f"{h} {t['h']} {t['and']} {m} {t['m']}", lang)
        if h:
            return _digits(f"{h} {t['h']}", lang)
        return _digits(f"{m} {t['m']}", lang)
    return f"{h}h {m:02d}m" if h else f"{m} min"


def fmt_date(d, lang, weekday=False, year=True):
    if lang == "fa":
        jy, jm, jd = i18n.to_jalali(datetime(d.year, d.month, d.day))
        s = f"{jd} {i18n.FA_MONTHS[jm - 1]}" + (f" {jy}" if year else "")
        if weekday:
            s = f"{i18n.FA_DAYS[d.weekday()]} {s}"
        return _digits(s, lang)
    s = d.strftime("%d %b") + (d.strftime(" %Y") if year else "")
    return (d.strftime("%a ") + s) if weekday else s


def fmt_jdate_numeric(d):
    jy, jm, jd = i18n.to_jalali(datetime(d.year, d.month, d.day))
    return f"{jy:04d}-{jm:02d}-{jd:02d}"


def month_key(d, lang):
    """(year, month) of the calendar the report uses: Jalali for Persian."""
    if lang == "fa":
        jy, jm, _jd = i18n.to_jalali(datetime(d.year, d.month, d.day))
        return jy, jm
    return d.year, d.month


def month_label(key, lang):
    y, m = key
    if lang == "fa":
        return _digits(f"{i18n.FA_MONTHS[m - 1]} {y}", lang)
    return date(y, m, 1).strftime("%b %Y")


def esc(s):
    return html.escape(str(s), quote=True)


# ------------------------------------------------------------------ periods
def period_range(kind, anchor, week_start=5, lang="fa", first=None, custom=None):
    """(start, end) dates of a report period around `anchor`. kind: day | week | month | year | all | custom."""
    anchor = anchor or date.today()
    if kind == "day":
        return anchor, anchor
    if kind == "week":
        s = anchor - timedelta(days=(anchor.weekday() - week_start) % 7)
        return s, s + timedelta(days=6)
    if kind in ("month", "year"):
        if lang == "fa":
            jy, jm, _jd = i18n.to_jalali(datetime(anchor.year, anchor.month, anchor.day))
            if kind == "month":
                s = date(*i18n.from_jalali(jy, jm, 1))
                e = date(*i18n.from_jalali(jy + (jm == 12), 1 if jm == 12 else jm + 1, 1)) - timedelta(days=1)
            else:
                s = date(*i18n.from_jalali(jy, 1, 1))
                e = date(*i18n.from_jalali(jy + 1, 1, 1)) - timedelta(days=1)
            return s, e
        if kind == "month":
            s = anchor.replace(day=1)
            e = (s.replace(year=s.year + (s.month == 12), month=1 if s.month == 12 else s.month + 1)) - timedelta(days=1)
            return s, e
        return date(anchor.year, 1, 1), date(anchor.year, 12, 31)
    if kind == "all":
        return (first or date.today()), date.today()
    if kind == "custom" and custom:
        a, b = custom
        return (a, b) if a <= b else (b, a)
    return anchor, anchor


def first_recorded_day(study, store):
    days = [e["date"] for e in study.d["entries"] if e.get("date")]
    days += list(study.d["tests"].keys()) + list(study.d["words"].keys())
    for r in store.history:
        try:
            days.append(datetime.fromtimestamp(r["start"]).date().isoformat())
        except Exception:
            pass
    ok = []
    for k in days:
        try:
            ok.append(date.fromisoformat(k))
        except (TypeError, ValueError):
            pass
    return min(ok) if ok else date.today()


# ------------------------------------------------------------------ data
def collect(store, study, start, end, name="", lang="fa", goal_min=None, now=None, include_schedule=True, include_exams=True):
    """Everything a report shows, as plain data."""
    today = (now or datetime.now()).date()
    eff_end = min(end, today)
    sl = study
    days = []
    subj = {}                          # casefolded name -> record
    known = {s["id"]: s for s in sl.subjects()}

    def rec_for(sid):
        s = known.get(sid)
        if s:
            g = {"name": s["name"], "color": s.get("color", "#8A8F9C"), "ghost": False}
        else:
            g = dict(sl.ghost(sid))
            g["ghost"] = True
        key = str(g["name"]).strip().casefold()
        r = subj.setdefault(key, {"name": g["name"], "color": g["color"], "ghost": g["ghost"], "sec": 0, "tests": 0, "words": 0})
        if r["ghost"] and not g["ghost"]:
            r["ghost"] = False         # a living subject with the same name wins
        return r

    d = start
    while d <= eff_end:
        total = sl.day_sec(d, True, now, include_sessions=False)
        parts = []
        for s, v in sl.day_subject_times(d, now):
            r = rec_for(s["id"])
            r["sec"] += v
            parts.append((r["name"], v))
        day_tests = sl.d["tests"].get(d.isoformat(), {})
        for sid, c in day_tests.items():
            rec_for(sid)["tests"] += int(c)
        day_words = sl.d["words"].get(d.isoformat(), {})
        for sid, c in day_words.items():
            rec_for(sid)["words"] += int(c)
        days.append({"date": d, "sec": total, "tests": sum(int(c) for c in day_tests.values()),
                     "words": sum(int(c) for c in day_words.values()), "parts": parts,
                     "exam": [e["name"] for e in sl.exam_on(d)]})
        d += timedelta(days=1)

    sessions = []
    for r in sorted(store.history, key=lambda r: r.get("start", 0)):
        try:
            dt = datetime.fromtimestamp(float(r["start"]))
        except (KeyError, TypeError, ValueError, OSError):
            continue
        if start <= dt.date() <= eff_end:
            sessions.append({"start": dt, "subject": str(r.get("subject") or ""), "planned_min": int(r.get("planned_min", 0)),
                             "focus_sec": int(r.get("focus_sec", 0)), "status": str(r.get("status", "")),
                             "blocked": int(r.get("blocked_count", 0) or 0)})

    exams = []
    for e in sl.exams():
        try:
            ed = date.fromisoformat(e["date"])
        except ValueError:
            continue
        if start <= ed <= end:
            exams.append({"name": e["name"], "date": ed})

    total = sum(x["sec"] for x in days)
    active = [x for x in days if x["sec"] > 0]
    best = max(active, key=lambda x: x["sec"]) if active else None
    goal = (goal_min if goal_min is not None else store.settings.get("daily_goal_min", 120)) * 60
    streak = run = 0
    for x in days:
        run = run + 1 if x["sec"] >= STREAK_MIN_SEC else 0
        streak = max(streak, run)
    subjects = sorted(subj.values(), key=lambda r: (-r["sec"], -r["tests"], r["name"]))
    subjects = [r for r in subjects if r["sec"] or r["tests"] or r["words"]]
    monthly = []
    if len(days) > MAX_DAILY_ROWS:
        by = {}
        for x in days:
            k = month_key(x["date"], lang)
            m = by.setdefault(k, {"key": k, "sec": 0, "tests": 0, "words": 0, "active": 0, "days": 0})
            m["sec"] += x["sec"]
            m["tests"] += x["tests"]
            m["words"] += x["words"]
            m["days"] += 1
            m["active"] += 1 if x["sec"] > 0 else 0
        monthly = [by[k] for k in sorted(by)]
    return {
        "lang": lang, "name": name.strip(), "start": start, "end": end, "eff_end": eff_end, "generated": datetime.now(),
        "days": days, "monthly": monthly, "daily_rows": len(days) <= MAX_DAILY_ROWS, "subjects": subjects,
        "sessions": sessions, "exams": exams, "goal_sec": goal,
        "summary": {
            "total": total, "active_days": len(active), "period_days": len(days),
            "avg_active": (total // len(active)) if active else 0, "avg_cal": (total // len(days)) if days else 0,
            "best": best, "tests": sum(x["tests"] for x in days), "words": sum(x["words"] for x in days),
            "streak": streak, "goal_days": sum(1 for x in days if goal and x["sec"] >= goal),
            "sessions": len(sessions), "sessions_sec": sum(s["focus_sec"] for s in sessions),
        },
        "version": __version__, "week_start": int(store.settings.get("week_start", 5)),
        "schedule": schedule_data(store, lang) if include_schedule else None,
        "results": results_data(study, end, lang) if include_exams else None,
    }


def schedule_data(store, lang):
    """The weekly timetable (classes and planned study sessions), days in the person's week order."""
    ws = int(store.settings.get("week_start", 5))
    days = []
    cmin = smin = 0
    for k in range(7):
        wd = (ws + k) % 7
        items = []
        for c in store.classes:
            if c.get("enabled", True) and c["day"] == wd:
                items.append({"kind": "class", "time": c["time"], "minutes": int(c["minutes"]), "name": c["name"], "place": c.get("place", "")})
                cmin += int(c["minutes"])
        for e in store.schedule:
            if e.get("enabled", True) and e["day"] == wd:
                items.append({"kind": "session", "time": e["time"], "minutes": int(e["minutes"]), "name": e.get("subject") or "", "place": ""})
                smin += int(e["minutes"])
        items.sort(key=lambda x: x["time"])
        days.append({"weekday": wd, "items": items})
    has = any(d["items"] for d in days)
    return {"days": days, "class_min": cmin, "session_min": smin, "has": has}


def _short_date(iso, lang):
    d = date.fromisoformat(iso)
    return fmt_date(d, lang, year=False)


def results_data(study, end, lang):
    """Exam results up to the end of the period, with what the charts and the text need."""
    P = study.exam_progress(upto=end)
    ex = P["exams"]
    if not ex:
        return None
    tz = [(i, e["taraz"]) for i, e in enumerate(ex) if e["taraz"] is not None]
    rk = [(i, e["rank"]) for i, e in enumerate(ex) if e["rank"] is not None]
    for i, e in enumerate(ex):
        prev = next((ex[j]["taraz"] for j in range(i - 1, -1, -1) if ex[j]["taraz"] is not None), None)
        e["delta"] = (e["taraz"] - prev) if (e["taraz"] is not None and prev is not None) else None
        prevr = next((ex[j]["rank"] for j in range(i - 1, -1, -1) if ex[j]["rank"] is not None), None)
        e["delta_rank"] = (prevr - e["rank"]) if (e["rank"] is not None and prevr is not None) else None   # + = better rank
        e["short"] = _short_date(e["date"], lang)
    subs = []
    for s in P["subjects"]:
        pts = [p for p in s["points"] if p[2] is not None or p[1] is not None]
        tz_pts = [p for p in s["points"] if p[2] is not None]
        latest = pts[-1] if pts else None
        delta = (tz_pts[-1][2] - tz_pts[-2][2]) if len(tz_pts) >= 2 else None
        subs.append({"key": s["key"], "name": s["name"], "color": s["color"], "points": s["points"],
                     "latest_pct": latest[1] if latest else None, "latest_taraz": tz_pts[-1][2] if tz_pts else None, "delta": delta})
    ranked = sorted([s for s in subs if s["latest_taraz"] is not None], key=lambda s: -s["latest_taraz"])
    moved = [s for s in subs if s["delta"] is not None]
    out = {
        "exams": ex, "subjects": subs, "count": len(ex),
        "latest": ex[-1], "prev": ex[-2] if len(ex) > 1 else None,
        "best_taraz": max((e for e in ex if e["taraz"] is not None), key=lambda e: e["taraz"], default=None),
        "avg_taraz": (sum(v for _i, v in tz) / len(tz)) if tz else None,
        "best_rank": min((e for e in ex if e["rank"] is not None), key=lambda e: e["rank"], default=None),
        "first_to_last": (tz[-1][1] - tz[0][1]) if len(tz) >= 2 else None,
        "strong": ranked[:2], "weak": ranked[-2:][::-1] if len(ranked) >= 4 else [],
        "improved": max(moved, key=lambda s: s["delta"]) if moved and max(s["delta"] for s in moved) > 0 else None,
        "declined": min(moved, key=lambda s: s["delta"]) if moved and min(s["delta"] for s in moved) < 0 else None,
    }
    return out


def exam_chart(res, kind, lang, pal=charts.LIGHT, w=760, h=260):
    """One exam-progress chart. kind: taraz | rank | subjects (taraz per subject) | percent (percent per subject).
    Returns an empty scene when there is nothing to draw."""
    fa = lang == "fa"
    t = STR[lang]
    ex = res["exams"] if res else []
    if not ex:
        return charts.Scene(w, 10)
    labels = [e["short"] for e in ex]
    tips = [f"{e['name']} · {fmt_date(date.fromisoformat(e['date']), lang)}" for e in ex]
    fi = lambda n: charts.fmt_int(n, fa)
    if kind in ("taraz", "rank"):
        key = kind
        vals = [e[key] for e in ex]
        if not any(v is not None for v in vals):
            return charts.Scene(w, 10)
        return charts.line_chart({"labels": labels, "invert": kind == "rank", "unit": t["taraz" if kind == "taraz" else "rank"],
                                  "series": [{"name": t["taraz_total" if kind == "taraz" else "rank"], "color": pal.get("line1", "#0e7490") if kind == "taraz" else pal.get("line2", "#2563eb"), "values": vals}],
                                  "tips": [f"{tp}: " + (fi(v) if v is not None else "-") for tp, v in zip(tips, vals)]}, pal, w, h, fa)
    series = []
    for s in res["subjects"]:
        vals = [None] * len(ex)
        for i, pct, tz in s["points"]:
            v = tz if kind == "subjects" else pct
            if v is not None:
                vals[i] = v
        if any(v is not None for v in vals):
            series.append({"name": s["name"], "color": s["color"], "values": vals, "width": 2.2})
    if not series or len(ex) < 2:
        return charts.Scene(w, 10)
    spec = {"labels": labels, "series": series, "unit": t["taraz"] if kind == "subjects" else "%"}
    if kind == "percent":
        spec["fmt"] = lambda v: _digits(f"{v:.0f}", lang)
    return charts.line_chart(spec, pal, w, h, fa)


def result_scenes(R, w=760):
    """Charts of the exam progress for the report (those that have data)."""
    res = R.get("results")
    if not res:
        return {}
    out = {}
    for kind, name, hh in (("taraz", "taraz", 250), ("rank", "rank", 230), ("subjects", "subjects", 270)):
        sc = exam_chart(res, kind, R["lang"], charts.LIGHT, w, hh)
        if sc.items:
            out[name] = sc
    return out


def pdf_scenes(R, w=680):
    """Every chart of the PDF, by the name used in its HTML (<img src=name>)."""
    sc = {}
    t = STR[R["lang"]]
    fa = R["lang"] == "fa"
    if R["days"]:
        st_ = charts.study_chart(R, charts.LIGHT, w)
        sc["chart_study"] = charts.titled(st_, t["chart_daily"] if R["daily_rows"] else t["chart_monthly"], fa)
        if len(R["days"]) >= 7:
            sc["chart_weekday"] = charts.titled(charts.weekday_chart(R, charts.LIGHT, min(w, 460), 190), t["weekday_chart"], fa)
    titles = {"taraz": t["chart_taraz"], "rank": t["chart_rank"], "subjects": t["chart_subj"]}
    for k, v in result_scenes(R, w).items():
        sc["chart_" + k] = charts.titled(v, titles[k], fa)
    return sc


def period_title(R):
    lang = R["lang"]
    a, b = R["start"], R["end"]
    if a == b:
        return fmt_date(a, lang, weekday=True)
    return f"{fmt_date(a, lang)}  -  {fmt_date(b, lang)}"


def _status(st, lang):
    return STR[lang].get("st_" + st, st or STR[lang]["none"])


# ------------------------------------------------------------------ HTML
_CSS = """
.tw{overflow-x:auto}
.sched{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:8px}
.sd{background:#f8fafc;border:1px solid #e3e9f3;border-radius:10px;padding:8px;min-height:70px}
.sd h4{margin:0 0 6px;font-size:12.5px;color:#334155;text-align:center}
.it{border-radius:8px;padding:5px 7px;margin-bottom:5px;font-size:12px;line-height:1.5;border-inline-start:4px solid}
.it.class{background:#f3e8ff;border-color:#7e22ce}
.it.session{background:#e0f2fe;border-color:#0369a1}
.it b{display:block;font-size:12.5px}
.it span{color:#64748b}
.chart{margin-top:4px}
.two{display:flex;flex-wrap:wrap;gap:12px}
.two>div{flex:1 1 320px;min-width:0}
.pos{color:#15803d;font-weight:700}.neg{color:#b91c1c;font-weight:700}
.ins{margin:8px 0 0;padding:0;list-style:none;font-size:13px}
.ins li{padding:3px 0}
@media (max-width:720px){.sched{grid-template-columns:repeat(2,minmax(0,1fr))}}
*{box-sizing:border-box}
html{-webkit-print-color-adjust:exact;print-color-adjust:exact}
body{margin:0;background:#eef1f6;color:#1d2433;font:14px/1.7 "Vazirmatn","Vazir","Segoe UI",Tahoma,"Noto Sans Arabic",system-ui,sans-serif}
.page{max-width:900px;margin:0 auto;padding:24px 16px 40px}
.head{background:linear-gradient(135deg,#0e7490,#6d28d9);color:#fff;border-radius:16px;padding:22px 26px;margin-bottom:16px}
.head h1{margin:0 0 6px;font-size:26px}
.head .meta{display:flex;flex-wrap:wrap;gap:6px 22px;opacity:.95;font-size:14px}
.card{background:#fff;border:1px solid #dde3ee;border-radius:14px;padding:18px 20px;margin-bottom:14px}
.card h2{margin:0 0 12px;font-size:17px;color:#0e5a72}
.grid{display:flex;flex-wrap:wrap;gap:10px}
.stat{flex:1 1 170px;background:#f5f8fc;border:1px solid #e3e9f3;border-radius:12px;padding:10px 14px;min-width:150px;max-width:100%;overflow-wrap:anywhere}
.stat b{display:block;font-size:19px;color:#0f172a}
.stat span{font-size:12px;color:#5b6577}
table{width:100%;border-collapse:collapse;font-size:13.5px}
th,td{padding:7px 9px;border-bottom:1px solid #e6ebf3;text-align:start;vertical-align:middle}
th{background:#f1f5fb;color:#334155;font-weight:700;font-size:12.5px}
tbody tr:nth-child(even){background:#fafcff}
td.num,th.num,td.name{white-space:nowrap}
.dot{display:inline-block;width:11px;height:11px;border-radius:50%;margin-inline-end:7px;vertical-align:middle}
.bar{background:#e8edf5;border-radius:6px;height:10px;min-width:70px;overflow:hidden}
.bar i{display:block;height:100%;border-radius:6px}
.muted{color:#64748b}
.legend{display:flex;flex-wrap:wrap;gap:6px 18px;font-size:12px;color:#475569;margin-top:6px}
.exam{color:#b45309;font-weight:700}
.note{font-size:12.5px;color:#64748b;margin:8px 2px}
.empty{padding:22px;text-align:center;color:#64748b}
.foot{text-align:center;color:#64748b;font-size:12px;margin-top:18px}
svg{width:100%;height:auto;display:block}
button.noprint{font:inherit;background:#0e7490;color:#fff;border:0;border-radius:10px;padding:8px 18px;cursor:pointer;margin:0 0 12px}
@page{size:A4;margin:12mm}
@media print{
 .tw{overflow:visible}
 .sched{grid-template-columns:repeat(7,minmax(0,1fr))}
 .it{font-size:10.5px}
 body{background:#fff}
 .page{max-width:none;padding:0}
 .noprint{display:none!important}
 .card,.head,.stat{break-inside:avoid}
 .card.tall{break-inside:auto}
 h2{break-after:avoid}
 table{page-break-inside:auto}
 tr{break-inside:avoid}
 thead{display:table-header-group}
}
"""


def _stat(label, value):
    return f'<div class="stat"><b>{esc(value)}</b><span>{esc(label)}</span></div>'


def _bar(pct, color):
    return f'<div class="bar"><i style="width:{max(0.0, min(100.0, pct)):.1f}%;background:{esc(color)}"></i></div>'


def _delta_html(v, lang, better_up=True, fmt=None):
    if v is None or v == 0:
        return ""
    good = (v > 0) == better_up
    arrow = STR[lang]["up"] if v > 0 else STR[lang]["down"]
    num = (fmt or (lambda x: charts.fmt_int(abs(x), lang == "fa")))(v)
    return f'<span class="{"pos" if good else "neg"}">{arrow} {esc(num)}</span>'


def _results_html(R):
    res = R.get("results")
    lang = R["lang"]
    t = STR[lang]
    fa = lang == "fa"
    if not res:
        return ""
    ex = res["exams"]
    fi = lambda n: charts.fmt_int(n, fa)
    pc = lambda p: _digits(f"{p:.1f}", lang) + ("٪" if fa else "%")
    latest, best, bestr = res["latest"], res["best_taraz"], res["best_rank"]
    stats = [_stat(t["exams_taken"], _digits(res["count"], lang))]
    if latest["taraz"] is not None:
        d = _delta_html(latest["delta"], lang)
        stats.append(f'<div class="stat"><b>{esc(fi(latest["taraz"]))} {d}</b><span>{esc(t["latest"])} · {esc(t["taraz_total"])}</span></div>')
    if latest["rank"] is not None:
        d = _delta_html(latest["delta_rank"], lang)
        stats.append(f'<div class="stat"><b>{esc(fi(latest["rank"]))} {d}</b><span>{esc(t["latest"])} · {esc(t["rank"])}</span></div>')
    if best:
        stats.append(_stat(t["best_taraz"] + f" ({best['short']})", fi(best["taraz"])))
    if res["avg_taraz"] is not None:
        stats.append(_stat(t["avg_taraz"], fi(res["avg_taraz"])))
    if bestr:
        stats.append(_stat(t["best_rank"] + f" ({bestr['short']})", fi(bestr["rank"])))
    if res["first_to_last"] is not None:
        v = res["first_to_last"]
        stats.append(f'<div class="stat"><b>{_delta_html(v, lang) or esc(t["same"])}</b><span>{esc(t["first_to_last"])}</span></div>')
    out = [f'<div class="card"><h2>{esc(t["results_title"])}</h2><div class="grid">{"".join(stats)}</div>'
           f'<div class="note">{esc(t["results_upto"])}</div></div>\n']
    scenes = result_scenes(R)
    for key, title in (("taraz", "chart_taraz"), ("rank", "chart_rank"), ("subjects", "chart_subj")):
        if key in scenes:
            out.append(f'<div class="card"><h2>{esc(t[title])}</h2><div class="chart">{scenes[key].to_svg(t[title], fa)}</div></div>\n')
    # exams table
    rows = []
    for e in reversed(ex):
        rows.append(f'<tr><td class="num">{esc(fmt_date(date.fromisoformat(e["date"]), lang))}</td><td>{esc(e["name"])}</td>'
                    f'<td class="num">{esc(fi(e["taraz"])) if e["taraz"] is not None else "<span class=muted>" + esc(t["none"]) + "</span>"}</td>'
                    f'<td class="num">{_delta_html(e["delta"], lang)}</td>'
                    f'<td class="num">{esc(fi(e["rank"])) if e["rank"] is not None else "<span class=muted>" + esc(t["none"]) + "</span>"}</td>'
                    f'<td class="num">{_delta_html(e["delta_rank"], lang)}</td>'
                    f'<td class="num">{esc(pc(e["pct_avg"])) if e["pct_avg"] is not None else ""}</td><td>{esc(e["note"])}</td></tr>')
    out.append(f'<div class="card tall"><h2>{esc(t["exam_name"])}</h2><table><thead><tr><th>{esc(t["date"])}</th><th>{esc(t["exam_name"])}</th>'
               f'<th class="num">{esc(t["taraz_total"])}</th><th class="num">{esc(t["delta_taraz"])}</th><th class="num">{esc(t["rank"])}</th><th class="num">{esc(t["delta_rank"])}</th>'
               f'<th class="num">{esc(t["pct_avg"])}</th><th>{esc(t["note_l"])}</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table></div>\n")
    # per subject matrix: last 8 exams
    subs = [s for s in res["subjects"] if any(p[1] is not None or p[2] is not None for p in s["points"])]
    if subs:
        cols = list(range(max(0, len(ex) - 8), len(ex)))
        head = "".join(f'<th class="num">{esc(ex[i]["short"])}</th>' for i in cols)
        rows = []
        for s in subs:
            cells = {i: (pct, tz) for i, pct, tz in s["points"]}
            tds = []
            for i in cols:
                pct, tz = cells.get(i, (None, None))
                tds.append('<td class="num">' + (f'<b>{esc(fi(tz))}</b>' if tz is not None else "") + (f'<br><span class="muted">{esc(pc(pct))}</span>' if pct is not None else "")
                           + ("" if (tz is not None or pct is not None) else f'<span class="muted">{esc(t["none"])}</span>') + "</td>")
            rows.append(f'<tr><td class="name"><span class="dot" style="background:{esc(s["color"])}"></span>{esc(s["name"])}</td>{"".join(tds)}'
                        f'<td class="num">{_delta_html(s["delta"], lang)}</td></tr>')
        out.append(f'<div class="card tall"><h2>{esc(t["subject_matrix"])}</h2><table><thead><tr><th>{esc(t["subject"])}</th>{head}'
                   f'<th class="num">{esc(t["latest_vs_prev"])}</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table>"
                   f'<div class="note">{esc(t["taraz"])} / {esc(t["pct"])}</div></div>\n')
    # insights
    ins = []
    if res["strong"]:
        ins.append(f'<li><b>{esc(t["strong"])}:</b> ' + "، ".join(esc(f'{s["name"]} ({fi(s["latest_taraz"])})') for s in res["strong"]) + "</li>")
    if res["weak"]:
        ins.append(f'<li><b>{esc(t["weak"])}:</b> ' + "، ".join(esc(f'{s["name"]} ({fi(s["latest_taraz"])})') for s in res["weak"]) + "</li>")
    if res["improved"]:
        s = res["improved"]
        ins.append(f'<li><b>{esc(t["improved"])}:</b> {esc(s["name"])} {_delta_html(s["delta"], lang)}</li>')
    if res["declined"]:
        s = res["declined"]
        ins.append(f'<li><b>{esc(t["declined"])}:</b> {esc(s["name"])} {_delta_html(s["delta"], lang)}</li>')
    if ins:
        out.append(f'<div class="card"><ul class="ins">{"".join(ins)}</ul></div>\n')
    return "".join(out)


def _schedule_html(R):
    sch = R.get("schedule")
    lang = R["lang"]
    t = STR[lang]
    rtl = lang == "fa"
    if not sch or not sch["has"]:
        return ""
    cols = []
    for d in sch["days"]:
        name = i18n.FA_DAYS[d["weekday"]] if rtl else date(2024, 1, 1 + d["weekday"]).strftime("%A")
        items = []
        for it in d["items"]:
            kind = t["kind_class"] if it["kind"] == "class" else t["kind_session"]
            title = it["name"] or kind
            sub = [fmt_dur(it["minutes"] * 60, lang)]
            if it["place"]:
                sub.append(it["place"])
            items.append(f'<div class="it {it["kind"]}"><b>{esc(_digits(it["time"], lang))} · {esc(title)}</b><span>{esc(" · ".join(sub))}</span></div>')
        cols.append(f'<div class="sd"><h4>{esc(name)}</h4>{"".join(items) or "<div class=muted style=text-align:center>" + esc(t["none"]) + "</div>"}</div>')
    stats = [_stat(t["week_class_h"], fmt_dur(sch["class_min"] * 60, lang)), _stat(t["week_session_h"], fmt_dur(sch["session_min"] * 60, lang))]
    return (f'<div class="card"><h2>{esc(t["schedule_title"])}</h2><div class="sched">{"".join(cols)}</div>'
            f'<div class="grid" style="margin-top:10px">{"".join(stats)}</div></div>\n')


def render_html(R, interactive=True):
    lang = R["lang"]
    t = STR[lang]
    rtl = lang == "fa"
    s = R["summary"]
    total = s["total"]
    out = [f'<!DOCTYPE html>\n<html lang="{lang}" dir="{"rtl" if rtl else "ltr"}">\n<head>\n<meta charset="utf-8">\n'
           f'<meta name="viewport" content="width=device-width,initial-scale=1">\n<title>{esc(t["title"])}'
           f'{" - " + esc(R["name"]) if R["name"] else ""}</title>\n<style>{_CSS}</style>\n</head>\n<body>\n<div class="page">\n']
    if interactive:
        out.append(f'<button class="noprint" onclick="window.print()">{esc(t["print"])}</button>\n')
    # header
    meta = [f'{esc(t["period"])}: <b>{esc(period_title(R))}</b>']
    if R["name"]:
        meta.insert(0, f'{esc(t["student"])}: <b>{esc(R["name"])}</b>')
    meta.append(f'{esc(t["generated"])}: {esc(fmt_date(R["generated"].date(), lang))}')
    out.append(f'<div class="head"><h1>{esc(t["title"])}</h1><div class="meta">' + "".join(f"<span>{m}</span>" for m in meta) + "</div></div>\n")

    if not R["days"] or (not total and not R["sessions"] and not R["subjects"]):
        out.append(f'<div class="card"><div class="empty">{esc(t["no_data"])}</div></div>\n')
    # summary
    best = s["best"]
    stats = [
        _stat(t["total"], fmt_dur(total, lang)),
        _stat(t["active_days"], _digits(f"{s['active_days']} " + t["of_days"].format(n=s["period_days"]), lang)),
        _stat(t["avg_active"], fmt_dur(s["avg_active"], lang)),
        _stat(t["avg_cal"], fmt_dur(s["avg_cal"], lang)),
        _stat(t["best"] + (f" ({fmt_date(best['date'], lang, year=False)})" if best else ""), fmt_dur(best["sec"], lang) if best else t["none"]),
        _stat(t["tests"], _digits(s["tests"], lang)),
    ]
    if s["words"]:
        stats.append(_stat(t["words"], _digits(s["words"], lang)))
    stats.append(_stat(t["streak"], _digits(s["streak"], lang)))
    if R["goal_sec"]:
        stats.append(_stat(t["goal_days"], _digits(f"{s['goal_days']} {t['of']} {s['period_days']}", lang)))
    stats.append(_stat(t["sessions"], _digits(s["sessions"], lang)))
    stats.append(_stat(t["sessions_time"], fmt_dur(s["sessions_sec"], lang)))
    out.append(f'<div class="card"><h2>{esc(t["summary"])}</h2><div class="grid">{"".join(stats)}</div>'
               f'<div class="note">{esc(t["note"])}</div></div>\n')
    dash = f'<span class="muted">{esc(t["none"])}</span>'
    # subjects
    if R["subjects"]:
        rows = []
        for r in R["subjects"]:
            pct = (r["sec"] / total * 100) if total else 0
            nm = esc(r["name"]) + (f' <span class="muted">({esc(t["deleted"])})</span>' if r["ghost"] else "")
            rows.append(f'<tr><td class="name"><span class="dot" style="background:{esc(r["color"])}"></span>{nm}</td>'
                        f'<td class="num">{esc(fmt_dur(r["sec"], lang))}</td><td class="num">{_digits(f"{pct:.0f}%", lang)}</td>'
                        f'<td style="width:28%">{_bar(pct, r["color"])}</td>'
                        f'<td class="num">{_digits(r["tests"], lang) if r["tests"] else dash}</td>'
                        f'<td class="num">{_digits(r["words"], lang) if r["words"] else dash}</td></tr>')
        out.append(f'<div class="card"><h2>{esc(t["subjects"])}</h2><table><thead><tr><th>{esc(t["subject"])}</th>'
                   f'<th class="num">{esc(t["time"])}</th><th class="num">{esc(t["share"])}</th><th></th>'
                   f'<th class="num">{esc(t["tests_short"])}</th><th class="num">{esc(t["words_short"])}</th></tr></thead><tbody>'
                   + "".join(rows) + "</tbody></table></div>\n")
    # daily chart + table
    sc_study = charts.study_chart(R)
    if sc_study.items and len(R["days"]) > 1:
        mode = "day" if R["daily_rows"] else "month"
        wk = charts.weekday_chart(R) if len(R["days"]) >= 7 else None
        out.append(f'<div class="card"><h2>{esc(t["chart_daily"] if mode == "day" else t["chart_monthly"])}</h2><div class="chart">{sc_study.to_svg(t["chart_daily"], rtl)}</div></div>\n')
        if wk is not None:
            out.append(f'<div class="card"><h2>{esc(t["weekday_chart"])}</h2><div class="chart" style="max-width:520px;margin:0 auto">{wk.to_svg(t["weekday_chart"], rtl)}</div></div>\n')
    out.append(_results_html(R))
    out.append(_schedule_html(R))
    if R["daily_rows"] and R["days"]:
        mx = max([x["sec"] for x in R["days"]] + [1])
        any_exam = any(x["exam"] for x in R["days"])
        rows = []
        for x in R["days"]:
            ex = f'<td><span class="exam">{esc(", ".join(x["exam"]))}</span></td>' if x["exam"] else ("<td></td>" if any_exam else "")
            rows.append(f'<tr><td class="num">{esc(fmt_date(x["date"], lang))}</td><td class="num">{esc(i18n.FA_DAYS[x["date"].weekday()] if rtl else x["date"].strftime("%a"))}</td>'
                        f'<td class="num">{esc(fmt_dur(x["sec"], lang)) if x["sec"] else "<span class=muted>" + esc(t["none"]) + "</span>"}</td>'
                        f'<td style="width:26%">{_bar(x["sec"] / mx * 100, "#0e7490")}</td>'
                        f'<td class="num">{_digits(x["tests"] or "", lang)}</td><td class="num">{_digits(x["words"] or "", lang)}</td>{ex}</tr>')
        out.append(f'<div class="card tall"><h2>{esc(t["daily"])}</h2><table><thead><tr><th>{esc(t["date"])}</th><th class="num">{esc(t["weekday"])}</th>'
                   f'<th class="num">{esc(t["time"])}</th><th></th><th class="num">{esc(t["tests_short"])}</th><th class="num">{esc(t["words_short"])}</th>'
                   f'{"<th>" + esc(t["exam"]) + "</th>" if any_exam else ""}</tr></thead><tbody>'
                   + "".join(rows) + "</tbody></table></div>\n")
    elif R["monthly"]:
        mx = max([m["sec"] for m in R["monthly"]] + [1])
        rows = []
        for m in R["monthly"]:
            rows.append(f'<tr><td>{esc(month_label(m["key"], lang))}</td><td class="num">{esc(fmt_dur(m["sec"], lang)) if m["sec"] else dash}</td>'
                        f'<td style="width:28%">{_bar(m["sec"] / mx * 100, "#0e7490")}</td>'
                        f'<td class="num">{_digits(str(m["active"]) + " " + t["of"] + " " + str(m["days"]), lang)}</td>'
                        f'<td class="num">{_digits(m["tests"], lang) if m["tests"] else dash}</td><td class="num">{_digits(m["words"], lang) if m["words"] else dash}</td></tr>')
        out.append(f'<div class="card tall"><h2>{esc(t["monthly"])}</h2><table><thead><tr><th>{esc(t["month"])}</th><th class="num">{esc(t["time"])}</th><th></th>'
                   f'<th class="num">{esc(t["active_days"])}</th><th class="num">{esc(t["tests_short"])}</th><th class="num">{esc(t["words_short"])}</th></tr></thead><tbody>'
                   + "".join(rows) + "</tbody></table></div>\n")
    # sessions
    if R["sessions"]:
        rows = []
        for x in R["sessions"]:
            rows.append(f'<tr><td class="num">{esc(fmt_date(x["start"].date(), lang))} · {_digits(x["start"].strftime("%H:%M"), lang)}</td>'
                        f'<td>{esc(x["subject"] or t["none"])}</td><td class="num">{esc(fmt_dur(x["planned_min"] * 60, lang))}</td>'
                        f'<td class="num">{esc(fmt_dur(x["focus_sec"], lang))}</td><td>{esc(_status(x["status"], lang))}</td>'
                        f'<td class="num">{_digits(x["blocked"], lang)}</td></tr>')
        out.append(f'<div class="card tall"><h2>{esc(t["sessions_title"])}</h2><table><thead><tr><th>{esc(t["when"])}</th><th>{esc(t["subject"])}</th>'
                   f'<th class="num">{esc(t["planned"])}</th><th class="num">{esc(t["focused"])}</th><th>{esc(t["status"])}</th>'
                   f'<th class="num">{esc(t["blocked"])}</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table></div>\n")
    # exams
    if R["exams"]:
        out.append(f'<div class="card"><h2>{esc(t["exams"])}</h2><table><tbody>'
                   + "".join(f'<tr><td class="num">{esc(fmt_date(e["date"], lang, weekday=True))}</td><td>{esc(e["name"])}</td></tr>' for e in R["exams"])
                   + "</tbody></table></div>\n")
    out.append(f'<div class="foot">{esc(t["app"])} · v{esc(R["version"])}</div>\n</div>\n</body>\n</html>\n')
    # tables scroll sideways on a phone instead of squeezing (print shows them whole)
    return "".join(out).replace("<table>", '<div class="tw"><table>').replace("</table>", "</table></div>")


# ------------------------------------------------------------------ CSV
def render_csv(R):
    """One UTF-8 file in sections (summary, subjects, days or months, sessions, exams); opens in Excel."""
    lang = R["lang"]
    t = STR[lang]
    s = R["summary"]
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")

    def mins(sec):
        return round(sec / 60, 1)

    w.writerow([t["title"], "VOIDLOCK " + R["version"]])
    if R["name"]:
        w.writerow([t["student"], R["name"]])
    w.writerow([t["start_gdate"], R["start"].isoformat(), fmt_jdate_numeric(R["start"])])
    w.writerow([t["end_gdate"], R["end"].isoformat(), fmt_jdate_numeric(R["end"])])
    w.writerow([t["generated"], R["generated"].strftime("%Y-%m-%d %H:%M")])
    w.writerow([])
    w.writerow([t["summary"]])
    w.writerow([t["key"], t["value"]])
    for k, v in ((t["total_min"], mins(s["total"])), (t["active_days"], s["active_days"]), (t["of_days"].format(n="").strip(), s["period_days"]),
                 (t["avg_active"] + " (" + t["csv_minutes"] + ")", mins(s["avg_active"])), (t["avg_cal"] + " (" + t["csv_minutes"] + ")", mins(s["avg_cal"])),
                 (t["tests"], s["tests"]), (t["words"], s["words"]), (t["streak"], s["streak"]), (t["goal_days"], s["goal_days"]),
                 (t["sessions"], s["sessions"]), (t["sessions_time"] + " (" + t["csv_minutes"] + ")", mins(s["sessions_sec"]))):
        w.writerow([k, v])
    if s["best"]:
        w.writerow([t["best"], s["best"]["date"].isoformat(), mins(s["best"]["sec"])])
    w.writerow([])
    w.writerow([t["subjects"]])
    w.writerow([t["subject"], t["total_min"], t["share"] + " %", t["tests"], t["words"]])
    total = s["total"]
    for r in R["subjects"]:
        nm = r["name"] + (f" ({t['deleted']})" if r["ghost"] else "")
        w.writerow([nm, mins(r["sec"]), round(r["sec"] / total * 100, 1) if total else 0, r["tests"], r["words"]])
    w.writerow([])
    cols = [r["name"] for r in R["subjects"] if r["sec"]]
    if R["daily_rows"]:
        w.writerow([t["daily"]])
        w.writerow([t["gdate"], t["jdate"], t["weekday"], t["total_min"], t["tests"], t["words"]] + cols)
        for x in R["days"]:
            per = {n: v for n, v in x["parts"]}
            w.writerow([x["date"].isoformat(), fmt_jdate_numeric(x["date"]), i18n.FA_DAYS[x["date"].weekday()] if lang == "fa" else x["date"].strftime("%a"),
                        mins(x["sec"]), x["tests"], x["words"]] + [mins(per.get(c, 0)) if per.get(c) else "" for c in cols])
    else:
        w.writerow([t["monthly"]])
        w.writerow([t["month"], t["total_min"], t["active_days"], t["days"], t["tests"], t["words"]])
        for m in R["monthly"]:
            w.writerow([month_label(m["key"], lang), mins(m["sec"]), m["active"], m["days"], m["tests"], m["words"]])
    w.writerow([])
    w.writerow([t["sessions_title"]])
    w.writerow([t["gdate"], "HH:MM", t["subject"], t["planned_min"], t["focus_min"], t["status"], t["blocked"]])
    for x in R["sessions"]:
        w.writerow([x["start"].date().isoformat(), x["start"].strftime("%H:%M"), x["subject"], x["planned_min"], mins(x["focus_sec"]),
                    _status(x["status"], lang), x["blocked"]])
    if R["exams"]:
        w.writerow([])
        w.writerow([t["exams"]])
        for e in R["exams"]:
            w.writerow([e["date"].isoformat(), fmt_jdate_numeric(e["date"]), e["name"]])
    sch = R.get("schedule")
    if sch and sch["has"]:
        w.writerow([])
        w.writerow([t["schedule_title"]])
        w.writerow([t["kind"], t["weekday"], "HH:MM", t["csv_minutes"], t["subject"], t["place"]])
        for d in sch["days"]:
            dn = i18n.FA_DAYS[d["weekday"]] if lang == "fa" else date(2024, 1, 1 + d["weekday"]).strftime("%A")
            for it in d["items"]:
                w.writerow([t["kind_class"] if it["kind"] == "class" else t["kind_session"], dn, it["time"], it["minutes"], it["name"], it["place"]])
    res = R.get("results")
    if res:
        w.writerow([])
        w.writerow([t["results_title"]])
        subs = [s for s in res["subjects"] if s["points"]]
        head = [t["gdate"], t["jdate"], t["exam_name"], t["taraz_total"], t["rank"], t["pct_avg"], t["note_l"]]
        for s in subs:
            head += [f"{s['name']} - {t['pct']}", f"{s['name']} - {t['taraz']}"]
        w.writerow(head)
        for i, e in enumerate(res["exams"]):
            d = date.fromisoformat(e["date"])
            row_ = [e["date"], fmt_jdate_numeric(d), e["name"], "" if e["taraz"] is None else e["taraz"], "" if e["rank"] is None else e["rank"],
                    "" if e["pct_avg"] is None else round(e["pct_avg"], 2), e["note"]]
            for s in subs:
                pt = next((p for p in s["points"] if p[0] == i), None)
                row_ += ["" if not pt or pt[1] is None else pt[1], "" if not pt or pt[2] is None else pt[2]]
            w.writerow(row_)
    return buf.getvalue()


def write_text(path, text, bom=False):
    with open(path, "w", encoding="utf-8-sig" if bom else "utf-8", newline="") as f:
        f.write(text)


# ------------------------------------------------------------------ PDF (Qt rich-text subset; drawn by report_pdf.py)
def _results_pdf(R, scenes, row, table, h, al):
    res = R.get("results")
    if not res:
        return ""
    lang = R["lang"]
    t = STR[lang]
    fa = lang == "fa"
    fi = lambda n: charts.fmt_int(n, fa)
    pc = lambda p: _digits(f"{p:.1f}", lang) + ("٪" if fa else "%")
    ex = res["exams"]

    def dl(v, better_up=True):
        if v is None or v == 0:
            return ""
        good = (v > 0) == better_up
        return f' <span style="color:{"#15803d" if good else "#b91c1c"}">{t["up"] if v > 0 else t["down"]} {esc(fi(abs(v)))}</span>'

    out = [h(t["results_title"])]
    latest = res["latest"]
    stats = [(t["exams_taken"], _digits(res["count"], lang))]
    if latest["taraz"] is not None:
        stats.append((t["latest"] + " · " + t["taraz_total"], fi(latest["taraz"]) + dl(latest["delta"])))
    if latest["rank"] is not None:
        stats.append((t["latest"] + " · " + t["rank"], fi(latest["rank"]) + dl(latest["delta_rank"])))
    if res["best_taraz"]:
        stats.append((t["best_taraz"] + f" ({res['best_taraz']['short']})", fi(res["best_taraz"]["taraz"])))
    if res["avg_taraz"] is not None:
        stats.append((t["avg_taraz"], fi(res["avg_taraz"])))
    if res["best_rank"]:
        stats.append((t["best_rank"] + f" ({res['best_rank']['short']})", fi(res["best_rank"]["rank"])))
    if res["first_to_last"] is not None:
        stats.append((t["first_to_last"], dl(res["first_to_last"]) or t["same"]))
    while len(stats) % 3:
        stats.append(("", ""))
    srows = []
    for i in range(0, len(stats), 3):
        cells = [(f'<span style="font-size:12.5pt; font-weight:600">{v}</span><br><span style="font-size:8pt; color:#5b6577">{esc(k)}</span>' if k else "")
                 for k, v in stats[i:i + 3]]
        srows.append(row(cells, bg="#f5f8fc"))
        srows.append('<tr><td></td></tr>')
    out.append(table(srows))
    for key, title in (("chart_taraz", "chart_taraz"), ("chart_rank", "chart_rank"), ("chart_subjects", "chart_subj")):
        if key in scenes:
            out.append(f'<p style="margin-top:6px; margin-bottom:0"><img src="{key}"></p>')
    rows = []
    for i, e in enumerate(reversed(ex)):
        rows.append(row([esc(fmt_date(date.fromisoformat(e["date"]), lang)), esc(e["name"]), esc(fi(e["taraz"])) if e["taraz"] is not None else esc(t["none"]),
                         dl(e["delta"]).strip(), esc(fi(e["rank"])) if e["rank"] is not None else esc(t["none"]), dl(e["delta_rank"]).strip(),
                         esc(pc(e["pct_avg"])) if e["pct_avg"] is not None else ""], bg="#fafcff" if i % 2 else None))
    out.append(h(t["exam_name"]))
    out.append(table(rows, head=[t["date"], t["exam_name"], t["taraz_total"], t["delta_taraz"], t["rank"], t["delta_rank"], t["pct_avg"]]))
    subs = [s for s in res["subjects"] if any(p[1] is not None or p[2] is not None for p in s["points"])]
    if subs:
        cols = list(range(max(0, len(ex) - 6), len(ex)))
        rows = []
        for k, s in enumerate(subs):
            cells = {i: (pct, tz) for i, pct, tz in s["points"]}
            vals = [f'<span style="color:{esc(s["color"])}">&#9679;</span> {esc(s["name"])}']
            for i in cols:
                pct, tz = cells.get(i, (None, None))
                vals.append((f"<b>{esc(fi(tz))}</b>" if tz is not None else "") + (f'<br><span style="font-size:7.5pt; color:#64748b">{esc(pc(pct))}</span>' if pct is not None else "")
                            or esc(t["none"]))
            vals.append(dl(s["delta"]).strip())
            rows.append(row(vals, bg="#fafcff" if k % 2 else None))
        out.append(h(t["subject_matrix"]))
        out.append(table(rows, head=[t["subject"]] + [ex[i]["short"] for i in cols] + [t["latest_vs_prev"]]))
    ins = []
    if res["strong"]:
        ins.append(f'<b>{esc(t["strong"])}:</b> ' + "، ".join(esc(f'{s["name"]} ({fi(s["latest_taraz"])})') for s in res["strong"]))
    if res["weak"]:
        ins.append(f'<b>{esc(t["weak"])}:</b> ' + "، ".join(esc(f'{s["name"]} ({fi(s["latest_taraz"])})') for s in res["weak"]))
    if res["improved"]:
        ins.append(f'<b>{esc(t["improved"])}:</b> {esc(res["improved"]["name"])}{dl(res["improved"]["delta"])}')
    if res["declined"]:
        ins.append(f'<b>{esc(t["declined"])}:</b> {esc(res["declined"]["name"])}{dl(res["declined"]["delta"], True)}')
    if ins:
        out.append('<p style="margin-top:8px">' + "<br>".join(ins) + "</p>")
    return "".join(out)


def _schedule_pdf(R, row, h, al):
    sch = R.get("schedule")
    if not sch or not sch["has"]:
        return ""
    lang = R["lang"]
    t = STR[lang]
    rtl = lang == "fa"
    heads, cells = [], []
    for d in sch["days"]:
        heads.append(esc(i18n.FA_DAYS[d["weekday"]] if rtl else date(2024, 1, 1 + d["weekday"]).strftime("%a")))
        parts = []
        for it in d["items"]:
            col = "#7e22ce" if it["kind"] == "class" else "#0369a1"
            title = it["name"] or (t["kind_class"] if it["kind"] == "class" else t["kind_session"])
            sub = fmt_dur(it["minutes"] * 60, lang) + ((" · " + it["place"]) if it["place"] else "")
            parts.append(f'<span style="color:{col}"><b>{esc(_digits(it["time"], lang))}</b></span> {esc(title)}<br><span style="font-size:7.5pt; color:#64748b">{esc(sub)}</span>')
        cells.append("<br>".join(parts) or esc(t["none"]))
    out = [h(t["schedule_title"])]
    body = ['<table width="100%" cellspacing="0" cellpadding="3" border="0">',
            row(heads, bg="#eef2f9", head=True, aligns=["center"] * 7), row(cells, aligns=[al] * 7), "</table>"]
    out.append("".join(body))
    out.append(f'<p style="font-size:8.5pt; color:#475569">{esc(t["week_class_h"])}: <b>{esc(fmt_dur(sch["class_min"] * 60, lang))}</b> &nbsp;·&nbsp; '
               f'{esc(t["week_session_h"])}: <b>{esc(fmt_dur(sch["session_min"] * 60, lang))}</b></p>')
    return "".join(out)


def render_pdf_html(R):
    """HTML for QTextDocument (tables, no flexbox). Qt lays tables out left-to-right even in an RTL document, so for Persian
    every row is written in reverse order - the first column then ends up at the right. Charts are images named
    chart_share / chart_daily that report_pdf draws."""
    lang = R["lang"]
    t = STR[lang]
    rtl = lang == "fa"
    s = R["summary"]
    total = s["total"]
    al = "right" if rtl else "left"

    def row(cells, bg=None, head=False, aligns=None):
        cells = list(cells)
        aligns = list(aligns or [al] * len(cells))
        if rtl:
            cells, aligns = cells[::-1], aligns[::-1]
        tag = "th" if head else "td"
        b = f' bgcolor="{bg}"' if bg else ""
        return "<tr" + b + ">" + "".join(f'<{tag} align="{a}" style="padding:4px 6px">{c}</{tag}>' for c, a in zip(cells, aligns)) + "</tr>"

    def table(rows, widths=None, head=None, aligns=None):
        out = ['<table width="100%" cellspacing="0" cellpadding="3" border="0" style="margin-top:2px">']
        if head:
            out.append("<thead>" + row(head, bg="#eef2f9", head=True, aligns=aligns) + "</thead>")
        out.extend(rows)
        out.append("</table>")
        return "".join(out)

    def h(text):
        return f'<p style="margin-top:14px; margin-bottom:3px"><span style="font-size:13pt; font-weight:600; color:#0e5a72">{esc(text)}</span></p>'

    dash = esc(t["none"])
    parts = [f'<html><body dir="{"rtl" if rtl else "ltr"}" style="color:#1d2433">']
    meta = []
    if R["name"]:
        meta.append(f'{esc(t["student"])}: <b>{esc(R["name"])}</b>')
    meta.append(f'{esc(t["period"])}: <b>{esc(period_title(R))}</b>')
    meta.append(f'{esc(t["generated"])}: {esc(fmt_date(R["generated"].date(), lang))}')
    parts.append('<table width="100%" cellspacing="0" cellpadding="10" border="0"><tr><td bgcolor="#0e7490" align="' + al + '">'
                 f'<span style="font-size:20pt; font-weight:600; color:#ffffff">{esc(t["title"])}</span><br>'
                 f'<span style="font-size:9.5pt; color:#e6f6fb">{"&nbsp;&nbsp;·&nbsp;&nbsp;".join(meta)}</span></td></tr></table>')
    if not R["days"] or (not total and not R["sessions"] and not R["subjects"]):
        parts.append(f'<p style="margin-top:20px">{esc(t["no_data"])}</p>')
    # summary: 3 columns
    best = s["best"]
    stats = [(t["total"], fmt_dur(total, lang)),
             (t["active_days"], _digits(f"{s['active_days']} " + t["of_days"].format(n=s["period_days"]), lang)),
             (t["avg_active"], fmt_dur(s["avg_active"], lang)), (t["avg_cal"], fmt_dur(s["avg_cal"], lang)),
             (t["best"] + (f" ({fmt_date(best['date'], lang, year=False)})" if best else ""), fmt_dur(best["sec"], lang) if best else t["none"]),
             (t["tests"], _digits(s["tests"], lang))]
    if s["words"]:
        stats.append((t["words"], _digits(s["words"], lang)))
    stats.append((t["streak"], _digits(s["streak"], lang)))
    if R["goal_sec"]:
        stats.append((t["goal_days"], _digits(f"{s['goal_days']} {t['of']} {s['period_days']}", lang)))
    stats.append((t["sessions"], _digits(s["sessions"], lang)))
    stats.append((t["sessions_time"], fmt_dur(s["sessions_sec"], lang)))
    while len(stats) % 3:
        stats.append(("", ""))
    parts.append(h(t["summary"]))
    srows = []
    for i in range(0, len(stats), 3):
        cells = [(f'<span style="font-size:12.5pt; font-weight:600">{esc(v)}</span><br><span style="font-size:8pt; color:#5b6577">{esc(k)}</span>' if k else "")
                 for k, v in stats[i:i + 3]]
        srows.append(row(cells, bg="#f5f8fc"))
        srows.append('<tr><td></td></tr>')
    parts.append(table(srows))
    parts.append(f'<p style="font-size:8pt; color:#64748b">{esc(t["note"])}</p>')
    # subjects
    if R["subjects"]:
        parts.append('<table width="100%" cellspacing="0" cellpadding="0" border="0"><tr><td align="' + al + '">'
                     + h(t["subjects"]) + '<br><img src="chart_share"></td></tr></table>')
        rows = []
        for r in R["subjects"]:
            pct = (r["sec"] / total * 100) if total else 0
            nm = f'<span style="color:{esc(r["color"])}">&#9679;</span> {esc(r["name"])}' + (f' <span style="color:#64748b">({esc(t["deleted"])})</span>' if r["ghost"] else "")
            rows.append(row([nm, esc(fmt_dur(r["sec"], lang)), _digits(f"{pct:.0f}%", lang),
                             _digits(r["tests"], lang) if r["tests"] else dash, _digits(r["words"], lang) if r["words"] else dash]))
        parts.append(table(rows, head=[t["subject"], t["time"], t["share"], t["tests_short"], t["words_short"]]))
    # charts, exam results and the weekly timetable
    scenes = pdf_scenes(R)
    if "chart_study" in scenes:
        mode = "day" if R["daily_rows"] else "month"
        parts.append('<p style="margin-top:12px; margin-bottom:0"><img src="chart_study"></p>')
        if "chart_weekday" in scenes:
            parts.append('<p style="margin-top:6px; margin-bottom:0"><img src="chart_weekday"></p>')
    parts.append(_results_pdf(R, scenes, row, table, h, al))
    parts.append(_schedule_pdf(R, row, h, al))
    if R["daily_rows"] and R["days"]:
        any_exam = any(x["exam"] for x in R["days"])
        rows = []
        for x in R["days"]:
            cells = [esc(fmt_date(x["date"], lang)), esc(i18n.FA_DAYS[x["date"].weekday()] if rtl else x["date"].strftime("%a")),
                     esc(fmt_dur(x["sec"], lang)) if x["sec"] else dash, _digits(x["tests"] or "", lang), _digits(x["words"] or "", lang)]
            if any_exam:
                cells.append(f'<span style="color:#b45309">{esc(", ".join(x["exam"]))}</span>' if x["exam"] else "")
            rows.append(row(cells, bg="#fafcff" if len(rows) % 2 else None))
        head = [t["date"], t["weekday"], t["time"], t["tests_short"], t["words_short"]] + ([t["exam"]] if any_exam else [])
        parts.append(h(t["daily"]))
        parts.append(table(rows, head=head))
    elif R["monthly"]:
        rows = [row([esc(month_label(m["key"], lang)), esc(fmt_dur(m["sec"], lang)) if m["sec"] else dash, _digits(str(m["active"]) + " " + t["of"] + " " + str(m["days"]), lang),
                     _digits(m["tests"], lang) if m["tests"] else dash, _digits(m["words"], lang) if m["words"] else dash], bg="#fafcff" if i % 2 else None)
                for i, m in enumerate(R["monthly"])]
        parts.append(h(t["monthly"]))
        parts.append(table(rows, head=[t["month"], t["time"], t["active_days"], t["tests_short"], t["words_short"]]))
    # sessions
    if R["sessions"]:
        rows = [row([f'{esc(fmt_date(x["start"].date(), lang))} {_digits(x["start"].strftime("%H:%M"), lang)}', esc(x["subject"] or t["none"]),
                     esc(fmt_dur(x["planned_min"] * 60, lang)), esc(fmt_dur(x["focus_sec"], lang)), esc(_status(x["status"], lang)),
                     _digits(x["blocked"], lang)], bg="#fafcff" if i % 2 else None) for i, x in enumerate(R["sessions"])]
        parts.append(h(t["sessions_title"]))
        parts.append(table(rows, head=[t["when"], t["subject"], t["planned"], t["focused"], t["status"], t["blocked"]]))
    if R["exams"]:
        parts.append(h(t["exams"]))
        parts.append(table([row([esc(fmt_date(e["date"], lang, weekday=True)), esc(e["name"])]) for e in R["exams"]]))
    parts.append("</body></html>")
    return "".join(parts)
