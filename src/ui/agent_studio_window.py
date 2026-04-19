"""Agent Studio Window for the BabkaCode."""

from __future__ import annotations

import json
import logging
import time

import sys
from pathlib import Path
from typing import Any

from azure.ai.inference.models import UserMessage
from PySide6.QtCore import QDir, QModelIndex, QPoint, QRect, QSize, Qt, QThread, QTimer, QEvent
from PySide6.QtGui import (
    QAction,
    QColor,
    QFont,
    QIcon,
    QKeySequence,
    QMoveEvent,
    QMouseEvent,
    QPainter,
    QPen,
    QResizeEvent,
    QShowEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QFileSystemModel,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QPlainTextEdit,
    QToolButton,
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
    from src.ui.python_highlighter import PythonHighlighter
    from src.ui.title_bar import build_app_icon, TitleBar
    from src.ui.native_chrome_win32 import LowLevelNativeChromeMixin
    from src.ui.ui_utils import build_messages, build_nerd_font
    from src.ui.activity_bar import ActivityBar
    from src.ui.chat_history_view import ChatHistoryPanel
    from src.ui.prompt_input_widget import PromptInputWidget
    from src.ui.design_tokens import (
        BG_HOVER,
        TEXT_PRIMARY,
        TEXT_TERTIARY,
        ACCENT,
        ACCENT_MUTED_QT,
        ACCENT_ACTIVE_QT,
        RADIUS_SM,
        SIDEBAR_W,
        CHAT_PANEL_W,
        PANEL_HEADER_H,
        TAB_BAR_H,
    )
    from src.web_chat.chat_event import ChatEvent
    from src.ui.style import STYLE_SHEET
    from src.web_chat.html_generator import render_chat_history, get_copy_block
    from src.web_chat.chat_webview import ChatWebView
    from src.web_chat.chat_storage import (
        chat_file_path,
        fresh_session_state,
        list_saved_chats,
        load_chat_session,
        move_chat_from_archive,
        move_chat_to_archive,
        read_last_chat_id,
        save_chat_session,
        write_last_chat_id,
    )

else:
    from ..ui.interactive_terminal import InteractiveTerminal
    from ..ui.terminal import TerminalController
    from ..ui.ui_utils import SUPPORTED_MODES, normalize_mode, format_json
    from ..ui.agent_worker import AgentWorker
    from ..ui.python_highlighter import PythonHighlighter
    from ..ui.title_bar import build_app_icon, TitleBar
    from ..ui.native_chrome_win32 import LowLevelNativeChromeMixin
    from ..ui.ui_utils import build_messages, build_nerd_font
    from ..ui.activity_bar import ActivityBar
    from ..ui.chat_history_view import ChatHistoryPanel
    from ..ui.prompt_input_widget import PromptInputWidget
    from ..ui.design_tokens import (
        BG_HOVER,
        TEXT_PRIMARY,
        TEXT_TERTIARY,
        ACCENT,
        ACCENT_MUTED_QT,
        ACCENT_ACTIVE_QT,
        RADIUS_SM,
        SIDEBAR_W,
        CHAT_PANEL_W,
        PANEL_HEADER_H,
        TAB_BAR_H,
    )
    from ..web_chat.chat_event import ChatEvent
    from ..ui.style import STYLE_SHEET
    from ..web_chat.html_generator import render_chat_history, get_copy_block
    from ..web_chat.chat_webview import ChatWebView
    from ..web_chat.chat_storage import (
        chat_file_path,
        fresh_session_state,
        list_saved_chats,
        load_chat_session,
        move_chat_from_archive,
        move_chat_to_archive,
        read_last_chat_id,
        save_chat_session,
        write_last_chat_id,
    )

logger = logging.getLogger(__name__)


class _ChatWebContainer(QWidget):
    """Host chat webview with direct geometry control for native WebView2 sync."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._chat_view: ChatWebView | None = None
        self._last_rect = QRect()
        self._last_global_top_left = QPoint()
        self._last_visible = False

    def set_chat_view(self, chat_view: ChatWebView) -> None:
        self._chat_view = chat_view
        self._sync_child_geometry()

    def event(self, event) -> bool:  # noqa: ANN001
        result = super().event(event)
        if event.type() == QEvent.Type.LayoutRequest:
            self._sync_child_geometry()
        return result

    def moveEvent(self, event: QMoveEvent) -> None:  # noqa: N802
        super().moveEvent(event)
        self._sync_child_geometry()

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._sync_child_geometry()

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        self._sync_child_geometry()

    def hideEvent(self, event) -> None:  # noqa: ANN001, N802
        super().hideEvent(event)

    def _sync_child_geometry(self) -> None:
        if self._chat_view is None:
            return
        visible = self.isVisible() and self._chat_view.isVisible()
        rect = self.rect()
        global_top_left = self.mapToGlobal(rect.topLeft())
        if self._chat_view.geometry() != rect:
            self._chat_view.setGeometry(self.rect())
        if (
            rect == self._last_rect
            and global_top_left == self._last_global_top_left
            and visible == self._last_visible
        ):
            return
        self._last_rect = QRect(rect)
        self._last_global_top_left = QPoint(global_top_left)
        self._last_visible = visible
        self._chat_view.sync_native_geometry()


def _format_duration(seconds: float) -> str:
    total = int(seconds)
    if total < 60:
        return f"{total}s"
    mins, secs = divmod(total, 60)
    return f"{mins}m {secs}s" if secs else f"{mins}m"


# ── Explorer item delegate ────────────────────────────────────────────────────


class ExplorerItemDelegate(QStyledItemDelegate):
    """Dark-theme explorer rows: subtle hover, indigo selection, no colored dots."""

    _TEXT_FILE = QColor(TEXT_PRIMARY)
    _TEXT_DIR = QColor("#aab0c4")
    _TEXT_SELECTED = QColor(TEXT_PRIMARY)
    _TEXT_MUTED = QColor(TEXT_TERTIARY)
    _FILL_HOVER = QColor(BG_HOVER)
    _FILL_CURRENT = QColor(ACCENT_ACTIVE_QT)
    _FILL_SELECTED = QColor(ACCENT_MUTED_QT)
    _BORDER_CURRENT = QColor(ACCENT)
    _BORDER_SELECTED = QColor(ACCENT)
    _CHEVRON = QColor(TEXT_TERTIARY)
    _DOT_FILE = QColor(TEXT_TERTIARY)
    _DOT_DIR = QColor("#6366f1")
    _DOT_CURRENT = QColor(ACCENT)
    _DOT_SELECTED = QColor(ACCENT)

    def __init__(
        self,
        window: "AgentStudioWindow",
        model: QFileSystemModel,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._window = window
        self._model = model

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:  # noqa: N802
        base = super().sizeHint(option, index)
        return QSize(base.width(), max(32, base.height() + 6))

    def paint(
        self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:  # noqa: N802
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)

        path = Path(self._model.filePath(index))
        is_dir = self._model.isDir(index)
        is_selected = bool(opt.state & QStyle.StateFlag.State_Selected)
        is_hover = bool(opt.state & QStyle.StateFlag.State_MouseOver)
        is_current_file = self._window._current_file == path

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        row_rect = opt.rect.adjusted(6, 2, -6, -2)
        fill_color: QColor | None = None
        border_color: QColor | None = None
        dot_color = self._DOT_DIR if is_dir else self._DOT_FILE
        text_color = self._TEXT_DIR if is_dir else self._TEXT_FILE

        if is_selected:
            fill_color = self._FILL_SELECTED
            border_color = self._BORDER_SELECTED
            dot_color = self._DOT_SELECTED
            text_color = self._TEXT_SELECTED
        elif is_current_file:
            fill_color = self._FILL_CURRENT
            border_color = self._BORDER_CURRENT
            dot_color = self._DOT_CURRENT
        elif is_hover:
            fill_color = self._FILL_HOVER

        if fill_color is not None:
            painter.setBrush(fill_color)
            painter.setPen(QPen(border_color or fill_color, 1))
            painter.drawRoundedRect(row_rect, RADIUS_SM, RADIUS_SM)

        # Small dot indicator
        dot_rect = QRect(row_rect.left() + 8, row_rect.center().y() - 2, 4, 4)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(dot_color)
        painter.drawEllipse(dot_rect)

        # Icon
        icon_rect = QRect(row_rect.left() + 18, row_rect.center().y() - 7, 14, 14)
        mode = (
            QIcon.Mode.Normal
            if opt.state & QStyle.StateFlag.State_Enabled
            else QIcon.Mode.Disabled
        )
        state = QIcon.State.On if is_selected else QIcon.State.Off
        opt.icon.paint(painter, icon_rect, Qt.AlignmentFlag.AlignCenter, mode, state)

        # Text
        text_rect = row_rect.adjusted(38, 0, -10, 0)
        display = painter.fontMetrics().elidedText(
            opt.text,
            Qt.TextElideMode.ElideMiddle,
            max(0, text_rect.width()),
        )
        font = QFont(opt.font)
        font.setBold(is_dir or is_selected or is_current_file)
        painter.setFont(font)
        painter.setPen(text_color)
        painter.drawText(
            text_rect,
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
            display,
        )

        painter.restore()


# ── File tab bar (VS Code style) ─────────────────────────────────────────────


class _FileTab(QFrame):
    """Single tab in the file tab bar."""

    from PySide6.QtCore import Signal as _Sig

    clicked = _Sig(Path)
    close_requested = _Sig(Path)

    def __init__(
        self, path: Path, workspace: Path, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._path = path
        self._active = False
        self._dirty = False
        self.setObjectName("fileTab")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(TAB_BAR_H)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 4, 0)
        layout.setSpacing(4)

        try:
            display = str(path.relative_to(workspace))
        except ValueError:
            display = path.name
        self._label = QLabel(display)
        self._label.setObjectName("fileTabLabel")
        layout.addWidget(self._label, 1)

        close_btn = QToolButton(self)
        close_btn.setText("\u00d7")
        close_btn.setObjectName("fileTabClose")
        close_btn.setFixedSize(18, 18)
        close_btn.setAutoRaise(True)
        close_btn.setCursor(Qt.CursorShape.ArrowCursor)
        close_btn.clicked.connect(lambda: self.close_requested.emit(self._path))
        layout.addWidget(close_btn, 0)

    @property
    def path(self) -> Path:
        return self._path

    def set_active(self, active: bool) -> None:
        self._active = active
        self.setObjectName("fileTabActive" if active else "fileTab")
        self._label.setObjectName("fileTabLabelActive" if active else "fileTabLabel")
        self.style().unpolish(self)
        self.style().polish(self)
        self._label.style().unpolish(self._label)
        self._label.style().polish(self._label)
        self.update()

    def set_dirty(self, dirty: bool) -> None:
        self._dirty = dirty
        try:
            text = str(self._path.relative_to(self.parent()._workspace))  # type: ignore[union-attr]
        except (ValueError, AttributeError):
            text = self._path.name
        self._label.setText(f"{text} *" if dirty else text)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._path)
        super().mousePressEvent(event)


class FileTabBar(QWidget):
    """Horizontal scrollable file tab bar."""

    from PySide6.QtCore import Signal as _Sig

    tab_clicked = _Sig(Path)
    tab_close_requested = _Sig(Path)

    def __init__(self, workspace: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._workspace = workspace
        self._tabs: dict[Path, _FileTab] = {}
        self._active: Path | None = None
        self.setObjectName("fileTabBar")
        self.setFixedHeight(TAB_BAR_H)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea(self)
        scroll.setObjectName("fileTabScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setFixedHeight(TAB_BAR_H)

        self._container = QWidget()
        self._container.setObjectName("fileTabContainer")
        self._layout = QHBoxLayout(self._container)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        scroll.setWidget(self._container)
        outer.addWidget(scroll, 1)

    def add_tab(self, path: Path) -> None:
        if path in self._tabs:
            self.set_active(path)
            return
        tab = _FileTab(path, self._workspace, self)
        tab.clicked.connect(self.tab_clicked.emit)
        tab.close_requested.connect(self.tab_close_requested.emit)
        self._tabs[path] = tab
        self._layout.addWidget(tab)
        self.set_active(path)

    def remove_tab(self, path: Path) -> None:
        tab = self._tabs.pop(path, None)
        if tab is None:
            return
        self._layout.removeWidget(tab)
        tab.deleteLater()
        if self._active == path:
            self._active = None
            if self._tabs:
                self.set_active(next(iter(self._tabs)))

    def set_active(self, path: Path) -> None:
        if self._active and self._active in self._tabs:
            self._tabs[self._active].set_active(False)
        self._active = path
        if path in self._tabs:
            self._tabs[path].set_active(True)

    def set_dirty(self, path: Path, dirty: bool) -> None:
        if path in self._tabs:
            self._tabs[path].set_dirty(dirty)

    def has_tab(self, path: Path) -> bool:
        return path in self._tabs


# ── Main window ───────────────────────────────────────────────────────────────


class AgentStudioWindow(QMainWindow, LowLevelNativeChromeMixin):
    """Activity-bar + sidebar + editor + chat panel layout."""

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
        self._title_content_gap: QWidget | None = None
        self._chat_web_container: QWidget | None = None
        self._chat_id: str = ""
        self._chat_stored_in_archive = False
        self._chat_usage_totals = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
        self._turn_prompt_tokens = 0
        self._turn_completion_tokens = 0
        self._scroll_chat_on_next_load = False
        self._sidebar_visible = True
        self._chat_panel_visible = True

        self.setWindowTitle("BabkaCode")
        self.setWindowIcon(build_app_icon())

        self._build_ui()
        self.resize(1520, 920)
        self._configure_window_chrome()
        self._apply_style()
        self._open_initial_file()
        self._init_chat_persistence()

    def _configure_window_chrome(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowMinMaxButtonsHint
            | Qt.WindowType.WindowSystemMenuHint,
        )

    def _build_ui(self) -> None:
        model_short = self._model.split("/")[-1] if "/" in self._model else self._model
        fixed_font = build_nerd_font(12)

        # ── Activity bar ──────────────────────────────────────────────────────
        self._activity_bar = ActivityBar(self)
        self._activity_bar.view_requested.connect(self._on_activity_view)
        self._activity_bar.set_active_view("explorer")

        # ── Explorer panel ────────────────────────────────────────────────────
        explorer_header = QLabel("EXPLORER")
        explorer_header.setObjectName("panelHeader")
        explorer_header.setFixedHeight(PANEL_HEADER_H)
        explorer_header.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )

        self._tree_model = QFileSystemModel(self)
        self._tree_model.setRootPath(str(self._workspace))
        self._tree_model.setFilter(
            QDir.AllEntries | QDir.NoDotAndDotDot | QDir.AllDirs | QDir.Files
        )
        self._tree_model.setNameFilterDisables(False)
        self._tree_model.sort(0, Qt.SortOrder.AscendingOrder)

        self._tree_view = QTreeView(self)
        self._tree_view.setObjectName("explorerTree")
        self._tree_view.setModel(self._tree_model)
        self._tree_view.setRootIndex(self._tree_model.index(str(self._workspace)))
        self._tree_view.setHeaderHidden(True)
        self._tree_view.setAnimated(False)
        self._tree_view.setIndentation(18)
        self._tree_view.setIconSize(QSize(14, 14))
        self._tree_view.setMouseTracking(True)
        self._tree_view.setExpandsOnDoubleClick(False)
        self._tree_view.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._tree_view.setSelectionBehavior(QTreeView.SelectionBehavior.SelectRows)
        self._tree_view.setUniformRowHeights(True)
        self._tree_view.setItemDelegate(
            ExplorerItemDelegate(self, self._tree_model, self._tree_view)
        )
        for column in range(1, 4):
            self._tree_view.hideColumn(column)
        self._tree_view.clicked.connect(self._handle_tree_clicked)

        explorer_page = QWidget()
        explorer_page.setObjectName("explorerPanel")
        exp_layout = QVBoxLayout(explorer_page)
        exp_layout.setContentsMargins(0, 0, 0, 0)
        exp_layout.setSpacing(0)
        exp_layout.addWidget(explorer_header)
        exp_layout.addWidget(self._tree_view, 1)

        # ── Chat history panel ────────────────────────────────────────────────
        self._chat_history_panel = ChatHistoryPanel(self._workspace, self)
        self._chat_history_panel.chat_selected.connect(self._on_history_chat_selected)
        self._chat_history_panel.new_chat_requested.connect(self._new_chat_clicked)
        self._chat_history_panel.archive_requested.connect(
            lambda _cid: self._archive_current_chat()
        )

        # ── Sidebar stacked widget ────────────────────────────────────────────
        self._sidebar_stack = QStackedWidget(self)
        self._sidebar_stack.setObjectName("sidebarPanel")
        self._sidebar_stack.setMinimumWidth(200)
        self._sidebar_stack.setMaximumWidth(400)
        self._sidebar_stack.addWidget(explorer_page)  # index 0 = explorer
        self._sidebar_stack.addWidget(self._chat_history_panel)  # index 1 = history

        # ── Editor panel ──────────────────────────────────────────────────────
        self._save_action = QAction("Save", self)
        self._save_action.setShortcut(QKeySequence.Save)
        self._save_action.triggered.connect(self._save_current_file)
        self.addAction(self._save_action)

        self._file_tab_bar = FileTabBar(self._workspace, self)
        self._file_tab_bar.tab_clicked.connect(self._on_tab_clicked)
        self._file_tab_bar.tab_close_requested.connect(self._on_tab_close)

        self._editor = QPlainTextEdit(self)
        self._editor.setObjectName("editorSurface")
        self._editor.textChanged.connect(self._mark_dirty)
        self._editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._editor.setFont(fixed_font)
        self._editor.setTabStopDistance(
            self._editor.fontMetrics().horizontalAdvance(" ") * 4
        )
        self._python_highlighter = PythonHighlighter(self._editor.document())

        self._terminal_output = InteractiveTerminal(self)
        self._terminal_output.setFont(fixed_font)
        self._terminal_output.setObjectName("terminalOutput")
        self._terminal_output.setPlaceholderText("Interactive ANSI/VT100 terminal")
        self._terminal_output.data_ready.connect(self._write_terminal_data)
        self._terminal_output.resize_requested.connect(self._resize_terminal)
        self._terminal_output.interrupt_requested.connect(self._interrupt_terminal)

        terminal_header = QLabel("  TERMINAL")
        terminal_header.setObjectName("terminalHeader")
        terminal_header.setFixedHeight(32)

        self._terminal_panel = QWidget(self)
        self._terminal_panel.setObjectName("terminalPanel")
        self._terminal_panel.setFixedHeight(220)
        terminal_layout = QVBoxLayout(self._terminal_panel)
        terminal_layout.setContentsMargins(0, 0, 0, 0)
        terminal_layout.setSpacing(0)
        terminal_layout.addWidget(terminal_header)
        terminal_layout.addWidget(self._terminal_output, 1)
        self._terminal_panel.setVisible(False)

        editor_panel = QWidget(self)
        editor_panel.setObjectName("editorPanel")
        ed_layout = QVBoxLayout(editor_panel)
        ed_layout.setContentsMargins(0, 0, 0, 0)
        ed_layout.setSpacing(0)
        ed_layout.addWidget(self._file_tab_bar)
        ed_layout.addWidget(self._editor, 1)
        ed_layout.addWidget(self._terminal_panel, 0)

        # ── Chat panel ────────────────────────────────────────────────────────
        chat_hdr_label = QLabel("AI ASSISTANT")
        chat_hdr_label.setObjectName("chatHeaderLabel")

        chat_hdr = QFrame(self)
        chat_hdr.setObjectName("chatHeaderFrame")
        ch_layout = QHBoxLayout(chat_hdr)
        ch_layout.setContentsMargins(14, 0, 14, 0)
        ch_layout.setSpacing(8)
        ch_layout.addWidget(chat_hdr_label, 1)

        chat_panel = QWidget(self)
        chat_panel.setObjectName("chatPanel")
        chat_panel.setStyleSheet(
            "background-color: rgba(255, 0, 0, 0.12);"
            "border-left: 3px solid #ff3b30;"
        )

        self._chat_web_container = _ChatWebContainer(chat_panel)
        self._chat_web_container.setObjectName("chatWebContainer")
        self._chat_web_container.setStyleSheet(
            "background-color: rgba(57, 255, 20, 0.14);"
            "border: 2px solid #39ff14;"
        )

        self._chat_view = ChatWebView(self._chat_web_container)
        self._chat_view.link_activated.connect(self._handle_chat_anchor_clicked)
        self._chat_view.content_loaded.connect(self._scroll_chat_to_bottom)
        self._chat_web_container.set_chat_view(self._chat_view)

        self._prompt_input = PromptInputWidget(
            modes=SUPPORTED_MODES,
            initial_mode=self._mode,
            assets_dir=Path(__file__).parent / "assets",
            parent=self,
        )
        self._prompt_input.set_font(fixed_font)
        self._prompt_input.set_tab_changes_focus(True)
        self._prompt_input.mode_changed.connect(self._handle_mode_changed)
        self._prompt_input.send_requested.connect(self._send_chat)
        self._update_chat_placeholder()
        self._chat_input_shortcut = QAction(self)
        self._chat_input_shortcut.setShortcut(QKeySequence("Ctrl+Return"))
        self._chat_input_shortcut.triggered.connect(self._send_chat)
        self.addAction(self._chat_input_shortcut)
        self._chat_input_shortcut2 = QAction(self)
        self._chat_input_shortcut2.setShortcut(QKeySequence("Ctrl+Enter"))
        self._chat_input_shortcut2.triggered.connect(self._send_chat)
        self.addAction(self._chat_input_shortcut2)

        cp_layout = QVBoxLayout(chat_panel)
        cp_layout.setContentsMargins(0, 0, 0, 0)
        cp_layout.setSpacing(0)
        cp_layout.addWidget(chat_hdr)
        cp_layout.addWidget(self._chat_web_container, 1)

        prompt_input_slot = QWidget(self)
        prompt_input_layout = QVBoxLayout(prompt_input_slot)
        prompt_input_layout.setContentsMargins(20, 20, 20, 20)
        prompt_input_layout.setSpacing(0)
        prompt_input_layout.addWidget(self._prompt_input)
        cp_layout.addWidget(prompt_input_slot, 0)

        # ── Main horizontal splitter: sidebar | editor | chat ─────────────────
        self._splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self._splitter.setObjectName("mainSplitter")
        self._splitter.addWidget(self._sidebar_stack)
        self._splitter.addWidget(editor_panel)
        self._splitter.addWidget(chat_panel)
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setStretchFactor(2, 0)
        self._splitter.setSizes([SIDEBAR_W, 780, CHAT_PANEL_W])
        self._splitter.splitterMoved.connect(self._schedule_chat_view_geometry_sync)

        # ── Title bar ─────────────────────────────────────────────────────────
        self._title_bar = TitleBar(self)
        self._title_bar.set_metadata(
            title="BabkaCode",
            workspace=str(self._workspace),
            model=model_short,
        )

        # ── Root layout: titlebar / (activity bar + splitter) ─────────────────
        container = QWidget(self)
        container.setObjectName("centralContainer")

        workspace_row = QHBoxLayout()
        workspace_row.setContentsMargins(0, 0, 0, 0)
        workspace_row.setSpacing(0)
        workspace_row.addWidget(self._activity_bar, 0)
        workspace_row.addWidget(self._splitter, 1)

        root = QVBoxLayout(container)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self._title_content_gap = QWidget(container)
        self._title_content_gap.setObjectName("titleContentGap")
        self._title_content_gap.setFixedHeight(0)
        root.addWidget(self._title_bar, 0)
        root.addWidget(self._title_content_gap, 0)
        root.addLayout(workspace_row, 1)
        self._root_layout = root
        self.setCentralWidget(container)

        self.titlebar_widget = self._title_bar
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
        self._token_status = QLabel("  Tokens: —")
        self._token_status.setObjectName("tokenStatusLabel")
        self._status_bar.addPermanentWidget(self._token_status)
        self.setStatusBar(self._status_bar)
        self._set_status("Ready")

        # ── Keyboard shortcuts ────────────────────────────────────────────────
        toggle_sidebar_action = QAction("Toggle Sidebar", self)
        toggle_sidebar_action.setShortcut(QKeySequence("Ctrl+B"))
        toggle_sidebar_action.triggered.connect(self._toggle_sidebar)
        self.addAction(toggle_sidebar_action)

        toggle_chat_action = QAction("Toggle Chat", self)
        toggle_chat_action.setShortcut(QKeySequence("Ctrl+J"))
        toggle_chat_action.triggered.connect(self._toggle_chat_panel)
        self.addAction(toggle_chat_action)

        toggle_terminal_action = QAction("Toggle Terminal", self)
        toggle_terminal_action.setShortcut(QKeySequence("Ctrl+`"))
        toggle_terminal_action.triggered.connect(self._toggle_terminal)
        self.addAction(toggle_terminal_action)

        focus_chat_action = QAction("Focus Chat Input", self)
        focus_chat_action.setShortcut(QKeySequence("Ctrl+L"))
        focus_chat_action.triggered.connect(self._focus_chat_input)
        self.addAction(focus_chat_action)

    def _apply_style(self) -> None:
        app = QApplication.instance()
        if app is not None:
            app.setStyle("Fusion")
        self.setStyleSheet(STYLE_SHEET)

    # ── Panel toggle helpers ───────────────────────────────────────────────────

    def _toggle_sidebar(self) -> None:
        self._sidebar_visible = not self._sidebar_visible
        self._sidebar_stack.setVisible(self._sidebar_visible)

    def _toggle_chat_panel(self) -> None:
        self._chat_panel_visible = not self._chat_panel_visible
        sizes = self._splitter.sizes()
        if not self._chat_panel_visible:
            self._splitter.setSizes([sizes[0], sizes[1] + sizes[2], 0])
        else:
            total = sum(sizes)
            self._splitter.setSizes(
                [sizes[0], total - sizes[0] - CHAT_PANEL_W, CHAT_PANEL_W]
            )
        self._schedule_chat_view_geometry_sync()

    def _focus_chat_input(self) -> None:
        if not self._chat_panel_visible:
            self._toggle_chat_panel()
        self._prompt_input.focus_editor()

    # ── Activity bar handler ───────────────────────────────────────────────────

    def _on_activity_view(self, view_id: str) -> None:
        if view_id == "explorer":
            self._sidebar_stack.setCurrentIndex(0)
            if not self._sidebar_visible:
                self._toggle_sidebar()
        elif view_id == "history":
            self._chat_history_panel.refresh()
            self._sidebar_stack.setCurrentIndex(1)
            if not self._sidebar_visible:
                self._toggle_sidebar()
        # "settings" reserved for future

    # ── Status helpers ─────────────────────────────────────────────────────────

    def _set_status(self, text: str) -> None:
        self._status.setText(f"  {text}")

    def _schedule_chat_view_geometry_sync(self, *_args) -> None:
        if getattr(self, "_chat_view", None) is None:
            return
        QTimer.singleShot(0, self._chat_view.sync_native_geometry)

    def changeEvent(self, event) -> None:  # noqa: N802
        super().changeEvent(event)
        if self._title_bar is not None:
            self._title_bar.sync_window_state()

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        if not self._native_chrome_applied and sys.platform == "win32":
            self._native_chrome_applied = True
            self._apply_native_styles()
        self._schedule_chat_view_geometry_sync()

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._schedule_chat_view_geometry_sync()

    def nativeEvent(self, eventType, message):  # noqa: N802
        if sys.platform == "win32":
            result = self._process_native_event(message)
            if result is not None:
                return result
        return super().nativeEvent(eventType, message)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            p = event.position().toPoint()
            if self._point_in_titlebar_drag_region(p.x(), p.y()):
                if self._title_bar is not None:
                    self._title_bar._handle_maximize_restore()
                event.accept()
                return
        super().mouseDoubleClickEvent(event)

    # ── Terminal ───────────────────────────────────────────────────────────────

    def _start_terminal(self) -> None:
        if self._terminal is None:
            self._terminal = TerminalController(self)
            self._terminal.output_ready.connect(self._append_terminal_text)
            self._terminal.error.connect(
                lambda msg: self._append_terminal_text(f"\n[terminal error] {msg}\n")
            )

        if self._terminal.is_running():
            return

        self._terminal_output.reset_terminal("")
        columns, rows = self._terminal_output.terminal_size()
        self._terminal.start(cwd=str(self._workspace), rows=rows, columns=columns)
        if not self._terminal.is_running():
            self._terminal_output.append_output(
                "Failed to start interactive terminal.\n"
            )
            return

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
            self._set_status("Terminal opened")
            self._terminal_output.setFocus()
            return
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

    # ── File operations ────────────────────────────────────────────────────────

    def _open_initial_file(self) -> None:
        preferred = self._workspace / "main.py"
        if preferred.exists():
            self._open_file(preferred)
            return
        for child in sorted(
            self._workspace.iterdir(),
            key=lambda item: (not item.is_file(), item.name.lower()),
        ):
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

    def _on_tab_clicked(self, path: Path) -> None:
        if path == self._current_file:
            return
        self._open_file(path)

    def _on_tab_close(self, path: Path) -> None:
        if path == self._current_file and self._dirty:
            choice = QMessageBox.question(
                self,
                "Unsaved changes",
                f"Save changes to {path.name} before closing?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save,
            )
            if choice == QMessageBox.StandardButton.Cancel:
                return
            if (
                choice == QMessageBox.StandardButton.Save
                and not self._save_current_file()
            ):
                return

        self._file_tab_bar.remove_tab(path)
        if path == self._current_file:
            self._current_file = None
            self._dirty = False
            self._editor.clear()
            self._sync_python_highlighter(None)

    def _open_file(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            return

        if self._dirty and self._current_file and self._current_file != path:
            pass

        self._loading_file = True
        try:
            self._editor.setPlainText(path.read_text(encoding="utf-8"))
            self._current_file = path
            self._dirty = False
            self._file_tab_bar.add_tab(path)
            self._file_tab_bar.set_active(path)
            self._sync_python_highlighter(path)
            self._set_status(f"Opened {path.relative_to(self._workspace)}")
        finally:
            self._loading_file = False

    def _sync_python_highlighter(self, path: Path | None) -> None:
        self._python_highlighter.set_enabled(
            path is not None and path.suffix.lower() == ".py"
        )

    def _mark_dirty(self) -> None:
        if self._loading_file or self._current_file is None:
            return
        if not self._dirty:
            self._dirty = True
            self._file_tab_bar.set_dirty(self._current_file, True)
            self._set_status(
                f"Modified {self._current_file.relative_to(self._workspace)}"
            )

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
        self._file_tab_bar.set_dirty(self._current_file, False)
        self._set_status(f"Saved {self._current_file.relative_to(self._workspace)}")
        return True

    # ── Chat persistence ───────────────────────────────────────────────────────

    def _init_chat_persistence(self) -> None:
        last = read_last_chat_id(self._workspace)
        try:
            if last and chat_file_path(self._workspace, last).is_file():
                state = load_chat_session(self._workspace, last)
                self._apply_chat_state(state)
            elif list_saved_chats(self._workspace):
                cid = list_saved_chats(self._workspace)[0][0]
                state = load_chat_session(self._workspace, cid)
                self._apply_chat_state(state)
                write_last_chat_id(self._workspace, cid)
            else:
                state = fresh_session_state(self._mode)
                self._apply_chat_state(state)
                self._save_current_chat_session()
                write_last_chat_id(self._workspace, self._chat_id)
        except (OSError, ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
            logger.warning("Chat load failed, starting fresh: %s", exc)
            state = fresh_session_state(self._mode)
            self._apply_chat_state(state)
        self._chat_history_panel.refresh()
        self._chat_history_panel.set_active_chat(self._chat_id)

    def _apply_chat_state(self, state: dict[str, Any]) -> None:
        self._chat_id = str(state["chat_id"])
        self._mode = str(state["mode"])
        self._messages = list(state["messages"])
        self._chat_events = list(state["chat_events"])
        self._collapsed_blocks = set(state["collapsed_blocks"])
        self._next_block_id = max(1, int(state["next_block_id"]))
        self._chat_stored_in_archive = bool(state.get("stored_in_archive", False))
        ut = state.get("usage_totals") or {}
        self._chat_usage_totals = {
            "prompt_tokens": int(ut["prompt_tokens"])
            if isinstance(ut.get("prompt_tokens"), (int, float))
            else 0,
            "completion_tokens": int(ut["completion_tokens"])
            if isinstance(ut.get("completion_tokens"), (int, float))
            else 0,
            "total_tokens": int(ut["total_tokens"])
            if isinstance(ut.get("total_tokens"), (int, float))
            else 0,
        }
        self._prompt_input.set_mode(self._mode)
        self._update_chat_placeholder()
        self._render_chat_history(scroll_to_bottom=True)
        self._update_token_badge()

    def _save_current_chat_session(self) -> None:
        if not self._chat_id:
            return
        try:
            save_chat_session(
                self._workspace,
                chat_id=self._chat_id,
                mode=self._mode,
                messages=self._messages,
                chat_events=self._chat_events,
                collapsed_blocks=self._collapsed_blocks,
                next_block_id=self._next_block_id,
                usage_totals=dict(self._chat_usage_totals),
                stored_in_archive=self._chat_stored_in_archive,
            )
        except OSError as exc:
            logger.warning("Failed to save chat: %s", exc)

    def _on_history_chat_selected(self, chat_id: str) -> None:
        if chat_id == self._chat_id:
            return
        if self._worker_thread is not None:
            QMessageBox.warning(
                self,
                "Chat",
                "Дождитесь завершения ответа агента перед сменой чата.",
            )
            self._chat_history_panel.set_active_chat(self._chat_id)
            return
        try:
            self._save_current_chat_session()
            state = load_chat_session(self._workspace, chat_id)
            self._apply_chat_state(state)
            write_last_chat_id(self._workspace, chat_id)
            self._chat_history_panel.set_active_chat(chat_id)
        except (OSError, ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
            QMessageBox.critical(self, "Chat", str(exc))
            self._chat_history_panel.set_active_chat(self._chat_id)

    def _new_chat_clicked(self) -> None:
        if self._worker_thread is not None:
            QMessageBox.warning(
                self,
                "Chat",
                "Дождитесь завершения ответа агента перед созданием нового чата.",
            )
            return
        self._save_current_chat_session()
        state = fresh_session_state(self._mode)
        self._apply_chat_state(state)
        self._save_current_chat_session()
        write_last_chat_id(self._workspace, self._chat_id)
        self._chat_history_panel.refresh()
        self._chat_history_panel.set_active_chat(self._chat_id)

    def _archive_current_chat(self) -> None:
        if self._worker_thread is not None:
            QMessageBox.warning(self, "Chat", "Дождитесь завершения ответа агента.")
            return
        if not self._chat_id or self._chat_stored_in_archive:
            return
        self._save_current_chat_session()
        try:
            move_chat_to_archive(self._workspace, self._chat_id)
        except OSError as exc:
            QMessageBox.critical(self, "Архив", str(exc))
            return

        others = list_saved_chats(self._workspace)
        if others:
            cid = others[0][0]
            try:
                state = load_chat_session(self._workspace, cid)
                self._apply_chat_state(state)
                write_last_chat_id(self._workspace, cid)
            except (
                OSError,
                ValueError,
                FileNotFoundError,
                json.JSONDecodeError,
            ) as exc:
                QMessageBox.critical(self, "Chat", str(exc))
        else:
            state = fresh_session_state(self._mode)
            self._apply_chat_state(state)
            self._save_current_chat_session()
            write_last_chat_id(self._workspace, self._chat_id)
        self._chat_history_panel.refresh()
        self._chat_history_panel.set_active_chat(self._chat_id)

    def _restore_current_from_archive(self) -> None:
        if self._worker_thread is not None:
            QMessageBox.warning(self, "Chat", "Дождитесь завершения ответа агента.")
            return
        if not self._chat_id or not self._chat_stored_in_archive:
            return
        self._save_current_chat_session()
        try:
            move_chat_from_archive(self._workspace, self._chat_id)
        except OSError as exc:
            QMessageBox.critical(self, "Архив", str(exc))
            return
        self._chat_stored_in_archive = False
        self._save_current_chat_session()
        self._chat_history_panel.refresh()
        self._chat_history_panel.set_active_chat(self._chat_id)

    # ── Chat rendering ─────────────────────────────────────────────────────────

    def _new_block_id(self) -> str:
        block_id = f"block-{self._next_block_id}"
        self._next_block_id += 1
        return block_id

    def _scroll_chat_to_bottom(self) -> None:
        if not self._scroll_chat_on_next_load:
            return
        self._scroll_chat_on_next_load = False
        self._chat_view.run_js("window.scrollTo(0, document.body.scrollHeight);")

    def _render_chat_history(self, *, scroll_to_bottom: bool = False) -> None:
        self._scroll_chat_on_next_load = scroll_to_bottom
        html_parts = render_chat_history(self._chat_events, self._collapsed_blocks)
        self._chat_view.set_html("".join(html_parts))

    def _append_chat_message(
        self, role: str, body: str, *, tone: str = "neutral"
    ) -> None:
        self._chat_events.append(
            ChatEvent(kind="message", title=role, body=body, tone=tone)
        )
        self._render_chat_history(scroll_to_bottom=True)

    def _update_chat_placeholder(self) -> None:
        if self._mode == "ask":
            self._prompt_input.set_prompt_placeholder("Ask a question…")
            return
        self._prompt_input.set_prompt_placeholder("Describe a task for the agent…")

    def _reset_chat_session(self, *, announce: bool) -> None:
        self._messages = build_messages(self._mode)
        self._chat_usage_totals = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
        self._update_token_badge()
        self._update_chat_placeholder()
        if announce:
            self._append_chat_message(
                "System",
                f"Switched to `{self._mode}` mode. Conversation context was reset.",
                tone="meta",
            )
        self._set_status(f"Ready ({self._mode} mode)")
        self._save_current_chat_session()

    def _handle_mode_changed(self, mode: str) -> None:
        normalized_mode = normalize_mode(mode)
        if normalized_mode == self._mode:
            return
        self._mode = normalized_mode
        self._reset_chat_session(announce=True)

    def _handle_chat_anchor_clicked(self, token: str) -> None:
        if token.startswith("copy:"):
            block_id = token[len("copy:") :]
            content = get_copy_block(block_id)
            if content:
                QApplication.clipboard().setText(content)
            return

        if token.startswith("toggle:"):
            block_id = token[len("toggle:") :]
            is_group_header = any(
                e.kind == "group_header" and e.block_id == block_id
                for e in self._chat_events
            )
            if block_id in self._collapsed_blocks:
                self._collapsed_blocks.remove(block_id)
                collapsed = False
            else:
                self._collapsed_blocks.add(block_id)
                collapsed = True
            if is_group_header:
                self._render_chat_history()
                return

            safe_content_id = json.dumps(f"chat-content-{block_id}")
            safe_arrow_id = json.dumps(f"chat-arrow-{block_id}")
            arrow = "&rsaquo;" if collapsed else "&#10549;"
            self._chat_view.run_js(
                f"""
                (function() {{
                    var content = document.getElementById({safe_content_id});
                    if (content) {{
                        content.style.display = {"'none'" if collapsed else "''"};
                    }}
                    var arrow = document.getElementById({safe_arrow_id});
                    if (arrow) {{
                        if (arrow.classList && arrow.classList.contains("tool-run-arrow")) {{
                            arrow.innerHTML = "&nbsp;{arrow}";
                        }} else {{
                            arrow.innerHTML = "{arrow}";
                        }}
                    }}
                }})();
                """
            )

    # ── Busy state ─────────────────────────────────────────────────────────────

    def _set_busy(self, busy: bool) -> None:
        self._prompt_input.set_busy(busy)
        self._chat_history_panel.setDisabled(busy)

    # ── Agent interaction ──────────────────────────────────────────────────────

    def _send_chat(self) -> None:
        if self._worker_thread is not None:
            self._set_status("Agent is already running")
            return

        prompt = self._prompt_input.text()
        if not prompt:
            return

        self._prompt_input.clear()
        self._messages.append(UserMessage(prompt))
        self._append_chat_message("You", prompt, tone="user")

        self._turn_prompt_tokens = 0
        self._turn_completion_tokens = 0

        self._work_group_id = self._new_block_id()
        self._work_start_time = time.monotonic()
        group_event = ChatEvent(
            kind="group_header", title="Working…", block_id=self._work_group_id
        )
        self._chat_events.append(group_event)
        self._work_group_header = group_event
        self._render_chat_history(scroll_to_bottom=True)

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
        self._append_step_header(
            step,
            total,
            f"{self._mode.upper()} step {step}/{total}",
            group_id=self._work_group_id,
        )

    def _append_step_header(
        self, step: int, total: int, label: str, *, group_id: str = ""
    ) -> None:
        self._chat_events.append(
            ChatEvent(
                kind="step", title=label, step=step, total=total, group_id=group_id
            )
        )
        self._render_chat_history(scroll_to_bottom=True)

    def _append_code_block(
        self,
        title: str,
        body: str,
        *,
        tone: str = "tool",
        group_id: str = "",
        usage: dict[str, int] | None = None,
    ) -> None:
        block_id = self._new_block_id()
        pu = co = tu = None
        if usage:
            if isinstance(usage.get("prompt_tokens"), int):
                pu = usage["prompt_tokens"]
            if isinstance(usage.get("completion_tokens"), int):
                co = usage["completion_tokens"]
            if isinstance(usage.get("total_tokens"), int):
                tu = usage["total_tokens"]
        self._chat_events.append(
            ChatEvent(
                kind="block",
                title=title,
                body=body,
                tone=tone,
                block_id=block_id,
                collapsible=True,
                group_id=group_id,
                usage_prompt_tokens=pu,
                usage_completion_tokens=co,
                usage_total_tokens=tu,
            )
        )
        self._collapsed_blocks.add(block_id)
        self._render_chat_history(scroll_to_bottom=True)

    def _merge_completion_usage(self, usage: object) -> None:
        if not isinstance(usage, dict):
            return
        pr = usage.get("prompt_tokens")
        co = usage.get("completion_tokens")
        tot = usage.get("total_tokens")
        if isinstance(pr, int):
            self._turn_prompt_tokens += pr
            self._chat_usage_totals["prompt_tokens"] += pr
        if isinstance(co, int):
            self._turn_completion_tokens += co
            self._chat_usage_totals["completion_tokens"] += co
        if isinstance(tot, int):
            self._chat_usage_totals["total_tokens"] += tot
        self._update_token_badge()

    def _update_token_badge(self) -> None:
        p = self._chat_usage_totals["prompt_tokens"]
        c = self._chat_usage_totals["completion_tokens"]
        t = self._chat_usage_totals["total_tokens"]
        extra = f"  Σ {t}" if t else ""
        self._token_status.setText(f"  in {p} / out {c}{extra}")

    def _handle_assistant_response(
        self, step: int, raw_response: str, usage: object = None
    ) -> None:
        self._merge_completion_usage(usage)
        udict = usage if isinstance(usage, dict) else None
        self._append_code_block(
            f"Assistant JSON, step {step}",
            raw_response,
            tone="assistant",
            group_id=self._work_group_id,
            usage=udict,
        )

    def _handle_repair_requested(self, step: int, message: str) -> None:
        self._append_code_block(
            f"Invalid response, step {step}",
            message,
            tone="error",
            group_id=self._work_group_id,
        )

    def _handle_command_executed(self, step: int, command: str, data: object) -> None:
        self._append_code_block(
            f"Tool: {command}",
            format_json(data if isinstance(data, dict) else {"value": data}),
            tone="tool",
            group_id=self._work_group_id,
        )
        if command == "writefile":
            payload = data if isinstance(data, dict) else {}
            path = payload.get("path")
            if isinstance(path, str):
                current = self._current_file
                if (
                    current is not None
                    and str(current.relative_to(self._workspace)) == path
                ):
                    self._loading_file = True
                    try:
                        self._editor.setPlainText(current.read_text(encoding="utf-8"))
                        self._dirty = False
                        self._file_tab_bar.set_dirty(current, False)
                    finally:
                        self._loading_file = False

    def _finalise_work_group(self, *, label: str) -> None:
        if self._work_group_header is not None:
            elapsed = time.monotonic() - self._work_start_time
            tok = ""
            if self._turn_prompt_tokens or self._turn_completion_tokens:
                tok = f"  ·  in {self._turn_prompt_tokens} / out {self._turn_completion_tokens}"
            self._work_group_header.title = f"{label} {_format_duration(elapsed)}{tok}"
            self._collapsed_blocks.add(self._work_group_id)
        self._work_group_id = ""
        self._work_group_header = None

    def _handle_agent_finished(self, result: str, messages: object) -> None:
        if isinstance(messages, list):
            self._messages = list(messages)
        self._finalise_work_group(label="Done in")
        self._append_chat_message("Assistant", result, tone="assistant")
        self._set_status("Ready")
        self._save_current_chat_session()
        self._chat_history_panel.refresh()
        self._chat_history_panel.set_active_chat(self._chat_id)

    def _handle_agent_error(self, message: str) -> None:
        self._finalise_work_group(label="Failed after")
        self._append_chat_message("Error", message, tone="error")
        self._set_status("Agent error")
        self._save_current_chat_session()
        self._chat_history_panel.refresh()
        QMessageBox.critical(self, "Agent error", message)

    # ── Close ──────────────────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:  # noqa: N802
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
            if (
                choice == QMessageBox.StandardButton.Save
                and not self._save_current_file()
            ):
                event.ignore()
                return

        if self._worker_thread is not None:
            self._worker_thread.quit()
            self._worker_thread.wait(1500)

        if self._terminal is not None:
            self._terminal.close()
            self._terminal = None

        self._save_current_chat_session()
        if self._chat_id:
            write_last_chat_id(self._workspace, self._chat_id)

        event.accept()
