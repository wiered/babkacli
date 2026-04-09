STYLE_SHEET = """
/* ── Global ─────────────────────────────────────────── */
QMainWindow, QWidget {
    background: #161618;
    color: #d0d0d0;
}

QLabel {
    color: #d0d0d0;
    background: transparent;
}

/* ── Title bar ───────────────────────────────────────── */
QWidget#titleBar {
    background: #1c1c1f;
    border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

QWidget#titleBarControls {
    background: transparent;
}

QLabel#titleIconLabel {
    background: transparent;
}

QLabel#titleLabel {
    color: #e0e0e0;
    font-weight: 600;
    font-size: 14px;
    letter-spacing: 0.02em;
    background: transparent;
}

QLabel#workspacePathLabel {
    color: #5a5a64;
    font-size: 11px;
    background: transparent;
}

QLabel#modelBadge {
    color: #60a5fa;
    font-size: 10px;
    font-weight: 500;
    background: rgba(59, 130, 246, 0.12);
    border: 1px solid rgba(59, 130, 246, 0.25);
    border-radius: 10px;
    padding: 2px 10px;
}

QToolButton#titleBtn,
QToolButton#titleBtnClose {
    background: transparent;
    border: none;
    border-radius: 8px;
    padding: 2px;
}

QToolButton#titleBtn:hover {
    background: rgba(255, 255, 255, 0.08);
}

QToolButton#titleBtn:pressed {
    background: rgba(255, 255, 255, 0.04);
}

QToolButton#titleBtnClose:hover {
    background: rgba(196, 43, 28, 0.30);
}

QToolButton#titleBtnClose:pressed {
    background: rgba(196, 43, 28, 0.18);
}

/* ── Panel headers ───────────────────────────────────── */
QLabel#panelHeader {
    background: #1c1c1f;
    color: #8a8a96;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.10em;
    padding: 0 12px;
    border-bottom: 1px solid #2a2a2e;
}

/* ── File Explorer ───────────────────────────────────── */
QTreeView {
    background: #1c1c1f;
    color: #d0d0d0;
    border: none;
    outline: none;
    selection-background-color: transparent;
    selection-color: #ffffff;
}

QTreeView::item {
    padding: 3px 6px;
    height: 24px;
    border: none;
    border-radius: 4px;
}

QTreeView::item:hover {
    background: rgba(255, 255, 255, 0.04);
}

QTreeView::item:selected {
    background: rgba(59, 130, 246, 0.18);
    color: #e0e0e0;
}

/* ── File tab bar ────────────────────────────────────── */
QFrame#fileTabBar {
    background: #222226;
    border-bottom: 1px solid #2a2a2e;
}

QLabel#fileLabel {
    color: #d0d0d0;
    font-size: 12px;
    font-weight: 500;
    background: transparent;
}

QPushButton#editorInlineButton {
    background: transparent;
    color: #8a8a96;
    border: 1px solid #3a3a40;
    border-radius: 6px;
    padding: 2px 10px;
    font-size: 11px;
}

QPushButton#editorInlineButton:hover {
    background: rgba(255, 255, 255, 0.06);
    color: #d0d0d0;
    border-color: #4a4a52;
}

QPushButton#editorInlineButton:disabled {
    color: #3a3a40;
    border-color: #2a2a2e;
}

/* ── Editor ──────────────────────────────────────────── */
QPlainTextEdit {
    background: #1a1a1d;
    color: #d4d4d8;
    border: none;
    selection-background-color: rgba(59, 130, 246, 0.30);
    selection-color: #ffffff;
}

/* ── Chat header ─────────────────────────────────────── */
QFrame#chatHeaderFrame {
    background: #1c1c1f;
    border-bottom: 1px solid #2a2a2e;
    border-left: 1px solid #2a2a2e;
}

QLabel#chatHeaderLabel {
    color: #8a8a96;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.10em;
    background: transparent;
}

QLabel#modeLabelSmall {
    color: #5a5a64;
    font-size: 11px;
    background: transparent;
}

/* ── Chat history ────────────────────────────────────── */
QTextBrowser {
    background: #161618;
    color: #d0d0d0;
    border: none;
    border-left: 1px solid #2a2a2e;
}

/* ── Chat input frame ────────────────────────────────── */
QFrame#chatInputFrame {
    background: #1c1c1f;
    border-top: 1px solid #2a2a2e;
    border-left: 1px solid #2a2a2e;
}

QFrame#chatInputFrame QPlainTextEdit {
    background: #222226;
    color: #d4d4d8;
    border: 1px solid #3a3a40;
    border-radius: 6px;
    padding: 6px 8px;
    selection-background-color: rgba(59, 130, 246, 0.30);
}

QFrame#chatInputFrame QPlainTextEdit:focus {
    border-color: #3b82f6;
}

QPlainTextEdit#terminalOutput,
QTextEdit#terminalOutput {
    background: #111114;
    color: #d4d4d4;
    border: none;
    border-top: 1px solid #2a2a2e;
}

QLabel#hintLabel {
    color: #3a3a40;
    font-size: 11px;
    background: transparent;
}

/* ── Send button ─────────────────────────────────────── */
QPushButton#sendButton {
    background: #3b82f6;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 4px 18px;
    font-size: 12px;
    font-weight: 600;
    min-width: 72px;
}

QPushButton#sendButton:hover {
    background: #2563eb;
}

QPushButton#sendButton:pressed {
    background: #1d4ed8;
}

QPushButton#sendButton:disabled {
    background: #222226;
    color: #4a4a52;
}

/* ── inlineButton (chat header buttons) ──────────────── */
QPushButton#inlineButton {
    background: transparent;
    color: #8a8a96;
    border: 1px solid #3a3a40;
    border-radius: 6px;
    padding: 2px 10px;
    font-size: 11px;
}

QPushButton#inlineButton:hover {
    background: rgba(255, 255, 255, 0.06);
    color: #d0d0d0;
    border-color: #4a4a52;
}

QPushButton#inlineButton:disabled {
    color: #3a3a40;
    border-color: #2a2a2e;
}

/* ── Default buttons ─────────────────────────────────── */
QPushButton {
    background: #3b82f6;
    color: #ffffff;
    border: none;
    padding: 5px 14px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 500;
}

QPushButton:hover {
    background: #2563eb;
}

QPushButton:pressed {
    background: #1d4ed8;
}

QPushButton:disabled {
    background: #222226;
    color: #4a4a52;
}

/* ── ComboBox ────────────────────────────────────────── */
QComboBox {
    background: #222226;
    color: #d0d0d0;
    border: 1px solid #3a3a40;
    border-radius: 6px;
    padding: 3px 8px;
    min-width: 80px;
    font-size: 12px;
}

QComboBox:hover {
    border-color: #4a4a52;
}

QComboBox::drop-down {
    border: none;
    width: 18px;
}

QComboBox QAbstractItemView {
    background: #1c1c1f;
    color: #d0d0d0;
    border: 1px solid #3a3a40;
    selection-background-color: rgba(59, 130, 246, 0.18);
}

/* ── Splitter ────────────────────────────────────────── */
QSplitter::handle {
    background: #2a2a2e;
    width: 1px;
    height: 1px;
}

QSplitter::handle:hover {
    background: #3b82f6;
}

/* ── Scrollbars ──────────────────────────────────────── */
QScrollBar:vertical {
    background: transparent;
    width: 6px;
    border: none;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: rgba(255, 255, 255, 0.10);
    border-radius: 3px;
    min-height: 24px;
}

QScrollBar::handle:vertical:hover {
    background: rgba(255, 255, 255, 0.18);
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background: transparent;
    height: 6px;
    border: none;
    margin: 0;
}

QScrollBar::handle:horizontal {
    background: rgba(255, 255, 255, 0.10);
    border-radius: 3px;
    min-width: 24px;
}

QScrollBar::handle:horizontal:hover {
    background: rgba(255, 255, 255, 0.18);
}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {
    width: 0;
}

/* ── Status bar ──────────────────────────────────────── */
QStatusBar {
    background: #1c1c1f;
    color: #8a8a96;
    font-size: 11px;
    border-top: 1px solid #2a2a2e;
}

QStatusBar QLabel {
    color: #8a8a96;
    background: transparent;
    padding: 2px 6px;
}

QStatusBar::item {
    border: none;
}

QLabel#statusLabel {
    color: #d0d0d0;
    background: transparent;
}

QLabel#tokenStatusLabel {
    color: #4a4a52;
    font-size: 11px;
    background: transparent;
}

"""
