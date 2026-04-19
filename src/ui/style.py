"""Global QSS stylesheet for BabkaCode -- dark minimal devtool theme."""

from __future__ import annotations

if __package__ in {None, ""}:
    import sys
    from pathlib import Path

    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from src.ui.design_tokens import (
        BG_BASE,
        BG_SURFACE,
        BG_ELEVATED,
        BG_HOVER,
        BORDER_SUBTLE,
        BORDER_DEFAULT,
        BORDER_STRONG,
        TEXT_PRIMARY,
        TEXT_SECONDARY,
        TEXT_TERTIARY,
        TEXT_DISABLED,
        ACCENT,
        ACCENT_HOVER,
        ACCENT_MUTED_QT,
        ACCENT_ACTIVE_QT,
        RADIUS_SM,
        RADIUS_MD,
        RADIUS_LG,
        TITLE_BAR_H,
        PANEL_HEADER_H,
        TAB_BAR_H,
        STATUS_BAR_H,
    )
else:
    from .design_tokens import (
        BG_BASE,
        BG_SURFACE,
        BG_ELEVATED,
        BG_HOVER,
        BORDER_SUBTLE,
        BORDER_DEFAULT,
        BORDER_STRONG,
        TEXT_PRIMARY,
        TEXT_SECONDARY,
        TEXT_TERTIARY,
        TEXT_DISABLED,
        ACCENT,
        ACCENT_HOVER,
        ACCENT_MUTED_QT,
        ACCENT_ACTIVE_QT,
        RADIUS_SM,
        RADIUS_MD,
        RADIUS_LG,
        TITLE_BAR_H,
        PANEL_HEADER_H,
        TAB_BAR_H,
        STATUS_BAR_H,
    )


STYLE_SHEET = f"""
/* ── Global ──────────────────────────────────────────────────────────────── */
QMainWindow, QWidget#centralContainer {{
    background: {BG_BASE};
    color: {TEXT_PRIMARY};
}}

QWidget {{
    color: {TEXT_PRIMARY};
    font-size: 12px;
}}

QLabel {{
    color: {TEXT_PRIMARY};
    background: transparent;
}}

QWidget#titleContentGap {{
    background: {BG_BASE};
    max-height: 0px;
}}

/* ── Title bar ───────────────────────────────────────────────────────────── */
QWidget#titleBar {{
    background: {BG_SURFACE};
    border-bottom: 1px solid {BORDER_SUBTLE};
    min-height: {TITLE_BAR_H}px;
    max-height: {TITLE_BAR_H}px;
}}

QWidget#titleBarControls {{
    background: transparent;
}}

QLabel#titleIconLabel {{
    background: transparent;
}}

QLabel#titleLabel {{
    color: {TEXT_PRIMARY};
    font-weight: 600;
    font-size: 13px;
    background: transparent;
}}

QLabel#workspacePathLabel {{
    color: {TEXT_SECONDARY};
    font-size: 11px;
    background: transparent;
}}

QLabel#modelBadge {{
    color: {ACCENT};
    font-size: 10px;
    font-weight: 600;
    background: {ACCENT_MUTED_QT};
    border: 1px solid rgba(99, 102, 241, 0.25);
    border-radius: {RADIUS_SM}px;
    padding: 2px 10px;
}}

QToolButton#titleBtn,
QToolButton#titleBtnClose {{
    background: transparent;
    border: none;
    border-radius: {RADIUS_SM}px;
    padding: 4px;
}}

QToolButton#titleBtn:hover {{
    background: rgba(255, 255, 255, 0.07);
}}

QToolButton#titleBtn:pressed {{
    background: rgba(255, 255, 255, 0.12);
}}

QToolButton#titleBtnClose:hover {{
    background: rgba(248, 113, 113, 0.18);
}}

QToolButton#titleBtnClose:pressed {{
    background: rgba(248, 113, 113, 0.28);
}}

/* ── Activity bar ────────────────────────────────────────────────────────── */
QWidget#activityBar {{
    background: {BG_BASE};
    border-right: 1px solid {BORDER_SUBTLE};
    min-width: 48px;
    max-width: 48px;
}}

QToolButton#activityBtn {{
    background: transparent;
    border: none;
    border-radius: {RADIUS_SM}px;
    padding: 8px;
    color: {TEXT_TERTIARY};
    min-width: 32px;
    min-height: 32px;
    max-width: 32px;
    max-height: 32px;
}}

QToolButton#activityBtn:hover {{
    background: rgba(255, 255, 255, 0.06);
    color: {TEXT_SECONDARY};
}}

QToolButton#activityBtnActive {{
    background: {ACCENT_MUTED_QT};
    border: none;
    border-radius: {RADIUS_SM}px;
    padding: 8px;
    color: {ACCENT};
    min-width: 32px;
    min-height: 32px;
    max-width: 32px;
    max-height: 32px;
}}

QToolButton#activityBtnActive:hover {{
    background: {ACCENT_ACTIVE_QT};
}}

/* ── Sidebar panel ───────────────────────────────────────────────────────── */
QWidget#sidebarPanel {{
    background: {BG_SURFACE};
    border-right: 1px solid {BORDER_SUBTLE};
}}

QWidget#sidebarContent {{
    background: transparent;
}}

QLabel#panelHeader {{
    background: transparent;
    color: {TEXT_TERTIARY};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.08em;
    padding: 0 16px;
}}

/* ── File Explorer ───────────────────────────────────────────────────────── */
QWidget#explorerPanel {{
    background: {BG_SURFACE};
}}

QTreeView#explorerTree {{
    background: transparent;
    color: {TEXT_PRIMARY};
    border: none;
    outline: none;
    padding: 8px 6px 12px 6px;
    selection-background-color: transparent;
    selection-color: {TEXT_PRIMARY};
    show-decoration-selected: 0;
}}

QTreeView#explorerTree::item {{
    padding: 0;
    height: 32px;
    border: none;
}}

QTreeView#explorerTree::branch {{
    background: transparent;
}}

/* ── Editor panel ────────────────────────────────────────────────────────── */
QWidget#editorPanel {{
    background: {BG_SURFACE};
}}

/* ── File tab bar ────────────────────────────────────────────────────────── */
QWidget#fileTabBar {{
    background: {BG_SURFACE};
    border-bottom: 1px solid {BORDER_SUBTLE};
    min-height: {TAB_BAR_H}px;
    max-height: {TAB_BAR_H}px;
}}

QScrollArea#fileTabScroll {{
    background: transparent;
    border: none;
}}

QWidget#fileTabContainer {{
    background: transparent;
}}

QFrame#fileTab {{
    background: transparent;
    border: none;
    border-right: 1px solid {BORDER_SUBTLE};
    min-height: {TAB_BAR_H}px;
    max-height: {TAB_BAR_H}px;
    padding: 0;
}}

QFrame#fileTab:hover {{
    background: rgba(255, 255, 255, 0.04);
}}

QFrame#fileTabActive {{
    background: {BG_ELEVATED};
    border: none;
    border-bottom: 2px solid {ACCENT};
    border-right: 1px solid {BORDER_SUBTLE};
    min-height: {TAB_BAR_H}px;
    max-height: {TAB_BAR_H}px;
    padding: 0;
}}

QLabel#fileTabLabel {{
    color: {TEXT_SECONDARY};
    font-size: 12px;
    font-weight: 400;
    background: transparent;
}}

QLabel#fileTabLabelActive {{
    color: {TEXT_PRIMARY};
    font-size: 12px;
    font-weight: 500;
    background: transparent;
}}

QToolButton#fileTabClose {{
    background: transparent;
    border: none;
    border-radius: 3px;
    color: {TEXT_TERTIARY};
    font-size: 13px;
    padding: 0;
}}

QToolButton#fileTabClose:hover {{
    background: rgba(255, 255, 255, 0.10);
    color: {TEXT_PRIMARY};
}}

/* ── Editor surface ──────────────────────────────────────────────────────── */
QPlainTextEdit#editorSurface {{
    background: {BG_ELEVATED};
    color: {TEXT_PRIMARY};
    border: none;
    selection-background-color: rgba(99, 102, 241, 0.20);
    selection-color: {TEXT_PRIMARY};
}}

/* ── Terminal panel ──────────────────────────────────────────────────────── */
QWidget#terminalPanel {{
    background: {BG_SURFACE};
    border-top: 1px solid {BORDER_SUBTLE};
}}

QLabel#terminalHeader {{
    background: transparent;
    color: {TEXT_TERTIARY};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.08em;
    padding: 0 16px;
}}

QPlainTextEdit#terminalOutput,
QTextEdit#terminalOutput {{
    background: {BG_SURFACE};
    color: {TEXT_PRIMARY};
    border: none;
}}

/* ── Chat panel ──────────────────────────────────────────────────────────── */
QWidget#chatPanel {{
    background: {BG_SURFACE};
    border-left: 1px solid {BORDER_SUBTLE};
}}

QWidget#chatWebContainer {{
    background: {BG_SURFACE};
    border: none;
}}

/* ── Chat header ─────────────────────────────────────────────────────────── */
QFrame#chatHeaderFrame {{
    background: {BG_SURFACE};
    border-bottom: 1px solid {BORDER_SUBTLE};
    min-height: {PANEL_HEADER_H}px;
    max-height: {PANEL_HEADER_H}px;
}}

QLabel#chatHeaderLabel {{
    color: {TEXT_TERTIARY};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.08em;
    background: transparent;
}}

QLabel#modeLabelSmall {{
    color: {TEXT_SECONDARY};
    font-size: 11px;
    background: transparent;
}}

/* ── Prompt input widget ─────────────────────────────────────────────────── */
QFrame#promptInputWidget {{
    background: {BG_SURFACE};
    border: 1px solid {BORDER_DEFAULT};
    border-radius: {RADIUS_LG}px;
}}

QPlainTextEdit#chatInputEditor {{
    background: {BG_SURFACE};
    color: {TEXT_PRIMARY};
    border: none;
    border-radius: 0px;
    padding: 0px;
    selection-background-color: rgba(99, 102, 241, 0.24);
}}

QPlainTextEdit#chatInputEditor:focus {{
    border: none;
}}

/* ── Send button (round, inside prompt widget) ───────────────────────────── */
QPushButton#sendButtonRound {{
    background: {BG_SURFACE};
    color: #ffffff;
    border: none;
    border-radius: 16px;
    padding: 0;
    min-width: 32px;
    max-width: 32px;
    min-height: 32px;
    max-height: 32px;
}}

QPushButton#sendButtonRound:hover {{
    background: {BG_SURFACE};
}}

QPushButton#sendButtonRound[filled="true"] {{
    background: {ACCENT};
}}

QPushButton#sendButtonRound[filled="true"]:hover {{
    background: {ACCENT};
}}

QPushButton#sendButtonRound:pressed {{
    background: #4f51d4;
}}

QPushButton#sendButtonRound:disabled {{
    background: rgba(99, 102, 241, 0.20);
}}

/* ── Mode dropdown (inside prompt widget) ───────────────────────────────── */
QComboBox#modeDropdown {{
    background: {BG_SURFACE};
    color: {TEXT_SECONDARY};
    border: 1px solid {BORDER_DEFAULT};
    border-radius: {RADIUS_SM}px;
    padding: 3px 8px;
    font-size: 11px;
    font-weight: 500;
    min-width: 70px;
    max-width: 80px;
}}

QComboBox#modeDropdown:hover {{
    border-color: {BORDER_STRONG};
    color: {TEXT_PRIMARY};
}}

QComboBox#modeDropdown:focus {{
    border-color: rgba(99, 102, 241, 0.50);
}}

QComboBox#modeDropdown::drop-down {{
    border: none;
    width: 14px;
}}

/* ── Inline buttons (chat header) ────────────────────────────────────────── */
QPushButton#inlineButton {{
    background: rgba(255, 255, 255, 0.04);
    color: {TEXT_SECONDARY};
    border: 1px solid {BORDER_DEFAULT};
    border-radius: {RADIUS_MD}px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 500;
}}

QPushButton#inlineButton:hover {{
    background: rgba(255, 255, 255, 0.07);
    color: {TEXT_PRIMARY};
    border-color: {BORDER_STRONG};
}}

QPushButton#inlineButton:disabled {{
    color: {TEXT_DISABLED};
    border-color: {BORDER_SUBTLE};
}}

/* ── Default buttons ─────────────────────────────────────────────────────── */
QPushButton {{
    background: {ACCENT};
    color: #ffffff;
    border: none;
    padding: 5px 14px;
    border-radius: {RADIUS_MD}px;
    font-size: 12px;
    font-weight: 600;
}}

QPushButton:hover {{
    background: {ACCENT_HOVER};
}}

QPushButton:pressed {{
    background: #4f51d4;
}}

QPushButton:disabled {{
    background: rgba(99, 102, 241, 0.18);
    color: rgba(255, 255, 255, 0.30);
}}

/* ── ComboBox ────────────────────────────────────────────────────────────── */
QComboBox {{
    background: {BG_ELEVATED};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_DEFAULT};
    border-radius: {RADIUS_MD}px;
    padding: 4px 10px;
    min-width: 80px;
    font-size: 12px;
}}

QComboBox:hover {{
    border-color: {BORDER_STRONG};
}}

QComboBox:focus {{
    border-color: rgba(99, 102, 241, 0.50);
}}

QComboBox::drop-down {{
    border: none;
    width: 18px;
}}

QComboBox QAbstractItemView {{
    background: {BG_ELEVATED};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_DEFAULT};
    border-radius: {RADIUS_MD}px;
    selection-background-color: {ACCENT_MUTED_QT};
    selection-color: {TEXT_PRIMARY};
    outline: none;
    padding: 4px;
}}

/* ── Splitter ────────────────────────────────────────────────────────────── */
QSplitter#mainSplitter::handle,
QSplitter::handle {{
    background: {BORDER_SUBTLE};
    width: 1px;
    height: 1px;
}}

QSplitter#mainSplitter::handle:hover,
QSplitter::handle:hover {{
    background: rgba(99, 102, 241, 0.40);
}}

/* ── Scrollbars ──────────────────────────────────────────────────────────── */
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    border: none;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background: rgba(255, 255, 255, 0.10);
    border-radius: 4px;
    min-height: 24px;
}}

QScrollBar::handle:vertical:hover {{
    background: rgba(255, 255, 255, 0.18);
}}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar:horizontal {{
    background: transparent;
    height: 8px;
    border: none;
    margin: 0;
}}

QScrollBar::handle:horizontal {{
    background: rgba(255, 255, 255, 0.10);
    border-radius: 4px;
    min-width: 24px;
}}

QScrollBar::handle:horizontal:hover {{
    background: rgba(255, 255, 255, 0.18);
}}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* ── Status bar ──────────────────────────────────────────────────────────── */
QStatusBar {{
    background: {BG_BASE};
    color: {TEXT_SECONDARY};
    font-size: 11px;
    border-top: 1px solid {BORDER_SUBTLE};
    min-height: {STATUS_BAR_H}px;
    max-height: {STATUS_BAR_H}px;
}}

QStatusBar QLabel {{
    color: {TEXT_SECONDARY};
    background: transparent;
    padding: 2px 6px;
}}

QStatusBar::item {{
    border: none;
}}

QLabel#statusLabel {{
    color: {TEXT_PRIMARY};
    background: transparent;
}}

QLabel#tokenStatusLabel {{
    color: {TEXT_TERTIARY};
    font-size: 11px;
    background: transparent;
}}

/* ── Chat history panel ──────────────────────────────────────────────────── */
QWidget#chatHistoryPanel {{
    background: {BG_SURFACE};
}}

QScrollArea#chatHistoryScroll {{
    background: transparent;
    border: none;
}}

QScrollArea#chatHistoryScroll > QWidget > QWidget {{
    background: transparent;
}}

QPushButton#newChatButton {{
    background: transparent;
    color: {TEXT_SECONDARY};
    border: 1px dashed rgba(255, 255, 255, 0.14);
    border-radius: {RADIUS_LG}px;
    padding: 8px 14px;
    font-size: 12px;
    font-weight: 500;
    text-align: left;
}}

QPushButton#newChatButton:hover {{
    background: rgba(255, 255, 255, 0.04);
    color: {TEXT_PRIMARY};
    border-color: rgba(255, 255, 255, 0.22);
}}

QFrame#chatCard {{
    background: {BG_ELEVATED};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: {RADIUS_LG}px;
}}

QFrame#chatCard:hover {{
    background: {BG_HOVER};
    border-color: {BORDER_DEFAULT};
}}

QFrame#chatCardActive {{
    background: {ACCENT_ACTIVE_QT};
    border: 1px solid rgba(99, 102, 241, 0.35);
    border-radius: {RADIUS_LG}px;
    border-left: 3px solid {ACCENT};
}}

QLabel#chatCardTitle {{
    color: {TEXT_PRIMARY};
    font-size: 12px;
    font-weight: 600;
    background: transparent;
}}

QLabel#chatCardPreview {{
    color: {TEXT_SECONDARY};
    font-size: 11px;
    background: transparent;
}}

QLabel#chatCardDate {{
    color: {TEXT_TERTIARY};
    font-size: 10px;
    background: transparent;
}}

/* ── Tooltip ─────────────────────────────────────────────────────────────── */
QToolTip {{
    background: {BG_ELEVATED};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_DEFAULT};
    border-radius: {RADIUS_SM}px;
    padding: 4px 8px;
    font-size: 11px;
}}

/* ── Message box ─────────────────────────────────────────────────────────── */
QMessageBox {{
    background: {BG_ELEVATED};
    color: {TEXT_PRIMARY};
}}

QMessageBox QLabel {{
    color: {TEXT_PRIMARY};
}}

/* ── Input dialog ────────────────────────────────────────────────────────── */
QInputDialog {{
    background: {BG_ELEVATED};
    color: {TEXT_PRIMARY};
}}

QLineEdit {{
    background: {BG_ELEVATED};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_DEFAULT};
    border-radius: {RADIUS_MD}px;
    padding: 6px 10px;
    selection-background-color: rgba(99, 102, 241, 0.24);
}}

QLineEdit:focus {{
    border-color: rgba(99, 102, 241, 0.50);
}}
"""
