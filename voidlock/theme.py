"""Centralised design tokens, motion settings and the global stylesheet."""
import os
import sys

from PySide6.QtGui import QColor, QFont


THEMES = {
    "void": dict(bg="#080A0F", panel="#0E121A", panel2="#131925", raised="#1A2232", border="#1F2837",
                 border_hi="#2D3A50", text="#E8EEF7", text2="#9AA8BF", text3="#5E6D86", cyan="#00E5FF",
                 cyan_dim="#0891A8", cyan_end="#14B8D4", violet="#8B5CF6", violet_end="#6D3FE0",
                 green="#34D399", amber="#FBBF24", red="#F43F5E", on_accent="#04141A", scrim="#02040A",
                 light=False),
    "candy": dict(bg="#FFF5FA", panel="#FFFFFF", panel2="#FFF0F7", raised="#FFE3F0", border="#F6D2E4",
                  border_hi="#EDB4D2", text="#3A2A4D", text2="#6C5784", text3="#A18FB8", cyan="#FF4F9A",
                  cyan_dim="#D93A80", cyan_end="#FF8A5C", violet="#7C5CFF", violet_end="#5B3FE0",
                  green="#0EA371", amber="#E08A00", red="#E5384F", on_accent="#FFFFFF", scrim="#3A2A4D",
                  light=True),
    "ocean": dict(bg="#06121A", panel="#0B1D29", panel2="#102838", raised="#16364B", border="#17384C",
                  border_hi="#25506B", text="#E6F6FF", text2="#8DB4C9", text3="#527A91", cyan="#2DD4BF",
                  cyan_dim="#14A090", cyan_end="#38BDF8", violet="#60A5FA", violet_end="#3B82F6",
                  green="#4ADE80", amber="#FACC15", red="#FB7185", on_accent="#03201C", scrim="#020B12",
                  light=False),
    "forest": dict(bg="#07110C", panel="#0C1B13", panel2="#12251A", raised="#193325", border="#1B3626",
                   border_hi="#2A5238", text="#E8F5EC", text2="#94B8A3", text3="#5B806B", cyan="#4ADE80",
                   cyan_dim="#22A659", cyan_end="#A3E635", violet="#2DD4BF", violet_end="#0EA5A0",
                   green="#86EFAC", amber="#FACC15", red="#FB7185", on_accent="#03170B", scrim="#020A05",
                   light=False),
    "sunset": dict(bg="#140A10", panel="#1E1018", panel2="#2A1621", raised="#3A1F2D", border="#3A1F2D",
                   border_hi="#5B3045", text="#FFEDE6", text2="#D1A3A8", text3="#8E6671", cyan="#FF8A4C",
                   cyan_dim="#D9622A", cyan_end="#FF5E7E", violet="#C084FC", violet_end="#9B5BE0",
                   green="#4ADE80", amber="#FBBF24", red="#FF4D6D", on_accent="#1F0A05", scrim="#0A0408",
                   light=False),
    "midnight": dict(bg="#0A0B1E", panel="#11132B", panel2="#181B3A", raised="#22264C", border="#232850",
                     border_hi="#353B73", text="#ECEEFF", text2="#A0A6D6", text3="#666CA0", cyan="#7C9CFF",
                     cyan_dim="#5472E6", cyan_end="#A78BFA", violet="#F472B6", violet_end="#D6409F",
                     green="#34D399", amber="#FBBF24", red="#FB7185", on_accent="#070A24", scrim="#04051A",
                     light=False),
    "graphite": dict(bg="#0B0B0C", panel="#141416", panel2="#1B1B1E", raised="#25252A", border="#2A2A30",
                     border_hi="#3C3C45", text="#F0F0F2", text2="#A4A4AE", text3="#6C6C76", cyan="#E5E7EB",
                     cyan_dim="#9CA3AF", cyan_end="#CBD5E1", violet="#A1A1AA", violet_end="#71717A",
                     green="#6EE7B7", amber="#FCD34D", red="#F87171", on_accent="#0B0B0C", scrim="#000000",
                     light=False),
    "paper": dict(bg="#F6F4EF", panel="#FFFFFF", panel2="#F1EEE7", raised="#E9E5DB", border="#E2DDD0",
                  border_hi="#CFC8B6", text="#1F2430", text2="#4F5666", text3="#8A8F9C", cyan="#2563EB",
                  cyan_dim="#1D4FC4", cyan_end="#0EA5E9", violet="#7C3AED", violet_end="#5B21B6",
                  green="#0E9F6E", amber="#C77700", red="#DC2626", on_accent="#FFFFFF", scrim="#1F2430",
                  light=True),
    "mint": dict(bg="#F2FBF7", panel="#FFFFFF", panel2="#E8F6EF", raised="#D9EFE5", border="#CFE8DC",
                 border_hi="#A9D4C0", text="#11322A", text2="#3F6558", text3="#7FA597", cyan="#0EA37A",
                 cyan_dim="#0A7F5E", cyan_end="#22C1A0", violet="#6366F1", violet_end="#4F46E5",
                 green="#16A34A", amber="#CA8A04", red="#E11D48", on_accent="#FFFFFF", scrim="#11322A",
                 light=True),
}
THEME_ORDER = ("void", "ocean", "midnight", "forest", "sunset", "graphite", "candy", "paper", "mint")
THEME_NAMES = {"void": "Void", "candy": "Candy", "ocean": "Ocean", "forest": "Forest", "sunset": "Sunset",
               "midnight": "Midnight", "graphite": "Graphite", "paper": "Paper", "mint": "Mint"}


class T:
    # filled by apply_theme() - defaults are the "void" theme
    locals().update(THEMES["void"])
    # geometry
    r_lg = 16
    r_md = 12
    r_sm = 8
    ui_font = ["Segoe UI Variable Display", "Segoe UI", "Inter", "SF Pro Text",
               "Helvetica Neue", "DejaVu Sans", "Arial"]
    mono_font = ["Cascadia Mono", "Consolas", "JetBrains Mono", "DejaVu Sans Mono",
                 "Courier New"]
    CATEGORY = {
        "Games": "#8B5CF6", "Launchers": "#00E5FF", "Social": "#38BDF8", "Media": "#F43F5E",
        "Browsers": "#FBBF24", "Sites": "#34D399", "Other": "#94A3B8",
    }


def apply_theme(name):
    """Switch all colour tokens. Must be called before any widget is created."""
    th = THEMES.get(name, THEMES["void"])
    for k, v in th.items():
        setattr(T, k, v)
    if th["light"]:
        T.CATEGORY.update({"Games": "#7C5CFF", "Launchers": "#E0408A", "Social": "#1E88E5", "Media": "#E5384F",
                           "Browsers": "#D98200", "Sites": "#0EA371", "Other": "#7B8794"})
    else:
        T.CATEGORY.update({"Games": "#8B5CF6", "Launchers": T.cyan, "Social": "#38BDF8", "Media": "#F43F5E",
                           "Browsers": "#FBBF24", "Sites": "#34D399", "Other": "#94A3B8"})


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
