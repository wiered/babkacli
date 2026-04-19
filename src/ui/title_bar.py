"""Custom title bar widget for the main window.

Compact 36px dark strip: app icon + BabkaCode (left), workspace path,
model badge, window controls (far right).

On Windows, window move/maximize follow prototype DemoWindow: no custom
mouse logic here -- only LowLevelNativeChromeMixin on the top-level window.
Non-Windows keeps manual drag/double-click like a plain frameless window.
"""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtGui import QIcon, QMouseEvent, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QToolButton, QWidget

if __package__ in {None, ""}:
    import sys

    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from src.ui.design_tokens import TITLE_BAR_H
else:
    from .design_tokens import TITLE_BAR_H

_ASSETS = Path(__file__).parent / "assets"
_APP_ICON = _ASSETS / "diamond.png"


def build_app_icon() -> QIcon:
    return QIcon(str(_APP_ICON))


class TitleBar(QWidget):
    """Compact 36px title strip with app identity."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        show_app_identity: bool = True,
        show_window_controls: bool = True,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("titleBar")
        self.setFixedHeight(TITLE_BAR_H)
        self._show_window_controls = show_window_controls

        self._dragging = False
        self._drag_start_pos = QPoint()
        self._window_start_pos = QPoint()
        self._drag_from_maximized = False
        self._press_offset = QPoint()

        # App icon
        self._app_icon = QLabel("")
        self._app_icon.setObjectName("titleIconLabel")
        icon_pixmap = QPixmap(str(_APP_ICON))
        if not icon_pixmap.isNull():
            self._app_icon.setPixmap(
                icon_pixmap.scaled(
                    18,
                    18,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        self._app_icon.setFixedSize(18, 18)

        # App name
        self._title_label = QLabel("BabkaCode")
        self._title_label.setObjectName("titleLabel")

        # Workspace path label
        self._workspace_label = QLabel("")
        self._workspace_label.setObjectName("workspacePathLabel")

        # Model badge
        self._model_badge = QLabel("")
        self._model_badge.setObjectName("modelBadge")

        # Window controls
        self._min_button = self._make_icon_button("minimize.png", "Minimize")
        self._max_button = self._make_icon_button("maximize.png", "Maximize")
        self._close_button = self._make_icon_button("close.png", "Close", danger=True)

        self._min_button.clicked.connect(self._handle_minimize)
        self._max_button.clicked.connect(self._handle_maximize_restore)
        self._close_button.clicked.connect(self._handle_close)

        controls = QWidget(self)
        controls.setObjectName("titleBarControls")
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(2)
        controls_layout.addWidget(self._min_button)
        controls_layout.addWidget(self._max_button)
        controls_layout.addWidget(self._close_button)
        controls.setVisible(self._show_window_controls)
        self._controls = controls

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 8, 0)
        layout.setSpacing(8)
        layout.addWidget(self._app_icon, 0)
        layout.addWidget(self._title_label, 0)
        layout.addWidget(self._workspace_label, 1)
        layout.addWidget(self._model_badge, 0)
        if self._show_window_controls:
            layout.addSpacing(4)
            layout.addWidget(controls, 0)

        self._app_icon.setVisible(show_app_identity)
        self._title_label.setVisible(show_app_identity)

        self.sync_window_state()

    def set_metadata(self, *, title: str, workspace: str, model: str) -> None:
        self._title_label.setText(title)
        self._workspace_label.setText(workspace)
        self._model_badge.setText(f"  {model}  ")

    def sync_window_state(self) -> None:
        window = self.window()
        maximized = bool(window is not None and window.isMaximized())
        self._max_button.setIcon(QIcon(str(_ASSETS / "maximize.png")))
        self._max_button.setToolTip("Restore" if maximized else "Maximize")

    def _make_icon_button(
        self, icon_filename: str, tooltip: str, *, danger: bool = False
    ) -> QToolButton:
        btn = QToolButton(self)
        obj_name = "titleBtnClose" if danger else "titleBtn"
        btn.setObjectName(obj_name)
        icon_path = _ASSETS / icon_filename
        btn.setIcon(QIcon(str(icon_path)))
        btn.setIconSize(QSize(20, 20))
        btn.setToolTip(tooltip)
        btn.setCursor(Qt.CursorShape.ArrowCursor)
        btn.setAutoRaise(True)
        btn.setFixedSize(28, 28)
        return btn

    def _handle_minimize(self) -> None:
        window = self.window()
        if window is not None:
            window.showMinimized()

    def _handle_maximize_restore(self) -> None:
        window = self.window()
        if window is None:
            return
        if window.isMaximized():
            window.showNormal()
        else:
            window.showMaximized()
        self.sync_window_state()

    def _handle_close(self) -> None:
        window = self.window()
        if window is not None:
            window.close()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if os.name == "nt":
            return super().mousePressEvent(event)

        if event.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(event)

        window = self.window()
        if window is None:
            return super().mousePressEvent(event)

        self._dragging = True
        self._drag_start_pos = event.globalPosition().toPoint()
        self._window_start_pos = window.pos()
        self._drag_from_maximized = window.isMaximized()
        self._press_offset = self.mapTo(window, event.position().toPoint())
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if os.name == "nt":
            return super().mouseMoveEvent(event)
        if not self._dragging or not (event.buttons() & Qt.MouseButton.LeftButton):
            return super().mouseMoveEvent(event)

        window = self.window()
        if window is None:
            return super().mouseMoveEvent(event)

        current_pos = event.globalPosition().toPoint()
        delta = current_pos - self._drag_start_pos

        if self._drag_from_maximized and window.isMaximized():
            window.showNormal()
            self._drag_from_maximized = False
            window.move(current_pos - self._press_offset)
            self._window_start_pos = window.pos()
            self._drag_start_pos = current_pos
            event.accept()
            return

        window.move(self._window_start_pos + delta)
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if os.name == "nt":
            return super().mouseReleaseEvent(event)
        self._dragging = False
        self._drag_from_maximized = False
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if os.name == "nt":
            return super().mouseDoubleClickEvent(event)
        if event.button() != Qt.MouseButton.LeftButton:
            return super().mouseDoubleClickEvent(event)
        self._handle_maximize_restore()
        event.accept()
