# Changelog

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
