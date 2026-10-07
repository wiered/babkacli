"""Unified chat web-view widget with WebView2 (Windows) and QWebEngineView (fallback) backends."""

from __future__ import annotations

import logging
import os
import sys

from PySide6.QtCore import QEvent, Qt, Signal, Slot
from PySide6.QtGui import QColor
from PySide6.QtGui import QMoveEvent, QResizeEvent, QShowEvent
from PySide6.QtWidgets import QWidget
from ..utils.config import debug_colors_enabled

logger = logging.getLogger(__name__)

_USE_WEBVIEW2 = False
if sys.platform == "win32" and os.environ.get(
    "BABKACLI_DISABLE_WEBVIEW2", ""
).lower() not in (
    "1",
    "true",
    "yes",
):
    try:
        from qtwebview2 import QtWebView2Widget, DictJsBridge
        import win32gui
        import win32con

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

_BG_COLOR = "#14161c"
_DEBUG_CHAT_VIEW_BG = "rgba(0, 255, 255, 0.18)"
_DEBUG_CHAT_VIEW_BORDER = "#00e5ff"
_DEBUG_NATIVE_HOST_BG = "rgba(255, 255, 0, 0.16)"
_DEBUG_NATIVE_HOST_BORDER = "#ffd400"


if _USE_WEBVIEW2:

    class _ChatNativeHost(QWidget):
        """Native host window that moves with Qt layouts."""

        def __init__(self, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
            self.setAttribute(Qt.WidgetAttribute.WA_DontCreateNativeAncestors, True)
            self.setStyleSheet(
                "background-color: "
                f"{_DEBUG_NATIVE_HOST_BG};"
                f"border: 2px solid {_DEBUG_NATIVE_HOST_BORDER};"
            ) if debug_colors_enabled() else self.setStyleSheet(
                f"background-color: {_BG_COLOR}; border: none;"
            )
            self.winId()

    class _ChatQtWebView2Widget(QtWebView2Widget):
        """Project-local wrapper around qtwebview2 with reliable native bounds sync."""

        @Slot(bool, str)
        def _on_initialization_completed(self, success: bool, error_message: str):
            """Embed WebView2 directly into the dedicated native host widget."""
            if not success:
                logger.error(f"WebView initialization error: {error_message}")
                self.deleteLater()
                return

            core_webview = self._webview.CoreWebView2
            settings = core_webview.Settings
            settings.IsScriptEnabled = True
            settings.IsWebMessageEnabled = True
            settings.AreDefaultScriptDialogsEnabled = True
            settings.AreDevToolsEnabled = self._debug_enabled
            settings.AreBrowserAcceleratorKeysEnabled = self._debug_enabled
            settings.AreDefaultContextMenusEnabled = self._context_menus_enabled
            if self._user_agent:
                settings.UserAgent = self._user_agent

            if self._handle_new_window:
                core_webview.NewWindowRequested += self._on_new_window_request

            core_webview.ContainsFullScreenElementChanged += (
                self._on_contains_fullscreen_element_changed
            )

            if self._init_settings_hook:
                try:
                    self._init_settings_hook(core_webview)
                except Exception as exc:
                    logger.error(
                        "Error in init_settings_hook: %r",
                        exc,
                        exc_info=True,
                    )

            self.is_ready = True
            self._webview_hwnd = self._webview.Handle.ToInt32()
            host = self.parentWidget()
            if host is None:
                logger.error("WebView2 host widget is missing")
                self.deleteLater()
                return
            host_hwnd = int(host.winId())
            if not host_hwnd or not win32gui.IsWindow(host_hwnd):
                logger.error("WebView2 host HWND is invalid")
                self.deleteLater()
                return

            win32gui.SetParent(self._webview_hwnd, host_hwnd)
            style = win32gui.GetWindowLong(self._webview_hwnd, win32con.GWL_STYLE)
            win32gui.SetWindowLong(
                self._webview_hwnd,
                win32con.GWL_STYLE,
                style & ~win32con.WS_BORDER | win32con.WS_CHILD,
            )

            self._webview.Visible = self.isVisible()
            core_webview.DOMContentLoaded += lambda sender, args: (
                self.bridge.domContentLoaded.emit()
            )

            if self.wsgi_app:
                logger.info(
                    "WSGI application detected. Intercepting requests for host: %s",
                    self.wsgi_host_name,
                )
                # Chat view does not use WSGI hosting right now.

            win32gui.ShowWindow(self._webview_hwnd, win32con.SW_SHOW)
            self._sync_native_bounds()

            if self.url:
                self.load_url(self.url)

            for method_name, args, kwargs in self._pending_calls:
                getattr(self, method_name)(*args, **kwargs)
            self._pending_calls.clear()

        def event(self, event):  # noqa: ANN001
            result = super().event(event)
            if event.type() in {
                QEvent.Type.LayoutRequest,
                QEvent.Type.ParentChange,
                QEvent.Type.WinIdChange,
            }:
                self._sync_native_bounds()
            return result

        def moveEvent(self, event: QMoveEvent) -> None:  # noqa: N802
            super().moveEvent(event)
            self._sync_native_bounds()

        def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
            super().resizeEvent(event)
            self._sync_native_bounds()

        def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
            super().showEvent(event)
            self._sync_native_bounds()

        def _resize_webview(self) -> None:
            self._sync_native_bounds()

        def _sync_native_bounds(self) -> None:
            hwnd = getattr(self, "_webview_hwnd", None)
            if not hwnd or not win32gui.IsWindow(hwnd):
                return
            host = self.parentWidget()
            if host is None:
                return
            host_hwnd = int(host.winId())
            if not host_hwnd or not win32gui.IsWindow(host_hwnd):
                return
            if win32gui.GetParent(hwnd) != host_hwnd:
                win32gui.SetParent(hwnd, host_hwnd)
                style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
                win32gui.SetWindowLong(
                    hwnd,
                    win32con.GWL_STYLE,
                    style & ~win32con.WS_BORDER | win32con.WS_CHILD,
                )
            dpr = 1.0
            if host.windowHandle() is not None:
                dpr = host.windowHandle().devicePixelRatio()
            physical_width = max(0, int(round(host.width() * dpr)))
            physical_height = max(0, int(round(host.height() * dpr)))
            win32gui.SetWindowPos(
                hwnd,
                0,
                0,
                0,
                physical_width,
                physical_height,
                win32con.SWP_NOACTIVATE
                | win32con.SWP_NOOWNERZORDER
                | win32con.SWP_NOZORDER
                | win32con.SWP_SHOWWINDOW,
            )


class ChatWebView(QWidget):
    """Backend-agnostic chat renderer.

    On Windows with qtwebview2 installed, uses Edge WebView2.
    Otherwise, falls back to Qt WebEngine (QWebEngineView).
    """

    link_activated = Signal(str)
    content_loaded = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(
            "background-color: "
            f"{_DEBUG_CHAT_VIEW_BG};"
            f"border: 2px solid {_DEBUG_CHAT_VIEW_BORDER};"
        ) if debug_colors_enabled() else self.setStyleSheet(
            f"background-color: {_BG_COLOR}; border: none;"
        )

        if _USE_WEBVIEW2:
            self._backend = "webview2"
            self._bridge = DictJsBridge()

            @self._bridge.bind_js_api_func
            def on_link_click(url: str) -> None:
                self.link_activated.emit(url)

            self._native_host = _ChatNativeHost(self)
            self._webview = _ChatQtWebView2Widget(
                parent=self._native_host,
                js_apis=self._bridge,
                background_color=_BG_COLOR,
            )
            self._webview.bridge.domContentLoaded.connect(self._on_dom_loaded)
        else:
            self._backend = "webengine"
            self._native_host = None
            self._webview = QWebEngineView(self)
            self._page = _FallbackChatPage(self._webview)
            self._page.setBackgroundColor(QColor(_BG_COLOR))
            self._webview.setPage(self._page)
            self._webview.setStyleSheet(
                f"background: {_DEBUG_NATIVE_HOST_BG};"
                f"border: 2px solid {_DEBUG_NATIVE_HOST_BORDER};"
            ) if debug_colors_enabled() else self._webview.setStyleSheet(
                f"background-color: {_BG_COLOR}; border: none;"
            )
            self._page.link_activated.connect(self.link_activated)
            self._webview.loadFinished.connect(self.content_loaded)
        self._sync_child_geometry()

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

    def sync_native_geometry(self) -> None:
        self._sync_backend_geometry()

    def event(self, event):  # noqa: ANN001
        result = super().event(event)
        if event.type() == QEvent.Type.LayoutRequest:
            self._sync_backend_geometry()
        return result

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._sync_backend_geometry()

    def moveEvent(self, event: QMoveEvent) -> None:  # noqa: N802
        super().moveEvent(event)
        self._sync_backend_geometry()

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        self._sync_backend_geometry()

    # ── Private ───────────────────────────────────────────────────────────────

    def _on_dom_loaded(self) -> None:
        self._webview.evaluate_js(_LINK_INTERCEPT_JS)
        self.content_loaded.emit()

    def _sync_child_geometry(self) -> None:
        target = self.rect()
        if self._native_host is not None and self._native_host.geometry() != target:
            self._native_host.setGeometry(target)
        parent_rect = (
            self._native_host.rect() if self._native_host is not None else target
        )
        if self._webview.geometry() != parent_rect:
            self._webview.setGeometry(parent_rect)

    def _sync_backend_geometry(self) -> None:
        self._sync_child_geometry()
        sync_native_bounds = getattr(self._webview, "_sync_native_bounds", None)
        if callable(sync_native_bounds):
            sync_native_bounds()


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
