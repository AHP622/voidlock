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

## Auto-update from GitHub
1. Put the project in a **public** GitHub repo (the `.github/workflows/release.yml` file builds the exe for you).
2. To publish a version: raise `__version__` in `voidlock/__init__.py` (e.g. "1.2.0"), commit, push, then
   `git tag v1.2.0` and `git push origin v1.2.0`. GitHub Actions builds `VoidLock.exe` + `VoidLock.exe.sha256`
   and attaches them to a release. (The workflow refuses a tag that does not match `__version__`.)
3. In the app: Settings -> Updates -> enter `owner/repo`. It checks on start; with "Install automatically" on it
   downloads, verifies the SHA-256, swaps the exe and restarts - only when no session is running.
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
