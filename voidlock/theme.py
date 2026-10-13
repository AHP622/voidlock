"""Centralised design tokens, motion settings and the global stylesheet."""
import os
import sys

from PySide6.QtGui import QColor, QFont


class T:
    # surfaces
    bg = "#080A0F"
    panel = "#0E121A"
    panel2 = "#131925"
    raised = "#1A2232"
    border = "#1F2837"
    border_hi = "#2D3A50"
    # text
    text = "#E8EEF7"
    text2 = "#9AA8BF"
    text3 = "#5E6D86"
    # accents
    cyan = "#00E5FF"
    cyan_dim = "#0891A8"
    violet = "#8B5CF6"
    green = "#34D399"
    amber = "#FBBF24"
    red = "#F43F5E"
    # geometry
    r_lg = 16
    r_md = 12
    r_sm = 8
    ui_font = ["Segoe UI Variable Display", "Segoe UI", "Inter", "SF Pro Text",
               "Helvetica Neue", "DejaVu Sans", "Arial"]
    mono_font = ["Cascadia Mono", "Consolas", "JetBrains Mono", "DejaVu Sans Mono",
                 "Courier New"]

    CATEGORY = {
        "Games": "#8B5CF6", "Launchers": "#00E5FF", "Social": "#38BDF8",
        "Media": "#F43F5E", "Browsers": "#FBBF24", "Other": "#94A3B8",
    }


def qc(hex_color, alpha=1.0):
    c = QColor(hex_color)
    c.setAlphaF(max(0.0, min(1.0, alpha)))
    return c


def font(px=13, weight=QFont.Weight.Normal, mono=False, spacing=0.0, keep_mono=False):
    from . import i18n
    fa = i18n.is_fa()
    f = QFont()
    ui = (["Vazirmatn"] + T.ui_font + ["Tahoma"]) if fa else T.ui_font
    f.setFamilies((T.mono_font + ui) if (mono and (keep_mono or not fa)) else ui)
    f.setPixelSize(int(px))
    f.setWeight(weight)
    if spacing and not fa:
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
    return f


class Motion:
    """Global motion switch. Every animation routes its duration through ms()."""
    reduced = False

    @classmethod
    def ms(cls, n):
        return 0 if cls.reduced else int(n)


def system_reduced_motion():
    if os.environ.get("VOIDLOCK_REDUCED_MOTION") == "1":
        return True
    if sys.platform == "win32":
        try:
            import ctypes
            flag = ctypes.c_int(1)
            ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(flag), 0)
            return flag.value == 0
        except Exception:
            return False
    return False


def stylesheet():
    return f"""
* {{ outline: none; }}
QWidget {{ color: {T.text}; }}
QMainWindow, QWidget#root {{ background: {T.bg}; }}
QToolTip {{
    background: {T.raised}; color: {T.text}; border: 1px solid {T.border_hi};
    padding: 6px 9px; border-radius: 6px; font-size: 12px;
}}
QLabel {{ background: transparent; }}
QLineEdit {{
    background: {T.panel2}; border: 1px solid {T.border}; border-radius: 10px;
    padding: 9px 12px; color: {T.text}; selection-background-color: {T.cyan_dim};
}}
QLineEdit:hover {{ border-color: {T.border_hi}; }}
QLineEdit:focus {{ border: 1px solid {T.cyan}; background: {T.panel}; }}
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {T.border_hi}; border-radius: 3px; min-height: 36px; }}
QScrollBar::handle:vertical:hover {{ background: {T.text3}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; height: 0; }}
QScrollBar:horizontal {{ height: 0; }}
QSlider::groove:horizontal {{ height: 4px; background: {T.border}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {T.cyan}, stop:1 {T.violet});
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {T.text}; width: 16px; height: 16px; margin: -6px 0; border-radius: 8px;
    border: 3px solid {T.cyan};
}}
QSlider::handle:horizontal:hover {{ border-color: {T.violet}; }}
"""
