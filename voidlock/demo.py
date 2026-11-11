"""Demo data for screenshots: a believable, anonymous month of studying, exams with results, classes and sessions.
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
    for k in range(44, -1, -1):
        d = today - timedelta(days=k)
        if rnd.random() < 0.1 and k:
            continue
        for s in rnd.sample(subs, rnd.randint(2, 4)):
            sl.add_manual(d, s["id"], rnd.randint(25, 110))
            made += 1
        for s in subs[:3]:
            if rnd.random() < 0.8:
                sl.set_tests(d, s["id"], rnd.randint(10, 55))
        if rnd.random() < 0.5:
            sl.set_words(d, subs[5]["id"], rnd.randint(10, 35))
    # exams: the program's own exam subjects (separate from the study timer's)
    es = [sl.add_exam_subject(n, c) for n, c in SUBJECTS[lang][:5]]
    for i, off in enumerate((35, 28, 21, 14, 7)):
        e = sl.add_exam(EXAMS[lang].format(n=i + 1), today - timedelta(days=off))
        sl.set_exam_result(e["id"], taraz=6000 + i * 190 + rnd.randint(0, 80), rank=10400 - i * 1050 + rnd.randint(0, 180),
                           rank_region=520 - i * 52 + rnd.randint(0, 12),
                           subjects=[{"sid": x["id"], "pct": 36 + i * 7 + rnd.randint(0, 22), "taraz": 5100 + i * 230 + rnd.randint(0, 900)} for x in es],
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
        planned = rnd.choice((25, 45, 50, 60))
        done = rnd.random() > 0.18
        hist.append({"start": t0.timestamp(), "subject": SUBJECTS[lang][k % 4][0], "planned_min": planned,
                     "focus_sec": planned * 60 if done else planned * 60 - rnd.randint(300, 900), "status": "completed" if done else "ended", "blocked_count": rnd.randint(0, 5)})
    store.history = hist
    # weekly classes
    store.classes = [{"id": uuid.uuid4().hex[:8], "name": n, "day": d, "time": t, "minutes": 90, "remind": 15, "enabled": True, "place": p} for n, d, t, p in CLASSES[lang]]
    store.save_classes()
    # points
    for k in range(10, 0, -1):
        points.add(20, "clean", day=(today - timedelta(days=k)).isoformat())
    points.add(30, "bonus", day=today.isoformat())
    store.settings.update({"daily_goal_min": 240, "play_tracking": False, "default_minutes": 50})
    store.save_history()
    store.save_settings()
    store.save_study()
    return made


def quiet_first_run(store, version):
    """No welcome / tips in the pictures."""
    store.settings.update({"intro_done": True, "tips_enabled": False, "intro_version": version})


def order_of_tabs():
    from .intro import ORDER
    return list(ORDER)
