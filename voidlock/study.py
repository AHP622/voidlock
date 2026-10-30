"""Study log (stopwatch, tests, to-dos), play statistics, focus points and attempt reports.
Pure functions over the Store - no Qt."""
import re
import time
from datetime import date, datetime, timedelta

from . import i18n
from .store import read_json, uid, write_json

SUBJECT_COLORS = ["#FF5DA2", "#8B5CF6", "#00C2FF", "#34D399", "#FBBF24", "#FB7185", "#60A5FA", "#F97316"]
DEFAULT_SUBJECTS = [("Math", "#8B5CF6"), ("Physics", "#00C2FF"), ("Chemistry", "#34D399"),
                    ("Biology", "#FBBF24"), ("Literature", "#FF5DA2"), ("English", "#FB923C")]
# subjects whose name looks like a language get a "words learned" counter next to the tests counter
_WORDS_NAME = re.compile(r"english|انگلیسی|زبان|language|vocab|لغت|واژه", re.I)


_FA = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩٫٬،/", "01234567890123456789.,,.")


def parse_number(text):
    """'۷۵٫۵', '75,5', '-12.3', '8 120' -> float (None when empty or not a number). Persian / Arabic digits are accepted."""
    t = str(text or "").translate(_FA).replace(" ", "").replace("\u200c", "").replace("\u200f", "").replace("\u200e", "")
    if not t:
        return None
    if t.count(",") == 1 and "." not in t and len(t.split(",")[1]) <= 2:
        t = t.replace(",", ".")                    # decimal comma
    t = t.replace(",", "")
    t = t.replace("\u2212", "-")                  # a typographic minus sign
    try:
        return float(t)
    except ValueError:
        return None


def dkey(d):
    if isinstance(d, str):
        return d
    if isinstance(d, datetime):          # datetime is a subclass of date: its isoformat() would carry the time
        return d.date().isoformat()
    return d.isoformat()


# ============================================================ study log
class StudyLog:
    """subjects, entries, tests, todos and the running stopwatch, stored in store.study."""

    def __init__(self, store):
        self.store = store
        self._gen = 0                      # bumped by every change made through this class
        self._ikey, self._idx = None, None
        self._ensure()

    def _ensure(self):
        """The study data can be replaced behind our back (reset, restore, import). Missing parts are put back here,
        on every access, instead of only once at start-up (a reset used to crash the Study page and the Overview)."""
        st = self.store.study
        if not isinstance(st, dict):
            st = self.store.study = {}
        fresh = "subjects" not in st
        st.setdefault("subjects", [])
        st.setdefault("entries", [])      # {id,date,subject,sec,source,t}
        st.setdefault("tests", {})        # {date: {subject_id: count}}
        st.setdefault("words", {})        # {date: {subject_id: count}}  (language subjects)
        st.setdefault("gone", {})         # {subject_id: {name, color}} of deleted subjects: their hours keep a name
        st.setdefault("exams", [])        # {id, name, date, time, notified}
        st.setdefault("todos", [])        # {id,date,text,done}
        st.setdefault("active", None)     # {subject, started, last_seen}
        if fresh and not st["subjects"]:
            st["subjects"] = [{"id": uid(), "name": n, "color": c} for n, c in DEFAULT_SUBJECTS]
            self.save()
        return st

    @property
    def d(self):
        return self._ensure()

    # ---- per-day totals, built once per change (the Overview asks for them every second; they used to be recomputed
    # from every entry and every session for every day, which gets slow after months of use)
    def _index(self):
        st, hist = self.d, self.store.history
        key = (id(st["entries"]), len(st["entries"]), id(hist), len(hist),
               hist[-1].get("id") if hist and isinstance(hist[-1], dict) else None, self._gen)
        if key == self._ikey:
            return self._idx
        ent_day, ent_subj, sess_day, sess_subj = {}, {}, {}, {}
        for e in st["entries"]:
            try:
                k, sec = e["date"], int(e["sec"])
            except (KeyError, TypeError, ValueError):
                continue
            ent_day[k] = ent_day.get(k, 0) + sec
            ent_subj[(k, e.get("subject"))] = ent_subj.get((k, e.get("subject")), 0) + sec
        for r in hist:
            try:
                k = datetime.fromtimestamp(r["start"]).date().isoformat()
                fs = int(r.get("focus_sec", 0))
                sess_day[k] = sess_day.get(k, 0) + fs
                nm = str(r.get("subject") or "").strip().lower()
                if nm:
                    sess_subj[(k, nm)] = sess_subj.get((k, nm), 0) + fs
            except Exception:
                pass
        self._ikey, self._idx = key, (ent_day, ent_subj, sess_day, sess_subj)
        return self._idx

    def save(self):
        self.store.save_study()

    # ---- subjects
    def subjects(self):
        return self.d["subjects"]

    def subject(self, sid):
        return next((s for s in self.subjects() if s["id"] == sid), None)

    @staticmethod
    def _same(a, b):
        return str(a).strip().casefold() == str(b).strip().casefold()

    def add_subject(self, name, color=None, words=False, tests=True):
        """A subject with the name of a deleted one gets that subject's id back, so its old hours, tests and words
        belong to it again (deleting a subject and adding it again used to cut the history off)."""
        name = name.strip()
        color = color or SUBJECT_COLORS[len(self.subjects()) % len(SUBJECT_COLORS)]
        sid = next((k for k, g in self.d["gone"].items() if self._same(g.get("name", ""), name)), None)
        s = {"id": sid or uid(), "name": name, "color": color}
        if sid:
            self.d["gone"].pop(sid, None)
        if words:
            s["words"] = True
        if not tests:
            s["tests"] = False
        self.subjects().append(s)
        self._gen += 1
        self.save()
        return s

    def edit_subject(self, sid, name=None, color=None, words=None, tests=None):
        s = self.subject(sid)
        if not s:
            return None
        if name is not None and name.strip():
            s["name"] = name.strip()
        if color:
            s["color"] = color
        if words is not None:
            s["words"] = bool(words)
        if tests is not None:
            s["tests"] = bool(tests)
        self._gen += 1
        self.save()
        return s

    def shows_tests(self, subject):
        s = subject if isinstance(subject, dict) else self.subject(subject)
        return bool(s) and s.get("tests", True)

    def remove_subject(self, sid):
        if self.d["active"] and self.d["active"]["subject"] == sid:
            self.stop()                    # keep the time that was running (it used to be thrown away)
        s = self.subject(sid)
        if s:
            self.d["gone"][sid] = {"name": s["name"], "color": s.get("color", "#8A8F9C")}
        self.d["subjects"] = [s for s in self.subjects() if s["id"] != sid]
        self._gen += 1
        self.save()

    # ---- hours / tests that belong to subjects that no longer exist
    def orphan_ids(self):
        known = {s["id"] for s in self.subjects()}
        ids = set()
        for e in self.d["entries"]:
            ids.add(e.get("subject"))
        for key in ("tests", "words"):
            for day in self.d[key].values():
                ids.update(day.keys())
        return {i for i in ids if i and i not in known}

    def ghost(self, sid):
        """A subject-like record for an id that is not in the list any more (name from the 'gone' notes if known)."""
        g = self.d["gone"].get(sid)
        return {"id": sid, "name": (g or {}).get("name") or "Deleted subjects", "color": (g or {}).get("color") or "#8A8F9C",
                "ghost": True}

    def repair_subjects(self, backups):
        """`backups`: study.json dicts (newest first). Hours of subjects that were deleted *and added again by hand*
        (so they got a new id) are given back to the subject with the same name; the others get their old name from the
        newest backup that knew them, or stay as 'Deleted subjects'. Returns (relinked_ids, named_ids)."""
        orphans = self.orphan_ids() - set(self.d["gone"])
        if not orphans:
            return 0, 0
        found = {}
        for b in backups:
            for s in (b.get("subjects") or []) if isinstance(b, dict) else []:
                if isinstance(s, dict) and s.get("id") in orphans and s["id"] not in found:
                    found[s["id"]] = {"name": str(s.get("name", "")), "color": s.get("color") or "#8A8F9C"}
        relinked = named = 0
        for old, info in found.items():
            tgt = next((s for s in self.subjects() if self._same(s["name"], info["name"])), None)
            if tgt:
                self._relink(old, tgt["id"])
                relinked += 1
            else:
                self.d["gone"][old] = info
                named += 1
        if found:
            self._gen += 1
            self.save()
        return relinked, named

    def _relink(self, old, new):
        for e in self.d["entries"]:
            if e.get("subject") == old:
                e["subject"] = new
        for key in ("tests", "words"):
            for day in self.d[key].values():
                if old in day:
                    day[new] = day.get(new, 0) + day.pop(old)
        a = self.d["active"]
        if a and a.get("subject") == old:
            a["subject"] = new

    # ---- stopwatch (one subject at a time)
    def active(self):
        return self.d["active"]

    def start(self, sid, now=None):
        now = now or time.time()
        if self.d["active"]:
            self.stop(now)
        self.d["active"] = {"subject": sid, "started": now, "last_seen": now}
        self.save()

    def heartbeat(self, now=None):
        a = self.d["active"]
        if a:
            a["last_seen"] = now or time.time()
            self.save()

    def elapsed(self, now=None):
        a = self.d["active"]
        return max(0, (now or time.time()) - a["started"]) if a else 0

    def stop(self, now=None):
        """Saves the running time as an entry. Returns the seconds recorded."""
        a = self.d["active"]
        if not a:
            return 0
        now = now or time.time()
        sec = int(max(0, min(now, a["started"] + 12 * 3600) - a["started"]))
        if sec >= 5:
            self._split_over_midnight(a["subject"], a["started"], a["started"] + sec, "stopwatch")
        self.d["active"] = None
        self.save()
        return sec

    def restore(self, now=None):
        """After a restart: if the stopwatch was running, count only until the last time we saw the app."""
        a = self.d["active"]
        if not a:
            return 0
        now = now or time.time()
        if now - a["last_seen"] > 120:
            end = a["last_seen"]
            sec = int(max(0, end - a["started"]))
            if sec >= 5:
                self._split_over_midnight(a["subject"], a["started"], end, "stopwatch")
            self.d["active"] = None
            self.save()
            return sec
        return 0

    def _split_over_midnight(self, sid, t0, t1, source):
        self._gen += 1
        cur = t0
        while cur < t1:
            dt = datetime.fromtimestamp(cur)
            nxt = (dt.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)).timestamp()
            end = min(t1, nxt)
            self.d["entries"].append({"id": uid(), "date": dt.date().isoformat(), "subject": sid,
                                      "sec": int(end - cur), "source": source, "t": cur})
            cur = end

    def add_manual(self, d, sid, minutes):
        self.d["entries"].append({"id": uid(), "date": dkey(d), "subject": sid, "sec": int(minutes * 60),
                                  "source": "manual", "t": time.time()})
        self._gen += 1
        self.save()

    # ---- totals (stopwatch/manual entries + finished countdown sessions)
    def day_entries_sec(self, d, sid=None):
        k = dkey(d)
        ent_day, ent_subj, _s, _ss = self._index()
        return ent_day.get(k, 0) if sid is None else ent_subj.get((k, sid), 0)

    def day_sessions_sec(self, d, sid=None):
        """Focus-session time of a day (Study Sessions tab); for one subject when `sid` is given (matched by name)."""
        idx = self._index()
        if sid is None:
            return idx[2].get(dkey(d), 0)
        s = self.subject(sid)
        return idx[3].get((dkey(d), str(s["name"]).strip().lower()), 0) if s else 0

    def day_subject_times(self, d, now=None):
        """[(subject, seconds)] for every subject with study time on that day, longest first. Time of deleted subjects is
        included (as ghosts, grouped by name), so the list always adds up to the day's total."""
        out = [(s, self.subject_day_sec(d, s["id"], now)) for s in self.subjects()]
        k = dkey(d)
        known = {s["id"] for s in self.subjects()}
        ghosts = {}
        for (day, sid), v in self._index()[1].items():
            if day == k and sid not in known and v > 0:
                g = self.ghost(sid)
                slot = ghosts.setdefault(g["name"].strip().casefold(), [g, 0])
                slot[1] += v
        out += [(g, v) for g, v in ghosts.values()]
        return sorted([(s, v) for s, v in out if v > 0], key=lambda t: -t[1])

    def day_orphan_tests(self, d):
        known = {s["id"] for s in self.subjects()}
        return sum(c for sid, c in self.d["tests"].get(dkey(d), {}).items() if sid not in known)

    # ---- manual corrections
    def remove_time(self, d, sid, minutes):
        """Takes up to `minutes` away from one subject's timer / manual entries of a day (newest entries first).
        Returns the seconds actually removed."""
        want = int(minutes * 60)
        left = want
        k = dkey(d)
        for e in sorted((e for e in self.d["entries"] if e["date"] == k and e.get("subject") == sid),
                        key=lambda e: e.get("t", 0), reverse=True):
            if left <= 0:
                break
            cut = min(left, int(e["sec"]))
            e["sec"] = int(e["sec"]) - cut
            left -= cut
        self.d["entries"] = [e for e in self.d["entries"] if int(e["sec"]) > 0]
        if left != want:
            self._gen += 1
            self.save()
        return want - left

    # ---- exams
    def exams(self):
        return sorted(self.d["exams"], key=lambda e: (e["date"], e.get("time", "")))

    def add_exam(self, name, d, time_s=""):
        e = {"id": uid(), "name": name.strip()[:40], "date": dkey(d), "time": time_s, "notified": ""}
        self.d["exams"].append(e)
        self.save()
        return e

    def update_exam(self, eid, name=None, d=None, time_s=None):
        for e in self.d["exams"]:
            if e["id"] == eid:
                if name is not None and name.strip():
                    e["name"] = name.strip()[:40]
                if d is not None:
                    if dkey(d) != e["date"]:
                        e["notified"] = ""
                    e["date"] = dkey(d)
                if time_s is not None:
                    e["time"] = time_s
        self.save()

    def remove_exam(self, eid):
        self.d["exams"] = [e for e in self.d["exams"] if e["id"] != eid]
        self.save()

    def next_exam(self, today=None):
        """(exam, days_left) of the nearest exam that is today or later, or (None, None)."""
        today = today or date.today()
        for e in self.exams():
            try:
                dd = (date.fromisoformat(e["date"]) - today).days
            except ValueError:
                continue
            if dd >= 0:
                return e, dd
        return None, None

    def exam_on(self, d):
        return [e for e in self.d["exams"] if e["date"] == dkey(d)]

    # ---- exam results: percent and taraz per subject, total taraz and rank
    PCT_RANGE, TARAZ_MAX, RANK_MAX = (-33.4, 100.0), 20000, 5_000_000

    def set_exam_result(self, eid, taraz=None, rank=None, subjects=(), note=""):
        """Stores what you got in an exam. subjects: [{"sid", "pct", "taraz"}]; empty values are dropped. Returns False when
        nothing usable was given (the result is removed then)."""
        e = next((x for x in self.d["exams"] if x["id"] == eid), None)
        if not e:
            return False
        rows = []
        for r in subjects:
            pct = r.get("pct")
            tz = r.get("taraz")
            pct = None if pct is None else max(self.PCT_RANGE[0], min(self.PCT_RANGE[1], float(pct)))
            tz = None if tz is None else max(0, min(self.TARAZ_MAX, int(round(float(tz)))))
            if pct is None and tz is None:
                continue
            sub = self.subject(r.get("sid")) if r.get("sid") else None
            rows.append({"sid": r.get("sid") or "", "name": (sub["name"] if sub else str(r.get("name") or "")).strip(),
                         "pct": None if pct is None else round(pct, 2), "taraz": tz})
        taraz = None if taraz is None else max(0, min(self.TARAZ_MAX, int(round(float(taraz)))))
        rank = None if rank is None else max(1, min(self.RANK_MAX, int(round(float(rank)))))
        if taraz is None and rank is None and not rows:
            e.pop("result", None)
            self.save()
            return False
        e["result"] = {"taraz": taraz, "rank": rank, "subjects": rows, "note": str(note or "").strip()[:200]}
        self.save()
        return True

    def clear_exam_result(self, eid):
        for e in self.d["exams"]:
            if e["id"] == eid:
                e.pop("result", None)
        self.save()

    def exams_with_results(self, upto=None):
        """Exams that have a result, oldest first (optionally only up to a date)."""
        out = [e for e in self.exams() if e.get("result")]
        if upto is not None:
            out = [e for e in out if e["date"] <= dkey(upto)]
        return out

    def subject_key(self, row):
        """Series key of a result row: the subject id while it exists, otherwise the saved name."""
        sid = row.get("sid")
        if sid and self.subject(sid):
            return sid
        return "n:" + str(row.get("name", "")).strip().casefold()

    def exam_progress(self, upto=None):
        """Data for the progress charts.
        {"exams": [{id,name,date,taraz,rank,pct_avg,note}], "subjects": [{key,name,color,points:[(i,pct,taraz)]}]}"""
        ex = self.exams_with_results(upto)
        subj = {}
        out = []
        for i, e in enumerate(ex):
            r = e["result"]
            pcts = [x["pct"] for x in r.get("subjects", []) if x.get("pct") is not None]
            out.append({"id": e["id"], "name": e["name"], "date": e["date"], "taraz": r.get("taraz"), "rank": r.get("rank"),
                        "pct_avg": (sum(pcts) / len(pcts)) if pcts else None, "note": r.get("note", "")})
            for row in r.get("subjects", []):
                key = self.subject_key(row)
                s = self.subject(row.get("sid")) if row.get("sid") else None
                rec = subj.setdefault(key, {"key": key, "name": s["name"] if s else row.get("name") or "?",
                                            "color": (s or {}).get("color", "#8A8F9C"), "points": []})
                rec["points"].append((i, row.get("pct"), row.get("taraz")))
        return {"exams": out, "subjects": sorted(subj.values(), key=lambda r: r["name"])}

    def day_sec(self, d, include_running=True, now=None, include_sessions=True):
        """Study time for a day. Focus sessions (Start on Overview) are left out when include_sessions is False."""
        tot = self.day_entries_sec(d) + (self.day_sessions_sec(d) if include_sessions else 0)
        a = self.d["active"]
        if include_running and a and dkey(d) == date.today().isoformat():
            tot += int(self.elapsed(now))
        return tot

    def subject_day_sec(self, d, sid, now=None):
        """Study-timer time of one subject on a day (timer + manual entries) - the same thing the Study Timer tab's
        day total counts. Focus sessions (Start on the Overview) are counted separately, as everywhere in this tab."""
        tot = self.day_entries_sec(d, sid)
        a = self.d["active"]
        if a and a["subject"] == sid and dkey(d) == date.today().isoformat():
            tot += int(self.elapsed(now))
        return tot

    def range_secs(self, d0, d1):
        out, d = [], d0
        while d <= d1:
            out.append(self.day_sec(d, True))
            d += timedelta(days=1)
        return out

    # ---- tests
    def set_tests(self, d, sid, count):
        day = self.d["tests"].setdefault(dkey(d), {})
        if count <= 0:
            day.pop(sid, None)
        else:
            day[sid] = int(count)
        if not day:
            self.d["tests"].pop(dkey(d), None)
        self.save()

    def day_tests(self, d, sid=None):
        day = self.d["tests"].get(dkey(d), {})
        return day.get(sid, 0) if sid else sum(day.values())

    def year_tests(self, year):
        return sum(sum(v.values()) for k, v in self.d["tests"].items() if k.startswith(f"{year}-"))

    # ---- words learned (language subjects)
    def tracks_words(self, subject):
        """True for a subject that was marked as a language one, or whose name says so (English, زبان, ...)."""
        s = subject if isinstance(subject, dict) else self.subject(subject)
        return bool(s) and (bool(s.get("words")) or bool(_WORDS_NAME.search(str(s.get("name", "")))))

    def word_subjects(self):
        return [s for s in self.subjects() if self.tracks_words(s)]

    def set_words(self, d, sid, count):
        day = self.d["words"].setdefault(dkey(d), {})
        if count <= 0:
            day.pop(sid, None)
        else:
            day[sid] = int(count)
        if not day:
            self.d["words"].pop(dkey(d), None)
        self.save()

    def day_words(self, d, sid=None):
        day = self.d["words"].get(dkey(d), {})
        return day.get(sid, 0) if sid else sum(day.values())

    def year_words(self, year):
        return sum(sum(v.values()) for k, v in self.d["words"].items() if k.startswith(f"{year}-"))

    # ---- to-dos
    def todos(self, d):
        return [t for t in self.d["todos"] if t["date"] == dkey(d)]

    def add_todo(self, d, text):
        t = {"id": uid(), "date": dkey(d), "text": text.strip(), "done": False}
        self.d["todos"].append(t)
        self.save()
        return t

    def toggle_todo(self, tid):
        for t in self.d["todos"]:
            if t["id"] == tid:
                t["done"] = not t["done"]
        self.save()

    def remove_todo(self, tid):
        self.d["todos"] = [t for t in self.d["todos"] if t["id"] != tid]
        self.save()

    # ---- long-range stats
    def month_totals(self, year):
        """[(study_sec, tests)] for 12 months of the given Gregorian year."""
        sec = [0] * 12
        tests = [0] * 12
        for e in self.d["entries"]:
            if e["date"].startswith(f"{year}-"):
                sec[int(e["date"][5:7]) - 1] += e["sec"]
        for r in self.store.history:
            try:
                dt = datetime.fromtimestamp(r["start"])
                if dt.year == year:
                    sec[dt.month - 1] += int(r.get("focus_sec", 0))
            except Exception:
                pass
        for k, v in self.d["tests"].items():
            if k.startswith(f"{year}-"):
                tests[int(k[5:7]) - 1] += sum(v.values())
        return list(zip(sec, tests))

    def _ym(self, datestr, jalali):
        y, m, d = (int(x) for x in datestr.split("-"))
        if jalali:
            jy, jm, _jd = i18n.to_jalali(datetime(y, m, d))
            return jy, jm
        return y, m

    def year_summary(self, year, jalali=False):
        """12 months of (study_sec, tests) for a Gregorian or Jalali year, plus totals and the best day."""
        sec, tests = [0] * 12, [0] * 12
        per_day = {}
        for e in self.d["entries"]:
            per_day[e["date"]] = per_day.get(e["date"], 0) + e["sec"]
        for r in self.store.history:
            try:
                k = datetime.fromtimestamp(r["start"]).date().isoformat()
                per_day[k] = per_day.get(k, 0) + int(r.get("focus_sec", 0))
            except Exception:
                pass
        best = (None, 0)
        for k, v in per_day.items():
            yy, mm = self._ym(k, jalali)
            if yy == year:
                sec[mm - 1] += v
                if v > best[1]:
                    best = (k, v)
        for k, v in self.d["tests"].items():
            yy, mm = self._ym(k, jalali)
            if yy == year:
                tests[mm - 1] += sum(v.values())
        days = sum(1 for k in per_day if self._ym(k, jalali)[0] == year)
        words = sum(sum(v.values()) for k, v in self.d["words"].items() if self._ym(k, jalali)[0] == year)
        return {"months": list(zip(sec, tests)), "sec": sum(sec), "tests": sum(tests), "best": best, "active_days": days,
                "words": words}

    def heat(self, weeks=15, today=None):
        """Matrix [week][weekday Mon..Sun] of study seconds ending with the current week."""
        today = today or date.today()
        start = today - timedelta(days=today.weekday() + 7 * (weeks - 1))
        cols = []
        for w in range(weeks):
            col = []
            for i in range(7):
                d = start + timedelta(days=7 * w + i)
                col.append(self.day_sec(d, True) if d <= today else -1)
            cols.append(col)
        return cols

    def streak(self, min_sec=1800, today=None):
        d = today or date.today()
        if self.day_sec(d) < min_sec:
            d -= timedelta(days=1)
        n = 0
        while self.day_sec(d) >= min_sec:
            n += 1
            d -= timedelta(days=1)
        return n


# ============================================================ play tracking + attempts
_PLAY_CACHE = {}


def play_days(store):
    """play.json is written by the guard; reading + parsing it every second (the Rewards page refreshes that often)
    is wasteful, so it is cached until the file changes."""
    try:
        stt = store.p_play.stat()
        sig = (stt.st_mtime_ns, stt.st_size)
    except OSError:
        return {}
    hit = _PLAY_CACHE.get(str(store.p_play))
    if hit and hit[0] == sig:
        return hit[1]
    data = read_json(store.p_play, {})
    days = data.get("days", {}) if isinstance(data, dict) else {}
    days = days if isinstance(days, dict) else {}
    _PLAY_CACHE[str(store.p_play)] = (sig, days)
    return days


def play_day(store, d):
    return play_days(store).get(dkey(d), {"monitored": 0, "total": 0, "apps": {}})


def attempts(store):
    d = read_json(store.p_attempts, {})
    lst = d.get("list", []) if isinstance(d, dict) else []
    return [a for a in lst if isinstance(a, dict) and isinstance(a.get("t"), (int, float))]


def attempts_report(store, days=7, now=None):
    now = now or time.time()
    since = now - days * 86400
    items = [a for a in attempts(store) if a["t"] >= since]
    per_day, per_hour, per_app = {}, [0] * 24, {}
    for a in items:
        dt = datetime.fromtimestamp(a["t"])
        k = dt.date().isoformat()
        per_day[k] = per_day.get(k, 0) + 1
        per_hour[dt.hour] += 1
        per_app[a.get("name") or a["exe"]] = per_app.get(a.get("name") or a["exe"], 0) + 1
    # weakest 2-hour stretch
    best, best_h = 0, None
    for h in range(24):
        c = per_hour[h] + per_hour[(h + 1) % 24]
        if c > best:
            best, best_h = c, h
    top = sorted(per_app.items(), key=lambda kv: -kv[1])[:5]
    return {"total": len(items), "per_day": per_day, "per_hour": per_hour, "top_apps": top,
            "weak_start": best_h, "weak_count": best}


# ============================================================ focus points
DEFAULT_REWARDS = [
    {"id": "r_movie", "name": "Watch a movie", "kind": "movie", "cost": 30, "minutes": 0},
    {"id": "r_video", "name": "Long YouTube video", "kind": "video", "cost": 15, "minutes": 0},
    {"id": "r_play90", "name": "Play for 1.5 hours", "kind": "game", "cost": 100, "minutes": 90},
    {"id": "r_play120", "name": "Play for 2 hours", "kind": "game", "cost": 140, "minutes": 120},
]
OLD_GAME_COSTS = {"r_play90": 60, "r_play120": 80}      # earlier defaults, upgraded when the user never changed them


class Points:
    def __init__(self, store):
        self.store = store
        # through the store reader: a damaged points file is restored from the newest backup instead of silently
        # starting again at zero (the backup of points.json existed but was never used)
        d = store._read(store.p_points, dict)
        if not isinstance(d, dict):
            d = {}
        d.setdefault("balance", 0)
        d.setdefault("last_award", None)
        d.setdefault("ledger", [])
        d.setdefault("tickets", [])
        d.setdefault("rewards", [dict(r) for r in DEFAULT_REWARDS])
        new = {r["id"]: r["cost"] for r in DEFAULT_REWARDS}
        for r in d["rewards"]:
            if r.get("id") in OLD_GAME_COSTS and int(r.get("cost", 0)) == OLD_GAME_COSTS[r["id"]]:
                r["cost"] = new[r["id"]]
        self.d = d

    def save(self):
        write_json(self.store.p_points, self.d)

    @property
    def balance(self):
        return int(self.d["balance"])

    def add(self, pts, kind, note="", day=None):
        self.d["balance"] = int(self.d["balance"]) + int(pts)
        self.d["ledger"].append({"t": time.time(), "date": day or date.today().isoformat(), "kind": kind,
                                 "pts": int(pts), "note": note})
        self.d["ledger"] = self.d["ledger"][-500:]

    # ---- daily award
    def clean_streak(self):
        n = 0
        for e in reversed(self.d["ledger"]):
            if e["kind"] == "clean":
                n += 1
            elif e["kind"] in ("played",):
                break
        return n

    def process_days(self, today=None):
        """Award points for every finished day since the last award. Returns [(date, kind, pts)]."""
        s = self.store.settings
        today = today or date.today()
        if not s.get("play_tracking", True):
            return []
        if not self.d["last_award"]:
            self.d["last_award"] = (today - timedelta(days=1)).isoformat()   # start counting from today
            self.save()
            return []
        try:
            last = date.fromisoformat(self.d["last_award"])
        except (TypeError, ValueError):
            last = today - timedelta(days=1)
        out = []
        d = last + timedelta(days=1)
        tol = int(s.get("play_tolerance_min", 5)) * 60
        while d < today:
            rec = play_day(self.store, d)
            if rec["monitored"] < 3600:
                self.d["ledger"].append({"t": time.time(), "date": d.isoformat(), "kind": "unverified", "pts": 0,
                                         "note": "monitoring was off for most of the day"})
                out.append((d, "unverified", 0))
            elif rec["total"] > tol:
                self.d["ledger"].append({"t": time.time(), "date": d.isoformat(), "kind": "played", "pts": 0,
                                         "note": f"{int(rec['total'] // 60)} min played"})
                out.append((d, "played", 0))
            else:
                pts = int(s.get("points_per_day", 5))
                self.add(pts, "clean", "a day without playing", d.isoformat())
                streak = self.clean_streak()
                if streak and streak % 7 == 0:
                    bonus = int(s.get("streak_bonus", 10))
                    self.add(bonus, "bonus", f"{streak} clean days in a row", d.isoformat())
                    pts += bonus
                out.append((d, "clean", pts))
            d += timedelta(days=1)
        # never move backwards: setting the PC clock back and forth must not award the same days twice
        self.d["last_award"] = max(last, today - timedelta(days=1)).isoformat()
        if out:
            self.save()
        return out

    # ---- rewards
    def cost(self, reward, when=None):
        return int(reward["cost"])

    def game_day_ok(self, when=None):
        """Play passes can only be used on Fridays (setting 'game_friday_only', on by default)."""
        when = when or date.today()
        return when.weekday() == 4 or not self.store.settings.get("game_friday_only", True)

    def claim(self, reward_id, when=None):
        r = next((x for x in self.d["rewards"] if x["id"] == reward_id), None)
        if not r:
            return None, "Unknown reward."
        c = self.cost(r, when)
        if self.balance < c:
            return None, "Not enough points."
        self.add(-c, "spend", r["name"])
        t = {"id": uid(), "reward": r["id"], "name": r["name"], "kind": r["kind"], "minutes": r.get("minutes", 0),
             "cost": c, "t": time.time(), "used": False, "used_t": None}
        self.d["tickets"].append(t)
        self.save()
        return t, ""

    def use_ticket(self, tid):
        t = next((x for x in self.d["tickets"] if x["id"] == tid), None)
        if not t or t["used"]:
            return None
        t["used"], t["used_t"] = True, time.time()
        self.save()
        return t

    def unused(self):
        return [t for t in self.d["tickets"] if not t["used"]]


# ---- play pass (written by the UI, honoured by the guard)
def pass_until(store):
    d = read_json(store.p_pass, {}) or {}
    return float(d.get("until", 0) or 0)


def start_pass(store, minutes, now=None):
    now = now or time.time()
    until = max(now, pass_until(store)) + minutes * 60
    write_json(store.p_pass, {"until": until, "minutes": minutes, "started": now})
    return until
