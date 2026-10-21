# VOIDLOCK

Study-focus desktop app (PySide6) with a separate enforcement guard process.

## Run
    python -m pip install -r requirements.txt
    python main.py

## Build a single exe (Windows)
    build.bat            ->  dist\VoidLock.exe   (icon: assets\icon.ico)

## Architecture
| Part | File | Role |
|---|---|---|
| UI state | `voidlock/core.py` | session state machine, honest protection report |
| UI | `voidlock/app.py`, `pages_a.py`, `pages_b.py` | shell, pages |
| Components | `widgets.py`, `viz.py`, `overlays.py`, `icons.py`, `theme.py` | reusable, tokens in `theme.py` |
| Enforcement | `voidlock/guard.py` | separate process: terminates blocked programs |
| Storage | `voidlock/store.py` | JSON in `%APPDATA%\VoidLock` |

The UI never blocks anything itself. It writes `session.json`; the guard process reads it,
terminates blocked programs, and reports what actually happened in `status.json`.
The status shown in the app (ENFORCING / PARTIAL / NOT ENFORCING ...) comes from that report.

## Multi-day locks
Application Control -> lock icon on any app (or "Lock all shown"): the app is closed at all times for N days,
with no session needed, and the guard restarts at Windows sign-in. A lock can be extended but never shortened;
the guard keeps its own copy and corrects the PC clock against internet time. Releasing early needs the phrase
RELEASE + a wait (Settings -> Day-lock release wait), or `VoidLock.exe --release-locks` (same wait).

## Your data is never reset
Data lives in `%APPDATA%\VoidLock` (not in the program folder). New versions only add things; every start writes a
rolling backup (15 kept), damaged files are restored from backup, and Settings has Restore / Export / Import.

## Language
Settings -> Language: English / فارسی (right-to-left, Jalali calendar). Translations: `voidlock/fa_strings.py`.
To add another language, add a catalog like that file and a code in `i18n.LANGS`.

## What changed in 1.4.1

- **Update download:** "The downloaded file does not match its checksum" could appear when the connection was cut or filtered (VPN / proxy)
  - Python's HTTP client does not report a download that ends early. The download is now checked against the release's file size,
  resumed from where it stopped (Range), restarted when it arrives corrupted, and retried up to 4 times. The message now says what
  happened. Nothing is installed without a matching SHA-256, as before.

## What changed in 1.4.0

- **Study log:** every subject now shows its study time for the selected day next to the number of tests (also for past days).
- **Words learned:** language subjects (English, زبان ...; or any subject marked "Count words" when it is added) get a words counter like the tests counter; yearly total in Analytics.
- **Classes:** Schedule -> Add class (name, place, days, time, duration, reminder minutes). The top bar always shows the next class
  ("Next class: Math in 1h 20m" / "Class now"), a card pops up 15 minutes before (configurable per class) and a note when it starts.
  If the window is closed the guard shows the reminder.
- **Schedule tab:** "Today" timeline (classes + sessions, now / in 25m / done / missed), a week summary, add a session or class to
  several days at once, overlap warnings, optional automatic start, sessions are still offered up to 30 minutes late, editing a
  time resets only what changed.
- **Updates:** the repository is fixed (`AHP622/voidlock`); automatic check every 3 hours while open and a notice (once per version).
- **Themes and sounds:** 6 new themes (Midnight, Forest, Sunset, Graphite + light Paper and Mint) with a visual picker; 7 new sounds
  (Chime, Marimba, Zen, Crystal, Pulse, Arcade, Drop).
- **Application Control:** during a session what is blocked can only grow. Apps that were blocked could be switched off mid-session; now the toggle is
  disabled, "Allow all" is refused, and the guard also keeps a session's rules even if the session file is edited. Restore / Import are refused while a session runs.
- **Persian:** the "Female character" row and a few other labels were untranslated.
- **Guard on battery:** the scheduled tasks (watchdog and the administrator guard) were created with the Windows defaults - not started on battery power,
  stopped when unplugged, killed after 72 hours. They are now registered from an XML definition without those limits. The watchdog is refreshed
  automatically; the administrator task asks once (Windows prompt) to be refreshed.

## What changed in 1.3.0 (bug-fix release)

**Data safety**
- A file that was only locked for a moment (Windows sharing violation) was treated as corrupt: it got quarantined and replaced by an older backup. Now only really damaged files are restored.
- Reading `locks.json` / `windows.json` failing for a moment made the UI forget all locks, and the next write dropped the others. Release/extend now never rewrite a file they could not read.
- `points.json` was never restored from its backup (a damaged file silently reset your points to 0). Fixed.
- **Reset everything / import / restore** left the Study log without its data keys, so the Study page and Overview crashed (`KeyError`). The log now repairs itself.
- Imported / hand-edited settings with invalid values (for example `reduce_motion`) crashed the Settings page. Every value is validated on load and on import; broken apps / schedule / presets / history entries are dropped instead of crashing later.
- Writes are fsync'ed, temp files are per-process, leftovers are cleaned up.

**Guard**
- The internet-time check ran inside the enforcement loop: up to 15 s per 10 min with nothing blocked (and a stale heartbeat) when offline. It now runs in a background thread and is anchored to the monotonic clock, so changing the Windows clock afterwards has no effect.
- Closing blocked programs: all processes are terminated first and waited for together (a 30-process browser used to take ~12 s per pass).
- Only one guard can run (file lock), even if the watchdog, sign-in task and UI start one in the same second.
- A damaged JSON file can no longer stop the enforcement loop.
- After an update, a guard still running the old code is swapped once when idle.

**Loopholes closed**
- The day-lock release wait could be lowered in Settings (or by scrolling the mouse wheel over its stepper, or by importing/restoring an older file) while locks existed. It can now only be raised while locks exist.
- Day locks, play passes and the Friday rule use the guard's internet-corrected time, so moving the PC clock no longer gives a longer pass / the wrong weekday.
- Moving the PC clock back and forth could award the same clean days twice.
- An imported settings file could change the update source (remote code on next start). The update source is never imported.
- Updater: redirects must stay on GitHub hosts, size cap, partial files removed.

**Other**
- Mouse wheel over a stepper no longer changes it unless it has focus; steppers clamp their start value.
- Overview / Study / Rewards refreshed every second recomputed everything from all history (and re-read `play.json`): now indexed / cached.
- Deleting a subject with a running timer discarded the time; a due scheduled session could open on top of another dialog; a broken schedule entry blocked all others; added site name was wrong after editing the chip text; hosts file keeps CRLF; `--clean-hosts` output; Task Scheduler calls no longer freeze the window; Jalali / duplicate translation key fixes.
- New tests: `tests/logic_test.py` (no Qt, runs real guard + victim processes) and `tests/regressions_ui_test.py`.

## Features added in 1.2
* **Lock hours** (Schedule page): close whole categories (games, launchers, social, media, sites) on chosen days between two
  times. Add freely; removing needs the RELEASE phrase + wait. Outside the hours you can play - and VOIDLOCK watches it.
* **Focus points + rewards** (Rewards page): every day with no (or very little) play earns points; 7 clean days = bonus.
  Spend them on movies, long videos or a timed **play pass** (1.5 h = 100 points, 2 h = 140) that lifts lock hours (never
  day locks or sessions). The play pass can only be used on **Fridays** (Settings -> Focus points). Days when the guard
  was not watching earn nothing.
* **Study Timer** (Yeolpumta-style): tap a subject to start its stopwatch, daily plan (to-do), tests per subject per day,
  manual time, D-day countdown, daily goal, confetti and a mascot.
* **Websites**: Application Control -> Add website. Blocked through the Windows hosts file, which needs the
  **administrator guard** (Settings; Windows asks once). Without it the status honestly says NEEDS ADMIN.
* **Personal message + soft sound** when a program is closed: your target field and the days left to the exam (default
  10 Tir 1406; change in Settings).
* **Weekly report**: attempts per day and per hour, weakest hours, most-tried games. **Year overview**: hours and tests per
  month (Jalali months in Persian) and a study calendar.
* **Themes**: Void, Candy (light), Ocean. **Languages**: English / Persian.
* Emergency: `VoidLock.exe --clean-hosts` (as administrator) removes the website block immediately.

## Auto-update from GitHub
1. Put the project in a **public** GitHub repo (the `.github/workflows/release.yml` file builds the exe for you).
2. To publish a version: raise `__version__` in `voidlock/__init__.py` (e.g. "1.2.0"), commit, push, then
   `git tag v1.2.0` and `git push origin v1.2.0`. GitHub Actions builds `VoidLock.exe` + `VoidLock.exe.sha256`
   and attaches them to a release. (The workflow refuses a tag that does not match `__version__`.)
3. The source is fixed in the program (`updater.REPO` = `AHP622/voidlock`); it is no longer a setting. VOIDLOCK checks
   when it starts and every 3 hours while it is open, and shows a notice when a new version is out. With "Install
   automatically" on it downloads, verifies the SHA-256, swaps the exe and restarts - only when no session is running.
Only files from github.com are accepted and an update without a matching checksum is refused.
Anyone who can push tags to that repo can ship code to your PC: protect the account with 2FA.

## Survives Task Manager?
Closing the window or ending the UI in Task Manager does NOT stop day locks - the guard is a separate process.
If the guard itself is ended, a Task Scheduler watchdog (VoidLockWatchdog, every minute, no admin needed) starts it
again within about a minute, and it also starts at Windows sign-in. A determined admin can still delete the task.

## Safety / recovery
* Emergency unlock (Overview): type UNLOCK + cooldown (Settings). Always available, even in strict mode.
* `VoidLock.exe --recover` (or `python main.py --recover`) clears the session and stops the guard.
* Create an empty file named `RECOVER` in the data folder: the guard clears the current session.
* System-critical programs (explorer, task manager, cmd, PowerShell ...) are never terminated.
* The guard never enforces longer than 12 hours and exits when idle.

## Keyboard
Ctrl+1..6 pages · Ctrl+K search apps · Ctrl+Enter start/pause/resume · Esc closes dialogs · Tab/Shift+Tab focus.

## Limits (honest)
Enforcement = terminating processes by name every second. It cannot stop a user with admin rights
from killing the guard, and it cannot terminate programs running with higher privileges than the
guard (reported as PARTIAL / "Permission denied" - use "Run guard as administrator").
