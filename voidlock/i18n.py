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
_BREAKS = (-61, 9, 38, 199, 426, 686, 756, 818, 1111, 1181, 1210, 1635, 2060, 2097, 2192, 2262, 2324, 2394,
           2456, 3178)


def _jal_cal(jy):
    """Leap status and the March day of Nowruz for Jalali year `jy` (33-year-cycle rules with the official break
    years, as in jalaali-js). The old 4-year arithmetic was a day off after 1407, e.g. for exam dates in 1408+."""
    gy = jy + 621
    leap_j = -14
    jp = _BREAKS[0]
    jump = 0
    for jm in _BREAKS[1:]:
        jump = jm - jp
        if jy < jm:
            break
        leap_j += (jump // 33) * 8 + (jump % 33) // 4
        jp = jm
    n = jy - jp
    leap_j += (n // 33) * 8 + ((n % 33) + 3) // 4
    if jump % 33 == 4 and jump - n == 4:
        leap_j += 1
    leap_g = gy // 4 - ((gy // 100 + 1) * 3) // 4 - 150
    march = 20 + leap_j - leap_g
    if jump - n < 6:
        n = n - jump + ((jump + 4) // 33) * 33
    leap = ((n + 1) % 33 - 1) % 4
    if leap == -1:
        leap = 4
    return leap, march


def is_jalali_leap(jy):
    return _jal_cal(jy)[0] == 0


def jalali_month_days(jy, jm):
    return 31 if jm <= 6 else (30 if jm <= 11 else (30 if is_jalali_leap(jy) else 29))


def to_jalali(dt):
    from datetime import date as _date
    d = _date(dt.year, dt.month, dt.day)
    jy = d.year - 621
    leap, march = _jal_cal(jy)
    k = d.toordinal() - _date(d.year, 3, march).toordinal()
    if k >= 0:
        if k <= 185:
            return jy, 1 + k // 31, k % 31 + 1
        k -= 186
    else:
        jy -= 1
        k += 179
        if leap == 1:
            k += 1
    return jy, 7 + k // 30, k % 30 + 1


EN_JMONTHS = ["Farvardin", "Ordibehesht", "Khordad", "Tir", "Mordad", "Shahrivar", "Mehr", "Aban", "Azar", "Dey",
              "Bahman", "Esfand"]


def from_jalali(jy, jm, jd):
    """Jalali -> (gy, gm, gd). Raises ValueError for an impossible date."""
    from datetime import date as _date, timedelta as _td
    if not (1 <= jm <= 12) or not (1 <= jd <= jalali_month_days(jy, jm)):
        raise ValueError("invalid Jalali date")
    _leap, march = _jal_cal(jy)
    d = _date(jy + 621, 3, march) + _td(days=(jm - 1) * 31 - (jm // 7) * (jm - 7) + jd - 1)
    return d.year, d.month, d.day


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
