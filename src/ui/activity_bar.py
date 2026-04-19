"""Activity Bar widget -- vertical icon rail for BabkaCode.

A fixed-width (48px) vertical strip that lives on the left edge of the main
window.  Clicking an icon swaps the contextual sidebar content and emits
``view_requested`` with the view identifier string.

View identifiers:
    "explorer"   -- file tree
    "history"    -- chat history cards
    "settings"   -- (future) settings panel
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import (
    QSizePolicy,
    QSpacerItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

if __package__ in {None, ""}:
    import sys
    from pathlib import Path

    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from src.ui.design_tokens import ACCENT, ACTIVITY_BAR_W
else:
    from .design_tokens import ACCENT, ACTIVITY_BAR_W


# ── Unicode icon glyphs (no external SVG dependency needed) ──────────────────

_ICONS: dict[str, str] = {
    "explorer": "⌂",  # file/home
    "history": "⊡",  # clock/history
    "settings": "⚙",  # gear
}

# Nerd Font code points if available (rendered as text in the button)
_NERD_ICONS: dict[str, str] = {
    "explorer": "\uf07c",  # nf-fa-folder_open
    "history": "\uf017",  # nf-fa-clock_o
    "settings": "\uf013",  # nf-fa-cog
}

_TOOLTIPS: dict[str, str] = {
    "explorer": "Explorer",
    "history": "Chat History",
    "settings": "Settings",
}

_TOP_VIEWS = ["explorer", "history"]
_BOTTOM_VIEWS = ["settings"]


class _ActivityButton(QToolButton):
    """Single icon button in the activity bar with an active-state left border."""

    def __init__(
        self, view_id: str, icon_text: str, tooltip: str, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._view_id = view_id
        self._active = False
        self._icon_text = icon_text

        self.setText(icon_text)
        self.setToolTip(tooltip)
        self.setFixedSize(QSize(ACTIVITY_BAR_W, ACTIVITY_BAR_W))
        self.setObjectName("activityBtn")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAutoRaise(True)

        font = QFont()
        font.setPointSize(14)
        self.setFont(font)

    @property
    def view_id(self) -> str:
        return self._view_id

    def set_active(self, active: bool) -> None:
        if self._active == active:
            return
        self._active = active
        self.setObjectName("activityBtnActive" if active else "activityBtn")
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        if self._active:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(ACCENT))
            painter.drawRoundedRect(0, (self.height() - 20) // 2, 3, 20, 2, 2)
            painter.end()


class ActivityBar(QWidget):
    """Vertical 48-px icon strip.

    Signals:
        view_requested(str): Emitted when the user clicks an icon.
                             Carries the view identifier (e.g. "explorer").
    """

    view_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("activityBar")
        self.setFixedWidth(ACTIVITY_BAR_W)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

        self._buttons: dict[str, _ActivityButton] = {}
        self._active_view: str = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 12, 8, 12)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        for view_id in _TOP_VIEWS:
            btn = self._make_button(view_id)
            layout.addWidget(btn, 0, Qt.AlignmentFlag.AlignHCenter)

        layout.addSpacerItem(
            QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        )

        for view_id in _BOTTOM_VIEWS:
            btn = self._make_button(view_id)
            layout.addWidget(btn, 0, Qt.AlignmentFlag.AlignHCenter)

    # ── Public API ─────────────────────────────────────────────────────────────

    def set_active_view(self, view_id: str) -> None:
        """Highlight the button for *view_id* and clear all others."""
        if self._active_view == view_id:
            return
        if self._active_view and self._active_view in self._buttons:
            self._buttons[self._active_view].set_active(False)
        self._active_view = view_id
        if view_id in self._buttons:
            self._buttons[view_id].set_active(True)

    def active_view(self) -> str:
        return self._active_view

    # ── Private ────────────────────────────────────────────────────────────────

    def _make_button(self, view_id: str) -> _ActivityButton:
        icon_text = _NERD_ICONS.get(view_id, _ICONS.get(view_id, "?"))
        tooltip = _TOOLTIPS.get(view_id, view_id.capitalize())
        btn = _ActivityButton(view_id, icon_text, tooltip, self)
        btn.clicked.connect(lambda checked=False, v=view_id: self._on_clicked(v))
        self._buttons[view_id] = btn
        return btn

    def _on_clicked(self, view_id: str) -> None:
        self.set_active_view(view_id)
        self.view_requested.emit(view_id)
