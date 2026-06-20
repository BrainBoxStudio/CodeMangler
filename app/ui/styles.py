"""Global stylesheet for CodeMangler.

A `Palette` holds the small set of semantic color roles the QSS template
below actually varies by theme; `build_stylesheet()` renders the template
against one. The live-log terminal area (`QTextEdit#logArea`) deliberately
keeps its own fixed dark/monospace styling regardless of theme — terminal-
style panels conventionally stay dark — so it isn't parameterized here.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    background: str        # page background
    chrome: str              # top bar / status bar / unselected tabs
    surface: str              # text inputs/combos (usually white-ish)
    border: str                # default border/accent color
    scrollbar_handle: str        # needs more contrast than `border` alone
    primary: str                  # main accent (buttons, selected tab, focus)
    primary_hover: str
    primary_pressed: str
    text: str                      # default text color
    accent_text: str                # text drawn on `chrome` (unselected tabs, status bar)
    text_on_primary: str             # text drawn on a filled `primary` background
    disabled_bg: str
    disabled_text: str


PALETTE_LIGHT_BLUE = Palette(
    background="#EBF5FB",
    chrome="#D6EAF8",
    surface="#FFFFFF",
    border="#AED6F1",
    scrollbar_handle="#7FB3D3",
    primary="#2E86C1",
    primary_hover="#1A6EA8",
    primary_pressed="#154F7A",
    text="#1A3550",
    accent_text="#1A5276",
    text_on_primary="#FFFFFF",
    disabled_bg="#BDC3C7",
    disabled_text="#7F8C8D",
)

PALETTE_DARK = Palette(
    background="#1B2631",
    chrome="#212E3B",
    surface="#27323D",
    border="#3B4A59",
    scrollbar_handle="#5C7185",
    primary="#5DADE2",
    primary_hover="#3498DB",
    primary_pressed="#21618C",
    text="#EAF2F8",
    accent_text="#AED6F1",
    text_on_primary="#0B1620",
    disabled_bg="#3B4A59",
    disabled_text="#85929E",
)

PALETTE_LIGHT_GRAY = Palette(
    background="#F4F6F7",
    chrome="#E5E8E8",
    surface="#FFFFFF",
    border="#D5DBDB",
    scrollbar_handle="#AEB6BF",
    primary="#5D6D7E",
    primary_hover="#4A5A6A",
    primary_pressed="#36454F",
    text="#2C3E50",
    accent_text="#34495E",
    text_on_primary="#FFFFFF",
    disabled_bg="#D5DBDB",
    disabled_text="#909497",
)

PREDEFINED_PALETTES: dict[str, Palette] = {
    "Light Blue": PALETTE_LIGHT_BLUE,
    "Dark": PALETTE_DARK,
    "Light Gray": PALETTE_LIGHT_GRAY,
}


def _relative_luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    return 0.299 * r + 0.587 * g + 0.114 * b


def _lighten(hex_color: str, amount: float) -> str:
    from PySide6.QtGui import QColor

    color = QColor(hex_color)
    h, s, l, a = color.getHslF()
    l = min(1.0, l + amount)
    result = QColor.fromHslF(h, s, l, a)
    return result.name()


def _darken(hex_color: str, amount: float) -> str:
    return _lighten(hex_color, -amount)


def derive_palette_from_base_color(base_hex: str) -> Palette:
    """Builds a full Palette from a single user-picked base color: lighter
    tints for background/chrome/surface/hover, a darker shade for
    pressed/border, and white-vs-dark text chosen by a standard luminance
    threshold so contrast against `base_hex` is never accidentally broken.
    """
    text_is_light = _relative_luminance(base_hex) < 140
    text = "#F5F5F5" if text_is_light else "#1A1A1A"
    text_on_primary = "#FFFFFF" if text_is_light else "#1A1A1A"
    accent_text = base_hex if not text_is_light else _lighten(base_hex, 0.35)
    return Palette(
        background=_lighten(base_hex, 0.42),
        chrome=_lighten(base_hex, 0.36),
        surface=_lighten(base_hex, 0.48),
        border=_lighten(base_hex, 0.20),
        scrollbar_handle=_lighten(base_hex, 0.05),
        primary=base_hex,
        primary_hover=_darken(base_hex, 0.08),
        primary_pressed=_darken(base_hex, 0.18),
        text=text,
        accent_text=accent_text,
        text_on_primary=text_on_primary,
        disabled_bg=_lighten(base_hex, 0.15),
        disabled_text=_darken(base_hex, 0.05) if text_is_light else _lighten(base_hex, 0.30),
    )


def build_stylesheet(palette: Palette) -> str:
    p = palette
    return f"""
/* ── Base ── */
QMainWindow, QWidget {{
    background-color: {p.background};
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
    color: {p.text};
}}

QLabel {{
    color: {p.text};
    background: transparent;
}}

/* ── Toolbar / top bar ── */
QWidget#topBar {{
    background-color: {p.chrome};
    border-bottom: 1px solid {p.border};
}}

/* ── Mode toggle buttons ── */
QPushButton#modeBtn {{
    background-color: {p.chrome};
    color: {p.accent_text};
    border: 1.5px solid {p.border};
    border-radius: 14px;
    padding: 5px 14px;
    font-weight: bold;
    min-width: 64px;
}}
QPushButton#modeBtn:hover {{
    background-color: {p.border};
}}
QPushButton#modeBtn:checked {{
    background-color: {p.primary};
    color: {p.text_on_primary};
    border: 1.5px solid {p.primary_pressed};
}}

/* ── Generic push buttons ── */
QPushButton {{
    background-color: {p.primary};
    color: {p.text_on_primary};
    border: none;
    border-radius: 14px;
    padding: 5px 12px;
    font-weight: bold;
}}
QPushButton:hover  {{ background-color: {p.primary_hover}; }}
QPushButton:pressed {{ background-color: {p.primary_pressed}; }}
QPushButton:disabled {{ background-color: {p.disabled_bg}; color: {p.disabled_text}; }}

/* ── Process button (file panel) ── */
QPushButton#processBtn {{
    background-color: #1ABC9C;
    color: white;
    border-radius: 17px;
    padding: 7px 24px;
    font-size: 14px;
    font-weight: bold;
}}
QPushButton#processBtn:hover   {{ background-color: #17A589; }}
QPushButton#processBtn:pressed {{ background-color: #148F77; }}
QPushButton#processBtn:disabled {{ background-color: {p.disabled_bg}; color: {p.disabled_text}; }}

/* ── Animated arrow button ── */
QPushButton#arrowBtn {{
    background-color: {p.primary};
    color: {p.text_on_primary};
    border-radius: 32px;
    font-size: 20px;
    font-weight: bold;
    min-width:  64px;
    max-width:  64px;
    min-height: 64px;
    max-height: 64px;
}}
QPushButton#arrowBtn:hover   {{ background-color: {p.primary_hover}; }}
QPushButton#arrowBtn:disabled {{ background-color: {p.border}; color: {p.disabled_text}; }}

/* ── Text / code editors ── */
QTextEdit {{
    background-color: {p.surface};
    border: 1.5px solid {p.border};
    border-radius: 6px;
    padding: 6px;
    color: {p.text};
    selection-background-color: {p.border};
}}
QTextEdit:focus {{
    border: 1.5px solid {p.primary};
}}

/* ── Live log area — fixed dark terminal style, not themed ── */
QTextEdit#logArea {{
    background-color: #0D1B2A;
    color: #A8D8EA;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 12px;
    border: 1px solid #2E86C1;
    border-radius: 4px;
    padding: 6px;
    selection-background-color: #2E86C1;
}}

/* ── Line edits ── */
QLineEdit {{
    background-color: {p.surface};
    border: 1.5px solid {p.border};
    border-radius: 4px;
    padding: 5px 8px;
    color: {p.text};
}}
QLineEdit:focus {{ border: 1.5px solid {p.primary}; }}

/* ── Combo box ── */
QComboBox {{
    background-color: {p.surface};
    border: 1.5px solid {p.border};
    border-radius: 14px;
    padding: 4px 26px 4px 12px;
    color: {p.text};
    min-width: 140px;
}}
QComboBox:focus {{ border: 1.5px solid {p.primary}; }}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox::down-arrow {{
    image: none;
    border-left:  5px solid transparent;
    border-right: 5px solid transparent;
    border-top:   6px solid {p.primary};
    width: 0; height: 0;
    margin-right: 8px;
}}
QComboBox QAbstractItemView {{
    background-color: {p.surface};
    border: 1px solid {p.border};
    selection-background-color: {p.primary};
    selection-color: {p.text_on_primary};
    outline: none;
}}

/* ── Mangle Options dropdown ── */
QToolButton#mangleDropdown {{
    background-color: {p.surface};
    border: 1.5px solid {p.border};
    border-radius: 14px;
    padding: 4px 26px 4px 12px;
    color: {p.text};
    min-width: 100px;
}}
QToolButton#mangleDropdown:hover {{
    border: 1.5px solid {p.primary};
}}
QToolButton#mangleDropdown::menu-indicator {{
    subcontrol-origin: padding;
    subcontrol-position: right center;
    right: 6px;
}}
QTreeWidget#mangleTree {{
    background-color: {p.surface};
    border: 1px solid {p.border};
    outline: none;
    padding: 4px;
}}
QTreeWidget#mangleTree::item {{
    padding: 3px 4px;
    color: {p.text};
}}
QTreeWidget#mangleTree::item:hover {{
    background-color: {p.background};
}}

/* ── Group box ── */
QGroupBox {{
    border: 1.5px solid {p.border};
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 6px;
    color: {p.text};
    font-weight: bold;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 6px;
    color: {p.primary};
}}

/* ── Tab widget ── */
QTabWidget::pane {{
    border: none;
    background-color: {p.background};
}}
QTabBar::tab {{
    background-color: {p.chrome};
    color: {p.accent_text};
    border: 1.5px solid {p.border};
    border-radius: 15px;
    padding: 5px 8px;
    font-weight: bold;
    margin: 2px 4px 2px 0;
    min-width: 88px;
    max-width: 88px;
}}
QTabBar::tab:hover {{
    background-color: {p.border};
}}
QTabBar::tab:selected {{
    background-color: {p.primary};
    color: {p.text_on_primary};
    min-width: 200px;
    max-width: 200px;
}}

/* ── Scroll bars ── */
QScrollBar:vertical {{
    background: {p.chrome};
    width: 10px;
    border-radius: 5px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {p.scrollbar_handle};
    border-radius: 5px;
    min-height: 24px;
}}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{ height: 0; }}

QScrollBar:horizontal {{
    background: {p.chrome};
    height: 10px;
    border-radius: 5px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {p.scrollbar_handle};
    border-radius: 5px;
    min-width: 24px;
}}
QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ── Status bar ── */
QStatusBar {{
    background-color: {p.chrome};
    border-top: 1px solid {p.border};
    color: {p.accent_text};
    font-size: 12px;
}}
QStatusBar::item {{ border: none; }}

/* ── Splitter handle ── */
QSplitter::handle {{
    background-color: {p.border};
}}
QSplitter::handle:horizontal {{ width: 2px; }}
QSplitter::handle:vertical   {{ height: 2px; }}
"""


# Backwards-compatible default — today's exact look, unchanged.
THEME = build_stylesheet(PALETTE_LIGHT_BLUE)
