STYLE_SHEET = """
/* ── Global ─────────────────────────────────────────── */
QMainWindow, QWidget {
    background: #1a1a1a;
    color: #cccccc;
}

QLabel {
    color: #cccccc;
    background: transparent;
}

/* ── Title bar ───────────────────────────────────────── */
QWidget#titleBar {
    background: #1e1e1e;
    border-bottom: 1px solid #2a2a2a;
}

QWidget#titleBarControls {
    background: transparent;
}

QLabel#titleIconLabel {
    background: transparent;
}

QLabel#titleLabel {
    color: #d4d4d4;
    font-weight: 600;
    font-size: 13px;
    letter-spacing: 0.02em;
    background: transparent;
}

QLabel#workspacePathLabel {
    color: #555555;
    font-size: 11px;
    background: transparent;
}

QLabel#modelBadge {
    color: #6b9fd4;
    font-size: 10px;
    font-weight: 500;
    background: transparent;
    border: 1px solid #2e4a66;
    border-radius: 8px;
    padding: 1px 7px;
}

QToolButton#titleBtn,
QToolButton#titleBtnClose {
    background: transparent;
    border: none;
    border-radius: 6px;
    padding: 2px;
}

QToolButton#titleBtn:hover {
    background: rgba(255, 255, 255, 0.07);
}

QToolButton#titleBtn:pressed {
    background: rgba(255, 255, 255, 0.04);
}

QToolButton#titleBtnClose:hover {
    background: rgba(196, 43, 28, 0.25);
}

QToolButton#titleBtnClose:pressed {
    background: rgba(196, 43, 28, 0.15);
}

/* ── Panel headers ───────────────────────────────────── */
QLabel#panelHeader {
    background: #252526;
    color: #bbbbbb;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.08em;
    padding: 0 12px;
    border-bottom: 1px solid #3c3c3c;
}

/* ── File Explorer ───────────────────────────────────── */
QTreeView {
    background: #252526;
    color: #cccccc;
    border: none;
    outline: none;
    selection-background-color: #094771;
    selection-color: #ffffff;
}

QTreeView::item {
    padding: 2px 4px;
    height: 22px;
    border: none;
}

QTreeView::item:hover {
    background: #2a2d2e;
}

QTreeView::item:selected {
    background: #094771;
}

/* ── File tab bar ────────────────────────────────────── */
QFrame#fileTabBar {
    background: #2d2d2d;
    border-bottom: 1px solid #3c3c3c;
}

QLabel#fileLabel {
    color: #cccccc;
    font-size: 12px;
    font-weight: 500;
    background: transparent;
}

QPushButton#inlineButton {
    background: transparent;
    color: #858585;
    border: 1px solid #484848;
    border-radius: 3px;
    padding: 2px 10px;
    font-size: 11px;
}

QPushButton#inlineButton:hover {
    background: #3c3c3c;
    color: #cccccc;
    border-color: #666;
}

QPushButton#inlineButton:disabled {
    color: #484848;
    border-color: #383838;
}

/* ── Editor ──────────────────────────────────────────── */
QPlainTextEdit {
    background: #1e1e1e;
    color: #d4d4d4;
    border: none;
    selection-background-color: #264f78;
    selection-color: #ffffff;
}

/* ── Chat header ─────────────────────────────────────── */
QFrame#chatHeaderFrame {
    background: #252526;
    border-bottom: 1px solid #3c3c3c;
    border-left: 1px solid #3c3c3c;
}

QLabel#chatHeaderLabel {
    color: #bbbbbb;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.08em;
    background: transparent;
}

QLabel#modeLabelSmall {
    color: #777;
    font-size: 11px;
    background: transparent;
}

/* ── Chat history ────────────────────────────────────── */
QTextBrowser {
    background: #1a1a1a;
    color: #cccccc;
    border: none;
    border-left: 1px solid #3c3c3c;
}

/* ── Chat input frame ────────────────────────────────── */
QFrame#chatInputFrame {
    background: #252526;
    border-top: 1px solid #3c3c3c;
    border-left: 1px solid #3c3c3c;
}

QFrame#chatInputFrame QPlainTextEdit {
    background: #2d2d2d;
    color: #d4d4d4;
    border: 1px solid #3c3c3c;
    border-radius: 6px;
    padding: 6px 8px;
    selection-background-color: #264f78;
}

QFrame#chatInputFrame QPlainTextEdit:focus {
    border-color: #0078d4;
}

QPlainTextEdit#terminalOutput,
QTextEdit#terminalOutput {
    background: #111111;
    color: #d4d4d4;
    border: none;
    border-top: 1px solid #262626;
}

QLabel#hintLabel {
    color: #484848;
    font-size: 11px;
    background: transparent;
}

/* ── Send button ─────────────────────────────────────── */
QPushButton#sendButton {
    background: #0078d4;
    color: #ffffff;
    border: none;
    border-radius: 5px;
    padding: 4px 18px;
    font-size: 12px;
    font-weight: 600;
    min-width: 72px;
}

QPushButton#sendButton:hover {
    background: #106ebe;
}

QPushButton#sendButton:pressed {
    background: #0d5a9e;
}

QPushButton#sendButton:disabled {
    background: #1e3a5f;
    color: #4a6a8a;
}

/* ── Default buttons ─────────────────────────────────── */
QPushButton {
    background: #0e639c;
    color: #ffffff;
    border: none;
    padding: 5px 14px;
    border-radius: 4px;
    font-size: 12px;
    font-weight: 500;
}

QPushButton:hover {
    background: #1177bb;
}

QPushButton:pressed {
    background: #0d5189;
}

QPushButton:disabled {
    background: #2d2d2d;
    color: #555;
}

/* ── ComboBox ────────────────────────────────────────── */
QComboBox {
    background: #3c3c3c;
    color: #cccccc;
    border: 1px solid #555;
    border-radius: 4px;
    padding: 3px 8px;
    min-width: 80px;
    font-size: 12px;
}

QComboBox:hover {
    border-color: #777;
}

QComboBox::drop-down {
    border: none;
    width: 18px;
}

QComboBox QAbstractItemView {
    background: #252526;
    color: #cccccc;
    border: 1px solid #555;
    selection-background-color: #094771;
}

/* ── Splitter ────────────────────────────────────────── */
QSplitter::handle {
    background: #3c3c3c;
    width: 1px;
    height: 1px;
}

QSplitter::handle:hover {
    background: #0078d4;
}

/* ── Scrollbars ──────────────────────────────────────── */
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    border: none;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: #424242;
    border-radius: 4px;
    min-height: 24px;
}

QScrollBar::handle:vertical:hover {
    background: #5a5a5a;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background: transparent;
    height: 8px;
    border: none;
    margin: 0;
}

QScrollBar::handle:horizontal {
    background: #424242;
    border-radius: 4px;
    min-width: 24px;
}

QScrollBar::handle:horizontal:hover {
    background: #5a5a5a;
}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {
    width: 0;
}

/* ── Status bar ──────────────────────────────────────── */
QStatusBar {
    background: #0078d4;
    color: #ffffff;
    font-size: 11px;
}

QStatusBar QLabel {
    color: #ffffff;
    background: transparent;
    padding: 2px 6px;
}

QStatusBar::item {
    border: none;
}

"""
