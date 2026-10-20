# Changelog

## 1.2.9
Bug-fix release (no data migration; your data and locks are untouched).

**Guard / locks**
* The internet-time lookup no longer runs inside the guard loop. Offline, it froze the guard for up to 15 s (nothing
  was blocked, the heartbeat went stale, and the app/watchdog then started a *second* guard).
* New single-instance lock (`guard.lock`): the UI, the Task Scheduler watchdog and the sign-in entry can no longer
  start duplicate guards. A starting guard waits briefly for the one it replaces.
* "Stop guard" now checks the PID really is a VOIDLOCK guard before terminating it (a recycled PID could be killed).
* Session failsafe measured from the real end time, so a long-paused session is no longer treated as expired.
* Lock length, extending a lock and the "Fridays only" play-pass rule use internet-corrected time (via the guard),
  so changing the PC clock no longer shortens a lock or fakes a Friday.

**Data**
* Atomic writes use a unique temp name and retry: the UI and guard writing the same file at once could raise
  `FileNotFoundError`.
* An empty application list is kept (it was silently replaced by the default list, re-enabling blocks, on restart).
* Import validates every entry; import / restore are refused while a session is running (they could be used to
  empty the block list during a strict session).
* Only the 5 newest `.corrupt-*` quarantine files are kept.

**Calendar / dates**
* New Jalali conversion with the official leap-year rules (the old 4-year formula was a day off from 1407 on).
  Impossible dates (e.g. 30 Esfand in a common year) are rejected; the exam-date picker clamps correctly.
* `study.dkey()` returned a full timestamp when given a `datetime`.

**App**
* While the study stopwatch runs, VOIDLOCK keeps Windows from sleeping because of inactivity (the screen can still
  turn off) - no need to change power settings. If the PC sleeps anyway (lid closed, manual sleep), the stopwatch no
  longer counts the time it was asleep.
* Scheduled sessions are checked by elapsed time (the old `second % 15` test could be skipped by timer jitter).
* Update check repeats every few hours while the app stays open; every redirect hop of a download must stay on
  https + GitHub, download size is capped, partial downloads are removed.
* "Remove administrator guard" keeps the flag until Windows really removed the task (cancelling the prompt left a
  half-removed state and two guards at sign-in).
* Modal dialogs ignore a second click/Esc while fading out (could touch a deleted widget).
* Lock-hours "next change" is computed from window boundaries instead of 11 520 minute checks on every refresh.
* History CSV export tolerates old records with missing fields.
* README: shortcuts are Ctrl+1..9. Added `tests/logic_test.py` (28 tests); UI test no longer uses a hard-coded path.
