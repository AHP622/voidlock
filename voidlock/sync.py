"""Device sync (phone <-> laptop). Pure Python, no Qt.

What is synced: the study data (subjects, study entries, tests and words per day, deleted subjects, exams with their results,
exam subjects, to-dos) and the focus-session history. NOT synced: settings, locks, apps, points, the running stopwatch.

The model (the same on every device, so every device ends with the same data):
  * Every record has an id and a time of its last change ("mt", milliseconds). A deleted record leaves a tombstone with the
    time of the deletion. For one id, whichever happened last wins: the newest version, or the deletion.
  * Nothing else is remembered about the other device, so a file that is old, or one that is imported twice, can do no
    harm: its records are older than what is already here and simply lose.
  * The first time two devices meet, all records of both are added together; the old history of the laptop reaches the
    phone and the phone's reaches the laptop (nothing is deleted just because the other side does not have it).
  * Two subjects with the same name but different ids (both devices made a "Math") become one: the smaller id is kept
    and everything that points to the other one is moved over.
How changes are noticed: this device keeps a fingerprint of every record (sync.json). Whenever a package is made or an
import is prepared, records whose fingerprint changed get the current time, and records that vanished get a tombstone.
A restore / import / reset forgets those fingerprints (see Store._forget_sync), so replacing the data is never mistaken
for deleting it. Before anything is applied the caller sees a plan, and a merge that would remove a lot of what is on
this device is flagged. A backup is made before applying.
"""
import copy
import hashlib
import json
import platform
import time
from datetime import date

from .store import clean_history, read_json, uid, write_json

FORMAT = "voidlock-sync"
VERSION = 2
EXT = ".voidsync"
MAX_BYTES = 60 * 1024 * 1024
LIST_KINDS = ("subjects", "entries", "exams", "exam_subjects", "todos", "sessions")
LEAF_KINDS = ("tests", "words")                     # one record per day and subject: id "date|subject_id", value {"n": count}
KINDS = LIST_KINDS + LEAF_KINDS + ("gone",)
LOCAL_ONLY = {"exams": ("notified",)}               # per-device state that must not count as a change
MASS_DELETE_MIN = 10                                # removing this many (and half of what is here) is flagged
TOMB_KEEP_MS = 400 * 86400 * 1000


class SyncError(Exception):
    pass


# ------------------------------------------------------------------ canonical records of this device
def _dumps(x):
    return json.dumps(x, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _digest(v):
    return hashlib.sha1(_dumps(v).encode("utf-8")).hexdigest()[:16]


def _session_id(r):
    return str(r.get("id") or "") or "s" + str(int(float(r.get("start", 0)) * 1000))


def _strip(kind, rec):
    drop = LOCAL_ONLY.get(kind, ())
    return {k: v for k, v in rec.items() if k not in drop} if drop else rec


def _valid(kind, r):
    """A record from a file must have what the app reads from it (a damaged or hostile file must not crash the app)."""
    try:
        if kind in ("subjects", "exam_subjects"):
            return isinstance(r.get("name"), str) and r["name"].strip() != ""
        if kind == "entries":
            int(r["sec"])
            return isinstance(r.get("date"), str) and len(r["date"]) == 10
        if kind == "exams":
            return isinstance(r.get("name"), str) and isinstance(r.get("date"), str) and len(r["date"]) == 10
        if kind == "todos":
            return isinstance(r.get("text"), str)
        if kind == "sessions":
            float(r["start"])
            return True
        if kind in LEAF_KINDS:
            return isinstance(r.get("n"), int) and r["n"] > 0
        return True
    except (KeyError, TypeError, ValueError):
        return False


def _records(store):
    """{kind: {id: record}} of this device, as plain canonical data."""
    st = store.study if isinstance(store.study, dict) else {}
    out = {k: {} for k in KINDS}
    for kind in ("subjects", "entries", "exams", "exam_subjects", "todos"):
        for x in st.get(kind) or []:
            if isinstance(x, dict) and isinstance(x.get("id"), str) and x["id"]:
                out[kind][x["id"]] = _strip(kind, copy.deepcopy(x))
    for r in store.history or []:
        try:
            sid = _session_id(r)
            out["sessions"][sid] = {**copy.deepcopy(r), "id": sid}
        except (TypeError, ValueError, AttributeError):
            continue
    for kind in LEAF_KINDS:
        for day, row in (st.get(kind) or {}).items():
            if isinstance(row, dict) and isinstance(day, str):
                for sid, n in row.items():
                    try:
                        n = int(n)
                    except (TypeError, ValueError):
                        continue
                    if n > 0 and isinstance(sid, str):
                        out[kind][f"{day}|{sid}"] = {"n": n}
    for k, g in (st.get("gone") or {}).items():
        if isinstance(k, str) and isinstance(g, dict):
            out["gone"][k] = copy.deepcopy(g)
    return out


# ------------------------------------------------------------------ noticing changes (fingerprints in sync.json)
def _state_path(home):
    return home / "sync.json"


def load_state(home):
    s = read_json(_state_path(home))
    s = s if isinstance(s, dict) else {}
    s.setdefault("device_id", uid())
    s.setdefault("device_name", platform.node() or "VOIDLOCK")
    for k in ("dg", "mt", "tomb", "peers"):
        if not isinstance(s.get(k), dict):
            s[k] = {}
    return s


def save_state(home, s):
    write_json(_state_path(home), s)


def forget_peers(home):
    """The data was replaced wholesale: what we remembered no longer matches it. Forget the fingerprints and tombstones so the
    difference is not read as deletions (the next sync only adds)."""
    try:
        s = load_state(home)
        s["dg"], s["mt"], s["tomb"] = {}, {}, {}
        save_state(home, s)
    except OSError:
        pass


def device_info(home):
    s = load_state(home)
    return {"id": s["device_id"], "name": s["device_name"],
            "peers": {k: {"name": v.get("name", "?"), "last_sync": v.get("last_sync")} for k, v in s["peers"].items()}}


def observe(store, s, now_ms=None):
    """Compares the data with the fingerprints: changed records get `now`, vanished ones a tombstone. Returns the state of this
    device: {kind: {"recs": {id: {"mt", "v"}}, "tomb": {id: ts}}}."""
    now = int(now_ms if now_ms is not None else time.time() * 1000)
    cur = _records(store)
    dg, mt, tomb = s["dg"], s["mt"], s["tomb"]
    for kind in KINDS:
        for rid, v in cur[kind].items():
            key = f"{kind}|{rid}"
            d = _digest(v)
            if dg.get(key) != d:
                dg[key], mt[key] = d, now
            if key in tomb and mt.get(key, 0) >= tomb[key]:
                del tomb[key]                                  # it is back: newer than its deletion
    for key in list(dg):
        kind, rid = key.split("|", 1)
        if kind in cur and rid not in cur[kind]:
            del dg[key]
            mt.pop(key, None)
            tomb[key] = now                                    # it was here and is gone: a deletion
    for key in [k for k, t in tomb.items() if now - t > TOMB_KEEP_MS]:
        del tomb[key]
    return _state(cur, s)


def _state(cur, s):
    out = {k: {"recs": {}, "tomb": {}} for k in KINDS}
    for kind in KINDS:
        for rid, v in cur[kind].items():
            out[kind]["recs"][rid] = {"mt": s["mt"].get(f"{kind}|{rid}", 0), "v": v}
    for key, ts in s["tomb"].items():
        kind, rid = key.split("|", 1)
        if kind in out and rid not in out[kind]["recs"]:
            out[kind]["tomb"][rid] = ts
    return out


# ------------------------------------------------------------------ same-name subjects become one
def _name_ids(recs):
    out = {}
    for rid, e in recs.items():
        n = str(e["v"].get("name") or "").strip().casefold()
        if n:
            out.setdefault(n, set()).add(rid)
    return out


def _id_map(a, b):
    """{id that loses: id kept} for live subjects of the same name that exist on BOTH sides with different ids. The smallest id
    is kept (the same on every device); if one side holds the name twice, both are moved to it as well."""
    na, nb = _name_ids(a), _name_ids(b)
    m = {}
    for n, ids in na.items():
        other = nb.get(n)
        if other:
            allids = ids | other
            if len(allids) > 1:
                keep = min(allids)
                for i in allids:
                    if i != keep:
                        m[i] = keep
    return m


def _remap(state, subj, exs):
    """Moves every reference to a subject id that lost to the other one (in place)."""
    if not subj and not exs:
        return state
    for kind, mp in (("subjects", subj), ("exam_subjects", exs)):
        if mp:
            state[kind]["recs"] = {mp.get(i, i): {"mt": e["mt"], "v": {**e["v"], "id": mp.get(i, i)}} for i, e in state[kind]["recs"].items()}
            state[kind]["tomb"] = {mp.get(i, i): t for i, t in state[kind]["tomb"].items()}
    if subj:
        for e in state["entries"]["recs"].values():
            if e["v"].get("subject") in subj:
                e["v"]["subject"] = subj[e["v"]["subject"]]
        for kind in LEAF_KINDS:
            def mv(i):
                day, sid = i.split("|", 1)
                return f"{day}|{subj.get(sid, sid)}"
            recs = {}
            for i, e in state[kind]["recs"].items():
                j = mv(i)
                if j not in recs or e["mt"] >= recs[j]["mt"]:
                    recs[j] = e
            state[kind]["recs"] = recs
            state[kind]["tomb"] = {mv(i): t for i, t in state[kind]["tomb"].items()}
        state["gone"]["recs"] = {subj.get(i, i): e for i, e in state["gone"]["recs"].items()}
        state["gone"]["tomb"] = {subj.get(i, i): t for i, t in state["gone"]["tomb"].items()}
    if exs:
        for e in state["exams"]["recs"].values():
            for row in (e["v"].get("result") or {}).get("subjects", []):
                if row.get("sid") in exs:
                    row["sid"] = exs[row["sid"]]
    return state


# ------------------------------------------------------------------ the merge: newest event per id wins
def _winner(l, lt, r, rt):
    """Candidates: a record version (mt) or a deletion (ts). The latest wins; on a tie the record is kept, then the version that
    sorts higher (the same answer on every device). Returns ("rec", entry) or ("tomb", ts) or None."""
    ev = []
    for e in (l, r):
        if e is not None:
            ev.append((e["mt"], 1, _dumps(e["v"]), "rec", e))
    for t in (lt, rt):
        if t is not None:
            ev.append((t, 0, "", "tomb", t))
    if not ev:
        return None
    w = max(ev, key=lambda x: (x[0], x[1], x[2]))
    return w[3], w[4]


def merge(local, remote):
    """local / remote: states ({kind: {"recs", "tomb"}}). Returns (merged, remap, conflicts)."""
    local, remote = copy.deepcopy(local), copy.deepcopy(remote)
    sm = _id_map(local["subjects"]["recs"], remote["subjects"]["recs"])
    em = _id_map(local["exam_subjects"]["recs"], remote["exam_subjects"]["recs"])
    _remap(local, sm, em)
    _remap(remote, sm, em)
    merged, conflicts = {}, 0
    for kind in KINDS:
        L, R = local[kind], remote[kind]
        out = {"recs": {}, "tomb": {}}
        for rid in set(L["recs"]) | set(R["recs"]) | set(L["tomb"]) | set(R["tomb"]):
            lr, rr = L["recs"].get(rid), R["recs"].get(rid)
            if lr is not None and rr is not None and lr["v"] != rr["v"]:
                conflicts += 1
            w = _winner(lr, L["tomb"].get(rid), rr, R["tomb"].get(rid))
            if w is None:
                continue
            if w[0] == "rec":
                out["recs"][rid] = {"mt": w[1]["mt"], "v": copy.deepcopy(w[1]["v"])}
            else:
                out["tomb"][rid] = w[1]
        merged[kind] = out
    return merged, {**sm, **em}, conflicts


def stats(local, merged):
    """What the merge changes on THIS device: {kind: {"added", "updated", "removed"}} (local already in the merged id space)."""
    out = {}
    for kind in KINDS:
        a, b = local[kind]["recs"], merged[kind]["recs"]
        out[kind] = {"added": sum(1 for k in b if k not in a), "removed": sum(1 for k in a if k not in b),
                     "updated": sum(1 for k in b if k in a and a[k]["v"] != b[k]["v"])}
    return out


def warnings(local, st):
    """Kinds where the merge would remove a lot of what is on this device (ask the person first)."""
    out = []
    for kind in LIST_KINDS:
        n, rm = len(local[kind]["recs"]), st[kind]["removed"]
        if rm >= MASS_DELETE_MIN and rm * 2 >= n:
            out.append(kind)
    return out


# ------------------------------------------------------------------ packages (the file / the network message)
def _pack(state):
    return {kind: {"recs": [{"id": rid, "mt": e["mt"], "v": e["v"]} for rid, e in sorted(state[kind]["recs"].items())],
                   "tomb": dict(sorted(state[kind]["tomb"].items()))} for kind in KINDS}


def make_package(store, home=None):
    """The package for another device (what this device has, and what it has deleted)."""
    home = home or store.home
    s = load_state(home)
    state = observe(store, s)
    save_state(home, s)
    return {"format": FORMAT, "version": VERSION, "device": {"id": s["device_id"], "name": s["device_name"]},
            "created": int(time.time()), "data": _pack(state)}


def _clean_state(data):
    if not isinstance(data, dict):
        raise SyncError("The file has no data.")
    out = {k: {"recs": {}, "tomb": {}} for k in KINDS}
    for kind in KINDS:
        part = data.get(kind)
        if not isinstance(part, dict):
            continue
        items = part.get("recs")
        for x in items if isinstance(items, list) else []:
            if not isinstance(x, dict) or not isinstance(x.get("id"), str) or not x["id"] or not isinstance(x.get("v"), dict):
                continue
            try:
                mt = int(x["mt"])
            except (KeyError, TypeError, ValueError):
                continue
            v = x["v"]
            if kind in LIST_KINDS and kind != "sessions" and v.get("id") != x["id"]:
                continue
            if kind == "sessions":
                cl = clean_history([v])
                if not cl:
                    continue
                v = {**cl[0], "id": x["id"]}
            if kind in LEAF_KINDS and "|" not in x["id"]:
                continue
            if _valid(kind, v):
                out[kind]["recs"][x["id"]] = {"mt": mt, "v": copy.deepcopy(v)}
        tomb = part.get("tomb")
        for rid, ts in (tomb.items() if isinstance(tomb, dict) else []):
            try:
                if isinstance(rid, str) and rid and not (kind in LEAF_KINDS and "|" not in rid):
                    out[kind]["tomb"][rid] = int(ts)
            except (TypeError, ValueError):
                continue
    return out


def parse_package(raw):
    """bytes / str / dict -> a validated package. Raises SyncError with a message that can be shown."""
    try:
        if isinstance(raw, (bytes, bytearray)):
            if len(raw) > MAX_BYTES:
                raise SyncError("The file is too big to be a VOIDLOCK sync file.")
            raw = raw.decode("utf-8")
        pkg = json.loads(raw) if isinstance(raw, str) else raw
    except (ValueError, UnicodeDecodeError):
        raise SyncError("That file is not a VOIDLOCK sync file.")
    if not isinstance(pkg, dict) or pkg.get("format") != FORMAT:
        raise SyncError("That file is not a VOIDLOCK sync file.")
    try:
        ver = int(pkg.get("version", 0))
    except (TypeError, ValueError):
        ver = 0
    if ver != VERSION:
        raise SyncError("This sync file was made by a different version of VOIDLOCK. Update both devices.")
    dev = pkg.get("device")
    if not isinstance(dev, dict) or not isinstance(dev.get("id"), str) or not dev["id"]:
        raise SyncError("That sync file has no device id.")
    return {"device": {"id": dev["id"], "name": str(dev.get("name") or "?")[:60]}, "created": pkg.get("created"),
            "data": _clean_state(pkg.get("data"))}


class Plan:
    """What an import would do. Nothing has changed yet; commit() applies it."""

    def __init__(self, peer, local, remote, merged, remap, conflicts, st, warn):
        self.peer, self.local, self.remote, self.merged = peer, local, remote, merged
        self.remap, self.conflicts, self.stats, self.warn = remap, conflicts, st, warn

    def changes(self):
        return sum(v["added"] + v["updated"] + v["removed"] for v in self.stats.values())

    def removed(self):
        return sum(v["removed"] for k, v in self.stats.items() if k in LIST_KINDS)

    def added(self):
        return sum(v["added"] for k, v in self.stats.items() if k in LIST_KINDS)


def prepare(store, raw, home=None):
    """Reads a package and works out the merge. Raises SyncError when the file cannot be used. Changes no data."""
    home = home or store.home
    pkg = parse_package(raw)
    s = load_state(home)
    if pkg["device"]["id"] == s["device_id"]:
        raise SyncError("This file was made by this same device.")
    local = observe(store, s)
    save_state(home, s)                                # the bookkeeping only (what changed here), not the data
    merged, remap, conflicts = merge(local, pkg["data"])
    mine = _remap(copy.deepcopy(local), {k: v for k, v in remap.items() if k in local["subjects"]["recs"]},
                  {k: v for k, v in remap.items() if k in local["exam_subjects"]["recs"]})
    st = stats(mine, merged)
    return Plan(pkg["device"], mine, pkg["data"], merged, remap, conflicts, st, warnings(mine, st))


def commit(store, plan, home=None, sl=None):
    """Applies a plan: a backup first, then the merged data; then the fingerprints are brought in line with what is now here."""
    home = home or store.home
    store.snapshot("before-sync", force=True)
    apply(store, plan.merged, plan.remap, sl)
    s = load_state(home)
    cur = _records(store)
    s["dg"], s["mt"] = {}, {}
    for kind in KINDS:
        for rid, v in cur[kind].items():
            key = f"{kind}|{rid}"
            s["dg"][key] = _digest(v)
            e = plan.merged[kind]["recs"].get(rid)
            s["mt"][key] = e["mt"] if e else int(time.time() * 1000)
    s["tomb"] = {f"{kind}|{rid}": ts for kind in KINDS for rid, ts in plan.merged[kind]["tomb"].items() if rid not in cur[kind]}
    s["peers"][plan.peer["id"]] = {"name": plan.peer["name"], "last_sync": int(time.time())}
    save_state(home, s)


def _sorted_by(items, *keys):
    return sorted(items, key=lambda r: tuple(str(r.get(k, "")) for k in keys))


def apply(store, merged, remap=None, sl=None):
    st = store.study if isinstance(store.study, dict) else {}
    store.study = st
    recs = {k: {i: e["v"] for i, e in merged[k]["recs"].items()} for k in KINDS}
    old_exams = {e.get("id"): e for e in st.get("exams", []) if isinstance(e, dict)}
    remap = remap or {}
    order = {k: [remap.get(r.get("id"), r.get("id")) for r in st.get(k, []) if isinstance(r, dict)] for k in ("subjects", "todos", "exam_subjects")}

    def keep_order(kind):                             # this device's order first, new ones after it
        first = [recs[kind][i] for i in order[kind] if i in recs[kind]]
        seen = {r["id"] for r in first}
        return copy.deepcopy(first + [r for i, r in recs[kind].items() if i not in seen])

    st["subjects"] = keep_order("subjects")
    st["exam_subjects"] = keep_order("exam_subjects")
    st["todos"] = keep_order("todos")
    st["entries"] = copy.deepcopy(_sorted_by(recs["entries"].values(), "date", "t", "id"))
    today = date.today().isoformat()
    exams = []
    for e in _sorted_by(recs["exams"].values(), "date", "time", "id"):
        e = copy.deepcopy(e)
        old = old_exams.get(e["id"])
        if old is not None and "notified" in old:
            e["notified"] = old["notified"]
        elif str(e.get("date", "")) < today:
            e["notified"] = f"done:{today}"            # an exam of the past must not "remind" about itself on this device
        exams.append(e)
    st["exams"] = exams
    for kind in LEAF_KINDS:
        out = {}
        for key, v in sorted(recs[kind].items()):
            day, sid = key.split("|", 1)
            out.setdefault(day, {})[sid] = int(v["n"])
        st[kind] = out
    st["gone"] = {sid: copy.deepcopy(v) for sid, v in recs["gone"].items()}
    act = st.get("active")
    if isinstance(act, dict) and act.get("subject") in remap:
        act["subject"] = remap[act["subject"]]       # the running stopwatch follows its subject
    store.history = copy.deepcopy(sorted(recs["sessions"].values(), key=lambda r: float(r.get("start", 0))))
    if sl is not None:
        sl._gen += 1
    store.save_study()
    store.save_history()
