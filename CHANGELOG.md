# Changelog

## 1.14.73
* Notes for each day. The plan of every day (Study Timer on the computer, Plan on the phone) has a "Notes for this day" box. The note is saved automatically, syncs between the computer and the phone (a new kind of synced data: an older app simply ignores it and nothing is deleted), and is shown in the HTML report's "Daily plans" panel under the date and above that day's tasks. A day that has only a note is listed too and can be picked. Notes follow the same last-day rule as the plans (never later than today). CSV and PDF reports are unchanged.
* Fixed a rare mix-up of the order of tasks (or subjects) on the phone after a sync: an id made only of digits looks like a number to JavaScript, which lists such items first. New ids always contain a letter, on both the computer and the phone.

## 1.14.72
* The Daily plans in the HTML report (computer and phone) now stop at the last day of the report: the end day you chose, but never later than today, like the rest of the report. Plans of future days are no longer listed as "not done".

## 1.14.71
* Phone: sending a report now lets you choose ANY period. The sheet has quick buttons (today, 7, 14, 30, 90 days, all) that fill two always-visible From / To date fields, and those can be changed to any dates. The format buttons start with the web page (it has the Daily plans button). A period that only has daily plans is no longer called empty. "Send weekly report" stays as the one-tap button.
* Windows sync server: it now binds its port exclusively (SO_EXCLUSIVEADDRUSE). Before, Windows let two programs listen on the same port, so a test (or a second program) could end up talking to the running VOIDLOCK, and the other way round. This is what made `test_lan_sync_server` fail while the program was open.
* Diagnostics: `chrome.log` in the data folder records, once each, the window style bits and whether the maximize button is answered as HTMAXBUTTON and reported by Windows. It is for finding out why the Windows 11 Snap Layouts flyout does not appear.

## 1.14.70
* One-tap weekly report. Phone: a "Send weekly report" button on the Report card shares the last 7 days (HTML, with the Daily plans button) straight to the share sheet. Computer: a "Weekly report" button next to "Export report" saves the last 7 days in Documents\VoidLock reports and shows the file in its folder.
* Windows: the maximize button now shows the Windows 11 Snap Layouts flyout (it answers WM_NCHITTEST with HTMAXBUTTON, and its hover / press / click are forwarded). The frameless window now asks for the minimize / maximize / system-menu hints, so a click on its taskbar icon minimizes it like other programs. The maximize icon follows the real window state.
* Fixed buttons (window controls, the buttons everywhere, the sidebar tabs) staying lit after the mouse moved quickly over them: one shared hover logic cancels stale animations, lets only one widget look hovered and releases a widget whose pointer is gone.
* The report dialogs no longer mention the removed focus-sessions table; they mention the daily plans.

## 1.14.69
* HTML reports (computer and phone) have a "Daily plans" button. It opens the student's daily to-do lists for the report period, each task marked done or not done with a done/total count and percentage. A one-day report shows that day; a longer period has a day picker with "All days". CSV and PDF reports are unchanged.
* Reports (Windows and Android; HTML, CSV and PDF) no longer contain the "Focus sessions" table. The summary tiles with the number and time of focus sessions stay.

## 1.14.68
* Settings > Updates shows a progress bar and the percentage (with MB) while an update downloads; the bar is full when the file is ready.
* A downloaded update is no longer installed silently. VOIDLOCK asks "Install now" or "Later"; "Later" asks again every 6 hours (a notice when the window is hidden or not in front, a dialog when you are looking at it, never during a session).
* "Install automatically" is now "Download automatically": the file is downloaded and SHA-256 verified in the background, installing always needs your answer.
* A finished download is kept and re-checked after a restart instead of being downloaded again; a failed automatic download is retried up to 3 times (every 30 min).

## 1.14.67
* Fixed sidebar tabs staying highlighted after the mouse moved quickly over them: a new hover animation now cancels the previous one, only one tab can look hovered, and a short guard releases a tab whose `leaveEvent` was skipped.
* Reduced the gap between the VOIDLOCK logo and the first tab.
* The sidebar collapse/expand arrow now follows the language: in Persian the sidebar is on the right, so the arrow points right to collapse and left to expand.

## 1.14.66
* Fixed Persian Settings descriptions and Help text rendering left-aligned: the window is already right-to-left, and an explicit `AlignRight` is mirrored by Qt in RTL, so it ended up on the left. Labels now use the default (direction-aware) alignment, and the Help search box no longer overrides it.

## 1.14.65
* Restored the existing Settings and Help layout alignment while keeping Persian descriptions right-aligned.

## 1.14.64
* Fixed startup failure in the Help page caused by a missing Qt import.
* Windows fallback downloads now report live percentage progress while curl is downloading.

## 1.14.63
* Windows sidebar can now collapse to icon-only navigation, expand manually, or follow the window width automatically; the version and Novum signature remain visible.
* Fixed Persian right-to-left alignment in Settings descriptions and Help content.

## 1.14.62
* Android launcher icons now follow the selected app palette (Ocean, Paper, Dark or Midnight), including Android themed monochrome icons.
* Changed the untouched daily study goal from 2 hours to 10 hours (600 minutes); old 120-minute defaults migrate once, and other saved goals are preserved. Clarified the units in Settings.
* Fixed the Android Exams add button jumping during page transitions by placing it outside the animated scroll view.
* Windows updater now falls back to the Windows curl TLS stack when Python's TLS connection to GitHub's asset CDN is reset; the final host, file size and SHA-256 are still checked before install.

## 1.14.61
* Redesigned the Android interface with a calmer study-focused layout, clearer timer hierarchy, simpler cards and navigation, and coordinated light and dark themes.
* Updated Android system bars to match the new default light palette.

## 1.14.6
* Fixed: study calendar (`Heatmap`, `voidlock/mascot.py`): in right-to-left layout the hit-test mirrored the column inside the grid's own width,
  but the grid is drawn from the widget's right edge. In a card wider than the grid the highlighted day and its tooltip were hundreds of
  pixels away from the mouse. The column is now counted from the same edge the cells are drawn from. `tests/heatmap_test.py` covers LTR/RTL,
  the empty space beside the grid and days that do not exist.

## 1.14.5 (Android)
* Fixed: switching tabs felt like the whole page reloaded. Causes found in `app.js` / `app.css`: (1) `App.render()` rebuilt the bottom bar and the top title on every call; (2) the entrance animation (`#view.v-in` plus `cardIn` on every card) replayed on every re-render - a tab switch, but also a "+" tap, a subject chip, a range switch, a sync result; (3) `#view` had `scroll-behavior:smooth`, so the scroll position restored after each rebuild visibly scrolled back from the top; (4) coming back to the app always re-read the database and redrew the screen even when nothing had changed; (5) Back always jumped to Today; (6) the Today ring was redrawn as SVG every second, even with no timer running.
* Now: the shell (bottom bar, title) is built once and only updated; only a real tab switch plays the entrance animation; each tab remembers its scroll position; Back walks the tab history; returning to the app re-renders only if the stored data really changed; the ring is redrawn only when its value changes; `App.boot` cannot run twice. The timer is unchanged: it was already computed from the saved start time, so it never restarted on navigation, and it still is.
* New look "Deep Blue Cinematic" (design layer `css/cinema.css`, components in `js/art.js`, bundled Vazirmatn + Space Grotesk fonts): orbital focus timer on the dashboard (goal ring, 60 ticks that light up during a session, orbiting seconds dot), layered atmosphere, glass cards with lit edges, redesigned Tasks and Exams, illustrated empty states, floating glass bottom bar. Ambient light is static and effects are limited to what kept frame rate close to 1.14.4 in the software-rendered test. The Void, Midnight and Light themes keep their colours and get the same shapes. Windows app: untouched.

## 1.14.4
* Fixed: `--screenshots` saved nothing. `QWidget.render(painter)` needs a target offset in PySide6, so every picture raised a TypeError inside a
  timer callback - which was invisible in the windowed exe and left the program running without ever quitting. The logic now lives in
  `voidlock/shots.py`: one tab at a time (show, wait until it is really the visible page, paint, save, verify the file, only then the
  next tab), every failure is printed and written to `screenshots.log`, a watchdog ends a stuck run, the window is closed properly and
  the exit code is 0 (all saved) or 1 (something failed). The demo data is now a strong student (studies every day, high taraz and
  ranks) and the same every run; update checks are off in screenshot mode.

## 1.14.3
* Fixed: updating could fail with "Could not read the checksum: ... WinError 10054" because the small `.sha256` file was fetched once with no
  retry. `updater.check()` now reads the SHA-256 from the release asset's `digest` field (GitHub provides it) so no extra download is needed;
  when it is missing the `.sha256` file is fetched with up to 5 tries. The `.sha256` asset is optional if the digest is present.

## 1.14.2
* Fixed a real, confirmed bug: several widgets (`label()`, `Pill`, `Chip`, `IconTile`, `EmptyState`, `Modal`) used `color=T.something` as a
  Python default *parameter* value. Default parameter values are evaluated once, when the function is defined (at import time, before any
  theme is applied) - not each time the function runs - so every caller that left the colour out got permanently stuck with whatever the
  Void theme's colour happened to be, regardless of the theme actually chosen. In dark themes this mostly went unnoticed; in light themes
  (Candy, Paper, Mint) it meant text in the Void theme's near-white colour on a near-white background. Fixed by resolving the theme colour
  inside the function body instead of in the signature.
* Fixed: `Heatmap.mouseMoveEvent` (the study calendar) computed the hovered cell's column with a plain left-to-right formula while the cells
  are drawn mirrored in a right-to-left (Persian) layout - the tooltip for the cell under the mouse was actually the tooltip for a different,
  mirrored cell. Mirrored the hit-test to match the drawing.
* The Overview's daily chart no longer mirrors its time axis for Persian; it always runs oldest (left) to newest (right).
* The Overview's date range can now be set to "All time", and the period's daily average is shown next to the range button.
* Investigated the window-resize video: the native Win32 edge-resize hit-testing and the background painter both look correct by reading
  (the root widget always fills its full current rect first), but this could not be reproduced or confirmed without a live Windows session -
  see the reply for what to check.

## 1.14.1
* Fixed: with the app language set to English, clicking the Study Timer or Settings tab did nothing (`i18n.jalali_str()` referenced an
  undefined `EN_JMONTHS`, raised `NameError` on every refresh of those two tabs, which silently aborted the tab switch before it happened).
  The same function is also used by the lock-screen message and the exam-date field, so this could have surfaced elsewhere in English too.
  Regression test: `tests/logic_test.py::test_jalali_str_works_in_both_languages`.

## 1.14.0
* Weekly classes sync between computer and phone; the phone can add/edit/delete its own classes; the phone's report includes the timetable.
* Real Android notifications for class reminders, exam reminders and new-version notices (not run on a real device/emulator here).
* Smoother phone UI: sliding segmented-control highlight, tab fade-in, nicer switches, a Reduce Motion setting.
* Windows motion system reviewed (already complete from an earlier revision); fixed one Reduced-Motion gap in the new Overview's session ring.

## 1.13.2
* Fix: the subject donut started at the wrong angle (the arcs did not join and left a dark gap). It is a closed ring starting at 12 o'clock now, with a hairline between the colours; `dashboard.donut_arcs` is tested.
* The tiny chart of a card without data is a faint dashed line, not a coloured block.

## 1.13.1
* Dashboard fixes after the first real run: nothing is wider than the window any more (cards wrap and re-flow with the width), donut segments are flat with thin gaps, right-to-left alignment of the painted legend, a header with a greeting card, the day's goal and the start square of the same height, brighter columns and a stronger glow.
* `--screenshots` tool and demo data for presentation pictures (see README).
* The phone app carries the same version number (no other changes).

## 1.13.0
* New Overview dashboard (small start-session square, headline cards, daily bar chart, subject donut, recent sessions, coming up, protection, block rules) with a 7 / 30 / 90 day range.
* Glass look for the cards of every tab and soft glows behind the window (dark themes).
* Help text for the Overview updated (English and Persian).
## 1.12.0
* Android report identical to the computer's report (sections, charts, tables, CSV), with a name field.
* Android sync finds the computer again by itself after its address or port changed.
* Welcome + tour, a tip for each tab on first visit, and a What's new page after every update (computer and phone).
* Signature Novum in the sidebar, About and welcome.
* Exact Jalali calendar on the computer.
