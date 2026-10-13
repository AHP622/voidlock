"""VOIDLOCK entry point.
   python main.py            -> desktop app
   python main.py --guard    -> enforcement guard process (started automatically by the app)
   python main.py --recover  -> emergency recovery: clear session and stop the guard
"""
import argparse
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--guard", action="store_true")
    ap.add_argument("--recover", action="store_true")
    ap.add_argument("--home", default=None)
    ap.add_argument("--version", action="store_true")
    ap.add_argument("--after", type=int, default=0)       # wait for this PID to exit (used by restart)
    ap.add_argument("--release-locks", action="store_true")
    args, _ = ap.parse_known_args()

    if args.version:
        from voidlock import __version__
        print(__version__)
        return 0
    if getattr(sys, "frozen", False):
        from voidlock import updater
        updater.cleanup_old()          # remove the previous exe left behind by an update
    if args.guard:
        from voidlock.guard import run_guard
        run_guard(args.home)
        return 0
    if args.release_locks:
        import time
        from voidlock.guard import GuardClient
        from voidlock.store import Store
        store = Store(args.home)
        locks = store.active_locks()
        if not locks:
            print("No active day locks.")
            return 0
        wait = int(store.settings.get("long_cooldown", 600))
        print(f"Releasing {len(locks)} lock(s) in {wait} seconds. Close this window to cancel.")
        for left in range(wait, 0, -1):
            print(f"\r{left:4d}s ", end="", flush=True)
            time.sleep(1)
        GuardClient(store).release_locks([l["exe"] for l in locks])
        print("\nLocks released.")
        return 0
    if args.recover:
        from voidlock.guard import emergency_recover
        from voidlock.store import Store
        emergency_recover(Store(args.home))
        print("VOIDLOCK recovery done: session cleared, guard stopped.")
        return 0

    if args.after:
        import time
        import psutil
        end = time.time() + 10
        while psutil.pid_exists(args.after) and time.time() < end:
            time.sleep(0.2)

    from PySide6.QtCore import QLockFile, QTimer, Qt
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication, QMessageBox

    from voidlock import i18n
    from voidlock.guard import GuardClient
    from voidlock.store import Store
    store = Store(args.home)                     # language must be known before any widget is built
    i18n.set_language(store.settings.get("language", "en"))
    from voidlock.app import MainWindow
    from voidlock.theme import T, font, stylesheet

    import os
    if sys.platform == "win32":  # lets the taskbar show our icon instead of python's
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("VoidLock.StudyFocus.1")
        except Exception:
            pass
    app = QApplication(sys.argv)
    app.setApplicationName("VOIDLOCK")
    from PySide6.QtGui import QIcon
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    for name in ("icon.ico", "icon.png"):
        path = os.path.join(base, "assets", name)
        if os.path.exists(path):
            app.setWindowIcon(QIcon(path))
            break
    app.setStyle("Fusion")
    app.setFont(font(13))
    app.setStyleSheet(stylesheet())
    i18n.install_hooks()
    if i18n.is_fa():
        app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    lock = QLockFile(str(store.home / "ui.lock"))
    lock.setStaleLockTime(5000)
    if not lock.tryLock(100):
        QMessageBox.information(None, "VOIDLOCK", "VOIDLOCK is already running.")
        return 0
    win = MainWindow(store, GuardClient(store))
    win.show()
    if store.notices:
        QTimer.singleShot(900, lambda: [win.toast(n, "info") for n in store.notices])
    code = app.exec()
    lock.unlock()
    return code


if __name__ == "__main__":
    sys.exit(main())
