from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal, Slot
from PySide6.QtGui import QColor
from PySide6.QtQml import QQmlContext
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import QVBoxLayout, QWidget

logger = logging.getLogger(__name__)


class _ChatWebViewBridge(QObject):
    setHtmlRequested = Signal(str)
    scrollRequested = Signal()
    anchorActivated = Signal(str)
    pageLoadFinished = Signal(bool, str)

    @Slot(str)
    def notifyAnchor(self, token: str) -> None:
        self.anchorActivated.emit(token)

    @Slot()
    def notifyLoadSucceeded(self) -> None:
        self.pageLoadFinished.emit(True, "")

    @Slot(str)
    def notifyLoadFailed(self, message: str) -> None:
        self.pageLoadFinished.emit(False, message)


class ChatWebViewHost(QWidget):
    """QWidget wrapper around a QML WebView used by the chat history panel."""

    anchor_activated = Signal(str)
    loadFinished = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._bridge = _ChatWebViewBridge(self)
        self._bridge.anchorActivated.connect(self._emit_anchor_activated)
        self._bridge.pageLoadFinished.connect(self._handle_page_load_finished)

        self._qml_ready = False
        self._page_ready = False
        self._pending_html: str | None = None
        self._scroll_pending = False

        self._quick_widget = QQuickWidget(self)
        self._quick_widget.setObjectName("chatWebViewQuickWidget")
        self._quick_widget.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
        self._quick_widget.setClearColor(QColor("#1a1a1a"))
        self._quick_widget.statusChanged.connect(self._handle_qml_status_changed)

        context = self._quick_widget.rootContext()
        if not isinstance(context, QQmlContext):  # pragma: no cover - defensive
            raise RuntimeError("Qt WebView host did not expose a QQmlContext.")
        context.setContextProperty("bridge", self._bridge)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._quick_widget, 1)

        self._quick_widget.setSource(QUrl.fromLocalFile(str(self._qml_file())))
        if self._quick_widget.status() == QQuickWidget.Status.Error:
            raise RuntimeError(self._format_qml_errors())
        if self._quick_widget.status() == QQuickWidget.Status.Ready:
            self._qml_ready = True

    @staticmethod
    def _qml_file() -> Path:
        return Path(__file__).with_name("chat_webview.qml")

    def _format_qml_errors(self) -> str:
        errors = [error.toString() for error in self._quick_widget.errors()]
        if not errors:
            return "Qt WebView QML host failed to load."
        return "Qt WebView QML host failed to load:\n" + "\n".join(errors)

    def _handle_qml_status_changed(self, status) -> None:
        if status == QQuickWidget.Status.Error:
            logger.error(self._format_qml_errors())
            return
        if status == QQuickWidget.Status.Ready:
            self._qml_ready = True
            if self._pending_html is not None:
                self._dispatch_html(self._pending_html)

    def _dispatch_html(self, html: str) -> None:
        self._page_ready = False
        self._bridge.setHtmlRequested.emit(html)

    def _emit_anchor_activated(self, token: str) -> None:
        self.anchor_activated.emit(token)

    def _handle_page_load_finished(self, ok: bool, message: str) -> None:
        self._page_ready = ok
        self.loadFinished.emit(ok)
        if not ok:
            logger.warning("Qt WebView failed to load chat HTML: %s", message)
            return
        if self._scroll_pending:
            self._scroll_pending = False
            self._bridge.scrollRequested.emit()

    def set_chat_html(self, html: str) -> None:
        self._pending_html = html
        if not self._qml_ready:
            return
        self._dispatch_html(html)

    def scroll_to_bottom(self) -> None:
        self._scroll_pending = True
        if self._qml_ready and self._page_ready:
            self._scroll_pending = False
            self._bridge.scrollRequested.emit()
