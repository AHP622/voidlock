"""Demo data for screenshots: an anonymous, STRONG student - studies every day for hours, high test counts, exam results that climb to
the top ranks, nearly every focus session completed. Fixed seed, so every run gives the same pictures.
Used by  `VoidLock.exe --home <empty folder> --screenshots <folder>`  (see main.py). Never touches a folder that already has data."""
import random
import uuid
from datetime import date, datetime, timedelta

from . import study as studymod

SUBJECTS = {
    "fa": [("ریاضی", "#8B5CF6"), ("فیزیک", "#00C2FF"), ("شیمی", "#34D399"), ("زیست", "#FBBF24"), ("ادبیات", "#FF5DA2"), ("عربی", "#60A5FA")],
    "en": [("Math", "#8B5CF6"), ("Physics", "#00C2FF"), ("Chemistry", "#34D399"), ("Biology", "#FBBF24"), ("Literature", "#FF5DA2"), ("English", "#60A5FA")],
}
EXAMS = {"fa": "آزمون {n} ماز", "en": "Mock exam {n}"}
FINAL = {"fa": "آزمون جامع ۵", "en": "Final mock exam"}
TASKS = {"fa": ["حل ۴۰ تست ریاضی", "مرور فصل ۳ فیزیک", "خلاصه‌نویسی شیمی", "۳۰ لغت عربی"], "en": ["Solve 40 math tests", "Review physics chapter 3", "Summarise chemistry", "30 vocabulary words"]}
CLASSES = {
    "fa": [("حسابان", 0, "17:00", "معین کرمی"), ("فیزیک", 1, "19:00", "دکتر رضایی"), ("شیمی", 2, "16:30", "آنلاین"), ("زیست", 3, "18:00", "آنلاین"), ("ادبیات", 5, "09:00", "آقای احمدی")],
    "en": [("Calculus", 0, "17:00", "Mr. Karimi"), ("Physics", 1, "19:00", "Dr. Rezaei"), ("Chemistry", 2, "16:30", "Online"), ("Biology", 3, "18:00", "Online"), ("Literature", 5, "09:00", "Mr. Ahmadi")],
}


def has_data(store, sl):
    return bool(store.history or sl.d.get("entries") or store.active_locks() or store.classes)


def fill(store, sl, points, lang="fa", seed=11, today=None):
    """Fills an EMPTY program folder. Returns the number of study entries made."""
    today = today or date.today()
    rnd = random.Random(seed)
    lang = "fa" if lang == "fa" else "en"
    sl.d["subjects"] = []
    subs = [sl.add_subject(n, c, words=(i == 5)) for i, (n, c) in enumerate(SUBJECTS[lang])]
    made = 0
    for k in range(44, -1, -1):                      # no day off: a strong student studies every single day
        d = today - timedelta(days=k)
        for s in rnd.sample(subs, rnd.randint(4, 5)):
            sl.add_manual(d, s["id"], rnd.randint(55, 120))
            made += 1
        for s in subs[:3]:
            sl.set_tests(d, s["id"], rnd.randint(30, 75))
        sl.set_words(d, subs[5]["id"], rnd.randint(30, 60))
    # exams: the program's own exam subjects (separate from the study timer's). Taraz climbs 7400 -> ~8300, the country rank
    # falls from about 480 to about 40, the region rank to the single digits, subject percentages stay between 70 and 98.
    es = [sl.add_exam_subject(n, c) for n, c in SUBJECTS[lang][:5]]
    for i, off in enumerate((35, 28, 21, 14, 7)):
        e = sl.add_exam(EXAMS[lang].format(n=i + 1), today - timedelta(days=off))
        sl.set_exam_result(e["id"], taraz=7400 + i * 230 + rnd.randint(0, 60), rank=480 - i * 105 + rnd.randint(0, 25),
                           rank_region=max(1, 24 - i * 5 + rnd.randint(0, 2)),
                           subjects=[{"sid": x["id"], "pct": min(98, 70 + i * 5 + rnd.randint(0, 8)),
                                      "taraz": 7000 + i * 260 + rnd.randint(0, 700)} for x in es],
                           note="")
    sl.add_exam(FINAL[lang], today + timedelta(days=6))
    for t in TASKS[lang]:
        sl.add_todo(today, t)
    # focus sessions
    hist = []
    for k in range(14):
        t0 = datetime.combine(today - timedelta(days=k * 2 + (0 if k else 0)), datetime.min.time()) + timedelta(hours=16 + (k % 3), minutes=(k * 7) % 50)
        if t0 > datetime.now():
            t0 -= timedelta(days=1)
        planned = rnd.choice((50, 60, 90))
        done = rnd.random() > 0.05
        hist.append({"start": t0.timestamp(), "subject": SUBJECTS[lang][k % 4][0], "planned_min": planned,
                     "focus_sec": planned * 60 if done else planned * 60 - rnd.randint(300, 900), "status": "completed" if done else "ended", "blocked_count": rnd.randint(0, 1)})
    store.history = hist
    # weekly classes
    store.classes = [{"id": uuid.uuid4().hex[:8], "name": n, "day": d, "time": t, "minutes": 90, "remind": 15, "enabled": True, "place": p} for n, d, t, p in CLASSES[lang]]
    store.save_classes()
    # points
    for k in range(30, 0, -1):
        points.add(20, "clean", day=(today - timedelta(days=k)).isoformat())
    points.add(60, "bonus", day=today.isoformat())
    store.settings.update({"daily_goal_min": 420, "play_tracking": False, "default_minutes": 50})
    store.save_history()
    store.save_settings()
    store.save_study()
    return made


def quiet_first_run(store, version):
    """No welcome / tips in the pictures."""
    store.settings.update({"intro_done": True, "tips_enabled": False, "intro_version": version,
                           "update_check": False, "update_auto_install": False})   # no network, and never an update in the middle of the pictures


def order_of_tabs():
    from .intro import ORDER
    return list(ORDER)
