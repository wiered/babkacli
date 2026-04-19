"""Chat History sidebar panel for BabkaCode.

Renders saved chat sessions as clickable cards with title, preview
and relative timestamp.  Replaces the old QComboBox chat selector.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

if __package__ in {None, ""}:
    import sys

    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from src.ui.design_tokens import SP_8, SP_12, SP_16
    from src.web_chat.chat_storage import list_saved_chats
else:
    from .design_tokens import SP_8, SP_12, SP_16
    from ..web_chat.chat_storage import list_saved_chats


def _relative_time(mtime: float) -> str:
    """Return a human-readable relative timestamp string."""
    now = datetime.now(timezone.utc).timestamp()
    delta = now - mtime
    if delta < 60:
        return "just now"
    if delta < 3600:
        mins = int(delta / 60)
        return f"{mins}m ago"
    if delta < 86400:
        hours = int(delta / 3600)
        return f"{hours}h ago"
    days = int(delta / 86400)
    if days == 1:
        return "yesterday"
    if days < 7:
        return f"{days}d ago"
    weeks = int(days / 7)
    if weeks == 1:
        return "1w ago"
    return f"{weeks}w ago"


class _ChatCard(QFrame):
    """A single clickable chat card."""

    clicked = Signal(str)  # chat_id
    archive_requested = Signal(str)  # chat_id (context menu / button)

    def __init__(
        self,
        chat_id: str,
        title: str,
        mtime: float,
        is_active: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._chat_id = chat_id
        self._is_active = is_active

        self.setObjectName("chatCardActive" if is_active else "chatCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SP_12, SP_8 + 2, SP_12, SP_8 + 2)
        layout.setSpacing(3)

        # Title row
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(4)

        title_label = QLabel(title or "Untitled chat")
        title_label.setObjectName("chatCardTitle")
        title_label.setWordWrap(False)
        title_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        title_row.addWidget(title_label, 1)

        date_label = QLabel(_relative_time(mtime))
        date_label.setObjectName("chatCardDate")
        date_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        title_row.addWidget(date_label, 0)

        layout.addLayout(title_row)

    @property
    def chat_id(self) -> str:
        return self._chat_id

    def set_active(self, active: bool) -> None:
        if self._is_active == active:
            return
        self._is_active = active
        self.setObjectName("chatCardActive" if active else "chatCard")
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._chat_id)
        super().mousePressEvent(event)


class ChatHistoryPanel(QWidget):
    """Sidebar panel that lists all saved chats as cards.

    Signals:
        chat_selected(str): Emitted when user clicks a chat card.
        new_chat_requested():  Emitted when the "+ New Chat" button is pressed.
        archive_requested(str): Emitted when user wants to archive a chat.
    """

    chat_selected = Signal(str)
    new_chat_requested = Signal()
    archive_requested = Signal(str)

    def __init__(self, workspace: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._workspace = workspace
        self._active_chat_id: str = ""
        self._cards: dict[str, _ChatCard] = {}

        self.setObjectName("chatHistoryPanel")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Header
        header = QWidget(self)
        header.setFixedHeight(44)
        header.setObjectName("sidebarContent")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(SP_16, 0, SP_8, 0)
        header_layout.setSpacing(8)

        header_label = QLabel("CHATS")
        header_label.setObjectName("panelHeader")
        header_layout.addWidget(header_label, 1)

        self._archive_btn = QPushButton("Archive")
        self._archive_btn.setObjectName("inlineButton")
        self._archive_btn.setFixedHeight(24)
        self._archive_btn.setToolTip("Archive current chat")
        self._archive_btn.clicked.connect(
            lambda: self.archive_requested.emit(self._active_chat_id)
        )
        header_layout.addWidget(self._archive_btn, 0)

        root_layout.addWidget(header)

        # Scroll area
        scroll = QScrollArea(self)
        scroll.setObjectName("chatHistoryScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._cards_container = QWidget()
        self._cards_container.setObjectName("sidebarContent")
        self._cards_container.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred
        )
        self._cards_layout = QVBoxLayout(self._cards_container)
        self._cards_layout.setContentsMargins(SP_8, SP_8, SP_8, SP_8)
        self._cards_layout.setSpacing(SP_8 - 2)
        self._cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # "New Chat" button
        self._new_btn = QPushButton("  +  New Chat")
        self._new_btn.setObjectName("newChatButton")
        self._new_btn.setMinimumHeight(36)
        self._new_btn.clicked.connect(self.new_chat_requested)
        self._cards_layout.addWidget(self._new_btn)

        scroll.setWidget(self._cards_container)
        root_layout.addWidget(scroll, 1)

    # ── Public API ──────────────────────────────────────────────────────────────

    def set_workspace(self, workspace: Path) -> None:
        self._workspace = workspace
        self.refresh()

    def set_active_chat(self, chat_id: str) -> None:
        if self._active_chat_id == chat_id:
            return
        if self._active_chat_id in self._cards:
            self._cards[self._active_chat_id].set_active(False)
        self._active_chat_id = chat_id
        if chat_id in self._cards:
            self._cards[chat_id].set_active(True)

    def refresh(self) -> None:
        """Rebuild cards from storage (call after chats change)."""
        while self._cards_layout.count() > 1:
            item = self._cards_layout.takeAt(1)
            if item and item.widget():
                item.widget().deleteLater()
        self._cards.clear()

        rows = list_saved_chats(self._workspace)
        for chat_id, mtime, title in rows:
            is_active = chat_id == self._active_chat_id
            card = _ChatCard(
                chat_id, title, mtime, is_active=is_active, parent=self._cards_container
            )
            card.clicked.connect(self._on_card_clicked)
            self._cards[chat_id] = card
            self._cards_layout.addWidget(card)

    # ── Private ─────────────────────────────────────────────────────────────────

    def _on_card_clicked(self, chat_id: str) -> None:
        self.set_active_chat(chat_id)
        self.chat_selected.emit(chat_id)
