"""Centralized design tokens for BabkaCode dark theme.

All UI files should import colors, spacing, and typography constants from here
to ensure consistency across Qt widgets and HTML/CSS chat rendering.
"""

from __future__ import annotations

# ── Surfaces (darkest → lightest) ─────────────────────────────────────────────
BG_BASE = "#0e1015"  # Activity bar, status bar, deepest bg
BG_SURFACE = "#14161c"  # Panel backgrounds, title bar, terminal
BG_ELEVATED = "#1a1d25"  # Cards, inputs, sidebar content, editor
BG_HOVER = "#22252e"  # Hover states, elevated interactive elements

# ── Borders ───────────────────────────────────────────────────────────────────
BORDER_SUBTLE = "rgba(255, 255, 255, 0.06)"
BORDER_DEFAULT = "rgba(255, 255, 255, 0.10)"
BORDER_STRONG = "rgba(255, 255, 255, 0.16)"

# QColor-compatible versions (no rgba() syntax for Qt painter use)
BORDER_SUBTLE_QT = "#0f1118"  # approximation for QPainter; use alpha in code
BORDER_DEFAULT_QT = "#242730"

# ── Text ──────────────────────────────────────────────────────────────────────
TEXT_PRIMARY = "#e2e4ea"
TEXT_SECONDARY = "#8b8fa3"
TEXT_TERTIARY = "#525669"
TEXT_DISABLED = "#3a3d4a"

# ── Accent (indigo) ───────────────────────────────────────────────────────────
ACCENT = "#6366f1"
ACCENT_HOVER = "#7577f5"
ACCENT_MUTED = "rgba(99, 102, 241, 0.12)"
ACCENT_FOCUS = "rgba(99, 102, 241, 0.50)"
ACCENT_SELECTION = "rgba(99, 102, 241, 0.20)"

# Qt solid approximations for accent-muted areas
ACCENT_MUTED_QT = "#1a1b2e"
ACCENT_ACTIVE_QT = "#1e2040"

# ── Semantic ──────────────────────────────────────────────────────────────────
SUCCESS = "#34d399"
SUCCESS_MUTED = "rgba(52, 211, 153, 0.12)"
ERROR = "#f87171"
ERROR_MUTED = "rgba(248, 113, 113, 0.10)"
ERROR_BG = "#1e1518"
WARNING = "#fbbf24"

# ── Spacing (px values as ints) ───────────────────────────────────────────────
SP_2 = 2
SP_4 = 4
SP_8 = 8
SP_12 = 12
SP_16 = 16
SP_20 = 20
SP_24 = 24

# ── Border radii ──────────────────────────────────────────────────────────────
RADIUS_SM = 6  # badges, pills, tooltips
RADIUS_MD = 8  # buttons
RADIUS_LG = 10  # cards, inputs
RADIUS_XL = 12  # chat bubbles, larger cards

# ── Typography ────────────────────────────────────────────────────────────────
FONT_UI = '"Geist", "Inter", "Segoe UI Variable", "Segoe UI", system-ui, sans-serif'
FONT_MONO = '"JetBrains Mono Nerd Font", "JetBrains Mono", "Consolas", monospace'
FONT_UI_QT = "Segoe UI Variable"  # Qt font family for QSS (system-available on Win11)
FONT_UI_QT_FB = "Segoe UI"  # Fallback for Win10

SIZE_XS = 10
SIZE_SM = 11
SIZE_BASE = 12
SIZE_MD = 13
SIZE_LG = 14

# ── Layout dimensions ─────────────────────────────────────────────────────────
TITLE_BAR_H = 36
ACTIVITY_BAR_W = 48
PANEL_HEADER_H = 44
TAB_BAR_H = 38
STATUS_BAR_H = 28
SIDEBAR_W = 280
CHAT_PANEL_W = 420

# ── Syntax highlighting (for dark editor) ─────────────────────────────────────
SYN_KEYWORD = "#c792ea"  # purple
SYN_BUILTIN = "#80cbc4"  # teal
SYN_CLASS = "#82aaff"  # blue
SYN_FUNCTION = "#f6c177"  # amber
SYN_STRING = "#c3e88d"  # green
SYN_NUMBER = "#f78c6c"  # orange
SYN_COMMENT = "#546e7a"  # steel gray
SYN_DECORATOR = "#c792ea"  # purple

# ── Terminal ANSI palette ──────────────────────────────────────────────────────
TERM_FG = (226, 228, 234)  # TEXT_PRIMARY as RGB
TERM_BG = (20, 22, 28)  # BG_SURFACE as RGB
TERM_CURSOR_FG = (20, 22, 28)
TERM_CURSOR_BG = (226, 228, 234)

ANSI_COLORS: tuple[tuple[int, int, int], ...] = (
    (14, 16, 21),  # 0  black
    (240, 113, 120),  # 1  red
    (195, 232, 141),  # 2  green
    (255, 203, 107),  # 3  yellow
    (130, 170, 255),  # 4  blue
    (199, 146, 234),  # 5  magenta
    (137, 221, 255),  # 6  cyan
    (176, 190, 197),  # 7  white
    (84, 86, 105),  # 8  bright black (gray)
    (255, 85, 114),  # 9  bright red
    (204, 255, 176),  # 10 bright green
    (255, 230, 120),  # 11 bright yellow
    (130, 177, 255),  # 12 bright blue
    (215, 160, 255),  # 13 bright magenta
    (128, 203, 196),  # 14 bright cyan
    (236, 239, 244),  # 15 bright white
)
