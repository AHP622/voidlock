"""Weekly class timetable: what is next, what is running now, and which reminders are due. Pure functions, no Qt."""
from datetime import datetime, timedelta


def _start(c, day):
    h, m = (int(x) for x in c["time"].split(":"))
    return day.replace(hour=h, minute=m, second=0, microsecond=0)


def occurrences(classes, now, days=8):
    """[(start, end, class)] for the classes of today and the coming days, sorted by start. A class that began less
    than its duration ago is still included (it is 'running')."""
    out = []
    base = now.replace(hour=0, minute=0, second=0, microsecond=0)
    for add in range(-1, days):
        d = base + timedelta(days=add)
        for c in classes:
            if not c.get("enabled", True) or c["day"] != d.weekday():
                continue
            s = _start(c, d)
            e = s + timedelta(minutes=int(c.get("minutes", 90)))
            if e > now:
                out.append((s, e, c))
    out.sort(key=lambda t: t[0])
    return out


def today_list(classes, now):
    """Today's classes in time order (finished ones included)."""
    base = now.replace(hour=0, minute=0, second=0, microsecond=0)
    out = []
    for c in classes:
        if c.get("enabled", True) and c["day"] == now.weekday():
            s = _start(c, base)
            out.append((s, s + timedelta(minutes=int(c.get("minutes", 90))), c))
    out.sort(key=lambda t: t[0])
    return out


def current_or_next(classes, now):
    """Returns (state, class, start, end): state is 'now' (running), 'next', or None when nothing is planned."""
    occ = occurrences(classes, now)
    for s, e, c in occ:
        if s <= now < e:
            return "now", c, s, e
    for s, e, c in occ:
        if s > now:
            return "next", c, s, e
    return None, None, None, None


def due_reminders(classes, now):
    """Reminders that should fire right now: [(class, kind, minutes_left)]. kind 'soon' = N minutes before the class,
    'start' = it begins (within the last 2 minutes). Each fires once per day (rem_done / start_done)."""
    today = now.date().isoformat()
    out = []
    for s, e, c in today_list(classes, now):
        lead = int(c.get("remind", 15))
        if lead > 0 and c.get("rem_done") != today and s - timedelta(minutes=lead) <= now < s:
            out.append((c, "soon", max(1, int((s - now).total_seconds() // 60 + (1 if (s - now).total_seconds() % 60 else 0)))))
        if c.get("start_done") != today and s <= now < s + timedelta(minutes=2):
            out.append((c, "start", 0))
    return out


def mark_done(c, kind, now):
    c["rem_done" if kind == "soon" else "start_done"] = now.date().isoformat()
    if kind == "start" and c.get("rem_done") != now.date().isoformat():
        c["rem_done"] = now.date().isoformat()      # a late reminder is pointless once the class has begun


def overlap_names(classes, sessions, day, time_s, minutes, skip_id=None):
    """Names of classes / sessions on `day` that overlap [time_s, time_s + minutes). For a warning in the forms."""
    def span(t, mins):
        h, m = (int(x) for x in t.split(":"))
        return h * 60 + m, h * 60 + m + int(mins)
    a0, a1 = span(time_s, minutes)
    out = []
    for kind, items in (("class", classes), ("session", sessions)):
        for e in items:
            if e.get("id") == skip_id or e.get("day") != day or not e.get("enabled", True):
                continue
            b0, b1 = span(e["time"], e.get("minutes", 90))
            if a0 < b1 and b0 < a1:
                out.append((e.get("name") or e.get("subject") or kind, e["time"], kind))
    return out
