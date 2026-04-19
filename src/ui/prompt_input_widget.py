"""Dedicated prompt input widget for the chat panel."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEasingCurve, QSize, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QFont, QMovie, QPixmap, QResizeEvent
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

if __package__ in {None, ""}:
    import sys

    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from src.ui.design_tokens import ACCENT, BG_SURFACE
else:
    from .design_tokens import ACCENT, BG_SURFACE


class _AnimatedSendButton(QPushButton):
    """Send button that morphs between cross and arrow states."""

    def __init__(self, assets_dir: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sendButtonRound")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Send (Ctrl+Enter)")
        self.setFixedSize(32, 32)
        self.setIconSize(QSize(16, 16))
        self.setProperty("filled", False)
        self.setStyleSheet("border: none;")

        self._icon_label = QLabel(self)
        self._icon_label.setObjectName("sendButtonIcon")
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self._cross_pixmap = QPixmap(str(assets_dir / "cross.png"))
        self._arrow_pixmap = QPixmap(str(assets_dir / "arrow_up.png"))
        self._movie_to_arrow = self._build_movie(assets_dir / "cross_to_arrow.gif")
        self._movie_to_cross = self._build_movie(assets_dir / "arrow_to_cross.gif")
        self._movie: QMovie | None = None
        self._filled = False
        self._target_filled = False
        self._bg_surface = QColor(BG_SURFACE)
        self._bg_accent = QColor(ACCENT)
        self._background_color = QColor(self._bg_surface)
        self._bg_animation = QVariantAnimation(self)
        self._bg_animation.setDuration(180)
        self._bg_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._bg_animation.valueChanged.connect(self._handle_bg_value_changed)

        if self._movie_to_arrow is not None:
            self._movie_to_arrow.frameChanged.connect(
                self._handle_movie_frame_changed
            )
        if self._movie_to_cross is not None:
            self._movie_to_cross.frameChanged.connect(
                self._handle_movie_frame_changed
            )

        self._apply_static_state(False)

    def _build_movie(self, path: Path) -> QMovie | None:
        if not path.is_file():
            return None
        movie = QMovie(str(path))
        movie.setCacheMode(QMovie.CacheMode.CacheAll)
        movie.setScaledSize(self.iconSize())
        return movie

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._icon_label.setGeometry(self.rect())

    def set_has_text(self, has_text: bool) -> None:
        if has_text == self._target_filled and self._movie is not None:
            return
        if has_text == self._filled and self._movie is None:
            return
        self._target_filled = has_text
        self._play_transition()

    def _play_transition(self) -> None:
        if self._movie is not None:
            self._movie.stop()
            self._movie = None

        if self._target_filled == self._filled:
            self._apply_static_state(self._filled)
            return

        movie = self._movie_to_arrow if self._target_filled else self._movie_to_cross
        if movie is None:
            self._filled = self._target_filled
            self._apply_static_state(self._filled)
            return

        self._movie = movie
        self._icon_label.setMovie(movie)
        movie.jumpToFrame(0)
        movie.start()

    def _handle_movie_frame_changed(self, frame_number: int) -> None:
        movie = self.sender()
        if movie is not self._movie or not isinstance(movie, QMovie):
            return
        frame_count = movie.frameCount()
        if frame_count <= 0 or frame_number < frame_count - 1:
            return
        movie.stop()
        self._filled = self._target_filled
        self._movie = None
        self._apply_static_state(self._filled)

    def _apply_static_state(self, filled: bool) -> None:
        self._filled = filled
        self._target_filled = filled
        self._icon_label.setMovie(None)
        self._animate_background(self._bg_accent if filled else self._bg_surface)
        pixmap = self._arrow_pixmap if filled else self._cross_pixmap
        self._icon_label.setPixmap(
            pixmap.scaled(
                self.iconSize(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        self.setProperty("filled", filled)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def _animate_background(self, color: QColor) -> None:
        end_value = QColor(color)
        self._bg_animation.stop()
        self._bg_animation.setStartValue(QColor(self._background_color))
        self._bg_animation.setEndValue(end_value)
        self._bg_animation.start()

    def _handle_bg_value_changed(self, value) -> None:
        color = value if isinstance(value, QColor) else QColor(value)
        self._background_color = QColor(color)
        self.setStyleSheet(
            "border: none;"
            f"background-color: {self._background_color.name()};"
            "border-radius: 16px;"
        )


class PromptInputWidget(QFrame):
    """Prompt editor with mode selector and animated send button."""

    send_requested = Signal()
    mode_changed = Signal(str)

    def __init__(
        self,
        *,
        modes: tuple[str, ...],
        initial_mode: str,
        assets_dir: Path,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("promptInputWidget")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self._editor = QPlainTextEdit(self)
        self._editor.setObjectName("chatInputEditor")
        self._editor.setMinimumHeight(60)
        self._editor.setMaximumHeight(120)
        self._editor.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.MinimumExpanding,
        )
        self._editor.textChanged.connect(self._sync_send_button_state)
        layout.addWidget(self._editor, 1)

        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(0, 0, 0, 0)
        bottom_row.setSpacing(8)

        self._mode_selector = QComboBox(self)
        self._mode_selector.setObjectName("modeDropdown")
        for mode in modes:
            self._mode_selector.addItem(mode.capitalize(), mode)
        self.set_mode(initial_mode)
        self._mode_selector.currentIndexChanged.connect(self._emit_mode_changed)
        bottom_row.addWidget(self._mode_selector, 0, Qt.AlignmentFlag.AlignLeft)
        bottom_row.addStretch(1)

        self._send_button = _AnimatedSendButton(assets_dir, self)
        self._send_button.clicked.connect(self.send_requested.emit)
        bottom_row.addWidget(self._send_button, 0, Qt.AlignmentFlag.AlignRight)

        layout.addLayout(bottom_row)
        self._sync_send_button_state()

    def _emit_mode_changed(self, index: int) -> None:
        mode = self._mode_selector.itemData(index)
        if isinstance(mode, str):
            self.mode_changed.emit(mode)

    def _sync_send_button_state(self) -> None:
        self._send_button.set_has_text(bool(self.text()))

    def set_mode(self, mode: str) -> None:
        self._mode_selector.blockSignals(True)
        index = self._mode_selector.findData(mode)
        if index >= 0:
            self._mode_selector.setCurrentIndex(index)
        self._mode_selector.blockSignals(False)

    def set_prompt_placeholder(self, text: str) -> None:
        self._editor.setPlaceholderText(text)

    def set_font(self, font: QFont) -> None:
        self._editor.setFont(font)

    def set_tab_changes_focus(self, enabled: bool) -> None:
        self._editor.setTabChangesFocus(enabled)

    def set_busy(self, busy: bool) -> None:
        self._editor.setDisabled(busy)
        self._mode_selector.setDisabled(busy)
        self._send_button.setDisabled(busy)

    def text(self) -> str:
        return self._editor.toPlainText().strip()

    def clear(self) -> None:
        self._editor.clear()

    def focus_editor(self) -> None:
        self._editor.setFocus()
