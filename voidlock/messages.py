"""The personal message shown when a blocked program is closed (pure; no Qt)."""
from datetime import date

from . import i18n


def exam_date(settings):
    j = settings.get("exam_date") or [1406, 4, 10]
    try:
        return date(*i18n.from_jalali(int(j[0]), int(j[1]), int(j[2])))
    except (ValueError, TypeError, IndexError):
        return date(2027, 7, 1)


def days_left(settings, today=None):
    return (exam_date(settings) - (today or date.today())).days


def _fa_quotes(text):
    """Turns ASCII double quotes in the user's own text into « » pairs."""
    out, opened = [], False
    for ch in text:
        if ch == '"':
            out.append("»" if opened else "«")
            opened = not opened
        else:
            out.append(ch)
    return "".join(out)


def block_message(settings, name, why="session", today=None):
    """Returns (title, body) in the user's language."""
    fa = settings.get("language") == "fa"
    n = days_left(settings, today)
    j = settings.get("exam_date") or [1406, 4, 10]
    when = i18n.jalali_str(int(j[0]), int(j[1]), int(j[2]))
    field = (settings.get("target_field") or "").strip()
    custom = (settings.get("custom_message") or "").strip()
    if fa:
        reasons = {"lock": "قفل چندروزه فعاله.", "window": "الان ساعت قفل بازیه.",
                   "session": "الان وقت تمرکزه."}
        lines = [f"«\u2067{name}\u2069» بسته شد. {reasons.get(why, '')}".strip()]
        if field:
            lines.append(f"هدفت: {field}")
        if n > 0:
            lines.append(i18n.digits(f"{n} روز تا کنکور (\u2067{when}\u2069)"))
        elif n == 0:
            lines.append("امروز روز کنکوره! موفق باشی.")
        lines.append(_fa_quotes(custom) if custom else "بعداً با خیال راحت می‌تونی بازی کنی؛ الان برای اون چیزی که می‌خوای تلاش کن.")
        return "VOIDLOCK", "\n".join(lines)
    reasons = {"lock": "A multi-day lock is active.", "window": "It is lock hours right now.",
               "session": "It is focus time."}
    lines = [f"“{name}” was closed. {reasons.get(why, '')}".strip()]
    if field:
        lines.append(f"Your goal: {field}")
    if n > 0:
        lines.append(f"{n} days until the exam ({when})")
    elif n == 0:
        lines.append("The exam is today. Good luck!")
    lines.append(custom or "You can play later - right now, work for what you want.")
    return "VOIDLOCK", "\n".join(lines)
