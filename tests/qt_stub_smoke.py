"""Smoke test of the new Overview dashboard WITHOUT Qt: PySide6 is replaced by permissive stubs so the Python of dashkit.py / pages_a.py
(construction, refresh in every session state, the chart paint code) really runs and typos / wrong attribute names show up.
It cannot prove that the pictures look right (that needs the real program); skipped when the real PySide6 is installed.
Run:  python tests/qt_stub_smoke.py"""
import sys
import tempfile
import types
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
try:
    import PySide6  # noqa: F401
    print("real PySide6 found: skipped (run tests/features_ui_test.py instead)")
    sys.exit(0)
except ImportError:
    pass

CALLS = []


class _Meta(type):
    def __getattr__(cls, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return _cls(name)

    def __or__(cls, o):
        return cls

    __ror__ = __and__ = __rand__ = __or__


_CACHE = {}


def _cls(name):
    if name not in _CACHE:
        _CACHE[name] = _Meta(name, (_Stub,), {})
    return _CACHE[name]


class _Stub(metaclass=_Meta):
    def __init__(self, *a, **k):
        pass

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        if name in ("width", "w"):
            return lambda *a: 420.0
        if name in ("height", "h"):
            return lambda *a: 230.0
        if name in ("x", "y"):
            return lambda *a: 10.0
        if name in ("count", "length", "size"):
            return lambda *a: 0
        if name in ("isRightToLeft", "isVisible", "isEnabled", "isChecked", "isHidden"):
            return lambda *a: False
        return _Stub()

    def __call__(self, *a, **k):
        return _Stub()

    def __iter__(self):
        return iter(())

    def __bool__(self):
        return True

    def __float__(self):
        return 100.0

    def __int__(self):
        return 100

    def __index__(self):
        return 100

    def _num(self, *_):
        return 100.0
    __add__ = __radd__ = __sub__ = __rsub__ = __mul__ = __rmul__ = __truediv__ = __rtruediv__ = __floordiv__ = _num
    __neg__ = __abs__ = __or__ = __ror__ = __and__ = _num

    def __lt__(self, o):
        return False
    __gt__ = __le__ = __ge__ = __lt__

    def __eq__(self, o):
        return self is o

    def __hash__(self):
        return id(self)


class _Mod(types.ModuleType):
    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return _cls(name)


for m in ("PySide6", "PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets", "PySide6.QtNetwork", "PySide6.QtSvg", "PySide6.QtPrintSupport"):
    sys.modules[m] = _Mod(m)

from voidlock import dashboard as DB, dashkit, i18n, pages_a, store as S, study  # noqa: E402

FAILS = []


def ok(c, n):
    print(("PASS " if c else "FAIL ") + n)
    if not c:
        FAILS.append(n)


class FakeSession:
    def __init__(self):
        self.state, self.planned, self.remaining, self.subject, self.strict, self.active = "idle", 2700, 2700, "", False, False
        self.session_id = "s1"
        self.gstat = {"alive": True, "pid": 123, "killed": 2, "session_id": "s1"}
        self.changed = _Stub()
        self.pause = self.resume = self.dismiss = lambda *a: None

    def clock_text(self):
        return "18:42"

    def protection(self):
        return {"level": "ok", "title": "ARMED", "color": "#34D399", "locked": True, "detail": "All rules are enforced."}


class Ctx:
    def __init__(self):
        self.store = S.Store(Path(tempfile.mkdtemp()))
        self.study = study.StudyLog(self.store)
        self.points = study.Points(self.store)
        self.session = FakeSession()
        self.plan = {"minutes": 45, "subject": "Math", "strict": True}
        self.store.settings["daily_goal_min"] = 240
        for n in ("quick_start_default", "quick_start_preset", "custom_start_flow", "end_flow", "emergency_flow", "restart_guard", "elevate_guard", "goto"):
            setattr(self, n, lambda *a, **k: None)

    def hours_state(self):
        return "Lock hours: Games until 22:00"


def main():
    ctx = Ctx()
    sl = ctx.study
    sl.d["subjects"] = []
    subs = [sl.add_subject(n, c) for n, c in (("Math", "#8B5CF6"), ("Physics", "#00C2FF"), ("Chem", "#34D399"))]
    today = date.today()
    import random
    rnd = random.Random(1)
    for k in range(40, -1, -1):
        for s in rnd.sample(subs, 2):
            sl.add_manual(today - timedelta(days=k), s["id"], rnd.randint(20, 120))
    sl.add_exam("Mock", today + timedelta(days=4))
    ctx.store.history = [{"start": 1.7e9 + k * 86400, "subject": "Math", "focus_sec": 2500, "planned_min": 45, "status": "completed"} for k in range(5)]
    ctx.store.apps = [{"id": "a", "exe": "x.exe", "name": "Game", "category": "Games", "enabled": True, "custom": True, "path": ""}]
    for fa in (False, True):
        i18n.is_fa = (lambda v=fa: v)
        pg = pages_a.OverviewPage(ctx)
        ok(True, f"[{'fa' if fa else 'en'}] the dashboard is built")
        for state, active in (("idle", False), ("running", True), ("paused", True), ("completed", False)):
            ctx.session.state, ctx.session.active = state, active
            ctx.session.remaining = 1500
            pg.refresh(force=True)
            pg.refresh()
            ok(True, f"[{'fa' if fa else 'en'}] refresh in state {state}")
        for d in pg.RANGES:
            pg._set_range(d)
        ok(True, f"[{'fa' if fa else 'en'}] every range works")
        # paint the painted widgets once (all drawing maths runs, against stub painters)
        ch = DB.chart(DB.daily(sl, today, 30, 0), today, 30, 4 * 3600, [today])
        for cls in (dashkit.DailyChart, dashkit.ShareChart):
            cls.isRightToLeft = (lambda self, v=fa: v)                 # the right-to-left drawing path in Persian
        w = dashkit.DailyChart()
        w.set_chart(ch)
        w._grow = 1.0
        w.paintEvent(None)
        sh = dashkit.ShareChart()
        sh.set_data(*DB.share(sl, today, 30))
        sh._paint()
        sp = dashkit.Sparkline()
        sp.set_data([1, 3, 2, 5, 4, 6, 7])
        sp.paintEvent(None)
        for st in ("idle", "running", "paused", "completed"):
            r = dashkit.MiniRing(86)
            r.set_state(st, 0.4, "18:42")
            r.paintEvent(None)
        ok(True, f"[{'fa' if fa else 'en'}] the painted widgets run their drawing code")
    print("\n%d failure(s)" % len(FAILS) if FAILS else "\nALL PASSED")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
