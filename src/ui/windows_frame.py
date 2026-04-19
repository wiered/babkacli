"""Windows native frame helpers for extended client area windows."""

from __future__ import annotations

import os
from typing import Final

from PySide6.QtCore import QPoint, QRect
from PySide6.QtWidgets import QAbstractButton, QWidget

WINDOW_RESIZE_BORDER_PX: Final[int] = 6
WINDOWS_NATIVE_EVENT_TYPES: Final[set[object]] = {
    "windows_generic_MSG",
    "windows_dispatcher_MSG",
    b"windows_generic_MSG",
    b"windows_dispatcher_MSG",
}

WM_GETMINMAXINFO: Final[int] = 0x0024
WM_NCCALCSIZE: Final[int] = 0x0083
WM_NCHITTEST: Final[int] = 0x0084
WM_DWMCOMPOSITIONCHANGED: Final[int] = 0x031E

DWMWA_USE_IMMERSIVE_DARK_MODE: Final[int] = 20
DWMWA_BORDER_COLOR: Final[int] = 34
DWMWA_CAPTION_COLOR: Final[int] = 35
DWMWA_TEXT_COLOR: Final[int] = 36

SM_CXSIZEFRAME: Final[int] = 32
SM_CYSIZEFRAME: Final[int] = 33
SM_CXPADDEDBORDER: Final[int] = 92
SM_CYCAPTION: Final[int] = 4

HTCLIENT: Final[int] = 1
HTCAPTION: Final[int] = 2
HTLEFT: Final[int] = 10
HTRIGHT: Final[int] = 11
HTTOP: Final[int] = 12
HTTOPLEFT: Final[int] = 13
HTTOPRIGHT: Final[int] = 14
HTBOTTOM: Final[int] = 15
HTBOTTOMLEFT: Final[int] = 16
HTBOTTOMRIGHT: Final[int] = 17

if os.name == "nt":
    import ctypes
    from ctypes import wintypes

    class MSG(ctypes.Structure):
        _fields_ = [
            ("hwnd", wintypes.HWND),
            ("message", wintypes.UINT),
            ("wParam", wintypes.WPARAM),
            ("lParam", wintypes.LPARAM),
            ("time", wintypes.DWORD),
            ("pt", wintypes.POINT),
        ]

    class POINT(ctypes.Structure):
        _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

    class MINMAXINFO(ctypes.Structure):
        _fields_ = [
            ("ptReserved", POINT),
            ("ptMaxSize", POINT),
            ("ptMaxPosition", POINT),
            ("ptMinTrackSize", POINT),
            ("ptMaxTrackSize", POINT),
        ]

    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", wintypes.LONG),
            ("top", wintypes.LONG),
            ("right", wintypes.LONG),
            ("bottom", wintypes.LONG),
        ]

    class MONITORINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", RECT),
            ("rcWork", RECT),
            ("dwFlags", wintypes.DWORD),
        ]

    class MARGINS(ctypes.Structure):
        _fields_ = [
            ("cxLeftWidth", ctypes.c_int),
            ("cxRightWidth", ctypes.c_int),
            ("cyTopHeight", ctypes.c_int),
            ("cyBottomHeight", ctypes.c_int),
        ]

    class NCCALCSIZE_PARAMS(ctypes.Structure):
        _fields_ = [
            ("rgrc", RECT * 3),
            ("lppos", ctypes.c_void_p),
        ]

    _MONITOR_DEFAULTTONEAREST = 2
    _user32 = ctypes.windll.user32
    _monitor_from_window = _user32.MonitorFromWindow
    _monitor_from_window.restype = wintypes.HANDLE
    _monitor_from_window.argtypes = [wintypes.HWND, wintypes.DWORD]
    _get_monitor_info = _user32.GetMonitorInfoW
    _get_monitor_info.restype = wintypes.BOOL
    _get_monitor_info.argtypes = [wintypes.HANDLE, ctypes.POINTER(MONITORINFO)]
    _get_dpi_for_window = getattr(_user32, "GetDpiForWindow", None)
    if _get_dpi_for_window is not None:
        _get_dpi_for_window.restype = wintypes.UINT
        _get_dpi_for_window.argtypes = [wintypes.HWND]
    _get_system_metrics_for_dpi = getattr(_user32, "GetSystemMetricsForDpi", None)
    if _get_system_metrics_for_dpi is not None:
        _get_system_metrics_for_dpi.restype = ctypes.c_int
        _get_system_metrics_for_dpi.argtypes = [ctypes.c_int, wintypes.UINT]
    _get_system_metrics = _user32.GetSystemMetrics
    _get_system_metrics.restype = ctypes.c_int
    _get_system_metrics.argtypes = [ctypes.c_int]
    _set_window_pos = _user32.SetWindowPos
    _set_window_pos.restype = wintypes.BOOL
    _set_window_pos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]
    _LRESULT = (
        ctypes.c_longlong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_long
    )
    _dwmapi = ctypes.windll.dwmapi
    _dwm_def_window_proc = _dwmapi.DwmDefWindowProc
    _dwm_def_window_proc.restype = wintypes.BOOL
    _dwm_def_window_proc.argtypes = [
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
        ctypes.POINTER(_LRESULT),
    ]
    _dwm_set_window_attribute = _dwmapi.DwmSetWindowAttribute
    _dwm_set_window_attribute.restype = ctypes.c_long
    _dwm_set_window_attribute.argtypes = [
        wintypes.HWND,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
    ]
    _dwm_extend_frame_into_client_area = _dwmapi.DwmExtendFrameIntoClientArea
    _dwm_extend_frame_into_client_area.restype = ctypes.c_long
    _dwm_extend_frame_into_client_area.argtypes = [
        wintypes.HWND,
        ctypes.POINTER(MARGINS),
    ]

    _SWP_NOMOVE = 0x0002
    _SWP_NOSIZE = 0x0001
    _SWP_NOZORDER = 0x0004
    _SWP_NOACTIVATE = 0x0010
    _SWP_FRAMECHANGED = 0x0020

    _GWL_STYLE: Final[int] = -16
    _WS_CAPTION: Final[int] = 0x00C00000
    _WS_THICKFRAME: Final[int] = 0x00040000
    _WS_SYSMENU: Final[int] = 0x00080000
    _WS_MINIMIZEBOX: Final[int] = 0x00020000
    _WS_MAXIMIZEBOX: Final[int] = 0x00010000
    _get_window_long = _user32.GetWindowLongW
    _get_window_long.restype = ctypes.c_long
    _get_window_long.argtypes = [wintypes.HWND, ctypes.c_int]
    _set_window_long = _user32.SetWindowLongW
    _set_window_long.restype = ctypes.c_long
    _set_window_long.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]


def _signed_word(value: int) -> int:
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def point_from_lparam(lparam: int) -> QPoint:
    return QPoint(_signed_word(lparam), _signed_word(lparam >> 16))


def _system_metric(metric: int, *, dpi: int | None = None) -> int:
    if os.name != "nt":
        return 0
    if dpi is not None and _get_system_metrics_for_dpi is not None:
        return int(_get_system_metrics_for_dpi(metric, dpi))
    return int(_get_system_metrics(metric))


def _colorref(red: int, green: int, blue: int) -> int:
    return (red & 0xFF) | ((green & 0xFF) << 8) | ((blue & 0xFF) << 16)


def frame_border_thickness_for_window(window: QWidget) -> int:
    if os.name != "nt":
        return 0

    hwnd = int(window.winId())
    dpi = (
        int(_get_dpi_for_window(hwnd))
        if hwnd and _get_dpi_for_window is not None
        else None
    )
    return max(
        0,
        _system_metric(SM_CYSIZEFRAME, dpi=dpi)
        + _system_metric(SM_CXPADDEDBORDER, dpi=dpi),
    )


def caption_height_for_window(window: QWidget) -> int:
    if os.name != "nt":
        return 0

    hwnd = int(window.winId())
    dpi = (
        int(_get_dpi_for_window(hwnd))
        if hwnd and _get_dpi_for_window is not None
        else None
    )
    return max(0, _system_metric(SM_CYCAPTION, dpi=dpi))


def top_client_inset_for_window(window: QWidget) -> int:
    if os.name != "nt":
        return 0
    if window.isMaximized():
        return 0
    return frame_border_thickness_for_window(window)


def apply_nccalcsize_insets(window: QWidget, rect: RECT) -> None:
    top_inset = top_client_inset_for_window(window)
    if top_inset > 0:
        rect.top += top_inset


def apply_extended_client_area(window: QWidget, *, top_margin: int) -> None:
    if os.name != "nt":
        return

    hwnd = int(window.winId())
    if hwnd == 0:
        return

    margins = MARGINS(0, 0, max(0, top_margin), 0)
    _dwm_extend_frame_into_client_area(hwnd, ctypes.byref(margins))
    _set_window_pos(
        hwnd,
        0,
        0,
        0,
        0,
        0,
        _SWP_NOMOVE | _SWP_NOSIZE | _SWP_NOZORDER | _SWP_NOACTIVATE | _SWP_FRAMECHANGED,
    )


def set_windows_title_bar_colors(
    window: QWidget,
    *,
    caption_rgb: tuple[int, int, int],
    text_rgb: tuple[int, int, int],
    border_rgb: tuple[int, int, int] | None = None,
) -> None:
    if os.name != "nt":
        return

    hwnd = int(window.winId())
    if hwnd == 0:
        return

    immersive_dark = ctypes.c_int(1)
    _dwm_set_window_attribute(
        hwnd,
        DWMWA_USE_IMMERSIVE_DARK_MODE,
        ctypes.byref(immersive_dark),
        ctypes.sizeof(immersive_dark),
    )

    caption = wintypes.DWORD(_colorref(*caption_rgb))
    _dwm_set_window_attribute(
        hwnd,
        DWMWA_CAPTION_COLOR,
        ctypes.byref(caption),
        ctypes.sizeof(caption),
    )

    text = wintypes.DWORD(_colorref(*text_rgb))
    _dwm_set_window_attribute(
        hwnd,
        DWMWA_TEXT_COLOR,
        ctypes.byref(text),
        ctypes.sizeof(text),
    )

    if border_rgb is not None:
        border = wintypes.DWORD(_colorref(*border_rgb))
        _dwm_set_window_attribute(
            hwnd,
            DWMWA_BORDER_COLOR,
            ctypes.byref(border),
            ctypes.sizeof(border),
        )


def restore_caption_style(window: QWidget) -> None:
    """Re-add WS_CAPTION and WS_THICKFRAME after FramelessWindowHint removes them.

    Qt's FramelessWindowHint strips these styles so the window has no native chrome,
    but Windows shell components (PowerToys, FancyZones, Aero Shake, taskbar previews)
    rely on WS_CAPTION to treat the window as a normal movable window.  Restoring the
    styles here keeps full shell integration while WM_NCCALCSIZE collapses the visible
    NC area so no native title bar is actually drawn.
    """
    if os.name != "nt":
        return
    hwnd = int(window.winId())
    if hwnd == 0:
        return
    style = _get_window_long(hwnd, _GWL_STYLE)
    style |= (
        _WS_CAPTION | _WS_THICKFRAME | _WS_SYSMENU | _WS_MINIMIZEBOX | _WS_MAXIMIZEBOX
    )
    _set_window_long(hwnd, _GWL_STYLE, style)
    _set_window_pos(
        hwnd,
        0,
        0,
        0,
        0,
        0,
        _SWP_NOMOVE | _SWP_NOSIZE | _SWP_NOZORDER | _SWP_NOACTIVATE | _SWP_FRAMECHANGED,
    )


def hit_test_title_bar(title_bar: QWidget | None, cursor_pos: QPoint) -> bool:
    if title_bar is None or not title_bar.isVisible():
        return False

    title_bar_top_left = title_bar.mapToGlobal(QPoint(0, 0))
    title_bar_rect = QRect(title_bar_top_left, title_bar.size())
    if not title_bar_rect.contains(cursor_pos):
        return False

    local_pos = cursor_pos - title_bar_top_left
    widget = title_bar.childAt(local_pos)
    while widget is not None:
        if isinstance(widget, QAbstractButton):
            return False
        widget = widget.parentWidget()

    return True


def hit_test_resize_border(
    frame_geometry: QRect,
    cursor_pos: QPoint,
    *,
    resize_border_px: int = WINDOW_RESIZE_BORDER_PX,
) -> int:
    left = cursor_pos.x() - frame_geometry.left() <= resize_border_px
    right = frame_geometry.right() - cursor_pos.x() <= resize_border_px
    top = cursor_pos.y() - frame_geometry.top() <= resize_border_px
    bottom = frame_geometry.bottom() - cursor_pos.y() <= resize_border_px

    if top and left:
        return HTTOPLEFT
    if top and right:
        return HTTOPRIGHT
    if bottom and left:
        return HTBOTTOMLEFT
    if bottom and right:
        return HTBOTTOMRIGHT
    if top:
        return HTTOP
    if left:
        return HTLEFT
    if right:
        return HTRIGHT
    if bottom:
        return HTBOTTOM

    return HTCLIENT


def resolve_hit_test(
    *,
    title_bar: QWidget | None,
    frame_geometry: QRect,
    cursor_pos: QPoint,
    is_maximized: bool,
    resize_border_px: int = WINDOW_RESIZE_BORDER_PX,
) -> int:
    if hit_test_title_bar(title_bar, cursor_pos):
        return HTCAPTION

    if is_maximized:
        return HTCLIENT

    return hit_test_resize_border(
        frame_geometry,
        cursor_pos,
        resize_border_px=resize_border_px,
    )


def native_frame_event(
    *,
    window: QWidget,
    title_bar: QWidget | None,
    event_type: object,
    message: object,
) -> tuple[bool, int] | None:
    if os.name != "nt" or event_type not in WINDOWS_NATIVE_EVENT_TYPES:
        return None

    try:
        msg = int(message)
    except (TypeError, ValueError):
        return None

    try:
        native_msg = MSG.from_address(msg)
    except (ValueError, OSError):
        return None

    handled_result = _LRESULT()
    if _dwm_def_window_proc(
        native_msg.hwnd,
        native_msg.message,
        native_msg.wParam,
        native_msg.lParam,
        ctypes.byref(handled_result),
    ):
        return True, handled_result.value

    if native_msg.message == WM_GETMINMAXINFO:
        monitor = _monitor_from_window(native_msg.hwnd, _MONITOR_DEFAULTTONEAREST)
        if monitor:
            mmi = MINMAXINFO.from_address(native_msg.lParam)
            monitor_info = MONITORINFO()
            monitor_info.cbSize = ctypes.sizeof(MONITORINFO)
            if _get_monitor_info(monitor, ctypes.byref(monitor_info)):
                work = monitor_info.rcWork
                screen = monitor_info.rcMonitor
                mmi.ptMaxPosition.x = work.left - screen.left
                mmi.ptMaxPosition.y = work.top - screen.top
                mmi.ptMaxSize.x = work.right - work.left
                mmi.ptMaxSize.y = work.bottom - work.top
                mmi.ptMaxTrackSize.x = mmi.ptMaxSize.x
                mmi.ptMaxTrackSize.y = mmi.ptMaxSize.y
        return True, 0

    if native_msg.message == WM_DWMCOMPOSITIONCHANGED:
        top_margin = title_bar.height() if title_bar is not None else 0
        apply_extended_client_area(window, top_margin=top_margin)
        return False, 0

    if native_msg.message == WM_NCCALCSIZE:
        if native_msg.wParam:
            params = NCCALCSIZE_PARAMS.from_address(native_msg.lParam)
            apply_nccalcsize_insets(window, params.rgrc[0])
            return True, 0
        rect = RECT.from_address(native_msg.lParam)
        apply_nccalcsize_insets(window, rect)
        return True, 0

    if native_msg.message != WM_NCHITTEST:
        return None

    cursor_pos = point_from_lparam(native_msg.lParam)
    return True, resolve_hit_test(
        title_bar=title_bar,
        frame_geometry=window.frameGeometry(),
        cursor_pos=cursor_pos,
        is_maximized=window.isMaximized(),
    )
