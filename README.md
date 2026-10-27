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

## What changed in 1.7.1

- **Release build failed (v1.7.0):** the new report tests print Persian section names, and the Windows CI console (cp1252) cannot encode them, so the test step crashed with `UnicodeEncodeError`
  and no release was built. The tests now switch stdout to UTF-8 (and the workflow sets `PYTHONUTF8=1`). No change to the program itself.

## What changed in 1.7.0

- **Study report for an advisor or parents** (Analytics -> *Export report…*, or Settings -> Data): pick the period (day, week, Jalali month, year, all time or a custom range), the student's name,
  the language (Persian or English) and the format:
  - **HTML** - one self-contained file (CSS and the SVG charts are inside, nothing is loaded from the internet), right-to-left Persian or left-to-right English, tables scroll sideways on a phone,
    clean when printed (`@page` A4, repeated table headers, no page-breaks inside rows). Contains the summary (total, days studied, averages, best day, tests, words, streak, goal days),
    time per subject (deleted subjects keep their names), a chart, the daily table (or a month-by-month table for periods over 62 days) and the focus-session table.
  - **PDF** - drawn with Qt (`report_pdf.py`), A4, page numbers, selectable Persian text, same sections.
  - **CSV** - UTF-8 with BOM so Excel shows Persian correctly; sections: summary, subjects, daily (with one column per subject, Gregorian and Jalali dates) or monthly, sessions, exams.
  "Study time" is the Study Timer's definition (subject timer + manual entries); focus sessions are listed in their own table and are not added to the total.
- The data and both text formats live in `voidlock/report.py` (no Qt, covered by `tests/logic_test.py::test_report`); the dialog is `report_ui.py`.

## What changed in 1.6.1

- **Exams dialog was squashed:** the date row (three steppers, 510 px) was wider than the dialog, so Qt squeezed it and cut the buttons in half; list rows overlapped. The date steppers are
  compact now (390 px), rows have a minimum height, and any dialog whose content is wider than its panel makes the panel wider. New test `tests/modal_layout_test.py` opens every form dialog in
  English and Persian at two window sizes and fails if anything is smaller than its minimum or sticks out (with a control that proves it can detect the problem).

## What changed in 1.6.0

- **Bug: the daily bar lost hours of deleted subjects.** Deleting a subject (and typing it in again) cut its hours off from the day bar, and with every subject deleted the bar
  disappeared. Now: a deleted subject's hours and tests stay in the log under its old name ("... · deleted", and "From deleted subjects" for tests); adding a subject with the
  same name gives the whole history back; and at start the program matches hours of already re-created subjects to the same-name subject using the backups. The bar always adds up to the day total.
- **Exams:** `Exams` button on the Study page - add exam days (Jalali dates in Persian). The nearest one is written on the page ("Next exam: ... in 3 days"), the daily log marks exam days,
  and a reminder pops up the day before and on the day.
- **Subjects:** choose whether a new subject appears in "Tests solved"; **Manage** now has Edit (name, colour, tests, words) as well as Delete; renaming keeps all history.
- **Manual time:** "Remove time" next to "Add time" (takes from the newest entries of that subject on that day, never below zero).
- **Plan for other days:** the plan card has arrows and a Today button, so you can write tomorrow's (or any day's) plan.
- **Help** rewritten: every feature, Persian and English, with troubleshooting.

## What changed in 1.5.1

- **"DLL load failed while importing QtCore"** on another PC: Qt needs the Microsoft Visual C++ runtime, which a clean Windows does not always have. The release
  workflow now packs those DLLs into `VoidLock.exe`. If Qt still cannot load, a plain message explains it (and the link to install the runtime) instead of a stack trace.
  VOIDLOCK needs **64-bit Windows 10 or 11** (Qt 6); on Windows 7 / 8 it cannot run. The installer refuses older Windows.

## What changed in 1.5.0

- **Tray icon:** VOIDLOCK sits next to the clock. Left click opens the window; right click: Open, next class, Start focus session, Pause / Resume, Quit.
  The window's close button hides it in the tray (Settings -> Window & tray -> "Keep running in the tray"; turn it off to make the button quit again). A
  second copy started from a shortcut now just shows the running window instead of saying "already running".
- **No window at start-up:** Windows never opens the window by itself. Optional: "Start in the tray with Windows" (off by default) starts only the tray icon.
- **Installer:** the release now also contains `VoidLock-Setup.exe` (Inno Setup, per-user, no administrator rights): Start menu shortcut, optional
  desktop shortcut, uninstall from Windows Settings (removes the scheduled tasks / sign-in entries and the website block; asks whether to delete your data).
  Build it yourself with `iscc /DAppVersion=1.5.0 installer\voidlock.iss` after building `dist\VoidLock.exe`. `VoidLock.exe` is still published for the auto-updater.
- **Your data:** it lives in `%APPDATA%\VoidLock` and is never touched by updating, installing or uninstalling (unless you answer "yes" when the uninstaller asks).
  New test `test_upgrade_from_old_data` opens data in the old formats with the new version.

## What changed in 1.4.5

- **Daily log, study time by subject:** a compact summary under "Study time this day" - one stacked bar in the subjects' colours and one line of labels
  (longest first, only subjects that have time; Persian shows h:mm). Replaces the small grey text under each subject's name in the tests list, which cluttered it.
  It uses the Study Timer's own definition (timer + manual entries), so it adds up to the day total. (1.4.4 had mixed focus sessions into the subject rows,
  which made them exceed that total - reverted.)

## What changed in 1.4.3 (calmer, smoother interface)

- **Page switches no longer flash.** A page used to appear fully, vanish a moment later and then fade in again card by card (the fade started
  *after* a delay, and the page also slid 14 px while its cards slid separately). Measured: old = full -> empty -> fade over ~650 ms; now = hidden
  from the first frame and a quiet fade of ~300 ms. Cards fade in with a short even cascade (45 ms apart, max 6 steps); nothing slides, so a value changing during
  the animation can no longer make things jitter.
- **Idle animations at 30 fps** (were 60) and 5 fps while the window is in the background or minimised. The character is a little calmer.
- **Smooth mouse-wheel scrolling** (glides instead of jumping a whole notch).
- **Steadier text** while things fade or move (no font hinting, anti-aliased).
- Graphics effects are removed after each fade, so they do not slow down later painting.

## What changed in 1.4.2

- **Stray little window** flashing open and closed when moving between days in the Study tab (introduced by the per-subject time label in 1.4.0:
  a widget was shown before it had a parent, which makes Windows open it as a window of its own). Same pattern fixed in the schedule / class edit
  forms and the custom-app row. New test: `tests/flash_windows_test.py` fails if any top-level window appears while navigating.

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
