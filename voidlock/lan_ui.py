"""Qt side of the Wi-Fi sync: runs the server's data access on the main thread and refreshes the app when the phone changed something."""
import threading

from PySide6.QtCore import QObject, Qt, Signal

from . import i18n, lansync


class _Job:
    def __init__(self, fn):
        self.fn, self.done, self.result, self.exc = fn, threading.Event(), None, None

    def run(self):
        try:
            self.result = self.fn()
        except BaseException as e:                       # handed back to the server thread, which answers the phone
            self.exc = e
        finally:
            self.done.set()


class MainThreadCaller(QObject):
    """Create it on the main thread. call(fn) from another thread runs fn on the main thread and returns its result."""
    _run = Signal(object)

    def __init__(self):
        super().__init__()
        self._run.connect(self._exec, Qt.ConnectionType.QueuedConnection)

    def _exec(self, job):
        job.run()

    def call(self, fn, timeout=40):
        if threading.current_thread() is threading.main_thread():
            return fn()
        job = _Job(fn)
        self._run.emit(job)
        if not job.done.wait(timeout):
            raise TimeoutError("the app did not answer in time")
        if job.exc is not None:
            raise job.exc
        return job.result


class LanService(QObject):
    """Owns the sync server. Started / stopped by the setting `lan_sync`."""
    changed = Signal()                                    # the paired phones list changed (Settings refreshes)
    pair_request = Signal(object)                         # a phone entered the right code: {name, sas, pid} - the person must allow it

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.caller = MainThreadCaller()
        self.backend = lansync.StoreBackend(win.store, win.study, call=self.caller.call, on_changed=self._data_changed,
                                            on_paired=lambda: self.changed.emit(), on_pair_request=lambda info: self.pair_request.emit(info))
        self.server = lansync.LanServer(self.backend)
        self.error = ""

    def apply(self):
        """Start or stop to match the setting."""
        want = bool(self.win.store.settings.get("lan_sync"))
        self.error = ""
        if want and not self.server.running:
            try:
                self.server.start()
            except lansync.CryptoMissing as e:
                self.error = i18n.tr("The encryption library is missing, so Wi-Fi sync is off.") + f" ({e})"
            except OSError as e:
                self.error = str(e)
        elif not want and self.server.running:
            self.server.stop()
        self.changed.emit()

    def stop(self):
        self.server.stop()

    def _data_changed(self, plan):
        """Runs on the main thread, inside a sync request from the phone."""
        w = self.win
        for pg in w.pages.values():
            pg.refresh()
        w.session.changed.emit()
        w.toast(f"{i18n.tr('Synced with')} {plan.peer['name']}", "success")
