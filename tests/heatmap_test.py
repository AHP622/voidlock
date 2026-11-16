"""Study calendar hover (voidlock/mascot.py Heatmap): the highlighted day must be the one under the mouse, in LTR and RTL,
also when the grid is narrower than the card. Run: python tests/heatmap_test.py"""
import os
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QEvent, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QMouseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from voidlock.mascot import Heatmap  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)


def make(rtl, width=800, height=150, weeks=13):
    h = Heatmap()
    h.resize(width, height)
    h.setLayoutDirection(Qt.LayoutDirection.RightToLeft if rtl else Qt.LayoutDirection.LeftToRight)
    cols = [[3600 * ((wi + di) % 5) for di in range(7)] for wi in range(weeks)]
    cols[-1][4:] = [-1, -1, -1]                       # the last week is unfinished: those days do not exist
    h.set_data(cols, date(2026, 1, 3))
    return h


def move(h, x, y):
    h.mouseMoveEvent(QMouseEvent(QEvent.Type.MouseMove, QPointF(x, y), QPointF(x, y), Qt.MouseButton.NoButton,
                                 Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier))
    return h._hover


class Hover(unittest.TestCase):
    def test_hover_is_the_cell_drawn_under_the_mouse(self):
        for rtl in (False, True):
            h = make(rtl)
            c = h._cell()
            for wi in (0, 5, 12):
                for di in (0, 3, 6):
                    if h.cols[wi][di] < 0:
                        continue
                    x = (h.width() - (wi + 0.5) * c) if rtl else (wi + 0.5) * c      # centre of the cell exactly as paintEvent places it
                    self.assertEqual(move(h, x, (di + 0.5) * c), (wi, di), f"rtl={rtl} cell=({wi},{di})")

    def test_empty_space_beside_the_grid_has_no_hover(self):
        h = make(True)                                  # RTL: the grid sits at the right, the left part of the card is empty
        self.assertIsNone(move(h, 40, 30))
        self.assertIsNone(move(h, h.width() / 2, 30))
        h = make(False)                                 # LTR: the grid sits at the left, the right part is empty
        self.assertIsNone(move(h, h.width() - 40, 30))

    def test_days_that_do_not_exist_and_outside_the_widget(self):
        h = make(True)
        c = h._cell()
        self.assertIsNone(move(h, h.width() - 12.5 * c, 5.5 * c), "the unfinished (last) week has no day 5")
        self.assertEqual(move(h, h.width() - 12.5 * c, 2.5 * c), (12, 2), "...but its first days exist")
        self.assertIsNone(move(h, h.width() + 5, 10))
        self.assertIsNone(move(h, h.width() - 10, h.height() + 5))


if __name__ == "__main__":
    unittest.main(verbosity=2)
