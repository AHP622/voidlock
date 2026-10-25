"""VOIDLOCK entry point.
   python main.py            -> desktop app
   python main.py --guard    -> enforcement guard process (started automatically by the app)
   python main.py --recover  -> emergency recovery: clear session and stop the guard
"""
import argparse
import sys


def _startup_failure(err):
    """Qt could not be loaded (usually: the Microsoft Visual C++ runtime is missing, or Windows is too old / 32-bit).
    No Qt here, so the message is a plain Windows box instead of a stack trace."""
    text = (f"VOIDLOCK could not start: the Qt libraries failed to load.\n({err})\n\n"
            "Most likely the Microsoft Visual C++ Redistributable is missing on this PC. Install it from\n"
            "https://aka.ms/vs/17/release/vc_redist.x64.exe\nand start VOIDLOCK again. "
            "VOIDLOCK needs 64-bit Windows 10 or 11.\n\n"
            "VOIDLOCK اجرا نشد: کتابخانه‌های Qt بارگذاری نشدند.\n"
            "به احتمال زیاد «Microsoft Visual C++ Redistributable» روی این کامپیوتر نصب نیست. از آدرس بالا نصبش کنید و دوباره "
            "اجرا کنید. VOIDLOCK ویندوز ۱۰ یا ۱۱ ۶۴ بیتی لازم دارد.")
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, text, "VOIDLOCK", 0x10)
    except Exception:
        print(text, file=sys.stderr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--guard", action="store_true")
    ap.add_argument("--recover", action="store_true")
    ap.add_argument("--home", default=None)
    ap.add_argument("--version", action="store_true")
    ap.add_argument("--after", type=int, default=0)       # wait for this PID to exit (used by restart)
    ap.add_argument("--release-locks", action="store_true")
    ap.add_argument("--install-admin-guard", action="store_true")
    ap.add_argument("--remove-admin-guard", action="store_true")
    ap.add_argument("--clean-hosts", action="store_true")
    ap.add_argument("--tray", action="store_true")           # start hidden in the tray (login autostart option)
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
    if args.install_admin_guard or args.remove_admin_guard or args.clean_hosts:
        from voidlock.guard import admin_guard_install, admin_guard_remove
        from voidlock.hosts import write_hosts
        from voidlock.store import Store
        store = Store(args.home)
        if args.clean_hosts:
            ok, msg = write_hosts([])
            print(("Website block removed (" + msg + ")") if ok else ("Could not clean the hosts file: " + msg))
        elif args.install_admin_guard:
            ok, msg = admin_guard_install(store)
            print("Administrator guard installed." if ok else f"Could not install the administrator guard: {msg}")
        else:
            print("Administrator guard removed." if admin_guard_remove(store) else "Could not remove the administrator guard.")
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

    try:
        from PySide6.QtCore import QLockFile, QTimer, Qt
        from PySide6.QtGui import QFont
        from PySide6.QtWidgets import QApplication, QMessageBox
    except ImportError as e:                      # "DLL load failed while importing QtCore"
        _startup_failure(e)
        return 1

    from voidlock import i18n
    from voidlock.guard import GuardClient
    from voidlock.store import Store
    store = Store(args.home)                     # language must be known before any widget is built
    i18n.set_language(store.settings.get("language", "en"))
    from voidlock.app import MainWindow
    from voidlock.theme import T, apply_theme, font, stylesheet
    apply_theme(store.settings.get("theme", "void"))

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
    # Only one copy runs. Starting a second one (a shortcut, the installer's "Launch") asks the running copy - which may be
    # hidden in the tray - to show its window, instead of complaining.
    import hashlib
    from PySide6.QtNetwork import QLocalServer, QLocalSocket
    pipe = "voidlock-" + hashlib.sha1(str(store.home).encode("utf-8")).hexdigest()[:12]
    probe = QLocalSocket()
    probe.connectToServer(pipe)
    if probe.waitForConnected(400):
        probe.write(b"show")
        probe.waitForBytesWritten(400)
        probe.disconnectFromServer()
        return 0
    lock = QLockFile(str(store.home / "ui.lock"))
    lock.setStaleLockTime(5000)
    if not lock.tryLock(100):
        QMessageBox.information(None, "VOIDLOCK", "VOIDLOCK is already running.")
        return 0
    app.setQuitOnLastWindowClosed(False)         # a window hidden in the tray must not end the program
    win = MainWindow(store, GuardClient(store))
    server = QLocalServer()
    QLocalServer.removeServer(pipe)
    server.listen(pipe)

    def _client():
        sock = server.nextPendingConnection()
        if sock:
            sock.waitForReadyRead(200)
            win.bring_to_front()
            sock.disconnectFromServer()
    server.newConnection.connect(_client)
    if args.tray and win.tray is not None:
        pass                                      # start quietly: only the tray icon
    else:
        win.show()
    if store.notices:
        QTimer.singleShot(900, lambda: [win.toast(n, "info") for n in store.notices])
    code = app.exec()
    server.close()
    lock.unlock()
    return code


if __name__ == "__main__":
    sys.exit(main())
