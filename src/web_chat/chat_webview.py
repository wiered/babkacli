"""Unified chat web-view widget with WebView2 (Windows) and QWebEngineView (fallback) backends."""

from __future__ import annotations

import logging
import os
import sys

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QVBoxLayout, QWidget

logger = logging.getLogger(__name__)

_USE_WEBVIEW2 = False
if sys.platform == "win32" and os.environ.get("BABKACLI_DISABLE_WEBVIEW2", "").lower() not in (
    "1",
    "true",
    "yes",
):
    try:
        from qtwebview2 import QtWebView2Widget, DictJsBridge

        _USE_WEBVIEW2 = True
    except ImportError:
        logger.info("qtwebview2 not available, falling back to QWebEngineView")

if not _USE_WEBVIEW2:
    from PySide6.QtCore import QUrl
    from PySide6.QtWebEngineCore import QWebEnginePage
    from PySide6.QtWebEngineWidgets import QWebEngineView


_LINK_INTERCEPT_JS = """
(function() {
    if (window.__babka_link_hook) return;
    window.__babka_link_hook = true;
    document.addEventListener('click', function(e) {
        var a = e.target.closest('a');
        if (a && a.href) {
            e.preventDefault();
            if (window.qtwebview2 && window.qtwebview2.api && window.qtwebview2.api.on_link_click) {
                window.qtwebview2.api.on_link_click(a.href);
            }
        }
    }, true);
})();
"""

_BG_COLOR = "#1a1a1a"


class ChatWebView(QWidget):
    """Backend-agnostic chat renderer.

    On Windows with qtwebview2 installed, uses Edge WebView2.
    Otherwise, falls back to Qt WebEngine (QWebEngineView).
    """

    link_activated = Signal(str)
    content_loaded = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        if _USE_WEBVIEW2:
            self._backend = "webview2"
            self._bridge = DictJsBridge()

            @self._bridge.bind_js_api_func
            def on_link_click(url: str) -> None:
                self.link_activated.emit(url)

            self.setStyleSheet(f"background-color: {_BG_COLOR};")
            self._webview = QtWebView2Widget(
                parent=self,
                js_apis=self._bridge,
                background_color=_BG_COLOR,
            )
            self._webview.bridge.domContentLoaded.connect(self._on_dom_loaded)
            layout.addWidget(self._webview, 1)
        else:
            self._backend = "webengine"
            self._webview = QWebEngineView(self)
            self._page = _FallbackChatPage(self._webview)
            self._page.setBackgroundColor(QColor(_BG_COLOR))
            self._webview.setPage(self._page)
            self._webview.setStyleSheet(f"background: {_BG_COLOR};")
            self._page.link_activated.connect(self.link_activated)
            self._webview.loadFinished.connect(self.content_loaded)
            layout.addWidget(self._webview, 1)

    # ── Public API ────────────────────────────────────────────────────────────

    def set_html(self, html: str) -> None:
        """Load *html* into the view."""
        if self._backend == "webview2":
            self._webview.load_html(html)
        else:
            self._webview.setHtml(html)

    def run_js(self, code: str) -> None:
        """Execute JavaScript *code* inside the loaded page."""
        if self._backend == "webview2":
            self._webview.evaluate_js(code)
        else:
            self._webview.page().runJavaScript(code)

    def backend_name(self) -> str:
        return self._backend

    # ── Private ───────────────────────────────────────────────────────────────

    def _on_dom_loaded(self) -> None:
        self._webview.evaluate_js(_LINK_INTERCEPT_JS)
        self.content_loaded.emit()


# ── QWebEngineView fallback (non-Windows / missing qtwebview2) ────────────────

if not _USE_WEBVIEW2:

    class _FallbackChatPage(QWebEnginePage):
        """QWebEnginePage that intercepts link clicks and emits them as signals."""

        link_activated = Signal(str)

        def acceptNavigationRequest(  # noqa: N802
            self, url: QUrl, nav_type, is_main_frame: bool
        ) -> bool:
            if nav_type == QWebEnginePage.NavigationType.NavigationTypeLinkClicked:
                self.link_activated.emit(url.toString())
                return False
            return True
