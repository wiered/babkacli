from __future__ import annotations

import sys

if sys.platform.startswith("win32"):
    import winreg


_WEBVIEW2_CLIENT_GUID = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
_WEBVIEW2_REGISTRY_LOCATIONS = (
    (
        winreg.HKEY_LOCAL_MACHINE,
        rf"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{_WEBVIEW2_CLIENT_GUID}",
    ),
    (
        winreg.HKEY_CURRENT_USER,
        rf"Software\Microsoft\EdgeUpdate\Clients\{_WEBVIEW2_CLIENT_GUID}",
    ),
) if sys.platform.startswith("win32") else ()


class QtWebViewSetupError(RuntimeError):
    """Raised when the Qt WebView stack cannot be initialized safely."""


def initialize_qt_webview() -> None:
    """Import the required Qt WebView modules and initialize the backend."""

    try:
        from PySide6.QtQuickWidgets import QQuickWidget  # noqa: F401
        from PySide6.QtQml import QQmlContext  # noqa: F401
        from PySide6.QtWebView import QtWebView
    except ImportError as exc:
        raise QtWebViewSetupError(
            "PySide6 is missing Qt WebView dependencies. "
            "Install a build that includes QtQuickWidgets, QtQml, and QtWebView."
        ) from exc

    try:
        QtWebView.initialize()
    except Exception as exc:  # pragma: no cover - depends on local Qt runtime
        raise QtWebViewSetupError(
            "Qt WebView failed to initialize before QApplication startup."
        ) from exc


def detect_webview2_runtime_version() -> str | None:
    """Return the installed WebView2 Runtime version, or None if unavailable."""

    if not sys.platform.startswith("win32"):
        return None

    for hive, path in _WEBVIEW2_REGISTRY_LOCATIONS:
        try:
            with winreg.OpenKey(hive, path) as key:
                value, _ = winreg.QueryValueEx(key, "pv")
        except OSError:
            continue
        if isinstance(value, str) and value and value != "0.0.0.0":
            return value
    return None


def ensure_windows_webview2_runtime() -> str | None:
    """Fail fast on Windows when the Microsoft Edge WebView2 Runtime is missing."""

    if not sys.platform.startswith("win32"):
        return None

    version = detect_webview2_runtime_version()
    if version is None:
        raise QtWebViewSetupError(
            "Microsoft Edge WebView2 Runtime is required on Windows for the chat panel.\n\n"
            "Install the Evergreen WebView2 Runtime and launch the UI again."
        )
    return version
