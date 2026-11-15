"""Screenshot automation (`--screenshots`): one PNG per tab, strictly one after the other, then the program quits.

Order of events for every tab (nothing overlaps, the next tab starts only after the previous picture is on disk):
    show tab -> wait until it is really the visible page and the animations settled -> paint -> save -> verify the file -> next tab

Every failure is printed (and written to <folder>/screenshots.log, because the packaged exe has no console) and the program
always quits at the end, also after an error. Exit code 0 = all pictures saved, 1 = at least one failed.
"""
import sys
import time
from pathlib import Path

from PySide6.QtCore import QPoint, QTimer
from PySide6.QtGui import QImage, QPainter


class ShotRunner:
    def __init__(self, app, win, keys, out, size=(1500, 1000), scale=2.0, start_delay=1800, settle=2400,
                 limit_s=None, grab=None):
        self.app, self.win, self.keys = app, win, list(keys)
        self.out = Path(out)
        self.size = size
        self.scale = max(1.0, min(4.0, float(scale)))
        self.start_delay, self.settle = start_delay, settle
        self.limit_s = limit_s if limit_s is not None else 60 + 8 * len(self.keys)
        self.grab = grab or self._paint                  # tests can replace the painting step
        self.i = 0
        self.saved = []                                  # [(index, key, path)] in the order they were taken
        self.errors = []
        self.finished = False
        self.exit_code = None
        self._log_file = None

    # ------------------------------------------------------------------ output
    def say(self, text, error=False):
        line = ("ERROR: " if error else "") + text
        try:
            print(line, file=sys.stderr if error else sys.stdout, flush=True)
        except Exception:
            pass                                          # no console (windowed exe): the log file below is the record
        try:
            if self._log_file is None:
                self.out.mkdir(parents=True, exist_ok=True)
                self._log_file = open(self.out / "screenshots.log", "w", encoding="utf-8")
            self._log_file.write(line + "\n")
            self._log_file.flush()
        except OSError:
            pass

    # ------------------------------------------------------------------ the steps
    def start(self):
        try:
            self.out.mkdir(parents=True, exist_ok=True)
            self.win.showNormal()
            self.win.resize(*self.size)
        except Exception as e:
            self._fail(f"could not prepare the window or the folder: {e}")
        deadline = int(self.limit_s * 1000)
        QTimer.singleShot(deadline, self._timeout)       # a stuck run must never leave the program hanging
        QTimer.singleShot(self.start_delay, self.step)

    def step(self):
        """Show the next tab, then take its picture after it has settled."""
        if self.finished:
            return
        if self.i >= len(self.keys):
            return self.finish()
        key = self.keys[self.i]
        try:
            self.win.goto(key, animate=False)
        except Exception as e:
            self._fail(f"{key}: could not open the tab: {e!r}")
            return self._next()
        QTimer.singleShot(self.settle, self.capture)

    def capture(self):
        if self.finished:
            return
        i, key = self.i, self.keys[self.i]
        try:
            self.app.processEvents()                      # finish pending layout / paint work before the picture
            shown = self.win.current_key()
            if shown != key:
                raise RuntimeError(f"the window shows '{shown}' instead of '{key}'")
            path = self.out / f"{i + 1:02d}_{key}.png"
            img = self.grab()
            if img is None or img.isNull():
                raise RuntimeError("nothing was painted")
            if not img.save(str(path), "PNG"):
                raise RuntimeError(f"could not write {path}")
            if not path.exists() or path.stat().st_size == 0:
                raise RuntimeError(f"{path} is missing or empty after saving")
        except Exception as e:
            self._fail(f"{key}: {e}")
        else:
            self.saved.append((i, key, str(path)))
            self.say(f"saved {path}")
        self._next()                                      # only now, after the save, the next tab starts

    def _next(self):
        self.i += 1
        QTimer.singleShot(0, self.step)

    def _paint(self):
        w, h = self.win.width(), self.win.height()
        img = QImage(int(w * self.scale), int(h * self.scale), QImage.Format.Format_ARGB32_Premultiplied)
        img.setDevicePixelRatio(self.scale)               # the layout stays the same, every pixel count is multiplied
        img.fill(0)
        painter = QPainter(img)
        try:
            self.win.render(painter, QPoint(0, 0))
        finally:
            painter.end()
        return img

    # ------------------------------------------------------------------ the end
    def _fail(self, text):
        self.errors.append(text)
        self.say(text, error=True)

    def _timeout(self):
        if not self.finished:
            self._fail(f"timed out after {self.limit_s}s with {len(self.saved)} of {len(self.keys)} pictures")
            self.finish()

    def finish(self):
        if self.finished:
            return
        self.finished = True
        self.exit_code = 1 if (self.errors or len(self.saved) != len(self.keys)) else 0
        self.say(f"Done: {len(self.saved)} of {len(self.keys)} pictures in {self.out}"
                 + ("" if not self.errors else f" ({len(self.errors)} problem(s), see above)"))
        if self._log_file:
            try:
                self._log_file.close()
            except OSError:
                pass
        quit_app = getattr(self.win, "quit_app", None)    # the window's own way out: stops its background scanner thread,
        if quit_app:                                      # otherwise Qt aborts at exit ("QThread: Destroyed while ... running")
            try:
                quit_app()
            except Exception as e:
                self.say(f"closing the window failed: {e!r}", error=True)
                self.exit_code = 1
        # the window's close schedules its own quit(0); ours comes after it so that app.exec() returns OUR code
        QTimer.singleShot(150, lambda: self.app.exit(self.exit_code))
