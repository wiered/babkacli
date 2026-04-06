"""
Low-level Win32 chrome for frameless Qt windows.

This module is the canonical copy of the Win32 section of prototype.py
(LowLevelNativeChromeMixin and ctypes setup). prototype.py imports from here.
"""

from __future__ import annotations

import sys

from PySide6.QtCore import QPoint, QRect
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QWidget

if not sys.platform.startswith("win32"):
    # Non-Windows: minimal stub so imports and AgentStudioWindow succeed (CI / Linux).
    class LowLevelNativeChromeMixin:
        resize_border_override = None
        titlebar_height = 40

        def _apply_native_styles(self) -> None:
            return

        def _process_native_event(self, message: object):
            return None

        def _point_in_titlebar_drag_region(self, x: int, y: int) -> bool:
            return False

else:
    import ctypes
    from ctypes import wintypes

    try:
        LRESULT = wintypes.LRESULT  # type: ignore[attr-defined]
    except AttributeError:
        LRESULT = ctypes.c_longlong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_long

    # =========================
    # WinAPI constants/types (verbatim from prototype.py)
    # =========================

    user32 = ctypes.windll.user32
    dwmapi = ctypes.windll.dwmapi

    WM_NCCALCSIZE = 0x0083
    WM_NCHITTEST = 0x0084
    WM_GETMINMAXINFO = 0x0024
    WM_NCLBUTTONDBLCLK = 0x00A3

    HTNOWHERE = 0
    HTCLIENT = 1
    HTCAPTION = 2
    HTLEFT = 10
    HTRIGHT = 11
    HTTOP = 12
    HTTOPLEFT = 13
    HTTOPRIGHT = 14
    HTBOTTOM = 15
    HTBOTTOMLEFT = 16
    HTBOTTOMRIGHT = 17

    MONITOR_DEFAULTTONEAREST = 2

    SM_CXSIZEFRAME = 32
    SM_CYSIZEFRAME = 33
    SM_CXPADDEDBORDER = 92

    DWMWA_VISIBLE_FRAME_BORDER_THICKNESS = 37

    GWL_STYLE = -16
    WS_SYSMENU = 0x00080000
    WS_THICKFRAME = 0x00040000
    WS_CAPTION = 0x00C00000
    WS_MINIMIZEBOX = 0x00020000
    WS_MAXIMIZEBOX = 0x00010000

    SWP_FRAMECHANGED = 0x0020
    SWP_NOMOVE = 0x0002
    SWP_NOSIZE = 0x0001
    SWP_NOZORDER = 0x0004

    WM_NCLBUTTONDOWN = 0x00A1

    class POINT(ctypes.Structure):
        _fields_ = [
            ("x", wintypes.LONG),
            ("y", wintypes.LONG),
        ]

    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", wintypes.LONG),
            ("top", wintypes.LONG),
            ("right", wintypes.LONG),
            ("bottom", wintypes.LONG),
        ]

    class MINMAXINFO(ctypes.Structure):
        _fields_ = [
            ("ptReserved", POINT),
            ("ptMaxSize", POINT),
            ("ptMaxPosition", POINT),
            ("ptMinTrackSize", POINT),
            ("ptMaxTrackSize", POINT),
        ]

    class MONITORINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", RECT),
            ("rcWork", RECT),
            ("dwFlags", wintypes.DWORD),
        ]

    class NCCALCSIZE_PARAMS(ctypes.Structure):
        _fields_ = [
            ("rgrc", RECT * 3),
            ("lppos", ctypes.c_void_p),
        ]

    class MSG(ctypes.Structure):
        _fields_ = [
            ("hwnd", wintypes.HWND),
            ("message", wintypes.UINT),
            ("wParam", wintypes.WPARAM),
            ("lParam", wintypes.LPARAM),
            ("time", wintypes.DWORD),
            ("pt", POINT),
            ("lPrivate", wintypes.DWORD),
        ]

    def get_x_lparam(lp: int) -> int:
        return ctypes.c_short(lp & 0xFFFF).value

    def get_y_lparam(lp: int) -> int:
        return ctypes.c_short((lp >> 16) & 0xFFFF).value

    dwmapi.DwmDefWindowProc.argtypes = [
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
        ctypes.POINTER(LRESULT),
    ]
    dwmapi.DwmDefWindowProc.restype = wintypes.BOOL

    user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
    user32.MonitorFromWindow.restype = wintypes.HMONITOR

    user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(MONITORINFO)]
    user32.GetMonitorInfoW.restype = wintypes.BOOL

    user32.GetSystemMetrics.argtypes = [ctypes.c_int]
    user32.GetSystemMetrics.restype = ctypes.c_int

    user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetWindowLongW.restype = wintypes.LONG

    user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LONG]
    user32.SetWindowLongW.restype = wintypes.LONG

    user32.SetWindowPos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]
    user32.SetWindowPos.restype = wintypes.BOOL

    user32.DefWindowProcW.argtypes = [
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
    ]
    user32.DefWindowProcW.restype = LRESULT

    class LowLevelNativeChromeMixin:
        """
        Низкоуровневая реализация custom non-client поведения для Windows.

        Требует:
          - top-level QWidget/QMainWindow
          - frameless окно
          - self.titlebar_widget
          - self.no_drag_widgets (list[QWidget])
        """

        resize_border_override = None  # если None, берём системную толщину
        titlebar_height = 40

        def _apply_native_styles(self):
            """Restore Win32 styles that Qt.FramelessWindowHint strips."""
            hwnd = int(self.winId())
            style = user32.GetWindowLongW(hwnd, GWL_STYLE)
            style |= (
                WS_THICKFRAME | WS_CAPTION | WS_SYSMENU
                | WS_MAXIMIZEBOX | WS_MINIMIZEBOX
            )
            user32.SetWindowLongW(hwnd, GWL_STYLE, style)
            user32.SetWindowPos(
                hwnd, None, 0, 0, 0, 0,
                SWP_FRAMECHANGED | SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER,
            )

        def _system_resize_border_px(self) -> int:
            frame_x = user32.GetSystemMetrics(SM_CXSIZEFRAME)
            padded = user32.GetSystemMetrics(SM_CXPADDEDBORDER)
            return frame_x + padded

        def _effective_resize_border_px(self) -> int:
            if self.resize_border_override is not None:
                return int(self.resize_border_override)
            return self._system_resize_border_px()

        def _is_point_in_widget(self, widget: QWidget, x: int, y: int) -> bool:
            if widget is None or not widget.isVisible():
                return False
            top_left = widget.mapTo(self, QPoint(0, 0))
            rect = QRect(top_left, widget.size())
            return rect.contains(x, y)

        def _point_hits_no_drag(self, x: int, y: int) -> bool:
            for w in getattr(self, "no_drag_widgets", []):
                if self._is_point_in_widget(w, x, y):
                    return True
            return False

        def _point_in_titlebar_drag_region(self, x: int, y: int) -> bool:
            titlebar = getattr(self, "titlebar_widget", None)
            if titlebar is None or not titlebar.isVisible():
                return False

            top_left = titlebar.mapTo(self, QPoint(0, 0))
            rect = QRect(top_left, titlebar.size())
            if not rect.contains(x, y):
                return False

            if self._point_hits_no_drag(x, y):
                return False

            return True

        def _hit_test_native(self, x: int, y: int) -> int:
            w = self.width()
            h = self.height()
            border = self._effective_resize_border_px()

            if w <= 0 or h <= 0:
                return HTCLIENT

            if not self.isMaximized():
                on_left = x < border
                on_right = x >= w - border
                on_top = y < border
                on_bottom = y >= h - border

                if on_top and on_left:
                    return HTTOPLEFT
                if on_top and on_right:
                    return HTTOPRIGHT
                if on_bottom and on_left:
                    return HTBOTTOMLEFT
                if on_bottom and on_right:
                    return HTBOTTOMRIGHT
                if on_left:
                    return HTLEFT
                if on_right:
                    return HTRIGHT
                if on_top:
                    return HTTOP
                if on_bottom:
                    return HTBOTTOM

            if self._point_hits_no_drag(x, y):
                return HTCLIENT

            if self._point_in_titlebar_drag_region(x, y):
                return HTCAPTION

            return HTCLIENT

        def _handle_getminmaxinfo(self, hwnd: int, lparam: int) -> tuple[bool, int]:
            """
            Корректный maximize по рабочей области монитора.
            Это нужно для frameless/custom windows.
            """
            mmi = ctypes.cast(lparam, ctypes.POINTER(MINMAXINFO)).contents

            monitor = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
            if not monitor:
                return False, 0

            mi = MONITORINFO()
            mi.cbSize = ctypes.sizeof(MONITORINFO)
            if not user32.GetMonitorInfoW(monitor, ctypes.byref(mi)):
                return False, 0

            rc_monitor = mi.rcMonitor
            rc_work = mi.rcWork

            mmi.ptMaxPosition.x = rc_work.left - rc_monitor.left
            mmi.ptMaxPosition.y = rc_work.top - rc_monitor.top
            mmi.ptMaxSize.x = rc_work.right - rc_work.left
            mmi.ptMaxSize.y = rc_work.bottom - rc_work.top

            return True, 0

        def _handle_nccalcsize(self, wparam: int, lparam: int) -> tuple[bool, int]:
            """
            Убираем стандартную non-client рамку.
            Для кастомного frame при wParam=TRUE обычно возвращают 0.
            """
            if wparam:
                return True, 0
            return False, 0

        def _process_native_event(self, message):
            """Returns (True, result) if handled, None otherwise."""
            msg = MSG.from_address(int(message))
            # Do not call self.winId() here: it forces native window realization and
            # on Windows can re-enter CreateWindowEx while the platform window is
            # still being created, leading to repeated failures and log spam.
            hwnd = msg.hwnd
            if not hwnd:
                return None

            if msg.message == WM_NCHITTEST:
                local = self.mapFromGlobal(QCursor.pos())
                return True, self._hit_test_native(local.x(), local.y())

            if msg.message in (WM_NCLBUTTONDOWN, WM_NCLBUTTONDBLCLK):
                result = user32.DefWindowProcW(
                    hwnd, msg.message, msg.wParam, msg.lParam,
                )
                return True, int(result)

            if msg.message == WM_NCCALCSIZE:
                handled, result = self._handle_nccalcsize(msg.wParam, msg.lParam)
                if handled:
                    return True, result

            if msg.message == WM_GETMINMAXINFO:
                handled, result = self._handle_getminmaxinfo(int(hwnd), msg.lParam)
                if handled:
                    return True, result

            return None
