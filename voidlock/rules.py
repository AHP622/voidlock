"""Lock-hour windows (pure). A window blocks whole categories on chosen weekdays between two times."""
from datetime import datetime, timedelta

WINDOW_CATS = ["Games", "Launchers", "Social", "Media", "Browsers", "Sites", "Other"]
PASS_CATS = {"Games", "Launchers"}      # a play pass lifts lock hours for these categories only


def hm(s):
    h, m = str(s).split(":")
    return int(h) * 60 + int(m)


def window_active(w, dt):
    """Is window `w` blocking at datetime `dt`? Supports ranges that cross midnight."""
    days = set(w.get("days", []))
    if not days:
        return False
    s, e = hm(w["start"]), hm(w["end"])
    m = dt.hour * 60 + dt.minute
    wd = dt.weekday()
    if s == e:
        return wd in days                      # same time twice = the whole day
    if s < e:
        return wd in days and s <= m < e
    return (wd in days and m >= s) or (((wd - 1) % 7) in days and m < e)


def window_end(w, dt):
    """When the currently active window ends (datetime), or None."""
    if not window_active(w, dt):
        return None
    s, e = hm(w["start"]), hm(w["end"])
    if s == e:
        return dt.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    end = dt.replace(hour=e // 60, minute=e % 60, second=0, microsecond=0)
    if end <= dt:
        end += timedelta(days=1)
    return end


def active_windows(windows, dt):
    return [w for w in windows if w.get("enabled", True) and window_active(w, dt)]


def blocked_categories(windows, dt, pass_active=False):
    cats = set()
    for w in active_windows(windows, dt):
        cats |= set(w.get("categories", []))
    if pass_active:
        cats -= PASS_CATS
    return cats


def next_change(windows, dt):
    """Next datetime (within 8 days) at which the blocked/unblocked state flips, or None."""
    cur = bool(active_windows(windows, dt))
    t = dt.replace(second=0, microsecond=0)
    for i in range(1, 8 * 24 * 60 + 1):
        t2 = t + timedelta(minutes=i)
        if bool(active_windows(windows, t2)) != cur:
            return t2
    return None
