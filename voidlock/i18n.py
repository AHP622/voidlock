"""Translation layer (English source strings -> Persian) with RTL support.

Strings stay in English in the code. When the language is Persian, every label, button,
tooltip and placeholder is translated on its way into the widget (see install_hooks), by
exact match or by a template such as "Showing {n} of {t} applications". Anything not in the
catalog simply stays English, so a missing translation can never break the UI.
"""
import os
import re
from datetime import datetime
from functools import lru_cache

LANGS = {"en": "English", "fa": "فارسی"}
FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
_NUMERIC = re.compile(r"^[\d\s.,:%/·+\-−x×]+$")
_PH = re.compile(r"\{(\w+)\}")
_state = {"lang": "en"}
_exact, _exact_ci, _rules = {}, {}, []
misses = set()          # untranslated strings seen (debug helper)


def lang():
    return _state["lang"]


def is_fa():
    return _state["lang"] == "fa"


def set_language(code):
    _state["lang"] = code if code in LANGS else "en"
    _tr.cache_clear()
    if is_fa() and not _exact:
        _load_catalog()


def _load_catalog():
    from .fa_strings import FA
    for k, v in FA.items():
        if "{" in k:
            pat = re.escape(k)
            pat = re.sub(r"\\\{(\w+)\\\}",
                         lambda m: f"(?P<{m.group(1)}>" + (r"\d+" if m.group(1).startswith("num") else ".+?") + ")", pat)
            _rules.append((re.compile("^" + pat + "$", re.S), v, len(k)))
        else:
            _exact[k] = v
            _exact_ci.setdefault(k.casefold(), v)
    _rules.sort(key=lambda r: -r[2])


def digits(s):
    return str(s).translate(FA_DIGITS) if is_fa() else str(s)


def tr(s):
    if not is_fa() or not isinstance(s, str) or not s:
        return s
    return _tr(s)


def _sep(s):
    return s.replace(" · ", " | ")


@lru_cache(maxsize=8192)
def _tr(s):
    return _sep(_tr_raw(s))


def _tr_raw(s):
    if "\n" in s:
        return "\n".join(_tr_raw(line) if line else line for line in s.split("\n"))
    t = _exact.get(s)
    if t is None:
        t = _exact_ci.get(s.casefold())
    if t is not None:
        return t
    for rx, out, _n in _rules:
        m = rx.match(s)
        if m:
            vals = {k: _group(v) for k, v in m.groupdict().items()}
            try:
                return out.format(**vals)
            except (KeyError, IndexError):
                break
    if _NUMERIC.match(s):
        return s.translate(FA_DIGITS)
    if os.environ.get("VOIDLOCK_I18N_DEBUG") and re.search(r"[A-Za-z]{3,}", s):
        misses.add(s)
    return s


def _group(v):
    if _NUMERIC.match(v):
        return v.translate(FA_DIGITS)
    return _tr(v)


# ------------------------------------------------------------------ calendar (Jalali)
def to_jalali(dt):
    gy, gm, gd = dt.year, dt.month, dt.day
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    if gy > 1600:
        jy = 979
        gy -= 1600
    else:
        jy = 0
        gy -= 621
    gy2 = gy + 1 if gm > 2 else gy
    days = 365 * gy + (gy2 + 3) // 4 - (gy2 + 99) // 100 + (gy2 + 399) // 400 - 80 + gd + g_d_m[gm - 1]
    jy += 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + days // 31
        jd = 1 + days % 31
    else:
        jm = 7 + (days - 186) // 30
        jd = 1 + (days - 186) % 30
    return jy, jm, jd


EN_JMONTHS = ["Farvardin", "Ordibehesht", "Khordad", "Tir", "Mordad", "Shahrivar", "Mehr", "Aban", "Azar", "Dey",
              "Bahman", "Esfand"]


def from_jalali(jy, jm, jd):
    """Jalali -> (gy, gm, gd)."""
    jy += 1595
    days = -355668 + (365 * jy) + ((jy // 33) * 8) + (((jy % 33) + 3) // 4) + jd + \
        ((jm - 1) * 31 if jm < 7 else ((jm - 7) * 30) + 186)
    gy = 400 * (days // 146097)
    days %= 146097
    if days > 36524:
        days -= 1
        gy += 100 * (days // 36524)
        days %= 36524
        if days >= 365:
            days += 1
    gy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        gy += (days - 1) // 365
        days = (days - 1) % 365
    gd = days + 1
    leap = (gy % 4 == 0 and gy % 100 != 0) or gy % 400 == 0
    sal = [0, 31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    gm = 0
    while gm < 13 and gd > sal[gm]:
        gd -= sal[gm]
        gm += 1
    return gy, gm, gd


def jalali_str(jy, jm, jd):
    if is_fa():
        return digits(f"{jd} {FA_MONTHS[jm - 1]} {jy}")
    return f"{jd} {EN_JMONTHS[jm - 1]} {jy} (Jalali)"


FA_MONTHS = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور", "مهر", "آبان", "آذر", "دی",
             "بهمن", "اسفند"]
FA_DAYS = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه", "شنبه", "یکشنبه"]        # Mon..Sun
FA_DAYS_SHORT = ["د", "س", "چ", "پ", "ج", "ش", "ی"]
EN_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def day_name(weekday, short=False):
    if is_fa():
        return FA_DAYS_SHORT[weekday] if short else FA_DAYS[weekday]
    return EN_DAYS[weekday]


def fmt_when(dt, with_time=True):
    """'Sat 10 Oct · 23:06' or '۱۸ مهر · ۲۳:۰۶' (Jalali)."""
    if is_fa():
        jy, jm, jd = to_jalali(dt)
        s = f"{FA_DAYS[dt.weekday()]} {jd} {FA_MONTHS[jm - 1]}"
        if with_time:
            s += f" | {dt.strftime('%H:%M')}"
        return digits(s)
    s = dt.strftime("%a %d %b")
    return s + (dt.strftime(" · %H:%M") if with_time else "")


def fmt_clock_line(dt):
    if is_fa():
        jy, jm, jd = to_jalali(dt)
        return digits(f"{FA_DAYS[dt.weekday()]} {jd} {FA_MONTHS[jm - 1]}  |  {dt.strftime('%H:%M:%S')}")
    return dt.strftime("%a %d %b  ·  %H:%M:%S")


def fmt_remaining(sec):
    """Compact remaining time for locks: 2d 4h / 5h 12m / 42m."""
    sec = max(0, int(sec))
    d, r = divmod(sec, 86400)
    h, r = divmod(r, 3600)
    m = r // 60
    if d:
        return tr(f"{d}d {h}h")
    if h:
        return tr(f"{h}h {m:02d}m")
    return tr(f"{max(1, m)}m")


def fmt_in(sec):
    """'in 25m' / '۲۵ دقیقه دیگر'."""
    return tr(f"in {fmt_remaining(sec)}")


# ------------------------------------------------------------------ Qt hooks
def install_hooks():
    """Translate text on its way into widgets. Call once, after QApplication exists."""
    from PySide6.QtWidgets import QAbstractButton, QLabel, QLineEdit, QWidget

    def wrap(cls, name):
        orig = getattr(cls, name)

        def w(self, text, *a, **k):
            return orig(self, tr(text) if isinstance(text, str) else text, *a, **k)
        w.__name__ = name
        setattr(cls, name, w)

    wrap(QLabel, "setText")
    wrap(QAbstractButton, "setText")
    wrap(QLineEdit, "setPlaceholderText")
    wrap(QWidget, "setToolTip")


def lead_right():
    """True when text should be right-aligned (Persian UI)."""
    return is_fa()
