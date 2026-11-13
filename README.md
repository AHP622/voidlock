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

## What changed in 1.14.0
* **Weekly classes now sync** between the computer and the phone (`sync.py` / `core.js`): add, edit or delete a class on either device and it
  travels with the next sync. Per-device state ("already reminded today") is never shared. `android/tests/classes_sync_test.py` and the randomized
  `android/tests/interop_test.py` cover it.
* **The phone can manage its own classes**: a new "Classes" mode in the Tasks tab (`android/.../js/views_classes.js`), with a next-class card on
  Today. `android/.../js/classes.js` is a tested port of `voidlock/classes.py` (`android/tests/classes_parity_test.py`, 150 random moments, 0
  differences).
* **The phone's report has the weekly timetable too** (`report.js`'s `scheduleHtml`/CSV), kept in parity with the computer's report.
* **Real notifications on the phone**: class reminders, exam reminders (6 pm the evening before, 7 am on the day) and a new-version notice, via
  Android's AlarmManager/NotificationManager (`Reminders.kt`, `BootReceiver`, `ReminderReceiver`), planned on the web side by `notify.js` and
  switchable per kind in More ▸ Notifications. These alarms could not be run on a real device or emulator here (none is available in this
  environment) — they were checked by having a stub "Android shell" receive the planned reminders in Chromium
  (`android/tests/classes_ui_test.py`) and by reading the Kotlin, not by installing the app.
* **A smoother phone interface** (`motion.js` + new CSS tokens in `app.css`): a sliding highlight behind segmented controls, a gentle fade+slide
  when a tab's content appears, restyled toggle switches, and a Reduce Motion setting (More ▸ Settings) that collapses every duration to near
  zero. Checked in Chromium (`android/tests/motion_test.py`): the thumb tracks the selected option, Reduced Motion is saved and still applied
  after a reload.
* **Windows**: the computer app already had a complete motion-design system from an earlier revision of this project (duration/easing tokens
  routed through a shared `tween()`/`reveal()`, a Settings ▸ Auto/On/Off Reduced-Motion control that also follows the Windows system setting,
  and animated buttons, cards, toggles, dialogs and the sidebar). It was reviewed rather than rebuilt, since rewriting a working system blind
  (no Qt display is available in this environment) risks breaking it for no visible gain. One real gap was fixed: the new Overview's small
  session-ring glow pulsed forever even under Reduced Motion; it now turns itself off with everything else.

## What changed in 1.13.2
* Fix: the donut of the subject share started at the wrong angle (arcs did not join, a dark wedge showed). It is a closed ring now (`dashboard.donut_arcs`, tested). Cards without data show a dashed baseline instead of a block.

## What changed in 1.13.1
* **Dashboard fixes after the first real run:** nothing is wider than the window any more (the dashboard follows the window width: 4 / 2 columns of cards, stacked rows, the goal card hides when narrow; long texts wrap), flat donut segments with thin gaps, correct right-to-left alignment of the painted legend, a header with a greeting card, the day's goal and the start square (same height), brighter chart columns and a stronger window glow.
* **Screenshots of every tab for presentations:** `VoidLock.exe --home "C:\vl-shots" --screenshots "C:\vl-shots\out" --shot-lang fa` fills the (empty!) `--home` folder with anonymous demo data (`voidlock/demo.py`), shows each tab in turn, saves `01_overview.png` ... `10_help.png` at twice the resolution and quits. Options: `--shot-lang fa|en`, `--shot-theme void|ocean|...`, `--shot-size 1500x1000`, `--shot-scale 2`. It refuses a folder that already has data, so your own data is never used.
* Tests: `tests/demo_test.py` (the demo data), `tests/dashboard_test.py`, `tests/qt_stub_smoke.py`.

## What changed in 1.13.0
* **New Overview dashboard** (`voidlock/dashboard.py` for the numbers, `voidlock/dashkit.py` for the painted widgets): the start-session card is a small square in the corner (round play button, countdown ring while a session runs, presets in its arrow); four headline cards with sparklines (study today, streak, focus time, points); a clean daily bar chart with the goal line, 7-day average and exam days; the share of each subject as a donut; recent sessions, what is coming up (exam, class, lock hours) and the protection status; block rules in a compact grid. 7 / 30 / 90 day range. The previous page stays in the code as `ClassicOverviewPage`, used automatically if the dashboard cannot be built.
* **One look for every tab:** the cards are a little glassy (the window's soft glow shows through, the top edge catches light) and the window background has two gentle glows. Light themes keep their solid cards.
* Tests: `tests/dashboard_test.py` (the numbers), `tests/demo_test.py` (the demo data), `tests/qt_stub_smoke.py` (the dashboard's Python runs against stubbed Qt when PySide6 is missing).

## What changed in 1.12.0
* **Phone report = computer report.** The Android report is now a port of the computer's report (`android/.../js/report.js`, `wincharts.js`, texts generated from `report.py`): same sections, numbers, charts, tables and CSV, plus your name on it. `android/tests/report_parity_test.py` builds both from the same data and compares them (HTML text, every chart coordinate, CSV).
* **The phone reconnects by itself.** Previously the phone kept calling the computer's old address; after a DHCP renewal, a restart on another port or a Wi-Fi change, sync failed with "could not connect" until the pairing was deleted and made again. Now the phone looks for the computer by its id (same address on every port, then a scan of its own network) and carries on. A computer that is simply off gives a clear message and keeps the pairing.
* **First-run help** (computer and phone): a welcome with a short tour of the tabs, a small tip the first time each tab is opened, and a **What's new** page after every update (`voidlock/intro.py`, `android/.../js/intro.js`). Replay them from Help (computer) or More (phone).
* The signature **Novum** sits under the version in the sidebar, in the phone's About and in the welcome.
* Exact Jalali calendar on the computer too (it was a day off after 1407); checked against the phone's on 40 000 days.
* Fixes found on the way: the phone's totals no longer add focus sessions (as on the computer), seeds/tests updated.

## What changed in 1.11.0

- **Wi-Fi sync is now encrypted.** Pairing: the 6-digit code only lets a phone ask; both devices do an ECDH (P-256) key exchange and show the same 6-digit confirmation number; you press *Allow* on the computer only if the numbers match (somebody in the middle gets a different number). After that every call is an AES-256-GCM envelope (key from HKDF-SHA256) with a growing counter, so nothing readable travels over the network and a recorded request cannot be replayed. Needs the `cryptography` package (in `requirements.txt`, bundled in the exe). The phone uses the browser's Web Crypto with the same constructions. Older phone apps (protocol 1) cannot connect: update both.
- **Charts run left to right** everywhere (windows app, reports, phone): the oldest day / exam is at the left, the value axis at the left, also in Persian. Persian text and digits are unchanged.
- **Computer addresses while a VPN is on:** the address list puts Wi-Fi / Ethernet first and hides VPN / virtual adapters (their addresses are not reachable from the phone).
- **Phone:** report export (PDF through the Android print dialog, a web page, or CSV for Excel), sync in the background (about every 15 minutes and shortly after leaving the app, only on the same network), the phone's Wi-Fi traffic is bound to the Wi-Fi network so a VPN on the phone does not swallow it, tests and words subjects are separate groups on Today.

## What changed in 1.10.0

- **VOIDLOCK for Android** (`android/`, see `android/README.md`): study timer, subjects with any colour, tests / words, tasks, daily chart, exams with results and region rank, Persian + English, offline. It is a web UI in a small native shell; the same GitHub release carries `VoidLock.exe` and `VoidLock.apk`, and each app updates itself from it.
- **Wi-Fi sync with the phone** (`voidlock/lansync.py`): Settings → *Sync with the phone over Wi-Fi* turns on a small server on the local network (any modem, even a SIM modem, or the phone's hotspot; no internet). *Pair a phone…* shows a 6-digit code; the phone finds this computer, you type the code once, and from then on both stay identical by themselves while the phone app is open: a change on either side reaches the other within seconds. The phone sends its data and receives the merged result in one request. A merge that would delete a lot is refused over Wi-Fi (use a file, where the computer asks first). Plain HTTP inside the home network; the token is random and only its hash is stored here.
- Region rank, own exam subjects and every sync rule from 1.9.0 are the same on the phone; `tests` check that the Python and JavaScript implementations always end with identical data.
- Subjects, to-dos and other lists keep their order when synced. The device id is saved on first use.

## What changed in 1.9.0

- **Sync between devices (step 1: files).** Settings → *Sync between devices*: *Save sync file…* writes a `.voidsync` file, *Import sync file…* merges one from another device. Study data is synced: subjects, study time, tests / words per day, to-dos, exams with results and exam subjects, and the focus-session history. Settings, locks, apps and points are not.
  The first time two devices meet **everything of both is added together** (the old history goes both ways). Two subjects with the same name become one. After that, edits and deletions travel too: for each record the latest change wins, and an old file or the same file twice can never undo anything.
  Before an import you see what will change (new / changed / removed); a backup is made first; a file that would remove a lot of what is here asks for extra care. Restore, import and reset forget what the device knew about others, so replacing the data is never read as deleting it.
  The file format (`voidlock-sync`, version 2) is documented at the top of `voidlock/sync.py`; the Android app will use the same one, and automatic sync over Wi-Fi (QR pairing) is the next step.

## What changed in 1.8.13

- **The colour picker is the app's own.** The colour-wheel button no longer opens Qt's grey system dialog. It opens a sheet in the style of the app (same panel as every other dialog): a saturation / brightness square, a hue bar, a preview of the colour that will really be saved, and a `#RRGGBB` field (type or paste a code, 3 or 6 digits). Black and white are lifted to a visible shade and the sheet tells you when that happens.

## What changed in 1.8.12

- **Any colour for a subject.** Next to the 8 preset colours there is now a colour-wheel button (Study Timer and Exam subject forms). It opens a full colour dialog (spectrum, brightness, #RRGGBB / RGB); the chosen colour appears as its own circle and is kept when you edit the subject. Black and white are lifted to a visible shade, because they would vanish on the dark app or on the white report.
- **One colour per subject everywhere.** The colour of a subject in the Study Timer / Exams tab is the colour in the daily study chart, the subject table and the exam progress charts of the report (HTML and PDF). A new exam subject named like a Study Timer subject starts with that subject's colour.

- **Update download is sturdier.** Only one download can run at a time (a second click or the auto-update no longer fights over the same `.part` file: `WinError 32`), and a file the antivirus still holds for a moment is retried instead of failing at once.

## What changed in 1.8.11

- **Exams have their own subjects.** The result form no longer lists the Study Timer subjects. You add exactly the subjects of your exam (in the result form itself - type a name and press Add - or in the new *Exam subjects* card on the Exams tab, where you can also rename, recolour and delete them).
  Renaming keeps the saved results; a deleted subject keeps its saved results in the charts and reports. Results saved in 1.8.0 are carried over: the subjects they used become your exam subjects automatically.
- **Region rank.** Every result now has *Region rank* next to total taraz and overall rank. It has its own card, its own progress chart (inverted: up is better), a pill on the exam card, a column in the exam table, and it is in the HTML / PDF / CSV report.
- **The daily study chart is cleaner.** One column per day, stacked by your five main subjects (the rest are merged into one grey *Other subjects* slice), the day's hours written above every column, three light gridlines, one dashed daily-goal line with its label, and exam days marked with a soft band and a marker.
  The average line, the 7-day moving average and the full-height exam line were removed (the average is in the summary cards). The same chart is used in HTML and PDF; the monthly view for long periods follows the same style.
- **The exam list is sorted by date** (oldest first) instead of upcoming first and past last.

## What changed in 1.8.0

- **New tab: Exams.** Add your exam days, and after each exam enter the results: percent and taraz of every subject, the total taraz and the overall rank (Persian digits and separators are accepted; leave out what you do not know;
  percent can be negative down to -33.4). The tab shows cards (days to the next exam, latest and best taraz, latest rank, number of exams), a progress chart with four views - total taraz (trend line, best point), overall rank
  (inverted axis: up is always better), taraz per subject and percent per subject - hover a point for details, a table of the latest exam by subject with the change since the previous exam, and the list of all exams.
- **Reports are fuller:** the study chart is stacked by subject with hour gridlines, the daily goal, the average of the study days, a 7-day moving average and exam markers (monthly bars for long periods);
  a weekday pattern chart; **the weekly timetable** (classes with teacher / place, and planned study sessions, with hours per week) so an advisor knows when your classes are held; and **exam results and taraz progress** (summary cards,
  taraz / rank / per-subject charts, an exam table with changes, a subject-by-exam matrix, strongest and weakest subjects, biggest gain and drop). Both sections are in HTML, PDF and CSV and can be switched off in the export window.
  Results are included up to the end of the chosen period (a trend needs the earlier exams too).
- One chart engine (`voidlock/charts.py`): a chart is a small vector scene drawn as inline SVG in the HTML (hover tooltips, right-to-left aware) and with QPainter in the PDF and in the app (`charts_qt.py`), so the three look alike.
  In the PDF every chart carries its own heading in the picture, so a heading is never left alone at the bottom of a page.
- The "Exams" button on the Study page now opens the Exams tab.

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
