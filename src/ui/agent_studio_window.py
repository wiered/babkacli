"""Agent Studio Window for the BabkaCode."""

from __future__ import annotations

import argparse
import html
import json
import logging
import os
import time
from urllib.parse import unquote

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from azure.ai.inference.models import SystemMessage, UserMessage
from dotenv import load_dotenv
from PySide6.QtCore import QDir, QEvent, QModelIndex, QObject, Qt, QThread, QUrl
from PySide6.QtGui import QAction, QCloseEvent, QDesktopServices, QFont, QKeySequence, QMouseEvent, QShowEvent
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileSystemModel,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStatusBar,
    QPlainTextEdit,
    QToolBar,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

if __package__ in {None, ""}:
    import sys

    sys.path.append(str(Path(__file__).resolve().parents[1]))

    from src.ui.interactive_terminal import InteractiveTerminal
    from src.ui.terminal import TerminalController
    from src.ui.ui_utils import SUPPORTED_MODES, normalize_mode, format_json
    from src.ui.agent_worker import AgentWorker
    from src.ui.chat_webview import ChatWebViewHost
    from src.ui.python_highlighter import PythonHighlighter
    from src.ui.title_bar import build_app_icon, TitleBar
    from src.ui.native_chrome_win32 import LowLevelNativeChromeMixin
    from src.ui.ui_utils import build_messages, build_nerd_font, ChatEvent
    from src.ui.style import STYLE_SHEET
    from src.ui.html_generator import render_chat_history, get_copy_block

else:
    from ..ui.interactive_terminal import InteractiveTerminal
    from ..ui.terminal import TerminalController
    from ..ui.ui_utils import SUPPORTED_MODES, normalize_mode, format_json
    from ..ui.agent_worker import AgentWorker
    from ..ui.chat_webview import ChatWebViewHost
    from ..ui.python_highlighter import PythonHighlighter
    from ..ui.title_bar import build_app_icon, TitleBar
    from ..ui.native_chrome_win32 import LowLevelNativeChromeMixin
    from ..ui.ui_utils import build_messages, build_nerd_font, ChatEvent
    from ..ui.style import STYLE_SHEET
    from ..ui.html_generator import render_chat_history, get_copy_block

logger = logging.getLogger(__name__)


def _webview_layout_diag_enabled() -> bool:
    """Diagnostic layout (gap, colors, hit logging). Env BABKA_WEBVIEW_DIAG=0 disables."""
    raw = os.environ.get("BABKA_WEBVIEW_DIAG", os.environ.get("BABKA_WEBENGINE_DIAG", "1"))
    v = raw.strip().lower()
    return v in ("1", "true", "yes", "on")


def _enum_log_value(value: object) -> object:
    """Return a stable loggable value for Qt enums across PySide versions."""
    raw = getattr(value, "value", None)
    if isinstance(raw, int):
        return raw
    try:
        return int(value)
    except (TypeError, ValueError):
        return str(value)


class _WebViewDiagHitLogFilter(QObject):
    """Logs childAt / titlebar / synthetic native hit-test for mouse presses in the main window."""

    def __init__(self, window: AgentStudioWindow) -> None:
        super().__init__(window)
        self._window = window

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if event.type() != QEvent.Type.MouseButtonPress:
            return False
        if not isinstance(event, QMouseEvent):
            return False
        w = self._window
        if not w.isVisible():
            return False
        gp = event.globalPosition().toPoint()
        lp = w.mapFromGlobal(gp)
        if not w.rect().contains(lp):
            return False
        child = w.childAt(lp)
        child_name = child.objectName() if child is not None else ""
        child_cls = type(child).__name__ if child is not None else "None"
        in_tb = w._point_in_titlebar_drag_region(lp.x(), lp.y())
        ht = None
        if sys.platform == "win32" and hasattr(w, "_hit_test_native"):
            ht = w._hit_test_native(lp.x(), lp.y())
        cw = w.centralWidget()
        child_cw = None
        if cw is not None:
            lp_cw = cw.mapFromGlobal(gp)
            child_cw = cw.childAt(lp_cw)
        logger.info(
            "webview_diag hit: button=%s global=%s local_win=%s child=%s (%s) "
            "central_child=%s in_titlebar_drag=%s win32_ht=%s watched=%s",
            _enum_log_value(event.button()),
            (gp.x(), gp.y()),
            (lp.x(), lp.y()),
            child_name,
            child_cls,
            type(child_cw).__name__ if child_cw is not None else None,
            in_tb,
            ht,
            type(watched).__name__,
        )
        return False


def _format_duration(seconds: float) -> str:
    total = int(seconds)
    if total < 60:
        return f"{total}s"
    mins, secs = divmod(total, 60)
    return f"{mins}m {secs}s" if secs else f"{mins}m"


class AgentStudioWindow(QMainWindow, LowLevelNativeChromeMixin):
    """Three-pane workspace view: files, editor, and agent chat."""

    def __init__(self, *, workspace: Path, model: str, max_steps: int) -> None:
        super().__init__()
        self._workspace = workspace
        self._model = model
        self._max_steps = max_steps
        self._mode = "agent"
        self._messages: list[Any] = build_messages(self._mode)
        self._worker_thread: QThread | None = None
        self._worker: AgentWorker | None = None
        self._loading_file = False
        self._current_file: Path | None = None
        self._dirty = False
        self._chat_events: list[ChatEvent] = []
        self._collapsed_blocks: set[str] = set()
        self._next_block_id = 1
        self._terminal_visible = False
        self._terminal: TerminalController | None = None
        self._work_group_id: str = ""
        self._work_start_time: float = 0.0
        self._work_group_header: ChatEvent | None = None
        self._native_chrome_applied = False
        self._title_bar: TitleBar | None = None
        self._webview_diag = _webview_layout_diag_enabled()
        self._diag_hit_filter: QObject | None = None
        self._root_container: QWidget | None = None
        self._title_content_gap: QWidget | None = None
        self._chat_web_container: QWidget | None = None

        self.setWindowTitle("BabkaCode")
        self.setWindowIcon(build_app_icon())

        # Same order as prototype DemoWindow: build UI and size first, then
        # setWindowFlags last (before show), so the widget tree exists before the
        # frameless/native window is configured.
        self._build_ui()
        self.resize(1520, 920)
        self._configure_window_chrome()
        self._apply_style()
        if self._webview_diag:
            self._diag_hit_filter = _WebViewDiagHitLogFilter(self)
            app_inst = QApplication.instance()
            if app_inst is not None:
                app_inst.installEventFilter(self._diag_hit_filter)
        self._open_initial_file()

    def _configure_window_chrome(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowMinMaxButtonsHint
            | Qt.WindowType.WindowSystemMenuHint,
        )

    def _build_ui(self) -> None:
        model_short = self._model.split("/")[-1] if "/" in self._model else self._model
        # ── File Explorer panel ───────────────────────────────────────────────
        explorer_label = QLabel("  EXPLORER")
        explorer_label.setObjectName("panelHeader")
        explorer_label.setFixedHeight(32)

        self._tree_model = QFileSystemModel(self)
        self._tree_model.setRootPath(str(self._workspace))
        self._tree_model.setFilter(QDir.AllEntries | QDir.NoDotAndDotDot | QDir.AllDirs | QDir.Files)
        self._tree_model.setNameFilterDisables(False)
        self._tree_model.sort(0, Qt.SortOrder.AscendingOrder)

        self._tree_view = QTreeView(self)
        self._tree_view.setModel(self._tree_model)
        self._tree_view.setRootIndex(self._tree_model.index(str(self._workspace)))
        self._tree_view.setHeaderHidden(True)
        self._tree_view.setAnimated(False)
        self._tree_view.setIndentation(16)
        self._tree_view.setSelectionBehavior(QTreeView.SelectionBehavior.SelectRows)
        self._tree_view.setUniformRowHeights(True)
        for column in range(1, 4):
            self._tree_view.hideColumn(column)
        self._tree_view.clicked.connect(self._handle_tree_clicked)

        explorer_panel = QWidget(self)
        exp_layout = QVBoxLayout(explorer_panel)
        exp_layout.setContentsMargins(0, 0, 0, 0)
        exp_layout.setSpacing(0)
        exp_layout.addWidget(explorer_label)
        exp_layout.addWidget(self._tree_view, 1)

        # ── Editor panel ──────────────────────────────────────────────────────
        self._file_label = QLabel("No file open")
        self._file_label.setObjectName("fileLabel")

        self._save_action = QAction("Save", self)
        self._save_action.setShortcut(QKeySequence.Save)
        self._save_action.triggered.connect(self._save_current_file)
        self.addAction(self._save_action)

        self._save_button = QPushButton("Save")
        self._save_button.setObjectName("inlineButton")
        self._save_button.setFixedHeight(26)
        self._save_button.clicked.connect(self._save_current_file)

        self._toggle_terminal_button = QPushButton("Terminal")
        self._toggle_terminal_button.setObjectName("inlineButton")
        self._toggle_terminal_button.setFixedHeight(26)
        self._toggle_terminal_button.clicked.connect(self._toggle_terminal)

        file_tab_bar = QFrame(self)
        file_tab_bar.setObjectName("fileTabBar")
        file_tab_bar.setFixedHeight(36)
        tab_layout = QHBoxLayout(file_tab_bar)
        tab_layout.setContentsMargins(12, 0, 8, 0)
        tab_layout.setSpacing(8)
        tab_layout.addWidget(self._file_label, 1)
        tab_layout.addWidget(self._toggle_terminal_button, 0)
        tab_layout.addWidget(self._save_button, 0)

        fixed_font = build_nerd_font(12)

        self._editor = QPlainTextEdit(self)
        self._editor.textChanged.connect(self._mark_dirty)
        self._editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._editor.setFont(fixed_font)
        self._editor.setTabStopDistance(self._editor.fontMetrics().horizontalAdvance(" ") * 4)
        self._python_highlighter = PythonHighlighter(self._editor.document())

        self._terminal_output = InteractiveTerminal(self)
        self._terminal_output.setFont(fixed_font)
        self._terminal_output.setObjectName("terminalOutput")
        self._terminal_output.setPlaceholderText("Interactive ANSI/VT100 terminal")
        self._terminal_output.data_ready.connect(self._write_terminal_data)
        self._terminal_output.resize_requested.connect(self._resize_terminal)
        self._terminal_output.interrupt_requested.connect(self._interrupt_terminal)

        terminal_header = QLabel("  TERMINAL / PWSH")
        terminal_header.setObjectName("panelHeader")
        terminal_header.setFixedHeight(32)

        self._terminal_panel = QWidget(self)
        terminal_layout = QVBoxLayout(self._terminal_panel)
        terminal_layout.setContentsMargins(0, 0, 0, 0)
        terminal_layout.setSpacing(0)
        terminal_layout.addWidget(terminal_header)
        terminal_layout.addWidget(self._terminal_output, 1)
        self._terminal_panel.setVisible(False)

        self._editor_splitter = QSplitter(Qt.Orientation.Vertical, self)
        self._editor_splitter.addWidget(self._editor)
        self._editor_splitter.addWidget(self._terminal_panel)
        self._editor_splitter.setStretchFactor(0, 1)
        self._editor_splitter.setStretchFactor(1, 0)
        self._editor_splitter.setSizes([640, 0])

        editor_panel = QWidget(self)
        ed_layout = QVBoxLayout(editor_panel)
        ed_layout.setContentsMargins(0, 0, 0, 0)
        ed_layout.setSpacing(0)
        ed_layout.addWidget(file_tab_bar)
        ed_layout.addWidget(self._editor_splitter, 1)

        # ── Chat panel ────────────────────────────────────────────────────────
        chat_hdr_label = QLabel("AI ASSISTANT")
        chat_hdr_label.setObjectName("chatHeaderLabel")

        self._mode_selector = QComboBox(self)
        self._mode_selector.addItems(list(SUPPORTED_MODES))
        self._mode_selector.setCurrentText(self._mode)
        self._mode_selector.currentTextChanged.connect(self._handle_mode_changed)

        chat_hdr = QFrame(self)
        chat_hdr.setObjectName("chatHeaderFrame")
        chat_hdr.setFixedHeight(44)
        ch_layout = QHBoxLayout(chat_hdr)
        ch_layout.setContentsMargins(12, 0, 12, 0)
        ch_layout.setSpacing(8)
        ch_layout.addWidget(chat_hdr_label, 1)
        mode_lbl = QLabel("Mode:")
        mode_lbl.setObjectName("modeLabelSmall")
        ch_layout.addWidget(mode_lbl)
        ch_layout.addWidget(self._mode_selector)

        chat_panel = QWidget(self)

        # The WebView host lives only inside this container; 2 px margins keep the
        # embedded surface away from adjacent Qt widgets.
        self._chat_web_container = QWidget(chat_panel)
        self._chat_web_container.setObjectName("chatWebViewContainer")
        web_c_layout = QVBoxLayout(self._chat_web_container)
        web_c_layout.setContentsMargins(2, 2, 2, 2)
        web_c_layout.setSpacing(0)

        self._chat_history = ChatWebViewHost(self._chat_web_container)
        self._chat_history.anchor_activated.connect(self._handle_chat_anchor_clicked)
        self._chat_history.loadFinished.connect(self._scroll_chat_to_bottom)
        web_c_layout.addWidget(self._chat_history, 1)

        self._chat_input = QPlainTextEdit(self)
        self._update_chat_placeholder()
        self._chat_input.setFixedHeight(88)
        self._chat_input.setFont(fixed_font)
        self._chat_input.setTabChangesFocus(True)
        self._chat_input_shortcut = QAction(self)
        self._chat_input_shortcut.setShortcut(QKeySequence("Ctrl+Return"))
        self._chat_input_shortcut.triggered.connect(self._send_chat)
        self.addAction(self._chat_input_shortcut)
        self._chat_input_shortcut2 = QAction(self)
        self._chat_input_shortcut2.setShortcut(QKeySequence("Ctrl+Enter"))
        self._chat_input_shortcut2.triggered.connect(self._send_chat)
        self.addAction(self._chat_input_shortcut2)

        self._send_button = QPushButton("Send")
        self._send_button.setObjectName("sendButton")
        self._send_button.setFixedHeight(30)
        self._send_button.clicked.connect(self._send_chat)

        hint_lbl = QLabel("Ctrl+Enter")
        hint_lbl.setObjectName("hintLabel")
        send_row = QHBoxLayout()
        send_row.setContentsMargins(0, 0, 0, 0)
        send_row.addWidget(hint_lbl)
        send_row.addStretch()
        send_row.addWidget(self._send_button)

        chat_input_frame = QFrame(self)
        chat_input_frame.setObjectName("chatInputFrame")
        ci_layout = QVBoxLayout(chat_input_frame)
        ci_layout.setContentsMargins(10, 10, 10, 10)
        ci_layout.setSpacing(6)
        ci_layout.addWidget(self._chat_input)
        ci_layout.addLayout(send_row)

        cp_layout = QVBoxLayout(chat_panel)
        cp_layout.setContentsMargins(0, 0, 0, 0)
        cp_layout.setSpacing(0)
        cp_layout.addWidget(chat_hdr)
        cp_layout.addWidget(self._chat_web_container, 1)
        cp_layout.addWidget(chat_input_frame, 0)

        # ── Splitter ──────────────────────────────────────────────────────────
        self._splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self._splitter.addWidget(explorer_panel)
        self._splitter.addWidget(editor_panel)
        self._splitter.addWidget(chat_panel)
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setStretchFactor(2, 0)
        self._splitter.setSizes([240, 780, 500])

        # ── Custom title bar (native caption hidden via WM_NCCALCSIZE on Windows) ─
        self._title_bar = TitleBar(self)
        self._title_bar.set_metadata(
            title="BabkaCode",
            workspace=str(self._workspace),
            model=model_short,
        )

        # ── Root container ────────────────────────────────────────────────────
        container = QWidget(self)
        if self._webview_diag:
            container.setObjectName("diagRootContainer")
        self._root_container = container
        root = QVBoxLayout(container)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self._title_content_gap = QWidget(container)
        self._title_content_gap.setObjectName("titleContentGap")
        self._title_content_gap.setFixedHeight(2)
        gap_bg = "#888888" if self._webview_diag else "#1a1a1a"
        self._title_content_gap.setStyleSheet(f"background-color: {gap_bg};")
        root.addWidget(self._title_bar, 0)
        root.addWidget(self._title_content_gap, 0)
        root.addWidget(self._splitter, 1)
        self._root_layout = root
        self.setCentralWidget(container)

        self.titlebar_widget = self._title_bar
        # Same list shape as prototype DemoWindow: min, max, close, main client area.
        self.no_drag_widgets = [
            self._title_bar._min_button,
            self._title_bar._max_button,
            self._title_bar._close_button,
            self._splitter,
        ]

        # ── Status bar ────────────────────────────────────────────────────────
        self._status = QLabel("  Ready")
        self._status.setObjectName("statusLabel")
        self._status_bar = QStatusBar(self)
        self._status_bar.addWidget(self._status)
        self.setStatusBar(self._status_bar)
        self._set_status("Ready")

    def _apply_style(self) -> None:
        app = QApplication.instance()
        if app is not None:
            app.setStyle("Fusion")

        self.setStyleSheet(
            STYLE_SHEET
        )
        self._apply_webview_diag_overrides()

    def _apply_webview_diag_overrides(self) -> None:
        """Bold diagnostic chrome: red title strip, gray client, blue WebView frame."""
        if not self._webview_diag:
            return
        if self._title_bar is not None:
            self._title_bar.setStyleSheet(
                """
                QWidget#titleBar {
                    background: #cc0000;
                    border-bottom: 2px solid #990000;
                }
                QWidget#titleBarControls { background: transparent; }
                QLabel#titleIconLabel, QLabel#titleLabel { color: #ffffff; background: transparent; }
                QLabel#workspacePathLabel { color: #eeeeee; background: transparent; }
                QLabel#modelBadge {
                    color: #ffffff;
                    background: rgba(0,0,0,0.25);
                    border: 1px solid #ffffff;
                }
                QToolButton#titleBtn, QToolButton#titleBtnClose {
                    background: transparent;
                    border: none;
                }
                QToolButton#titleBtn:hover { background: rgba(255,255,255,0.2); }
                QToolButton#titleBtnClose:hover { background: rgba(0,0,0,0.35); }
                """
            )
        if self._root_container is not None:
            self._root_container.setStyleSheet(
                "QWidget#diagRootContainer { background-color: #808080; }"
            )
        if self._chat_web_container is not None:
            self._chat_web_container.setStyleSheet(
                """
                QWidget#chatWebViewContainer {
                    border: 3px solid #0066ff;
                    background-color: #505050;
                }
                """
            )

    def _set_status(self, text: str) -> None:
        self._status.setText(f"  {text}")

    def changeEvent(self, event) -> None:  # noqa: N802 - Qt callback signature
        super().changeEvent(event)
        if self._title_bar is not None:
            self._title_bar.sync_window_state()

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 - Qt callback signature
        super().showEvent(event)
        if not self._native_chrome_applied and sys.platform == "win32":
            self._native_chrome_applied = True
            self._apply_native_styles()

    def _remove_diag_hit_filter(self) -> None:
        if self._diag_hit_filter is not None:
            app_inst = QApplication.instance()
            if app_inst is not None:
                app_inst.removeEventFilter(self._diag_hit_filter)
            self._diag_hit_filter.deleteLater()
            self._diag_hit_filter = None

    def nativeEvent(self, eventType, message):  # noqa: N802 - Qt callback signature
        if sys.platform == "win32":
            result = self._process_native_event(message)
            if result is not None:
                return result
        return super().nativeEvent(eventType, message)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        # Same as prototype DemoWindow.mouseDoubleClickEvent (native chrome unchanged).
        if event.button() == Qt.MouseButton.LeftButton:
            p = event.position().toPoint()
            if self._point_in_titlebar_drag_region(p.x(), p.y()):
                if self._title_bar is not None:
                    self._title_bar._handle_maximize_restore()
                event.accept()
                return
        super().mouseDoubleClickEvent(event)

    def _start_terminal(self) -> None:
        if self._terminal is None:
            self._terminal = TerminalController(self)
            self._terminal.output_ready.connect(self._append_terminal_text)
            self._terminal.error.connect(lambda msg: self._append_terminal_text(f"\n[terminal error] {msg}\n"))

        if self._terminal.is_running():
            return

        columns, rows = self._terminal_output.terminal_size()
        self._terminal.start(cwd=str(self._workspace), rows=rows, columns=columns)
        if not self._terminal.is_running():
            self._terminal_output.append_output("Failed to start interactive terminal.\n")
            return

        reset_message = f"PowerShell started in {self._workspace}."
        self._terminal_output.reset_terminal("")
        backend = self._terminal.backend_name() or "unknown"
        self._set_status(f"Terminal started ({backend})")

    def _append_terminal_text(self, text: str) -> None:
        if not text:
            return
        self._terminal_output.append_output(text)

    def _toggle_terminal(self) -> None:
        self._terminal_visible = not self._terminal_visible
        self._terminal_panel.setVisible(self._terminal_visible)
        if self._terminal_visible:
            self._start_terminal()
            self._editor_splitter.setSizes([520, 220])
            self._toggle_terminal_button.setText("Hide Terminal")
            self._set_status("Terminal opened")
            self._terminal_output.setFocus()
            return

        self._editor_splitter.setSizes([740, 0])
        self._toggle_terminal_button.setText("Terminal")
        self._set_status("Terminal hidden")

    def _submit_terminal_command(self, command: str) -> None:
        if self._terminal is None or not self._terminal.is_running():
            self._start_terminal()
        if self._terminal is None or not self._terminal.is_running():
            return
        self._terminal_output.expect_command_echo(command)
        self._terminal.submit_command(command)

    def _write_terminal_data(self, text: str) -> None:
        if self._terminal is None or not self._terminal.is_running():
            self._start_terminal()
        if self._terminal is None or not self._terminal.is_running():
            return
        self._terminal.write(text)

    def _resize_terminal(self, columns: int, rows: int) -> None:
        if self._terminal is None or not self._terminal.is_running():
            return
        self._terminal.resize(columns, rows)

    def _interrupt_terminal(self) -> None:
        if self._terminal is None or not self._terminal.is_running():
            return
        self._terminal.send_ctrl_c()

    def _open_initial_file(self) -> None:
        preferred = self._workspace / "main.py"
        if preferred.exists():
            self._open_file(preferred)
            return

        for child in sorted(self._workspace.iterdir(), key=lambda item: (not item.is_file(), item.name.lower())):
            if child.is_file():
                self._open_file(child)
                return

    def _selected_path(self, index: QModelIndex) -> Path:
        return Path(self._tree_model.filePath(index))

    def _handle_tree_clicked(self, index: QModelIndex) -> None:
        path = self._selected_path(index)
        if path.is_dir():
            self._tree_view.setExpanded(index, not self._tree_view.isExpanded(index))
            return
        self._open_file(path)

    def _open_file(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            return

        if self._dirty and self._current_file != path:
            choice = QMessageBox.question(
                self,
                "Unsaved changes",
                f"Save changes to {self._current_file} before opening another file?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save,
            )
            if choice == QMessageBox.StandardButton.Cancel:
                return
            if choice == QMessageBox.StandardButton.Save and not self._save_current_file():
                return

        self._loading_file = True
        try:
            self._editor.setPlainText(path.read_text(encoding="utf-8"))
            self._current_file = path
            self._dirty = False
            self._file_label.setText(str(path.relative_to(self._workspace)))
            self._sync_python_highlighter(path)
            self._set_status(f"Opened {path.relative_to(self._workspace)}")
        finally:
            self._loading_file = False

    def _sync_python_highlighter(self, path: Path | None) -> None:
        self._python_highlighter.set_enabled(path is not None and path.suffix.lower() == ".py")

    def _mark_dirty(self) -> None:
        if self._loading_file or self._current_file is None:
            return
        if not self._dirty:
            self._dirty = True
            self._file_label.setText(f"{self._current_file.relative_to(self._workspace)} *")
            self._set_status(f"Modified {self._current_file.relative_to(self._workspace)}")

    def _save_current_file(self) -> bool:
        if self._current_file is None:
            self._set_status("No file selected")
            return False

        try:
            self._current_file.write_text(self._editor.toPlainText(), encoding="utf-8")
        except OSError as exc:
            QMessageBox.critical(self, "Save failed", str(exc))
            return False

        self._dirty = False
        self._file_label.setText(str(self._current_file.relative_to(self._workspace)))
        self._set_status(f"Saved {self._current_file.relative_to(self._workspace)}")
        return True

    def _new_block_id(self) -> str:
        block_id = f"block-{self._next_block_id}"
        self._next_block_id += 1
        return block_id

    def _scroll_chat_to_bottom(self) -> None:
        self._chat_history.scroll_to_bottom()

    def _render_chat_history(self) -> None:
        html_parts = render_chat_history(self._chat_events, self._collapsed_blocks)
        self._chat_history.set_chat_html("".join(html_parts))

    def _append_chat_message(self, role: str, body: str, *, tone: str = "neutral") -> None:
        self._chat_events.append(ChatEvent(kind="message", title=role, body=body, tone=tone))
        self._render_chat_history()

    def _update_chat_placeholder(self) -> None:
        if self._mode == "ask":
            self._chat_input.setPlaceholderText("Type a question for ask mode. Ctrl+Enter sends.")
            return
        self._chat_input.setPlaceholderText("Type a task for agent mode. Ctrl+Enter sends.")

    def _reset_chat_session(self, *, announce: bool) -> None:
        self._messages = build_messages(self._mode)
        self._update_chat_placeholder()
        if announce:
            self._append_chat_message(
                "System",
                f"Switched to `{self._mode}` mode. Conversation context was reset for the next request.",
                tone="meta",
            )
        self._set_status(f"Ready ({self._mode} mode)")

    def _handle_mode_changed(self, mode: str) -> None:
        normalized_mode = normalize_mode(mode)
        if normalized_mode == self._mode:
            return
        self._mode = normalized_mode
        self._reset_chat_session(announce=True)

    def _append_step_header(self, step: int, total: int, label: str, *, group_id: str = "") -> None:
        self._chat_events.append(ChatEvent(kind="step", title=label, step=step, total=total, group_id=group_id))
        self._render_chat_history()

    def _append_code_block(self, title: str, body: str, *, tone: str = "tool", group_id: str = "") -> None:
        block_id = self._new_block_id()
        self._chat_events.append(
            ChatEvent(
                kind="block",
                title=title,
                body=body,
                tone=tone,
                block_id=block_id,
                collapsible=True,
                group_id=group_id,
            )
        )
        self._collapsed_blocks.add(block_id)
        self._render_chat_history()

    def _handle_chat_anchor_clicked(self, token: str) -> None:
        token = unquote(token)

        if token.startswith("copy:"):
            block_id = token[len("copy:"):]
            content = get_copy_block(block_id)
            if content:
                QApplication.clipboard().setText(content)
            return

        if token.startswith("toggle:"):
            block_id = token[len("toggle:"):]
            if block_id in self._collapsed_blocks:
                self._collapsed_blocks.remove(block_id)
            else:
                self._collapsed_blocks.add(block_id)
            self._render_chat_history()
            return

        if token:
            QDesktopServices.openUrl(QUrl(token))

    def _set_busy(self, busy: bool) -> None:
        self._send_button.setDisabled(busy)
        self._chat_input.setDisabled(busy)
        self._mode_selector.setDisabled(busy)
        self._tree_view.setDisabled(busy)
        self._save_button.setDisabled(busy)

    def _send_chat(self) -> None:
        if self._worker_thread is not None:
            self._set_status("Agent is already running")
            return

        prompt = self._chat_input.toPlainText().strip()
        if not prompt:
            return

        self._chat_input.clear()
        self._messages.append(UserMessage(prompt))
        self._append_chat_message("You", prompt, tone="user")

        self._work_group_id = self._new_block_id()
        self._work_start_time = time.monotonic()
        group_event = ChatEvent(kind="group_header", title="Работает…", block_id=self._work_group_id)
        self._chat_events.append(group_event)
        self._work_group_header = group_event
        self._render_chat_history()

        self._set_status("Thinking...")
        self._set_busy(True)

        self._worker_thread = QThread(self)
        self._worker = AgentWorker(
            workspace=self._workspace,
            model=self._model,
            mode=self._mode,
            max_steps=self._max_steps,
            messages=self._messages,
        )
        self._worker.moveToThread(self._worker_thread)
        self._worker_thread.started.connect(self._worker.run)
        self._worker.step_started.connect(self._handle_step_started)
        self._worker.assistant_response.connect(self._handle_assistant_response)
        self._worker.repair_requested.connect(self._handle_repair_requested)
        self._worker.command_executed.connect(self._handle_command_executed)
        self._worker.finished.connect(self._handle_agent_finished)
        self._worker.error.connect(self._handle_agent_error)
        self._worker.finished.connect(self._worker_thread.quit)
        self._worker.error.connect(self._worker_thread.quit)
        self._worker_thread.finished.connect(self._worker.deleteLater)
        self._worker_thread.finished.connect(self._worker_thread.deleteLater)
        self._worker_thread.finished.connect(self._clear_worker_refs)
        self._worker_thread.start()

    def _clear_worker_refs(self) -> None:
        self._worker = None
        self._worker_thread = None
        self._set_busy(False)

    def _handle_step_started(self, step: int, total: int) -> None:
        self._append_step_header(step, total, f"{self._mode.upper()} формирует следующий шаг", group_id=self._work_group_id)

    def _handle_assistant_response(self, step: int, raw_response: str) -> None:
        self._append_code_block(f"Assistant JSON, шаг {step}", raw_response, tone="assistant", group_id=self._work_group_id)

    def _handle_repair_requested(self, step: int, message: str) -> None:
        self._append_code_block(f"Invalid response, шаг {step}", message, tone="error", group_id=self._work_group_id)

    def _handle_command_executed(self, step: int, command: str, data: object) -> None:
        self._append_code_block(
            f"Tool {command}, шаг {step}",
            format_json(data if isinstance(data, dict) else {"value": data}),
            tone="tool",
            group_id=self._work_group_id,
        )
        if command == "writefile":
            payload = data if isinstance(data, dict) else {}
            path = payload.get("path")
            if isinstance(path, str):
                current = self._current_file
                if current is not None and str(current.relative_to(self._workspace)) == path:
                    self._loading_file = True
                    try:
                        self._editor.setPlainText(current.read_text(encoding="utf-8"))
                        self._dirty = False
                        self._file_label.setText(path)
                    finally:
                        self._loading_file = False

    def _finalise_work_group(self, *, label: str) -> None:
        if self._work_group_header is not None:
            elapsed = time.monotonic() - self._work_start_time
            self._work_group_header.title = f"{label} {_format_duration(elapsed)}"
            self._collapsed_blocks.add(self._work_group_id)
        self._work_group_id = ""
        self._work_group_header = None

    def _handle_agent_finished(self, result: str, messages: object) -> None:
        if isinstance(messages, list):
            self._messages = list(messages)
        self._finalise_work_group(label="Работал на протяжении")
        self._append_chat_message("Assistant", result, tone="assistant")
        self._set_status("Ready")

    def _handle_agent_error(self, message: str) -> None:
        self._finalise_work_group(label="Завершился с ошибкой за")
        self._append_chat_message("Error", message, tone="error")
        self._set_status("Agent error")
        QMessageBox.critical(self, "Agent error", message)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt callback signature
        if self._dirty and self._current_file is not None:
            choice = QMessageBox.question(
                self,
                "Unsaved changes",
                f"Save changes to {self._current_file} before closing?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save,
            )
            if choice == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
            if choice == QMessageBox.StandardButton.Save and not self._save_current_file():
                event.ignore()
                return

        self._remove_diag_hit_filter()

        if self._worker_thread is not None:
            self._worker_thread.quit()
            self._worker_thread.wait(1500)

        if self._terminal is not None:
            self._terminal.close()
            self._terminal = None

        super().closeEvent(event)
